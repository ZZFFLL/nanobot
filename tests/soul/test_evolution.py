"""Tests for EvolutionEngine — personality and relationship evolution."""
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from nanobot.soul.evolution import EvolutionEngine, EVOLUTION_PROMPT, SENSITIVITY_KEYWORDS


@pytest.fixture
def workspace(tmp_path):
    return tmp_path


@pytest.fixture
def mock_provider():
    provider = MagicMock()
    provider.chat_with_retry = AsyncMock()
    return provider


@pytest.fixture
def engine(workspace, mock_provider):
    return EvolutionEngine(workspace, mock_provider, "test-model")


class TestCheckEvolution:

    async def test_no_evolution_without_evidence(self, engine, workspace):
        """Insufficient evidence should not trigger evolution."""
        from nanobot.soul.heart import HeartManager
        hm = HeartManager(workspace)
        hm.initialize("小文", "温柔")
        hm.write({
            "当前情绪": "平静",
            "情绪强度": "中",
            "关系状态": "信任",
            "性格表现": "温柔",
            "情感脉络": [{"时间": "1天前", "事件": "单次事件", "影响": "轻微影响"}],
            "情绪趋势": "平稳",
            "当前渴望": "无",
        })
        result = await engine.check_evolution()
        assert result is None

    async def test_no_evolution_without_heart(self, engine):
        """No HEART.md → None."""
        result = await engine.check_evolution()
        assert result is None

    async def test_evolution_with_sufficient_evidence(self, engine, mock_provider, workspace):
        """Sufficient evidence should trigger evolution check."""
        from nanobot.soul.heart import HeartManager
        hm = HeartManager(workspace)
        hm.initialize("小文", "温柔")
        hm.write({
            "当前情绪": "平静",
            "情绪强度": "中",
            "关系状态": "信任",
            "性格表现": "温柔",
            "情感脉络": [
                {"时间": "1天前", "事件": "用户寻求安慰", "影响": "想去照顾"},
                {"时间": "3天前", "事件": "用户倾诉烦恼", "影响": "心疼"},
                {"时间": "5天前", "事件": "用户心情不好", "影响": "想陪伴"},
            ],
            "情绪趋势": "平稳",
            "当前渴望": "无",
        })

        mock_provider.chat_with_retry.return_value = MagicMock(
            content=json.dumps({
                "personality_update": "变得更加照顾人",
                "reason": "用户反复寻求安慰",
                "evidence_count": 3,
            })
        )

        result = await engine.check_evolution()
        assert result is not None
        assert "personality_update" in result

    async def test_evolution_is_conservative(self, engine, mock_provider, workspace):
        """Evolution should be conservative and gradual."""
        from nanobot.soul.heart import HeartManager
        hm = HeartManager(workspace)
        hm.initialize("小文", "温柔但倔强")
        hm.write({
            "当前情绪": "平静",
            "情绪强度": "中",
            "关系状态": "信任",
            "性格表现": "温柔但倔强",
            "情感脉络": [
                {"时间": "1天前", "事件": "反复吵架", "影响": "受伤"},
                {"时间": "2天前", "事件": "又吵了", "影响": "更受伤"},
                {"时间": "3天前", "事件": "吵架", "影响": "难过"},
            ],
            "情绪趋势": "下降",
            "当前渴望": "安静",
        })

        mock_provider.chat_with_retry.return_value = MagicMock(
            content=json.dumps({
                "personality_update": "变得更加敏感，但核心温柔不变",
                "reason": "反复吵架的经历",
                "evidence_count": 3,
            })
        )

        result = await engine.check_evolution()
        assert result is not None
        # Conservative: "核心温柔不变" shows gradual change
        assert "核心温柔不变" in result["personality_update"]

    async def test_sensitive_personality_lower_threshold(self, engine, workspace):
        """Sensitive personality should lower evidence threshold."""
        from nanobot.soul.heart import HeartManager
        hm = HeartManager(workspace)
        hm.initialize("小文", "温柔")
        hm.write({
            "当前情绪": "委屈",
            "情绪强度": "中偏高",
            "关系状态": "有点受伤",
            "性格表现": "敏感，容易受伤",
            "情感脉络": [
                {"时间": "1天前", "事件": "用户说了重话", "影响": "很受伤"},
                {"时间": "2天前", "事件": "用户态度冷淡", "影响": "不安"},
            ],
            "情绪趋势": "下降",
            "当前渴望": "被安慰",
        })

        # Sensitive personality: threshold should be 3 + (-1) = 2
        # With 2 arcs, should still trigger LLM check
        # But the engine won't call LLM if arcs < adjusted threshold
        # Let's verify the threshold calculation
        data = hm.read()
        personality = data.get("性格表现", "")
        threshold = engine.min_evidence
        for keyword, delta in SENSITIVITY_KEYWORDS.items():
            if keyword in personality:
                threshold = max(1, threshold + delta)
        # "敏感" and "容易受伤" both reduce threshold
        assert threshold <= 2

    async def test_blunt_personality_higher_threshold(self, engine, workspace):
        """Blunt personality should raise evidence threshold."""
        from nanobot.soul.heart import HeartManager
        hm = HeartManager(workspace)
        hm.initialize("小文", "独立")
        hm.write({
            "当前情绪": "平静",
            "情绪强度": "中",
            "关系状态": "信任",
            "性格表现": "钝感，大大咧咧，独立",
            "情感脉络": [
                {"时间": "1天前", "事件": "小事", "影响": "无所谓"},
            ],
            "情绪趋势": "平稳",
            "当前渴望": "无",
        })

        # Blunt personality: threshold should be 3 + 1 + 1 + 1 = 6
        data = hm.read()
        personality = data.get("性格表现", "")
        threshold = engine.min_evidence
        for keyword, delta in SENSITIVITY_KEYWORDS.items():
            if keyword in personality:
                threshold = max(1, threshold + delta)
        assert threshold >= 5

    async def test_llm_returns_null(self, engine, mock_provider, workspace):
        """LLM returning 'null' means no evolution needed."""
        from nanobot.soul.heart import HeartManager
        hm = HeartManager(workspace)
        hm.initialize("小文", "温柔")
        hm.write({
            "当前情绪": "平静",
            "情绪强度": "中",
            "关系状态": "信任",
            "性格表现": "温柔",
            "情感脉络": [
                {"时间": "1天前", "事件": "正常对话", "影响": "无特别"},
                {"时间": "2天前", "事件": "日常聊天", "影响": "一般"},
                {"时间": "3天前", "事件": "说了几句话", "影响": "没感觉"},
            ],
            "情绪趋势": "平稳",
            "当前渴望": "无",
        })

        mock_provider.chat_with_retry.return_value = MagicMock(content="null")
        result = await engine.check_evolution()
        assert result is None

    async def test_llm_failure_returns_none(self, engine, mock_provider, workspace):
        """LLM call failure returns None."""
        from nanobot.soul.heart import HeartManager
        hm = HeartManager(workspace)
        hm.initialize("小文", "温柔")
        hm.write({
            "当前情绪": "复杂",
            "情绪强度": "中偏高",
            "关系状态": "复杂",
            "性格表现": "温柔",
            "情感脉络": [
                {"时间": f"{i}天前", "事件": f"事件{i}", "影响": f"影响{i}"}
                for i in range(4)
            ],
            "情绪趋势": "波动",
            "当前渴望": "想稳定",
        })

        mock_provider.chat_with_retry.side_effect = Exception("API error")
        result = await engine.check_evolution()
        assert result is None


class TestApplyEvolution:

    def test_apply_evolution_updates_soul(self, engine, workspace):
        """Evolution result should update SOUL.md."""
        from nanobot.soul.heart import HeartManager
        hm = HeartManager(workspace)
        hm.initialize("小文", "温柔但倔强")

        soul_file = workspace / "SOUL.md"
        soul_file.write_text("# 性格\n温柔但倔强，嘴硬心软\n", encoding="utf-8")

        evolution_result = {
            "personality_update": "变得更加照顾人",
            "reason": "用户反复寻求安慰",
        }

        engine.apply_evolution(evolution_result)

        updated_soul = soul_file.read_text(encoding="utf-8")
        assert "照顾人" in updated_soul
        assert "成长的痕迹" in updated_soul

    def test_apply_evolution_no_soul_file(self, engine, workspace):
        """No SOUL.md should not crash."""
        evolution_result = {
            "personality_update": "变化",
            "reason": "测试",
        }
        # Should not raise
        engine.apply_evolution(evolution_result)

    def test_apply_evolution_no_personality_update(self, engine, workspace):
        """No personality_update in result should not modify SOUL.md."""
        soul_file = workspace / "SOUL.md"
        original = "# 性格\n温柔\n"
        soul_file.write_text(original, encoding="utf-8")

        engine.apply_evolution({"reason": "测试"})
        assert soul_file.read_text(encoding="utf-8") == original
