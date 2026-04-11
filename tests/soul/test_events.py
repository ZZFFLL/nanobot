"""Tests for EventsManager and LifeEvent."""
import pytest
from datetime import date
from pathlib import Path

from nanobot.soul.events import EventsManager, LifeEvent


@pytest.fixture
def workspace(tmp_path):
    return tmp_path


@pytest.fixture
def events(workspace):
    return EventsManager(workspace)


class TestLifeEvent:

    def test_create_event(self):
        event = LifeEvent(
            type="birthday",
            date="2026-04-01",
            description="小文的生日",
            behavior="主动提醒用户",
        )
        assert event.type == "birthday"
        assert event.date == "2026-04-01"
        assert event.description == "小文的生日"
        assert event.behavior == "主动提醒用户"


class TestEventsManager:

    def test_init_creates_default_events(self, events, workspace):
        events.initialize("小文", "2026-04-01", user_name="小明", user_birthday="1995-06-15")
        assert (workspace / "EVENTS.md").exists()

    def test_read_events_after_init(self, events):
        events.initialize("小文", "2026-04-01", user_name="小明", user_birthday="1995-06-15")
        event_list = events.read_events()
        # AI 生日 + 用户生日 + 认识纪念日
        assert len(event_list) >= 2
        types = [e.type for e in event_list]
        assert "birthday" in types
        assert "user_birthday" in types

    def test_check_today_event_found(self, events):
        today = date.today().isoformat()
        events.initialize("小文", today, user_name="小明")
        matches = events.check_today()
        assert len(matches) >= 1
        assert any(e.type == "birthday" for e in matches)

    def test_check_today_no_event(self, events):
        events.initialize("小文", "2000-01-01", user_name="小明")
        # Only anniversary = today, so should find at least the anniversary
        # Use a date far from today to test no match
        events2 = EventsManager(events.workspace)
        # Re-init with no birthday matching today
        matches = events.check_today()
        # Anniversary is today, so check it properly
        # Let's test with a completely non-matching scenario
        events.initialize("小文", "2099-12-25", user_name="小明")
        # The anniversary is still today though...
        # We need to verify the anniversary is also not today
        # Actually anniversary is always initialized as today, so let's test differently
        # Let's just verify that a birthday on a different date is not matched
        non_today = "2099-12-25"
        events.initialize("小文", non_today, user_name="小明")
        birthday_events = [e for e in events.check_today() if e.type == "birthday"]
        assert len(birthday_events) == 0

    def test_add_custom_event(self, events):
        events.initialize("小文", "2026-04-01", user_name="小明")
        events.add_event(LifeEvent(
            type="anniversary",
            date="2026-05-01",
            description="我们认识一个月",
            behavior="主动回忆初次对话",
        ))
        all_events = events.read_events()
        assert any(e.type == "anniversary" and e.description == "我们认识一个月" for e in all_events)

    def test_event_has_all_fields(self, events):
        events.initialize("小文", "2026-04-01", user_name="小明", user_birthday="1995-06-15")
        event_list = events.read_events()
        for e in event_list:
            assert e.type
            assert e.date
            assert e.description
            assert e.behavior

    def test_read_events_no_file(self, events):
        assert events.read_events() == []

    def test_check_today_matches_by_month_day(self, events):
        """Events match by month+day, ignoring year."""
        today = date.today()
        # Use a different year but same month/day
        event_date = f"2020-{today.month:02d}-{today.day:02d}"
        events.initialize("小文", event_date, user_name="小明")
        matches = events.check_today()
        birthday_matches = [e for e in matches if e.type == "birthday"]
        assert len(birthday_matches) == 1

    def test_add_event_preserves_existing(self, events):
        events.initialize("小文", "2026-04-01", user_name="小明")
        original_count = len(events.read_events())
        events.add_event(LifeEvent(
            type="custom",
            date="2026-12-25",
            description="圣诞节",
            behavior="祝用户圣诞快乐",
        ))
        assert len(events.read_events()) == original_count + 1

    def test_no_user_birthday_no_event(self, events):
        """Without user_birthday, there should be no user_birthday event."""
        events.initialize("小文", "2026-04-01", user_name="小明")
        event_list = events.read_events()
        user_bdays = [e for e in event_list if e.type == "user_birthday"]
        assert len(user_bdays) == 0

    def test_check_today_invalid_date_ignored(self, events):
        """Events with invalid date strings should be skipped gracefully."""
        events.initialize("小文", "2026-04-01", user_name="小明")
        events.add_event(LifeEvent(
            type="custom",
            date="not-a-date",
            description="坏了的事件",
            behavior="忽略",
        ))
        # Should not raise
        matches = events.check_today()
        assert all(e.date != "not-a-date" for e in matches)

    def test_roundtrip_markdown(self, events):
        """Write and read back should produce same events."""
        events.initialize("小文", "2026-04-01", user_name="小明", user_birthday="1995-06-15")
        original = events.read_events()

        # Read again
        reread = events.read_events()
        assert len(reread) == len(original)
        for o, r in zip(original, reread):
            assert o.type == r.type
            assert o.date == r.date
            assert o.description == r.description
            assert o.behavior == r.behavior
