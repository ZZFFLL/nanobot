"""Life event management — EVENTS.md read/write."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path


@dataclass
class LifeEvent:
    """A life event entry."""

    type: str          # birthday / anniversary / user_birthday / custom
    date: str          # YYYY-MM-DD — triggers annually by month+day
    description: str
    behavior: str      # behavior description when triggered


class EventsManager:
    """Manage EVENTS.md file for life events."""

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.events_file = workspace / "EVENTS.md"

    def initialize(
        self,
        ai_name: str,
        ai_birthday: str,
        user_name: str = "用户",
        user_birthday: str | None = None,
    ) -> None:
        """Initialize EVENTS.md with default events."""
        events: list[LifeEvent] = [
            LifeEvent(
                type="birthday",
                date=ai_birthday,
                description=f"{ai_name}的生日",
                behavior="主动提醒用户，表达期待和撒娇",
            ),
        ]
        if user_birthday:
            events.append(LifeEvent(
                type="user_birthday",
                date=user_birthday,
                description=f"{user_name}的生日",
                behavior="主动祝福，表达在意和关心",
            ))
        # Anniversary = today (the day they met)
        today = date.today().isoformat()
        events.append(LifeEvent(
            type="anniversary",
            date=today,
            description=f"{ai_name}和{user_name}认识的第一天",
            behavior="主动回忆初次对话，感慨关系变化",
        ))
        self._write_events(events)

    def read_events(self) -> list[LifeEvent]:
        """Read all events from EVENTS.md."""
        if not self.events_file.exists():
            return []
        text = self.events_file.read_text(encoding="utf-8")
        return self._parse_events(text)

    def add_event(self, event: LifeEvent) -> None:
        """Add a single event, preserving existing ones."""
        events = self.read_events()
        events.append(event)
        self._write_events(events)

    def check_today(self) -> list[LifeEvent]:
        """Check if any event matches today (by month+day, year is ignored)."""
        today = date.today()
        events = self.read_events()
        matches: list[LifeEvent] = []
        for e in events:
            try:
                event_date = date.fromisoformat(e.date)
                if event_date.month == today.month and event_date.day == today.day:
                    matches.append(e)
            except ValueError:
                continue
        return matches

    # ── Private ──────────────────────────────────────────────────────

    def _write_events(self, events: list[LifeEvent]) -> None:
        """Write events to EVENTS.md in Markdown format."""
        lines = ["# 生活事件日历", ""]
        for e in events:
            lines.append(f"## [{e.type}] {e.description}")
            lines.append(f"- 日期: {e.date}")
            lines.append(f"- 行为: {e.behavior}")
            lines.append("")
        self.events_file.write_text("\n".join(lines), encoding="utf-8")

    @staticmethod
    def _parse_events(text: str) -> list[LifeEvent]:
        """Parse EVENTS.md Markdown format."""
        events: list[LifeEvent] = []
        # Split by event headers: ## [type] description
        pattern = re.compile(r"##\s*\[(\w+)\]\s*(.+)")
        date_pattern = re.compile(r"-\s*日期:\s*(.+)")
        behavior_pattern = re.compile(r"-\s*行为:\s*(.+)")

        current_type = ""
        current_desc = ""
        current_date = ""
        current_behavior = ""

        for line in text.splitlines():
            header_match = pattern.match(line)
            if header_match:
                # Save previous event if any
                if current_type:
                    events.append(LifeEvent(
                        type=current_type,
                        date=current_date.strip(),
                        description=current_desc.strip(),
                        behavior=current_behavior.strip(),
                    ))
                current_type = header_match.group(1)
                current_desc = header_match.group(2)
                current_date = ""
                current_behavior = ""
                continue

            date_match = date_pattern.match(line)
            if date_match:
                current_date = date_match.group(1)
                continue

            behavior_match = behavior_pattern.match(line)
            if behavior_match:
                current_behavior = behavior_match.group(1)
                continue

        # Don't forget the last event
        if current_type:
            events.append(LifeEvent(
                type=current_type,
                date=current_date.strip(),
                description=current_desc.strip(),
                behavior=current_behavior.strip(),
            ))

        return events
