"""Tests for soul init inference protocol."""

from types import SimpleNamespace

import pytest

from nanobot.soul.init_inference import SoulInitCandidate, parse_soul_init_candidate


def test_parse_soul_init_candidate_from_code_fenced_json():
    text = """```json
{
  "soul_markdown": "# 性格\\n\\n温柔但克制\\n\\n# 初始关系\\n\\n刚刚认识",
  "profile": {
    "personality": {"Fi": 0.8, "Fe": 0.3, "Ti": 0.2, "Te": 0.1, "Si": 0.5, "Se": 0.1, "Ni": 0.2, "Ne": 0.5},
    "relationship": {"stage": "熟悉", "trust": 0.1, "intimacy": 0.0, "attachment": 0.0, "security": 0.1, "boundary": 0.9, "affection": 0.0},
    "companionship": {"empathy_fit": 0.2, "memory_fit": 0.0, "naturalness": 0.2, "initiative_quality": 0.0, "scene_awareness": 0.1, "boundary_expression": 0.9}
  }
}
```"""

    candidate = parse_soul_init_candidate(text)

    assert isinstance(candidate, SoulInitCandidate)
    assert "温柔但克制" in candidate.soul_markdown
    assert candidate.profile["relationship"]["stage"] == "熟悉"


def test_parse_soul_init_candidate_returns_none_on_invalid_payload():
    assert parse_soul_init_candidate("not json") is None


@pytest.mark.asyncio
async def test_inference_calls_provider_and_parses_response():
    from nanobot.soul.init_inference import SoulInitInference

    provider = SimpleNamespace(
        chat_with_retry=lambda **_kwargs: None,
    )

    async def _chat_with_retry(**_kwargs):
        return SimpleNamespace(
            content='{"soul_markdown":"# 性格\\n\\n细腻\\n\\n# 初始关系\\n\\n谨慎靠近","profile":{"personality":{"Fi":0.8,"Fe":0.3,"Ti":0.2,"Te":0.1,"Si":0.5,"Se":0.1,"Ni":0.2,"Ne":0.5},"relationship":{"stage":"熟悉","trust":0.1,"intimacy":0.0,"attachment":0.0,"security":0.1,"boundary":0.9,"affection":0.0},"companionship":{"empathy_fit":0.2,"memory_fit":0.0,"naturalness":0.2,"initiative_quality":0.0,"scene_awareness":0.1,"boundary_expression":0.9}}}'
        )

    provider.chat_with_retry = _chat_with_retry
    inference = SoulInitInference(provider=provider, model="test-model")

    candidate = await inference.infer(
        ai_name="温予安",
        personality="温柔但倔强",
        relationship="刚刚认识用户",
        user_name="阿峰",
        core_anchor_text="# 核心锚点\n- 不无底线顺从",
        soul_method_text="# SOUL 方法论\n- 主轴: 荣格八维",
    )

    assert isinstance(candidate, SoulInitCandidate)
    assert candidate.profile["companionship"]["naturalness"] == 0.2
