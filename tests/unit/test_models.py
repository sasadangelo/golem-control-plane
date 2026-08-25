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

    for mod in ("domain.models",):
        sys.modules.pop(mod, None)
        importlib.invalidate_caches()


def test_sandbox_handle_auto_generates_agent_id() -> None:
    """SandboxHandle agent_id must be unique when two different ids are used."""
    from domain.models import SandboxHandle

    h1 = SandboxHandle(agent_id="aria-sre-001")
    h2 = SandboxHandle(agent_id="sage-tri-001")
    assert h1.agent_id != h2.agent_id


def test_sandbox_handle_derives_namespace_and_pod_name() -> None:
    """namespace and pod_name must be derived from agent_id automatically."""
    from domain.models import SandboxHandle

    h = SandboxHandle(agent_id="aria-sre-001")
    assert h.namespace == "aria-sre-001"
    assert h.pod_name == "aria-sre-001-runner"


def test_sandbox_handle_explicit_agent_id() -> None:
    """Explicit agent_id must be respected."""
    from domain.models import SandboxHandle

    h = SandboxHandle(agent_id="golem-agent-test")
    assert h.agent_id == "golem-agent-test"
    assert h.namespace == "golem-agent-test"
    assert h.pod_name == "golem-agent-test-runner"


def test_agent_spec_defaults() -> None:
    """AgentSpec must apply sensible defaults."""
    from domain.models import AgentSpec, SandboxMode

    spec = AgentSpec(agent_id="aria-sre-001")
    assert spec.agent_id == "aria-sre-001"
    assert spec.mode == SandboxMode.EPHEMERAL
    assert spec.ttl_seconds == 3600
    assert spec.runner_config == ""


def test_sandbox_status_values() -> None:
    """SandboxStatus must expose the four expected states."""
    from domain.models import SandboxStatus

    assert set(SandboxStatus) == {"pending", "running", "failed", "terminated"}
