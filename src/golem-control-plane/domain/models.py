# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Domain models for the Golem Control Plane."""

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class SandboxMode(StrEnum):
    EPHEMERAL = "ephemeral"
    STATEFUL = "stateful"


class AgentSpec(BaseModel):
    """Input specification for creating a new agent sandbox."""

    agent_id: str = Field(description="Agent identifier from config.yaml — used as namespace and pod name prefix.")
    mode: SandboxMode = Field(default=SandboxMode.EPHEMERAL, description="Sandbox lifecycle mode.")
    ttl_seconds: int | None = Field(
        default=None,
        description="Idle TTL in seconds before the sandbox is garbage-collected. None means the sandbox never expires.",
    )
    runner_config: str = Field(default="", description="Raw runner config.yaml content to mount in the pod.")
    agents_md: str | None = Field(
        default=None,
        description="Optional AGENTS.md content to mount at /app/AGENTS.md inside the pod.",
    )
    skills: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of skill name to SKILL.md content. Each skill is mounted at /app/skills/<name>.md.",
    )
    env_secrets: list[str] = Field(
        default_factory=list,
        description="Names of K8s Secrets already in the agent namespace to mount as envFrom.",
    )


class SandboxStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    FAILED = "failed"
    TERMINATED = "terminated"


class SandboxHandle(BaseModel):
    """Runtime reference to a provisioned sandbox."""

    agent_id: str = Field(description="Agent identifier — also used as namespace and pod name prefix.")
    namespace: str = ""
    pod_name: str = ""
    status: SandboxStatus = SandboxStatus.PENDING
    ttl_seconds: int | None = None
    agent_card: dict | None = None

    def model_post_init(self, __context: object, /) -> None:
        if not self.namespace:
            self.namespace = self.agent_id
        if not self.pod_name:
            self.pod_name = f"{self.agent_id}-runner"


# ---------------------------------------------------------------------------
# A2A Task lifecycle
# ---------------------------------------------------------------------------


class TaskStatus(StrEnum):
    SUBMITTED = "submitted"
    WORKING = "working"
    COMPLETED = "completed"
    FAILED = "failed"


class A2ATask(BaseModel):
    """A single A2A task assigned to an agent sandbox."""

    task_id: str = Field(default_factory=lambda: f"task-{uuid.uuid4().hex[:12]}")
    agent_id: str
    status: TaskStatus = TaskStatus.SUBMITTED
    source: str = Field(
        default="manual",
        description="Origin of the task: 'golem-cli', 'timer', 'cron', 'webhook', or 'a2a'.",
    )
    message: str = Field(default="", description="The input message / instruction for this task.")
    result: str | None = Field(default=None, description="Output produced by the agent when the task completes.")
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))


# ---------------------------------------------------------------------------
# Conversation
# ---------------------------------------------------------------------------


class Conversation(BaseModel):
    """A named, isolated conversation associated with an agent."""

    conversation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str
    name: str = Field(default="", description="Optional human-readable label.")
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
