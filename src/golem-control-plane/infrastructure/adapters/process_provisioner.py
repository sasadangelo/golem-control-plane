# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""ProcessProvisioner — personal assistant mode (no containers, no Kubernetes).

Launches each agent runner as a local subprocess via ``uv run uvicorn main:app``.
Sandbox files (config.yaml, AGENTS.md, skills) are written to
``~/.golem/agents/<agent_id>/`` and passed to the runner via the
``GOLEM_CONFIG_DIR`` environment variable — the runner source directory is
never written to at runtime.

The runner version is read from ``agent.version`` inside the agent's
``config.yaml``.  The effective source directory is resolved as::

    runner_path / agent_version / "src" / "golem-runner"

Two install modes are supported (``control-plane.runner_install_mode`` in the
CP ``config.yaml``):

* **copy** (default) — the versioned directory is created by cloning the
  release from GitHub if it does not already exist.
* **editable** — the versioned directory must already exist (e.g. a manual
  ``git clone`` or a symlink to the local working tree).  Nothing is
  downloaded; changes to the source are picked up on the next subprocess
  start.

Enable via the Control Plane ``config.yaml``:

    control-plane:
      provisioner: process
      runner_path: ~/.golem/runners        # base dir for all runner versions
      runner_install_mode: copy            # copy (default) | editable
"""

import os
import shlex
import shutil
import socket
import subprocess  # nosec B404
from pathlib import Path
from subprocess import Popen  # nosec B404
from typing import ClassVar

import httpx
import yaml
from httpx._models import Response

from core.config import settings
from core.log import LoggerManager
from domain.models import AgentSpec, SandboxHandle, SandboxStatus
from domain.ports.provisioner import Provisioner

logger = LoggerManager.get_logger(name="ProcessProvisioner")

# Base directory under which each agent's sandbox files are written.
_GOLEM_AGENTS_DIR: Path = Path.home() / ".golem" / "agents"

# Default runner version when not specified in the agent config.
_DEFAULT_RUNNER_VERSION: str = "0.2.0"

# GitHub repository used to clone runner releases on demand (copy mode only).
_RUNNER_REPO: str = "https://github.com/sasadangelo/golem-runner"


def _find_free_port() -> int:
    """Bind to port 0 and let the OS assign a free ephemeral port."""
    with socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _check_uv() -> None:
    """Raise RuntimeError if ``uv`` is not found in PATH."""
    if shutil.which("uv") is None:
        raise RuntimeError("'uv' not found in PATH. Install it from https://docs.astral.sh/uv/ and re-run.")


def _check_git() -> None:
    """Raise RuntimeError if ``git`` is not found in PATH."""
    if shutil.which("git") is None:
        raise RuntimeError("'git' not found in PATH. Install Git or place the runner manually at the expected path.")


def _clone_runner(version: str, base_path: Path) -> Path:
    """Clone the runner release tag into ``base_path / version``.

    Args:
        version: Git tag to clone (e.g. ``"0.2.0"``); the tag on GitHub is
            prefixed with ``v`` (``v0.2.0``).
        base_path: Base directory for all runner versions.

    Returns:
        The effective runner source path
        ``base_path / version / "src" / "golem-runner"``.

    Raises:
        RuntimeError: If ``git`` is not available or the clone fails.
    """
    _check_git()
    target = base_path / version
    target.mkdir(parents=True, exist_ok=True)
    tag = f"v{version}"
    logger.info(f"Cloning runner {tag} into {target} …")
    result = subprocess.run(  # nosec B603 B607
        ["git", "clone", "--depth", "1", "--branch", tag, _RUNNER_REPO, str(target)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to clone runner {tag} from {_RUNNER_REPO}:\n{result.stderr}")
    effective = target / "src" / "golem-runner"
    if not effective.is_dir():
        raise RuntimeError(f"Runner cloned to {target} but expected source dir not found: {effective}")
    logger.info(f"Runner {tag} installed at {effective}")
    return effective


class ProcessProvisioner(Provisioner):
    """Provisions agent runners as local subprocesses.

    Layout
    ------
    ``settings.control_plane.runner_path`` is the **base directory** for all
    runner versions (e.g. ``~/.golem/runners``).  Each agent's
    ``config.yaml`` carries ``agent.version`` which selects the versioned
    subdirectory::

        runner_path / agent_version / src / golem-runner

    In **copy** mode (default) the directory is created by cloning the
    matching GitHub release tag if it does not yet exist.

    In **editable** mode the directory must already exist — typically a
    ``git clone`` of the working tree.  No download is attempted; changes
    to the source are picked up on the next subprocess start, making this
    ideal for runner development.

    Each sandbox writes its workspace files to
    ``~/.golem/agents/<agent_id>/`` and passes ``GOLEM_CONFIG_DIR`` pointing
    there to the subprocess.  The runner source directory is **never** written
    to at runtime.

    Stdout and stderr of each subprocess are redirected to
    ``~/.golem/agents/<agent_id>/runner.log``.

    ``get_status`` returns ``RUNNING`` only when the subprocess is alive
    **and** ``GET /health`` responds with HTTP 200.
    """

    # In-memory map of agent_id → Popen handle.  Survives across calls within
    # the same process lifetime; lost on CP restart (acceptable for MVP).
    _processes: ClassVar[dict[str, Popen]] = {}  # type: ignore[type-arg]

    def __init__(self) -> None:
        _check_uv()
        runner_path = settings.control_plane.runner_path
        if not runner_path:
            raise RuntimeError(
                "control-plane.runner_path must be set when using ProcessProvisioner. "
                "Add it to config.yaml (e.g. runner_path: ~/.golem/runners)."
            )
        self._base_path = Path(runner_path).expanduser()
        self._base_path.mkdir(parents=True, exist_ok=True)
        self._install_mode: str = settings.control_plane.runner_install_mode

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def create_sandbox(self, spec: AgentSpec) -> SandboxHandle:
        """Write sandbox files and launch the runner subprocess.

        Reads ``agent.version`` from the agent's ``runner_config`` YAML to
        select the runner version; falls back to ``_DEFAULT_RUNNER_VERSION``
        when absent.  In copy mode the versioned directory is cloned from
        GitHub on demand; in editable mode the directory must already exist.

        Args:
            spec: Agent specification carrying config, AGENTS.md, and skills.

        Returns:
            A SandboxHandle with status PENDING and endpoint set to
            ``http://127.0.0.1:<port>``.

        Raises:
            RuntimeError: If the subprocess cannot be started or the runner
                directory is missing in editable mode.
        """
        sandbox_dir: Path = _GOLEM_AGENTS_DIR / spec.agent_id
        sandbox_dir.mkdir(parents=True, exist_ok=True)

        # Write runner config.yaml.
        (sandbox_dir / "config.yaml").write_text(spec.runner_config, encoding="utf-8")

        # Write optional AGENTS.md.
        if spec.agents_md is not None:
            (sandbox_dir / "AGENTS.md").write_text(spec.agents_md, encoding="utf-8")

        # Write skill files under skills/.
        if spec.skills:
            skills_dir: Path = sandbox_dir / "skills"
            skills_dir.mkdir(exist_ok=True)
            for skill_name, skill_content in spec.skills.items():
                (skills_dir / f"{skill_name}.md").write_text(skill_content, encoding="utf-8")

        # Resolve agent.version from runner config; fall back to default.
        version = _DEFAULT_RUNNER_VERSION
        try:
            cfg = yaml.safe_load(spec.runner_config) or {}
            version = cfg.get("agent", {}).get("version", _DEFAULT_RUNNER_VERSION)
        except yaml.YAMLError:
            pass

        effective_path = self._resolve_runner_path(version)

        port: int = _find_free_port()
        log_file: Path = sandbox_dir / "runner.log"

        cmd: list[str] = [
            "uv",
            "run",
            "uvicorn",
            "main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ]
        logger.info(
            f"Launching runner {version} ({self._install_mode}) for agent "
            f"'{spec.agent_id}' on port {port}: {shlex.join(cmd)}"
        )

        with log_file.open("w", encoding="utf-8") as log_fh:
            proc: Popen[bytes] = subprocess.Popen(  # nosec B603
                cmd,
                cwd=str(effective_path),
                env=self._build_env(sandbox_dir),
                stdout=log_fh,
                stderr=log_fh,
            )

        self._processes[spec.agent_id] = proc
        handle = SandboxHandle(
            agent_id=spec.agent_id,
            endpoint=f"http://127.0.0.1:{port}",
            ttl_seconds=spec.ttl_seconds,
        )
        logger.info(f"Runner process started (pid={proc.pid}) for agent '{spec.agent_id}'")
        return handle

    def delete_sandbox(self, handle: SandboxHandle) -> None:
        """Terminate the subprocess and remove sandbox files.

        Args:
            handle: The SandboxHandle returned by create_sandbox.
        """
        proc = self._processes.pop(handle.agent_id, None)
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            logger.info(f"Runner process terminated for agent '{handle.agent_id}' (pid={proc.pid})")

        sandbox_dir: Path = _GOLEM_AGENTS_DIR / handle.agent_id
        if sandbox_dir.exists():
            shutil.rmtree(sandbox_dir)
            logger.info(f"Sandbox directory removed: {sandbox_dir}")

    def get_status(self, handle: SandboxHandle) -> SandboxHandle:
        """Check subprocess liveness and /health endpoint.

        Args:
            handle: The SandboxHandle to inspect.

        Returns:
            Updated handle: RUNNING if subprocess alive and /health → 200,
            FAILED otherwise.
        """
        proc = self._processes.get(handle.agent_id)
        if proc is None or proc.poll() is not None:
            handle.status = SandboxStatus.FAILED
            return handle

        if not handle.endpoint:
            handle.status = SandboxStatus.FAILED
            return handle

        try:
            response: Response = httpx.get(url=f"{handle.endpoint}/health", timeout=3.0)
            handle.status = SandboxStatus.RUNNING if response.status_code == 200 else SandboxStatus.FAILED
        except (OSError, httpx.HTTPError):
            handle.status = SandboxStatus.FAILED

        return handle

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _resolve_runner_path(self, version: str) -> Path:
        """Return the effective runner source path for ``version``.

        In **copy** mode: clones the release from GitHub if the versioned
        directory does not exist yet.

        In **editable** mode: expects the directory to already exist; raises
        a clear error if it does not (no download attempted).

        Args:
            version: Runner version (e.g. ``"0.2.0"``).

        Returns:
            Path to ``runner_path / version / "src" / "golem-runner"``.

        Raises:
            RuntimeError: In editable mode when the directory is missing.
        """
        effective = self._base_path / version / "src" / "golem-runner"

        if effective.is_dir():
            return effective

        if self._install_mode == "editable":
            raise RuntimeError(
                f"runner_install_mode=editable but runner directory not found: {effective}\n"
                f"Create it manually, e.g.:\n"
                f"  git clone https://github.com/sasadangelo/golem-runner "
                f"{self._base_path / version}"
            )

        # copy mode — clone from GitHub on demand.
        return _clone_runner(version, self._base_path)

    def _build_env(self, sandbox_dir: Path) -> dict[str, str]:
        """Build the subprocess environment.

        Sets ``GOLEM_CONFIG_DIR`` to the sandbox directory so the runner
        reads its workspace (config.yaml, AGENTS.md, skills/) from there.
        The runner source directory is never written to.

        Args:
            sandbox_dir: Path to the agent's sandbox directory
                (``~/.golem/agents/<agent_id>/``).

        Returns:
            A dict suitable for ``subprocess.Popen(env=...)``.
        """
        env = os.environ.copy()
        env["GOLEM_CONFIG_DIR"] = str(sandbox_dir)
        return env
