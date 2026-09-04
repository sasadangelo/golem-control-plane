# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Abstract CardRegistry port — contract for A2A Agent Card storage and retrieval."""

from abc import ABC, abstractmethod
from typing import Any

from domain.models import SandboxHandle


class CardRegistry(ABC):
    """Port for storing, fetching, and querying A2A Agent Cards.

    Two concrete implementations are expected:
    - ``InMemoryCardRegistry`` (MVP, this file's sibling in infrastructure/adapters/).
    - A distributed registry backed by PostgreSQL or Redis (Week 3+).
    """

    @abstractmethod
    def register_card(self, agent_id: str, card: dict[str, Any]) -> None:
        """Store an Agent Card pushed by the runner via the handshake endpoint.

        Args:
            agent_id: The unique agent identifier.
            card: The full A2A Agent Card dict sent by the runner.
        """

    @abstractmethod
    def fetch_and_register(self, handle: SandboxHandle) -> dict[str, Any] | None:
        """Fetch the Agent Card from the runner pod and persist it.

        Makes an HTTP GET to ``/.well-known/agent.json`` on the runner pod.
        Stores the result and returns it, or returns None on failure.

        Args:
            handle: The SandboxHandle of a running pod.

        Returns:
            The Agent Card dict if successful, None otherwise.
        """

    @abstractmethod
    def get_card(self, agent_id: str) -> dict[str, Any] | None:
        """Return the registered Agent Card for agent_id, or None if not found.

        Args:
            agent_id: The unique agent identifier.
        """

    @abstractmethod
    def deregister(self, agent_id: str) -> None:
        """Remove the Agent Card for agent_id. No-op if not present.

        Args:
            agent_id: The unique agent identifier.
        """

    @abstractmethod
    def list_cards(self) -> list[dict[str, Any]]:
        """Return all currently registered Agent Cards."""
