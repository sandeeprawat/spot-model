"""MCP (Model Context Protocol) client for connecting to external tool servers."""

from __future__ import annotations

import json
from typing import Any

from spot_agent.logging import get_logger
from spot_agent.tools.base import BaseTool
from spot_agent.tools.registry import ToolRegistry

log = get_logger(__name__)


class MCPToolWrapper(BaseTool):
    """Wraps an MCP server tool as a BaseTool."""

    def __init__(self, tool_name: str, tool_description: str, tool_schema: dict[str, Any], client: Any) -> None:
        self._name = tool_name
        self._description = tool_description
        self._schema = tool_schema
        self._client = client

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return self._schema

    async def execute(self, **kwargs: Any) -> Any:
        """Execute the MCP tool via the client session."""
        try:
            result = await self._client.call_tool(self._name, kwargs)
            return result
        except Exception as exc:
            log.error("mcp_tool_error", tool=self._name, error=str(exc))
            raise


class MCPClientManager:
    """Manages connections to MCP servers and registers their tools."""

    def __init__(self, server_uris: list[str], registry: ToolRegistry) -> None:
        self._server_uris = server_uris
        self._registry = registry
        self._sessions: list[Any] = []

    async def connect_all(self) -> None:
        """Connect to all configured MCP servers and register their tools."""
        for uri in self._server_uris:
            try:
                await self._connect_server(uri)
            except Exception as exc:
                log.error("mcp_connection_failed", uri=uri, error=str(exc))

    async def _connect_server(self, uri: str) -> None:
        """Connect to a single MCP server."""
        try:
            from mcp import ClientSession
            from mcp.client.stdio import stdio_client, StdioServerParameters

            # Parse URI to determine transport
            if uri.startswith("stdio://"):
                command = uri.removeprefix("stdio://")
                params = StdioServerParameters(command=command, args=[])
                
                async with stdio_client(params) as (read_stream, write_stream):
                    session = ClientSession(read_stream, write_stream)
                    await session.initialize()
                    
                    # List and register tools
                    tools_result = await session.list_tools()
                    for tool in tools_result.tools:
                        wrapper = MCPToolWrapper(
                            tool_name=f"mcp_{tool.name}",
                            tool_description=tool.description or f"MCP tool: {tool.name}",
                            tool_schema=tool.inputSchema if hasattr(tool, 'inputSchema') else {},
                            client=session,
                        )
                        self._registry.register(wrapper)
                    
                    self._sessions.append(session)
                    log.info("mcp_server_connected", uri=uri, tools=len(tools_result.tools))
            else:
                log.warning("unsupported_mcp_transport", uri=uri)
        except ImportError:
            log.warning("mcp_package_not_available")
        except Exception as exc:
            log.error("mcp_connect_error", uri=uri, error=str(exc))
            raise

    async def disconnect_all(self) -> None:
        """Disconnect from all MCP servers."""
        for session in self._sessions:
            try:
                if hasattr(session, 'close'):
                    await session.close()
            except Exception:
                pass
        self._sessions.clear()
        log.info("mcp_sessions_closed")
