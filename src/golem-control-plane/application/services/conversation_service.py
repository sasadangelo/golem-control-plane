# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""ConversationService — application-layer use cases for conversation management."""

import re

from core.log import LoggerManager
from domain.models import Conversation
from domain.ports.sandbox_repo import SandboxRepository
from domain.ports.task_repo import ConversationRepository

logger = LoggerManager.get_logger(name="ConversationService")

_STOPWORDS = {
    "hi",
    "hello",
    "hey",
    "please",
    "could",
    "you",
    "would",
    "write",
    "create",
    "make",
    "show",
    "tell",
    "explain",
    "help",
    "me",
    "with",
    "a",
    "an",
    "the",
    "to",
    "for",
    "in",
    "on",
    "at",
    "by",
    "of",
    "from",
    "and",
    "or",
    "but",
    "what",
    "how",
    "why",
    "who",
    "which",
    "can",
    "do",
    "does",
    "did",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "have",
    "has",
    "had",
}


def _generate_title(message: str) -> str:
    """Derive a 2–4 word title from the first message of a conversation.

    Args:
        message: The first user message text.

    Returns:
        A capitalized short title, or "New Conversation" if nothing meaningful remains.
    """
    text = message.strip()
    if not text:
        return "New Conversation"

    words = re.findall(r"\b\w+\b", text.lower())
    filtered = [w for w in words if w not in _STOPWORDS] or words[:5]
    title = " ".join(w.capitalize() for w in filtered[:4])
    if len(title) > 24:
        title = f"{title[:21]}..."
    return title or "New Conversation"


class ConversationService:
    """Encapsulates business logic for conversation create, list, delete, and auto-naming."""

    def __init__(self, sandbox_repo: SandboxRepository, conversation_repo: ConversationRepository) -> None:
        self._sandboxes = sandbox_repo
        self._conversations = conversation_repo

    # ------------------------------------------------------------------
    # Use-case: create conversation
    # ------------------------------------------------------------------

    def create_conversation(self, agent_id: str, name: str) -> Conversation:
        """Create a new isolated conversation for an agent.

        Args:
            agent_id: The agent sandbox identifier.
            name: Optional human-readable label; defaults to "New Conversation".

        Returns:
            The newly created Conversation.

        Raises:
            KeyError: If the agent does not exist.
        """
        if not self._sandboxes.contains(agent_id):
            raise KeyError(agent_id)

        resolved_name = name.strip() if name.strip() else "New Conversation"
        conv = Conversation(agent_id=agent_id, name=resolved_name)
        self._conversations.save(conv)
        logger.info(f"Conversation created: agent={agent_id}  id={conv.conversation_id}  name={conv.name!r}")
        return conv

    # ------------------------------------------------------------------
    # Use-case: list conversations
    # ------------------------------------------------------------------

    def list_conversations(self, agent_id: str, active_ids: set[tuple[str, str]]) -> list[tuple[Conversation, bool]]:
        """Return all conversations for an agent with their active-connection flag.

        Args:
            agent_id: The agent sandbox identifier.
            active_ids: Set of (agent_id, conversation_id) keys that currently have open WebSocket connections.

        Returns:
            A list of (Conversation, is_active) tuples ordered by creation time.

        Raises:
            KeyError: If the agent does not exist.
        """
        if not self._sandboxes.contains(agent_id):
            raise KeyError(agent_id)

        convs = self._conversations.list_by_agent(agent_id)
        return [(c, (c.agent_id, c.conversation_id) in active_ids) for c in convs]

    # ------------------------------------------------------------------
    # Use-case: delete conversation
    # ------------------------------------------------------------------

    def delete_conversation(self, agent_id: str, conversation_id: str) -> None:
        """Remove a conversation record.

        Args:
            agent_id: The agent sandbox identifier.
            conversation_id: The conversation UUID to delete.

        Raises:
            KeyError: If the conversation does not exist.
        """
        if not self._conversations.contains(agent_id, conversation_id):
            raise KeyError(conversation_id)

        self._conversations.delete(agent_id, conversation_id)
        logger.info(f"Conversation deleted: agent={agent_id}  id={conversation_id}")

    # ------------------------------------------------------------------
    # Use-case: get conversation (existence check / lookup)
    # ------------------------------------------------------------------

    def get_conversation(self, agent_id: str, conversation_id: str) -> Conversation:
        """Return a conversation or raise KeyError if not found.

        Args:
            agent_id: The agent sandbox identifier.
            conversation_id: The conversation UUID.

        Returns:
            The matching Conversation.

        Raises:
            KeyError: If the conversation does not exist.
        """
        conv = self._conversations.get(agent_id, conversation_id)
        if conv is None:
            raise KeyError(conversation_id)
        return conv

    # ------------------------------------------------------------------
    # Use-case: auto-name conversation on first message
    # ------------------------------------------------------------------

    def auto_name_if_needed(self, agent_id: str, conversation_id: str, first_message: str) -> None:
        """Rename a conversation from its default title using the first message.

        A no-op if the conversation has already been renamed or does not exist.

        Args:
            agent_id: The agent sandbox identifier.
            conversation_id: The conversation UUID.
            first_message: The first user message text.
        """
        conv = self._conversations.get(agent_id, conversation_id)
        if conv is None or conv.name != "New Conversation":
            return

        title = _generate_title(first_message)
        conv.name = title
        self._conversations.save(conv)
        logger.info(f"Auto-named conversation {conversation_id} to {title!r}")
