"""Tests for ADR-450 template resolver MCP tools.

Validates the template resolution pipeline: YAML parsing, override merging,
orphan detection, dependency checking, and active template reading.
"""

# TODO_CLEANUP: This file is 942 lines — consider splitting into smaller modules

from __future__ import annotations

import yaml
from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MODULE = "src.mcp.augur_framework.tools.internal.template_resolver"


def _write_yaml(path: Path, data: dict | list) -> None:
    """Write a YAML file, creating parent dirs as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")


def _base_template(tmp_path: Path, hub: str, template_id: str, data: dict) -> Path:
    """Write a base template YAML and return its path."""
    p = tmp_path / "project" / "plugins" / "ui" / "templates" / hub / f"{template_id}.yaml"
    _write_yaml(p, data)
    return p


def _override(tmp_path: Path, hub: str, template_id: str, data: dict) -> Path:
    """Write a user override YAML and return its path."""
    p = tmp_path / "vault" / "config" / "dashboard" / "templates" / hub / f"{template_id}.overrides.yaml"
    _write_yaml(p, data)
    return p


def _active_yaml(tmp_path: Path, data: dict) -> Path:
    """Write the active.yaml file and return its path."""
    p = tmp_path / "vault" / "config" / "dashboard" / "active.yaml"
    _write_yaml(p, data)
    return p


def _add_skill(tmp_path: Path, skill_name: str, *, claude: bool = False, hub: str = "brain") -> None:
    """Create a SKILL.md in the canonical shared skills directory."""
    skill_dir = tmp_path / "project" / "project-brain" / "capabilities" / "skills" / skill_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(f"# {skill_name}\n")


def _disable_skill(tmp_path: Path, skill_name: str, *, hub: str = "brain") -> None:
    """Disable a canonical skill through the runtime-backed local state store."""
    state_path = tmp_path / "runtime" / "dashboard" / "skills-state.yaml"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    if state_path.exists():
        raw = yaml.safe_load(state_path.read_text(encoding="utf-8")) or {}
        state = raw if isinstance(raw, dict) else {}
    else:
        state = {}
    disabled = state.get("disabled")
    if not isinstance(disabled, list):
        disabled = []
    if skill_name not in disabled:
        disabled.append(skill_name)
    state["version"] = state.get("version", 1)
    state["disabled"] = sorted(disabled)
    state.setdefault("partial", {})
    state.setdefault("skills", {})
    state_path.write_text(yaml.safe_dump(state, sort_keys=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def env(tmp_path):
    """Set up isolated project root + vault dir via monkeypatching."""
    from src.plugins.skill_config import clear_config_cache
    from src.mcp.augur_framework.tools.internal.template_resolver import _invalidate_skill_cache

    project_root = tmp_path / "project"
    vault_dir = tmp_path / "vault"
    runtime_dir = tmp_path / "runtime"
    project_root.mkdir()
    vault_dir.mkdir()
    runtime_dir.mkdir()

    # Ensure plugins/ui/templates dir exists (even if empty)
    (project_root / "plugins" / "ui" / "templates").mkdir(parents=True, exist_ok=True)
    (project_root / "project-brain" / "capabilities" / "skills").mkdir(parents=True, exist_ok=True)

    # Clear config and skill caches to avoid stale state between tests
    clear_config_cache()
    _invalidate_skill_cache()

    with (
        patch(f"{MODULE}.get_project_root", return_value=project_root),
        patch(f"{MODULE}.get_vault_config_dir", return_value=vault_dir / "config"),
        # Patch skill_config's get_project_root too so canonical skill state
        # helpers resolve against our tmp_path.
        patch("src.plugins.skill_config.get_project_root", return_value=project_root),
        patch("src.plugins.skill_ui_state.get_runtime_dir", return_value=runtime_dir),
    ):
        yield tmp_path

    clear_config_cache()
    _invalidate_skill_cache()


# ---------------------------------------------------------------------------
# 1. YAML parsing
# ---------------------------------------------------------------------------


class TestYAMLParsing:
    """Template YAML with blocks and actions parses correctly."""

    def test_base_template_parses_blocks_and_actions(self, env):
        from src.mcp.augur_framework.tools.internal.template_resolver import _resolve_template

        _add_skill(env, "memory")
        _base_template(
            env,
            "brain",
            "overview",
            {
                "name": "Brain Overview",
                "description": "Main brain dashboard",
                "hub": "brain",
                "icon": "Brain",
                "layout": "2-column",
                "requires": ["memory"],
                "blocks": [
                    {"id": "mem-recent", "source": "memory", "block": "recent-entries", "span": 6, "order": 1},
                    {
                        "id": "mem-stats",
                        "source": "memory",
                        "block": "stats",
                        "span": 6,
                        "order": 2,
                        "config": {"limit": 10},
                    },
                ],
                "actions": [
                    {"id": "sync-memory", "source": "memory", "action": "sync"},
                ],
            },
        )

        result = _resolve_template("brain", "overview")

        assert result["name"] == "Brain Overview"
        assert result["description"] == "Main brain dashboard"
        assert result["hub"] == "brain"
        assert result["icon"] == "Brain"
        assert result["layout"] == "2-column"
        assert len(result["blocks"]) == 2
        assert result["blocks"][0]["id"] == "mem-recent"
        assert result["blocks"][0]["registryKey"] == "memory:recent-entries"
        assert result["blocks"][0]["span"] == 6
        assert result["blocks"][0]["order"] == 1
        assert result["blocks"][1]["config"] == {"limit": 10}
        assert len(result["actions"]) == 1
        assert result["actions"][0]["id"] == "sync-memory"
        assert result["actions"][0]["source"] == "memory"
        assert result["actions"][0]["action"] == "sync"

    def test_missing_base_template_returns_error(self, env):
        from src.mcp.augur_framework.tools.internal.template_resolver import _resolve_template

        result = _resolve_template("brain", "nonexistent")
        assert "error" in result
        assert "not found" in result["error"]


# ---------------------------------------------------------------------------
# 2. Override merge — add
# ---------------------------------------------------------------------------


class TestOverrideAdd:
    """Override adds a new block (user-added)."""

    def test_user_added_block_appears_in_resolved(self, env):
        from src.mcp.augur_framework.tools.internal.template_resolver import _resolve_template

        _add_skill(env, "notes")
        _add_skill(env, "calendar")
        _base_template(
            env,
            "brain",
            "dash",
            {
                "name": "Dash",
                "blocks": [
                    {"id": "b1", "source": "notes", "block": "list", "span": 6, "order": 1},
                ],
            },
        )
        _override(
            env,
            "brain",
            "dash",
            {
                "blocks": {
                    "user-cal": {
                        "source": "calendar",
                        "block": "upcoming",
                        "span": 4,
                        "order": 5,
                    },
                },
            },
        )

        result = _resolve_template("brain", "dash")

        user_block = next(b for b in result["blocks"] if b["id"] == "user-cal")
        assert user_block["userAdded"] is True
        assert user_block["registryKey"] == "calendar:upcoming"
        assert user_block["span"] == 4
        assert user_block["order"] == 5

    def test_base_block_is_not_user_added(self, env):
        from src.mcp.augur_framework.tools.internal.template_resolver import _resolve_template

        _add_skill(env, "notes")
        _base_template(
            env,
            "brain",
            "dash",
            {
                "name": "Dash",
                "blocks": [
                    {"id": "b1", "source": "notes", "block": "list", "span": 6, "order": 1},
                ],
            },
        )

        result = _resolve_template("brain", "dash")
        assert result["blocks"][0]["userAdded"] is False


# ---------------------------------------------------------------------------
# 3. Override merge — remove
# ---------------------------------------------------------------------------


class TestOverrideRemove:
    """Override marks block as removed: true, it is excluded."""

    def test_removed_block_is_excluded(self, env):
        from src.mcp.augur_framework.tools.internal.template_resolver import _resolve_template

        _add_skill(env, "notes")
        _base_template(
            env,
            "brain",
            "dash",
            {
                "name": "Dash",
                "blocks": [
                    {"id": "b1", "source": "notes", "block": "list", "span": 6, "order": 1},
                    {"id": "b2", "source": "notes", "block": "stats", "span": 6, "order": 2},
                ],
            },
        )
        _override(
            env,
            "brain",
            "dash",
            {
                "blocks": {
                    "b1": {"removed": True},
                },
            },
        )

        result = _resolve_template("brain", "dash")

        block_ids = [b["id"] for b in result["blocks"]]
        assert "b1" not in block_ids
        assert "b2" in block_ids

    def test_removed_user_added_block_is_excluded(self, env):
        from src.mcp.augur_framework.tools.internal.template_resolver import _resolve_template

        _add_skill(env, "notes")
        _base_template(
            env,
            "brain",
            "dash",
            {
                "name": "Dash",
                "blocks": [
                    {"id": "b1", "source": "notes", "block": "list", "span": 6, "order": 1},
                ],
            },
        )
        _override(
            env,
            "brain",
            "dash",
            {
                "blocks": {
                    "user-extra": {
                        "source": "notes",
                        "block": "archive",
                        "removed": True,
                    },
                },
            },
        )

        result = _resolve_template("brain", "dash")
        block_ids = [b["id"] for b in result["blocks"]]
        assert "user-extra" not in block_ids


# ---------------------------------------------------------------------------
# 4. Override merge — reorder
# ---------------------------------------------------------------------------


class TestOverrideReorder:
    """Override changes order of a block."""

    def test_reordered_block_moves_position(self, env):
        from src.mcp.augur_framework.tools.internal.template_resolver import _resolve_template

        _add_skill(env, "notes")
        _base_template(
            env,
            "brain",
            "dash",
            {
                "name": "Dash",
                "blocks": [
                    {"id": "b1", "source": "notes", "block": "list", "span": 6, "order": 1},
                    {"id": "b2", "source": "notes", "block": "stats", "span": 6, "order": 2},
                    {"id": "b3", "source": "notes", "block": "graph", "span": 6, "order": 3},
                ],
            },
        )
        # Move b3 to the front
        _override(
            env,
            "brain",
            "dash",
            {
                "blocks": {
                    "b3": {"order": 0},
                },
            },
        )

        result = _resolve_template("brain", "dash")

        ids_in_order = [b["id"] for b in result["blocks"]]
        assert ids_in_order == ["b3", "b1", "b2"]


# ---------------------------------------------------------------------------
# 5. Override merge — config override
# ---------------------------------------------------------------------------


class TestOverrideConfig:
    """Override changes block config."""

    def test_config_values_are_merged(self, env):
        from src.mcp.augur_framework.tools.internal.template_resolver import _resolve_template

        _add_skill(env, "notes")
        _base_template(
            env,
            "brain",
            "dash",
            {
                "name": "Dash",
                "blocks": [
                    {
                        "id": "b1",
                        "source": "notes",
                        "block": "list",
                        "span": 6,
                        "order": 1,
                        "config": {"limit": 10, "sort": "date"},
                    },
                ],
            },
        )
        _override(
            env,
            "brain",
            "dash",
            {
                "blocks": {
                    "b1": {"config": {"limit": 25}},
                },
            },
        )

        result = _resolve_template("brain", "dash")
        block = result["blocks"][0]
        # limit overridden, sort preserved from base
        assert block["config"]["limit"] == 25
        assert block["config"]["sort"] == "date"

    def test_span_override(self, env):
        from src.mcp.augur_framework.tools.internal.template_resolver import _resolve_template

        _add_skill(env, "notes")
        _base_template(
            env,
            "brain",
            "dash",
            {
                "name": "Dash",
                "blocks": [
                    {"id": "b1", "source": "notes", "block": "list", "span": 6, "order": 1},
                ],
            },
        )
        _override(
            env,
            "brain",
            "dash",
            {
                "blocks": {
                    "b1": {"span": 12},
                },
            },
        )

        result = _resolve_template("brain", "dash")
        assert result["blocks"][0]["span"] == 12


# ---------------------------------------------------------------------------
# 6. Orphan detection
# ---------------------------------------------------------------------------


class TestOrphanDetection:
    """Base removes a block that user customized -> appears in orphanedOverrides."""

    def test_orphaned_override_is_reported(self, env):
        from src.mcp.augur_framework.tools.internal.template_resolver import _resolve_template

        _add_skill(env, "notes")
        # Base has only b1 — b2 no longer exists
        _base_template(
            env,
            "brain",
            "dash",
            {
                "name": "Dash",
                "blocks": [
                    {"id": "b1", "source": "notes", "block": "list", "span": 6, "order": 1},
                ],
            },
        )
        # User had customized b2 (which was removed from base) but override
        # lacks source/block, so it can't be rendered as user-added.
        _override(
            env,
            "brain",
            "dash",
            {
                "blocks": {
                    "b2": {"order": 5, "span": 12},
                },
            },
        )

        result = _resolve_template("brain", "dash")
        assert "b2" in result["orphanedOverrides"]

    def test_non_orphaned_override_is_not_reported(self, env):
        from src.mcp.augur_framework.tools.internal.template_resolver import _resolve_template

        _add_skill(env, "notes")
        _base_template(
            env,
            "brain",
            "dash",
            {
                "name": "Dash",
                "blocks": [
                    {"id": "b1", "source": "notes", "block": "list", "span": 6, "order": 1},
                ],
            },
        )
        _override(
            env,
            "brain",
            "dash",
            {
                "blocks": {
                    "b1": {"order": 5},
                },
            },
        )

        result = _resolve_template("brain", "dash")
        assert result["orphanedOverrides"] == []


# ---------------------------------------------------------------------------
# 7. Dependency check
# ---------------------------------------------------------------------------


class TestDependencyCheck:
    """Template requiring a non-existent skill marks blocks as unavailable."""

    def test_missing_skill_dependency_marked_unavailable(self, env):
        from src.mcp.augur_framework.tools.internal.template_resolver import _resolve_template

        # Do NOT add "phantom" skill — it doesn't exist
        _base_template(
            env,
            "brain",
            "dash",
            {
                "name": "Dash",
                "requires": ["phantom"],
                "blocks": [
                    {"id": "b1", "source": "phantom", "block": "widget", "span": 6, "order": 1},
                ],
            },
        )

        result = _resolve_template("brain", "dash")

        assert result["dependencies"]["missing"] == ["phantom"]
        assert result["dependencies"]["available"] == []
        assert result["blocks"][0]["dependency"]["available"] is False
        assert result["blocks"][0]["dependency"]["skill"] == "phantom"

    def test_present_skill_dependency_marked_available(self, env):
        from src.mcp.augur_framework.tools.internal.template_resolver import _resolve_template

        _add_skill(env, "memory")
        _base_template(
            env,
            "brain",
            "dash",
            {
                "name": "Dash",
                "requires": ["memory"],
                "blocks": [
                    {"id": "b1", "source": "memory", "block": "entries", "span": 6, "order": 1},
                ],
            },
        )

        result = _resolve_template("brain", "dash")

        assert result["dependencies"]["available"] == ["memory"]
        assert result["dependencies"]["missing"] == []
        assert result["blocks"][0]["dependency"]["available"] is True

    def test_claude_skill_is_discoverable(self, env):
        from src.mcp.augur_framework.tools.internal.template_resolver import _resolve_template

        _add_skill(env, "dev-merge", claude=True)
        _base_template(
            env,
            "brain",
            "dash",
            {
                "name": "Dash",
                "requires": ["dev-merge"],
                "blocks": [
                    {"id": "b1", "source": "dev-merge", "block": "status", "span": 6, "order": 1},
                ],
            },
        )

        result = _resolve_template("brain", "dash")
        assert result["dependencies"]["available"] == ["dev-merge"]
        assert result["blocks"][0]["dependency"]["available"] is True

    def test_disabled_skill_gets_auto_enabled(self, env):
        """A disabled internal skill required by a template gets auto-enabled."""
        from src.mcp.augur_framework.tools.internal.template_resolver import _resolve_template

        _add_skill(env, "analytics")
        _disable_skill(env, "analytics")
        _base_template(
            env,
            "brain",
            "dash",
            {
                "name": "Dash",
                "requires": ["analytics"],
                "blocks": [
                    {"id": "b1", "source": "analytics", "block": "chart", "span": 6, "order": 1},
                ],
            },
        )

        result = _resolve_template("brain", "dash")

        # Skill was auto-enabled: available, no longer missing
        assert result["dependencies"]["available"] == ["analytics"]
        assert result["dependencies"]["missing"] == []
        assert result["dependencies"]["autoEnabled"] == ["analytics"]
        # Block dependency reflects auto-enabled state
        dep_detail = result["dependencies"]["details"][0]
        assert dep_detail["autoEnabled"] is True
        assert dep_detail["available"] is True
        assert dep_detail["enabled"] is True
        assert dep_detail["community"] is False
        # Block itself is available
        assert result["blocks"][0]["dependency"]["available"] is True
        assert result["blocks"][0]["dependency"]["autoEnabled"] is True

    def test_community_skill_not_found_locally(self, env):
        """A required skill not found locally is flagged as community/unavailable."""
        from src.mcp.augur_framework.tools.internal.template_resolver import _resolve_template

        _base_template(
            env,
            "brain",
            "dash",
            {
                "name": "Dash",
                "requires": ["community-plugin"],
                "blocks": [
                    {"id": "b1", "source": "community-plugin", "block": "feed", "span": 6, "order": 1},
                ],
            },
        )

        result = _resolve_template("brain", "dash")

        # Dependency summary
        assert result["dependencies"]["required"] == ["community-plugin"]
        assert result["dependencies"]["missing"] == ["community-plugin"]
        assert result["dependencies"]["available"] == []
        # Detail record has community flag
        dep_detail = result["dependencies"]["details"][0]
        assert dep_detail["community"] is True
        assert dep_detail["available"] is False
        assert dep_detail["enabled"] is False
        assert dep_detail["autoEnabled"] is False
        # Block-level dependency
        assert result["blocks"][0]["dependency"]["community"] is True
        assert result["blocks"][0]["dependency"]["available"] is False

    def test_multiple_blocks_same_skill(self, env):
        """Multiple blocks from the same skill all get consistent dependency status."""
        from src.mcp.augur_framework.tools.internal.template_resolver import _resolve_template

        _add_skill(env, "notes")
        _base_template(
            env,
            "brain",
            "dash",
            {
                "name": "Dash",
                "requires": ["notes"],
                "blocks": [
                    {"id": "b1", "source": "notes", "block": "list", "span": 6, "order": 1},
                    {"id": "b2", "source": "notes", "block": "stats", "span": 6, "order": 2},
                    {"id": "b3", "source": "notes", "block": "graph", "span": 12, "order": 3},
                ],
            },
        )

        result = _resolve_template("brain", "dash")

        # Only one entry in required/available despite 3 blocks from "notes"
        assert result["dependencies"]["required"] == ["notes"]
        assert result["dependencies"]["available"] == ["notes"]
        assert result["dependencies"]["missing"] == []
        assert len(result["dependencies"]["details"]) == 1

        # All 3 blocks reference "notes" and all are available
        for block in result["blocks"]:
            assert block["dependency"]["skill"] == "notes"
            assert block["dependency"]["available"] is True

    def test_no_requires_empty_dependencies(self, env):
        """Template with no requires field has empty dependency arrays but blocks still resolve."""
        from src.mcp.augur_framework.tools.internal.template_resolver import _resolve_template

        _add_skill(env, "tasks")
        _base_template(
            env,
            "brain",
            "dash",
            {
                "name": "No Requires",
                "blocks": [
                    {"id": "b1", "source": "tasks", "block": "inbox", "span": 6, "order": 1},
                ],
            },
        )

        result = _resolve_template("brain", "dash")

        # Dependency summary is empty since no requires
        assert result["dependencies"]["required"] == []
        assert result["dependencies"]["available"] == []
        assert result["dependencies"]["missing"] == []
        assert result["dependencies"]["details"] == []
        assert result["dependencies"]["autoEnabled"] == []

        # Block is still present with its own per-block dependency check
        assert len(result["blocks"]) == 1
        assert result["blocks"][0]["dependency"]["skill"] == "tasks"
        assert result["blocks"][0]["dependency"]["available"] is True

    def test_dependency_arrays_mixed_available_and_missing(self, env):
        """Required/available/missing arrays are correct when some skills exist and some don't."""
        from src.mcp.augur_framework.tools.internal.template_resolver import _resolve_template

        _add_skill(env, "notes")
        _add_skill(env, "calendar")
        # "phantom" is NOT added — it will be missing
        _base_template(
            env,
            "brain",
            "dash",
            {
                "name": "Mixed",
                "requires": ["notes", "phantom", "calendar"],
                "blocks": [
                    {"id": "b1", "source": "notes", "block": "list", "span": 6, "order": 1},
                    {"id": "b2", "source": "phantom", "block": "widget", "span": 6, "order": 2},
                    {"id": "b3", "source": "calendar", "block": "upcoming", "span": 6, "order": 3},
                ],
            },
        )

        result = _resolve_template("brain", "dash")

        assert result["dependencies"]["required"] == ["notes", "phantom", "calendar"]
        assert result["dependencies"]["available"] == ["notes", "calendar"]
        assert result["dependencies"]["missing"] == ["phantom"]
        assert len(result["dependencies"]["details"]) == 3

        # Block-level checks
        blocks_by_id = {b["id"]: b for b in result["blocks"]}
        assert blocks_by_id["b1"]["dependency"]["available"] is True
        assert blocks_by_id["b2"]["dependency"]["available"] is False
        assert blocks_by_id["b2"]["dependency"]["community"] is True
        assert blocks_by_id["b3"]["dependency"]["available"] is True


# ---------------------------------------------------------------------------
# 8. Missing override file
# ---------------------------------------------------------------------------


class TestMissingOverride:
    """No override file -> template renders from base only, hasOverride: false."""

    def test_no_override_file(self, env):
        from src.mcp.augur_framework.tools.internal.template_resolver import _resolve_template

        _add_skill(env, "notes")
        _base_template(
            env,
            "brain",
            "dash",
            {
                "name": "Dash",
                "blocks": [
                    {"id": "b1", "source": "notes", "block": "list", "span": 6, "order": 1},
                ],
            },
        )

        result = _resolve_template("brain", "dash")

        assert result["hasOverride"] is False
        assert len(result["blocks"]) == 1
        assert result["orphanedOverrides"] == []

    def test_with_override_file_has_override_true(self, env):
        from src.mcp.augur_framework.tools.internal.template_resolver import _resolve_template

        _add_skill(env, "notes")
        _base_template(
            env,
            "brain",
            "dash",
            {
                "name": "Dash",
                "blocks": [
                    {"id": "b1", "source": "notes", "block": "list", "span": 6, "order": 1},
                ],
            },
        )
        _override(
            env,
            "brain",
            "dash",
            {
                "blocks": {
                    "b1": {"span": 12},
                },
            },
        )

        result = _resolve_template("brain", "dash")
        assert result["hasOverride"] is True


# ---------------------------------------------------------------------------
# 9. Empty template
# ---------------------------------------------------------------------------


class TestEmptyTemplate:
    """Template with no blocks -> empty blocks array."""

    def test_empty_blocks(self, env):
        from src.mcp.augur_framework.tools.internal.template_resolver import _resolve_template

        _base_template(
            env,
            "brain",
            "empty",
            {
                "name": "Empty Template",
                "blocks": [],
            },
        )

        result = _resolve_template("brain", "empty")

        assert result["blocks"] == []
        assert result["actions"] == []
        assert result["name"] == "Empty Template"

    def test_no_blocks_key(self, env):
        from src.mcp.augur_framework.tools.internal.template_resolver import _resolve_template

        _base_template(
            env,
            "brain",
            "minimal",
            {
                "name": "Minimal",
            },
        )

        result = _resolve_template("brain", "minimal")

        assert result["blocks"] == []
        assert result["actions"] == []


# ---------------------------------------------------------------------------
# 10. Active templates
# ---------------------------------------------------------------------------


class TestActiveTemplates:
    """read-active-templates reads active.yaml and returns correct hub data."""

    def test_read_all_hubs(self, env):
        from src.mcp.augur_framework.tools.internal.template_resolver import _read_active_templates

        _active_yaml(
            env,
            {
                "brain": {"templates": ["overview", "memory"], "order": {"overview": 1, "memory": 2}},
                "career": {"templates": ["jobs"]},
            },
        )

        result = _read_active_templates()

        assert "brain" in result
        assert "career" in result
        assert result["brain"]["templates"] == ["overview", "memory"]
        assert result["career"]["templates"] == ["jobs"]

    def test_read_single_hub(self, env):
        from src.mcp.augur_framework.tools.internal.template_resolver import _read_active_templates

        _active_yaml(
            env,
            {
                "brain": {"templates": ["overview"]},
                "career": {"templates": ["jobs"]},
            },
        )

        result = _read_active_templates(hub="career")

        assert "career" in result
        assert "brain" not in result
        assert result["career"]["templates"] == ["jobs"]

    def test_read_nonexistent_hub_returns_empty(self, env):
        from src.mcp.augur_framework.tools.internal.template_resolver import _read_active_templates

        _active_yaml(
            env,
            {
                "brain": {"templates": ["overview"]},
            },
        )

        result = _read_active_templates(hub="nonexistent")
        assert result == {}

    def test_missing_active_yaml_returns_empty(self, env):
        from src.mcp.augur_framework.tools.internal.template_resolver import _read_active_templates

        # No active.yaml written
        result = _read_active_templates()
        assert result == {}


# ---------------------------------------------------------------------------
# 11. Activate template
# ---------------------------------------------------------------------------


class TestActivateTemplate:
    """activate-template adds/removes templates in active.yaml."""

    def test_activate_adds_template(self, env):
        from src.mcp.augur_framework.tools.internal.template_resolver import _activate_template, _read_active_templates

        _base_template(env, "brain", "overview", {"name": "Overview", "blocks": []})

        result = _activate_template("brain", "overview")

        assert result["ok"] is True
        assert result["hub"] == "brain"
        assert result["template_id"] == "overview"
        assert result["active"] is True
        assert "overview" in result["templates"]
        # Verify it's readable back from active.yaml
        active = _read_active_templates("brain")
        assert "overview" in active["brain"]["templates"]

    def test_activate_idempotent(self, env):
        from src.mcp.augur_framework.tools.internal.template_resolver import _activate_template

        _base_template(env, "brain", "overview", {"name": "Overview", "blocks": []})

        _activate_template("brain", "overview")
        result = _activate_template("brain", "overview")

        assert result["ok"] is True
        assert result["templates"].count("overview") == 1

    def test_deactivate_removes_template(self, env):
        from src.mcp.augur_framework.tools.internal.template_resolver import _activate_template, _read_active_templates

        _base_template(env, "brain", "overview", {"name": "Overview", "blocks": []})

        _activate_template("brain", "overview")
        result = _activate_template("brain", "overview", active=False)

        assert result["ok"] is True
        assert result["active"] is False
        assert "overview" not in result["templates"]
        active = _read_active_templates("brain")
        # Hub entry might exist but templates list should be empty
        if "brain" in active:
            assert "overview" not in active["brain"].get("templates", [])

    def test_deactivate_nonexistent_is_noop(self, env):
        from src.mcp.augur_framework.tools.internal.template_resolver import _activate_template

        # No active.yaml exists, deactivating something that isn't active
        result = _activate_template("brain", "ghost", active=False)

        assert result["ok"] is True
        assert "ghost" not in result["templates"]

    def test_activate_nonexistent_template_returns_error(self, env):
        from src.mcp.augur_framework.tools.internal.template_resolver import _activate_template

        # No template YAML file exists for "nonexistent"
        result = _activate_template("brain", "nonexistent")

        assert result["ok"] is False
        assert "error" in result
        assert "not found" in result["error"]

    def test_activate_creates_hub_entry(self, env):
        from src.mcp.augur_framework.tools.internal.template_resolver import _activate_template, _read_active_templates

        _base_template(env, "career", "jobs", {"name": "Jobs", "blocks": []})

        # No active.yaml exists yet — activating should create the hub entry
        result = _activate_template("career", "jobs")

        assert result["ok"] is True
        assert result["hub"] == "career"
        active = _read_active_templates()
        assert "career" in active
        assert "jobs" in active["career"]["templates"]


# ---------------------------------------------------------------------------
# 12. List templates catalog
# ---------------------------------------------------------------------------


class TestListTemplatesCatalog:
    """list-templates-catalog returns catalog entries grouped by hub."""

    def test_list_all_hubs(self, env):
        from src.mcp.augur_framework.tools.internal.template_resolver import _list_templates_catalog

        _base_template(env, "brain", "overview", {"name": "Brain Overview", "blocks": []})
        _base_template(env, "career", "jobs", {"name": "Career Jobs", "blocks": []})

        result = _list_templates_catalog()

        assert "brain" in result
        assert "career" in result
        assert len(result["brain"]) == 1
        assert result["brain"][0]["id"] == "overview"
        assert result["brain"][0]["name"] == "Brain Overview"
        assert len(result["career"]) == 1
        assert result["career"][0]["id"] == "jobs"

    def test_list_single_hub(self, env):
        from src.mcp.augur_framework.tools.internal.template_resolver import _list_templates_catalog

        _base_template(env, "brain", "overview", {"name": "Brain Overview", "blocks": []})
        _base_template(env, "career", "jobs", {"name": "Career Jobs", "blocks": []})

        result = _list_templates_catalog(hub="brain")

        assert "brain" in result
        assert "career" not in result
        assert result["brain"][0]["id"] == "overview"

    def test_active_flag_set_correctly(self, env):
        from src.mcp.augur_framework.tools.internal.template_resolver import _list_templates_catalog

        _base_template(env, "brain", "overview", {"name": "Overview", "blocks": []})
        _base_template(env, "brain", "memory", {"name": "Memory", "blocks": []})
        _active_yaml(env, {"brain": {"templates": ["overview"]}})

        result = _list_templates_catalog(hub="brain")

        entries_by_id = {e["id"]: e for e in result["brain"]}
        assert entries_by_id["overview"]["active"] is True
        assert entries_by_id["memory"]["active"] is False

    def test_inactive_template_has_active_false(self, env):
        from src.mcp.augur_framework.tools.internal.template_resolver import _list_templates_catalog

        _base_template(env, "brain", "overview", {"name": "Overview", "blocks": []})
        # No active.yaml — nothing is active

        result = _list_templates_catalog(hub="brain")

        assert result["brain"][0]["active"] is False

    def test_empty_templates_dir(self, env):
        from src.mcp.augur_framework.tools.internal.template_resolver import (
            _list_templates_catalog,
            _load_seed_templates_catalog,
        )

        # templates dir exists (created by env fixture) but is empty,
        # so the catalog falls back to starter seed templates.
        result = _list_templates_catalog()

        assert result == _load_seed_templates_catalog()

    def test_malformed_yaml_skipped(self, env):
        from src.mcp.augur_framework.tools.internal.template_resolver import _list_templates_catalog

        # Write a valid template
        _base_template(env, "brain", "good", {"name": "Good Template", "blocks": []})

        # Write a malformed YAML file directly
        bad_path = env / "project" / "plugins" / "ui" / "templates" / "brain" / "bad.yaml"
        bad_path.write_text(": invalid: yaml: {{{\n  broken", encoding="utf-8")

        result = _list_templates_catalog(hub="brain")

        # Good template is present, bad one is skipped
        ids = [e["id"] for e in result["brain"]]
        assert "good" in ids
        assert "bad" not in ids


# ---------------------------------------------------------------------------
# 13. Hub-disabled blocks auto-enable (Gap #12)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
