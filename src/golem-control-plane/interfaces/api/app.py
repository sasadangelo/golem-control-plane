# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Golem Control Plane — FastAPI application bootstrap.

This module is intentionally thin: it creates the FastAPI instance, wires
together infrastructure adapters and application services, registers routers,
and exposes the ``app`` object consumed by the ASGI server.

Business logic lives in ``application/services/``.
HTTP routing lives in ``interfaces/api/routers/``.
"""

import asyncio
from _asyncio import Task
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from application.services.agent_service import AgentService
from application.services.chat_service import ChatService
from application.services.conversation_service import ConversationService
from application.services.task_service import TaskService
from fastapi import FastAPI

from core.config import settings
from core.log import LoggerManager, setup_logging
from domain.ports.provisioner import Provisioner
from infrastructure.adapters.card_registry import InMemoryCardRegistry
from infrastructure.adapters.in_memory_repos import (
    InMemoryConversationRepository,
    InMemorySandboxRepository,
    InMemoryTaskRepository,
)
from interfaces.api.routers import make_agent_router, make_chat_router, make_conversation_router, make_task_router

setup_logging(
    level=settings.log.level,
    console=settings.log.console,
    file=settings.log.file,
    rotation=settings.log.rotation,
    retention=settings.log.retention,
    compression=settings.log.compression,
)

logger = LoggerManager.get_logger(name="ControlPlaneApp")


# ---------------------------------------------------------------------------
# Infrastructure — adapters
# ---------------------------------------------------------------------------


def _build_provisioner() -> Provisioner:
    """Return the provisioner configured in settings.

    Uses ``MockProvisioner`` when ``test.provisioner == "mock"`` to allow
    local smoke-testing without a Kubernetes cluster.
    """
    if settings.test.provisioner == "mock":
        from infrastructure.adapters.mock_provisioner import MockProvisioner

        logger.warning("MockProvisioner active — for local smoke-testing only, never use in production")
        return MockProvisioner()

    from infrastructure.adapters.k8s_provisioner import KubernetesProvisioner

    return KubernetesProvisioner()


# ---------------------------------------------------------------------------
# Dependency wiring
# ---------------------------------------------------------------------------

sandbox_repo = InMemorySandboxRepository()
task_repo = InMemoryTaskRepository()
conversation_repo = InMemoryConversationRepository()
card_registry = InMemoryCardRegistry()
provisioner: Provisioner = _build_provisioner()

agent_service = AgentService(provisioner=provisioner, sandbox_repo=sandbox_repo, card_registry=card_registry)
task_service = TaskService(sandbox_repo=sandbox_repo, task_repo=task_repo)
conversation_service = ConversationService(sandbox_repo=sandbox_repo, conversation_repo=conversation_repo)
chat_service = ChatService(sandbox_repo=sandbox_repo)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app_: FastAPI) -> AsyncGenerator[None, None]:
    """Start the TTL GC background task on startup and cancel it on shutdown."""
    gc_task: Task[None] = asyncio.create_task(agent_service.gc_loop())
    logger.info(f"TTL garbage collector started (interval={settings.control_plane.gc_interval}s)")
    try:
        yield
    finally:
        gc_task.cancel()
        logger.info("TTL garbage collector stopped")


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app: FastAPI = FastAPI(title="Golem Control Plane", version="0.1.0", lifespan=lifespan)

app.include_router(make_agent_router(agent_service))
app.include_router(make_task_router(task_service))
app.include_router(make_conversation_router(conversation_service, chat_service))
app.include_router(make_chat_router(chat_service, conversation_service))


@app.get(path="/health")
async def health() -> dict:
    """Liveness probe."""
    return {"status": "ok"}
