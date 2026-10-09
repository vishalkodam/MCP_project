from anthropic.types import MessageParam

from core import usage
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
        self.session_input_tokens = 0
        self.session_output_tokens = 0

    def clear_history(self) -> None:
        """Reset the conversation history, dropping all prior messages."""
        self.messages = []

    async def _process_query(self, query: str):
        self.messages.append({"role": "user", "content": query})

    def _report_turn_usage(self, response) -> None:
        """Print this turn's token usage + cost, and fold it into the session total."""
        turn_in, turn_out = usage.usage_of(response)
        if turn_in == 0 and turn_out == 0:
            return  # no usage info (e.g. test doubles) — nothing to report
        self.session_input_tokens += turn_in
        self.session_output_tokens += turn_out
        model = self.claude_service.model
        turn_cost = usage.estimate_cost(model, turn_in, turn_out)
        session_cost = usage.estimate_cost(
            model, self.session_input_tokens, self.session_output_tokens
        )
        print(usage.format_turn_usage(turn_in, turn_out, turn_cost, session_cost))

    async def run(
        self,
        query: str,
        system: str | None = None,
    ) -> str:
        await self._process_query(query)

        for _ in range(self.max_iterations):
            response = self.claude_service.chat_stream(
                messages=self.messages,
                tools=await ToolManager.get_all_tools(self.clients),
                system=system,
                on_token=lambda token: print(token, end="", flush=True),
            )
            print()  # finish the streamed line (text is already on screen)
            self._report_turn_usage(response)

            self.claude_service.add_assistant_message(self.messages, response)

            if response.stop_reason == "tool_use":
                tool_result_parts = await ToolManager.execute_tool_requests(self.clients, response)

                self.claude_service.add_user_message(self.messages, tool_result_parts)
            else:
                return self.claude_service.text_from_message(response)

        raise RuntimeError(f"Model did not finish within {self.max_iterations} tool iterations.")
