# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Task router — HTTP endpoints for A2A task lifecycle and delegation."""

import httpx
from application.services.task_service import TaskService
from fastapi import APIRouter, HTTPException

from interfaces.api.schemas import (
    DelegateTaskRequest,
    DelegateTaskResponse,
    SubmitTaskRequest,
    TaskResponse,
    UpdateTaskRequest,
)


def make_router(task_service: TaskService) -> APIRouter:
    """Wire the task_service into the router and return it.

    Args:
        task_service: The application-layer service to delegate to.

    Returns:
        A fully configured APIRouter ready to be included in the FastAPI app.
    """
    router = APIRouter(tags=["tasks"])

    @router.post(path="/agents/{agent_id}/tasks", response_model=TaskResponse, status_code=201)
    async def submit_task(agent_id: str, body: SubmitTaskRequest) -> TaskResponse:
        """Submit a new A2A task to an agent sandbox (fire-and-forget)."""
        try:
            task = await task_service.submit_task(agent_id=agent_id, message=body.message, source=body.source)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found.")
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"Runner unreachable: {exc}") from exc

        return TaskResponse(
            task_id=task.task_id,
            agent_id=task.agent_id,
            status=task.status,
            source=task.source,
            message=task.message,
            result=task.result,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )

    @router.get(path="/agents/{agent_id}/tasks", response_model=list[TaskResponse])
    async def list_tasks(agent_id: str) -> list[TaskResponse]:
        """List all A2A tasks for a given agent sandbox."""
        try:
            tasks = await task_service.list_tasks(agent_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found.")
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"Runner unreachable: {exc}") from exc

        return [
            TaskResponse(
                task_id=t.task_id,
                agent_id=t.agent_id,
                status=t.status,
                source=t.source,
                message=t.message,
                result=t.result,
                created_at=t.created_at,
                updated_at=t.updated_at,
            )
            for t in tasks
        ]

    @router.get(path="/agents/{agent_id}/tasks/{task_id}", response_model=TaskResponse)
    async def get_task(agent_id: str, task_id: str) -> TaskResponse:
        """Return the current state of a single A2A task."""
        try:
            task = await task_service.get_task(agent_id=agent_id, task_id=task_id)
        except KeyError as e:
            key = str(e).strip("'")
            if key == agent_id:
                raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found.")
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found for agent {agent_id}.")
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"Runner unreachable: {exc}") from exc

        return TaskResponse(
            task_id=task.task_id,
            agent_id=task.agent_id,
            status=task.status,
            source=task.source,
            message=task.message,
            result=task.result,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )

    @router.patch(path="/agents/{agent_id}/tasks/{task_id}", response_model=TaskResponse)
    async def update_task(agent_id: str, task_id: str, body: UpdateTaskRequest) -> TaskResponse:
        """Advance a task's lifecycle state (called by the runner pod)."""

        try:
            task = task_service.update_task(
                agent_id=agent_id,
                task_id=task_id,
                new_status=body.status,
                result=body.result,
            )
        except KeyError as e:
            key = str(e).strip("'")
            if key == agent_id:
                raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found.")
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found for agent {agent_id}.")
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e

        return TaskResponse(
            task_id=task.task_id,
            agent_id=task.agent_id,
            status=task.status,
            source=task.source,
            message=task.message,
            result=task.result,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )

    @router.post(path="/agents/{source_agent_id}/delegate", response_model=DelegateTaskResponse, status_code=201)
    async def delegate_task(source_agent_id: str, body: DelegateTaskRequest) -> DelegateTaskResponse:
        """Delegate an A2A task from a source agent to a target agent."""
        try:
            task_id, status = await task_service.delegate_task(
                source_agent_id=source_agent_id,
                target_agent_id=body.target_agent_id,
                message=body.message,
                source=body.source,
            )
        except KeyError as e:
            key = str(e).strip("'")
            if key == source_agent_id:
                raise HTTPException(status_code=404, detail=f"Source agent {source_agent_id} not found.")
            raise HTTPException(status_code=404, detail=f"Target agent {body.target_agent_id} not found.")
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"Target runner unreachable: {exc}") from exc

        return DelegateTaskResponse(
            task_id=task_id,
            source_agent_id=source_agent_id,
            target_agent_id=body.target_agent_id,
            status=status,
        )

    return router
