from __future__ import annotations

import importlib
import sys
from pathlib import Path


PROJECT_ROOT = next(
    (
        p
        for p in Path(__file__).resolve().parents
        if (p / "pyproject.toml").exists() and (p / ".git").exists()
    ),
    Path(__file__).resolve().parents[-1],
)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

mod = importlib.import_module("skills.auto-skill-quality.scripts.standard_skill_migration")
classify_apple_staged_path = mod.classify_apple_staged_path
collect_apple_migration_matrix = mod.collect_apple_migration_matrix


def test_classify_apple_staged_paths() -> None:
    assert classify_apple_staged_path("scripts/note_sync.py").target == "standard-apple"
    assert classify_apple_staged_path("scripts/apple_notes.py").target == "standard-apple"
    assert classify_apple_staged_path("scripts/calendar_query.swift").target == "standard-apple"
    assert classify_apple_staged_path("scripts/voice.py").target == "standard-apple"
    assert classify_apple_staged_path("scripts/email_inbox.py").target == "ingest-email"
    assert classify_apple_staged_path("augur/tests/test_email_inbox.py").target == "ingest-email"
    assert (
        classify_apple_staged_path("scripts/migrate_sync_frontmatter.py").target
        == "vault-note-taking"
    )
    assert classify_apple_staged_path("_config/config.yaml").target == "augur-projection"
    assert classify_apple_staged_path("scripts/mcp/tools_notes.py").target == "augur-projection"
    assert classify_apple_staged_path("scripts/__pycache__/x.pyc").target == "discard"


def test_collect_apple_migration_matrix(tmp_path: Path) -> None:
    staged = tmp_path / "apple"
    (staged / "scripts").mkdir(parents=True)
    (staged / "_config").mkdir()
    (staged / "scripts" / "note_sync.py").write_text(
        "print('notes')\n",
        encoding="utf-8",
    )
    (staged / "scripts" / "email_inbox.py").write_text(
        "print('mail')\n",
        encoding="utf-8",
    )
    (staged / "scripts" / "migrate_sync_frontmatter.py").write_text(
        "print('vault')\n",
        encoding="utf-8",
    )
    (staged / "_config" / "config.yaml").write_text(
        "x-augur-hub: workspace\n",
        encoding="utf-8",
    )

    matrix = collect_apple_migration_matrix(staged)

    assert [(item.relative_path, item.target) for item in matrix] == [
        ("_config/config.yaml", "augur-projection"),
        ("scripts/email_inbox.py", "ingest-email"),
        ("scripts/migrate_sync_frontmatter.py", "vault-note-taking"),
        ("scripts/note_sync.py", "standard-apple"),
    ]
