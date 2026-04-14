"""Structured LLM candidate protocols for the soul system."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RelationshipInference:
    """Candidate relationship-stage assessment proposed by the LLM."""

    current_stage_assessment: str
    proposed_stage: str
    direction: str
    evidence_summary: str
    dimension_changes: dict[str, float]
    personality_influence: str
    risk_flags: list[str]
    confidence: float
