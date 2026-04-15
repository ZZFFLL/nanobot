"""Tests for soul methodology source definitions."""

from nanobot.soul.bootstrap import load_workspace_template
from nanobot.soul.methodology import RELATIONSHIP_STAGES, render_soul_method_markdown


def test_render_soul_method_markdown_lists_all_relationship_stages():
    content = render_soul_method_markdown()

    for stage in RELATIONSHIP_STAGES:
        assert stage in content


def test_load_workspace_template_uses_methodology_rendered_soul_method():
    assert load_workspace_template("SOUL_METHOD.md") == render_soul_method_markdown()
