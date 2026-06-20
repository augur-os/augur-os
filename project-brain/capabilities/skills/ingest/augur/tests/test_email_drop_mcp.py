from __future__ import annotations

import json
from email.message import EmailMessage
from pathlib import Path

from src.lib.ingest.note_index_refresh import NoteBrowseIndexRefresh


def _write_eml(path: Path) -> None:
    message = EmailMessage()
    message["From"] = "alice@example.com"
    message["To"] = "me@example.com"
    message["Subject"] = "MCP mail"
    message.set_content("Read https://example.com/mcp")
    path.write_bytes(message.as_bytes())


async def test_email_drop_sources_add_and_list(tmp_path, monkeypatch) -> None:
    from skills.ingest.scripts.mcp import inbox_tools

    monkeypatch.setattr(inbox_tools, "_store_root", lambda: tmp_path / "state")

    created = json.loads(
        await inbox_tools.email_drop_sources_impl(
            action="add",
            name="Mail Drop",
            path=str(tmp_path / "mail"),
        )
    )
    listed = json.loads(await inbox_tools.email_drop_sources_impl(action="list"))

    assert created["success"] is True
    assert created["source"]["id"] == "mail-drop"
    assert listed["sources"][0]["path"] == str((tmp_path / "mail").resolve())


async def test_email_drop_scan_source_returns_counts(tmp_path, monkeypatch) -> None:
    from skills.ingest.scripts.mcp import inbox_tools

    mail = tmp_path / "mail"
    mail.mkdir()
    _write_eml(mail / "message.eml")
    monkeypatch.setattr(inbox_tools, "_store_root", lambda: tmp_path / "state")
    created = json.loads(
        await inbox_tools.email_drop_sources_impl(
            action="add",
            name="Mail Drop",
            path=str(mail),
        )
    )

    scanned = json.loads(
        await inbox_tools.email_drop_scan_source_impl(created["source"]["id"])
    )

    assert scanned["success"] is True
    assert scanned["counts"]["pending_files"] == 1
    assert scanned["counts"]["article_links"] == 1


async def test_email_drop_consume_source_returns_partial_flag(tmp_path, monkeypatch) -> None:
    from skills.ingest.scripts import email_drop_consume
    from skills.ingest.scripts.mcp import inbox_tools

    mail = tmp_path / "mail"
    mail.mkdir()
    _write_eml(mail / "message.eml")
    (mail / "message.msg").write_bytes(b"requires optional parser")
    vault = tmp_path / "vault"
    refresh_calls: list[Path] = []
    monkeypatch.setattr(inbox_tools, "_store_root", lambda: tmp_path / "state")
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
    created = json.loads(
        await inbox_tools.email_drop_sources_impl(
            action="add",
            name="Mail Drop",
            path=str(mail),
        )
    )

    consumed = json.loads(
        await inbox_tools.email_drop_consume_source_impl(created["source"]["id"])
    )

    assert consumed["success"] is False
    assert consumed["partial"] is True
    assert refresh_calls == [vault]
    assert consumed["packets_created"] == 1
    assert consumed["files_skipped"] == 1
