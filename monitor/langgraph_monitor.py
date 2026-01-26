"""Utilities to monitor LangGraph agent runs with callbacks."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

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

    def _record(self, event: str, payload: dict[str, Any]) -> None:
        self.events.append(AgentEvent(event=event, payload=payload))

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[BaseMessage]],
        **kwargs: Any,
    ) -> None:
        payload = {"model": serialized.get("name") or serialized.get("id")}
        if self.capture_messages:
            payload["messages"] = [[m.dict() for m in batch] for batch in messages]
        if kwargs:
            payload["params"] = kwargs
        self._record("chat_model_start", payload)

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        **kwargs: Any,
    ) -> None:
        payload = {
            "tool": serialized.get("name") or serialized.get("id"),
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
        payload = {
            "chain": serialized.get("name") or serialized.get("id"),
            "inputs": inputs,
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
