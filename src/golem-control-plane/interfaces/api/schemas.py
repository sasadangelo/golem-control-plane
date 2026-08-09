# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Pydantic request/response schemas for the Control Plane HTTP API."""

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
