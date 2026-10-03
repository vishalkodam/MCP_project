# Project notes

A second sample document, so `@`-mentions and search have something to chew on.

## Roadmap ideas

- Elicitation: let tools ask the user questions mid-call.
- Stream responses instead of waiting for the full reply.
- Persist conversation history between sessions.

## Stack

- Server: FastMCP 4.x (Model Context Protocol, spec 2026-07-28)
- Client: fastmcp.Client (stdio + Streamable HTTP)
- Model: Anthropic Messages API with tool use
- CLI: prompt-toolkit
