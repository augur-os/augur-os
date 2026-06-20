from __future__ import annotations

from pathlib import Path


def _wiki_status_fixture() -> dict:
    return {
        "verdict": "healthy",
        "healthy": True,
        "structure": {"pages": 77, "missing_links": [], "orphan_pages": []},
        "compiler": {
            "sources_total": 12,
            "sources_compiled_with_concepts": 9,
            "sources_pending_or_changed": 0,
            "current": True,
        },
        "coverage": {"concept_coverage_ratio": 0.75, "top_uncovered_source_families": []},
        "index": {"indexed": True, "wiki_rag_entries": 76},
        "batches": {"batch_count": 2, "needs_update": False},
        "compounding_health": {
            "concept_page_count": 18,
            "average_sources_per_concept_page": 4.5,
            "thin_page_count": 3,
            "target_sources_per_page": "10-15",
        },
        "actions": [],
    }


def test_brain_insights_returns_latest_runs(tmp_path: Path) -> None:
    from skills.ingest.scripts.brain_insights import build_brain_insights
    from src.lib.ingest.inbox_models import InboxRunRecord
    from src.lib.ingest.inbox_store import InboxStore

    store = InboxStore(tmp_path / "state")
    folder = store.add_folder(name="Desktop", path=tmp_path / "Desktop")
    store.save_run(
        InboxRunRecord(
            id="run_1",
            folder_id=folder.id,
            started_at="2026-05-07T12:00:00+00:00",
            completed_at="2026-05-07T12:01:00+00:00",
            status="success",
            airplane_mode=True,
            files_seen=1,
            files_moved=1,
            files_indexed=1,
        )
    )

    payload = build_brain_insights(store=store, wiki_status_builder=_wiki_status_fixture)

    assert payload["success"] is True
    assert payload["latest_runs"][0]["id"] == "run_1"
    assert payload["wiki_status"]["actions"][0]["tool"] == "wiki-update"


def test_brain_insights_includes_demo_rag_proof(monkeypatch, tmp_path: Path) -> None:
    from skills.ingest.scripts import brain_insights
    from src.lib.ingest.inbox_models import InboxFileResult, InboxRunRecord
    from src.lib.ingest.inbox_store import InboxStore

    monkeypatch.setattr(
        brain_insights,
        "verify_demo_rag",
        lambda query, expected_files=None: {
            "query": query,
            "hit_count": 1,
            "hits": [
                {
                    "file": "vault/sources/files/demo-meeting.md",
                    "line": "7",
                    "content": "investor demo meeting",
                    "scope": "rag",
                }
            ],
            "ready": True,
            "expected_files": expected_files,
        },
        raising=False,
    )

    store = InboxStore(tmp_path / "state")
    folder = store.add_folder(name="Desktop", path=tmp_path / "Desktop")
    store.save_run(
        InboxRunRecord(
            id="run_1",
            folder_id=folder.id,
            started_at="2026-05-07T12:00:00+00:00",
            completed_at="2026-05-07T12:01:00+00:00",
            status="success",
            airplane_mode=True,
            files_seen=1,
            files_moved=1,
            files_indexed=1,
            file_results=[
                InboxFileResult(
                    source_path="C:/Desktop/demo-meeting.mp3",
                    final_path="C:/Vault/meetings/demo-meeting.mp3",
                    source_card_path="C:/Vault/sources/files/demo-meeting.md",
                    extracted_path="C:/Vault/sources/extracted/demo-meeting.transcript.md",
                    content_type="audio",
                    extraction_method="faster-whisper",
                    hardware_backend="local",
                    confidence="high",
                    route="meetings",
                    renamed_to="demo-meeting.mp3",
                    rag_indexed=True,
                    status="success",
                )
            ],
        )
    )

    payload = brain_insights.build_brain_insights(store=store, wiki_status_builder=_wiki_status_fixture)
    index = payload["wiki_status"]["index"]

    assert index["wiki_rag_entries"] == 76
    assert index["demo_query"] == "investor demo meeting"
    assert index["demo_hit_count"] == 1
    assert index["demo_ready"] is True
    assert index["demo_hits"] == [
        {
            "file": "vault/sources/files/demo-meeting.md",
            "line": "7",
            "content": "investor demo meeting",
            "scope": "rag",
        }
    ]


def test_brain_insights_without_runs_reports_demo_rag_not_ready(
    tmp_path: Path,
) -> None:
    from skills.ingest.scripts.brain_insights import build_brain_insights
    from src.lib.ingest.inbox_store import InboxStore

    payload = build_brain_insights(store=InboxStore(tmp_path / "state"), wiki_status_builder=_wiki_status_fixture)
    index = payload["wiki_status"]["index"]

    assert payload["wiki_status"]["structure"]["pages"] == 77
    assert payload["wiki_status"]["compounding_health"]["concept_page_count"] == 18
    assert index["demo_query"] == "investor demo meeting"
    assert index["demo_hit_count"] == 0
    assert index["demo_ready"] is False
    assert index["demo_hits"] == []


def test_brain_insights_latest_runs_drop_file_results(tmp_path: Path) -> None:
    from skills.ingest.scripts.brain_insights import build_brain_insights
    from src.lib.ingest.inbox_models import InboxFileResult, InboxRunRecord
    from src.lib.ingest.inbox_store import InboxStore

    store = InboxStore(tmp_path / "state")
    folder = store.add_folder(name="Desktop", path=tmp_path / "Desktop")
    store.save_run(
        InboxRunRecord(
            id="run_with_files",
            folder_id=folder.id,
            started_at="2026-05-07T12:00:00+00:00",
            completed_at="2026-05-07T12:01:00+00:00",
            status="success",
            airplane_mode=True,
            files_seen=1,
            files_moved=1,
            files_indexed=1,
            file_results=[
                InboxFileResult(
                    source_path="C:/Desktop/report.pdf",
                    final_path="C:/Vault/sources/report.md",
                    source_card_path="sources/report.md",
                    content_type="application/pdf",
                    extraction_method="local",
                    hardware_backend="cpu",
                    confidence="high",
                    route="sources/web",
                    renamed_to="report.pdf",
                    rag_indexed=True,
                    status="indexed",
                )
            ],
        )
    )

    payload = build_brain_insights(store=store, wiki_status_builder=_wiki_status_fixture)

    assert payload["latest_runs"][0]["files_indexed"] == 1
    assert "insights" in payload["latest_runs"][0]
    assert "file_results" not in payload["latest_runs"][0]
