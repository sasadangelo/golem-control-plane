# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""TaskService — application-layer use cases for A2A task lifecycle."""

import re
from datetime import UTC, datetime

import httpx

from core.config import settings
from core.log import LoggerManager
from domain.models import A2ATask, SandboxHandle, TaskStatus
from domain.ports.sandbox_repo import SandboxRepository
from domain.ports.task_repo import TaskRepository

logger = LoggerManager.get_logger(name="TaskService")


def _runner_http_url(handle: SandboxHandle) -> str:
    """Return the base HTTP URL for a runner pod.

    Uses ``settings.test.runner_url`` when set (smoke-testing without K8s).
    """
    if settings.test.runner_url:
        base = settings.test.runner_url
        base = re.sub(r"^ws", "http", base)
        base = base.rstrip("/").removesuffix("/ws/chat")
        return base
    return f"http://{handle.pod_name}.{handle.namespace}.svc.cluster.local:8000"


class TaskService:
    """Encapsulates all business logic for A2A task submission, listing, retrieval, and update."""

    def __init__(self, sandbox_repo: SandboxRepository, task_repo: TaskRepository) -> None:
        self._sandboxes = sandbox_repo
        self._tasks = task_repo

    # ------------------------------------------------------------------
    # Use-case: submit task
    # ------------------------------------------------------------------

    async def submit_task(self, agent_id: str, message: str, source: str) -> A2ATask:
        """Fire-and-forget task submission — proxies to the runner pod.

        Args:
            agent_id: The target agent sandbox identifier.
            message: The instruction text for the agent.
            source: Origin label (e.g. "manual", "a2a", "cron").

        Returns:
            An A2ATask with status=submitted.

        Raises:
            KeyError: If the agent does not exist.
            httpx.HTTPError: If the runner pod is unreachable.
        """
        handle = self._sandboxes.get(agent_id)
        if handle is None:
            raise KeyError(agent_id)

        base = _runner_http_url(handle)
        payload = {
            "message": {"role": "user", "parts": [{"type": "text", "text": message}]},
            "source": source,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{base}/a2a/tasks/send", json=payload)
            resp.raise_for_status()

        data = resp.json()
        task_id: str = data["id"]
        now = datetime.now(tz=UTC)
        task = A2ATask(
            task_id=task_id,
            agent_id=agent_id,
            status=TaskStatus.SUBMITTED,
            source=source,
            message=message,
            result=None,
            created_at=now,
            updated_at=now,
        )
        logger.info(f"Task {task_id} submitted to agent {agent_id} (fire-and-forget)")
        return task

    # ------------------------------------------------------------------
    # Use-case: list tasks
    # ------------------------------------------------------------------

    async def list_tasks(self, agent_id: str) -> list[A2ATask]:
        """Return all tasks for an agent, proxied from the runner pod.

        Args:
            agent_id: The agent sandbox identifier.

        Returns:
            A list of A2ATasks ordered by creation time.

        Raises:
            KeyError: If the agent does not exist.
            httpx.HTTPError: If the runner pod is unreachable.
        """
        handle = self._sandboxes.get(agent_id)
        if handle is None:
            raise KeyError(agent_id)

        base = _runner_http_url(handle)
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{base}/a2a/tasks")
            resp.raise_for_status()

        return [
            A2ATask(
                task_id=t["task_id"],
                agent_id=agent_id,
                status=TaskStatus(t["status"]),
                source=t.get("source", "manual"),
                message=t["message"],
                result=t.get("result"),
                created_at=t["created_at"],
                updated_at=t["updated_at"],
            )
            for t in resp.json()
        ]

    # ------------------------------------------------------------------
    # Use-case: get task
    # ------------------------------------------------------------------

    async def get_task(self, agent_id: str, task_id: str) -> A2ATask:
        """Return a single task, proxied from the runner pod.

        Args:
            agent_id: The agent sandbox identifier.
            task_id: The task identifier.

        Returns:
            The matching A2ATask.

        Raises:
            KeyError: If the agent or task does not exist.
            httpx.HTTPError: If the runner pod is unreachable.
        """
        handle = self._sandboxes.get(agent_id)
        if handle is None:
            raise KeyError(agent_id)

        base = _runner_http_url(handle)
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{base}/a2a/tasks/{task_id}")
            if resp.status_code == 404:
                raise KeyError(task_id)
            resp.raise_for_status()

        t = resp.json()
        return A2ATask(
            task_id=t["task_id"],
            agent_id=agent_id,
            status=TaskStatus(t["status"]),
            source=t.get("source", "manual"),
            message=t["message"],
            result=t.get("result"),
            created_at=t["created_at"],
            updated_at=t["updated_at"],
        )

    # ------------------------------------------------------------------
    # Use-case: update task
    # ------------------------------------------------------------------

    def update_task(self, agent_id: str, task_id: str, new_status: str, result: str | None) -> A2ATask:
        """Advance a task's lifecycle state (called by the runner pod).

        Args:
            agent_id: The agent sandbox identifier.
            task_id: The task identifier.
            new_status: Target status string.
            result: Optional output produced by the agent.

        Returns:
            The updated A2ATask.

        Raises:
            KeyError: If the agent or task does not exist.
            ValueError: If new_status is not a valid TaskStatus value.
        """
        if not self._sandboxes.contains(agent_id):
            raise KeyError(agent_id)

        task = self._tasks.get(task_id)
        if task is None or task.agent_id != agent_id:
            raise KeyError(task_id)

        task.status = TaskStatus(new_status)
        if result is not None:
            task.result = result
        task.updated_at = datetime.now(tz=UTC)
        self._tasks.save(task)
        logger.info(f"Task {task_id} for agent {agent_id} updated to status={task.status}")
        return task

    # ------------------------------------------------------------------
    # Use-case: delegate task (A2A broker)
    # ------------------------------------------------------------------

    async def delegate_task(
        self, source_agent_id: str, target_agent_id: str, message: str, source: str
    ) -> tuple[str, str]:
        """Delegate a task from one agent to another via the runner pod.

        Args:
            source_agent_id: The agent initiating the delegation.
            target_agent_id: The agent that will execute the task.
            message: The instruction text.
            source: Origin label (typically "a2a").

        Returns:
            A tuple of (task_id, status).

        Raises:
            KeyError: If source or target agent does not exist.
            httpx.HTTPError: If the target runner is unreachable.
        """
        if not self._sandboxes.contains(source_agent_id):
            raise KeyError(source_agent_id)

        target_handle = self._sandboxes.get(target_agent_id)
        if target_handle is None:
            raise KeyError(target_agent_id)

        base = _runner_http_url(target_handle)
        payload = {
            "message": {"role": "user", "parts": [{"type": "text", "text": message}]},
            "source": source,
        }
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(f"{base}/a2a/tasks/send", json=payload)
            resp.raise_for_status()

        data = resp.json()
        task_id: str = data["id"]
        status: str = data.get("status", {}).get("state", "submitted")
        logger.info(f"Task {task_id} delegated from {source_agent_id} to {target_agent_id}")
        return task_id, status
