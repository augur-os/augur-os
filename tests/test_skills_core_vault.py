"""Unit tests for the vault/actions/reindex skill-discovery implementations.

Covers ``skills_vault``: page-action listing from a real ``actions.yaml``,
vault-note parsing (frontmatter type, grouping, stats), and the
category-validation guards in the reindex impl. All filesystem state lives in
``tmp_path``; ``get_skill_data_dir`` is monkeypatched so the real vault is
never read.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from src.mcp.augur_core.tools.core import skills_vault
from src.mcp.augur_core.tools.core.skills_vault import (
    list_skill_actions_impl,
    list_skill_vault_notes_impl,
    reindex_browse_category_impl,
)

ACTIONS_YAML = """\
actions:
  - id: open-page
    label: Open Page
    kind: mcp
    dispatch: fire
    mcp_tool: some-tool
    surfaces: [page]
    icon: rocket
  - id: card-only
    label: Card Only
    kind: mcp
    dispatch: ide
    surfaces: [card]
    categories: [skills]
"""


def test_list_skill_actions_filters_to_page_surface(tmp_path):
    """Only actions whose surfaces include 'page' are returned."""
    skill_path = tmp_path / "ask"
    (skill_path / "augur").mkdir(parents=True)
    (skill_path / "augur" / "actions.yaml").write_text(ACTIONS_YAML, encoding="utf-8")
    entry = SimpleNamespace(name="ask", path=skill_path)

    result = list_skill_actions_impl("ask", resolve_skill_entry=lambda n: entry)
    actions = result["actions"]
    assert len(actions) == 1
    assert actions[0]["id"] == "open-page"
    assert actions[0]["label"] == "Open Page"
    assert actions[0]["icon"] == "rocket"
    assert actions[0]["mcp_tools"] == ["some-tool"]
    assert actions[0]["dispatch"] == "fire"


def test_list_skill_actions_missing_yaml_returns_empty(tmp_path):
    """A skill with no actions.yaml yields an empty action list."""
    skill_path = tmp_path / "ask"
    skill_path.mkdir()
    entry = SimpleNamespace(name="ask", path=skill_path)

    assert list_skill_actions_impl("ask", resolve_skill_entry=lambda n: entry) == {"actions": []}


def test_list_skill_actions_unresolved_skill_returns_empty():
    """An unresolvable skill yields an empty action list."""
    assert list_skill_actions_impl("nope", resolve_skill_entry=lambda n: None) == {"actions": []}


def test_list_skill_actions_skill_id_alias(tmp_path):
    """The skill_id keyword alias resolves the same as skill_name."""
    skill_path = tmp_path / "ask"
    (skill_path / "augur").mkdir(parents=True)
    (skill_path / "augur" / "actions.yaml").write_text(ACTIONS_YAML, encoding="utf-8")
    entry = SimpleNamespace(name="ask", path=skill_path)

    result = list_skill_actions_impl(skill_id="ask", resolve_skill_entry=lambda n: entry)
    assert [a["id"] for a in result["actions"]] == ["open-page"]


@pytest.mark.asyncio
async def test_list_skill_vault_notes_parses_and_groups(monkeypatch, tmp_path):
    """Notes parse frontmatter type, preview, line count, and group by dir."""
    vault = tmp_path / "vault-ask"
    (vault / "topic").mkdir(parents=True)
    (vault / "root-note.md").write_text('---\ntype: log\n---\nFirst line\nSecond line\n', encoding="utf-8")
    (vault / "topic" / "nested.md").write_text("# Nested\nBody text", encoding="utf-8")

    monkeypatch.setattr(skills_vault, "get_skill_data_dir", lambda name: vault)
    entry = SimpleNamespace(name="ask", path=tmp_path)

    result = json.loads(await list_skill_vault_notes_impl("ask", lambda n: entry))
    assert result["stats"]["total_files"] == 2
    names = {n["name"] for n in result["notes"]}
    assert names == {"root-note.md", "topic/nested.md"}

    group_dirs = {g["directory"] for g in result["groups"]}
    assert group_dirs == {".", "topic"}

    # The root note's frontmatter type is parsed out and body used for preview.
    root_group = next(g for g in result["groups"] if g["directory"] == ".")
    root_entry = root_group["files"][0]
    assert root_entry["type"] == "log"
    assert root_entry["preview"].startswith("First line")


@pytest.mark.asyncio
async def test_list_skill_vault_notes_unresolved_skill_is_empty(tmp_path):
    """An unresolvable skill returns the canonical empty payload."""
    result = json.loads(await list_skill_vault_notes_impl("nope", lambda n: None))
    assert result == {"notes": [], "groups": [], "stats": {"total_files": 0, "total_dirs": 0}}


@pytest.mark.asyncio
async def test_list_skill_vault_notes_missing_dir_is_empty(monkeypatch, tmp_path):
    """A resolvable skill with no vault dir returns the empty payload."""
    monkeypatch.setattr(skills_vault, "get_skill_data_dir", lambda name: tmp_path / "absent")
    entry = SimpleNamespace(name="ask", path=tmp_path)

    result = json.loads(await list_skill_vault_notes_impl("ask", lambda n: entry))
    assert result["stats"]["total_files"] == 0


@pytest.mark.asyncio
async def test_reindex_browse_category_rejects_unknown():
    """An unknown category fails fast without shelling out."""
    result = json.loads(await reindex_browse_category_impl("not-a-category"))
    assert result["success"] is False
    assert "Unknown category" in result["error"]


@pytest.mark.asyncio
async def test_reindex_browse_category_profile_is_synthetic():
    """The 'profile' category short-circuits to a synthetic success."""
    result = json.loads(await reindex_browse_category_impl("profile"))
    assert result["success"] is True
    assert result["category"] == "profile"
    assert result["synthetic"] is True
