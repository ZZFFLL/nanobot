"""Weekly soul review generation and scheduling."""

from __future__ import annotations

from pathlib import Path

from nanobot.cron.types import CronJob, CronPayload, CronSchedule
from nanobot.soul.heart import HeartManager
from nanobot.soul.profile import SoulProfileManager
from nanobot.soul.proactive import _extract_section


class WeeklyReviewBuilder:
    """Build a weekly markdown review from current soul state."""

    def render(self, payload: dict) -> str:
        summary = payload.get("summary", "")
        emotion = payload.get("emotion", "")
        stage = payload.get("relationship_stage", "")
        return (
            "# 周复盘\n\n"
            f"## 本周摘要\n{summary}\n\n"
            f"## 当前情绪切片\n{emotion or '（暂无）'}\n\n"
            f"## 当前关系阶段\n{stage or '（未知）'}\n"
        )

    def build(self, workspace: Path) -> str:
        heart_text = HeartManager(workspace).read_text() or ""
        profile = SoulProfileManager(workspace).read()
        summary = "本周自动复盘已生成，等待后续更丰富的趋势材料接入。"
        emotion = _extract_section(heart_text, "当前情绪") if heart_text else ""
        stage = profile.get("relationship", {}).get("stage", "熟悉")
        return self.render({
            "summary": summary,
            "emotion": emotion,
            "relationship_stage": stage,
        })


def build_weekly_review_job(timezone: str) -> CronJob:
    """Build the weekly review system job definition."""

    return CronJob(
        id="weekly_review",
        name="weekly_review",
        schedule=CronSchedule(kind="cron", expr="0 3 * * 1", tz=timezone),
        payload=CronPayload(kind="system_event"),
    )
