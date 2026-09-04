# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Unit tests for the InMemoryCardRegistry adapter."""

import pytest

from infrastructure.adapters.card_registry import InMemoryCardRegistry


@pytest.fixture()
def registry() -> InMemoryCardRegistry:
    """Return a fresh InMemoryCardRegistry instance for each test."""
    return InMemoryCardRegistry()


def test_register_and_get_card(registry: InMemoryCardRegistry) -> None:
    """register_card and get_card must round-trip."""
    card = {"id": "golem-agent-001", "name": "Test Agent", "skills": []}
    registry.register_card("golem-agent-001", card)
    assert registry.get_card("golem-agent-001") == card


def test_get_card_missing_returns_none(registry: InMemoryCardRegistry) -> None:
    """get_card must return None for an unknown agent_id."""
    assert registry.get_card("does-not-exist") is None


def test_deregister_removes_card(registry: InMemoryCardRegistry) -> None:
    """deregister must remove the card from the registry."""
    registry.register_card("golem-agent-002", {"id": "golem-agent-002"})
    registry.deregister("golem-agent-002")
    assert registry.get_card("golem-agent-002") is None


def test_list_cards_returns_all(registry: InMemoryCardRegistry) -> None:
    """list_cards must return all registered cards."""
    registry.register_card("golem-agent-003", {"id": "golem-agent-003"})
    registry.register_card("golem-agent-004", {"id": "golem-agent-004"})
    ids = [c["id"] for c in registry.list_cards()]
    assert "golem-agent-003" in ids
    assert "golem-agent-004" in ids


def test_fetch_and_register_on_http_error(
    registry: InMemoryCardRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """fetch_and_register must return None gracefully on HTTP error."""
    import httpx

    from domain.models import SandboxHandle

    monkeypatch.setattr(httpx, "get", lambda *a, **kw: (_ for _ in ()).throw(httpx.ConnectError("refused")))
    handle = SandboxHandle(agent_id="golem-agent-005")
    result = registry.fetch_and_register(handle)
    assert result is None
    assert registry.get_card("golem-agent-005") is None
