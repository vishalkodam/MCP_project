# 30-Day Improvement Roadmap

One focused improvement per day. Check an item off when its commit lands.
The daily job works top-down: take the first unchecked item, implement it,
run `ruff check`, `ruff format --check`, and `pytest`, then commit.

## Week 1 — Polish & robustness

- [x] Day 1: Add a `/clear` chat command that resets the conversation history.
- [x] Day 2: Add a `/tools` chat command listing available MCP tools and descriptions.
- [x] Day 3: Stream model responses token-by-token instead of waiting for the full reply.
- [ ] Day 4: Print token usage and an estimated cost after each turn.
- [ ] Day 5: Persist conversation history to disk and add `/history` to browse it.

## Week 2 — Server features

- [ ] Day 6: Add a `get_doc_stats` tool (word count, size, file type per document).
- [ ] Day 7: Add an `append_to_doc` tool for appending text to documents.
- [ ] Day 8: Add regex support to `search_documents` via a `regex: bool` flag.
- [ ] Day 9: Add an elicitation example — a `create_doc` tool that asks the user
  to confirm the file name mid-call.
- [ ] Day 10: Watch `docs/` for file changes and refresh the resource list live.

## Week 3 — Client & multi-server

- [ ] Day 11: Retry with backoff when a server subprocess fails to spawn.
- [ ] Day 12: Cache tool schemas per session instead of re-listing every turn.
- [ ] Day 13: Load extra servers from an `mcp.json` config file (stdio + http entries).
- [ ] Day 14: Support per-server env vars in the `mcp.json` config.
- [ ] Day 15: Namespace colliding tool names as `<server>__<tool>` instead of first-wins.

## Week 4 — Developer experience & docs

- [ ] Day 16: Add a `Dockerfile` for running the server standalone.
- [ ] Day 17: Add `CONTRIBUTING.md` (setup, tests, commit style).
- [ ] Day 18: Add a mermaid architecture diagram to the README.
- [ ] Day 19: Start `CHANGELOG.md` (Keep a Changelog format) and document 0.2.0.
- [ ] Day 20: Add an example second server (`examples/calculator_server.py`).

## Week 5 — Quality & CLI flags

- [ ] Day 21: Add tests for the CLI completer (`UnifiedCompleter`).
- [ ] Day 22: Add `ruff format --check` failure as a CI-blocking step (already runs; make it strict).
- [ ] Day 23: Add type checking with mypy to CI.
- [ ] Day 24: Handle Ctrl-C gracefully mid-stream without losing history.
- [ ] Day 25: Add `--model` and `--temperature` CLI flags overriding `.env`.

## Final stretch

- [ ] Day 26: Add `/export <file>` to save the conversation as Markdown.
- [ ] Day 27: Add a `summarize` variant that writes the summary back into the doc.
- [ ] Day 28: Demo progress notifications for a long-running tool.
- [ ] Day 29: Add a Troubleshooting section to the README from real issues hit.
- [ ] Day 30: Bump to v0.3.0, write release notes in CHANGELOG.md.
