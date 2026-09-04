# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Interfaces API routers — one router module per resource group."""

from .agent_router import make_router as make_agent_router
from .chat_router import make_router as make_chat_router
from .conversation_router import make_router as make_conversation_router
from .task_router import make_router as make_task_router

__all__ = [
    "make_agent_router",
    "make_chat_router",
    "make_conversation_router",
    "make_task_router",
]
