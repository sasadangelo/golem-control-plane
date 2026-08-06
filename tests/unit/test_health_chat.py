# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Unit tests for /health and /chat endpoints."""

from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage


def _executor(reply: str) -> MagicMock:
    mock = MagicMock()
    mock.invoke.return_value = {"messages": [AIMessage(content=reply)]}
    return mock


def test_health_returns_ok(client: TestClient) -> None:
    """Health endpoint must return HTTP 200 with status ok."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chat_returns_reply(client: TestClient) -> None:
    """Chat endpoint must return the agent reply in the response body."""
    import main as m

    m.agent_executor = _executor("Ciao!")
    response = client.post("/chat", json={"message": "Ciao"})
    assert response.status_code == 200
    assert response.json()["reply"] == "Ciao!"


def test_chat_executor_error_returns_500(client: TestClient) -> None:
    """If agent_executor raises, /chat must return HTTP 500."""
    import main as m

    broken = MagicMock()
    broken.invoke.side_effect = RuntimeError("boom")
    m.agent_executor = broken
    assert client.post("/chat", json={"message": "Hi"}).status_code == 500


def test_chat_missing_message_returns_422(client: TestClient) -> None:
    """A /chat request without the message field must return HTTP 422."""
    assert client.post("/chat", json={}).status_code == 422
