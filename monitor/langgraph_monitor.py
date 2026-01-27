"""Utilities to monitor LangGraph agent runs with callbacks."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable
import json
import time
import os
from pathlib import Path

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import BaseMessage


@dataclass
class AgentEvent:
    """Simple container for captured agent events."""

    event: str
    payload: dict[str, Any]


@dataclass
class AgentEventLogger(BaseCallbackHandler):
    """Callback handler that records agent events for inspection."""

    events: list[AgentEvent] = field(default_factory=list)
    capture_messages: bool = True

    # per-run persistent log path (initialized in __post_init__)
    _hook_log_path: Path | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        try:
            logs_dir = Path.cwd() / "logs" / "hookLogs"
            logs_dir.mkdir(parents=True, exist_ok=True)
            ts = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime())
            pid = os.getpid()
            filename = f"{ts}-{pid}.jsonl"
            self._hook_log_path = logs_dir / filename
        except Exception as exc:
            print(f"[AgentEventLogger.__post_init__] failed to create hook log path: {exc}")
            self._hook_log_path = None

    def __hash__(self) -> int:  # allow instances to be placed in sets
        return id(self)

    def _record(self, event: str, payload: dict[str, Any]) -> None:
        # keep in-memory record
        self.events.append(AgentEvent(event=event, payload=payload))
        # append to per-run hookLogs file when available
        try:
            path = self._hook_log_path
            if path is None:
                # attempt to lazily initialize if __post_init__ failed
                logs_dir = Path.cwd() / "logs" / "hookLogs"
                logs_dir.mkdir(parents=True, exist_ok=True)
                ts = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime())
                pid = os.getpid()
                filename = f"{ts}-{pid}.jsonl"
                path = logs_dir / filename
                self._hook_log_path = path

            entry = {"event": event, "payload": payload, "timestamp": time.time(), "pid": os.getpid()}
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
        except Exception as exc:
            # do not raise from logger; emit diagnostic to stdout
            print(f"[AgentEventLogger._record] failed to write hookLog to {self._hook_log_path}: {exc}")

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[BaseMessage]],
        **kwargs: Any,
    ) -> None:
        ser = serialized or {}
        payload = {"model": ser.get("name") or ser.get("id")}
        if self.capture_messages and messages:
            try:
                payload["messages"] = [[m.dict() for m in batch] for batch in messages]
            except Exception:
                # best-effort: skip message capture on unexpected shapes
                payload["messages"] = None
        if kwargs:
            payload["params"] = kwargs
        self._record("chat_model_start", payload)

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        **kwargs: Any,
    ) -> None:
        ser = serialized or {}
        payload = {
            "tool": ser.get("name") or ser.get("id"),
            "input": input_str,
        }
        if kwargs:
            payload["params"] = kwargs
        self._record("tool_start", payload)

    def on_tool_end(self, output: Any, **kwargs: Any) -> None:
        payload = {"output": output}
        if kwargs:
            payload["params"] = kwargs
        self._record("tool_end", payload)

    def on_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: dict[str, Any],
        **kwargs: Any,
    ) -> None:
        ser = serialized or {}
        payload = {
            "chain": ser.get("name") or ser.get("id"),
            "inputs": inputs or {},
        }
        if kwargs:
            payload["params"] = kwargs
        self._record("chain_start", payload)

    def on_chain_end(self, outputs: dict[str, Any], **kwargs: Any) -> None:
        payload = {"outputs": outputs}
        if kwargs:
            payload["params"] = kwargs
        self._record("chain_end", payload)


def attach_callbacks(
    graph: Any,
    inputs: dict[str, Any],
    *,
    callbacks: Iterable[BaseCallbackHandler] | None = None,
) -> tuple[Any, list[AgentEvent]]:
    """Invoke a LangGraph graph with callbacks and return results + events."""

    handler = AgentEventLogger()
    callback_list = [handler]
    if callbacks:
        callback_list.extend(callbacks)
    result = graph.invoke(inputs, config={"callbacks": callback_list})
    return result, handler.events
