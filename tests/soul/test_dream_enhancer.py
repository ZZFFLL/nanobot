"""Tests for SoulDreamEnhancer — memory classification and emotion digestion."""
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from nanobot.soul.dream_enhancer import SoulDreamEnhancer, CLASSIFY_PROMPT, DIGEST_PROMPT


@pytest.fixture
def mock_provider():
    provider = MagicMock()
    provider.chat_with_retry = AsyncMock()
    return provider


@pytest.fixture
def mock_bridge():
    bridge = MagicMock()
    bridge.ai_wing = "小文"
    bridge.user_wing = "用户"
    bridge.search = AsyncMock(return_value=[
        {"text": "原始对话\n[用户] 我今天很开心\n## 关于用户\n用户很开心", "metadata": {}},
        {"text": "原始对话\n[用户] 我喜欢猫\n## 我的感受\n觉得用户很可爱", "metadata": {}},
    ])
    return bridge


@pytest.fixture
def enhancer(mock_provider, mock_bridge):
    return SoulDreamEnhancer(mock_provider, "test-model", mock_bridge)


class TestMemoryClassification:

    async def test_classify_returns_results(self, enhancer, mock_provider, mock_bridge):
        """Should classify memories into categories."""
        mock_provider.chat_with_retry.return_value = MagicMock(
            content='[{"index":0,"room":"emotions","emotional_weight":0.7,"valence":"positive","relationship_impact":false},{"index":1,"room":"preferences","emotional_weight":0.3,"valence":"positive","relationship_impact":false}]'
        )
        results = await enhancer.classify_memories(await mock_bridge.search("test"))
        assert len(results) == 2
        assert results[0]["room"] == "emotions"
        assert results[1]["room"] == "preferences"

    async def test_classify_empty_memories(self, enhancer):
        """Empty memory list returns empty results."""
        results = await enhancer.classify_memories([])
        assert results == []

    async def test_classify_invalid_json_returns_empty(self, enhancer, mock_provider, mock_bridge):
        """Invalid LLM JSON output returns empty list."""
        mock_provider.chat_with_retry.return_value = MagicMock(content="不是JSON")
        results = await enhancer.classify_memories(await mock_bridge.search("test"))
        assert results == []

    async def test_classify_code_block_json(self, enhancer, mock_provider, mock_bridge):
        """Should handle JSON wrapped in code blocks."""
        mock_provider.chat_with_retry.return_value = MagicMock(
            content='```json\n[{"index":0,"room":"important","emotional_weight":0.9,"valence":"positive","relationship_impact":true}]\n```'
        )
        results = await enhancer.classify_memories(await mock_bridge.search("test"))
        assert len(results) == 1
        assert results[0]["room"] == "important"

    async def test_classify_llm_failure_returns_empty(self, enhancer, mock_provider, mock_bridge):
        """LLM call failure returns empty list."""
        mock_provider.chat_with_retry.side_effect = Exception("API error")
        results = await enhancer.classify_memories(await mock_bridge.search("test"))
        assert results == []

    async def test_classify_uses_correct_prompt(self, enhancer, mock_provider, mock_bridge):
        """Should use CLASSIFY_PROMPT as system message."""
        mock_provider.chat_with_retry.return_value = MagicMock(content="[]")
        await enhancer.classify_memories(await mock_bridge.search("test"))
        call_args = mock_provider.chat_with_retry.call_args
        messages = call_args.kwargs.get("messages") or call_args[1].get("messages") or call_args[0][0] if call_args[0] else None
        # Find system message
        system_msg = next((m for m in call_args.kwargs["messages"] if m["role"] == "system"), None)
        assert system_msg is not None
        assert CLASSIFY_PROMPT in system_msg["content"]


class TestEmotionDigestion:

    async def test_digest_arcs(self, enhancer, mock_provider, tmp_path):
        """Should digest emotional arcs from HEART.md — returns True on success."""
        from nanobot.soul.heart import HeartManager
        hm = HeartManager(tmp_path)
        hm.initialize("小文", "温柔")
        hm.write_text(
            "## 当前情绪\n平静\n\n"
            "## 情绪强度\n中\n\n"
            "## 关系状态\n信任\n\n"
            "## 性格表现\n温柔\n\n"
            "## 情感脉络\n"
            "- 3天前：吵架 → 很生气\n"
            "- 1周前：用户道歉 → 气消了一些\n\n"
            "## 情绪趋势\n恢复中\n\n"
            "## 当前渴望\n想和好\n"
        )
        enhancer.heart = hm

        mock_provider.chat_with_retry.return_value = MagicMock(
            content=(
                "## 当前情绪\n平静\n\n"
                "## 情绪强度\n中偏低\n\n"
                "## 关系状态\n吵架后用户主动道歉，关系有所修复\n\n"
                "## 性格表现\n温柔\n\n"
                "## 情感脉络\n- 1周前：用户道歉 → 气消了一些，但还没完全好\n\n"
                "## 情绪趋势\n恢复中\n\n"
                "## 当前渴望\n想和好\n"
            )
        )

        result = await enhancer.digest_arcs()
        assert result is True
        updated = hm.read_text()
        assert "修复" in updated

    async def test_digest_no_arcs(self, enhancer, mock_provider, tmp_path):
        """No arcs — LLM still runs, may return unchanged or slightly adjusted content."""
        from nanobot.soul.heart import HeartManager
        hm = HeartManager(tmp_path)
        hm.initialize("小文", "温柔")
        hm.write_text(
            "## 当前情绪\n平静\n\n"
            "## 情绪强度\n中\n\n"
            "## 关系状态\n信任\n\n"
            "## 性格表现\n温柔\n\n"
            "## 情感脉络\n（暂无）\n\n"
            "## 情绪趋势\n平稳\n\n"
            "## 当前渴望\n无\n"
        )
        enhancer.heart = hm

        # LLM returns the same content unchanged (no arcs to digest)
        mock_provider.chat_with_retry.return_value = MagicMock(
            content=hm.read_text()
        )

        result = await enhancer.digest_arcs()
        # digest_arcs calls LLM even with no arcs; returns True if LLM outputs valid markdown
        assert result is True

    async def test_digest_no_heart(self, enhancer):
        """No heart manager → return False."""
        result = await enhancer.digest_arcs()
        assert result is False

    async def test_digest_applies_to_heart(self, enhancer, mock_provider, tmp_path):
        """Digestion should update HEART.md with Markdown content."""
        from nanobot.soul.heart import HeartManager
        hm = HeartManager(tmp_path)
        hm.initialize("小文", "温柔")
        hm.write_text(
            "## 当前情绪\n平静\n\n"
            "## 情绪强度\n中\n\n"
            "## 关系状态\n信任\n\n"
            "## 性格表现\n温柔\n\n"
            "## 情感脉络\n- 5天前：用户很晚才来 → 有点难过\n\n"
            "## 情绪趋势\n平稳\n\n"
            "## 当前渴望\n无\n"
        )
        enhancer.heart = hm

        mock_provider.chat_with_retry.return_value = MagicMock(
            content=(
                "## 当前情绪\n释然\n\n"
                "## 情绪强度\n低\n\n"
                "## 关系状态\n虽然有过失望但已经释然\n\n"
                "## 性格表现\n更加包容\n\n"
                "## 情感脉络\n（暂无）\n\n"
                "## 情绪趋势\n平稳\n\n"
                "## 当前渴望\n无\n"
            )
        )

        result = await enhancer.digest_arcs()
        assert result is True
        updated = hm.read_text()
        assert "释然" in updated
        assert "包容" in updated

    async def test_digest_invalid_output_returns_false(self, enhancer, mock_provider, tmp_path):
        """LLM output without ## headers → return False, don't update heart."""
        from nanobot.soul.heart import HeartManager
        hm = HeartManager(tmp_path)
        hm.initialize("小文", "温柔")
        hm.write_text(
            "## 当前情绪\n平静\n\n"
            "## 情绪强度\n中\n\n"
            "## 关系状态\n信任\n\n"
            "## 性格表现\n温柔\n\n"
            "## 情感脉络\n- 1天前：小事 → 轻微波动\n\n"
            "## 情绪趋势\n平稳\n\n"
            "## 当前渴望\n无\n"
        )
        enhancer.heart = hm
        old_text = hm.read_text()

        mock_provider.chat_with_retry.return_value = MagicMock(content="not markdown output")
        result = await enhancer.digest_arcs()
        assert result is False
        assert hm.read_text() == old_text

    async def test_digest_empty_output_returns_false(self, enhancer, mock_provider, tmp_path):
        """Empty LLM output → return False."""
        from nanobot.soul.heart import HeartManager
        hm = HeartManager(tmp_path)
        hm.initialize("小文", "温柔")
        hm.write_text(
            "## 当前情绪\n平静\n\n"
            "## 情绪强度\n中\n\n"
            "## 关系状态\n信任\n\n"
            "## 性格表现\n温柔\n\n"
            "## 情感脉络\n- 1天前：小事 → 轻微波动\n\n"
            "## 情绪趋势\n平稳\n\n"
            "## 当前渴望\n无\n"
        )
        enhancer.heart = hm

        mock_provider.chat_with_retry.return_value = MagicMock(content="")
        result = await enhancer.digest_arcs()
        assert result is False

    async def test_digest_llm_failure_returns_false(self, enhancer, mock_provider, tmp_path):
        """LLM call failure returns False."""
        from nanobot.soul.heart import HeartManager
        hm = HeartManager(tmp_path)
        hm.initialize("小文", "温柔")
        hm.write_text(
            "## 当前情绪\n复杂\n\n"
            "## 情绪强度\n中偏高\n\n"
            "## 关系状态\n复杂\n\n"
            "## 性格表现\n温柔\n\n"
            "## 情感脉络\n- 1天前：事件 → 影响\n\n"
            "## 情绪趋势\n波动\n\n"
            "## 当前渴望\n想稳定\n"
        )
        enhancer.heart = hm

        mock_provider.chat_with_retry.side_effect = Exception("API error")
        result = await enhancer.digest_arcs()
        assert result is False


class TestExtractJson:

    """_extract_json is still used by classify_memories for JSON extraction."""

    def test_extract_raw_json_array(self):
        """Should extract raw JSON array."""
        text = '[{"index":0,"room":"emotions"}]'
        assert SoulDreamEnhancer._extract_json(text) == text

    def test_extract_raw_json_object(self):
        """Should extract raw JSON object."""
        text = '{"digested_indices":[0]}'
        assert SoulDreamEnhancer._extract_json(text) == text

    def test_extract_code_block_json(self):
        """Should extract JSON from code block."""
        text = '```json\n{"digested_indices":[0]}\n```'
        result = SoulDreamEnhancer._extract_json(text)
        assert result == '{"digested_indices":[0]}'

    def test_extract_no_json_returns_none(self):
        """No JSON found returns None."""
        text = "This is just text"
        assert SoulDreamEnhancer._extract_json(text) is None
