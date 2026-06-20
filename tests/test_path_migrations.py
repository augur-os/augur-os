"""Tests for the path-migration redirect map (src/lib/path_migrations.py)."""

from __future__ import annotations

import textwrap
from pathlib import Path

from src.lib import path_migrations as pm


def _write_map(tmp_path: Path, old: str, new: str) -> Path:
    cfg = tmp_path / "path_migrations.yaml"
    cfg.write_text(
        textwrap.dedent(f"""
            migrations:
              - old: {old}
                new: {new}
                date: 2026-06-13
                note: test move
            """),
        encoding="utf-8",
    )
    return cfg


def test_load_migrations_expands_and_skips_malformed(tmp_path: Path) -> None:
    cfg = tmp_path / "m.yaml"
    cfg.write_text(
        textwrap.dedent("""
            migrations:
              - old: ~/old-root
                new: ~/new-root
              - old: only-old
              - not-a-dict
            """),
        encoding="utf-8",
    )
    migs = pm.load_migrations(cfg)
    assert len(migs) == 1
    assert migs[0]["old"].endswith("/old-root")
    assert migs[0]["new"].endswith("/new-root")
    assert migs[0]["old"].startswith("/")  # expanded to absolute


def test_load_missing_file_returns_empty(tmp_path: Path) -> None:
    assert pm.load_migrations(tmp_path / "nope.yaml") == []


def test_resolve_successor_exact_root(tmp_path: Path) -> None:
    old = tmp_path / "Au-docs"
    new = tmp_path / "Documents"
    new.mkdir()  # successor exists; old does not
    migs = pm.load_migrations(_write_map(tmp_path, str(old), str(new)))
    assert pm.resolve_successor(old, migs) == new


def test_resolve_successor_subpath(tmp_path: Path) -> None:
    old = tmp_path / "Au-docs"
    new = tmp_path / "Documents"
    (new / "venture/decks").mkdir(parents=True)
    migs = pm.load_migrations(_write_map(tmp_path, str(old), str(new)))
    got = pm.resolve_successor(old / "venture/decks", migs)
    assert got == new / "venture/decks"


def test_no_repair_when_successor_absent(tmp_path: Path) -> None:
    """Old path moved but the rewritten path doesn't exist -> no unsafe repair."""
    old = tmp_path / "Au-docs"
    new = tmp_path / "Documents"  # not created
    migs = pm.load_migrations(_write_map(tmp_path, str(old), str(new)))
    assert pm.resolve_successor(old / "sub", migs) is None


def test_no_repair_when_path_still_exists(tmp_path: Path) -> None:
    """A path that exists is not dangling and must not be rewritten."""
    old = tmp_path / "Au-docs"
    old.mkdir()
    new = tmp_path / "Documents"
    new.mkdir()
    migs = pm.load_migrations(_write_map(tmp_path, str(old), str(new)))
    assert pm.resolve_successor(old, migs) is None


def test_unrelated_missing_path_returns_none(tmp_path: Path) -> None:
    old = tmp_path / "Au-docs"
    new = tmp_path / "Documents"
    new.mkdir()
    migs = pm.load_migrations(_write_map(tmp_path, str(old), str(new)))
    assert pm.resolve_successor(tmp_path / "Unrelated/path", migs) is None


# ── auto-record / reconcile (migration hook) ──────────────────────────────────


def test_append_migration_dedups(tmp_path: Path) -> None:
    cfg = tmp_path / "m.yaml"
    cfg.write_text("migrations:\n", encoding="utf-8")
    assert pm.append_migration("/a", "/b", note="x", today="2026-06-16", config_path=cfg) is True
    # identical entry -> no second write
    assert pm.append_migration("/a", "/b", note="x", today="2026-06-16", config_path=cfg) is False
    assert len(pm.load_migrations(cfg)) == 1


def test_append_migration_preserves_comments(tmp_path: Path) -> None:
    cfg = tmp_path / "m.yaml"
    cfg.write_text("# leading comment\nmigrations:\n", encoding="utf-8")
    pm.append_migration("/x", "/y", note="moved", today="2026-06-16", config_path=cfg)
    text = cfg.read_text()
    assert "# leading comment" in text
    migs = pm.load_migrations(cfg)
    assert migs[0]["old"] == "/x" and migs[0]["new"] == "/y"


def test_reconcile_first_run_seeds_snapshot_no_records(tmp_path: Path, monkeypatch) -> None:
    cfg = tmp_path / "m.yaml"
    cfg.write_text("migrations:\n", encoding="utf-8")
    snap = tmp_path / "snap.json"
    monkeypatch.setattr(pm, "current_roots", lambda: {"documents": "/old/docs"})

    recorded = pm.reconcile_migrations(config_path=cfg, snapshot_path=snap, today="2026-06-16")
    assert recorded == []  # cold start invents nothing
    assert snap.exists()
    assert pm.load_migrations(cfg) == []


def test_reconcile_records_moved_root(tmp_path: Path, monkeypatch) -> None:
    cfg = tmp_path / "m.yaml"
    cfg.write_text("migrations:\n", encoding="utf-8")
    snap = tmp_path / "snap.json"

    # First run seeds snapshot at /old/docs.
    monkeypatch.setattr(pm, "current_roots", lambda: {"documents": "/old/docs"})
    pm.reconcile_migrations(config_path=cfg, snapshot_path=snap, today="2026-06-16")

    # Root moves -> recorded on next run.
    monkeypatch.setattr(pm, "current_roots", lambda: {"documents": "/new/docs"})
    recorded = pm.reconcile_migrations(config_path=cfg, snapshot_path=snap, today="2026-06-16")
    assert recorded == [{"root": "documents", "old": "/old/docs", "new": "/new/docs"}]
    migs = pm.load_migrations(cfg)
    assert (migs[0]["old"], migs[0]["new"]) == ("/old/docs", "/new/docs")

    # Stable root -> nothing new recorded.
    again = pm.reconcile_migrations(config_path=cfg, snapshot_path=snap, today="2026-06-16")
    assert again == []
