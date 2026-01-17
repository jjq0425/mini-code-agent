from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Annotated

from langchain_core.tools import tool

WORKSPACE_ROOT = Path.cwd()


def _resolve_path(path: str) -> Path:
    target = (WORKSPACE_ROOT / path).resolve()
    if WORKSPACE_ROOT not in target.parents and target != WORKSPACE_ROOT:
        raise ValueError("Path escapes workspace root.")
    return target


@tool
def read_file(path: Annotated[str, "Relative path to file."]) -> str:
    """Read a text file from the workspace and return its contents."""
    target = _resolve_path(path)
    return target.read_text(encoding="utf-8")


@tool
def write_file(
    path: Annotated[str, "Relative path to file."],
    content: Annotated[str, "File content to write."],
) -> str:
    """Write content to a text file in the workspace."""
    target = _resolve_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"Wrote {len(content)} characters to {path}."


@tool
def run_bash(command: Annotated[str, "Shell command to execute."]) -> str:
    """Run a bash command inside the workspace and return stdout/stderr."""
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


TOOLS = [read_file, write_file, run_bash]
