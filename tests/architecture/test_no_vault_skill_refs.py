"""Verify no string literals matching vault-tier skill names remain in src/.

Track 3a verification gate: replaces hardcoded skill enumerations
with dynamic discovery via src.mcp.augur_shared.skill_registry.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from src.config.paths import get_project_root

# Vault-tier skills per Track 2. These names should NOT appear as
# string literals in src/ (use is_vault_skill() / is_known_skill() instead).
#
# 'vault' is intentionally excluded from this list (post-ADR-605 rename):
# the bare token "vault" is overloaded across the codebase (project.yaml
# `vault:` config key, file-system categories, path components), so a
# blunt string-grep produces unmanageable false positives. Skill-name
# discovery for the vault skill is enforced dynamically via
# src.mcp.augur_shared.skill_registry instead.
VAULT_SKILL_NAMES = ["apple", "lifestyle", "file-manager", "ingest"]

# Files allowed to contain these names (registry, helpers, comments,
# test fixtures, generated artifacts):
ALLOWED_FILES = {
    "src/mcp/augur_shared/skill_registry.py",
    "src/mcp/augur_shared/plugin_tools.py",
    # browse/cli.py's `skill == "obsidian"` is an Obsidian-specific config
    # probe (`.obsidian/` directory check), not a vault-tier enumeration.
    "src/mcp/augur_framework/tools/infrastructure/browse/cli.py",
    # client_surface.PLUGIN_TOOL_SOURCES is a tool→skill mapping where
    # each value names the skill that owns the tool — by definition the
    # values include vault-tier skill names like 'file-manager'. This is
    # data, not a discovery enumeration; future tool registrations declare
    # their owner skill here directly.
    "src/mcp/augur_shared/client_surface.py",
    # paths.py keeps a skill-name → vault-relative-path registry
    # (_VAULT_FIRST_SKILL_VAULT_DIRS) that legitimately holds vault-tier
    # skill names as dict keys. This is data, not a discovery enumeration.
    "src/config/paths.py",
}


def _scan_python_files() -> list[Path]:
    src = get_project_root() / "src"
    skipped_parts = {"__pycache__", ".venv", "venv", "env", "site-packages"}
    return [p for p in src.rglob("*.py") if skipped_parts.isdisjoint(p.parts)]


@pytest.mark.parametrize("skill_name", VAULT_SKILL_NAMES)
def test_no_vault_skill_string_literals_in_src(skill_name: str) -> None:
    pattern = re.compile(rf'["\']({re.escape(skill_name)})["\']')
    violations: list[tuple[Path, int]] = []

    project_root = get_project_root()
    for path in _scan_python_files():
        rel = path.relative_to(project_root).as_posix()
        if rel in ALLOWED_FILES:
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if pattern.search(line):
                # Skip comments
                stripped = line.split("#", 1)[0]
                if pattern.search(stripped):
                    violations.append((path.relative_to(project_root), lineno))

    assert not violations, f"Vault skill name {skill_name!r} found as string literal in src/:\n" + "\n".join(
        f"  {p}:{ln}" for p, ln in violations
    )
