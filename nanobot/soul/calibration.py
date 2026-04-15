"""Monthly soul calibration generation and scheduling."""

from __future__ import annotations

from pathlib import Path

from nanobot.cron.types import CronJob, CronPayload, CronSchedule
from nanobot.soul.anchor import AnchorManager
from nanobot.soul.profile import SoulProfileManager


class MonthlyCalibrationBuilder:
    """Build a monthly calibration report from current soul state."""

    def render(self, payload: dict) -> str:
        summary = payload.get("summary", "")
        anchor_state = payload.get("anchor_state", "")
        stage = payload.get("relationship_stage", "")
        return (
            "# 月校准报告\n\n"
            f"## 本月总体结论\n{summary}\n\n"
            f"## 锚点一致性\n{anchor_state or '（暂无）'}\n\n"
            f"## 当前关系阶段\n{stage or '（未知）'}\n"
        )

    def build(self, workspace: Path) -> str:
        anchor_text = AnchorManager(workspace).read_text()
        profile = SoulProfileManager(workspace).read()
        stage = profile.get("relationship", {}).get("stage", "熟悉")
        summary = "本月自动校准已生成，后续将接入更完整的偏移与风险审视逻辑。"
        anchor_state = "已读取核心锚点" if anchor_text else "未发现核心锚点文件"
        return self.render({
            "summary": summary,
            "anchor_state": anchor_state,
            "relationship_stage": stage,
        })


def build_monthly_calibration_job(timezone: str) -> CronJob:
    """Build the monthly calibration system job definition."""

    return CronJob(
        id="monthly_calibration",
        name="monthly_calibration",
        schedule=CronSchedule(kind="cron", expr="0 4 1 * *", tz=timezone),
        payload=CronPayload(kind="system_event"),
    )
