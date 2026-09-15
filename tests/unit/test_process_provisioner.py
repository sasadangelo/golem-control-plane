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
import pytest

_CP_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src", "golem-control-plane"))
if _CP_PATH not in sys.path:
    sys.path.insert(0, _CP_PATH)

# Import after sys.path is set so type annotations resolve correctly.
from domain.models import AgentSpec
from infrastructure.adapters.process_provisioner import ProcessProvisioner

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_spec(agent_id: str = "test-agent", version: str = "0.2.0") -> AgentSpec:
    """Return a minimal AgentSpec with agent.version set."""
    return AgentSpec(
        agent_id=agent_id,
        runner_config=f'agent:\n  id: {agent_id}\n  version: "{version}"\n',
        agents_md="You are a test agent.",
        skills={"hello": "# Hello skill"},
    )


def _make_provisioner(tmp_path: Path, install_mode: str = "copy") -> ProcessProvisioner:
    """Instantiate ProcessProvisioner with all heavy deps mocked.

    ``tmp_path / "runners"`` is used as the base runners directory.
    The provisioner is created via ``__new__`` so ``__init__`` (which checks
    for ``uv``) is bypassed.
    """
    base_path = tmp_path / "runners"
    base_path.mkdir(parents=True, exist_ok=True)

    mock_settings = MagicMock()
    mock_settings.control_plane.runner_path = str(base_path)
    mock_settings.control_plane.runner_install_mode = install_mode

    with (
        patch("infrastructure.adapters.process_provisioner.settings", mock_settings),
        patch("infrastructure.adapters.process_provisioner._check_uv"),
    ):
        prov = ProcessProvisioner.__new__(ProcessProvisioner)
        prov._base_path = base_path
        prov._install_mode = install_mode
        ProcessProvisioner._processes = {}
        return prov


def _make_effective_path(tmp_path: Path, version: str = "0.2.0") -> Path:
    """Create and return the versioned runner source directory."""
    p = tmp_path / "runners" / version / "src" / "golem-runner"
    p.mkdir(parents=True, exist_ok=True)
    return p


# ---------------------------------------------------------------------------
# Tests: create_sandbox — file writing
# ---------------------------------------------------------------------------


def test_create_sandbox_writes_config_yaml(tmp_path: Path) -> None:
    """create_sandbox must write config.yaml into the sandbox directory."""
    _make_effective_path(tmp_path)
    prov = _make_provisioner(tmp_path)
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
    _make_effective_path(tmp_path)
    prov = _make_provisioner(tmp_path)
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
    _make_effective_path(tmp_path)
    prov = _make_provisioner(tmp_path)
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
    _make_effective_path(tmp_path)
    prov = _make_provisioner(tmp_path)
    spec = _make_spec()

    mock_proc = MagicMock()
    mock_proc.pid = 9999

    with (
        patch("infrastructure.adapters.process_provisioner._GOLEM_AGENTS_DIR", tmp_path / "agents"),
        patch("infrastructure.adapters.process_provisioner._find_free_port", return_value=12345),
        patch("subprocess.Popen", return_value=mock_proc) as mock_popen,
    ):
        prov.create_sandbox(spec)

    cmd = mock_popen.call_args[0][0]
    assert cmd[0] == "uv"
    assert "uvicorn" in cmd
    assert "main:app" in cmd
    assert "--port" in cmd
    assert "12345" in cmd


def test_create_sandbox_sets_golem_config_dir_env(tmp_path: Path) -> None:
    """create_sandbox must set GOLEM_CONFIG_DIR in the subprocess environment."""
    _make_effective_path(tmp_path)
    prov = _make_provisioner(tmp_path)
    spec = _make_spec()

    mock_proc = MagicMock()
    mock_proc.pid = 1234

    with (
        patch("infrastructure.adapters.process_provisioner._GOLEM_AGENTS_DIR", tmp_path / "agents"),
        patch("infrastructure.adapters.process_provisioner._find_free_port", return_value=54321),
        patch("subprocess.Popen", return_value=mock_proc) as mock_popen,
    ):
        prov.create_sandbox(spec)

    env = mock_popen.call_args[1]["env"]
    expected_config_dir = str(tmp_path / "agents" / "test-agent")
    assert env.get("GOLEM_CONFIG_DIR") == expected_config_dir


# ---------------------------------------------------------------------------
# Tests: _resolve_runner_path — versioning & install modes
# ---------------------------------------------------------------------------


def test_resolve_runner_path_reuses_existing_directory(tmp_path: Path) -> None:
    """_resolve_runner_path returns existing path without cloning."""
    effective = _make_effective_path(tmp_path, version="0.2.0")
    prov = _make_provisioner(tmp_path, install_mode="copy")

    result = prov._resolve_runner_path("0.2.0")

    assert result == effective


def test_resolve_runner_path_copy_mode_clones_when_missing(tmp_path: Path) -> None:
    """In copy mode, _resolve_runner_path clones the runner when not present."""
    prov = _make_provisioner(tmp_path, install_mode="copy")

    expected = tmp_path / "runners" / "0.2.0" / "src" / "golem-runner"

    with patch(
        "infrastructure.adapters.process_provisioner._clone_runner",
        return_value=expected,
    ) as mock_clone:
        result = prov._resolve_runner_path("0.2.0")

    mock_clone.assert_called_once_with("0.2.0", prov._base_path)
    assert result == expected


def test_resolve_runner_path_editable_mode_raises_when_missing(tmp_path: Path) -> None:
    """In editable mode, _resolve_runner_path raises RuntimeError when dir absent."""
    prov = _make_provisioner(tmp_path, install_mode="editable")

    with pytest.raises(RuntimeError, match="editable"):
        prov._resolve_runner_path("0.2.0")


def test_resolve_runner_path_editable_mode_reuses_existing(tmp_path: Path) -> None:
    """In editable mode, _resolve_runner_path returns the dir when it exists."""
    effective = _make_effective_path(tmp_path, version="0.2.0")
    prov = _make_provisioner(tmp_path, install_mode="editable")

    result = prov._resolve_runner_path("0.2.0")

    assert result == effective


def test_create_sandbox_reads_version_from_agent_config(tmp_path: Path) -> None:
    """create_sandbox must use agent.version from runner_config to select the path."""
    effective = _make_effective_path(tmp_path, version="0.1.0")
    prov = _make_provisioner(tmp_path)
    spec = _make_spec(version="0.1.0")

    mock_proc = MagicMock()
    mock_proc.pid = 1234

    with (
        patch("infrastructure.adapters.process_provisioner._GOLEM_AGENTS_DIR", tmp_path / "agents"),
        patch("infrastructure.adapters.process_provisioner._find_free_port", return_value=54321),
        patch("subprocess.Popen", return_value=mock_proc) as mock_popen,
    ):
        prov.create_sandbox(spec)

    cwd = mock_popen.call_args[1]["cwd"]
    assert cwd == str(effective)


# ---------------------------------------------------------------------------
# Tests: delete_sandbox
# ---------------------------------------------------------------------------


def test_delete_sandbox_terminates_process(tmp_path: Path) -> None:
    """delete_sandbox must call terminate() on the subprocess."""
    from domain.models import SandboxHandle

    prov = _make_provisioner(tmp_path)

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

    prov = _make_provisioner(tmp_path)

    sandbox_dir = tmp_path / "agents" / "test-agent"
    sandbox_dir.mkdir(parents=True)
    (sandbox_dir / "config.yaml").write_text("agent:\n  id: test-agent\n")

    ProcessProvisioner._processes.pop("test-agent", None)
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

    prov = _make_provisioner(tmp_path)

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

    prov = _make_provisioner(tmp_path)

    mock_proc = MagicMock()
    mock_proc.poll.return_value = 1  # exited
    ProcessProvisioner._processes["test-agent"] = mock_proc

    handle = SandboxHandle(agent_id="test-agent", endpoint="http://127.0.0.1:54321")
    result = prov.get_status(handle)

    assert result.status == SandboxStatus.FAILED


def test_get_status_failed_when_health_not_200(tmp_path: Path) -> None:
    """get_status returns FAILED when /health does not return 200."""
    from domain.models import SandboxHandle, SandboxStatus

    prov = _make_provisioner(tmp_path)

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

    prov = _make_provisioner(tmp_path)

    mock_proc = MagicMock()
    mock_proc.poll.return_value = None  # alive
    ProcessProvisioner._processes["test-agent"] = mock_proc

    handle = SandboxHandle(agent_id="test-agent", endpoint="http://127.0.0.1:54321")

    with patch("httpx.get", side_effect=httpx.ConnectError("refused")):
        result = prov.get_status(handle)

    assert result.status == SandboxStatus.FAILED
