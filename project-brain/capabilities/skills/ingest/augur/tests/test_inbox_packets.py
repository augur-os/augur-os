from __future__ import annotations

import hashlib
from pathlib import Path

import yaml


def _write_defaults(repo: Path, *, write_modes: str = "[mcp_content, filesystem_mcp, pending_drop]") -> None:
    config_dir = repo / "config" / "system"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "inbox.yaml").write_text(
        "version: 1\n"
        "default_sources:\n"
        "  - id: claude-chat\n"
        "    type: chat_mcp\n"
        "    name: Claude Chat\n"
        "    domain: docs\n"
        f"    write_modes: {write_modes}\n"
        "    filesystem_roots: [documents/inbox/claude]\n"
        "    default_target_vault: personal\n",
        encoding="utf-8",
    )


def _patch_registry_paths(monkeypatch, tmp_path: Path) -> tuple[Path, Path, Path]:
    from skills.ingest.scripts import inbox_packets, inbox_registry

    runtime = tmp_path / "runtime"
    docs = tmp_path / "docs"
    vault = tmp_path / "vault"
    repo = tmp_path / "repo"
    _write_defaults(repo)

    monkeypatch.setattr(inbox_registry, "get_runtime_dir", lambda: runtime)
    monkeypatch.setattr(inbox_registry, "get_documents_dir", lambda: docs)
    monkeypatch.setattr(inbox_registry, "get_vault_dir", lambda: vault)
    monkeypatch.setattr(inbox_registry, "get_config_dir", lambda: repo / "config")
    monkeypatch.setattr(inbox_packets, "_now_compact", lambda: "20260518-143012")
    monkeypatch.setattr(inbox_packets, "_now_iso", lambda: "2026-05-18T14:30:12Z")
    return runtime, docs, vault


def test_stage_packet_writes_payload_and_manifest(monkeypatch, tmp_path: Path) -> None:
    from skills.ingest.scripts import inbox_packets
    from skills.ingest.scripts.inbox_unified_models import to_dict

    _, docs, _ = _patch_registry_paths(monkeypatch, tmp_path)

    packet = inbox_packets.stage_packet(
        source_id="claude-chat",
        title="Augur Office Hours Deck",
        filename="office-hours.pptx",
        content=b"deck bytes",
        user_instruction="save this deck to my Augur docs",
        content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        capture_mode="mcp_content",
    )

    packet_dir = Path(packet.packet_dir)
    manifest = yaml.safe_load((packet_dir / "manifest.yaml").read_text(encoding="utf-8"))
    assert packet.packet_id == "20260518-143012-augur-office-hours-deck"
    assert packet.packet_dir == str(docs / "inbox" / "claude" / packet.packet_id)
    assert packet.status == "staged"
    assert packet.target_vault == "personal"
    assert packet.source_type == "chat_mcp"
    assert packet.created_at == "2026-05-18T14:30:12Z"
    assert (packet_dir / "office-hours.pptx").read_bytes() == b"deck bytes"
    assert packet.content_hash == f"sha256:{hashlib.sha256(b'deck bytes').hexdigest()}"
    assert manifest == to_dict(packet)
    assert manifest["source_id"] == "claude-chat"
    assert manifest["payload_paths"] == ["office-hours.pptx"]


def test_pending_packet_reports_drop_target(monkeypatch, tmp_path: Path) -> None:
    from skills.ingest.scripts import inbox_packets, inbox_registry

    _, docs, _ = _patch_registry_paths(monkeypatch, tmp_path)
    _write_defaults(tmp_path / "repo", write_modes="[pending_drop]")
    monkeypatch.setattr(inbox_registry, "get_config_dir", lambda: tmp_path / "repo" / "config")
    monkeypatch.setattr(inbox_packets, "_now_compact", lambda: "20260518-143500")
    monkeypatch.setattr(inbox_packets, "_now_iso", lambda: "2026-05-18T14:35:00Z")

    packet = inbox_packets.create_pending_packet(
        source_id="claude-chat",
        title="Slide Draft",
        user_instruction="save this slide to Augur",
    )

    assert packet.status == "pending_content"
    assert packet.failure_state == "pending_content"
    assert Path(packet.packet_dir) == docs / "inbox" / "claude" / "20260518-143500-slide-draft"
    manifest = yaml.safe_load((Path(packet.packet_dir) / "manifest.yaml").read_text(encoding="utf-8"))
    assert manifest["payload_paths"] == []
    assert manifest["content_hash"] == ""


def test_stage_packet_uses_safe_payload_basename(monkeypatch, tmp_path: Path) -> None:
    from skills.ingest.scripts import inbox_packets

    _patch_registry_paths(monkeypatch, tmp_path)

    packet = inbox_packets.stage_packet(
        source_id="claude-chat",
        title="Unsafe Filename",
        filename="../slides\\Quarterly Deck: v1?.pptx",
        content=b"deck",
        user_instruction="save this deck",
    )

    packet_dir = Path(packet.packet_dir)
    assert packet.original_filename == "quarterly-deck-v1.pptx"
    assert packet.payload_paths == ["quarterly-deck-v1.pptx"]
    assert (packet_dir / "quarterly-deck-v1.pptx").read_bytes() == b"deck"
    assert not (packet_dir / "slides\\Quarterly Deck: v1?.pptx").exists()


def test_stage_packet_renames_manifest_payload_without_losing_bytes(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.ingest.scripts import inbox_packets

    _patch_registry_paths(monkeypatch, tmp_path)

    packet = inbox_packets.stage_packet(
        source_id="claude-chat",
        title="Manifest Payload",
        filename="manifest.yaml",
        content=b"payload: original bytes\n",
        user_instruction="save this yaml",
        content_type="application/yaml",
    )

    packet_dir = Path(packet.packet_dir)
    manifest = yaml.safe_load((packet_dir / "manifest.yaml").read_text(encoding="utf-8"))
    assert packet.original_filename == "payload-manifest.yaml"
    assert packet.payload_paths == ["payload-manifest.yaml"]
    assert (packet_dir / "payload-manifest.yaml").read_bytes() == b"payload: original bytes\n"
    assert manifest["packet_id"] == packet.packet_id
    assert manifest["payload_paths"] == ["payload-manifest.yaml"]
    assert manifest["content_hash"] == f"sha256:{hashlib.sha256(b'payload: original bytes\n').hexdigest()}"


def test_stage_packet_preserves_extensionless_payload_names(monkeypatch, tmp_path: Path) -> None:
    from skills.ingest.scripts import inbox_packets

    _patch_registry_paths(monkeypatch, tmp_path)

    dockerfile = inbox_packets.stage_packet(
        source_id="claude-chat",
        title="Dockerfile Payload",
        filename="Dockerfile",
        content=b"FROM python:3.12\n",
        user_instruction="save this Dockerfile",
    )
    readme = inbox_packets.stage_packet(
        source_id="claude-chat",
        title="Readme Payload",
        filename="README",
        content=b"project notes\n",
        user_instruction="save this README",
    )

    assert dockerfile.original_filename == "dockerfile"
    assert dockerfile.payload_paths == ["dockerfile"]
    assert (Path(dockerfile.packet_dir) / "dockerfile").read_bytes() == b"FROM python:3.12\n"
    assert readme.original_filename == "readme"
    assert readme.payload_paths == ["readme"]
    assert (Path(readme.packet_dir) / "readme").read_bytes() == b"project notes\n"


def test_stage_packet_preserves_compound_payload_suffix(monkeypatch, tmp_path: Path) -> None:
    from skills.ingest.scripts import inbox_packets

    _patch_registry_paths(monkeypatch, tmp_path)

    packet = inbox_packets.stage_packet(
        source_id="claude-chat",
        title="Archive Payload",
        filename="archive.tar.gz",
        content=b"compressed bytes",
        user_instruction="save this archive",
    )

    assert packet.original_filename == "archive.tar.gz"
    assert packet.payload_paths == ["archive.tar.gz"]
    assert (Path(packet.packet_dir) / "archive.tar.gz").read_bytes() == b"compressed bytes"


def test_stage_packet_same_second_title_creates_unique_packet_dirs(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.ingest.scripts import inbox_packets

    _patch_registry_paths(monkeypatch, tmp_path)

    first = inbox_packets.stage_packet(
        source_id="claude-chat",
        title="Repeated Save",
        filename="note.md",
        content=b"first",
        user_instruction="save first",
    )
    second = inbox_packets.stage_packet(
        source_id="claude-chat",
        title="Repeated Save",
        filename="note.md",
        content=b"second",
        user_instruction="save second",
    )

    assert first.packet_id == "20260518-143012-repeated-save"
    assert second.packet_id == "20260518-143012-repeated-save-2"
    assert Path(first.packet_dir) != Path(second.packet_dir)
    assert (Path(first.packet_dir) / "note.md").read_bytes() == b"first"
    assert (Path(second.packet_dir) / "note.md").read_bytes() == b"second"

    first_manifest = yaml.safe_load((Path(first.packet_dir) / "manifest.yaml").read_text(encoding="utf-8"))
    second_manifest = yaml.safe_load((Path(second.packet_dir) / "manifest.yaml").read_text(encoding="utf-8"))
    assert first_manifest["packet_id"] == first.packet_id
    assert second_manifest["packet_id"] == second.packet_id
    assert first_manifest["user_instruction"] == "save first"
    assert second_manifest["user_instruction"] == "save second"


def test_pending_packet_same_second_title_creates_unique_packet_dirs(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.ingest.scripts import inbox_packets

    _patch_registry_paths(monkeypatch, tmp_path)

    first = inbox_packets.create_pending_packet(
        source_id="claude-chat",
        title="Repeated Pending",
        user_instruction="drop first later",
    )
    second = inbox_packets.create_pending_packet(
        source_id="claude-chat",
        title="Repeated Pending",
        user_instruction="drop second later",
    )

    assert first.packet_id == "20260518-143012-repeated-pending"
    assert second.packet_id == "20260518-143012-repeated-pending-2"
    first_manifest = yaml.safe_load((Path(first.packet_dir) / "manifest.yaml").read_text(encoding="utf-8"))
    second_manifest = yaml.safe_load((Path(second.packet_dir) / "manifest.yaml").read_text(encoding="utf-8"))
    assert first_manifest["user_instruction"] == "drop first later"
    assert second_manifest["user_instruction"] == "drop second later"
    assert first_manifest["failure_state"] == "pending_content"
    assert second_manifest["failure_state"] == "pending_content"


def test_packet_id_uses_packet_slug_for_empty_title(monkeypatch, tmp_path: Path) -> None:
    from skills.ingest.scripts import inbox_packets

    _patch_registry_paths(monkeypatch, tmp_path)

    packet = inbox_packets.create_pending_packet(
        source_id="claude-chat",
        title=" !!! ",
        user_instruction="save later",
    )

    assert packet.packet_id == "20260518-143012-packet"
    assert Path(packet.packet_dir).name == packet.packet_id
