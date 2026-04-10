"""Unit tests for ReMe memory adapter."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nanobot.agent.reme_adapter import RemeMemoryAdapter


@pytest.fixture
def mock_config():
    """Create mock ReMe config."""
    config = MagicMock()
    config.working_dir = "reme_working"
    config.retrieve_top_k = 10
    config.enable_time_filter = True
    config.enable_profile_files = True
    config.enable_procedural_memory = True
    config.compression_enabled = False
    config.compression_block_size = 20
    config.summarizer_context_window = 4000
    config.summarizer_max_output_tokens = 500
    config.vector_store_backend = "chroma"

    # Profile config
    profile = MagicMock()
    profile.soul_file = "SOUL.md"
    profile.user_file = "USER.md"
    profile.memory_file = "MEMORY.md"
    config.profile = profile

    # Compression config
    compression = MagicMock()
    compression.input_reserved_tokens = 100
    config.compression = compression

    # Methods
    config.get_effective_llm_config = MagicMock(return_value={
        "model_name": "test-model",
        "api_key": "test-key",
        "base_url": "http://test",
    })
    config.get_effective_embedding_config = MagicMock(return_value={
        "model_name": "text-embedding-v3",
        "api_key": "test-key",
        "base_url": "http://test",
    })
    config.get_effective_vector_store_config = MagicMock(return_value={})
    config.get_compression_llm_config = MagicMock(return_value={
        "model_name": "test-model",
        "api_key": "test-key",
        "base_url": "http://test",
        "max_output_tokens": 500,
        "temperature": 0.3,
    })

    return config


@pytest.fixture
def mock_provider():
    """Create mock LLM provider."""
    provider = MagicMock()
    provider.api_key = "provider-key"
    provider.api_base = "http://provider"
    provider.get_default_model = MagicMock(return_value="provider-model")
    return provider


@pytest.fixture
def workspace(tmp_path):
    """Create temporary workspace."""
    return tmp_path


@pytest.fixture
def adapter(workspace, mock_config, mock_provider):
    """Create ReMe adapter."""
    return RemeMemoryAdapter(workspace, mock_config, mock_provider)


class TestCircuitBreaker:
    """Tests for circuit breaker pattern."""

    def test_initial_state_is_healthy(self, adapter):
        """Adapter should start healthy."""
        assert adapter.is_healthy() is False  # Not started yet
        assert adapter._healthy is True
        assert adapter._circuit_open is False
        assert adapter._failure_count == 0

    def test_record_failure_increments_count(self, adapter):
        """Recording failure increments count."""
        adapter._record_failure(RuntimeError("test"), "test_op")
        assert adapter._failure_count == 1
        assert adapter._last_error is not None
        assert adapter._last_failure_time is not None

    def test_circuit_opens_after_max_failures(self, adapter):
        """Circuit should open after MAX_FAILURES."""
        for i in range(adapter.MAX_FAILURES):
            adapter._record_failure(RuntimeError(f"fail {i}"), "test")

        assert adapter._circuit_open is True
        assert adapter._healthy is False

    def test_circuit_blocks_operations(self, adapter):
        """Open circuit should block operations."""
        adapter._circuit_open = True
        adapter._last_failure_time = time.time()

        assert adapter._check_circuit() is False

    def test_circuit_recovery_after_timeout(self, adapter):
        """Circuit should allow recovery after timeout."""
        adapter._circuit_open = True
        # Set failure time to older than recovery timeout
        adapter._last_failure_time = time.time() - adapter.RECOVERY_TIMEOUT - 10

        assert adapter._check_circuit() is True

    def test_record_success_resets_circuit(self, adapter):
        """Success should reset circuit breaker."""
        adapter._failure_count = 2
        adapter._circuit_open = True
        adapter._healthy = False

        adapter._record_success()

        assert adapter._failure_count == 0
        assert adapter._circuit_open is False
        assert adapter._healthy is True


class TestDeadLoopProtection:
    """Tests for dead loop protection."""

    def test_recursive_retrieval_blocked(self, adapter):
        """Recursive retrieval should be blocked."""
        adapter._retrieval_in_progress = True

        should_skip, reason = adapter._check_dead_loop()

        assert should_skip is True
        assert "Recursive retrieval" in reason

    def test_min_interval_enforced(self, adapter):
        """Minimum interval between retrievals should be enforced."""
        adapter._retrieval_in_progress = False
        adapter._last_retrieval_time = time.time() - 2  # 2 seconds ago < MIN_RETRIEVAL_INTERVAL (5s)

        should_skip, reason = adapter._check_dead_loop()

        assert should_skip is True
        assert "Too soon" in reason

    def test_max_retrievals_per_minute(self, adapter):
        """Max retrievals per minute should be enforced."""
        adapter._retrieval_in_progress = False
        adapter._last_retrieval_time = 0  # Long ago
        # Add many retrieval times
        now = time.time()
        adapter._retrieval_times = [now - i * 5 for i in range(adapter.MAX_RETRIEVALS_PER_MINUTE)]

        should_skip, reason = adapter._check_dead_loop()

        assert should_skip is True
        assert "Too many retrievals" in reason
        assert adapter._circuit_open is True

    def test_retrieval_allowed_when_conditions_ok(self, adapter):
        """Retrieval should be allowed when conditions are OK."""
        adapter._retrieval_in_progress = False
        adapter._last_retrieval_time = time.time() - 10  # 10 seconds ago > MIN_RETRIEVAL_INTERVAL
        adapter._retrieval_times = []  # No recent retrievals

        should_skip, reason = adapter._check_dead_loop()

        assert should_skip is False
        assert reason == ""

    def test_begin_end_retrieval(self, adapter):
        """Begin and end retrieval should update state."""
        adapter._begin_retrieval()
        assert adapter._retrieval_in_progress is True
        assert len(adapter._retrieval_times) == 1

        adapter._end_retrieval()
        assert adapter._retrieval_in_progress is False


class TestStatus:
    """Tests for adapter status."""

    def test_get_status_returns_state(self, adapter):
        """get_status should return current state."""
        adapter._failure_count = 2
        adapter._last_error = "test error"

        status = adapter.get_status()

        assert status["healthy"] is True
        assert status["started"] is False
        assert status["circuit_open"] is False
        assert status["failure_count"] == 2
        assert status["last_error"] == "test error"


class TestFileOperations:
    """Tests for file-based operations."""

    def test_read_soul_exists(self, adapter, workspace):
        """read_soul should return content when file exists."""
        soul_file = workspace / "SOUL.md"
        soul_file.write_text("I am a helpful assistant", encoding="utf-8")

        content = adapter.read_soul()

        assert content == "I am a helpful assistant"

    def test_read_soul_missing(self, adapter):
        """read_soul should return empty string when file missing."""
        content = adapter.read_soul()
        assert content == ""

    def test_write_soul(self, adapter, workspace):
        """write_soul should write to file."""
        adapter.write_soul("New personality")

        soul_file = workspace / "SOUL.md"
        assert soul_file.exists()
        assert soul_file.read_text(encoding="utf-8") == "New personality"

    def test_read_user_exists(self, adapter, workspace):
        """read_user should return content when file exists."""
        user_file = workspace / "USER.md"
        user_file.write_text("User preferences", encoding="utf-8")

        content = adapter.read_user()
        assert content == "User preferences"

    def test_write_user(self, adapter, workspace):
        """write_user should write to file."""
        adapter.write_user("User info")

        user_file = workspace / "USER.md"
        assert user_file.exists()
        assert user_file.read_text(encoding="utf-8") == "User info"

    def test_append_history(self, adapter, workspace):
        """append_history should write to history.jsonl."""
        cursor = adapter.append_history("Test history entry")

        history_file = workspace / "memory" / "history.jsonl"
        assert history_file.exists()

        content = history_file.read_text(encoding="utf-8")
        assert "Test history entry" in content
        assert cursor == 1

    def test_append_history_incrementing_cursor(self, adapter, workspace):
        """Cursor should increment for each entry."""
        cursor1 = adapter.append_history("Entry 1")
        cursor2 = adapter.append_history("Entry 2")

        assert cursor1 == 1
        assert cursor2 == 2


class TestMessageFormatting:
    """Tests for message format conversion."""

    def test_convert_timestamp_iso_format(self, adapter):
        """ISO timestamp should be converted correctly."""
        # This tests the internal convert_timestamp logic
        messages = [
            {
                "role": "user",
                "content": "Hello",
                "timestamp": "2026-04-10T00:23:59.406550",
            }
        ]

        # Run async method
        result = asyncio.run(adapter._format_messages_for_reme(messages))

        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "Hello"
        assert result[0]["time_created"] == "2026-04-10 00:23:59"

    def test_filter_system_messages(self, adapter):
        """System messages should be filtered out."""
        messages = [
            {"role": "system", "content": "You are a bot"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]

        result = asyncio.run(adapter._format_messages_for_reme(messages))

        assert len(result) == 2
        assert result[0]["role"] == "user"
        assert result[1]["role"] == "assistant"

    def test_handle_multimodal_content(self, adapter):
        """Multimodal content should be extracted."""
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Look at this"},
                    {"type": "image_url", "image_url": {"url": "http://image"}},
                ],
            }
        ]

        result = asyncio.run(adapter._format_messages_for_reme(messages))

        assert len(result) == 1
        assert result[0]["content"] == "Look at this"

    def test_empty_content_filtered(self, adapter):
        """Empty content messages should be filtered."""
        messages = [
            {"role": "user", "content": ""},
            {"role": "assistant", "content": "Response"},
        ]

        result = asyncio.run(adapter._format_messages_for_reme(messages))

        assert len(result) == 1
        assert result[0]["role"] == "assistant"


class TestTokenEstimation:
    """Tests for token estimation."""

    def test_estimate_message_tokens(self, adapter):
        """Token estimation should be reasonable."""
        msg = {"content": "Hello world this is a test message"}

        tokens = adapter._estimate_message_tokens(msg)

        # Should be approximately chars/2 + overhead
        expected = len(msg["content"]) // 2 + 20
        assert tokens == expected

    def test_estimate_block_tokens(self, adapter):
        """Block token estimation should sum messages."""
        block = [
            {"content": "Short message"},
            {"content": "A longer message with more content"},
        ]

        block_tokens = adapter._estimate_block_tokens(block)
        msg1_tokens = adapter._estimate_message_tokens(block[0])
        msg2_tokens = adapter._estimate_message_tokens(block[1])

        assert block_tokens == msg1_tokens + msg2_tokens


class TestEnsureStarted:
    """Tests for start validation."""

    def test_ensure_started_raises_when_not_started(self, adapter):
        """_ensure_started should raise when not started."""
        with pytest.raises(RuntimeError, match="not started"):
            adapter._ensure_started()

    def test_ensure_started_passes_when_started(self, adapter):
        """_ensure_started should pass when started."""
        adapter._started = True
        adapter._reme = MagicMock()

        # Should not raise
        adapter._ensure_started()


class TestCircuitIntegration:
    """Integration tests for circuit breaker with operations."""

    @pytest.mark.asyncio
    async def test_retrieve_memory_blocked_by_circuit(self, adapter):
        """retrieve_memory should return empty when circuit is open."""
        adapter._started = True
        adapter._reme = MagicMock()
        adapter._circuit_open = True
        adapter._last_failure_time = time.time()

        result = await adapter.retrieve_memory("test query")

        assert result == ""

    @pytest.mark.asyncio
    async def test_add_memory_blocked_by_circuit(self, adapter):
        """add_memory should return None when circuit is open."""
        adapter._started = True
        adapter._reme = MagicMock()
        adapter._circuit_open = True
        adapter._last_failure_time = time.time()

        result = await adapter.add_memory("test content")

        assert result is None

    @pytest.mark.asyncio
    async def test_list_memories_blocked_by_circuit(self, adapter):
        """list_memories should return empty list when circuit is open."""
        adapter._started = True
        adapter._reme = MagicMock()
        adapter._circuit_open = True
        adapter._last_failure_time = time.time()

        result = await adapter.list_memories()

        assert result == []