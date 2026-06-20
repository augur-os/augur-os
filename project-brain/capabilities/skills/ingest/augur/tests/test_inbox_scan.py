from __future__ import annotations

import os
from pathlib import Path

import pytest


def test_scan_counts_documents_and_trash(tmp_path: Path) -> None:
    from src.lib.ingest.inbox_scan import scan_folder

    (tmp_path / "invoice.pdf").write_bytes(b"%PDF-1.7\n")
    (tmp_path / "meeting.mp3").write_bytes(b"audio")
    (tmp_path / "download.tmp").write_text("partial", encoding="utf-8")

    result = scan_folder(tmp_path)

    assert result.counts.new_files == 3
    assert result.counts.document_candidates == 2
    assert result.counts.trash_candidates == 1
    assert [item.name for item in result.items] == [
        "download.tmp",
        "invoice.pdf",
        "meeting.mp3",
    ]


def test_scan_skips_symlinked_files(tmp_path: Path) -> None:
    from src.lib.ingest.inbox_scan import scan_folder

    (tmp_path / "invoice.pdf").write_bytes(b"%PDF-1.7\n")
    target = tmp_path.parent / "outside.pdf"
    target.write_bytes(b"%PDF-1.7\n")
    link = tmp_path / "linked.pdf"
    try:
        link.symlink_to(target)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"Symlinks are unavailable on this platform: {exc}")

    result = scan_folder(tmp_path)

    assert result.counts.new_files == 1
    assert [item.name for item in result.items] == ["invoice.pdf"]


def test_scan_marks_recently_modified_files_unstable(tmp_path: Path) -> None:
    from src.lib.ingest.inbox_scan import scan_folder

    recent = tmp_path / "recording.mp3"
    recent.write_bytes(b"audio")
    now = 1_800_000_000
    os.utime(recent, (now, now))

    result = scan_folder(tmp_path, stable_age_seconds=60.0, now=now + 1.0)

    assert result.items[0].name == "recording.mp3"
    assert result.items[0].stable is False


def test_scan_records_stat_failures(monkeypatch, tmp_path: Path) -> None:
    from src.lib.ingest import inbox_scan

    class BrokenFile:
        name = "vanished.pdf"
        suffix = ".pdf"

        def is_symlink(self) -> bool:
            return False

        def is_file(self) -> bool:
            return True

        def stat(self):
            raise OSError("stat boom")

        def resolve(self, strict: bool = False):
            return tmp_path / self.name

    monkeypatch.setattr(Path, "iterdir", lambda self: iter([BrokenFile()]))

    result = inbox_scan.scan_folder(tmp_path)

    assert result.counts.failed == 1
    assert result.items[0].name == "vanished.pdf"
    assert result.items[0].candidate_type == "failed"
    assert result.items[0].stable is False
