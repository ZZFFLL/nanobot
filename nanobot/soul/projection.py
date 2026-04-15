"""LLM-backed projection from structured SOUL_PROFILE to natural-language SOUL.md."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from nanobot.soul.logs import SoulLogWriter
from nanobot.soul.methodology import render_soul_method_markdown
from nanobot.soul.profile import SoulProfileManager

PROJECTION_PROMPT = (
    "你是数字伴侣的慢状态画像投影器。"
    "你的任务是把结构化的 SOUL_PROFILE 投影成纯自然语言的 SOUL.md。"
    "你必须严格遵守 CORE_ANCHOR 和 SOUL 方法论，但不能把它们原文抄进结果。"
    "你只能输出 markdown，且只能包含两个一级标题，顺序固定：# 性格、# 初始关系。"
    "不要输出 JSON、字段名、量化指标、方法论说明或治理说明。"
)

REPAIR_PROMPT = (
    "你是数字伴侣的慢状态画像修复器。"
    "上一轮 SOUL.md 候选不合法。"
    "请保留合法语义，修复结构和表达，只输出合法 markdown。"
)

_ALLOWED_HEADINGS = ("# 性格", "# 初始关系")
_FORBIDDEN_TEXT = (
    "# 核心锚点",
    "# SOUL 方法论",
    "```",
)
_FORBIDDEN_STRUCTURED_PATTERNS = (
    r'"(?:Fi|Fe|Ti|Te|Si|Se|Ni|Ne)"\s*:',
    r'"(?:trust|intimacy|attachment|security|boundary|affection)"\s*:',
    r'"(?:empathy_fit|memory_fit|naturalness|initiative_quality|scene_awareness|boundary_expression)"\s*:',
    r"\b(?:Fi|Fe|Ti|Te|Si|Se|Ni|Ne)\s*[:=]",
    r"\b(?:trust|intimacy|attachment|security|boundary|affection)\s*[:=]",
    r"\b(?:empathy_fit|memory_fit|naturalness|initiative_quality|scene_awareness|boundary_expression)\s*[:=]",
)


class SoulProjectionError(RuntimeError):
    """Raised when SOUL.md projection fails validation."""


async def project_soul_from_profile(
    workspace: Path,
    *,
    provider,
    model: str,
    profile_override: dict | None = None,
    max_attempts: int = 2,
    trigger: str = "runtime",
) -> str:
    """Project ``SOUL_PROFILE.md`` into natural-language ``SOUL.md`` via LLM."""

    soul_file = workspace / "SOUL.md"
    current_soul_text = soul_file.read_text(encoding="utf-8") if soul_file.exists() else ""
    profile = profile_override if profile_override is not None else SoulProfileManager(workspace).read()
    profile_text = json.dumps(profile, ensure_ascii=False, indent=2)
    core_anchor_text = _read_optional_text(workspace / "CORE_ANCHOR.md")
    soul_method_text = _read_optional_text(workspace / "SOUL_METHOD.md") or render_soul_method_markdown()
    last_error = "SOUL 投影候选为空"
    last_output = ""
    trace_records: list[dict] = []
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")

    for attempt in range(1, max_attempts + 1):
        messages = (
            _build_projection_messages(
                profile_text=profile_text,
                current_soul_text=current_soul_text,
                core_anchor_text=core_anchor_text,
                soul_method_text=soul_method_text,
            )
            if attempt == 1 or not last_output
            else _build_repair_messages(
                profile_text=profile_text,
                current_soul_text=current_soul_text,
                core_anchor_text=core_anchor_text,
                soul_method_text=soul_method_text,
                previous_output=last_output,
                rejection_reason=last_error,
            )
        )
        try:
            response = await provider.chat_with_retry(model=model, messages=messages)
        except Exception as exc:
            last_error = f"LLM 调用失败: {exc}"
            trace_records.append(_trace_record(
                attempt=attempt,
                max_attempts=max_attempts,
                stage="provider_call",
                status="error",
                model=model,
                trigger=trigger,
                reason=last_error,
            ))
            continue

        candidate = (response.content or "").strip()
        trace_records.append(_trace_record(
            attempt=attempt,
            max_attempts=max_attempts,
            stage="provider_call",
            status="ok",
            model=model,
            trigger=trigger,
            detail=candidate,
        ))
        error = validate_soul_markdown(candidate)
        if not error:
            normalized = candidate.rstrip() + "\n"
            soul_file.write_text(normalized, encoding="utf-8")
            trace_records.append(_trace_record(
                attempt=attempt,
                max_attempts=max_attempts,
                stage="validation",
                status="accepted",
                model=model,
                trigger=trigger,
            ))
            trace_records.append(_trace_record(
                attempt=attempt,
                max_attempts=max_attempts,
                stage="write",
                status="ok",
                model=model,
                trigger=trigger,
                detail=normalized,
            ))
            _write_projection_logs(
                workspace,
                stamp=stamp,
                trace_records=trace_records,
                audit_payload={
                    "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
                    "trigger": trigger,
                    "model": model,
                    "final_status": "accepted",
                    "final_reason": "",
                    "accepted_attempt": attempt,
                    "attempts": len({record["attempt"] for record in trace_records}),
                    "profile_stage": profile.get("relationship", {}).get("stage", ""),
                    "result": {
                        "soul_markdown": normalized,
                        "profile": profile,
                    },
                },
            )
            return normalized
        trace_records.append(_trace_record(
            attempt=attempt,
            max_attempts=max_attempts,
            stage="validation",
            status="rejected",
            model=model,
            trigger=trigger,
            reason=error,
            detail=candidate,
        ))
        last_output = candidate
        last_error = error

    _write_projection_logs(
        workspace,
        stamp=stamp,
        trace_records=trace_records,
        audit_payload={
            "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
            "trigger": trigger,
            "model": model,
            "final_status": "failed",
            "final_reason": last_error,
            "accepted_attempt": None,
            "attempts": len({record["attempt"] for record in trace_records}),
            "profile_stage": profile.get("relationship", {}).get("stage", ""),
            "result": {
                "soul_markdown": current_soul_text,
                "profile": profile,
            },
            "last_candidate": last_output,
        },
    )
    raise SoulProjectionError(last_error)


def validate_soul_markdown(text: str) -> str:
    """Validate projected SOUL markdown and return the rejection reason."""

    candidate = (text or "").strip()
    if not candidate:
        return "SOUL.md 投影候选非法: 内容为空"

    headings = re.findall(r"(?m)^# .+$", candidate)
    if headings != list(_ALLOWED_HEADINGS):
        return "SOUL.md 投影候选非法: 一级标题只能是 # 性格 和 # 初始关系，且顺序固定"

    if any(token in candidate for token in _FORBIDDEN_TEXT):
        return "SOUL.md 投影候选非法: 混入了治理或代码块内容"

    if "{" in candidate or "}" in candidate:
        return "SOUL.md 投影候选非法: 包含结构化对象内容"

    for pattern in _FORBIDDEN_STRUCTURED_PATTERNS:
        if re.search(pattern, candidate):
            return "SOUL.md 投影候选非法: 泄露了结构化字段"

    personality = _extract_section(candidate, "性格")
    relationship = _extract_section(candidate, "初始关系")
    if not personality or not relationship:
        return "SOUL.md 投影候选非法: 章节内容不能为空"

    return ""


def _build_projection_messages(
    *,
    profile_text: str,
    current_soul_text: str,
    core_anchor_text: str,
    soul_method_text: str,
) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": PROJECTION_PROMPT},
        {
            "role": "user",
            "content": (
                f"## 当前结构化 SOUL_PROFILE\n{profile_text}\n\n"
                f"## 当前 SOUL.md\n{current_soul_text or '（暂无，需从头生成）'}\n\n"
                f"## CORE_ANCHOR\n{core_anchor_text or '（暂无）'}\n\n"
                f"## SOUL 方法论\n{soul_method_text}\n\n"
                "请输出新的 SOUL.md。要求：\n"
                "1. 只保留长期慢状态画像，不要写热状态情绪。\n"
                "2. 语气自然、像人物自我画像，不要列表化。\n"
                "3. 关系描述必须是方法论约束下的自然语言推断，不能直接抄字段值。\n"
                "4. 必须只输出两个一级标题：# 性格、# 初始关系。\n"
            ),
        },
    ]


def _build_repair_messages(
    *,
    profile_text: str,
    current_soul_text: str,
    core_anchor_text: str,
    soul_method_text: str,
    previous_output: str,
    rejection_reason: str,
) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": REPAIR_PROMPT},
        {
            "role": "user",
            "content": (
                f"## 当前结构化 SOUL_PROFILE\n{profile_text}\n\n"
                f"## 当前 SOUL.md\n{current_soul_text or '（暂无，需从头生成）'}\n\n"
                f"## CORE_ANCHOR\n{core_anchor_text or '（暂无）'}\n\n"
                f"## SOUL 方法论\n{soul_method_text}\n\n"
                f"## 上一轮失败原因\n{rejection_reason}\n\n"
                f"## 上一轮非法候选\n{previous_output or '（空）'}\n\n"
                "请只输出修复后的 SOUL.md markdown。"
            ),
        },
    ]


def _extract_section(text: str, heading: str) -> str:
    pattern = re.compile(rf"(?ms)^# {re.escape(heading)}\s*\n(.*?)(?=^# |\Z)")
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def _read_optional_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def _trace_record(
    *,
    attempt: int,
    max_attempts: int,
    stage: str,
    status: str,
    model: str,
    trigger: str,
    reason: str = "",
    detail: str = "",
) -> dict:
    return {
        "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
        "attempt": attempt,
        "max_attempts": max_attempts,
        "stage": stage,
        "status": status,
        "reason": reason,
        "detail": detail,
        "model": model,
        "trigger": trigger,
    }


def _write_projection_logs(
    workspace: Path,
    *,
    stamp: str,
    trace_records: list[dict],
    audit_payload: dict,
) -> None:
    writer = SoulLogWriter(workspace)
    writer.write_projection_trace(stamp, trace_records)
    writer.write_projection_audit(stamp, audit_payload)
