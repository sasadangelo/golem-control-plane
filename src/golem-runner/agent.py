# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""LangGraph agent with dynamic tool loading from environment variables."""

import os
from typing import Annotated, Literal

from dotenv import load_dotenv
from langchain_core.messages import BaseMessage, SystemMessage
from langchain_ibm import ChatWatsonx
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from tools.http_tools import http_health_check
from tools.system_tools import execute_bash_command
from typing_extensions import TypedDict

# Central registry of available skills
TOOL_REGISTRY = {
    "bash": execute_bash_command,
    "http_check": http_health_check,
}

load_dotenv()


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


def build_agent():
    system_prompt = os.getenv("SYSTEM_PROMPT", "You are a helpful generic automation agent.")
    enabled_skills_env = os.getenv("ENABLED_SKILLS", "")  # e.g. "bash,http_check"

    selected_tools = []
    if enabled_skills_env:
        for key in (s.strip() for s in enabled_skills_env.split(",") if s.strip()):
            if key in TOOL_REGISTRY:
                selected_tools.append(TOOL_REGISTRY[key])

    llm = ChatWatsonx(
        model_id=os.getenv("WATSONX_MODEL_ID", "openai/gpt-oss-120b"),
        url=os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com"),
        project_id=os.getenv("WATSONX_PROJECT_ID"),
        api_key=os.getenv("WATSONX_API_KEY"),
    )

    if selected_tools:
        llm = llm.bind_tools(selected_tools)

    def call_model(state: AgentState):
        messages = [SystemMessage(content=system_prompt)] + state["messages"]
        response = llm.invoke(messages)
        return {"messages": [response]}

    builder = StateGraph(AgentState)
    builder.add_node("agent", call_model)

    if selected_tools:
        tool_node = ToolNode(selected_tools)
        builder.add_node("tools", tool_node)
        builder.set_entry_point("agent")

        def should_continue(state: AgentState) -> Literal["tools", "__end__"]:
            last = state["messages"][-1]
            if hasattr(last, "tool_calls") and last.tool_calls:
                return "tools"
            return "__end__"

        builder.add_conditional_edges("agent", should_continue)
        builder.add_edge("tools", "agent")
    else:
        builder.set_entry_point("agent")
        builder.add_edge("agent", END)

    return builder.compile()


# Compiled graph — instantiated once at container startup
agent_executor = build_agent()
