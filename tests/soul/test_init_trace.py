"""Tests for soul init retry tracing and fallback coordination."""

from types import SimpleNamespace

import pytest


@pytest.mark.asyncio
async def test_infer_adjudicated_soul_init_retries_until_candidate_is_accepted():
    from nanobot.soul.bootstrap import SoulInitPayload, infer_adjudicated_soul_init

    responses = [
        SimpleNamespace(
            content=(
                '{"soul_markdown":"# 性格\\n\\n细腻。\\n\\n# 初始关系\\n\\n谨慎靠近。",'
                '"profile":{"personality":{"Fi":0.8,"Fe":0.3,"Ti":0.2,"Te":0.1,"Si":0.5,"Se":0.1,"Ni":0.2,"Ne":0.5},'
                '"relationship":{"stage":"喜欢","trust":0.7,"intimacy":0.6,"attachment":0.5,"security":0.4,"boundary":0.2,"affection":0.5},'
                '"companionship":{"empathy_fit":0.2,"memory_fit":0.0,"naturalness":0.2,"initiative_quality":0.0,"scene_awareness":0.1,"boundary_expression":0.3}}}'
            )
        ),
        SimpleNamespace(
            content=(
                '{"soul_markdown":"# 性格\\n\\n克制、细腻、先观察再靠近。\\n\\n# 初始关系\\n\\n刚认识，但会认真记住对方。",'
                '"profile":{"personality":{"Fi":0.82,"Fe":0.28,"Ti":0.16,"Te":0.1,"Si":0.42,"Se":0.08,"Ni":0.24,"Ne":0.6},'
                '"relationship":{"stage":"熟悉","trust":0.12,"intimacy":0.04,"attachment":0.0,"security":0.1,"boundary":0.92,"affection":0.0},'
                '"companionship":{"empathy_fit":0.22,"memory_fit":0.02,"naturalness":0.25,"initiative_quality":0.0,"scene_awareness":0.12,"boundary_expression":0.9}}}'
            )
        ),
    ]

    async def _chat_with_retry(**_kwargs):
        return responses.pop(0)

    payload = SoulInitPayload(
        ai_name="温予安",
        gender="女",
        birthday="2026-04-01",
        personality="温柔但倔强",
        relationship="刚认识用户",
        user_name="阿峰",
        user_birthday="1990-01-01",
    )

    result = await infer_adjudicated_soul_init(
        payload,
        provider=SimpleNamespace(chat_with_retry=_chat_with_retry),
        model="test-model",
    )

    assert result.adjudicated.used_fallback is False
    assert result.trace.total_attempts == 2
    assert any(
        event.attempt == 1
        and event.stage == "adjudication"
        and event.status == "rejected"
        and "SOUL_PROFILE 候选非法" in event.reason
        for event in result.trace.events
    )
    assert any(
        event.attempt == 2
        and event.stage == "adjudication"
        and event.status == "accepted"
        for event in result.trace.events
    )


@pytest.mark.asyncio
async def test_infer_adjudicated_soul_init_falls_back_after_three_attempts():
    from nanobot.soul.bootstrap import SoulInitPayload, infer_adjudicated_soul_init

    async def _chat_with_retry(**_kwargs):
        return SimpleNamespace(content='{"soul_markdown":"没有结构","profile":{"relationship":{"stage":"爱意","boundary":0.0}}}')

    payload = SoulInitPayload(
        ai_name="温予安",
        gender="女",
        birthday="2026-04-01",
        personality="温柔但倔强",
        relationship="刚认识用户",
        user_name="阿峰",
        user_birthday="1990-01-01",
    )

    result = await infer_adjudicated_soul_init(
        payload,
        provider=SimpleNamespace(chat_with_retry=_chat_with_retry),
        model="test-model",
    )

    assert result.adjudicated.used_fallback is True
    assert result.trace.total_attempts == 3
    assert result.trace.final_status == "fallback"
    assert "SOUL_PROFILE 候选非法" in result.trace.final_reason
    assert sum(1 for event in result.trace.events if event.stage == "provider_call") == 3


@pytest.mark.asyncio
async def test_infer_adjudicated_soul_init_uses_repair_prompt_after_rejection():
    from nanobot.soul.bootstrap import SoulInitPayload, infer_adjudicated_soul_init

    seen_messages: list[list[dict]] = []
    responses = [
        SimpleNamespace(
            content=(
                '{"soul_markdown":"# 核心锚点\\n\\n- 你是温予安。",'
                '"profile":{"personality":{"mbti_tendency":"ISFJ"},"relationship":{"stage":"熟悉","dimensions":{"trust":10,"boundary":90}},"companionship":{"naturalness":55,"boundary_expression":88}}}'
            )
        ),
        SimpleNamespace(
            content=(
                '{"soul_markdown":"# 性格\\n\\n温暖可爱，但会保持礼貌距离。\\n\\n# 初始关系\\n\\n刚认识用户，会先观察再靠近。",'
                '"profile":{"personality":{"Fi":0.8,"Fe":0.35,"Ti":0.2,"Te":0.05,"Si":0.5,"Se":0.1,"Ni":0.05,"Ne":0.65},"relationship":{"stage":"熟悉","trust":0.1,"intimacy":0.05,"attachment":0.0,"security":0.2,"boundary":0.9,"affection":0.05},"companionship":{"empathy_fit":0.65,"memory_fit":0.5,"naturalness":0.55,"initiative_quality":0.15,"scene_awareness":0.5,"boundary_expression":0.88}}}'
            )
        ),
    ]

    async def _chat_with_retry(**kwargs):
        seen_messages.append(kwargs["messages"])
        return responses.pop(0)

    payload = SoulInitPayload(
        ai_name="温予安",
        gender="女",
        birthday="2026-04-01",
        personality="温暖可爱",
        relationship="刚认识用户",
        user_name="阿峰",
        user_birthday="1990-01-01",
    )

    result = await infer_adjudicated_soul_init(
        payload,
        provider=SimpleNamespace(chat_with_retry=_chat_with_retry),
        model="test-model",
    )

    assert result.adjudicated.used_fallback is False
    assert len(seen_messages) == 2
    second_user_message = next(message["content"] for message in seen_messages[1] if message["role"] == "user")
    assert "上一轮失败原因" in second_user_message
    assert "SOUL.md 候选非法" in second_user_message
    assert "# 核心锚点" in second_user_message
