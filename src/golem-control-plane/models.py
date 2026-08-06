# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Domain models for the Golem Control Plane."""

import uuid
from enum import StrEnum

from pydantic import BaseModel, Field


class SandboxMode(StrEnum):
    EPHEMERAL = "ephemeral"
    STATEFUL = "stateful"


class AgentSpec(BaseModel):
    """Input specification for creating a new agent sandbox."""

    name: str = Field(..., description="Human-readable agent name.")
    system_prompt: str = Field(..., description="Agent persona and instructions.")
    enabled_skills: list[str] = Field(
        default_factory=list, description="Skill IDs to activate (e.g. bash, http_check)."
    )
    mode: SandboxMode = Field(default=SandboxMode.EPHEMERAL, description="Sandbox lifecycle mode.")
    ttl_seconds: int = Field(default=3600, description="Idle TTL before the sandbox is garbage-collected.")


class SandboxStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    FAILED = "failed"
    TERMINATED = "terminated"


class SandboxHandle(BaseModel):
    """Runtime reference to a provisioned sandbox."""

    agent_id: str = Field(default_factory=lambda: f"golem-agent-{uuid.uuid4().hex[:8]}")
    namespace: str = ""
    pod_name: str = ""
    status: SandboxStatus = SandboxStatus.PENDING
    ttl_seconds: int = 3600
    agent_card: dict | None = None

    def model_post_init(self, __context: object) -> None:
        if not self.namespace:
            self.namespace = self.agent_id
        if not self.pod_name:
            self.pod_name = f"{self.agent_id}-runner"
