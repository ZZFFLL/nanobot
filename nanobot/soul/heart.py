"""HEART.md read/write, format conversion and validation."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from loguru import logger

from nanobot.soul.schemas import validate_heart


class HeartManager:
    """Manage HEART.md file read/write and format conversion."""

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.heart_file = workspace / "HEART.md"
        self.identity_file = workspace / "IDENTITY.md"

    def initialize(self, name: str, initial_description: str) -> None:
        """Initialize HEART.md with default emotional state."""
        data = {
            "当前情绪": f"刚刚诞生，{initial_description}",
            "情绪强度": "中",
            "关系状态": "刚刚被创造，对用户充满好奇",
            "性格表现": initial_description,
            "情感脉络": [],
            "情绪趋势": "刚刚开始，还没有趋势",
            "当前渴望": "想了解用户",
        }
        md = self.render_markdown(data)
        self.heart_file.write_text(md, encoding="utf-8")

    def read(self) -> dict[str, Any] | None:
        """Read HEART.md and parse to dict. Returns None if file doesn't exist."""
        if not self.heart_file.exists():
            return None
        md = self.heart_file.read_text(encoding="utf-8")
        return self._parse_markdown(md)

    def write(self, data: dict[str, Any]) -> bool:
        """Write HEART.md. Validates first; on failure preserves old data and returns False."""
        try:
            validated = validate_heart(data)
        except Exception as e:
            logger.warning("HEART.md data validation failed: {}", e)
            return False
        md = self.render_markdown(validated)
        self.heart_file.write_text(md, encoding="utf-8")
        return True

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

    @staticmethod
    def render_markdown(data: dict[str, Any]) -> str:
        """Render dict to HEART.md Markdown format."""
        lines = []
        lines.append(f"## 当前情绪\n{data.get('当前情绪', '')}\n")
        lines.append(f"## 情绪强度\n{data.get('情绪强度', '中')}\n")
        lines.append(f"## 关系状态\n{data.get('关系状态', '')}\n")
        lines.append(f"## 性格表现\n{data.get('性格表现', '')}\n")

        arcs = data.get("情感脉络", [])
        arc_lines = ["## 情感脉络"]
        if arcs:
            for arc in arcs:
                arc_lines.append(
                    f"- [{arc.get('时间', '?')}] {arc.get('事件', '')} -> {arc.get('影响', '')}"
                )
        else:
            arc_lines.append("（暂无）")
        lines.append("\n".join(arc_lines) + "\n")

        lines.append(f"## 情绪趋势\n{data.get('情绪趋势', '')}\n")
        lines.append(f"## 当前渴望\n{data.get('当前渴望', '')}\n")

        return "\n".join(lines)

    @staticmethod
    def _parse_markdown(md: str) -> dict[str, Any]:
        """Parse HEART.md Markdown to dict."""
        sections: dict[str, str] = {}
        current_header = ""
        current_content: list[str] = []

        for line in md.splitlines():
            header_match = re.match(r"^## (.+)$", line.strip())
            if header_match:
                if current_header:
                    sections[current_header] = "\n".join(current_content).strip()
                current_header = header_match.group(1)
                current_content = []
            else:
                current_content.append(line)

        if current_header:
            sections[current_header] = "\n".join(current_content).strip()

        # Parse emotional arcs
        arcs = []
        arcs_text = sections.get("情感脉络", "")
        if arcs_text and arcs_text != "（暂无）":
            for line in arcs_text.splitlines():
                match = re.match(r"^- \[([^\]]+)\]\s*(.+?)\s*->\s*(.+)$", line.strip())
                if match:
                    arcs.append({
                        "时间": match.group(1),
                        "事件": match.group(2).strip(),
                        "影响": match.group(3).strip(),
                    })

        return {
            "当前情绪": sections.get("当前情绪", ""),
            "情绪强度": sections.get("情绪强度", "中"),
            "关系状态": sections.get("关系状态", ""),
            "性格表现": sections.get("性格表现", ""),
            "情感脉络": arcs,
            "情绪趋势": sections.get("情绪趋势", ""),
            "当前渴望": sections.get("当前渴望", ""),
        }
