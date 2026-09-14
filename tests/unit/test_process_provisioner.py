# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Unit tests for ProcessProvisioner."""

# ---------------------------------------------------------------------------
# Ensure the control-plane source is importable (mirrors conftest.py)
# ---------------------------------------------------------------------------
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx

_CP_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src", "golem-control-plane"))
if _CP_PATH not in sys.path:
    sys.path.insert(0, _CP_PATH)

# Import after sys.path is set so type annotations resolve correctly.
from domain.models import AgentSpec
from infrastructure.adapters.process_provisioner import ProcessProvisioner

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_spec(agent_id: str = "test-agent") -> AgentSpec:
    """Return a minimal AgentSpec."""
    return AgentSpec(
        agent_id=agent_id,
        runner_config="agent:\n  id: test-agent\n",
        agents_md="You are a test agent.",
        skills={"hello": "# Hello skill"},
    )


def _make_provisioner(tmp_path: Path, runner_path: Path) -> ProcessProvisioner:
    """Instantiate ProcessProvisioner with all heavy deps mocked."""
    mock_settings = MagicMock()
    mock_settings.control_plane.runner_path = str(runner_path)

    with (
        patch("infrastructure.adapters.process_provisioner.settings", mock_settings),
        patch("infrastructure.adapters.process_provisioner._check_uv"),
        patch("infrastructure.adapters.process_provisioner._GOLEM_AGENTS_DIR", tmp_path / "agents"),
    ):
        prov = ProcessProvisioner.__new__(ProcessProvisioner)
        prov._runner_path = runner_path
        # Reset class-level process map so tests are isolated.
        ProcessProvisioner._processes = {}
        return prov


# ---------------------------------------------------------------------------
# Tests: create_sandbox
# ---------------------------------------------------------------------------


def test_create_sandbox_writes_config_yaml(tmp_path: Path) -> None:
    """create_sandbox must write config.yaml into the sandbox directory."""
    runner_path = tmp_path / "runner"
    runner_path.mkdir()
    prov = _make_provisioner(tmp_path, runner_path)
    spec = _make_spec()

    mock_proc = MagicMock()
    mock_proc.pid = 1234

    with (
        patch("infrastructure.adapters.process_provisioner._GOLEM_AGENTS_DIR", tmp_path / "agents"),
        patch("infrastructure.adapters.process_provisioner._find_free_port", return_value=54321),
        patch("subprocess.Popen", return_value=mock_proc),
    ):
        handle = prov.create_sandbox(spec)

    config_file = tmp_path / "agents" / "test-agent" / "config.yaml"
    assert config_file.exists()
    assert "test-agent" in config_file.read_text()
    assert handle.endpoint == "http://127.0.0.1:54321"


def test_create_sandbox_writes_agents_md(tmp_path: Path) -> None:
    """create_sandbox must write AGENTS.md when provided in spec."""
    runner_path = tmp_path / "runner"
    runner_path.mkdir()
    prov = _make_provisioner(tmp_path, runner_path)
    spec = _make_spec()

    mock_proc = MagicMock()
    mock_proc.pid = 1234

    with (
        patch("infrastructure.adapters.process_provisioner._GOLEM_AGENTS_DIR", tmp_path / "agents"),
        patch("infrastructure.adapters.process_provisioner._find_free_port", return_value=54321),
        patch("subprocess.Popen", return_value=mock_proc),
    ):
        prov.create_sandbox(spec)

    agents_md = tmp_path / "agents" / "test-agent" / "AGENTS.md"
    assert agents_md.exists()
    assert "test agent" in agents_md.read_text()


def test_create_sandbox_writes_skill_files(tmp_path: Path) -> None:
    """create_sandbox must write each skill into skills/<name>.md."""
    runner_path = tmp_path / "runner"
    runner_path.mkdir()
    prov = _make_provisioner(tmp_path, runner_path)
    spec = _make_spec()

    mock_proc = MagicMock()
    mock_proc.pid = 1234

    with (
        patch("infrastructure.adapters.process_provisioner._GOLEM_AGENTS_DIR", tmp_path / "agents"),
        patch("infrastructure.adapters.process_provisioner._find_free_port", return_value=54321),
        patch("subprocess.Popen", return_value=mock_proc),
    ):
        prov.create_sandbox(spec)

    skill_file = tmp_path / "agents" / "test-agent" / "skills" / "hello.md"
    assert skill_file.exists()
    assert "Hello skill" in skill_file.read_text()


def test_create_sandbox_launches_subprocess(tmp_path: Path) -> None:
    """create_sandbox must launch uv run uvicorn main:app with the correct port."""
    runner_path = tmp_path / "runner"
    runner_path.mkdir()
    prov = _make_provisioner(tmp_path, runner_path)
    spec = _make_spec()

    mock_proc = MagicMock()
    mock_proc.pid = 9999

    with (
        patch("infrastructure.adapters.process_provisioner._GOLEM_AGENTS_DIR", tmp_path / "agents"),
        patch("infrastructure.adapters.process_provisioner._find_free_port", return_value=12345),
        patch("subprocess.Popen", return_value=mock_proc) as mock_popen,
    ):
        prov.create_sandbox(spec)

    call_args = mock_popen.call_args
    cmd = call_args[0][0]
    assert cmd[0] == "uv"
    assert "uvicorn" in cmd
    assert "main:app" in cmd
    assert "--port" in cmd
    assert "12345" in cmd


# ---------------------------------------------------------------------------
# Tests: delete_sandbox
# ---------------------------------------------------------------------------


def test_delete_sandbox_terminates_process(tmp_path: Path) -> None:
    """delete_sandbox must call terminate() on the subprocess."""
    from domain.models import SandboxHandle

    runner_path = tmp_path / "runner"
    runner_path.mkdir()
    prov = _make_provisioner(tmp_path, runner_path)

    mock_proc = MagicMock()
    mock_proc.poll.return_value = None  # still running

    ProcessProvisioner._processes["test-agent"] = mock_proc
    handle = SandboxHandle(agent_id="test-agent", endpoint="http://127.0.0.1:54321")

    with patch("infrastructure.adapters.process_provisioner._GOLEM_AGENTS_DIR", tmp_path / "agents"):
        prov.delete_sandbox(handle)

    mock_proc.terminate.assert_called_once()


def test_delete_sandbox_removes_directory(tmp_path: Path) -> None:
    """delete_sandbox must remove the sandbox directory from disk."""
    from domain.models import SandboxHandle

    runner_path = tmp_path / "runner"
    runner_path.mkdir()
    prov = _make_provisioner(tmp_path, runner_path)

    sandbox_dir = tmp_path / "agents" / "test-agent"
    sandbox_dir.mkdir(parents=True)
    (sandbox_dir / "config.yaml").write_text("agent:\n  id: test-agent\n")

    ProcessProvisioner._processes.pop("test-agent", None)  # no process
    handle = SandboxHandle(agent_id="test-agent", endpoint="http://127.0.0.1:54321")

    with patch("infrastructure.adapters.process_provisioner._GOLEM_AGENTS_DIR", tmp_path / "agents"):
        prov.delete_sandbox(handle)

    assert not sandbox_dir.exists()


# ---------------------------------------------------------------------------
# Tests: get_status
# ---------------------------------------------------------------------------


def test_get_status_running_when_process_alive_and_health_ok(tmp_path: Path) -> None:
    """get_status returns RUNNING when subprocess is alive and /health → 200."""
    from domain.models import SandboxHandle, SandboxStatus

    runner_path = tmp_path / "runner"
    runner_path.mkdir()
    prov = _make_provisioner(tmp_path, runner_path)

    mock_proc = MagicMock()
    mock_proc.poll.return_value = None  # alive
    ProcessProvisioner._processes["test-agent"] = mock_proc

    handle = SandboxHandle(agent_id="test-agent", endpoint="http://127.0.0.1:54321")

    mock_response = MagicMock()
    mock_response.status_code = 200

    with patch("httpx.get", return_value=mock_response):
        result = prov.get_status(handle)

    assert result.status == SandboxStatus.RUNNING


def test_get_status_failed_when_process_dead(tmp_path: Path) -> None:
    """get_status returns FAILED when the subprocess has exited."""
    from domain.models import SandboxHandle, SandboxStatus

    runner_path = tmp_path / "runner"
    runner_path.mkdir()
    prov = _make_provisioner(tmp_path, runner_path)

    mock_proc = MagicMock()
    mock_proc.poll.return_value = 1  # exited with code 1
    ProcessProvisioner._processes["test-agent"] = mock_proc

    handle = SandboxHandle(agent_id="test-agent", endpoint="http://127.0.0.1:54321")
    result = prov.get_status(handle)

    assert result.status == SandboxStatus.FAILED


def test_get_status_failed_when_health_not_200(tmp_path: Path) -> None:
    """get_status returns FAILED when /health does not return 200."""
    from domain.models import SandboxHandle, SandboxStatus

    runner_path = tmp_path / "runner"
    runner_path.mkdir()
    prov = _make_provisioner(tmp_path, runner_path)

    mock_proc = MagicMock()
    mock_proc.poll.return_value = None  # alive
    ProcessProvisioner._processes["test-agent"] = mock_proc

    handle = SandboxHandle(agent_id="test-agent", endpoint="http://127.0.0.1:54321")

    mock_response = MagicMock()
    mock_response.status_code = 503

    with patch("httpx.get", return_value=mock_response):
        result = prov.get_status(handle)

    assert result.status == SandboxStatus.FAILED


def test_get_status_failed_when_health_raises(tmp_path: Path) -> None:
    """get_status returns FAILED when /health raises a network error."""
    from domain.models import SandboxHandle, SandboxStatus

    runner_path = tmp_path / "runner"
    runner_path.mkdir()
    prov = _make_provisioner(tmp_path, runner_path)

    mock_proc = MagicMock()
    mock_proc.poll.return_value = None  # alive
    ProcessProvisioner._processes["test-agent"] = mock_proc

    handle = SandboxHandle(agent_id="test-agent", endpoint="http://127.0.0.1:54321")

    with patch("httpx.get", side_effect=httpx.ConnectError("refused")):
        result = prov.get_status(handle)

    assert result.status == SandboxStatus.FAILED
