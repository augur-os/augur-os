"""Tests for auto-studio-hub-coverage."""
from __future__ import annotations

import importlib.util
from pathlib import Path

from src.lib.ops_protocol import FixResult, OpsContext, ScanResult

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "studio_hub_coverage_ops.py"
_SPEC = importlib.util.spec_from_file_location("studio_hub_coverage_under_test", _MODULE_PATH)
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _ctx(tmp_path: Path, **kw) -> OpsContext:
    return OpsContext(project_root=tmp_path, **kw)


def test_scan_detects_legacy_studio_refs(tmp_path: Path) -> None:
    _write(
        tmp_path / "project-brain" / "capabilities" / "skills" / "frontend" / "SKILL.md",
        """---
x-augur-hub: studio
name: frontend
---

# Frontend

Storage: `plugins/dev/skills/executor/augur/backlog/`
""",
    )
    _write(tmp_path / "project-brain" / "capabilities" / "skills" / "executor" / "augur" / "backlog" / ".gitkeep", "")

    result = mod.scan(_ctx(tmp_path))

    assert isinstance(result, ScanResult)
    assert len(result.issues) == 1
    assert result.issues[0]["path"] == "project-brain/capabilities/skills/frontend/SKILL.md"
    assert result.issues[0]["replacements"][0]["old"] == "plugins/dev/skills/executor/augur/backlog/"
    assert result.issues[0]["replacements"][0]["new"] == "project-brain/capabilities/skills/executor/augur/backlog/"


def test_fix_rewrites_legacy_refs(tmp_path: Path) -> None:
    target = tmp_path / "project-brain" / "capabilities" / "skills" / "validator" / "references" / "workflow.md"
    _write(
        tmp_path / "project-brain" / "capabilities" / "skills" / "validator" / "SKILL.md",
        """---
x-augur-hub: studio
name: validator
---

# Validator
""",
    )
    _write(
        target,
        "See `plugins/observability/skills/executor/augur/backlog/` for backlog.\n",
    )
    _write(tmp_path / "project-brain" / "capabilities" / "skills" / "executor" / "augur" / "backlog" / ".gitkeep", "")

    issues = mod.scan(_ctx(tmp_path)).issues
    result = mod.fix(_ctx(tmp_path), issues)
    updated = target.read_text(encoding="utf-8")

    assert isinstance(result, FixResult)
    assert result.success is True
    assert "project-brain/capabilities/skills/executor/augur/backlog/" in updated
    assert "plugins/observability/skills/executor/augur/backlog/" not in updated


def test_scan_ignores_non_studio_hub_files(tmp_path: Path) -> None:
    _write(
        tmp_path / "project-brain" / "capabilities" / "skills" / "observe" / "SKILL.md",
        """---
x-augur-hub: command
name: observe
---

# Observe

Legacy: `project-brain/capabilities/skills/daemon/`
""",
    )
    _write(tmp_path / "project-brain" / "capabilities" / "skills" / "daemon" / "SKILL.md", "---\nname: daemon\n---\n")

    result = mod.scan(_ctx(tmp_path))
    assert result.issues == []
