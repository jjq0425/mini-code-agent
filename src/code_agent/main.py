from __future__ import annotations

import argparse
import json
import os
import time
import uuid
import logging
import traceback
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LangGraph code agent demo")
    parser.add_argument(
        "prompt",
        nargs="?",
        default="请读取 README.md 并总结项目用途。",
        help="User prompt to send to the agent.",
    )
    return parser.parse_args()


def _read_hooks(run_id: str) -> list:
    logs_dir = Path.cwd() / "logs"
    path = logs_dir / f"{run_id}.jsonl"
    if not path.exists():
        return []
    items = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            try:
                items.append(json.loads(line))
            except Exception:
                items.append({"raw": line.strip()})
    return items


def _group_hooks_by_call(hooks: list) -> dict:
    groups = {}
    for h in hooks:
        cid = h.get("call_id")
        if cid is None:
            cid = "-"
        groups.setdefault(cid, []).append(h)
    return groups


def _parse_agent_output(serializable, model_trace_messages, hooks):
    """Produce a clean, human-friendly agent_output list.

    Each item is either a human/ai message with optional tool_calls entries
    enriched from `hooks` (timestamps, results).
    """
    # build call_id -> hook info map
    call_map = {}
    try:
        for h in hooks:
            cid = h.get("call_id")
            if not cid:
                continue
            call_map.setdefault(cid, {})
            ev = h.get("event")
            if ev == "hook_before":
                call_map[cid]["before"] = {k: h.get(k) for k in ("timestamp", "process_pid", "payload")}
            elif ev == "hook_after":
                call_map[cid]["after"] = {k: h.get(k) for k in ("timestamp", "process_pid", "payload")}
    except Exception:
        call_map = {}

    # If we already have structured model_trace_messages, convert to readable form
    if model_trace_messages:
        out = []
        for m in model_trace_messages:
            entry = {
                "id": m.get("id"),
                "role": m.get("role"),
                "content": m.get("content"),
                "response_metadata": m.get("response_metadata"),
            }
            # try to find tool_calls in response_metadata
            calls = []
            try:
                rm = entry.get("response_metadata") or {}
                if isinstance(rm, dict) and "tool_calls" in rm and isinstance(rm["tool_calls"], list):
                    for c in rm["tool_calls"]:
                        call = {"name": c.get("name"), "id": c.get("id"), "args": c.get("args")}
                        cid = c.get("id")
                        if cid and cid in call_map:
                            call.update(call_map[cid])
                        calls.append(call)
            except Exception:
                calls = []
            entry["tool_calls"] = calls
            out.append(entry)
        return out

    # Otherwise try to parse string representation like the legacy runs
    parsed = []
    if isinstance(serializable, str):
        s = serializable
        import re

        pattern = re.compile(r"(HumanMessage|AIMessage|ToolMessage)\((.*?)\)(?:, |,?$)", re.DOTALL)
        for m in pattern.finditer(s):
            kind = m.group(1)
            inner = m.group(2)
            entry = {"type": kind}
            # id
            id_m = re.search(r"id=(?P<q>['\"])(?P<id>.*?)(?P=q)", inner)
            if id_m:
                entry["id"] = id_m.group("id")
            # content
            cm = re.search(r"content=(?P<q>['\"])(?P<c>.*?)(?P=q)", inner, re.DOTALL)
            if cm:
                entry["content"] = cm.group("c")
            # tool_calls for AIMessage
            if kind == "AIMessage":
                tc_m = re.search(r"tool_calls=\[(?P<t>.*?)\](,|\)|$)", inner, re.DOTALL)
                calls = []
                if tc_m:
                    calls_block = tc_m.group("t")
                    for tb in re.finditer(r"\{(.*?)\}", calls_block, re.DOTALL):
                        tb_inner = tb.group(1)
                        name_m = re.search(r"name['\"]?[:=]\s*['\"](?P<name>[^'\"]+)['\"]", tb_inner)
                        id_m2 = re.search(r"id['\"]?[:=]\s*['\"](?P<id>[^'\"]+)['\"]", tb_inner)
                        args_m = re.search(r"args['\"]?[:=]\s*\{(?P<args>.*?)\}\s*(,|$)", tb_inner, re.DOTALL)
                        call = {}
                        if name_m:
                            call["name"] = name_m.group("name")
                        if id_m2:
                            call["id"] = id_m2.group("id")
                        if args_m:
                            args_txt = args_m.group("args")
                            # extract common args
                            path_m = re.search(r"path['\"]?\s*[:=]\s*['\"](?P<path>[^'\"]+)['\"]", args_txt)
                            cmd_m = re.search(r"command['\"]?\s*[:=]\s*['\"](?P<cmd>[^'\"]+)['\"]", args_txt)
                            content_m = re.search(r"content['\"]?\s*[:=]\s*(?P<q>['\"])(?P<content>.*?)(?P=q)", args_txt, re.DOTALL)
                            call_args = {}
                            if path_m:
                                call_args["path"] = path_m.group("path")
                            if cmd_m:
                                call_args["command"] = cmd_m.group("cmd")
                            if content_m:
                                call_args["content"] = content_m.group("content")
                            call["args"] = call_args if call_args else {"raw": args_txt.strip()}
                        # enrich from hooks
                        if id_m2:
                            cid_val = id_m2.group("id")
                            if cid_val in call_map:
                                call.update(call_map[cid_val])
                        calls.append(call)
                entry["tool_calls"] = calls
            parsed.append(entry)
    return parsed


def main() -> None:
    args = _parse_args()
    # create a run id and export it so tools write hooks to logs/{run_id}.jsonl
    run_id = str(uuid.uuid4())
    os.environ["AGENT_RUN_ID"] = run_id

    # ensure logs dir exists
    logs_dir = Path.cwd() / "logs"
    logs_dir.mkdir(exist_ok=True)

    # minimal error capture: attempt to import the agent here so we can catch
    # SyntaxError/ImportError and write a structured error log even if the
    # code fails to compile.
    try:
        from code_agent.agent import build_agent
    except Exception as e:
        err_path = logs_dir / f"{run_id}.error.json"
        err_payload = {
            "run_id": run_id,
            "error_type": type(e).__name__,
            "error": str(e),
            "traceback": traceback.format_exc(),
            "timestamp": time.time(),
        }
        try:
            err_path.write_text(json.dumps(err_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            # fallback: basic logging to stderr if file write fails
            logging.error("Failed to write error log for run %s: %s", run_id, e)
            logging.error(traceback.format_exc())
        print(f"Agent failed to start. See logs/{run_id}.error.json")
        return

    start_ts = time.time()
    try:
        app = build_agent()
        result = app.invoke({"messages": [{"role": "user", "content": args.prompt}]})
        duration = time.time() - start_ts
    except Exception as e:
        duration = time.time() - start_ts
        err_path = logs_dir / f"{run_id}.error.json"
        err_payload = {
            "run_id": run_id,
            "phase": "runtime",
            "error_type": type(e).__name__,
            "error": str(e),
            "traceback": traceback.format_exc(),
            "timestamp": time.time(),
        }
        try:
            err_path.write_text(json.dumps(err_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            logging.error("Failed to write runtime error log for run %s: %s", run_id, e)
            logging.error(traceback.format_exc())
        print(f"Agent runtime error. See logs/{run_id}.error.json")
        # still attempt to continue to produce a run record with error info
        result = {"error": str(e), "traceback": traceback.format_exc()}

    # Extract model-internal trace: messages, response metadata, and any tool_calls
    model_trace = {"messages": []}
    try:
        # prefer live object messages
        msgs = None
        if hasattr(result, "messages"):
            msgs = getattr(result, "messages")
        elif isinstance(result, dict) and "messages" in result:
            msgs = result["messages"]

        if msgs:
            for m in msgs:
                entry = {}
                try:
                    entry["id"] = getattr(m, "id", None) or (m.get("id") if isinstance(m, dict) else None)
                except Exception:
                    entry["id"] = None
                try:
                    entry["role"] = getattr(m, "role", None) or (m.get("role") if isinstance(m, dict) else None)
                except Exception:
                    entry["role"] = None
                try:
                    entry["content"] = getattr(m, "content", None) or (m.get("content") if isinstance(m, dict) else None)
                except Exception:
                    entry["content"] = None
                try:
                    # response_metadata may be nested; try attribute then dict access
                    rm = getattr(m, "response_metadata", None)
                    if rm is None and isinstance(m, dict):
                        rm = m.get("response_metadata")
                    entry["response_metadata"] = rm
                except Exception:
                    entry["response_metadata"] = None
                model_trace["messages"].append(entry)
    except Exception:
        # best-effort; leave model_trace minimal
        pass

    # collect hooks written by tools
    hooks = _read_hooks(run_id)
    grouped = _group_hooks_by_call(hooks)

    # normalize result for JSON storage
    if hasattr(result, "dict") and callable(getattr(result, "dict")):
        serializable = result.dict()
    else:
        try:
            json.dumps(result)
            serializable = result
        except TypeError:
            # fallback to string representation (do not attempt unicode_escape decode)
            serializable = str(result)

    # write full run record
    parsed_agent_output = _parse_agent_output(serializable, model_trace.get("messages", []), hooks)
    run_record = {
        "run_id": run_id,
        "prompt": args.prompt,
        "timestamp": start_ts,
        "duration": duration,
        "agent_pid": os.getpid(),
        "hooks": hooks,
        "result": serializable,
        "agent_output": parsed_agent_output,
        "agent_output_raw": model_trace.get("messages", []),
    }
    # Write full run record to its own JSON file and remove the jsonl hooks file
    out_path = Path.cwd() / "logs" / f"{run_id}.json"
    out_path.write_text(json.dumps(run_record, ensure_ascii=False, indent=2), encoding="utf-8")

    # remove the jsonl file for this run (hooks were already read into `hooks`)
    jsonl_path = Path.cwd() / "logs" / f"{run_id}.jsonl"
    try:
        if jsonl_path.exists():
            jsonl_path.unlink()
    except Exception:
        # non-fatal: if we can't remove, leave it
        pass

    # Pretty-print to terminal: summary, tools, and final AI message
    def _fmt_ts(ts: float) -> str:
        try:
            return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))
        except Exception:
            return str(ts)

    print("=== Agent run summary ===")
    print(f"run_id: {run_id}")
    print(f"agent_pid: {os.getpid()}")
    print(f"prompt: {args.prompt}")
    print(f"duration: {duration:.3f}s")
    print()

    if grouped:
        print("--- Tool calls ---")
        for cid, events in grouped.items():
            events_sorted = sorted(events, key=lambda e: e.get("timestamp", 0))
            tool_name = events_sorted[0].get("tool")
            print(f"call_id: {cid}    tool: {tool_name}")
            # detect pid variations for this call
            pids = [e.get("process_pid") for e in events_sorted if e.get("process_pid") is not None]
            uniq_pids = sorted(set(pids))
            if uniq_pids and (len(uniq_pids) > 1 or uniq_pids[0] != os.getpid()):
                print(f"  -> pid(s) observed for this call: {uniq_pids}")
            for e in events_sorted:
                ev = e.get("event")
                payload = e.get("payload")
                ts = e.get("timestamp")
                header = f"  - {ev} @ {_fmt_ts(ts)}"
                print(header)
                if payload is not None:
                    # If payload contains result and it's multiline, print indented block
                    if isinstance(payload, dict) and "result" in payload:
                        # print other keys first
                        for k, v in payload.items():
                            if k == "result":
                                continue
                            print(f"      {k}: {json.dumps(v, ensure_ascii=False)}")
                        print("      result:")
                        # print multiline result safely
                        res_text = payload.get("result")
                        for line in str(res_text).splitlines():
                            print(f"        {line}")
                    else:
                        print(f"    payload: {json.dumps(payload, ensure_ascii=False)}")
            print()

    # final AI message(s)
    print("--- Final result ---")
    # try to extract assistant text from live result object first
    printed = False
    try:
        if hasattr(result, "messages"):
            msgs = getattr(result, "messages")
            for m in msgs:
                # try to access content attribute or dict
                content = None
                role = None
                if hasattr(m, "content"):
                    content = getattr(m, "content")
                elif isinstance(m, dict):
                    content = m.get("content") or m.get("text")
                    role = m.get("role")
                if role is None:
                    role = getattr(m, "type", None) or getattr(m, "role", "message")
                if content is not None:
                    print(f"[{role}]\n{content}\n")
                    printed = True
        # if not printed, try serializable dict
        if not printed and isinstance(serializable, dict) and "messages" in serializable:
            for m in serializable["messages"]:
                if isinstance(m, dict):
                    role = m.get("role") or m.get("type") or "message"
                    content = m.get("content") or m.get("text") or ""
                    print(f"[{role}]\n{content}\n")
                    printed = True
    except Exception:
        printed = False

    if not printed:
        # fallback: try to extract readable parts from a string result
        if isinstance(serializable, str):
            import re

            # try to extract triple-backtick code block
            m = re.search(r"```(?:.*?\n)?(.*?)```", serializable, re.DOTALL)
            if m:
                print(m.group(1))
            else:
                # try to extract AIMessage(content='...') pattern
                m2 = re.search(r"AIMessage\(content=(?P<q>['\"]).*?(?P=q)\)", serializable, re.DOTALL)
                if m2:
                    # capture inside the quotes
                    inner = re.search(r"AIMessage\(content=(?P<q>['\"]).*?(?P=q)\)", serializable, re.DOTALL)
                    if inner:
                        # extract the quoted content
                        quote = inner.group("q")
                        pat = r"AIMessage\(content=" + quote + r"(?P<c>.*?)" + quote + r"\)"
                        found = re.search(pat, serializable, re.DOTALL)
                        if found:
                            content = found.group("c")
                            try:
                                content = content.encode("utf-8").decode("unicode_escape")
                            except Exception:
                                pass
                            print(content)
                            
                        else:
                            print(serializable)
                    else:
                        print(serializable)
                else:
                    print(serializable)
        elif isinstance(serializable, (dict, list)):
            print(json.dumps(serializable, ensure_ascii=False, indent=2))
        else:
            print(serializable)


if __name__ == "__main__":
    main()
