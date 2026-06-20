"""Tests for sync --purge: dry_run mode and purge_mode output."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


class TestBaseAdapterDryRun:
    def test_dry_run_returns_paths_without_deleting(self, tmp_path):
        """dry_run=True reports what would be deleted but leaves files intact."""
# TODO_CLEANUP: This file is 1455 lines — consider splitting into smaller modules
        from sync_agents.adapters.base import BaseAdapter

        class FakeAdapter(BaseAdapter):
            adapter_name = "fake"

            def get_managed_files(self):
                return ["target_file.txt", "target_dir/"]

        (tmp_path / "target_file.txt").write_text("keep me", encoding="utf-8")
        (tmp_path / "target_dir").mkdir()
        (tmp_path / "target_dir" / "child.txt").write_text("also keep me", encoding="utf-8")

        import unittest.mock as mock

        with mock.patch("sync_agents.constants.PROJECT_ROOT", tmp_path):
            adapter = FakeAdapter()
            reported = adapter.cleanup(dry_run=True)

        assert "target_file.txt" in reported
        assert "target_dir/" in reported
        assert (tmp_path / "target_file.txt").exists(), "dry_run must not delete files"
        assert (tmp_path / "target_dir").exists(), "dry_run must not delete dirs"

    def test_dry_run_skips_missing_paths(self, tmp_path):
        """dry_run=True silently skips paths that do not exist."""
        from sync_agents.adapters.base import BaseAdapter

        class FakeAdapter(BaseAdapter):
            adapter_name = "fake"

            def get_managed_files(self):
                return ["nonexistent.txt"]

        import unittest.mock as mock

        with mock.patch("sync_agents.constants.PROJECT_ROOT", tmp_path):
            reported = FakeAdapter().cleanup(dry_run=True)

        assert reported == []

    def test_dry_run_false_still_deletes(self, tmp_path):
        """dry_run=False (default) still performs the actual deletion."""
        from sync_agents.adapters.base import BaseAdapter

        class FakeAdapter(BaseAdapter):
            adapter_name = "fake"

            def get_managed_files(self):
                return ["delete_me.txt"]

        target = tmp_path / "delete_me.txt"
        target.write_text("bye", encoding="utf-8")

        import unittest.mock as mock

        with mock.patch("sync_agents.constants.PROJECT_ROOT", tmp_path):
            FakeAdapter().cleanup(dry_run=False)

        assert not target.exists()


class TestBaseAdapterStateCleanup:
    def test_get_state_files_defaults_to_empty_list(self):
        """BaseAdapter exposes no state files by default."""
        from sync_agents.adapters.base import BaseAdapter

        assert BaseAdapter().get_state_files() == []

    def test_cleanup_state_dry_run_reports_paths_without_deleting(self, tmp_path):
        """cleanup_state(dry_run=True) reports state paths but leaves them intact."""
        from sync_agents.adapters.base import BaseAdapter

        class FakeAdapter(BaseAdapter):
            adapter_name = "fake"

            def get_state_files(self):
                return [str(tmp_path / "state.txt")]

        target = tmp_path / "state.txt"
        target.write_text("keep me", encoding="utf-8")

        reported = FakeAdapter().cleanup_state(dry_run=True)

        assert reported == [str(target)]
        assert target.exists(), "dry_run must not delete state files"

    def test_cleanup_state_deletes_paths_when_not_dry_run(self, tmp_path):
        """cleanup_state(dry_run=False) deletes state paths."""
        from sync_agents.adapters.base import BaseAdapter

        class FakeAdapter(BaseAdapter):
            adapter_name = "fake"

            def get_state_files(self):
                return [str(tmp_path / "state.txt")]

        target = tmp_path / "state.txt"
        target.write_text("remove me", encoding="utf-8")

        reported = FakeAdapter().cleanup_state(dry_run=False)

        assert reported == [str(target)]
        assert not target.exists(), "cleanup_state must delete state files"


class TestCursorAdapterManagedFiles:
    def test_cursor_includes_global_skills_cursor(self):
        """CursorAdapter must manage ~/.cursor/skills-cursor/ for orphan cleanup."""
        from sync_agents.adapters.cursor import CursorAdapter

        managed = CursorAdapter().get_managed_files()
        home = str(Path.home())
        assert f"{home}/.cursor/skills-cursor/" in managed, (
            f"~/.cursor/skills-cursor/ not in managed files: {managed}"
        )

    def test_cursor_dry_run_reports_skills_cursor(self, tmp_path):
        """dry_run reports ~/.cursor/skills-cursor/ when it exists."""
        from sync_agents.adapters.cursor import CursorAdapter
        import unittest.mock as mock

        fake_skills_cursor = tmp_path / ".cursor" / "skills-cursor"
        fake_skills_cursor.mkdir(parents=True)
        (fake_skills_cursor / "create-skill").mkdir()

        adapter = CursorAdapter()

        with mock.patch("sync_agents.adapters.cursor.Path.home", return_value=tmp_path):
            with mock.patch("sync_agents.constants.PROJECT_ROOT", tmp_path):
                with mock.patch("sync_agents.adapters.cursor.PROJECT_ROOT", tmp_path):
                    reported = adapter.cleanup(dry_run=True)

        assert any(".cursor/skills-cursor/" in p for p in reported)
        assert fake_skills_cursor.exists(), "dry_run must not delete"


class TestCursorAdapterStateCleanup:
    def test_reports_and_deletes_cursor_runtime_state(self, tmp_path):
        """cleanup_state() removes Cursor runtime state but leaves unrelated files alone."""
        from sync_agents.adapters.cursor import CursorAdapter
        import unittest.mock as mock

        cursor_home = tmp_path / ".cursor"
        state_paths = [
            cursor_home / "projects",
            cursor_home / "workspaceStorage",
            cursor_home / "User" / "workspaceStorage",
            cursor_home / ".backups",
        ]
        for path in state_paths:
            path.mkdir(parents=True, exist_ok=True)
            (path / "marker.txt").write_text("state", encoding="utf-8")
        settings_file = cursor_home / "mcp.json"
        settings_file.parent.mkdir(parents=True, exist_ok=True)
        settings_file.write_text('{"mcpServers": {"augur": {}}}', encoding="utf-8")

        adapter = CursorAdapter()

        with mock.patch("sync_agents.adapters.cursor.Path.home", return_value=tmp_path):
            reported = adapter.cleanup_state(dry_run=False)

        assert any(p.endswith(".cursor/projects/") for p in reported)
        assert any(p.endswith(".cursor/workspaceStorage/") for p in reported)
        assert any(p.endswith(".cursor/User/workspaceStorage/") for p in reported)
        assert any(p.endswith(".cursor/.backups/") for p in reported)
        assert settings_file.exists(), "cleanup_state must not delete settings/config files"
        for path in state_paths:
            assert not path.exists()


class TestClaudeCodeAdapterCleanup:
    _PLUGIN_KEY = "augur@augur-cowork"

    def _make_plugins_json(self, claude_home: Path, project_path: str, extra: dict | None = None) -> Path:
        data: dict = {
            "version": 2,
            "plugins": {
                self._PLUGIN_KEY: [
                    {"scope": "local", "projectPath": project_path, "version": "2.0.0"}
                ]
            },
        }
        if extra:
            data["plugins"].update(extra)
        target = claude_home / "plugins" / "installed_plugins.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return target

    def _make_cache(self, claude_home: Path) -> Path:
        cache = claude_home / "plugins" / "cache" / "augur-cowork" / "augur" / "2.0.0"
        cache.mkdir(parents=True)
        (cache / "plugin.json").write_text("{}", encoding="utf-8")
        return claude_home / "plugins" / "cache" / "augur-cowork"

    def test_removes_augur_plugin_entry_from_installed_json(self, tmp_path):
        """cleanup() removes augur@augur-cowork from installed_plugins.json."""
        from sync_agents.adapters.claude_code import ClaudeCodeAdapter
        import unittest.mock as mock

        claude_home = tmp_path / ".claude"
        project_root = tmp_path / "project"
        project_root.mkdir()

        target = self._make_plugins_json(claude_home, str(project_root.resolve()))
        adapter = ClaudeCodeAdapter()

        with mock.patch("sync_agents.adapters.claude_code.Path.home", return_value=tmp_path):
            with mock.patch("sync_agents.adapters.claude_code.PROJECT_ROOT", project_root):
                with mock.patch("sync_agents.constants.PROJECT_ROOT", project_root):
                    result = adapter.cleanup(dry_run=False)

        data = json.loads(target.read_text(encoding="utf-8"))
        assert self._PLUGIN_KEY not in data["plugins"], "augur plugin must be removed"
        assert any("installed_plugins.json" in p for p in result)

    def test_preserves_other_plugins_in_installed_json(self, tmp_path):
        """cleanup() keeps non-augur plugin entries intact."""
        from sync_agents.adapters.claude_code import ClaudeCodeAdapter
        import unittest.mock as mock

        claude_home = tmp_path / ".claude"
        project_root = tmp_path / "project"
        project_root.mkdir()

        target = self._make_plugins_json(
            claude_home,
            str(project_root.resolve()),
            extra={"other-plugin@marketplace": [{"scope": "local", "version": "1.0"}]},
        )
        adapter = ClaudeCodeAdapter()

        with mock.patch("sync_agents.adapters.claude_code.Path.home", return_value=tmp_path):
            with mock.patch("sync_agents.adapters.claude_code.PROJECT_ROOT", project_root):
                with mock.patch("sync_agents.constants.PROJECT_ROOT", project_root):
                    adapter.cleanup(dry_run=False)

        data = json.loads(target.read_text(encoding="utf-8"))
        assert "other-plugin@marketplace" in data["plugins"], "other plugins must be preserved"

    def test_deletes_plugin_cache_dir(self, tmp_path):
        """cleanup() removes ~/.claude/plugins/cache/augur-cowork/."""
        from sync_agents.adapters.claude_code import ClaudeCodeAdapter
        import unittest.mock as mock

        claude_home = tmp_path / ".claude"
        project_root = tmp_path / "project"
        project_root.mkdir()

        cache_dir = self._make_cache(claude_home)
        adapter = ClaudeCodeAdapter()

        with mock.patch("sync_agents.adapters.claude_code.Path.home", return_value=tmp_path):
            with mock.patch("sync_agents.adapters.claude_code.PROJECT_ROOT", project_root):
                with mock.patch("sync_agents.constants.PROJECT_ROOT", project_root):
                    result = adapter.cleanup(dry_run=False)

        assert not cache_dir.exists(), "cache dir must be deleted"
        assert any("augur-cowork" in p for p in result)

    def test_dry_run_does_not_modify_installed_json(self, tmp_path):
        """cleanup(dry_run=True) reports paths but leaves installed_plugins.json unchanged."""
        from sync_agents.adapters.claude_code import ClaudeCodeAdapter
        import unittest.mock as mock

        claude_home = tmp_path / ".claude"
        project_root = tmp_path / "project"
        project_root.mkdir()

        target = self._make_plugins_json(claude_home, str(project_root.resolve()))
        original = target.read_text(encoding="utf-8")
        adapter = ClaudeCodeAdapter()

        with mock.patch("sync_agents.adapters.claude_code.Path.home", return_value=tmp_path):
            with mock.patch("sync_agents.adapters.claude_code.PROJECT_ROOT", project_root):
                with mock.patch("sync_agents.constants.PROJECT_ROOT", project_root):
                    reported = adapter.cleanup(dry_run=True)

        assert target.read_text(encoding="utf-8") == original, "dry_run must not modify the file"
        assert any("installed_plugins.json" in p for p in reported)

    def test_dry_run_does_not_delete_cache(self, tmp_path):
        """cleanup(dry_run=True) does not delete the cache dir."""
        from sync_agents.adapters.claude_code import ClaudeCodeAdapter
        import unittest.mock as mock

        claude_home = tmp_path / ".claude"
        project_root = tmp_path / "project"
        project_root.mkdir()

        cache_dir = self._make_cache(claude_home)
        adapter = ClaudeCodeAdapter()

        with mock.patch("sync_agents.adapters.claude_code.Path.home", return_value=tmp_path):
            with mock.patch("sync_agents.adapters.claude_code.PROJECT_ROOT", project_root):
                with mock.patch("sync_agents.constants.PROJECT_ROOT", project_root):
                    adapter.cleanup(dry_run=True)

        assert cache_dir.exists(), "dry_run must not delete cache"

    def test_missing_installed_json_is_silent(self, tmp_path):
        """cleanup() is a no-op when installed_plugins.json does not exist."""
        from sync_agents.adapters.claude_code import ClaudeCodeAdapter
        import unittest.mock as mock

        project_root = tmp_path / "project"
        project_root.mkdir()
        adapter = ClaudeCodeAdapter()

        with mock.patch("sync_agents.adapters.claude_code.Path.home", return_value=tmp_path):
            with mock.patch("sync_agents.adapters.claude_code.PROJECT_ROOT", project_root):
                with mock.patch("sync_agents.constants.PROJECT_ROOT", project_root):
                    result = adapter.cleanup(dry_run=False)

        assert not any("installed_plugins.json" in p for p in result)


class TestClaudeCodeAdapterStateCleanup:
    def test_reports_projects_and_plugin_data_state(self, tmp_path):
        """cleanup_state() removes Claude runtime state but preserves settings."""
        from sync_agents.adapters.claude_code import ClaudeCodeAdapter
        import unittest.mock as mock

        claude_home = tmp_path / ".claude"
        project_state = claude_home / "projects"
        todos_state = claude_home / "todos"
        statsig_state = claude_home / "statsig"
        plugin_data_state = claude_home / "plugins" / "data"
        settings_file = claude_home / "settings.json"

        for path in (project_state, todos_state, statsig_state, plugin_data_state):
            path.mkdir(parents=True, exist_ok=True)
            (path / "marker.txt").write_text("state", encoding="utf-8")
        settings_file.parent.mkdir(parents=True, exist_ok=True)
        settings_file.write_text('{"theme":"dark"}', encoding="utf-8")

        adapter = ClaudeCodeAdapter()

        with mock.patch("sync_agents.adapters.claude_code.Path.home", return_value=tmp_path):
            reported = adapter.cleanup_state(dry_run=False)

        assert any(p.endswith(".claude/projects/") for p in reported)
        assert any(p.endswith(".claude/todos/") for p in reported)
        assert any(p.endswith(".claude/statsig/") for p in reported)
        assert any(p.endswith(".claude/plugins/data/") for p in reported)
        assert settings_file.exists(), "cleanup_state must not delete settings.json"
        assert not project_state.exists()
        assert not todos_state.exists()
        assert not statsig_state.exists()
        assert not plugin_data_state.exists()


class TestGeminiAdapterStateCleanup:
    def test_reports_and_deletes_antigravity_runtime_state(self, tmp_path):
        """cleanup_state() removes repo-local Antigravity runtime state."""
        from sync_agents.adapters.gemini import GeminiAdapter
        import unittest.mock as mock

        gemini_home = tmp_path / ".antigravity"
        state_paths = [
            gemini_home / "history",
            gemini_home / "sessions",
            gemini_home / "cache",
        ]
        for path in state_paths:
            path.mkdir(parents=True, exist_ok=True)
            (path / "marker.txt").write_text("state", encoding="utf-8")
        settings_file = gemini_home / "settings.json"
        settings_file.parent.mkdir(parents=True, exist_ok=True)
        settings_file.write_text('{"theme":"dark"}', encoding="utf-8")

        adapter = GeminiAdapter()

        with mock.patch("sync_agents.adapters.gemini.Path.home", return_value=tmp_path):
            reported = adapter.cleanup_state(dry_run=False)

        assert any(p.endswith(".antigravity/history/") for p in reported)
        assert any(p.endswith(".antigravity/sessions/") for p in reported)
        assert any(p.endswith(".antigravity/cache/") for p in reported)
        assert settings_file.exists(), "cleanup_state must not delete settings.json"
        for path in state_paths:
            assert not path.exists()


class TestAntigravityAdapterStateCleanup:
    def test_reports_and_deletes_antigravity_runtime_state(self, tmp_path):
        """cleanup_state() removes Antigravity runtime state but preserves mcp_config.json."""
        from sync_agents.adapters.antigravity import AntigravityAdapter
        import unittest.mock as mock

        antigravity_home = tmp_path / ".gemini" / "antigravity"
        state_paths = [
            antigravity_home / "brain",
            antigravity_home / "code_tracker",
        ]
        for path in state_paths:
            path.mkdir(parents=True, exist_ok=True)
            (path / "marker.txt").write_text("state", encoding="utf-8")
        config_file = antigravity_home / "mcp_config.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text('{"mcpServers": {"augur": {}}}', encoding="utf-8")

        adapter = AntigravityAdapter()

        with mock.patch("sync_agents.adapters.antigravity.Path.home", return_value=tmp_path):
            reported = adapter.cleanup_state(dry_run=False)

        assert any(p.endswith(".gemini/antigravity/brain/") for p in reported)
        assert any(p.endswith(".gemini/antigravity/code_tracker/") for p in reported)
        assert config_file.exists(), "cleanup_state must not delete mcp_config.json"
        for path in state_paths:
            assert not path.exists()


class TestCoworkAdapterCleanup:
    def _make_cowork_dir(self, runtime_dir: Path, session: str = "session-1", org: str = "org-1") -> Path:
        cowork_dir = (
            runtime_dir
            / "local-agent-mode-sessions"
            / session
            / org
            / "cowork_plugins"
        )
        cowork_dir.mkdir(parents=True)
        return cowork_dir

    def test_removes_legacy_augur_install_manifest(self, tmp_path):
        """cleanup() removes legacy cowork install manifests for Augur."""
        from sync_agents.adapters.cowork import CoworkAdapter
        import unittest.mock as mock

        runtime_dir = tmp_path / "claude-runtime"
        cowork_dir = self._make_cowork_dir(runtime_dir)
        manifest = cowork_dir / ".install-manifests" / "augur@augur-cowork.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text("{}", encoding="utf-8")

        adapter = CoworkAdapter()
        with mock.patch("sync_agents.adapters.cowork.get_client_runtime_dir", return_value=runtime_dir):
            result = adapter.cleanup(dry_run=False)

        assert not manifest.exists(), "legacy Augur install manifest must be removed"
        assert any("augur@augur-cowork.json" in p for p in result)

    def test_removes_legacy_augur_cache_dir(self, tmp_path):
        """cleanup() removes legacy cowork cache/augur-cowork/ leftovers."""
        from sync_agents.adapters.cowork import CoworkAdapter
        import unittest.mock as mock

        runtime_dir = tmp_path / "claude-runtime"
        cowork_dir = self._make_cowork_dir(runtime_dir)
        cache_dir = cowork_dir / "cache" / "augur-cowork" / "augur" / "1.0.0"
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / "plugin.json").write_text("{}", encoding="utf-8")

        adapter = CoworkAdapter()
        with mock.patch("sync_agents.adapters.cowork.get_client_runtime_dir", return_value=runtime_dir):
            result = adapter.cleanup(dry_run=False)

        assert not (cowork_dir / "cache" / "augur-cowork").exists(), (
            "legacy Augur cowork cache must be removed"
        )
        assert any("cache/augur-cowork" in p for p in result)

    def test_dry_run_reports_legacy_cowork_leftovers_without_deleting(self, tmp_path):
        """cleanup(dry_run=True) reports legacy cowork leftovers but preserves them."""
        from sync_agents.adapters.cowork import CoworkAdapter
        import unittest.mock as mock

        runtime_dir = tmp_path / "claude-runtime"
        cowork_dir = self._make_cowork_dir(runtime_dir)
        manifest = cowork_dir / ".install-manifests" / "augur@augur-cowork.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text("{}", encoding="utf-8")
        cache_dir = cowork_dir / "cache" / "augur-cowork" / "augur" / "1.0.0"
        cache_dir.mkdir(parents=True, exist_ok=True)

        adapter = CoworkAdapter()
        with mock.patch("sync_agents.adapters.cowork.get_client_runtime_dir", return_value=runtime_dir):
            reported = adapter.cleanup(dry_run=True)

        assert manifest.exists(), "dry_run must not delete the legacy install manifest"
        assert (cowork_dir / "cache" / "augur-cowork").exists(), (
            "dry_run must not delete the legacy cache dir"
        )
        assert any("augur@augur-cowork.json" in p for p in reported)
        assert any("cache/augur-cowork" in p for p in reported)

    def test_cleanup_discovers_and_cleans_all_cowork_plugin_roots(self, tmp_path):
        """cleanup() should remove leftovers from every cowork_plugins tree under runtime."""
        from sync_agents.adapters.cowork import CoworkAdapter
        import unittest.mock as mock

        runtime_dir = tmp_path / "claude-runtime"
        first_root = self._make_cowork_dir(runtime_dir, session="session-1", org="org-1")
        second_root = self._make_cowork_dir(runtime_dir, session="session-2", org="org-2")

        for root in (first_root, second_root):
            manifest = root / ".install-manifests" / "augur@augur-cowork.json"
            manifest.parent.mkdir(parents=True, exist_ok=True)
            manifest.write_text("{}", encoding="utf-8")
            cache_dir = root / "cache" / "augur-cowork" / "augur" / "1.0.0"
            cache_dir.mkdir(parents=True, exist_ok=True)

        adapter = CoworkAdapter()

        with mock.patch("sync_agents.adapters.cowork.Path.home", side_effect=AssertionError("Path.home should not be used")):
            with mock.patch("sync_agents.adapters.cowork.get_client_runtime_dir", return_value=runtime_dir):
                reported = adapter.cleanup(dry_run=False)

        for root in (first_root, second_root):
            assert not (root / ".install-manifests" / "augur@augur-cowork.json").exists()
            assert not (root / "cache" / "augur-cowork").exists()
        assert sum("augur@augur-cowork.json" in path for path in reported) == 2
        assert sum("cache/augur-cowork" in path for path in reported) == 2


class TestCoworkAdapterStateCleanup:
    def _make_cowork_dir(self, runtime_dir: Path, session: str = "session-1", org: str = "org-1") -> Path:
        return (
            runtime_dir
            / "local-agent-mode-sessions"
            / session
            / org
            / "cowork_plugins"
        )

    def test_get_state_files_returns_empty_when_plugin_dir_missing(self, tmp_path):
        """get_state_files() returns [] when Cowork plugin data cannot be found."""
        from sync_agents.adapters.cowork import CoworkAdapter
        import unittest.mock as mock

        adapter = CoworkAdapter()

        with mock.patch("sync_agents.adapters.cowork.get_client_runtime_dir", return_value=tmp_path / "claude-runtime"):
            assert adapter.get_state_files() == []

    def test_reports_and_deletes_cowork_runtime_state(self, tmp_path):
        """cleanup_state() removes Cowork runtime state but preserves Claude config."""
        from sync_agents.adapters.cowork import CoworkAdapter
        import unittest.mock as mock

        runtime_dir = tmp_path / "claude-runtime"
        cowork_dir = self._make_cowork_dir(runtime_dir)
        state_paths = [
            cowork_dir / "cache",
            cowork_dir / "runtime-memory",
            cowork_dir / "session-history",
        ]
        for path in state_paths:
            path.mkdir(parents=True, exist_ok=True)
            (path / "marker.txt").write_text("state", encoding="utf-8")
        config_file = runtime_dir / "claude_desktop_config.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        original_config = '{"mcpServers": {"augur": {"command": "python3"}}, "theme": "dark"}'
        config_file.write_text(original_config, encoding="utf-8")

        adapter = CoworkAdapter()

        with mock.patch("sync_agents.adapters.cowork.Path.home", side_effect=AssertionError("Path.home should not be used")):
            with mock.patch("sync_agents.adapters.cowork.get_client_runtime_dir", return_value=runtime_dir):
                reported = adapter.cleanup_state(dry_run=False)

        assert reported == [
            f"{cowork_dir}/cache/",
            f"{cowork_dir}/runtime-memory/",
            f"{cowork_dir}/session-history/",
        ]
        assert config_file.read_text(encoding="utf-8") == original_config
        for path in state_paths:
            assert not path.exists()

    def test_cleanup_state_discovers_all_cowork_plugin_roots(self, tmp_path):
        """cleanup_state() should purge every Cowork runtime tree under Claude Desktop."""
        from sync_agents.adapters.cowork import CoworkAdapter
        import unittest.mock as mock

        runtime_dir = tmp_path / "claude-runtime"
        first_root = self._make_cowork_dir(runtime_dir, session="session-1", org="org-1")
        second_root = self._make_cowork_dir(runtime_dir, session="session-2", org="org-2")

        for root in (first_root, second_root):
            for subdir in ("cache", "runtime-memory", "session-history"):
                path = root / subdir
                path.mkdir(parents=True, exist_ok=True)
                (path / "marker.txt").write_text("state", encoding="utf-8")

        adapter = CoworkAdapter()

        with mock.patch("sync_agents.adapters.cowork.Path.home", side_effect=AssertionError("Path.home should not be used")):
            with mock.patch("sync_agents.adapters.cowork.get_client_runtime_dir", return_value=runtime_dir):
                reported = adapter.cleanup_state(dry_run=False)

        expected = {
            f"{first_root}/cache/",
            f"{first_root}/runtime-memory/",
            f"{first_root}/session-history/",
            f"{second_root}/cache/",
            f"{second_root}/runtime-memory/",
            f"{second_root}/session-history/",
        }
        assert set(reported) == expected
        for root in (first_root, second_root):
            for subdir in ("cache", "runtime-memory", "session-history"):
                assert not (root / subdir).exists()


class TestCodexAdapterCleanup:
    """Global ~/.codex/config.toml is surgically edited; local .codex/config.toml is deleted.

    Tests use separate directories: codex_home/ for the global config, project/ for
    PROJECT_ROOT so the local .codex/config.toml is distinct from the global one.
    """

    def _make_global_config(self, codex_home: Path, extra_servers: dict | None = None) -> Path:
        """Write a minimal global config.toml with an augur MCP entry."""
        servers = {"augur": {"command": "/bin/zsh", "args": ["-lc", "exec python3"]}}
        if extra_servers:
            servers.update(extra_servers)
        lines = ['model = "gpt-5.4"\n', "[mcp_servers]\n"]
        for name, cfg in servers.items():
            lines.append(f"\n[mcp_servers.{name}]\n")
            for k, v in cfg.items():
                if isinstance(v, list):
                    formatted = "[" + ", ".join(f'"{i}"' for i in v) + "]"
                    lines.append(f"{k} = {formatted}\n")
                else:
                    lines.append(f'{k} = "{v}"\n')
        target = codex_home / "config.toml"
        codex_home.mkdir(parents=True, exist_ok=True)
        target.write_text("".join(lines), encoding="utf-8")
        return target

    def test_removes_augur_entry_preserves_other_servers(self, tmp_path):
        """cleanup() removes mcp_servers.augur from global config but keeps other entries."""
        from sync_agents.adapters.codex import CodexAdapter
        import unittest.mock as mock

        codex_home = tmp_path / "codex_home"
        project_root = tmp_path / "project"
        project_root.mkdir()

        target = self._make_global_config(codex_home, extra_servers={"other": {"command": "npx"}})
        adapter = CodexAdapter()

        with mock.patch("sync_agents.adapters.codex.CODEX_HOME", codex_home):
            with mock.patch("sync_agents.constants.PROJECT_ROOT", project_root):
                result = adapter.cleanup(dry_run=False)

        assert target.exists(), "global config must not be deleted when other servers remain"
        content = target.read_text(encoding="utf-8")
        assert "augur" not in content, "augur entry must be removed"
        assert "other" in content, "other server must be preserved"
        assert any("config.toml" in p for p in result)

    def test_removes_mcp_servers_section_when_augur_is_only_entry(self, tmp_path):
        """cleanup() drops [mcp_servers] from global config when augur is the only server."""
        from sync_agents.adapters.codex import CodexAdapter
        import unittest.mock as mock

        codex_home = tmp_path / "codex_home"
        project_root = tmp_path / "project"
        project_root.mkdir()

        target = self._make_global_config(codex_home)
        adapter = CodexAdapter()

        with mock.patch("sync_agents.adapters.codex.CODEX_HOME", codex_home):
            with mock.patch("sync_agents.constants.PROJECT_ROOT", project_root):
                adapter.cleanup(dry_run=False)

        content = target.read_text(encoding="utf-8")
        assert "augur" not in content
        assert "mcp_servers" not in content
        assert 'model = "gpt-5.4"' in content, "non-MCP keys must survive"

    def test_dry_run_does_not_modify_global_config(self, tmp_path):
        """cleanup(dry_run=True) reports the global config path but leaves it unchanged."""
        from sync_agents.adapters.codex import CodexAdapter
        import unittest.mock as mock

        codex_home = tmp_path / "codex_home"
        project_root = tmp_path / "project"
        project_root.mkdir()

        target = self._make_global_config(codex_home)
        original = target.read_text(encoding="utf-8")
        adapter = CodexAdapter()

        with mock.patch("sync_agents.adapters.codex.CODEX_HOME", codex_home):
            with mock.patch("sync_agents.constants.PROJECT_ROOT", project_root):
                reported = adapter.cleanup(dry_run=True)

        assert target.read_text(encoding="utf-8") == original, "dry_run must not modify the file"
        assert any("config.toml" in p for p in reported)

    def test_missing_global_config_is_silent(self, tmp_path):
        """cleanup() does not report global config.toml when it does not exist."""
        from sync_agents.adapters.codex import CodexAdapter
        import unittest.mock as mock

        codex_home = tmp_path / "codex_home"
        project_root = tmp_path / "project"
        project_root.mkdir()

        adapter = CodexAdapter()
        with mock.patch("sync_agents.adapters.codex.CODEX_HOME", codex_home):
            with mock.patch("sync_agents.constants.PROJECT_ROOT", project_root):
                result = adapter.cleanup(dry_run=False)

        assert not any(str(codex_home / "config.toml") in p for p in result)

    def test_global_config_without_augur_is_untouched(self, tmp_path):
        """cleanup() leaves global config.toml unchanged when there is no augur entry."""
        from sync_agents.adapters.codex import CodexAdapter
        import unittest.mock as mock

        codex_home = tmp_path / "codex_home"
        codex_home.mkdir()
        project_root = tmp_path / "project"
        project_root.mkdir()

        target = codex_home / "config.toml"
        target.write_text('model = "gpt-5.4"\n', encoding="utf-8")
        original = target.read_text(encoding="utf-8")
        adapter = CodexAdapter()

        with mock.patch("sync_agents.adapters.codex.CODEX_HOME", codex_home):
            with mock.patch("sync_agents.constants.PROJECT_ROOT", project_root):
                result = adapter.cleanup(dry_run=False)

        assert target.read_text(encoding="utf-8") == original
        assert not any(str(target) in p for p in result)

    def test_local_config_deleted_during_purge(self, tmp_path):
        """cleanup() deletes local .codex/config.toml (it is Augur-managed)."""
        from sync_agents.adapters.codex import CodexAdapter
        import unittest.mock as mock

        codex_home = tmp_path / "codex_home"
        project_root = tmp_path / "project"
        local_config = project_root / ".codex" / "config.toml"
        local_config.parent.mkdir(parents=True)
        local_config.write_text('approval_policy = "never"\n', encoding="utf-8")

        adapter = CodexAdapter()
        with mock.patch("sync_agents.adapters.codex.CODEX_HOME", codex_home):
            with mock.patch("sync_agents.constants.PROJECT_ROOT", project_root):
                adapter.cleanup(dry_run=False)

        assert not local_config.exists(), "local .codex/config.toml must be deleted by purge"


class TestCodexAdapterStateCleanup:
    def test_reports_runtime_state_from_codex_home_but_not_config(self, tmp_path):
        """cleanup_state() removes Codex runtime state under CODEX_HOME while preserving config.toml."""
        from sync_agents.adapters.codex import CodexAdapter
        import unittest.mock as mock

        codex_home = tmp_path / ".codex"
        unrelated_home = tmp_path / "unrelated-home"
        sessions_state = codex_home / "sessions"
        history_state = codex_home / "history"
        transcripts_state = codex_home / "transcripts"
        tmp_state = codex_home / ".tmp"
        global_state = codex_home / ".codex-global-state.json"
        config_file = codex_home / "config.toml"

        for path in (sessions_state, history_state, transcripts_state, tmp_state):
            path.mkdir(parents=True, exist_ok=True)
            (path / "marker.txt").write_text("state", encoding="utf-8")
        global_state.parent.mkdir(parents=True, exist_ok=True)
        global_state.write_text('{"client":"codex"}', encoding="utf-8")
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text('model = "gpt-5.4"\n', encoding="utf-8")

        adapter = CodexAdapter()

        with mock.patch("sync_agents.adapters.codex.Path.home", return_value=unrelated_home):
            with mock.patch("sync_agents.adapters.codex.CODEX_HOME", codex_home):
                with mock.patch("sync_agents.constants.CODEX_HOME", codex_home):
                    reported = adapter.cleanup_state(dry_run=False)

        assert any(p.endswith(".codex/sessions/") for p in reported)
        assert any(p.endswith(".codex/history/") for p in reported)
        assert any(p.endswith(".codex/transcripts/") for p in reported)
        assert any(p.endswith(".codex/.tmp/") for p in reported)
        assert any(p.endswith(".codex/.codex-global-state.json") for p in reported)
        assert config_file.exists(), "cleanup_state must not delete config.toml"
        assert not sessions_state.exists()
        assert not history_state.exists()
        assert not transcripts_state.exists()
        assert not tmp_state.exists()
        assert not global_state.exists()

    def test_does_not_follow_unrelated_home_when_codex_home_differs(self, tmp_path):
        """cleanup_state() ignores Path.home() when CODEX_HOME points elsewhere."""
        from sync_agents.adapters.codex import CodexAdapter
        import unittest.mock as mock

        codex_home = tmp_path / "codex-home"
        unrelated_home = tmp_path / ".codex"
        state_dir = codex_home / "sessions"
        config_file = codex_home / "config.toml"

        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / "marker.txt").write_text("state", encoding="utf-8")
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text('model = "gpt-5.4"\n', encoding="utf-8")

        adapter = CodexAdapter()

        with mock.patch("sync_agents.adapters.codex.Path.home", return_value=unrelated_home):
            with mock.patch("sync_agents.adapters.codex.CODEX_HOME", codex_home):
                with mock.patch("sync_agents.constants.CODEX_HOME", codex_home):
                    reported = adapter.cleanup_state(dry_run=False)

        assert any(str(codex_home / "sessions") in p for p in reported)
        assert not (unrelated_home / "sessions").exists()
        assert config_file.exists(), "cleanup_state must not delete config.toml"


class TestCodexLocalConfigSync:
    def test_creates_local_config_toml_when_missing(self, tmp_path):
        """_sync_local_codex_config() creates .codex/config.toml with project settings."""
        from sync_agents.adapters.codex import CodexAdapter
        import unittest.mock as mock

        adapter = CodexAdapter()
        with mock.patch("sync_agents.adapters.codex.CODEX_HOME", tmp_path / ".codex_home"):
            with mock.patch("sync_agents.adapters.codex.PROJECT_ROOT", tmp_path):
                with mock.patch("sync_agents.constants.PROJECT_ROOT", tmp_path):
                    with mock.patch("sync_agents.adapters.codex.GENERATED_FILES", []):
                        adapter._sync_local_codex_config()

        target = tmp_path / ".codex" / "config.toml"
        assert target.exists()
        content = target.read_text(encoding="utf-8")
        assert "approval_policy" in content
        assert "never" in content
        assert "sandbox_mode" in content
        assert "danger-full-access" in content

    def test_preserves_existing_keys_when_updating(self, tmp_path):
        """_sync_local_codex_config() keeps user-added keys alongside Augur settings."""
        from sync_agents.adapters.codex import CodexAdapter
        import unittest.mock as mock

        target = tmp_path / ".codex" / "config.toml"
        target.parent.mkdir(parents=True)
        target.write_text('model = "gpt-5.4"\n', encoding="utf-8")

        adapter = CodexAdapter()
        with mock.patch("sync_agents.adapters.codex.CODEX_HOME", tmp_path / ".codex_home"):
            with mock.patch("sync_agents.adapters.codex.PROJECT_ROOT", tmp_path):
                with mock.patch("sync_agents.constants.PROJECT_ROOT", tmp_path):
                    with mock.patch("sync_agents.adapters.codex.GENERATED_FILES", []):
                        adapter._sync_local_codex_config()

        content = target.read_text(encoding="utf-8")
        assert 'model = "gpt-5.4"' in content
        assert "approval_policy" in content
        assert "sandbox_mode" in content

    def test_no_op_when_settings_already_correct(self, tmp_path):
        """_sync_local_codex_config() skips write when settings are already in place."""
        from sync_agents.adapters.codex import CodexAdapter
        import unittest.mock as mock

        target = tmp_path / ".codex" / "config.toml"
        target.parent.mkdir(parents=True)
        target.write_text(
            'approval_policy = "never"\nsandbox_mode = "danger-full-access"\n',
            encoding="utf-8",
        )
        mtime_before = target.stat().st_mtime

        adapter = CodexAdapter()
        with mock.patch("sync_agents.adapters.codex.CODEX_HOME", tmp_path / ".codex_home"):
            with mock.patch("sync_agents.adapters.codex.PROJECT_ROOT", tmp_path):
                with mock.patch("sync_agents.constants.PROJECT_ROOT", tmp_path):
                    with mock.patch("sync_agents.adapters.codex.GENERATED_FILES", []):
                        adapter._sync_local_codex_config()

        assert target.stat().st_mtime == mtime_before, "file must not be rewritten if up to date"

    def test_local_config_in_managed_files(self):
        """get_managed_files() includes .codex/config.toml so purge removes it."""
        from sync_agents.adapters.codex import CodexAdapter

        managed = CodexAdapter().get_managed_files()
        assert ".codex/config.toml" in managed


class TestOpenCodeAdapterCleanup:
    def _make_config(self, tmp_path, extra_mcp: dict | None = None) -> Path:
        config = {
            "$schema": "https://opencode.ai/config.json",
            "mcp": {"augur": {"type": "local", "command": ["python3"]}},
        }
        if extra_mcp:
            config["mcp"].update(extra_mcp)
        target = tmp_path / ".config" / "opencode" / "opencode.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(config, indent=2), encoding="utf-8")
        return target

    def test_removes_augur_key_preserves_other_mcp(self, tmp_path):
        """cleanup() removes mcp.augur but keeps other MCP entries."""
        from sync_agents.adapters.opencode import OpenCodeAdapter
        import unittest.mock as mock

        target = self._make_config(tmp_path, extra_mcp={"context7": {"command": "npx"}})
        adapter = OpenCodeAdapter()

        with mock.patch("sync_agents.adapters.opencode.Path.home", return_value=tmp_path):
            with mock.patch("sync_agents.constants.PROJECT_ROOT", tmp_path):
                with mock.patch("sync_agents.adapters.opencode.PROJECT_ROOT", tmp_path):
                    adapter.cleanup(dry_run=False)

        assert target.exists(), "file must not be deleted when other MCP entries exist"
        data = json.loads(target.read_text(encoding="utf-8"))
        assert "augur" not in data.get("mcp", {}), "augur key must be removed"
        assert "context7" in data.get("mcp", {}), "context7 must be preserved"

    def test_deletes_file_when_augur_is_only_mcp(self, tmp_path):
        """cleanup() deletes the file when augur is the only MCP entry."""
        from sync_agents.adapters.opencode import OpenCodeAdapter
        import unittest.mock as mock

        target = self._make_config(tmp_path)
        adapter = OpenCodeAdapter()

        with mock.patch("sync_agents.adapters.opencode.Path.home", return_value=tmp_path):
            with mock.patch("sync_agents.constants.PROJECT_ROOT", tmp_path):
                with mock.patch("sync_agents.adapters.opencode.PROJECT_ROOT", tmp_path):
                    adapter.cleanup(dry_run=False)

        assert not target.exists(), "file must be deleted when augur is the only MCP entry"

    def test_dry_run_does_not_edit_file(self, tmp_path):
        """cleanup(dry_run=True) does not modify the file."""
        from sync_agents.adapters.opencode import OpenCodeAdapter
        import unittest.mock as mock

        target = self._make_config(tmp_path, extra_mcp={"context7": {"command": "npx"}})
        original = target.read_text(encoding="utf-8")
        adapter = OpenCodeAdapter()

        with mock.patch("sync_agents.adapters.opencode.Path.home", return_value=tmp_path):
            with mock.patch("sync_agents.constants.PROJECT_ROOT", tmp_path):
                with mock.patch("sync_agents.adapters.opencode.PROJECT_ROOT", tmp_path):
                    reported = adapter.cleanup(dry_run=True)

        assert target.read_text(encoding="utf-8") == original, "dry_run must not modify the file"
        assert any("opencode.json" in p for p in reported)

    def test_missing_file_is_silent(self, tmp_path):
        """cleanup() is a no-op when opencode.json does not exist."""
        from sync_agents.adapters.opencode import OpenCodeAdapter
        import unittest.mock as mock

        adapter = OpenCodeAdapter()
        with mock.patch("sync_agents.adapters.opencode.Path.home", return_value=tmp_path):
            with mock.patch("sync_agents.constants.PROJECT_ROOT", tmp_path):
                with mock.patch("sync_agents.adapters.opencode.PROJECT_ROOT", tmp_path):
                    result = adapter.cleanup(dry_run=False)

        assert result == []


class TestOpenCodeAdapterStateCleanup:
    def test_reports_and_deletes_opencode_runtime_state(self, tmp_path):
        """cleanup_state() removes OpenCode runtime state but preserves opencode.json."""
        from sync_agents.adapters.opencode import OpenCodeAdapter
        import unittest.mock as mock

        opencode_home = tmp_path / ".local" / "share" / "opencode"
        state_paths = [
            opencode_home / "history",
            opencode_home / "sessions",
            tmp_path / ".cache" / "opencode",
        ]
        for path in state_paths:
            path.mkdir(parents=True, exist_ok=True)
            (path / "marker.txt").write_text("state", encoding="utf-8")
        config_file = tmp_path / ".config" / "opencode" / "opencode.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        original_config = '{"mcp": {"augur": {"enabled": true}}, "theme": "midnight"}'
        config_file.write_text(original_config, encoding="utf-8")

        adapter = OpenCodeAdapter()

        with mock.patch("sync_agents.adapters.opencode.Path.home", return_value=tmp_path):
            reported = adapter.cleanup_state(dry_run=False)

        assert reported == [
            f"{tmp_path}/.local/share/opencode/history/",
            f"{tmp_path}/.local/share/opencode/sessions/",
            f"{tmp_path}/.cache/opencode/",
        ]
        assert config_file.read_text(encoding="utf-8") == original_config
        for path in state_paths:
            assert not path.exists()


class TestKimiAdapterStateCleanup:
    def test_reports_and_deletes_kimi_runtime_state(self, tmp_path):
        """cleanup_state() removes Kimi runtime state but preserves mcp.json."""
        from sync_agents.adapters.kimi import KimiAdapter
        import unittest.mock as mock

        kimi_home = tmp_path / ".kimi"
        state_paths = [
            kimi_home / "history",
            kimi_home / "sessions",
            kimi_home / "cache",
        ]
        for path in state_paths:
            path.mkdir(parents=True, exist_ok=True)
            (path / "marker.txt").write_text("state", encoding="utf-8")
        config_file = kimi_home / "mcp.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        original_config = '{"mcpServers": {"augur": {"enabled": true}}, "profile": "work"}'
        config_file.write_text(original_config, encoding="utf-8")

        adapter = KimiAdapter()

        with mock.patch("sync_agents.adapters.kimi.Path.home", return_value=tmp_path):
            reported = adapter.cleanup_state(dry_run=False)

        assert reported == [
            f"{tmp_path}/.kimi/history/",
            f"{tmp_path}/.kimi/sessions/",
            f"{tmp_path}/.kimi/cache/",
        ]
        assert config_file.read_text(encoding="utf-8") == original_config
        for path in state_paths:
            assert not path.exists()


class TestWindsurfAdapterStateCleanup:
    def test_reports_and_deletes_windsurf_runtime_state(self, tmp_path):
        """cleanup_state() removes Windsurf runtime state but preserves mcp.json."""
        from sync_agents.adapters.windsurf import WindsurfAdapter
        import unittest.mock as mock

        windsurf_home = tmp_path / "home" / ".windsurf"
        project_root = tmp_path / "project"
        state_paths = [
            windsurf_home / "history",
            windsurf_home / "sessions",
            windsurf_home / "cache",
        ]
        for path in state_paths:
            path.mkdir(parents=True, exist_ok=True)
            (path / "marker.txt").write_text("state", encoding="utf-8")
        config_file = project_root / ".windsurf" / "mcp.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        original_config = '{"mcpServers": {"augur": {"command": "python3"}}, "workspace": "project"}'
        config_file.write_text(original_config, encoding="utf-8")

        adapter = WindsurfAdapter()

        with mock.patch("sync_agents.adapters.windsurf.Path.home", return_value=tmp_path / "home"):
            with mock.patch("sync_agents.constants.PROJECT_ROOT", project_root):
                with mock.patch("sync_agents.adapters.windsurf.PROJECT_ROOT", project_root):
                    reported = adapter.cleanup_state(dry_run=False)

        assert reported == [
            f"{tmp_path / 'home'}/.windsurf/history/",
            f"{tmp_path / 'home'}/.windsurf/sessions/",
            f"{tmp_path / 'home'}/.windsurf/cache/",
        ]
        assert config_file.read_text(encoding="utf-8") == original_config
        for path in state_paths:
            assert not path.exists()


class TestPurgeMode:
    def test_dry_run_prints_report_without_deleting(self, tmp_path, capsys):
        """purge_mode(dry_run=True) prints per-client report, deletes nothing."""
        from sync_agents.modes import purge_mode
        import unittest.mock as mock
        from sync_agents.adapters.base import BaseAdapter

        class ControlledAdapter(BaseAdapter):
            adapter_name = "test_client"

            def get_managed_files(self):
                return ["fake_file.txt"]

        target = tmp_path / "fake_file.txt"
        target.write_text("should survive", encoding="utf-8")

        with mock.patch("sync_agents.engine._get_all_adapters", return_value=[ControlledAdapter()]):
            with mock.patch("sync_agents.constants.PROJECT_ROOT", tmp_path):
                result = purge_mode(dry_run=True)

        assert result == 0
        assert target.exists(), "dry_run must not delete files"
        out = capsys.readouterr().out
        assert "DRY RUN" in out
        assert "test_client" in out
        assert "fake_file.txt" in out

    def test_confirm_deletes_files(self, tmp_path, capsys):
        """purge_mode(dry_run=False) actually deletes managed files."""
        from sync_agents.modes import purge_mode
        import unittest.mock as mock
        from sync_agents.adapters.base import BaseAdapter

        class ControlledAdapter(BaseAdapter):
            adapter_name = "test_client"

            def get_managed_files(self):
                return ["delete_me.txt"]

        target = tmp_path / "delete_me.txt"
        target.write_text("gone", encoding="utf-8")

        with mock.patch("sync_agents.engine._get_all_adapters", return_value=[ControlledAdapter()]):
            # Adapter file resolution reads constants.PROJECT_ROOT while the
            # llms-removal path reads the directly-imported modes.PROJECT_ROOT;
            # patch both or purge runs against the real repo root.
            with mock.patch("sync_agents.constants.PROJECT_ROOT", tmp_path), mock.patch(
                "sync_agents.modes.PROJECT_ROOT", tmp_path
            ):
                result = purge_mode(dry_run=False)

        assert result == 0
        assert not target.exists()
        out = capsys.readouterr().out
        assert "COMPLETE" in out

    def test_empty_adapter_not_printed(self, tmp_path, capsys):
        """Adapters with nothing to delete are omitted from the report."""
        from sync_agents.modes import purge_mode
        import unittest.mock as mock
        from sync_agents.adapters.base import BaseAdapter

        class EmptyAdapter(BaseAdapter):
            adapter_name = "empty_client"

            def get_managed_files(self):
                return []

        with mock.patch("sync_agents.engine._get_all_adapters", return_value=[EmptyAdapter()]):
            with mock.patch("sync_agents.constants.PROJECT_ROOT", tmp_path):
                purge_mode(dry_run=True)

        out = capsys.readouterr().out
        assert "empty_client" not in out


class TestPurgeStateMode:
    def test_dry_run_reports_state_without_deleting(self, tmp_path, capsys):
        """purge_state_mode(dry_run=True) reports state files and preserves them."""
        from sync_agents.modes import purge_state_mode
        import unittest.mock as mock
        from sync_agents.adapters.base import BaseAdapter

        class ControlledAdapter(BaseAdapter):
            adapter_name = "codex"

            def get_state_files(self):
                return ["state.json"]

        target = tmp_path / "state.json"
        target.write_text("keep me", encoding="utf-8")

        with mock.patch("sync_agents.engine._get_all_adapters", return_value=[ControlledAdapter()]):
            with mock.patch("sync_agents.constants.PROJECT_ROOT", tmp_path):
                result = purge_state_mode(selected_clients=None, dry_run=True)

        assert result == 0
        assert target.exists(), "dry_run must not delete state files"
        out = capsys.readouterr().out
        assert "AUGUR STATE PURGE — DRY RUN" in out
        assert "codex" in out
        assert "state.json" in out
        assert "Run with --confirm to execute." in out

    def test_selected_clients_filters_adapters(self, tmp_path, capsys):
        """purge_state_mode(selected_clients=...) skips unselected adapters."""
        from sync_agents.modes import purge_state_mode
        import unittest.mock as mock
        from sync_agents.adapters.base import BaseAdapter

        class SelectedAdapter(BaseAdapter):
            adapter_name = "codex"

            def __init__(self):
                self.calls = 0

            def cleanup_state(self, dry_run: bool = False):
                self.calls += 1
                return ["selected.state"]

        class SkippedAdapter(BaseAdapter):
            adapter_name = "gemini"

            def __init__(self):
                self.calls = 0

            def cleanup_state(self, dry_run: bool = False):
                self.calls += 1
                return ["skipped.state"]

        selected = SelectedAdapter()
        skipped = SkippedAdapter()

        with mock.patch("sync_agents.engine._get_all_adapters", return_value=[selected, skipped]):
            with mock.patch("sync_agents.constants.PROJECT_ROOT", tmp_path):
                result = purge_state_mode(selected_clients={"codex"}, dry_run=True)

        assert result == 0
        assert selected.calls == 1
        assert skipped.calls == 0
        out = capsys.readouterr().out
        assert "codex" in out
        assert "gemini" not in out

    def test_claude_selection_expands_to_concrete_adapters(self, tmp_path, capsys):
        """purge_state_mode(selected_clients={'claude'}) reaches both Claude adapters."""
        from sync_agents.modes import purge_state_mode
        import unittest.mock as mock
        from sync_agents.adapters.base import BaseAdapter

        class ClaudeCodeAdapter(BaseAdapter):
            adapter_name = "claude_code"

            def __init__(self):
                self.calls = 0

            def cleanup_state(self, dry_run: bool = False):
                self.calls += 1
                return ["claude_code.state"]

        class ClaudeDesktopAdapter(BaseAdapter):
            adapter_name = "claude_desktop"

            def __init__(self):
                self.calls = 0

            def cleanup_state(self, dry_run: bool = False):
                self.calls += 1
                return ["claude_desktop.state"]

        claude_code = ClaudeCodeAdapter()
        claude_desktop = ClaudeDesktopAdapter()

        with mock.patch(
            "sync_agents.engine._get_all_adapters",
            return_value=[claude_code, claude_desktop],
        ):
            with mock.patch("sync_agents.constants.PROJECT_ROOT", tmp_path):
                result = purge_state_mode(selected_clients={"claude"}, dry_run=True)

        assert result == 0
        assert claude_code.calls == 1
        assert claude_desktop.calls == 1
        out = capsys.readouterr().out
        assert "claude_code" in out
        assert "claude_desktop" in out


class TestPurgeCLI:
    def test_purge_flag_triggers_dry_run(self, monkeypatch):
        """sync all --purge calls purge_mode(dry_run=True)."""
        from sync_agents import main
        import unittest.mock as mock

        with mock.patch("sync_agents.purge_mode") as mock_purge:
            mock_purge.return_value = 0
            monkeypatch.setattr("sys.argv", ["sync_agents", "sync", "all", "--purge"])
            main()

        mock_purge.assert_called_once_with(dry_run=True)

    def test_purge_confirm_triggers_execute(self, monkeypatch):
        """sync all --purge --confirm calls purge_mode(dry_run=False)."""
        from sync_agents import main
        import unittest.mock as mock

        with mock.patch("sync_agents.purge_mode") as mock_purge:
            mock_purge.return_value = 0
            monkeypatch.setattr(
                "sys.argv",
                ["sync_agents", "sync", "all", "--purge", "--confirm"],
            )
            main()

        mock_purge.assert_called_once_with(dry_run=False)

    def test_sync_without_purge_unchanged(self, monkeypatch):
        """sync all without --purge calls sync_all, not purge_mode."""
        from sync_agents import main
        import unittest.mock as mock

        with mock.patch("sync_agents.sync_all") as mock_sync, mock.patch(
            "sync_agents.purge_mode"
        ) as mock_purge:
            mock_sync.return_value = 0
            monkeypatch.setattr("sys.argv", ["sync_agents", "sync", "all"])
            main()

        mock_sync.assert_called_once()
        mock_purge.assert_not_called()


class TestPurgeDocs:
    def test_module_doc_mentions_purge_state_examples(self):
        """sync_agents __init__ usage text includes --purge-state examples."""
        project_root = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])

        text = (
            project_root / "project-brain/capabilities/skills/ai/scripts/sync_agents/__init__.py"
        ).read_text(encoding="utf-8")

        assert "python -m skills.ai.scripts.sync_agents sync all --purge-state" in text
        assert (
            "python -m skills.ai.scripts.sync_agents sync all --purge-state --confirm" in text
        )
        assert (
            "python -m skills.ai.scripts.sync_agents sync all --purge-state --clients claude,codex"
            in text
        )

    def test_command_doc_mentions_purge_state_mode(self):
        """sync-agents command doc explains --purge and --purge-state."""
        project_root = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])

        text = (
            project_root / "project-brain/capabilities/skills/ai/commands/sync-agents.md"
        ).read_text(encoding="utf-8")
        normalized = text.replace("`", "")

        assert "--purge for Augur-managed artifacts only" in normalized
        assert "--purge-state for supported client state reset while preserving settings/config" in normalized


class TestPurgeStateCLI:
    def test_purge_state_defaults_to_dry_run(self, monkeypatch):
        """sync all --purge-state routes to purge_state_mode(dry_run=True)."""
        from sync_agents import main
        import unittest.mock as mock

        with mock.patch("sync_agents.purge_state_mode", create=True) as mock_purge_state:
            mock_purge_state.return_value = 0
            monkeypatch.setattr("sys.argv", ["sync_agents", "sync", "all", "--purge-state"])
            main()

        mock_purge_state.assert_called_once_with(selected_clients=None, dry_run=True)

    def test_purge_state_with_confirm_executes(self, monkeypatch):
        """sync all --purge-state --confirm routes to purge_state_mode(dry_run=False)."""
        from sync_agents import main
        import unittest.mock as mock

        with mock.patch("sync_agents.purge_state_mode", create=True) as mock_purge_state:
            mock_purge_state.return_value = 0
            monkeypatch.setattr(
                "sys.argv",
                ["sync_agents", "sync", "all", "--purge-state", "--confirm"],
            )
            main()

        mock_purge_state.assert_called_once_with(selected_clients=None, dry_run=False)

    def test_purge_and_purge_state_conflict(self, monkeypatch, capsys):
        """sync all --purge --purge-state is rejected with SystemExit(2)."""
        from sync_agents import main

        monkeypatch.setattr(
            "sys.argv",
            ["sync_agents", "sync", "all", "--purge", "--purge-state"],
        )

        with pytest.raises(SystemExit) as excinfo:
            main()

        assert excinfo.value.code == 2
        assert "--purge and --purge-state cannot be used together" in capsys.readouterr().err

    def test_purge_state_cli_dispatches_real_mode(self, monkeypatch, capsys):
        """sync all --purge-state now dispatches the real state purge mode."""
        from sync_agents import main
        import unittest.mock as mock

        with mock.patch("sync_agents.engine._get_all_adapters", return_value=[]):
            monkeypatch.setattr("sys.argv", ["sync_agents", "sync", "all", "--purge-state"])
            result = main()

        assert result == 0
        assert "AUGUR STATE PURGE — DRY RUN" in capsys.readouterr().out

    def test_purge_state_rejected_for_sync_agents(self, monkeypatch, capsys):
        """sync agents --purge-state is rejected with SystemExit(2)."""
        from sync_agents import main

        monkeypatch.setattr("sys.argv", ["sync_agents", "sync", "agents", "--purge-state"])

        with pytest.raises(SystemExit) as excinfo:
            main()

        assert excinfo.value.code == 2
        assert "--purge-state requires sync all" in capsys.readouterr().err

    def test_clients_without_purge_state_are_rejected(self, monkeypatch, capsys):
        """sync all --clients codex is rejected with SystemExit(2)."""
        from sync_agents import main
        import unittest.mock as mock

        with mock.patch("sync_agents.sync_all") as mock_sync:
            mock_sync.return_value = 0
            monkeypatch.setattr("sys.argv", ["sync_agents", "sync", "all", "--clients", "codex"])
            with pytest.raises(SystemExit) as excinfo:
                main()

        assert excinfo.value.code == 2
        assert "--clients is only valid with --purge-state" in capsys.readouterr().err
        mock_sync.assert_not_called()

    def test_purge_state_with_clients_routes_subset(self, monkeypatch):
        """sync all --purge-state --clients ... routes a selected client set."""
        from sync_agents import main
        import unittest.mock as mock

        with mock.patch("sync_agents.purge_state_mode", create=True) as mock_purge_state:
            mock_purge_state.return_value = 0
            monkeypatch.setattr(
                "sys.argv",
                [
                    "sync_agents",
                    "sync",
                    "all",
                    "--purge-state",
                    "--clients",
                    "claude,codex,cursor",
                ],
            )
            main()

        mock_purge_state.assert_called_once_with(
            selected_clients={"claude", "codex", "cursor"},
            dry_run=True,
        )
