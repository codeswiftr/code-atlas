"""MCP (Model Context Protocol) server integration for Code Atlas.

Enables Code Atlas to be accessed from Claude Desktop and other MCP clients.
"""

from .server import MCPServer
from .resources import ResourceManager
from .tools import ToolManager

__all__ = ["MCPServer", "ResourceManager", "ToolManager"]
