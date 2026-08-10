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


class UpdateTaskRequest(BaseModel):
    """Request body for PATCH /agents/{agent_id}/tasks/{task_id}."""

    status: str
    result: str | None = None


class TaskResponse(BaseModel):
    """Response schema for A2A task endpoints."""

    task_id: str
    agent_id: str
    status: str
    message: str
    result: str | None = None
    created_at: datetime
    updated_at: datetime
