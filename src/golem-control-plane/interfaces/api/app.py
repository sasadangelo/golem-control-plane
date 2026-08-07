# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Golem Control Plane — FastAPI application."""

import asyncio
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from core.config import settings
from core.log import LoggerManager, setup_logging
from domain.models import AgentSpec, SandboxHandle, SandboxStatus
from infrastructure.adapters import card_registry
from infrastructure.adapters.k8s_provisioner import KubernetesProvisioner
from interfaces.api.schemas import AgentStatusResponse, CreateAgentResponse

setup_logging(
    level=settings.log.level,
    console=settings.log.console,
    file=settings.log.file,
    rotation=settings.log.rotation,
    retention=settings.log.retention,
    compression=settings.log.compression,
)

logger = LoggerManager.get_logger("ControlPlaneApp")

# In-memory store of active sandboxes. Replaced by PostgreSQL in Week 3.
_sandboxes: dict[str, SandboxHandle] = {}

# Sandbox creation timestamps for TTL tracking {agent_id: created_at_epoch}
_created_at: dict[str, float] = {}

GC_INTERVAL_SECONDS = settings.control_plane.gc_interval


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
        expired = [
            agent_id
            for agent_id, handle in list(_sandboxes.items())
            if now - _created_at.get(agent_id, now) > handle.ttl_seconds
        ]
        for agent_id in expired:
            handle = _sandboxes[agent_id]
            logger.info(f"TTL expired for agent {agent_id} — deleting sandbox")
            try:
                provisioner.delete_sandbox(handle)
            except Exception as e:
                logger.warning(f"GC could not delete sandbox {agent_id}: {e}")
            card_registry.deregister(agent_id)
            _sandboxes.pop(agent_id, None)
            _created_at.pop(agent_id, None)


@asynccontextmanager
async def lifespan(app_: FastAPI) -> AsyncGenerator[None, None]:
    """Start the TTL GC background task on startup and cancel it on shutdown."""
    gc_task = asyncio.create_task(_gc_loop())
    logger.info(f"TTL garbage collector started (interval={GC_INTERVAL_SECONDS}s)")
    try:
        yield
    finally:
        gc_task.cancel()
        logger.info("TTL garbage collector stopped")


provisioner = KubernetesProvisioner()
app = FastAPI(title="Golem Control Plane", version="0.1.0", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.post("/agents", response_model=CreateAgentResponse, status_code=201)
async def create_agent(
    config: UploadFile = File(..., description="Runner config.yaml file."),
    ttl_seconds: int = Form(default=3600, description="Sandbox TTL in seconds."),
) -> CreateAgentResponse:
    """
    Provision a new isolated agent sandbox.

    Accepts a multipart/form-data request with:
    - ``config``: the runner config.yaml file
    - ``ttl_seconds``: optional sandbox TTL (default 3600)

    Creates a K8s Namespace + ConfigMap + Pod + ResourceQuota + NetworkPolicy.
    """
    runner_config = (await config.read()).decode("utf-8")
    spec = AgentSpec(
        ttl_seconds=ttl_seconds,
        runner_config=runner_config,
    )

    try:
        handle = provisioner.create_sandbox(spec)
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
        handle = provisioner.get_status(handle)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    _sandboxes[agent_id] = handle

    # Fetch Agent Card the first time the pod reaches Running
    if handle.status == SandboxStatus.RUNNING and not handle.agent_card:
        card_registry.fetch_and_register(handle)

    return AgentStatusResponse(
        agent_id=handle.agent_id,
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
    """List all known agent sandboxes."""
    return [
        AgentStatusResponse(
            agent_id=h.agent_id,
            status=h.status,
            agent_card=h.agent_card,
        )
        for h in _sandboxes.values()
    ]


@app.get("/agents/{agent_id}/card")
async def get_agent_card(agent_id: str) -> dict:
    """Return the A2A Agent Card for an agent (A2A peer-discovery endpoint)."""
    card = card_registry.get_card(agent_id)
    if not card:
        raise HTTPException(status_code=404, detail=f"Agent Card for {agent_id} not found.")
    return card


@app.get(path="/health")
async def health() -> dict:
    return {"status": "ok"}
