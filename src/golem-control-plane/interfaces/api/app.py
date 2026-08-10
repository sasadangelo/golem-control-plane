# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Golem Control Plane — FastAPI application."""

import asyncio
import time
from _asyncio import Task
from asyncio.events import AbstractEventLoop
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

import websockets
import websockets.exceptions
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect

from core.config import settings
from core.log import LoggerManager, setup_logging
from domain.models import A2ATask, AgentSpec, SandboxHandle, SandboxStatus, TaskStatus
from domain.ports.provisioner import Provisioner
from infrastructure.adapters import card_registry
from infrastructure.adapters.k8s_provisioner import KubernetesProvisioner
from interfaces.api.schemas import (
    AgentStatusResponse,
    CreateAgentResponse,
    HandshakeRequest,
    HandshakeResponse,
    SubmitTaskRequest,
    TaskResponse,
    UpdateTaskRequest,
)

setup_logging(
    level=settings.log.level,
    console=settings.log.console,
    file=settings.log.file,
    rotation=settings.log.rotation,
    retention=settings.log.retention,
    compression=settings.log.compression,
)

logger = LoggerManager.get_logger(name="ControlPlaneApp")

# In-memory store of active sandboxes. Replaced by PostgreSQL in Week 3.
_sandboxes: dict[str, SandboxHandle] = {}

# Sandbox creation timestamps for TTL tracking {agent_id: created_at_epoch}
_created_at: dict[str, float] = {}

# In-memory A2A task registry {task_id: A2ATask}
_tasks: dict[str, A2ATask] = {}

GC_INTERVAL_SECONDS: int = settings.control_plane.gc_interval


# ---------------------------------------------------------------------------
# TTL Garbage Collector
# ---------------------------------------------------------------------------


async def _gc_loop() -> None:
    """
    Background coroutine that runs every GC_INTERVAL_SECONDS.

    Scans all sandboxes and deletes those whose age exceeds their TTL.
    """
    while True:
        await asyncio.sleep(GC_INTERVAL_SECONDS)
        now = time.time()
        expired: list[str] = [
            agent_id
            for agent_id, handle in list(_sandboxes.items())
            if now - _created_at.get(agent_id, now) > handle.ttl_seconds
        ]
        for agent_id in expired:
            handle: SandboxHandle = _sandboxes[agent_id]
            logger.info(f"TTL expired for agent {agent_id} — deleting sandbox")
            try:
                provisioner.delete_sandbox(handle)
            except (OSError, RuntimeError) as e:
                logger.warning(f"GC could not delete sandbox {agent_id}: {e}")
            card_registry.deregister(agent_id)
            _sandboxes.pop(agent_id, None)
            _created_at.pop(agent_id, None)


@asynccontextmanager
async def lifespan(app_: FastAPI) -> AsyncGenerator[None, None]:
    """Start the TTL GC background task on startup and cancel it on shutdown."""
    gc_task: Task[None] = asyncio.create_task(coro=_gc_loop())
    logger.info(f"TTL garbage collector started (interval={GC_INTERVAL_SECONDS}s)")
    try:
        yield
    finally:
        gc_task.cancel()
        logger.info("TTL garbage collector stopped")


def _build_provisioner() -> Provisioner:
    """Return the provisioner configured in settings.

    Uses ``MockProvisioner`` when ``test.provisioner == "mock"`` to allow
    local smoke-testing without a Kubernetes cluster.
    """
    if settings.test.provisioner == "mock":
        from infrastructure.adapters.mock_provisioner import MockProvisioner

        logger.warning("MockProvisioner active — for local smoke-testing only, never use in production")
        return MockProvisioner()
    return KubernetesProvisioner()


provisioner: Provisioner = _build_provisioner()
app: FastAPI = FastAPI(title="Golem Control Plane", version="0.1.0", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.post(path="/agents", response_model=CreateAgentResponse, status_code=201)
async def create_agent(
    config: UploadFile = File(description="Runner config.yaml file."),  # noqa: B008
    ttl_seconds: int = Form(default=3600, description="Sandbox TTL in seconds."),
) -> CreateAgentResponse:
    """
    Provision a new isolated agent sandbox.

    Accepts a multipart/form-data request with:
    - ``config``: the runner config.yaml file
    - ``ttl_seconds``: optional sandbox TTL (default 3600)

    Creates a K8s Namespace + ConfigMap + Pod + ResourceQuota + NetworkPolicy.
    """
    runner_config: str = (await config.read()).decode(encoding="utf-8")
    spec = AgentSpec(
        ttl_seconds=ttl_seconds,
        runner_config=runner_config,
    )

    try:
        handle: SandboxHandle = provisioner.create_sandbox(spec)
    except Exception as e:
        logger.error(f"Failed to create sandbox: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

    _sandboxes[handle.agent_id] = handle
    _created_at[handle.agent_id] = time.time()
    logger.info(f"Agent {handle.agent_id} created in namespace {handle.namespace}")

    return CreateAgentResponse(
        agent_id=handle.agent_id,
        namespace=handle.namespace,
        status=handle.status,
    )


@app.get("/agents/{agent_id}/status", response_model=AgentStatusResponse)
async def get_agent_status(agent_id: str) -> AgentStatusResponse:
    """
    Return the current status of an agent sandbox.

    When the pod transitions to Running, the Agent Card is fetched
    and registered automatically.
    """
    handle = _sandboxes.get(agent_id)
    if not handle:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found.")

    try:
        loop: AbstractEventLoop = asyncio.get_event_loop()
        handle = await loop.run_in_executor(None, provisioner.get_status, handle)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    _sandboxes[agent_id] = handle

    # Register Agent Card the first time the pod reaches Running.
    # Two paths:
    #   1. handle.agent_card is already set (MockProvisioner populated it in get_status)
    #      → write it directly into the registry.
    #   2. handle.agent_card is None → fetch it from the pod via HTTP (K8s / real runner).
    if handle.status == SandboxStatus.RUNNING and not card_registry.get_card(agent_id):
        if handle.agent_card:
            card_registry.register_card(agent_id=agent_id, card=handle.agent_card)
        else:
            card_registry.fetch_and_register(handle)

    return AgentStatusResponse(
        agent_id=handle.agent_id,
        namespace=handle.namespace,
        status=handle.status,
        agent_card=handle.agent_card,
    )


@app.delete("/agents/{agent_id}", status_code=204)
async def delete_agent(agent_id: str) -> None:
    """Tear down the agent sandbox and deregister its Agent Card."""
    handle: SandboxHandle | None = _sandboxes.get(agent_id)
    if not handle:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found.")

    try:
        provisioner.delete_sandbox(handle)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    card_registry.deregister(agent_id)
    _sandboxes.pop(agent_id, None)
    _created_at.pop(agent_id, None)
    logger.info(f"Agent {agent_id} deleted")


@app.get(path="/agents", response_model=list[AgentStatusResponse])
async def list_agents() -> list[AgentStatusResponse]:
    """List all known agent sandboxes with their current live status.

    All get_status calls are dispatched concurrently in the thread-pool so that
    one slow K8s API round-trip does not block the others.
    """
    loop: AbstractEventLoop = asyncio.get_event_loop()
    snapshot: list[tuple[str, SandboxHandle]] = list(_sandboxes.items())

    async def _refresh(agent_id: str, handle: SandboxHandle) -> SandboxHandle:
        try:
            handle = await loop.run_in_executor(None, provisioner.get_status, handle)
        except Exception as e:
            logger.warning(f"Could not refresh status for agent {agent_id}: {e}")
        else:
            _sandboxes[agent_id] = handle
            if handle.status == SandboxStatus.RUNNING and not card_registry.get_card(agent_id):
                if handle.agent_card:
                    card_registry.register_card(agent_id=agent_id, card=handle.agent_card)
                else:
                    card_registry.fetch_and_register(handle)
        return handle

    handles: list[SandboxHandle] = await asyncio.gather(*(_refresh(agent_id=aid, handle=h) for aid, h in snapshot))
    return [
        AgentStatusResponse(
            agent_id=h.agent_id,
            namespace=h.namespace,
            status=h.status,
            agent_card=h.agent_card,
        )
        for h in handles
    ]


@app.get(path="/agents/{agent_id}/card")
async def get_agent_card(agent_id: str) -> dict:
    """Return the A2A Agent Card for an agent (A2A peer-discovery endpoint)."""
    card: dict[str, Any] | None = card_registry.get_card(agent_id)
    if not card:
        raise HTTPException(status_code=404, detail=f"Agent Card for {agent_id} not found.")
    return card


@app.post(path="/agents/{agent_id}/handshake", response_model=HandshakeResponse)
async def agent_handshake(agent_id: str, body: HandshakeRequest) -> HandshakeResponse:
    """A2A peer handshake — runner pushes its Agent Card to the Control Plane broker.

    Called by the runner pod at startup (push model).  The Control Plane
    registers the card immediately so that peer-discovery via
    ``GET /agents/{id}/card`` works without waiting for a status-poll cycle.

    The sandbox must already exist (created via ``POST /agents``) before
    the runner can handshake.

    Args:
        agent_id: The agent sandbox identifier.
        body:     Request payload carrying the full A2A Agent Card.
    """
    if agent_id not in _sandboxes:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found.")

    card_registry.register_card(agent_id=agent_id, card=body.card)
    _sandboxes[agent_id].agent_card = body.card
    logger.info(f"Handshake completed for agent {agent_id}")

    return HandshakeResponse(registered=True, agent_id=agent_id)


@app.websocket(path="/chat/{agent_id}")
async def chat_proxy(websocket: WebSocket, agent_id: str) -> None:
    """
    Proxy WebSocket chat sessions between a client and the agent runner pod.

    Connects to ``ws://<pod>.<namespace>.svc.cluster.local:8000/ws/chat`` and
    pumps messages bidirectionally until either side closes the connection.

    Args:
        websocket: The inbound client WebSocket connection.
        agent_id: The agent sandbox identifier.
    """
    handle: SandboxHandle | None = _sandboxes.get(agent_id)
    if not handle:
        await websocket.close(code=4404, reason=f"Agent {agent_id} not found.")
        return

    if handle.status != SandboxStatus.RUNNING:
        await websocket.close(code=4503, reason=f"Agent {agent_id} is not running (status={handle.status}).")
        return

    runner_url = settings.test.runner_url or f"ws://{handle.pod_name}.{handle.namespace}.svc.cluster.local:8000/ws/chat"
    await websocket.accept()

    try:
        async with websockets.connect(runner_url) as runner_ws:  # type: ignore[attr-defined]
            logger.info(f"Chat proxy open: client ↔ {agent_id} ({runner_url})")

            async def _client_to_runner() -> None:
                """Forward messages from the external client to the runner pod."""
                async for message in websocket.iter_text():
                    await runner_ws.send(message)

            async def _runner_to_client() -> None:
                """Forward tokens from the runner pod to the external client."""
                async for token in runner_ws:
                    await websocket.send_text(str(token))

            _done, pending = await asyncio.wait(
                [
                    asyncio.ensure_future(_client_to_runner()),
                    asyncio.ensure_future(_runner_to_client()),
                ],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()

    except websockets.exceptions.ConnectionClosed:
        pass
    except WebSocketDisconnect:
        pass
    except (OSError, TimeoutError, websockets.exceptions.WebSocketException) as e:
        logger.warning(f"Chat proxy error for agent {agent_id}: {e}")
        await websocket.close(code=1011, reason=str(e))
    finally:
        logger.info(f"Chat proxy closed: {agent_id}")


# ---------------------------------------------------------------------------
# A2A Task lifecycle endpoints
# ---------------------------------------------------------------------------


@app.post(path="/agents/{agent_id}/tasks", response_model=TaskResponse, status_code=201)
async def submit_task(agent_id: str, body: SubmitTaskRequest) -> TaskResponse:
    """
    Submit a new A2A task to an agent sandbox.

    Creates a task record in ``submitted`` state and returns it immediately.
    The runner is responsible for transitioning the task to ``working``,
    then ``completed`` or ``failed`` via PATCH.

    Args:
        agent_id: The target agent sandbox identifier.
        body: The task submission payload containing the instruction message.
    """
    if agent_id not in _sandboxes:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found.")

    task: A2ATask = A2ATask(agent_id=agent_id, message=body.message)
    _tasks[task.task_id] = task
    logger.info(f"Task {task.task_id} submitted to agent {agent_id}")

    return TaskResponse(
        task_id=task.task_id,
        agent_id=task.agent_id,
        status=task.status,
        message=task.message,
        result=task.result,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@app.get(path="/agents/{agent_id}/tasks", response_model=list[TaskResponse])
async def list_tasks(agent_id: str) -> list[TaskResponse]:
    """
    List all A2A tasks for a given agent sandbox.

    Args:
        agent_id: The agent sandbox identifier.
    """
    if agent_id not in _sandboxes:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found.")

    return [
        TaskResponse(
            task_id=t.task_id,
            agent_id=t.agent_id,
            status=t.status,
            message=t.message,
            result=t.result,
            created_at=t.created_at,
            updated_at=t.updated_at,
        )
        for t in _tasks.values()
        if t.agent_id == agent_id
    ]


@app.get(path="/agents/{agent_id}/tasks/{task_id}", response_model=TaskResponse)
async def get_task(agent_id: str, task_id: str) -> TaskResponse:
    """
    Return the current state of a single A2A task.

    Args:
        agent_id: The agent sandbox identifier.
        task_id: The task identifier.
    """
    if agent_id not in _sandboxes:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found.")

    task: A2ATask | None = _tasks.get(task_id)
    if not task or task.agent_id != agent_id:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found for agent {agent_id}.")

    return TaskResponse(
        task_id=task.task_id,
        agent_id=task.agent_id,
        status=task.status,
        message=task.message,
        result=task.result,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@app.patch(path="/agents/{agent_id}/tasks/{task_id}", response_model=TaskResponse)
async def update_task(agent_id: str, task_id: str, body: UpdateTaskRequest) -> TaskResponse:
    """
    Update the status (and optional result) of an A2A task.

    Called by the runner pod to advance the task through its lifecycle:
    ``submitted → working → completed / failed``.

    Args:
        agent_id: The agent sandbox identifier.
        task_id: The task identifier.
        body: The updated status and optional result payload.
    """
    if agent_id not in _sandboxes:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found.")

    task: A2ATask | None = _tasks.get(task_id)
    if not task or task.agent_id != agent_id:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found for agent {agent_id}.")

    try:
        new_status: TaskStatus = TaskStatus(value=body.status)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid task status '{body.status}'.")

    task.status = new_status
    if body.result is not None:
        task.result = body.result
    task.updated_at = datetime.now(UTC)
    logger.info(f"Task {task_id} for agent {agent_id} updated to status={new_status}")

    return TaskResponse(
        task_id=task.task_id,
        agent_id=task.agent_id,
        status=task.status,
        message=task.message,
        result=task.result,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@app.get(path="/health")
async def health() -> dict:
    return {"status": "ok"}
