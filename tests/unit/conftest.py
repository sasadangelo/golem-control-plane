# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Shared fixtures for Control Plane unit tests.

Inserts the golem-control-plane source path first and stubs all heavy
third-party dependencies (kubernetes, pydantic_settings) before any module import.
"""

import os
import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# 1. Ensure control-plane source is first on sys.path
# ---------------------------------------------------------------------------
_CP_PATH: str = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src", "golem-control-plane"))
if _CP_PATH not in sys.path:
    sys.path.insert(0, _CP_PATH)

# ---------------------------------------------------------------------------
# 2. Stub all heavy dependencies before any control-plane module is imported
# ---------------------------------------------------------------------------
_STUBS: list[str] = [
    "kubernetes",
    "kubernetes.client",
    "kubernetes.client.rest",
    "kubernetes.config",
]
for _name in _STUBS:
    if _name not in sys.modules:
        sys.modules[_name] = MagicMock()  # type: ignore[assignment]

_k8s_config: ModuleType = sys.modules["kubernetes.config"]
_k8s_config.load_incluster_config = MagicMock(side_effect=Exception("not in cluster"))  # type: ignore[attr-defined]
_k8s_config.load_kube_config = MagicMock()  # type: ignore[attr-defined]
_k8s_config.ConfigException = Exception  # type: ignore[attr-defined]

# ---------------------------------------------------------------------------
# 3. Stub core.config so tests never touch config.yaml / .env
# ---------------------------------------------------------------------------
_mock_settings: MagicMock = MagicMock()
_mock_settings.control_plane.gc_interval = 60
_mock_settings.control_plane.runner_image = "localhost/golem-runner:v1"
_mock_settings.llm.api_key = ""
_mock_settings.llm.url = "https://us-south.ml.cloud.ibm.com"
_mock_settings.llm.project_id = ""
_mock_settings.llm.model = "openai/gpt-oss-120b"
_mock_settings.test.provisioner = ""
_mock_settings.test.runner_url = ""

_mock_log: MagicMock = MagicMock()
_mock_log.LoggerManager = MagicMock()
_mock_log.LoggerManager.get_logger = MagicMock(return_value=MagicMock())
_mock_log.setup_logging = MagicMock()

_mock_core_config: MagicMock = MagicMock()
_mock_core_config.settings = _mock_settings
_mock_core: MagicMock = MagicMock()
sys.modules["core"] = _mock_core  # type: ignore[assignment]
sys.modules["core.config"] = _mock_core_config  # type: ignore[assignment]
sys.modules["core.log"] = _mock_log  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# 4. Helpers to reset the hexagonal module tree between tests
# ---------------------------------------------------------------------------

_CONTROL_PLANE_MODULES = (
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
    "core.config",
)


def _reset_modules() -> None:
    for mod in _CONTROL_PLANE_MODULES:
        sys.modules.pop(mod, None)
    sys.modules["core.config"] = _mock_core_config  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# 5. Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_provisioner() -> MagicMock:
    """A fresh MagicMock provisioner for each test."""
    return MagicMock()


@pytest.fixture()
def cp_client(mock_provisioner: MagicMock) -> TestClient:
    """TestClient for the Control Plane app with the provisioner fully mocked."""
    _reset_modules()

    import infrastructure.adapters.k8s_provisioner as k8s_mod

    with patch.object(k8s_mod, "_load_k8s_config"):
        import interfaces.api.app as cp_main

        # Inject mock provisioner and reset sandbox/task stores
        cp_main.provisioner = mock_provisioner  # type: ignore[attr-defined]
        cp_main._sandboxes.clear()  # type: ignore[attr-defined]
        cp_main._tasks.clear()  # type: ignore[attr-defined]
        return TestClient(app=cp_main.app)
