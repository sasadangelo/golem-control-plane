# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Pydantic request/response schemas for the Control Plane HTTP API."""

from datetime import datetime

from pydantic import BaseModel


class CreateAgentResponse(BaseModel):
    agent_id: str
    namespace: str
    status: str


class AgentStatusResponse(BaseModel):
    agent_id: str
    namespace: str
    status: str
    agent_card: dict | None = None


class SubmitTaskRequest(BaseModel):
    """Request body for POST /agents/{agent_id}/tasks."""

    message: str
    source: str = "manual"


class UpdateTaskRequest(BaseModel):
    """Request body for PATCH /agents/{agent_id}/tasks/{task_id}."""

    status: str
    result: str | None = None


class TaskResponse(BaseModel):
    """Response schema for A2A task endpoints."""

    task_id: str
    agent_id: str
    status: str
    source: str = "manual"
    message: str
    result: str | None = None
    created_at: datetime
    updated_at: datetime


class HandshakeRequest(BaseModel):
    """Request body for POST /agents/{agent_id}/handshake.

    The runner sends its full A2A Agent Card so the Control Plane can
    register it immediately on startup (push model) rather than waiting
    for the first status-poll to trigger a fetch (pull model).
    """

    card: dict


class HandshakeResponse(BaseModel):
    """Response body for POST /agents/{agent_id}/handshake."""

    registered: bool
    agent_id: str
