"""Bridge heartbeat ticks with SOUL proactive behavior without leaking raw event text."""

from __future__ import annotations

from nanobot.bus.events import OutboundMessage


def format_today_event_context(events: list) -> str:
    """Render today's events as internal context for proactive reasoning."""

    if not events:
        return ""
    event_msgs = [f"[{e.type}] {e.description} — {e.behavior}" for e in events]
    return "今天有特别的日子：\n" + "\n".join(event_msgs)


async def run_soul_heartbeat_tick(
    *,
    heartbeat,
    proactive,
    events_mgr,
    bus,
    pick_target,
    original_tick,
    record_proactive,
) -> None:
    """Run one heartbeat tick with SOUL-aware proactive behavior."""

    interval = proactive.get_interval_seconds()
    heartbeat.interval_s = interval

    today_events = events_mgr.check_today()
    event_context = format_today_event_context(today_events)

    decision = await proactive.decide_and_generate(
        extra_context=event_context or None,
    )
    if decision and decision.want_to_reach_out and decision.message:
        await record_proactive(decision)

        channel, chat_id = pick_target()
        if channel != "cli":
            await bus.publish_outbound(
                OutboundMessage(channel=channel, chat_id=chat_id, content=decision.message)
            )
        return

    await original_tick()
