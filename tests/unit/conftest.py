# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Shared pytest fixtures for unit tests.

Mocks all heavy third-party modules (langchain_ibm, langchain_core LLM classes,
langgraph) before any source module is imported, so tests run without credentials
and without installing the full golem-runner dependency tree.
"""

import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


def _install_module_mocks() -> None:
    """Inject lightweight stubs into sys.modules for all runner dependencies."""
    stubs = [
        "langchain_ibm",
        "langgraph",
        "langgraph.graph",
        "langgraph.graph.message",
        "langgraph.prebuilt",
        "dotenv",
    ]
    for name in stubs:
        if name not in sys.modules:
            sys.modules[name] = MagicMock()  # type: ignore[assignment]

    # dotenv.load_dotenv must be a no-op callable
    sys.modules["dotenv"].load_dotenv = lambda *a, **kw: None  # type: ignore[attr-defined]

    # langgraph.graph must expose END and StateGraph
    lg_graph = sys.modules["langgraph.graph"]
    lg_graph.END = "END"  # type: ignore[attr-defined]
    lg_graph.StateGraph = MagicMock()  # type: ignore[attr-defined]

    # langgraph.graph.message must expose add_messages
    sys.modules["langgraph.graph.message"].add_messages = MagicMock()  # type: ignore[attr-defined]

    # langgraph.prebuilt must expose ToolNode
    sys.modules["langgraph.prebuilt"].ToolNode = MagicMock()  # type: ignore[attr-defined]


_install_module_mocks()


@pytest.fixture()
def client() -> TestClient:
    """FastAPI TestClient with agent_executor replaced by a no-op mock."""
    # Ensure a fresh import of main for each fixture use
    for mod in ("agent", "main"):
        sys.modules.pop(mod, None)

    with patch("agent.build_agent", return_value=MagicMock()):
        import main as m

        return TestClient(m.app)
