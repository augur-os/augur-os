from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
QUEUE_PATH = PROJECT_ROOT / "project-brain" / "capabilities" / "skills" / "ingest" / "scripts" / "pending_enrichment_queue.py"


def _load_queue():
    spec = importlib.util.spec_from_file_location("ingest_pending_queue", QUEUE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["ingest_pending_queue"] = module
    spec.loader.exec_module(module)
    return module


def test_enqueue_then_read_returns_entry(tmp_path: Path) -> None:
    q = _load_queue()
    qfile = tmp_path / "state" / "pending_enrichment.jsonl"

    enqueued = q.enqueue(qfile, note_path=Path("/vault/notes/a.md"), reason="new")

    assert enqueued is True
    entries = q.read_pending(qfile)
    assert len(entries) == 1
    assert entries[0]["note_path"].endswith("a.md")
    assert entries[0]["reason"] == "new"
    assert "enqueued_at" in entries[0]
    assert qfile.exists()


def test_drain_removes_processed_entries(tmp_path: Path) -> None:
    q = _load_queue()
    qfile = tmp_path / "pending_enrichment.jsonl"
    q.enqueue(qfile, note_path=Path("/vault/notes/a.md"), reason="new")
    q.enqueue(qfile, note_path=Path("/vault/notes/b.md"), reason="new")
    q.enqueue(qfile, note_path=Path("/vault/notes/c.md"), reason="new")

    removed = q.drain(qfile, processed_note_paths={Path("/vault/notes/a.md"), Path("/vault/notes/c.md")})

    assert removed == 2
    remaining = q.read_pending(qfile)
    assert len(remaining) == 1
    assert remaining[0]["note_path"].endswith("b.md")


def test_dedup_does_not_enqueue_same_path_twice(tmp_path: Path) -> None:
    q = _load_queue()
    qfile = tmp_path / "pending_enrichment.jsonl"

    first = q.enqueue(qfile, note_path=Path("/vault/notes/a.md"), reason="new")
    second = q.enqueue(qfile, note_path=Path("/vault/notes/a.md"), reason="new")

    assert first is True
    assert second is False
    entries = q.read_pending(qfile)
    assert len(entries) == 1


def test_read_pending_tolerates_missing_and_malformed_lines(tmp_path: Path) -> None:
    q = _load_queue()
    qfile = tmp_path / "pending_enrichment.jsonl"

    assert q.read_pending(qfile) == []

    qfile.write_text(
        "\n".join(
            [
                '{"note_path": "/vault/notes/a.md", "reason": "new"}',
                "not-json",
                '{"note_path": "/vault/notes/b.md", "reason": "new"}',
                "",
            ]
        ),
        encoding="utf-8",
    )

    entries = q.read_pending(qfile)
    assert [entry["note_path"] for entry in entries] == ["/vault/notes/a.md", "/vault/notes/b.md"]


def test_drain_handles_empty_and_missing_queue(tmp_path: Path) -> None:
    q = _load_queue()
    missing = tmp_path / "missing" / "pending_enrichment.jsonl"
    empty = tmp_path / "pending_enrichment.jsonl"
    empty.write_text("", encoding="utf-8")

    assert q.drain(missing, processed_note_paths={Path("/vault/notes/a.md")}) == 0
    assert q.drain(empty, processed_note_paths={Path("/vault/notes/a.md")}) == 0
    assert q.read_pending(empty) == []
