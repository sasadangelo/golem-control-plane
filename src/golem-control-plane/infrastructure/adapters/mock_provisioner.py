# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Mock Provisioner — local smoke-testing only, never used in production."""

import httpx

from core.config import settings
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

    ``get_status`` fetches the Agent Card from the local runner via
    ``settings.test.runner_url`` (converted to HTTP) instead of the K8s
    in-cluster address used by the real provisioner, so peer-discovery
    works end-to-end in local dev mode.

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
        """Return RUNNING and fetch the Agent Card from the local runner if not yet registered.

        Derives the card URL from ``settings.test.runner_url`` by replacing
        the ``ws://`` scheme with ``http://`` and stripping the WebSocket path,
        so no K8s DNS is needed in local dev mode.
        """
        handle.status = SandboxStatus.RUNNING

        if handle.agent_card:
            return handle

        # Derive HTTP base from ws runner_url: ws://localhost:8000/ws/chat → http://localhost:8000
        runner_ws_url: str = settings.test.runner_url or ""
        if not runner_ws_url:
            return handle

        http_base = runner_ws_url.replace("ws://", "http://").replace("wss://", "https://")
        http_base = http_base.split("/ws/")[0].rstrip("/")
        card_url = f"{http_base}/.well-known/agent.json"

        try:
            response = httpx.get(card_url, timeout=5.0)
            response.raise_for_status()
            handle.agent_card = response.json()
            logger.info(f"MockProvisioner: Agent Card fetched for '{handle.agent_id}' from {card_url}")
        except Exception as e:
            logger.warning(f"MockProvisioner: could not fetch Agent Card from {card_url}: {e}")

        return handle
