"""Tests for bounded normalization of soul init candidates."""

from nanobot.soul.init_inference import SoulInitCandidate


def test_normalize_candidate_wraps_plain_text_and_flattens_percentage_profile():
    from nanobot.soul.init_normalizer import normalize_candidate

    candidate = SoulInitCandidate(
        soul_markdown="温暖可爱，但会保持礼貌距离。",
        heart_markdown="## 当前情绪\n安静。\n\n## 情绪强度\n低\n\n## 关系状态\n正在观察。\n\n## 性格表现\n温暖可爱\n\n## 情感脉络\n（暂无）\n\n## 情绪趋势\n尚在形成\n\n## 当前渴望\n想慢一点理解用户。",
        profile={
            "personality": {"Fi": 80, "Fe": 35, "Ti": 20, "Te": 5, "Si": 50, "Se": 10, "Ni": 5, "Ne": 65},
            "relationship": {
                "stage": "熟悉",
                "dimensions": {
                    "trust": 10,
                    "intimacy": 5,
                    "attachment": 0,
                    "security": 20,
                    "boundary": 90,
                    "affection": 5,
                },
            },
            "companionship": {
                "empathy_fit": 65,
                "memory_fit": 50,
                "naturalness": 55,
                "initiative_quality": 15,
                "scene_awareness": 50,
                "boundary_expression": 88,
            },
        },
    )

    normalized = normalize_candidate(candidate, default_relationship="刚认识用户")

    assert normalized.soul_markdown.startswith("# 性格")
    assert "# 初始关系" in normalized.soul_markdown
    assert "当前情绪" in normalized.heart_markdown
    assert normalized.profile["personality"]["Fi"] == 0.8
    assert normalized.profile["relationship"]["trust"] == 0.1
    assert normalized.profile["relationship"]["boundary"] == 0.9
    assert normalized.profile["companionship"]["naturalness"] == 0.55
