"""LLM-backed initialization inference for soul bootstrap."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re

import json_repair


INIT_SOUL_PROMPT = (
    "你是数字伴侣初始化评估器。"
    "你必须严格根据给定的核心锚点和 SOUL 方法论，为一个新的单用户数字伴侣生成初始化候选。"
    "你不能创造新的方法论，也不能越过关系边界。"
    "你必须只输出严格 JSON，不要 markdown 代码块，不要解释。"
)

REPAIR_SOUL_PROMPT = (
    "你是数字伴侣初始化修复器。"
    "你会收到上一轮失败原因和上一轮无效候选。"
    "你的任务是保留原始语义，但把结果修复为严格合法的初始化 JSON。"
    "不允许继续输出非法结构，不允许输出解释。"
)

STRICT_SCHEMA_TEXT = (
    "输出格式必须严格是："
    '{"soul_markdown":"","profile":{"personality":{"Fi":0.00,"Fe":0.00,"Ti":0.00,"Te":0.00,"Si":0.00,"Se":0.00,"Ni":0.00,"Ne":0.00},"relationship":{"stage":"熟悉","trust":0.00,"intimacy":0.00,"attachment":0.00,"security":0.00,"boundary":0.00,"affection":0.00},"companionship":{"empathy_fit":0.00,"memory_fit":0.00,"naturalness":0.00,"initiative_quality":0.00,"scene_awareness":0.00,"boundary_expression":0.00}}}。'
    "其中 soul_markdown 必须是 markdown 字符串，且只能包含这两个一级标题，顺序固定：# 性格、# 初始关系。"
    "不要输出 # 核心锚点、# SOUL 方法论、或任何其他一级标题。"
    "personality 必须是荣格八维 8 个字段，值必须是 0.0 到 1.0 的小数。"
    "relationship 与 companionship 必须是扁平对象，不允许 dimensions 嵌套。"
    "所有数值都必须是 0.0 到 1.0 的小数，不允许 0-100 百分制。"
    "如果你看到 MBTI/archetype/traits/cognitive_stack 等替代字段，必须把它们转译为荣格八维数值。"
)


@dataclass(slots=True)
class SoulInitCandidate:
    """Candidate soul initialization payload proposed by the LLM."""

    soul_markdown: str
    profile: dict


@dataclass(slots=True)
class SoulInitInferenceResponse:
    """Raw provider output plus parsed candidate."""

    raw_text: str
    candidate: SoulInitCandidate | None


def parse_soul_init_candidate(text: str) -> SoulInitCandidate | None:
    """Parse a candidate from raw LLM output."""

    if not text:
        return None

    payload = _extract_json_payload(text)
    if payload is None:
        return None

    soul_markdown = payload.get("soul_markdown")
    profile = payload.get("profile")
    if not isinstance(soul_markdown, str) or not isinstance(profile, dict):
        return None
    return SoulInitCandidate(
        soul_markdown=soul_markdown.strip(),
        profile=profile,
    )


def _extract_json_payload(text: str) -> dict | None:
    candidate = text.strip()
    if not candidate.startswith("{"):
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", candidate, re.DOTALL)
        if match:
            candidate = match.group(1).strip()

    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        try:
            payload = json_repair.loads(candidate)
        except Exception:
            start = candidate.find("{")
            end = candidate.rfind("}")
            if start < 0 or end <= start:
                return None
            fragment = candidate[start : end + 1]
            try:
                payload = json.loads(fragment)
            except json.JSONDecodeError:
                try:
                    payload = json_repair.loads(fragment)
                except Exception:
                    return None

    return payload if isinstance(payload, dict) else None


class SoulInitInference:
    """Call the configured provider to build an initialization candidate."""

    def __init__(self, provider, model: str) -> None:
        self.provider = provider
        self.model = model

    async def infer(
        self,
        *,
        ai_name: str,
        personality: str,
        relationship: str,
        user_name: str,
        core_anchor_text: str,
        soul_method_text: str,
    ) -> SoulInitCandidate | None:
        response = await self.infer_with_response(
            ai_name=ai_name,
            personality=personality,
            relationship=relationship,
            user_name=user_name,
            core_anchor_text=core_anchor_text,
            soul_method_text=soul_method_text,
        )
        return response.candidate

    async def infer_with_response(
        self,
        *,
        ai_name: str,
        personality: str,
        relationship: str,
        user_name: str,
        core_anchor_text: str,
        soul_method_text: str,
    ) -> SoulInitInferenceResponse:
        response = await self.provider.chat_with_retry(
            model=self.model,
            messages=self._build_init_messages(
                ai_name=ai_name,
                personality=personality,
                relationship=relationship,
                user_name=user_name,
                core_anchor_text=core_anchor_text,
                soul_method_text=soul_method_text,
            ),
        )
        raw_text = (response.content or "").strip()
        return SoulInitInferenceResponse(
            raw_text=raw_text,
            candidate=parse_soul_init_candidate(raw_text),
        )

    async def repair_with_response(
        self,
        *,
        ai_name: str,
        personality: str,
        relationship: str,
        user_name: str,
        core_anchor_text: str,
        soul_method_text: str,
        previous_output: str,
        rejection_reason: str,
    ) -> SoulInitInferenceResponse:
        response = await self.provider.chat_with_retry(
            model=self.model,
            messages=self._build_repair_messages(
                ai_name=ai_name,
                personality=personality,
                relationship=relationship,
                user_name=user_name,
                core_anchor_text=core_anchor_text,
                soul_method_text=soul_method_text,
                previous_output=previous_output,
                rejection_reason=rejection_reason,
            ),
        )
        raw_text = (response.content or "").strip()
        return SoulInitInferenceResponse(
            raw_text=raw_text,
            candidate=parse_soul_init_candidate(raw_text),
        )

    def _build_init_messages(
        self,
        *,
        ai_name: str,
        personality: str,
        relationship: str,
        user_name: str,
        core_anchor_text: str,
        soul_method_text: str,
    ) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": INIT_SOUL_PROMPT},
            {
                "role": "user",
                "content": (
                    f"## 数字伴侣名字\n{ai_name}\n\n"
                    f"## 初始性格描述\n{personality}\n\n"
                    f"## 初始关系描述\n{relationship}\n\n"
                    f"## 用户名字\n{user_name or '用户'}\n\n"
                    f"## 核心锚点\n{core_anchor_text}\n\n"
                    f"## SOUL 方法论\n{soul_method_text}\n\n"
                    f"{STRICT_SCHEMA_TEXT}\n\n"
                    "额外要求：relationship.stage 只能是“熟悉”；boundary 与 boundary_expression 必须偏高；不要输出解释性文字。"
                ),
            },
        ]

    def _build_repair_messages(
        self,
        *,
        ai_name: str,
        personality: str,
        relationship: str,
        user_name: str,
        core_anchor_text: str,
        soul_method_text: str,
        previous_output: str,
        rejection_reason: str,
    ) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": REPAIR_SOUL_PROMPT},
            {
                "role": "user",
                "content": (
                    f"## 数字伴侣名字\n{ai_name}\n\n"
                    f"## 初始性格描述\n{personality}\n\n"
                    f"## 初始关系描述\n{relationship}\n\n"
                    f"## 用户名字\n{user_name or '用户'}\n\n"
                    f"## 核心锚点\n{core_anchor_text}\n\n"
                    f"## SOUL 方法论\n{soul_method_text}\n\n"
                    f"{STRICT_SCHEMA_TEXT}\n\n"
                    f"## 上一轮失败原因\n{rejection_reason}\n\n"
                    "## 上一轮无效候选\n"
                    f"{previous_output}\n\n"
                    "请只输出修复后的严格 JSON。优先修复标题结构、字段结构、数值范围和方法论映射。"
                ),
            },
        ]
