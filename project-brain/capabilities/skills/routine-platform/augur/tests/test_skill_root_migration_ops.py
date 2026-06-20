"""Tests for auto-skill-root-migration scan/fix protocol."""
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import yaml

from src.lib.ops_protocol import OpsContext, ScanResult

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "skill_root_migration_ops.py"
_SPEC = importlib.util.spec_from_file_location("skill_root_migration_under_test", _MODULE_PATH)
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


def _ctx(tmp_path: Path, **kw) -> OpsContext:
    return OpsContext(project_root=tmp_path, **kw)


def _completed(returncode: int, stdout: str, stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["python", "scripts/check_skill_root_migration.py", "--final-contract"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def _write_guard(project_root: Path) -> None:
    script = project_root / "scripts" / "check_skill_root_migration.py"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("#!/usr/bin/env python3\n", encoding="utf-8")


def test_module_name() -> None:
    assert mod.name == "auto-skill-root-migration"


def test_loop_repo_registers_skill_root_migration_command() -> None:
    skill_md = Path(__file__).resolve().parents[2] / "SKILL.md"
    content = skill_md.read_text(encoding="utf-8")
    frontmatter = yaml.safe_load(content.split("---", 2)[1])

    commands = frontmatter["x-augur-commands"]
    command = next(cmd for cmd in commands if cmd.get("id") == "auto-skill-root-migration")

    assert command["callable"] == "scripts/skill_root_migration_ops.py"
    assert command["protocol"] == "scan-fix"
    assert command["loop"]["name"] == "hardening"
    assert command["loop"]["tier"] == 1


def test_scan_reports_clean_when_guard_passes(tmp_path: Path, monkeypatch) -> None:
    _write_guard(tmp_path)
    monkeypatch.setattr(
        mod,
        "_run_guard",
        lambda project_root: _completed(0, "skill root migration contract passed\n"),
    )

    result = mod.scan(_ctx(tmp_path))

    assert isinstance(result, ScanResult)
    assert result.issues == []
    assert result.health == "verified"
    assert result.severity == "info"
    assert "passed" in result.summary


def test_scan_reports_guard_violations_when_guard_fails(tmp_path: Path, monkeypatch) -> None:
    _write_guard(tmp_path)
    monkeypatch.setattr(
        mod,
        "_run_guard",
        lambda project_root: _completed(
            1,
            "skill root migration contract failed:\n"
            "  - src/lib/example.py:71: forbidden root-skill repo-root attribute\n"
            "  - project-brain/capabilities/skills/ai/scripts/sync_agents/constants.py:33: forbidden root-skill repo-root variable\n",
        ),
    )

    result = mod.scan(_ctx(tmp_path))

    assert result.health == "degraded"
    assert result.severity == "error"
    assert len(result.issues) == 2
    assert result.issues[0]["category"] == "skill-root-migration"
    assert result.issues[0]["file"] == "src/lib/example.py"
    assert result.issues[0]["line"] == 71
    assert "repo-root attribute" in result.issues[0]["detail"]
    assert result.issues[1]["file"] == "project-brain/capabilities/skills/ai/scripts/sync_agents/constants.py"


def test_scan_reports_missing_guard_script(tmp_path: Path) -> None:
    result = mod.scan(_ctx(tmp_path))

    assert result.health == "broken"
    assert result.severity == "error"
    assert result.issues[0]["category"] == "skill-root-migration"
    assert "missing migration guard" in result.issues[0]["detail"]
