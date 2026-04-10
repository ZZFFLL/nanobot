"""End-to-end tests for multi-turn conversation flow with ReMe memory.

This tests the complete flow:
1. Multiple conversation turns
2. /new command triggers consolidation
3. Conversation is compressed and stored to ReMe
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any

import pytest

from nanobot.agent.loop import AgentLoop
from nanobot.agent.memory import MemoryStore
from nanobot.bus.events import InboundMessage, OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.session.manager import SessionManager


@pytest.fixture
def mock_provider():
    """Create a mock LLM provider that simulates responses."""
    provider = MagicMock()
    provider.get_default_model = MagicMock(return_value="test-model")

    # Track call count for different responses
    call_count = [0]

    async def mock_chat(*, messages, **kwargs):
        call_count[0] += 1
        # Return different responses based on call count
        from nanobot.providers.base import LLMResponse
        return LLMResponse(
            content=f"Response {call_count[0]}",
            tool_calls=[],
            usage={"prompt_tokens": 100, "completion_tokens": 50},
        )

    provider.chat_with_retry = mock_chat
    return provider


@pytest.fixture
def mock_reme_adapter():
    """Create a mock ReMe adapter that tracks calls."""
    adapter = MagicMock()
    adapter._started = True
    adapter._healthy = True
    adapter._circuit_open = False

    # Track all summarize_conversation calls
    summarize_calls = []

    async def mock_summarize(messages, user_id=None, task_name=None):
        summarize_calls.append({
            "messages": messages,
            "user_id": user_id,
            "task_name": task_name,
            "timestamp": datetime.now().isoformat(),
        })
        # Return empty list (no memory nodes created in mock)
        return []

    adapter.summarize_conversation = mock_summarize
    adapter._summarize_calls = summarize_calls  # For test assertions

    # Other mock methods
    adapter.add_memory = AsyncMock()
    adapter.retrieve_memory = AsyncMock(return_value="")
    adapter.list_memories = AsyncMock(return_value=[])
    adapter.is_healthy = MagicMock(return_value=True)
    adapter.get_status = MagicMock(return_value={
        "healthy": True,
        "started": True,
        "circuit_open": False,
        "failure_count": 0,
        "last_error": None,
        "last_failure_time": None,
    })

    return adapter


@pytest.fixture
def workspace(tmp_path):
    """Create a workspace with necessary files."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Create memory directory
    (workspace / "memory").mkdir()

    # Create minimal USER.md
    user_md = workspace / "USER.md"
    user_md.write_text("""# User Profile

**名字：** 测试用户

## Preferences
- 测试偏好
""", encoding="utf-8")

    # Create minimal SOUL.md
    soul_md = workspace / "SOUL.md"
    soul_md.write_text("""# Bot Personality

你是一个测试助手。
""", encoding="utf-8")

    return workspace


class TestMultiTurnConversation:
    """Tests for multi-turn conversation flow."""

    @pytest.mark.asyncio
    async def test_multiple_turns_create_session_history(self, workspace, mock_provider):
        """Multiple conversation turns should create session history."""
        bus = MessageBus()
        session_mgr = SessionManager(workspace)

        # Mock build_messages to return minimal messages
        def mock_build_messages(**kwargs):
            return [{"role": "system", "content": "test"}]

        agent = AgentLoop(
            bus=bus,
            provider=mock_provider,
            workspace=workspace,
            model="test-model",
            max_iterations=10,
            session_manager=session_mgr,
            context_window_tokens=128000,  # Large context to avoid consolidation
        )

        # Patch the consolidator's build_messages to avoid estimation issues
        agent.consolidator._build_messages = mock_build_messages
        agent.consolidator._get_tool_definitions = lambda: []

        # Process multiple messages
        session_key = "test:session1"

        response1 = await agent.process_direct(
            content="你好，我是测试用户",
            session_key=session_key,
            channel="cli",
            chat_id="test",
        )

        response2 = await agent.process_direct(
            content="我住在北京",
            session_key=session_key,
            channel="cli",
            chat_id="test",
        )

        response3 = await agent.process_direct(
            content="我喜欢编程",
            session_key=session_key,
            channel="cli",
            chat_id="test",
        )

        # Verify responses
        assert response1 is not None
        assert response2 is not None
        assert response3 is not None

        # Verify session has history
        session = session_mgr.get_or_create(session_key)
        assert len(session.messages) >= 3  # At least 3 user messages

    @pytest.mark.asyncio
    async def test_new_command_clears_session(self, workspace, mock_provider):
        """/new command should clear the session."""
        bus = MessageBus()
        session_mgr = SessionManager(workspace)

        def mock_build_messages(**kwargs):
            return [{"role": "system", "content": "test"}]

        agent = AgentLoop(
            bus=bus,
            provider=mock_provider,
            workspace=workspace,
            model="test-model",
            max_iterations=10,
            session_manager=session_mgr,
            context_window_tokens=128000,
        )

        agent.consolidator._build_messages = mock_build_messages
        agent.consolidator._get_tool_definitions = lambda: []

        session_key = "test:session2"

        # Have a conversation
        await agent.process_direct(
            content="第一条消息",
            session_key=session_key,
            channel="cli",
            chat_id="test",
        )

        await agent.process_direct(
            content="第二条消息",
            session_key=session_key,
            channel="cli",
            chat_id="test",
        )

        # Verify session has messages
        session = session_mgr.get_or_create(session_key)
        msg_count_before = len(session.messages)
        assert msg_count_before >= 2

        # Simulate /new command via process_direct with command
        from nanobot.command.builtin import cmd_new
        from nanobot.command.router import CommandContext

        ctx = CommandContext(
            loop=agent,
            msg=InboundMessage(
                channel="cli",
                sender_id="user",
                chat_id="test",
                content="/new",
            ),
            raw="/new",
            args="",
            session=session,
            key=session_key,
        )

        result = await cmd_new(ctx)

        # Session should be cleared
        session_mgr.invalidate(session_key)
        session = session_mgr.get_or_create(session_key)
        assert len(session.messages) == 0


class TestConversationConsolidation:
    """Tests for conversation consolidation with ReMe."""

    @pytest.mark.asyncio
    async def test_archive_with_reme_calls_summarize(self, workspace, mock_provider, mock_reme_adapter):
        """archive_with_reme should call ReMe summarize_conversation."""
        from nanobot.agent.memory import Consolidator

        store = MemoryStore(workspace)

        # Create consolidator with proper parameters
        consolidator = Consolidator(
            store=store,
            provider=mock_provider,
            model="test-model",
            sessions=SessionManager(workspace),
            context_window_tokens=4096,
            build_messages=lambda *args, **kwargs: [],
            get_tool_definitions=lambda: [],
            reme_adapter=mock_reme_adapter,
        )

        # Create test conversation
        messages = [
            {"role": "user", "content": "你好，我叫张烽林", "timestamp": "2026-04-10T10:00:00"},
            {"role": "assistant", "content": "你好烽林！", "timestamp": "2026-04-10T10:00:05"},
            {"role": "user", "content": "我住在望城", "timestamp": "2026-04-10T10:01:00"},
            {"role": "assistant", "content": "望城是个好地方", "timestamp": "2026-04-10T10:01:05"},
        ]

        # Call archive_with_reme
        result = await consolidator.archive_with_reme(messages)

        # Verify summarize_conversation was called
        assert len(mock_reme_adapter._summarize_calls) == 1
        call = mock_reme_adapter._summarize_calls[0]

        # Verify messages were formatted
        assert len(call["messages"]) > 0

    @pytest.mark.asyncio
    async def test_archive_with_reme_fallback_without_adapter(self, workspace, mock_provider):
        """archive_with_reme should fallback to basic archive when no ReMe adapter."""
        from nanobot.agent.memory import Consolidator

        store = MemoryStore(workspace)
        consolidator = Consolidator(
            store=store,
            provider=mock_provider,
            model="test-model",
            sessions=SessionManager(workspace),
            context_window_tokens=4096,
            build_messages=lambda *args, **kwargs: [],
            get_tool_definitions=lambda: [],
            reme_adapter=None,  # No ReMe adapter
        )

        messages = [
            {"role": "user", "content": "测试消息"},
            {"role": "assistant", "content": "测试回复"},
        ]

        # Should not raise even without ReMe adapter
        result = await consolidator.archive_with_reme(messages)


class TestReMeMemoryTools:
    """Tests for ReMe memory tools."""

    @pytest.mark.asyncio
    async def test_retrieve_memory_tool_calls_adapter(self, mock_reme_adapter):
        """retrieve_memory tool should call ReMe adapter."""
        from nanobot.agent.tools.memory import RetrieveMemoryTool

        tool = RetrieveMemoryTool(mock_reme_adapter, get_user_name=lambda: "测试用户")

        result = await tool.execute(query="用户的偏好是什么？")

        # Should have called retrieve_memory
        mock_reme_adapter.retrieve_memory.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_memory_tool_calls_adapter(self, mock_reme_adapter):
        """add_memory tool should call ReMe adapter."""
        from nanobot.agent.tools.memory import AddMemoryTool

        tool = AddMemoryTool(mock_reme_adapter, get_user_name=lambda: "测试用户")

        result = await tool.execute(content="用户喜欢编程")

        # Should have called add_memory
        mock_reme_adapter.add_memory.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_memories_tool_calls_adapter(self, mock_reme_adapter):
        """list_memories tool should call ReMe adapter."""
        from nanobot.agent.tools.memory import ListMemoriesTool

        tool = ListMemoriesTool(mock_reme_adapter, get_user_name=lambda: "测试用户")

        result = await tool.execute()

        # Should have called list_memories
        mock_reme_adapter.list_memories.assert_called_once()


class TestEndToEndWithMockReMe:
    """Full end-to-end tests with mocked ReMe backend."""

    @pytest.mark.asyncio
    async def test_full_conversation_flow(self, workspace, mock_provider, mock_reme_adapter):
        """Test complete conversation flow from messages to memory storage."""
        bus = MessageBus()
        session_mgr = SessionManager(workspace)

        def mock_build_messages(**kwargs):
            return [{"role": "system", "content": "test"}]

        agent = AgentLoop(
            bus=bus,
            provider=mock_provider,
            workspace=workspace,
            model="test-model",
            max_iterations=10,
            session_manager=session_mgr,
            context_window_tokens=128000,
        )

        # Patch consolidator methods
        agent.consolidator._build_messages = mock_build_messages
        agent.consolidator._get_tool_definitions = lambda: []

        # Inject mock ReMe adapter
        agent.reme_adapter = mock_reme_adapter
        agent.consolidator.reme_adapter = mock_reme_adapter

        session_key = "test:e2e"

        # Step 1: Have a conversation
        print("\n=== Step 1: Multi-turn conversation ===")

        response1 = await agent.process_direct(
            content="你好，我是张烽林",
            session_key=session_key,
            channel="cli",
            chat_id="test",
        )
        print(f"Response 1: {response1.content[:50] if response1 else 'None'}...")

        response2 = await agent.process_direct(
            content="我住在望城，在九天银河产业园上班",
            session_key=session_key,
            channel="cli",
            chat_id="test",
        )
        print(f"Response 2: {response2.content[:50] if response2 else 'None'}...")

        response3 = await agent.process_direct(
            content="我喜欢《月儿弯挂山川》这首歌",
            session_key=session_key,
            channel="cli",
            chat_id="test",
        )
        print(f"Response 3: {response3.content[:50] if response3 else 'None'}...")

        # Step 2: Verify session has history
        print("\n=== Step 2: Verify session history ===")
        session = session_mgr.get_or_create(session_key)
        print(f"Session has {len(session.messages)} messages")
        assert len(session.messages) >= 3, f"Expected at least 3 messages, got {len(session.messages)}"

        # Step 3: Trigger /new to consolidate
        print("\n=== Step 3: Trigger /new command ===")
        from nanobot.command.builtin import cmd_new
        from nanobot.command.router import CommandContext

        ctx = CommandContext(
            loop=agent,
            msg=InboundMessage(
                channel="cli",
                sender_id="user",
                chat_id="test",
                content="/new",
            ),
            raw="/new",
            args="",
            session=session,
            key=session_key,
        )

        new_result = await cmd_new(ctx)
        print(f"/new result: {new_result.content}")

        # Wait for background consolidation
        await asyncio.sleep(0.5)

        # Step 4: Verify session was cleared
        print("\n=== Step 4: Verify session cleared ===")
        session_mgr.invalidate(session_key)
        session = session_mgr.get_or_create(session_key)
        print(f"Session now has {len(session.messages)} messages")
        assert len(session.messages) == 0, "Session should be cleared after /new"

        print("\n=== Test completed successfully ===")

    @pytest.mark.asyncio
    async def test_memory_tool_usage_in_conversation(self, mock_reme_adapter):
        """Test that memory tools can be used during conversation."""
        from nanobot.agent.tools.memory import AddMemoryTool, RetrieveMemoryTool
        from nanobot.agent.tools.registry import ToolRegistry

        # Create tool registry with memory tools
        registry = ToolRegistry()
        registry.register(AddMemoryTool(mock_reme_adapter, get_user_name=lambda: "测试用户"))
        registry.register(RetrieveMemoryTool(mock_reme_adapter, get_user_name=lambda: "测试用户"))

        # Verify tools are registered
        tools = registry.get_definitions()
        tool_names = [t["function"]["name"] for t in tools]

        assert "add_memory" in tool_names
        assert "retrieve_memory" in tool_names

        # Test executing tools directly
        add_result = await registry.execute("add_memory", {
            "content": "用户偏好编程",
        })
        print(f"Add memory result: {add_result}")

        mock_reme_adapter.add_memory.assert_called_once()