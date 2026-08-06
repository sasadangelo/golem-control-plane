# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Shared fixtures for Control Plane unit tests.

Inserts the golem-control-plane source path first and stubs all heavy
third-party dependencies (kubernetes, dotenv) before any module import.
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# 1. Ensure control-plane source is first on sys.path
# ---------------------------------------------------------------------------
_CP_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src", "golem-control-plane"))
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
    "dotenv",
]
for _name in _STUBS:
    if _name not in sys.modules:
        sys.modules[_name] = MagicMock()  # type: ignore[assignment]

sys.modules["dotenv"].load_dotenv = lambda *a, **kw: None  # type: ignore[attr-defined]

_k8s_config = sys.modules["kubernetes.config"]
_k8s_config.load_incluster_config = MagicMock(side_effect=Exception("not in cluster"))  # type: ignore[attr-defined]
_k8s_config.load_kube_config = MagicMock()  # type: ignore[attr-defined]
_k8s_config.ConfigException = Exception  # type: ignore[attr-defined]


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
    for mod in ("models", "provisioner", "k8s_provisioner", "card_registry", "app"):
        sys.modules.pop(mod, None)

    with patch("k8s_provisioner._load_k8s_config"):
        import app as cp_main  # noqa: PLC0415

        # Inject mock provisioner and reset sandbox store
        cp_main.provisioner = mock_provisioner  # type: ignore[attr-defined]
        cp_main._sandboxes.clear()  # type: ignore[attr-defined]
        return TestClient(cp_main.app)
