"""Scan generated client directories for duplicate external skill IDs (ADR-734 D5)."""

from __future__ import annotations

from pathlib import Path

_CLIENT_DIRS = (
    (".claude", "claude"),
    (".codex", "codex"),
    (".gemini", "gemini"),
    (".opencode", "opencode"),
)


def find_external_skill_duplicates(
    project_root: Path,
) -> list[tuple[str, tuple[str, ...]]]:
    """Return ``(skill_name, (client, ...))`` tuples for skills present in 2+ clients."""
    by_name: dict[str, list[str]] = {}
    for dirname, client in _CLIENT_DIRS:
        skills_dir = project_root / dirname / "skills"
        if not skills_dir.is_dir():
            continue
        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            if not (skill_dir / "SKILL.md").exists():
                continue
            by_name.setdefault(skill_dir.name, []).append(client)
    return [(name, tuple(clients)) for name, clients in sorted(by_name.items()) if len(clients) > 1]
