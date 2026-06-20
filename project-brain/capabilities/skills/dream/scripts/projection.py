"""Cross-client routine projection metadata for the Dream Cycle (ADR-744).

Thin façade module. The actual per-client materialization lives in the
sync_agents adapter modules (one method per adapter). This module exposes:

- ``dream_codex_seed_path()`` — absolute path to the skill-local routine
  schedule seed yaml the Codex adapter reads
- ``dream_routine_doc_path()`` — absolute path to ``commands/dream.md``, the
  source the per-client command projection picks up automatically
- ``dream_manual_command_template()`` — markdown body for clients with no
  native routine surface (Cursor / Copilot graceful degradation)
- ``dream_activation_hint(client_id)`` — one-line activation reminder the
  adapter prints in the post-sync report, e.g. "Run ``/schedule /dream``
  once in Claude Code to activate the overnight cycle."

By keeping these as pure metadata accessors, the dream skill stays decoupled
from the sync_agents engine internals — adapters call these accessors, dream
never imports sync_agents.
"""
from __future__ import annotations

from pathlib import Path


_SKILL_ROOT = Path(__file__).resolve().parents[1]


def dream_codex_seed_path() -> Path:
    """Absolute path to the Codex schedule-seed yaml emitted by this skill."""
    return _SKILL_ROOT / "assets" / "seeds" / "routine-schedule.yaml"


def dream_routine_doc_path() -> Path:
    """Absolute path to ``commands/dream.md`` — the routine prompt."""
    return _SKILL_ROOT / "commands" / "dream.md"


def dream_manual_command_template() -> str:
    """Markdown body used by clients with no native routine surface.

    Cursor and Copilot don't expose a programmatic scheduling surface, so the
    dream cycle ships as a manual ``/dream`` slash command the user fires when
    they want a compounding pass.
    """
    return (
        "# /dream\n\n"
        "Run the Dream Cycle manually. This client has no native routine surface,\n"
        "so dream is fired on demand instead of scheduled. The full ten-phase\n"
        "routine lives in `commands/dream.md` of the dream skill — invoke `/dream`\n"
        "here and the active AI session will execute the phases.\n"
    )


_ACTIVATION_HINTS: dict[str, str] = {
    "codex": (
        "Dream Cycle is auto-scheduled via Codex automations "
        "(daily 04:00 local). No manual activation needed — re-running "
        "`sync_agents` keeps the schedule up to date."
    ),
    "claude-code": (
        "Dream Cycle is projected as `/dream`. Run `/schedule /dream` once "
        "in Claude Code to activate the overnight cycle."
    ),
    "gemini": (
        "Dream Cycle is projected as `/dream`. Activate via Gemini's "
        "scheduled-routine surface (one-time registration)."
    ),
    "cursor": (
        "Dream Cycle has no native scheduling in Cursor. Run `/dream` "
        "manually when you want a compounding pass."
    ),
    "copilot": (
        "Dream Cycle has no native scheduling in Copilot. Run `/dream` "
        "manually when you want a compounding pass."
    ),
}


def dream_activation_hint(client_id: str) -> str:
    """Return the one-line activation hint for ``client_id``."""
    return _ACTIVATION_HINTS.get(
        client_id,
        f"Dream Cycle command projected. Activation for {client_id!r}: "
        "consult the client's scheduled-routine surface if any; otherwise "
        "invoke `/dream` manually.",
    )


__all__ = [
    "dream_codex_seed_path",
    "dream_routine_doc_path",
    "dream_manual_command_template",
    "dream_activation_hint",
]
