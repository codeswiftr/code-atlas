"""Tests for MCP server integration."""

import pytest
from unittest.mock import MagicMock, AsyncMock

from code_atlas.mcp.server import MCP_AVAILABLE, MCPServer


@pytest.mark.skipif(not MCP_AVAILABLE, reason="MCP SDK not installed")
class TestMCPServerInitialization:
    """Tests for MCP server initialization."""

    def test_mcp_sdk_is_available(self):
        """MCP SDK should be installed and importable."""
        assert MCP_AVAILABLE is True

    def test_mcp_server_import_works(self):
        """Server class can be imported from mcp.server."""
        from mcp.server import Server
        assert Server is not None

    def test_mcp_types_import_works(self):
        """MCP types can be imported."""
        from mcp.types import Resource, Tool
        assert Resource is not None
        assert Tool is not None


@pytest.mark.skipif(not MCP_AVAILABLE, reason="MCP SDK not installed")
class TestMCPServerCreation:
    """Tests for creating MCP server instance."""

    def test_mcp_server_requires_dependencies(self):
        """MCPServer requires graph_populator, resource_manager, tool_manager."""
        # Should raise error without required dependencies
        with pytest.raises(TypeError):
            MCPServer()  # type: ignore[call-arg]

    def test_mcp_server_initializes_with_dependencies(self):
        """MCPServer initializes when all dependencies provided."""
        mock_graph = MagicMock()
        mock_resources = MagicMock()
        mock_tools = MagicMock()

        # This should not raise
        server = MCPServer(
            graph_populator=mock_graph,
            resource_manager=mock_resources,
            tool_manager=mock_tools,
        )

        assert server.graph == mock_graph
        assert server.resource_manager == mock_resources
        assert server.tool_manager == mock_tools


class TestMCPToolDefinitions:
    """Tests for MCP tool definitions."""

    def test_tools_module_exists(self):
        """Tools module should exist and be importable."""
        from code_atlas.mcp import tools
        assert tools is not None

    def test_resources_module_exists(self):
        """Resources module should exist and be importable."""
        from code_atlas.mcp import resources
        assert resources is not None


class TestMCPWithoutSDK:
    """Tests for graceful degradation without MCP SDK."""

    def test_mcp_available_flag_exists(self):
        """MCP_AVAILABLE flag should always be defined."""
        from code_atlas.mcp.server import MCP_AVAILABLE
        assert isinstance(MCP_AVAILABLE, bool)
