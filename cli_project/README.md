# MCP Chat

A command-line chat app where **Claude** answers your questions with help from
your own documents — wired up through the **[Model Context Protocol (MCP)](https://modelcontextprotocol.io)**.

Type normally to chat. Mention a document with `@` to pull it into context, or
run a server-side prompt with `/`. Everything the model can do with your files
lives in a real MCP server, so the same tools also work from Claude Desktop,
Claude Code, or any other MCP client.

## Features

- 💬 Chat with Claude (Anthropic Messages API) from your terminal
- ⚡ Replies stream token-by-token as the model generates them
- 📄 `@doc.md` mentions — inline any document into your question (with Tab completion)
- ⌨️ `/summarize`, `/format` prompt commands, also Tab-completed
- 🛠️ MCP tools the model calls on its own: read, edit, and search documents
- 📦 Real document parsing: Markdown, text, **PDF**, and **Word** files
- 🌐 Server runs over **stdio** locally or **Streamable HTTP** for remote clients
- ✅ Test suite, linting, and CI included

## Tech stack

| Layer   | Technology | Version |
|---------|------------|---------|
| MCP server & client | [FastMCP](https://gofastmcp.com) | 4.x (spec `2026-07-28`) |
| Model API | [Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python) | 1.x |
| CLI | prompt-toolkit | 3.x |
| Doc parsing | pypdf, python-docx | latest |
| Env / packaging | python-dotenv, uv or pip | — |
| Dev | pytest, pytest-asyncio, ruff | — |

Requires **Python 3.10+** and an Anthropic API key.

## Quickstart

### 1. Configure

```bash
cd cli_project
cp .env.example .env
# edit .env: set ANTHROPIC_API_KEY and CLAUDE_MODEL (e.g. claude-sonnet-5)
```

### 2. Install

With uv (recommended):

```bash
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
```

Or plain pip:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

### 3. Add documents

Drop `.md`, `.txt`, `.pdf`, or `.docx` files into `cli_project/docs/`.
Two samples are included so it works out of the box.

### 4. Chat

```bash
python main.py
```

```
> Tell me about @welcome.md
> /summarize notes.md
```

Extra MCP server scripts can be passed as arguments and their tools become
available to the model too:

```bash
python main.py /path/to/other_server.py
```

## Usage

### `@` mentions

Type `@` and start typing a file name — Tab completes it. The document's full
text is attached to your question as context.

### `/` commands

Commands are prompts defined by the MCP server. They Tab-complete, including
their document argument:

- `/summarize <doc>` — bullet-point summary of a document
- `/format <doc>` — ask the model to rewrite a document in clean Markdown
  (it uses the `edit_document` tool to apply changes)

Built-in commands handled by the CLI itself:

- `/clear` — reset the conversation history (no arguments needed)
- `/tools` — list every available MCP tool with its description, grouped by
  server (no arguments needed)

### Remote server mode

Serve the document tools over Streamable HTTP for other MCP clients:

```bash
python mcp_server.py --transport http --port 8000
```

Then point the chat at it:

```bash
MCP_TRANSPORT=http MCP_SERVER_URL=http://localhost:8000/mcp python main.py
```

Or register it in Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "documents": {
      "url": "http://localhost:8000/mcp",
      "transport": "http"
    }
  }
}
```

## Project structure

```
cli_project/
├── main.py            # CLI entrypoint: config, server startup, chat loop
├── mcp_server.py      # FastMCP server: tools, resources, prompts, doc store
├── mcp_client.py      # Async client wrapper (stdio + Streamable HTTP)
├── core/
│   ├── chat.py        # Tool-use conversation loop
│   ├── cli_chat.py    # @ mentions and / command handling
│   ├── cli.py         # prompt-toolkit UI: completion, history, keybindings
│   ├── claude.py      # Anthropic API wrapper
│   └── tools.py       # MCP tools <-> Anthropic tool definitions bridge
├── docs/              # Your documents live here
└── tests/             # pytest suite (server, tools, document store)
```

## How it fits together

```
┌─────────┐  stdio/HTTP   ┌──────────────┐  tool calls   ┌─────────────┐
│ main.py │◄──────────────► mcp_server.py │◄──────────────► │  docs/*.md  │
│ (CLI +  │               │ (FastMCP:    │               │  docs/*.pdf │
│  Claude)│               │  tools,       │               └─────────────┘
└─────────┘               │  resources,  │
                          │  prompts)    │
                          └──────────────┘
```

`core/tools.py` converts each MCP tool schema into an Anthropic `input_schema`
and routes the model's `tool_use` blocks back to the server that owns them.

## Development

```bash
cd cli_project
python -m pytest -q          # run tests
ruff check .                 # lint
ruff format .                # format
```

CI (`.github/workflows/ci.yml`) runs lint + tests on Python 3.10–3.13 for every
push and pull request.

## Configuration reference

| Variable | Purpose | Default |
|---|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API key (required) | — |
| `CLAUDE_MODEL` | Model ID, e.g. `claude-sonnet-5` (required) | — |
| `DOCS_DIR` | Where the server looks for documents | `cli_project/docs` |
| `MCP_TRANSPORT` | `stdio` or `http` | `stdio` |
| `MCP_SERVER_URL` | Server URL for `http` transport | `http://localhost:8000/mcp` |

## Roadmap

See [ROADMAP.md](../ROADMAP.md) — it's also the backlog for the daily
improvement commits landing on this repo.
