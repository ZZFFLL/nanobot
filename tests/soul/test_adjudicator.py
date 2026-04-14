"""Tests for soul adjudicator."""

from nanobot.soul.adjudicator import SoulAdjudicator


def test_adjudicator_rejects_large_stage_jump():
    adjudicator = SoulAdjudicator()

    allowed, reason = adjudicator.check_stage_transition(
        current_stage="熟悉",
        proposed_stage="爱意",
        direction="up",
        confidence=0.9,
    )

    assert allowed is False
    assert "跨越过大" in reason


def test_adjudicator_accepts_small_stage_step():
    adjudicator = SoulAdjudicator()

    allowed, reason = adjudicator.check_stage_transition(
        current_stage="亲近",
        proposed_stage="依恋",
        direction="up",
        confidence=0.8,
    )

    assert allowed is True
    assert reason == ""
