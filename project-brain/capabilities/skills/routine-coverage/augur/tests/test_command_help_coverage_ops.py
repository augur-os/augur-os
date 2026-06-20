"""Tests for auto-command-help-coverage."""
from __future__ import annotations

import importlib.util
from pathlib import Path

from src.lib.ops_protocol import FixResult, OpsContext, ScanResult

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "command_help_coverage_ops.py"
_SPEC = importlib.util.spec_from_file_location("command_help_coverage_under_test", _MODULE_PATH)
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _ctx(tmp_path: Path, **kw) -> OpsContext:
    return OpsContext(project_root=tmp_path, **kw)


def _shared_skills(tmp_path: Path) -> Path:
    return tmp_path / "project-brain" / "capabilities" / "skills"


def test_scan_detects_missing_help_sections(tmp_path: Path) -> None:
    skill_md = _shared_skills(tmp_path) / "demo-command" / "SKILL.md"
    _write(
        skill_md,
        """---
x-augur-hub: command
x-augur-type: command
name: demo-command
---

# /demo-command

## Usage

```bash
/demo-command --status  # Show status
/demo-command --fix     # Repair state
```
""",
    )

    result = mod.scan(_ctx(tmp_path))

    assert isinstance(result, ScanResult)
    assert len(result.issues) == 1
    assert result.issues[0]["missing_sections"] == ["Examples", "Options", "Mode Selection"]


def test_fix_adds_examples_options_and_mode_selection(tmp_path: Path) -> None:
    skill_md = _shared_skills(tmp_path) / "demo-command" / "SKILL.md"
    _write(
        skill_md,
        """---
x-augur-hub: command
x-augur-type: command
name: demo-command
---

# /demo-command

## Usage

```bash
/demo-command --status  # Show status
/demo-command --fix     # Repair state
```

## Additional resources

- data/.gitkeep
""",
    )

    issues = mod.scan(_ctx(tmp_path)).issues
    result = mod.fix(_ctx(tmp_path), issues)
    updated = skill_md.read_text(encoding="utf-8")

    assert isinstance(result, FixResult)
    assert result.success is True
    assert "## Examples" in updated
    assert "## Options" in updated
    assert "## Mode Selection" in updated
    assert "`--status`" in updated
    assert "`--fix`" in updated
    assert updated.index("## Examples") < updated.index("## Additional resources")


def test_fix_infers_usage_for_header_only_command(tmp_path: Path) -> None:
    skill_md = _shared_skills(tmp_path) / "careful" / "SKILL.md"
    _write(
        skill_md,
        """---
x-augur-hub: command
x-augur-type: command
name: careful
---

# /careful — Destructive Command Blocker

Blocks destructive operations for the session.
""",
    )

    issues = mod.scan(_ctx(tmp_path)).issues
    result = mod.fix(_ctx(tmp_path), issues)
    updated = skill_md.read_text(encoding="utf-8")

    assert result.success is True
    assert "## Usage" in updated
    assert "/careful" in updated
    assert "## Examples" in updated


def test_scan_does_not_treat_prose_flags_as_command_options(tmp_path: Path) -> None:
    skill_md = _shared_skills(tmp_path) / "careful" / "SKILL.md"
    _write(
        skill_md,
        """---
x-augur-hub: command
x-augur-type: command
name: careful
---

# /careful

Blocks `git push --force` and `git reset --hard` for safety.
""",
    )

    result = mod.scan(_ctx(tmp_path))

    assert len(result.issues) == 1
    assert result.issues[0]["missing_sections"] == ["Usage", "Examples"]


def test_scan_does_not_require_mode_selection_for_positional_examples(tmp_path: Path) -> None:
    skill_md = _shared_skills(tmp_path) / "save" / "SKILL.md"
    _write(
        skill_md,
        """---
x-augur-hub: command
x-augur-type: command
name: save
---

# /save

## Usage

```bash
/save
/save banner.png
/save report.pdf
```
""",
    )

    result = mod.scan(_ctx(tmp_path))

    assert len(result.issues) == 1
    assert result.issues[0]["missing_sections"] == ["Examples"]


def test_scan_ignores_non_command_skills(tmp_path: Path) -> None:
    skill_md = _shared_skills(tmp_path) / "observe" / "SKILL.md"
    _write(
        skill_md,
        """---
x-augur-hub: command
x-augur-type: domain
name: observe
---

# Observe
""",
    )

    result = mod.scan(_ctx(tmp_path))
    assert result.issues == []
