from __future__ import annotations

import os
from pathlib import Path
from typing import Sequence

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from code_agent.tools import get_tools

from langchain_core.tools import tool as tool_decorator
from code_agent.tools import write_file as orig_write_file


def _load_dotenv(path: str | Path | None = None) -> None:
    """尽力从 .env 文件加载简单的 KEY=VALUE 对到 os.environ 中。

    该实现避免了额外依赖；支持基本的引号和注释行为。
    已存在的环境变量不会被覆盖。
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
            # 不覆盖已存在的环境变量
            os.environ.setdefault(k, v)
    except Exception:
        # non-fatal; fall back to whatever env is already set
        return


def build_agent(tools: Sequence | None = None):
    """创建一个与 DashScope 兼容的 LangGraph ReAct agent。

    API key 会优先从仓库根目录的 `.env` 文件读取（变量名 `DASHSCOPE_API_KEY`），
    若不存在则从环境变量中读取。
    """
    _load_dotenv()
    api_key = os.environ.get("DASHSCOPE_API_KEY")
    # Read service endpoint and model name from environment (or .env)
    # Defaults kept for backwards compatibility.
    base_url = os.environ.get("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    model_name = os.environ.get("DASHSCOPE_MODEL", "qwen-flash")
    model = ChatOpenAI(
        api_key=api_key,
        base_url=base_url,
        model=model_name,
    )
    # 如果存在则加载简单的策略文件
    policy_path = Path.cwd() / "policies" / "policy.yaml"
    forbidden = []
    if policy_path.exists():
        try:
            # 一个极简的类 YAML 解析器，用于读取 `forbidden_folders:` 列表
            lines = [l.rstrip() for l in policy_path.read_text(encoding="utf-8").splitlines()]
            in_list = False
            for ln in lines:
                if ln.strip().startswith("forbidden_folders:"):
                    in_list = True
                    continue
                if in_list:
                    s = ln.strip()
                    if s.startswith("-"):
                        item = s.lstrip("- ")
                        if item:
                            forbidden.append(item)
                    elif s == "":
                        continue
                    else:
                        # 列表结束
                        break
        except Exception:
            forbidden = []

    # 在不修改 tools.py 的情况下，创建一个带策略检查的 write_file 包装器
    @tool_decorator
    def write_file(path: str, content: str) -> str:
        """在调用原始 `write_file` 之前执行策略检查。

        如果目标路径位于被禁止的文件夹或其子路径下，函数将返回一条
        以 `PolicyBlocked` 开头的说明字符串并阻止写入；否则将委托给
        原始的 `write_file` 实现执行实际写入。
        """
        try:
            target = (Path.cwd() / path).resolve()
            for f in forbidden:
                base = (Path.cwd() / f).resolve()
                if base == target or base in target.parents:
                    return f"PolicyBlocked: 写入 '{path}' 被策略阻止（禁止: {f}）"
        except Exception:
            # 如果策略校验出错，保守起见阻止写入
            return f"PolicyError: 无法校验路径 '{path}'"
        # delegate to the original tool implementation
        # 委托给原始的 write_file 工具实现进行实际写入
        # bugfix: invoke
        return orig_write_file.invoke({"path": path, "content": content})

    # 将 tools 列表中的 write_file 替换为我们的包装器
    def _tool_name(t):
        # 尝试从不同属性获取工具的名字，兼容被框架包装后的对象
        try:
            name = getattr(t, "__name__", None)
            if name:
                return name
        except Exception:
            pass
        name = getattr(t, "name", None)
        if name:
            return name
        func = getattr(t, "func", None)
        if func:
            return getattr(func, "__name__", None)
        return None

    if tools is None:
        tools = get_tools()
        print(f"Loaded {len(tools)} tools, they are: {tools}")

    new_tools = []
    for t in tools:
        if _tool_name(t) == "write_file":
            new_tools.append(write_file)
        else:
            new_tools.append(t)

    return create_react_agent(model, new_tools)
    # Fallback / legacy path: also respect env vars here
    base_url = os.environ.get("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    model_name = os.environ.get("DASHSCOPE_MODEL", "qwen-flash")
    model = ChatOpenAI(
        api_key=api_key,
        base_url=base_url,
        model=model_name,
    )
    return create_react_agent(model, tools)
