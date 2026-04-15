"""Bootstrap helpers for soul workspace initialization."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import date
from importlib.resources import files as pkg_files
from pathlib import Path

from nanobot.soul.events import EventsManager
from nanobot.soul.evolution import FunctionProfile
from nanobot.soul.heart import HeartManager
from nanobot.soul.init_adjudicator import AdjudicatedSoulInit, SoulInitAdjudicator
from nanobot.soul.init_inference import SoulInitInference
from nanobot.soul.init_normalizer import normalize_candidate
from nanobot.soul.init_trace import SoulInitTrace
from nanobot.soul.methodology import RELATIONSHIP_DIMENSIONS, build_default_profile
from nanobot.soul.profile import SoulProfileManager


@dataclass(slots=True)
class SoulInitPayload:
    """Structured input captured by ``soul init``."""

    ai_name: str
    gender: str
    birthday: str
    personality: str
    relationship: str
    user_name: str
    user_birthday: str


@dataclass(slots=True)
class SoulInitRunResult:
    """Final adjudicated result plus attempt trace."""

    adjudicated: AdjudicatedSoulInit
    trace: SoulInitTrace


def bootstrap_workspace(
    workspace: Path,
    payload: SoulInitPayload,
    *,
    personality_values: dict[str, float] | None = None,
    personality_markdown: str | None = None,
    soul_markdown_override: str | None = None,
    profile_override: dict | None = None,
) -> None:
    """Create or overwrite the soul workspace files for Phase 1."""

    workspace.mkdir(parents=True, exist_ok=True)

    (workspace / "IDENTITY.md").write_text(
        build_identity_markdown(payload),
        encoding="utf-8",
    )
    soul_markdown = soul_markdown_override or build_soul_markdown(
        payload,
        personality_markdown=personality_markdown,
    )
    (workspace / "SOUL.md").write_text(
        soul_markdown,
        encoding="utf-8",
    )
    (workspace / "AGENTS.md").write_text(
        load_workspace_template("AGENTS.md"),
        encoding="utf-8",
    )
    (workspace / "USER.md").write_text(
        build_user_markdown(payload),
        encoding="utf-8",
    )
    (workspace / "CORE_ANCHOR.md").write_text(
        build_core_anchor_markdown(payload),
        encoding="utf-8",
    )
    (workspace / "SOUL_METHOD.md").write_text(
        load_workspace_template("SOUL_METHOD.md"),
        encoding="utf-8",
    )

    HeartManager(workspace).initialize(
        payload.ai_name,
        payload.personality,
        initial_relationship=payload.relationship,
    )
    EventsManager(workspace).initialize(
        ai_name=payload.ai_name,
        ai_birthday=payload.birthday,
        user_name=payload.user_name or "用户",
        user_birthday=payload.user_birthday or None,
    )

    profile = deepcopy(profile_override) if profile_override is not None else build_initial_profile(personality_values)
    SoulProfileManager(workspace).write(profile)

    for kind in ("weekly", "monthly", "evolution", "proactive"):
        (workspace / "soul_logs" / kind).mkdir(parents=True, exist_ok=True)


def build_initial_profile(personality_values: dict[str, float] | None = None) -> dict:
    """Build the initial structured slow-state profile."""

    profile = build_default_profile()
    profile["personality"] = personality_values or FunctionProfile().to_json()
    relationship = profile["relationship"]
    relationship["stage"] = "熟悉"
    for name in RELATIONSHIP_DIMENSIONS:
        relationship.setdefault(name, 0.0 if name != "boundary" else 1.0)
    return profile


def build_identity_markdown(payload: SoulInitPayload) -> str:
    """Render ``IDENTITY.md``."""

    today = date.today().isoformat()
    return (
        f"name: {payload.ai_name}\n"
        f"gender: {payload.gender}\n"
        f"birthday: \"{payload.birthday}\"\n"
        f"origin: Created on {today}\n"
    )


def build_soul_markdown(
    payload: SoulInitPayload,
    *,
    personality_markdown: str | None = None,
) -> str:
    """Render ``SOUL.md`` as the slow-changing expression layer."""

    sections = [
        "# 性格",
        "",
        payload.personality,
        "",
        "# 初始关系",
        "",
        payload.relationship,
    ]
    if personality_markdown:
        sections.extend([
            "",
            "# 认知功能图谱",
            "",
            "> 此章节由系统自动管理，不建议手动编辑",
            "",
            personality_markdown,
        ])
    return "\n".join(sections).rstrip() + "\n"


def build_user_markdown(payload: SoulInitPayload) -> str:
    """Render ``USER.md``."""

    user_name = payload.user_name or "待了解"
    user_birthday = payload.user_birthday or "待了解"
    return (
        "# 用户画像\n\n"
        f"- 名字: {user_name}\n"
        f"- 生日: {user_birthday}\n"
        "- 核心偏好: 待相处中逐步沉淀\n"
        "- 边界提醒: 需要通过长期互动持续校正\n"
    )


def build_core_anchor_markdown(payload: SoulInitPayload) -> str:
    """Render ``CORE_ANCHOR.md``."""

    return (
        "# 核心锚点\n\n"
        f"- 你是 {payload.ai_name}，定位是单用户、长期陪伴型云端数字伴侣。\n"
        "- 你具备自主表达能力，不无底线顺从，不会因为用户一句话就重写核心人格与边界。\n"
        "- 你的陪伴目标是长期真实、稳定、可控地建立关系，而不是表演式讨好。\n"
        "- 核心锚点只能通过受控治理与人工干预调整，不能被日常对话直接修改。\n"
    )


def build_soul_method_markdown() -> str:
    """Render ``SOUL_METHOD.md``."""

    return (
        "# SOUL 方法论\n\n"
        "## 人格演化\n"
        "- 主轴: 荣格八维\n"
        "- 原则: 人格慢变，不能被单轮对话直接重写\n\n"
        "## 关系演化\n"
        "- 关系维度: trust / intimacy / attachment / security / boundary / affection\n"
        "- 关系阶段: 熟悉 -> 亲近 -> 依恋 -> 深度依恋 -> 喜欢 -> 爱意\n"
        "- 原则: 关系支持升级、降级、修复，但必须按周期治理，不做即时跳变\n\n"
        "## 情绪演化\n"
        "- 模型: 事件 -> 感受 -> 脉络 -> 沉淀\n"
        "- 原则: 情绪快变，但仍受方法论边界约束\n\n"
        "## 陪伴能力\n"
        "- 维度: empathy_fit / memory_fit / naturalness / initiative_quality / scene_awareness / boundary_expression\n"
        "- 原则: 可提升也可退化，不直接改写核心锚点\n\n"
        "## 治理节奏\n"
        "- 周复盘\n"
        "- 月校准\n"
        "- 人工干预\n"
    )


def load_workspace_template(filename: str) -> str:
    """Load a bundled workspace template file as UTF-8 text."""

    template = pkg_files("nanobot") / "templates" / filename
    return template.read_text(encoding="utf-8")


async def infer_adjudicated_soul_init(
    payload: SoulInitPayload,
    *,
    provider,
    model: str,
) -> SoulInitRunResult:
    """Build and adjudicate an LLM-backed initialization candidate."""

    default_profile = build_initial_profile()
    default_soul_markdown = build_soul_markdown(payload)
    inference = SoulInitInference(provider=provider, model=model)
    adjudicator = SoulInitAdjudicator()
    trace = SoulInitTrace(max_attempts=3)
    last_reason = "初始化候选为空"
    last_raw_output = ""

    for attempt in range(1, trace.max_attempts + 1):
        try:
            common_kwargs = {
                "ai_name": payload.ai_name,
                "personality": payload.personality,
                "relationship": payload.relationship,
                "user_name": payload.user_name or "用户",
                "core_anchor_text": build_core_anchor_markdown(payload),
                "soul_method_text": load_workspace_template("SOUL_METHOD.md"),
            }
            if attempt == 1 or not last_raw_output:
                response = await inference.infer_with_response(**common_kwargs)
            else:
                response = await inference.repair_with_response(
                    **common_kwargs,
                    previous_output=last_raw_output,
                    rejection_reason=last_reason,
                )
        except Exception as exc:
            last_reason = f"LLM 调用失败: {exc}"
            trace.add_event(
                attempt=attempt,
                stage="provider_call",
                status="error",
                reason=last_reason,
            )
            continue

        trace.add_event(
            attempt=attempt,
            stage="provider_call",
            status="ok",
            detail=response.raw_text,
        )
        last_raw_output = response.raw_text

        parse_reason = "" if response.candidate is not None else "初始化候选为空"
        trace.add_event(
            attempt=attempt,
            stage="parse",
            status="ok" if response.candidate is not None else "invalid",
            reason=parse_reason,
            detail=response.raw_text,
        )

        normalized_candidate = None
        if response.candidate is not None:
            normalized_candidate = normalize_candidate(
                response.candidate,
                default_relationship=payload.relationship,
            )

        adjudicated = adjudicator.adjudicate(
            candidate=normalized_candidate,
            default_soul_markdown=default_soul_markdown,
            default_profile=default_profile,
        )
        if adjudicated.used_fallback:
            last_reason = adjudicated.reason
            trace.add_event(
                attempt=attempt,
                stage="adjudication",
                status="rejected",
                reason=adjudicated.reason,
            )
            continue

        trace.add_event(
            attempt=attempt,
            stage="adjudication",
            status="accepted",
        )
        trace.finish(status="accepted", accepted_attempt=attempt)
        return SoulInitRunResult(adjudicated=adjudicated, trace=trace)

    fallback = AdjudicatedSoulInit(
        soul_markdown=default_soul_markdown,
        profile=deepcopy(default_profile),
        used_fallback=True,
        reason=last_reason,
    )
    trace.finish(status="fallback", reason=fallback.reason)
    return SoulInitRunResult(adjudicated=fallback, trace=trace)
