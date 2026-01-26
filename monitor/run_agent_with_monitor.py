"""Run the code agent with monitoring callbacks without modifying main.py."""
from __future__ import annotations

import argparse

from code_agent.agent import build_agent

from monitor.langgraph_monitor import AgentEventLogger


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run code agent with callbacks")
    parser.add_argument(
        "prompt",
        nargs="?",
        default="请读取 README.md 并总结项目用途。",
        help="User prompt to send to the agent.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    app = build_agent()
    handler = AgentEventLogger(capture_messages=True)
    result = app.invoke({"messages": [{"role": "user", "content": args.prompt}]}, config={"callbacks": [handler]})

    print("=== Result ===")
    print(result)
    print("\n=== Captured events ===")
    for event in handler.events:
        print(event.event, event.payload)


if __name__ == "__main__":
    main()
