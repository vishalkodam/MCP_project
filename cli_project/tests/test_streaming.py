"""Tests for token-by-token streaming of model responses (Day 3)."""

from types import SimpleNamespace

from core.chat import Chat
from core.claude import Claude


class FakeStream:
    """Stand-in for the Anthropic SDK's MessageStream context manager."""

    def __init__(self, deltas, final_message):
        self._deltas = list(deltas)
        self._final_message = final_message

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    @property
    def text_stream(self):
        return iter(self._deltas)

    def get_final_message(self):
        return self._final_message


class FakeMessagesAPI:
    """Mimics ``client.messages``; serves one canned stream per call."""

    def __init__(self, streams):
        self._streams = list(streams)
        self.calls = []

    def stream(self, **kwargs):
        self.calls.append(kwargs)
        deltas, final_message = self._streams.pop(0)
        return FakeStream(deltas, final_message)


class FakeAnthropicClient:
    def __init__(self, streams):
        self.messages = FakeMessagesAPI(streams)


def text_block(text):
    return SimpleNamespace(type="text", text=text)


def tool_use_block(tool_id="toolu_1", name="read_document"):
    return SimpleNamespace(type="tool_use", id=tool_id, name=name, input={"doc_id": "hello.md"})


def final_message(blocks, stop_reason="end_turn"):
    return SimpleNamespace(stop_reason=stop_reason, content=list(blocks))


def make_claude(streams, model="test-model"):
    # Bypass Claude.__init__ (it builds a real Anthropic client, which needs
    # network/proxy config); the tests only exercise chat_stream, which uses
    # self.model and self.client.
    service = Claude.__new__(Claude)
    service.model = model
    service.client = FakeAnthropicClient(streams)
    return service


def test_chat_stream_delivers_each_token_to_callback():
    deltas = ["Hel", "lo", ", ", "world"]
    service = make_claude([(deltas, final_message([text_block("Hello, world")]))])
    seen = []
    response = service.chat_stream(messages=[], on_token=seen.append)
    assert seen == deltas
    assert response.stop_reason == "end_turn"


def test_chat_stream_without_callback_still_returns_message():
    service = make_claude([(["abc"], final_message([text_block("abc")]))])
    response = service.chat_stream(messages=[])
    assert response.content[0].text == "abc"


def test_chat_stream_returns_final_message_with_tool_use():
    final = final_message([text_block("Reading it now."), tool_use_block()], stop_reason="tool_use")
    service = make_claude([(["Reading it now."], final)])
    response = service.chat_stream(messages=[])
    assert response.stop_reason == "tool_use"
    assert response.content[1].name == "read_document"


def test_chat_stream_forwards_request_params():
    service = make_claude([([], final_message([text_block("ok")]))])
    tools = [{"name": "read_document"}]
    service.chat_stream(messages=[{"role": "user", "content": "hi"}], tools=tools, system="sys")
    call = service.client.messages.calls[0]
    assert call["model"] == "test-model"
    assert call["tools"] == tools
    assert call["system"] == "sys"


class FakeMcpClient:
    """MCP client stand-in with a single working tool."""

    async def list_tools(self):
        return [SimpleNamespace(name="read_document", description="Read a doc.", input_schema={})]

    async def call_tool(self, name, arguments):
        assert name == "read_document"
        return "document contents here"


async def test_run_streams_tokens_and_returns_final_text(capsys):
    service = make_claude([(["Hello", " world"], final_message([text_block("Hello world")]))])
    chat = Chat(claude_service=service, clients={})
    result = await chat.run("hi")
    assert result == "Hello world"
    out = capsys.readouterr().out
    assert "Hello" in out
    assert " world" in out


async def test_run_streams_tool_use_turn_then_continues(capsys):
    first = final_message(
        [text_block("Let me read that."), tool_use_block()], stop_reason="tool_use"
    )
    second = final_message([text_block("Done reading.")])
    service = make_claude(
        [
            (["Let me read that."], first),
            (["Done reading."], second),
        ]
    )
    chat = Chat(claude_service=service, clients={"documents": FakeMcpClient()})
    result = await chat.run("read hello.md")
    assert result == "Done reading."
    out = capsys.readouterr().out
    assert "Let me read that." in out
    assert "Done reading." in out
    # the tool result was fed back into the conversation as a user message
    tool_results = [
        m for m in chat.messages if m["role"] == "user" and isinstance(m["content"], list)
    ]
    assert tool_results
