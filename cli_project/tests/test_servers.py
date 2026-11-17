"""Tests for loading extra MCP servers from mcp.json (Day 13)."""

import json

import pytest
from fastmcp.client.transports import StdioTransport, StreamableHttpTransport

from core.servers import ServerConfig, client_for, load_servers_config
from mcp_client import MCPClient


def _write_config(tmp_path, data):
    path = tmp_path / "mcp.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_stdio_entry_parsed(tmp_path):
    path = _write_config(
        tmp_path,
        {
            "mcpServers": {
                "calculator": {
                    "command": "python",
                    "args": ["calc.py"],
                    "env": {"DEBUG": "1"},
                    "cwd": "/tmp",
                }
            }
        },
    )
    configs = load_servers_config(path)
    assert list(configs) == ["calculator"]
    config = configs["calculator"]
    assert config == ServerConfig(
        name="calculator",
        kind="stdio",
        command="python",
        args=["calc.py"],
        env={"DEBUG": "1"},
        cwd="/tmp",
    )


def test_http_entry_parsed(tmp_path):
    path = _write_config(tmp_path, {"mcpServers": {"remote": {"url": "http://localhost:8000/mcp"}}})
    configs = load_servers_config(path)
    assert configs["remote"] == ServerConfig(
        name="remote", kind="http", url="http://localhost:8000/mcp"
    )


def test_stdio_defaults_are_empty(tmp_path):
    path = _write_config(tmp_path, {"mcpServers": {"s": {"command": "node"}}})
    config = load_servers_config(path)["s"]
    assert config.args == []
    assert config.env == {}
    assert config.cwd is None


def test_bare_map_without_mcpservers_wrapper(tmp_path):
    path = _write_config(tmp_path, {"s": {"url": "http://localhost:9000/mcp"}})
    configs = load_servers_config(path)
    assert configs["s"].kind == "http"


def test_missing_file_returns_empty(tmp_path):
    assert load_servers_config(tmp_path / "no-such.json") == {}


def test_malformed_json_raises(tmp_path):
    path = tmp_path / "mcp.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid JSON"):
        load_servers_config(path)


def test_top_level_must_be_object(tmp_path):
    path = _write_config(tmp_path, ["calculator"])
    with pytest.raises(ValueError, match="must be an object"):
        load_servers_config(path)


def test_mcpservers_must_be_object(tmp_path):
    path = _write_config(tmp_path, {"mcpServers": ["calculator"]})
    with pytest.raises(ValueError, match="'mcpServers' must be an object"):
        load_servers_config(path)


def test_entry_without_url_or_command_raises(tmp_path):
    path = _write_config(tmp_path, {"mcpServers": {"s": {"args": ["x.py"]}}})
    with pytest.raises(ValueError, match="needs 'url'"):
        load_servers_config(path)


def test_entry_with_both_url_and_command_raises(tmp_path):
    path = _write_config(
        tmp_path,
        {"mcpServers": {"s": {"command": "python", "url": "http://localhost:8000/mcp"}}},
    )
    with pytest.raises(ValueError, match="either 'url'"):
        load_servers_config(path)


def test_entry_must_be_object(tmp_path):
    path = _write_config(tmp_path, {"mcpServers": {"s": "python"}})
    with pytest.raises(ValueError, match="must be an object"):
        load_servers_config(path)


def test_non_string_args_raise(tmp_path):
    path = _write_config(tmp_path, {"mcpServers": {"s": {"command": "python", "args": [1]}}})
    with pytest.raises(ValueError, match="'args' must be a list of strings"):
        load_servers_config(path)


def test_non_string_env_values_raise(tmp_path):
    path = _write_config(
        tmp_path, {"mcpServers": {"s": {"command": "python", "env": {"DEBUG": 1}}}}
    )
    with pytest.raises(ValueError, match="'env' must be an object of string values"):
        load_servers_config(path)


def test_client_for_stdio_builds_stdio_transport():
    config = ServerConfig(
        name="calc", kind="stdio", command="python", args=["calc.py"], env={"K": "V"}
    )
    client = client_for(config)
    assert isinstance(client, MCPClient)
    assert isinstance(client._transport, StdioTransport)
    assert client._transport.command == "python"
    assert client._transport.args == ["calc.py"]


def test_client_for_http_builds_http_transport():
    config = ServerConfig(name="remote", kind="http", url="http://localhost:8000/mcp")
    client = client_for(config)
    assert isinstance(client._transport, StreamableHttpTransport)


def test_mcp_client_command_label():
    client = MCPClient(command="python", args=["calc.py"])
    assert client._label == "python calc.py"
    assert isinstance(client._transport, StdioTransport)


def test_mcp_client_needs_one_of_script_command_url():
    with pytest.raises(ValueError, match="needs a server script, a command, or a URL"):
        MCPClient()
