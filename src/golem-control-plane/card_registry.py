# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Agent Card Registry — collects and stores A2A Agent Cards from running pods."""

import logging
from typing import Any

import httpx
from models import SandboxHandle

logger = logging.getLogger(__name__)

# In-memory registry for MVP. Replace with PostgreSQL in Week 3.
_registry: dict[str, dict[str, Any]] = {}


def fetch_and_register(handle: SandboxHandle) -> dict[str, Any] | None:
    """
    Fetch the A2A Agent Card from the pod and store it in the registry.

    Args:
        handle: The SandboxHandle of a Running pod.

    Returns:
        The Agent Card dict if successful, None otherwise.
    """
    url = f"http://{handle.pod_name}.{handle.namespace}.svc.cluster.local:8000/.well-known/agent.json"
    try:
        response = httpx.get(url, timeout=5.0)
        response.raise_for_status()
        card: dict[str, Any] = response.json()
        _registry[handle.agent_id] = card
        handle.agent_card = card
        logger.info("Agent Card registered for %s.", handle.agent_id)
        return card
    except Exception as e:
        logger.warning("Could not fetch Agent Card for %s: %s", handle.agent_id, e)
        return None


def get_card(agent_id: str) -> dict[str, Any] | None:
    """
    Retrieve a registered Agent Card by agent ID.

    Args:
        agent_id: The unique agent identifier.

    Returns:
        The Agent Card dict, or None if not registered.
    """
    return _registry.get(agent_id)


def list_cards() -> list[dict[str, Any]]:
    """Return all registered Agent Cards."""
    return list(_registry.values())


def deregister(agent_id: str) -> None:
    """Remove an Agent Card from the registry."""
    _registry.pop(agent_id, None)
    logger.info("Agent Card deregistered for %s.", agent_id)
