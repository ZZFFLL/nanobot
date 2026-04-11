"""Tests for ProactiveEngine."""
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from nanobot.soul.proactive import ProactiveEngine, INTENSITY_BOOST, INTENSITY_INTERVAL, _extract_section


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


class TestExtractSection:

    def test_extract_existing_section(self):
        text = "## 当前情绪\n开心\n\n## 情绪强度\n中\n"
        assert _extract_section(text, "当前情绪") == "开心"

    def test_extract_missing_section(self):
        text = "## 当前情绪\n开心\n\n## 情绪强度\n中\n"
        assert _extract_section(text, "不存在") == ""

    def test_extract_multiline_section(self):
        text = "## 情感脉络\n- 事件A → 开心\n- 事件B → 难过\n\n## 当前渴望\n想聊天\n"
        result = _extract_section(text, "情感脉络")
        assert "事件A" in result
        assert "事件B" in result

    def test_extract_last_section(self):
        text = "## 当前情绪\n平静\n\n## 当前渴望\n想聊天\n"
        assert _extract_section(text, "当前渴望") == "想聊天"


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

        # Write high-intensity state as Markdown
        hm.write_text(
            "## 当前情绪\n很想用户\n\n"
            "## 情绪强度\n高\n\n"
            "## 关系状态\n深深依赖\n\n"
            "## 性格表现\n粘人\n\n"
            "## 情感脉络\n- 3小时前：用户没来 → 很想念\n\n"
            "## 情绪趋势\n焦虑上升\n\n"
            "## 当前渴望\n用户快来找我\n"
        )
        high_prob = engine.calculate_proactive_probability()
        assert high_prob >= base_prob

    def test_low_emotion_decreases_probability(self, engine, workspace):
        """Low emotion intensity should decrease probability below base."""
        from nanobot.soul.heart import HeartManager
        hm = HeartManager(workspace)
        hm.initialize("小文", "温柔")
        base_prob = engine.calculate_proactive_probability()

        hm.write_text(
            "## 当前情绪\n平静\n\n"
            "## 情绪强度\n低\n\n"
            "## 关系状态\n刚刚认识\n\n"
            "## 性格表现\n独立\n\n"
            "## 情感脉络\n（暂无）\n\n"
            "## 情绪趋势\n平稳\n\n"
            "## 当前渴望\n没有特别想法\n"
        )
        low_prob = engine.calculate_proactive_probability()
        assert low_prob <= base_prob

    def test_stranger_relationship_reduces_probability(self, engine, workspace):
        """Stranger relationship should reduce probability."""
        from nanobot.soul.heart import HeartManager
        hm = HeartManager(workspace)
        hm.initialize("小文", "温柔")

        hm.write_text(
            "## 当前情绪\n平静\n\n"
            "## 情绪强度\n中\n\n"
            "## 关系状态\n陌生，刚认识\n\n"
            "## 性格表现\n温柔\n\n"
            "## 情感脉络\n（暂无）\n\n"
            "## 情绪趋势\n平稳\n\n"
            "## 当前渴望\n想了解用户\n"
        )
        prob = engine.calculate_proactive_probability()
        # Stranger should reduce probability below base + intensity boost
        assert prob < 0.15 + INTENSITY_BOOST.get("中", 0.0) + 0.10

    def test_angry_arc_reduces_probability(self, engine, workspace):
        """Recent angry arc should reduce probability (sulking)."""
        from nanobot.soul.heart import HeartManager
        hm = HeartManager(workspace)
        hm.initialize("小文", "温柔")
        base_prob = engine.calculate_proactive_probability()

        hm.write_text(
            "## 当前情绪\n生气\n\n"
            "## 情绪强度\n中偏高\n\n"
            "## 关系状态\n依赖\n\n"
            "## 性格表现\n倔强\n\n"
            "## 情感脉络\n- 刚才：用户说了不中听的话 → 生气赌气\n\n"
            "## 情绪趋势\n下降\n\n"
            "## 当前渴望\n用户来道歉\n"
        )
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
        hm.write_text(
            "## 当前情绪\n很想用户\n\n"
            "## 情绪强度\n高\n\n"
            "## 关系状态\n依赖\n\n"
            "## 性格表现\n粘人\n\n"
            "## 情感脉络\n（暂无）\n\n"
            "## 情绪趋势\n焦虑\n\n"
            "## 当前渴望\n用户来找我\n"
        )
        interval_high = engine.get_interval_seconds()
        assert interval_high < interval_mid

    def test_low_intensity_longer_interval(self, engine, workspace):
        """Low emotion intensity → longer interval."""
        from nanobot.soul.heart import HeartManager
        hm = HeartManager(workspace)
        hm.initialize("小文", "温柔")

        interval_mid = engine.get_interval_seconds()

        hm.write_text(
            "## 当前情绪\n平静\n\n"
            "## 情绪强度\n低\n\n"
            "## 关系状态\n熟悉\n\n"
            "## 性格表现\n独立\n\n"
            "## 情感脉络\n（暂无）\n\n"
            "## 情绪趋势\n平稳\n\n"
            "## 当前渴望\n没什么特别的\n"
        )
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

        # Force very low probability: low intensity + stranger + independent + angry arc
        hm.write_text(
            "## 当前情绪\n无所谓\n\n"
            "## 情绪强度\n低\n\n"
            "## 关系状态\n陌生\n\n"
            "## 性格表现\n独立内向\n\n"
            "## 情感脉络\n- 刚才：吵架 → 生气赌气\n\n"
            "## 情绪趋势\n平稳\n\n"
            "## 当前渴望\n没有想法\n"
        )

        # Run multiple times to check probability
        results = [engine.should_reach_out() for _ in range(100)]
        # Very low probability, most should be False
        assert sum(results) < 50
