"""Tests for the inbox-to-notes migration script."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
MIGRATE_PATH = (
    PROJECT_ROOT
    / "project-brain"
    / "capabilities"
    / "skills"
    / "ingest"
    / "augur"
    / "scripts"
    / "migrate_inbox_to_notes.py"
)


def _load_migrate():
    spec = importlib.util.spec_from_file_location("ingest_migrate_inbox", MIGRATE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["ingest_migrate_inbox"] = module
    spec.loader.exec_module(module)
    return module


def _write_card(path: Path, frontmatter: dict, body: str = "stub body\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fm_lines = ["---"]
    for key, value in frontmatter.items():
        fm_lines.append(f"{key}: {value}")
    fm_lines.append("---\n")
    path.write_text("\n".join(fm_lines) + body, encoding="utf-8")


def test_migrates_inbox_source_to_notes(tmp_path):
    migrate = _load_migrate()
    vault = tmp_path / "vault"
    src = vault / "inbox" / "2026-05-10-url-example.md"
    _write_card(src, {"title": "Example", "source": "url"})

    report = migrate.migrate_vault(vault, dry_run=False)

    dst = vault / "notes" / "2026-05-10-url-example.md"
    assert report.moved == 1
    assert dst.exists()
    assert "x-augur-note-type: url" in dst.read_text(encoding="utf-8")
    assert not src.exists()


def test_migrates_prompts_to_notes(tmp_path):
    migrate = _load_migrate()
    vault = tmp_path / "vault"
    src = vault / "prompts" / "2026-05-10-prompt-pr-review.md"
    _write_card(src, {"label": "PR review", "prompt_triggerable": "true"})

    report = migrate.migrate_vault(vault, dry_run=False)

    dst = vault / "notes" / "2026-05-10-prompt-pr-review.md"
    assert report.moved == 1
    assert dst.exists()
    assert "x-augur-note-type: prompt" in dst.read_text(encoding="utf-8")


def test_migrates_sources_url_to_notes(tmp_path):
    migrate = _load_migrate()
    vault = tmp_path / "vault"
    src = vault / "sources" / "urls" / "2026-05-10-url-example2.md"
    _write_card(src, {"title": "Example2", "url": "https://example.com"})

    report = migrate.migrate_vault(vault, dry_run=False)

    dst = vault / "notes" / "2026-05-10-url-example2.md"
    assert report.moved == 1
    assert dst.exists()
    assert "x-augur-note-type: url" in dst.read_text(encoding="utf-8")


def test_is_idempotent(tmp_path):
    migrate = _load_migrate()
    vault = tmp_path / "vault"
    existing = vault / "notes" / "2026-05-10-thought-already-migrated.md"
    _write_card(existing, {"title": "x", "x-augur-note-type": "thought"})

    report = migrate.migrate_vault(vault, dry_run=False)
    report2 = migrate.migrate_vault(vault, dry_run=False)

    assert report.moved == 0
    assert report.skipped_already_migrated == 0
    assert report2.moved == 0


def test_dry_run_does_not_move(tmp_path):
    migrate = _load_migrate()
    vault = tmp_path / "vault"
    src = vault / "inbox" / "2026-05-10-url-example.md"
    _write_card(src, {"title": "Example", "source": "url"})

    report = migrate.migrate_vault(vault, dry_run=True)

    assert report.moved == 1
    assert src.exists()
