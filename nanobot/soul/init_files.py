"""Partial file initialization helpers for ``soul init``."""

from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import Path
from typing import Callable

from nanobot.soul.bootstrap import (
    SoulInitPayload,
    build_core_anchor_markdown,
    build_identity_markdown,
    build_initial_profile,
    build_soul_markdown,
    build_user_markdown,
    load_workspace_template,
)
from nanobot.soul.events import EventsManager
from nanobot.soul.heart import HeartManager, render_initial_heart_markdown
from nanobot.soul.profile import SoulProfileManager

ALLOWED_INIT_FILES = (
    "IDENTITY.md",
    "USER.md",
    "AGENTS.md",
    "CORE_ANCHOR.md",
    "SOUL_METHOD.md",
    "SOUL_GOVERNANCE.json",
    "SOUL.md",
    "SOUL_PROFILE.md",
    "HEART.md",
    "EVENTS.md",
)

INIT_FILE_ORDER = list(ALLOWED_INIT_FILES)
_SOUL_LLM_TARGETS = {"SOUL.md", "SOUL_PROFILE.md", "HEART.md"}

_PROMPT_LABELS = {
    "ai_name": "数字生命的名字",
    "gender": "性别",
    "birthday": "生日 (YYYY-MM-DD)",
    "personality": "初始性格描述",
    "relationship": "与用户的初始关系",
    "user_name": "用户的名字（可留空运行中学习）",
    "user_birthday": "用户的生日（可选，格式 YYYY-MM-DD）",
}

_PROMPT_DEFAULTS = {
    "ai_name": "小文",
    "gender": "女",
    "birthday": "2026-04-01",
    "personality": "温柔但倔强，嘴硬心软，容易吃醋",
    "relationship": "刚刚被创造，对用户充满好奇",
    "user_name": "",
    "user_birthday": "",
}


@dataclass(slots=True)
class FileInitAction:
    """One partial initialization result."""

    filename: str
    status: str


def normalize_only_files(files: list[str] | None) -> list[str]:
    """Validate, deduplicate, and sort requested partial-init filenames."""

    if not files:
        return []

    cleaned = []
    seen: set[str] = set()
    for item in files:
        name = item.strip()
        if not name or name in seen:
            continue
        seen.add(name)
        cleaned.append(name)

    unknown = [name for name in cleaned if name not in ALLOWED_INIT_FILES]
    if unknown:
        raise ValueError(f"不支持的初始化文件: {', '.join(unknown)}")

    return [name for name in INIT_FILE_ORDER if name in seen]


def targets_need_llm(targets: list[str]) -> bool:
    return any(target in _SOUL_LLM_TARGETS for target in targets)


def required_fields_for_targets(targets: list[str], *, use_llm: bool = False) -> set[str]:
    """Return the minimal set of payload fields required by the target files."""

    required: set[str] = set()
    for target in targets:
        if target == "IDENTITY.md":
            required.update({"ai_name", "gender", "birthday"})
        elif target == "USER.md":
            required.update({"user_name", "user_birthday"})
        elif target == "CORE_ANCHOR.md":
            required.add("ai_name")
        elif target == "SOUL.md":
            required.update({"personality", "relationship"})
        elif target == "HEART.md":
            required.update({"ai_name", "personality", "relationship"})
        elif target == "EVENTS.md":
            required.update({"ai_name", "birthday", "user_name", "user_birthday"})

    if use_llm:
        required.update({"ai_name", "personality", "relationship", "user_name"})
    return required


def collect_payload_for_targets(
    workspace: Path,
    *,
    required_fields: set[str],
    prompt_fn: Callable[[str, str], str],
) -> SoulInitPayload | None:
    """Build a payload from existing workspace state, prompting only for missing required fields."""

    if not required_fields:
        return None

    existing = read_existing_seed(workspace)
    values: dict[str, str] = {}
    for field, default in _PROMPT_DEFAULTS.items():
        existing_value = existing.get(field, "").strip()
        if field in required_fields and not existing_value:
            values[field] = prompt_fn(_PROMPT_LABELS[field], default)
        else:
            values[field] = existing_value or default

    return SoulInitPayload(**values)


def read_existing_seed(workspace: Path) -> dict[str, str]:
    """Extract reusable seed values from existing workspace files."""

    seed: dict[str, str] = {
        "ai_name": "",
        "gender": "",
        "birthday": "",
        "personality": "",
        "relationship": "",
        "user_name": "",
        "user_birthday": "",
    }

    identity = workspace / "IDENTITY.md"
    if identity.exists():
        text = identity.read_text(encoding="utf-8")
        seed["ai_name"] = _read_keyed_line(text, "name")
        seed["gender"] = _read_keyed_line(text, "gender")
        seed["birthday"] = _read_keyed_line(text, "birthday").strip('"')

    user = workspace / "USER.md"
    if user.exists():
        text = user.read_text(encoding="utf-8")
        seed["user_name"] = _read_bullet_value(text, "名字")
        seed["user_birthday"] = _read_bullet_value(text, "生日")
        if seed["user_name"] == "待了解":
            seed["user_name"] = ""
        if seed["user_birthday"] == "待了解":
            seed["user_birthday"] = ""

    soul = workspace / "SOUL.md"
    if soul.exists():
        text = soul.read_text(encoding="utf-8")
        seed["personality"] = _read_heading_section(text, "性格")
        seed["relationship"] = _read_heading_section(text, "初始关系")

    return seed


def write_selected_files(
    workspace: Path,
    *,
    targets: list[str],
    payload: SoulInitPayload | None,
    force: bool,
    soul_markdown_override: str | None = None,
    heart_markdown_override: str | None = None,
    profile_override: dict | None = None,
) -> list[FileInitAction]:
    """Write only the selected files, respecting skip/force semantics."""

    actions: list[FileInitAction] = []
    workspace.mkdir(parents=True, exist_ok=True)

    for filename in normalize_only_files(targets):
        target = workspace / filename
        existed = target.exists()
        if existed and not force:
            actions.append(FileInitAction(filename=filename, status="skipped"))
            continue

        if filename == "AGENTS.md":
            target.write_text(load_workspace_template("AGENTS.md"), encoding="utf-8")
        elif filename == "SOUL_METHOD.md":
            target.write_text(load_workspace_template("SOUL_METHOD.md"), encoding="utf-8")
        elif filename == "SOUL_GOVERNANCE.json":
            target.write_text(load_workspace_template("SOUL_GOVERNANCE.json"), encoding="utf-8")
        else:
            if payload is None:
                raise ValueError(f"{filename} 初始化需要有效的 payload")
            if filename == "IDENTITY.md":
                target.write_text(build_identity_markdown(payload), encoding="utf-8")
            elif filename == "USER.md":
                target.write_text(build_user_markdown(payload), encoding="utf-8")
            elif filename == "CORE_ANCHOR.md":
                target.write_text(build_core_anchor_markdown(payload), encoding="utf-8")
            elif filename == "SOUL.md":
                target.write_text(
                    soul_markdown_override or build_soul_markdown(payload),
                    encoding="utf-8",
                )
            elif filename == "SOUL_PROFILE.md":
                profile = profile_override if profile_override is not None else build_initial_profile()
                SoulProfileManager(workspace).write(profile)
            elif filename == "HEART.md":
                HeartManager(workspace).write_text(
                    heart_markdown_override
                    or render_initial_heart_markdown(
                        payload.personality,
                        initial_relationship=payload.relationship,
                    )
                )
            elif filename == "EVENTS.md":
                EventsManager(workspace).initialize(
                    ai_name=payload.ai_name,
                    ai_birthday=payload.birthday,
                    user_name=payload.user_name or "用户",
                    user_birthday=payload.user_birthday or None,
                )
            else:
                raise ValueError(f"未处理的初始化文件: {filename}")

        actions.append(FileInitAction(
            filename=filename,
            status="overwritten" if existed and force else "created",
        ))

    return actions


def _read_keyed_line(text: str, key: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if line.lower().startswith(f"{key.lower()}:"):
            return line.split(":", 1)[1].strip()
    return ""


def _read_bullet_value(text: str, label: str) -> str:
    pattern = re.compile(rf"^- {re.escape(label)}:\s*(.+)$", re.MULTILINE)
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def _read_heading_section(text: str, heading: str) -> str:
    pattern = re.compile(rf"(?ms)^# {re.escape(heading)}\s*\n(.*?)(?=^# |\Z)")
    match = pattern.search(text)
    return match.group(1).strip() if match else ""
