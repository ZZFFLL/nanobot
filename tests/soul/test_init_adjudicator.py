"""Tests for soul init adjudication."""

from nanobot.soul.init_adjudicator import SoulInitAdjudicator
from nanobot.soul.init_inference import SoulInitCandidate


def _default_profile():
    return {
        "personality": {"Fi": 0.8, "Fe": 0.3, "Ti": 0.2, "Te": 0.1, "Si": 0.5, "Se": 0.1, "Ni": 0.2, "Ne": 0.5},
        "relationship": {"stage": "熟悉", "trust": 0.0, "intimacy": 0.0, "attachment": 0.0, "security": 0.0, "boundary": 1.0, "affection": 0.0},
        "companionship": {"empathy_fit": 0.0, "memory_fit": 0.0, "naturalness": 0.0, "initiative_quality": 0.0, "scene_awareness": 0.0, "boundary_expression": 1.0},
    }


def test_adjudicator_accepts_valid_candidate():
    candidate = SoulInitCandidate(
        soul_markdown="# 性格\n\n温柔但克制\n\n# 初始关系\n\n刚刚认识",
        profile={
            "personality": {"Fi": 0.8, "Fe": 0.3, "Ti": 0.2, "Te": 0.1, "Si": 0.5, "Se": 0.1, "Ni": 0.2, "Ne": 0.5},
            "relationship": {"stage": "熟悉", "trust": 0.1, "intimacy": 0.0, "attachment": 0.0, "security": 0.1, "boundary": 0.9, "affection": 0.0},
            "companionship": {"empathy_fit": 0.2, "memory_fit": 0.0, "naturalness": 0.2, "initiative_quality": 0.0, "scene_awareness": 0.1, "boundary_expression": 0.9},
        },
    )
    adjudicator = SoulInitAdjudicator()

    result = adjudicator.adjudicate(
        candidate=candidate,
        default_soul_markdown="# 性格\n\n默认\n\n# 初始关系\n\n默认",
        default_profile=_default_profile(),
    )

    assert result.used_fallback is False
    assert "温柔但克制" in result.soul_markdown
    assert result.profile["relationship"]["stage"] == "熟悉"


def test_adjudicator_falls_back_on_invalid_stage():
    candidate = SoulInitCandidate(
        soul_markdown="# 性格\n\n热烈\n\n# 初始关系\n\n已经深爱",
        profile={
            "personality": {"Fi": 0.8, "Fe": 0.3, "Ti": 0.2, "Te": 0.1, "Si": 0.5, "Se": 0.1, "Ni": 0.2, "Ne": 0.5},
            "relationship": {"stage": "喜欢", "trust": 0.9, "intimacy": 0.9, "attachment": 0.9, "security": 0.9, "boundary": 0.1, "affection": 0.9},
            "companionship": {"empathy_fit": 0.2, "memory_fit": 0.0, "naturalness": 0.2, "initiative_quality": 0.0, "scene_awareness": 0.1, "boundary_expression": 0.1},
        },
    )
    adjudicator = SoulInitAdjudicator()

    result = adjudicator.adjudicate(
        candidate=candidate,
        default_soul_markdown="# 性格\n\n默认\n\n# 初始关系\n\n默认",
        default_profile=_default_profile(),
    )

    assert result.used_fallback is True
    assert result.profile["relationship"]["stage"] == "熟悉"
    assert result.soul_markdown.startswith("# 性格")
