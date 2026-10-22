"""End-to-end tests against the real FastMCP server, in-memory.

Uses FastMCP's in-process transport — no subprocesses, no network.
The server's docs dir is pointed at tests/test_docs by conftest.py.
"""

from pathlib import Path

import pytest
from fastmcp import Client

from mcp_server import mcp


async def test_lists_expected_tools():
    async with Client(mcp) as client:
        names = {t.name for t in await client.list_tools()}
    assert {
        "read_doc_contents",
        "edit_document",
        "append_to_doc",
        "search_documents",
        "get_doc_stats",
    } <= names


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


async def test_search_documents_regex_flag_matches_pattern():
    async with Client(mcp) as client:
        result = await client.call_tool(
            "search_documents", {"query": r"alp.a\s+beta", "regex": True}
        )
    assert not result.is_error
    assert "data.txt" in result.data


async def test_search_documents_regex_off_treats_query_as_literal():
    async with Client(mcp) as client:
        result = await client.call_tool("search_documents", {"query": r"alp.a\s+beta"})
    assert not result.is_error
    assert result.data == []


async def test_search_documents_invalid_regex_returns_error():
    from fastmcp.exceptions import ToolError

    async with Client(mcp) as client:
        with pytest.raises(ToolError):
            await client.call_tool("search_documents", {"query": "(", "regex": True})


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


async def test_get_doc_stats_markdown():
    async with Client(mcp) as client:
        result = await client.call_tool("get_doc_stats", {"doc_id": "hello.md"})
    assert not result.is_error
    stats = result.data
    assert (stats.doc_id, stats.word_count, stats.size_bytes, stats.file_type) == (
        "hello.md",
        7,  # "# Hello\nThis is a test document.\n"
        33,
        "md",
    )


async def test_get_doc_stats_text_file():
    async with Client(mcp) as client:
        result = await client.call_tool("get_doc_stats", {"doc_id": "data.txt"})
    assert not result.is_error
    stats = result.data
    assert (stats.doc_id, stats.word_count, stats.size_bytes, stats.file_type) == (
        "data.txt",
        3,  # "alpha beta gamma"
        16,
        "txt",
    )


async def test_get_doc_stats_unreadable_file_still_reports_size_and_type():
    bin_path = Path(__file__).parent / "test_docs" / "sample.bin"
    bin_path.write_bytes(b"\xff\xfe\x00binary")
    try:
        async with Client(mcp) as client:
            result = await client.call_tool("get_doc_stats", {"doc_id": "sample.bin"})
        assert not result.is_error
        stats = result.data
        assert stats.word_count == 0
        assert stats.size_bytes == bin_path.stat().st_size
        assert stats.file_type == "bin"
    finally:
        bin_path.unlink(missing_ok=True)


async def test_get_doc_stats_missing_doc_is_tool_error():
    from fastmcp.exceptions import ToolError

    async with Client(mcp) as client:
        with pytest.raises(ToolError):
            await client.call_tool("get_doc_stats", {"doc_id": "nope.md"})


async def test_append_to_doc_roundtrip():
    append_path = Path(__file__).parent / "test_docs" / "append_me.txt"
    append_path.write_text("original", encoding="utf-8")
    try:
        async with Client(mcp) as client:
            result = await client.call_tool(
                "append_to_doc", {"doc_id": "append_me.txt", "text": "\nappended"}
            )
        assert not result.is_error
        assert result.data.doc_id == "append_me.txt"
        assert result.data.updated_content == "original\nappended"
        assert append_path.read_text(encoding="utf-8") == "original\nappended"
    finally:
        append_path.unlink(missing_ok=True)


async def test_append_to_doc_missing_doc_is_tool_error():
    from fastmcp.exceptions import ToolError

    async with Client(mcp) as client:
        with pytest.raises(ToolError):
            await client.call_tool("append_to_doc", {"doc_id": "nope.md", "text": "x"})


async def test_missing_doc_is_tool_error():
    from fastmcp.exceptions import ToolError

    async with Client(mcp) as client:
        with pytest.raises(ToolError):
            await client.call_tool("read_doc_contents", {"doc_id": "nope.md"})
