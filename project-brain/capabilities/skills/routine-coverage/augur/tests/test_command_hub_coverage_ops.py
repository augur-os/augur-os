"""Tests for auto-command-hub-coverage."""
from __future__ import annotations

import importlib.util
from pathlib import Path

from src.lib.ops_protocol import FixResult, OpsContext, ScanResult


_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "command_hub_coverage_ops.py"
_SPEC = importlib.util.spec_from_file_location("command_hub_coverage_under_test", _MODULE_PATH)
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_scan_detects_command_hub_legacy_refs(tmp_path: Path) -> None:
    _write(
        tmp_path / "project-brain" / "capabilities" / "skills" / "ops-kill" / "SKILL.md",
        "---\nname: ops-kill\nx-augur-hub: command\n---\n"
        "python3 plugins/admin/skills/process-tools/scripts/cleanup_processes.py\n",
    )
    _write(
        tmp_path / "project-brain" / "capabilities" / "skills" / "process-tools" / "scripts" / "cleanup_processes.py",
        "# live\n",
    )

    result = mod.scan(OpsContext(project_root=tmp_path))
    assert isinstance(result, ScanResult)
    assert len(result.issues) == 1
    assert result.issues[0]["path"] == "project-brain/capabilities/skills/ops-kill/SKILL.md"


def test_fix_rewrites_command_hub_refs(tmp_path: Path) -> None:
    _write(
        tmp_path / "project-brain" / "capabilities" / "skills" / "ops-audit" / "SKILL.md",
        "---\nname: ops-audit\nx-augur-hub: command\n---\n",
    )
    target = tmp_path / "project-brain" / "capabilities" / "skills" / "ops-audit" / "references" / "workflow.md"
    _write(
        target,
        "Read and follow `plugins/orchestration/skills/orch-audit/commands/runbook.md`\n",
    )
    _write(
        tmp_path / "project-brain" / "capabilities" / "skills" / "orch-audit" / "commands" / "runbook.md",
        "# live\n",
    )

    scan = mod.scan(OpsContext(project_root=tmp_path))
    fixed = mod.fix(OpsContext(project_root=tmp_path, difficulty=1), scan.issues)

    assert isinstance(fixed, FixResult)
    assert fixed.success is True
    updated = target.read_text(encoding="utf-8")
    assert "project-brain/capabilities/skills/orch-audit/commands/runbook.md" in updated
    assert "plugins/orchestration/skills/orch-audit/commands/runbook.md" not in updated


def test_scan_ignores_non_command_hub_files(tmp_path: Path) -> None:
    _write(
        tmp_path / "project-brain" / "capabilities" / "skills" / "frontend" / "SKILL.md",
        "---\nname: frontend\nx-augur-hub: studio\n---\n"
        "python3 plugins/admin/skills/process-tools/scripts/cleanup_processes.py\n",
    )
    _write(
        tmp_path / "project-brain" / "capabilities" / "skills" / "process-tools" / "scripts" / "cleanup_processes.py",
        "# live\n",
    )

    result = mod.scan(OpsContext(project_root=tmp_path))
    assert result.issues == []
