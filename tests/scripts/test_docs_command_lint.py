from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    PROJECT_ROOT / "project-brain" / "capabilities" / "skills" / "platform-admin" / "scripts" / "docs_command_lint.py"
)
SPEC = importlib.util.spec_from_file_location("docs_command_lint", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
lint = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = lint
SPEC.loader.exec_module(lint)


def test_windows_section_rejects_bash_only_commands(tmp_path: Path) -> None:
    doc = tmp_path / "plan.md"
    fence = "`" * 3
    doc.write_text(
        f"""
# Plan

## Windows verification

{fence}bash
python3 scripts/example.py
grep -R thing .
{fence}
""".lstrip(),
        encoding="utf-8",
    )

    issues = lint.lint_file(doc)

    assert any(issue.code == "windows-bash-command" for issue in issues)


def test_posix_labeled_bash_is_allowed(tmp_path: Path) -> None:
    doc = tmp_path / "plan.md"
    fence = "`" * 3
    doc.write_text(
        f"""
# Plan

## POSIX verification

{fence}bash
python3 scripts/example.py
grep -R thing .
{fence}
""".lstrip(),
        encoding="utf-8",
    )

    assert lint.lint_file(doc) == []


def test_cross_platform_section_requires_platform_labels_for_shell_blocks(tmp_path: Path) -> None:
    doc = tmp_path / "plan.md"
    fence = "`" * 3
    doc.write_text(
        f"""
# Cross-platform command

{fence}bash
./scripts/xa-launch.sh --help
{fence}
""".lstrip(),
        encoding="utf-8",
    )

    issues = lint.lint_file(doc)

    assert any(issue.code == "unlabeled-bash-block" for issue in issues)


def test_generic_bash_block_outside_cross_platform_context_is_allowed(tmp_path: Path) -> None:
    doc = tmp_path / "plan.md"
    fence = "`" * 3
    doc.write_text(
        f"""
# Local helper

{fence}bash
python3 scripts/example.py
{fence}
""".lstrip(),
        encoding="utf-8",
    )

    assert lint.lint_file(doc) == []


def test_nearby_posix_label_allows_bash_block(tmp_path: Path) -> None:
    doc = tmp_path / "plan.md"
    fence = "`" * 3
    doc.write_text(
        f"""
# Cross-platform command

POSIX verification:

{fence}bash
./scripts/xa-launch.sh --help
{fence}
""".lstrip(),
        encoding="utf-8",
    )

    assert lint.lint_file(doc) == []


def test_posix_section_after_windows_section_does_not_inherit_windows_context(tmp_path: Path) -> None:
    doc = tmp_path / "plan.md"
    fence = "`" * 3
    doc.write_text(
        f"""
# Manual verification

## Windows verification

Expected: PowerShell function works.

## POSIX verification

Run in a POSIX shell:

{fence}bash
./scripts/xa-launch.sh --help
{fence}
""".lstrip(),
        encoding="utf-8",
    )

    assert lint.lint_file(doc) == []
