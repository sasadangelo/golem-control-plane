# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Golem Agent Runner — FastAPI application exposing A2A and chat endpoints."""

import os
import uuid
from typing import Any

from agent import agent_executor
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

app = FastAPI(title="Golem Agent Runner", version="0.1.0")

# ---------------------------------------------------------------------------
# A2A Agent Card — served at /.well-known/agent.json (A2A v1.0 spec)
# ---------------------------------------------------------------------------

AGENT_ID = os.getenv("AGENT_ID", f"golem-agent-{uuid.uuid4().hex[:8]}")
AGENT_NAME = os.getenv("AGENT_NAME", "Golem Agent Runner")
AGENT_DESCRIPTION = os.getenv("AGENT_DESCRIPTION", "Generic automation agent powered by Golem.")
AGENT_ENDPOINT = os.getenv("AGENT_ENDPOINT", "http://localhost:8000")

_enabled_skills = [s.strip() for s in os.getenv("ENABLED_SKILLS", "").split(",") if s.strip()]

AGENT_CARD: dict[str, Any] = {
    "id": AGENT_ID,
    "name": AGENT_NAME,
    "description": AGENT_DESCRIPTION,
    "version": "0.1.0",
    "endpoint": AGENT_ENDPOINT,
    "capabilities": {
        "streaming": False,
        "pushNotifications": False,
    },
    "skills": [{"id": skill, "name": skill} for skill in _enabled_skills],
}


# Starlette blocks paths with dot-prefixed segments (e.g. /.well-known/) via its
# routing internals, so we intercept the request with a middleware before routing.
@app.middleware("http")
async def well_known_middleware(request: Request, call_next: Any) -> Response:
    """Serve /.well-known/agent.json before Starlette routing drops the request."""
    if request.url.path == "/.well-known/agent.json":
        return JSONResponse(content=AGENT_CARD)
    return await call_next(request)


# ---------------------------------------------------------------------------
# A2A inbound task endpoint  (A2A v1.0 — tasks/send)
# ---------------------------------------------------------------------------


class A2AMessage(BaseModel):
    role: str
    parts: list[dict[str, Any]]


class A2ASendParams(BaseModel):
    id: str | None = None
    message: A2AMessage


class A2ATaskResult(BaseModel):
    id: str
    status: dict[str, Any]
    artifacts: list[dict[str, Any]]


@app.post("/a2a/tasks/send", response_model=A2ATaskResult)
async def a2a_tasks_send(params: A2ASendParams):
    """
    A2A inbound task reception.
    Accepts a task delegated by a peer agent, runs it through the LangGraph loop,
    and returns a completed artifact.
    """
    task_id = params.id or uuid.uuid4().hex

    # Extract text from the first text part of the message
    text = ""
    for part in params.message.parts:
        if part.get("type") == "text":
            text = part.get("text", "")
            break

    if not text:
        raise HTTPException(status_code=400, detail="No text part found in A2A message.")

    try:
        inputs = {"messages": [HumanMessage(content=text)]}
        result = agent_executor.invoke(inputs)
        reply = str(result["messages"][-1].content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return A2ATaskResult(
        id=task_id,
        status={"state": "completed"},
        artifacts=[{"parts": [{"type": "text", "text": reply}]}],
    )


# ---------------------------------------------------------------------------
# Chat endpoint (human-facing)
# ---------------------------------------------------------------------------


class ChatPayload(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str


@app.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatPayload):
    try:
        inputs = {"messages": [HumanMessage(content=payload.message)]}
        result = agent_executor.invoke(inputs)
        last_message = result["messages"][-1]
        return ChatResponse(reply=str(last_message.content))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/health")
async def health():
    return {"status": "ok"}
