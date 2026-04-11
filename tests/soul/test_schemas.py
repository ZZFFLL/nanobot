"""Tests for HEART.md JSON Schema and validation."""
import pytest
from nanobot.soul.schemas import HEART_SCHEMA, validate_heart, HEART_FIELDS


class TestHeartSchema:

    def test_schema_has_all_required_fields(self):
        required = HEART_SCHEMA["required"]
        for field in HEART_FIELDS:
            assert field in required, f"{field} missing from required"

    def test_valid_minimal_data_passes(self):
        data = {
            "当前情绪": "平静",
            "情绪强度": "中",
            "关系状态": "刚刚认识",
            "性格表现": "温柔",
            "情感脉络": [],
            "情绪趋势": "平稳",
            "当前渴望": "想聊天",
        }
        result = validate_heart(data)
        assert result is not None
        assert result["情绪强度"] == "中"

    def test_missing_required_field_fails(self):
        data = {
            "当前情绪": "平静",
            # missing other fields
        }
        with pytest.raises(Exception):
            validate_heart(data)

    def test_intensity_must_be_enum(self):
        data = {
            "当前情绪": "平静",
            "情绪强度": "超高",  # invalid
            "关系状态": "刚刚认识",
            "性格表现": "温柔",
            "情感脉络": [],
            "情绪趋势": "平稳",
            "当前渴望": "想聊天",
        }
        with pytest.raises(Exception):
            validate_heart(data)

    def test_arcs_max_8(self):
        arcs = [{"时间": f"{i}小时前", "事件": f"事件{i}", "影响": f"影响{i}"} for i in range(10)]
        data = {
            "当前情绪": "平静",
            "情绪强度": "中",
            "关系状态": "刚刚认识",
            "性格表现": "温柔",
            "情感脉络": arcs,  # 10 > 8
            "情绪趋势": "平稳",
            "当前渴望": "想聊天",
        }
        with pytest.raises(Exception):
            validate_heart(data)

    def test_arcs_valid_within_limit(self):
        arcs = [{"时间": "1小时前", "事件": "测试", "影响": "测试"} for _ in range(5)]
        data = {
            "当前情绪": "平静",
            "情绪强度": "中",
            "关系状态": "刚刚认识",
            "性格表现": "温柔",
            "情感脉络": arcs,
            "情绪趋势": "平稳",
            "当前渴望": "想聊天",
        }
        result = validate_heart(data)
        assert len(result["情感脉络"]) == 5

    def test_extra_field_rejected(self):
        data = {
            "当前情绪": "平静",
            "情绪强度": "中",
            "关系状态": "刚刚认识",
            "性格表现": "温柔",
            "情感脉络": [],
            "情绪趋势": "平稳",
            "当前渴望": "想聊天",
            "额外字段": "不该存在",
        }
        with pytest.raises(Exception):
            validate_heart(data)

    def test_arc_missing_required_subfield(self):
        data = {
            "当前情绪": "平静",
            "情绪强度": "中",
            "关系状态": "刚刚认识",
            "性格表现": "温柔",
            "情感脉络": [{"时间": "1小时前", "事件": "测试"}],  # missing "影响"
            "情绪趋势": "平稳",
            "当前渴望": "想聊天",
        }
        with pytest.raises(Exception):
            validate_heart(data)
