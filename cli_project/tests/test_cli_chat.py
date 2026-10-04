"""Tests for the /clear local slash command in core.cli_chat.CliChat."""

from core.cli_chat import CliChat


class FakeDocClient:
    """Minimal stand-in: /clear never touches the doc client."""

    async def list_prompts(self):  # pragma: no cover
        raise AssertionError("local /clear must not reach the server")

    async def get_prompt(self, command, args):  # pragma: no cover
        raise AssertionError("local /clear must not reach the server")


def make_chat(messages=None):
    chat = CliChat(doc_client=FakeDocClient(), clients={}, claude_service=None)
    chat.messages = list(messages or [])
    return chat


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
