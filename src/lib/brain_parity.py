"""Parity gate for the single-brain to layered cutover (ADR-781 section 2c)."""

from __future__ import annotations

from dataclasses import dataclass

from src.lib.brain_effective import compute_effective_skills
from src.lib.brain_layered_projection import resolve_layered_projection
from src.lib.brain_stack import BrainStack


@dataclass(frozen=True)
class SkillParityResult:
    ok: bool
    added: set[str]
    dropped: set[str]


def assert_skill_parity(
    stack: BrainStack,
    *,
    single_brain_skills: set[str],
) -> SkillParityResult:
    """Require layered effective skills to preserve the old single-brain set."""
    layered = set(compute_effective_skills(resolve_layered_projection(stack)).names())
    dropped = single_brain_skills - layered
    added = layered - single_brain_skills
    return SkillParityResult(ok=not dropped, added=added, dropped=dropped)
