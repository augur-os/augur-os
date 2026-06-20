from __future__ import annotations

from typing import Callable

from src.lib.onboard.prereqs import detect_prereqs
from src.lib.onboard.result import OnboardContext, StepResult
from src.lib.onboard.steps import build_dashboard, seed_brain_and_vault, sync_deps, wire_mcp
from src.lib.onboard.verify import verify

Step = tuple[str, Callable[[OnboardContext], StepResult]]


def _verify_step(ctx: OnboardContext) -> StepResult:
    from src.lib.onboard.live_probes import live_probes  # wired in Task 7

    return verify(ctx, probes=live_probes(ctx))


STEPS: list[Step] = [
    ("detect_prereqs", detect_prereqs),
    ("sync_deps", sync_deps),
    ("build_dashboard", build_dashboard),
    ("wire_mcp", wire_mcp),
    ("seed_brain_and_vault", seed_brain_and_vault),
    ("verify", _verify_step),
]

_ICON = {"ok": "✓", "guide": "→", "fail": "✗"}


def run_onboard(ctx: OnboardContext, steps: list[Step] | None = None) -> list[tuple[str, StepResult]]:
    """Run steps in order; stop on the first non-ok. Returns (name, result) pairs
    for the steps that ran. Re-running is safe because each step is idempotent.

    Interactive (default): a ``guide`` step stops with its guidance so the user
    can resolve it and re-run. Non-interactive (CI): a ``guide`` step is a hard
    failure — there is no human to act on the guidance, so the run aborts."""
    steps = steps if steps is not None else STEPS
    results: list[tuple[str, StepResult]] = []
    for name, fn in steps:
        result = fn(ctx)
        results.append((name, result))
        print(f"{_ICON.get(result.status, '?')} {name}: {result.message}")
        if not result.is_ok:
            if ctx.non_interactive and result.status == "guide":
                print(f"  non-interactive: {name} requires manual action, aborting")
            remaining = [n for n, _ in steps[len(results) :]]
            if remaining:
                print(f"  stopped; remaining: {', '.join(remaining)}")
            break
    return results


def is_hard_failure(results: list[tuple[str, StepResult]], ctx: OnboardContext) -> bool:
    """True when the onboard run did not reach a fully-ok end state (the signal
    the CLI turns into a non-zero exit code). Empty results, or a trailing
    non-ok step (``fail`` always; ``guide`` both interactively and, especially,
    in non-interactive CI where no human can resolve it), are hard failures."""
    if not results:
        return True
    return not results[-1][1].is_ok
