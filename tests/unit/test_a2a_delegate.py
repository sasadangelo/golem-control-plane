# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Unit tests for the A2A delegation endpoint.

POST /agents/{source_id}/delegate — Control Plane brokers a task from
a source agent to a target agent by forwarding it to the target runner.
"""

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

_SAMPLE_CONFIG_TEMPLATE = b"""
agent:
  id: {agent_id}
  name: test-agent
  system_prompt: You are a test agent.
llm:
  provider: watsonx
  model: openai/gpt-oss-120b
  project_id: test-project
  url: https://us-south.ml.cloud.ibm.com
"""


def _post_agent(client: TestClient, mock_provisioner: MagicMock, agent_id: str) -> str:
    """Create an agent sandbox and return its agent_id."""
    from domain.models import SandboxHandle, SandboxStatus

    handle = SandboxHandle(agent_id=agent_id)
    handle.status = SandboxStatus.RUNNING
    mock_provisioner.create_sandbox.return_value = handle

    config = _SAMPLE_CONFIG_TEMPLATE.replace(b"{agent_id}", agent_id.encode())
    resp = client.post(
        "/agents",
        files={"config": ("config.yaml", config, "application/x-yaml")},
        data={"ttl_seconds": "3600"},
    )
    assert resp.status_code == 201
    return agent_id


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_delegate_returns_201(cp_client: TestClient, mock_provisioner: MagicMock) -> None:
    """POST /agents/{source}/delegate must return 201 with task metadata."""
    _post_agent(cp_client, mock_provisioner, "source-agent-001")
    _post_agent(cp_client, mock_provisioner, "target-agent-001")

    resp = cp_client.post(
        "/agents/source-agent-001/delegate",
        json={"target_agent_id": "target-agent-001", "message": "Write a report."},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["source_agent_id"] == "source-agent-001"
    assert body["target_agent_id"] == "target-agent-001"
    assert body["task_id"].startswith("task-")
    assert body["status"] in ("submitted", "working", "completed")


def test_delegate_task_appears_in_target_tasks(cp_client: TestClient, mock_provisioner: MagicMock) -> None:
    """After delegation the task must be visible via GET /agents/{target}/tasks."""
    _post_agent(cp_client, mock_provisioner, "source-agent-002")
    _post_agent(cp_client, mock_provisioner, "target-agent-002")

    delegate_resp = cp_client.post(
        "/agents/source-agent-002/delegate",
        json={"target_agent_id": "target-agent-002", "message": "Produce analysis."},
    )
    assert delegate_resp.status_code == 201
    task_id = delegate_resp.json()["task_id"]

    # The task should now be visible in the target agent's task list.
    tasks_resp = cp_client.get("/agents/target-agent-002/tasks")
    assert tasks_resp.status_code == 200
    task_ids = [t["task_id"] for t in tasks_resp.json()]
    assert task_id in task_ids


def test_delegate_source_field_is_a2a(cp_client: TestClient, mock_provisioner: MagicMock) -> None:
    """Delegated tasks must have source='a2a' by default."""
    _post_agent(cp_client, mock_provisioner, "source-agent-003")
    _post_agent(cp_client, mock_provisioner, "target-agent-003")

    cp_client.post(
        "/agents/source-agent-003/delegate",
        json={"target_agent_id": "target-agent-003", "message": "Do something."},
    )

    tasks = cp_client.get("/agents/target-agent-003/tasks").json()
    assert any(t["source"] == "a2a" for t in tasks)


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


def test_delegate_unknown_source_returns_404(cp_client: TestClient) -> None:
    """POST /agents/{source}/delegate must return 404 when source does not exist."""
    resp = cp_client.post(
        "/agents/does-not-exist/delegate",
        json={"target_agent_id": "also-does-not-exist", "message": "x"},
    )
    assert resp.status_code == 404


def test_delegate_unknown_target_returns_404(cp_client: TestClient, mock_provisioner: MagicMock) -> None:
    """POST /agents/{source}/delegate must return 404 when target does not exist."""
    _post_agent(cp_client, mock_provisioner, "source-agent-404")

    resp = cp_client.post(
        "/agents/source-agent-404/delegate",
        json={"target_agent_id": "does-not-exist", "message": "x"},
    )
    assert resp.status_code == 404
