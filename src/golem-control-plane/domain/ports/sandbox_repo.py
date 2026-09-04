# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Abstract SandboxRepository port for sandbox persistence."""

from abc import ABC, abstractmethod

from domain.models import SandboxHandle


class SandboxRepository(ABC):
    """Port for persisting and querying sandbox state.

    The in-memory implementation lives in infrastructure/adapters/in_memory_repos.py.
    A PostgreSQL adapter is planned for Week 3.
    """

    @abstractmethod
    def get(self, agent_id: str) -> SandboxHandle | None:
        """Return the SandboxHandle for the given agent, or None if not found."""

    @abstractmethod
    def save(self, handle: SandboxHandle) -> None:
        """Persist (create or update) a SandboxHandle."""

    @abstractmethod
    def delete(self, agent_id: str) -> None:
        """Remove the sandbox record for agent_id. No-op if not present."""

    @abstractmethod
    def all(self) -> list[SandboxHandle]:
        """Return all persisted SandboxHandles."""

    @abstractmethod
    def items(self) -> list[tuple[str, SandboxHandle]]:
        """Return a snapshot of (agent_id, handle) pairs — safe to iterate during mutation."""

    @abstractmethod
    def get_created_at(self, agent_id: str) -> float | None:
        """Return the epoch timestamp when agent_id was first saved, or None."""

    @abstractmethod
    def set_created_at(self, agent_id: str, ts: float) -> None:
        """Record the creation epoch timestamp for agent_id."""

    @abstractmethod
    def contains(self, agent_id: str) -> bool:
        """Return True if a sandbox for agent_id exists."""
