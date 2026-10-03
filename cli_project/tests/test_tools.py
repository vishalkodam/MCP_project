"""Tests for core.tools.ToolManager with fake MCP clients."""

from types import SimpleNamespace

from core.tools import ToolManager
from mcp_client import MCPToolError


def make_tool(name, description="A tool.", schema=None):
    return SimpleNamespace(
        name=name,
        description=description,
        input_schema=schema or {"type": "object", "properties": {}},
    )


class FakeClient:
    def __init__(self, tools, results=None, errors=()):
        self._tools = tools
        self._results = results or {}
        self._errors = set(errors)

    async def list_tools(self):
        return self._tools

    async def call_tool(self, name, args):
        if name in self._errors:
            raise MCPToolError("boom")
        return self._results[name]


def make_response(*blocks):
    return SimpleNamespace(content=list(blocks), stop_reason="tool_use")


def tool_use_block(id="t1", name="read_doc_contents", input=None):
    return SimpleNamespace(type="tool_use", id=id, name=name, input=input or {"doc_id": "a.md"})


async def test_get_all_tools_converts_to_anthropic_format():
    clients = {"docs": FakeClient([make_tool("read_doc_contents", "Reads docs.")])}
    tools = await ToolManager.get_all_tools(clients)
    assert tools == [
        {
            "name": "read_doc_contents",
            "description": "Reads docs.",
            "input_schema": {"type": "object", "properties": {}},
        }
    ]


async def test_get_all_tools_merges_multiple_servers():
    clients = {
        "docs": FakeClient([make_tool("read_doc_contents")]),
        "extra": FakeClient([make_tool("calculate")]),
    }
    tools = await ToolManager.get_all_tools(clients)
    assert {t["name"] for t in tools} == {"read_doc_contents", "calculate"}


async def test_execute_tool_requests_returns_tool_results():
    clients = {
        "docs": FakeClient(
            [make_tool("read_doc_contents")], {"read_doc_contents": "file text here"}
        )
    }
    results = await ToolManager.execute_tool_requests(clients, make_response(tool_use_block()))
    assert results == [{"type": "tool_result", "tool_use_id": "t1", "content": "file text here"}]


async def test_execute_unknown_tool_returns_error_result():
    clients = {"docs": FakeClient([make_tool("read_doc_contents")])}
    results = await ToolManager.execute_tool_requests(
        clients, make_response(tool_use_block(name="nope"))
    )
    assert results[0]["is_error"] is True
    assert "Unknown tool" in results[0]["content"]


async def test_execute_failing_tool_returns_error_result():
    clients = {"docs": FakeClient([make_tool("read_doc_contents")], errors=("read_doc_contents",))}
    results = await ToolManager.execute_tool_requests(clients, make_response(tool_use_block()))
    assert results[0]["is_error"] is True


async def test_non_tool_blocks_are_ignored():
    text_block = SimpleNamespace(type="text", text="hello")
    clients = {"docs": FakeClient([])}
    results = await ToolManager.execute_tool_requests(clients, make_response(text_block))
    assert results == []
