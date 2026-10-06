import logging
from typing import List, Tuple

from anthropic.types import MessageParam

from core.chat import Chat
from core.claude import Claude
from mcp_client import MCPClient

logger = logging.getLogger(__name__)


class CliChat(Chat):
    #: Slash commands handled locally by the CLI instead of being sent to an
    #: MCP server as prompts. Maps command name -> description for completion.
    LOCAL_COMMANDS = {
        "clear": "Clear the conversation history.",
        "tools": "List available MCP tools and their descriptions.",
    }

    def __init__(
        self,
        doc_client: MCPClient,
        clients: dict[str, MCPClient],
        claude_service: Claude,
    ):
        super().__init__(clients=clients, claude_service=claude_service)

        self.doc_client: MCPClient = doc_client

    async def list_prompts(self) -> list:
        return await self.doc_client.list_prompts()

    async def list_docs_ids(self) -> list[str]:
        logger.debug("Reading documents resource...")
        result = await self.doc_client.read_resource("docs://documents")
        if result and isinstance(result, list):
            return result
        return []

    async def get_doc_content(self, doc_id: str) -> str:
        logger.debug("Reading document content for: %s", doc_id)
        result = await self.doc_client.read_resource(f"docs://documents/{doc_id}")
        if result and isinstance(result, str):
            return result
        return f"Document '{doc_id}' not found"

    async def get_prompt(self, command: str, doc_id: str) -> list:
        return await self.doc_client.get_prompt(command, {"doc_id": doc_id})

    async def _extract_resources(self, query: str) -> str:
        mentions = [word[1:] for word in query.split() if word.startswith("@")]

        doc_ids = await self.list_docs_ids()
        mentioned_docs: list[Tuple[str, str]] = []

        # Handle case where doc_ids is None (e.g., when MCP server doesn't have docs resource)
        if doc_ids is None:
            return ""

        for doc_id in doc_ids:
            if doc_id in mentions:
                content = await self.get_doc_content(doc_id)
                mentioned_docs.append((doc_id, content))

        return "".join(
            f'\n<document id="{doc_id}">\n{content}\n</document>\n'
            for doc_id, content in mentioned_docs
        )

    async def _process_command(self, query: str) -> bool:
        if not query.startswith("/"):
            return False

        words = query.split()
        command = words[0].replace("/", "")

        if command in self.LOCAL_COMMANDS:
            await self._process_local_command(command)
            return True

        if len(words) < 2:
            print(f"Usage: /{command} <document-id>")
            return True

        try:
            messages = await self.doc_client.get_prompt(command, {"doc_id": words[1]})
        except Exception as exc:
            print(f"Unknown command '/{command}': {exc}")
            return True

        self.messages += convert_prompt_messages_to_message_params(messages)
        return True

    async def _process_local_command(self, command: str) -> None:
        """Handle a locally-defined slash command (no server round-trip)."""
        if command == "clear":
            self.clear_history()
            print("Conversation history cleared.")
        elif command == "tools":
            await self._print_tools()

    async def _print_tools(self) -> None:
        """Print every available MCP tool, grouped by server, with descriptions."""
        listed: list[tuple[str, str, str]] = []  # (server_id, tool_name, description)
        for client_id, client in self.clients.items():
            try:
                tools = await client.list_tools()
            except Exception as exc:
                logger.warning("Could not list tools from %r: %s", client_id, exc)
                print(f"  (could not list tools from '{client_id}': {exc})")
                continue
            for tool in tools or []:
                listed.append((client_id, tool.name, tool.description or "(no description)"))

        if not listed:
            print("No MCP tools available.")
            return

        print(f"Available MCP tools ({len(listed)}):")
        for server_id, name, description in listed:
            print(f"  {name} — {description}  [{server_id}]")

    async def _process_query(self, query: str):
        if await self._process_command(query):
            return

        added_resources = await self._extract_resources(query)

        prompt = f"""
        The user has a question:
        <query>
        {query}
        </query>

        The following context may be useful in answering their question:
        <context>
        {added_resources}
        </context>

        Note the user's query might contain references to documents like
        "@report.docx". The "@" is only included as a way of mentioning the
        doc. The actual name of the document would be "report.docx".
        If the document content is included in this prompt, you don't need to
        use an additional tool to read the document.
        Answer the user's question directly and concisely. Start with the exact
        information they need.
        Don't refer to or mention the provided context in any way - just use
        it to inform your answer.
        """

        self.messages.append({"role": "user", "content": prompt})


def _message_content_to_text(content) -> str:
    """Extract plain text from an MCP prompt message content object."""
    text = getattr(content, "text", None)
    if isinstance(text, str):
        return text
    if isinstance(content, str):
        return content
    return ""


def convert_prompt_message_to_message_param(prompt_message) -> MessageParam:
    role = "user" if prompt_message.role == "user" else "assistant"

    content = prompt_message.content

    if isinstance(content, list):
        text_blocks = []
        for item in content:
            item_text = _message_content_to_text(item)
            if item_text:
                text_blocks.append({"type": "text", "text": item_text})
        if text_blocks:
            return {"role": role, "content": text_blocks}

    text = _message_content_to_text(content)
    return {"role": role, "content": text}


def convert_prompt_messages_to_message_params(
    prompt_messages: List,
) -> List[MessageParam]:
    return [convert_prompt_message_to_message_param(msg) for msg in prompt_messages]
