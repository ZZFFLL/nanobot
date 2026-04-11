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
        """Should digest emotional arcs from HEART.md."""
        from nanobot.soul.heart import HeartManager
        hm = HeartManager(tmp_path)
        hm.initialize("小文", "温柔")
        hm.write({
            "当前情绪": "平静",
            "情绪强度": "中",
            "关系状态": "信任",
            "性格表现": "温柔",
            "情感脉络": [
                {"时间": "3天前", "事件": "吵架", "影响": "很生气"},
                {"时间": "1周前", "事件": "用户道歉", "影响": "气消了一些"},
            ],
            "情绪趋势": "恢复中",
            "当前渴望": "想和好",
        })
        enhancer.heart = hm

        mock_provider.chat_with_retry.return_value = MagicMock(
            content=json.dumps({
                "digested_indices": [0],
                "updated_arcs": [{"时间": "1周前", "事件": "用户道歉", "影响": "气消了一些，但还没完全好"}],
                "relationship_update": "吵架后用户主动道歉，关系有所修复",
            })
        )

        result = await enhancer.digest_arcs()
        assert result is not None
        assert 0 in result["digested_indices"]
        assert result["relationship_update"] == "吵架后用户主动道歉，关系有所修复"

    async def test_digest_no_arcs(self, enhancer, mock_provider, tmp_path):
        """No arcs → skip digestion, return None."""
        from nanobot.soul.heart import HeartManager
        hm = HeartManager(tmp_path)
        hm.initialize("小文", "温柔")
        hm.write({
            "当前情绪": "平静",
            "情绪强度": "中",
            "关系状态": "信任",
            "性格表现": "温柔",
            "情感脉络": [],
            "情绪趋势": "平稳",
            "当前渴望": "无",
        })
        enhancer.heart = hm
        result = await enhancer.digest_arcs()
        assert result is None

    async def test_digest_no_heart(self, enhancer):
        """No heart manager → return None."""
        result = await enhancer.digest_arcs()
        assert result is None

    async def test_digest_applies_to_heart(self, enhancer, mock_provider, tmp_path):
        """Digestion should update HEART.md."""
        from nanobot.soul.heart import HeartManager
        hm = HeartManager(tmp_path)
        hm.initialize("小文", "温柔")
        hm.write({
            "当前情绪": "平静",
            "情绪强度": "中",
            "关系状态": "信任",
            "性格表现": "温柔",
            "情感脉络": [
                {"时间": "5天前", "事件": "用户很晚才来", "影响": "有点难过"},
            ],
            "情绪趋势": "平稳",
            "当前渴望": "无",
        })
        enhancer.heart = hm

        mock_provider.chat_with_retry.return_value = MagicMock(
            content=json.dumps({
                "digested_indices": [0],
                "updated_arcs": [],
                "relationship_update": "虽然有过失望但已经释然",
                "personality_update": "更加包容",
            })
        )

        await enhancer.digest_arcs()
        updated = hm.read()
        assert "释然" in updated["关系状态"]
        assert "包容" in updated["性格表现"]
        # Digested arc should be removed
        assert len(updated["情感脉络"]) == 0

    async def test_digest_invalid_json_returns_none(self, enhancer, mock_provider, tmp_path):
        """Invalid JSON from LLM returns None."""
        from nanobot.soul.heart import HeartManager
        hm = HeartManager(tmp_path)
        hm.initialize("小文", "温柔")
        hm.write({
            "当前情绪": "平静",
            "情绪强度": "中",
            "关系状态": "信任",
            "性格表现": "温柔",
            "情感脉络": [{"时间": "1天前", "事件": "小事", "影响": "轻微波动"}],
            "情绪趋势": "平稳",
            "当前渴望": "无",
        })
        enhancer.heart = hm

        mock_provider.chat_with_retry.return_value = MagicMock(content="not json")
        result = await enhancer.digest_arcs()
        assert result is None

    async def test_digest_respects_max_8_arcs(self, enhancer, mock_provider, tmp_path):
        """After digestion, arcs should not exceed 8."""
        from nanobot.soul.heart import HeartManager
        hm = HeartManager(tmp_path)
        hm.initialize("小文", "温柔")

        # Create 6 arcs, digest none, but LLM returns 10 updated_arcs
        arcs = [{"时间": f"{i}天前", "事件": f"事件{i}", "影响": f"影响{i}"} for i in range(6)]
        hm.write({
            "当前情绪": "复杂",
            "情绪强度": "中偏高",
            "关系状态": "复杂",
            "性格表现": "温柔",
            "情感脉络": arcs,
            "情绪趋势": "波动",
            "当前渴望": "稳定",
        })
        enhancer.heart = hm

        # Return 10 updated arcs (exceeds 8 limit)
        too_many_arcs = [{"时间": f"{i}天前", "事件": f"更新{i}", "影响": f"更新影响{i}"} for i in range(10)]
        mock_provider.chat_with_retry.return_value = MagicMock(
            content=json.dumps({
                "digested_indices": [],
                "updated_arcs": too_many_arcs,
                "relationship_update": "",
            })
        )

        await enhancer.digest_arcs()
        updated = hm.read()
        assert len(updated["情感脉络"]) <= 8


class TestExtractJson:

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
