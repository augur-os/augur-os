from __future__ import annotations

from pathlib import Path


def test_store_adds_source_with_supported_formats_and_persists_counts(
    tmp_path: Path,
) -> None:
    from skills.ingest.scripts.email_drop_store import EmailDropStore

    drop_path = tmp_path / "email"
    drop_path.mkdir()
    store = EmailDropStore(tmp_path / "state")

    source = store.add_source(name="Augur Mail", path=drop_path)
    saved = store.update_source_counts(
        source.id,
        {
            "pending_files": 7,
            "email_native": 4,
            "archives": 1,
            "degraded": 2,
            "unsupported": 0,
            "failed": 0,
            "contained_messages": 9,
            "attachments": 3,
            "article_links": 5,
        },
    )

    reloaded = EmailDropStore(tmp_path / "state")
    sources = reloaded.list_sources()

    assert source.id == "augur-mail"
    assert ".eml" in source.formats
    assert ".msg" in source.formats
    assert ".oft" in source.formats
    assert ".mbox" in source.formats
    assert ".pst" in source.formats
    assert ".zip" in source.formats
    assert ".tar.gz" in source.formats
    assert ".mhtml" in source.formats
    assert saved.counts.pending_files == 7
    assert saved.counts.contained_messages == 9
    assert len(sources) == 1
    assert sources[0].path == str(drop_path.resolve())


def test_store_records_run_history_and_detail(tmp_path: Path) -> None:
    from skills.ingest.scripts.email_drop_models import (
        EmailDropPacket,
        EmailDropRunRecord,
    )
    from skills.ingest.scripts.email_drop_store import EmailDropStore

    store = EmailDropStore(tmp_path / "state")
    source = store.add_source(name="Augur Mail", path=tmp_path / "email")
    record = EmailDropRunRecord(
        id="run_1",
        source_id=source.id,
        started_at="2026-05-14T09:00:00+00:00",
        completed_at="2026-05-14T09:01:00+00:00",
        status="success",
        artifacts_seen=1,
        packets_created=1,
        archives_seen=0,
        degraded_files_seen=0,
        files_failed=0,
        wiki_update_marked=True,
        packets=[
            EmailDropPacket(
                source_path="C:/Users/example/Augur Mail/message.eml",
                artifact_type="eml",
                subject="Read this",
                from_address="alice@example.com",
                to_addresses=["me@example.com"],
                date="Thu, 14 May 2026 09:00:00 +0000",
                message_id="<msg-1@example.com>",
                body_text="https://example.com/article",
                links=["https://example.com/article"],
                status="success",
            )
        ],
    )

    store.save_run(record)

    assert store.list_runs()[0].id == "run_1"
    assert store.get_run("run_1").packets[0].subject == "Read this"


def test_store_saves_unsafe_run_ids_inside_runs_dir(tmp_path: Path) -> None:
    from skills.ingest.scripts.email_drop_models import EmailDropRunRecord
    from skills.ingest.scripts.email_drop_store import EmailDropStore

    store = EmailDropStore(tmp_path / "state")
    source = store.add_source(name="Augur Mail", path=tmp_path / "email")
    unsafe_id = "../2026-05-14T09:00:00+00:00\\mail"
    record = EmailDropRunRecord(
        id=unsafe_id,
        source_id=source.id,
        started_at="2026-05-14T09:00:00+00:00",
        completed_at="2026-05-14T09:01:00+00:00",
        status="success",
    )

    store.save_run(record)

    saved_files = list(store.runs_dir.glob("*.json"))
    assert len(saved_files) == 1
    assert saved_files[0].parent == store.runs_dir
    assert ":" not in saved_files[0].name
    assert store.get_run(unsafe_id).id == unsafe_id


def test_store_ignores_future_source_fields(tmp_path: Path) -> None:
    import json

    from skills.ingest.scripts.email_drop_store import EmailDropStore

    store = EmailDropStore(tmp_path / "state")
    store.sources_path.parent.mkdir(parents=True)
    store.sources_path.write_text(
        json.dumps(
            [
                {
                    "id": "mail",
                    "name": "Mail",
                    "path": str(tmp_path / "email"),
                    "future_field": {"ignored": True},
                    "counts": {"pending_files": 2, "future_count": 99},
                }
            ]
        ),
        encoding="utf-8",
    )

    source = store.list_sources()[0]

    assert source.id == "mail"
    assert source.counts.pending_files == 2


def test_store_preserves_configured_source_path(tmp_path: Path) -> None:
    from skills.ingest.scripts.email_drop_store import EmailDropStore

    store = EmailDropStore(tmp_path / "state")

    source = store.add_source(name="Mail Drop", path="~/Documents/Augur/inbox/email")

    assert source.path == "~/Documents/Augur/inbox/email"
