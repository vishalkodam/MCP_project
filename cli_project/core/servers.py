"""Load extra MCP servers from an ``mcp.json`` config file.

The file uses the same ``mcpServers`` map shape as Claude Desktop:

.. code-block:: json

    {
      "mcpServers": {
        "calculator": {
          "command": "python",
          "args": ["examples/calculator_server.py"]
        },
        "remote-docs": {
          "url": "http://localhost:8000/mcp"
        }
      }
    }

A **stdio** entry needs ``command`` (plus optional ``args``, ``env`` and
``cwd``); an **HTTP** entry needs ``url``. A missing config file means "no
extra servers" — that is not an error. Anything malformed raises
:class:`ValueError` with a message naming the problem, so a typo'd config
fails loudly at startup instead of silently connecting to nothing.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mcp_client import MCPClient

logger = logging.getLogger(__name__)


@dataclass
class ServerConfig:
    """One extra MCP server, as declared in ``mcp.json``."""

    name: str
    kind: str  # "stdio" or "http"
    command: str | None = None
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    cwd: str | None = None
    url: str | None = None


def _require_str(entry: dict[str, Any], key: str, name: str) -> str:
    value = entry.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Server {name!r}: {key!r} must be a non-empty string.")
    return value


def _parse_entry(name: str, entry: Any) -> ServerConfig:
    if not isinstance(entry, dict):
        raise ValueError(f"Server {name!r}: entry must be an object.")
    has_url = "url" in entry
    has_command = "command" in entry
    if has_url and has_command:
        raise ValueError(
            f"Server {name!r}: give either 'url' (http) or 'command' (stdio), not both."
        )
    if has_url:
        return ServerConfig(name=name, kind="http", url=_require_str(entry, "url", name))
    if has_command:
        args = entry.get("args", [])
        if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
            raise ValueError(f"Server {name!r}: 'args' must be a list of strings.")
        env = entry.get("env", {})
        if not isinstance(env, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in env.items()
        ):
            raise ValueError(f"Server {name!r}: 'env' must be an object of string values.")
        cwd = entry.get("cwd")
        if cwd is not None and not isinstance(cwd, str):
            raise ValueError(f"Server {name!r}: 'cwd' must be a string.")
        return ServerConfig(
            name=name,
            kind="stdio",
            command=_require_str(entry, "command", name),
            args=list(args),
            env=dict(env),
            cwd=cwd,
        )
    raise ValueError(f"Server {name!r}: entry needs 'url' (http) or 'command' (stdio).")


def load_servers_config(path: str | Path) -> dict[str, ServerConfig]:
    """Read ``mcp.json`` and return its servers keyed by name.

    Returns an empty dict when the file does not exist. Raises
    :class:`ValueError` for malformed JSON or malformed entries.
    """
    path = Path(path)
    if not path.exists():
        logger.info("No server config at %s — no extra servers.", path)
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"Invalid config in {path}: top level must be an object.")
    servers_map = raw.get("mcpServers", raw)
    if not isinstance(servers_map, dict):
        raise ValueError(f"Invalid config in {path}: 'mcpServers' must be an object.")
    configs: dict[str, ServerConfig] = {}
    for name, entry in servers_map.items():
        if not isinstance(name, str) or not name:
            raise ValueError(f"Invalid config in {path}: server names must be non-empty.")
        configs[name] = _parse_entry(name, entry)
    logger.info("Loaded %d extra server(s) from %s.", len(configs), path)
    return configs


def client_for(config: ServerConfig) -> MCPClient:
    """Build the :class:`MCPClient` for one configured server."""
    if config.kind == "http":
        assert config.url is not None
        return MCPClient(url=config.url)
    assert config.command is not None
    return MCPClient(
        command=config.command,
        args=config.args,
        env=config.env or None,
        cwd=config.cwd,
    )
