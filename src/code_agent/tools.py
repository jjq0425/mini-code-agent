from __future__ import annotations
from __future__ import annotations

import functools
import json
import os
import subprocess
import time
import uuid
from pathlib import Path
from typing import Annotated, Any, List

import httpx
from langchain_core.tools import StructuredTool, tool
from pydantic import BaseModel, Field, create_model

WORKSPACE_ROOT = Path.cwd()
LOGS_DIR = WORKSPACE_ROOT / "logs"
LOGS_DIR.mkdir(exist_ok=True)


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
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


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
    _write_hook_entry(entry)


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


def _post_json(url: str, payload: dict) -> dict:
    headers = {
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=30) as client:
        response = client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()


def _fetch_mcp_schemas(url: str) -> list[dict]:
    errors = []
    print(f"Fetching MCP tool schemas from: {url}")
    
    # 尝试 1: POST with JSON-RPC 2.0 format
    try:
        # Standard JSON-RPC 2.0 format with required fields
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {}
        }
        
        response = _post_json(url, payload)

        
        # Check for JSON-RPC error
        if "error" in response:
            raise Exception(f"JSON-RPC error: {response['error']}")
        
        # Try to extract tools from response
        result = response.get("result", {})
        tools = result.get("tools") if isinstance(result, dict) else None
        if not tools:
            tools = response.get("tools")
        
        if isinstance(tools, list):
            print(f"Successfully loaded {len(tools)} tools via POST")
            return tools
    except Exception as exc:
        
        errors.append(exc)
    
    # # 尝试 2: Simple GET request
    # try:
    #     print("Trying GET request...")
    #     with httpx.Client(timeout=30) as client:
    #         response = client.get(url)
    #         response.raise_for_status()
    #         data = response.json()
    #     print(f"GET response: {data}")
    #     if isinstance(data, dict) and "tools" in data and isinstance(data["tools"], list):
    #         print(f"Successfully loaded {len(data['tools'])} tools via GET")
    #         return data["tools"]
    #     if isinstance(data, dict) and "name" in data:
    #         print("Found single tool definition via GET")
    #         return [data]
    # except Exception as exc:
    #     print(f"GET request failed: {type(exc).__name__}: {exc}")
    #     errors.append(exc)
    
    if errors:
        print(f"All attempts failed. Raising last error.")
        raise errors[-1]
    return []


def _json_schema_to_pydantic(schema: dict, name: str) -> type[BaseModel]:
    # 递归地将 JSON Schema 转为 Pydantic model
    created_models: dict[str, type[BaseModel]] = {}

    def _make_model(sch: dict, base: str) -> type[BaseModel]:
        key = base
        if key in created_models:
            return created_models[key]

        if sch.get("type") != "object":
            # 非 object 类型，返回一个占位的简单容器模型
            model = create_model(f"{base.title().replace('-', '').replace(' ', '')}Args")
            created_models[key] = model
            return model

        properties = sch.get("properties", {}) or {}
        required = set(sch.get("required", []) or [])
        fields: dict[str, tuple[Any, Any]] = {}

        for prop_name, prop_schema in properties.items():
            description = prop_schema.get("description", "")
            default_val = prop_schema.get("default", ...)
            ptype = prop_schema.get("type")

            # 处理基础类型
            if ptype == "string":
                py_type = str
            elif ptype == "integer":
                py_type = int
            elif ptype == "number":
                py_type = float
            elif ptype == "boolean":
                py_type = bool
            elif ptype == "object":
                # 递归创建子模型
                child = _make_model(prop_schema, f"{base}_{prop_name}")
                py_type = child
            elif ptype == "array":
                items = prop_schema.get("items") or {}
                item_type = items.get("type")
                if item_type == "object":
                    child = _make_model(items, f"{base}_{prop_name}_item")
                    py_type = list[child]
                else:
                    if item_type == "string":
                        it = str
                    elif item_type == "integer":
                        it = int
                    elif item_type == "number":
                        it = float
                    elif item_type == "boolean":
                        it = bool
                    else:
                        it = Any
                    py_type = list[it]
            else:
                py_type = Any

            if prop_name in required:
                field_default = Field(..., description=description)
            else:
                field_default = Field(default_val if default_val is not ... else None, description=description)

            fields[prop_name] = (py_type, field_default)

        model_name = f"{base.title().replace('-', '').replace(' ', '')}Args"
        model = create_model(model_name, **fields)
        created_models[key] = model
        return model

    return _make_model(schema, name)


def _call_mcp_tool_impl(url: str, tool_name: str, arguments: dict) -> str:
    payload = {"method": "tools/call", "params": {"name": tool_name, "arguments": arguments}}
    response = _post_json(url, payload)
    if isinstance(response, dict) and "result" in response:
        return json.dumps(response["result"], ensure_ascii=False)
    return json.dumps(response, ensure_ascii=False)


def _build_mcp_tool(url: str, schema: dict) -> StructuredTool:
    tool_name = schema.get("name") or "mcp_tool"
    description = schema.get("description") or "Feishu MCP tool"
    input_schema = schema.get("input_schema") or schema.get("inputSchema") or {}
    args_schema = _json_schema_to_pydantic(input_schema, tool_name)

    # Diagnostic: 输出原始 input_schema 与生成的 pydantic model字段，方便排查解析是否正确
    try:
        print(f"MCP tool '{tool_name}' input_schema: {json.dumps(input_schema, ensure_ascii=False)[:1000]}")
    except Exception:
        print(f"MCP tool '{tool_name}' input_schema: (unprintable)")
    try:
        fields = getattr(args_schema, "__fields__", None)
        if fields is not None:
            field_names = list(fields.keys())
            print(f"MCP tool '{tool_name}' generated args_schema fields: {field_names}")
        else:
            print(f"MCP tool '{tool_name}' generated args_schema: {args_schema}")
    except Exception:
        print(f"MCP tool '{tool_name}' args_schema inspection failed")

    def _runner(**kwargs: Any) -> str:
        call_id = str(uuid.uuid4())
        _log_hook("hook_before", tool_name, call_id, {"url": url, "args": kwargs})
        start = time.time()
        try:
            res = _call_mcp_tool_impl(url, tool_name, kwargs)
            _log_hook(
                "hook_after",
                tool_name,
                call_id,
                {"result_len": len(res), "result_snippet": res[:200], "duration": time.time() - start},
            )
            return res
        except Exception as exc:
            _log_hook("hook_error", tool_name, call_id, {"error": str(exc)})
            raise

    tool_obj = StructuredTool.from_function(
        func=functools.wraps(_runner)(_runner),
        name=tool_name,
        description=description,
        args_schema=args_schema,
    )
    try:
        print(f"Built MCP tool: {tool_name}, args_schema={getattr(args_schema,'__name__', str(type(args_schema)))}")
    except Exception:
        print(f"Built MCP tool: {tool_name}")
    return tool_obj


def load_mcp_tools() -> list[StructuredTool]:
    url = os.environ.get("MCP_FEISHU_URL")
    if not url:
        print("MCP_FEISHU_URL environment variable not set, skipping MCP tools.")
        return []
    print(f"Loading MCP tools from {url}...")
    try:
        schemas = _fetch_mcp_schemas(url)
    except Exception as e:
        print(f"Failed to fetch MCP tool schemas from {url}: {type(e).__name__}: {e}")
        return []
    tools: list[StructuredTool] = []
    for i, schema in enumerate(schemas):
        if isinstance(schema, dict):
            print(f"Building tool {i+1}/{len(schemas)}: {schema.get('name')}")
            tools.append(_build_mcp_tool(url, schema))
    print(f"Built {len(tools)} MCP tools, returning to caller.")
    return tools[:1]


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
