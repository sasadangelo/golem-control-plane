# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""ChatService — application-layer use cases for WebSocket chat proxying."""

import asyncio

import websockets
import websockets.exceptions
from fastapi import WebSocket

from core.config import settings
from core.log import LoggerManager
from domain.models import SandboxStatus
from domain.ports.sandbox_repo import SandboxRepository

logger = LoggerManager.get_logger(name="ChatService")


class ChatService:
    """Encapsulates the bidirectional WebSocket proxy between a client and a runner pod."""

    def __init__(self, sandbox_repo: SandboxRepository) -> None:
        self._sandboxes = sandbox_repo
        # Active connections: {(agent_id, conversation_id): [WebSocket]}
        self._active: dict[tuple[str, str], list[WebSocket]] = {}

    # ------------------------------------------------------------------
    # Active-connection registry (read-only view used by ConversationService)
    # ------------------------------------------------------------------

    @property
    def active_connection_keys(self) -> set[tuple[str, str]]:
        """Return the set of (agent_id, conversation_id) pairs with open sockets."""
        return {k for k, sockets in self._active.items() if sockets}

    # ------------------------------------------------------------------
    # Use-case: proxy chat session
    # ------------------------------------------------------------------

    async def proxy(
        self,
        websocket: WebSocket,
        agent_id: str,
        conversation_id: str | None,
        auto_name_callback: object = None,
    ) -> None:
        """Proxy a WebSocket chat session between a client and the runner pod.

        Args:
            websocket: The inbound client WebSocket connection.
            agent_id: The agent sandbox identifier.
            conversation_id: Optional UUID of an existing conversation.
            auto_name_callback: Optional async callable(agent_id, conversation_id, first_message)
                                 invoked with the first message for auto-naming.

        Raises:
            ValueError: If the agent does not exist or is not running.
            KeyError: If conversation_id is specified but does not exist in the registry.
        """
        handle = self._sandboxes.get(agent_id)
        if handle is None:
            await websocket.close(code=4404, reason=f"Agent {agent_id} not found.")
            return

        if handle.status != SandboxStatus.RUNNING:
            await websocket.close(code=4503, reason=f"Agent {agent_id} is not running (status={handle.status}).")
            return

        base_runner_url = (
            settings.test.runner_url or f"ws://{handle.pod_name}.{handle.namespace}.svc.cluster.local:8000/ws/chat"
        )
        runner_url = f"{base_runner_url}?conversation_id={conversation_id}" if conversation_id else base_runner_url
        await websocket.accept()

        if conversation_id:
            key = (agent_id, conversation_id)
            self._active.setdefault(key, []).append(websocket)

        try:
            async with websockets.connect(runner_url) as runner_ws:  # type: ignore[attr-defined]
                logger.info(f"Chat proxy open: client ↔ {agent_id} ({runner_url})")

                async def _client_to_runner() -> None:
                    nonlocal conversation_id
                    is_first = True
                    async for message in websocket.iter_text():
                        if is_first and conversation_id and auto_name_callback is not None:
                            is_first = False
                            await auto_name_callback(agent_id, conversation_id, message)  # type: ignore[operator]
                        await runner_ws.send(message)

                async def _runner_to_client() -> None:
                    async for token in runner_ws:
                        await websocket.send_text(str(token))

                await asyncio.wait(
                    [
                        asyncio.ensure_future(_client_to_runner()),
                        asyncio.ensure_future(_runner_to_client()),
                    ],
                    return_when=asyncio.ALL_COMPLETED,
                )

        except websockets.exceptions.ConnectionClosed:
            pass
        except (OSError, TimeoutError, websockets.exceptions.WebSocketException) as e:
            logger.warning(f"Chat proxy error for agent {agent_id}: {e}")
            await websocket.close(code=1011, reason=str(e))
        finally:
            if conversation_id:
                key = (agent_id, conversation_id)
                conns = self._active.get(key, [])
                if websocket in conns:
                    conns.remove(websocket)
                if not conns:
                    self._active.pop(key, None)
            logger.info(f"Chat proxy closed: {agent_id}")

    # ------------------------------------------------------------------
    # Use-case: force-close connections for a conversation
    # ------------------------------------------------------------------

    async def close_connections(self, agent_id: str, conversation_id: str) -> None:
        """Force-close all active WebSocket connections for a conversation.

        Args:
            agent_id: The agent sandbox identifier.
            conversation_id: The conversation UUID.
        """
        key = (agent_id, conversation_id)
        for ws in list(self._active.get(key, [])):
            try:
                await ws.close(code=1001, reason="Conversation deleted via force option.")
            except Exception as exc:  # noqa: BLE001
                logger.debug(f"Failed to close active websocket during force delete: {exc}")
        self._active.pop(key, None)

    def has_active_connections(self, agent_id: str, conversation_id: str) -> bool:
        """Return True if there are open WebSocket connections for this conversation.

        Args:
            agent_id: The agent sandbox identifier.
            conversation_id: The conversation UUID.
        """
        return bool(self._active.get((agent_id, conversation_id)))
