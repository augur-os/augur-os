"""Regression tests for runtime sync command entrypoints."""

from __future__ import annotations

from pathlib import Path

import pytest


PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])


@pytest.mark.parametrize(
    ("relative_path", "expected", "forbidden"),
    [
        (
            "plugins/vscode/src/extension.ts",
            "uv run python -m skills.ai.scripts.sync_agents sync all",
            "python -m .claude.skills.ai.scripts.sync_agents --all",
        ),
        (
            # Obsidian invokes the canonical entrypoint via execFile argv (no
            # shell — rule 30), so the args appear as an array, not a single
            # "uv run python -m ... sync all" string.
            "plugins/obsidian/src/main.ts",
            '"skills.ai.scripts.sync_agents", "sync", "all"',
            ".claude.skills.ai.scripts.sync_agents",
        ),
        (
            "project-brain/capabilities/skills/routine-vault/scripts/claude_md_audit.py",
            '"skills.ai.scripts.sync_agents", "sync", "all"',
            '"skills" / "ai" / "scripts" / "sync_agents.py"',
        ),
    ],
)
def test_runtime_callers_use_canonical_sync_entrypoint(
    relative_path: str,
    expected: str,
    forbidden: str,
) -> None:
    content = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")

    assert expected in content
    assert forbidden not in content
