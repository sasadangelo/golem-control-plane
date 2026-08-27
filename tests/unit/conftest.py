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
from typing import Any, Self
from unittest.mock import MagicMock, patch

import httpx
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
# 5. Runner HTTP mock — serves tasks from the in-memory _tasks store
# ---------------------------------------------------------------------------


def _make_runner_http_mock(cp_main: Any) -> type:
    """Return a mock httpx.AsyncClient class that serves tasks from _tasks.

    POST /a2a/tasks/send  → create a task in _tasks, return A2ATaskResponse
    GET  /a2a/tasks       → all tasks
    GET  /a2a/tasks/{id}  → single task; 404 if not found
    """
    import uuid as _uuid

    def _resp(status: int, body: object) -> httpx.Response:
        req = httpx.Request("GET", "http://runner-mock/")
        return httpx.Response(status, json=body, request=req)

    class _MockAsyncClient:
        def __init__(self, *_a: object, **_kw: object) -> None:
            pass

        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *_: object) -> None:
            pass

        async def post(self, url: str, *, json: dict | None = None, **_kw: object) -> httpx.Response:
            """Handle POST /a2a/tasks/send — create a task record in _tasks."""
            if "/a2a/tasks/send" not in url:
                return _resp(404, {"detail": "not found"})

            payload = json or {}
            text = ""
            for part in payload.get("message", {}).get("parts", []):
                if part.get("type") == "text" and part.get("text"):
                    text = part["text"]
                    break
            source = payload.get("source", "manual")
            task_id = f"task-{_uuid.uuid4().hex[:12]}"

            # Store in _tasks so the subsequent GET can find it.
            from domain.models import A2ATask  # type: ignore[import]

            task = A2ATask(task_id=task_id, agent_id="mock", message=text, source=source)
            task.status = "completed"  # type: ignore[assignment]
            task.result = "mock result"
            cp_main._tasks[task_id] = task  # type: ignore[attr-defined]

            return _resp(200, {"id": task_id, "status": {"state": "completed"}, "artifacts": []})

        async def get(self, url: str, **_kw: object) -> httpx.Response:
            import json as _json

            tasks_store: dict = cp_main._tasks  # type: ignore[attr-defined]
            if "/a2a/tasks/" in url:
                task_id = url.split("/a2a/tasks/")[-1]
                task = tasks_store.get(task_id)
                if task is None:
                    return _resp(404, {"detail": "not found"})
                return _resp(200, _json.loads(task.model_dump_json()))
            # list all
            all_tasks = [_json.loads(t.model_dump_json()) for t in tasks_store.values()]
            return _resp(200, all_tasks)

    return _MockAsyncClient


# ---------------------------------------------------------------------------
# 6. Fixtures
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

        # Patch httpx.AsyncClient globally for the duration of this test so
        # any GET /a2a/tasks* inside cp_main is served from _tasks in-memory.
        # We patch the httpx module directly (not via cp_main.httpx which no
        # longer exists after the import was removed from app.py).
        import httpx as _httpx

        _orig = _httpx.AsyncClient
        _httpx.AsyncClient = _make_runner_http_mock(cp_main)  # type: ignore[assignment,misc]
        client = TestClient(app=cp_main.app)
        client._httpx_orig = (_httpx, _orig)  # type: ignore[attr-defined]
        return client
