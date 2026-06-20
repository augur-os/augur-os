from __future__ import annotations

from email.message import EmailMessage
from pathlib import Path

from src.lib.ingest.note_index_refresh import NoteBrowseIndexRefresh


def _write_eml(
    path: Path,
    subject: str = "Inbox article",
    *,
    with_attachment: bool = False,
) -> None:
    message = EmailMessage()
    message["From"] = "alice@example.com"
    message["To"] = "me@example.com"
    message["Subject"] = subject
    message.set_content("Read https://example.com/article")
    if with_attachment:
        message.add_attachment(
            b"Attachment body",
            maintype="text",
            subtype="plain",
            filename="brief.txt",
        )
    path.write_bytes(message.as_bytes())


def test_scan_email_drop_source_updates_counts_without_moving_files(tmp_path, monkeypatch) -> None:
    from skills.ingest.scripts.email_drop_consume import scan_email_drop_source
    from skills.ingest.scripts.email_drop_store import EmailDropStore

    drop = tmp_path / "mail"
    drop.mkdir()
    _write_eml(drop / "message.eml")
    (drop / "notes.txt").write_text("Saved body https://example.com/note", encoding="utf-8")
    store = EmailDropStore(tmp_path / "state")
    source = store.add_source("Mail Drop", drop)

    counts = scan_email_drop_source(store=store, source_id=source.id)

    assert counts.pending_files == 2
    assert counts.email_native == 1
    assert counts.degraded == 1
    assert counts.contained_messages == 2
    assert (drop / "message.eml").exists()
    assert store.get_source(source.id).last_scan_at is not None


def test_consume_email_drop_source_records_run_and_moves_successes(
    tmp_path,
    monkeypatch,
) -> None:
    from skills.ingest.scripts import email_drop_consume
    from skills.ingest.scripts.email_drop_consume import consume_email_drop_source
    from skills.ingest.scripts.email_drop_store import EmailDropStore

    drop = tmp_path / "mail"
    drop.mkdir()
    _write_eml(drop / "message.eml", with_attachment=True)
    store = EmailDropStore(tmp_path / "state")
    source = store.add_source("Mail Drop", drop)
    vault = tmp_path / "vault"
    stale_vault = tmp_path / "stale-vault"
    vault_calls = iter([vault, stale_vault])
    refresh_calls: list[Path] = []
    monkeypatch.setattr(email_drop_consume, "get_vault_dir", lambda: next(vault_calls))
    monkeypatch.setattr(email_drop_consume, "get_runtime_dir", lambda: tmp_path / "runtime")

    def refresh_notes_browse_index(*, vault_dir):
        refresh_calls.append(vault_dir)
        return NoteBrowseIndexRefresh(success=True, count=1)

    monkeypatch.setattr(
        email_drop_consume,
        "refresh_notes_browse_index",
        refresh_notes_browse_index,
    )

    record = consume_email_drop_source(store=store, source_id=source.id)

    assert record.status == "success"
    assert refresh_calls == [vault]
    assert record.files_moved == 1
    assert record.packets_created == 1
    assert record.links_seen == 1
    assert record.attachments_seen == 1
    assert record.wiki_update_marked is True
    assert (drop / "processed" / "message.eml").exists()
    assert (tmp_path / "runtime" / "wiki" / "needs-update.flag").exists()
    saved = store.get_run(record.id)
    assert saved.packets[0].subject == "Inbox article"
    final_path = Path(saved.packets[0].attachments[0].final_path or "")
    assert final_path.exists()
    assert final_path.read_bytes() == b"Attachment body"
    assert list((vault / "knowledge" / "notes").glob("*.md"))
    assert not (stale_vault / "knowledge" / "notes").exists()


def test_consume_email_drop_source_blocks_aftercare_on_partial_success(
    tmp_path,
    monkeypatch,
) -> None:
    from skills.ingest.scripts import email_drop_consume
    from skills.ingest.scripts.email_drop_consume import consume_email_drop_source
    from skills.ingest.scripts.email_drop_store import EmailDropStore

    drop = tmp_path / "mail"
    drop.mkdir()
    _write_eml(drop / "message.eml")
    (drop / "message.msg").write_bytes(b"requires optional parser")
    store = EmailDropStore(tmp_path / "state")
    source = store.add_source("Mail Drop", drop)
    vault = tmp_path / "vault"
    refresh_calls: list[Path] = []
    monkeypatch.setattr(email_drop_consume, "get_vault_dir", lambda: vault)
    monkeypatch.setattr(email_drop_consume, "get_runtime_dir", lambda: tmp_path / "runtime")

    def refresh_notes_browse_index(*, vault_dir):
        refresh_calls.append(vault_dir)
        return NoteBrowseIndexRefresh(success=True, count=1)

    monkeypatch.setattr(
        email_drop_consume,
        "refresh_notes_browse_index",
        refresh_notes_browse_index,
    )

    record = consume_email_drop_source(store=store, source_id=source.id)

    assert record.status == "partial_success"
    assert refresh_calls == [vault]
    assert record.files_moved == 0
    assert record.packets_created == 1
    assert record.files_skipped == 1
    assert (drop / "message.eml").exists()
    assert (drop / "message.msg").exists()


def test_consume_email_drop_source_records_refresh_failure(
    tmp_path,
    monkeypatch,
) -> None:
    from skills.ingest.scripts import email_drop_consume
    from skills.ingest.scripts.email_drop_consume import consume_email_drop_source
    from skills.ingest.scripts.email_drop_store import EmailDropStore

    drop = tmp_path / "mail"
    drop.mkdir()
    _write_eml(drop / "message.eml")
    store = EmailDropStore(tmp_path / "state")
    source = store.add_source("Mail Drop", drop)
    vault = tmp_path / "vault"

    monkeypatch.setattr(email_drop_consume, "get_vault_dir", lambda: vault)
    monkeypatch.setattr(email_drop_consume, "get_runtime_dir", lambda: tmp_path / "runtime")
    monkeypatch.setattr(
        email_drop_consume,
        "refresh_notes_browse_index",
        lambda **kwargs: NoteBrowseIndexRefresh(success=False, error="index boom"),
    )

    record = consume_email_drop_source(store=store, source_id=source.id)

    assert record.status == "partial_success"
    assert record.errors == ["reindex_failed: index boom"]
    assert record.files_failed == 1
    assert (drop / "processed" / "message.eml").exists()
    assert list((vault / "knowledge" / "notes").glob("*.md"))
    assert list((vault / "sources" / "extracted").glob("*.email.md"))
