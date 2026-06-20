"""Migration inventory helpers for the staged Apple skill."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MigrationClassification:
    target: str
    reason: str


@dataclass(frozen=True)
class MigrationItem:
    relative_path: str
    target: str
    reason: str


STANDARD_APPLE_PREFIXES = (
    "references/reminders-sync.md",
    "references/remote-control-apple-remote.md",
    "scripts/__init__.py",
    "scripts/apple_notes.py",
    "scripts/calendar_query.swift",
    "scripts/calendar_service.py",
    "scripts/note_ingest.py",
    "scripts/note_sync.py",
    "scripts/note_watcher.py",
    "scripts/notes_lib.py",
    "scripts/remote_control.py",
    "scripts/sync/",
    "scripts/voice.py",
)

INGEST_EMAIL_PREFIXES = (
    "augur/tests/test_desktop_inbox.py",
    "augur/tests/test_detect_patterns.py",
    "augur/tests/test_email_inbox.py",
    "augur/tests/test_inbox.py",
    "augur/tests/test_migrate_inboxes.py",
    "augur/tests/test_process_inbox.py",
    "augur/tests/test_show_inbox.py",
    "augur/tests/test_triage_inbox.py",
    "scripts/desktop_inbox.py",
    "scripts/detect_patterns.py",
    "scripts/email_inbox.py",
    "scripts/inbox.py",
    "scripts/migrate_inboxes.py",
    "scripts/process_inbox.py",
    "scripts/show_inbox.py",
    "scripts/triage_inbox.py",
)

VAULT_NOTE_TAKING_PREFIXES = (
    "augur/tests/test_migrate_sync_frontmatter.py",
    "scripts/migrate_sync_frontmatter.py",
    "scripts/sync_discover.py",
)

AUGUR_PROJECTION_PREFIXES = (
    "SKILL.md",
    "_config/",
    "augur/tests/test_apple_mcp.py",
    "augur/tests/test_notes_mcp_live_state.py",
    "augur/tests/test_tools_",
    "evals/",
    "scripts/mcp/",
)


def classify_apple_staged_path(relative_path: str) -> MigrationClassification:
    normalized = relative_path.replace("\\", "/")
    path_parts = set(normalized.split("/"))

    if "__pycache__" in path_parts or normalized.endswith((".pyc", ".pyo")):
        return MigrationClassification("discard", "generated Python cache")
    if normalized.startswith(INGEST_EMAIL_PREFIXES):
        return MigrationClassification(
            "ingest-email",
            "email and inbox intake belongs to ingest",
        )
    if normalized.startswith(VAULT_NOTE_TAKING_PREFIXES):
        return MigrationClassification(
            "vault-note-taking",
            "vault frontmatter and note-routing behavior belongs outside Apple",
        )
    if normalized.startswith(AUGUR_PROJECTION_PREFIXES):
        return MigrationClassification(
            "augur-projection",
            "Augur metadata, MCP, dashboard, eval, or generated integration",
        )
    if normalized.startswith(STANDARD_APPLE_PREFIXES) or normalized.startswith(
        "augur/tests/test_"
    ):
        return MigrationClassification("standard-apple", "portable Apple device capability")
    return MigrationClassification("review", "requires manual classification")


def collect_apple_migration_matrix(staged_root: Path) -> list[MigrationItem]:
    items: list[MigrationItem] = []
    for path in sorted(
        candidate for candidate in staged_root.rglob("*") if candidate.is_file()
    ):
        relative_path = path.relative_to(staged_root).as_posix()
        classification = classify_apple_staged_path(relative_path)
        items.append(
            MigrationItem(
                relative_path=relative_path,
                target=classification.target,
                reason=classification.reason,
            )
        )
    return items
