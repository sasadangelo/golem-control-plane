# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Mock Provisioner — local smoke-testing only, never used in production."""

from core.log import LoggerManager
from domain.models import AgentSpec, SandboxHandle, SandboxStatus
from domain.ports.provisioner import Provisioner

logger = LoggerManager.get_logger(name="MockProvisioner")


class MockProvisioner(Provisioner):
    """
    No-op provisioner for local development without Kubernetes.

    Creates an in-memory SandboxHandle with status RUNNING immediately,
    so the chat proxy can connect to ``settings.test.runner_url`` without
    needing a real pod.

    Enable via ``config.yaml``:

        test:
          provisioner: "mock"
          runner_url: "ws://localhost:8000/ws/chat"
    """

    def create_sandbox(self, spec: AgentSpec) -> SandboxHandle:
        """Return a RUNNING handle immediately — no K8s resources created."""
        handle: SandboxHandle = SandboxHandle(ttl_seconds=spec.ttl_seconds)
        handle.status = SandboxStatus.RUNNING
        logger.info(f"MockProvisioner: sandbox '{handle.agent_id}' created (status=RUNNING)")
        return handle

    def delete_sandbox(self, handle: SandboxHandle) -> None:
        """No-op — nothing to delete."""
        logger.info(f"MockProvisioner: sandbox '{handle.agent_id}' deleted (no-op)")

    def get_status(self, handle: SandboxHandle) -> SandboxHandle:
        """Always returns RUNNING."""
        handle.status = SandboxStatus.RUNNING
        return handle
