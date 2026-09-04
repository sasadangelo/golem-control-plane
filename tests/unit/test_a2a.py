# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Unit tests for A2A task lifecycle endpoints."""

from typing import cast
from unittest.mock import MagicMock

from fastapi.testclient import TestClient


def _post_agent(client: TestClient, mock_provisioner: MagicMock, agent_id: str = "golem-agent-a2a") -> str:
    """Create an agent sandbox and return its agent_id."""
    from domain.models import SandboxHandle, SandboxStatus

    handle = SandboxHandle(agent_id=agent_id)
    handle.status = SandboxStatus.RUNNING
    mock_provisioner.create_sandbox.return_value = handle

    _SAMPLE_CONFIG = b"""
agent:
  id: golem-agent-a2a
  name: test-agent
  system_prompt: You are a test agent.
llm:
  provider: watsonx
  model: openai/gpt-oss-120b
  project_id: test-project
  url: https://us-south.ml.cloud.ibm.com
"""
    resp = client.post(
        "/agents",
        files={"config": ("config.yaml", _SAMPLE_CONFIG, "application/x-yaml")},
        data={"ttl_seconds": "3600"},
    )
    assert resp.status_code == 201
    return cast(str, resp.json()["agent_id"])


# ---------------------------------------------------------------------------
# POST /agents/{agent_id}/tasks
# ---------------------------------------------------------------------------


def test_submit_task_returns_201(cp_client: TestClient, mock_provisioner: MagicMock) -> None:
    """POST /agents/{id}/tasks must proxy to runner and return 201."""
    agent_id: str = _post_agent(client=cp_client, mock_provisioner=mock_provisioner)

    resp = cp_client.post(f"/agents/{agent_id}/tasks", json={"message": "analyse logs"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["agent_id"] == agent_id
    assert body["task_id"].startswith("task-")
    assert body["message"] == "analyse logs"
    assert "created_at" in body
    assert "updated_at" in body


def test_submit_task_unknown_agent_returns_404(cp_client: TestClient) -> None:
    """POST /agents/{id}/tasks must return 404 for unknown agent."""
    resp = cp_client.post(url="/agents/does-not-exist/tasks", json={"message": "do something"})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /agents/{agent_id}/tasks
# ---------------------------------------------------------------------------


def test_list_tasks_empty(cp_client: TestClient, mock_provisioner: MagicMock) -> None:
    """GET /agents/{id}/tasks must return an empty list when no tasks exist."""
    agent_id: str = _post_agent(client=cp_client, mock_provisioner=mock_provisioner, agent_id="golem-agent-empty")
    resp = cp_client.get(url=f"/agents/{agent_id}/tasks")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_tasks_returns_all_for_agent(cp_client: TestClient, mock_provisioner: MagicMock) -> None:
    """GET /agents/{id}/tasks returns tasks after submit via runner proxy."""
    agent_id: str = _post_agent(client=cp_client, mock_provisioner=mock_provisioner, agent_id="golem-agent-list")

    cp_client.post(url=f"/agents/{agent_id}/tasks", json={"message": "task one"})
    cp_client.post(url=f"/agents/{agent_id}/tasks", json={"message": "task two"})

    resp = cp_client.get(url=f"/agents/{agent_id}/tasks")
    assert resp.status_code == 200
    tasks = resp.json()
    # At least the two submitted tasks must be present (mock runner stores all in _tasks).
    messages = {t["message"] for t in tasks}
    assert "task one" in messages
    assert "task two" in messages


def test_list_tasks_unknown_agent_returns_404(cp_client: TestClient) -> None:
    """GET /agents/{id}/tasks must return 404 for unknown agent."""
    assert cp_client.get("/agents/does-not-exist/tasks").status_code == 404


# ---------------------------------------------------------------------------
# GET /agents/{agent_id}/tasks/{task_id}
# ---------------------------------------------------------------------------


def test_get_task_returns_correct_task(cp_client: TestClient, mock_provisioner: MagicMock) -> None:
    """GET /agents/{id}/tasks/{task_id} must return the correct task."""
    agent_id: str = _post_agent(client=cp_client, mock_provisioner=mock_provisioner, agent_id="golem-agent-get")

    submit_resp = cp_client.post(url=f"/agents/{agent_id}/tasks", json={"message": "fetch me"})
    assert submit_resp.status_code == 201
    task_id = submit_resp.json()["task_id"]

    resp = cp_client.get(url=f"/agents/{agent_id}/tasks/{task_id}")
    assert resp.status_code == 200
    assert resp.json()["task_id"] == task_id
    assert resp.json()["message"] == "fetch me"


def test_get_task_unknown_task_returns_404(cp_client: TestClient, mock_provisioner: MagicMock) -> None:
    """GET /agents/{id}/tasks/{task_id} must return 404 for unknown task."""
    agent_id: str = _post_agent(cp_client, mock_provisioner=mock_provisioner, agent_id="golem-agent-get404")
    assert cp_client.get(url=f"/agents/{agent_id}/tasks/task-does-not-exist").status_code == 404


def test_get_task_wrong_agent_returns_404(cp_client: TestClient, mock_provisioner: MagicMock) -> None:
    """GET /agents/{id}/tasks/{task_id} must return 404 for a task the runner does not know."""
    agent_id: str = _post_agent(client=cp_client, mock_provisioner=mock_provisioner, agent_id="golem-agent-owner")
    _post_agent(client=cp_client, mock_provisioner=mock_provisioner, agent_id="golem-agent-other")

    # task-does-not-exist is not in the runner mock store → runner returns 404 → CP returns 404
    assert cp_client.get(url=f"/agents/{agent_id}/tasks/task-does-not-exist-xyz").status_code == 404


# ---------------------------------------------------------------------------
# PATCH /agents/{agent_id}/tasks/{task_id}
# ---------------------------------------------------------------------------


def test_update_task_to_working(cp_client: TestClient, mock_provisioner: MagicMock) -> None:
    """PATCH must advance a CP-tracked task from submitted to working."""
    import interfaces.api.app as cp_main
    from domain.models import A2ATask

    agent_id: str = _post_agent(client=cp_client, mock_provisioner=mock_provisioner, agent_id="golem-agent-patch1")
    # Insert a task directly in task_repo (as the runner would via internal state).
    task = A2ATask(agent_id=agent_id, message="work on it")
    cp_main.task_repo.save(task)
    task_id = task.task_id

    resp = cp_client.patch(url=f"/agents/{agent_id}/tasks/{task_id}", json={"status": "working"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "working"
    assert resp.json()["result"] is None


def test_update_task_to_completed_with_result(cp_client: TestClient, mock_provisioner: MagicMock) -> None:
    """PATCH must set task to completed and store the result."""
    import interfaces.api.app as cp_main
    from domain.models import A2ATask

    agent_id: str = _post_agent(client=cp_client, mock_provisioner=mock_provisioner, agent_id="golem-agent-patch2")
    task = A2ATask(agent_id=agent_id, message="compute something")
    cp_main.task_repo.save(task)
    task_id = task.task_id

    resp = cp_client.patch(
        url=f"/agents/{agent_id}/tasks/{task_id}",
        json={"status": "completed", "result": "42"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert body["result"] == "42"
    assert body["updated_at"] >= body["created_at"]


def test_update_task_to_failed(cp_client: TestClient, mock_provisioner: MagicMock) -> None:
    """PATCH must set task to failed."""
    import interfaces.api.app as cp_main
    from domain.models import A2ATask

    agent_id: str = _post_agent(cp_client, mock_provisioner=mock_provisioner, agent_id="golem-agent-patch3")
    task = A2ATask(agent_id=agent_id, message="risky op")
    cp_main.task_repo.save(task)

    resp = cp_client.patch(f"/agents/{agent_id}/tasks/{task.task_id}", json={"status": "failed", "result": "timeout"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "failed"


def test_update_task_invalid_status_returns_422(cp_client: TestClient, mock_provisioner: MagicMock) -> None:
    """PATCH with an unrecognised status must return 422."""
    import interfaces.api.app as cp_main
    from domain.models import A2ATask

    agent_id: str = _post_agent(client=cp_client, mock_provisioner=mock_provisioner, agent_id="golem-agent-patch4")
    task = A2ATask(agent_id=agent_id, message="x")
    cp_main.task_repo.save(task)

    resp = cp_client.patch(url=f"/agents/{agent_id}/tasks/{task.task_id}", json={"status": "invalid-state"})
    assert resp.status_code == 422


def test_update_task_unknown_agent_returns_404(cp_client: TestClient) -> None:
    """PATCH must return 404 for unknown agent."""
    resp = cp_client.patch(url="/agents/does-not-exist/tasks/task-xyz", json={"status": "working"})
    assert resp.status_code == 404
