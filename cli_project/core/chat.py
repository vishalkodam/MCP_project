from anthropic.types import MessageParam

from core.claude import Claude
from core.tools import ToolManager
from mcp_client import MCPClient


class Chat:
    def __init__(
        self,
        claude_service: Claude,
        clients: dict[str, MCPClient],
        max_iterations: int = 10,
    ):
        self.claude_service: Claude = claude_service
        self.clients: dict[str, MCPClient] = clients
        self.messages: list[MessageParam] = []
        self.max_iterations = max_iterations

    async def _process_query(self, query: str):
        self.messages.append({"role": "user", "content": query})

    async def run(
        self,
        query: str,
        system: str | None = None,
    ) -> str:
        await self._process_query(query)

        for _ in range(self.max_iterations):
            response = self.claude_service.chat(
                messages=self.messages,
                tools=await ToolManager.get_all_tools(self.clients),
                system=system,
            )

            self.claude_service.add_assistant_message(self.messages, response)

            if response.stop_reason == "tool_use":
                print(self.claude_service.text_from_message(response))
                tool_result_parts = await ToolManager.execute_tool_requests(self.clients, response)

                self.claude_service.add_user_message(self.messages, tool_result_parts)
            else:
                return self.claude_service.text_from_message(response)

        raise RuntimeError(f"Model did not finish within {self.max_iterations} tool iterations.")
