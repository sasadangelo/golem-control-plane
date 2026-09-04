# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""InMemoryCardRegistry — in-process implementation of the CardRegistry port.

Backed by a plain Python dict. Will be replaced by a PostgreSQL or Redis
adapter in Week 3 without touching any business logic.
"""

from typing import Any

import httpx

from core.log import LoggerManager
from domain.models import SandboxHandle
from domain.ports.card_registry import CardRegistry

logger = LoggerManager.get_logger("CardRegistry")


class InMemoryCardRegistry(CardRegistry):
    """Thread-unsafe, in-process Agent Card store (single-worker FastAPI only)."""

    def __init__(self) -> None:
        self._registry: dict[str, dict[str, Any]] = {}

    def register_card(self, agent_id: str, card: dict[str, Any]) -> None:
        """Store an Agent Card pushed by the runner via the handshake endpoint.

        Args:
            agent_id: The unique agent identifier.
            card: The full A2A Agent Card dict sent by the runner.
        """
        self._registry[agent_id] = card
        logger.info(f"Agent Card registered via handshake for agent '{agent_id}'")

    def fetch_and_register(self, handle: SandboxHandle) -> dict[str, Any] | None:
        """Fetch the Agent Card from the runner pod via HTTP and persist it.

        Args:
            handle: The SandboxHandle of a running pod.

        Returns:
            The Agent Card dict if successful, None otherwise.
        """
        url = f"http://{handle.pod_name}.{handle.namespace}.svc.cluster.local:8000/.well-known/agent.json"
        try:
            response = httpx.get(url, timeout=5.0)
            response.raise_for_status()
            card: dict[str, Any] = response.json()
            self._registry[handle.agent_id] = card
            handle.agent_card = card
            logger.info(f"Agent Card registered for agent '{handle.agent_id}'")
            return card
        except (OSError, ValueError, httpx.HTTPError) as e:
            logger.warning(f"Could not fetch Agent Card for agent '{handle.agent_id}': {e}")
            return None

    def get_card(self, agent_id: str) -> dict[str, Any] | None:
        """Return the registered Agent Card for agent_id, or None if not found.

        Args:
            agent_id: The unique agent identifier.
        """
        return self._registry.get(agent_id)

    def deregister(self, agent_id: str) -> None:
        """Remove the Agent Card for agent_id. No-op if not present.

        Args:
            agent_id: The unique agent identifier.
        """
        self._registry.pop(agent_id, None)
        logger.info(f"Agent Card deregistered for agent '{agent_id}'")

    def list_cards(self) -> list[dict[str, Any]]:
        """Return all currently registered Agent Cards."""
        return list(self._registry.values())
