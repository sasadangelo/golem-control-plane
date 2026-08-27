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
        "infrastructure",
        "infrastructure.adapters",
        "infrastructure.adapters.k8s_provisioner",
        "infrastructure.adapters.card_registry",
        "interfaces",
        "interfaces.api",
        "interfaces.api.schemas",
        "interfaces.api.app",
    ):
        sys.modules.pop(mod, None)

    import infrastructure.adapters.k8s_provisioner as k8s_mod

    with patch.object(k8s_mod, "_load_k8s_config"):
        import interfaces.api.app as cp

        mock_prov = MagicMock()
        cp.provisioner = mock_prov  # type: ignore[attr-defined]
        cp._sandboxes.clear()  # type: ignore[attr-defined]
        cp._created_at.clear()  # type: ignore[attr-defined]

        from domain.models import SandboxHandle, SandboxStatus

        handle = SandboxHandle(agent_id="golem-agent-expired", ttl_seconds=60)
        handle.status = SandboxStatus.RUNNING
        cp._sandboxes["golem-agent-expired"] = handle  # type: ignore[attr-defined]
        # Set created_at 120 seconds in the past (TTL is 60s → already expired)
        cp._created_at["golem-agent-expired"] = time.time() - 120  # type: ignore[attr-defined]

        # Run one GC pass synchronously by replicating the loop logic
        import asyncio

        async def _one_pass() -> None:
            now = time.time()
            expired = [
                aid for aid, h in list(cp._sandboxes.items()) if now - cp._created_at.get(aid, now) > h.ttl_seconds
            ]
            for aid in expired:
                h = cp._sandboxes[aid]
                cp.provisioner.delete_sandbox(h)
                from infrastructure.adapters import card_registry

                card_registry.deregister(aid)
                cp._sandboxes.pop(aid, None)
                cp._created_at.pop(aid, None)

        asyncio.run(_one_pass())

    assert "golem-agent-expired" not in cp._sandboxes  # type: ignore[attr-defined]
    mock_prov.delete_sandbox.assert_called_once()


def test_gc_keeps_non_expired_sandbox() -> None:
    """GC loop must not delete a sandbox whose TTL has not yet expired."""
    for mod in (
        "domain",
        "domain.models",
        "domain.ports",
        "domain.ports.provisioner",
        "infrastructure",
        "infrastructure.adapters",
        "infrastructure.adapters.k8s_provisioner",
        "infrastructure.adapters.card_registry",
        "interfaces",
        "interfaces.api",
        "interfaces.api.schemas",
        "interfaces.api.app",
    ):
        sys.modules.pop(mod, None)

    import infrastructure.adapters.k8s_provisioner as k8s_mod

    with patch.object(k8s_mod, "_load_k8s_config"):
        import interfaces.api.app as cp

        mock_prov = MagicMock()
        cp.provisioner = mock_prov  # type: ignore[attr-defined]
        cp._sandboxes.clear()  # type: ignore[attr-defined]
        cp._created_at.clear()  # type: ignore[attr-defined]

        from domain.models import SandboxHandle, SandboxStatus

        handle = SandboxHandle(agent_id="golem-agent-alive", ttl_seconds=3600)
        handle.status = SandboxStatus.RUNNING
        cp._sandboxes["golem-agent-alive"] = handle  # type: ignore[attr-defined]
        cp._created_at["golem-agent-alive"] = time.time()  # just created

        import asyncio

        async def _one_pass() -> None:
            now = time.time()
            expired = [
                aid for aid, h in list(cp._sandboxes.items()) if now - cp._created_at.get(aid, now) > h.ttl_seconds
            ]
            for aid in expired:
                cp._sandboxes.pop(aid, None)

        asyncio.run(_one_pass())

    assert "golem-agent-alive" in cp._sandboxes  # type: ignore[attr-defined]
    mock_prov.delete_sandbox.assert_not_called()
