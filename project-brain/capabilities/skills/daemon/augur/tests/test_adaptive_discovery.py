"""Tests for auto-command discovery (ADR-200).

Verifies that discover_auto_commands() reads canonical SKILL.md metadata:
- x-augur-commands entries with protocol: scan-fix
- x-augur-loop fallback for standalone loop skills
- grouping by loop name
"""
from __future__ import annotations

import sys
from pathlib import Path

from src.plugins.skill_discovery import invalidate_discovery_cache

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import pytest
import yaml

from skills.daemon.scripts.adaptive.discovery import (
    default_scheduler_for_trigger,
    discover_auto_commands,
    group_by_loop,
    load_ops_module,
    resolve_scheduler,
)


def _create_ops_module(path: Path, name: str = "auto-test") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'''"""Auto-command: {name}."""
from dataclasses import dataclass, field

name = "{name}"

@dataclass
class ScanResult:
    issues: list = field(default_factory=list)
    summary: str = ""
    severity: str = "info"

@dataclass
class FixResult:
    success: bool = True
    actions: list = field(default_factory=list)
    changes: list = field(default_factory=list)
    summary: str = ""

def scan(ctx):
    return ScanResult(issues=[], summary="clean")

def fix(ctx, issues):
    return FixResult(success=True, summary="fixed")
''',
        encoding="utf-8",
    )
    return path


def _write_skill(
    root: Path,
    skill: str,
    *,
    commands: list[dict] | None = None,
    loop: dict | None = None,
) -> Path:
    skill_dir = root / "project-brain" / "capabilities" / "skills" / skill
    skill_dir.mkdir(parents=True, exist_ok=True)

    metadata: dict[str, object] = {
        "name": skill,
        "description": f"{skill} skill",
        "x-augur-hub": "command",
    }
    if commands is not None:
        metadata["x-augur-commands"] = commands
    if loop is not None:
        metadata["x-augur-loop"] = loop

    frontmatter = yaml.safe_dump(
        metadata,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
    )
    (skill_dir / "SKILL.md").write_text(f"---\n{frontmatter}---\n# {skill}\n", encoding="utf-8")
    return skill_dir


@pytest.fixture(autouse=True)
def _isolated_skill_discovery(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.chdir(tmp_path)
    invalidate_discovery_cache()
    yield
    invalidate_discovery_cache()


class TestLoadOpsModule:
    def test_load_valid_module(self, tmp_path):
        mod_path = tmp_path / "test_mod.py"
        _create_ops_module(mod_path, "auto-valid")
        module = load_ops_module(mod_path)
        assert callable(module.scan)
        assert callable(module.fix)
        assert module.name == "auto-valid"

    def test_load_missing_module_raises(self, tmp_path):
        with pytest.raises(ImportError, match="not found"):
            load_ops_module(tmp_path / "nonexistent.py")

    def test_load_module_supports_sibling_bootstrap_paths_import(self, tmp_path):
        scripts_dir = tmp_path / "project-brain" / "capabilities" / "skills" / "demo" / "scripts"
        scripts_dir.mkdir(parents=True)
        (scripts_dir / "bootstrap_paths.py").write_text(
            'BOOTSTRAP_MARKER = "local-bootstrap"\n',
            encoding="utf-8",
        )
        mod_path = scripts_dir / "ops.py"
        mod_path.write_text(
            'from bootstrap_paths import BOOTSTRAP_MARKER\n'
            'name = "auto-bootstrap-demo"\n'
            "def scan(ctx):\n"
            "    return BOOTSTRAP_MARKER\n"
            "def fix(ctx, issues):\n"
            "    return None\n",
            encoding="utf-8",
        )

        module = load_ops_module(mod_path)

        assert module.scan(None) == "local-bootstrap"

    def test_load_real_self_heal_module_prefers_package_over_ops_name_collision(self):
        module_path = Path(__file__).resolve().parents[2] / "scripts" / "ops" / "self_heal.py"

        for name in ("ai_self_healer", "ops_cmd_self_heal"):
            sys.modules.pop(name, None)

        module = load_ops_module(
            module_path,
            project_root=Path(__file__).resolve().parents[4],
        )

        assert module.healer is not None


class TestDiscoverAutoCommands:
    def test_discovers_scan_fix_commands_from_x_augur_commands(self, tmp_path):
        skill_dir = _write_skill(
            tmp_path,
            "daemon",
            commands=[
                {
                    "id": "auto-lint",
                    "protocol": "scan-fix",
                    "callable": "scripts/ops/lint.py",
                    "loop": {"name": "code-quality", "tier": 1, "trigger": "nightly"},
                }
            ],
        )
        _create_ops_module(skill_dir / "scripts" / "ops" / "lint.py", "auto-lint")

        registry = discover_auto_commands(tmp_path)
        assert "auto-lint" in registry
        entry = registry["auto-lint"]
        assert entry.loop_name == "code-quality"
        assert entry.tier == 1
        assert entry.trigger == "nightly"
        assert entry.scheduler == "codex"

    def test_discovers_module_capabilities(self, tmp_path):
        skill_dir = _write_skill(
            tmp_path,
            "daemon",
            commands=[
                {
                    "id": "auto-lint",
                    "protocol": "scan-fix",
                    "callable": "scripts/ops/lint.py",
                    "loop": {"name": "code-quality", "tier": 1, "trigger": "nightly"},
                }
            ],
        )
        module_path = skill_dir / "scripts" / "ops" / "lint.py"
        module_path.parent.mkdir(parents=True, exist_ok=True)
        module_path.write_text(
            "from src.lib.ops_protocol import declare_ops_capabilities\n"
            'name = "auto-lint"\n'
            'OPS_CAPABILITIES = declare_ops_capabilities(platforms=("cross_platform",), windows_fix_mode="report_only")\n'
            "def scan(ctx):\n"
            '    return type("R", (), {"issues": [], "summary": "clean", "severity": "info", "health": "verified"})()\n'
            "def fix(ctx, issues):\n"
            '    return type("F", (), {"success": True, "actions": [], "changes": [], "summary": "fixed"})()\n',
            encoding="utf-8",
        )

        entry = discover_auto_commands(tmp_path)["auto-lint"]
        assert entry.capabilities.windows_fix_mode == "report_only"

    def test_skips_module_with_invalid_capabilities(self, tmp_path):
        skill_dir = _write_skill(
            tmp_path,
            "daemon",
            commands=[
                {
                    "id": "auto-invalid",
                    "protocol": "scan-fix",
                    "callable": "scripts/ops/invalid.py",
                    "loop": {"name": "code-quality", "tier": 1, "trigger": "nightly"},
                }
            ],
        )
        module_path = skill_dir / "scripts" / "ops" / "invalid.py"
        module_path.parent.mkdir(parents=True, exist_ok=True)
        module_path.write_text(
            'name = "auto-invalid"\n'
            'OPS_CAPABILITIES = {"platforms": ("cross_platform",)}\n'
            "def scan(ctx):\n"
            '    return type("R", (), {"issues": [], "summary": "clean", "severity": "info", "health": "verified"})()\n'
            "def fix(ctx, issues):\n"
            '    return type("F", (), {"success": True, "actions": [], "changes": [], "summary": "fixed"})()\n',
            encoding="utf-8",
        )

        registry = discover_auto_commands(tmp_path)
        assert "auto-invalid" not in registry

    def test_skips_module_with_invalid_capability_values(self, tmp_path):
        skill_dir = _write_skill(
            tmp_path,
            "daemon",
            commands=[
                {
                    "id": "auto-invalid-values",
                    "protocol": "scan-fix",
                    "callable": "scripts/ops/invalid_values.py",
                    "loop": {"name": "code-quality", "tier": 1, "trigger": "nightly"},
                }
            ],
        )
        module_path = skill_dir / "scripts" / "ops" / "invalid_values.py"
        module_path.parent.mkdir(parents=True, exist_ok=True)
        module_path.write_text(
            "from src.lib.ops_protocol import OpsCapabilities\n"
            'name = "auto-invalid-values"\n'
            'OPS_CAPABILITIES = OpsCapabilities(platforms=("cross_platform",), windows_fix_mode="bogus")\n'
            "def scan(ctx):\n"
            '    return type("R", (), {"issues": [], "summary": "clean", "severity": "info", "health": "verified"})()\n'
            "def fix(ctx, issues):\n"
            '    return type("F", (), {"success": True, "actions": [], "changes": [], "summary": "fixed"})()\n',
            encoding="utf-8",
        )

        registry = discover_auto_commands(tmp_path)
        assert "auto-invalid-values" not in registry

    def test_skips_non_scan_fix_commands(self, tmp_path):
        skill_dir = _write_skill(
            tmp_path,
            "daemon",
            commands=[
                {
                    "id": "ops-daemon",
                    "protocol": "fire",
                    "callable": "scripts/ops/daemon.py",
                }
            ],
        )
        _create_ops_module(skill_dir / "scripts" / "ops" / "daemon.py", "ops-daemon")

        registry = discover_auto_commands(tmp_path)
        assert registry == {}

    def test_uses_x_augur_loop_for_standalone_loop_skill(self, tmp_path):
        skill_dir = _write_skill(
            tmp_path,
            "auto-example",
            loop={"name": "self-heal", "tier": 2, "trigger": "continuous"},
        )
        _create_ops_module(skill_dir / "scripts" / "example.py", "auto-example")

        registry = discover_auto_commands(tmp_path)
        assert "auto-example" in registry
        assert registry["auto-example"].loop_name == "self-heal"
        assert registry["auto-example"].tier == 2
        assert registry["auto-example"].scheduler == "daemon"

    def test_ignores_generated_client_exports_with_missing_callable(self, tmp_path, caplog):
        real_skill = _write_skill(
            tmp_path,
            "real-loop",
            commands=[
                {
                    "id": "auto-real-loop",
                    "protocol": "scan-fix",
                    "callable": "scripts/ops/real.py",
                    "loop": {"name": "testing", "tier": 1, "trigger": "nightly"},
                }
            ],
        )
        _create_ops_module(real_skill / "scripts" / "ops" / "real.py", "auto-real-loop")

        generated_skill = tmp_path / ".gemini" / "skills" / "generated-loop"
        generated_skill.mkdir(parents=True)
        (generated_skill / "SKILL.md").write_text(
            """---
name: generated-loop
x-augur-commands:
  - id: auto-generated-loop
    protocol: scan-fix
    callable: scripts/ops/missing.py
    loop:
      name: testing
      trigger: nightly
---
""",
            encoding="utf-8",
        )

        registry = discover_auto_commands(tmp_path)

        assert sorted(registry) == ["auto-real-loop"]
        assert "auto-generated-loop" not in registry
        assert ".gemini/skills" not in caplog.text

    def test_groups_by_loop(self, tmp_path):
        first = _write_skill(
            tmp_path,
            "auto-a",
            commands=[
                {
                    "id": "auto-a",
                    "protocol": "scan-fix",
                    "callable": "scripts/a.py",
                    "loop": {"name": "hardening", "tier": 2},
                }
            ],
        )
        second = _write_skill(
            tmp_path,
            "auto-b",
            commands=[
                {
                    "id": "auto-b",
                    "protocol": "scan-fix",
                    "callable": "scripts/b.py",
                    "loop": {"name": "hardening", "tier": 1},
                }
            ],
        )
        _create_ops_module(first / "scripts" / "a.py", "auto-a")
        _create_ops_module(second / "scripts" / "b.py", "auto-b")

        grouped = group_by_loop(discover_auto_commands(tmp_path))
        assert [entry.name for entry in grouped["hardening"]] == ["auto-b", "auto-a"]

    def test_discovers_scheduler_ownership(self, tmp_path, monkeypatch):
        skill_dir = _write_skill(
            tmp_path,
            "daemon",
            commands=[
                {
                    "id": "auto-nightly-testing",
                    "protocol": "scan-fix",
                    "callable": "scripts/ops/testing.py",
                    "loop": {
                        "name": "testing",
                        "tier": 1,
                        "trigger": "nightly",
                        "scheduler": "codex",
                    },
                }
            ],
        )
        _create_ops_module(
            skill_dir / "scripts" / "ops" / "testing.py",
            "auto-nightly-testing",
        )

        monkeypatch.setattr(
            "src.plugins.skill_discovery.get_skills_dir",
            lambda: tmp_path / "skills",
        )
        registry = discover_auto_commands(tmp_path)
        assert registry["auto-nightly-testing"].scheduler == "codex"

    def test_normalizes_trigger_and_scheduler_metadata(self, tmp_path):
        skill_dir = _write_skill(
            tmp_path,
            "daemon",
            commands=[
                {
                    "id": "auto-nightly-testing",
                    "protocol": "scan-fix",
                    "callable": "scripts/ops/testing.py",
                    "loop": {
                        "name": "testing",
                        "tier": 1,
                        "trigger": " Nightly ",
                        "scheduler": " Codex ",
                    },
                }
            ],
        )
        _create_ops_module(
            skill_dir / "scripts" / "ops" / "testing.py",
            "auto-nightly-testing",
        )

        entry = discover_auto_commands(tmp_path)["auto-nightly-testing"]

        assert entry.trigger == "nightly"
        assert entry.scheduler == "codex"

    def test_discovers_configured_vault_skill_with_namespace_imports(self, tmp_path):
        vault = tmp_path / "vault"
        (tmp_path / "project.yaml").write_text(
            "name: TestAugur\npaths:\n  vault: " + str(vault) + "\n",
            encoding="utf-8",
        )
        skill_dir = vault / "capabilities" / "skills" / "ingest"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            """---
name: ingest
x-augur-commands:
  - id: auto-wiki-maintenance
    protocol: scan-fix
    callable: scripts/wiki_ops.py
    loop:
      name: knowledge-enrichment
      trigger: nightly
---
# Ingest
""",
            encoding="utf-8",
        )
        helper = skill_dir / "scripts" / "helper.py"
        helper.parent.mkdir(parents=True)
        helper.write_text(
            "from types import SimpleNamespace\n"
            "def clean():\n"
            "    return SimpleNamespace(issues=[], summary='clean', severity='info', health='verified')\n"
            "def fixed():\n"
            "    return SimpleNamespace(success=True, actions=[], changes=[], summary='fixed')\n",
            encoding="utf-8",
        )
        (skill_dir / "scripts" / "wiki_ops.py").write_text(
            "from skills.ingest.scripts.helper import clean, fixed\n"
            "name = 'auto-wiki-maintenance'\n"
            "def scan(ctx):\n"
            "    return clean()\n"
            "def fix(ctx, issues):\n"
            "    return fixed()\n",
            encoding="utf-8",
        )

        registry = discover_auto_commands(tmp_path)

        assert "auto-wiki-maintenance" in registry
        assert registry["auto-wiki-maintenance"].plugin_root == skill_dir


def test_default_scheduler_for_trigger_uses_daemon_only_for_continuous():
    assert default_scheduler_for_trigger("continuous") == "daemon"
    assert default_scheduler_for_trigger(" Continuous ") == "daemon"
    assert default_scheduler_for_trigger("nightly") == "codex"
    assert default_scheduler_for_trigger("post-execution") == "codex"
    assert default_scheduler_for_trigger("weekly") == "codex"


def test_resolve_scheduler_prefers_explicit_scheduler():
    assert resolve_scheduler({"trigger": "nightly", "scheduler": "daemon"}) == "daemon"
    assert resolve_scheduler({"trigger": "continuous", "scheduler": "codex"}) == "codex"
    assert resolve_scheduler({"trigger": "nightly", "scheduler": " Codex "}) == "codex"


def test_resolve_scheduler_uses_fallback_trigger():
    assert resolve_scheduler({}, {"trigger": "nightly"}) == "codex"
    assert resolve_scheduler({"trigger": "continuous"}, {"scheduler": "codex"}) == "codex"


def test_daemon_config_marks_nightly_scheduler_ownership():
    config_path = Path(__file__).resolve().parents[2] / "config.yaml"
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    commands = (payload.get("contributions") or {}).get("commands") or []
    command_by_id = {
        command.get("id"): command
        for command in commands
        if isinstance(command, dict) and command.get("id")
    }

    expected_codex = {
        "auto-page-mounts",
        "auto-security-scan",
        "auto-stale-paths",
        "auto-code-health",
        "auto-skill-md",
        "auto-skill-refs",
        "auto-heal-validate",
        "auto-memory-consolidation",
        "auto-mcp-hygiene",
    }
    expected_daemon = {
        "auto-self-heal",
    }

    for command_id in expected_codex:
        loop_cfg = command_by_id[command_id].get("loop") or {}
        assert loop_cfg.get("scheduler") == "codex"

    for command_id in expected_daemon:
        loop_cfg = command_by_id[command_id].get("loop") or {}
        assert loop_cfg.get("scheduler", "daemon") == "daemon"


def test_daemon_config_marks_self_heal_validate_codex_owned():
    config_path = Path(__file__).resolve().parents[2] / "config.yaml"
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    commands = (payload.get("contributions") or {}).get("commands") or []
    auto_heal_validate = next(
        command
        for command in commands
        if isinstance(command, dict) and command.get("id") == "auto-heal-validate"
    )

    loop_cfg = auto_heal_validate.get("loop") or {}
    assert loop_cfg.get("scheduler") == "codex"
    assert loop_cfg.get("trigger") == "nightly"
