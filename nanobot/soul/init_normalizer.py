"""Bounded normalization for soul init candidates.

This module only repairs structure/format issues. It does not hardcode
personality decisions.
"""

from __future__ import annotations

from copy import deepcopy

from nanobot.soul.evolution import FUNCTIONS
from nanobot.soul.init_inference import SoulInitCandidate

_RELATIONSHIP_KEYS = ("trust", "intimacy", "attachment", "security", "boundary", "affection")
_COMPANIONSHIP_KEYS = (
    "empathy_fit",
    "memory_fit",
    "naturalness",
    "initiative_quality",
    "scene_awareness",
    "boundary_expression",
)


def normalize_candidate(
    candidate: SoulInitCandidate,
    *,
    default_relationship: str,
) -> SoulInitCandidate:
    """Normalize common formatting errors while preserving meaning."""

    return SoulInitCandidate(
        soul_markdown=_normalize_soul_markdown(candidate.soul_markdown, default_relationship),
        heart_markdown=(candidate.heart_markdown or "").strip(),
        profile=_normalize_profile(candidate.profile),
    )


def _normalize_soul_markdown(text: str, default_relationship: str) -> str:
    stripped = (text or "").strip()
    if not stripped:
        return stripped
    if "# 性格" in stripped and "# 初始关系" in stripped:
        return stripped

    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    has_headings = any(line.startswith("#") for line in lines)
    if has_headings:
        return stripped

    return (
        "# 性格\n\n"
        f"{stripped}\n\n"
        "# 初始关系\n\n"
        f"{default_relationship}"
    )


def _normalize_profile(profile: dict) -> dict:
    if not isinstance(profile, dict):
        return profile

    normalized = deepcopy(profile)
    normalized["personality"] = _normalize_personality(normalized.get("personality"))
    normalized["relationship"] = _normalize_relationship(normalized.get("relationship"))
    normalized["companionship"] = _normalize_companionship(normalized.get("companionship"))
    return normalized


def _normalize_personality(personality: dict | None) -> dict | None:
    if not isinstance(personality, dict):
        return personality

    source = personality
    for nested_key in ("functions", "jungian_functions", "cognitive_functions"):
        nested = personality.get(nested_key)
        if isinstance(nested, dict):
            source = nested
            break

    if not all(func in source for func in FUNCTIONS):
        return personality

    normalized: dict[str, float] = {}
    for func in FUNCTIONS:
        value = _normalize_ratio(source.get(func))
        if value is None:
            return personality
        normalized[func] = value
    return normalized


def _normalize_relationship(relationship: dict | None) -> dict | None:
    return _normalize_metric_group(relationship, metric_keys=_RELATIONSHIP_KEYS, keep_stage=True)


def _normalize_companionship(companionship: dict | None) -> dict | None:
    return _normalize_metric_group(companionship, metric_keys=_COMPANIONSHIP_KEYS, keep_stage=False)


def _normalize_metric_group(
    section: dict | None,
    *,
    metric_keys: tuple[str, ...],
    keep_stage: bool,
) -> dict | None:
    if not isinstance(section, dict):
        return section

    merged = deepcopy(section)
    dimensions = merged.pop("dimensions", None)
    if isinstance(dimensions, dict):
        for key, value in dimensions.items():
            merged.setdefault(key, value)

    normalized: dict[str, float | str] = {}
    if keep_stage and "stage" in merged:
        normalized["stage"] = merged["stage"]

    all_ok = True
    for key in metric_keys:
        value = _normalize_ratio(merged.get(key))
        if value is None:
            all_ok = False
            break
        normalized[key] = value

    if all_ok:
        return normalized
    return section


def _normalize_ratio(value) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, str):
        try:
            value = float(value.strip())
        except ValueError:
            return None
    if not isinstance(value, (int, float)):
        return None

    numeric = float(value)
    if 0.0 <= numeric <= 1.0:
        return round(numeric, 4)
    if 1.0 < numeric <= 100.0:
        return round(numeric / 100.0, 4)
    return None
