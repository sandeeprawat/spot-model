"""Tool registry for discovering and managing available tools."""

from __future__ import annotations

from typing import Any

from spot_agent.logging import get_logger
from spot_agent.tools.base import BaseTool

log = get_logger(__name__)


class ToolRegistry:
    """Registry for managing and discovering agent tools."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool in the registry."""
        if tool.name in self._tools:
            log.warning("tool_overwritten", name=tool.name)
        self._tools[tool.name] = tool
        log.info("tool_registered", name=tool.name)

    def unregister(self, name: str) -> None:
        """Remove a tool from the registry."""
        if name in self._tools:
            del self._tools[name]
            log.info("tool_unregistered", name=name)

    def get_tool(self, name: str) -> BaseTool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[BaseTool]:
        """List all registered tools."""
        return list(self._tools.values())

    def get_tool_names(self) -> list[str]:
        """Get names of all registered tools."""
        return list(self._tools.keys())

    def get_openai_tools(self) -> list[dict[str, Any]]:
        """Get all tools in OpenAI function calling format."""
        return [tool.to_openai_tool() for tool in self._tools.values()]

    def register_builtin_tools(self) -> None:
        """Register all built-in tools."""
        from spot_agent.tools.builtin.code_executor import CodeExecutorTool
        from spot_agent.tools.builtin.file_ops import FileOpsTool
        from spot_agent.tools.builtin.shell import ShellTool
        from spot_agent.tools.builtin.web_search import WebSearchTool

        self.register(CodeExecutorTool())
        self.register(FileOpsTool())
        self.register(ShellTool())
        self.register(WebSearchTool())
        log.info("builtin_tools_registered", count=len(self._tools))
