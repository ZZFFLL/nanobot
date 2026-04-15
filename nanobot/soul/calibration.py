"""Monthly soul calibration generation and scheduling."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from nanobot.cron.types import CronJob, CronPayload, CronSchedule
from nanobot.soul.anchor import AnchorManager
from nanobot.soul.profile import SoulProfileManager


def _read_optional(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


class MonthlyCalibrationBuilder:
    """Build a monthly calibration report from current soul state."""

    @staticmethod
    def _sanitize_section_body(text: str) -> str:
        # Prevent payload text from creating extra markdown H2 sections.
        lines = text.splitlines()
        return "\n".join(f"\\{line}" if line.startswith("## ") else line for line in lines)

    def render(self, payload: Mapping[str, str]) -> str:
        summary = self._sanitize_section_body(payload.get("summary", ""))
        anchor_state = self._sanitize_section_body(payload.get("anchor_state", ""))
        relationship_check = self._sanitize_section_body(payload.get("relationship_check", ""))
        risks = self._sanitize_section_body(payload.get("risks", ""))
        actions = self._sanitize_section_body(payload.get("actions", ""))
        return (
            "# 月校准报告\n\n"
            f"## 本月总体结论\n{summary or '（暂无）'}\n\n"
            f"## 锚点一致性\n{anchor_state or '（暂无）'}\n\n"
            f"## 关系演化校验\n{relationship_check or '（暂无）'}\n\n"
            f"## 风险与偏移点\n{risks or '（暂无）'}\n\n"
            f"## 建议动作\n{actions or '（暂无）'}\n"
        )

    def build(self, workspace: Path) -> str:
        anchor_text = AnchorManager(workspace).read_text()
        soul_text = _read_optional(workspace / "SOUL.md")
        heart_text = _read_optional(workspace / "HEART.md")
        profile = SoulProfileManager(workspace).read()
        stage = profile.get("relationship", {}).get("stage", "还不认识")

        summary = "本月已完成最小校准，后续可继续增强。"
        anchor_state = "已读取核心锚点" if anchor_text else "未发现核心锚点文件"

        soul_state = "SOUL.md 已加载" if soul_text else "SOUL.md 缺失或为空"
        heart_state = "HEART.md 已加载" if heart_text else "HEART.md 缺失或为空"

        relationship_check = f"当前关系阶段为 {stage}，需结合周复盘继续观察是否存在异常跳变。"
        risks = (
            "本节为最小规则校验：仅检查文件存在/可读与基础字段读取，未做越界判定。\n"
            "若 SOUL/HEART/PROFILE 数据缺失或长期不一致，需人工复核一致性与边界风险。\n\n"
            f"- {soul_state}\n"
            f"- {heart_state}"
        )
        actions = (
            "- 保留：当前锚点与阶段状态\n"
            "- 观察：关系变化与热状态波动\n"
            "- 人工复核：若出现连续异常跳变"
        )

        return self.render({
            "summary": summary,
            "anchor_state": anchor_state,
            "relationship_check": relationship_check,
            "risks": risks,
            "actions": actions,
        })


def build_monthly_calibration_job(timezone: str) -> CronJob:
    """Build the monthly calibration system job definition."""

    return CronJob(
        id="monthly_calibration",
        name="monthly_calibration",
        schedule=CronSchedule(kind="cron", expr="0 4 1 * *", tz=timezone),
        payload=CronPayload(kind="system_event"),
    )
