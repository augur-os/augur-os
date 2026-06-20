from __future__ import annotations

import json
from pathlib import Path


def test_run_demo_case_eval_scores_deck_evidence_and_writes_record(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.evals.scripts import demo_case_records, eval_ops

    documents_dir = tmp_path / "documents"
    monkeypatch.setattr(demo_case_records, "get_documents_dir", lambda: documents_dir)
    monkeypatch.setattr(demo_case_records, "get_documents_machine_dir", lambda name: documents_dir / "_augur" / name)
    evidence_path = tmp_path / "vault" / "notes" / "demo" / "evidence" / "deck.md"
    evidence_path.parent.mkdir(parents=True)
    evidence_path.write_text(
        """---
title: Demo evidence: deck-slide-critique
type: demo-evidence
---
# Demo Evidence: Deck Slide Critique

## Source

- File: `Augur Demo Deck`
- Backend: `local-critique`

## Useful Snippet

The Augur Demo Deck critique names Claude and Gemini, cites offline OpenVINO,
flags empty metadata, and explains a specific slide transcript risk for Browse.
""",
        encoding="utf-8",
    )

    result = eval_ops.run_demo_case_eval(
        "deck-slide-critique",
        "Augur Demo Deck",
        evidence_path,
        4_200,
    )

    record_path = Path(result["record_path"])
    payload = json.loads(record_path.read_text(encoding="utf-8"))

    assert result["status"] == "pass"
    assert result["run_id"] == payload["run_id"]
    assert record_path.parent == documents_dir / "_augur" / "evals" / "demo-runs"
    assert result["scores"]["grounding"] >= 4
    assert payload["case_id"] == "deck-slide-critique"
    assert payload["evidence_path"] == str(evidence_path)
    assert payload["scores"] == result["scores"]
    assert payload["findings"] == result["findings"]


def test_run_demo_case_eval_preserves_source_path_in_private_record(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.evals.scripts import demo_case_records, eval_ops

    documents_dir = tmp_path / "documents"
    monkeypatch.setattr(demo_case_records, "get_documents_dir", lambda: documents_dir)
    monkeypatch.setattr(demo_case_records, "get_documents_machine_dir", lambda name: documents_dir / "_augur" / name)
    source_path = tmp_path / "media" / "weekly-planning.m4a"
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(b"audio")
    evidence_path = tmp_path / "vault" / "notes" / "demo" / "evidence" / "meeting.md"
    evidence_path.parent.mkdir(parents=True)
    evidence_path.write_text(
        (
            "# Demo Evidence: Meeting Transcript\n\n"
            "## Useful Snippet\n\n"
            "Weekly Planning Transcript captures the meeting source, transcript, "
            "decisions, and actions for offline Browse review.\n"
        ),
        encoding="utf-8",
    )

    result = eval_ops.run_demo_case_eval(
        "meeting-transcript",
        "Weekly Planning Transcript",
        evidence_path,
        None,
        source_path=source_path,
    )

    payload = json.loads(Path(result["record_path"]).read_text(encoding="utf-8"))

    assert result["status"] == "pass"
    assert payload["source_path"] == str(source_path)


def test_run_demo_case_eval_scores_useful_snippet_not_generated_metadata(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.evals.scripts import demo_case_records, eval_ops

    documents_dir = tmp_path / "documents"
    monkeypatch.setattr(demo_case_records, "get_documents_dir", lambda: documents_dir)
    monkeypatch.setattr(demo_case_records, "get_documents_machine_dir", lambda name: documents_dir / "_augur" / name)
    evidence_path = tmp_path / "vault" / "notes" / "demo" / "evidence" / "deck.md"
    evidence_path.parent.mkdir(parents=True)
    evidence_path.write_text(
        """---
title: Demo evidence: deck-slide-critique
type: demo-evidence
source_file_name: Augur Demo Deck.md
---
# Demo Evidence: Deck Slide Critique

## Source

- File: `Augur Demo Deck.md`
- Client: `claude`
- Backend: `offline OpenVINO`
- Output: `/vault/notes/demo/Augur Demo Deck slide transcript.md`

## Useful Snippet

The critique broadly says Claude, Gemini, offline OpenVINO, metadata, slide
transcript, and Browse are useful, but does not ground the claim in the source.

## Demo Case Eval

- Status: `pass`
""",
        encoding="utf-8",
    )

    result = eval_ops.run_demo_case_eval(
        "deck-slide-critique",
        "Augur Demo Deck.md",
        evidence_path,
        4_200,
    )

    assert result["status"] == "fail"
    assert any("source title" in finding.lower() for finding in result["findings"])


def test_run_demo_case_eval_fails_scaffold_only_demo_evidence_without_snippet(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.evals.scripts import demo_case_records, eval_ops

    documents_dir = tmp_path / "documents"
    monkeypatch.setattr(demo_case_records, "get_documents_dir", lambda: documents_dir)
    monkeypatch.setattr(demo_case_records, "get_documents_machine_dir", lambda name: documents_dir / "_augur" / name)
    evidence_path = tmp_path / "vault" / "notes" / "demo" / "evidence" / "deck.md"
    evidence_path.parent.mkdir(parents=True)
    evidence_path.write_text(
        """---
title: Demo evidence: deck-slide-critique
type: demo-evidence
source_file_name: Augur Demo Deck.md
---
# Demo Evidence: Deck Slide Critique

## Source

- File: `Augur Demo Deck.md`
- Client: `claude`
- Backend: `offline OpenVINO`
- Output: `/vault/notes/demo/Augur Demo Deck slide transcript.md`
""",
        encoding="utf-8",
    )

    result = eval_ops.run_demo_case_eval(
        "deck-slide-critique",
        "Augur Demo Deck.md",
        evidence_path,
        4_200,
    )

    assert result["status"] == "fail"
    assert any("source title" in finding.lower() for finding in result["findings"])
