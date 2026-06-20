from __future__ import annotations

import os
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.lib.ingest.note_index_refresh import NoteBrowseIndexRefresh


def _extracted(
    *,
    title: str = "Invoice",
    markdown: str = "Invoice 1042\nAmount due 1200\n",
    needs_llm: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        success=True,
        markdown=markdown,
        title=title,
        tier_used=0,
        error=None,
        ocr_applied=False,
        needs_llm=needs_llm,
    )


def _mark_stable(path: Path) -> None:
    stable_time = time.time() - 10
    os.utime(path, (stable_time, stable_time))


@pytest.fixture(autouse=True)
def _isolate_runtime_queue(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AUGUR_STATE", str(tmp_path / "runtime-state"))


def _registry_with_project_and_team(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    """Build a brains registry with personal, project, and packets-only team brains."""
    from src.lib.brain_manifest import (
        BrainManifest,
        ensure_brain_skeleton,
        write_brain_manifest,
    )
    from src.lib.brain_registry_io import save_registry
    from src.lib.brain_registry_models import (
        Brain,
        BrainRegistry,
        BrainType,
        GitArrangement,
        GitConfig,
    )

    personal_root = tmp_path / "personal"
    team_root = tmp_path / "team"
    project = tmp_path / "repo"
    project_brain = project / "project-brain"
    ensure_brain_skeleton(project_brain)
    write_brain_manifest(
        project_brain,
        BrainManifest(
            schema_version=1,
            id="project-repo",
            type=BrainType.PROJECT,
            root=str(project_brain),
            attached_project=str(project),
        ),
    )
    registry_path = tmp_path / "brains.yaml"
    save_registry(
        BrainRegistry(
            version=1,
            brains={
                "personal": Brain(
                    id="personal",
                    type=BrainType.PERSONAL,
                    data_root=personal_root,
                    git=GitConfig(arrangement=GitArrangement.UNTRACKED),
                ),
                "project-repo": Brain(
                    id="project-repo",
                    type=BrainType.PROJECT,
                    data_root=project_brain,
                    git=GitConfig(
                        arrangement=GitArrangement.BUNDLED, host_repo=project
                    ),
                    auto_activate_cwd_under=(project,),
                ),
                "team-core": Brain(
                    id="team-core",
                    type=BrainType.TEAM,
                    data_root=team_root,
                    git=GitConfig(arrangement=GitArrangement.UNTRACKED),
                    write_policy="packets_only",
                ),
            },
        ),
        registry_path,
    )
    return registry_path, personal_root, project_brain, team_root


def test_consume_routes_to_explicit_project_brain(monkeypatch, tmp_path: Path) -> None:
    from src.lib.frontmatter_utils import parse_frontmatter

    from src.lib.ingest import inbox_consume
    from src.lib.ingest.inbox_store import InboxStore

    registry_path, _personal_root, project_brain, _team_root = (
        _registry_with_project_and_team(tmp_path)
    )

    inbox = tmp_path / "Desktop"
    inbox.mkdir()
    (inbox / "invoice.txt").write_text("Invoice 1042\nAmount due 1200\n", encoding="utf-8")
    _mark_stable(inbox / "invoice.txt")
    store = InboxStore(tmp_path / "state")
    folder = store.add_folder(name="Desktop", path=inbox)
    refresh_calls: list[Path] = []

    # Routing must bypass the personal vault entirely.
    def _fail_vault_dir() -> Path:
        raise AssertionError("get_vault_dir should not be used when routing is explicit")

    monkeypatch.setattr(inbox_consume, "get_vault_dir", _fail_vault_dir)
    monkeypatch.setattr(
        inbox_consume,
        "refresh_notes_browse_index",
        lambda **kwargs: (
            refresh_calls.append(kwargs["vault_dir"])
            or NoteBrowseIndexRefresh(success=True, count=1)
        ),
    )
    monkeypatch.setattr(
        inbox_consume,
        "get_extraction_policy",
        lambda: {
            "airplane_mode_enabled": True,
            "cloud_escalation_allowed": False,
            "local_agent_escalation_allowed": True,
        },
    )

    record = inbox_consume.consume_folder(
        store=store,
        folder_id=folder.id,
        to="project-repo",
        registry_path=registry_path,
    )

    # ADR-771 complete: the write target is the brain root; card writers
    # append knowledge/notes themselves.
    expected_vault = project_brain
    assert record.status == "success"
    assert refresh_calls == [expected_vault]
    card_path = Path(record.file_results[0].source_card_path)
    assert card_path.exists()
    assert card_path.parent == expected_vault / "knowledge" / "notes"
    metadata, _ = parse_frontmatter(card_path)
    assert metadata["x-augur-note-type"] == "file"


def test_consume_packet_only_brain_is_rejected(monkeypatch, tmp_path: Path) -> None:
    from src.lib.ingest import inbox_consume
    from src.lib.ingest.inbox_store import InboxStore

    registry_path, _personal_root, _project_brain, _team_root = (
        _registry_with_project_and_team(tmp_path)
    )

    inbox = tmp_path / "Desktop"
    inbox.mkdir()
    (inbox / "invoice.txt").write_text("Invoice\n", encoding="utf-8")
    _mark_stable(inbox / "invoice.txt")
    store = InboxStore(tmp_path / "state")
    folder = store.add_folder(name="Desktop", path=inbox)

    monkeypatch.setattr(
        inbox_consume,
        "get_extraction_policy",
        lambda: {
            "airplane_mode_enabled": True,
            "cloud_escalation_allowed": False,
            "local_agent_escalation_allowed": True,
        },
    )

    with pytest.raises(ValueError, match="packet"):
        inbox_consume.consume_folder(
            store=store,
            folder_id=folder.id,
            to="team-core",
            registry_path=registry_path,
        )


def test_consume_text_file_writes_card_and_run(monkeypatch, tmp_path: Path) -> None:
    from src.lib.frontmatter_utils import parse_frontmatter

    from src.lib.ingest import inbox_consume
    from src.lib.ingest.inbox_store import InboxStore

    inbox = tmp_path / "Desktop"
    inbox.mkdir()
    (inbox / "invoice.txt").write_text(
        "Invoice 1042\nAmount due 1200\n",
        encoding="utf-8",
    )
    _mark_stable(inbox / "invoice.txt")
    vault = tmp_path / "vault"
    store = InboxStore(tmp_path / "state")
    folder = store.add_folder(name="Desktop", path=inbox)
    refresh_calls: list[Path] = []

    monkeypatch.setattr(inbox_consume, "get_vault_dir", lambda: vault)

    def refresh_notes_browse_index(*, vault_dir):
        assert vault_dir == vault
        refresh_calls.append(vault_dir)
        return NoteBrowseIndexRefresh(success=True, count=1)

    monkeypatch.setattr(
        inbox_consume,
        "refresh_notes_browse_index",
        refresh_notes_browse_index,
    )
    monkeypatch.setattr(
        inbox_consume,
        "get_extraction_policy",
        lambda: {
            "airplane_mode_enabled": True,
            "cloud_escalation_allowed": False,
            "local_agent_escalation_allowed": True,
        },
    )

    record = inbox_consume.consume_folder(store=store, folder_id=folder.id)

    assert record.status == "success"
    assert refresh_calls == [vault]
    assert record.cloud_calls == 0
    assert record.files_indexed == 1
    card_path = Path(record.file_results[0].source_card_path)
    assert card_path.exists()
    assert card_path.parent == vault / "knowledge" / "notes"
    metadata, _ = parse_frontmatter(card_path)
    assert metadata["x-augur-note-type"] == "file"
    assert "invoice" in record.file_results[0].renamed_to


def test_consume_recently_modified_real_file_needs_review_without_extracting(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from src.lib.ingest import inbox_consume
    from src.lib.ingest.inbox_store import InboxStore

    inbox = tmp_path / "Desktop"
    inbox.mkdir()
    source = inbox / "new-invoice.txt"
    source.write_text("Invoice still being written\n", encoding="utf-8")
    store = InboxStore(tmp_path / "state")
    folder = store.add_folder(name="Desktop", path=inbox)

    monkeypatch.setattr(inbox_consume, "get_vault_dir", lambda: tmp_path / "vault")
    monkeypatch.setattr(
        inbox_consume,
        "extract",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("extract called")),
    )
    monkeypatch.setattr(
        inbox_consume,
        "get_extraction_policy",
        lambda: {
            "airplane_mode_enabled": True,
            "cloud_escalation_allowed": False,
            "local_agent_escalation_allowed": True,
        },
    )

    record = inbox_consume.consume_folder(store=store, folder_id=folder.id)

    assert record.status == "partial_success"
    assert record.files_needing_review == 1
    assert record.files_moved == 0
    assert record.file_results[0].status == "needs_review"
    assert "still changing" in record.file_results[0].review_reason
    assert source.exists()


def test_consume_missing_folder_records_failed_run(monkeypatch, tmp_path: Path) -> None:
    from src.lib.ingest import inbox_consume
    from src.lib.ingest.inbox_store import InboxStore

    store = InboxStore(tmp_path / "state")
    folder = store.add_folder(name="Missing", path=tmp_path / "missing")

    monkeypatch.setattr(inbox_consume, "get_vault_dir", lambda: tmp_path / "vault")
    monkeypatch.setattr(
        inbox_consume,
        "get_extraction_policy",
        lambda: {
            "airplane_mode_enabled": True,
            "cloud_escalation_allowed": False,
            "local_agent_escalation_allowed": True,
        },
    )

    record = inbox_consume.consume_folder(store=store, folder_id=folder.id)

    assert record.status == "failed"
    assert record.files_failed == 1
    assert record.file_results[0].status == "failed"
    assert "scan failed" in record.file_results[0].error.lower()
    assert store.list_runs(folder.id)[0].id == record.id


def test_consume_unstable_file_needs_review_without_extracting(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from src.lib.ingest import inbox_consume
    from src.lib.ingest.inbox_scan import ScanItem, ScanResult
    from src.lib.ingest.inbox_store import InboxStore

    inbox = tmp_path / "Desktop"
    inbox.mkdir()
    source = inbox / "active-download.txt"
    source.write_text("still changing", encoding="utf-8")
    store = InboxStore(tmp_path / "state")
    folder = store.add_folder(name="Desktop", path=inbox)

    monkeypatch.setattr(inbox_consume, "get_vault_dir", lambda: tmp_path / "vault")
    monkeypatch.setattr(
        inbox_consume,
        "scan_folder",
        lambda path, **kwargs: ScanResult(
            path=str(inbox),
            items=[
                ScanItem(
                    path=str(source),
                    name=source.name,
                    suffix=source.suffix,
                    candidate_type="document",
                    stable=False,
                )
            ],
        ),
    )
    monkeypatch.setattr(
        inbox_consume,
        "extract",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("extract called")),
    )
    monkeypatch.setattr(
        inbox_consume,
        "get_extraction_policy",
        lambda: {
            "airplane_mode_enabled": True,
            "cloud_escalation_allowed": False,
            "local_agent_escalation_allowed": True,
        },
    )

    record = inbox_consume.consume_folder(store=store, folder_id=folder.id)

    assert record.status == "partial_success"
    assert record.files_needing_review == 1
    assert record.file_results[0].status == "needs_review"
    assert "still changing" in record.file_results[0].review_reason
    assert source.exists()


def test_consume_destination_collision_uses_unique_final_filename(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from src.lib.ingest import inbox_consume
    from src.lib.ingest.inbox_store import InboxStore

    inbox = tmp_path / "Desktop"
    inbox.mkdir()
    (inbox / "first.txt").write_text("Invoice\n", encoding="utf-8")
    (inbox / "second.txt").write_text("Invoice\n", encoding="utf-8")
    _mark_stable(inbox / "first.txt")
    _mark_stable(inbox / "second.txt")
    vault = tmp_path / "vault"
    store = InboxStore(tmp_path / "state")
    folder = store.add_folder(name="Desktop", path=inbox)
    refresh_calls: list[Path] = []

    monkeypatch.setattr(inbox_consume, "get_vault_dir", lambda: vault)
    monkeypatch.setattr(inbox_consume, "extract", lambda *args, **kwargs: _extracted())
    monkeypatch.setattr(
        inbox_consume,
        "refresh_notes_browse_index",
        lambda **kwargs: (
            refresh_calls.append(kwargs["vault_dir"])
            or NoteBrowseIndexRefresh(success=True, count=1)
        ),
    )
    monkeypatch.setattr(
        inbox_consume,
        "get_extraction_policy",
        lambda: {
            "airplane_mode_enabled": True,
            "cloud_escalation_allowed": False,
            "local_agent_escalation_allowed": True,
        },
    )

    record = inbox_consume.consume_folder(store=store, folder_id=folder.id)

    final_names = [Path(result.final_path).name for result in record.file_results]
    assert record.status == "success"
    assert refresh_calls == [vault]
    assert len(final_names) == len(set(final_names))
    assert any(name.endswith("-2.txt") for name in final_names)
    assert [result.renamed_to for result in record.file_results] == final_names
    assert all(Path(result.final_path).exists() for result in record.file_results)


def test_consume_needs_llm_extraction_needs_review_without_moving(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from src.lib.ingest import inbox_consume
    from src.lib.ingest.inbox_store import InboxStore

    inbox = tmp_path / "Desktop"
    inbox.mkdir()
    source = inbox / "scan.pdf"
    source.write_bytes(b"%PDF-1.7\n")
    _mark_stable(source)
    store = InboxStore(tmp_path / "state")
    folder = store.add_folder(name="Desktop", path=inbox)

    monkeypatch.setattr(inbox_consume, "get_vault_dir", lambda: tmp_path / "vault")
    monkeypatch.setattr(
        inbox_consume,
        "extract",
        lambda *args, **kwargs: _extracted(
            title="Scan",
            markdown="[Image: page requires OCR]",
            needs_llm=True,
        ),
    )
    monkeypatch.setattr(
        inbox_consume,
        "write_source_card",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("card called")),
    )
    monkeypatch.setattr(
        inbox_consume.shutil,
        "move",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("move called")),
    )
    monkeypatch.setattr(
        inbox_consume,
        "get_extraction_policy",
        lambda: {
            "airplane_mode_enabled": True,
            "cloud_escalation_allowed": False,
            "local_agent_escalation_allowed": True,
        },
    )

    record = inbox_consume.consume_folder(store=store, folder_id=folder.id)

    assert record.status == "partial_success"
    assert record.files_moved == 0
    assert record.files_indexed == 0
    assert record.files_needing_review == 1
    assert record.local_agent_calls == 1
    assert record.file_results[0].status == "needs_review"
    assert record.file_results[0].local_agent_used is True
    assert "local agent" in record.file_results[0].review_reason
    assert source.exists()


def test_consume_destination_setup_failure_is_recorded(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from src.lib.ingest import inbox_consume
    from src.lib.ingest.inbox_store import InboxStore

    inbox = tmp_path / "Desktop"
    inbox.mkdir()
    source = inbox / "invoice.txt"
    source.write_text("Invoice\n", encoding="utf-8")
    _mark_stable(source)
    store = InboxStore(tmp_path / "state")
    folder = store.add_folder(name="Desktop", path=inbox)

    monkeypatch.setattr(inbox_consume, "get_vault_dir", lambda: tmp_path / "vault")
    monkeypatch.setattr(inbox_consume, "extract", lambda *args, **kwargs: _extracted())
    monkeypatch.setattr(
        inbox_consume,
        "_unique_destination_path",
        lambda target: (_ for _ in ()).throw(RuntimeError("destination boom")),
    )
    monkeypatch.setattr(
        inbox_consume,
        "get_extraction_policy",
        lambda: {
            "airplane_mode_enabled": True,
            "cloud_escalation_allowed": False,
            "local_agent_escalation_allowed": True,
        },
    )

    record = inbox_consume.consume_folder(store=store, folder_id=folder.id)

    assert record.status == "failed"
    assert record.files_moved == 0
    assert record.files_failed == 1
    assert record.file_results[0].status == "failed"
    assert "destination boom" in record.file_results[0].error
    assert source.exists()


def test_consume_card_write_failure_is_captured_and_run_saved(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from src.lib.ingest import inbox_consume
    from src.lib.ingest.inbox_store import InboxStore

    inbox = tmp_path / "Desktop"
    inbox.mkdir()
    source = inbox / "invoice.txt"
    source.write_text("Invoice\n", encoding="utf-8")
    _mark_stable(source)
    store = InboxStore(tmp_path / "state")
    folder = store.add_folder(name="Desktop", path=inbox)

    monkeypatch.setattr(inbox_consume, "get_vault_dir", lambda: tmp_path / "vault")
    monkeypatch.setattr(inbox_consume, "extract", lambda *args, **kwargs: _extracted())
    monkeypatch.setattr(
        inbox_consume,
        "write_source_card",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("card boom")),
    )
    monkeypatch.setattr(
        inbox_consume,
        "get_extraction_policy",
        lambda: {
            "airplane_mode_enabled": True,
            "cloud_escalation_allowed": False,
            "local_agent_escalation_allowed": True,
        },
    )

    record = inbox_consume.consume_folder(store=store, folder_id=folder.id)

    assert record.status == "failed"
    assert record.files_failed == 1
    assert record.file_results[0].status == "failed"
    assert "card boom" in record.file_results[0].error
    assert store.list_runs(folder.id)[0].id == record.id


def test_consume_move_failure_does_not_increment_files_moved(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from src.lib.ingest import inbox_consume
    from src.lib.ingest.inbox_store import InboxStore

    inbox = tmp_path / "Desktop"
    inbox.mkdir()
    source = inbox / "invoice.txt"
    source.write_text("Invoice\n", encoding="utf-8")
    _mark_stable(source)
    store = InboxStore(tmp_path / "state")
    folder = store.add_folder(name="Desktop", path=inbox)

    monkeypatch.setattr(inbox_consume, "get_vault_dir", lambda: tmp_path / "vault")
    monkeypatch.setattr(inbox_consume, "extract", lambda *args, **kwargs: _extracted())
    monkeypatch.setattr(
        inbox_consume.shutil,
        "move",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("move boom")),
    )
    monkeypatch.setattr(
        inbox_consume,
        "get_extraction_policy",
        lambda: {
            "airplane_mode_enabled": True,
            "cloud_escalation_allowed": False,
            "local_agent_escalation_allowed": True,
        },
    )

    record = inbox_consume.consume_folder(store=store, folder_id=folder.id)

    assert record.status == "failed"
    assert record.files_moved == 0
    assert record.files_failed == 1
    assert record.file_results[0].status == "failed"
    assert record.file_results[0].final_path
    assert "move boom" in record.file_results[0].error


def test_consume_source_missing_before_move_fails_without_moved_count(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from src.lib.ingest import inbox_consume
    from src.lib.ingest.inbox_store import InboxStore

    inbox = tmp_path / "Desktop"
    inbox.mkdir()
    source = inbox / "invoice.txt"
    source.write_text("Invoice\n", encoding="utf-8")
    _mark_stable(source)
    store = InboxStore(tmp_path / "state")
    folder = store.add_folder(name="Desktop", path=inbox)

    def extract_and_remove(*args, **kwargs):
        source.unlink()
        return _extracted()

    monkeypatch.setattr(inbox_consume, "get_vault_dir", lambda: tmp_path / "vault")
    monkeypatch.setattr(inbox_consume, "extract", extract_and_remove)
    monkeypatch.setattr(
        inbox_consume,
        "get_extraction_policy",
        lambda: {
            "airplane_mode_enabled": True,
            "cloud_escalation_allowed": False,
            "local_agent_escalation_allowed": True,
        },
    )

    record = inbox_consume.consume_folder(store=store, folder_id=folder.id)

    assert record.status == "failed"
    assert record.files_moved == 0
    assert record.files_failed == 1
    assert record.file_results[0].status == "failed"
    assert "disappeared" in record.file_results[0].error


def test_consume_move_success_then_card_write_failure_counts_moved(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from src.lib.ingest import inbox_consume
    from src.lib.ingest.inbox_store import InboxStore

    inbox = tmp_path / "Desktop"
    inbox.mkdir()
    source = inbox / "invoice.txt"
    source.write_text("Invoice\n", encoding="utf-8")
    _mark_stable(source)
    store = InboxStore(tmp_path / "state")
    folder = store.add_folder(name="Desktop", path=inbox)

    monkeypatch.setattr(inbox_consume, "get_vault_dir", lambda: tmp_path / "vault")
    monkeypatch.setattr(inbox_consume, "extract", lambda *args, **kwargs: _extracted())
    monkeypatch.setattr(
        inbox_consume,
        "write_source_card",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("card boom")),
    )
    monkeypatch.setattr(
        inbox_consume,
        "get_extraction_policy",
        lambda: {
            "airplane_mode_enabled": True,
            "cloud_escalation_allowed": False,
            "local_agent_escalation_allowed": True,
        },
    )

    record = inbox_consume.consume_folder(store=store, folder_id=folder.id)

    assert record.status == "failed"
    assert record.files_moved == 1
    assert record.files_failed == 1
    assert record.file_results[0].status == "failed"
    assert Path(record.file_results[0].final_path).exists()
    assert "card boom" in record.file_results[0].error


def test_consume_reindex_failure_preserves_file_evidence(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from src.lib.ingest import inbox_consume
    from src.lib.ingest.inbox_store import InboxStore

    inbox = tmp_path / "Desktop"
    inbox.mkdir()
    (inbox / "invoice.txt").write_text("Invoice\n", encoding="utf-8")
    _mark_stable(inbox / "invoice.txt")
    vault = tmp_path / "vault"
    store = InboxStore(tmp_path / "state")
    folder = store.add_folder(name="Desktop", path=inbox)

    monkeypatch.setattr(inbox_consume, "get_vault_dir", lambda: vault)
    monkeypatch.setattr(inbox_consume, "extract", lambda *args, **kwargs: _extracted())

    def refresh_notes_browse_index(*, vault_dir):
        assert vault_dir == vault
        return NoteBrowseIndexRefresh(success=False, error="index boom")

    monkeypatch.setattr(
        inbox_consume,
        "refresh_notes_browse_index",
        refresh_notes_browse_index,
    )
    monkeypatch.setattr(
        inbox_consume,
        "get_extraction_policy",
        lambda: {
            "airplane_mode_enabled": True,
            "cloud_escalation_allowed": False,
            "local_agent_escalation_allowed": True,
        },
    )

    record = inbox_consume.consume_folder(store=store, folder_id=folder.id)

    assert record.status == "partial_success"
    assert record.files_indexed == 0
    assert record.files_needing_review == 1
    assert record.file_results[0].status == "needs_review"
    assert record.file_results[0].rag_indexed is False
    assert Path(record.file_results[0].source_card_path).exists()
    assert "index boom" in record.file_results[0].review_reason


def test_consume_cloud_allowed_policy_still_records_no_cloud_use(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from src.lib.ingest import inbox_consume
    from src.lib.ingest.inbox_store import InboxStore

    inbox = tmp_path / "Desktop"
    inbox.mkdir()
    (inbox / "invoice.txt").write_text("Invoice\n", encoding="utf-8")
    _mark_stable(inbox / "invoice.txt")
    store = InboxStore(tmp_path / "state")
    folder = store.add_folder(name="Desktop", path=inbox)
    vault = tmp_path / "vault"
    refresh_calls: list[Path] = []

    monkeypatch.setattr(inbox_consume, "get_vault_dir", lambda: vault)
    monkeypatch.setattr(inbox_consume, "extract", lambda *args, **kwargs: _extracted())
    monkeypatch.setattr(
        inbox_consume,
        "refresh_notes_browse_index",
        lambda **kwargs: (
            refresh_calls.append(kwargs["vault_dir"])
            or NoteBrowseIndexRefresh(success=True, count=1)
        ),
    )
    monkeypatch.setattr(
        inbox_consume,
        "get_extraction_policy",
        lambda: {
            "airplane_mode_enabled": False,
            "cloud_escalation_allowed": True,
            "local_agent_escalation_allowed": True,
        },
    )

    record = inbox_consume.consume_folder(store=store, folder_id=folder.id)

    assert record.status == "success"
    assert refresh_calls == [vault]
    assert record.cloud_calls == 0
    assert all(result.cloud_used is False for result in record.file_results)


def test_consume_writes_extracted_artifact_and_cloud_evidence(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from src.lib.extraction import ExtractionResult

    from src.lib.ingest import inbox_consume
    from src.lib.ingest.inbox_store import InboxStore

    inbox = tmp_path / "Desktop"
    inbox.mkdir()
    source = inbox / "demo-hard-photo.png"
    source.write_bytes(b"image")
    _mark_stable(source)
    vault = tmp_path / "vault"
    store = InboxStore(tmp_path / "state")
    folder = store.add_folder(name="Desktop", path=inbox)
    refresh_calls: list[Path] = []

    monkeypatch.setattr(inbox_consume, "get_vault_dir", lambda: vault)
    monkeypatch.setattr(
        inbox_consume,
        "refresh_notes_browse_index",
        lambda **kwargs: (
            refresh_calls.append(kwargs["vault_dir"])
            or NoteBrowseIndexRefresh(success=True, count=1)
        ),
    )
    monkeypatch.setattr(
        inbox_consume,
        "get_extraction_policy",
        lambda: {
            "airplane_mode_enabled": False,
            "cloud_escalation_allowed": True,
            "local_agent_escalation_allowed": True,
        },
    )

    def fake_extract(path, max_tier=1, **kwargs):
        assert kwargs["allow_cloud"] is True
        return ExtractionResult(
            success=True,
            markdown="Cloud OCR text invoice amount 1842.25",
            title="Cloud invoice",
            tier_used=1,
            format="png",
            size_bytes=5,
            extraction_time=0.1,
            ocr_applied=True,
            cloud_used=True,
            escalation_reason="local OCR and local vision did not produce usable text",
            cloud_provider="FakeVisionClient",
            cloud_model="gpt-vision-demo",
            hardware_backend="cloud-vision",
        )

    monkeypatch.setattr(inbox_consume, "extract", fake_extract)

    record = inbox_consume.consume_folder(store=store, folder_id=folder.id)

    result = record.file_results[0]
    assert refresh_calls == [vault]
    assert record.cloud_calls == 1
    assert result.cloud_used is True
    assert result.escalation_reason == "local OCR and local vision did not produce usable text"
    assert result.cloud_provider == "FakeVisionClient"
    assert Path(result.extracted_path).exists()
    assert "Cloud OCR text" in Path(result.extracted_path).read_text(encoding="utf-8")
    assert "Cloud OCR text" in Path(result.source_card_path).read_text(encoding="utf-8")
