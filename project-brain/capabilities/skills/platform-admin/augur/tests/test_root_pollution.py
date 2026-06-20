"""Tests for repo hygiene scanning and root pollution discovery."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import yaml

from src.lib.ops_protocol import OpsContext

REPO_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
SHARED_VAULT_ROOT = REPO_ROOT / "project-brain"
PLATFORM_ADMIN_ROOT = SHARED_VAULT_ROOT / "capabilities" / "skills" / "platform-admin"
for _path in (REPO_ROOT, SHARED_VAULT_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

SCRIPTS_DIR = PLATFORM_ADMIN_ROOT / "scripts" / "ops"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_root_pollution_importable():
    """Verify that root_pollution can be imported without errors."""
    mod = importlib.import_module("skills.platform-admin.scripts.ops.root_pollution")
    assert mod is not None


def test_root_pollution_scans_safe_junk_and_legacy_plugin_dirs(tmp_path):
    mod = importlib.import_module("skills.platform-admin.scripts.ops.root_pollution")

    (tmp_path / "skills" / "demo").mkdir(parents=True)
    (tmp_path / "plugins" / "orchestration" / "skills" / "executor").mkdir(parents=True)
    (tmp_path / "scripts" / "__pycache__").mkdir(parents=True)
    (tmp_path / "skills" / "demo" / ".DS_Store").write_text("", encoding="utf-8")
    (tmp_path / "scripts" / "__pycache__" / "cache.pyc").write_bytes(b"pyc")
    (tmp_path / "factory").mkdir()
    (tmp_path / "factory" / "requests.ljson").write_text("{}", encoding="utf-8")

    result = mod.scan(OpsContext(project_root=tmp_path, difficulty=1))
    actions = {issue["action"] for issue in result.issues}

    assert "stray-root-dir" in actions
    assert "safe-junk-file" in actions
    assert "safe-junk-dir" in actions
    assert "legacy-plugin-skill-dir" in actions
    assert "legacy-script-candidate" not in actions


def test_legacy_plugin_skill_uses_shared_vault_for_live_skill_match(tmp_path):
    """Legacy plugin duplicate detection should compare against project-brain skills."""
    mod = importlib.import_module("skills.platform-admin.scripts.ops.root_pollution")

    (tmp_path / "project-brain" / "capabilities" / "skills" / "executor").mkdir(parents=True)
    (tmp_path / "plugins" / "orchestration" / "skills" / "executor").mkdir(parents=True)

    issue = mod._scan_legacy_plugin_skill_dirs(tmp_path)[0]

    assert issue["has_live_skill"] is True


def test_root_pollution_marks_safe_junk_as_maintenance(tmp_path):
    mod = importlib.import_module("skills.platform-admin.scripts.ops.root_pollution")

    (tmp_path / "scripts" / "__pycache__").mkdir(parents=True)
    (tmp_path / "scripts" / "__pycache__" / "cache.pyc").write_bytes(b"pyc")
    (tmp_path / "skills" / "demo").mkdir(parents=True)
    (tmp_path / "skills" / "demo" / ".DS_Store").write_text("", encoding="utf-8")

    result = mod.scan(OpsContext(project_root=tmp_path, difficulty=1))
    kinds = {
        issue["action"]: issue.get("kind", "actionable")
        for issue in result.issues
    }

    assert kinds["safe-junk-dir"] == "maintenance"
    assert kinds["safe-junk-file"] == "maintenance"


def test_root_pollution_fix_relocates_safe_items_only(tmp_path):
    mod = importlib.import_module("skills.platform-admin.scripts.ops.root_pollution")

    (tmp_path / "factory").mkdir()
    (tmp_path / "factory" / "requests.ljson").write_text("{}", encoding="utf-8")
    (tmp_path / "skills" / "demo").mkdir(parents=True)
    ds_store = tmp_path / "skills" / "demo" / ".DS_Store"
    ds_store.write_text("", encoding="utf-8")
    legacy = tmp_path / "plugins" / "orchestration" / "skills" / "executor"
    legacy.mkdir(parents=True)

    result = mod.scan(OpsContext(project_root=tmp_path, difficulty=1))
    fixed = mod.fix(OpsContext(project_root=tmp_path, difficulty=1), result.issues)

    assert fixed.success is True
    assert not (tmp_path / "factory").exists()
    assert not ds_store.exists()
    assert legacy.exists()
    assert "manual hygiene candidate(s) need review" in fixed.summary


def test_platform_admin_skill_registers_auto_root_pollution():
    skill_md = PLATFORM_ADMIN_ROOT / "SKILL.md"
    text = skill_md.read_text(encoding="utf-8")
    assert text.startswith("---")
    end = text.index("---", 3)
    frontmatter = yaml.safe_load(text[3:end])
    commands = frontmatter.get("x-augur-commands", [])
    command_ids = {command.get("id") for command in commands if isinstance(command, dict)}
    assert "auto-root-pollution" in command_ids
