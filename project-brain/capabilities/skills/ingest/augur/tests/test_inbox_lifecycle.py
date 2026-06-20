from __future__ import annotations

from pathlib import Path


def test_archive_plan_archives_lower_versions_and_refuses_milestone(tmp_path: Path) -> None:
    from skills.ingest.scripts.inbox_lifecycle import plan_version_archives

    folder = tmp_path / "docs" / "venture-augur" / "office-hours"
    folder.mkdir(parents=True)
    (folder / "augur-office-hours-v21.pptx").write_bytes(b"v21")
    (folder / "augur-office-hours-v22.pptx").write_bytes(b"v22")
    (folder / "augur-office-hours-board-milestone.pptx").write_bytes(b"board")
    (folder / ".milestones.json").write_text(
        '[{"path": "augur-office-hours-board-milestone.pptx", "reason": "board milestone"}]',
        encoding="utf-8",
    )

    plan = plan_version_archives(
        docs_root=tmp_path / "docs",
        target_folder="venture-augur/office-hours",
        version_group="augur-office-hours",
        final_filename="augur-office-hours-v23.pptx",
    )

    assert [move.relative_path for move in plan.auto_archive] == [
        "venture-augur/office-hours/augur-office-hours-v21.pptx",
        "venture-augur/office-hours/augur-office-hours-v22.pptx",
    ]
    assert [move.relative_path for move in plan.refused] == [
        "venture-augur/office-hours/augur-office-hours-board-milestone.pptx",
    ]
    assert plan.refused[0].refusal_category == "milestone_pinned"


def test_archive_plan_asks_on_same_version_ambiguity(tmp_path: Path) -> None:
    from skills.ingest.scripts.inbox_lifecycle import plan_version_archives

    folder = tmp_path / "docs" / "deck"
    folder.mkdir(parents=True)
    (folder / "deck-v2-final.pptx").write_bytes(b"v2")

    plan = plan_version_archives(
        docs_root=tmp_path / "docs",
        target_folder="deck",
        version_group="deck",
        final_filename="deck-v2.pptx",
    )

    assert plan.auto_archive == []
    assert [move.relative_path for move in plan.ask] == ["deck/deck-v2-final.pptx"]
    assert plan.ask[0].refusal_category == "same_version_ambiguous"


def test_archive_plan_refuses_target_folder_outside_docs_root(tmp_path: Path) -> None:
    from skills.ingest.scripts.inbox_lifecycle import plan_version_archives

    docs = tmp_path / "docs"
    (tmp_path / "outside").mkdir()

    plan = plan_version_archives(
        docs_root=docs,
        target_folder="../outside",
        version_group="deck",
        final_filename="deck-v2.pptx",
    )

    assert plan.auto_archive == []
    assert plan.ask == []
    assert plan.refused[0].refusal_category == "outside_docs_root"


def test_apply_archive_plan_refuses_cross_root(monkeypatch, tmp_path: Path) -> None:
    from skills.ingest.scripts.inbox_lifecycle import apply_archive_plan, plan_version_archives

    docs = tmp_path / "docs"
    folder = docs / "deck"
    folder.mkdir(parents=True)
    (folder / "deck-v1.pptx").write_bytes(b"v1")
    plan = plan_version_archives(
        docs_root=docs,
        target_folder="deck",
        version_group="deck",
        final_filename="deck-v2.pptx",
    )
    calls: list[Path] = []

    def fake_apply(**kwargs):
        calls.append(kwargs["store_root"])
        return {"moves": [{"from": "deck/deck-v1.pptx", "to": "deck/.archive/deck-v1.pptx", "status": "succeeded"}]}

    monkeypatch.setattr("skills.ingest.scripts.inbox_lifecycle.hygiene_apply", fake_apply)

    result = apply_archive_plan(docs_root=docs, plan=plan, dry_run=False)

    assert calls == [docs.resolve()]
    assert result["moves"][0]["status"] == "succeeded"
