# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Abstract TaskRepository and ConversationRepository ports."""

from abc import ABC, abstractmethod

from domain.models import A2ATask, Conversation


class TaskRepository(ABC):
    """Port for persisting and querying A2A task state."""

    @abstractmethod
    def get(self, task_id: str) -> A2ATask | None:
        """Return the task with the given id, or None if not found."""

    @abstractmethod
    def save(self, task: A2ATask) -> None:
        """Persist (create or update) a task."""

    @abstractmethod
    def list_by_agent(self, agent_id: str) -> list[A2ATask]:
        """Return all tasks belonging to agent_id, ordered by creation time."""


class ConversationRepository(ABC):
    """Port for persisting and querying Conversation state."""

    @abstractmethod
    def get(self, agent_id: str, conversation_id: str) -> Conversation | None:
        """Return the conversation, or None if not found."""

    @abstractmethod
    def save(self, conversation: Conversation) -> None:
        """Persist (create or update) a conversation."""

    @abstractmethod
    def delete(self, agent_id: str, conversation_id: str) -> None:
        """Remove the conversation. No-op if not present."""

    @abstractmethod
    def list_by_agent(self, agent_id: str) -> list[Conversation]:
        """Return all conversations belonging to agent_id, ordered by creation time."""

    @abstractmethod
    def contains(self, agent_id: str, conversation_id: str) -> bool:
        """Return True if the conversation exists."""
