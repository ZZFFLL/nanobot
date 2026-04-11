"""Tests for MemoryPalaceBridge — mempalace integration layer."""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
from nanobot.soul.memory_config import MemoryPalaceBridge, _to_wing_slug


class TestWingSlug:

    def test_chinese_name_to_slug(self):
        # Chinese characters get transliterated; fallback to ai-wing
        slug = _to_wing_slug("温予安")
        assert slug == "ai-wing"  # NFKD transliteration strips all CJK

    def test_ascii_name_passes_through(self):
        assert _to_wing_slug("wenyuan") == "wenyuan"

    def test_mixed_name_keeps_ascii(self):
        slug = _to_wing_slug("ai-assistant")
        assert slug == "ai-assistant"

    def test_empty_falls_back(self):
        slug = _to_wing_slug("")
        assert slug == "ai-wing"


class TestMemoryPalaceBridge:

    def test_init_creates_bridge(self, tmp_path):
        bridge = MemoryPalaceBridge(workspace=tmp_path)
        assert bridge is not None

    def test_ai_wing_name_from_identity(self, tmp_path):
        (tmp_path / "IDENTITY.md").write_text("name: 小文\ngender: 女\n", encoding="utf-8")
        bridge = MemoryPalaceBridge(workspace=tmp_path)
        # Chinese name → slug (NFKD strips CJK → fallback to "ai-wing")
        assert bridge.ai_wing == "ai-wing"

    def test_ai_wing_default_without_identity(self, tmp_path):
        bridge = MemoryPalaceBridge(workspace=tmp_path)
        # "数字生命" → NFKD strips CJK → fallback "ai-wing"
        assert bridge.ai_wing == "ai-wing"

    def test_ai_wing_english_name(self, tmp_path):
        (tmp_path / "IDENTITY.md").write_text("name: wenyuan\ngender: female\n", encoding="utf-8")
        bridge = MemoryPalaceBridge(workspace=tmp_path)
        assert bridge.ai_wing == "wenyuan"

    def test_user_wing_default(self, tmp_path):
        bridge = MemoryPalaceBridge(workspace=tmp_path)
        assert bridge.user_wing == "user"

    def test_update_user_wing_name(self, tmp_path):
        bridge = MemoryPalaceBridge(workspace=tmp_path)
        bridge.update_user_wing("xiaoming")
        assert bridge.user_wing == "xiaoming"

    def test_update_user_wing_chinese_name(self, tmp_path):
        bridge = MemoryPalaceBridge(workspace=tmp_path)
        bridge.update_user_wing("小明")
        # Chinese → NFKD strips → fallback "ai-wing"
        assert bridge.user_wing == "ai-wing"

    def test_update_user_wing_ignores_empty(self, tmp_path):
        bridge = MemoryPalaceBridge(workspace=tmp_path)
        bridge.update_user_wing("xiaoming")
        bridge.update_user_wing("")
        assert bridge.user_wing == "xiaoming"

    def test_update_user_wing_ignores_same_name(self, tmp_path):
        bridge = MemoryPalaceBridge(workspace=tmp_path)
        bridge.update_user_wing("user")  # same as default
        assert bridge.user_wing == "user"

    @patch("nanobot.soul.memory_config.mempalace_available", True)
    async def test_add_drawer_success(self, tmp_path):
        with patch("nanobot.soul.memory_config.tool_add_drawer") as mock_add:
            mock_add.return_value = {"success": True, "drawer_id": "test_id"}
            bridge = MemoryPalaceBridge(workspace=tmp_path)
            result = await bridge.add_drawer(
                wing="ai-wing", room="daily",
                content="测试内容",
                metadata={"timestamp": "2026-04-10"},
            )
            assert result is True
            mock_add.assert_called_once()

    @patch("nanobot.soul.memory_config.mempalace_available", False)
    async def test_add_drawer_unavailable(self, tmp_path):
        bridge = MemoryPalaceBridge(workspace=tmp_path)
        result = await bridge.add_drawer(
            wing="ai-wing", room="daily",
            content="测试内容",
        )
        assert result is False

    @patch("nanobot.soul.memory_config.mempalace_available", True)
    async def test_add_drawer_failure(self, tmp_path):
        with patch("nanobot.soul.memory_config.tool_add_drawer") as mock_add:
            mock_add.return_value = {"success": False, "error": "validation error"}
            bridge = MemoryPalaceBridge(workspace=tmp_path)
            result = await bridge.add_drawer(
                wing="ai-wing", room="daily",
                content="测试内容",
            )
            assert result is False

    @patch("nanobot.soul.memory_config.mempalace_available", True)
    async def test_add_drawer_exception(self, tmp_path):
        with patch("nanobot.soul.memory_config.tool_add_drawer") as mock_add:
            mock_add.side_effect = Exception("connection error")
            bridge = MemoryPalaceBridge(workspace=tmp_path)
            result = await bridge.add_drawer(
                wing="ai-wing", room="daily",
                content="测试内容",
            )
            assert result is False

    @patch("nanobot.soul.memory_config.mempalace_available", True)
    async def test_search_returns_results(self, tmp_path):
        with patch("nanobot.soul.memory_config.search_memories") as mock_search:
            mock_search.return_value = {
                "results": [
                    {"text": "用户说很开心", "wing": "ai-wing", "room": "daily", "similarity": 0.9},
                ]
            }
            bridge = MemoryPalaceBridge(workspace=tmp_path)
            results = await bridge.search("开心", wing="ai-wing", n_results=3)
            assert len(results) == 1
            assert "开心" in results[0]["text"]

    @patch("nanobot.soul.memory_config.mempalace_available", False)
    async def test_search_unavailable_returns_empty(self, tmp_path):
        bridge = MemoryPalaceBridge(workspace=tmp_path)
        results = await bridge.search("测试", wing="ai-wing")
        assert results == []

    @patch("nanobot.soul.memory_config.mempalace_available", True)
    async def test_search_exception_returns_empty(self, tmp_path):
        with patch("nanobot.soul.memory_config.search_memories") as mock_search:
            mock_search.side_effect = Exception("db error")
            bridge = MemoryPalaceBridge(workspace=tmp_path)
            results = await bridge.search("测试", wing="ai-wing")
            assert results == []
