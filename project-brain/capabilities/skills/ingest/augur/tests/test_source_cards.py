from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
SOURCE_CARDS_PATH = (
    PROJECT_ROOT / "project-brain" / "capabilities" / "skills" / "ingest" / "scripts" / "source_cards.py"
)
INBOX_ROUTING_PATH = (
    PROJECT_ROOT / "project-brain" / "capabilities" / "skills" / "ingest" / "scripts" / "inbox_routing.py"
)


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _load_source_cards():
    return _load_module("ingest_source_cards", SOURCE_CARDS_PATH)


def _load_inbox_routing():
    return _load_module("ingest_inbox_routing", INBOX_ROUTING_PATH)


@pytest.fixture(autouse=True)
def _isolate_runtime_queue(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AUGUR_STATE", str(tmp_path / "runtime-state"))


def _meeting_decision():
    routing = _load_inbox_routing()
    return routing.RouteDecision(
        route="meetings",
        filename="2026-05-07-product-roadmap-meeting.mp3",
        reason="Audio meeting detected.",
    )


def _write_card(module, tmp_path: Path):
    return module.write_source_card(
        vault_dir=tmp_path,
        title="Product roadmap meeting",
        body="Summary text.",
        decision=_meeting_decision(),
        original_path="C:/Users/example/Desktop/meeting.mp3",
        final_path=str(tmp_path / "meetings" / "2026-05-07-product-roadmap-meeting.mp3"),
        extracted_path=str(
            tmp_path
            / "sources"
            / "files"
            / "2026-05-07-product-roadmap-meeting.transcript.md"
        ),
        extraction_method="faster-whisper",
        hardware_backend="CPU",
        confidence="medium",
        content_type="audio",
    )


def test_pending_enrichment_queue_path_uses_runtime_dir(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from src.config import paths as paths_mod

    monkeypatch.setattr(paths_mod, "get_runtime_dir", lambda: tmp_path / "runtime")

    assert (
        paths_mod.get_pending_enrichment_queue_path()
        == tmp_path / "runtime" / "pending_enrichment.jsonl"
    )


def test_route_decision_uses_meeting_audio_summary() -> None:
    routing = _load_inbox_routing()

    decision = routing.decide_route(
        source_name="meeting.mp3",
        title="Product roadmap meeting",
        body="Discussed roadmap decisions and follow-up actions.",
        content_type="audio",
    )

    assert decision.route == "meetings"
    assert decision.filename.endswith("product-roadmap-meeting.mp3")


def test_source_card_starts_with_frontmatter(tmp_path: Path) -> None:
    from src.lib.frontmatter_utils import parse_frontmatter

    source_cards = _load_source_cards()
    card = _write_card(source_cards, tmp_path)

    text = card.read_text(encoding="utf-8")
    metadata, _ = parse_frontmatter(card)
    assert card.parent == tmp_path / "knowledge" / "notes"
    assert metadata["x-augur-note-type"] == "file"
    assert text.startswith("---\n")
    assert "Product roadmap meeting" in text
    assert "Audio meeting detected." in text


def test_source_card_write_enqueues_for_enrichment(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source_cards = _load_source_cards()
    qpath = tmp_path / "runtime" / "pending_enrichment.jsonl"
    monkeypatch.setattr(
        source_cards,
        "get_pending_enrichment_queue_path",
        lambda: qpath,
        raising=False,
    )

    card = _write_card(source_cards, tmp_path)

    assert qpath.exists()
    entries = [
        json.loads(line)
        for line in qpath.read_text(encoding="utf-8").splitlines()
    ]
    assert len(entries) == 1
    assert entries[0]["note_path"] == str(card)
    assert entries[0]["reason"] == "new"


def test_source_card_queue_failure_does_not_block_note_write(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source_cards = _load_source_cards()
    qpath = tmp_path / "runtime" / "pending_enrichment.jsonl"
    calls: list[Path] = []

    def fail_enqueue(queue_path: Path, *, note_path: Path, reason: str) -> bool:
        assert queue_path == qpath
        assert reason == "new"
        calls.append(note_path)
        raise RuntimeError("queue boom")

    monkeypatch.setattr(
        source_cards,
        "get_pending_enrichment_queue_path",
        lambda: qpath,
        raising=False,
    )
    monkeypatch.setattr(source_cards, "enqueue", fail_enqueue, raising=False)

    card = _write_card(source_cards, tmp_path)

    assert card.exists()
    assert calls == [card]


def test_source_card_uses_collision_safe_filename(tmp_path: Path) -> None:
    source_cards = _load_source_cards()

    first = source_cards.write_source_card(
        vault_dir=tmp_path,
        title="Product roadmap meeting",
        body="First summary.",
        decision=_meeting_decision(),
        original_path="C:/Users/example/Desktop/meeting.mp3",
        final_path=None,
        extracted_path=None,
        extraction_method="faster-whisper",
        hardware_backend="CPU",
        confidence="medium",
        content_type="audio",
    )
    second = source_cards.write_source_card(
        vault_dir=tmp_path,
        title="Product roadmap meeting",
        body="Second summary.",
        decision=_meeting_decision(),
        original_path="C:/Users/example/Desktop/meeting-copy.mp3",
        final_path=None,
        extracted_path=None,
        extraction_method="faster-whisper",
        hardware_backend="CPU",
        confidence="medium",
        content_type="audio",
    )

    assert first.name == "2026-05-07-product-roadmap-meeting.md"
    assert second.name == "2026-05-07-product-roadmap-meeting-2.md"
    assert first.parent == tmp_path / "knowledge" / "notes"
    assert second.parent == tmp_path / "knowledge" / "notes"
    assert "First summary." in first.read_text(encoding="utf-8")
    assert "Second summary." in second.read_text(encoding="utf-8")


def test_source_card_writes_content_hash_frontmatter(tmp_path: Path) -> None:
    from src.lib.frontmatter_utils import parse_frontmatter

    source_cards = _load_source_cards()
    card = source_cards.write_source_card(
        vault_dir=tmp_path,
        title="Product roadmap meeting",
        body="Summary text.",
        decision=_meeting_decision(),
        original_path="C:/Users/example/Desktop/meeting.mp3",
        final_path=None,
        extracted_path=None,
        extraction_method="faster-whisper",
        hardware_backend="CPU",
        confidence="medium",
        content_type="audio",
        content_hash="sha256:provided",
    )

    metadata, _ = parse_frontmatter(card)
    assert metadata["content_hash"] == "sha256:provided"
    assert metadata["x-augur-note-type"] == "file"


def test_source_card_computes_stable_content_hash(tmp_path: Path) -> None:
    from src.lib.frontmatter_utils import parse_frontmatter

    source_cards = _load_source_cards()
    kwargs = {
        "title": "Product roadmap meeting",
        "body": "Summary text.",
        "decision": _meeting_decision(),
        "original_path": "C:/Users/example/Desktop/meeting.mp3",
        "final_path": None,
        "extracted_path": None,
        "extraction_method": "faster-whisper",
        "hardware_backend": "CPU",
        "confidence": "medium",
        "content_type": "audio",
    }
    first = source_cards.write_source_card(vault_dir=tmp_path / "one", **kwargs)
    second = source_cards.write_source_card(vault_dir=tmp_path / "two", **kwargs)

    first_metadata, _ = parse_frontmatter(first)
    second_metadata, _ = parse_frontmatter(second)
    assert first_metadata["content_hash"]
    assert first_metadata["content_hash"] == second_metadata["content_hash"]


def test_source_card_formats_multiline_summary_as_callout(tmp_path: Path) -> None:
    source_cards = _load_source_cards()
    card = source_cards.write_source_card(
        vault_dir=tmp_path,
        title="Product roadmap meeting",
        body="Line one.\nLine two.\n\nLine four.",
        decision=_meeting_decision(),
        original_path="C:/Users/example/Desktop/meeting.mp3",
        final_path=None,
        extracted_path=None,
        extraction_method="faster-whisper",
        hardware_backend="CPU",
        confidence="medium",
        content_type="audio",
    )

    text = card.read_text(encoding="utf-8")
    assert "> Line one.\n> Line two.\n>\n> Line four." in text


def test_audio_source_card_contains_meeting_memory(tmp_path: Path) -> None:
    source_cards = _load_source_cards()
    routing = _load_inbox_routing()
    card = source_cards.write_source_card(
        vault_dir=tmp_path,
        title="Investor demo meeting",
        body="Decision: use airplane mode first. Action: Gur will prepare fixture pack.",
        decision=routing.RouteDecision(
            route="meetings",
            filename="2026-05-07-investor-demo.mp3",
            reason="Audio meeting or recording detected.",
        ),
        original_path="C:/Desktop/demo-meeting.mp3",
        final_path=str(tmp_path / "meetings" / "2026-05-07-investor-demo.mp3"),
        extracted_path=str(
            tmp_path
            / "sources"
            / "extracted"
            / "2026-05-07-investor-demo.transcript.md"
        ),
        extraction_method="document-extractor:0",
        hardware_backend="local",
        confidence="high",
        content_type="audio",
    )

    text = card.read_text(encoding="utf-8")
    assert "## Meeting Memory" in text
    assert "- use airplane mode first." in text
    assert "- [ ] Gur will prepare fixture pack." in text
