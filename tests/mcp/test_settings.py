"""Tests for set-config and get-settings MCP tools (ADR-457).

Tests exercise the public ``set_config_impl`` and ``get_settings_impl``
functions with ``tmp_path``-based file isolation via monkeypatched
``_get_config_dir`` and ``_get_state_dir``.
"""

from __future__ import annotations

import sys

import json
import threading
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import yaml

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def dirs(tmp_path: Path) -> dict[str, Path]:
    """Create and return isolated config_dir and state_dir under tmp_path."""
    config_dir = tmp_path / "config"
    state_dir = tmp_path / "state"
    config_dir.mkdir()
    state_dir.mkdir()
    return {"config": config_dir, "state": state_dir}


@pytest.fixture(autouse=True)
def _patch_dirs(dirs: dict[str, Path]):
    """Redirect settings module path helpers to tmp_path directories."""
    with (
        patch(
            "src.mcp.augur_framework.tools.infrastructure.settings._helpers._get_config_dir",
            return_value=dirs["config"],
        ),
        patch(
            "src.mcp.augur_framework.tools.infrastructure.settings._helpers._get_state_dir",
            return_value=dirs["state"],
        ),
    ):
        yield


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _set(params: dict[str, Any]) -> dict[str, Any]:
    from src.mcp.augur_framework.tools.infrastructure.settings import set_config_impl

    raw = await set_config_impl(params)
    return json.loads(raw)


async def _get(params: dict[str, Any]) -> dict[str, Any]:
    from src.mcp.augur_framework.tools.infrastructure.settings import get_settings_impl

    raw = await get_settings_impl(params)
    return json.loads(raw)


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="Windows file-locking: cannot rename over an open handle during concurrent atomic writes; validation pending (ROADMAP)",
)
def test_write_json_uses_unique_temp_files_under_concurrency(
    dirs: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Concurrent writes to the same target must not collide on a shared temp file."""
    from src.mcp.augur_framework.tools.infrastructure.settings import _helpers

    path = dirs["state"] / "focus_state.json"
    barrier = threading.Barrier(2)
    original_replace = Path.replace

    def synchronized_replace(self: Path, target: Path) -> Path:
        if target == path and self.parent == path.parent and self.suffix == ".tmp":
            barrier.wait(timeout=2)
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", synchronized_replace)

    errors: list[Exception] = []

    def writer(value: int) -> None:
        try:
            _helpers._write_json(path, {"value": value})
        except Exception as exc:  # pragma: no cover - asserted below
            errors.append(exc)

    threads = [
        threading.Thread(target=writer, args=(0,)),
        threading.Thread(target=writer, args=(1,)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors
    assert json.loads(path.read_text())["value"] in {0, 1}


# ===================================================================
# set_config_impl tests
# ===================================================================


class TestSetConfigImpl:
    """Write-side scope handlers."""

    @pytest.mark.asyncio
    async def test_set_preferences(self, dirs: dict[str, Path]) -> None:
        result = await _set({"scope": "preferences", "key": "theme", "value": "dark"})
        assert result["success"] is True
        assert result["key"] == "theme"
        assert result["value"] == "dark"

        # Verify file on disk
        prefs_path = dirs["config"] / "system" / "preferences.yaml"
        assert prefs_path.exists()
        data = yaml.safe_load(prefs_path.read_text())
        assert data["theme"] == "dark"

    @pytest.mark.asyncio
    async def test_set_preferences_missing_key(self) -> None:
        result = await _set({"scope": "preferences", "value": "dark"})
        assert result["success"] is False
        assert "key" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_set_layout_presets(self, dirs: dict[str, Path]) -> None:
        result = await _set({"scope": "layout-presets", "preset": "focus"})
        assert result["success"] is True
        assert result["activePreset"] == "focus"

        data = json.loads((dirs["state"] / "dashboard" / "layout-presets.json").read_text())
        assert data["activePreset"] == "focus"
        assert "updatedAt" in data

    @pytest.mark.asyncio
    async def test_set_layout_reset(self, dirs: dict[str, Path]) -> None:
        # Seed a preset first
        await _set({"scope": "layout-presets", "preset": "wide"})

        result = await _set({"scope": "layout-reset"})
        assert result["success"] is True
        assert result["reset_scope"] == "all"

        data = json.loads((dirs["state"] / "dashboard" / "layout-presets.json").read_text())
        assert data["activePreset"] == "custom"

    @pytest.mark.asyncio
    async def test_set_nav_order_update(self, dirs: dict[str, Path]) -> None:
        result = await _set(
            {
                "scope": "nav-order-update",
                "type": "hub",
                "items": ["career", "life", "system"],
            }
        )
        assert result["success"] is True
        assert result["items"] == ["career", "life", "system"]

        data = json.loads((dirs["state"] / "dashboard" / "nav-order.json").read_text())
        assert data["hubs"] == ["career", "life", "system"]

    @pytest.mark.asyncio
    async def test_set_nav_order_update_invalid_type(self) -> None:
        result = await _set({"scope": "nav-order-update", "type": "invalid", "items": ["a"]})
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_set_skill_nav_toggle(self, dirs: dict[str, Path]) -> None:
        result = await _set(
            {
                "scope": "skill-nav-toggle",
                "skill": "career",
                "visible": False,
                "category": "work",
                "label": "Career",
            }
        )
        assert result["success"] is True
        assert result["skill"] == "career"
        assert result["visible"] is False

        data = json.loads((dirs["state"] / "dashboard" / "skill-nav.json").read_text())
        assert data["skills"]["career"]["visible"] is False
        assert data["skills"]["career"]["category"] == "work"

    @pytest.mark.asyncio
    async def test_set_skill_nav_toggle_missing_params(self) -> None:
        result = await _set({"scope": "skill-nav-toggle", "skill": "x"})
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_set_dashboard_toggle(self, dirs: dict[str, Path]) -> None:
        result = await _set({"scope": "dashboard-toggle", "group_id": "health", "enabled": True})
        assert result["success"] is True
        assert result["group_id"] == "health"
        assert result["enabled"] is True

        data = json.loads((dirs["state"] / "dashboard" / "dashboard-groups.json").read_text())
        assert data["groups"]["health"]["enabled"] is True

    @pytest.mark.asyncio
    async def test_set_dashboard_toggle_missing_params(self) -> None:
        result = await _set({"scope": "dashboard-toggle", "group_id": "health"})
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_set_schedule_create(self, dirs: dict[str, Path]) -> None:
        result = await _set(
            {
                "scope": "schedule-create",
                "plugin": "career",
                "action_id": "sync-jobs",
                "schedule": "0 9 * * *",
                "label": "Daily job sync",
            }
        )
        assert result["success"] is True
        schedule = result["schedule"]
        assert schedule["action_id"] == "sync-jobs"
        assert schedule["plugin"] == "career"
        assert schedule["schedule"] == "0 9 * * *"
        assert "id" in schedule  # UUID generated

        data = json.loads((dirs["state"] / "schedules" / "career" / "schedules.json").read_text())
        assert len(data["schedules"]) == 1

    @pytest.mark.asyncio
    async def test_set_schedule_delete(self, dirs: dict[str, Path]) -> None:
        # Create first
        create_result = await _set(
            {
                "scope": "schedule-create",
                "plugin": "career",
                "action_id": "sync",
                "schedule": "daily",
            }
        )
        schedule_id = create_result["schedule"]["id"]

        # Delete
        result = await _set({"scope": "schedule-delete", "plugin": "career", "id": schedule_id})
        assert result["success"] is True
        assert result["deleted"] is True

        data = json.loads((dirs["state"] / "schedules" / "career" / "schedules.json").read_text())
        assert len(data["schedules"]) == 0

    @pytest.mark.asyncio
    async def test_set_schedule_delete_not_found(self) -> None:
        result = await _set(
            {
                "scope": "schedule-delete",
                "plugin": "career",
                "id": "nonexistent-id",
            }
        )
        assert result["success"] is False
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_set_focus_state(self, dirs: dict[str, Path]) -> None:
        result = await _set(
            {
                "scope": "focus-state",
                "current_page": "/brain",
                "skill_name": "brain",
                "bundle": "brain",
                "session_id": "dashboard-main",
            }
        )
        assert result["success"] is True
        assert result["current_page"] == "/brain"

        focus_state = json.loads((dirs["state"] / "focus_state.json").read_text())
        session_state = json.loads((dirs["state"] / "sessions" / "dashboard-main.json").read_text())
        assert focus_state["skill_name"] == "brain"
        assert session_state["session_id"] == "dashboard-main"

    @pytest.mark.asyncio
    async def test_set_bridge_connection_create(self, dirs: dict[str, Path]) -> None:
        result = await _set(
            {
                "scope": "bridge-connection-create",
                "hub": "career",
                "source_type": "github",
                "source_path": "/repos/augur",
                "integrations": ["pr-review"],
            }
        )
        assert result["success"] is True
        conn = result["connection"]
        assert conn["hub"] == "career"
        assert conn["source_type"] == "github"
        assert "id" in conn

        data = json.loads((dirs["state"] / "bridge" / "career" / "connections.json").read_text())
        assert data["total"] == 1
        assert len(data["connections"]) == 1

    @pytest.mark.asyncio
    async def test_set_bridge_connection_create_missing_hub(self) -> None:
        result = await _set({"scope": "bridge-connection-create"})
        assert result["success"] is False
        assert "hub" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_set_unknown_scope(self) -> None:
        result = await _set({"scope": "does-not-exist"})
        assert result["success"] is False
        assert "Unknown scope" in result["error"]
        assert "available_scopes" in result

    @pytest.mark.asyncio
    async def test_set_missing_scope(self) -> None:
        result = await _set({})
        assert result["success"] is False
        assert "scope" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_set_llm_config(self, dirs: dict[str, Path]) -> None:
        # impl uses profiles-shaped llm.yaml schema (active_profile + profiles);
        # mutation needs `profile` to identify which profile's fields to update.
        system_dir = dirs["config"] / "system"
        system_dir.mkdir(parents=True, exist_ok=True)
        (system_dir / "llm.yaml").write_text(
            "active_profile: default\n"
            "profiles:\n"
            "  default:\n"
            "    provider: openai_compatible\n"
            "    base_url: http://localhost:11434/v1\n"
            "    model: placeholder\n"
        )

        config = {
            "profile": "default",
            "provider": "anthropic",
            "base_url": "https://api.anthropic.com",
            "model": "claude-opus-4-20250514",
        }
        result = await _set({"scope": "llm-config", "config": config})
        assert result["success"] is True

        written = yaml.safe_load((dirs["config"] / "system" / "llm.yaml").read_text())
        assert written["profiles"]["default"]["provider"] == "anthropic"

    @pytest.mark.asyncio
    async def test_set_llm_config_write_raw_yaml(self, dirs: dict[str, Path]) -> None:
        system_dir = dirs["config"] / "system"
        system_dir.mkdir(parents=True, exist_ok=True)
        (system_dir / "llm.yaml").write_text(
            "active_profile: default\n"
            "profiles:\n"
            "  default:\n"
            "    provider: openai_compatible\n"
            "    base_url: http://localhost:11434/v1\n"
            "    model: placeholder\n"
        )

        raw = (
            "active_profile: default\n"
            "profiles:\n"
            "  default:\n"
            "    provider: openai\n"
            "    base_url: https://api.openai.com/v1\n"
            "    model: gpt-4o\n"
        )
        result = await _set({"scope": "llm-config-write", "yaml": raw})
        assert result["success"] is True

        content = (dirs["config"] / "system" / "llm.yaml").read_text()
        assert "openai" in content

    @pytest.mark.asyncio
    async def test_set_llm_config_write_invalid_yaml(self) -> None:
        result = await _set({"scope": "llm-config-write", "yaml": "{{{"})
        assert result["success"] is False
        assert "Invalid YAML" in result["error"]

    @pytest.mark.asyncio
    async def test_set_default_cli(self, dirs: dict[str, Path]) -> None:
        result = await _set({"scope": "default-cli", "default_cli": "claude"})
        assert result["success"] is True

        written = yaml.safe_load((dirs["config"] / "system" / "settings.yaml").read_text())
        assert written["default_cli"] == "claude"

    @pytest.mark.asyncio
    async def test_set_dashboard_remove(self, dirs: dict[str, Path]) -> None:
        # Create a group first
        await _set({"scope": "dashboard-toggle", "group_id": "health", "enabled": True})
        # Remove it
        result = await _set({"scope": "dashboard-remove", "group_id": "health"})
        assert result["success"] is True
        assert result["removed"] is True

        data = json.loads((dirs["state"] / "dashboard" / "dashboard-groups.json").read_text())
        assert "health" not in data["groups"]


# ===================================================================
# get_settings_impl tests
# ===================================================================


class TestGetSettingsImpl:
    """Read-side scope handlers."""

    @pytest.mark.asyncio
    async def test_get_preferences_empty(self) -> None:
        result = await _get({"scope": "preferences"})
        # No file on disk → empty dict
        assert result == {}

    @pytest.mark.asyncio
    async def test_get_preferences_with_key(self, dirs: dict[str, Path]) -> None:
        # Write a preference first
        await _set({"scope": "preferences", "key": "theme", "value": "dark"})
        await _set({"scope": "preferences", "key": "lang", "value": "en"})

        # Read specific key
        result = await _get({"scope": "preferences", "key": "theme"})
        assert result == {"theme": "dark"}

    @pytest.mark.asyncio
    async def test_get_preferences_with_nonexistent_key(self) -> None:
        result = await _get({"scope": "preferences", "key": "nonexistent"})
        assert result == {}

    @pytest.mark.asyncio
    async def test_get_layout_presets_defaults(self) -> None:
        result = await _get({"scope": "layout-presets"})
        assert result["success"] is True
        assert result["activePreset"] == "custom"
        assert isinstance(result["availablePresets"], list)
        assert "focus" in result["availablePresets"]

    @pytest.mark.asyncio
    async def test_get_layout_presets_after_write(self) -> None:
        await _set({"scope": "layout-presets", "preset": "compact"})
        result = await _get({"scope": "layout-presets"})
        assert result["activePreset"] == "compact"

    @pytest.mark.asyncio
    async def test_get_nav_order_empty(self) -> None:
        result = await _get({"scope": "nav-order"})
        assert result == {}

    @pytest.mark.asyncio
    async def test_get_nav_order_after_write(self) -> None:
        await _set(
            {
                "scope": "nav-order-update",
                "type": "hub",
                "items": ["life", "career"],
            }
        )
        result = await _get({"scope": "nav-order"})
        assert result["hubs"] == ["life", "career"]

    @pytest.mark.asyncio
    async def test_get_skill_nav_empty(self) -> None:
        result = await _get({"scope": "skill-nav"})
        assert result == {"skills": []}

    @pytest.mark.asyncio
    async def test_get_skill_nav_after_toggle(self) -> None:
        await _set({"scope": "skill-nav-toggle", "skill": "health", "visible": True})
        result = await _get({"scope": "skill-nav"})
        skills = result["skills"]
        assert len(skills) == 1
        assert skills[0]["skill"] == "health"
        assert skills[0]["visible"] is True

    @pytest.mark.asyncio
    async def test_get_dashboard_groups_empty(self) -> None:
        result = await _get({"scope": "dashboard-groups"})
        assert result == {}

    @pytest.mark.asyncio
    async def test_get_schedules_empty(self) -> None:
        result = await _get({"scope": "schedules"})
        assert result["schedules"] == []

    @pytest.mark.asyncio
    async def test_get_schedules_after_create(self) -> None:
        await _set(
            {
                "scope": "schedule-create",
                "plugin": "health",
                "action_id": "check",
                "schedule": "daily",
            }
        )
        result = await _get({"scope": "schedules", "plugin": "health"})
        assert len(result["schedules"]) == 1
        assert result["schedules"][0]["action_id"] == "check"

    @pytest.mark.asyncio
    async def test_get_schedules_all_plugins(self) -> None:
        await _set(
            {
                "scope": "schedule-create",
                "plugin": "career",
                "action_id": "a",
                "schedule": "daily",
            }
        )
        await _set(
            {
                "scope": "schedule-create",
                "plugin": "health",
                "action_id": "b",
                "schedule": "weekly",
            }
        )
        result = await _get({"scope": "schedules"})
        assert len(result["schedules"]) == 2

    @pytest.mark.asyncio
    async def test_get_schedule_history_empty(self) -> None:
        result = await _get({"scope": "schedule-history"})
        assert result["entries"] == []
        assert result["total_entries"] == 0

    @pytest.mark.asyncio
    async def test_get_llm_config_no_file(self) -> None:
        result = await _get({"scope": "llm-config"})
        assert result["config"] == {}
        assert result["raw"] == ""
        assert "configPath" in result

    @pytest.mark.asyncio
    async def test_get_llm_config_after_write(self, dirs: dict[str, Path]) -> None:
        system_dir = dirs["config"] / "system"
        system_dir.mkdir(parents=True, exist_ok=True)
        (system_dir / "llm.yaml").write_text(
            "active_profile: default\n"
            "profiles:\n"
            "  default:\n"
            "    provider: openai_compatible\n"
            "    base_url: http://localhost:11434/v1\n"
            "    model: placeholder\n"
        )

        config = {
            "profile": "default",
            "provider": "anthropic",
            "base_url": "https://api.anthropic.com",
            "model": "claude-opus-4-20250514",
        }
        await _set({"scope": "llm-config", "config": config})

        result = await _get({"scope": "llm-config"})
        assert result["config"]["profiles"]["default"]["provider"] == "anthropic"
        assert result["effective"]["profiles"]["default"]["model"] == "claude-opus-4-20250514"
        assert "anthropic" in result["raw"]

    @pytest.mark.asyncio
    async def test_get_llm_alias(self) -> None:
        """'llm' scope is an alias for 'llm-config'."""
        result = await _get({"scope": "llm"})
        assert "config" in result

    @pytest.mark.asyncio
    async def test_get_bridge_connections_no_hub(self) -> None:
        result = await _get({"scope": "bridge-connections"})
        assert result["connections"] == []
        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_get_bridge_connections_after_create(self) -> None:
        await _set(
            {
                "scope": "bridge-connection-create",
                "hub": "career",
                "source_type": "github",
                "source_path": "/repos/test",
            }
        )
        result = await _get({"scope": "bridge-connections", "hub": "career"})
        assert result["total"] == 1
        assert result["connections"][0]["source_type"] == "github"

    @pytest.mark.asyncio
    async def test_get_default_cli_empty(self) -> None:
        result = await _get({"scope": "default-cli"})
        assert result["default_cli"] == ""

    @pytest.mark.asyncio
    async def test_get_unknown_scope(self) -> None:
        result = await _get({"scope": "does-not-exist"})
        assert result["success"] is False
        assert "Unknown scope" in result["error"]
        assert "available_scopes" in result

    @pytest.mark.asyncio
    async def test_get_missing_scope(self) -> None:
        result = await _get({})
        assert result["success"] is False
        assert "scope" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_get_nav_visibility_alias(self) -> None:
        """'nav-visibility' is an alias for skill-nav reader."""
        result = await _get({"scope": "nav-visibility"})
        assert "skills" in result

    @pytest.mark.asyncio
    async def test_get_activity_summary(self, dirs: dict[str, Path]) -> None:
        (dirs["state"] / "dashboard").mkdir(parents=True, exist_ok=True)
        (dirs["state"] / "focus_state.json").write_text(
            json.dumps(
                {
                    "current_page": "/brain",
                    "skill_name": "brain",
                    "bundle": "brain",
                    "session_id": "dashboard-main",
                    "timestamp": "2026-03-22T12:00:00",
                    "source": "dashboard",
                }
            )
        )
        (dirs["state"] / "dashboard" / "usage-stats.json").write_text(
            json.dumps(
                {
                    "pages": [
                        {
                            "page": "/brain",
                            "timestamp": "2026-03-22T12:01:00",
                            "action": "view",
                        },
                        {
                            "page": "/brain",
                            "timestamp": "2026-03-22T12:02:00",
                            "action": "reindex-rag",
                        },
                    ]
                }
            )
        )

        with (
            patch(
                "src.mcp.augur_framework.tools.infrastructure.settings._helpers._get_project_root",
                return_value=dirs["state"],
            ),
            patch(
                "src.mcp.augur_framework.tools.infrastructure.settings.dashboard.run",
                side_effect=[
                    type("Result", (), {"stdout": "main\n"})(),
                    type(
                        "Result",
                        (),
                        {"stdout": "Fix activity summary|5 minutes ago\n"},
                    )(),
                ],
            ),
        ):
            result = await _get({"scope": "activity-summary"})

        assert result["focus"]["current_page"] == "/brain"
        assert result["pages"][0]["page"] == "/brain"
        assert result["workflows"][0]["prompt"] == "reindex-rag"
        assert result["dev"]["branch"] == "main"


# ===================================================================
# Round-trip integration tests
# ===================================================================


class TestRoundTrip:
    """Verify write-then-read consistency across scopes."""

    @pytest.mark.asyncio
    async def test_preferences_round_trip(self) -> None:
        await _set({"scope": "preferences", "key": "font_size", "value": 14})
        result = await _get({"scope": "preferences"})
        assert result["font_size"] == 14

    @pytest.mark.asyncio
    async def test_schedule_create_read_delete_read(self) -> None:
        # Create
        create = await _set(
            {
                "scope": "schedule-create",
                "plugin": "test",
                "action_id": "run",
                "schedule": "hourly",
            }
        )
        sid = create["schedule"]["id"]

        # Read — should be present
        read1 = await _get({"scope": "schedules", "plugin": "test"})
        assert any(s["id"] == sid for s in read1["schedules"])

        # Delete
        await _set({"scope": "schedule-delete", "plugin": "test", "id": sid})

        # Read — should be gone
        read2 = await _get({"scope": "schedules", "plugin": "test"})
        assert not any(s["id"] == sid for s in read2["schedules"])

    @pytest.mark.asyncio
    async def test_bridge_create_delete_round_trip(self) -> None:
        create = await _set(
            {
                "scope": "bridge-connection-create",
                "hub": "life",
                "source_type": "notion",
                "source_path": "/workspace",
            }
        )
        cid = create["connection"]["id"]

        read1 = await _get({"scope": "bridge-connections", "hub": "life"})
        assert read1["total"] == 1

        await _set(
            {
                "scope": "bridge-connection-delete",
                "hub": "life",
                "connection_id": cid,
            }
        )

        read2 = await _get({"scope": "bridge-connections", "hub": "life"})
        assert read2["total"] == 0

    @pytest.mark.asyncio
    async def test_layout_preset_set_reset_round_trip(self) -> None:
        await _set({"scope": "layout-presets", "preset": "wide"})
        r1 = await _get({"scope": "layout-presets"})
        assert r1["activePreset"] == "wide"

        await _set({"scope": "layout-reset"})
        r2 = await _get({"scope": "layout-presets"})
        assert r2["activePreset"] == "custom"
