"""Pure classifier for the bare-name loop command surface.

`a-loops <token>`: the token is classified (verb | prompt-loop | orchestrator-loop
| catalog-goal | unknown) and routed. No argparse/registry coupling lives here —
the caller passes the known sets, so this is fully unit-testable.
"""
from __future__ import annotations

import difflib
from dataclasses import dataclass


@dataclass(frozen=True)
class RouteDecision:
    kind: str                       # verb | prompt | orchestrator | goal | unknown
    argv: list[str] | None = None   # rewritten args after "a-loops" (None for verb/unknown)
    message: str | None = None      # friendly text for unknown


def resolve_loop_token(
    token: str,
    *,
    verbs: set[str],
    prompt_loops: set[str],
    orchestrator_loops: set[str],
    goals: set[str],
) -> RouteDecision:
    """Classify the first token after `a-loops`. Precedence: verb > loop > goal > unknown."""
    if token in verbs:
        return RouteDecision(kind="verb")
    if token in prompt_loops:
        return RouteDecision(kind="prompt", argv=["run", token])
    if token in orchestrator_loops:
        return RouteDecision(kind="orchestrator", argv=["goal", token, "--catalog-loop"])
    if token in goals:
        return RouteDecision(kind="goal", argv=["goal", token, "--catalog-loop"])

    universe = sorted(prompt_loops | orchestrator_loops | goals)
    close = difflib.get_close_matches(token, universe, n=3, cutoff=0.6)
    hint = f" — did you mean: {', '.join(close)}?" if close else ""
    loops = ", ".join(sorted(prompt_loops | orchestrator_loops)) or "(none)"
    msg = (
        f"unknown loop or goal {token!r}{hint}\n"
        f"loops: {loops}\n"
        f"goals: {', '.join(sorted(goals)) or '(none)'}\n"
        f"verbs: {', '.join(sorted(verbs))}"
    )
    return RouteDecision(kind="unknown", message=msg)
