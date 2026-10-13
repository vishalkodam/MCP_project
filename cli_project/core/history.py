"""Conversation history persistence (Day 5).

The chat history is saved as JSON after every model turn, so a conversation
survives restarts. ``HistoryStore`` owns the file; ``Chat`` wires it in and
``/history`` browses what is stored.
"""

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import List

from anthropic.types import MessageParam

logger = logging.getLogger(__name__)

#: Where history lives when no explicit path is given.
DEFAULT_HISTORY_PATH = Path.home() / ".mcp_chat" / "history.json"


def _jsonable(value):
    """Convert a value into plain JSON-safe types.

    In-memory messages may hold Anthropic SDK block objects (pydantic models),
    which ``json.dump`` cannot serialize. Those are converted via
    ``model_dump()``; anything else exotic falls back to ``str()``.
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return _jsonable(model_dump())
    return str(value)


class HistoryStore:
    """Load/save conversation messages as a JSON file, written atomically."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path is not None else DEFAULT_HISTORY_PATH

    def load(self) -> List[MessageParam]:
        """Return the stored messages, or [] when there is nothing usable.

        A missing, unreadable, or corrupt file is not fatal: the chat simply
        starts with an empty history.
        """
        try:
            raw = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return []
        except OSError as exc:
            logger.warning("Could not read history file %s: %s", self.path, exc)
            return []
        try:
            messages = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.warning("History file %s is not valid JSON, starting fresh: %s", self.path, exc)
            return []
        if not isinstance(messages, list):
            logger.warning(
                "History file %s does not hold a message list, starting fresh.",
                self.path,
            )
            return []
        return messages

    def save(self, messages: List[MessageParam]) -> None:
        """Write messages to disk via temp file + rename, so a crash can never
        leave a half-written history file behind."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=self.path.parent, prefix=self.path.name, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as tmp:
                json.dump(_jsonable(messages), tmp, ensure_ascii=False, indent=2)
            os.replace(tmp_name, self.path)
        except BaseException:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise
