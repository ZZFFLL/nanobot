"""Tests for MemoryWriter — async dual-perspective memory writing."""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from nanobot.soul.memory_writer import MemoryWriter, WriteTask


@pytest.fixture
def mock_bridge():
    bridge = MagicMock()
    bridge.ai_wing = "小文"
    bridge.user_wing = "用户"
    bridge.add_drawer = AsyncMock(return_value=True)
    return bridge


@pytest.fixture
def writer(mock_bridge):
    return MemoryWriter(mock_bridge)


class TestMemoryWriter:

    async def test_write_dual_creates_two_drawers(self, writer, mock_bridge):
        await writer.write_dual("你好", "你好呀~", "2026-04-10T12:00:00")
        assert mock_bridge.add_drawer.call_count == 2

    async def test_ai_perspective_uses_ai_wing(self, writer, mock_bridge):
        await writer.write_dual("你好", "你好呀~", "2026-04-10T12:00:00")
        first_call = mock_bridge.add_drawer.call_args_list[0]
        assert first_call.kwargs["wing"] == "小文"

    async def test_user_perspective_uses_user_wing(self, writer, mock_bridge):
        await writer.write_dual("你好", "你好呀~", "2026-04-10T12:00:00")
        second_call = mock_bridge.add_drawer.call_args_list[1]
        assert second_call.kwargs["wing"] == "用户"

    async def test_content_includes_raw_dialog(self, writer, mock_bridge):
        await writer.write_dual("我今天很开心", "真好呀！", "2026-04-10T12:00:00")
        first_content = mock_bridge.add_drawer.call_args_list[0]
        content = first_content.kwargs["content"]
        assert "我今天很开心" in content

    async def test_ai_content_has_feeling_section(self, writer, mock_bridge):
        await writer.write_dual("你好", "你好呀~", "2026-04-10T12:00:00")
        first_content = mock_bridge.add_drawer.call_args_list[0]
        content = first_content.kwargs["content"]
        assert "我的感受" in content

    async def test_user_content_has_about_user_section(self, writer, mock_bridge):
        await writer.write_dual("你好", "你好呀~", "2026-04-10T12:00:00")
        second_content = mock_bridge.add_drawer.call_args_list[1]
        content = second_content.kwargs["content"]
        assert "我观察到的关于对方" in content

    async def test_both_write_to_daily_room(self, writer, mock_bridge):
        await writer.write_dual("你好", "你好呀~", "2026-04-10T12:00:00")
        for call in mock_bridge.add_drawer.call_args_list:
            assert call.kwargs["room"] == "daily"

    async def test_metadata_includes_timestamp(self, writer, mock_bridge):
        await writer.write_dual("你好", "你好呀~", "2026-04-10T12:00:00")
        first_call = mock_bridge.add_drawer.call_args_list[0]
        assert first_call.kwargs["metadata"]["timestamp"] == "2026-04-10T12:00:00"

    async def test_metadata_digestion_status_active(self, writer, mock_bridge):
        await writer.write_dual("你好", "你好呀~", "2026-04-10T12:00:00")
        for call in mock_bridge.add_drawer.call_args_list:
            assert call.kwargs["metadata"]["digestion_status"] == "active"

    async def test_failure_enters_retry_queue(self, writer, mock_bridge):
        mock_bridge.add_drawer = AsyncMock(side_effect=Exception("写入失败"))
        await writer.write_dual("你好", "你好", "2026-04-10")
        assert len(writer._retry_queue) > 0

    async def test_retry_max_then_discard(self, writer, mock_bridge):
        task = WriteTask(
            wing="小文", room="daily",
            content="测试", metadata={},
            retries=3,  # already at max
        )
        await writer._enqueue_retry(task)
        # Exceeds max retries, should not be added
        assert len(writer._retry_queue) == 0

    async def test_queue_max_size_drops_oldest(self, writer, mock_bridge):
        # Fill queue beyond max
        for i in range(105):
            task = WriteTask(wing="小文", room="daily", content=f"内容{i}", metadata={}, retries=0)
            writer._retry_queue.append(task)
        # Enqueue one more should drop oldest
        await writer._enqueue_retry(
            WriteTask(wing="小文", room="daily", content="新的", metadata={}, retries=0)
        )
        assert len(writer._retry_queue) <= writer.QUEUE_MAX_SIZE

    async def test_retry_increments_counter(self, writer, mock_bridge):
        task = WriteTask(
            wing="小文", room="daily",
            content="测试", metadata={},
            retries=1,
        )
        await writer._enqueue_retry(task)
        assert writer._retry_queue[0].retries == 2

    async def test_partial_failure_only_queues_failed(self, writer, mock_bridge):
        call_count = 0
        async def alternating_success(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:
                raise Exception("偶数次失败")
            return True

        mock_bridge.add_drawer = AsyncMock(side_effect=alternating_success)
        await writer.write_dual("你好", "你好", "2026-04-10")
        # One of two writes failed
        assert len(writer._retry_queue) == 1
