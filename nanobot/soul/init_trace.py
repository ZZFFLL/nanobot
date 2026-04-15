"""Tracing utilities for methodology-bound soul initialization."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class SoulInitTraceEvent:
    """One observable event emitted during soul initialization."""

    timestamp: str
    attempt: int
    stage: str
    status: str
    reason: str = ""
    detail: str = ""


@dataclass(slots=True)
class SoulInitTrace:
    """Collect attempt-level trace events for soul initialization."""

    max_attempts: int
    events: list[SoulInitTraceEvent] = field(default_factory=list)
    total_attempts: int = 0
    final_status: str = ""
    final_reason: str = ""
    accepted_attempt: int | None = None

    def add_event(
        self,
        *,
        attempt: int,
        stage: str,
        status: str,
        reason: str = "",
        detail: str = "",
    ) -> None:
        self.total_attempts = max(self.total_attempts, attempt)
        self.events.append(
            SoulInitTraceEvent(
                timestamp=datetime.now().astimezone().isoformat(timespec="seconds"),
                attempt=attempt,
                stage=stage,
                status=status,
                reason=reason,
                detail=detail,
            )
        )

    def finish(
        self,
        *,
        status: str,
        reason: str = "",
        accepted_attempt: int | None = None,
    ) -> None:
        self.final_status = status
        self.final_reason = reason
        self.accepted_attempt = accepted_attempt

    def to_console_lines(self) -> list[str]:
        lines: list[str] = []
        for event in self.events:
            line = f"Attempt {event.attempt}/{self.max_attempts}: {event.stage}={event.status}"
            if event.reason:
                line += f" ({event.reason})"
            lines.append(line)
        return lines

    def to_log_records(self, *, model: str, targets: list[str] | None = None) -> list[dict]:
        records: list[dict] = []
        for event in self.events:
            records.append(
                {
                    "timestamp": event.timestamp,
                    "attempt": event.attempt,
                    "max_attempts": self.max_attempts,
                    "stage": event.stage,
                    "status": event.status,
                    "reason": event.reason,
                    "detail": event.detail,
                    "model": model,
                    "targets": list(targets or []),
                    "final_status": self.final_status,
                    "final_reason": self.final_reason,
                    "accepted_attempt": self.accepted_attempt,
                }
            )
        return records
