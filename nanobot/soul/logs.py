"""Unified log writing for soul review, calibration, and evolution traces."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path


class SoulLogWriter:
    """Write structured markdown logs under the workspace soul_logs directory."""

    def __init__(self, workspace: Path) -> None:
        self.base_dir = workspace / "soul_logs"

    def write_weekly(self, stamp: str, content: str) -> Path:
        return self._write("weekly", f"{stamp}-周复盘.md", content)

    def write_monthly(self, stamp: str, content: str) -> Path:
        return self._write("monthly", f"{stamp}-月校准报告.md", content)

    def write_proactive(self, stamp: str, decision) -> Path:
        content = decision.to_markdown() if hasattr(decision, "to_markdown") else str(decision)
        return self._write("proactive", f"{stamp}-主动陪伴.md", content)

    def write_proactive_event(self, stamp: str, *, event_type: str, detail: str) -> Path:
        content = (
            "# 主动陪伴事件\n\n"
            f"- 事件类型: {event_type}\n"
            f"- 详细信息: {detail}\n"
        )
        return self._write("proactive", f"{stamp}-主动事件.md", content)

    def write_init_trace(self, stamp: str, records: list[dict]) -> Path:
        lines = [json.dumps(record, ensure_ascii=False) for record in records]
        content = "\n".join(lines)
        if content:
            content += "\n"
        return self._write("init", f"{stamp}-初始化追踪.jsonl", content)

    def write_init_audit(self, stamp: str, payload: dict) -> Path:
        return self._write_json("init", f"{stamp}-初始化审计.json", payload)

    def write_projection_trace(self, stamp: str, records: list[dict]) -> Path:
        lines = [json.dumps(record, ensure_ascii=False) for record in records]
        content = "\n".join(lines)
        if content:
            content += "\n"
        return self._write("projection", f"{stamp}-投影追踪.jsonl", content)

    def write_projection_audit(self, stamp: str, payload: dict) -> Path:
        return self._write_json("projection", f"{stamp}-投影审计.json", payload)

    def _write(self, kind: str, filename: str, content: str) -> Path:
        target = self.base_dir / kind
        target.mkdir(parents=True, exist_ok=True)
        path = target / filename
        path.write_text(content, encoding="utf-8")
        return path

    def _write_json(self, kind: str, filename: str, payload: dict) -> Path:
        return self._write(
            kind,
            filename,
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        )


def build_init_audit_payload(
    *,
    timestamp: str,
    model: str,
    targets: list[str] | None,
    final_status: str,
    final_reason: str,
    accepted_attempt: int | None,
    used_fallback: bool,
    governance: dict,
    candidate: dict | None,
    heart_markdown: str,
    profile: dict,
    projected_soul_markdown: str,
    profile_source: str,
) -> dict:
    """Build the init audit payload with explicit candidate/result separation."""

    payload = {
        "timestamp": timestamp,
        "model": model,
        "targets": list(targets or []),
        "final_status": final_status,
        "final_reason": final_reason,
        "accepted_attempt": accepted_attempt,
        "used_fallback": used_fallback,
        "governance": deepcopy(governance),
        "result": {
            # Keep the legacy field as an alias of the final projected SOUL.md.
            "soul_markdown": projected_soul_markdown,
            "projected_soul_markdown": projected_soul_markdown,
            "heart_markdown": heart_markdown,
            "profile": deepcopy(profile),
            "profile_source": profile_source,
        },
    }
    if candidate:
        payload["candidate"] = deepcopy(candidate)
    return payload
