"""MCP server implementation for Code Atlas.

Provides Model Context Protocol server to enable integration with Claude Desktop
and other MCP clients.
"""

from __future__ import annotations

from typing import Any

from ..logging_config import get_logger

logger = get_logger(__name__)

# MCP protocol implementation using official SDK
try:
    from mcp.server import Server
    from mcp.types import Resource, Tool
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    Server = None  # type: ignore[misc,assignment]
    logger.warning("MCP SDK not available. Install with: uv add mcp")


class MCPServer:
    """MCP server for Code Atlas integration."""

    def __init__(
        self,
        graph_populator: Any,
        resource_manager: Any,
        tool_manager: Any,
    ) -> None:
        """Initialize MCP server.

        Args:
            graph_populator: GraphPopulator instance for graph operations.
            resource_manager: ResourceManager instance for resources.
            tool_manager: ToolManager instance for tools.
        """
        if not MCP_AVAILABLE:
            raise ImportError(
                "MCP SDK not available. Install with: uv add mcp"
            )

        self.graph = graph_populator
        self.resource_manager = resource_manager
        self.tool_manager = tool_manager
        self.server = Server("code-atlas")

        self._setup_handlers()

        logger.info("MCP server initialized")

    def _setup_handlers(self) -> None:
        """Register handlers with MCP server using decorator pattern."""

        @self.server.list_resources()
        async def handle_list_resources() -> list[Resource]:
            """List all available resources."""
            resources = await self.resource_manager.list_all()
            return [
                Resource(
                    uri=r.get("uri", ""),
                    name=r.get("name", ""),
                    description=r.get("description"),
                    mimeType=r.get("mimeType", "application/json"),
                )
                for r in resources
            ]

        @self.server.read_resource()
        async def handle_read_resource(uri: str) -> str:
            """Read a specific resource."""
            result = await self.resource_manager.get(uri)
            return str(result)

        @self.server.list_tools()
        async def handle_list_tools() -> list[Tool]:
            """List all available tools."""
            tools = await self.tool_manager.list_all()
            return [
                Tool(
                    name=t.get("name", ""),
                    description=t.get("description"),
                    inputSchema=t.get("inputSchema", {}),
                )
                for t in tools
            ]

        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: dict[str, Any]) -> list[Any]:
            """Execute a tool."""
            result = await self.tool_manager.call(name, arguments)
            return [result]

    async def run(self, stdio: bool = True) -> None:
        """Run MCP server.

        Args:
            stdio: If True, use stdio transport. If False, use HTTP.
        """
        if stdio:
            # Run with stdio transport (for Claude Desktop)
            from mcp.server.stdio import stdio_server

            async with stdio_server() as (read_stream, write_stream):
                await self.server.run(
                    read_stream,
                    write_stream,
                    self.server.create_initialization_options(),
                )
        else:
            # HTTP transport not yet implemented
            raise NotImplementedError("HTTP transport not yet implemented")
