import yaml
# TODO_CLEANUP: This file is 1263 lines — consider splitting into smaller modules
"""Tests for adapter lifecycle methods (ADR-219)."""

import importlib.util as _augur_importlib_util
import sys as _augur_sys
from pathlib import Path as _AugurPath

_augur_bootstrap_start = _AugurPath(__file__).resolve()
for _augur_bootstrap_parent in (_augur_bootstrap_start.parent, *_augur_bootstrap_start.parents):
    _augur_bootstrap_path = _augur_bootstrap_parent / "daemon" / "scripts" / "bootstrap_paths.py"
    if _augur_bootstrap_path.is_file():
        break
else:
    raise RuntimeError(f"Unable to locate shared skill bootstrap from {_augur_bootstrap_start}")

_augur_bootstrap_spec = _augur_importlib_util.spec_from_file_location(
    "_augur_shared_bootstrap_paths", _augur_bootstrap_path
)
if _augur_bootstrap_spec is None or _augur_bootstrap_spec.loader is None:
    raise RuntimeError(f"Unable to load shared skill bootstrap from {_augur_bootstrap_path}")
_augur_bootstrap_module = _augur_importlib_util.module_from_spec(_augur_bootstrap_spec)
_augur_sys.modules[_augur_bootstrap_spec.name] = _augur_bootstrap_module
_augur_bootstrap_spec.loader.exec_module(_augur_bootstrap_module)
_augur_bootstrap_module.ensure_project_paths(__file__)
import json
import os
import subprocess
import sys
import textwrap
import tomllib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

# Ensure sync_agents package is importable
scripts_dir = Path(__file__).resolve().parents[2]
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

import pytest
from sync_agents.adapters.base import BaseAdapter
from sync_agents.adapters.claude_code import ClaudeCodeAdapter
from sync_agents.adapters.cursor import CursorAdapter
from sync_agents.adapters.windsurf import WindsurfAdapter
from sync_agents.adapters.cline import ClineAdapter
from sync_agents.adapters.copilot import CopilotAdapter
from sync_agents.adapters.gemini import GeminiAdapter
from sync_agents.adapters.opencode import OpenCodeAdapter
from sync_agents.adapters.kimi import KimiAdapter
from sync_agents.adapters.antigravity import AntigravityAdapter
from sync_agents.adapters.codex import CodexAdapter, _build_codex_mcp_entry
from sync_agents.adapters.cowork import CoworkAdapter
from sync_agents.adapters.codex_plugin import CodexPluginAdapter
from sync_agents.adapters.copilot_plugin import CopilotPluginAdapter
from sync_agents.adapters.gemini_plugin import GeminiPluginAdapter
from src.cli_config.codex_runtime import build_codex_mcp_entry
from src.lib.frontmatter_utils import parse_frontmatter

ALL_ADAPTERS = [
    ClaudeCodeAdapter,
    CursorAdapter,
    WindsurfAdapter,
    ClineAdapter,
    CopilotAdapter,
    GeminiAdapter,
    OpenCodeAdapter,
    KimiAdapter,
    AntigravityAdapter,
    CodexAdapter,
    CoworkAdapter,
    CodexPluginAdapter,
    CopilotPluginAdapter,
    GeminiPluginAdapter,
]


def _patch_capability_exports(
    monkeypatch, capability_type: str, exports: dict[str, tuple[str, ...]]
) -> None:
    from src.lib.capabilities import export_filter
    from src.lib.capabilities.discovery import capability_id
    from src.lib.capabilities.exposure_policy import (
        CapabilityDiscovery,
        resolve_capability_records,
    )

    records = [
        CapabilityDiscovery(
            id=capability_id(capability_type, name),
            type=capability_type,
            current_exposure=("agents-md", "browse"),
        )
        for name in exports
    ]
    policy = {
        "capabilities": {
            capability_id(capability_type, name): {
                "classification_status": "approved",
                "export_to": list(targets),
            }
            for name, targets in exports.items()
        }
    }

    resolved = resolve_capability_records(records, policy=policy)
    monkeypatch.setattr(
        export_filter,
        "_resolved_records_by_id",
        lambda: {record.id: record for record in resolved},
    )


def _patch_mcp_policy_records(monkeypatch, *records: SimpleNamespace) -> None:
    monkeypatch.setattr(
        "src.cli_config.manifest.resolve_capability_records",
        lambda _discovered, *, policy=None: list(records),
    )


def _write_split_mcp_manifest(project_root: Path) -> None:
    manifest_path = project_root / "config" / "system" / "mcp_servers.yaml"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        textwrap.dedent(
            """\
            project_tier:
              - id: augur-core
                command: python
                args: [-m, augur_core]
                cwd_required: true
                env:
                  PYTHONPATH: "${AUGUR_ROOT}:${AUGUR_ROOT}/src/mcp"
                  PYTHONUNBUFFERED: "1"
                per_client_args:
                  claude: ["--client-id", "claude"]
                  codex: ["--client-id", "codex"]
                  gemini: ["--client-id", "gemini"]
              - id: augur-framework
                command: python
                args: [-m, augur_framework]
                cwd_required: true
                env:
                  PYTHONPATH: "${AUGUR_ROOT}:${AUGUR_ROOT}/src/mcp"
                  PYTHONUNBUFFERED: "1"
                per_client_args:
                  claude: ["--client-id", "claude"]
                  codex: ["--client-id", "codex"]
                  gemini: ["--client-id", "gemini"]
            vault_tier: []
            monolith_exclusions: []
            """
        ),
        encoding="utf-8",
    )


class TestBaseAdapterLifecycle:
    def test_base_get_managed_files_returns_empty(self):
        adapter = BaseAdapter()
        assert adapter.get_managed_files() == []

    def test_base_cleanup_returns_empty(self):
        adapter = BaseAdapter()
        assert adapter.cleanup() == []

    def test_base_detect_installed_returns_false(self):
        adapter = BaseAdapter()
        assert adapter.detect_installed() is False

    def test_base_adapter_name_is_empty(self):
        adapter = BaseAdapter()
        assert adapter.adapter_name == ""

    def test_cleanup_prunes_empty_parent_directories_inside_repo(self, tmp_path):
        class DummyAdapter(BaseAdapter):
            def get_managed_files(self) -> list[str]:
                return [".cursor/rules/"]

        managed_dir = tmp_path / ".cursor" / "rules"
        managed_dir.mkdir(parents=True)
        (managed_dir / "prompt.md").write_text("prompt\n", encoding="utf-8")

        with patch("sync_agents.constants.PROJECT_ROOT", tmp_path):
            deleted = DummyAdapter().cleanup()

        assert deleted == [".cursor/rules/"]
        assert not managed_dir.exists()
        assert not (tmp_path / ".cursor").exists()

    def test_cleanup_preserves_excluded_shared_paths(self, tmp_path):
        class DummyAdapter(BaseAdapter):
            def get_managed_files(self) -> list[str]:
                return ["CLAUDE.md", ".cursor/rules/"]

        managed_file = tmp_path / "CLAUDE.md"
        managed_file.write_text("rules\n", encoding="utf-8")
        managed_dir = tmp_path / ".cursor" / "rules"
        managed_dir.mkdir(parents=True)
        (managed_dir / "prompt.md").write_text("prompt\n", encoding="utf-8")

        with patch("sync_agents.constants.PROJECT_ROOT", tmp_path):
            deleted = DummyAdapter().cleanup(exclude_paths={managed_file})

        assert deleted == [".cursor/rules/"]
        assert managed_file.exists()
        assert not managed_dir.exists()


class TestCoworkAdapter:
    def test_plugin_pack_scripts_dir_prefers_live_skill_payload(self, tmp_path):
        from sync_agents.adapters.cowork import _plugin_pack_scripts_dir
        skill_dir = tmp_path / "project-brain" / "capabilities" / "skills" / "plugin-pack"
        scripts_dir = skill_dir / "scripts"
        scripts_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("---\nname: plugin-pack\n---\n", encoding="utf-8")

        assert _plugin_pack_scripts_dir(tmp_path) == scripts_dir

    def test_plugin_pack_scripts_dir_raises_when_missing(self, tmp_path):
        from sync_agents.adapters.cowork import _plugin_pack_scripts_dir
        with pytest.raises(FileNotFoundError, match="plugin-pack skill payload not found"):
            _plugin_pack_scripts_dir(tmp_path)

    def test_adapter_name(self):
        assert CoworkAdapter().adapter_name == "cowork"

    def test_cleanup_noop_when_nothing_present(self, tmp_path):
        adapter = CoworkAdapter()
        adapter._output_dir = tmp_path / "build" / "cowork"
        with patch("sync_agents.adapters.cowork._find_cowork_plugin_dirs", return_value=[]), \
             patch("sync_agents.adapters.cowork.get_client_runtime_dir", return_value=tmp_path / "runtime"):
            assert adapter.cleanup(dry_run=True) == []

    def test_cleanup_removes_augur_cowork_leftovers_without_touching_other_plugins(self, tmp_path):
        runtime_dir = tmp_path / "claude-runtime"
        cowork_dir = (
            runtime_dir
            / "local-agent-mode-sessions"
            / "session-1"
            / "org-1"
            / "cowork_plugins"
        )

        augur_upload = cowork_dir / "marketplaces" / "local-desktop-app-uploads" / "augur"
        unrelated_upload = (
            cowork_dir / "marketplaces" / "local-desktop-app-uploads" / "other-plugin"
        )
        legacy_augur_cache = cowork_dir / "cache" / "augur-cowork"
        unrelated_cache = cowork_dir / "cache" / "other-plugin"
        augur_manifest = cowork_dir / ".install-manifests" / "augur@augur-cowork.json"
        upload_manifest = (
            cowork_dir
            / ".install-manifests"
            / "augur@local-desktop-app-uploads.json"
        )
        unrelated_manifest = cowork_dir / ".install-manifests" / "vendor@other-plugin.json"

        for commands_dir in (
            augur_upload / "commands",
            legacy_augur_cache / "augur" / "1.0.0" / "commands",
            unrelated_upload / "commands",
            unrelated_cache / "other" / "1.0.0" / "commands",
        ):
            commands_dir.mkdir(parents=True)
            (commands_dir / "ask.md").write_text("command\n", encoding="utf-8")

        augur_manifest.parent.mkdir(parents=True, exist_ok=True)
        augur_manifest.write_text("{}", encoding="utf-8")
        upload_manifest.write_text("{}", encoding="utf-8")
        unrelated_manifest.write_text("{}", encoding="utf-8")

        installed_plugins = cowork_dir / "installed_plugins.json"
        installed_plugins.write_text(
            json.dumps(
                {
                    "plugins": {
                        "augur@local-desktop-app-uploads": [{"version": "2.0.0"}],
                        "augur@augur-cowork": [{"version": "1.0.0"}],
                        "vendor@other-plugin": [{"version": "3.0.0"}],
                    },
                    "metadata": {"preserve": True},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        claude_config = runtime_dir / "claude_desktop_config.json"
        claude_config.parent.mkdir(parents=True, exist_ok=True)
        claude_config.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "augur": {"command": "uv", "args": ["run", "augur"]},
                        "other": {"command": "node", "args": ["server.js"]},
                    },
                    "globalShortcut": "keep",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        adapter = CoworkAdapter()
        adapter._output_dir = tmp_path / "build" / "cowork"

        with patch("sync_agents.adapters.cowork.get_client_runtime_dir", return_value=runtime_dir):
            deleted = adapter.cleanup()

        assert not augur_upload.exists()
        assert not legacy_augur_cache.exists()
        assert not augur_manifest.exists()
        assert not upload_manifest.exists()

        assert unrelated_upload.exists()
        assert unrelated_cache.exists()
        assert unrelated_manifest.exists()

        remaining_plugins = json.loads(installed_plugins.read_text(encoding="utf-8"))
        assert remaining_plugins == {
            "plugins": {
                "vendor@other-plugin": [{"version": "3.0.0"}],
            },
            "metadata": {"preserve": True},
        }

        remaining_config = json.loads(claude_config.read_text(encoding="utf-8"))
        assert remaining_config == {
            "mcpServers": {
                "other": {"command": "node", "args": ["server.js"]},
            },
            "globalShortcut": "keep",
        }

        assert str(augur_upload) + "/" in deleted
        assert str(legacy_augur_cache) + "/" in deleted
        assert str(augur_manifest) in deleted
        assert str(upload_manifest) in deleted
        assert str(installed_plugins) in deleted
        assert str(claude_config) in deleted

    def test_cleanup_honors_exclude_paths_for_all_managed_cowork_paths(self, tmp_path):
        runtime_dir = tmp_path / "claude-runtime"
        cowork_dir = (
            runtime_dir
            / "local-agent-mode-sessions"
            / "session-1"
            / "org-1"
            / "cowork_plugins"
        )

        augur_upload = cowork_dir / "marketplaces" / "local-desktop-app-uploads" / "augur"
        upload_command = augur_upload / "commands" / "ask.md"
        legacy_augur_cache = cowork_dir / "cache" / "augur-cowork"
        augur_manifest = cowork_dir / ".install-manifests" / "augur@augur-cowork.json"
        upload_manifest = (
            cowork_dir
            / ".install-manifests"
            / "augur@local-desktop-app-uploads.json"
        )
        output_dir = tmp_path / "build" / "cowork"

        for path in (upload_command, legacy_augur_cache / "augur" / "1.0.0" / "plugin.json"):
            path.parent.mkdir(parents=True)
            path.write_text("{}", encoding="utf-8")

        augur_manifest.parent.mkdir(parents=True, exist_ok=True)
        augur_manifest.write_text("{}", encoding="utf-8")
        upload_manifest.write_text("{}", encoding="utf-8")
        (output_dir / "plugins" / "augur").mkdir(parents=True)

        installed_plugins = cowork_dir / "installed_plugins.json"
        installed_plugins.write_text(
            json.dumps(
                {
                    "plugins": {
                        "augur@local-desktop-app-uploads": [{"version": "2.0.0"}],
                        "augur@augur-cowork": [{"version": "1.0.0"}],
                    }
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        claude_config = runtime_dir / "claude_desktop_config.json"
        claude_config.parent.mkdir(parents=True, exist_ok=True)
        claude_config.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "augur": {"command": "uv", "args": ["run", "augur"]},
                    }
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        adapter = CoworkAdapter()
        adapter._output_dir = output_dir

        excluded = {
            output_dir,
            upload_command,
            cowork_dir / "cache",
            augur_manifest.parent,
            installed_plugins,
            claude_config,
        }
        with patch("sync_agents.adapters.cowork.get_client_runtime_dir", return_value=runtime_dir):
            deleted = adapter.cleanup(exclude_paths=excluded)

        assert deleted == []
        assert output_dir.exists()
        assert augur_upload.exists()
        assert legacy_augur_cache.exists()
        assert augur_manifest.exists()
        assert upload_manifest.exists()

        remaining_plugins = json.loads(installed_plugins.read_text(encoding="utf-8"))
        assert "augur@local-desktop-app-uploads" in remaining_plugins["plugins"]
        assert "augur@augur-cowork" in remaining_plugins["plugins"]

        remaining_config = json.loads(claude_config.read_text(encoding="utf-8"))
        assert "augur" in remaining_config["mcpServers"]

    def test_cleanup_dry_run_reports_json_edits_without_mutating_files(self, tmp_path):
        runtime_dir = tmp_path / "claude-runtime"
        cowork_dir = (
            runtime_dir
            / "local-agent-mode-sessions"
            / "session-1"
            / "org-1"
            / "cowork_plugins"
        )
        cowork_dir.mkdir(parents=True)

        installed_plugins = cowork_dir / "installed_plugins.json"
        installed_plugins_payload = {
            "plugins": {
                "augur@local-desktop-app-uploads": [{"version": "2.0.0"}],
                "augur@augur-cowork": [{"version": "1.0.0"}],
                "vendor@other-plugin": [{"version": "3.0.0"}],
            },
            "metadata": {"preserve": True},
        }
        installed_plugins.write_text(
            json.dumps(installed_plugins_payload, indent=2) + "\n",
            encoding="utf-8",
        )

        claude_config = runtime_dir / "claude_desktop_config.json"
        claude_config.parent.mkdir(parents=True, exist_ok=True)
        claude_config_payload = {
            "mcpServers": {
                "augur": {"command": "uv", "args": ["run", "augur"]},
                "other": {"command": "node", "args": ["server.js"]},
            },
            "globalShortcut": "keep",
        }
        claude_config.write_text(
            json.dumps(claude_config_payload, indent=2) + "\n",
            encoding="utf-8",
        )

        adapter = CoworkAdapter()
        adapter._output_dir = tmp_path / "build" / "cowork"

        with patch("sync_agents.adapters.cowork.get_client_runtime_dir", return_value=runtime_dir):
            deleted = adapter.cleanup(dry_run=True)

        assert str(installed_plugins) in deleted
        assert str(claude_config) in deleted
        assert json.loads(installed_plugins.read_text(encoding="utf-8")) == installed_plugins_payload
        assert json.loads(claude_config.read_text(encoding="utf-8")) == claude_config_payload


class TestCodexPluginAdapter:
    def test_plugin_pack_scripts_dir_raises_when_missing(self, tmp_path):
        from sync_agents.adapters.codex_plugin import _plugin_pack_scripts_dir
        with pytest.raises(FileNotFoundError, match="plugin-pack skill payload not found"):
            _plugin_pack_scripts_dir(tmp_path)

    def test_adapter_name(self):
        assert CodexPluginAdapter().adapter_name == "codex_plugin"

    def test_cleanup_noop_when_nothing_present(self, tmp_path):
        adapter = CodexPluginAdapter()
        adapter._output_dir = tmp_path / "build" / "codex"
        with patch("sync_agents.adapters.codex_plugin.PROJECT_ROOT", tmp_path), \
             patch("sync_agents.adapters.codex_plugin.CODEX_HOME", tmp_path / "home" / ".codex"):
            assert adapter.cleanup(dry_run=True) == []

    def test_cleanup_removes_codex_home_plugin_cache(self, tmp_path):
        project_root = tmp_path / "project"
        codex_home = tmp_path / "home" / ".codex"
        runtime_cache = codex_home / "plugins" / "cache" / "augur-local"
        runtime_cache.mkdir(parents=True)
        (runtime_cache / "marker.txt").write_text("stale", encoding="utf-8")

        adapter = CodexPluginAdapter()
        adapter._output_dir = project_root / "build" / "codex"

        with patch("sync_agents.adapters.codex_plugin.PROJECT_ROOT", project_root), \
             patch("sync_agents.adapters.codex_plugin.CODEX_HOME", codex_home):
            deleted = adapter.cleanup()

        assert str(runtime_cache) + "/" in deleted
        assert not runtime_cache.exists()

    def test_generate_mcp_config_refreshes_codex_home_plugin_cache(self, tmp_path):
        calls = []

        def assemble(target, output_dir):
            calls.append(("assemble", target, str(output_dir)))
            return output_dir, "skills-latest"

        def install(target, output_dir, version, **kwargs):
            calls.append(
                (
                    "install",
                    target,
                    str(output_dir),
                    version,
                    {key: str(value) for key, value in sorted(kwargs.items())},
                )
            )

        module = SimpleNamespace(assemble=assemble, install=install)
        scripts_dir = tmp_path / "pack"
        codex_home = tmp_path / "home" / ".codex"
        adapter = CodexPluginAdapter()
        adapter._output_dir = tmp_path / "build" / "codex"

        with patch.dict("sys.modules", {"plugin_assembler": module}), \
             patch("sync_agents.adapters.codex_plugin._plugin_pack_scripts_dir", return_value=scripts_dir), \
             patch("sync_agents.adapters.codex_plugin.PROJECT_ROOT", tmp_path), \
             patch("sync_agents.adapters.codex_plugin.CODEX_HOME", codex_home, create=True):
            adapter.generate_mcp_config()

        assert calls == [
            ("assemble", "codex", str(adapter._output_dir)),
            ("install", "codex", str(adapter._output_dir), "skills-latest", {}),
            (
                "install",
                "codex",
                str(adapter._output_dir),
                "skills-latest",
                {
                    "cache_dir": str(codex_home / "plugins" / "cache"),
                    "global_marketplace_dir": str(tmp_path / ".agents" / "plugins"),
                },
            ),
        ]


class TestGeminiPluginAdapter:
    def test_plugin_pack_scripts_dir_raises_when_missing(self, tmp_path):
        from sync_agents.adapters.gemini_plugin import _plugin_pack_scripts_dir

        with pytest.raises(
            FileNotFoundError, match="plugin-pack skill payload not found"
        ):
            _plugin_pack_scripts_dir(tmp_path, checkout_root=tmp_path / "missing-checkout")

    def test_plugin_pack_scripts_dir_prefers_checkout_skill_payload(self, tmp_path):
        from sync_agents.adapters.gemini_plugin import _plugin_pack_scripts_dir

        stable_root = tmp_path / "stable"
        stale_scripts = stable_root / "project-brain" / "capabilities" / "skills" / "plugin-pack" / "scripts"
        stale_scripts.mkdir(parents=True)
        (stable_root / "project-brain" / "capabilities" / "skills" / "plugin-pack" / "SKILL.md").write_text(
            "---\nname: plugin-pack\n---\n",
            encoding="utf-8",
        )

        checkout_root = tmp_path / "checkout"
        current_scripts = checkout_root / "project-brain" / "capabilities" / "skills" / "plugin-pack" / "scripts"
        current_scripts.mkdir(parents=True)
        (checkout_root / "project-brain" / "capabilities" / "skills" / "plugin-pack" / "SKILL.md").write_text(
            "---\nname: plugin-pack\n---\n",
            encoding="utf-8",
        )

        assert _plugin_pack_scripts_dir(stable_root, checkout_root=checkout_root) == current_scripts

    def test_adapter_name(self):
        assert GeminiPluginAdapter().adapter_name == "gemini_plugin"

    def test_detect_installed_uses_gemini_binary_or_home_dir(self, tmp_path):
        with patch("sync_agents.adapters.gemini_plugin.shutil.which", return_value=None), \
             patch("sync_agents.adapters.gemini_plugin.Path.home", return_value=tmp_path / "home"):
            assert GeminiPluginAdapter().detect_installed() is False

        gemini_home = tmp_path / "home" / ".antigravity"
        gemini_home.mkdir(parents=True)
        with patch("sync_agents.adapters.gemini_plugin.shutil.which", return_value=None), \
             patch("sync_agents.adapters.gemini_plugin.Path.home", return_value=tmp_path / "home"):
            assert GeminiPluginAdapter().detect_installed() is True

        with patch("sync_agents.adapters.gemini_plugin.shutil.which", return_value="/usr/bin/gemini"), \
             patch("sync_agents.adapters.gemini_plugin.Path.home", return_value=tmp_path / "empty-home"):
            assert GeminiPluginAdapter().detect_installed() is True

    def test_get_managed_files_include_build_and_extension_dir(self, tmp_path):
        home_dir = tmp_path / "home"
        with patch("sync_agents.adapters.gemini_plugin.Path.home", return_value=home_dir), \
             patch("sync_agents.adapters.gemini_plugin.PROJECT_ROOT", tmp_path):
            adapter = GeminiPluginAdapter()
            files = adapter.get_managed_files()

        assert any(p.endswith("build/gemini/") for p in files)
        assert any(
            p.endswith(str(home_dir / ".antigravity" / "plugins" / "augur") + "/")
            for p in files
        )

    def test_cleanup_noop_when_nothing_present(self, tmp_path):
        adapter = GeminiPluginAdapter()
        adapter._output_dir = tmp_path / "build" / "gemini"
        with patch("sync_agents.adapters.gemini_plugin.PROJECT_ROOT", tmp_path), \
             patch("sync_agents.adapters.gemini_plugin.Path.home", return_value=tmp_path / "home"):
            assert adapter.cleanup(dry_run=True) == []

    def test_cleanup_removes_build_and_extension(self, tmp_path):
        adapter = GeminiPluginAdapter()
        adapter._output_dir = tmp_path / "build" / "gemini"
        extension_dir = tmp_path / "home" / ".antigravity" / "plugins" / "augur"
        other_extension_dir = tmp_path / "home" / ".antigravity" / "plugins" / "other"
        adapter._output_dir.mkdir(parents=True)
        extension_dir.mkdir(parents=True)
        other_extension_dir.mkdir(parents=True)
        (extension_dir / "plugin.json").write_text("{}", encoding="utf-8")
        (other_extension_dir / "plugin.json").write_text("{}", encoding="utf-8")

        with patch("sync_agents.adapters.gemini_plugin.PROJECT_ROOT", tmp_path), \
             patch("sync_agents.adapters.gemini_plugin.Path.home", return_value=tmp_path / "home"):
            deleted = adapter.cleanup()

        assert (str(adapter._output_dir) + "/") in deleted
        assert str(extension_dir) + "/" in deleted
        assert not adapter._output_dir.exists()
        assert not extension_dir.exists()
        assert other_extension_dir.exists()

    def test_cleanup_removes_file_extension_path(self, tmp_path):
        adapter = GeminiPluginAdapter()
        adapter._output_dir = tmp_path / "build" / "gemini"
        extension_file = tmp_path / "home" / ".antigravity" / "plugins" / "augur"
        extension_file.parent.mkdir(parents=True)
        extension_file.write_text("not a directory", encoding="utf-8")

        with patch("sync_agents.adapters.gemini_plugin.Path.home", return_value=tmp_path / "home"):
            deleted = adapter.cleanup()

        assert str(extension_file) + "/" in deleted
        assert not extension_file.exists()

    def test_cleanup_preserves_excluded_extension_path(self, tmp_path):
        adapter = GeminiPluginAdapter()
        adapter._output_dir = tmp_path / "build" / "gemini"
        extension_dir = tmp_path / "home" / ".antigravity" / "plugins" / "augur"
        extension_dir.mkdir(parents=True)
        (extension_dir / "marker.txt").write_text("extension", encoding="utf-8")
        excluded = Path(str(extension_dir).replace("/private/var", "/var"))

        with patch("sync_agents.adapters.gemini_plugin.Path.home", return_value=tmp_path / "home"):
            deleted = adapter.cleanup(exclude_paths={excluded})

        assert str(extension_dir) + "/" not in deleted
        assert extension_dir.exists()

    def test_generate_mcp_config_assembles_and_installs(self, tmp_path):
        scripts_dir = tmp_path / "pack"
        scripts_dir.mkdir()
        (scripts_dir / "profiles.py").write_text('VALUE = "fresh"\n', encoding="utf-8")
        (scripts_dir / "plugin_assembler.py").write_text(
            "import profiles\n"
            "calls = []\n"
            "def assemble(target, output_dir):\n"
            "    assert profiles.VALUE == 'fresh'\n"
            "    calls.append(('assemble', target, str(output_dir)))\n"
            "    return output_dir, '9.9.9'\n"
            "def install(target, output_dir, version):\n"
            "    calls.append(('install', target, str(output_dir), version))\n",
            encoding="utf-8",
        )

        stale_module = SimpleNamespace(
            assemble=lambda *_args: pytest.fail("stale plugin_assembler was reused"),
            install=lambda *_args: pytest.fail("stale plugin_assembler was reused"),
        )
        stale_profiles = SimpleNamespace(VALUE="stale")

        adapter = GeminiPluginAdapter()
        adapter._output_dir = tmp_path / "build" / "gemini"

        with patch.dict("sys.modules", {"plugin_assembler": stale_module, "profiles": stale_profiles}), \
             patch("sync_agents.adapters.gemini_plugin._plugin_pack_scripts_dir", return_value=scripts_dir), \
             patch("sync_agents.adapters.gemini_plugin.PROJECT_ROOT", tmp_path):
            module = adapter.generate_mcp_config()

        assert module.calls == [
            ("assemble", "gemini", str(adapter._output_dir)),
            ("install", "gemini", str(adapter._output_dir), "9.9.9"),
        ]
        assert str(scripts_dir) not in sys.path


class TestAllAdaptersHaveLifecycleMethods:
    @pytest.mark.parametrize("AdapterClass", ALL_ADAPTERS, ids=lambda c: c.__name__)
    def test_adapter_has_name(self, AdapterClass):
        adapter = AdapterClass()
        assert adapter.adapter_name != "", f"{AdapterClass.__name__} missing adapter_name"

    @pytest.mark.parametrize("AdapterClass", ALL_ADAPTERS, ids=lambda c: c.__name__)
    def test_adapter_managed_files_returns_nonempty_list(self, AdapterClass):
        adapter = AdapterClass()
        files = adapter.get_managed_files()
        assert isinstance(files, list)
        assert len(files) > 0, f"{AdapterClass.__name__} returned empty managed_files"

    @pytest.mark.parametrize("AdapterClass", ALL_ADAPTERS, ids=lambda c: c.__name__)
    def test_adapter_detect_installed_returns_bool(self, AdapterClass):
        adapter = AdapterClass()
        result = adapter.detect_installed()
        assert isinstance(result, bool)

    def test_adapter_names_are_unique(self):
        names = [cls().adapter_name for cls in ALL_ADAPTERS]
        assert len(names) == len(set(names)), f"Duplicate adapter names: {names}"

    def test_codex_managed_files_include_repo_agents(self):
        files = CodexAdapter().get_managed_files()
        assert "CODEX.md" in files
        assert "AGENTS.md" in files
        assert ".codex/agents/" in files
        assert ".codex/prompts/" in files
        assert ".codex/skills/" in files
        assert f"{Path.home()}/.agents/skills/augur" in files

    def test_engine_lists_gemini_plugin_adapter(self):
        from sync_agents import engine

        assert "gemini_plugin" in {
            adapter.adapter_name
            for adapter in engine._get_all_adapters()
        }

    def test_gemini_plugin_adapter_is_gated_with_gemini_group(self):
        from sync_agents import engine

        assert engine._ADAPTER_TO_GROUP["gemini_plugin"] == "gemini"


class TestClaudeCodeAdapterAgentScan:
    def test_claude_code_managed_files_exclude_repo_source_dirs(self):
        files = ClaudeCodeAdapter().get_managed_files()
        assert "CLAUDE.md" in files
        assert ".claude/mcp.json" in files
        assert ".claude/agents/" in files
        assert ".claude/commands/" in files
        assert "docs/agent-topics/" not in files
        assert "skills/" not in files
        assert "project-brain/capabilities/skills/" not in files

    def test_claude_code_cleanup_preserves_repo_source_dirs(self, tmp_path):
        source_skills = tmp_path / "project-brain" / "capabilities" / "skills"
        source_skills.mkdir(parents=True)
        (source_skills / "README.md").write_text("source\n", encoding="utf-8")

        topic_docs = tmp_path / "docs" / "agent-topics"
        topic_docs.mkdir(parents=True)
        (topic_docs / "AGENTS.md").write_text("source\n", encoding="utf-8")

        managed_agents = tmp_path / ".claude" / "agents"
        managed_agents.mkdir(parents=True)
        (managed_agents / "developer.md").write_text("generated\n", encoding="utf-8")

        managed_commands = tmp_path / ".claude" / "commands"
        managed_commands.mkdir(parents=True)
        (managed_commands / "dev-build.md").write_text("generated\n", encoding="utf-8")

        managed_mcp = tmp_path / ".claude" / "mcp.json"
        managed_mcp.write_text("{}", encoding="utf-8")

        managed_rules = tmp_path / "CLAUDE.md"
        managed_rules.write_text("generated\n", encoding="utf-8")

        with patch("sync_agents.constants.PROJECT_ROOT", tmp_path), \
             patch("sync_agents.adapters.claude_code.PROJECT_ROOT", tmp_path), \
             patch("sync_agents.adapters.claude_code.Path.home", return_value=tmp_path / "home"):
            deleted = ClaudeCodeAdapter().cleanup()

        assert sorted(deleted) == sorted(
            [
                "CLAUDE.md",
                ".claude/mcp.json",
                ".claude/agents/",
                ".claude/commands/",
            ]
        )
        assert source_skills.exists()
        assert topic_docs.exists()
        assert not managed_agents.exists()
        assert not managed_commands.exists()
        assert not managed_mcp.exists()
        assert not managed_rules.exists()

    def test_sync_subagents_ignores_readme_docs(self, tmp_path, caplog):
        agents_dir = tmp_path / ".claude" / "agents"
        agents_dir.mkdir(parents=True)
        (agents_dir / "README.md").write_text("# Agents\n", encoding="utf-8")
        (agents_dir / "reviewer.md").write_text(
            "---\nname: reviewer\ndescription: test reviewer\nmodel: sonnet\n---\n# Reviewer\n",
            encoding="utf-8",
        )

        with patch("sync_agents.adapters.claude_code.PROJECT_ROOT", tmp_path), \
             patch("sync_agents.adapters.claude_code.GENERATED_FILES", []), \
             patch("sync_agents.agent_parser.scan_plugin_agents", return_value=[]):
            ClaudeCodeAdapter().sync_subagents()

        assert "No YAML frontmatter in README.md" not in caplog.text
        registry = json.loads((agents_dir / "registry.json").read_text(encoding="utf-8"))
        assert "reviewer" in registry["agents"]

    def test_gemini_sync_subagents_adapts_claude_specific_plugin_agent_content(self, tmp_path):
        from sync_agents.agent_parser import AgentFile

        plugin_root = tmp_path / "plugin-cache" / "codex"
        agent_path = plugin_root / "agents" / "codex-rescue.md"
        agent_path.parent.mkdir(parents=True)
        master = AgentFile(
            name="codex-rescue",
            path=agent_path,
            frontmatter={"model": "sonnet", "tools": "Bash"},
            body=textwrap.dedent("""\
                You are a thin forwarding wrapper around the Codex companion task runtime.

                Selection guidance:

                - Use this subagent proactively when the main Claude thread should hand work to Codex.
                - Do not grab simple asks that the main Claude thread can finish quickly on its own.

                Forwarding rules:

                - Follow the established coding standards from CLAUDE.md.
                - Use exactly one `Bash` call to invoke `node "${CLAUDE_PLUGIN_ROOT}/scripts/codex-companion.mjs" task ...`.
                - If the Bash call fails or Codex cannot be invoked, return nothing.
            """),
            client_dir="plugin:codex",
        )

        with patch("sync_agents.adapters.gemini.PROJECT_ROOT", tmp_path), \
             patch("sync_agents.agent_parser.scan_agent_dirs", return_value=[]), \
             patch("sync_agents.agent_parser.scan_plugin_agents", return_value=[master]):
            GeminiAdapter().sync_subagents()

        generated_path = tmp_path / ".antigravity" / "agents" / "codex-rescue.md"
        metadata, body = parse_frontmatter(generated_path)
        generated = generated_path.read_text(encoding="utf-8")

        assert "Source: plugin:codex/agents/codex-rescue.md" in generated
        assert metadata["tools"] == ["run_shell_command"]
        assert "main Gemini thread" in body
        assert "main Claude thread" not in body
        assert "AGENTS.md" in body
        assert "CLAUDE.md" not in body
        assert "`run_shell_command` call" in body
        assert "`Bash` call" not in body
        assert "If the run_shell_command call fails" in body
        assert "CLAUDE_PLUGIN_ROOT" not in body
        assert f'node "{plugin_root / "scripts" / "codex-companion.mjs"}" task' in body

    def test_gemini_mcp_config_unignores_generated_runtime_surface(self, tmp_path):
        project_root = tmp_path / "project"
        project_root.mkdir()
        _write_split_mcp_manifest(project_root)

        with patch("sync_agents.adapters.gemini.PROJECT_ROOT", project_root):
            GeminiAdapter().generate_mcp_config()

        config = yaml.safe_load((project_root / ".antigravity" / "config.yaml").read_text(encoding="utf-8"))
        unignore_text = (project_root / ".antigravity" / "unignore").read_text(encoding="utf-8")

        assert config["context"]["fileFiltering"]["customIgnoreFilePaths"] == [".antigravity/unignore"]
        assert "!/.antigravity/plugins/" in unignore_text
        assert "!/.antigravity/plugins/**" in unignore_text

    def test_gemini_mcp_config_uses_split_manifest_not_legacy_template(self, tmp_path):
        project_root = tmp_path / "project"
        project_root.mkdir()
        _write_split_mcp_manifest(project_root)

        with patch("sync_agents.adapters.gemini.PROJECT_ROOT", project_root):
            GeminiAdapter().generate_mcp_config()

        config = yaml.safe_load((project_root / ".antigravity" / "config.yaml").read_text(encoding="utf-8"))
        rendered = yaml.dump(config, default_flow_style=False, sort_keys=False)

        assert "augur-core" in config["mcpServers"]
        assert "augur-framework" in config["mcpServers"]
        assert "augur" not in config["mcpServers"]
        assert "augur_mcp" not in rendered
        assert config["mcpServers"]["augur-core"]["args"] == [
            "-m",
            "augur_core",
            "--client-id",
            "gemini",
        ]
        assert config["extensions"]["augur"] is False

    def test_gemini_mcp_config_filters_manifest_entries_by_policy(self, tmp_path, monkeypatch):
        project_root = tmp_path / "project"
        project_root.mkdir()
        _write_split_mcp_manifest(project_root)
        _patch_mcp_policy_records(
            monkeypatch,
            SimpleNamespace(
                id="mcp-server:augur-core",
                classification_status="approved",
                export_to=("gemini",),
                current_exposure=(),
            ),
            SimpleNamespace(
                id="mcp-server:augur-framework",
                classification_status="blocked",
                export_to=(),
                current_exposure=("gemini",),
            ),
        )

        with patch("sync_agents.adapters.gemini.PROJECT_ROOT", project_root):
            GeminiAdapter().generate_mcp_config()

        config = yaml.safe_load((project_root / ".antigravity" / "config.yaml").read_text(encoding="utf-8"))
        assert set(config["mcpServers"]) == {"augur-core"}

    def test_gemini_mcp_config_skips_bundle_servers_to_stay_under_function_cap(self, tmp_path):
        project_root = tmp_path / "project"
        project_root.mkdir()
        _write_split_mcp_manifest(project_root)
        manifest_path = project_root / "config" / "system" / "mcp_servers.yaml"
        manifest_path.write_text(
            manifest_path.read_text(encoding="utf-8").replace(
                "vault_tier: []",
                textwrap.dedent(
                    """\
                    vault_tier:
                      - id: augur-apple
                        command: python
                        args: [-m, augur_shared.bundle_server, apple]
                        bundle: apple
                        bundle_path: /tmp/apple
                    """
                ).rstrip(),
            ),
            encoding="utf-8",
        )

        with patch("sync_agents.adapters.gemini.PROJECT_ROOT", project_root):
            GeminiAdapter().generate_mcp_config()

        config = yaml.safe_load((project_root / ".antigravity" / "config.yaml").read_text(encoding="utf-8"))
        assert "augur-core" in config["mcpServers"]
        assert "augur-framework" in config["mcpServers"]
        assert "augur-apple" not in config["mcpServers"]

    def test_codex_app_paths_use_home_and_anchor_applications_dirs(self, tmp_path):
        from sync_agents.adapters.codex import _codex_app_paths

        home_dir = tmp_path / "home"

        with patch("sync_agents.adapters.codex.Path.home", return_value=home_dir):
            paths = _codex_app_paths()

        assert paths == [
            home_dir / "Applications" / "Codex.app",
            Path(home_dir.anchor or "/") / "Applications" / "Codex.app",
        ]

    def test_codex_mcp_config_uses_clean_worktree_launcher(self, tmp_path):
        project_root = tmp_path / "project"
        project_root.mkdir()
        _write_split_mcp_manifest(project_root)
        config_path = tmp_path / "home" / ".codex" / "config.toml"
        adapter = CodexAdapter()

        with patch("sync_agents.adapters.codex.PROJECT_ROOT", project_root), patch(
            "sync_agents.adapters.codex.CODEX_HOME",
            config_path.parent,
        ):
            adapter.generate_mcp_config()

        config_text = config_path.read_text(encoding="utf-8")
        parsed = tomllib.loads(config_text)
        core_entry = parsed["mcp_servers"]["augur-core"]
        if sys.platform == "win32":
            assert core_entry["command"] == "powershell.exe"
            assert core_entry["args"][:4] == ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File"]
            assert core_entry["args"][4] == str(project_root / "scripts" / "augur-codex-mcp.ps1")
            assert core_entry["args"][5:] == ["-m", "augur_core", "--client-id", "codex"]
        else:
            assert core_entry["command"] == str(project_root / "scripts" / "augur-codex-mcp")
            assert core_entry["args"] == ["-m", "augur_core", "--client-id", "codex"]
        assert 'args = ["-lc"' not in config_text
        assert 'root="$(pwd -P)"' not in config_text
        assert "cwd =" not in config_text
        assert 'AUGUR_ROOT = ' not in config_text
        assert "[mcp_servers.augur-core.env]" not in config_text

    def test_codex_mcp_config_registers_absolute_augur_plugin_marketplace(self, tmp_path):
        project_root = tmp_path / "project"
        project_root.mkdir()
        _write_split_mcp_manifest(project_root)
        config_path = tmp_path / "home" / ".codex" / "config.toml"
        adapter = CodexAdapter()

        with patch("sync_agents.adapters.codex.PROJECT_ROOT", project_root), patch(
            "sync_agents.adapters.codex.CODEX_HOME", config_path.parent
        ):
            adapter.generate_mcp_config()

        parsed = tomllib.loads(config_path.read_text(encoding="utf-8"))
        marketplace = parsed["marketplaces"]["augur-local"]
        assert marketplace["source_type"] == "local"
        assert marketplace["source"] == str(project_root)
        assert Path(marketplace["source"]).is_absolute()
        assert parsed["plugins"]["augur@augur-local"]["enabled"] is True

    def test_codex_mcp_config_syncs_dev_loop_automations(self, tmp_path):
        project_root = tmp_path / "project"
        project_root.mkdir()
        _write_split_mcp_manifest(project_root)
        skills_root = project_root / "project-brain" / "capabilities" / "skills"
        skill_root = skills_root / "routine-codebase"
        skill_root.mkdir(parents=True)
        (skill_root / "SKILL.md").write_text(
            textwrap.dedent(
                """\
                ---
                name: routine-codebase
                x-augur-routine:
                  id: testing
                  execution: tiered
                  policy: adaptive
                  callable: ../daemon/scripts/routine_orchestrator/orchestrator.py
                  loop: testing
                ---
                """
            ),
            encoding="utf-8",
        )
        seed_path = (
            skill_root
            / "assets"
            / "seeds"
            / "routine-schedule.yaml"
        )
        seed_path.parent.mkdir(parents=True)
        seed_path.write_text(
            textwrap.dedent(
                """\
                schedules:
                  - id: codex-dev-loop-testing
                    title: Testing
                    rrule: RRULE:FREQ=WEEKLY;BYDAY=SU;BYHOUR=3;BYMINUTE=0
                    prompt: /dev-loops run testing
                    workspace: __PROJECT_ROOT__
                    model: gpt-5.4
                    reasoning_effort: high
                    runs_in: local
                """
            ),
            encoding="utf-8",
        )
        config_path = tmp_path / "home" / ".codex" / "config.toml"
        adapter = CodexAdapter()

        with patch("sync_agents.adapters.codex.PROJECT_ROOT", project_root), patch(
            "sync_agents.adapters.codex.CODEX_HOME", config_path.parent
        ), patch.object(adapter, "_routine_registry_roots", return_value=[skills_root]):
            adapter.generate_mcp_config()

        automation = (
            tmp_path
            / "home"
            / ".codex"
            / "automations"
            / "codex-dev-loop-testing"
            / "automation.toml"
        )
        content = automation.read_text(encoding="utf-8")
        parsed = tomllib.loads(content)
        assert 'execution_environment = "local"' in content
        assert parsed["cwds"] == [str(project_root)]

    def test_codex_mcp_config_registers_split_servers_and_drops_legacy_augur(self, tmp_path):
        project_root = tmp_path / "project"
        project_root.mkdir()
        _write_split_mcp_manifest(project_root)
        config_path = tmp_path / "home" / ".codex" / "config.toml"
        config_path.parent.mkdir(parents=True)
        config_path.write_text(
            textwrap.dedent(
                """\
                [mcp_servers.augur]
                command = "python3"
                args = ["-m", "augur_mcp"]

                [mcp_servers.context7]
                command = "npx"
                args = []
                """
            ),
            encoding="utf-8",
        )

        with patch("sync_agents.adapters.codex.PROJECT_ROOT", project_root), patch(
            "sync_agents.adapters.codex.CODEX_HOME", config_path.parent
        ):
            CodexAdapter().generate_mcp_config()

        parsed = tomllib.loads(config_path.read_text(encoding="utf-8"))
        rendered = config_path.read_text(encoding="utf-8")

        assert "augur-core" in parsed["mcp_servers"]
        assert "augur-framework" in parsed["mcp_servers"]
        assert "augur" not in parsed["mcp_servers"]
        assert "context7" in parsed["mcp_servers"]
        assert "augur_mcp" not in rendered
        assert "augur_core" in parsed["mcp_servers"]["augur-core"]["args"]
        assert parsed["marketplaces"]["augur-local"]["source"] == str(project_root)
        assert parsed["plugins"]["augur@augur-local"]["enabled"] is True

    def test_codex_mcp_config_filters_manifest_entries_by_policy(self, tmp_path, monkeypatch):
        project_root = tmp_path / "project"
        project_root.mkdir()
        _write_split_mcp_manifest(project_root)
        _patch_mcp_policy_records(
            monkeypatch,
            SimpleNamespace(
                id="mcp-server:augur-core",
                classification_status="approved",
                export_to=("codex",),
                current_exposure=(),
            ),
            SimpleNamespace(
                id="mcp-server:augur-framework",
                classification_status="blocked",
                export_to=(),
                current_exposure=("codex",),
            ),
        )
        config_path = tmp_path / "home" / ".codex" / "config.toml"
        config_path.parent.mkdir(parents=True)

        with patch("sync_agents.adapters.codex.PROJECT_ROOT", project_root), patch(
            "sync_agents.adapters.codex.CODEX_HOME", config_path.parent
        ):
            CodexAdapter().generate_mcp_config()

        parsed = tomllib.loads(config_path.read_text(encoding="utf-8"))
        assert set(parsed["mcp_servers"]) == {"augur-core"}

    def test_codex_cleanup_removes_augur_mcp_marketplace_and_plugin_entries(self, tmp_path):
        config_path = tmp_path / "home" / ".codex" / "config.toml"
        config_path.parent.mkdir(parents=True)
        config_path.write_text(
            textwrap.dedent(
                """\
                [mcp_servers.augur]
                command = "/bin/zsh"

                [mcp_servers.other]
                command = "other"

                [marketplaces.augur-local]
                source = "/repo"
                source_type = "local"

                [marketplaces.other-local]
                source = "/other"
                source_type = "local"

                [plugins."augur@augur-local"]
                enabled = true

                [plugins."other@other-local"]
                enabled = true
                """
            ),
            encoding="utf-8",
        )
        adapter = CodexAdapter()

        with patch("sync_agents.adapters.codex.CODEX_HOME", config_path.parent), patch.object(
            adapter,
            "get_managed_files",
            return_value=[],
        ):
            deleted = adapter.cleanup()

        parsed = tomllib.loads(config_path.read_text(encoding="utf-8"))
        assert deleted == [str(config_path)]
        assert "augur" not in parsed["mcp_servers"]
        assert "other" in parsed["mcp_servers"]
        assert "augur-local" not in parsed["marketplaces"]
        assert "other-local" in parsed["marketplaces"]
        assert "augur@augur-local" not in parsed["plugins"]
        assert parsed["plugins"]["other@other-local"]["enabled"] is True

    def test_codex_mcp_entry_is_dynamic_and_not_repo_pinned(self):
        entry = _build_codex_mcp_entry()

        assert Path(entry["command"]).is_absolute()
        assert entry["command"].endswith("/scripts/augur-codex-mcp")
        assert entry["args"] == ["-m", "augur_core", "--client-id", "codex"]
        assert "env" not in entry
        assert "cwd" not in entry

    def test_codex_mcp_launcher_falls_back_to_configured_root_when_cwd_is_not_repo(
        self,
        tmp_path,
    ):
        repo_root = next(
            parent
            for parent in Path(__file__).resolve().parents
            if (parent / "scripts" / "augur-codex-mcp").is_file()
        )
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / "project.yaml").write_text("name: test\n", encoding="utf-8")

        script_dir = project_root / "scripts"
        script_dir.mkdir()
        launcher = script_dir / "augur-codex-mcp"
        launcher.write_text(
            (repo_root / "scripts" / "augur-codex-mcp").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        launcher.chmod(0o755)

        fake_python = project_root / ".venv" / "bin" / "python"
        fake_python.parent.mkdir(parents=True)
        output_path = tmp_path / "codex-wrapper-env.txt"
        fake_python.write_text(
            "#!/bin/sh\n"
            'printf "AUGUR_ROOT=%s\\nPYTHONPATH=%s\\nARGS=%s\\n" "$AUGUR_ROOT" "$PYTHONPATH" "$*" > "$AUGUR_CODEX_TEST_OUT"\n',
            encoding="utf-8",
        )
        fake_python.chmod(0o755)
        launcher_cwd = tmp_path / "outside"
        launcher_cwd.mkdir()

        with patch("sync_agents.adapters.codex.PROJECT_ROOT", project_root):
            entry = _build_codex_mcp_entry()

        result = subprocess.run(
            [entry["command"], *entry["args"]],
            cwd=launcher_cwd,
            env={
                "AUGUR_CODEX_TEST_OUT": str(output_path),
                "PATH": os.environ.get("PATH", ""),
            },
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0, result.stderr
        output = output_path.read_text(encoding="utf-8")
        assert f"AUGUR_ROOT={project_root}" in output
        # ADR-770: canonical PYTHONPATH injects project-brain/capabilities (not
        # bare project-brain) ahead of the repo root and src/mcp.
        assert (
            f"{project_root / 'project-brain' / 'capabilities'}:{project_root}:{project_root / 'src' / 'mcp'}"
            in output
        )
        assert "ARGS=-m augur_core --client-id codex" in output

    def test_codex_sync_rules_repo_local_only_skips_global_codex_home(self, tmp_path, monkeypatch):
        project_root = tmp_path / "project"
        codex_home = tmp_path / "home" / ".codex"
        project_root.mkdir()
        monkeypatch.setenv("AUGUR_SYNC_REPO_LOCAL_ONLY", "1")

        with patch("sync_agents.adapters.codex.PROJECT_ROOT", project_root), patch(
            "sync_agents.adapters.codex.CODEX_HOME",
            codex_home,
        ):
            CodexAdapter().sync_rules("# Rules\n")

        assert (project_root / "CODEX.md").exists()
        assert (project_root / "AGENTS.md").exists()
        assert not (codex_home / "AGENTS.md").exists()
        assert not (codex_home / "instructions.md").exists()

    def test_codex_mcp_config_uses_authority_root_from_linked_worktree(
        self, tmp_path, monkeypatch
    ):
        main_root = tmp_path / "main"
        project_root = tmp_path / "project"
        main_root.mkdir()
        project_root.mkdir()
        (main_root / "project.yaml").write_text("name: augur\n", encoding="utf-8")
        _write_split_mcp_manifest(project_root)
        gitdir = main_root / ".git" / "worktrees" / "project"
        gitdir.mkdir(parents=True)
        (project_root / ".git").write_text(f"gitdir: {gitdir}\n", encoding="utf-8")
        codex_home = tmp_path / "home" / ".codex"
        monkeypatch.delenv("AUGUR_SYNC_REPO_LOCAL_ONLY", raising=False)

        with patch("sync_agents.adapters.codex.PROJECT_ROOT", project_root), patch(
            "sync_agents.adapters.codex.CODEX_HOME",
            codex_home,
        ):
            CodexAdapter().generate_mcp_config()

        global_config = (codex_home / "config.toml").read_text(encoding="utf-8")
        assert str(main_root.resolve()) in global_config
        assert str(project_root.resolve()) not in global_config
        assert (project_root / ".codex" / "config.toml").exists()

    def test_codex_runtime_check_includes_global_codex_home_from_linked_worktree(
        self, tmp_path, monkeypatch
    ):
        from sync_agents.adapters import codex as codex_adapter

        project_root = tmp_path / "project"
        project_root.mkdir()
        gitdir = tmp_path / "main" / ".git" / "worktrees" / "project"
        gitdir.mkdir(parents=True)
        (project_root / ".git").write_text(f"gitdir: {gitdir}\n", encoding="utf-8")
        codex_home = tmp_path / "home" / ".codex"
        monkeypatch.delenv("AUGUR_SYNC_REPO_LOCAL_ONLY", raising=False)

        with patch("sync_agents.adapters.codex.PROJECT_ROOT", project_root), patch(
            "sync_agents.adapters.codex.CODEX_HOME",
            codex_home,
        ):
            assert codex_adapter.should_check_global_codex_runtime_config() is True

        monkeypatch.setenv("AUGUR_SYNC_REPO_LOCAL_ONLY", "1")
        with patch("sync_agents.adapters.codex.PROJECT_ROOT", project_root), patch(
            "sync_agents.adapters.codex.CODEX_HOME",
            codex_home,
        ):
            assert codex_adapter.should_check_global_codex_runtime_config() is False

    def test_cursor_managed_files_track_generated_rules_and_agents_dirs(self):
        files = CursorAdapter().get_managed_files()
        assert ".cursor/rules/" in files
        assert ".cursor/agents/" in files
        assert ".cursor/skills/" not in files

    def test_cursor_cleanup_prunes_empty_client_root(self, tmp_path):
        cursor_root = tmp_path / ".cursor"
        cursor_root.mkdir(parents=True)

        with patch("sync_agents.adapters.cursor.PROJECT_ROOT", tmp_path):
            deleted = CursorAdapter().cleanup()

        assert ".cursor/" in deleted
        assert not cursor_root.exists()

    def test_cursor_mcp_config_uses_reduced_template_and_drops_legacy_augur(self, tmp_path):
        project_root = tmp_path / "project"
        target = project_root / ".cursor" / "mcp.json"
        target.parent.mkdir(parents=True)
        target.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "context7": {"command": "npx", "args": []},
                        "augur": {"command": "python3", "args": ["-m", "augur_mcp"]},
                    }
                }
            ),
            encoding="utf-8",
        )

        with patch("sync_agents.adapters.cursor.PROJECT_ROOT", project_root):
            CursorAdapter().generate_mcp_config()

        config = json.loads(target.read_text(encoding="utf-8"))
        rendered = yaml.dump(config, default_flow_style=False, sort_keys=False)

        assert "context7" in config["mcpServers"]
        assert "augur" not in config["mcpServers"]
        assert "augur-core" in config["mcpServers"]
        assert "augur-framework" not in config["mcpServers"]
        assert "augur_mcp" not in rendered

    def test_windsurf_managed_files_track_generated_skill_dirs(self):
        files = WindsurfAdapter().get_managed_files()
        assert ".windsurf/rules/" in files
        assert ".windsurf/skills/" in files
        assert ".windsurf/workflows/" not in files

    def test_windsurf_cleanup_prunes_empty_client_root(self, tmp_path):
        windsurf_root = tmp_path / ".windsurf"
        windsurf_root.mkdir(parents=True)

        with patch("sync_agents.adapters.windsurf.PROJECT_ROOT", tmp_path):
            deleted = WindsurfAdapter().cleanup()

        assert ".windsurf/" in deleted
        assert not windsurf_root.exists()

    def test_antigravity_managed_files_track_local_integration_dir(self):
        files = AntigravityAdapter().get_managed_files()
        assert files == [".antigravity/"]

    def test_antigravity_mcp_config_repo_local_only_skips_global_config(self, tmp_path, monkeypatch):
        project_root = tmp_path / "project"
        local_target = project_root / ".antigravity" / "mcp_config.json"
        global_target = tmp_path / "home" / ".antigravity" / "antigravity" / "mcp_config.json"
        template_path = tmp_path / "mcp_template.json"
        project_root.mkdir()
        template_path.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "augur": {
                            "command": "${AUGUR_PYTHON}",
                            "cwd": "${AUGUR_ROOT}",
                            "args": ["-m", "augur_mcp"],
                            "env": {"PYTHONPATH": "${AUGUR_ROOT}/src/mcp"},
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setenv("AUGUR_SYNC_REPO_LOCAL_ONLY", "1")

        with patch("sync_agents.adapters.antigravity.PROJECT_ROOT", project_root), patch(
            "sync_agents.adapters.antigravity.MCP_CONFIG_TEMPLATE",
            template_path,
        ), patch.object(AntigravityAdapter, "_GLOBAL_MCP_CONFIG", global_target):
            AntigravityAdapter().generate_mcp_config()

        assert local_target.exists()
        assert not global_target.exists()

    def test_antigravity_global_mcp_config_from_worktree_uses_main_root_and_preserves_external(
        self,
        tmp_path,
        monkeypatch,
    ):
        main_root = tmp_path / "main"
        worktree_root = tmp_path / "worktree"
        global_target = tmp_path / "home" / ".antigravity" / "antigravity" / "mcp_config.json"
        template_path = tmp_path / "mcp_template.json"
        (main_root / ".git" / "worktrees" / "worktree").mkdir(parents=True)
        (main_root / ".venv" / "bin").mkdir(parents=True)
        (main_root / ".venv" / "bin" / "python3").write_text("", encoding="utf-8")
        (main_root / "project.yaml").write_text("name: augur\n", encoding="utf-8")
        worktree_root.mkdir()
        (worktree_root / ".git").write_text(
            f"gitdir: {main_root / '.git' / 'worktrees' / 'worktree'}\n",
            encoding="utf-8",
        )
        template_path.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "augur-core": {
                            "command": "${AUGUR_PYTHON}",
                            "cwd": "${AUGUR_ROOT}",
                            "args": ["-m", "augur_core", "--client-id", "${AUGUR_CLIENT_ID}"],
                            "env": {"AUGUR_ROOT": "${AUGUR_ROOT}"},
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        global_target.parent.mkdir(parents=True)
        global_target.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "context7": {"command": "npx", "args": []},
                        "augur-old": {"command": "old", "args": []},
                    }
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.delenv("AUGUR_SYNC_REPO_LOCAL_ONLY", raising=False)

        with patch("sync_agents.adapters.antigravity.PROJECT_ROOT", worktree_root), patch(
            "sync_agents.adapters.antigravity.MCP_CONFIG_TEMPLATE",
            template_path,
        ), patch.object(AntigravityAdapter, "_GLOBAL_MCP_CONFIG", global_target):
            AntigravityAdapter().generate_mcp_config()

        config = yaml.safe_load(global_target.read_text(encoding="utf-8"))
        servers = config["mcpServers"]
        assert "context7" in servers
        assert "augur-old" not in servers
        assert str(main_root) in json.dumps(servers["augur-core"])
        assert str(worktree_root) not in json.dumps(servers["augur-core"])

    def test_opencode_managed_files_use_skill_dirs_and_current_config(self):
        files = OpenCodeAdapter().get_managed_files()
        assert ".opencode/skills/" in files
        assert f"{Path.home()}/.config/opencode/opencode.json" in files

    def test_opencode_mcp_config_uses_environment_key(self, tmp_path):
        adapter = OpenCodeAdapter()
        target = tmp_path / ".config" / "opencode" / "opencode.json"
        template = {
            "mcpServers": {
                "augur-core": {
                    "command": "/tmp/python3",
                    "args": ["-m", "augur_core", "--client-id", "opencode"],
                    "env": {"PYTHONPATH": "/tmp/project:/tmp/project/src/mcp"},
                },
                "augur-framework": {
                    "command": "/tmp/python3",
                    "args": ["-m", "augur_framework", "--client-id", "opencode"],
                    "env": {"PYTHONPATH": "/tmp/project:/tmp/project/src/mcp"},
                },
            }
        }

        with patch("sync_agents.adapters.opencode.MCP_CONFIG_TEMPLATE", tmp_path / "mcp_template.json"), \
             patch("sync_agents.adapters.opencode.PROJECT_ROOT", tmp_path / "project"), \
             patch("pathlib.Path.home", return_value=tmp_path):
            (tmp_path / "mcp_template.json").write_text(json.dumps(template))
            (tmp_path / "project" / ".venv" / "bin").mkdir(parents=True)
            (tmp_path / "project" / ".venv" / "bin" / "python3").write_text("")
            adapter.generate_mcp_config()

        config = json.loads(target.read_text())
        assert "augur" not in config["mcp"]
        assert "environment" in config["mcp"]["augur-core"]
        assert "env" not in config["mcp"]["augur-core"]
        assert config["mcp"]["augur-core"]["timeout"] == 30000
        assert "augur-framework" in config["mcp"]

    def test_opencode_global_mcp_config_from_worktree_uses_main_root(
        self,
        tmp_path,
        monkeypatch,
    ):
        adapter = OpenCodeAdapter()
        main_root = tmp_path / "main"
        worktree_root = tmp_path / "worktree"
        target = tmp_path / "home" / ".config" / "opencode" / "opencode.json"
        template_path = tmp_path / "mcp_template.json"
        (main_root / ".git" / "worktrees" / "worktree").mkdir(parents=True)
        (main_root / ".venv" / "bin").mkdir(parents=True)
        (main_root / ".venv" / "bin" / "python3").write_text("", encoding="utf-8")
        (main_root / "project.yaml").write_text("name: augur\n", encoding="utf-8")
        worktree_root.mkdir()
        (worktree_root / ".git").write_text(
            f"gitdir: {main_root / '.git' / 'worktrees' / 'worktree'}\n",
            encoding="utf-8",
        )
        template_path.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "augur-core": {
                            "command": "${AUGUR_PYTHON}",
                            "args": ["-m", "augur_core", "--client-id", "opencode"],
                            "env": {"AUGUR_ROOT": "${AUGUR_ROOT}"},
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        target.parent.mkdir(parents=True)
        target.write_text(
            json.dumps(
                {
                    "mcp": {
                        "context7": {"type": "local", "command": ["npx"], "enabled": True},
                        "augur-old": {"type": "local", "command": ["old"], "enabled": True},
                    }
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.delenv("AUGUR_SYNC_REPO_LOCAL_ONLY", raising=False)

        with patch("sync_agents.adapters.opencode.MCP_CONFIG_TEMPLATE", template_path), \
             patch("sync_agents.adapters.opencode.PROJECT_ROOT", worktree_root), \
             patch("pathlib.Path.home", return_value=tmp_path / "home"):
            adapter.generate_mcp_config()

        config = json.loads(target.read_text(encoding="utf-8"))
        assert "context7" in config["mcp"]
        assert "augur-old" not in config["mcp"]
        assert str(main_root) in json.dumps(config["mcp"]["augur-core"])
        assert str(worktree_root) not in json.dumps(config["mcp"]["augur-core"])

    def test_kimi_mcp_config_uses_reduced_template_and_drops_legacy_augur(self, tmp_path):
        project_root = tmp_path / "project"
        home = tmp_path / "home"
        target = home / ".kimi" / "mcp.json"
        target.parent.mkdir(parents=True)
        target.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "context7": {"command": "npx", "args": []},
                        "augur": {"command": "python3", "args": ["-m", "augur_mcp"]},
                    }
                }
            ),
            encoding="utf-8",
        )

        with patch("sync_agents.adapters.kimi.PROJECT_ROOT", project_root), patch(
            "pathlib.Path.home",
            return_value=home,
        ):
            KimiAdapter().generate_mcp_config()

        config = json.loads(target.read_text(encoding="utf-8"))
        rendered = yaml.dump(config, default_flow_style=False, sort_keys=False)

        assert "context7" in config["mcpServers"]
        assert "augur" not in config["mcpServers"]
        assert config["mcpServers"]["augur-core"]["args"] == [
            "-m",
            "augur_core",
            "--client-id",
            "kimi",
        ]
        assert "augur-framework" not in config["mcpServers"]
        assert "augur_mcp" not in rendered


class TestCodexAdapter:
    def test_codex_mcp_entry_is_dynamic_and_not_repo_pinned(self):
        entry = _build_codex_mcp_entry()

        assert Path(entry["command"]).is_absolute()
        assert entry["command"].endswith("/scripts/augur-codex-mcp")
        assert entry["args"] == ["-m", "augur_core", "--client-id", "codex"]
        assert "env" not in entry
        assert "cwd" not in entry

    def test_codex_mcp_entry_uses_windows_launcher_shape_when_requested(self):
        repo_root = Path("C:/Augur").resolve()

        entry = build_codex_mcp_entry(
            ["-m", "augur_core", "--client-id", "codex"],
            configured_root=repo_root,
            platform_name="Windows",
        )

        assert entry == {
            "command": "powershell.exe",
            "args": [
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(repo_root / "scripts" / "augur-codex-mcp.ps1"),
                "-m",
                "augur_core",
                "--client-id",
                "codex",
            ],
        }

    def test_codex_sync_subagents_rewrites_claude_model_labels(self, tmp_path):
        from sync_agents.agent_parser import AgentFile

        agent_path = tmp_path / ".claude" / "agents" / "developer.md"
        master = AgentFile(
            name="developer",
            path=agent_path,
            frontmatter={"name": "developer", "description": "Developer agent", "model": "sonnet"},
            body=textwrap.dedent(
                """\
                # Developer

                **Model**: sonnet | **Mode**: act | **Role**: executor

                ## Available Tiers

                - **deep**: `opus` (act)
                - **fast**: `haiku` (act)
                - **standard**: `sonnet` (act) ← default
                """
            ),
            client_dir="claude-code",
        )

        (tmp_path / "config" / "agents").mkdir(parents=True)
        (tmp_path / "config" / "agents" / "model_mapping.yaml").write_text(
            textwrap.dedent(
                """\
                tiers:
                  fast:
                    clients:
                      claude-code: haiku
                      codex: gpt-5.4-mini
                  standard:
                    clients:
                      claude-code: sonnet
                      codex: gpt-5.4
                  deep:
                    clients:
                      claude-code: opus
                      codex: gpt-5.3-codex
                reverse_lookup:
                  haiku: fast
                  sonnet: standard
                  opus: deep
                """
            ),
            encoding="utf-8",
        )

        with patch("sync_agents.adapters.codex.PROJECT_ROOT", tmp_path), \
             patch("sync_agents.constants.PROJECT_ROOT", tmp_path), \
             patch("sync_agents.model_mapping._mapping_cache", None), \
             patch("sync_agents.agent_parser.scan_agent_dirs", return_value=[master]), \
             patch("sync_agents.agent_parser.scan_plugin_agents", return_value=[]):
            CodexAdapter().sync_subagents()

        generated = (tmp_path / ".codex" / "agents" / "developer.md").read_text(encoding="utf-8")
        assert "**Model**: gpt-5.4 | **Mode**: act | **Role**: executor" in generated
        assert "- **deep**: `gpt-5.3-codex` (act)" in generated
        assert "- **fast**: `gpt-5.4-mini` (act)" in generated
        assert "- **standard**: `gpt-5.4` (act) ← default" in generated

    def test_codex_sync_subagents_reads_canonical_plugins_agents(self, tmp_path):
        agents_dir = tmp_path / "plugins" / "agents"
        agents_dir.mkdir(parents=True)
        (agents_dir / "dev-merge.md").write_text(
            textwrap.dedent(
                """\
                ---
                name: dev-merge
                description: Merge agent
                mode: act
                model: sonnet
                x-augur-master: claude-code
                ---

                # Dev Merge

                **Model**: sonnet | **Mode**: act | **Role**: executor
                """
            ),
            encoding="utf-8",
        )

        (tmp_path / "config" / "agents").mkdir(parents=True)
        (tmp_path / "config" / "agents" / "model_mapping.yaml").write_text(
            textwrap.dedent(
                """\
                tiers:
                  standard:
                    clients:
                      claude-code: sonnet
                      codex: gpt-5.4
                reverse_lookup:
                  sonnet: standard
                """
            ),
            encoding="utf-8",
        )

        with patch("sync_agents.adapters.codex.PROJECT_ROOT", tmp_path), \
             patch("sync_agents.constants.PROJECT_ROOT", tmp_path), \
             patch("sync_agents.model_mapping._mapping_cache", None), \
             patch("sync_agents.agent_parser.scan_plugin_agents", return_value=[]):
            CodexAdapter().sync_subagents()

        generated = (tmp_path / ".codex" / "agents" / "dev-merge.md").read_text(encoding="utf-8")
        assert "Source: plugins/agents/dev-merge.md" in generated
        assert "**Model**: gpt-5.4 | **Mode**: act | **Role**: executor" in generated


class TestAdapterLifecycle:
    def test_copilot_managed_files_track_generated_cloud_dirs(self):
        files = CopilotAdapter().get_managed_files()
        assert ".github/instructions/" in files
        assert ".github/prompts/" in files
        assert ".github/agents/" in files
        assert ".github/skills/" in files
        assert ".github/copilot/" in files

    def test_copilot_required_outputs_skip_instructions_without_external_bundle(self, tmp_path):
        (tmp_path / "config").mkdir()
        (tmp_path / "config" / "external_skills.yaml").write_text(
            "external_skill_bundles: []\n",
            encoding="utf-8",
        )

        files = CopilotAdapter().get_required_outputs(
            tmp_path,
            do_rules=False,
            do_memory=False,
            do_skill_exports=True,
        )

        assert ".github/instructions/" not in files

    def test_copilot_required_outputs_include_instructions_for_external_bundle(self, tmp_path):
        skill_dir = tmp_path / "vendor" / "hermes" / "skills" / "apple"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# Apple\n", encoding="utf-8")
        (tmp_path / "config").mkdir()
        (tmp_path / "config" / "external_skills.yaml").write_text(
            yaml.safe_dump(
                {
                    "external_skill_bundles": [
                        {
                            "id": "hermes",
                            "source": "vendor/hermes",
                            "upstream": "https://example.invalid/hermes",
                            "skills": ["apple"],
                            "targets": {"copilot": "convert_to_instructions"},
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        files = CopilotAdapter().get_required_outputs(
            tmp_path,
            do_rules=False,
            do_memory=False,
            do_skill_exports=True,
        )

        assert ".github/instructions/" in files

    def test_copilot_cleanup_removes_augur_generated_files_and_legacy_dir(self, tmp_path):
        instructions_dir = tmp_path / ".github" / "instructions"
        prompts_dir = tmp_path / ".github" / "prompts"
        agents_dir = tmp_path / ".github" / "agents"
        skills_dir = tmp_path / ".github" / "skills"
        legacy_dir = tmp_path / ".github" / "copilot"
        generated_files = []
        user_files = []
        for directory in (instructions_dir, prompts_dir, agents_dir, skills_dir):
            directory.mkdir(parents=True)
            generated_file = directory / "managed.md"
            user_file = directory / "user.md"
            generated_file.write_text("<!-- AUGUR-GENERATED -->\ngenerated\n", encoding="utf-8")
            user_file.write_text("user-owned\n", encoding="utf-8")
            generated_files.append(generated_file)
            user_files.append(user_file)
        generated_skill = skills_dir / "ask" / "SKILL.md"
        user_skill = skills_dir / "user" / "SKILL.md"
        generated_skill.parent.mkdir(parents=True)
        user_skill.parent.mkdir(parents=True)
        generated_skill.write_text("<!-- AUGUR-GENERATED -->\ngenerated\n", encoding="utf-8")
        user_skill.write_text("user-owned\n", encoding="utf-8")
        generated_files.append(generated_skill)
        user_files.append(user_skill)
        (tmp_path / ".github" / "copilot-instructions.md").write_text("instructions\n", encoding="utf-8")
        (tmp_path / ".github" / "copilot-memory.md").write_text("memory\n", encoding="utf-8")
        legacy_dir.mkdir(parents=True)
        (legacy_dir / "managed.md").write_text("generated\n", encoding="utf-8")

        with patch("sync_agents.constants.PROJECT_ROOT", tmp_path):
            deleted = CopilotAdapter().cleanup()

        assert ".github/copilot-instructions.md" in deleted
        assert ".github/copilot-memory.md" in deleted
        assert ".github/copilot/" in deleted
        for generated_file in generated_files:
            assert str(generated_file.relative_to(tmp_path)) in deleted
            assert not generated_file.exists()
        for user_file in user_files:
            assert user_file.exists()
        for directory in (instructions_dir, prompts_dir, agents_dir, skills_dir):
            assert directory.exists()
        assert not generated_skill.parent.exists()
        assert user_skill.parent.exists()
        assert not legacy_dir.exists()


class TestCopilotPluginAdapter:
    def test_copilot_plugin_adapter_assembles_and_installs(self, monkeypatch, tmp_path):
        adapter = CopilotPluginAdapter()
        calls: list[tuple] = []

        def fake_assemble(target, output_dir):
            calls.append(("assemble", target, output_dir))
            return tmp_path / "out", "1.2.3"

        def fake_install(target, output, version):
            calls.append(("install", target, output, version))

        monkeypatch.setattr(adapter, "_load_assembler", lambda: (fake_assemble, fake_install))
        adapter.generate_mcp_config()

        assert calls[0][0:2] == ("assemble", "copilot")
        assert calls[1][0:2] == ("install", "copilot")
        assert calls[1][3] == "1.2.3"

    def test_copilot_plugin_adapter_manages_only_build_dir(self):
        files = CopilotPluginAdapter().get_managed_files()
        assert any(f.endswith("build/copilot/") for f in files)
        assert not any(".github" in f for f in files)

    def test_copilot_plugin_adapter_is_gated_with_copilot_group(self):
        from sync_agents import engine

        assert engine._ADAPTER_TO_GROUP["copilot_plugin"] == "copilot"

    def test_engine_lists_copilot_plugin_adapter(self):
        from sync_agents import engine

        assert "copilot_plugin" in {
            adapter.adapter_name
            for adapter in engine._get_all_adapters()
        }

    def test_sync_client_copilot_expands_to_plugin_adapter(self):
        import sync_agents

        assert sync_agents._parse_sync_client("copilot") == {"copilot", "copilot_plugin"}

    def test_sync_client_copilot_plugin_selects_only_bundle_adapter(self):
        import sync_agents

        assert "copilot-plugin" in sync_agents._SYNC_CLIENTS
        assert sync_agents._parse_sync_client("copilot-plugin") == {"copilot_plugin"}

    def test_sync_client_codex_expansion_precedent_unchanged(self):
        import sync_agents

        assert sync_agents._parse_sync_client("codex") == {"codex", "codex_plugin"}
        assert sync_agents._parse_sync_client("codex-plugin") == {"codex_plugin"}


class TestEngineGating:
    def test_load_ide_integrations_returns_dict(self):
        from sync_agents.engine import _load_ide_integrations
        config = _load_ide_integrations()
        assert isinstance(config, dict)
        assert "integrations" in config

    def test_codex_defaults_to_project_prompt_scope(self):
        from sync_agents.engine import _load_ide_integrations

        config = _load_ide_integrations()

        assert config["integrations"]["codex"]["skill_scope"] == "project"

    def test_claude_code_scope_is_project(self):
        from sync_agents.engine import _load_ide_integrations

        config = _load_ide_integrations()

        assert config["integrations"]["claude_code"]["skill_scope"] == "project"

    def test_enabled_adapter_returns_true(self):
        from sync_agents.engine import _is_adapter_enabled
        config = {"integrations": {"claude_code": {"enabled": True}}}
        assert _is_adapter_enabled("claude_code", config) is True

    def test_disabled_adapter_returns_false(self):
        from sync_agents.engine import _is_adapter_enabled
        config = {"integrations": {"cursor": {"enabled": False}}}
        assert _is_adapter_enabled("cursor", config) is False

    def test_missing_adapter_defaults_to_true(self):
        from sync_agents.engine import _is_adapter_enabled
        config = {"integrations": {}}
        assert _is_adapter_enabled("unknown_ide", config) is True

    def test_missing_enabled_key_defaults_to_true(self):
        from sync_agents.engine import _is_adapter_enabled
        config = {"integrations": {"cursor": {}}}
        assert _is_adapter_enabled("cursor", config) is True

    def test_enabled_rule_targets_respect_disabled_adapters(self):
        from sync_agents.constants import PROJECT_ROOT
        from sync_agents.engine import _get_enabled_rule_targets

        config = {
            "integrations": {
                "claude_code": {"enabled": True},
                "claude_desktop": {"enabled": False},
                "kimi": {"enabled": False},
                "codex": {"enabled": True},
                "cursor": {"enabled": False},
                "gemini": {"enabled": False},
                "windsurf": {"enabled": False},
                "copilot": {"enabled": False},
                "opencode": {"enabled": False},
                "antigravity": {"enabled": False},
            }
        }

        targets = _get_enabled_rule_targets(config)
        assert PROJECT_ROOT / "CLAUDE.md" in targets
        assert PROJECT_ROOT / "CODEX.md" in targets
        assert PROJECT_ROOT / "AGENTS.md" in targets
        assert PROJECT_ROOT / ".cursorrules" not in targets

    def test_enabled_rule_targets_respect_disabled_groups(self):
        from sync_agents.constants import PROJECT_ROOT
        from sync_agents.engine import _get_enabled_rule_targets

        config = {
            "integrations": {
                "claude_code": {"enabled": True},
                "codex": {"enabled": True},
            }
        }

        targets = _get_enabled_rule_targets(config, enabled_groups={"codex"})

        assert PROJECT_ROOT / "CODEX.md" in targets
        assert PROJECT_ROOT / "AGENTS.md" in targets
        assert PROJECT_ROOT / "CLAUDE.md" not in targets

    def test_cleanup_legacy_unsupported_exports_removes_stale_legacy_dirs(self, tmp_path):
        from sync_agents import engine

        assert not any(path.parts[-2:] == (".github", "prompts") for path in engine._LEGACY_UNSUPPORTED_EXPORTS)

        legacy_dirs = (
            tmp_path / ".codebuddy",
            tmp_path / ".continue",
        )
        for path in legacy_dirs:
            path.mkdir(parents=True)
            (path / "marker.txt").write_text("legacy\n", encoding="utf-8")

        with patch.object(engine, "PROJECT_ROOT", tmp_path), \
             patch.object(engine, "_LEGACY_UNSUPPORTED_EXPORTS", legacy_dirs):
            removed = engine._cleanup_legacy_unsupported_exports()

        assert removed == list(legacy_dirs)
        for path in legacy_dirs:
            assert not path.exists()

    def test_ensure_brain_mounts_writes_existing_registered_brains(self, tmp_path):
        from sync_agents import engine
        from src.lib.brain_registry_models import (
            Brain,
            BrainRegistry,
            BrainType,
            GitArrangement,
            GitConfig,
        )

        existing_root = tmp_path / "personal"
        missing_root = tmp_path / "missing"
        existing_root.mkdir()
        registry = BrainRegistry(
            version=1,
            brains={
                "personal": Brain(
                    id="personal",
                    type=BrainType.PERSONAL,
                    data_root=existing_root,
                    git=GitConfig(arrangement=GitArrangement.UNTRACKED),
                ),
                "offline": Brain(
                    id="offline",
                    type=BrainType.TEAM,
                    data_root=missing_root,
                    git=GitConfig(arrangement=GitArrangement.UNTRACKED),
                ),
            },
        )

        with patch("src.lib.brain_registry.get_registry", return_value=registry):
            assert engine._ensure_brain_mounts() == ["personal"]

        manifest = existing_root / "BRAIN.yaml"
        assert manifest.is_file()
        assert "id: personal" in manifest.read_text(encoding="utf-8")
        assert not (existing_root / ".augur" / "BRAIN.yaml").exists()
        assert not (missing_root / "BRAIN.yaml").exists()

    def test_sync_all_only_passes_enabled_adapters_to_skill_sync(self, tmp_path):
        from sync_agents import engine

        class DummyAdapter:
            def __init__(self, adapter_name: str):
                self.adapter_name = adapter_name
                self.cleaned = False

            def get_managed_files(self):
                return []

            def cleanup(self, exclude_paths=None):
                self.cleaned = True
                return []

            def sync_rules(self, _content):
                return None

            def generate_mcp_config(self):
                return None

            def sync_subagents(self):
                return None

            def sync_memory(self):
                return None

        rules_file = tmp_path / "agent-rules.md"
        rules_file.write_text("rules", encoding="utf-8")
        enabled = DummyAdapter("codex")
        disabled = DummyAdapter("cursor")
        captured = {}

        with patch.object(engine, "SOURCE_RULES", rules_file), \
             patch.object(engine, "SOURCE_WORKFLOWS", tmp_path / "missing.md"), \
             patch.object(engine, "_get_all_adapters", return_value=[enabled, disabled]), \
             patch.object(engine, "_load_ide_integrations", return_value={
                 "integrations": {
                     "codex": {"enabled": True},
                     "cursor": {"enabled": False},
                 }
             }), \
             patch.object(engine, "_load_enabled_groups", return_value=None), \
             patch.object(engine, "discover_claude_plugins", return_value=[]), \
             patch.object(engine, "resolve_overlaps", return_value=[]), \
             patch.object(engine, "generate_ide_manifest"), \
             patch.object(engine, "_sync_command_stubs", return_value=0), \
             patch.object(engine, "_sync_skill_stubs", side_effect=lambda adapters, **_kwargs: captured.setdefault(
                 "adapter_names", [adapter.adapter_name for adapter in adapters]
             )), \
             patch.object(engine, "_ensure_brain_mounts", return_value=[]):
            assert engine.sync_all(
                do_rules=False,
                do_subagents=False,
                do_memory=False,
                do_plugins=False,
                do_mcp_config=False,
            ) == 0

        assert captured["adapter_names"] == ["codex"]
        assert disabled.cleaned is True

    def test_selected_client_sync_skips_plugin_phase(self, tmp_path):
        from sync_agents import engine

        rules_file = tmp_path / "agent-rules.md"
        rules_file.write_text("rules", encoding="utf-8")
        adapter = SimpleNamespace(
            adapter_name="codex",
            get_managed_files=lambda: [],
            cleanup=lambda exclude_paths=None: [],
            sync_rules=lambda _content: None,
            generate_mcp_config=lambda: None,
            sync_subagents=lambda: None,
            sync_memory=lambda: None,
        )

        with patch.object(engine, "SOURCE_RULES", rules_file), \
             patch.object(engine, "SOURCE_WORKFLOWS", tmp_path / "missing.md"), \
             patch.object(engine, "_get_all_adapters", return_value=[adapter]), \
             patch.object(engine, "_load_ide_integrations", return_value={"integrations": {"codex": {"enabled": True}}}), \
             patch.object(engine, "_load_enabled_groups", return_value=None), \
             patch.object(engine, "discover_claude_plugins") as discover_plugins, \
             patch.object(engine, "generate_ide_manifest"), \
             patch.object(engine, "_sync_skill_stubs", return_value=0), \
             patch.object(engine, "_sync_prompt_stubs", return_value=0), \
             patch.object(engine, "_sync_command_stubs", return_value=0), \
             patch.object(engine, "_ensure_brain_mounts", return_value=[]):
            assert engine.sync_all(selected_clients={"codex"}, do_memory=False) == 0

        discover_plugins.assert_not_called()

    def test_selected_client_sync_disables_legacy_skill_cleanup(self, tmp_path):
        from sync_agents import engine

        rules_file = tmp_path / "agent-rules.md"
        rules_file.write_text("rules", encoding="utf-8")
        adapter = SimpleNamespace(
            adapter_name="codex",
            get_managed_files=lambda: [],
            cleanup=lambda exclude_paths=None: [],
            sync_rules=lambda _content: None,
            generate_mcp_config=lambda: None,
            sync_subagents=lambda: None,
            sync_memory=lambda: None,
        )
        captured = {}

        def capture_skill(adapters, *, cleanup_disabled=True):
            captured["skill_cleanup_disabled"] = cleanup_disabled
            return 0

        def capture_prompt(adapters, *, cleanup_disabled=True):
            captured["prompt_cleanup_disabled"] = cleanup_disabled
            return 0

        with patch.object(engine, "SOURCE_RULES", rules_file), \
             patch.object(engine, "SOURCE_WORKFLOWS", tmp_path / "missing.md"), \
             patch.object(engine, "_get_all_adapters", return_value=[adapter]), \
             patch.object(engine, "_load_ide_integrations", return_value={"integrations": {"codex": {"enabled": True}}}), \
             patch.object(engine, "_load_enabled_groups", return_value=None), \
             patch.object(engine, "discover_claude_plugins", return_value=[]), \
             patch.object(engine, "resolve_overlaps", return_value=[]), \
             patch.object(engine, "generate_ide_manifest"), \
             patch.object(engine, "_sync_skill_stubs", side_effect=capture_skill), \
             patch.object(engine, "_sync_prompt_stubs", side_effect=capture_prompt), \
             patch.object(engine, "_sync_command_stubs", return_value=0), \
             patch.object(engine, "_ensure_brain_mounts", return_value=[]):
            assert engine.sync_all(selected_clients={"codex"}, do_memory=False) == 0

        assert captured["skill_cleanup_disabled"] is False
        assert captured["prompt_cleanup_disabled"] is False


class TestCleanMode:
    def test_clean_mode_removes_managed_outputs_and_sync_manifests(self, tmp_path):
        from sync_agents import modes

        managed_dir = tmp_path / ".cursor" / "rules"
        managed_dir.mkdir(parents=True)
        (managed_dir / "prompt.md").write_text("generated\n", encoding="utf-8")

        source_skills = tmp_path / "project-brain" / "capabilities" / "skills"
        source_skills.mkdir(parents=True)
        (source_skills / "README.md").write_text("source\n", encoding="utf-8")

        source_topics = tmp_path / "docs" / "agent-topics"
        source_topics.mkdir(parents=True)
        (source_topics / "ARCHITECTURE.md").write_text("source\n", encoding="utf-8")

        antigravity_manifest = tmp_path / ".antigravity" / "ide-manifest.json"
        antigravity_manifest.parent.mkdir(parents=True)
        antigravity_manifest.write_text("{}", encoding="utf-8")

        class DummyCursorAdapter:
            adapter_name = "cursor"

            def cleanup(self, exclude_paths=None):
                CursorAdapter().cleanup(exclude_paths=exclude_paths)
                return [".cursor/rules/"]

        class DummyClaudeAdapter:
            adapter_name = "claude_code"

            def cleanup(self, exclude_paths=None):
                return ClaudeCodeAdapter().cleanup(exclude_paths=exclude_paths)

        with patch.object(modes, "PROJECT_ROOT", tmp_path), \
             patch("sync_agents.constants.PROJECT_ROOT", tmp_path), \
             patch("sync_agents.engine.PROJECT_ROOT", tmp_path), \
             patch("sync_agents.engine._LEGACY_UNSUPPORTED_EXPORTS", ()), \
             patch("sync_agents.engine._get_all_adapters", return_value=[DummyCursorAdapter(), DummyClaudeAdapter()]):
            assert modes.clean_mode() == 0

        assert not managed_dir.exists()
        assert not antigravity_manifest.exists()
        assert source_skills.exists()
        assert source_topics.exists()

    def test_main_clean_command_calls_clean_mode(self):
        import sync_agents as sync_agents_module

        with patch.object(sync_agents_module, "clean_mode", return_value=0) as mock_clean, \
             patch.object(sys, "argv", ["sync_agents", "clean"]):
            assert sync_agents_module.main() == 0

        mock_clean.assert_called_once_with()

    def test_disabled_codex_cleanup_removes_generated_agents_dir(self, tmp_path):
        codex_agents = tmp_path / ".codex" / "agents"
        codex_agents.mkdir(parents=True)
        (codex_agents / "developer.md").write_text("generated\n", encoding="utf-8")

        with patch("sync_agents.constants.PROJECT_ROOT", tmp_path), \
             patch("sync_agents.adapters.codex.PROJECT_ROOT", tmp_path), \
             patch("sync_agents.adapters.codex.CODEX_HOME", tmp_path / "home" / ".codex"):
            deleted = CodexAdapter().cleanup()

        assert ".codex/agents/" in deleted
        assert not codex_agents.exists()


class TestCleanHygieneMode:
    def test_command_surfaces_mode_prints_duplicate_report_and_returns_one(self, capsys, monkeypatch, tmp_path):
        from sync_agents import modes
        from sync_agents.command_surface import CommandDuplicate, CommandSurfaceEntry

        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'augur'\n", encoding="utf-8")
        (tmp_path / "project-brain" / "capabilities" / "skills").mkdir(parents=True)
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("AUGUR_SYNC_PROJECT_ROOT", raising=False)

        duplicate = CommandDuplicate(
            command="wiki",
            suggested_owner="claude-code-project",
            sources=[
                CommandSurfaceEntry("wiki", "claude-code-project", Path(".claude/commands/wiki.md")),
                CommandSurfaceEntry("wiki", "cowork-upload", Path("cowork/commands/wiki.md")),
            ],
        )

        with patch.object(modes, "inventory_augur_command_surfaces", return_value=["entry"]) as mock_inventory, \
             patch.object(modes, "find_duplicate_commands", return_value=[duplicate]) as mock_find, \
             patch.object(modes, "format_duplicate_report", return_value="DUPLICATE /wiki") as mock_format, \
             patch.object(modes, "_find_cowork_plugin_dirs", return_value=[Path("cowork")]):
            assert modes.command_surfaces_mode() == 1

        mock_inventory.assert_called_once_with(
            tmp_path,
            cowork_plugin_dirs=[Path("cowork")],
        )
        mock_find.assert_called_once_with(["entry"])
        mock_format.assert_called_once_with([duplicate])
        assert capsys.readouterr().out == "DUPLICATE /wiki\n"

    def test_command_surfaces_mode_prints_clean_report_and_returns_zero(self, capsys, monkeypatch, tmp_path):
        from sync_agents import modes

        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'augur'\n", encoding="utf-8")
        (tmp_path / "project-brain" / "capabilities" / "skills").mkdir(parents=True)
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("AUGUR_SYNC_PROJECT_ROOT", raising=False)

        with patch.object(modes, "inventory_augur_command_surfaces", return_value=[]) as mock_inventory, \
             patch.object(modes, "find_duplicate_commands", return_value=[]) as mock_find, \
             patch.object(modes, "format_duplicate_report", return_value="No duplicate Augur command surfaces found."), \
             patch.object(modes, "_find_cowork_plugin_dirs", return_value=[]):
            assert modes.command_surfaces_mode() == 0

        mock_inventory.assert_called_once_with(
            tmp_path,
            cowork_plugin_dirs=[],
        )
        mock_find.assert_called_once_with([])
        assert capsys.readouterr().out == "No duplicate Augur command surfaces found.\n"

    def test_command_surfaces_mode_uses_active_worktree_root_without_env_override(
        self, capsys, monkeypatch, tmp_path
    ):
        from sync_agents import modes

        main_root = tmp_path / "main"
        worktree_root = tmp_path / "worktree"
        nested_cwd = worktree_root / "project-brain" / "capabilities" / "skills" / "ai"
        for root in (main_root, worktree_root):
            (root / "pyproject.toml").parent.mkdir(parents=True, exist_ok=True)
            (root / "pyproject.toml").write_text("[project]\nname = 'augur'\n", encoding="utf-8")
            (root / "project-brain" / "capabilities" / "skills").mkdir(parents=True, exist_ok=True)
        nested_cwd.mkdir(parents=True)

        monkeypatch.chdir(nested_cwd)
        monkeypatch.delenv("AUGUR_SYNC_PROJECT_ROOT", raising=False)

        with patch.object(modes, "PROJECT_ROOT", main_root), \
             patch.object(modes, "inventory_augur_command_surfaces", return_value=[]) as mock_inventory, \
             patch.object(modes, "find_duplicate_commands", return_value=[]), \
             patch.object(modes, "format_duplicate_report", return_value="No duplicate Augur command surfaces found."), \
             patch.object(modes, "_find_cowork_plugin_dirs", return_value=[]):
            assert modes.command_surfaces_mode() == 0

        mock_inventory.assert_called_once_with(worktree_root, cowork_plugin_dirs=[])
        assert capsys.readouterr().out == "No duplicate Augur command surfaces found.\n"

    def test_command_surfaces_mode_uses_explicit_project_root_override(
        self, capsys, monkeypatch, tmp_path
    ):
        from sync_agents import modes

        explicit_root = tmp_path / "explicit"
        active_root = tmp_path / "active"
        for root in (explicit_root, active_root):
            (root / "pyproject.toml").parent.mkdir(parents=True, exist_ok=True)
            (root / "pyproject.toml").write_text("[project]\nname = 'augur'\n", encoding="utf-8")
            (root / "project-brain" / "capabilities" / "skills").mkdir(parents=True, exist_ok=True)

        monkeypatch.chdir(active_root)
        monkeypatch.setenv("AUGUR_SYNC_PROJECT_ROOT", str(explicit_root))

        with patch.object(modes, "PROJECT_ROOT", explicit_root), \
             patch.object(modes, "inventory_augur_command_surfaces", return_value=[]) as mock_inventory, \
             patch.object(modes, "find_duplicate_commands", return_value=[]), \
             patch.object(modes, "format_duplicate_report", return_value="No duplicate Augur command surfaces found."), \
             patch.object(modes, "_find_cowork_plugin_dirs", return_value=[]):
            assert modes.command_surfaces_mode() == 0

        mock_inventory.assert_called_once_with(explicit_root, cowork_plugin_dirs=[])
        assert capsys.readouterr().out == "No duplicate Augur command surfaces found.\n"

    def test_clean_hygiene_mode_removes_scaffolding_and_preserves_state(self, tmp_path):
        from sync_agents import modes

        for relative_path in (
            ".claude/launch.json",
            ".claude/settings.json.example",
            ".codex/INSTALL.md",
            ".antigravity/INSTALL.md",
            ".opencode/INSTALL.md",
            ".cowork/INSTALL.md",
            ".agents/plugins/marketplace.json",
        ):
            target = tmp_path / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("artifact\n", encoding="utf-8")

        for relative_dir in (
            ".claude/plans",
            ".claude/projects",
            ".claude-plugin",
            ".cursor-plugin",
            ".playwright-mcp",
        ):
            target_dir = tmp_path / relative_dir
            target_dir.mkdir(parents=True, exist_ok=True)
            (target_dir / "marker.txt").write_text("artifact\n", encoding="utf-8")

        preserved_claude_config = tmp_path / ".claude" / "settings.json"
        preserved_claude_config.parent.mkdir(parents=True, exist_ok=True)
        preserved_claude_config.write_text("{\"keep\": true}\n", encoding="utf-8")

        preserved_source_dir = tmp_path / ".antigravity" / "workflows"
        preserved_source_dir.mkdir(parents=True)
        (preserved_source_dir / "onboard.md").write_text("keep\n", encoding="utf-8")

        with patch.object(modes, "PROJECT_ROOT", tmp_path):
            assert modes.clean_hygiene_mode() == 0

        assert not (tmp_path / ".codex").exists()
        assert not (tmp_path / ".antigravity" / "INSTALL.md").exists()
        assert not (tmp_path / ".opencode").exists()
        assert not (tmp_path / ".cowork").exists()
        assert not (tmp_path / ".claude" / "launch.json").exists()
        assert not (tmp_path / ".claude" / "settings.json.example").exists()
        assert not (tmp_path / ".claude" / "plans").exists()
        assert not (tmp_path / ".claude" / "projects").exists()
        assert not (tmp_path / ".claude-plugin").exists()
        assert not (tmp_path / ".cursor-plugin").exists()
        assert not (tmp_path / ".agents").exists()
        assert not (tmp_path / ".playwright-mcp").exists()
        assert preserved_claude_config.exists()
        assert preserved_source_dir.exists()

    def test_main_clean_hygiene_command_calls_clean_hygiene_mode(self):
        import sync_agents as sync_agents_module

        with patch.object(sync_agents_module, "clean_hygiene_mode", return_value=0) as mock_clean_hygiene, \
             patch.object(sys, "argv", ["sync_agents", "clean-hygiene"]):
            assert sync_agents_module.main() == 0

        mock_clean_hygiene.assert_called_once_with()

    def test_main_command_surfaces_dispatches_report_mode(self):
        import sync_agents as sync_agents_module

        with patch.object(sync_agents_module, "command_surfaces_mode", return_value=1) as mock_report, \
             patch.object(sys, "argv", ["sync_agents", "command-surfaces"]):
            assert sync_agents_module.main() == 1

        mock_report.assert_called_once_with()

    def test_main_sync_commands_client_dispatches_selected_client(self):
        import sync_agents as sync_agents_module

        with patch.object(sync_agents_module, "sync_all", return_value=0) as mock_sync, \
             patch.object(sys, "argv", ["sync_agents", "sync", "commands", "claude-code"]):
            assert sync_agents_module.main() == 0

        mock_sync.assert_called_once_with(
            do_rules=False,
            do_subagents=False,
            do_memory=False,
            do_plugins=False,
            do_mcp_config=False,
            do_skill_exports=False,
            do_prompt_exports=False,
            selected_clients={"claude_code"},
        )

    def test_main_sync_commands_client_accepts_gemini_plugin_alias(self):
        import sync_agents as sync_agents_module

        with patch.object(sync_agents_module, "sync_all", return_value=0) as mock_sync, \
             patch.object(sys, "argv", ["sync_agents", "sync", "commands", "gemini-plugin"]):
            assert sync_agents_module.main() == 0

        mock_sync.assert_called_once_with(
            do_rules=False,
            do_subagents=False,
            do_memory=False,
            do_plugins=False,
            do_mcp_config=False,
            do_skill_exports=False,
            do_prompt_exports=False,
            selected_clients={"gemini_plugin"},
        )

    def test_main_sync_all_codex_includes_codex_plugin(self):
        import sync_agents as sync_agents_module

        with patch.object(sync_agents_module, "sync_all", return_value=0) as mock_sync, \
             patch.object(sys, "argv", ["sync_agents", "sync", "all", "codex"]):
            assert sync_agents_module.main() == 0

        mock_sync.assert_called_once_with(selected_clients={"codex", "codex_plugin"})

    def test_main_sync_all_defaults_without_args(self):
        import sync_agents as sync_agents_module

        with patch.object(sync_agents_module, "sync_all", return_value=0) as mock_sync, \
             patch.object(sys, "argv", ["sync_agents"]):
            assert sync_agents_module.main() == 0

        mock_sync.assert_called_once_with(selected_clients=None)

    def test_clean_hygiene_mode_removes_read_only_files(self, tmp_path):
        from sync_agents import modes

        target = tmp_path / ".codex" / "INSTALL.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("artifact\n", encoding="utf-8")
        target.chmod(0o444)

        with patch.object(modes, "PROJECT_ROOT", tmp_path):
            assert modes.clean_hygiene_mode() == 0

        assert not target.exists()

    def test_sync_all_preserves_shared_targets_owned_by_enabled_adapter(self, tmp_path):
        from sync_agents import engine

        rules_file = tmp_path / "agent-rules.md"
        rules_file.write_text("rules", encoding="utf-8")
        shared_target = tmp_path / "CLAUDE.md"

        class EnabledAdapter:
            adapter_name = "claude_code"

            def get_managed_files(self):
                return ["CLAUDE.md"]

            def cleanup(self, exclude_paths=None):
                return []

            def sync_rules(self, _content):
                shared_target.write_text("generated\n", encoding="utf-8")

            def generate_mcp_config(self):
                return None

            def sync_subagents(self):
                return None

            def sync_memory(self):
                return None

        class DisabledSharedAdapter:
            adapter_name = "claude_desktop"

            def __init__(self):
                self.exclude_paths = None

            def cleanup(self, exclude_paths=None):
                self.exclude_paths = exclude_paths
                if exclude_paths and shared_target.resolve() in exclude_paths:
                    return []
                if shared_target.exists():
                    shared_target.unlink()
                return ["CLAUDE.md"]

            def get_managed_files(self):
                return ["CLAUDE.md"]

            def sync_rules(self, _content):
                return None

            def generate_mcp_config(self):
                return None

            def sync_subagents(self):
                return None

            def sync_memory(self):
                return None

        enabled = EnabledAdapter()
        disabled = DisabledSharedAdapter()

        with patch.object(engine, "PROJECT_ROOT", tmp_path), \
             patch.object(engine, "SOURCE_RULES", rules_file), \
             patch.object(engine, "SOURCE_WORKFLOWS", tmp_path / "missing.md"), \
             patch.object(engine, "_get_all_adapters", return_value=[enabled, disabled]), \
             patch.object(engine, "_load_ide_integrations", return_value={
                 "integrations": {
                     "claude_code": {"enabled": True},
                     "claude_desktop": {"enabled": False},
                 }
             }), \
             patch.object(engine, "_load_enabled_groups", return_value=None), \
             patch.object(engine, "discover_claude_plugins", return_value=[]), \
             patch.object(engine, "resolve_overlaps", return_value=[]), \
             patch.object(engine, "generate_ide_manifest"), \
             patch.object(engine, "_sync_command_stubs", return_value=0), \
             patch.object(engine, "_sync_skill_stubs", return_value=0), \
             patch.object(engine, "_ensure_brain_mounts", return_value=[]):
            assert engine.sync_all(
                do_rules=True,
                do_subagents=False,
                do_memory=False,
                do_plugins=False,
                do_mcp_config=False,
            ) == 0

        assert shared_target.exists()
        assert disabled.exclude_paths is not None
        assert shared_target.resolve() in disabled.exclude_paths

    def test_fix_mode_only_passes_enabled_adapters_to_skill_sync(self, tmp_path):
        from sync_agents import modes

        class DummyAdapter:
            def __init__(self, adapter_name: str):
                self.adapter_name = adapter_name
                self.cleaned = False

            def get_managed_files(self):
                return []

            def cleanup(self, exclude_paths=None):
                self.cleaned = True
                return []

            def sync_rules(self, _content):
                return None

            def generate_mcp_config(self):
                return None

            def sync_subagents(self):
                return None

            def sync_memory(self):
                return None

        rules_file = tmp_path / "agent-rules.md"
        rules_file.write_text("rules", encoding="utf-8")
        enabled = DummyAdapter("codex")
        disabled = DummyAdapter("cursor")
        captured = {}

        with patch.object(modes, "SOURCE_RULES", rules_file), \
             patch.object(modes, "SOURCE_WORKFLOWS", tmp_path / "missing.md"), \
             patch.object(modes, "check_mode", return_value=1), \
             patch("sync_agents.engine._get_all_adapters", return_value=[enabled, disabled]), \
             patch("sync_agents.engine._load_ide_integrations", return_value={
                 "integrations": {
                     "codex": {"enabled": True},
                     "cursor": {"enabled": False},
                 }
             }), \
             patch.object(modes, "discover_claude_plugins", return_value=[]), \
             patch.object(modes, "resolve_overlaps", return_value=[]), \
             patch.object(modes, "generate_ide_manifest"), \
             patch("sync_agents.engine._get_enabled_rule_targets", return_value=[]), \
             patch("sync_agents.engine._sync_command_stubs", return_value=0), \
             patch("sync_agents.engine._sync_skill_stubs", side_effect=lambda adapters, **_kwargs: captured.setdefault(
                 "adapter_names", [adapter.adapter_name for adapter in adapters]
             )):
            assert modes.fix_mode() == 0

        assert captured["adapter_names"] == ["codex"]
        assert disabled.cleaned is True


class TestSkillScopeCleanup:
    def test_export_filter_normalizes_claude_code_target_alias(self, monkeypatch):
        from src.lib.capabilities import export_filter

        _patch_capability_exports(
            monkeypatch,
            "skill",
            {"brief": ("claude",)},
        )

        assert export_filter.allowed_generated_names(
            "skill",
            ["brief"],
            target="claude-code",
            existing_names=set(),
        ) == {"brief"}

    def test_export_filter_warns_when_policy_resolution_fails_closed(
        self, monkeypatch, caplog
    ):
        from src.lib.capabilities import export_filter

        def fail_resolution():
            raise RuntimeError("policy unavailable")

        monkeypatch.setattr(export_filter, "_resolved_records_by_id", fail_resolution)

        with caplog.at_level("WARNING", logger="src.lib.capabilities.export_filter"):
            allowed = export_filter.allowed_generated_names(
                "skill",
                ["existing", "new"],
                target="claude_code",
                existing_names={"existing"},
            )

        assert allowed == {"existing"}
        assert "Capability export policy resolution failed" in caplog.text

    def test_skill_export_preserves_existing_unclassified_but_blocks_new_unclassified(
        self, tmp_path, monkeypatch
    ):
        from sync_agents.skill_sync import _sync_skill_stubs

        skill_root = tmp_path / "project-brain" / "capabilities" / "skills" / "knowledge"
        skill_root.mkdir(parents=True)
        (skill_root / "SKILL.md").write_text(
            "---\nname: knowledge\ndescription: Knowledge search\n---\n# Knowledge\n",
            encoding="utf-8",
        )

        new_root = tmp_path / "project-brain" / "capabilities" / "skills" / "new-skill"
        new_root.mkdir(parents=True)
        (new_root / "SKILL.md").write_text(
            "---\n"
            "name: new-skill\n"
            "description: New unclassified skill\n"
            "---\n"
            "# New Skill\n",
            encoding="utf-8",
        )

        claude_dir = tmp_path / ".claude" / "skills"
        managed_dir = claude_dir / "knowledge"
        managed_dir.mkdir(parents=True)
        (managed_dir / "SKILL.md").write_text("stale managed\n", encoding="utf-8")
        (claude_dir / ".augur-generated-prompts.json").write_text(
            json.dumps({"files": ["knowledge/SKILL.md"]}),
            encoding="utf-8",
        )

        monkeypatch.setattr(
            "src.lib.capabilities.export_filter._resolved_records_by_id", lambda: {}
        )

        project_codex_prompts = tmp_path / ".codex" / "prompts"
        global_codex_prompts = tmp_path / "home" / ".codex" / "prompts"
        project_codex_native = tmp_path / ".codex" / "skills"
        global_codex_native = tmp_path / "home" / ".agents" / "skills" / "augur"

        with (
            patch("sync_agents.skill_sync.PROJECT_ROOT", tmp_path),
            patch(
                "sync_agents.skill_sync._resolve_client_skill_dirs",
                return_value=[("claude-local", claude_dir, True)],
            ),
            patch(
                "sync_agents.skill_sync._load_skill_scopes",
                return_value={"claude-code": "project"},
            ),
            patch(
                "sync_agents.skill_sync.get_codex_prompt_dir",
                side_effect=[project_codex_prompts, global_codex_prompts],
            ),
            patch(
                "sync_agents.skill_sync.get_codex_native_skills_dir",
                side_effect=[project_codex_native, global_codex_native],
            ),
        ):
            written = _sync_skill_stubs([SimpleNamespace(adapter_name="claude_code")])

        assert written == 1
        assert (
            (managed_dir / "SKILL.md")
            .read_text(encoding="utf-8")
            .startswith("---\nname: knowledge\n")
        )
        assert not (claude_dir / "new-skill" / "SKILL.md").exists()

    def test_skill_sync_removes_policy_denied_exports_and_manifest_entries(
        self, tmp_path, monkeypatch
    ):
        from sync_agents.skill_sync import _sync_skill_stubs

        _patch_capability_exports(
            monkeypatch,
            "skill",
            {
                "allowed": ("gemini",),
                "stale": ("claude",),
            },
        )

        for name in ("allowed", "stale"):
            skill_root = tmp_path / "project-brain" / "capabilities" / "skills" / name
            skill_root.mkdir(parents=True)
            (skill_root / "SKILL.md").write_text(
                f"---\nname: {name}\ndescription: {name}\n---\n# {name}\n",
                encoding="utf-8",
            )

        gemini_dir = tmp_path / ".antigravity" / "plugins"
        stale_dir = gemini_dir / "stale"
        stale_dir.mkdir(parents=True)
        (stale_dir / "SKILL.md").write_text("stale managed\n", encoding="utf-8")
        (gemini_dir / ".augur-generated-prompts.json").write_text(
            json.dumps({"files": ["stale/SKILL.md"]}),
            encoding="utf-8",
        )

        with (
            patch("sync_agents.skill_sync.PROJECT_ROOT", tmp_path),
            patch(
                "sync_agents.skill_sync._resolve_client_skill_dirs",
                return_value=[("gemini-local", gemini_dir, True)],
            ),
            patch(
                "sync_agents.skill_sync._load_skill_scopes",
                return_value={"gemini": "project"},
            ),
        ):
            written = _sync_skill_stubs([SimpleNamespace(adapter_name="gemini")])

        assert written == 1
        assert (gemini_dir / "allowed" / "SKILL.md").is_file()
        assert not stale_dir.exists()
        manifest = json.loads(
            (gemini_dir / ".augur-generated-prompts.json").read_text(encoding="utf-8")
        )
        assert manifest == {"files": ["allowed/SKILL.md"]}

    def test_command_export_policy_blocks_new_unclassified_wrappers(
        self, tmp_path, monkeypatch
    ):
        from sync_agents.skill_sync import _sync_command_stubs

        skill_root = tmp_path / "project-brain" / "capabilities" / "skills" / "augur-core"
        (skill_root / "commands").mkdir(parents=True)
        (skill_root / "commands" / "experimental.md").write_text(
            "---\n"
            "id: experimental\n"
            "description: Experimental command\n"
            "x-augur-export-command: true\n"
            "---\n"
            "# /experimental\n",
            encoding="utf-8",
        )

        monkeypatch.setattr(
            "src.lib.capabilities.export_filter._resolved_records_by_id", lambda: {}
        )

        with (
            patch("sync_agents.skill_sync.PROJECT_ROOT", tmp_path),
            patch("sync_agents.generators.PROJECT_ROOT", tmp_path),
            patch("sync_agents.constants.PROJECT_ROOT", tmp_path),
        ):
            written = _sync_command_stubs([SimpleNamespace(adapter_name="gemini")])

        assert written == 0
        assert not (tmp_path / ".antigravity" / "plugins" / "experimental").exists()

    def test_command_export_policy_preserves_existing_unclassified_target_wrapper(
        self, monkeypatch
    ):
        from src.lib.capabilities import export_filter
        from src.lib.capabilities.discovery import capability_id
        from src.lib.capabilities.exposure_policy import (
            CapabilityDiscovery,
            resolve_capability_records,
        )

        command_id = capability_id("command", "ask")
        resolved = resolve_capability_records(
            [
                CapabilityDiscovery(
                    id=command_id,
                    type="command",
                    current_exposure=("agents-md", "browse"),
                )
            ],
            policy={"capabilities": {}},
        )
        monkeypatch.setattr(
            export_filter,
            "_resolved_records_by_id",
            lambda: {record.id: record for record in resolved},
        )

        assert export_filter.allowed_generated_names(
            "command",
            ["ask", "new-command"],
            target="gemini",
            existing_names={"ask"},
        ) == {"ask"}

    def test_prompt_source_loader_includes_shared_vault_prompt_directory(self, tmp_path):
        from sync_agents.skill_sync import _load_prompt_sources

        skills_dir = tmp_path / "project-brain" / "capabilities" / "skills"
        skill_root = skills_dir / "ingest"
        (skill_root / "prompts").mkdir(parents=True)
        (skill_root / "prompts" / "ingest-content.md").write_text(
            "---\n"
            "id: ingest-content\n"
            "description: Process dropped content\n"
            "---\n"
            "Process dropped content.\n",
            encoding="utf-8",
        )

        sources = _load_prompt_sources(skills_dir)

        assert [source[0] for source in sources] == ["ingest-content"]
        assert sources[0][1] == skill_root / "prompts" / "ingest-content.md"
        assert sources[0][4] == "Process dropped content"

    def test_disabled_client_cleanup_removes_only_managed_files(self, tmp_path):
        from sync_agents.skill_sync import _cleanup_disabled_client_outputs

        cursor_dir = tmp_path / ".cursor" / "rules"
        cursor_dir.mkdir(parents=True)
        managed_prompt = cursor_dir / "commands.md"
        managed_prompt.write_text("managed\n", encoding="utf-8")
        user_prompt = cursor_dir / "notes.md"
        user_prompt.write_text("user\n", encoding="utf-8")
        (cursor_dir / ".augur-generated-prompts.json").write_text(
            json.dumps({"files": ["commands.md"]}),
            encoding="utf-8",
        )

        removed = _cleanup_disabled_client_outputs(
            [("cursor-local", cursor_dir, False)],
            enabled_ids={"codex"},
        )

        assert removed == 1
        assert not managed_prompt.exists()
        assert user_prompt.exists()
        assert not (cursor_dir / ".augur-generated-prompts.json").exists()

    def test_command_sync_exports_only_explicit_command_docs(
        self, tmp_path, monkeypatch
    ):
        from sync_agents.skill_sync import _sync_command_stubs

        _patch_capability_exports(
            monkeypatch,
            "command",
            {"dev-build": ("claude",)},
        )

        skill_root = tmp_path / "project-brain" / "capabilities" / "skills" / "devops"
        (skill_root / "commands").mkdir(parents=True)
        (skill_root / "commands" / "dev-build.md").write_text(
            "---\n"
            "x-augur-export-command: true\n"
            "description: Rebuild the dashboard\n"
            "visibility: dev\n"
            "---\n"
            "# /dev-build\n",
            encoding="utf-8",
        )
        (skill_root / "commands" / "review-task.md").write_text(
            "---\n"
            "id: review-task\n"
            "description: Review a task\n"
            "skill: platform-admin\n"
            "---\n"
            "Review the task.\n",
            encoding="utf-8",
        )

        with (
            patch("sync_agents.skill_sync.PROJECT_ROOT", tmp_path),
            patch("sync_agents.generators.PROJECT_ROOT", tmp_path),
            patch("sync_agents.constants.PROJECT_ROOT", tmp_path),
        ):
            written = _sync_command_stubs([SimpleNamespace(adapter_name="claude_code")])

        command_file = tmp_path / ".claude" / "commands" / "dev-build.md"
        assert written == 1
        assert command_file.exists()
        assert not (tmp_path / ".claude" / "commands" / "review-task.md").exists()
        # Description must come from frontmatter, not the auto-generated HTML comment.
        content = command_file.read_text(encoding="utf-8")
        assert "description: Rebuild the dashboard" in content
        assert content.index("description:") < content.index("<!--")

    def test_command_sync_exports_only_commands_marked_for_client_export(
        self, tmp_path, monkeypatch
    ):
        from sync_agents.skill_sync import _sync_command_stubs

        _patch_capability_exports(
            monkeypatch,
            "command",
            {"ask": ("claude",)},
        )

        exported_root = tmp_path / "project-brain" / "capabilities" / "skills" / "augur-core"
        (exported_root / "commands").mkdir(parents=True)
        (exported_root / "commands" / "ask.md").write_text(
            "---\n"
            "id: ask\n"
            "description: Ask your second brain\n"
            "x-augur-export-command: true\n"
            "---\n"
            "# /ask\n",
            encoding="utf-8",
        )

        hidden_root = tmp_path / "project-brain" / "capabilities" / "skills" / "devops"
        (hidden_root / "commands").mkdir(parents=True)
        (hidden_root / "commands" / "internal-ops.md").write_text(
            "---\n"
            "id: internal-ops\n"
            "description: Internal maintenance\n"
            "---\n"
            "# /internal-ops\n",
            encoding="utf-8",
        )

        with (
            patch("sync_agents.skill_sync.PROJECT_ROOT", tmp_path),
            patch("sync_agents.generators.PROJECT_ROOT", tmp_path),
            patch("sync_agents.constants.PROJECT_ROOT", tmp_path),
        ):
            written = _sync_command_stubs([SimpleNamespace(adapter_name="claude_code")])

        assert written == 1
        assert (tmp_path / ".claude" / "commands" / "ask.md").exists()
        assert not (tmp_path / ".claude" / "commands" / "internal-ops.md").exists()

    def test_command_sync_cleans_stale_generated_command_when_flag_removed(
        self, tmp_path
    ):
        from sync_agents.skill_sync import _sync_command_stubs

        skill_root = tmp_path / "project-brain" / "capabilities" / "skills" / "augur-core"
        (skill_root / "commands").mkdir(parents=True)
        (skill_root / "commands" / "ask.md").write_text(
            "---\nid: ask\ndescription: Ask your second brain\n---\n# /ask\n",
            encoding="utf-8",
        )

        commands_dir = tmp_path / ".claude" / "commands"
        commands_dir.mkdir(parents=True)
        (commands_dir / "ask.md").write_text("generated\n", encoding="utf-8")
        (commands_dir / ".augur-generated-commands.json").write_text(
            json.dumps({"files": ["ask.md"]}),
            encoding="utf-8",
        )

        with (
            patch("sync_agents.skill_sync.PROJECT_ROOT", tmp_path),
            patch("sync_agents.generators.PROJECT_ROOT", tmp_path),
            patch("sync_agents.constants.PROJECT_ROOT", tmp_path),
        ):
            written = _sync_command_stubs([SimpleNamespace(adapter_name="claude_code")])

        assert written == 0
        assert not (commands_dir / "ask.md").exists()

    def test_command_sync_exports_flagged_commands_to_codex_and_gemini_skill_dirs(
        self, tmp_path, monkeypatch
    ):
        from sync_agents.skill_sync import _sync_command_stubs

        _patch_capability_exports(
            monkeypatch,
            "command",
            {"ask": ("codex", "gemini")},
        )

        skill_root = tmp_path / "project-brain" / "capabilities" / "skills" / "augur-core"
        (skill_root / "commands").mkdir(parents=True)
        (skill_root / "commands" / "ask.md").write_text(
            "---\n"
            "id: ask\n"
            "description: Ask your second brain\n"
            "x-augur-export-command: true\n"
            "---\n"
            "# /ask\n\n"
            "Ask your second brain.\n",
            encoding="utf-8",
        )

        with patch("sync_agents.skill_sync.PROJECT_ROOT", tmp_path), \
             patch("sync_agents.generators.PROJECT_ROOT", tmp_path), \
             patch("sync_agents.constants.PROJECT_ROOT", tmp_path):
            written = _sync_command_stubs(
                [
                    SimpleNamespace(adapter_name="codex"),
                    SimpleNamespace(adapter_name="gemini"),
                ]
            )

        codex_skill = tmp_path / ".codex" / "skills" / "ask" / "SKILL.md"
        gemini_skill = tmp_path / ".antigravity" / "plugins" / "ask" / "SKILL.md"
        assert written == 2
        assert codex_skill.exists()
        assert gemini_skill.exists()
        codex_text = codex_skill.read_text(encoding="utf-8")
        gemini_text = gemini_skill.read_text(encoding="utf-8")
        assert "name: ask" in codex_text
        assert "description: Ask your second brain" in codex_text
        assert "# /ask" in codex_text
        assert "AUTO-GENERATED FILE" in codex_text
        assert "name: ask" in gemini_text
        assert "description: Ask your second brain" in gemini_text
        assert "# /ask" in gemini_text
        assert "AUTO-GENERATED FILE" in gemini_text

    def test_workflows_table_uses_filtered_primary_command_surface(self, monkeypatch):
        from sync_agents.templates import _generate_workflows_table
        from src.plugins import command_discovery, command_listing

        monkeypatch.setattr(
            command_discovery,
            "discover_commands",
            lambda: [
                SimpleNamespace(id="adr", visibility="project"),
                SimpleNamespace(id="dev", visibility="project"),
                SimpleNamespace(id="sweep", visibility="project"),
                SimpleNamespace(id="dev-build", visibility="dev"),
            ],
        )
        monkeypatch.setattr(
            command_listing,
            "render_commands_payload",
            lambda: {
                "slash_commands": [
                    {
                        "key": "core",
                        "label": "Core Commands",
                        "commands": [
                            {"id": "ask"},
                            {"id": "discover"},
                            {"id": "keep"},
                            {"id": "project"},
                        ],
                    },
                    {
                        "key": "dev",
                        "label": "Dev Commands",
                        "commands": [
                            {"id": "routines"},
                            {"id": "skillify"},
                        ],
                    },
                ]
            },
        )

        text = _generate_workflows_table()

        assert "`/project`" in text
        for forbidden in ("`/adr`", "`/dev`", "`/sweep`", "`/dev-build`", "`/dev-debug`", "`/dev-merge`"):
            assert forbidden not in text

    def test_canonical_project_command_exports_without_retired_project_commands(self):
        from sync_agents.skill_sync import _load_command_sources

        repo_root = Path(__file__).resolve().parents[7]
        exported = {
            name
            for name, _source_path, _raw in _load_command_sources(
                repo_root / "project-brain" / "capabilities" / "skills"
            )
        }

        assert exported == {"ask", "discover", "keep", "project", "routines", "skillify"}
        assert "adr" not in exported
        assert "dev" not in exported
        assert "sweep" not in exported
        assert "wiki" not in exported
        assert "dev-loops" not in exported
        assert "dev-merge" not in exported

    def test_canonical_codex_command_exports_include_project_router(self):
        from sync_agents.skill_sync import _load_command_sources
        from src.lib.capabilities.export_filter import filter_named_sources

        repo_root = Path(__file__).resolve().parents[7]
        sources = _load_command_sources(repo_root / "project-brain" / "capabilities" / "skills")
        exported = {
            name
            for name, _source_path, _raw in filter_named_sources(
                "command",
                sources,
                target="codex",
                existing_names=set(),
            )
        }

        assert exported == {"ask", "discover", "keep", "project", "routines", "skillify"}
        assert "adr" not in exported
        assert "dev" not in exported
        assert "sweep" not in exported
        assert "dev-build" not in exported
        assert "dev-debug" not in exported
        assert "dev-loops" not in exported
        assert "dev-merge" not in exported

    def test_canonical_gemini_command_exports_match_project_router_surface(self):
        from sync_agents.skill_sync import _load_command_sources
        from src.lib.capabilities.export_filter import filter_named_sources

        repo_root = Path(__file__).resolve().parents[7]
        sources = _load_command_sources(repo_root / "project-brain" / "capabilities" / "skills")
        exported = {
            name
            for name, _source_path, _raw in filter_named_sources(
                "command",
                sources,
                target="gemini",
                existing_names=set(),
            )
        }

        assert exported == {"ask", "discover", "keep", "project", "routines", "skillify"}
        assert "adr" not in exported
        assert "dev" not in exported
        assert "sweep" not in exported
        assert "dev-build" not in exported
        assert "dev-debug" not in exported
        assert "dev-loops" not in exported
        assert "dev-merge" not in exported

    def test_command_sync_cleans_stale_codex_and_gemini_skill_wrappers_when_flag_removed(self, tmp_path):
        from sync_agents.skill_sync import _sync_command_stubs

        skill_root = tmp_path / "project-brain" / "capabilities" / "skills" / "augur-core"
        (skill_root / "commands").mkdir(parents=True)
        (skill_root / "commands" / "ask.md").write_text(
            "---\n"
            "id: ask\n"
            "description: Ask your second brain\n"
            "---\n"
            "# /ask\n",
            encoding="utf-8",
        )

        codex_dir = tmp_path / ".codex" / "skills"
        gemini_dir = tmp_path / ".antigravity" / "plugins"
        (codex_dir / "ask").mkdir(parents=True)
        (codex_dir / "ask" / "SKILL.md").write_text("generated\n", encoding="utf-8")
        (gemini_dir / "ask").mkdir(parents=True)
        (gemini_dir / "ask" / "SKILL.md").write_text("generated\n", encoding="utf-8")
        (codex_dir / ".augur-generated-commands.json").write_text(
            json.dumps({"files": ["ask"]}),
            encoding="utf-8",
        )
        (gemini_dir / ".augur-generated-commands.json").write_text(
            json.dumps({"files": ["ask"]}),
            encoding="utf-8",
        )

        with patch("sync_agents.skill_sync.PROJECT_ROOT", tmp_path), \
             patch("sync_agents.generators.PROJECT_ROOT", tmp_path), \
             patch("sync_agents.constants.PROJECT_ROOT", tmp_path):
            written = _sync_command_stubs(
                [
                    SimpleNamespace(adapter_name="codex"),
                    SimpleNamespace(adapter_name="gemini"),
                ]
            )

        assert written == 0
        assert not (codex_dir / "ask").exists()
        assert not (gemini_dir / "ask").exists()
        assert not (codex_dir / ".augur-generated-commands.json").exists()
        assert not (gemini_dir / ".augur-generated-commands.json").exists()

    def test_codex_non_native_prompts_are_mcp_only(self, tmp_path):
        from sync_agents.skill_sync import _sync_prompt_stubs

        skill_root = tmp_path / "project-brain" / "capabilities" / "skills" / "advisor"
        (skill_root / "commands").mkdir(parents=True)
        (skill_root / "commands" / "triage-backlog.md").write_text(
            "---\n"
            "id: triage-backlog\n"
            "description: Prioritize backlog items\n"
            "skill: advisor\n"
            "---\n"
            "Triage the backlog.\n",
            encoding="utf-8",
        )

        project_codex = tmp_path / ".codex" / "prompts"
        global_codex = tmp_path / "home" / ".codex" / "prompts"
        project_codex.mkdir(parents=True)
        global_codex.mkdir(parents=True)
        fake_adapter = SimpleNamespace(adapter_name="codex")

        with patch("sync_agents.skill_sync.PROJECT_ROOT", tmp_path), \
             patch("sync_agents.skill_sync.get_codex_prompt_dir", side_effect=lambda scope: project_codex if scope == "project" else global_codex):
            written = _sync_prompt_stubs([fake_adapter])

        assert written == 0
        assert not (project_codex / "triage-backlog.md").exists()
        assert not (global_codex / "triage-backlog.md").exists()

    def test_codex_global_prompt_sync_preserves_user_files(self, tmp_path):
        from sync_agents.skill_sync import _sync_prompt_stubs

        skill_root = tmp_path / "project-brain" / "capabilities" / "skills" / "apple"
        (skill_root / "commands").mkdir(parents=True)
        (skill_root / "commands" / "apple-brief.md").write_text(
            "---\n"
            "id: apple-brief\n"
            "description: Brief Apple updates\n"
            "skill: apple\n"
            "---\n"
            "Summarize Apple updates.\n",
            encoding="utf-8",
        )

        project_codex = tmp_path / ".codex" / "prompts"
        global_codex = tmp_path / "home" / ".codex" / "prompts"
        project_codex.mkdir(parents=True)
        global_codex.mkdir(parents=True)

        managed_prompt = global_codex / "apple-brief.md"
        managed_prompt.write_text("# apple\n")
        (global_codex / ".augur-generated-prompts.json").write_text(
            json.dumps({"files": ["apple-brief.md"]})
        )

        user_prompt = global_codex / "pdf.md"
        user_prompt.write_text("# PDF\n")

        fake_adapter = SimpleNamespace(adapter_name="codex")

        with patch("sync_agents.skill_sync.PROJECT_ROOT", tmp_path), \
             patch("sync_agents.skill_sync.get_codex_prompt_dir", side_effect=[project_codex, global_codex]):
            written = _sync_prompt_stubs([fake_adapter])

        assert written == 0
        assert not (project_codex / "apple-brief.md").exists()
        assert not managed_prompt.exists()
        assert not (global_codex / ".augur-generated-prompts.json").exists()
        assert user_prompt.exists()

    def test_codex_prompts_include_frontmatter_for_command_discovery(self, tmp_path):
        from sync_agents.skill_sync import _sync_prompt_stubs

        skill_root = tmp_path / "project-brain" / "capabilities" / "skills" / "dev-test"
        (skill_root / "commands").mkdir(parents=True)
        (skill_root / "SKILL.md").write_text(
            "---\n"
            "name: dev-test\n"
            "description: Dev test skill\n"
            "---\n"
            "# Dev Test\n",
            encoding="utf-8",
        )
        (skill_root / "commands" / "run-suite.md").write_text(
            "---\n"
            "id: run-suite\n"
            "description: Run test verticals\n"
            "skill: dev-test\n"
            "---\n"
            "# /run-suite\n\n"
            "Run the project test suite.\n",
            encoding="utf-8",
        )

        project_codex = tmp_path / ".codex" / "prompts"
        project_codex.mkdir(parents=True)
        global_codex = tmp_path / "home" / ".codex" / "prompts"
        fake_adapter = SimpleNamespace(adapter_name="codex")

        with patch("sync_agents.skill_sync.PROJECT_ROOT", tmp_path), \
             patch("sync_agents.skill_sync.get_codex_prompt_dir", side_effect=lambda scope: project_codex if scope == "project" else global_codex):
            written = _sync_prompt_stubs([fake_adapter])

        assert written == 0
        assert not (project_codex / "run-suite.md").exists()
        assert not (global_codex / "run-suite.md").exists()

    def test_codex_exports_skill_registry_commands_without_prompt_frontmatter(self, tmp_path):
        from sync_agents.skill_sync import _sync_prompt_stubs

        skill_root = tmp_path / "project-brain" / "capabilities" / "skills" / "augur-core"
        (skill_root / "commands").mkdir(parents=True)
        (skill_root / "SKILL.md").write_text(
            "---\n"
            "name: augur-core\n"
            "description: Core Augur workflows\n"
            "x-augur-commands:\n"
            "  - id: ask\n"
            "    description: Ask your second brain\n"
            "---\n"
            "# Augur Core\n",
            encoding="utf-8",
        )
        (skill_root / "commands" / "ask.md").write_text(
            "# /ask\n\n"
            "Ask your second brain.\n",
            encoding="utf-8",
        )

        project_codex = tmp_path / ".codex" / "prompts"
        global_codex = tmp_path / "home" / ".codex" / "prompts"
        project_codex.mkdir(parents=True)
        fake_adapter = SimpleNamespace(adapter_name="codex")

        with patch("sync_agents.skill_sync.PROJECT_ROOT", tmp_path), \
             patch("sync_agents.skill_sync.get_codex_prompt_dir", side_effect=lambda scope: project_codex if scope == "project" else global_codex):
            written = _sync_prompt_stubs([fake_adapter])

        assert written == 0
        assert not (project_codex / "ask.md").exists()
        assert not (global_codex / "ask.md").exists()

    def test_codex_syncs_native_prompts_to_global_runtime_registry(self, tmp_path):
        from sync_agents.skill_sync import _sync_prompt_stubs

        skill_root = tmp_path / "project-brain" / "capabilities" / "skills" / "augur-core"
        (skill_root / "commands").mkdir(parents=True)
        (skill_root / "SKILL.md").write_text(
            "---\n"
            "name: augur-core\n"
            "description: Core Augur workflows\n"
            "---\n"
            "# Augur Core\n",
            encoding="utf-8",
        )
        (skill_root / "commands" / "triage-backlog.md").write_text(
            "---\n"
            "id: triage-backlog\n"
            "description: Prioritize backlog items\n"
            "skill: advisor\n"
            "---\n"
            "Triage the backlog.\n",
            encoding="utf-8",
        )

        project_codex = tmp_path / ".codex" / "prompts"
        global_codex = tmp_path / "home" / ".codex" / "prompts"
        project_codex.mkdir(parents=True)
        global_codex.mkdir(parents=True)
        fake_adapter = SimpleNamespace(adapter_name="codex")

        with patch("sync_agents.skill_sync.PROJECT_ROOT", tmp_path), \
             patch("sync_agents.skill_sync.get_codex_prompt_dir", side_effect=lambda scope: project_codex if scope == "project" else global_codex):
            written = _sync_prompt_stubs([fake_adapter])

        assert written == 0
        assert not (project_codex / "triage-backlog.md").exists()
        assert not (global_codex / "triage-backlog.md").exists()

    def test_codex_prompt_sync_skips_cleanup_when_disabled(self, tmp_path):
        from sync_agents.skill_sync import _sync_prompt_stubs

        project_codex = tmp_path / ".codex" / "prompts"
        global_codex = tmp_path / "home" / ".codex" / "prompts"
        project_codex.mkdir(parents=True)
        global_codex.mkdir(parents=True)
        (project_codex / "triage-backlog.md").write_text("managed prompt\n", encoding="utf-8")
        (project_codex / "notes.md").write_text("user prompt\n", encoding="utf-8")
        (project_codex / ".augur-generated-prompts.json").write_text(
            json.dumps({"files": ["triage-backlog.md"]}),
            encoding="utf-8",
        )

        with patch("sync_agents.skill_sync.get_codex_prompt_dir", side_effect=lambda scope: project_codex if scope == "project" else global_codex):
            written = _sync_prompt_stubs([SimpleNamespace(adapter_name="cursor")], cleanup_disabled=False)

        assert written == 0
        assert (project_codex / "triage-backlog.md").exists()
        assert (project_codex / "notes.md").exists()
        assert (project_codex / ".augur-generated-prompts.json").exists()

    def test_codex_native_skills_export_to_global_skills_dir(self, tmp_path):
        from sync_agents.skill_sync import _sync_skill_stubs

        visible_root = tmp_path / "project-brain" / "capabilities" / "skills" / "commands"
        visible_root.mkdir(parents=True)
        (visible_root / "SKILL.md").write_text(
            "---\n"
            "name: commands\n"
            "description: Show all available slash commands\n"
            "x-augur-visibility: core\n"
            "---\n"
            "# /commands\n\n"
            "Display command help.\n",
            encoding="utf-8",
        )
        (visible_root / "references").mkdir()
        (visible_root / "references" / "example.md").write_text("example\n", encoding="utf-8")

        hidden_root = tmp_path / "project-brain" / "capabilities" / "skills" / "nightly"
        hidden_root.mkdir(parents=True)
        (hidden_root / "SKILL.md").write_text(
            "---\n"
            "name: nightly\n"
            "description: Internal nightly maintenance\n"
            "x-augur-visibility: hidden\n"
            "---\n"
            "# Nightly\n",
            encoding="utf-8",
        )

        visible_unflagged_root = tmp_path / "project-brain" / "capabilities" / "skills" / "search"
        visible_unflagged_root.mkdir(parents=True)
        (visible_unflagged_root / "SKILL.md").write_text(
            "---\n"
            "name: search\n"
            "description: Search across knowledge sources\n"
            "x-augur-visibility: core\n"
            "---\n"
            "# Search\n",
            encoding="utf-8",
        )

        project_prompts = tmp_path / ".codex" / "prompts"
        global_prompts = tmp_path / "home" / ".codex" / "prompts"
        project_prompts.mkdir(parents=True)
        global_prompts.mkdir(parents=True)
        project_native = tmp_path / ".codex" / "skills"
        global_native = tmp_path / "home" / ".agents" / "skills" / "augur"
        project_native.mkdir(parents=True)
        global_native.mkdir(parents=True)
        managed_project_skill = project_native / "commands"
        managed_project_skill.mkdir(parents=True)
        (managed_project_skill / "SKILL.md").write_text("managed project\n", encoding="utf-8")
        managed_global_skill = global_native / "commands"
        managed_global_skill.mkdir(parents=True)
        (managed_global_skill / "SKILL.md").write_text("managed global\n", encoding="utf-8")
        (project_native / ".augur-managed.json").write_text(
            json.dumps({"skills": ["commands"]}),
            encoding="utf-8",
        )
        (global_native / ".augur-managed.json").write_text(
            json.dumps({"skills": ["commands"]}),
            encoding="utf-8",
        )
        personal_skill = global_native / "ui-ux-pro-max"
        personal_skill.mkdir(parents=True)
        (personal_skill / "SKILL.md").write_text(
            "---\nname: ui-ux-pro-max\ndescription: Personal skill\n---\n",
            encoding="utf-8",
        )
        fake_adapter = SimpleNamespace(adapter_name="codex")

        with patch("sync_agents.skill_sync.PROJECT_ROOT", tmp_path), \
             patch("sync_agents.skill_sync._resolve_client_skill_dirs", return_value=[]), \
             patch("sync_agents.skill_sync._load_skill_scopes", return_value={"codex": "project"}), \
             patch("sync_agents.skill_sync.get_codex_native_skills_dir", side_effect=[project_native, global_native]), \
             patch("sync_agents.skill_sync.get_codex_prompt_dir", side_effect=[project_prompts, global_prompts]):
            written = _sync_skill_stubs([fake_adapter])

        assert written == 0
        assert not managed_project_skill.exists()
        assert not managed_global_skill.exists()
        assert (personal_skill / "SKILL.md").exists()

    def test_disabled_codex_cleans_managed_outputs_without_touching_user_files(self, tmp_path):
        from sync_agents.skill_sync import _sync_skill_stubs

        skill_root = tmp_path / "project-brain" / "capabilities" / "skills" / "commands"
        skill_root.mkdir(parents=True)
        (skill_root / "SKILL.md").write_text(
            "---\n"
            "name: commands\n"
            "description: Show all available slash commands\n"
            "---\n"
            "# /commands\n",
            encoding="utf-8",
        )

        project_prompts = tmp_path / ".codex" / "prompts"
        global_prompts = tmp_path / "home" / ".codex" / "prompts"
        project_prompts.mkdir(parents=True)
        global_prompts.mkdir(parents=True)
        (project_prompts / "commands.md").write_text("managed prompt\n", encoding="utf-8")
        (project_prompts / "notes.md").write_text("user prompt\n", encoding="utf-8")
        (project_prompts / ".augur-generated-prompts.json").write_text(
            json.dumps({"files": ["commands.md"]}),
            encoding="utf-8",
        )

        native_dir = tmp_path / ".agents" / "skills" / "augur"
        global_native = tmp_path / "home" / ".agents" / "skills" / "augur"
        global_native.mkdir(parents=True)
        managed_native = native_dir / "commands"
        managed_native.mkdir(parents=True)
        (managed_native / "SKILL.md").write_text("managed native\n", encoding="utf-8")
        (native_dir / "ui-ux-pro-max").mkdir(parents=True)
        (native_dir / "ui-ux-pro-max" / "SKILL.md").write_text("user native\n", encoding="utf-8")
        (native_dir / ".augur-managed.json").write_text(
            json.dumps({"skills": ["commands"]}),
            encoding="utf-8",
        )

        with patch("sync_agents.skill_sync.PROJECT_ROOT", tmp_path), \
             patch("sync_agents.skill_sync._resolve_client_skill_dirs", return_value=[]), \
             patch("sync_agents.skill_sync._load_skill_scopes", return_value={"codex": "project"}), \
             patch("sync_agents.skill_sync.get_codex_prompt_dir", side_effect=[project_prompts, global_prompts]), \
             patch("sync_agents.skill_sync.get_codex_native_skills_dir", side_effect=[native_dir, native_dir, global_native]):
            written = _sync_skill_stubs([SimpleNamespace(adapter_name="cursor")])

        assert written == 0
        assert not (project_prompts / "commands.md").exists()
        assert (project_prompts / "notes.md").exists()
        assert not (project_prompts / ".augur-generated-prompts.json").exists()
        assert not managed_native.exists()
        assert (native_dir / "ui-ux-pro-max" / "SKILL.md").exists()
        assert not (native_dir / ".augur-managed.json").exists()

    def test_codex_global_native_scope_replaces_stale_global_exports(self, tmp_path):
        from sync_agents.skill_sync import _sync_skill_stubs

        skill_root = tmp_path / "project-brain" / "capabilities" / "skills" / "search"
        skill_root.mkdir(parents=True)
        (skill_root / "SKILL.md").write_text(
            "---\n"
            "name: search\n"
            "description: Search across knowledge sources\n"
            "---\n"
            "# Search\n",
            encoding="utf-8",
        )

        project_prompts = tmp_path / ".codex" / "prompts"
        global_prompts = tmp_path / "home" / ".codex" / "prompts"
        project_prompts.mkdir(parents=True)
        global_prompts.mkdir(parents=True)

        project_native = tmp_path / ".codex" / "skills"
        global_native = tmp_path / "home" / ".agents" / "skills" / "augur"
        project_native.mkdir(parents=True)
        global_native.mkdir(parents=True)

        managed_global_native = global_native / "search"
        managed_global_native.mkdir(parents=True)
        (managed_global_native / "SKILL.md").write_text("managed native\n", encoding="utf-8")
        (global_native / "personal-skill").mkdir(parents=True)
        (global_native / "personal-skill" / "SKILL.md").write_text(
            "user native\n",
            encoding="utf-8",
        )
        (global_native / ".augur-managed.json").write_text(
            json.dumps({"skills": ["search"]}),
            encoding="utf-8",
        )

        fake_adapter = SimpleNamespace(adapter_name="codex")

        with patch("sync_agents.skill_sync.PROJECT_ROOT", tmp_path), \
             patch("sync_agents.skill_sync._resolve_client_skill_dirs", return_value=[]), \
             patch("sync_agents.skill_sync.get_codex_prompt_dir", side_effect=[project_prompts, global_prompts]), \
             patch("sync_agents.skill_sync.get_codex_native_skills_dir", side_effect=[project_native, global_native]), \
             patch("sync_agents.skill_sync._load_skill_scopes", return_value={"codex": "project"}):
            written = _sync_skill_stubs([fake_adapter])

        assert written == 0
        assert not (project_native / "search" / "SKILL.md").exists()
        assert not (global_native / "search" / "SKILL.md").exists()
        assert (global_native / "personal-skill" / "SKILL.md").exists()
        assert not (global_native / ".augur-managed.json").exists()

    def test_codex_native_cleanup_ignores_invalid_manifest_entries(self, tmp_path):
        from sync_agents.skill_sync import _sync_skill_stubs

        skill_root = tmp_path / "project-brain" / "capabilities" / "skills" / "search"
        skill_root.mkdir(parents=True)
        (skill_root / "SKILL.md").write_text(
            "---\n"
            "name: search\n"
            "description: Search across knowledge sources\n"
            "---\n"
            "# Search\n",
            encoding="utf-8",
        )

        project_prompts = tmp_path / ".codex" / "prompts"
        project_prompts.mkdir(parents=True)
        project_native = tmp_path / ".codex" / "skills"
        project_native.mkdir(parents=True)
        global_prompts = tmp_path / "home" / ".codex" / "prompts"
        global_prompts.mkdir(parents=True)
        global_native = tmp_path / "home" / ".agents" / "skills" / "augur"
        global_native.mkdir(parents=True)

        managed_global_native = global_native / "search"
        managed_global_native.mkdir(parents=True)
        (managed_global_native / "SKILL.md").write_text("managed native\n", encoding="utf-8")
        user_global_native = global_native / "personal-skill"
        user_global_native.mkdir(parents=True)
        (user_global_native / "SKILL.md").write_text("user native\n", encoding="utf-8")
        outside_file = tmp_path / "home" / ".agents" / "outside.txt"
        outside_file.write_text("keep me\n", encoding="utf-8")
        (global_native / ".augur-managed.json").write_text(
            json.dumps({"skills": ["", ".", "search", "../../outside.txt"]}),
            encoding="utf-8",
        )

        fake_adapter = SimpleNamespace(adapter_name="cursor")

        with patch("sync_agents.skill_sync.PROJECT_ROOT", tmp_path), \
             patch("sync_agents.skill_sync._resolve_client_skill_dirs", return_value=[]), \
             patch("sync_agents.skill_sync._load_skill_scopes", return_value={}), \
             patch("sync_agents.skill_sync.get_codex_prompt_dir", side_effect=[project_prompts, global_prompts]), \
             patch("sync_agents.skill_sync.get_codex_native_skills_dir", side_effect=[project_native, global_native]):
            written = _sync_skill_stubs([fake_adapter])

        assert written == 0
        assert global_native.exists()
        assert not managed_global_native.exists()
        assert (user_global_native / "SKILL.md").exists()
        assert outside_file.exists()

    def test_skill_stub_sync_rewrites_managed_client_skill_exports_from_canonical_sources(
        self, tmp_path, monkeypatch
    ):
        from sync_agents.skill_sync import _sync_skill_stubs

        _patch_capability_exports(
            monkeypatch,
            "skill",
            {"knowledge": ("claude",)},
        )

        skill_root = tmp_path / "project-brain" / "capabilities" / "skills" / "knowledge"
        skill_root.mkdir(parents=True)
        (skill_root / "SKILL.md").write_text(
            "---\n"
            "name: knowledge\n"
            "description: Knowledge search\n"
            "---\n"
            "# Knowledge\n",
            encoding="utf-8",
        )

        claude_dir = tmp_path / ".claude" / "skills"
        managed_dir = claude_dir / "knowledge"
        managed_dir.mkdir(parents=True)
        (managed_dir / "SKILL.md").write_text("generated\n", encoding="utf-8")
        (claude_dir / ".augur-generated-prompts.json").write_text(
            json.dumps({"files": ["knowledge/SKILL.md"]}),
            encoding="utf-8",
        )
        project_codex_prompts = tmp_path / ".codex" / "prompts"
        global_codex_prompts = tmp_path / "home" / ".codex" / "prompts"
        project_codex_native = tmp_path / ".codex" / "skills"
        global_codex_native = tmp_path / "home" / ".agents" / "skills" / "augur"

        with patch("sync_agents.skill_sync.PROJECT_ROOT", tmp_path), \
             patch("sync_agents.skill_sync._resolve_client_skill_dirs", return_value=[("claude-local", claude_dir, True)]), \
             patch("sync_agents.skill_sync._load_skill_scopes", return_value={"claude-code": "project"}), \
             patch("sync_agents.skill_sync.get_codex_prompt_dir", side_effect=[project_codex_prompts, global_codex_prompts]), \
             patch("sync_agents.skill_sync.get_codex_native_skills_dir", side_effect=[project_codex_native, global_codex_native]):
            written = _sync_skill_stubs([SimpleNamespace(adapter_name="claude-code")])

        assert written == 1
        assert managed_dir.exists()
        assert (managed_dir / "SKILL.md").read_text(encoding="utf-8").startswith("---\nname: knowledge\n")

    def test_skill_stub_sync_preserves_user_skill_dirs_while_cleaning_managed_exports(self, tmp_path):
        from sync_agents.skill_sync import _sync_skill_stubs

        claude_dir = tmp_path / ".claude" / "skills"
        managed_dir = claude_dir / "knowledge"
        managed_dir.mkdir(parents=True)
        (managed_dir / "SKILL.md").write_text("generated\n", encoding="utf-8")
        user_dir = claude_dir / "personal-skill"
        user_dir.mkdir(parents=True)
        (user_dir / "SKILL.md").write_text("user\n", encoding="utf-8")
        (claude_dir / ".augur-generated-prompts.json").write_text(
            json.dumps({"files": ["knowledge/SKILL.md"]}),
            encoding="utf-8",
        )
        project_codex_prompts = tmp_path / ".codex" / "prompts"
        global_codex_prompts = tmp_path / "home" / ".codex" / "prompts"
        project_codex_native = tmp_path / ".codex" / "skills"
        global_codex_native = tmp_path / "home" / ".agents" / "skills" / "augur"

        with patch("sync_agents.skill_sync.PROJECT_ROOT", tmp_path), \
             patch("sync_agents.skill_sync._resolve_client_skill_dirs", return_value=[("claude-local", claude_dir, True)]), \
             patch("sync_agents.skill_sync._load_skill_scopes", return_value={"claude-code": "project"}), \
             patch("sync_agents.skill_sync.get_codex_prompt_dir", side_effect=[project_codex_prompts, global_codex_prompts]), \
             patch("sync_agents.skill_sync.get_codex_native_skills_dir", side_effect=[project_codex_native, global_codex_native]):
            written = _sync_skill_stubs([SimpleNamespace(adapter_name="claude-code")])

        assert written == 0
        assert not managed_dir.exists()
        assert (user_dir / "SKILL.md").exists()

    def test_skill_stub_sync_cleans_managed_exports_across_multiple_clients_without_rewriting_them(self, tmp_path):
        from sync_agents.skill_sync import _sync_skill_stubs

        claude_dir = tmp_path / ".claude" / "skills"
        claude_managed = claude_dir / "knowledge"
        claude_managed.mkdir(parents=True)
        (claude_managed / "SKILL.md").write_text("generated claude\n", encoding="utf-8")
        claude_user = claude_dir / "personal-skill"
        claude_user.mkdir(parents=True)
        (claude_user / "SKILL.md").write_text("user claude\n", encoding="utf-8")
        (claude_dir / ".augur-generated-prompts.json").write_text(
            json.dumps({"files": ["knowledge/SKILL.md"]}),
            encoding="utf-8",
        )

        gemini_dir = tmp_path / ".antigravity" / "plugins"
        gemini_managed = gemini_dir / "troubleshooting"
        gemini_managed.mkdir(parents=True)
        (gemini_managed / "SKILL.md").write_text("generated gemini\n", encoding="utf-8")
        (gemini_dir / ".augur-generated-prompts.json").write_text(
            json.dumps({"files": ["troubleshooting/SKILL.md"]}),
            encoding="utf-8",
        )

        cursor_dir = tmp_path / ".cursor" / "rules"
        cursor_dir.mkdir(parents=True)
        (cursor_dir / "knowledge.md").write_text("generated cursor\n", encoding="utf-8")
        (cursor_dir / ".augur-generated-prompts.json").write_text(
            json.dumps({"files": ["knowledge.md"]}),
            encoding="utf-8",
        )
        (cursor_dir / "notes.md").write_text("user cursor\n", encoding="utf-8")

        project_codex_prompts = tmp_path / ".codex" / "prompts"
        global_codex_prompts = tmp_path / "home" / ".codex" / "prompts"
        project_codex_native = tmp_path / ".codex" / "skills"
        global_codex_native = tmp_path / "home" / ".agents" / "skills" / "augur"

        with patch("sync_agents.skill_sync.PROJECT_ROOT", tmp_path), \
             patch(
                 "sync_agents.skill_sync._resolve_client_skill_dirs",
                 return_value=[
                     ("claude-local", claude_dir, True),
                     ("gemini-local", gemini_dir, True),
                     ("cursor-local", cursor_dir, False),
                 ],
             ), \
             patch("sync_agents.skill_sync._load_skill_scopes", return_value={}), \
             patch("sync_agents.skill_sync.get_codex_prompt_dir", side_effect=[project_codex_prompts, global_codex_prompts]), \
             patch("sync_agents.skill_sync.get_codex_native_skills_dir", side_effect=[project_codex_native, global_codex_native]):
            written = _sync_skill_stubs(
                [
                    SimpleNamespace(adapter_name="claude-code"),
                    SimpleNamespace(adapter_name="gemini"),
                    SimpleNamespace(adapter_name="cursor"),
                ]
            )

        assert written == 0
        assert not claude_managed.exists()
        assert not gemini_managed.exists()
        assert not (cursor_dir / "knowledge.md").exists()
        assert (claude_user / "SKILL.md").exists()
        assert (cursor_dir / "notes.md").exists()

    def test_targeted_skill_sync_skips_cleanup_when_disabled(self, tmp_path):
        from sync_agents.skill_sync import _sync_skill_stubs

        claude_dir = tmp_path / ".claude" / "skills"
        managed_dir = claude_dir / "knowledge"
        managed_dir.mkdir(parents=True)
        (managed_dir / "SKILL.md").write_text("generated\n", encoding="utf-8")
        user_dir = claude_dir / "personal-skill"
        user_dir.mkdir(parents=True)
        (user_dir / "SKILL.md").write_text("user\n", encoding="utf-8")
        (claude_dir / ".augur-generated-prompts.json").write_text(
            json.dumps({"files": ["knowledge/SKILL.md"]}),
            encoding="utf-8",
        )

        project_codex_prompts = tmp_path / ".codex" / "prompts"
        global_codex_prompts = tmp_path / "home" / ".codex" / "prompts"
        project_codex_native = tmp_path / ".codex" / "skills"
        global_codex_native = tmp_path / "home" / ".agents" / "skills" / "augur"
        project_codex_prompts.mkdir(parents=True)
        global_codex_prompts.mkdir(parents=True)
        project_codex_native.mkdir(parents=True)
        global_codex_native.mkdir(parents=True)
        (project_codex_prompts / "triage-backlog.md").write_text("managed prompt\n", encoding="utf-8")
        (project_codex_prompts / ".augur-generated-prompts.json").write_text(
            json.dumps({"files": ["triage-backlog.md"]}),
            encoding="utf-8",
        )
        managed_native = global_codex_native / "commands"
        managed_native.mkdir(parents=True)
        (managed_native / "SKILL.md").write_text("managed native\n", encoding="utf-8")
        (global_codex_native / ".augur-managed.json").write_text(
            json.dumps({"skills": ["commands"]}),
            encoding="utf-8",
        )

        with patch("sync_agents.skill_sync.PROJECT_ROOT", tmp_path), \
             patch("sync_agents.skill_sync._resolve_client_skill_dirs", return_value=[("claude-local", claude_dir, True)]), \
             patch("sync_agents.skill_sync._load_skill_scopes", return_value={"claude-code": "project"}), \
             patch("sync_agents.skill_sync.get_codex_prompt_dir", side_effect=[project_codex_prompts, global_codex_prompts]), \
             patch("sync_agents.skill_sync.get_codex_native_skills_dir", side_effect=[project_codex_native, global_codex_native]):
            written = _sync_skill_stubs([SimpleNamespace(adapter_name="cursor")], cleanup_disabled=False)

        assert written == 0
        assert managed_dir.exists()
        assert (user_dir / "SKILL.md").exists()
        assert (project_codex_prompts / "triage-backlog.md").exists()
        assert (project_codex_prompts / ".augur-generated-prompts.json").exists()
        assert managed_native.exists()
        assert (global_codex_native / ".augur-managed.json").exists()

    def test_cleanup_managed_skill_dir_ignores_path_traversal_manifest_entries(self, tmp_path):
        from sync_agents.skill_sync import _cleanup_managed_skill_dir

        cdir = tmp_path / "workspace" / ".claude" / "skills"
        managed_dir = cdir / "knowledge"
        managed_dir.mkdir(parents=True)
        (managed_dir / "SKILL.md").write_text("generated\n", encoding="utf-8")
        user_dir = cdir / "personal-skill"
        user_dir.mkdir(parents=True)
        (user_dir / "SKILL.md").write_text("user\n", encoding="utf-8")

        outside_file = tmp_path / "workspace" / "outside.txt"
        outside_file.write_text("keep me\n", encoding="utf-8")
        (cdir / ".augur-generated-prompts.json").write_text(
            json.dumps({"files": ["", ".", "knowledge/SKILL.md", "../../outside.txt"]}),
            encoding="utf-8",
        )

        removed = _cleanup_managed_skill_dir(cdir, has_subdirs=True)

        assert removed == 1
        assert not managed_dir.exists()
        assert (user_dir / "SKILL.md").exists()
        assert cdir.exists()
        assert outside_file.exists()

    def test_codex_native_export_replaces_existing_global_symlink(self, tmp_path):
        from sync_agents.skill_sync import _sync_skill_stubs

        skill_root = tmp_path / "project-brain" / "capabilities" / "skills" / "search"
        skill_root.mkdir(parents=True)
        (skill_root / "SKILL.md").write_text(
            "---\n"
            "name: search\n"
            "description: Search across knowledge sources\n"
            "x-augur-visibility: core\n"
            "---\n"
            "# Search\n",
            encoding="utf-8",
        )

        project_prompts = tmp_path / ".codex" / "prompts"
        project_prompts.mkdir(parents=True)
        project_native = tmp_path / ".codex" / "skills"
        project_native.mkdir(parents=True)
        global_prompts = tmp_path / "home" / ".codex" / "prompts"
        global_prompts.mkdir(parents=True)
        global_native = tmp_path / "home" / ".agents" / "skills" / "augur"
        global_native.parent.mkdir(parents=True, exist_ok=True)
        symlink_target = tmp_path / "old-export"
        symlink_target.mkdir()
        global_native.symlink_to(symlink_target, target_is_directory=True)

        fake_adapter = SimpleNamespace(adapter_name="codex")

        with patch("sync_agents.skill_sync.PROJECT_ROOT", tmp_path), \
             patch("sync_agents.skill_sync._resolve_client_skill_dirs", return_value=[]), \
             patch("sync_agents.skill_sync._load_skill_scopes", return_value={"codex": "global"}), \
             patch(
                 "sync_agents.skill_sync.get_codex_native_skills_dir",
                 side_effect=[project_native, global_native],
             ), \
             patch(
                 "sync_agents.skill_sync.get_codex_prompt_dir",
                 side_effect=[project_prompts, global_prompts],
            ):
            _sync_skill_stubs([fake_adapter])

        assert not global_native.exists()
        assert not global_native.is_symlink()
        assert not (project_native / "search" / "SKILL.md").exists()


class TestManifestGeneration:
    def test_generate_ide_manifest_removes_stale_antigravity_manifest_when_unused(self, tmp_path):
        from sync_agents import generators

        antigravity_manifest = tmp_path / ".antigravity" / "ide-manifest.json"
        antigravity_manifest.parent.mkdir(parents=True)
        antigravity_manifest.write_text('{"files":["instructions.md"]}\n', encoding="utf-8")

        generated_file = tmp_path / ".claude" / "commands" / "search.md"
        generated_file.parent.mkdir(parents=True)
        generated_file.write_text("search\n", encoding="utf-8")

        with patch.object(generators, "PROJECT_ROOT", tmp_path), \
             patch.object(generators, "ANTIGRAVITY_IDE_MANIFEST", antigravity_manifest), \
             patch.object(generators, "GENERATED_FILES", [generated_file]):
            generators.generate_ide_manifest()

        assert not antigravity_manifest.exists()

    def test_generate_ide_manifest_writes_antigravity_manifest_only(self, tmp_path):
        from sync_agents import generators

        generated_file = tmp_path / ".antigravity" / "workflows" / "search.md"
        generated_file.parent.mkdir(parents=True)
        generated_file.write_text("search\n", encoding="utf-8")
        manifest_path = tmp_path / ".antigravity" / "ide-manifest.json"

        with patch.object(generators, "PROJECT_ROOT", tmp_path), \
             patch.object(generators, "ANTIGRAVITY_IDE_MANIFEST", manifest_path), \
             patch.object(generators, "GENERATED_FILES", [generated_file]):
            generators.generate_ide_manifest()

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["files"] == ["workflows/search.md"]


class TestSkillStubDrift:
    """ADR-734 C3: detect_skill_stub_drift mirrors the command-stub detector."""

    def test_detect_skill_stub_drift_flags_missing_allowed_skill(self, tmp_path, monkeypatch):
        from sync_agents.skill_sync import detect_skill_stub_drift

        src_skill = tmp_path / "project-brain" / "capabilities" / "skills" / "demo"
        src_skill.mkdir(parents=True)
        (src_skill / "SKILL.md").write_text(
            "---\nname: demo\nx-augur-type: domain\ndescription: demo skill\n---\n"
            "# Demo skill body\n",
            encoding="utf-8",
        )

        monkeypatch.setattr(
            "src.lib.capabilities.export_filter._resolved_records_by_id",
            lambda: {
                "skill:demo": SimpleNamespace(
                    id="skill:demo",
                    type="skill",
                    classification_status="approved",
                    export_to=("claude",),
                    current_exposure=(),
                )
            },
        )

        with patch("sync_agents.skill_sync.PROJECT_ROOT", tmp_path):
            drift = detect_skill_stub_drift([SimpleNamespace(adapter_name="claude_code")])
        assert any("demo" in entry and "missing" in entry for entry in drift)

    def test_detect_skill_stub_drift_silent_when_skill_is_synced(self, tmp_path, monkeypatch):
        from sync_agents.skill_sync import detect_skill_stub_drift

        src_skill = tmp_path / "project-brain" / "capabilities" / "skills" / "demo"
        src_skill.mkdir(parents=True)
        (src_skill / "SKILL.md").write_text(
            "---\nname: demo\n---\n# Demo body\n", encoding="utf-8"
        )
        client_skill = tmp_path / ".claude" / "skills" / "demo"
        client_skill.mkdir(parents=True)
        (client_skill / "SKILL.md").write_text("synced", encoding="utf-8")
        (tmp_path / ".claude" / "skills" / ".augur-generated-prompts.json").write_text(
            json.dumps({"files": ["demo/SKILL.md"]}),
            encoding="utf-8",
        )

        monkeypatch.setattr(
            "src.lib.capabilities.export_filter._resolved_records_by_id",
            lambda: {
                "skill:demo": SimpleNamespace(
                    id="skill:demo",
                    type="skill",
                    classification_status="approved",
                    export_to=("claude",),
                    current_exposure=("claude",),
                )
            },
        )

        with patch("sync_agents.skill_sync.PROJECT_ROOT", tmp_path):
            drift = detect_skill_stub_drift([SimpleNamespace(adapter_name="claude_code")])
        assert drift == []
