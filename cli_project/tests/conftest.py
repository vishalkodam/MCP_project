"""Pytest bootstrap: give the server a throwaway docs dir for tests."""

import os
from pathlib import Path

TEST_DOCS = Path(__file__).parent / "test_docs"
TEST_DOCS.mkdir(exist_ok=True)
(TEST_DOCS / "hello.md").write_text("# Hello\nThis is a test document.\n", encoding="utf-8")
(TEST_DOCS / "data.txt").write_text("alpha beta gamma", encoding="utf-8")

os.environ.setdefault("DOCS_DIR", str(TEST_DOCS))
