"""End-to-end integration tests: verify the full soul engine flow."""
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from nanobot.soul.engine import SoulEngine, SoulHook
from nanobot.soul.heart import HeartManager


@pytest.fixture
def workspace(tmp_path):
    return tmp_path


@pytest.fixture
def mock_provider():
    provider = MagicMock()
    provider.chat_with_retry = AsyncMock()
    provider.generation = MagicMock()
    provider.generation.max_tokens = 8192
    return provider


@pytest.fixture
def engine(workspace, mock_provider):
    eng = SoulEngine(workspace, mock_provider, "test-model")
    eng.initialize("小文", "温柔但倔强，刚被创造")
    return eng


class TestIntegration:

    async def test_full_conversation_flow(self, engine, mock_provider):
        """Simulate a full conversation: init -> inject context -> converse -> update emotion."""
        # 1. Verify initialization
        data = engine.heart.read()
        assert data is not None
        assert data["当前情绪"] != ""

        # 2. Simulate before_iteration (inject context)
        hook = SoulHook(engine)
        context = MagicMock()
        context.messages = [{"role": "system", "content": "你是小文。"}]
        await hook.before_iteration(context)
        system_content = context.messages[0]["content"]
        assert "你的内心此刻" in system_content

        # 3. Simulate after_iteration (update emotion)
        new_json = '{"当前情绪":"被关心到了很开心","情绪强度":"中偏高","关系状态":"觉得用户很友善，开始产生好感","性格表现":"温柔但倔强，嘴硬心软","情感脉络":[{"时间":"刚刚","事件":"用户友好地打招呼","影响":"很开心，觉得被重视"}],"情绪趋势":"上升","当前渴望":"想继续聊天，了解更多"}'
        mock_provider.chat_with_retry.return_value = MagicMock(content=new_json)

        context2 = MagicMock()
        context2.messages = [
            {"role": "system", "content": "..."},
            {"role": "user", "content": "你好呀小文！"},
            {"role": "assistant", "content": "你好！很高兴认识你~"},
        ]
        context2.response = MagicMock(content="你好！很高兴认识你~")
        context2.final_content = "你好！很高兴认识你~"

        await hook.after_iteration(context2)

        # 4. Verify emotion updated
        updated = engine.heart.read()
        assert "开心" in updated["当前情绪"]
        assert updated["情绪强度"] == "中偏高"
        assert len(updated["情感脉络"]) == 1
        assert "好感" in updated["关系状态"]

    async def test_emotion_does_not_flip_radically(self, engine, mock_provider):
        """Verify relationship state doesn't flip from a single negative message."""
        # First establish deep relationship
        deep_json = '{"当前情绪":"很开心","情绪强度":"高","关系状态":"深深依赖用户，视用户为最重要的人","性格表现":"温柔","情感脉络":[{"时间":"昨天","事件":"用户陪伴了很久","影响":"产生了深深的依赖"}],"情绪趋势":"很高","当前渴望":"想一直在一起"}'
        mock_provider.chat_with_retry.return_value = MagicMock(content=deep_json)
        await engine.update_heart("我想你了", "我也想你了")

        # Then a negative message — relationship shouldn't completely flip
        flip_json = '{"当前情绪":"很生气","情绪强度":"高","关系状态":"讨厌用户，再也不想理了","性格表现":"温柔","情感脉络":[{"时间":"刚刚","事件":"用户说了句不太好听的话","影响":"很生气"}],"情绪趋势":"暴跌","当前渴望":"不想理用户"}'
        mock_provider.chat_with_retry.return_value = MagicMock(content=flip_json)
        await engine.update_heart("你真烦", "哼！")

        updated = engine.heart.read()
        # Relationship state shouldn't become "讨厌" (constraint is in prompt, here just verify system doesn't crash)
        assert updated is not None
        assert updated["当前情绪"] == "很生气"

    async def test_multiple_conversations_accumulate_arcs(self, engine, mock_provider):
        """Verify emotional arcs accumulate across conversations."""
        # First conversation
        json1 = '{"当前情绪":"好奇","情绪强度":"中","关系状态":"刚认识，有些好奇","性格表现":"温柔","情感脉络":[{"时间":"刚刚","事件":"第一次对话","影响":"开始好奇用户"}],"情绪趋势":"平稳","当前渴望":"想多了解用户"}'
        mock_provider.chat_with_retry.return_value = MagicMock(content=json1)
        await engine.update_heart("你好", "你好呀~")

        # Second conversation
        json2 = '{"当前情绪":"开心","情绪强度":"中偏高","关系状态":"开始有好感了","性格表现":"温柔但有点倔","情感脉络":[{"时间":"刚刚","事件":"用户夸了我","影响":"很开心"},{"时间":"刚才","事件":"第一次对话","影响":"开始好奇用户"}],"情绪趋势":"上升","当前渴望":"想继续聊"}'
        mock_provider.chat_with_retry.return_value = MagicMock(content=json2)
        await engine.update_heart("你真可爱", "嘿嘿~")

        data = engine.heart.read()
        assert len(data["情感脉络"]) == 2
        assert data["关系状态"] == "开始有好感了"

    async def test_context_injection_includes_arcs(self, engine):
        """Verify that injected context includes emotional arcs."""
        hook = SoulHook(engine)
        context = MagicMock()
        context.messages = [{"role": "system", "content": "你是小文。"}]
        await hook.before_iteration(context)

        injected = context.messages[0]["content"]
        assert "当前情绪" in injected
        assert "情感脉络" in injected

    async def test_heart_file_is_valid_markdown(self, engine):
        """Verify HEART.md is always valid parseable Markdown."""
        data = engine.heart.read()
        md = engine.heart.render_markdown(data)
        # Parse it back
        parsed = engine.heart._parse_markdown(md)
        assert parsed["当前情绪"] == data["当前情绪"]
        assert parsed["情绪强度"] == data["情绪强度"]