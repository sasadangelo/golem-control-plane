# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Conversation router — HTTP endpoints for conversation management."""

from application.services.chat_service import ChatService
from application.services.conversation_service import ConversationService
from fastapi import APIRouter, HTTPException, Query

from interfaces.api.schemas import ConversationResponse, CreateConversationRequest


def make_router(conversation_service: ConversationService, chat_service: ChatService) -> APIRouter:
    """Wire services into the router and return it.

    Args:
        conversation_service: The application-layer service for conversation business logic.
        chat_service: Used to check and force-close active WebSocket connections.

    Returns:
        A fully configured APIRouter ready to be included in the FastAPI app.
    """
    router = APIRouter(tags=["conversations"])

    @router.post(path="/agents/{agent_id}/conversations", response_model=ConversationResponse, status_code=201)
    async def create_conversation(agent_id: str, body: CreateConversationRequest) -> ConversationResponse:
        """Create a new isolated conversation for an agent."""
        try:
            conv = conversation_service.create_conversation(agent_id=agent_id, name=body.name)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found.")

        return ConversationResponse(
            conversation_id=conv.conversation_id,
            agent_id=conv.agent_id,
            name=conv.name,
            is_active=False,
            created_at=conv.created_at,
        )

    @router.get(path="/agents/{agent_id}/conversations", response_model=list[ConversationResponse])
    async def list_conversations(agent_id: str) -> list[ConversationResponse]:
        """List all conversations for an agent."""
        try:
            items = conversation_service.list_conversations(
                agent_id=agent_id,
                active_ids=chat_service.active_connection_keys,
            )
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found.")

        return [
            ConversationResponse(
                conversation_id=c.conversation_id,
                agent_id=c.agent_id,
                name=c.name,
                is_active=is_active,
                created_at=c.created_at,
            )
            for c, is_active in items
        ]

    @router.delete(path="/agents/{agent_id}/conversations/{conversation_id}", status_code=204)
    async def delete_conversation(
        agent_id: str,
        conversation_id: str,
        force: bool = Query(False),
    ) -> None:
        """Delete a conversation, optionally force-disconnecting active WebSocket clients."""
        if chat_service.has_active_connections(agent_id, conversation_id):
            if not force:
                raise HTTPException(
                    status_code=409,
                    detail="Conversation has active connections. Use force to delete.",
                )
            await chat_service.close_connections(agent_id, conversation_id)

        try:
            conversation_service.delete_conversation(agent_id=agent_id, conversation_id=conversation_id)
        except KeyError:
            raise HTTPException(
                status_code=404,
                detail=f"Conversation {conversation_id} not found for agent {agent_id}.",
            )

    return router
