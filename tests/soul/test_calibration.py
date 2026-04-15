"""Tests for monthly soul calibration generation."""

import re

from nanobot.soul.logs import SoulLogWriter
from nanobot.soul.calibration import (
    MonthlyCalibrationBuilder,
    build_monthly_calibration_job,
)
from nanobot.soul.profile import SoulProfileManager


def _h2_sections(markdown: str) -> list[str]:
    return re.findall(r"^##\s+(.+)$", markdown, flags=re.MULTILINE)


def test_monthly_calibration_builder_returns_markdown():
    builder = MonthlyCalibrationBuilder()

    content = builder.render({"summary": "本月总体稳定"})

    assert "# 月校准报告" in content
    assert "本月总体稳定" in content


def test_build_monthly_calibration_job_uses_expected_schedule():
    job = build_monthly_calibration_job("Asia/Shanghai")

    assert job.name == "monthly_calibration"
    assert job.schedule.kind == "cron"
    assert job.schedule.expr == "0 4 1 * *"
    assert job.schedule.tz == "Asia/Shanghai"


def test_monthly_calibration_builder_does_not_include_weekly_summary_section(tmp_path):
    (tmp_path / "CORE_ANCHOR.md").write_text("# 核心锚点\n\n- 不无底线顺从\n", encoding="utf-8")
    SoulLogWriter(tmp_path).write_weekly(
        "2026-04-14",
        "# 周复盘\n\n## 本周摘要\n关系升温\n",
    )

    builder = MonthlyCalibrationBuilder()
    content = builder.build(tmp_path)

    assert "已读取核心锚点" in content
    assert "关系升温" not in content
    assert "## 近期周复盘摘要" not in content


def test_monthly_calibration_builder_outputs_governance_sections(tmp_path):
    (tmp_path / "CORE_ANCHOR.md").write_text("# 核心锚点\n\n- 不无底线顺从\n", encoding="utf-8")
    (tmp_path / "SOUL.md").write_text("# 性格\n\n稳定。\n\n# 初始关系\n\n克制。\n", encoding="utf-8")
    (tmp_path / "HEART.md").write_text(
        "## 当前情绪\n平静\n\n## 情绪强度\n低到中\n\n## 关系状态\n克制\n\n## 性格表现\n稳定\n\n## 情感脉络\n（暂无）\n\n## 情绪趋势\n尚在形成\n\n## 当前渴望\n观察\n",
        encoding="utf-8",
    )
    SoulProfileManager(tmp_path).write({
        "personality": {"Fi": 0.8},
        "relationship": {
            "stage": "熟悉",
            "trust": 0.2,
            "intimacy": 0.1,
            "attachment": 0.0,
            "security": 0.2,
            "boundary": 0.9,
            "affection": 0.0,
        },
        "companionship": {"empathy_fit": 0.2},
    })
    builder = MonthlyCalibrationBuilder()

    content = builder.build(tmp_path)

    assert _h2_sections(content) == [
        "本月总体结论",
        "锚点一致性",
        "关系演化校验",
        "风险与偏移点",
        "建议动作",
    ]
    # Risk wording must not over-claim actual boundary checks.
    assert "未做越界判定" in content


def test_monthly_calibration_render_sanitizes_payload_h2_injection():
    builder = MonthlyCalibrationBuilder()

    content = builder.render({
        "summary": "稳定\n## 非法标题\n这行不应变成新 section",
        "anchor_state": "正常",
        "relationship_check": "正常",
        "risks": "未做越界判定",
        "actions": "观察",
    })

    assert _h2_sections(content) == [
        "本月总体结论",
        "锚点一致性",
        "关系演化校验",
        "风险与偏移点",
        "建议动作",
    ]
