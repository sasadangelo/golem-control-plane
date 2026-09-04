# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""AgentService — application-layer use cases for sandbox lifecycle management."""

import asyncio
import time
from asyncio.events import AbstractEventLoop

import yaml

from core.config import settings
from core.log import LoggerManager
from domain.models import AgentSpec, SandboxHandle, SandboxStatus
from domain.ports.card_registry import CardRegistry
from domain.ports.provisioner import Provisioner
from domain.ports.sandbox_repo import SandboxRepository

logger = LoggerManager.get_logger(name="AgentService")

GC_INTERVAL_SECONDS: int = settings.control_plane.gc_interval


class AgentService:
    """Encapsulates all business logic for sandbox creation, deletion, status, and GC."""

    def __init__(
        self,
        provisioner: Provisioner,
        sandbox_repo: SandboxRepository,
        card_registry: CardRegistry,
    ) -> None:
        self._provisioner = provisioner
        self._repo = sandbox_repo
        self._card_registry = card_registry

    # ------------------------------------------------------------------
    # Use-case: create agent
    # ------------------------------------------------------------------

    def create_agent(
        self,
        runner_config: str,
        ttl_seconds: int | None,
        agents_md: str | None,
        skills: dict[str, str],
    ) -> SandboxHandle:
        """Parse config, provision sandbox, persist handle.

        Args:
            runner_config: Raw content of the runner config.yaml file.
            ttl_seconds: Optional idle TTL before GC deletes the sandbox.
            agents_md: Optional AGENTS.md content to mount in the pod.
            skills: Mapping of skill-name → SKILL.md content.

        Returns:
            The newly created SandboxHandle.

        Raises:
            ValueError: If agent.id is missing from config.yaml.
            RuntimeError: If the provisioner fails to create the sandbox.
        """
        try:
            _cfg = yaml.safe_load(runner_config) or {}
            agent_id: str = _cfg.get("agent", {}).get("id", "")
            env_secrets: list[str] = _cfg.get("agent", {}).get("env_secrets", [])
        except yaml.YAMLError:
            agent_id = ""
            env_secrets = []

        if not agent_id:
            raise ValueError("config.yaml must contain agent.id")

        spec = AgentSpec(
            agent_id=agent_id,
            ttl_seconds=ttl_seconds,
            runner_config=runner_config,
            agents_md=agents_md,
            skills=skills,
            env_secrets=env_secrets,
        )

        handle: SandboxHandle = self._provisioner.create_sandbox(spec)
        self._repo.save(handle)
        self._repo.set_created_at(handle.agent_id, time.time())
        logger.info(f"Agent {handle.agent_id} created in namespace {handle.namespace}")
        return handle

    # ------------------------------------------------------------------
    # Use-case: get agent status
    # ------------------------------------------------------------------

    async def get_status(self, agent_id: str) -> SandboxHandle:
        """Refresh and return the live status of a sandbox.

        Args:
            agent_id: The agent sandbox identifier.

        Returns:
            An updated SandboxHandle.

        Raises:
            KeyError: If the agent does not exist.
            RuntimeError: If the provisioner call fails.
        """
        handle = self._repo.get(agent_id)
        if handle is None:
            raise KeyError(agent_id)

        loop: AbstractEventLoop = asyncio.get_event_loop()
        handle = await loop.run_in_executor(None, self._provisioner.get_status, handle)
        self._repo.save(handle)
        self._register_card_if_running(handle)
        return handle

    # ------------------------------------------------------------------
    # Use-case: delete agent
    # ------------------------------------------------------------------

    def delete_agent(self, agent_id: str) -> None:
        """Tear down the sandbox and deregister its card.

        Args:
            agent_id: The agent sandbox identifier.

        Raises:
            KeyError: If the agent does not exist.
            RuntimeError: If the provisioner call fails.
        """
        handle = self._repo.get(agent_id)
        if handle is None:
            raise KeyError(agent_id)

        self._provisioner.delete_sandbox(handle)
        self._card_registry.deregister(agent_id)
        self._repo.delete(agent_id)
        logger.info(f"Agent {agent_id} deleted")

    # ------------------------------------------------------------------
    # Use-case: list agents
    # ------------------------------------------------------------------

    async def list_agents(self) -> list[SandboxHandle]:
        """Return all sandboxes with their live status (parallel refresh).

        Returns:
            A list of up-to-date SandboxHandles.
        """
        loop: AbstractEventLoop = asyncio.get_event_loop()
        snapshot = self._repo.items()

        async def _refresh(agent_id: str, handle: SandboxHandle) -> SandboxHandle:
            try:
                handle = await loop.run_in_executor(None, self._provisioner.get_status, handle)
            except (OSError, RuntimeError, ValueError) as e:
                logger.warning(f"Could not refresh status for agent {agent_id}: {e}")
            else:
                self._repo.save(handle)
                self._register_card_if_running(handle)
            return handle

        return list(await asyncio.gather(*(_refresh(aid, h) for aid, h in snapshot)))

    # ------------------------------------------------------------------
    # Use-case: handshake (runner push)
    # ------------------------------------------------------------------

    def register_handshake(self, agent_id: str, card: dict) -> None:
        """Record the agent card pushed by the runner pod at startup.

        Args:
            agent_id: The agent sandbox identifier.
            card: The full A2A Agent Card dict.

        Raises:
            KeyError: If the agent does not exist.
        """
        handle = self._repo.get(agent_id)
        if handle is None:
            raise KeyError(agent_id)

        self._card_registry.register_card(agent_id=agent_id, card=card)
        handle.agent_card = card
        handle.status = SandboxStatus.RUNNING
        self._repo.save(handle)
        logger.info(f"Handshake completed for agent {agent_id}")

    # ------------------------------------------------------------------
    # Use-case: get agent card
    # ------------------------------------------------------------------

    def get_card(self, agent_id: str) -> dict:
        """Return the registered A2A Agent Card.

        Args:
            agent_id: The agent sandbox identifier.

        Returns:
            The Agent Card dict.

        Raises:
            KeyError: If no card is registered for agent_id.
        """
        card = self._card_registry.get_card(agent_id)
        if card is None:
            raise KeyError(agent_id)
        return card

    # ------------------------------------------------------------------
    # Background: TTL garbage collector
    # ------------------------------------------------------------------

    async def gc_loop(self) -> None:
        """Background coroutine: refresh PENDING sandboxes and expire stale ones.

        Runs every GC_INTERVAL_SECONDS.  Started by the FastAPI lifespan handler.
        """
        while True:
            await asyncio.sleep(GC_INTERVAL_SECONDS)
            loop: AbstractEventLoop = asyncio.get_event_loop()

            for agent_id, handle in self._repo.items():
                if handle.status == SandboxStatus.PENDING:
                    try:
                        refreshed = await loop.run_in_executor(None, self._provisioner.get_status, handle)
                        self._repo.save(refreshed)
                        self._register_card_if_running(refreshed)
                    except Exception as e:  # noqa: BLE001
                        logger.warning(f"GC could not refresh status for agent {agent_id}: {e}")

            now = time.time()
            expired: list[str] = [
                agent_id
                for agent_id, handle in self._repo.items()
                if handle.ttl_seconds is not None
                and now - (self._repo.get_created_at(agent_id) or now) > handle.ttl_seconds
            ]
            for agent_id in expired:
                expired_handle = self._repo.get(agent_id)
                if expired_handle is None:
                    continue
                handle = expired_handle
                logger.info(f"TTL expired for agent {agent_id} — deleting sandbox")
                try:
                    self._provisioner.delete_sandbox(handle)  # handle is SandboxHandle here
                except (OSError, RuntimeError) as e:
                    logger.warning(f"GC could not delete sandbox {agent_id}: {e}")
                self._card_registry.deregister(agent_id)
                self._repo.delete(agent_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _register_card_if_running(self, handle: SandboxHandle) -> None:
        """Register the agent card the first time a sandbox reaches RUNNING."""
        if handle.status == SandboxStatus.RUNNING and not self._card_registry.get_card(handle.agent_id):
            if handle.agent_card:
                self._card_registry.register_card(agent_id=handle.agent_id, card=handle.agent_card)
            else:
                self._card_registry.fetch_and_register(handle)
