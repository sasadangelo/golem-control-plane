# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""In-memory implementations of SandboxRepository, TaskRepository, and ConversationRepository.

These are the Week-1/2 adapters backed by plain Python dicts.
They will be replaced by PostgreSQL adapters in Week 3 without touching
domain or application code — only the wiring in app.py needs to change.
"""

from domain.models import A2ATask, Conversation, SandboxHandle
from domain.ports.sandbox_repo import SandboxRepository
from domain.ports.task_repo import ConversationRepository, TaskRepository


class InMemorySandboxRepository(SandboxRepository):
    """Thread-unsafe, in-process sandbox store (single-worker FastAPI only)."""

    def __init__(self) -> None:
        self._sandboxes: dict[str, SandboxHandle] = {}
        self._created_at: dict[str, float] = {}

    def get(self, agent_id: str) -> SandboxHandle | None:
        return self._sandboxes.get(agent_id)

    def save(self, handle: SandboxHandle) -> None:
        self._sandboxes[handle.agent_id] = handle

    def delete(self, agent_id: str) -> None:
        self._sandboxes.pop(agent_id, None)
        self._created_at.pop(agent_id, None)

    def all(self) -> list[SandboxHandle]:
        return list(self._sandboxes.values())

    def get_created_at(self, agent_id: str) -> float | None:
        return self._created_at.get(agent_id)

    def set_created_at(self, agent_id: str, ts: float) -> None:
        self._created_at[agent_id] = ts

    def contains(self, agent_id: str) -> bool:
        return agent_id in self._sandboxes

    def items(self) -> list[tuple[str, SandboxHandle]]:
        """Return a snapshot of (agent_id, handle) pairs — safe to iterate during mutation."""
        return list(self._sandboxes.items())


class InMemoryTaskRepository(TaskRepository):
    """In-process A2A task store."""

    def __init__(self) -> None:
        self._tasks: dict[str, A2ATask] = {}

    def get(self, task_id: str) -> A2ATask | None:
        return self._tasks.get(task_id)

    def save(self, task: A2ATask) -> None:
        self._tasks[task.task_id] = task

    def list_by_agent(self, agent_id: str) -> list[A2ATask]:
        tasks = [t for t in self._tasks.values() if t.agent_id == agent_id]
        tasks.sort(key=lambda t: t.created_at)
        return tasks


class InMemoryConversationRepository(ConversationRepository):
    """In-process conversation store keyed by (agent_id, conversation_id)."""

    def __init__(self) -> None:
        self._conversations: dict[tuple[str, str], Conversation] = {}

    def get(self, agent_id: str, conversation_id: str) -> Conversation | None:
        return self._conversations.get((agent_id, conversation_id))

    def save(self, conversation: Conversation) -> None:
        self._conversations[(conversation.agent_id, conversation.conversation_id)] = conversation

    def delete(self, agent_id: str, conversation_id: str) -> None:
        self._conversations.pop((agent_id, conversation_id), None)

    def list_by_agent(self, agent_id: str) -> list[Conversation]:
        convs = [v for (aid, _), v in self._conversations.items() if aid == agent_id]
        convs.sort(key=lambda c: c.created_at)
        return convs

    def contains(self, agent_id: str, conversation_id: str) -> bool:
        return (agent_id, conversation_id) in self._conversations
