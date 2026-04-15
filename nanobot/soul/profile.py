"""Structured soul profile state management."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from nanobot.soul.methodology import (
    RELATIONSHIP_DIMENSIONS,
    RELATIONSHIP_STAGES,
    build_default_profile,
)


class SoulProfileManager:
    """Persist and load the structured soul profile markdown document."""

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.profile_file = workspace / "SOUL_PROFILE.md"

    def read(self) -> dict:
        try:
            raw = self.profile_file.read_text(encoding="utf-8")
        except FileNotFoundError:
            return build_default_profile()

        text = self._strip_code_fence(raw)
        if not text:
            return build_default_profile()
        return json.loads(text)

    def write(self, profile: dict) -> None:
        text = "```json\n" + json.dumps(profile, ensure_ascii=False, indent=2) + "\n```"
        self.profile_file.write_text(text, encoding="utf-8")

    def relationship_candidate(
        self,
        base_profile: dict,
        *,
        stage: str,
        dimension_deltas: dict[str, float],
    ) -> dict:
        """Return a candidate profile with relationship updates applied, without persisting."""

        candidate = copy.deepcopy(base_profile)
        candidate["relationship"] = self._apply_relationship_update(
            base_profile=base_profile,
            stage=stage,
            dimension_deltas=dimension_deltas,
        )
        return candidate

    def update_relationship(
        self,
        *,
        stage: str,
        dimension_deltas: dict[str, float],
    ) -> dict:
        profile = self.read()
        profile["relationship"] = self._apply_relationship_update(
            base_profile=profile,
            stage=stage,
            dimension_deltas=dimension_deltas,
        )
        self.write(profile)
        return profile["relationship"]

    def personality_candidate(self, base_profile: dict, personality_values: dict[str, float]) -> dict:
        """Return a candidate profile with personality replaced, without persisting."""

        candidate = copy.deepcopy(base_profile)
        candidate["personality"] = dict(personality_values)
        return candidate

    def update_personality(self, personality_values: dict[str, float]) -> dict[str, float]:
        """Replace structured personality values."""

        profile = self.read()
        profile["personality"] = dict(personality_values)
        self.write(profile)
        return profile["personality"]

    @staticmethod
    def _apply_relationship_update(
        *,
        base_profile: dict,
        stage: str,
        dimension_deltas: dict[str, float],
    ) -> dict:
        if stage not in RELATIONSHIP_STAGES:
            raise ValueError("未知关系阶段")

        current_relationship = build_default_profile()["relationship"]
        current_relationship.update(base_profile.get("relationship", {}))
        current_relationship["stage"] = stage

        for name, delta in dimension_deltas.items():
            if name not in RELATIONSHIP_DIMENSIONS:
                continue
            current_value = float(current_relationship.get(name, 0.0))
            next_value = max(0.0, min(1.0, current_value + float(delta)))
            current_relationship[name] = next_value

        return current_relationship

    @staticmethod
    def _strip_code_fence(text: str) -> str:
        stripped = text.strip()
        if not stripped.startswith("```"):
            return stripped

        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
