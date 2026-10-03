"""Bridge between MCP servers and Anthropic's tool-use API.

Collects the tools exposed by every connected MCP server, converts them to
the shape the Anthropic Messages API expects, and routes the model's
``tool_use`` requests back to the owning server.
"""

from __future__ import annotations

import logging
from typing import Any

from anthropic.types import Message, ToolResultBlockParam

logger = logging.getLogger(__name__)


def _tool_schema(tool: Any) -> dict[str, Any]:
    schema = getattr(tool, "input_schema", None)
    if not schema:
        schema = getattr(tool, "inputSchema", None)
    return schema or {"type": "object", "properties": {}}


class ToolManager:
    """Maps MCP tools to Anthropic tool definitions and executes tool calls."""

    @staticmethod
    async def get_all_tools(clients: dict[str, Any]) -> list[dict[str, Any]]:
        """Return every MCP tool as an Anthropic tool definition."""
        tools: list[dict[str, Any]] = []
        for client_id, client in clients.items():
            for tool in await client.list_tools():
                tools.append(
                    {
                        "name": tool.name,
                        "description": tool.description or "",
                        "input_schema": _tool_schema(tool),
                    }
                )
        logger.debug("Collected %d tools from %d MCP client(s).", len(tools), len(clients))
        return tools

    @staticmethod
    async def _owner_map(clients: dict[str, Any]) -> dict[str, Any]:
        """Map tool name -> the client (server) that provides it."""
        owners: dict[str, Any] = {}
        for client_id, client in clients.items():
            for tool in await client.list_tools():
                if tool.name in owners:
                    logger.warning(
                        "Tool %r provided by multiple servers; using the first one.",
                        tool.name,
                    )
                    continue
                owners[tool.name] = client
        return owners

    @staticmethod
    async def execute_tool_requests(
        clients: dict[str, Any], response: Message
    ) -> list[ToolResultBlockParam]:
        """Execute every ``tool_use`` block in a model response.

        Returns Anthropic ``tool_result`` blocks ready to append to the
        conversation.
        """
        owners = await ToolManager._owner_map(clients)
        results: list[ToolResultBlockParam] = []

        for block in response.content:
            if block.type != "tool_use":
                continue

            client = owners.get(block.name)
            if client is None:
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": f"Unknown tool: {block.name}",
                        "is_error": True,
                    }
                )
                continue

            try:
                logger.info("Calling MCP tool %r with %s", block.name, block.input)
                text = await client.call_tool(block.name, block.input or {})
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": text,
                    }
                )
            except Exception as exc:
                logger.exception("MCP tool %r failed", block.name)
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": f"Tool {block.name} failed: {exc}",
                        "is_error": True,
                    }
                )

        return results
