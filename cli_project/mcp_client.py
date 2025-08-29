import sys
import os
import asyncio
from typing import Optional, Any
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client


class MCPClient:
    def __init__(
        self,
        command: str,
        args: list[str],
        env: Optional[dict] = None,
    ):
        self._command = command
        self._args = args
        self._env = env
        self._session: Optional[ClientSession] = None
        self._exit_stack: AsyncExitStack = AsyncExitStack()

    async def connect(self):
        server_params = StdioServerParameters(
            command=self._command,
            args=self._args,
            env=self._env,
        )
        stdio_transport = await self._exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        _stdio, _write = stdio_transport
        self._session = await self._exit_stack.enter_async_context(
            ClientSession(_stdio, _write)
        )
        await self._session.initialize()

    def session(self) -> ClientSession:
        if self._session is None:
            raise ConnectionError(
                "Client session not initialized or cache not populated. Call connect_to_server first."
            )
        return self._session

    async def list_tools(self) -> list[types.Tool]:
        result = await self.session().list_tools()
        return result.tools

    async def call_tool(
        self, tool_name: str, tool_input: dict
    ) -> types.CallToolResult | None:
        result = await self.session().call_tool(tool_name, tool_input)
        return result

    async def list_prompts(self) -> list[types.Prompt]:
        # TODO: Return a list of prompts defined by the MCP server
        return []


    async def get_prompt(self, prompt_name, args: dict[str, str]):
        # TODO: Get a particular prompt defined by the MCP server
        return []

    async def read_resource(self, uri: str) -> Any:
        # TODO: Read a resource, parse the contents and return it
        return []

    async def cleanup(self):
        try:
            if self._session is not None and hasattr(self._session, "close"):
                maybe_close = self._session.close()
                if asyncio.iscoroutine(maybe_close):
                    await maybe_close
        finally:
            await self._exit_stack.aclose()
            self._session = None
        
        # On Windows, give transports time to close properly to avoid __del__ warnings
        if sys.platform == "win32":
            # Force garbage collection to clean up transport objects
            import gc
            gc.collect()
            await asyncio.sleep(0.1)

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()


# For testing
async def main():
    use_uv = os.getenv("USE_UV", "0") == "1"
    command, args = ("uv", ["run", "mcp_server.py"]) if use_uv else ("python", ["mcp_server.py"]) 
    async with MCPClient(
        command=command,
        args=args,
    ) as _client:
        result = await _client.list_tools()
        print(result)

if __name__ == "__main__":
    if sys.platform == "win32":
        # Proactor policy is required for subprocess support on Windows
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
