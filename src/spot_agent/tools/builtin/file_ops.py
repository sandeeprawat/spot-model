"""File operations tool — read, write, and list files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from spot_agent.logging import get_logger
from spot_agent.tools.base import BaseTool

log = get_logger(__name__)


class FileOpsTool(BaseTool):
    """Read, write, and list files on the filesystem."""

    @property
    def name(self) -> str:
        return "file_ops"

    @property
    def description(self) -> str:
        return "Perform file operations: read, write, append, or list files and directories."

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["read", "write", "append", "list"],
                    "description": "The file operation to perform",
                },
                "path": {
                    "type": "string",
                    "description": "File or directory path",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write (for write/append operations)",
                },
            },
            "required": ["operation", "path"],
        }

    async def execute(self, operation: str, path: str, content: str = "", **kwargs: Any) -> dict[str, Any]:
        """Execute a file operation."""
        target = Path(path)

        try:
            if operation == "read":
                if not target.exists():
                    return {"error": f"File not found: {path}"}
                text = target.read_text(encoding="utf-8")
                return {"content": text, "size": len(text)}

            elif operation == "write":
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
                return {"written": len(content), "path": str(target)}

            elif operation == "append":
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("a", encoding="utf-8") as f:
                    f.write(content)
                return {"appended": len(content), "path": str(target)}

            elif operation == "list":
                if not target.exists():
                    return {"error": f"Path not found: {path}"}
                if target.is_file():
                    return {"entries": [str(target)], "type": "file"}
                entries = [str(p) for p in sorted(target.iterdir())]
                return {"entries": entries, "count": len(entries)}

            else:
                return {"error": f"Unknown operation: {operation}"}

        except Exception as exc:
            log.error("file_ops_error", operation=operation, path=path, error=str(exc))
            return {"error": str(exc)}
