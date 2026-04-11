"""Tests for HeartManager — HEART.md text read/write."""
import pytest
from pathlib import Path
from nanobot.soul.heart import HeartManager


@pytest.fixture
def workspace(tmp_path):
    return tmp_path


@pytest.fixture
def heart(workspace):
    return HeartManager(workspace)


class TestHeartManager:

    def test_init_creates_heart_file(self, heart, workspace):
        heart.initialize("小文", "刚刚被创造，对一切充满好奇")
        assert (workspace / "HEART.md").exists()

    def test_read_after_init(self, heart):
        heart.initialize("小文", "刚刚被创造，对一切充满好奇")
        text = heart.read_text()
        assert text is not None
        assert "## 当前情绪" in text
        assert "刚刚被创造" in text

    def test_write_valid_text(self, heart):
        heart.initialize("小文", "测试")
        new_markdown = (
            "## 当前情绪\n有点开心\n\n"
            "## 情绪强度\n中偏高\n\n"
            "## 关系状态\n开始产生好奇\n\n"
            "## 性格表现\n温柔但倔强\n\n"
            "## 情感脉络\n- 刚刚：用户说了句话 → 有点开心\n\n"
            "## 情绪趋势\n上升趋势\n\n"
            "## 当前渴望\n想继续聊天\n"
        )
        result = heart.write_text(new_markdown)
        assert result is True
        read_back = heart.read_text()
        assert "有点开心" in read_back
        assert "中偏高" in read_back

    def test_write_overwrites_content(self, heart):
        heart.initialize("小文", "测试")
        new_content = "## 当前情绪\n很开心\n\n## 情绪强度\n高\n"
        heart.write_text(new_content)
        assert "很开心" in heart.read_text()

        newer_content = "## 当前情绪\n平静\n\n## 情绪强度\n低\n"
        heart.write_text(newer_content)
        assert "平静" in heart.read_text()
        assert "很开心" not in heart.read_text()

    def test_file_not_found_returns_none(self, tmp_path):
        hm = HeartManager(tmp_path / "nonexistent")
        assert hm.read_text() is None

    def test_initialize_produces_all_sections(self, heart):
        heart.initialize("小文", "温柔且好奇")
        text = heart.read_text()
        assert "## 当前情绪" in text
        assert "## 情绪强度" in text
        assert "## 关系状态" in text
        assert "## 性格表现" in text
        assert "## 情感脉络" in text
        assert "## 情绪趋势" in text
        assert "## 当前渴望" in text
        assert "温柔且好奇" in text

    def test_read_identity_name(self, heart, workspace):
        identity_file = workspace / "IDENTITY.md"
        identity_file.write_text("name: 小文\ngender: 女\n", encoding="utf-8")
        name = heart.read_identity_name()
        assert name == "小文"

    def test_read_identity_name_missing_file(self, heart):
        name = heart.read_identity_name()
        assert name is None

    def test_write_text_returns_false_on_error(self, heart, workspace, monkeypatch):
        """write_text returns False on file system error."""
        heart.initialize("小文", "测试")
        # Make the heart_file attribute point to a non-existent dir so write fails
        heart.heart_file = workspace / "no_such_dir" / "HEART.md"
        result = heart.write_text("## 当前情绪\ntest\n")
        assert result is False
