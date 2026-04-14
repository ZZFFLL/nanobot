"""Tests for soul inference protocol objects."""

from nanobot.soul.inference import RelationshipInference


def test_relationship_inference_has_required_fields():
    candidate = RelationshipInference(
        current_stage_assessment="亲近",
        proposed_stage="依恋",
        direction="up",
        evidence_summary="近 7 天高频互动",
        dimension_changes={"trust": 0.1},
        personality_influence="Fi 高导致情感感知更强",
        risk_flags=[],
        confidence=0.82,
    )

    assert candidate.proposed_stage == "依恋"
    assert candidate.direction == "up"
