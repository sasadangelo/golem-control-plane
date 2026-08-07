# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Unit tests for domain models (AgentSpec, SandboxHandle, SandboxStatus)."""

import sys

import pytest


@pytest.fixture(autouse=True)
def _use_control_plane_path() -> None:
    """Ensure control-plane modules are importable."""
    import importlib

    for mod in ("models",):
        sys.modules.pop(mod, None)
        importlib.invalidate_caches()


def test_sandbox_handle_auto_generates_agent_id() -> None:
    """SandboxHandle must auto-generate a unique agent_id when not provided."""
    from models import SandboxHandle

    h1 = SandboxHandle()
    h2 = SandboxHandle()
    assert h1.agent_id != h2.agent_id
    assert h1.agent_id.startswith("golem-agent-")


def test_sandbox_handle_derives_namespace_and_pod_name() -> None:
    """namespace and pod_name must be derived from agent_id automatically."""
    from models import SandboxHandle

    h = SandboxHandle()
    assert h.namespace == h.agent_id
    assert h.pod_name == f"{h.agent_id}-runner"


def test_sandbox_handle_explicit_agent_id() -> None:
    """Explicit agent_id must be respected."""
    from models import SandboxHandle

    h = SandboxHandle(agent_id="golem-agent-test")
    assert h.agent_id == "golem-agent-test"
    assert h.namespace == "golem-agent-test"
    assert h.pod_name == "golem-agent-test-runner"


def test_agent_spec_defaults() -> None:
    """AgentSpec must apply sensible defaults."""
    from models import AgentSpec, SandboxMode

    spec = AgentSpec()
    assert spec.mode == SandboxMode.EPHEMERAL
    assert spec.ttl_seconds == 3600
    assert spec.runner_config == ""


def test_sandbox_status_values() -> None:
    """SandboxStatus must expose the four expected states."""
    from models import SandboxStatus

    assert set(SandboxStatus) == {"pending", "running", "failed", "terminated"}
