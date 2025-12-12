"""
MCP Multi-Server Client Manager

A clean architecture for managing multiple simultaneous MCP server connections.
"""

import asyncio
import sys
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
from contextlib import asynccontextmanager
import os

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import Tool, CallToolResult
import mcp.types as mcp_types


@dataclass
class ServerConfig:
    """Configuration for an MCP server."""
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] | None = None
    
    def to_stdio_params(self) -> StdioServerParameters:
        return StdioServerParameters(
            command=self.command,
            args=self.args,
            env={**os.environ, **(self.env or {})},
        )


@dataclass
class ServerConnection:
    """Holds an active connection to an MCP server."""
    config: ServerConfig
    session: ClientSession
    tools: list[Tool] = field(default_factory=list)
    
    async def refresh_tools(self) -> list[Tool]:
        """Refresh the cached tool list."""
        result = await self.session.list_tools()
        self.tools = result.tools
        return self.tools
    
    async def call_tool(self, name: str, arguments: dict[str, Any] = None) -> CallToolResult:
        """Call a tool on this server."""
        return await self.session.call_tool(name, arguments or {})


class MCPClientManager:
    """
    Manages multiple persistent MCP server connections.
    
    Usage:
        async with MCPClientManager() as manager:
            await manager.connect("atlassian", "mcp-atlassian")
            await manager.connect("github", "mcp-github")
            
            # Call tools
            result = await manager.call_tool("atlassian", "search_issues", {"query": "..."})
            
            # Or get session directly
            session = manager.get_session("github")
            await session.call_tool(...)
    """
    
    def __init__(self, log_callback: Optional[Callable[[str, str, Optional[str], Optional[str]], None]] = None):
        self._connections: dict[str, ServerConnection] = {}
        self._contexts: list[Any] = [] # Track context managers for cleanup
        self._task_group = None
        self._log_callback = log_callback

    def _log(self, level: str, event: str, server: Optional[str] = None, details: Optional[str] = None):
        """Log an event if a callback is configured."""
        if self._log_callback:
            self._log_callback(level, event, server, details)
    
    @property
    def servers(self) -> list[str]:
        """List of connected server names."""
        return list(self._connections.keys())
    
    def get_connection(self, name: str) -> ServerConnection:
        """Get a server connection by name."""
        if name not in self._connections:
            raise KeyError(f"Server '{name}' not connected")
        return self._connections[name]
    
    def get_session(self, name: str) -> ClientSession:
        """Get a session by server name."""
        return self.get_connection(name).session
    
    async def connect(
        self,
        name: str,
        command: str,
        args: list[str] = None,
        env: dict[str, str] = None,
    ) -> ServerConnection:
        """
        Connect to an MCP server.
        
        Args:
            name: Unique identifier for this connection
            command: Command to run the server
            args: Command arguments
            env: Additional environment variables
        """
        if name in self._connections:
            raise ValueError(f"Server '{name}' already connected")

        config = ServerConfig(
            name=name,
            command=command,
            args=args or [],
            env=env,
        )

        self._log('DEBUG', f"Creating stdio_client: {command} {' '.join(str(a) for a in (args or []))}", server=name)

        # Enter the stdio_client context
        stdio_ctx = stdio_client(config.to_stdio_params())
        read, write = await stdio_ctx.__aenter__()
        self._contexts.append(stdio_ctx)

        self._log('DEBUG', 'stdio_client entered', server=name)

        # Enter the session context
        session_ctx = ClientSession(read, write)
        session = await session_ctx.__aenter__()
        self._contexts.append(session_ctx)

        self._log('DEBUG', 'ClientSession entered', server=name)

        # Initialize the session with protocol version negotiation
        try:
            # Get client protocol version info
            client_version = getattr(mcp_types, 'LATEST_PROTOCOL_VERSION', 'unknown')
            supported_versions = getattr(mcp_types, 'SUPPORTED_PROTOCOL_VERSIONS', [])

            self._log('INFO', f'Negotiating protocol version', server=name,
                     details=f'client={client_version}, supported={supported_versions}')

            result = await session.initialize()

            # Log successful negotiation with server version and capabilities
            server_version = result.protocolVersion if hasattr(result, 'protocolVersion') else 'unknown'
            server_caps = result.capabilities if hasattr(result, 'capabilities') else None

            self._log('INFO', f'Protocol negotiation successful', server=name,
                     details=f'server_version={server_version}, capabilities={server_caps}')

        except RuntimeError as e:
            # Version mismatch - this is likely the cause of connection cycling!
            error_msg = str(e)
            if 'protocol version' in error_msg.lower():
                self._log('ERROR', 'PROTOCOL VERSION MISMATCH DETECTED', server=name,
                         details=f'{error_msg} (client supports: {supported_versions})')
            raise
        except Exception as e:
            self._log('ERROR', f'Session initialization failed', server=name,
                     details=f'{type(e).__name__}: {e}')
            raise

        self._log('DEBUG', 'Session initialized', server=name)

        # Create connection object
        connection = ServerConnection(config=config, session=session)
        await connection.refresh_tools()

        self._connections[name] = connection
        self._log('INFO', f'Connection established ({len(connection.tools)} tools)', server=name)
        return connection
    
    async def disconnect(self, name: str) -> None:
        """Disconnect from a specific server."""
        if name not in self._connections:
            return
        
        # Note: proper cleanup requires tracking contexts per-connection
        # This simplified version just removes from registry
        del self._connections[name]
    
    async def call_tool(
        self,
        server: str,
        tool_name: str,
        arguments: dict[str, Any] = None,
    ) -> CallToolResult:
        """Call a tool on a specific server."""
        return await self.get_connection(server).call_tool(tool_name, arguments)
    
    async def find_tool(self, tool_name: str) -> tuple[str, Tool] | None:
        """Find which server has a given tool."""
        for name, conn in self._connections.items():
            for tool in conn.tools:
                if tool.name == tool_name:
                    return (name, tool)
        return None
    
    async def call_tool_auto(
        self,
        tool_name: str,
        arguments: dict[str, Any] = None,
    ) -> CallToolResult:
        """Call a tool, automatically finding which server has it."""
        result = await self.find_tool(tool_name)
        if not result:
            raise ValueError(f"Tool '{tool_name}' not found on any server")
        server_name, _ = result
        return await self.call_tool(server_name, tool_name, arguments)
    
    def all_tools(self) -> dict[str, list[Tool]]:
        """Get all tools from all servers."""
        return {name: conn.tools for name, conn in self._connections.items()}
    
    async def __aenter__(self) -> "MCPClientManager":
        self._log('DEBUG', 'MCPClientManager __aenter__ called')
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        # Close all contexts in reverse order with proper cleanup
        # On Windows, subprocess cleanup needs special handling to avoid pipe errors

        self._log('DEBUG', f'MCPClientManager __aexit__ called (exc_type={exc_type}, {len(self._connections)} connections)')

        # Give pending operations a chance to complete
        try:
            await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass  # Event loop may be shutting down

        # Cancel any pending tasks in the current event loop
        if sys.version_info >= (3, 11):
            try:
                tasks = [t for t in asyncio.all_tasks() if not t.done()]
                if tasks:
                    self._log('DEBUG', f'Cancelling {len(tasks)} pending tasks')
                    for task in tasks:
                        task.cancel()
                    # Wait briefly for cancellation to complete
                    await asyncio.sleep(0.05)
            except (Exception, asyncio.CancelledError):
                pass  # Ignore errors during task cleanup

        # Close all contexts in reverse order
        self._log('DEBUG', f'Closing {len(self._contexts)} contexts')
        for idx, ctx in enumerate(reversed(self._contexts)):
            try:
                self._log('DEBUG', f'Closing context {idx+1}/{len(self._contexts)}')
                await ctx.__aexit__(exc_type, exc_val, exc_tb)
            except (Exception, asyncio.CancelledError) as e:
                # Silently ignore cleanup errors - they're typically just
                # resource warnings from subprocess cleanup on Windows
                self._log('DEBUG', f'Context cleanup error (ignored): {e}')
                pass

        # On Windows, give subprocess transports time to finish cleanup
        if sys.platform == 'win32':
            try:
                await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                pass  # Event loop may be shutting down

        self._contexts.clear()
        self._connections.clear()
        self._log('DEBUG', 'MCPClientManager __aexit__ complete')

