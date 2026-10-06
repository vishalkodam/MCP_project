"""Tests for the /clear and /tools local slash commands in core.cli_chat.CliChat."""

from types import SimpleNamespace

from core.cli_chat import CliChat


class FakeDocClient:
    """Minimal stand-in: local commands never touch the doc client."""

    async def list_prompts(self):  # pragma: no cover
        raise AssertionError("local commands must not reach the server")

    async def get_prompt(self, command, args):  # pragma: no cover
        raise AssertionError("local commands must not reach the server")


class FakeToolsClient:
    """MCP client stand-in returning a fixed tool list."""

    def __init__(self, tools):
        self._tools = tools

    async def list_tools(self):
        return self._tools


def make_chat(messages=None, clients=None):
    chat = CliChat(doc_client=FakeDocClient(), clients=clients or {}, claude_service=None)
    chat.messages = list(messages or [])
    return chat


def tool(name, description=None):
    return SimpleNamespace(name=name, description=description)


async def test_clear_resets_conversation_history(capsys):
    chat = make_chat(
        [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ]
    )
    handled = await chat._process_command("/clear")
    assert handled is True
    assert chat.messages == []
    assert "cleared" in capsys.readouterr().out.lower()


async def test_clear_on_empty_history_is_harmless(capsys):
    chat = make_chat()
    handled = await chat._process_command("/clear")
    assert handled is True
    assert chat.messages == []


async def test_clear_is_not_sent_to_server_as_prompt():
    # FakeDocClient raises if get_prompt/list_prompts are called, so reaching
    # this assert means _process_command short-circuited correctly.
    chat = make_chat([{"role": "user", "content": "old"}])
    assert await chat._process_command("/clear") is True
    assert chat.messages == []


async def test_local_commands_registered():
    assert CliChat.LOCAL_COMMANDS["clear"]
    assert CliChat.LOCAL_COMMANDS["tools"]


async def test_tools_lists_each_tool_with_description(capsys):
    chat = make_chat(
        clients={
            "documents": FakeToolsClient(
                [
                    tool("read_document", "Read a document by ID."),
                    tool("search_documents", "Search document contents."),
                ]
            ),
        }
    )
    handled = await chat._process_command("/tools")
    assert handled is True
    out = capsys.readouterr().out
    assert "read_document" in out
    assert "Read a document by ID." in out
    assert "search_documents" in out
    assert "[documents]" in out


async def test_tools_groups_multiple_servers(capsys):
    chat = make_chat(
        clients={
            "documents": FakeToolsClient([tool("read_document", "Read a document.")]),
            "calc": FakeToolsClient([tool("add", "Add two numbers.")]),
        }
    )
    await chat._process_command("/tools")
    out = capsys.readouterr().out
    assert "[documents]" in out
    assert "[calc]" in out
    assert "Available MCP tools (2)" in out


async def test_tools_missing_description_gets_placeholder(capsys):
    chat = make_chat(clients={"documents": FakeToolsClient([tool("ping")])})
    await chat._process_command("/tools")
    out = capsys.readouterr().out
    assert "ping" in out
    assert "(no description)" in out


async def test_tools_with_no_tools_available(capsys):
    chat = make_chat(clients={"documents": FakeToolsClient([])})
    await chat._process_command("/tools")
    assert "No MCP tools available." in capsys.readouterr().out


async def test_tools_ignores_client_listing_failure(capsys):
    class BrokenClient:
        async def list_tools(self):
            raise RuntimeError("server down")

    chat = make_chat(
        clients={
            "broken": BrokenClient(),
            "documents": FakeToolsClient([tool("read_document", "Read a document.")]),
        }
    )
    await chat._process_command("/tools")
    out = capsys.readouterr().out
    assert "read_document" in out
    assert "could not list tools from 'broken'" in out


async def test_tools_is_not_sent_to_server_as_prompt():
    # FakeDocClient raises if get_prompt/list_prompts are called, so reaching
    # this assert means _process_command short-circuited correctly.
    chat = make_chat(clients={"documents": FakeToolsClient([])})
    assert await chat._process_command("/tools") is True
