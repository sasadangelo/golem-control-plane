# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Unit tests for the in-memory Agent Card Registry."""

import sys

import pytest


@pytest.fixture(autouse=True)
def _fresh_registry() -> None:
    """Re-import card_registry for each test to reset in-memory state."""
    sys.modules.pop("card_registry", None)


def test_register_and_get_card() -> None:
    """fetch_and_register (via direct store) and get_card must round-trip."""
    import card_registry
    from models import SandboxHandle

    handle = SandboxHandle(agent_id="golem-agent-001")
    card = {"id": "golem-agent-001", "name": "Test Agent", "skills": []}
    card_registry._registry["golem-agent-001"] = card
    handle.agent_card = card

    result = card_registry.get_card("golem-agent-001")
    assert result == card


def test_get_card_missing_returns_none() -> None:
    """get_card must return None for an unknown agent_id."""
    import card_registry

    assert card_registry.get_card("does-not-exist") is None


def test_deregister_removes_card() -> None:
    """deregister must remove the card from the registry."""
    import card_registry

    card_registry._registry["golem-agent-002"] = {"id": "golem-agent-002"}
    card_registry.deregister("golem-agent-002")
    assert card_registry.get_card("golem-agent-002") is None


def test_list_cards_returns_all() -> None:
    """list_cards must return all registered cards."""
    import card_registry

    card_registry._registry["golem-agent-003"] = {"id": "golem-agent-003"}
    card_registry._registry["golem-agent-004"] = {"id": "golem-agent-004"}
    cards = card_registry.list_cards()
    ids = [c["id"] for c in cards]
    assert "golem-agent-003" in ids
    assert "golem-agent-004" in ids


def test_fetch_and_register_on_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """fetch_and_register must return None gracefully on HTTP error."""
    import card_registry
    import httpx
    from models import SandboxHandle

    monkeypatch.setattr(httpx, "get", lambda *a, **kw: (_ for _ in ()).throw(httpx.ConnectError("refused")))
    handle = SandboxHandle(agent_id="golem-agent-005")
    result = card_registry.fetch_and_register(handle)
    assert result is None
    assert card_registry.get_card("golem-agent-005") is None
