from __future__ import annotations
from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
from pathlib import Path
from typing import Annotated, Any

from langchain_core.tools import BaseTool, StructuredTool, tool
from langchain_mcp_adapters.client import MultiServerMCPClient
import asyncio

WORKSPACE_ROOT = Path.cwd()
LOGS_DIR = WORKSPACE_ROOT / "logs"
try:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    # best-effort: if we cannot create logs dir under workspace, ignore for now
    pass


def _resolve_path(path: str) -> Path:
    target = (WORKSPACE_ROOT / path).resolve()
    if WORKSPACE_ROOT not in target.parents and target != WORKSPACE_ROOT:
        raise ValueError("Path escapes workspace root.")
    return target


def _write_hook_entry(entry: dict) -> None:
    run_id = os.environ.get("AGENT_RUN_ID")
    # if no run id, write to a fallback file with timestamp
    if not run_id:
        run_id = f"fallback-{int(time.time())}"
    path = LOGS_DIR / f"{run_id}.jsonl"
    try:
        # ensure directory exists (in case cwd changed after import)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as exc:
        # fallback: attempt to write to /tmp and emit a clear diagnostic to stdout
        try:
            tmp_path = Path("/tmp") / f"{run_id}.jsonl"
            with tmp_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
            print(f"[tools._write_hook_entry] failed to write to {path}: {exc}; wrote to {tmp_path} instead")
        except Exception as exc2:
            print(f"[tools._write_hook_entry] failed to write hook entry to {path} and /tmp: {exc2}")


def _log_hook(event: str, tool_name: str, call_id: str, payload: object | None = None) -> None:
    entry = {
        "event": event,
        "tool": tool_name,
        "call_id": call_id,
        "timestamp": time.time(),
        "process_pid": os.getpid(),
    }
    if payload is not None:
        try:
            json.dumps(payload)
            entry["payload"] = payload
        except TypeError:
            entry["payload"] = str(payload)
    try:
        _write_hook_entry(entry)
    except Exception as exc:
        # ensure logging doesn't raise and break tool execution
        print(f"[tools._log_hook] failed to write log entry: {exc}")


def _read_file_impl(path: str) -> str:
    target = _resolve_path(path)
    return target.read_text(encoding="utf-8")


def _write_file_impl(path: str, content: str) -> str:
    target = _resolve_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"Wrote {len(content)} characters to {path}."


def _run_bash_impl(command: str) -> str:
    completed = subprocess.run(
        command,
        cwd=WORKSPACE_ROOT,
        shell=True,
        check=False,
        capture_output=True,
        text=True,
    )
    output = completed.stdout
    if completed.stderr:
        output = f"{output}\nSTDERR:\n{completed.stderr}".strip()
    return output.strip() or "(no output)"


def _wrap_mcp_tool(tool_obj: BaseTool, url: str) -> StructuredTool:
    tool_name = tool_obj.name
    description = tool_obj.description or "Feishu MCP tool"
    args_schema = getattr(tool_obj, "args_schema", None)

    def _runner(**kwargs: Any) -> str:
        call_id = str(uuid.uuid4())
        _log_hook("hook_before", tool_name, call_id, {"url": url, "args": kwargs})
        start = time.time()
        try:
            result = asyncio.run(tool_obj.ainvoke(kwargs))
            if not isinstance(result, str):
                result = json.dumps(result, ensure_ascii=False)
            _log_hook(
                "hook_after",
                tool_name,
                call_id,
                {"result_len": len(result), "result_snippet": result[:200], "duration": time.time() - start},
            )
            return result
        except Exception as exc:
            _log_hook("hook_error", tool_name, call_id, {"error": str(exc)})
            raise

    return StructuredTool.from_function(
        func=_runner,
        name=tool_name,
        description=description,
        args_schema=args_schema,
    )


def load_mcp_tools() -> list[StructuredTool]:
    url = os.environ.get("MCP_FEISHU_URL")
    if not url:
        print("MCP_FEISHU_URL environment variable not set, skipping MCP tools.")
        return []
    print(f"Loading MCP tools from {url}...")
    client = MultiServerMCPClient(
        {
            "feishu_server": {
                "transport": "http",
                "url": url,
            }
        }
    )

    tools = asyncio.run(client.get_tools())
    wrapped_tools: list[StructuredTool] = []
    for tool_obj in tools:
        wrapped_tools.append(_wrap_mcp_tool(tool_obj, url))
    print(f"Loaded {len(wrapped_tools)} MCP tools via langchain-mcp-adapters.")
    return wrapped_tools


@tool
def read_file(path: Annotated[str, "Relative path to file."]) -> str:
    """Read a text file from the workspace and return its contents.

    This wrapper emits hook events before and after the underlying implementation.
    """
    call_id = str(uuid.uuid4())
    _log_hook("hook_before", "read_file", call_id, {"path": path})
    start = time.time()
    try:
        res = _read_file_impl(path)
        _log_hook("hook_after", "read_file", call_id, {"result_len": len(res), "duration": time.time() - start})
        return res
    except Exception as e:
        _log_hook("hook_error", "read_file", call_id, {"error": str(e)})
        raise


@tool
def write_file(
    path: Annotated[str, "Relative path to file."],
    content: Annotated[str, "File content to write."],
) -> str:
    """Write content to a text file in the workspace.

    Emits hook events before and after the underlying implementation.
    """
    call_id = str(uuid.uuid4())
    _log_hook("hook_before", "write_file", call_id, {"path": path, "content_len": len(content)})
    start = time.time()
    try:
        res = _write_file_impl(path, content)
        _log_hook("hook_after", "write_file", call_id, {"result": res, "duration": time.time() - start})
        return res
    except Exception as e:
        _log_hook("hook_error", "write_file", call_id, {"error": str(e)})
        raise


@tool
def run_bash(command: Annotated[str, "Shell command to execute."]) -> str:
    """Run a bash command inside the workspace and return stdout/stderr.

    Emits hook events before and after calling the shell.
    """
    call_id = str(uuid.uuid4())
    _log_hook("hook_before", "run_bash", call_id, {"command": command})
    start = time.time()
    try:
        res = _run_bash_impl(command)
        # include full result but cap length to avoid huge logs
        capped = res if len(res) <= 20000 else res[:20000] + "\n...[truncated]"
        _log_hook("hook_after", "run_bash", call_id, {"result": capped, "result_snippet": capped[:200], "duration": time.time() - start})
        return res
    except Exception as e:
        _log_hook("hook_error", "run_bash", call_id, {"error": str(e)})
        raise


BASE_TOOLS = [read_file, write_file, run_bash]


def get_tools() -> list:
    return [*BASE_TOOLS, *load_mcp_tools()]
