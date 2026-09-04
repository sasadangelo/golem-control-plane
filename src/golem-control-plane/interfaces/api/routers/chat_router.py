# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Chat router — WebSocket proxy endpoint."""

from application.services.chat_service import ChatService
from application.services.conversation_service import ConversationService
from fastapi import APIRouter, Query, WebSocket


def make_router(chat_service: ChatService, conversation_service: ConversationService) -> APIRouter:
    """Wire services into the router and return it.

    Args:
        chat_service: The application-layer service for WebSocket proxying.
        conversation_service: Used to validate conversation existence and auto-naming.

    Returns:
        A fully configured APIRouter ready to be included in the FastAPI app.
    """
    router = APIRouter(tags=["chat"])

    @router.websocket(path="/chat/{agent_id}")
    async def chat_proxy(
        websocket: WebSocket,
        agent_id: str,
        conversation_id: str | None = Query(None),
    ) -> None:
        """Proxy WebSocket chat sessions between a client and the agent runner pod."""
        if conversation_id is not None:
            try:
                conversation_service.get_conversation(agent_id, conversation_id)
            except KeyError:
                await websocket.close(
                    code=4404,
                    reason=f"Conversation {conversation_id} not found for agent {agent_id}.",
                )
                return

        async def _auto_name(aid: str, cid: str, message: str) -> None:
            conversation_service.auto_name_if_needed(aid, cid, message)

        await chat_service.proxy(
            websocket=websocket,
            agent_id=agent_id,
            conversation_id=conversation_id,
            auto_name_callback=_auto_name,
        )

    return router
