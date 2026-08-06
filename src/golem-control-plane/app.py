# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Golem Control Plane — FastAPI application."""

import asyncio
import logging
import os
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import card_registry
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from k8s_provisioner import KubernetesProvisioner
from models import AgentSpec, SandboxHandle, SandboxStatus
from pydantic import BaseModel

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# In-memory store of active sandboxes. Replaced by PostgreSQL in Week 3.
_sandboxes: dict[str, SandboxHandle] = {}

# Sandbox creation timestamps for TTL tracking {agent_id: created_at_epoch}
_created_at: dict[str, float] = {}

GC_INTERVAL_SECONDS = int(os.getenv("GC_INTERVAL_SECONDS", "60"))


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
            logger.info("TTL expired for agent %s — deleting sandbox.", agent_id)
            try:
                provisioner.delete_sandbox(handle)
            except Exception as e:
                logger.warning("GC could not delete sandbox %s: %s", agent_id, e)
            card_registry.deregister(agent_id)
            _sandboxes.pop(agent_id, None)
            _created_at.pop(agent_id, None)


@asynccontextmanager
async def lifespan(app_: FastAPI) -> AsyncGenerator[None, None]:
    """Start the TTL GC background task on startup and cancel it on shutdown."""
    gc_task = asyncio.create_task(_gc_loop())
    logger.info("TTL garbage collector started (interval=%ds).", GC_INTERVAL_SECONDS)
    try:
        yield
    finally:
        gc_task.cancel()
        logger.info("TTL garbage collector stopped.")


provisioner = KubernetesProvisioner()
app = FastAPI(title="Golem Control Plane", version="0.1.0", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class CreateAgentRequest(BaseModel):
    name: str
    system_prompt: str
    enabled_skills: list[str] = []
    ttl_seconds: int = 3600


class CreateAgentResponse(BaseModel):
    agent_id: str
    namespace: str
    status: str


class AgentStatusResponse(BaseModel):
    agent_id: str
    status: str
    agent_card: dict | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.post("/agents", response_model=CreateAgentResponse, status_code=201)
async def create_agent(request: CreateAgentRequest) -> CreateAgentResponse:
    """
    Provision a new isolated agent sandbox.

    Creates a K8s Namespace + Pod + ResourceQuota + NetworkPolicy
    for the given agent specification.
    """
    spec = AgentSpec(
        name=request.name,
        system_prompt=request.system_prompt,
        enabled_skills=request.enabled_skills,
        ttl_seconds=request.ttl_seconds,
    )

    try:
        handle = provisioner.create_sandbox(spec)
    except Exception as e:
        logger.error("Failed to create sandbox: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e

    _sandboxes[handle.agent_id] = handle
    _created_at[handle.agent_id] = time.time()
    logger.info("Agent %s created in namespace %s.", handle.agent_id, handle.namespace)

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
    handle = _sandboxes.get(agent_id)
    if not handle:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found.")

    try:
        provisioner.delete_sandbox(handle)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    card_registry.deregister(agent_id)
    _sandboxes.pop(agent_id, None)
    _created_at.pop(agent_id, None)
    logger.info("Agent %s deleted.", agent_id)


@app.get("/agents", response_model=list[AgentStatusResponse])
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


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
