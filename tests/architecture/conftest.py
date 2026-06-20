# tests/architecture/conftest.py
"""Shared fixtures for architecture-rule tests.

These tests perform static analysis (AST parsing, regex search) on the codebase
to enforce architectural rules. They do not import or run skill code.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from src.config.paths import get_project_root, get_project_brain_skills_dir

# Workaround for pre-existing test-infra fragility.
#
# The root tests/conftest.py imports the repo-root `scripts` package at
# collection-time and locks it into sys.modules to prevent skill-local
# `scripts/` directories from shadowing it. The lock protects ~13 tests
# under tests/ that depend on the repo-root namespace.
#
# But it BREAKS skill-local tests that do `from scripts.X import Y`
# (e.g., skills/ingest/scripts/mcp/wiki_tools.py:46) when their tests
# get collected together with anything under tests/. The bug is on main
# today — verifiable via:
#   pytest tests/integration/ skills/ingest/augur/tests/test_wiki_tools.py
# which produces the same `ModuleNotFoundError: No module named
# 'scripts.detector'` regardless of Phase 0 changes.
#
# Track 1 of the bundle architecture migration is the structural fix —
# moving skill-local libraries to src/lib/ eliminates the bare-name
# `scripts` collision entirely.
#
# Until Track 1 lands, this top-level statement runs at conftest-load
# time (after tests/conftest.py loads, before skill conftests load) and
# pops the locked `scripts` module. Skill conftests that load later
# adjust sys.path so `import scripts` re-resolves to the skill's
# scripts/. The tests/ tests that depended on the lock are collected
# before this conftest loads (the lock is active during their import
# phase) and still work.
sys.modules.pop("scripts", None)


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Repository root directory."""
    return get_project_root()


@pytest.fixture(scope="session")
def skills_dir(project_root: Path) -> Path:
    """Path to the project's shared skills directory."""
    return get_project_brain_skills_dir(project_root)


@pytest.fixture(scope="session")
def project_skill_names(skills_dir: Path) -> set[str]:
    """Names of all skills in the project tier (skills with a SKILL.md or scripts/ dir)."""
    if not skills_dir.exists():
        return set()
    return {
        d.name for d in skills_dir.iterdir() if d.is_dir() and ((d / "SKILL.md").exists() or (d / "scripts").is_dir())
    }


def _vault_skills_dir() -> Path:
    """Au-vault skills/ location used by Track 2 vault-tier bundles."""
    return Path.home() / "Projects" / "Au-vault" / "skills"


@pytest.fixture(scope="session")
def vault_skill_names() -> set[str]:
    """Names of vault-tier skills present in Au-vault/skills/ (Track 2+).

    Used by allowlist validators that must accept vault→project edges as
    valid references — the importer skill lives in Au-vault, the imported
    skill lives in the project tier. Returns an empty set if Au-vault is
    not present (CI / fresh clones).
    """
    vault_dir = _vault_skills_dir()
    if not vault_dir.exists():
        return set()
    return {
        d.name for d in vault_dir.iterdir() if d.is_dir() and ((d / "SKILL.md").exists() or (d / "scripts").is_dir())
    }


# Vault-private skill names. These MUST NOT be referenced by string literal in
# project code (src/, apps/). They are the user's vault tier and the project
# must not encode their existence as a hardcoded assumption.
VAULT_PRIVATE_SKILL_NAMES: frozenset[str] = frozenset({"apple", "lifestyle"})


@pytest.fixture(scope="session")
def vault_private_names() -> frozenset[str]:
    return VAULT_PRIVATE_SKILL_NAMES
