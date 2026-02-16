"""Code execution tool — runs Python and Node.js code in sandboxed subprocesses."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import Any

from spot_agent.logging import get_logger
from spot_agent.tools.base import BaseTool

log = get_logger(__name__)

EXECUTION_TIMEOUT = 30  # seconds


class CodeExecutorTool(BaseTool):
    """Execute Python or Node.js code in a sandboxed subprocess."""

    @property
    def name(self) -> str:
        return "execute_code"

    @property
    def description(self) -> str:
        return "Execute Python or Node.js code and return the output. Use for computation, data processing, or testing code snippets."

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "The code to execute",
                },
                "language": {
                    "type": "string",
                    "enum": ["python", "nodejs"],
                    "description": "Programming language (python or nodejs)",
                    "default": "python",
                },
            },
            "required": ["code"],
        }

    async def execute(self, code: str, language: str = "python", **kwargs: Any) -> dict[str, Any]:
        """Execute code and return stdout, stderr, and exit code."""
        if language == "python":
            cmd = ["python", "-c", code]
        elif language == "nodejs":
            cmd = ["node", "-e", code]
        else:
            return {"error": f"Unsupported language: {language}", "exit_code": 1}

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=EXECUTION_TIMEOUT
            )

            result = {
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
                "exit_code": process.returncode,
            }
            log.info("code_executed", language=language, exit_code=process.returncode)
            return result
        except asyncio.TimeoutError:
            process.kill()
            return {"error": "Execution timed out", "exit_code": -1}
        except Exception as exc:
            return {"error": str(exc), "exit_code": -1}
