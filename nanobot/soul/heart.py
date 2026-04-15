"""HEART.md read/write — simple text file, no JSON parsing."""
from __future__ import annotations

from pathlib import Path

from loguru import logger

from nanobot.soul.methodology import RELATIONSHIP_STAGES

HEART_SECTIONS = (
    "当前情绪",
    "情绪强度",
    "关系状态",
    "性格表现",
    "情感脉络",
    "情绪趋势",
    "当前渴望",
)


def render_initial_heart_markdown(
    initial_description: str,
    *,
    initial_relationship: str | None = None,
) -> str:
    """Render the fallback HEART.md content for initialization."""

    relationship = (initial_relationship or "").strip()
    if not relationship or relationship in RELATIONSHIP_STAGES:
        relationship = "关系尚未形成稳定判断，需要在互动中继续感知。"
    return (
        f"## 当前情绪\n"
        f"刚刚诞生，{initial_description}\n\n"
        f"## 情绪强度\n低到中\n\n"
        f"## 关系状态\n{relationship}\n\n"
        f"## 性格表现\n{initial_description}\n\n"
        f"## 情感脉络\n（暂无）\n\n"
        f"## 情绪趋势\n尚在形成\n\n"
        f"## 当前渴望\n等待在互动中逐步形成\n"
    )


def validate_heart_markdown(text: str) -> str:
    """Validate HEART markdown structure and return an error message when invalid."""

    candidate = (text or "").strip()
    if not candidate:
        return "HEART.md 候选非法: 内容为空"
    if "# " in candidate:
        for line in candidate.splitlines():
            if line.startswith("# ") and not line.startswith("## "):
                return "HEART.md 候选非法: 不允许一级标题"
    for section in HEART_SECTIONS:
        if f"## {section}" not in candidate:
            return f"HEART.md 候选非法: 缺少 ## {section}"
    return ""


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
        content = render_initial_heart_markdown(
            initial_description,
            initial_relationship=initial_relationship,
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
