"""Tests for auto-adaptive-hub-coverage."""
from __future__ import annotations

import importlib.util
from pathlib import Path

from src.lib.ops_protocol import FixResult, OpsContext, ScanResult


_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "adaptive_hub_coverage_ops.py"
_SPEC = importlib.util.spec_from_file_location("adaptive_hub_coverage_under_test", _MODULE_PATH)
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_scan_detects_adaptive_hub_stale_refs(tmp_path: Path) -> None:
    _write(
        tmp_path / "project-brain" / "capabilities" / "skills" / "auto-analytics" / "SKILL.md",
        "---\nname: auto-analytics\nx-augur-hub: adaptive\n---\n"
        "skills/ai/augur/data/agent-workflows/test-nightly.md\n",
    )

    result = mod.scan(OpsContext(project_root=tmp_path))
    assert isinstance(result, ScanResult)
    assert len(result.issues) == 1
    assert result.issues[0]["path"] == "project-brain/capabilities/skills/auto-analytics/SKILL.md"


def test_fix_rewrites_adaptive_hub_refs(tmp_path: Path) -> None:
    target = tmp_path / "project-brain" / "capabilities" / "skills" / "nightly" / "SKILL.md"
    _write(
        target,
        "---\nname: nightly\nx-augur-hub: adaptive\n---\n"
        "skills/ai/augur/data/agent-workflows/test-nightly.md\n",
    )

    scan = mod.scan(OpsContext(project_root=tmp_path))
    fixed = mod.fix(OpsContext(project_root=tmp_path), scan.issues)

    assert isinstance(fixed, FixResult)
    assert fixed.success is True
    updated = target.read_text(encoding="utf-8")
    assert "project-brain/capabilities/skills/validator/commands/test-nightly.md" in updated


def test_scan_ignores_non_adaptive_hub_files(tmp_path: Path) -> None:
    _write(
        tmp_path / "project-brain" / "capabilities" / "skills" / "save" / "SKILL.md",
        "---\nname: save\nx-augur-hub: command\n---\n"
        "skills/ai/scripts/ops/analytics.py\n",
    )
    _write(tmp_path / "project-brain" / "capabilities" / "skills" / "ai" / "scripts" / "ops" / "analytics.py", "# live\n")

    result = mod.scan(OpsContext(project_root=tmp_path))
    assert result.issues == []
