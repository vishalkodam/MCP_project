"""End-to-end tests against the real FastMCP server, in-memory.

Uses FastMCP's in-process transport — no subprocesses, no network.
The server's docs dir is pointed at tests/test_docs by conftest.py.
"""

import pytest
from fastmcp import Client

from mcp_server import mcp


async def test_lists_expected_tools():
    async with Client(mcp) as client:
        names = {t.name for t in await client.list_tools()}
    assert {"read_doc_contents", "edit_document", "search_documents"} <= names


async def test_tool_schemas_have_descriptions():
    async with Client(mcp) as client:
        tools = await client.list_tools()
    for tool in tools:
        assert tool.description, f"tool {tool.name} is missing a description"
        assert tool.input_schema["type"] == "object"


async def test_read_doc_contents_roundtrip():
    async with Client(mcp) as client:
        result = await client.call_tool("read_doc_contents", {"doc_id": "hello.md"})
    assert not result.is_error
    assert "This is a test document." in result.content[0].text


async def test_search_documents_finds_match():
    async with Client(mcp) as client:
        result = await client.call_tool("search_documents", {"query": "alpha beta"})
    assert not result.is_error
    assert "data.txt" in result.data


async def test_documents_resource_lists_ids():
    async with Client(mcp) as client:
        contents = await client.read_resource("docs://documents")
    assert contents[0].mime_type == "application/json"
    assert "hello.md" in contents[0].text


async def test_document_resource_template():
    async with Client(mcp) as client:
        contents = await client.read_resource("docs://documents/hello.md")
    assert "This is a test document." in contents[0].text


async def test_prompts_are_listed():
    async with Client(mcp) as client:
        prompts = await client.list_prompts()
    assert {"format", "summarize"} <= {p.name for p in prompts}


async def test_get_prompt_renders():
    async with Client(mcp) as client:
        result = await client.get_prompt("summarize", {"doc_id": "hello.md"})
    assert result.messages
    assert result.messages[0].role == "user"
    assert "hello.md" in result.messages[0].content.text


async def test_missing_doc_is_tool_error():
    from fastmcp.exceptions import ToolError

    async with Client(mcp) as client:
        with pytest.raises(ToolError):
            await client.call_tool("read_doc_contents", {"doc_id": "nope.md"})
