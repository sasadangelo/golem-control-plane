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
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# 1. Ensure control-plane source is first on sys.path
# ---------------------------------------------------------------------------
_CP_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src", "golem-control-plane"))
if _CP_PATH not in sys.path:
    sys.path.insert(0, _CP_PATH)

# ---------------------------------------------------------------------------
# 2. Stub all heavy dependencies before any control-plane module is imported
# ---------------------------------------------------------------------------
_STUBS = [
    "kubernetes",
    "kubernetes.client",
    "kubernetes.client.rest",
    "kubernetes.config",
]
for _name in _STUBS:
    if _name not in sys.modules:
        sys.modules[_name] = MagicMock()  # type: ignore[assignment]

_k8s_config = sys.modules["kubernetes.config"]
_k8s_config.load_incluster_config = MagicMock(side_effect=Exception("not in cluster"))  # type: ignore[attr-defined]
_k8s_config.load_kube_config = MagicMock()  # type: ignore[attr-defined]
_k8s_config.ConfigException = Exception  # type: ignore[attr-defined]

# ---------------------------------------------------------------------------
# 3. Stub core.config so tests never touch config.yaml / .env
# ---------------------------------------------------------------------------
_mock_settings = MagicMock()
_mock_settings.control_plane.gc_interval = 60
_mock_settings.control_plane.runner_image = "localhost/golem-runner:v1"
_mock_settings.llm.api_key = ""
_mock_settings.llm.url = "https://us-south.ml.cloud.ibm.com"
_mock_settings.llm.project_id = ""
_mock_settings.llm.model = "openai/gpt-oss-120b"

_mock_core_config = MagicMock()
_mock_core_config.settings = _mock_settings
sys.modules["core"] = MagicMock()  # type: ignore[assignment]
sys.modules["core.config"] = _mock_core_config  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# 3. Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_provisioner() -> MagicMock:
    """A fresh MagicMock provisioner for each test."""
    return MagicMock()


@pytest.fixture()
def cp_client(mock_provisioner: MagicMock) -> TestClient:
    """TestClient for the Control Plane app with the provisioner fully mocked."""
    # Pop cached control-plane modules so each test gets a clean slate
    for mod in ("models", "provisioner", "k8s_provisioner", "card_registry", "app", "core.config"):
        sys.modules.pop(mod, None)
    sys.modules["core.config"] = _mock_core_config  # type: ignore[assignment]

    with patch("k8s_provisioner._load_k8s_config"):
        import app as cp_main  # noqa: PLC0415

        # Inject mock provisioner and reset sandbox store
        cp_main.provisioner = mock_provisioner  # type: ignore[attr-defined]
        cp_main._sandboxes.clear()  # type: ignore[attr-defined]
        return TestClient(cp_main.app)
