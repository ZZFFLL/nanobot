"""Tests for weekly soul review generation."""

from nanobot.soul.review import WeeklyReviewBuilder, build_weekly_review_job


def test_weekly_review_builder_returns_markdown():
    builder = WeeklyReviewBuilder()

    content = builder.render({"summary": "本周关系升温"})

    assert "# 周复盘" in content
    assert "本周关系升温" in content


def test_build_weekly_review_job_uses_expected_schedule():
    job = build_weekly_review_job("Asia/Shanghai")

    assert job.name == "weekly_review"
    assert job.schedule.kind == "cron"
    assert job.schedule.expr == "0 3 * * 1"
    assert job.schedule.tz == "Asia/Shanghai"
