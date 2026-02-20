"""MCP (Model Context Protocol) server integration for Code Atlas.

Enables Code Atlas to be accessed from Claude Desktop and other MCP clients.
"""

from .resources import ResourceManager
from .server import MCPServer
from .tools import ToolManager

__all__ = ["MCPServer", "ResourceManager", "ToolManager"]
