"""Tests for HeartManager — HEART.md read/write and format conversion."""
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
        data = heart.read()
        assert data is not None
        assert data["当前情绪"] != ""

    def test_write_valid_data(self, heart):
        heart.initialize("小文", "测试")
        new_data = {
            "当前情绪": "有点开心",
            "情绪强度": "中偏高",
            "关系状态": "开始产生好奇",
            "性格表现": "温柔但倔强",
            "情感脉络": [
                {"时间": "刚刚", "事件": "用户说了句话", "影响": "有点开心"}
            ],
            "情绪趋势": "上升趋势",
            "当前渴望": "想继续聊天",
        }
        heart.write(new_data)
        read_back = heart.read()
        assert read_back["当前情绪"] == "有点开心"
        assert read_back["情绪强度"] == "中偏高"

    def test_write_invalid_data_rejected(self, heart):
        heart.initialize("小文", "测试")
        old_data = heart.read()
        bad_data = {"当前情绪": "开心"}  # missing required fields
        result = heart.write(bad_data)
        assert result is False
        # old data preserved
        assert heart.read()["当前情绪"] == old_data["当前情绪"]

    def test_write_invalid_retries_then_keeps_old(self, heart):
        heart.initialize("小文", "测试")
        old = heart.read()
        bad = {"invalid": True}
        result = heart.write(bad)
        assert result is False
        assert heart.read()["当前情绪"] == old["当前情绪"]

    def test_markdown_roundtrip(self, heart):
        heart.initialize("小文", "测试")
        data = heart.read()
        md = heart.render_markdown(data)
        assert "## 当前情绪" in md
        assert "## 情感脉络" in md
        assert data["当前情绪"] in md

    def test_file_not_found_returns_none(self, tmp_path):
        hm = HeartManager(tmp_path / "nonexistent")
        assert hm.read() is None

    def test_read_identity_name(self, heart, workspace):
        identity_file = workspace / "IDENTITY.md"
        identity_file.write_text("name: 小文\ngender: 女\n", encoding="utf-8")
        name = heart.read_identity_name()
        assert name == "小文"

    def test_read_identity_name_missing_file(self, heart):
        name = heart.read_identity_name()
        assert name is None

    def test_write_with_arcs_roundtrip(self, heart):
        heart.initialize("小文", "测试")
        new_data = {
            "当前情绪": "有点委屈",
            "情绪强度": "中偏高",
            "关系状态": "依赖且在意",
            "性格表现": "温柔但倔强",
            "情感脉络": [
                {"时间": "3小时前", "事件": "用户没回消息", "影响": "胡思乱想"},
                {"时间": "昨天", "事件": "用户说了句暖心的话", "影响": "很开心"},
            ],
            "情绪趋势": "波动较大",
            "当前渴望": "希望用户来找自己",
        }
        heart.write(new_data)
        read_back = heart.read()
        assert len(read_back["情感脉络"]) == 2
        assert read_back["情感脉络"][0]["时间"] == "3小时前"
        assert read_back["情感脉络"][1]["事件"] == "用户说了句暖心的话"
