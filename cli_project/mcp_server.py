"""Document MCP server.

Exposes document tools, resources and prompts over the Model Context Protocol
using FastMCP.

Run over stdio (default — used by the chat CLI)::

    python mcp_server.py

Run over Streamable HTTP (for remote clients such as Claude Desktop)::

    python mcp_server.py --transport http --port 8000
"""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

from fastmcp import FastMCP
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

DOCS_DIR = Path(os.getenv("DOCS_DIR", Path(__file__).resolve().parent / "docs"))
TEXT_SUFFIXES = {".md", ".markdown", ".txt", ".rst"}


class DocumentStore:
    """Reads documents from a directory on disk.

    Plain text and Markdown are read directly; PDF and Word documents are
    parsed with optional dependencies (``pypdf`` / ``python-docx``).
    """

    def __init__(self, docs_dir: Path = DOCS_DIR) -> None:
        self.docs_dir = docs_dir
        self.docs_dir.mkdir(parents=True, exist_ok=True)

    def list_ids(self) -> list[str]:
        """Return the sorted IDs (file names) of all documents."""
        return sorted(
            p.name for p in self.docs_dir.iterdir() if p.is_file() and not p.name.startswith(".")
        )

    def read(self, doc_id: str) -> str:
        """Return the full text of a document."""
        path = self._resolve(doc_id)
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            return self._read_pdf(path)
        if suffix == ".docx":
            return self._read_docx(path)
        return path.read_text(encoding="utf-8")

    def edit(self, doc_id: str, old_string: str, new_string: str) -> str:
        """Replace ``old_string`` with ``new_string`` in a text document.

        Returns the updated document content.
        """
        path = self._resolve(doc_id)
        if path.suffix.lower() not in TEXT_SUFFIXES:
            raise ValueError(f"Editing is only supported for text documents, not {doc_id}")
        content = path.read_text(encoding="utf-8")
        if old_string not in content:
            raise ValueError(f"Text to replace was not found in {doc_id}")
        path.write_text(content.replace(old_string, new_string), encoding="utf-8")
        return path.read_text(encoding="utf-8")

    def _resolve(self, doc_id: str) -> Path:
        if not doc_id or "/" in doc_id or "\\" in doc_id or doc_id.startswith("."):
            raise ValueError(f"Invalid document id: {doc_id!r}")
        path = self.docs_dir / doc_id
        if not path.is_file():
            raise ValueError(f"Document {doc_id} not found.")
        return path

    @staticmethod
    def _read_pdf(path: Path) -> str:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)

    @staticmethod
    def _read_docx(path: Path) -> str:
        from docx import Document

        doc = Document(str(path))
        return "\n".join(paragraph.text for paragraph in doc.paragraphs)


store = DocumentStore()

mcp = FastMCP("DocumentMCP")


class EditResult(BaseModel):
    """Structured result of an edit_document call."""

    doc_id: str = Field(description="ID of the edited document.")
    updated_content: str = Field(description="Full updated content of the document.")


@mcp.tool()
def read_doc_contents(
    doc_id: str = Field(description="The ID of the document to read."),
) -> str:
    """Read the contents of a document and return it as a string."""
    return store.read(doc_id)


@mcp.tool()
def edit_document(
    doc_id: str = Field(description="ID of the document to edit."),
    old_string: str = Field(
        description="The text to replace. Must match exactly, including whitespace."
    ),
    new_string: str = Field(description="The new text to insert in place of the old text."),
) -> EditResult:
    """Edit a text document by replacing a string. Returns the updated content."""
    return EditResult(doc_id=doc_id, updated_content=store.edit(doc_id, old_string, new_string))


@mcp.tool()
def search_documents(
    query: str = Field(description="Text to search for across all documents."),
) -> list[str]:
    """Search every document for a text query. Returns the matching document IDs."""
    matches: list[str] = []
    needle = query.lower()
    for doc_id in store.list_ids():
        try:
            if needle in store.read(doc_id).lower():
                matches.append(doc_id)
        except Exception as exc:  # unreadable file — skip, don't fail the search
            logger.warning("Skipping %s during search: %s", doc_id, exc)
    return matches


@mcp.resource("docs://documents", mime_type="application/json")
def list_docs() -> list[str]:
    """List the IDs of all available documents."""
    return store.list_ids()


@mcp.resource("docs://documents/{doc_id}", mime_type="text/plain")
def fetch_doc(doc_id: str) -> str:
    """Fetch the full text of a single document."""
    return store.read(doc_id)


@mcp.prompt()
def format(
    doc_id: str = Field(description="The ID of the document to format."),
) -> str:
    """Rewrite a document's contents in clean Markdown format."""
    return f"""Your goal is to reformat a document using Markdown syntax.

The id of the document you need to reformat is:
<document id>
{doc_id}
</document id>

Add headers, bullet points, tables, etc. as necessary. Feel free to add extra
whitespace as needed. Use the 'edit_document' tool to make changes to the
document. Once you are done, return the updated document.
"""


@mcp.prompt()
def summarize(
    doc_id: str = Field(description="The ID of the document to summarize."),
) -> str:
    """Summarize a document into a few bullet points."""
    return f"""Summarize the following document in 3-5 concise bullet points,
capturing the key facts and any action items.

The id of the document to summarize is:
<document id>
{doc_id}
</document id>

Use the 'read_doc_contents' tool to read it first if you don't already have
its contents.
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Document MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default=os.getenv("MCP_TRANSPORT", "stdio"),
        help="Transport to serve on (default: stdio).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("MCP_PORT", "8000")),
        help="Port for the http transport (default: 8000).",
    )
    args = parser.parse_args()

    if args.transport == "http":
        mcp.run(transport="http", port=args.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
