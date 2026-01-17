from __future__ import annotations

import argparse
import json

from code_agent.agent import build_agent


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LangGraph code agent demo")
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
    result = app.invoke(
        {"messages": [{"role": "user", "content": args.prompt}]}
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
