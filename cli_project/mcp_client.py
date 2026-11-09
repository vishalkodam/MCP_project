"""Async MCP client built on ``fastmcp.Client``.

Spawns a local server script over stdio, or connects to a remote server
over Streamable HTTP::

    async with MCPClient(script="mcp_server.py") as client:
        tools = await client.list_tools()

    async with MCPClient(url="http://localhost:8000/mcp") as client:
        tools = await client.list_tools()
"""

from __future__ import annotations

import asyncio
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
    """Thin async wrapper around :class:`fastmcp.Client`.

    ``connect()`` retries with exponential backoff when the server
    subprocess fails to spawn (or an HTTP endpoint is briefly
    unreachable): ``max_retries`` extra attempts after the first,
    waiting ``retry_backoff * 2 ** attempt`` seconds between attempts.
    """

    def __init__(
        self,
        script: str | Path | None = None,
        url: str | None = None,
        env: Optional[dict[str, str]] = None,
        cwd: Optional[str | Path] = None,
        max_retries: int = 3,
        retry_backoff: float = 0.5,
    ) -> None:
        if url:
            self._url = url
            self._script: Path | None = None
            self._label = url
        elif script is not None:
            self._url = None
            self._script = Path(script)
            self._label = str(script)
        else:
            raise ValueError("MCPClient needs either a server script or a URL.")
        self._env = env
        self._cwd = cwd
        self._max_retries = max_retries
        self._retry_backoff = retry_backoff
        self._transport = self._make_transport()
        self._client: Client | None = None

    def _make_transport(self) -> PythonStdioTransport | StreamableHttpTransport:
        """Build a fresh transport (a new subprocess per spawn attempt)."""
        if self._url:
            return StreamableHttpTransport(self._url)
        assert self._script is not None
        return PythonStdioTransport(
            script_path=self._script,
            env=self._env,
            cwd=str(self._cwd) if self._cwd else None,
        )

    async def __aenter__(self) -> "MCPClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.cleanup()

    async def connect(self) -> "MCPClient":
        """Open the connection to the MCP server.

        Retries with exponential backoff when the server subprocess fails
        to spawn (or the HTTP connect fails): ``max_retries`` extra
        attempts after the first, waiting ``retry_backoff * 2 ** attempt``
        seconds between attempts. Each attempt builds a fresh transport so
        a failed spawn never leaves a stale subprocess behind. The last
        error is re-raised once retries are exhausted.
        """
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            self._transport = self._make_transport()
            client = Client(self._transport)
            try:
                await client.__aenter__()
            except Exception as exc:
                last_error = exc
                try:
                    await client.__aexit__(None, None, None)
                except Exception:
                    pass
                if attempt == self._max_retries:
                    break
                delay = self._retry_backoff * (2**attempt)
                logger.warning(
                    "Connect to %s failed (attempt %d/%d): %s — retrying in %.1fs",
                    self._label,
                    attempt + 1,
                    self._max_retries + 1,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)
                continue
            self._client = client
            logger.info("Connected to MCP server: %s", self._label)
            return self
        assert last_error is not None
        raise last_error

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
