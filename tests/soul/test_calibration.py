"""Tests for monthly soul calibration generation."""

from nanobot.soul.calibration import (
    MonthlyCalibrationBuilder,
    build_monthly_calibration_job,
)


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
