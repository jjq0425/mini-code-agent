"""Sandbox MCP server for running limited Python code."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP


DEFAULT_SANDBOX_ROOT = Path(__file__).resolve().parent / "sandbox"


def _sandbox_root() -> Path:
    root = Path(os.environ.get("SANDBOX_ROOT", DEFAULT_SANDBOX_ROOT)).expanduser()
    return root.resolve()


mcp = FastMCP("sandbox-mcp", host="127.0.0.1", port=9000)


@mcp.tool()
def run_python(code: str, timeout_s: int = 5) -> dict[str, Any]:
    """Run python3 code inside the sandbox root with a timeout."""
    root = _sandbox_root()
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".py", dir=root, delete=False) as handle:
        handle.write(code)
        script_path = Path(handle.name)

    try:
        result = subprocess.run(
            ["python3", str(script_path)],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            env={
                "PYTHONUTF8": "1",
                "PATH": os.environ.get("PATH", ""),
            },
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "exit_code": None,
            "timed_out": True,
        }
    finally:
        if script_path.exists():
            script_path.unlink()


if __name__ == "__main__":
    _sandbox_root().mkdir(parents=True, exist_ok=True)
    print("Starting Sandbox MCP server")
    mcp.run()
    print("Sandbox MCP server stopped.")
