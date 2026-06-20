from __future__ import annotations

from pathlib import Path


def test_store_adds_folder_and_persists_counts(tmp_path: Path) -> None:
    from src.lib.ingest.inbox_store import InboxStore

    folder_path = tmp_path / "Desktop"
    folder_path.mkdir()
    store = InboxStore(tmp_path / "state")

    folder = store.add_folder(name="Desktop", path=folder_path)
    saved = store.update_folder_counts(
        folder.id,
        {
            "new_files": 3,
            "document_candidates": 2,
            "trash_candidates": 1,
            "failed": 0,
        },
    )

    reloaded = InboxStore(tmp_path / "state")
    folders = reloaded.list_folders()

    assert saved.counts.new_files == 3
    assert len(folders) == 1
    assert folders[0].id == "desktop"
    assert folders[0].path == str(folder_path.resolve())


def test_store_records_run_history_and_detail(tmp_path: Path) -> None:
    from src.lib.ingest.inbox_models import InboxFileResult, InboxRunRecord
    from src.lib.ingest.inbox_store import InboxStore

    store = InboxStore(tmp_path / "state")
    folder = store.add_folder(name="Desktop", path=tmp_path / "Desktop")
    record = InboxRunRecord(
        id="run_1",
        folder_id=folder.id,
        started_at="2026-05-07T12:00:00+00:00",
        completed_at="2026-05-07T12:01:00+00:00",
        status="partial_success",
        airplane_mode=True,
        files_seen=1,
        files_moved=1,
        files_indexed=1,
        files_skipped=0,
        files_failed=0,
        files_needing_review=0,
        cloud_calls=0,
        local_agent_calls=1,
        wiki_update_marked=True,
        file_results=[
            InboxFileResult(
                source_path="C:/Users/example/Desktop/meeting.mp3",
                final_path="C:/Users/example/Projects/Au-vault/meetings/2026-05-07-meeting.mp3",
                source_card_path="C:/Users/example/Projects/Au-vault/sources/files/2026-05-07-meeting.md",
                content_type="audio",
                extraction_method="faster-whisper",
                hardware_backend="CPU",
                confidence="medium",
                route="meetings",
                renamed_to="2026-05-07-meeting.mp3",
                rag_indexed=True,
                status="success",
            )
        ],
    )

    store.save_run(record)

    assert store.list_runs()[0].id == "run_1"
    assert store.get_run("run_1").file_results[0].content_type == "audio"


def test_store_list_run_payloads_limits_before_hydrating_file_results(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from src.lib.ingest.inbox_models import InboxFileResult, InboxRunRecord
    from src.lib.ingest.inbox_store import InboxStore

    store = InboxStore(tmp_path / "state")
    folder = store.add_folder(name="Desktop", path=tmp_path / "Desktop")
    for run_id, started_at in (
        ("old_run", "2026-05-07T12:00:00+00:00"),
        ("new_run", "2026-05-07T12:05:00+00:00"),
    ):
        store.save_run(
            InboxRunRecord(
                id=run_id,
                folder_id=folder.id,
                started_at=started_at,
                completed_at=started_at,
                status="success",
                airplane_mode=True,
                file_results=[
                    InboxFileResult(
                        source_path=f"C:/Desktop/{run_id}-{index}.pdf",
                        final_path=f"C:/Vault/{run_id}-{index}.pdf",
                        source_card_path=f"sources/files/{run_id}-{index}.md",
                        content_type="application/pdf",
                        extraction_method="local",
                        hardware_backend="npu",
                        confidence="medium",
                        route="finance",
                        renamed_to=f"{run_id}-{index}.pdf",
                        rag_indexed=True,
                        status="success",
                    )
                    for index in range(12)
                ],
            )
        )

    hydrated: list[tuple[str, int]] = []
    original_run_from_dict = store._run_from_dict

    def tracking_run_from_dict(data):
        hydrated.append((data["id"], len(data.get("file_results", []))))
        return original_run_from_dict(data)

    monkeypatch.setattr(store, "_run_from_dict", tracking_run_from_dict)

    payloads = store.list_run_payloads(limit=1, file_results_limit=2)

    assert [payload["id"] for payload in payloads] == ["new_run"]
    assert len(payloads[0]["file_results"]) == 2
    assert hydrated == [("new_run", 2)]


def test_store_list_run_payloads_can_drop_file_results(tmp_path: Path) -> None:
    from src.lib.ingest.inbox_models import InboxFileResult, InboxRunRecord
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
            file_results=[
                InboxFileResult(
                    source_path="C:/Desktop/report.pdf",
                    final_path="C:/Vault/report.pdf",
                    source_card_path="sources/files/report.md",
                    content_type="application/pdf",
                    extraction_method="local",
                    hardware_backend="npu",
                    confidence="medium",
                    route="finance",
                    renamed_to="report.pdf",
                    rag_indexed=True,
                    status="success",
                )
            ],
        )
    )

    payloads = store.list_run_payloads(limit=1, include_file_results=False)

    assert payloads[0]["id"] == "run_1"
    assert "file_results" not in payloads[0]


def test_store_saves_unsafe_run_ids_inside_runs_dir(tmp_path: Path) -> None:
    from src.lib.ingest.inbox_models import InboxRunRecord
    from src.lib.ingest.inbox_store import InboxStore

    store = InboxStore(tmp_path / "state")
    folder = store.add_folder(name="Desktop", path=tmp_path / "Desktop")
    unsafe_id = "../2026-05-07T12:00:00+00:00\\desktop"
    record = InboxRunRecord(
        id=unsafe_id,
        folder_id=folder.id,
        started_at="2026-05-07T12:00:00+00:00",
        completed_at="2026-05-07T12:01:00+00:00",
        status="success",
        airplane_mode=False,
    )

    store.save_run(record)

    saved_files = list(store.runs_dir.glob("*.json"))
    assert len(saved_files) == 1
    assert saved_files[0].parent == store.runs_dir
    assert ":" not in saved_files[0].name
    assert store.get_run(unsafe_id).id == unsafe_id


def test_store_run_filenames_do_not_collide_by_case(tmp_path: Path) -> None:
    from src.lib.ingest.inbox_models import InboxRunRecord
    from src.lib.ingest.inbox_store import InboxStore

    store = InboxStore(tmp_path / "state")
    folder = store.add_folder(name="Desktop", path=tmp_path / "Desktop")

    store.save_run(
        InboxRunRecord(
            id="run",
            folder_id=folder.id,
            started_at="2026-05-07T12:00:00+00:00",
            completed_at="2026-05-07T12:01:00+00:00",
            status="success",
            airplane_mode=False,
        )
    )
    store.save_run(
        InboxRunRecord(
            id="RUN",
            folder_id=folder.id,
            started_at="2026-05-07T12:02:00+00:00",
            completed_at="2026-05-07T12:03:00+00:00",
            status="success",
            airplane_mode=False,
        )
    )

    assert len(list(store.runs_dir.glob("*.json"))) == 2
    assert store.get_run("run").id == "run"
    assert store.get_run("RUN").id == "RUN"
    assert [record.id for record in store.list_runs()] == ["RUN", "run"]


def test_store_run_filenames_are_bounded_for_long_safe_ids(tmp_path: Path) -> None:
    from src.lib.ingest.inbox_models import InboxRunRecord
    from src.lib.ingest.inbox_store import InboxStore

    store = InboxStore(tmp_path / "state")
    folder = store.add_folder(name="Desktop", path=tmp_path / "Desktop")
    long_id = "run_" + ("a" * 300)

    store.save_run(
        InboxRunRecord(
            id=long_id,
            folder_id=folder.id,
            started_at="2026-05-07T12:00:00+00:00",
            completed_at="2026-05-07T12:01:00+00:00",
            status="success",
            airplane_mode=False,
        )
    )

    saved_files = list(store.runs_dir.glob("*.json"))
    assert len(saved_files) == 1
    assert len(saved_files[0].name) < 80
    assert store.get_run(long_id).id == long_id


def test_store_write_replaces_json_without_temp_residue(tmp_path: Path) -> None:
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
            airplane_mode=False,
        )
    )
    store.save_run(
        InboxRunRecord(
            id="run_1",
            folder_id=folder.id,
            started_at="2026-05-07T12:00:00+00:00",
            completed_at="2026-05-07T12:02:00+00:00",
            status="partial_success",
            airplane_mode=False,
        )
    )

    assert store.get_run("run_1").status == "partial_success"
    assert list(store.runs_dir.glob("*.tmp")) == []


def test_store_skips_corrupt_run_files_in_history(tmp_path: Path) -> None:
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
            airplane_mode=False,
        )
    )
    store.runs_dir.mkdir(parents=True, exist_ok=True)
    (store.runs_dir / "corrupt.json").write_text("{not json", encoding="utf-8")

    assert [record.id for record in store.list_runs()] == ["run_1"]


def test_store_get_run_reports_corrupt_requested_run(tmp_path: Path) -> None:
    import pytest

    from src.lib.ingest.inbox_store import InboxStore

    store = InboxStore(tmp_path / "state")
    run_path = store._run_path("run_1")
    run_path.parent.mkdir(parents=True, exist_ok=True)
    run_path.write_text("{not json", encoding="utf-8")

    with pytest.raises(ValueError, match="Corrupt inbox run record: run_1"):
        store.get_run("run_1")


def test_store_generates_unique_folder_ids_for_duplicate_names(tmp_path: Path) -> None:
    from src.lib.ingest.inbox_store import InboxStore

    store = InboxStore(tmp_path / "state")

    first = store.add_folder(name="Desktop", path=tmp_path / "Desktop")
    second = store.add_folder(name="Desktop", path=tmp_path / "OtherDesktop")

    reloaded = InboxStore(tmp_path / "state")
    folders = reloaded.list_folders()

    assert first.id == "desktop"
    assert second.id == "desktop-2"
    assert [folder.id for folder in folders] == ["desktop", "desktop-2"]
    assert folders[0].path == str((tmp_path / "Desktop").resolve())
    assert folders[1].path == str((tmp_path / "OtherDesktop").resolve())
