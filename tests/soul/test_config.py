"""Tests for SoulConfig and related config models."""
import json
import pytest

from nanobot.config.schema import (
    Config,
    SoulConfig,
    SoulModelConfig,
    SoulMemoryWriterConfig,
    SoulProactiveConfig,
    SoulEvolutionConfig,
)


class TestSoulModelConfig:

    def test_default_config(self):
        cfg = SoulModelConfig()
        assert cfg.model == ""
        assert cfg.temperature == 0.3
        assert cfg.max_tokens == 1000

    def test_custom_model_config(self):
        cfg = SoulModelConfig(model="claude-haiku-4-5", temperature=0.7, max_tokens=500)
        assert cfg.model == "claude-haiku-4-5"
        assert cfg.temperature == 0.7
        assert cfg.max_tokens == 500


class TestSoulMemoryWriterConfig:

    def test_defaults(self):
        cfg = SoulMemoryWriterConfig()
        assert cfg.max_retries == 3
        assert cfg.retry_delay == 5
        assert cfg.queue_max_size == 100


class TestSoulProactiveConfig:

    def test_defaults(self):
        cfg = SoulProactiveConfig()
        assert cfg.min_interval_s == 900
        assert cfg.max_interval_s == 7200
        assert cfg.idle_threshold_s == 43200


class TestSoulEvolutionConfig:

    def test_defaults(self):
        cfg = SoulEvolutionConfig()
        assert cfg.min_evidence_count == 3
        assert cfg.max_change_per_cycle == 0.2


class TestSoulConfig:

    def test_default_config(self):
        config = Config()
        assert config.agents.defaults.soul.enabled is False

    def test_soul_config_in_json(self):
        config = Config()
        data = json.loads(config.model_dump_json())
        assert "soul" in data["agents"]["defaults"]

    def test_has_all_model_configs(self):
        soul = SoulConfig()
        assert hasattr(soul, "emotion_model")
        assert hasattr(soul, "memory_classify_model")
        assert hasattr(soul, "proactive_model")
        assert hasattr(soul, "evolution_model")

    def test_has_sub_configs(self):
        soul = SoulConfig()
        assert hasattr(soul, "memory_writer")
        assert hasattr(soul, "proactive")
        assert hasattr(soul, "evolution")

    def test_full_soul_config(self):
        soul = SoulConfig(
            enabled=True,
            emotion_model=SoulModelConfig(model="claude-sonnet-4-6", temperature=0.3),
            memory_classify_model=SoulModelConfig(model="claude-haiku-4-5", temperature=0.2),
            proactive_model=SoulModelConfig(model="claude-sonnet-4-6", temperature=0.7),
        )
        assert soul.enabled is True
        assert soul.emotion_model.model == "claude-sonnet-4-6"
        assert soul.proactive_model.temperature == 0.7
        assert soul.memory_classify_model.model == "claude-haiku-4-5"

    def test_per_task_temperatures(self):
        """Different tasks should have different default temperatures."""
        soul = SoulConfig()
        # Emotion: conservative
        assert soul.emotion_model.temperature == 0.3
        # Memory classify: more conservative
        assert soul.memory_classify_model.temperature == 0.2
        # Proactive: more creative
        assert soul.proactive_model.temperature == 0.7
        # Evolution: conservative
        assert soul.evolution_model.temperature == 0.2
