"""MCP service — reads and manages MCP server configurations."""
from typing import Optional

from models.models import MCPServer
from services.claude_config import ClaudeConfigService


class McpService:
    """Manages MCP server configurations from .mcp.json."""

    def __init__(self, config: ClaudeConfigService):
        self.config = config

    def list_all(self) -> list[MCPServer]:
        """Parse .mcp.json and return server list."""
        data = self.config.read_mcp_config()
        servers_data = data.get("mcpServers", {})
        servers: list[MCPServer] = []

        for name, srv in servers_data.items():
            if not isinstance(srv, dict):
                continue
            server = MCPServer(
                name=name,
                type=srv.get("type", "stdio"),
                command=srv.get("command", ""),
                args=srv.get("args", []),
                url=srv.get("url", ""),
                env=srv.get("env", {}),
                enabled=True,  # MCP servers don't have enable/disable in the JSON
            )
            servers.append(server)

        return sorted(servers, key=lambda s: s.name)

    def get_raw_config(self) -> dict:
        """Return the full .mcp.json content (masked)."""
        data = self.config.read_mcp_config()
        from services.security import mask_dict
        return mask_dict(data)

    def save_config(self, data: dict) -> bool:
        """Save the full .mcp.json configuration."""
        return self.config.write_mcp_config(data)
