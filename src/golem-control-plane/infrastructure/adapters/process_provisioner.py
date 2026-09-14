# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""ProcessProvisioner — personal assistant mode (no containers, no Kubernetes).

Launches each agent runner as a local subprocess via ``uv run python main.py``.
Sandbox files (config.yaml, AGENTS.md, skills) are written to
``~/.golem/agents/<agent_id>/`` before the process starts.

Enable via ``config.yaml``:

    control-plane:
      provisioner: process
      runner_path: /absolute/path/to/golem-runner/src/golem-runner
"""

import shlex
import shutil
import socket
import subprocess  # nosec B404
from pathlib import Path
from subprocess import Popen  # nosec B404
from typing import ClassVar

import httpx
from httpx._models import Response

from core.config import settings
from core.log import LoggerManager
from domain.models import AgentSpec, SandboxHandle, SandboxStatus
from domain.ports.provisioner import Provisioner

logger = LoggerManager.get_logger(name="ProcessProvisioner")

# Base directory under which each agent's sandbox files are written.
_GOLEM_AGENTS_DIR: Path = Path.home() / ".golem" / "agents"


def _find_free_port() -> int:
    """Bind to port 0 and let the OS assign a free ephemeral port."""
    with socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _check_uv() -> None:
    """Raise RuntimeError if ``uv`` is not found in PATH."""
    if shutil.which("uv") is None:
        raise RuntimeError("'uv' not found in PATH. Install it from https://docs.astral.sh/uv/ and re-run.")


class ProcessProvisioner(Provisioner):
    """Provisions agent runners as local subprocesses.

    Each sandbox is a directory ``~/.golem/agents/<agent_id>/`` that contains
    the runner's ``config.yaml``, an optional ``AGENTS.md``, and any skill
    files under ``skills/``.  The runner is started with
    ``uv run python main.py`` from ``settings.control_plane.runner_path``.

    The subprocess's stdout and stderr are redirected to
    ``~/.golem/agents/<agent_id>/runner.log`` so they do not pollute the
    control-plane terminal.

    ``get_status`` returns ``RUNNING`` only when the subprocess is alive
    **and** ``GET /health`` responds with HTTP 200.
    """

    # In-memory map of agent_id → Popen handle.  Survives across calls within
    # the same process lifetime; lost on CP restart (acceptable for MVP).
    _processes: ClassVar[dict[str, subprocess.Popen]] = {}  # type: ignore[type-arg]

    def __init__(self) -> None:
        _check_uv()
        runner_path = settings.control_plane.runner_path
        if not runner_path:
            raise RuntimeError(
                "control-plane.runner_path must be set when using ProcessProvisioner. Add it to config.yaml."
            )
        self._runner_path = Path(runner_path)
        if not self._runner_path.is_dir():
            raise RuntimeError(f"runner_path '{self._runner_path}' does not exist or is not a directory.")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def create_sandbox(self, spec: AgentSpec) -> SandboxHandle:
        """Write sandbox files and launch the runner subprocess.

        Args:
            spec: Agent specification carrying config, AGENTS.md, and skills.

        Returns:
            A SandboxHandle with status PENDING and endpoint set to
            ``http://localhost:<port>``.

        Raises:
            RuntimeError: If the subprocess cannot be started.
        """
        sandbox_dir: Path = _GOLEM_AGENTS_DIR / spec.agent_id
        sandbox_dir.mkdir(parents=True, exist_ok=True)

        # Write runner config.yaml.
        (sandbox_dir / "config.yaml").write_text(spec.runner_config, encoding="utf-8")

        # Write optional AGENTS.md.
        if spec.agents_md is not None:
            (sandbox_dir / "AGENTS.md").write_text(data=spec.agents_md, encoding="utf-8")

        # Write skill files under skills/.
        if spec.skills:
            skills_dir: Path = sandbox_dir / "skills"
            skills_dir.mkdir(exist_ok=True)
            for skill_name, skill_content in spec.skills.items():
                (skills_dir / f"{skill_name}.md").write_text(data=skill_content, encoding="utf-8")

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
        logger.info(f"Launching runner for agent '{spec.agent_id}' on port {port}: {shlex.join(cmd)}")

        with log_file.open("w", encoding="utf-8") as log_fh:
            proc: Popen[bytes] = subprocess.Popen(  # nosec B603
                cmd,
                cwd=str(self._runner_path),
                env=self._build_env(sandbox_dir),
                stdout=log_fh,
                stderr=log_fh,
            )

        self._processes[spec.agent_id] = proc
        handle: SandboxHandle = SandboxHandle(
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
            Updated handle with status RUNNING if the subprocess is alive and
            /health returns 200, otherwise FAILED.
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
            if response.status_code == 200:
                handle.status = SandboxStatus.RUNNING
            else:
                handle.status = SandboxStatus.FAILED
        except (OSError, httpx.HTTPError):
            handle.status = SandboxStatus.FAILED

        return handle

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_env(self, sandbox_dir: Path) -> dict[str, str]:
        """Build the subprocess environment.

        Merges the current process environment with overrides that point the
        runner at the sandbox-specific config.yaml.

        Args:
            sandbox_dir: Path to the agent's sandbox directory.

        Returns:
            A dict suitable for ``subprocess.Popen(env=...)``.
        """
        import os

        env: dict[str, str] = os.environ.copy()
        # Tell the runner to load config from the sandbox directory instead of
        # its own source tree.  The runner's Settings reads config.yaml from
        # Path(__file__).parent.parent / "config.yaml" by default; overriding
        # the working directory is not sufficient because config resolution is
        # relative to the source file.  We pass the path via an env var that
        # the runner can honour (future work); for now the runner reads from
        # its own directory and we symlink/copy config.yaml there.
        #
        # Simpler approach for MVP: the runner reads config.yaml from CWD when
        # the env var GOLEM_CONFIG_PATH is set — but the runner does not support
        # that yet.  Instead we rely on the fact that `uv run` sets CWD to
        # self._runner_path, and we write config.yaml directly into
        # self._runner_path before launch, overwriting it per agent launch.
        #
        # TODO: teach the runner to honour GOLEM_CONFIG_PATH so multiple
        # process-mode agents can run concurrently without clobbering each other.
        config_src: Path = sandbox_dir / "config.yaml"
        config_dst: Path = self._runner_path / "config.yaml"
        shutil.copy2(str(config_src), str(config_dst))

        agents_src: Path = sandbox_dir / "AGENTS.md"
        if agents_src.exists():
            shutil.copy2(str(agents_src), str(self._runner_path / "AGENTS.md"))

        skills_src: Path = sandbox_dir / "skills"
        if skills_src.is_dir():
            skills_dst: Path = self._runner_path / "skills"
            if skills_dst.exists():
                shutil.rmtree(skills_dst)
            shutil.copytree(src=str(skills_src), dst=str(skills_dst))

        return env
