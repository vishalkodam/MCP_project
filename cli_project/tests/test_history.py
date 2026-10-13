"""Tests for Day 5: history persistence (core.history) and the /history command."""

import json
from pathlib import Path
from types import SimpleNamespace

from core.chat import Chat
from core.cli_chat import CliChat, message_text
from core.history import DEFAULT_HISTORY_PATH, HistoryStore


def make_store(tmp_path, name="history.json"):
    return HistoryStore(tmp_path / name)


# --- HistoryStore ---


def test_load_missing_file_returns_empty_list(tmp_path):
    assert make_store(tmp_path).load() == []


def test_save_and_load_round_trip(tmp_path):
    store = make_store(tmp_path)
    messages = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": [{"type": "text", "text": "hi there"}]},
    ]
    store.save(messages)
    assert store.load() == messages


def test_save_serializes_sdk_block_objects(tmp_path):
    """In-memory messages may hold Anthropic SDK block objects; save must not choke."""

    class FakeBlock:
        def model_dump(self):
            return {"type": "text", "text": "from an object"}

    store = make_store(tmp_path)
    store.save([{"role": "assistant", "content": [FakeBlock()]}])
    loaded = store.load()
    assert loaded == [
        {"role": "assistant", "content": [{"type": "text", "text": "from an object"}]}
    ]


def test_save_creates_parent_directories(tmp_path):
    store = HistoryStore(tmp_path / "deep" / "nested" / "history.json")
    store.save([{"role": "user", "content": "x"}])
    assert store.path.exists()
    assert store.load() == [{"role": "user", "content": "x"}]


def test_load_corrupt_file_returns_empty_list(tmp_path):
    store = make_store(tmp_path)
    store.path.write_text("{ not json", encoding="utf-8")
    assert store.load() == []


def test_load_non_list_json_returns_empty_list(tmp_path):
    store = make_store(tmp_path)
    store.path.write_text(json.dumps({"role": "user"}), encoding="utf-8")
    assert store.load() == []


def test_default_path_lives_under_home():
    assert DEFAULT_HISTORY_PATH == Path.home() / ".mcp_chat" / "history.json"


# --- Chat integration ---


def test_chat_restores_messages_from_store(tmp_path):
    store = make_store(tmp_path)
    store.save([{"role": "user", "content": "previous session"}])
    chat = Chat(claude_service=None, clients={}, history_store=store)
    assert chat.messages == [{"role": "user", "content": "previous session"}]


def test_chat_without_store_starts_empty_and_persists_nothing():
    chat = Chat(claude_service=None, clients={})
    assert chat.messages == []
    chat._persist_history()  # must be a harmless no-op


def test_clear_history_also_clears_the_store(tmp_path):
    store = make_store(tmp_path)
    chat = Chat(claude_service=None, clients={}, history_store=store)
    chat.messages.append({"role": "user", "content": "hi"})
    chat._persist_history()
    assert store.load() != []
    chat.clear_history()
    assert chat.messages == []
    assert store.load() == []


def test_persist_failure_does_not_raise(tmp_path):
    store = make_store(tmp_path)
    store.path.mkdir()  # saving where a directory sits must fail
    chat = Chat(claude_service=None, clients={}, history_store=store)
    chat._persist_history()  # must not raise


class FakeClaude:
    """Minimal Claude stand-in answering one plain-text turn."""

    model = "test-model"

    def __init__(self, text="reply"):
        self.text = text

    def chat_stream(self, messages, tools, system=None, on_token=None):
        return SimpleNamespace(stop_reason="end_turn")

    def add_assistant_message(self, messages, response):
        messages.append({"role": "assistant", "content": self.text})

    def text_from_message(self, response):
        return self.text


async def test_run_persists_history_to_disk(tmp_path, capsys):
    store = make_store(tmp_path)
    chat = Chat(claude_service=FakeClaude(), clients={}, history_store=store)
    result = await chat.run("hello")
    assert result == "reply"
    capsys.readouterr()  # discard usage/streaming output
    assert store.load() == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "reply"},
    ]


# --- message_text ---


def test_message_text_with_string_content():
    assert message_text({"role": "user", "content": "hello"}) == "hello"


def test_message_text_with_dict_blocks():
    message = {
        "role": "assistant",
        "content": [{"type": "text", "text": "hi"}, {"type": "text", "text": " there"}],
    }
    assert message_text(message) == "hi\n there"


def test_message_text_with_sdk_style_objects():
    message = {
        "role": "assistant",
        "content": [SimpleNamespace(type="text", text="obj text")],
    }
    assert message_text(message) == "obj text"


def test_message_text_marks_tool_use_blocks():
    message = {
        "role": "assistant",
        "content": [
            {"type": "text", "text": "calling it"},
            {"type": "tool_use", "name": "read_document", "id": "1", "input": {}},
        ],
    }
    assert message_text(message) == "calling it\n[tool: read_document]"


def test_message_text_with_missing_content():
    assert message_text({"role": "user"}) == ""


# --- /history command ---


class FakeDocClient:
    async def list_prompts(self):  # pragma: no cover
        raise AssertionError("local commands must not reach the server")

    async def get_prompt(self, command, args):  # pragma: no cover
        raise AssertionError("local commands must not reach the server")


def make_chat(messages, tmp_path):
    store = make_store(tmp_path)
    chat = CliChat(doc_client=FakeDocClient(), clients={}, claude_service=None, history_store=store)
    chat.messages = list(messages)
    return chat


def sample_messages():
    return [
        {"role": "user", "content": "what is in report.docx?"},
        {
            "role": "assistant",
            "content": "The report covers quarterly earnings in detail. " * 10,
        },
    ]


def test_history_is_registered_as_local_command():
    assert CliChat.LOCAL_COMMANDS["history"]


async def test_history_lists_turns_with_previews(tmp_path, capsys):
    chat = make_chat(sample_messages(), tmp_path)
    handled = await chat._process_command("/history")
    assert handled is True
    out = capsys.readouterr().out
    assert "Conversation history (2 turns)" in out
    assert "#1 [user] what is in report.docx?" in out
    assert "#2 [assistant]" in out
    assert "…" in out  # long assistant reply is truncated


async def test_history_on_empty_history(tmp_path, capsys):
    chat = make_chat([], tmp_path)
    assert await chat._process_command("/history") is True
    assert "No conversation history yet." in capsys.readouterr().out


async def test_history_with_turn_number_prints_full_text(tmp_path, capsys):
    chat = make_chat(sample_messages(), tmp_path)
    assert await chat._process_command("/history 2") is True
    out = capsys.readouterr().out
    assert "Turn 2 [assistant]:" in out
    assert "quarterly earnings" in out
    assert "…" not in out  # full text, no truncation


async def test_history_with_out_of_range_turn(tmp_path, capsys):
    chat = make_chat(sample_messages(), tmp_path)
    assert await chat._process_command("/history 99") is True
    assert "Usage: /history [1-2]" in capsys.readouterr().out


async def test_history_with_non_numeric_argument(tmp_path, capsys):
    chat = make_chat(sample_messages(), tmp_path)
    assert await chat._process_command("/history abc") is True
    assert "Usage: /history [1-2]" in capsys.readouterr().out


async def test_history_is_not_sent_to_server_as_prompt(tmp_path):
    chat = make_chat(sample_messages(), tmp_path)
    assert await chat._process_command("/history") is True
