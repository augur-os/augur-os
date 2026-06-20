from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
SCRIPT_PATH = (
    PROJECT_ROOT
    / "project-brain"
    / "capabilities"
    / "skills"
    / "ingest"
    / "augur"
    / "scripts"
    / "run_pending_enrichment.py"
)
QUEUE_PATH = (
    PROJECT_ROOT
    / "project-brain"
    / "capabilities"
    / "skills"
    / "ingest"
    / "scripts"
    / "pending_enrichment_queue.py"
)


def _load_script():
    spec = importlib.util.spec_from_file_location("ingest_run_pending_enrichment", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["ingest_run_pending_enrichment"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _load_queue():
    spec = importlib.util.spec_from_file_location("ingest_pending_enrichment_queue", QUEUE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["ingest_pending_enrichment_queue"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write_entry(queue_path: Path, note_path: Path) -> None:
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    queue_path.write_text(
        json.dumps(
            {
                "note_path": str(note_path),
                "reason": "test",
                "enqueued_at": "2026-05-16T00:00:00+00:00",
            }
        )
        + "\n",
        encoding="utf-8",
    )


def test_empty_queue_prints_queue_empty(monkeypatch, tmp_path, capsys) -> None:
    script = _load_script()
    queue_path = tmp_path / "runtime" / "pending_enrichment.jsonl"
    monkeypatch.setattr(script, "get_pending_enrichment_queue_path", lambda: queue_path)

    assert script.main(["--max-per-run", "1"]) == 0

    captured = capsys.readouterr()
    assert "[run_pending_enrichment] queue empty." in captured.out


def test_missing_note_path_is_drained_as_stale(monkeypatch, tmp_path, capsys) -> None:
    script = _load_script()
    queue = _load_queue()
    queue_path = tmp_path / "runtime" / "pending_enrichment.jsonl"
    missing_note = tmp_path / "notes" / "deleted.md"
    _write_entry(queue_path, missing_note)
    monkeypatch.setattr(script, "get_pending_enrichment_queue_path", lambda: queue_path)

    assert script.main(["--max-per-run", "1"]) == 0

    captured = capsys.readouterr()
    assert "stale=1" in captured.out
    assert queue.read_pending(queue_path) == []


def test_successful_dispatch_drains_entry(monkeypatch, tmp_path, capsys) -> None:
    script = _load_script()
    queue = _load_queue()
    queue_path = tmp_path / "runtime" / "pending_enrichment.jsonl"
    note = tmp_path / "notes" / "article.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("---\nx-augur-note-type: url\n---\n\n## Original content\n\nText.\n", encoding="utf-8")
    _write_entry(queue_path, note)
    monkeypatch.setattr(script, "get_pending_enrichment_queue_path", lambda: queue_path)
    monkeypatch.setattr(script, "_dispatch_enrichment_via_cli", lambda _note, **_kwargs: True)

    assert script.main(["--max-per-run", "1"]) == 0

    captured = capsys.readouterr()
    assert "processed=1" in captured.out
    assert "drained=1" in captured.out
    assert queue.read_pending(queue_path) == []


def test_failed_dispatch_leaves_entry_queued(monkeypatch, tmp_path, capsys) -> None:
    script = _load_script()
    queue = _load_queue()
    queue_path = tmp_path / "runtime" / "pending_enrichment.jsonl"
    note = tmp_path / "notes" / "article.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("---\nx-augur-note-type: url\n---\n\n## Original content\n\nText.\n", encoding="utf-8")
    _write_entry(queue_path, note)
    monkeypatch.setattr(script, "get_pending_enrichment_queue_path", lambda: queue_path)
    monkeypatch.setattr(script, "_dispatch_enrichment_via_cli", lambda _note, **_kwargs: False)

    assert script.main(["--max-per-run", "1"]) == 0

    captured = capsys.readouterr()
    assert "processed=0" in captured.out
    assert "failed=1" in captured.out
    assert queue.read_pending(queue_path)[0]["note_path"] == str(note)
