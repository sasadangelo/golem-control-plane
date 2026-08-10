# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Unit tests for the A2A peer handshake endpoint.

POST /agents/{agent_id}/handshake — runner pushes its Agent Card to the
Control Plane broker so the card is immediately available for peer-discovery
via GET /agents/{id}/card, without waiting for a status-poll cycle.
"""

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

_SAMPLE_CARD: dict = {
    "id": "golem-agent-hs",
    "name": "Handshake Agent",
    "description": "Agent used in handshake tests.",
    "version": "0.1.0",
    "endpoint": "http://golem-agent-hs.golem-agent-hs.svc.cluster.local:8000",
    "capabilities": {"streaming": True, "pushNotifications": False},
    "skills": [{"id": "bash", "name": "bash"}],
}

_SAMPLE_CONFIG = b"""
agent:
  id: golem-agent-hs
  name: handshake-agent
  system_prompt: You are a test agent.
llm:
  provider: watsonx
  model: openai/gpt-oss-120b
  project_id: test-project
  url: https://us-south.ml.cloud.ibm.com
"""


def _create_agent(client: TestClient, mock_provisioner: MagicMock, agent_id: str) -> str:
    """Helper: provision a sandbox and return its agent_id."""
    from domain.models import SandboxHandle, SandboxStatus

    handle = SandboxHandle(agent_id=agent_id)
    handle.status = SandboxStatus.RUNNING
    mock_provisioner.create_sandbox.return_value = handle

    resp = client.post(
        "/agents",
        files={"config": ("config.yaml", _SAMPLE_CONFIG, "application/x-yaml")},
        data={"ttl_seconds": "3600"},
    )
    assert resp.status_code == 201
    return resp.json()["agent_id"]


# ---------------------------------------------------------------------------
# POST /agents/{agent_id}/handshake — happy path
# ---------------------------------------------------------------------------


def test_handshake_returns_200_and_registered(cp_client: TestClient, mock_provisioner: MagicMock) -> None:
    """Handshake must return 200 with registered=True and the correct agent_id."""
    agent_id = _create_agent(cp_client, mock_provisioner, agent_id="golem-agent-hs")

    resp = cp_client.post(f"/agents/{agent_id}/handshake", json={"card": _SAMPLE_CARD})
    assert resp.status_code == 200
    body = resp.json()
    assert body["registered"] is True
    assert body["agent_id"] == agent_id


def test_handshake_card_retrievable_via_get_card(cp_client: TestClient, mock_provisioner: MagicMock) -> None:
    """After handshake, GET /agents/{id}/card must return the pushed card."""
    agent_id = _create_agent(cp_client, mock_provisioner, agent_id="golem-agent-hs")

    cp_client.post(f"/agents/{agent_id}/handshake", json={"card": _SAMPLE_CARD})

    card_resp = cp_client.get(f"/agents/{agent_id}/card")
    assert card_resp.status_code == 200
    assert card_resp.json() == _SAMPLE_CARD


def test_handshake_updates_sandbox_agent_card(cp_client: TestClient, mock_provisioner: MagicMock) -> None:
    """After handshake, the in-memory sandbox handle must reflect the card."""
    import interfaces.api.app as cp_main

    agent_id = _create_agent(cp_client, mock_provisioner, agent_id="golem-agent-hs")
    cp_client.post(f"/agents/{agent_id}/handshake", json={"card": _SAMPLE_CARD})

    assert cp_main._sandboxes[agent_id].agent_card == _SAMPLE_CARD


def test_handshake_card_appears_in_status(cp_client: TestClient, mock_provisioner: MagicMock) -> None:
    """After handshake, GET /agents/{id}/status must include the agent_card."""
    from domain.models import SandboxHandle, SandboxStatus

    agent_id = _create_agent(cp_client, mock_provisioner, agent_id="golem-agent-hs")

    # Make get_status return RUNNING with the card already present
    refreshed = SandboxHandle(agent_id=agent_id)
    refreshed.status = SandboxStatus.RUNNING
    refreshed.agent_card = _SAMPLE_CARD
    mock_provisioner.get_status.return_value = refreshed

    cp_client.post(f"/agents/{agent_id}/handshake", json={"card": _SAMPLE_CARD})

    status_resp = cp_client.get(f"/agents/{agent_id}/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["agent_card"] == _SAMPLE_CARD


# ---------------------------------------------------------------------------
# POST /agents/{agent_id}/handshake — error cases
# ---------------------------------------------------------------------------


def test_handshake_unknown_agent_returns_404(cp_client: TestClient) -> None:
    """Handshake for a non-existent sandbox must return 404."""
    resp = cp_client.post("/agents/does-not-exist/handshake", json={"card": _SAMPLE_CARD})
    assert resp.status_code == 404


def test_handshake_replaces_existing_card(cp_client: TestClient, mock_provisioner: MagicMock) -> None:
    """A second handshake must overwrite the previously registered card."""
    agent_id = _create_agent(cp_client, mock_provisioner, agent_id="golem-agent-hs")

    cp_client.post(f"/agents/{agent_id}/handshake", json={"card": _SAMPLE_CARD})

    updated_card = {**_SAMPLE_CARD, "version": "0.2.0"}
    cp_client.post(f"/agents/{agent_id}/handshake", json={"card": updated_card})

    card_resp = cp_client.get(f"/agents/{agent_id}/card")
    assert card_resp.json()["version"] == "0.2.0"
