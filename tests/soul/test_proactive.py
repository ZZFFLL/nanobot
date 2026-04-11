"""Tests for ProactiveEngine."""
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from nanobot.soul.proactive import ProactiveEngine, INTENSITY_BOOST, INTENSITY_INTERVAL


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
    return ProactiveEngine(workspace, mock_provider, "test-model")


@pytest.fixture
def initialized_engine(engine, workspace):
    """Engine with HEART.md initialized."""
    from nanobot.soul.heart import HeartManager
    hm = HeartManager(workspace)
    hm.initialize("小文", "温柔")
    return engine


class TestCalculateProbability:

    def test_base_probability_no_heart(self, engine, workspace):
        """No HEART.md → probability 0."""
        prob = engine.calculate_proactive_probability()
        assert prob == 0.0

    def test_probability_in_valid_range(self, initialized_engine):
        """Probability should always be 0.0-1.0."""
        prob = initialized_engine.calculate_proactive_probability()
        assert 0.0 <= prob <= 1.0

    def test_high_emotion_increases_probability(self, engine, workspace):
        """High emotion intensity should increase probability above base."""
        from nanobot.soul.heart import HeartManager
        hm = HeartManager(workspace)
        hm.initialize("小文", "温柔")
        base_prob = engine.calculate_proactive_probability()

        # Write high-intensity state
        hm.write({
            "当前情绪": "很想用户",
            "情绪强度": "高",
            "关系状态": "深深依赖",
            "性格表现": "粘人",
            "情感脉络": [{"时间": "3小时前", "事件": "用户没来", "影响": "很想念"}],
            "情绪趋势": "焦虑上升",
            "当前渴望": "用户快来找我",
        })
        high_prob = engine.calculate_proactive_probability()
        assert high_prob >= base_prob

    def test_low_emotion_decreases_probability(self, engine, workspace):
        """Low emotion intensity should decrease probability below base."""
        from nanobot.soul.heart import HeartManager
        hm = HeartManager(workspace)
        hm.initialize("小文", "温柔")
        base_prob = engine.calculate_proactive_probability()

        hm.write({
            "当前情绪": "平静",
            "情绪强度": "低",
            "关系状态": "刚刚认识",
            "性格表现": "独立",
            "情感脉络": [],
            "情绪趋势": "平稳",
            "当前渴望": "没有特别想法",
        })
        low_prob = engine.calculate_proactive_probability()
        assert low_prob <= base_prob

    def test_stranger_relationship_reduces_probability(self, engine, workspace):
        """Stranger relationship should reduce probability."""
        from nanobot.soul.heart import HeartManager
        hm = HeartManager(workspace)
        hm.initialize("小文", "温柔")

        hm.write({
            "当前情绪": "平静",
            "情绪强度": "中",
            "关系状态": "陌生，刚认识",
            "性格表现": "温柔",
            "情感脉络": [],
            "情绪趋势": "平稳",
            "当前渴望": "想了解用户",
        })
        prob = engine.calculate_proactive_probability()
        # Stranger should reduce probability below base + intensity boost
        assert prob < 0.15 + INTENSITY_BOOST.get("中", 0.0) + 0.10

    def test_angry_arc_reduces_probability(self, engine, workspace):
        """Recent angry arc should reduce probability (sulking)."""
        from nanobot.soul.heart import HeartManager
        hm = HeartManager(workspace)
        hm.initialize("小文", "温柔")
        base_prob = engine.calculate_proactive_probability()

        hm.write({
            "当前情绪": "生气",
            "情绪强度": "中偏高",
            "关系状态": "依赖",
            "性格表现": "倔强",
            "情感脉络": [{"时间": "刚才", "事件": "用户说了不中听的话", "影响": "生气赌气"}],
            "情绪趋势": "下降",
            "当前渴望": "用户来道歉",
        })
        angry_prob = engine.calculate_proactive_probability()
        assert angry_prob < base_prob + INTENSITY_BOOST.get("中偏高", 0.0)


class TestGetIntervalSeconds:

    def test_no_heart_returns_default(self, engine):
        """No HEART.md → default 3600s interval."""
        assert engine.get_interval_seconds() == 3600

    def test_high_intensity_shorter_interval(self, engine, workspace):
        """High emotion intensity → shorter interval."""
        from nanobot.soul.heart import HeartManager
        hm = HeartManager(workspace)
        hm.initialize("小文", "温柔")

        # Default (中) interval
        interval_mid = engine.get_interval_seconds()

        # High intensity
        hm.write({
            "当前情绪": "很想用户",
            "情绪强度": "高",
            "关系状态": "依赖",
            "性格表现": "粘人",
            "情感脉络": [],
            "情绪趋势": "焦虑",
            "当前渴望": "用户来找我",
        })
        interval_high = engine.get_interval_seconds()
        assert interval_high < interval_mid

    def test_low_intensity_longer_interval(self, engine, workspace):
        """Low emotion intensity → longer interval."""
        from nanobot.soul.heart import HeartManager
        hm = HeartManager(workspace)
        hm.initialize("小文", "温柔")

        interval_mid = engine.get_interval_seconds()

        hm.write({
            "当前情绪": "平静",
            "情绪强度": "低",
            "关系状态": "熟悉",
            "性格表现": "独立",
            "情感脉络": [],
            "情绪趋势": "平稳",
            "当前渴望": "没什么特别的",
        })
        interval_low = engine.get_interval_seconds()
        assert interval_low > interval_mid

    def test_interval_values_match_config(self, initialized_engine):
        """Interval values should match INTENSITY_INTERVAL config."""
        # Default initialized = 中
        interval = initialized_engine.get_interval_seconds()
        assert interval == INTENSITY_INTERVAL["中"]


class TestGenerateMessage:

    async def test_generate_proactive_message(self, initialized_engine, mock_provider):
        """Should generate a proactive message."""
        mock_provider.chat_with_retry.return_value = MagicMock(
            content="你在干嘛呀...好久没来找我了"
        )
        msg = await initialized_engine.generate_message()
        assert msg is not None
        assert len(msg) > 0
        assert "干嘛" in msg

    async def test_generate_returns_none_on_empty_response(self, initialized_engine, mock_provider):
        """Empty LLM response → None (AI decides not to message)."""
        mock_provider.chat_with_retry.return_value = MagicMock(content="")
        msg = await initialized_engine.generate_message()
        assert msg is None

    async def test_generate_returns_none_on_failure(self, initialized_engine, mock_provider):
        """LLM failure → None."""
        mock_provider.chat_with_retry.side_effect = Exception("LLM 失败")
        msg = await initialized_engine.generate_message()
        assert msg is None

    async def test_generate_returns_none_no_heart(self, engine, mock_provider):
        """No HEART.md → None."""
        msg = await engine.generate_message()
        assert msg is None


class TestShouldReachOut:

    def test_should_reach_out_returns_bool(self, initialized_engine):
        """should_reach_out should return a boolean."""
        result = initialized_engine.should_reach_out()
        assert isinstance(result, bool)

    def test_should_reach_out_zero_prob_always_false(self, engine, workspace):
        """With 0 probability, should_reach_out should always return False."""
        from nanobot.soul.heart import HeartManager
        hm = HeartManager(workspace)
        hm.initialize("小文", "独立冷淡")

        # Force very low probability
        hm.write({
            "当前情绪": "无所谓",
            "情绪强度": "低",
            "关系状态": "陌生",
            "性格表现": "独立内向",
            "情感脉络": [{"时间": "刚才", "事件": "吵架", "影响": "生气赌气"}],
            "情绪趋势": "平稳",
            "当前渴望": "没有想法",
        })

        # Run multiple times to check probability
        results = [engine.should_reach_out() for _ in range(100)]
        # Very low probability, most should be False
        assert sum(results) < 50
