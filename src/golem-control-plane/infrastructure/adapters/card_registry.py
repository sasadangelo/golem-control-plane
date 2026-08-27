# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Agent Card Registry — collects and stores A2A Agent Cards from running pods."""

from typing import Any

import httpx

from core.log import LoggerManager
from domain.models import SandboxHandle

logger = LoggerManager.get_logger("CardRegistry")

# In-memory registry for MVP. Replace with PostgreSQL in Week 3.
_registry: dict[str, dict[str, Any]] = {}


def register_card(agent_id: str, card: dict[str, Any]) -> None:
    """Register an Agent Card pushed by the runner via handshake (push model).

    Called by the handshake endpoint when a runner presents its own card
    at startup, before the Control Plane has a chance to pull it.

    Args:
        agent_id: The unique agent identifier.
        card:     The full A2A Agent Card dict sent by the runner.
    """
    _registry[agent_id] = card
    logger.info(f"Agent Card registered via handshake for agent '{agent_id}'")


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
        logger.info(f"Agent Card registered for agent '{handle.agent_id}'")
        return card
    except (OSError, ValueError, httpx.HTTPError) as e:
        logger.warning(f"Could not fetch Agent Card for agent '{handle.agent_id}': {e}")
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
    logger.info(f"Agent Card deregistered for agent '{agent_id}'")
