"""mempalace bridge — unified interface for memory read/write."""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

from loguru import logger

# Detect mempalace availability
try:
    from mempalace.mcp_server import tool_add_drawer
    from mempalace.searcher import search_memories
    mempalace_available = True
except ImportError:
    tool_add_drawer = None  # type: ignore[assignment,misc]
    search_memories = None  # type: ignore[assignment,misc]
    mempalace_available = False

# mempalace sanitize_name only allows [a-zA-Z0-9_ .'-]
_SAFE_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_ .'\-]{0,126}[a-zA-Z0-9]?$")


def _to_wing_slug(name: str) -> str:
    """Convert a display name to a mempalace-safe wing slug.

    Chinese names like '温予安' become pinyin-like slugs like 'wenyuan'.
    Non-ASCII characters are transliterated; spaces become hyphens.
    """
    # Try transliteration (e.g. Chinese → pinyin via unicodedata)
    ascii_name = unicodedata.normalize("NFKD", name)
    ascii_name = ascii_name.encode("ascii", "ignore").decode("ascii")
    if ascii_name.strip():
        slug = re.sub(r"[^a-zA-Z0-9_ .'-]+", "-", ascii_name).strip("-")
        slug = re.sub(r"-+", "-", slug)
        if slug and _SAFE_NAME_RE.match(slug):
            return slug

    # Fallback: use a fixed slug
    return "ai-wing"


class MemoryPalaceBridge:
    """Bridge to mempalace for memory operations."""

    DEFAULT_USER_WING = "user"

    def __init__(
        self,
        palace_path: str | None = None,
        workspace: Path | None = None,
        user_wing: str | None = None,
    ) -> None:
        self.palace_path = palace_path or self._resolve_palace_path()
        self.workspace = workspace
        self._user_wing = user_wing or self.DEFAULT_USER_WING
        self._ai_wing: str | None = None
        self._ai_wing_display: str | None = None

    @property
    def ai_wing(self) -> str:
        """mempalace-safe wing slug for AI (e.g. 'wenyuan')."""
        if self._ai_wing is None:
            display = self._read_identity_name() or "数字生命"
            self._ai_wing_display = display
            self._ai_wing = _to_wing_slug(display)
        return self._ai_wing

    @property
    def user_wing(self) -> str:
        return self._user_wing

    def update_user_wing(self, name: str) -> None:
        """Update user's wing name. Ignores empty or same name."""
        if not name or not name.strip():
            return
        slug = _to_wing_slug(name)
        if slug != self._user_wing:
            old = self._user_wing
            self._user_wing = slug
            logger.info("User wing name updated: {} -> {}", old, slug)

    @staticmethod
    def _resolve_palace_path() -> str | None:
        """Read palace_path from mempalace config, falling back to default."""
        try:
            import json as _json

            from mempalace.config import DEFAULT_PALACE_PATH

            config_path = Path.home() / ".mempalace" / "config.json"
            if config_path.exists():
                data = _json.loads(config_path.read_text(encoding="utf-8"))
                return data.get("palace_path") or str(DEFAULT_PALACE_PATH)
            return str(DEFAULT_PALACE_PATH)
        except Exception:
            return None

    def _read_identity_name(self) -> str | None:
        if not self.workspace:
            return None
        identity_file = self.workspace / "IDENTITY.md"
        if not identity_file.exists():
            return None
        text = identity_file.read_text(encoding="utf-8")
        for line in text.splitlines():
            line = line.strip()
            if line.lower().startswith("name:"):
                return line.split(":", 1)[1].strip()
        return None

    async def add_drawer(
        self,
        wing: str,
        room: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Add a memory drawer to mempalace. Returns True on success."""
        if not mempalace_available:
            logger.debug("mempalace unavailable, skipping memory write")
            return False
        try:
            result = tool_add_drawer(
                wing=wing,
                room=room,
                content=content,
                added_by="soul",
            )
            return result.get("success", False)
        except Exception:
            logger.exception("mempalace add_drawer failed: wing={}, room={}", wing, room)
            return False

    async def search(
        self,
        query: str,
        wing: str | None = None,
        room: str | None = None,
        n_results: int = 5,
    ) -> list[dict[str, Any]]:
        """Semantic search in mempalace. Returns list of result dicts."""
        if not mempalace_available:
            return []
        try:
            result = search_memories(
                query=query,
                palace_path=self.palace_path or "",
                wing=wing,
                room=room,
                n_results=n_results,
            )
            return result.get("results", [])
        except Exception:
            logger.exception("mempalace search failed")
            return []
