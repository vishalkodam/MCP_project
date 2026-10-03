# Welcome to MCP Chat

This is a sample document. Drop your own `.md`, `.txt`, `.pdf`, or `.docx`
files into this `docs/` folder and the document server will pick them up
automatically.

Try these in the chat:

- `Tell me about @welcome.md`
- `/summarize welcome.md`
- `/format welcome.md`

## How it works

The `mcp_server.py` next door exposes every file in this folder as MCP
resources (`docs://documents/...`), plus tools to read, edit, and search them.
The chat client (`main.py`) hands those tools to Claude, so the model can pull
in document content whenever it's useful.
