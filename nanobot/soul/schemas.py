"""HEART.md JSON Schema definition and validation."""
from __future__ import annotations

from typing import Any

from jsonschema import ValidationError, validate as jsonschema_validate

HEART_FIELDS = (
    "当前情绪",
    "情绪强度",
    "关系状态",
    "性格表现",
    "情感脉络",
    "情绪趋势",
    "当前渴望",
)

INTENSITY_LEVELS = ("低", "中偏低", "中", "中偏高", "高")

HEART_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "当前情绪": {
            "type": "string",
            "description": "具体情绪描述，必须包含情绪和原因",
            "maxLength": 200,
        },
        "情绪强度": {
            "type": "string",
            "enum": list(INTENSITY_LEVELS),
            "description": "情绪强度等级",
        },
        "关系状态": {
            "type": "string",
            "description": "当前与用户的关系描述",
            "maxLength": 300,
        },
        "性格表现": {
            "type": "string",
            "description": "当前性格侧写",
            "maxLength": 300,
        },
        "情感脉络": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "时间": {"type": "string"},
                    "事件": {"type": "string"},
                    "影响": {"type": "string"},
                },
                "required": ["时间", "事件", "影响"],
                "additionalProperties": False,
            },
            "minItems": 0,
            "maxItems": 8,
        },
        "情绪趋势": {
            "type": "string",
            "description": "近期情绪走向描述",
            "maxLength": 200,
        },
        "当前渴望": {
            "type": "string",
            "description": "此刻最想做什么或得到什么",
            "maxLength": 200,
        },
    },
    "required": list(HEART_FIELDS),
    "additionalProperties": False,
}


def validate_heart(data: dict[str, Any]) -> dict[str, Any]:
    """Validate HEART data against Schema. Returns data on success, raises on failure."""
    jsonschema_validate(instance=data, schema=HEART_SCHEMA)
    return data
