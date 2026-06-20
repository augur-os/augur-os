from __future__ import annotations

import importlib.util
import json
import sys
from datetime import date
from pathlib import Path

import pytest

from src.lib.frontmatter_utils import parse_frontmatter


PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
URL_INGEST_PATH = (
    PROJECT_ROOT / "project-brain" / "capabilities" / "skills" / "ingest" / "scripts" / "url_ingest.py"
)


def _load_url_ingest():
    spec = importlib.util.spec_from_file_location("ingest_url_ingest", URL_INGEST_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["ingest_url_ingest"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def _isolate_runtime_queue(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AUGUR_STATE", str(tmp_path / "runtime-state"))


def _meta(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "title": "Why Trees Matter",
        "canonical_url": "https://example.com/a",
        "content_hash": "sha256:" + ("0" * 64),
        "tags": ["trees", "ecology"],
        "captured_at": "2026-05-10T12:00:00Z",
        "note": None,
    }
    base.update(overrides)
    return base


def _write_url_card(module, tmp_path: Path) -> Path:
    return module.write_url_source_card(
        vault_dir=tmp_path,
        meta=_meta(),
        body="Trees are the lungs of the planet.",
        today=date(2026, 5, 10),
    )


def test_write_url_card_creates_file_in_notes_dir(tmp_path: Path) -> None:
    url_ingest = _load_url_ingest()

    path = _write_url_card(url_ingest, tmp_path)

    assert path.parent == tmp_path / "knowledge" / "notes"
    # naming spec 2026-06-12 Wave 3: date-free slug derived from the page title
    assert not path.stem[0].isdigit(), f"name must not start with date digit: {path.name}"
    assert path.name.endswith(".md")


def test_write_url_card_frontmatter_shape(tmp_path: Path) -> None:
    url_ingest = _load_url_ingest()

    path = _write_url_card(url_ingest, tmp_path)

    frontmatter, body = parse_frontmatter(path)
    assert frontmatter["title"] == "Why Trees Matter"
    assert frontmatter["source_type"] == "url"
    assert frontmatter["canonical_url"] == "https://example.com/a"
    assert frontmatter["content_hash"].startswith("sha256:")
    assert frontmatter["tags"] == ["trees", "ecology"]
    assert frontmatter["captured_at"] == "2026-05-10T12:00:00Z"
    assert "lungs of the planet" in body


def test_write_url_card_enqueues_for_enrichment(
    tmp_path: Path,
    monkeypatch,
) -> None:
    url_ingest = _load_url_ingest()
    qpath = tmp_path / "runtime" / "pending_enrichment.jsonl"
    monkeypatch.setattr(
        url_ingest,
        "get_pending_enrichment_queue_path",
        lambda: qpath,
        raising=False,
    )

    path = _write_url_card(url_ingest, tmp_path)

    assert qpath.exists()
    entries = [
        json.loads(line)
        for line in qpath.read_text(encoding="utf-8").splitlines()
    ]
    assert len(entries) == 1
    assert entries[0]["note_path"] == str(path)
    assert entries[0]["reason"] == "new"


def test_write_url_card_queue_failure_does_not_block_note_write(
    tmp_path: Path,
    monkeypatch,
) -> None:
    url_ingest = _load_url_ingest()
    qpath = tmp_path / "runtime" / "pending_enrichment.jsonl"
    calls: list[Path] = []

    def fail_enqueue(queue_path: Path, *, note_path: Path, reason: str) -> bool:
        assert queue_path == qpath
        assert reason == "new"
        calls.append(note_path)
        raise RuntimeError("queue boom")

    monkeypatch.setattr(
        url_ingest,
        "get_pending_enrichment_queue_path",
        lambda: qpath,
        raising=False,
    )
    monkeypatch.setattr(url_ingest, "enqueue", fail_enqueue, raising=False)

    path = _write_url_card(url_ingest, tmp_path)

    assert path.exists()
    assert calls == [path]


def test_write_url_card_optional_note(tmp_path: Path) -> None:
    url_ingest = _load_url_ingest()

    path = url_ingest.write_url_source_card(
        vault_dir=tmp_path,
        meta=_meta(note="reading list"),
        body="b",
        today=date(2026, 5, 10),
    )

    frontmatter, _ = parse_frontmatter(path)
    assert frontmatter["note"] == "reading list"


def test_write_url_card_collision_safe(tmp_path: Path) -> None:
    url_ingest = _load_url_ingest()

    first = url_ingest.write_url_source_card(
        vault_dir=tmp_path,
        meta=_meta(content_hash="sha256:" + ("a" * 64)),
        body="first",
        today=date(2026, 5, 10),
    )
    second = url_ingest.write_url_source_card(
        vault_dir=tmp_path,
        meta=_meta(content_hash="sha256:" + ("b" * 64)),
        body="second",
        today=date(2026, 5, 10),
    )

    assert first != second
    assert first.exists()
    assert second.exists()


def test_find_existing_url_card_by_hash(tmp_path: Path) -> None:
    url_ingest = _load_url_ingest()
    content_hash = "sha256:" + ("c" * 64)
    written = url_ingest.write_url_source_card(
        vault_dir=tmp_path,
        meta=_meta(content_hash=content_hash),
        body="b",
        today=date(2026, 5, 10),
    )

    found = url_ingest.find_existing_url_card(tmp_path, content_hash)
    assert found == written


def test_find_existing_url_card_missing(tmp_path: Path) -> None:
    url_ingest = _load_url_ingest()
    (tmp_path / "knowledge" / "notes").mkdir(parents=True)

    assert url_ingest.find_existing_url_card(tmp_path, "sha256:nope") is None
