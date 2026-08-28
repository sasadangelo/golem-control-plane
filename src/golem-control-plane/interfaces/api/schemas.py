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
    signature: str | None = None  # placeholder — validated in Phase 2


class DelegateTaskRequest(BaseModel):
    """Request body for POST /agents/{source_id}/delegate."""

    target_agent_id: str
    message: str
    source: str = "a2a"


class DelegateTaskResponse(BaseModel):
    """Response body for POST /agents/{source_id}/delegate."""

    task_id: str
    source_agent_id: str
    target_agent_id: str
    status: str


class HandshakeResponse(BaseModel):
    """Response body for POST /agents/{agent_id}/handshake."""

    registered: bool
    agent_id: str


class CreateConversationRequest(BaseModel):
    """Request body for POST /agents/{agent_id}/conversations."""

    name: str = ""


class ConversationResponse(BaseModel):
    """Response schema for conversation endpoints."""

    conversation_id: str
    agent_id: str
    name: str
    is_active: bool = False
    created_at: datetime
