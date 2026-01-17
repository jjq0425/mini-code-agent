from __future__ import annotations

import os
from typing import Sequence

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from code_agent.tools import TOOLS


def build_agent(tools: Sequence = TOOLS):
    """Create a LangGraph ReAct agent wired to DashScope-compatible API."""
    model = ChatOpenAI(
        api_key=os.getenv("DASHSCOPE_API_KEY"),
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model="qwen-plus",
    )
    return create_react_agent(model, tools)
