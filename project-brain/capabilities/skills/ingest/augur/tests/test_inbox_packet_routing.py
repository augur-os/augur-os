from __future__ import annotations

from pathlib import Path


def test_route_packet_matches_existing_office_hours_folder(tmp_path: Path) -> None:
    from skills.ingest.scripts.inbox_packet_routing import propose_packet_route
    from skills.ingest.scripts.inbox_unified_models import InboxPacket, InboxVaultTarget

    docs = tmp_path / "docs"
    (docs / "venture-augur" / "office-hours").mkdir(parents=True)
    (docs / "venture-augur" / "office-hours" / "augur-office-hours-v22.pptx").write_bytes(b"old")
    packet_dir = docs / "inbox" / "claude" / "packet"
    packet_dir.mkdir(parents=True)
    (packet_dir / "augur-office-hours-v23.pptx").write_bytes(b"new")
    packet = InboxPacket(
        packet_id="packet",
        source_id="claude-chat",
        source_type="chat_mcp",
        capture_mode="filesystem_mcp",
        packet_dir=str(packet_dir),
        title="Augur Office Hours v23",
        status="staged",
        target_vault="personal",
        original_filename="augur-office-hours-v23.pptx",
        payload_paths=["augur-office-hours-v23.pptx"],
    )
    target = InboxVaultTarget(
        id="personal",
        kind="private",
        name="Personal",
        vault_root=str(tmp_path / "vault"),
        docs_root=str(docs),
        default=True,
        writable=True,
    )

    proposal = propose_packet_route(packet=packet, target=target)

    assert proposal.status == "ready"
    assert proposal.target_folder == "venture-augur/office-hours"
    assert proposal.final_filename == "augur-office-hours-v23.pptx"
    assert proposal.version_group == "augur-office-hours"
    assert proposal.failure_state is None


def test_route_packet_requires_route_when_no_signal(tmp_path: Path) -> None:
    from skills.ingest.scripts.inbox_packet_routing import propose_packet_route
    from skills.ingest.scripts.inbox_unified_models import InboxPacket, InboxVaultTarget

    docs = tmp_path / "docs"
    packet_dir = docs / "inbox" / "claude" / "packet"
    packet_dir.mkdir(parents=True)
    (packet_dir / "artifact.bin").write_bytes(b"payload")
    packet = InboxPacket(
        packet_id="packet",
        source_id="claude-chat",
        source_type="chat_mcp",
        capture_mode="mcp_content",
        packet_dir=str(packet_dir),
        title="Untitled",
        status="staged",
        target_vault="personal",
        original_filename="artifact.bin",
        payload_paths=["artifact.bin"],
    )
    target = InboxVaultTarget("personal", "private", "Personal", str(tmp_path / "vault"), str(docs), True, True)

    proposal = propose_packet_route(packet=packet, target=target)

    assert proposal.status == "needs_input"
    assert proposal.failure_state == "needs_route"
    assert proposal.questions == ["Choose the final folder for artifact.bin."]


def test_route_packet_fails_closed_for_missing_payload(tmp_path: Path) -> None:
    from skills.ingest.scripts.inbox_packet_routing import propose_packet_route
    from skills.ingest.scripts.inbox_unified_models import InboxPacket, InboxVaultTarget

    docs = tmp_path / "docs"
    packet_dir = docs / "inbox" / "claude" / "packet"
    packet_dir.mkdir(parents=True)
    packet = InboxPacket(
        packet_id="packet",
        source_id="claude-chat",
        source_type="chat_mcp",
        capture_mode="pending_drop",
        packet_dir=str(packet_dir),
        title="Missing Deck",
        status="pending_content",
        target_vault="personal",
        payload_paths=["missing.pptx"],
    )
    target = InboxVaultTarget("personal", "private", "Personal", str(tmp_path / "vault"), str(docs), True, True)

    proposal = propose_packet_route(packet=packet, target=target)

    assert proposal.status == "needs_input"
    assert proposal.failure_state == "pending_content"
    assert proposal.questions == ["Attach or drop the payload before routing Missing Deck."]


def test_route_packet_rejects_path_traversal_payload_name(tmp_path: Path) -> None:
    from skills.ingest.scripts.inbox_packet_routing import propose_packet_route
    from skills.ingest.scripts.inbox_unified_models import InboxPacket, InboxVaultTarget

    docs = tmp_path / "docs"
    packet_dir = docs / "inbox" / "claude" / "packet"
    packet_dir.mkdir(parents=True)
    (packet_dir / "deck.pptx").write_bytes(b"payload")
    packet = InboxPacket(
        packet_id="packet",
        source_id="claude-chat",
        source_type="chat_mcp",
        capture_mode="filesystem_mcp",
        packet_dir=str(packet_dir),
        title="Deck",
        status="staged",
        target_vault="personal",
        original_filename="../deck.pptx",
        payload_paths=["../deck.pptx"],
    )
    target = InboxVaultTarget("personal", "private", "Personal", str(tmp_path / "vault"), str(docs), True, True)

    proposal = propose_packet_route(packet=packet, target=target)

    assert proposal.status == "needs_input"
    assert proposal.failure_state == "pending_content"
