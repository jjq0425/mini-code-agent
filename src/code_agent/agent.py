from __future__ import annotations

import os
from pathlib import Path
from typing import Sequence

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from code_agent.tools import TOOLS


def _load_dotenv(path: str | Path | None = None) -> None:
    """Best-effort load simple KEY=VALUE pairs from a .env file into os.environ.

    This avoids adding external dependencies; it handles basic quotes and comments.
    Existing environment variables are not overwritten.
    """
    p = Path(path) if path else Path.cwd() / ".env"
    if not p.exists():
        return
    try:
        for raw in p.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip()
            if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                v = v[1:-1]
            # don't overwrite existing env vars
            os.environ.setdefault(k, v)
    except Exception:
        # non-fatal; fall back to whatever env is already set
        return


def build_agent(tools: Sequence = TOOLS):
    """Create a LangGraph ReAct agent wired to DashScope-compatible API.

    The API key is loaded from a `.env` file in the repository root (variable
    name `DASHSCOPE_API_KEY`) if present, otherwise from the environment.
    """
    _load_dotenv()
    api_key = os.environ.get("DASHSCOPE_API_KEY")
    model = ChatOpenAI(
        api_key=api_key,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model="qwen-flash",
    )
    return create_react_agent(model, tools)
