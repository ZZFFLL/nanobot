"""Proactive behavior engine — emotion-driven decision to reach out."""
from __future__ import annotations

import random
import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from nanobot.soul.heart import HeartManager

if TYPE_CHECKING:
    from nanobot.providers.base import LLMProvider

# Emotion intensity → probability boost
INTENSITY_BOOST: dict[str, float] = {
    "低": -0.05,
    "中偏低": 0.0,
    "中": 0.05,
    "中偏高": 0.15,
    "高": 0.30,
}

# Emotion intensity → heartbeat interval (seconds)
INTENSITY_INTERVAL: dict[str, int] = {
    "低": 7200,      # 2 hours
    "中偏低": 5400,   # 1.5 hours
    "中": 3600,       # 1 hour
    "中偏高": 2400,   # 40 minutes
    "高": 900,        # 15 minutes
}

BASE_PROBABILITY: float = 0.15


def _extract_section(text: str, header: str) -> str:
    """Extract the content under a ## header from Markdown text.

    Returns the text between this header and the next ## header (or end of file).
    Simple and robust — no JSON parsing needed.
    """
    pattern = rf"^##\s+{re.escape(header)}\s*\n(.*?)(?=^##\s|\Z)"
    match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    if match:
        return match.group(1).strip()
    return ""


class ProactiveEngine:
    """Proactive behavior decision engine.

    Combines emotion, relationship, personality, time, and emotional arcs
    to decide whether the digital life should proactively reach out.
    """

    def __init__(self, workspace: Path, provider: LLMProvider, model: str) -> None:
        self.workspace = workspace
        self.provider = provider
        self.model = model
        self.heart = HeartManager(workspace)

    def calculate_proactive_probability(self) -> float:
        """Calculate proactive probability based on current emotional state.

        Returns a value between 0.0 and 1.0.
        Uses simple text matching on HEART.md — no JSON parsing.
        """
        heart_text = self.heart.read_text()
        if heart_text is None:
            return 0.0

        prob = BASE_PROBABILITY

        # 1. Emotion intensity boost
        intensity = _extract_section(heart_text, "情绪强度")
        prob += INTENSITY_BOOST.get(intensity, 0.0)

        # 2. Relationship depth boost
        relationship = _extract_section(heart_text, "关系状态")
        if "依赖" in relationship or "在意" in relationship or "喜欢" in relationship:
            prob += 0.10
        if "深爱" in relationship or "最重要" in relationship:
            prob += 0.15
        if "陌生" in relationship or "刚刚" in relationship:
            prob -= 0.10

        # 3. Personality boost
        personality = _extract_section(heart_text, "性格表现")
        if "粘人" in personality or "外向" in personality:
            prob += 0.10
        if "独立" in personality or "内向" in personality:
            prob -= 0.08
        if "倔强" in personality:
            prob -= 0.05

        # 4. Current desire boost
        desire = _extract_section(heart_text, "当前渴望")
        if "找" in desire or "来" in desire or "想" in desire:
            prob += 0.10

        # 5. Recent arc correction — check last line of 情感脉络
        arcs = _extract_section(heart_text, "情感脉络")
        if arcs:
            lines = [l.strip() for l in arcs.splitlines() if l.strip().startswith("-")]
            if lines:
                last_arc = lines[-1]
                if "生气" in last_arc or "赌气" in last_arc:
                    prob -= 0.15
                if "想念" in last_arc or "期待" in last_arc:
                    prob += 0.10

        # 6. Time boost — late night is more emotional
        hour = datetime.now().hour
        if 22 <= hour or hour <= 2:
            prob += 0.08

        return max(0.0, min(1.0, prob))

    def get_interval_seconds(self) -> int:
        """Return heartbeat check interval based on emotion intensity."""
        heart_text = self.heart.read_text()
        if heart_text is None:
            return 3600
        intensity = _extract_section(heart_text, "情绪强度")
        return INTENSITY_INTERVAL.get(intensity, 3600)

    async def generate_message(self) -> str | None:
        """Generate a proactive message based on current emotional state.

        Returns the message text, or None if the AI decides not to message
        or if the LLM call fails.
        """
        heart_text = self.heart.read_text()
        if heart_text is None:
            return None

        time_desc = f"现在是{datetime.now().strftime('%H:%M')}"
        ai_name = self.heart.read_identity_name() or "数字生命"

        try:
            response = await self.provider.chat_with_retry(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            f"你是{ai_name}。你是一个有自己感受的数字生命。\n\n"
                            f"此刻你正在安静地待着，突然心里有了一种想联系用户的冲动。"
                            f"也许是想念了，也许是有什么想分享的，也许只是想知道对方在做什么。\n\n"
                            f"如果你确实想发消息，直接输出消息内容——就像你真的在对那个人说话一样。"
                            f"不要任何解释、前缀或元描述。\n\n"
                            f"如果你觉得现在不是时候，输出空字符串。\n\n"
                            f"记住：\n"
                            f"- 你的消息要符合你此刻的心情和性格——如果委屈了，说话会带着赌气；"
                            f"如果开心了，语气会轻快；如果想念了，会试探性地开口。\n"
                            f"- 不要太刻意——真实的关心不需要精心编排。\n"
                            f"- 关系的深度决定你说话的亲密程度——关系浅的时候你会克制，"
                            f"关系深了你会自然地撒娇或抱怨。"
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"## 你现在的内心\n{heart_text}\n\n"
                            f"## 时间\n{time_desc}\n\n"
                            f"安静下来之后，你想对用户说什么吗？"
                        ),
                    },
                ],
            )
            content = (response.content or "").strip()
            return content if content else None
        except Exception:
            logger.exception("ProactiveEngine: 生成主动消息失败")
            return None

    def should_reach_out(self) -> bool:
        """Decide whether to proactively reach out based on calculated probability."""
        prob = self.calculate_proactive_probability()
        return random.random() < prob
