"""Tests for SOUL heartbeat bridge behavior."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_soul_heartbeat_tick_does_not_send_raw_event_text(tmp_path):
    from nanobot.soul.heartbeat_bridge import run_soul_heartbeat_tick
    from nanobot.soul.proactive import ProactiveDecision

    bus = SimpleNamespace(publish_outbound=AsyncMock())
    proactive = MagicMock()
    proactive.get_interval_seconds.return_value = 600
    proactive.decide_and_generate = AsyncMock(
        return_value=ProactiveDecision(
            want_to_reach_out=True,
            tone="轻轻想起",
            message="今天突然想到你了。",
            reason="纪念日让情绪有点波动",
        )
    )
    events_mgr = MagicMock()
    events_mgr.check_today.return_value = [
        SimpleNamespace(
            type="anniversary",
            description="温予安和张烽林认识的第一天",
            behavior="主动回忆初次对话，感慨关系变化",
        )
    ]
    heartbeat = SimpleNamespace(interval_s=1800)
    original_tick = AsyncMock()
    pick_target = lambda: ("feishu", "chat-1")
    record_proactive = AsyncMock()

    await run_soul_heartbeat_tick(
        heartbeat=heartbeat,
        proactive=proactive,
        events_mgr=events_mgr,
        bus=bus,
        pick_target=pick_target,
        original_tick=original_tick,
        record_proactive=record_proactive,
    )

    assert heartbeat.interval_s == 600
    proactive.decide_and_generate.assert_awaited_once()
    call = proactive.decide_and_generate.await_args
    assert "今天有特别的日子" in call.kwargs["extra_context"]
    assert "anniversary" in call.kwargs["extra_context"]
    bus.publish_outbound.assert_awaited_once()
    outbound = bus.publish_outbound.await_args.args[0]
    assert outbound.content == "今天突然想到你了。"
    assert "今天有特别的日子" not in outbound.content
    original_tick.assert_not_awaited()


@pytest.mark.asyncio
async def test_soul_heartbeat_tick_falls_back_to_normal_heartbeat_without_event_leak():
    from nanobot.soul.heartbeat_bridge import run_soul_heartbeat_tick

    bus = SimpleNamespace(publish_outbound=AsyncMock())
    proactive = MagicMock()
    proactive.get_interval_seconds.return_value = 900
    proactive.decide_and_generate = AsyncMock(return_value=None)
    events_mgr = MagicMock()
    events_mgr.check_today.return_value = [
        SimpleNamespace(
            type="anniversary",
            description="温予安和张烽林认识的第一天",
            behavior="主动回忆初次对话，感慨关系变化",
        )
    ]
    heartbeat = SimpleNamespace(interval_s=1800)
    original_tick = AsyncMock()
    pick_target = lambda: ("feishu", "chat-1")
    record_proactive = AsyncMock()

    await run_soul_heartbeat_tick(
        heartbeat=heartbeat,
        proactive=proactive,
        events_mgr=events_mgr,
        bus=bus,
        pick_target=pick_target,
        original_tick=original_tick,
        record_proactive=record_proactive,
    )

    bus.publish_outbound.assert_not_awaited()
    original_tick.assert_awaited_once()
