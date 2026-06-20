from __future__ import annotations

import mailbox
import tarfile
import zipfile
from email.message import EmailMessage
from pathlib import Path


def _write_eml(path: Path, subject: str = "Read this") -> None:
    message = EmailMessage()
    message["From"] = "alice@example.com"
    message["To"] = "me@example.com"
    message["Subject"] = subject
    message["Message-ID"] = "<msg-1@example.com>"
    message["Date"] = "Thu, 14 May 2026 09:00:00 +0000"
    message.set_content("Please read https://example.com/article")
    message.add_attachment(
        b"hello",
        maintype="text",
        subtype="plain",
        filename="note.txt",
    )
    path.write_bytes(message.as_bytes())


def test_classify_supported_provider_outputs(tmp_path: Path) -> None:
    from skills.ingest.scripts.email_artifact_parser import classify_artifact

    expected = {
        "message.eml": ("email_native", "eml"),
        "message.msg": ("email_native", "msg"),
        "template.oft": ("email_native", "oft"),
        "archive.mbox": ("email_native", "mbox"),
        "apple.mbox": ("email_native", "apple_mbox_bundle"),
        "export.pst": ("email_native", "pst"),
        "download.zip": ("archive", "zip"),
        "download.tgz": ("archive", "tgz"),
        "download.tar": ("archive", "tar"),
        "download.tar.gz": ("archive", "tar.gz"),
        "print.pdf": ("degraded", "pdf"),
        "copy.txt": ("degraded", "txt"),
        "page.html": ("degraded", "html"),
        "page.htm": ("degraded", "htm"),
        "saved.mht": ("degraded", "mht"),
        "saved.mhtml": ("degraded", "mhtml"),
    }

    apple_bundle = tmp_path / "apple.mbox"
    apple_bundle.mkdir()

    for filename, (category, artifact_type) in expected.items():
        path = apple_bundle if filename == "apple.mbox" else tmp_path / filename
        if filename != "apple.mbox":
            path.touch()

        info = classify_artifact(path)

        assert info.category == category
        assert info.artifact_type == artifact_type
        assert info.supported is True


def test_parse_eml_extracts_metadata_links_and_attachment_names(
    tmp_path: Path,
) -> None:
    from skills.ingest.scripts.email_artifact_parser import parse_artifact

    eml_path = tmp_path / "message.eml"
    _write_eml(eml_path)

    result = parse_artifact(eml_path, staging_dir=tmp_path / "stage")

    assert result.errors == []
    assert len(result.packets) == 1
    packet = result.packets[0]
    assert packet.artifact_type == "eml"
    assert packet.subject == "Read this"
    assert packet.from_address == "alice@example.com"
    assert packet.to_addresses == ["me@example.com"]
    assert packet.message_id == "<msg-1@example.com>"
    assert packet.links == ["https://example.com/article"]
    assert packet.attachments[0].filename == "note.txt"
    assert packet.attachments[0].staged_path is not None
    assert Path(packet.attachments[0].staged_path).is_file()


def test_parse_mbox_extracts_each_message(tmp_path: Path) -> None:
    from skills.ingest.scripts.email_artifact_parser import parse_artifact

    mbox_path = tmp_path / "mailbox.mbox"
    mbox = mailbox.mbox(mbox_path)
    for subject in ("First", "Second"):
        message = EmailMessage()
        message["From"] = "sender@example.com"
        message["To"] = "me@example.com"
        message["Subject"] = subject
        message.set_content(f"{subject} https://example.com/{subject.lower()}")
        mbox.add(message)
    mbox.close()

    result = parse_artifact(mbox_path, staging_dir=tmp_path / "stage")

    assert [packet.subject for packet in result.packets] == ["First", "Second"]
    assert [packet.ordinal for packet in result.packets] == [0, 1]
    assert result.errors == []


def test_parse_apple_mbox_bundle_extracts_messages(tmp_path: Path) -> None:
    from skills.ingest.scripts.email_artifact_parser import parse_artifact

    bundle_path = tmp_path / "Augur.mbox"
    bundle_path.mkdir()
    mbox_path = bundle_path / "mbox"
    mbox = mailbox.mbox(mbox_path)
    message = EmailMessage()
    message["From"] = "sender@example.com"
    message["To"] = "me@example.com"
    message["Subject"] = "Apple export"
    message.set_content("body")
    mbox.add(message)
    mbox.close()

    result = parse_artifact(bundle_path, staging_dir=tmp_path / "stage")

    assert len(result.packets) == 1
    assert result.packets[0].artifact_type == "apple_mbox_bundle"
    assert result.packets[0].subject == "Apple export"


def test_parse_zip_container_parses_nested_eml_with_provenance(
    tmp_path: Path,
) -> None:
    from skills.ingest.scripts.email_artifact_parser import parse_artifact

    eml_path = tmp_path / "message.eml"
    _write_eml(eml_path, subject="Nested")
    zip_path = tmp_path / "mail.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.write(eml_path, arcname="nested/message.eml")

    result = parse_artifact(zip_path, staging_dir=tmp_path / "stage")

    assert result.errors == []
    assert len(result.packets) == 1
    assert result.packets[0].subject == "Nested"
    assert result.packets[0].container_path == str(zip_path)
    assert result.packets[0].contained_path == "nested/message.eml"


def test_parse_archive_rejects_traversal_entries(tmp_path: Path) -> None:
    from skills.ingest.scripts.email_artifact_parser import parse_artifact

    zip_path = tmp_path / "bad.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("../evil.eml", b"bad")

    result = parse_artifact(zip_path, staging_dir=tmp_path / "stage")

    assert result.packets == []
    assert result.errors == ["unsafe_archive_entry: ../evil.eml"]
    assert not (tmp_path / "evil.eml").exists()


def test_parse_tar_gz_container_parses_nested_eml(tmp_path: Path) -> None:
    from skills.ingest.scripts.email_artifact_parser import parse_artifact

    eml_path = tmp_path / "message.eml"
    _write_eml(eml_path, subject="Tar nested")
    tar_path = tmp_path / "mail.tar.gz"
    with tarfile.open(tar_path, "w:gz") as archive:
        archive.add(eml_path, arcname="nested/message.eml")

    result = parse_artifact(tar_path, staging_dir=tmp_path / "stage")

    assert result.errors == []
    assert len(result.packets) == 1
    assert result.packets[0].subject == "Tar nested"
    assert result.packets[0].container_path == str(tar_path)
    assert result.packets[0].contained_path == "nested/message.eml"


def test_parse_known_binary_exports_are_dependency_isolated(tmp_path: Path) -> None:
    from skills.ingest.scripts.email_artifact_parser import parse_artifact

    for filename in ("message.msg", "template.oft", "archive.pst"):
        path = tmp_path / filename
        path.write_bytes(b"not parsed without optional dependency")

        result = parse_artifact(path, staging_dir=tmp_path / "stage")

        assert result.packets == []
        assert result.skipped[0].reason == "parser_unavailable"
        assert result.skipped[0].artifact_type == path.suffix.lstrip(".")


def test_parse_txt_export_marks_partial_metadata_and_links(tmp_path: Path) -> None:
    from skills.ingest.scripts.email_artifact_parser import parse_artifact

    path = tmp_path / "saved-email.txt"
    path.write_text("Forwarded note https://example.com/resource", encoding="utf-8")

    result = parse_artifact(path, staging_dir=tmp_path / "stage")

    assert result.errors == []
    assert result.packets[0].metadata_partial is True
    assert result.packets[0].artifact_type == "txt"
    assert result.packets[0].links == ["https://example.com/resource"]
