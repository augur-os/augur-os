# skills/plugin-pack/scripts/profiles.py
"""Filter profiles for plugin-pack targets."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FilterProfile:
    """Defines which skills to include for a given target platform."""

    name: str
    groups: frozenset[str]
    excluded_prefixes: tuple[str, ...]
    excluded_skills: frozenset[str]
    commands: dict[str, dict] = field(default_factory=dict)


_CANONICAL_COMMANDS = {
    "ask": {
        "description": "Ask your personal/global second brain any question",
        "body": "Search personal/global knowledge, notes, documents, memory, and history. Use /project ask for current-folder project questions.",
    },
    "discover": {
        "description": "Show Augur capabilities, commands, and system state",
        "body": "Use the canonical Augur discovery command to inspect available capabilities, commands, client surfaces, and system state without mutating the current folder.",
    },
    "keep": {
        "description": "Capture or persist anything to personal/global context",
        "body": "Use the canonical Augur keep command to capture URLs, files, audio, images, folders, thoughts, or generated artifacts. Use /project keep for current-folder project capture.",
    },
    "project": {
        "description": "Current-folder project router",
        "body": "Use the canonical Augur project command to initialize, inspect, ask, keep, skillify, run routines, manage ADRs, run development workflows, and sweep artifacts for the current folder.",
    },
    "routines": {
        "description": "Unified command surface for personal/global Augur routines",
        "body": "Use the canonical Augur routines command to list, run, report, and inspect recurring AI-orchestrated routines. Use /project routines for current-folder project routines.",
    },
    "skillify": {
        "description": "Convert a recurring incident or durable gap into an Augur skill",
        "body": "Use the canonical Augur skillify command to guide a concrete incident, recurring bug, or persistent capability gap into a durable skill. Use /project skillify for project-scoped skill creation.",
    },
}

_COPILOT_PROMPT_COMMANDS = {
    "ask": _CANONICAL_COMMANDS["ask"],
    "wiki": {
        "description": "Manage the shared wiki layer",
        "body": "Use the Augur wiki command to inspect, update, rebuild, lint, and report on durable compiled knowledge.",
    },
}

_COMMON_EXCLUDED_SKILLS = frozenset({
    "ai", "commands", "rag", "scraper", "advisor",
    "frontend", "page-builder", "dashboard", "daemon",
    "kill-augur", "system-cleanup", "test-client", "test-ui",
    "validator", "mcp-app-factory", "devops", "nightly",
    "reindex-project", "auto-rag-reindex", "sync-agents",
    "updater", "discovery", "workflows",
    "file-manager", "observe", "metrics", "plugin-pack",
})

# `groups` holds the x-augur-group values a target packages. cowork is a
# knowledge-collaboration surface, so it ships only the "brain" group (the
# user's second-brain skills). The coding assistants (codex / gemini / copilot)
# run inside the Augur repo, so they additionally ship the core, dev/quality-
# loop, and admin groups. _COMMON_EXCLUDED_SKILLS and the prefix filters still
# drop the truly-internal skills (daemon, plugin-pack, ai, rag, auto-*) on top
# of the group filter.
COWORK_PROFILE = FilterProfile(
    name="cowork",
    groups=frozenset({"brain"}),
    excluded_prefixes=("auto-", "dev-", "client-"),
    excluded_skills=_COMMON_EXCLUDED_SKILLS | {"developer", "onboard"},
    # Desktop has no repo checkout, so these hydrate to the full command docs
    # (keep.md carries the shell-free Session Reconcile flow for bare /keep —
    # spec 2026-06-11-session-keep-artifact-reconcile).
    commands={
        "ask": _CANONICAL_COMMANDS["ask"],
        "keep": _CANONICAL_COMMANDS["keep"],
    },
)

CODEX_PROFILE = FilterProfile(
    name="codex",
    groups=frozenset({"brain", "augur_core", "augur_autoloops", "augur_admin"}),
    excluded_prefixes=("auto-", "client-"),
    excluded_skills=_COMMON_EXCLUDED_SKILLS,
    commands=_CANONICAL_COMMANDS,
)

GEMINI_PROFILE = FilterProfile(
    name="gemini",
    groups=CODEX_PROFILE.groups,
    excluded_prefixes=CODEX_PROFILE.excluded_prefixes,
    excluded_skills=CODEX_PROFILE.excluded_skills,
    commands=CODEX_PROFILE.commands,
)

COPILOT_PROFILE = FilterProfile(
    name="copilot",
    groups=CODEX_PROFILE.groups,
    excluded_prefixes=CODEX_PROFILE.excluded_prefixes,
    excluded_skills=CODEX_PROFILE.excluded_skills,
    commands=_COPILOT_PROMPT_COMMANDS,
)

_PROFILES = {
    "cowork": COWORK_PROFILE,
    "codex": CODEX_PROFILE,
    "gemini": GEMINI_PROFILE,
    "copilot": COPILOT_PROFILE,
}


def get_profile(target: str) -> FilterProfile:
    """Look up a filter profile by target name."""
    if target not in _PROFILES:
        raise ValueError(f"Unknown target: {target!r}. Available: {sorted(_PROFILES)}")
    return _PROFILES[target]
