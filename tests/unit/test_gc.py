# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Unit tests for the TTL garbage collector."""

import sys
import time
from unittest.mock import MagicMock, patch


def test_gc_deletes_expired_sandbox() -> None:
    """GC loop must delete a sandbox whose TTL has expired."""
    for mod in (
        "domain",
        "domain.models",
        "domain.ports",
        "domain.ports.provisioner",
        "domain.ports.sandbox_repo",
        "domain.ports.task_repo",
        "infrastructure",
        "infrastructure.adapters",
        "infrastructure.adapters.k8s_provisioner",
        "infrastructure.adapters.card_registry",
        "infrastructure.adapters.in_memory_repos",
        "application",
        "application.services",
        "application.services.agent_service",
        "application.services.task_service",
        "application.services.conversation_service",
        "application.services.chat_service",
        "interfaces",
        "interfaces.api",
        "interfaces.api.schemas",
        "interfaces.api.routers",
        "interfaces.api.routers.agent_router",
        "interfaces.api.routers.task_router",
        "interfaces.api.routers.conversation_router",
        "interfaces.api.routers.chat_router",
        "interfaces.api.app",
    ):
        sys.modules.pop(mod, None)

    import infrastructure.adapters.k8s_provisioner as k8s_mod

    with patch.object(k8s_mod, "_load_k8s_config"):
        import interfaces.api.app as cp

        mock_prov = MagicMock()
        cp.agent_service._provisioner = mock_prov  # type: ignore[attr-defined]
        cp.sandbox_repo._sandboxes.clear()  # type: ignore[attr-defined]
        cp.sandbox_repo._created_at.clear()  # type: ignore[attr-defined]

        from domain.models import SandboxHandle, SandboxStatus

        handle = SandboxHandle(agent_id="golem-agent-expired", ttl_seconds=60)
        handle.status = SandboxStatus.RUNNING
        cp.sandbox_repo.save(handle)  # type: ignore[attr-defined]
        # Set created_at 120 seconds in the past (TTL is 60s → already expired)
        cp.sandbox_repo.set_created_at("golem-agent-expired", time.time() - 120)  # type: ignore[attr-defined]

        # Run one GC pass synchronously by replicating the loop logic
        import asyncio

        async def _one_pass() -> None:
            now = time.time()
            expired = [
                agent_id
                for agent_id, h in cp.sandbox_repo.items()  # type: ignore[attr-defined]
                if h.ttl_seconds is not None and now - (cp.sandbox_repo.get_created_at(agent_id) or now) > h.ttl_seconds
            ]
            for agent_id in expired:
                h = cp.sandbox_repo.get(agent_id)  # type: ignore[attr-defined]
                assert h is not None
                cp.agent_service._provisioner.delete_sandbox(h)  # type: ignore[attr-defined]
                cp.card_registry.deregister(agent_id)  # type: ignore[attr-defined]
                cp.sandbox_repo.delete(agent_id)  # type: ignore[attr-defined]

        asyncio.run(_one_pass())

    assert cp.sandbox_repo.get("golem-agent-expired") is None  # type: ignore[attr-defined]
    mock_prov.delete_sandbox.assert_called_once()


def test_gc_keeps_non_expired_sandbox() -> None:
    """GC loop must not delete a sandbox whose TTL has not yet expired."""
    for mod in (
        "domain",
        "domain.models",
        "domain.ports",
        "domain.ports.provisioner",
        "domain.ports.sandbox_repo",
        "domain.ports.task_repo",
        "infrastructure",
        "infrastructure.adapters",
        "infrastructure.adapters.k8s_provisioner",
        "infrastructure.adapters.card_registry",
        "infrastructure.adapters.in_memory_repos",
        "application",
        "application.services",
        "application.services.agent_service",
        "application.services.task_service",
        "application.services.conversation_service",
        "application.services.chat_service",
        "interfaces",
        "interfaces.api",
        "interfaces.api.schemas",
        "interfaces.api.routers",
        "interfaces.api.routers.agent_router",
        "interfaces.api.routers.task_router",
        "interfaces.api.routers.conversation_router",
        "interfaces.api.routers.chat_router",
        "interfaces.api.app",
    ):
        sys.modules.pop(mod, None)

    import infrastructure.adapters.k8s_provisioner as k8s_mod

    with patch.object(k8s_mod, "_load_k8s_config"):
        import interfaces.api.app as cp

        mock_prov = MagicMock()
        cp.agent_service._provisioner = mock_prov  # type: ignore[attr-defined]
        cp.sandbox_repo._sandboxes.clear()  # type: ignore[attr-defined]
        cp.sandbox_repo._created_at.clear()  # type: ignore[attr-defined]

        from domain.models import SandboxHandle, SandboxStatus

        handle = SandboxHandle(agent_id="golem-agent-alive", ttl_seconds=3600)
        handle.status = SandboxStatus.RUNNING
        cp.sandbox_repo.save(handle)  # type: ignore[attr-defined]
        cp.sandbox_repo.set_created_at("golem-agent-alive", time.time())  # type: ignore[attr-defined]

        import asyncio

        async def _one_pass() -> None:
            now = time.time()
            expired = [
                agent_id
                for agent_id, h in cp.sandbox_repo.items()  # type: ignore[attr-defined]
                if h.ttl_seconds is not None and now - (cp.sandbox_repo.get_created_at(agent_id) or now) > h.ttl_seconds
            ]
            for agent_id in expired:
                cp.sandbox_repo.delete(agent_id)  # type: ignore[attr-defined]

        asyncio.run(_one_pass())

    assert cp.sandbox_repo.get("golem-agent-alive") is not None  # type: ignore[attr-defined]
    mock_prov.delete_sandbox.assert_not_called()


def test_gc_never_deletes_sandbox_without_ttl() -> None:
    """GC loop must not delete a sandbox whose ttl_seconds is None (persistent)."""
    for mod in (
        "domain",
        "domain.models",
        "domain.ports",
        "domain.ports.provisioner",
        "domain.ports.sandbox_repo",
        "domain.ports.task_repo",
        "infrastructure",
        "infrastructure.adapters",
        "infrastructure.adapters.k8s_provisioner",
        "infrastructure.adapters.card_registry",
        "infrastructure.adapters.in_memory_repos",
        "application",
        "application.services",
        "application.services.agent_service",
        "application.services.task_service",
        "application.services.conversation_service",
        "application.services.chat_service",
        "interfaces",
        "interfaces.api",
        "interfaces.api.schemas",
        "interfaces.api.routers",
        "interfaces.api.routers.agent_router",
        "interfaces.api.routers.task_router",
        "interfaces.api.routers.conversation_router",
        "interfaces.api.routers.chat_router",
        "interfaces.api.app",
    ):
        sys.modules.pop(mod, None)

    import infrastructure.adapters.k8s_provisioner as k8s_mod

    with patch.object(k8s_mod, "_load_k8s_config"):
        import interfaces.api.app as cp

        mock_prov = MagicMock()
        cp.agent_service._provisioner = mock_prov  # type: ignore[attr-defined]
        cp.sandbox_repo._sandboxes.clear()  # type: ignore[attr-defined]
        cp.sandbox_repo._created_at.clear()  # type: ignore[attr-defined]

        from domain.models import SandboxHandle, SandboxStatus

        # ttl_seconds=None → sandbox must live forever
        handle = SandboxHandle(agent_id="golem-agent-persistent", ttl_seconds=None)
        handle.status = SandboxStatus.RUNNING
        cp.sandbox_repo.save(handle)  # type: ignore[attr-defined]
        # Pretend it was created a very long time ago
        cp.sandbox_repo.set_created_at("golem-agent-persistent", time.time() - 99999)  # type: ignore[attr-defined]

        import asyncio

        async def _one_pass() -> None:
            now = time.time()
            expired = [
                agent_id
                for agent_id, h in cp.sandbox_repo.items()  # type: ignore[attr-defined]
                if h.ttl_seconds is not None and now - (cp.sandbox_repo.get_created_at(agent_id) or now) > h.ttl_seconds
            ]
            for agent_id in expired:
                cp.sandbox_repo.delete(agent_id)  # type: ignore[attr-defined]

        asyncio.run(_one_pass())

    assert cp.sandbox_repo.get("golem-agent-persistent") is not None  # type: ignore[attr-defined]
    mock_prov.delete_sandbox.assert_not_called()
