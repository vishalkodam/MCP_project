"""Tests for MCPClient connect retry with exponential backoff."""

import asyncio

import pytest

import mcp_client
from mcp_client import MCPClient


def _fake_client_class(monkeypatch, failures_before_success):
    """Replace fastmcp.Client with a fake whose __aenter__ fails N times."""
    state = {"remaining": failures_before_success, "created": 0, "exited": 0}

    class FakeClient:
        def __init__(self, transport):
            state["created"] += 1

        async def __aenter__(self):
            if state["remaining"] > 0:
                state["remaining"] -= 1
                raise RuntimeError("spawn failed")
            return self

        async def __aexit__(self, *exc):
            state["exited"] += 1

    monkeypatch.setattr(mcp_client, "Client", FakeClient)
    return state


async def test_connect_succeeds_first_try(monkeypatch):
    state = _fake_client_class(monkeypatch, failures_before_success=0)
    client = MCPClient(script="mcp_server.py")
    await client.connect()
    assert client._client is not None
    assert state["created"] == 1
    assert state["exited"] == 0


async def test_connect_retries_then_succeeds(monkeypatch):
    state = _fake_client_class(monkeypatch, failures_before_success=2)
    client = MCPClient(script="mcp_server.py", max_retries=3, retry_backoff=0)
    await client.connect()
    assert client._client is not None
    assert state["created"] == 3
    assert state["exited"] == 2


async def test_connect_raises_after_retries_exhausted(monkeypatch):
    state = _fake_client_class(monkeypatch, failures_before_success=99)
    client = MCPClient(script="mcp_server.py", max_retries=2, retry_backoff=0)
    with pytest.raises(RuntimeError, match="spawn failed"):
        await client.connect()
    assert client._client is None
    assert state["created"] == 3
    assert state["exited"] == 3


async def test_connect_backoff_is_exponential(monkeypatch):
    _fake_client_class(monkeypatch, failures_before_success=2)
    delays: list[float] = []

    async def fake_sleep(delay):
        delays.append(delay)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    client = MCPClient(script="mcp_server.py", max_retries=3, retry_backoff=0.5)
    await client.connect()
    assert delays == [0.5, 1.0]


async def test_connect_retries_http_too(monkeypatch):
    state = _fake_client_class(monkeypatch, failures_before_success=1)
    client = MCPClient(url="http://localhost:8000/mcp", max_retries=3, retry_backoff=0)
    await client.connect()
    assert client._client is not None
    assert state["created"] == 2


def test_client_needs_script_or_url():
    with pytest.raises(ValueError, match="needs either a server script or a URL"):
        MCPClient()


def _fake_client_with_tools(monkeypatch, tools):
    """Fake fastmcp.Client whose list_tools counts calls and is mutable."""
    state = {"list_calls": 0, "tools": list(tools)}

    class FakeClient:
        def __init__(self, transport):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            pass

        async def list_tools(self):
            state["list_calls"] += 1
            return list(state["tools"])

    monkeypatch.setattr(mcp_client, "Client", FakeClient)
    return state


async def test_list_tools_caches_for_session(monkeypatch):
    _fake_client_with_tools(monkeypatch, tools=["read_document"])
    client = MCPClient(script="mcp_server.py")
    await client.connect()
    first = await client.list_tools()
    second = await client.list_tools()
    assert first == ["read_document"]
    assert second is first  # same cached list, no second server round-trip


async def test_refresh_tools_relists(monkeypatch):
    state = _fake_client_with_tools(monkeypatch, tools=["read_document"])
    client = MCPClient(script="mcp_server.py")
    await client.connect()
    assert await client.list_tools() == ["read_document"]
    state["tools"].append("new_tool")
    # Plain list_tools still serves the cache, refresh picks up the change.
    assert await client.list_tools() == ["read_document"]
    assert await client.refresh_tools() == ["read_document", "new_tool"]
    assert state["list_calls"] == 2
    assert await client.list_tools() == ["read_document", "new_tool"]


async def test_tool_cache_cleared_on_reconnect(monkeypatch):
    state = _fake_client_with_tools(monkeypatch, tools=["read_document"])
    client = MCPClient(script="mcp_server.py")
    await client.connect()
    await client.list_tools()
    await client.cleanup()
    await client.connect()
    await client.list_tools()
    assert state["list_calls"] == 2


async def test_list_tools_before_connect_raises(monkeypatch):
    _fake_client_with_tools(monkeypatch, tools=[])
    client = MCPClient(script="mcp_server.py")
    with pytest.raises(ConnectionError, match="not connected"):
        await client.list_tools()
