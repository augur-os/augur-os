"""Skill registry helpers — dynamic discovery to replace hardcoded lists.

Replaces hardcoded vault-private skill names (apple, lifestyle, etc.)
across src/. Backed by the same skill scanner used by Track 2's
plugin_tools._collect_skill_dirs().
"""

from __future__ import annotations

import functools
from pathlib import Path

from src.mcp.augur_shared.plugin_tools import _collect_skill_dirs


@functools.lru_cache(maxsize=1)
def _all_skill_dirs() -> tuple[Path, ...]:
    return tuple(skill_dir for _plugin_id, skill_dir in _collect_skill_dirs(apply_exclusions=False))


@functools.lru_cache(maxsize=1)
def _all_skill_names() -> frozenset[str]:
    return frozenset(sd.name for sd in _all_skill_dirs())


@functools.lru_cache(maxsize=1)
def _vault_skill_names() -> frozenset[str]:
    """Names of skills whose source dir lives outside the Augur repo (vault-tier)."""
    from src.config.paths import get_project_root

    project_root = get_project_root().resolve()
    out: set[str] = set()
    for sd in _all_skill_dirs():
        try:
            sd.resolve().relative_to(project_root)
        except ValueError:
            out.add(sd.name)
    return frozenset(out)


def is_known_skill(name: str) -> bool:
    """True if `name` is a registered skill (vault-tier or project-tier)."""
    return name in _all_skill_names()


def is_vault_skill(name: str) -> bool:
    """True if `name` is a vault-tier skill (resides outside the Augur repo)."""
    return name in _vault_skill_names()


def all_known_skills() -> frozenset[str]:
    return _all_skill_names()


def all_vault_skills() -> frozenset[str]:
    return _vault_skill_names()


__all__ = [
    "is_known_skill",
    "is_vault_skill",
    "all_known_skills",
    "all_vault_skills",
]
