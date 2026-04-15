"""Tests for partial soul init file selection helpers."""

import pytest

from nanobot.soul.init_files import normalize_only_files


def test_normalize_only_files_orders_and_deduplicates():
    result = normalize_only_files(["SOUL_PROFILE.md", "AGENTS.md", "SOUL_GOVERNANCE.json", "SOUL_PROFILE.md"])

    assert result == ["AGENTS.md", "SOUL_GOVERNANCE.json", "SOUL_PROFILE.md"]


def test_normalize_only_files_rejects_unknown_file():
    with pytest.raises(ValueError, match="不支持的初始化文件"):
        normalize_only_files(["BAD_FILE.md"])
