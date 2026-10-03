"""MCP Chat — a CLI for chatting with Claude, powered by MCP document tools."""

import argparse
import asyncio
import logging
import os
import sys
from contextlib import AsyncExitStack
from pathlib import Path

from dotenv import load_dotenv

from core.claude import Claude
from core.cli import CliApp
from core.cli_chat import CliChat
from mcp_client import MCPClient

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Chat with Claude using MCP document tools.")
    parser.add_argument(
        "servers",
        nargs="*",
        help="Additional MCP server scripts to connect over stdio.",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default=os.getenv("MCP_TRANSPORT", "stdio"),
        help="How to reach the document server (default: stdio).",
    )
    parser.add_argument(
        "--server-url",
        default=os.getenv("MCP_SERVER_URL", "http://localhost:8000/mcp"),
        help="Streamable HTTP URL of the document server (for --transport http).",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging.")
    return parser.parse_args()


async def amain(args: argparse.Namespace) -> None:
    load_dotenv()

    model = os.getenv("CLAUDE_MODEL", "")
    if not model:
        raise SystemExit("Set CLAUDE_MODEL in your .env file (e.g. CLAUDE_MODEL=claude-sonnet-5).")
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise SystemExit("Set ANTHROPIC_API_KEY in your .env file.")

    claude_service = Claude(model=model)
    clients: dict[str, MCPClient] = {}

    async with AsyncExitStack() as stack:
        if args.transport == "http":
            logger.info("Connecting to document server at %s", args.server_url)
            doc_client = await stack.enter_async_context(MCPClient(url=args.server_url))
        else:
            server_script = BASE_DIR / "mcp_server.py"
            logger.info("Spawning document server: %s", server_script)
            doc_client = await stack.enter_async_context(
                MCPClient(script=server_script, cwd=BASE_DIR)
            )
        clients["documents"] = doc_client

        for i, server_script in enumerate(args.servers):
            client = await stack.enter_async_context(MCPClient(script=server_script))
            clients[f"server_{i}"] = client

        chat = CliChat(
            doc_client=doc_client,
            clients=clients,
            claude_service=claude_service,
        )

        cli = CliApp(chat)
        await cli.initialize()
        await cli.run()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(amain(args))


if __name__ == "__main__":
    main()
