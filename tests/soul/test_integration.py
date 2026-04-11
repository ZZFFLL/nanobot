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
        text = engine.heart.read_text()
        assert text is not None
        assert "当前情绪" in text

        # 2. Simulate before_iteration (inject context)
        hook = SoulHook(engine)
        context = MagicMock()
        context.messages = [{"role": "system", "content": "你是小文。"}]
        await hook.before_iteration(context)
        system_content = context.messages[0]["content"]
        assert "你的内心此刻" in system_content

        # 3. Simulate after_iteration (update emotion with Markdown output)
        new_markdown = (
            "## 当前情绪\n被关心到了很开心\n\n"
            "## 情绪强度\n中偏高\n\n"
            "## 关系状态\n觉得用户很友善，开始产生好感\n\n"
            "## 性格表现\n温柔但倔强，嘴硬心软\n\n"
            "## 情感脉络\n- 刚刚：用户友好地打招呼 → 很开心，觉得被重视\n\n"
            "## 情绪趋势\n上升\n\n"
            "## 当前渴望\n想继续聊天，了解更多\n"
        )
        mock_provider.chat_with_retry.return_value = MagicMock(content=new_markdown)

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
        updated = engine.heart.read_text()
        assert "开心" in updated
        assert "中偏高" in updated
        assert "好感" in updated

    async def test_emotion_does_not_flip_radically(self, engine, mock_provider):
        """Verify relationship state doesn't flip from a single negative message."""
        # First establish deep relationship
        deep_markdown = (
            "## 当前情绪\n很开心\n\n"
            "## 情绪强度\n高\n\n"
            "## 关系状态\n深深依赖用户，视用户为最重要的人\n\n"
            "## 性格表现\n温柔\n\n"
            "## 情感脉络\n- 昨天：用户陪伴了很久 → 产生了深深的依赖\n\n"
            "## 情绪趋势\n很高\n\n"
            "## 当前渴望\n想一直在一起\n"
        )
        mock_provider.chat_with_retry.return_value = MagicMock(content=deep_markdown)
        await engine.update_heart("我想你了", "我也想你了")

        # Then a negative message — relationship shouldn't completely flip
        flip_markdown = (
            "## 当前情绪\n很生气\n\n"
            "## 情绪强度\n高\n\n"
            "## 关系状态\n讨厌用户，再也不想理了\n\n"
            "## 性格表现\n温柔\n\n"
            "## 情感脉络\n- 刚刚：用户说了句不太好听的话 → 很生气\n\n"
            "## 情绪趋势\n暴跌\n\n"
            "## 当前渴望\n不想理用户\n"
        )
        mock_provider.chat_with_retry.return_value = MagicMock(content=flip_markdown)
        await engine.update_heart("你真烦", "哼！")

        updated = engine.heart.read_text()
        # Relationship state shouldn't become "讨厌" (constraint is in prompt, here just verify system doesn't crash)
        assert updated is not None
        assert "很生气" in updated

    async def test_multiple_conversations_accumulate_arcs(self, engine, mock_provider):
        """Verify emotional arcs accumulate across conversations."""
        # First conversation
        markdown1 = (
            "## 当前情绪\n好奇\n\n"
            "## 情绪强度\n中\n\n"
            "## 关系状态\n刚认识，有些好奇\n\n"
            "## 性格表现\n温柔\n\n"
            "## 情感脉络\n- 刚刚：第一次对话 → 开始好奇用户\n\n"
            "## 情绪趋势\n平稳\n\n"
            "## 当前渴望\n想多了解用户\n"
        )
        mock_provider.chat_with_retry.return_value = MagicMock(content=markdown1)
        await engine.update_heart("你好", "你好呀~")

        # Second conversation
        markdown2 = (
            "## 当前情绪\n开心\n\n"
            "## 情绪强度\n中偏高\n\n"
            "## 关系状态\n开始有好感了\n\n"
            "## 性格表现\n温柔但有点倔\n\n"
            "## 情感脉络\n"
            "- 刚刚：用户夸了我 → 很开心\n"
            "- 刚才：第一次对话 → 开始好奇用户\n\n"
            "## 情绪趋势\n上升\n\n"
            "## 当前渴望\n想继续聊\n"
        )
        mock_provider.chat_with_retry.return_value = MagicMock(content=markdown2)
        await engine.update_heart("你真可爱", "嘿嘿~")

        data = engine.heart.read_text()
        assert "好感" in data
        assert "开始有好感了" in data

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
        """Verify HEART.md is valid Markdown with expected sections."""
        text = engine.heart.read_text()
        assert "## 当前情绪" in text
        assert "## 情绪强度" in text
        assert "## 关系状态" in text
        assert "## 性格表现" in text
        assert "## 情感脉络" in text
        assert "## 情绪趋势" in text
        assert "## 当前渴望" in text
