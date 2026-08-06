# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""System tool: execute bash commands inside the container sandbox."""

import subprocess  # nosec B404

from langchain_core.tools import tool


@tool
def execute_bash_command(command: str) -> str:
    """Execute a bash command inside the container and return stdout and stderr."""
    forbidden = ["rm -rf /", ":(){ :|:& };:"]
    if any(f in command for f in forbidden):
        return "Error: command blocked for security reasons."

    try:
        result = subprocess.run(  # nosec B602
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
        out = result.stdout or result.stderr
        return out if out else "Command executed successfully (no output)."
    except Exception as e:
        return f"Error executing command: {e}"
