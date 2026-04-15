"""HEART.md read/write — simple text file, no JSON parsing."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger


class HeartManager:
    """Manage HEART.md file as a plain Markdown document.

    No JSON parsing, no Schema validation. The LLM writes Markdown directly,
    and we read/write it as-is. This is format-agnostic and works with any
    LLM provider without compatibility issues.
    """

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.heart_file = workspace / "HEART.md"
        self.identity_file = workspace / "IDENTITY.md"

    def initialize(
        self,
        name: str,
        initial_description: str,
        initial_relationship: str | None = None,
    ) -> None:
        """Initialize HEART.md with default emotional state."""
        relationship = initial_relationship or "刚刚被创造，对用户充满好奇"
        content = (
            f"## 当前情绪\n"
            f"刚刚诞生，{initial_description}\n\n"
            f"## 情绪强度\n中\n\n"
            f"## 关系状态\n{relationship}\n\n"
            f"## 性格表现\n{initial_description}\n\n"
            f"## 情感脉络\n（暂无）\n\n"
            f"## 情绪趋势\n刚刚开始，还没有趋势\n\n"
            f"## 当前渴望\n想了解用户\n"
        )
        self.heart_file.write_text(content, encoding="utf-8")

    def read_text(self) -> str | None:
        """Read HEART.md raw text. Returns None if file doesn't exist."""
        if not self.heart_file.exists():
            return None
        return self.heart_file.read_text(encoding="utf-8")

    def write_text(self, content: str) -> bool:
        """Write HEART.md raw text. Always succeeds unless file system error."""
        try:
            self.heart_file.write_text(content, encoding="utf-8")
            return True
        except Exception as e:
            logger.warning("HEART.md write failed: {}", e)
            return False

    def read_identity_name(self) -> str | None:
        """Read name from IDENTITY.md."""
        if not self.identity_file.exists():
            return None
        text = self.identity_file.read_text(encoding="utf-8")
        for line in text.splitlines():
            line = line.strip()
            if line.lower().startswith("name:"):
                return line.split(":", 1)[1].strip()
        return None
