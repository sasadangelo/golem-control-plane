# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Unit tests for the A2A Agent Card endpoint (GET /.well-known/agent.json)."""

import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


def test_agent_card_returns_200(client: TestClient) -> None:
    """Agent Card endpoint must return HTTP 200."""
    assert client.get("/.well-known/agent.json").status_code == 200


def test_agent_card_required_fields(client: TestClient) -> None:
    """Agent Card must contain all required A2A v1.0 fields."""
    card = client.get("/.well-known/agent.json").json()
    for field in ("id", "name", "description", "version", "endpoint", "capabilities", "skills"):
        assert field in card, f"Missing required field: {field}"


def test_agent_card_capabilities_shape(client: TestClient) -> None:
    """Capabilities object must expose streaming and pushNotifications flags."""
    caps = client.get("/.well-known/agent.json").json()["capabilities"]
    assert "streaming" in caps
    assert "pushNotifications" in caps


def test_agent_card_skills_are_list(client: TestClient) -> None:
    """Skills field must be a list."""
    assert isinstance(client.get("/.well-known/agent.json").json()["skills"], list)


def test_agent_card_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """AGENT_ID and AGENT_NAME env vars must be reflected in the Agent Card."""
    monkeypatch.setenv("AGENT_ID", "test-agent-42")
    monkeypatch.setenv("AGENT_NAME", "Test Agent")

    for mod in ("agent", "main"):
        sys.modules.pop(mod, None)

    with patch("agent.build_agent", return_value=MagicMock()):
        import importlib

        import main as m

        importlib.reload(m)
        card = TestClient(m.app).get("/.well-known/agent.json").json()

    assert card["id"] == "test-agent-42"
    assert card["name"] == "Test Agent"
