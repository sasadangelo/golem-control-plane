# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Golem Control Plane — FastAPI application."""

import asyncio
import re
import time
from _asyncio import Task
from asyncio.events import AbstractEventLoop
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

import httpx
import websockets
import websockets.exceptions
import yaml
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect

from core.config import settings
from core.log import LoggerManager, setup_logging
from domain.models import A2ATask, AgentSpec, Conversation, SandboxHandle, SandboxStatus, TaskStatus
from domain.ports.provisioner import Provisioner
from infrastructure.adapters import card_registry
from infrastructure.adapters.k8s_provisioner import KubernetesProvisioner
from interfaces.api.schemas import (
    AgentStatusResponse,
    ConversationResponse,
    CreateAgentResponse,
    CreateConversationRequest,
    DelegateTaskRequest,
    DelegateTaskResponse,
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

# In-memory conversation registry {(agent_id, conversation_id): Conversation}
_conversations: dict[tuple[str, str], Conversation] = {}

# In-memory active websocket connections registry {(agent_id, conversation_id): [WebSocket]}
_active_chat_connections: dict[tuple[str, str], list[WebSocket]] = {}

GC_INTERVAL_SECONDS: int = settings.control_plane.gc_interval


# ---------------------------------------------------------------------------
# TTL Garbage Collector
# ---------------------------------------------------------------------------


async def _gc_loop() -> None:
    """
    Background coroutine that runs every GC_INTERVAL_SECONDS.

    Scans all sandboxes and:
    - Refreshes the status of PENDING sandboxes so that pods that have reached
      Running are reflected in memory without waiting for an explicit
      GET /agents/{id}/status call or a runner handshake push.
    - Deletes sandboxes whose age exceeds their TTL.
    """
    while True:
        await asyncio.sleep(GC_INTERVAL_SECONDS)
        loop: AbstractEventLoop = asyncio.get_event_loop()

        # Refresh PENDING sandboxes so the chat proxy unblocks as soon as the
        # pod reaches Running — even when the runner has no cp_url configured
        # and therefore never sends a handshake push.
        for agent_id, handle in list(_sandboxes.items()):
            if handle.status == SandboxStatus.PENDING:
                try:
                    refreshed = await loop.run_in_executor(None, provisioner.get_status, handle)
                    _sandboxes[agent_id] = refreshed
                    if refreshed.status == SandboxStatus.RUNNING and not card_registry.get_card(agent_id):
                        if refreshed.agent_card:
                            card_registry.register_card(agent_id=agent_id, card=refreshed.agent_card)
                        else:
                            card_registry.fetch_and_register(refreshed)
                except Exception as e:  # noqa: BLE001
                    logger.warning(f"GC could not refresh status for agent {agent_id}: {e}")

        now = time.time()
        expired: list[str] = [
            agent_id
            for agent_id, handle in list(_sandboxes.items())
            if handle.ttl_seconds is not None and now - _created_at.get(agent_id, now) > handle.ttl_seconds
        ]
        for agent_id in expired:
            handle = _sandboxes[agent_id]
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
    ttl_seconds: int | None = Form(
        default=None,
        description="Sandbox TTL in seconds. Omit (or pass None) for a sandbox that never expires automatically.",
    ),
    agents_md: UploadFile | None = File(default=None, description="Optional AGENTS.md file."),  # noqa: B008
    skills: list[UploadFile] = File(default=[], description="Optional SKILL.md files (one per skill)."),  # noqa: B008
) -> CreateAgentResponse:
    """
    Provision a new isolated agent sandbox.

    Accepts a multipart/form-data request with:
    - ``config``: the runner config.yaml file
    - ``ttl_seconds``: optional sandbox TTL (default 3600)
    - ``agents_md``: optional AGENTS.md file mounted at /app/AGENTS.md in the pod
    - ``skills``: zero or more SKILL.md files; each is mounted at /app/skills/<filename>.md

    Creates a K8s Namespace + ConfigMap + Pod + ResourceQuota + NetworkPolicy.
    """
    runner_config: str = (await config.read()).decode(encoding="utf-8")

    agents_md_content: str | None = None
    if agents_md is not None:
        agents_md_content = (await agents_md.read()).decode(encoding="utf-8")

    skills_content: dict[str, str] = {}
    for skill_file in skills:
        # Use the bare filename stem as the skill name (e.g. "read-logs.md" → "read-logs")
        skill_name = (skill_file.filename or "skill").removesuffix(".md")
        skills_content[skill_name] = (await skill_file.read()).decode(encoding="utf-8")

    # Derive agent_id and env_secrets from config.yaml.
    # agent_id → deterministic, human-readable namespace (e.g. "aria-sre-001").
    # env_secrets → names of K8s Secrets already in the agent namespace to mount as envFrom.
    try:
        _cfg = yaml.safe_load(runner_config) or {}
        agent_id: str = _cfg.get("agent", {}).get("id", "")
        env_secrets: list[str] = _cfg.get("agent", {}).get("env_secrets", [])
    except yaml.YAMLError:
        agent_id = ""
        env_secrets = []

    if not agent_id:
        raise HTTPException(status_code=422, detail="config.yaml must contain agent.id")

    spec = AgentSpec(
        agent_id=agent_id,
        ttl_seconds=ttl_seconds,
        runner_config=runner_config,
        agents_md=agents_md_content,
        skills=skills_content,
        env_secrets=env_secrets,
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
        except (OSError, RuntimeError, ValueError) as e:
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
    _sandboxes[agent_id].status = SandboxStatus.RUNNING
    logger.info(f"Handshake completed for agent {agent_id}")

    return HandshakeResponse(registered=True, agent_id=agent_id)


def _generate_conversation_title(message: str) -> str:
    """Generate a clean, professional, short title (2-4 words) from the first message in English."""
    text = message.strip()
    if not text:
        return "New Conversation"

    # Common English stop words / conversational fluff to filter out
    stopwords = {
        "hi",
        "hello",
        "hey",
        "please",
        "could",
        "you",
        "would",
        "write",
        "create",
        "make",
        "show",
        "tell",
        "explain",
        "help",
        "me",
        "with",
        "a",
        "an",
        "the",
        "to",
        "for",
        "in",
        "on",
        "at",
        "by",
        "of",
        "from",
        "and",
        "or",
        "but",
        "what",
        "how",
        "why",
        "who",
        "which",
        "can",
        "do",
        "does",
        "did",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "have",
        "has",
        "had",
    }

    # Remove punctuation and split into words
    import re

    words = re.findall(r"\b\w+\b", text.lower())

    # Filter out stopwords
    filtered_words = [w for w in words if w not in stopwords]

    # If we filtered out too much, fall back to the original words
    if not filtered_words:
        filtered_words = words[:5]

    # Take up to 3-4 significant words
    title_words = filtered_words[:4]

    # Capitalize each word and join
    title = " ".join(w.capitalize() for w in title_words)

    # If it is too long, truncate nicely
    if len(title) > 24:
        title = f"{title[:21]}..."

    return title or "New Conversation"


@app.websocket(path="/chat/{agent_id}")
async def chat_proxy(websocket: WebSocket, agent_id: str, conversation_id: str | None = Query(None)) -> None:
    """
    Proxy WebSocket chat sessions between a client and the agent runner pod.

    Connects to ``ws://<pod>.<namespace>.svc.cluster.local:8000/ws/chat`` and
    pumps messages bidirectionally until either side closes the connection.

    When ``conversation_id`` is provided the conversation must already exist
    (created via POST /agents/{agent_id}/conversations).  If it does not exist
    the connection is rejected with code 4404.

    Args:
        websocket: The inbound client WebSocket connection.
        agent_id: The agent sandbox identifier.
        conversation_id: Optional UUID of an existing conversation.
    """
    handle: SandboxHandle | None = _sandboxes.get(agent_id)
    if not handle:
        await websocket.close(code=4404, reason=f"Agent {agent_id} not found.")
        return

    if handle.status != SandboxStatus.RUNNING:
        await websocket.close(code=4503, reason=f"Agent {agent_id} is not running (status={handle.status}).")
        return

    if conversation_id is not None and (agent_id, conversation_id) not in _conversations:
        await websocket.close(code=4404, reason=f"Conversation {conversation_id} not found for agent {agent_id}.")
        return

    # Build runner URL — append conversation_id so the runner can isolate history
    base_runner_url = (
        settings.test.runner_url or f"ws://{handle.pod_name}.{handle.namespace}.svc.cluster.local:8000/ws/chat"
    )
    runner_url = f"{base_runner_url}?conversation_id={conversation_id}" if conversation_id else base_runner_url
    await websocket.accept()

    # Register active websocket connection
    if conversation_id:
        key = (agent_id, conversation_id)
        _active_chat_connections.setdefault(key, []).append(websocket)

    try:
        async with websockets.connect(runner_url) as runner_ws:  # type: ignore[attr-defined]
            logger.info(f"Chat proxy open: client ↔ {agent_id} ({runner_url})")

            async def _client_to_runner() -> None:
                """Forward messages from the external client to the runner pod."""
                is_first_msg = True
                async for message in websocket.iter_text():
                    nonlocal conversation_id
                    if is_first_msg and conversation_id:
                        is_first_msg = False
                        key = (agent_id, conversation_id)
                        if key in _conversations:
                            conv = _conversations[key]
                            if conv.name == "New Conversation":
                                title = _generate_conversation_title(message)
                                conv.name = title
                                logger.info(f"Auto-named conversation {conversation_id} to {title!r}")
                    await runner_ws.send(message)

            async def _runner_to_client() -> None:
                """Forward tokens from the runner pod to the external client."""
                async for token in runner_ws:
                    await websocket.send_text(str(token))

            await asyncio.wait(
                [
                    asyncio.ensure_future(_client_to_runner()),
                    asyncio.ensure_future(_runner_to_client()),
                ],
                return_when=asyncio.ALL_COMPLETED,
            )

    except websockets.exceptions.ConnectionClosed:
        pass
    except WebSocketDisconnect:
        pass
    except (OSError, TimeoutError, websockets.exceptions.WebSocketException) as e:
        logger.warning(f"Chat proxy error for agent {agent_id}: {e}")
        await websocket.close(code=1011, reason=str(e))
    finally:
        if conversation_id:
            key = (agent_id, conversation_id)
            if key in _active_chat_connections:
                if websocket in _active_chat_connections[key]:
                    _active_chat_connections[key].remove(websocket)
                if not _active_chat_connections[key]:
                    _active_chat_connections.pop(key, None)
        logger.info(f"Chat proxy closed: {agent_id}")


# ---------------------------------------------------------------------------
# A2A Task lifecycle endpoints
# ---------------------------------------------------------------------------


@app.post(path="/agents/{agent_id}/tasks", response_model=TaskResponse, status_code=201)
async def submit_task(agent_id: str, body: SubmitTaskRequest) -> TaskResponse:
    """
    Submit a new A2A task to an agent sandbox (fire-and-forget).

    Proxies to ``POST /a2a/tasks/send`` on the runner pod.  The runner
    executes the task asynchronously and returns immediately with
    ``status=submitted``.  Poll ``GET /agents/{agent_id}/tasks/{task_id}``
    to retrieve the result.

    Args:
        agent_id: The target agent sandbox identifier.
        body: The task submission payload containing the instruction message.
    """
    handle = _sandboxes.get(agent_id)
    if not handle:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found.")

    base = _runner_http_url(handle)
    payload = {
        "message": {"role": "user", "parts": [{"type": "text", "text": body.message}]},
        "source": body.source,
    }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{base}/a2a/tasks/send", json=payload)
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Runner unreachable: {exc}") from exc

    data = resp.json()
    task_id: str = data["id"]
    now = datetime.utcnow().isoformat()
    logger.info(f"Task {task_id} submitted to agent {agent_id} (fire-and-forget)")

    return TaskResponse(
        task_id=task_id,
        agent_id=agent_id,
        status="submitted",
        source=body.source,
        message=body.message,
        result=None,
        created_at=now,
        updated_at=now,
    )


def _runner_http_url(handle: SandboxHandle) -> str:
    """Return the base HTTP URL for the runner pod.

    Uses ``settings.test.runner_url`` when set (smoke tests without K8s).
    Falls back to in-cluster DNS.
    """
    if settings.test.runner_url:
        base = settings.test.runner_url
        base = re.sub(r"^ws", "http", base)
        base = base.rstrip("/").removesuffix("/ws/chat")
        return base
    return f"http://{handle.pod_name}.{handle.namespace}.svc.cluster.local:8000"


@app.get(path="/agents/{agent_id}/tasks", response_model=list[TaskResponse])
async def list_tasks(agent_id: str) -> list[TaskResponse]:
    """
    List all A2A tasks for a given agent sandbox.

    Proxies to GET /a2a/tasks on the runner pod so that tasks created by
    background triggers are visible alongside tasks submitted via the CLI.

    Args:
        agent_id: The agent sandbox identifier.
    """
    handle = _sandboxes.get(agent_id)
    if not handle:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found.")

    base = _runner_http_url(handle)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{base}/a2a/tasks")
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Runner unreachable: {exc}") from exc

    return [
        TaskResponse(
            task_id=t["task_id"],
            agent_id=agent_id,
            status=t["status"],
            source=t.get("source", "manual"),
            message=t["message"],
            result=t.get("result"),
            created_at=t["created_at"],
            updated_at=t["updated_at"],
        )
        for t in resp.json()
    ]


@app.get(path="/agents/{agent_id}/tasks/{task_id}", response_model=TaskResponse)
async def get_task(agent_id: str, task_id: str) -> TaskResponse:
    """
    Return the current state of a single A2A task.

    Proxies to GET /a2a/tasks/{task_id} on the runner pod.

    Args:
        agent_id: The agent sandbox identifier.
        task_id: The task identifier.
    """
    handle = _sandboxes.get(agent_id)
    if not handle:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found.")

    base = _runner_http_url(handle)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{base}/a2a/tasks/{task_id}")
            if resp.status_code == 404:
                raise HTTPException(status_code=404, detail=f"Task {task_id} not found for agent {agent_id}.")
            resp.raise_for_status()
    except HTTPException:
        raise
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Runner unreachable: {exc}") from exc

    t = resp.json()
    return TaskResponse(
        task_id=t["task_id"],
        agent_id=agent_id,
        status=t["status"],
        source=t.get("source", "manual"),
        message=t["message"],
        result=t.get("result"),
        created_at=t["created_at"],
        updated_at=t["updated_at"],
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
        source=task.source,
        message=task.message,
        result=task.result,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


# ---------------------------------------------------------------------------
# A2A delegation endpoint
# ---------------------------------------------------------------------------


@app.post(path="/agents/{source_agent_id}/delegate", response_model=DelegateTaskResponse, status_code=201)
async def delegate_task(source_agent_id: str, body: DelegateTaskRequest) -> DelegateTaskResponse:
    """Delegate an A2A task from a source agent to a target agent.

    The Control Plane acts as broker: it looks up the target agent's runner
    URL from the Card Registry and forwards the task via POST /a2a/tasks/send.

    Args:
        source_agent_id: The agent initiating the delegation.
        body:            Delegation payload — target agent ID and message.

    Raises:
        HTTPException 404: source or target agent not found.
        HTTPException 502: target runner is unreachable.
    """
    if source_agent_id not in _sandboxes:
        raise HTTPException(status_code=404, detail=f"Source agent {source_agent_id} not found.")

    target_handle = _sandboxes.get(body.target_agent_id)
    if not target_handle:
        raise HTTPException(status_code=404, detail=f"Target agent {body.target_agent_id} not found.")

    base = _runner_http_url(target_handle)
    payload = {
        "message": {"role": "user", "parts": [{"type": "text", "text": body.message}]},
        "source": body.source,
    }
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(f"{base}/a2a/tasks/send", json=payload)
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Target runner unreachable: {exc}") from exc

    data = resp.json()
    task_id: str = data["id"]
    logger.info(f"Task {task_id} delegated from {source_agent_id} to {body.target_agent_id}")

    return DelegateTaskResponse(
        task_id=task_id,
        source_agent_id=source_agent_id,
        target_agent_id=body.target_agent_id,
        status=data.get("status", {}).get("state", "submitted"),
    )


# ---------------------------------------------------------------------------
# Conversation management endpoints
# ---------------------------------------------------------------------------


@app.post(path="/agents/{agent_id}/conversations", response_model=ConversationResponse, status_code=201)
async def create_conversation(agent_id: str, body: CreateConversationRequest) -> ConversationResponse:
    """Create a new isolated conversation for an agent.

    Args:
        agent_id: The agent sandbox identifier.
        body:     Optional label for the conversation.

    Returns:
        The newly created conversation.

    Raises:
        HTTPException: 404 if the agent does not exist.
    """
    if agent_id not in _sandboxes:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found.")
    name = body.name.strip() if (body.name and body.name.strip()) else "New Conversation"
    conv = Conversation(agent_id=agent_id, name=name)
    _conversations[(agent_id, conv.conversation_id)] = conv
    logger.info(f"Conversation created: agent={agent_id}  id={conv.conversation_id}  name={conv.name!r}")
    return ConversationResponse(
        conversation_id=conv.conversation_id,
        agent_id=conv.agent_id,
        name=conv.name,
        is_active=False,
        created_at=conv.created_at,
    )


@app.get(path="/agents/{agent_id}/conversations", response_model=list[ConversationResponse])
async def list_conversations(agent_id: str) -> list[ConversationResponse]:
    """List all conversations for an agent.

    Args:
        agent_id: The agent sandbox identifier.

    Returns:
        All conversations belonging to the agent, ordered by creation time.

    Raises:
        HTTPException: 404 if the agent does not exist.
    """
    if agent_id not in _sandboxes:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found.")
    convs = [v for k, v in _conversations.items() if k[0] == agent_id]
    convs.sort(key=lambda c: c.created_at)
    return [
        ConversationResponse(
            conversation_id=c.conversation_id,
            agent_id=c.agent_id,
            name=c.name,
            is_active=(c.agent_id, c.conversation_id) in _active_chat_connections
            and bool(_active_chat_connections[(c.agent_id, c.conversation_id)]),
            created_at=c.created_at,
        )
        for c in convs
    ]


@app.delete(path="/agents/{agent_id}/conversations/{conversation_id}", status_code=204)
async def delete_conversation(agent_id: str, conversation_id: str, force: bool = Query(False)) -> None:
    """Delete a conversation.

    Args:
        agent_id:        The agent sandbox identifier.
        conversation_id: The conversation UUID to delete.
        force:           Whether to force-disconnect any active websocket connections and delete.

    Raises:
        HTTPException: 404 if the conversation does not exist.
        HTTPException: 409 if the conversation has active connections and force is False.
    """
    key = (agent_id, conversation_id)
    if key not in _conversations:
        raise HTTPException(status_code=404, detail=f"Conversation {conversation_id} not found for agent {agent_id}.")

    # Check for active websocket connections
    if _active_chat_connections.get(key):
        if not force:
            raise HTTPException(
                status_code=409,
                detail="Conversation has active connections. Use force to delete.",
            )
        # Force disconnect all active websocket connections
        for ws in list(_active_chat_connections[key]):
            try:
                await ws.close(code=1001, reason="Conversation deleted via force option.")
            except Exception as exc:  # noqa: BLE001
                logger.debug(f"Failed to close active websocket during force delete: {exc}")
        _active_chat_connections.pop(key, None)

    del _conversations[key]
    logger.info(f"Conversation deleted: agent={agent_id}  id={conversation_id}")


@app.get(path="/health")
async def health() -> dict:
    return {"status": "ok"}
