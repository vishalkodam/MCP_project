"""Tests for the server's DocumentStore."""

import pytest

from mcp_server import DocumentStore


def test_list_ids(tmp_path):
    (tmp_path / "b.md").write_text("b")
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / ".hidden").write_text("hidden")
    store = DocumentStore(tmp_path)
    assert store.list_ids() == ["a.txt", "b.md"]


def test_read_and_edit_markdown(tmp_path):
    (tmp_path / "a.md").write_text("# Title\nhello world", encoding="utf-8")
    store = DocumentStore(tmp_path)
    assert "hello world" in store.read("a.md")
    updated = store.edit("a.md", "hello", "goodbye")
    assert "goodbye world" in updated
    assert "goodbye world" in (tmp_path / "a.md").read_text(encoding="utf-8")


def test_read_missing_doc_raises(tmp_path):
    store = DocumentStore(tmp_path)
    with pytest.raises(ValueError, match="not found"):
        store.read("nope.md")


def test_path_traversal_is_blocked(tmp_path):
    store = DocumentStore(tmp_path)
    for bad_id in ("../secret.md", "..\\secret.md", ".hidden", ""):
        with pytest.raises(ValueError, match="Invalid document|not found"):
            store.read(bad_id)


def test_edit_missing_text_raises(tmp_path):
    (tmp_path / "a.md").write_text("hello", encoding="utf-8")
    store = DocumentStore(tmp_path)
    with pytest.raises(ValueError, match="not found"):
        store.edit("a.md", "absent", "x")


def test_edit_rejects_binary_types(tmp_path):
    (tmp_path / "doc.pdf").write_bytes(b"%PDF-1.4 fake")
    store = DocumentStore(tmp_path)
    with pytest.raises(ValueError, match="only supported for text"):
        store.edit("doc.pdf", "a", "b")


def test_creates_docs_dir_if_missing(tmp_path):
    nested = tmp_path / "docs"
    store = DocumentStore(nested)
    assert nested.is_dir()
    assert store.list_ids() == []
