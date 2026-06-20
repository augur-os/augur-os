"""Goal catalogs for routine-level autonomous runs."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


class UnknownGoalError(KeyError):
    """Raised when a routine-loop goal id is not in the catalog."""


@dataclass(frozen=True)
class GoalSpec:
    """A general routine goal resolved to ordered loop names."""

    id: str
    title: str
    loops: tuple[str, ...]
    rubric: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class GoalStep:
    """One deterministic proof step in a concrete goal."""

    id: str
    title: str
    kind: str
    required: bool = True
    fix_hint: str = ""


@dataclass(frozen=True)
class GoalDefinition:
    """A concrete user goal resolved to ordered proof steps."""

    id: str
    title: str
    description: str
    aliases: tuple[str, ...]
    steps: tuple[GoalStep, ...]


# Loop names are the `loop:` values declared by the routine-* skills.
GOAL_CATALOG: dict[str, GoalSpec] = {
    "harden": GoalSpec(
        id="harden",
        title="Harden the codebase and platform",
        loops=("testing", "code-quality", "page-health", "hardening", "auto-security-audit"),
        rubric="Drive tests/build/lint green, repair page wiring, close platform + security gaps.",
        tags=("harden",),
    ),
    "clean": GoalSpec(
        id="clean",
        title="Clean vault, docs, and skill hygiene",
        loops=("knowledge-enrichment", "skill-standards", "command-evolution"),
        rubric="Repair frontmatter, stale references, skill standards, and command coverage.",
        tags=("clean",),
    ),
    "harden-and-clean": GoalSpec(
        id="harden-and-clean",
        title="Harden then clean the whole project",
        loops=(
            "testing",
            "code-quality",
            "ui-quality",
            "page-health",
            "hardening",
            "auto-security-audit",
            "observability",
            "skill-standards",
            "command-evolution",
            "knowledge-enrichment",
        ),
        rubric="Full sweep: code green first, then platform/security, then hygiene.",
        tags=("harden", "clean"),
    ),
}

_DEMO_READINESS = GoalDefinition(
    id="demo-readiness",
    title="Prepare demo",
    description=(
        "Run the demo readiness, smoke, and project-compounding proof checks "
        "until the current AI-client session can harden the demo flow."
    ),
    aliases=("prepare demo", "first demo", "demo", "investor demo"),
    steps=(
        GoalStep(
            id="demo-readiness",
            title="Demo readiness",
            kind="demo_ready",
            fix_hint="Fix missing local/offline demo prerequisites before rerunning.",
        ),
        GoalStep(
            id="demo-smoke",
            title="Demo smoke",
            kind="demo_smoke",
            fix_hint="Repair the reset, ingest, transcript, or artifact verification failure.",
        ),
        GoalStep(
            id="compound-review",
            title="Project compounding review",
            kind="compound_review",
            fix_hint=(
                "Create an evidence-backed compound proposal JSON from the runtime "
                "evidence, or harden the wiki/skill proof gate that failed."
            ),
        ),
    ),
)

STEP_GOALS = {
    _DEMO_READINESS.id: _DEMO_READINESS,
}
STEP_ALIASES = {
    alias: goal_id
    for goal_id, goal in STEP_GOALS.items()
    for alias in goal.aliases
}


def catalog() -> list[GoalSpec]:
    """Return all general routine goal specs sorted by id."""

    return [GOAL_CATALOG[gid] for gid in sorted(GOAL_CATALOG)]


def resolve(goal_id: str) -> GoalSpec:
    """Return one general routine goal spec by id."""

    try:
        return GOAL_CATALOG[goal_id]
    except KeyError as exc:
        raise UnknownGoalError(
            f"unknown goal {goal_id!r}; known: {sorted(GOAL_CATALOG)}"
        ) from exc


def list_goals() -> list[GoalDefinition]:
    """Return concrete goals in display order."""

    return [STEP_GOALS[key] for key in sorted(STEP_GOALS)]


def get_goal(goal_id: str) -> GoalDefinition:
    """Resolve a concrete goal id or alias."""

    normalized = " ".join(str(goal_id).strip().lower().split())
    resolved = STEP_ALIASES.get(normalized, normalized)
    try:
        return STEP_GOALS[resolved]
    except KeyError as exc:
        known = ", ".join(sorted([*STEP_GOALS, *STEP_ALIASES]))
        raise ValueError(f"unknown routine goal {goal_id!r}; known goals: {known}") from exc


def goal_payload(goal: GoalDefinition) -> dict:
    """JSON-safe summary for concrete goal CLI output."""

    return {
        "id": goal.id,
        "title": goal.title,
        "description": goal.description,
        "aliases": list(goal.aliases),
        "steps": [
            {
                "id": step.id,
                "title": step.title,
                "kind": step.kind,
                "required": step.required,
                "fix_hint": step.fix_hint,
            }
            for step in goal.steps
        ],
    }


def steps_for_goal(goal: GoalDefinition, *, skip_smoke: bool = False) -> Iterable[GoalStep]:
    """Yield ordered steps for a concrete goal run."""

    for step in goal.steps:
        if skip_smoke and step.id == "demo-smoke":
            continue
        yield step
