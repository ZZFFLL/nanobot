"""Tests for soul logging utilities."""

from nanobot.soul.logs import SoulLogWriter
from nanobot.soul.proactive import ProactiveDecision


def test_log_writer_creates_weekly_log_dir(tmp_path):
    writer = SoulLogWriter(tmp_path)

    path = writer.write_weekly("2026-04-14", "# 周复盘\n")

    assert path.exists()
    assert "weekly" in str(path)


def test_log_writer_creates_proactive_trace(tmp_path):
    writer = SoulLogWriter(tmp_path)
    decision = ProactiveDecision(
        want_to_reach_out=True,
        tone="想念且克制",
        message="今天过得怎么样？",
        reason="最近互动频率下降，但依恋感上升",
    )

    path = writer.write_proactive("2026-04-14-230000", decision)
    content = path.read_text(encoding="utf-8")

    assert path.exists()
    assert "proactive" in str(path)
    assert "今天过得怎么样？" in content
    assert "最近互动频率下降" in content


def test_log_writer_creates_proactive_event_trace(tmp_path):
    writer = SoulLogWriter(tmp_path)

    path = writer.write_proactive_event(
        "2026-04-15-110000",
        event_type="gate_blocked",
        detail="冷却中 (剩余 100s)",
    )
    content = path.read_text(encoding="utf-8")

    assert path.exists()
    assert "gate_blocked" in content
    assert "冷却中" in content


def test_log_writer_creates_init_trace_jsonl(tmp_path):
    writer = SoulLogWriter(tmp_path)

    path = writer.write_init_trace(
        "2026-04-15-110000",
        [
            {
                "attempt": 1,
                "stage": "adjudication",
                "status": "rejected",
                "reason": "SOUL_PROFILE 候选非法",
            },
            {
                "attempt": 2,
                "stage": "adjudication",
                "status": "accepted",
                "reason": "",
            },
        ],
    )
    content = path.read_text(encoding="utf-8")

    assert path.exists()
    assert "init" in str(path)
    assert '"stage": "adjudication"' in content
    assert "SOUL_PROFILE 候选非法" in content


def test_log_writer_creates_init_audit_json(tmp_path):
    writer = SoulLogWriter(tmp_path)

    path = writer.write_init_audit(
        "2026-04-15-110000",
        {
            "final_status": "accepted",
            "used_fallback": False,
            "result": {"soul_markdown": "# 性格\n\n测试\n"},
        },
    )

    content = path.read_text(encoding="utf-8")
    assert path.exists()
    assert "init" in str(path)
    assert '"final_status": "accepted"' in content
    assert '"used_fallback": false' in content.lower()


def test_log_writer_creates_projection_trace_and_audit(tmp_path):
    writer = SoulLogWriter(tmp_path)

    trace_path = writer.write_projection_trace(
        "2026-04-15-120000",
        [
            {
                "attempt": 1,
                "stage": "validation",
                "status": "accepted",
            }
        ],
    )
    audit_path = writer.write_projection_audit(
        "2026-04-15-120000",
        {
            "final_status": "accepted",
            "trigger": "review",
            "result": {"soul_markdown": "# 性格\n\n测试\n"},
        },
    )

    assert trace_path.exists()
    assert audit_path.exists()
    assert "projection" in str(trace_path)
    assert "projection" in str(audit_path)
