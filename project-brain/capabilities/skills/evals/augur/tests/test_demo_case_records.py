from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_write_demo_case_eval_record_uses_private_documents_dir(
    monkeypatch, tmp_path: Path
) -> None:
    from skills.evals.scripts import demo_case_records as mod

    monkeypatch.setattr(mod, "get_documents_dir", lambda: tmp_path)
    monkeypatch.setattr(
        mod,
        "get_documents_machine_dir",
        lambda name: tmp_path / "_augur" / name,
    )
    evidence_path = Path("/vault/notes/demo/evidence/deck.md")
    source_path = Path("C:/Demo/Augur Demo.pptx")

    record = mod.write_demo_case_eval_record(
        case_id="deck-slide-critique",
        evidence_path=evidence_path,
        source_path=source_path,
        scores={"grounding": 4, "specificity": 5, "judge_readiness": 4, "speed": 3},
        findings=["Output named the actual slide and gave concrete design risks."],
    )

    expected_root = tmp_path / "_augur" / "evals" / "demo-runs"
    assert record.path.parent == expected_root
    assert record.path.is_file()
    assert record.path.relative_to(expected_root)
    assert record.case_id == "deck-slide-critique"
    assert record.scores["grounding"] == 4

    payload = json.loads(record.path.read_text(encoding="utf-8"))
    assert payload["case_id"] == "deck-slide-critique"
    assert payload["created_at"]
    assert payload["evidence_path"] == str(evidence_path)
    assert payload["source_path"] == str(source_path)
    assert payload["scores"]["grounding"] == 4
    assert payload["findings"] == [
        "Output named the actual slide and gave concrete design risks."
    ]


def test_write_demo_case_eval_record_uses_unique_non_overwriting_paths(
    monkeypatch, tmp_path: Path
) -> None:
    from skills.evals.scripts import demo_case_records as mod

    monkeypatch.setattr(mod, "get_documents_dir", lambda: tmp_path)
    monkeypatch.setattr(
        mod,
        "get_documents_machine_dir",
        lambda name: tmp_path / "_augur" / name,
    )

    kwargs = {
        "case_id": "deck-slide-critique",
        "evidence_path": Path("/vault/notes/demo/evidence/deck.md"),
        "source_path": Path("C:/Demo/Augur Demo.pptx"),
        "scores": {"grounding": 4, "specificity": 5, "judge_readiness": 4, "speed": 3},
        "findings": ["Output named the actual slide and gave concrete design risks."],
    }

    first = mod.write_demo_case_eval_record(**kwargs)
    second = mod.write_demo_case_eval_record(**kwargs)

    assert first.path.is_file()
    assert second.path.is_file()
    assert first.path != second.path

    first_payload = json.loads(first.path.read_text(encoding="utf-8"))
    second_payload = json.loads(second.path.read_text(encoding="utf-8"))
    assert first_payload["run_id"] != second_payload["run_id"]


def test_write_demo_case_eval_record_rejects_symlinked_demo_runs_root(
    monkeypatch, tmp_path: Path
) -> None:
    from skills.evals.scripts import demo_case_records as mod

    docs = tmp_path / "docs"
    outside = tmp_path / "outside"
    outside.mkdir()
    runs_parent = docs / "_augur" / "evals"
    runs_parent.mkdir(parents=True)
    try:
        (runs_parent / "demo-runs").symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")
    monkeypatch.setattr(mod, "get_documents_dir", lambda: docs)
    monkeypatch.setattr(
        mod,
        "get_documents_machine_dir",
        lambda name: docs / "_augur" / name,
    )

    with pytest.raises(ValueError):
        mod.write_demo_case_eval_record(
            case_id="deck-slide-critique",
            evidence_path=Path("/vault/notes/demo/evidence/deck.md"),
            source_path=Path("C:/Demo/Augur Demo.pptx"),
            scores={"grounding": 4, "specificity": 5, "judge_readiness": 4, "speed": 3},
            findings=["Output named the actual slide and gave concrete design risks."],
        )

    assert not list(outside.iterdir())
