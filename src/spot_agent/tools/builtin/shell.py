"""Shell command execution tool."""

from __future__ import annotations

import asyncio
from typing import Any

from spot_agent.logging import get_logger
from spot_agent.tools.base import BaseTool

log = get_logger(__name__)

SHELL_TIMEOUT = 60  # seconds


class ShellTool(BaseTool):
    """Execute shell commands."""

    @property
    def name(self) -> str:
        return "shell"

    @property
    def description(self) -> str:
        return "Execute a shell command and return stdout, stderr, and exit code. Use for system tasks, git operations, package management, etc."

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute",
                },
                "working_dir": {
                    "type": "string",
                    "description": "Working directory for the command (optional)",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (default: 60)",
                    "default": 60,
                },
            },
            "required": ["command"],
        }

    async def execute(self, command: str, working_dir: str | None = None, timeout: int = SHELL_TIMEOUT, **kwargs: Any) -> dict[str, Any]:
        """Execute a shell command."""
        log.info("shell_executing", command=command[:100])

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )

            result = {
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
                "exit_code": process.returncode,
            }
            log.info("shell_completed", exit_code=process.returncode)
            return result
        except asyncio.TimeoutError:
            process.kill()
            return {"error": f"Command timed out after {timeout}s", "exit_code": -1}
        except Exception as exc:
            return {"error": str(exc), "exit_code": -1}
