"""Tests for auto-brain-hub-coverage."""
from __future__ import annotations

import importlib.util
from pathlib import Path

from src.lib.ops_protocol import FixResult, OpsContext, ScanResult


_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "brain_hub_coverage_ops.py"
_SPEC = importlib.util.spec_from_file_location("brain_hub_coverage_under_test", _MODULE_PATH)
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_scan_detects_brain_hub_legacy_refs(tmp_path: Path) -> None:
    _write(
        tmp_path / "project-brain" / "capabilities" / "skills" / "rag" / "SKILL.md",
        "---\nname: rag\nx-augur-hub: brain\n---\n"
        "skills/ai/augur/agent-rules.md\n",
    )
    _write(tmp_path / "docs" / "agent-topics" / "agent-rules.md", "# live\n")

    result = mod.scan(OpsContext(project_root=tmp_path))
    assert isinstance(result, ScanResult)
    assert len(result.issues) == 1
    assert result.issues[0]["path"] == "project-brain/capabilities/skills/rag/SKILL.md"


def test_fix_rewrites_brain_hub_refs(tmp_path: Path) -> None:
    target = tmp_path / "project-brain" / "capabilities" / "skills" / "dev-learn" / "SKILL.md"
    _write(
        target,
        "---\nname: dev-learn\nx-augur-hub: brain\n---\n"
        "skills/ai/augur/agent-rules.md\n"
        "skills/frontend/references/design-standards.md\n",
    )
    _write(tmp_path / "docs" / "agent-topics" / "agent-rules.md", "# live\n")
    _write(
        tmp_path / "project-brain" / "capabilities" / "skills" / "frontend" / "references" / "design-standards.md",
        "# live\n",
    )

    scan = mod.scan(OpsContext(project_root=tmp_path))
    fixed = mod.fix(OpsContext(project_root=tmp_path), scan.issues)

    assert isinstance(fixed, FixResult)
    assert fixed.success is True
    updated = target.read_text(encoding="utf-8")
    assert "docs/agent-topics/agent-rules.md" in updated
    assert "skills/frontend/references/design-standards.md" in updated


def test_scan_prefers_exact_replacement_over_generic_candidate(tmp_path: Path) -> None:
    _write(
        tmp_path / "project-brain" / "capabilities" / "skills" / "rag" / "SKILL.md",
        "---\nname: rag\nx-augur-hub: brain\n---\n"
        "skills/rag/dashboard.yaml\n",
    )
    _write(tmp_path / "project-brain" / "capabilities" / "skills" / "rag" / "SKILL.md.bak", "placeholder\n")

    result = mod.scan(OpsContext(project_root=tmp_path))
    replacements = result.issues[0]["replacements"]
    assert replacements == [{
        "old": "skills/rag/dashboard.yaml",
        "new": "project-brain/capabilities/skills/rag/SKILL.md",
    }]


def test_scan_ignores_non_brain_hub_files(tmp_path: Path) -> None:
    _write(
        tmp_path / "project-brain" / "capabilities" / "skills" / "save" / "SKILL.md",
        "---\nname: save\nx-augur-hub: command\n---\n"
        "skills/ai/augur/agent-rules.md\n",
    )
    _write(tmp_path / "docs" / "agent-topics" / "agent-rules.md", "# live\n")

    result = mod.scan(OpsContext(project_root=tmp_path))
    assert result.issues == []
