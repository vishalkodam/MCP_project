"""Unit tests for DocsWatcher: polling a docs dir for changes."""

from mcp_server import DocsWatcher


def test_poll_empty_dir_reports_nothing(tmp_path):
    watcher = DocsWatcher(tmp_path)
    changes = watcher.poll()
    assert (changes.added, changes.modified, changes.removed, changes.documents) == (
        [],
        [],
        [],
        [],
    )


def test_poll_detects_added_modified_and_removed(tmp_path):
    (tmp_path / "a.md").write_text("one", encoding="utf-8")
    watcher = DocsWatcher(tmp_path)

    (tmp_path / "b.txt").write_text("two", encoding="utf-8")
    (tmp_path / "a.md").write_text("one two three", encoding="utf-8")
    (tmp_path / "gone.md").write_text("x", encoding="utf-8")
    watcher.poll()  # baseline now includes b.txt and gone.md
    (tmp_path / "gone.md").unlink()
    (tmp_path / "a.md").write_text("one two three four", encoding="utf-8")

    changes = watcher.poll()
    assert changes.added == []
    assert changes.modified == ["a.md"]
    assert changes.removed == ["gone.md"]
    assert changes.documents == ["a.md", "b.txt"]

    # A second poll with no changes is quiet.
    again = watcher.poll()
    assert (again.added, again.modified, again.removed) == ([], [], [])


def test_poll_ignores_dotfiles(tmp_path):
    (tmp_path / ".hidden").write_text("secret", encoding="utf-8")
    watcher = DocsWatcher(tmp_path)
    (tmp_path / ".hidden").write_text("changed secret", encoding="utf-8")
    changes = watcher.poll()
    assert (changes.added, changes.modified, changes.removed, changes.documents) == (
        [],
        [],
        [],
        [],
    )


def test_poll_handles_missing_dir(tmp_path):
    watcher = DocsWatcher(tmp_path / "does-not-exist")
    changes = watcher.poll()
    assert changes.documents == []
