# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Unit tests for Control Plane REST endpoints."""

from collections.abc import Callable
from typing import cast
from unittest.mock import MagicMock

import httpx
from fastapi.testclient import TestClient


def _req(client: TestClient, method: str, url: str, **kwargs: object) -> httpx.Response:
    """Typed wrapper around TestClient HTTP methods to satisfy pyright."""
    fn = cast(Callable[..., httpx.Response], getattr(client, method))
    return fn(url, **kwargs)


_SAMPLE_CONFIG = b"""
agent:
  id: golem-agent-abc
  name: test-agent
  system_prompt: You are a test agent.
  enabled_skill: bash
llm:
  provider: watsonx
  model: openai/gpt-oss-120b
  project_id: test-project
  url: https://us-south.ml.cloud.ibm.com
"""


def _post_agent(client: TestClient, config: bytes = _SAMPLE_CONFIG, ttl_seconds: int = 3600) -> httpx.Response:
    """Helper — POST /agents with a multipart config file."""
    return _req(
        client,
        "post",
        "/agents",
        files={"config": ("config.yaml", config, "application/x-yaml")},
        data={"ttl_seconds": str(ttl_seconds)},
    )


def test_health(cp_client: TestClient) -> None:
    """Health endpoint must return HTTP 200."""
    assert _req(cp_client, "get", "/health").status_code == 200
    assert _req(cp_client, "get", "/health").json() == {"status": "ok"}


def test_create_agent_returns_201(cp_client: TestClient, mock_provisioner: MagicMock) -> None:
    """POST /agents must return 201 with agent_id, namespace and status."""
    from models import SandboxHandle, SandboxStatus

    handle = SandboxHandle(agent_id="golem-agent-abc")
    handle.status = SandboxStatus.PENDING
    mock_provisioner.create_sandbox.return_value = handle

    response = _post_agent(cp_client)
    assert response.status_code == 201
    body = cast(dict[str, str], response.json())
    assert body["agent_id"] == "golem-agent-abc"
    assert body["status"] == "pending"


def test_create_agent_provisioner_error_returns_500(cp_client: TestClient, mock_provisioner: MagicMock) -> None:
    """POST /agents must return 500 when the provisioner raises."""
    mock_provisioner.create_sandbox.side_effect = RuntimeError("K8s unavailable")
    assert _post_agent(cp_client).status_code == 500


def test_get_status_unknown_agent_returns_404(cp_client: TestClient) -> None:
    """GET /agents/{id}/status must return 404 for unknown agent_id."""
    assert _req(cp_client, "get", "/agents/does-not-exist/status").status_code == 404


def test_get_status_known_agent(cp_client: TestClient, mock_provisioner: MagicMock) -> None:
    """GET /agents/{id}/status must return the current status."""
    from models import SandboxHandle, SandboxStatus

    handle = SandboxHandle(agent_id="golem-agent-xyz")
    handle.status = SandboxStatus.PENDING
    mock_provisioner.create_sandbox.return_value = handle

    _post_agent(cp_client)

    updated = SandboxHandle(agent_id="golem-agent-xyz")
    updated.status = SandboxStatus.RUNNING
    mock_provisioner.get_status.return_value = updated

    resp = _req(cp_client, "get", "/agents/golem-agent-xyz/status")
    assert resp.status_code == 200
    assert resp.json()["status"] == "running"


def test_delete_agent_returns_204(cp_client: TestClient, mock_provisioner: MagicMock) -> None:
    """DELETE /agents/{id} must return 204 and remove the agent."""
    from models import SandboxHandle, SandboxStatus

    handle = SandboxHandle(agent_id="golem-agent-del")
    handle.status = SandboxStatus.RUNNING
    mock_provisioner.create_sandbox.return_value = handle

    _post_agent(cp_client)
    assert _req(cp_client, "delete", "/agents/golem-agent-del").status_code == 204
    assert _req(cp_client, "get", "/agents/golem-agent-del/status").status_code == 404


def test_delete_unknown_agent_returns_404(cp_client: TestClient) -> None:
    """DELETE /agents/{id} must return 404 for unknown agent_id."""
    assert _req(cp_client, "delete", "/agents/does-not-exist").status_code == 404


def test_list_agents(cp_client: TestClient, mock_provisioner: MagicMock) -> None:
    """GET /agents must return all created agents."""
    from models import SandboxHandle, SandboxStatus

    for i in range(2):
        h = SandboxHandle(agent_id=f"golem-agent-list-{i}")
        h.status = SandboxStatus.PENDING
        mock_provisioner.create_sandbox.return_value = h
        _post_agent(cp_client)

    resp = _req(cp_client, "get", "/agents")
    assert resp.status_code == 200
    ids = [a["agent_id"] for a in resp.json()]
    assert "golem-agent-list-0" in ids
    assert "golem-agent-list-1" in ids


def test_get_card_not_found(cp_client: TestClient) -> None:
    """GET /agents/{id}/card must return 404 when no card is registered."""
    assert _req(cp_client, "get", "/agents/does-not-exist/card").status_code == 404
