"""Async MCP client built on ``fastmcp.Client``.

Spawns a local server script over stdio, or connects to a remote server
over Streamable HTTP::

    async with MCPClient(script="mcp_server.py") as client:
        tools = await client.list_tools()

    async with MCPClient(url="http://localhost:8000/mcp") as client:
        tools = await client.list_tools()
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

from fastmcp import Client
from fastmcp.client.transports import PythonStdioTransport, StreamableHttpTransport

logger = logging.getLogger(__name__)


class MCPToolError(RuntimeError):
    """Raised when a tool call returns an error result."""


def _blocks_to_text(content: list[Any]) -> str:
    """Flatten MCP content blocks into plain text."""
    parts: list[str] = []
    for block in content:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
        else:
            data = getattr(block, "data", None)
            if data is not None:
                parts.append(json.dumps(data))
            else:
                parts.append(f"[{type(block).__name__}]")
    return "\n".join(parts)


class MCPClient:
    """Thin async wrapper around :class:`fastmcp.Client`."""

    def __init__(
        self,
        script: str | Path | None = None,
        url: str | None = None,
        env: Optional[dict[str, str]] = None,
        cwd: Optional[str | Path] = None,
    ) -> None:
        if url:
            self._transport = StreamableHttpTransport(url)
            self._label = url
        elif script is not None:
            self._transport = PythonStdioTransport(
                script_path=Path(script),
                env=env,
                cwd=str(cwd) if cwd else None,
            )
            self._label = str(script)
        else:
            raise ValueError("MCPClient needs either a server script or a URL.")
        self._client: Client | None = None

    async def __aenter__(self) -> "MCPClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.cleanup()

    async def connect(self) -> "MCPClient":
        """Open the connection to the MCP server."""
        self._client = Client(self._transport)
        await self._client.__aenter__()
        logger.info("Connected to MCP server: %s", self._label)
        return self

    async def cleanup(self) -> None:
        """Close the connection to the MCP server."""
        if self._client is not None:
            await self._client.__aexit__(None, None, None)
            self._client = None
            logger.info("Disconnected from MCP server: %s", self._label)

    def _require(self) -> Client:
        if self._client is None:
            raise ConnectionError(
                "MCP client is not connected. Use 'async with MCPClient(...)' "
                "or call connect() first."
            )
        return self._client

    async def list_tools(self) -> list[Any]:
        """List the tools exposed by the server."""
        return await self._require().list_tools()

    async def call_tool(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """Call a tool and return its result as text.

        Raises :class:`MCPToolError` if the server reports a tool error.
        """
        try:
            result = await self._require().call_tool(tool_name, tool_input)
        except Exception as exc:
            raise MCPToolError(f"Tool {tool_name} failed: {exc}") from exc
        text = _blocks_to_text(result.content)
        if result.is_error:
            raise MCPToolError(text or f"Tool {tool_name} failed.")
        # Surface structured output alongside the text when present.
        if result.structured_content:
            text = (
                f"{text}\n{json.dumps(result.structured_content)}"
                if text
                else json.dumps(result.structured_content)
            )
        return text

    async def list_prompts(self) -> list[Any]:
        """List the prompts exposed by the server."""
        return await self._require().list_prompts()

    async def get_prompt(self, prompt_name: str, args: dict[str, str]) -> list[Any]:
        """Render a server prompt and return its messages."""
        result = await self._require().get_prompt(prompt_name, args)
        return result.messages

    async def list_resources(self) -> list[Any]:
        """List the resources exposed by the server."""
        return await self._require().list_resources()

    async def read_resource(self, uri: str) -> Any:
        """Read a resource. JSON resources are parsed, others returned as text."""
        contents = await self._require().read_resource(uri)
        if not contents:
            raise ValueError(f"Resource {uri} returned no content.")
        resource = contents[0]
        text = getattr(resource, "text", None)
        if text is None:
            raise ValueError(f"Resource {uri} has no text content.")
        if getattr(resource, "mime_type", None) == "application/json":
            return json.loads(text)
        return text
