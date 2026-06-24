from __future__ import annotations

from pathlib import Path

import yaml


def test_consume_packet_moves_payload_writes_sidecar_and_archives(monkeypatch, tmp_path: Path) -> None:
    from skills.ingest.scripts.inbox_packet_consume import consume_packet
    from skills.ingest.scripts.inbox_unified_models import (
        InboxArchiveMove,
        InboxArchivePlan,
        InboxPacket,
        InboxRouteProposal,
        InboxVaultTarget,
    )

    docs = tmp_path / "docs"
    packet_dir = docs / "inbox" / "claude" / "packet"
    packet_dir.mkdir(parents=True)
    (packet_dir / "augur-office-hours-v23.pptx").write_bytes(b"new")
    target_folder = docs / "venture-augur" / "office-hours"
    target_folder.mkdir(parents=True)
    (target_folder / "augur-office-hours-v22.pptx").write_bytes(b"old")

    monkeypatch.setattr(
        "skills.ingest.scripts.inbox_packet_consume.apply_archive_plan",
        lambda docs_root, plan, dry_run=False: {
            "moves": [
                {
                    "from": "venture-augur/office-hours/augur-office-hours-v22.pptx",
                    "to": "venture-augur/office-hours/.archive/augur-office-hours-v22.pptx",
                    "status": "succeeded",
                }
            ]
        },
    )
    monkeypatch.setattr(
        "skills.ingest.scripts.inbox_packet_consume.refresh_notes_browse_index",
        lambda vault_dir=None: type("Refresh", (), {"success": True})(),
    )

    packet = InboxPacket(
        packet_id="packet",
        source_id="claude-chat",
        source_type="chat_mcp",
        capture_mode="filesystem_mcp",
        packet_dir=str(packet_dir),
        title="Augur Office Hours",
        status="staged",
        target_vault="personal",
        original_filename="augur-office-hours-v23.pptx",
        payload_paths=["augur-office-hours-v23.pptx"],
        user_instruction="save this deck to Augur docs",
        content_hash="sha256:staged",
        created_at="2026-05-18T14:30:12Z",
    )
    target = InboxVaultTarget("personal", "private", "Personal", str(tmp_path / "vault"), str(docs), True, True)
    proposal = InboxRouteProposal(
        packet_id="packet",
        target_vault="personal",
        target_domain="docs",
        target_folder="venture-augur/office-hours",
        final_filename="augur-office-hours-v23.pptx",
        route_reason="matched nearby versions",
        version_group="augur-office-hours",
        status="ready",
        archive_plan=InboxArchivePlan(
            auto_archive=[
                InboxArchiveMove(
                    relative_path="venture-augur/office-hours/augur-office-hours-v22.pptx",
                    reason="superseded by augur-office-hours-v23.pptx",
                    artifact_group="augur-office-hours",
                )
            ]
        ),
    )

    result = consume_packet(packet=packet, target=target, proposal=proposal)

    final_path = target_folder / "augur-office-hours-v23.pptx"
    sidecar_path = target_folder / "augur-office-hours-v23.meta.yaml"
    sidecar = yaml.safe_load(sidecar_path.read_text(encoding="utf-8"))
    assert result.status == "success"
    assert final_path.read_bytes() == b"new"
    assert sidecar["source_id"] == "claude-chat"
    assert sidecar["source_packet"] == "packet"
    assert sidecar["target_vault"] == "personal"
    assert sidecar["target_domain"] == "docs"
    assert sidecar["route_reason"] == "matched nearby versions"
    assert sidecar["version_group"] == "augur-office-hours"
    assert sidecar["content_hash"].startswith("sha256:")
    assert sidecar["staged_content_hash"] == "sha256:staged"
    assert sidecar["user_instruction"] == "save this deck to Augur docs"
    assert sidecar["created_at"] == "2026-05-18T14:30:12Z"
    assert sidecar["archived_superseded"] == ["venture-augur/office-hours/.archive/augur-office-hours-v22.pptx"]
    manifest = yaml.safe_load((packet_dir / "manifest.yaml").read_text(encoding="utf-8"))
    assert manifest["status"] == "consumed"
    assert manifest["packet_id"] == "packet"
    assert result.final_paths == [str(final_path)]
    assert result.sidecar_paths == [str(sidecar_path)]
    assert result.archived_paths == ["venture-augur/office-hours/.archive/augur-office-hours-v22.pptx"]
    assert result.index_refreshed is True


def test_consume_html_packet_stamps_artifact_sidecar_fields(monkeypatch, tmp_path: Path) -> None:
    """Landing an .html packet writes a sidecar the artifacts catalog can read.

    The artifacts scanner reads <stem>.meta.yaml next to <stem>.html. Without the
    artifact fields (slug/title/kind/hub) read_sidecar raises and the file is
    invisible in Browse. /keep reconcile must stamp them for HTML (Option A).
    """
    from skills.ingest.scripts.inbox_packet_consume import consume_packet
    from skills.ingest.scripts.inbox_unified_models import (
        InboxPacket,
        InboxRouteProposal,
        InboxVaultTarget,
    )
    from src.lib.artifacts_sidecar import read_sidecar

    docs = tmp_path / "docs"
    packet_dir = docs / "inbox" / "claude" / "packet"
    packet_dir.mkdir(parents=True)
    (packet_dir / "nvidia-prep-project-monterey.html").write_text(
        "<html><head><title>NVIDIA Prep — Project Monterey DSE</title></head><body>x</body></html>",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "skills.ingest.scripts.inbox_packet_consume.refresh_notes_browse_index",
        lambda vault_dir=None: type("Refresh", (), {"success": True})(),
    )

    packet = InboxPacket(
        packet_id="packet",
        source_id="claude-chat",
        source_type="chat_mcp",
        capture_mode="filesystem_mcp",
        packet_dir=str(packet_dir),
        title="NVIDIA Prep",
        status="staged",
        target_vault="personal",
        original_filename="nvidia-prep-project-monterey.html",
        payload_paths=["nvidia-prep-project-monterey.html"],
        user_instruction="Keep this interview-prep HTML as a durable artifact",
        content_hash="sha256:staged",
        created_at="2026-06-23T15:15:28Z",
    )
    target = InboxVaultTarget("personal", "private", "Personal", str(tmp_path / "vault"), str(docs), True, True)
    proposal = InboxRouteProposal(
        packet_id="packet",
        target_vault="personal",
        target_domain="docs",
        target_folder="career",
        final_filename="nvidia-prep-project-monterey.html",
        route_reason="agent session judgment (/keep reconcile)",
        version_group="nvidia-prep-project-monterey",
        status="ready",
    )

    result = consume_packet(packet=packet, target=target, proposal=proposal)

    assert result.status == "success"
    sidecar_path = docs / "career" / "nvidia-prep-project-monterey.meta.yaml"
    sidecar = yaml.safe_load(sidecar_path.read_text(encoding="utf-8"))
    # Ingest provenance is still present...
    assert sidecar["source_id"] == "claude-chat"
    assert sidecar["user_instruction"].startswith("Keep this")
    # ...and the artifact fields are now stamped alongside it.
    assert sidecar["slug"] == "nvidia-prep-project-monterey"
    assert sidecar["title"] == "NVIDIA Prep — Project Monterey DSE"
    assert sidecar["kind"] == "saved"
    assert sidecar["hub"] == "career"
    # The artifacts scanner can now read it without raising.
    sc = read_sidecar(sidecar_path)
    assert sc.slug == "nvidia-prep-project-monterey"
    assert sc.title == "NVIDIA Prep — Project Monterey DSE"


def test_consume_packet_fails_closed_when_proposal_not_ready(tmp_path: Path) -> None:
    from skills.ingest.scripts.inbox_packet_consume import consume_packet
    from skills.ingest.scripts.inbox_unified_models import InboxPacket, InboxRouteProposal, InboxVaultTarget

    docs = tmp_path / "docs"
    packet_dir = docs / "inbox" / "claude" / "packet"
    packet_dir.mkdir(parents=True)
    (packet_dir / "deck.pptx").write_bytes(b"new")
    packet = InboxPacket(
        packet_id="packet",
        source_id="claude-chat",
        source_type="chat_mcp",
        capture_mode="filesystem_mcp",
        packet_dir=str(packet_dir),
        title="Deck",
        status="staged",
        target_vault="personal",
        payload_paths=["deck.pptx"],
    )
    target = InboxVaultTarget("personal", "private", "Personal", str(tmp_path / "vault"), str(docs), True, True)
    proposal = InboxRouteProposal(
        packet_id="packet",
        target_vault="personal",
        target_domain="docs",
        target_folder="",
        final_filename="deck.pptx",
        route_reason="",
        version_group="deck",
        status="needs_input",
        failure_state="needs_route",
        questions=["Choose the final folder for deck.pptx."],
    )

    result = consume_packet(packet=packet, target=target, proposal=proposal)

    assert result.status == "needs_input"
    assert result.failure_state == "needs_route"
    assert result.questions == ["Choose the final folder for deck.pptx."]
    assert (packet_dir / "deck.pptx").exists()


def test_consume_packet_refuses_final_path_outside_docs_root(tmp_path: Path) -> None:
    from skills.ingest.scripts.inbox_packet_consume import consume_packet
    from skills.ingest.scripts.inbox_unified_models import InboxPacket, InboxRouteProposal, InboxVaultTarget

    docs = tmp_path / "docs"
    packet_dir = docs / "inbox" / "claude" / "packet"
    packet_dir.mkdir(parents=True)
    (packet_dir / "deck.pptx").write_bytes(b"new")
    packet = InboxPacket(
        packet_id="packet",
        source_id="claude-chat",
        source_type="chat_mcp",
        capture_mode="filesystem_mcp",
        packet_dir=str(packet_dir),
        title="Deck",
        status="staged",
        target_vault="personal",
        payload_paths=["deck.pptx"],
    )
    target = InboxVaultTarget("personal", "private", "Personal", str(tmp_path / "vault"), str(docs), True, True)
    proposal = InboxRouteProposal(
        packet_id="packet",
        target_vault="personal",
        target_domain="docs",
        target_folder="../outside",
        final_filename="deck.pptx",
        route_reason="bad route",
        version_group="deck",
        status="ready",
    )

    result = consume_packet(packet=packet, target=target, proposal=proposal)

    assert result.status == "failed"
    assert result.failure_state == "blocked_permission"
    assert (packet_dir / "deck.pptx").exists()
    assert not (tmp_path / "outside" / "deck.pptx").exists()


def test_consume_packet_reports_failed_index_after_successful_move(monkeypatch, tmp_path: Path) -> None:
    from skills.ingest.scripts.inbox_packet_consume import consume_packet
    from skills.ingest.scripts.inbox_unified_models import InboxPacket, InboxRouteProposal, InboxVaultTarget

    docs = tmp_path / "docs"
    packet_dir = docs / "inbox" / "claude" / "packet"
    packet_dir.mkdir(parents=True)
    (packet_dir / "deck.pptx").write_bytes(b"new")
    monkeypatch.setattr(
        "skills.ingest.scripts.inbox_packet_consume.apply_archive_plan",
        lambda docs_root, plan, dry_run=False: {"moves": []},
    )
    monkeypatch.setattr(
        "skills.ingest.scripts.inbox_packet_consume.refresh_notes_browse_index",
        lambda vault_dir=None: type("Refresh", (), {"success": False, "error": "index broke"})(),
    )
    packet = InboxPacket(
        packet_id="packet",
        source_id="claude-chat",
        source_type="chat_mcp",
        capture_mode="filesystem_mcp",
        packet_dir=str(packet_dir),
        title="Deck",
        status="staged",
        target_vault="personal",
        payload_paths=["deck.pptx"],
    )
    target = InboxVaultTarget("personal", "private", "Personal", str(tmp_path / "vault"), str(docs), True, True)
    proposal = InboxRouteProposal(
        packet_id="packet",
        target_vault="personal",
        target_domain="docs",
        target_folder="decks",
        final_filename="deck.pptx",
        route_reason="manual",
        version_group="deck",
        status="ready",
    )

    result = consume_packet(packet=packet, target=target, proposal=proposal)

    assert result.status == "needs_input"
    assert result.failure_state == "failed_index"
    assert result.final_paths == [str(docs / "decks" / "deck.pptx")]
    assert result.index_refreshed is False
    assert (docs / "decks" / "deck.pptx").read_bytes() == b"new"


def test_consume_packet_refuses_to_overwrite_existing_final_file(tmp_path: Path) -> None:
    from skills.ingest.scripts.inbox_packet_consume import consume_packet
    from skills.ingest.scripts.inbox_unified_models import InboxPacket, InboxRouteProposal, InboxVaultTarget

    docs = tmp_path / "docs"
    packet_dir = docs / "inbox" / "claude" / "packet"
    packet_dir.mkdir(parents=True)
    staged_payload = packet_dir / "deck-v2.pptx"
    staged_payload.write_bytes(b"new")
    target_folder = docs / "decks"
    target_folder.mkdir(parents=True)
    existing_final = target_folder / "deck-v2.pptx"
    existing_final.write_bytes(b"existing")
    packet = InboxPacket(
        packet_id="packet",
        source_id="claude-chat",
        source_type="chat_mcp",
        capture_mode="filesystem_mcp",
        packet_dir=str(packet_dir),
        title="Deck",
        status="staged",
        target_vault="personal",
        payload_paths=["deck-v2.pptx"],
    )
    target = InboxVaultTarget("personal", "private", "Personal", str(tmp_path / "vault"), str(docs), True, True)
    proposal = InboxRouteProposal(
        packet_id="packet",
        target_vault="personal",
        target_domain="docs",
        target_folder="decks",
        final_filename="deck-v2.pptx",
        route_reason="manual",
        version_group="deck",
        status="ready",
    )

    result = consume_packet(packet=packet, target=target, proposal=proposal)

    assert result.status == "needs_input"
    assert result.failure_state == "needs_version_choice"
    assert result.questions == ["deck-v2.pptx already exists in decks. Choose whether to archive, rename, or skip it."]
    assert staged_payload.read_bytes() == b"new"
    assert existing_final.read_bytes() == b"existing"


def test_consume_packet_stops_when_archive_plan_needs_user_choice(tmp_path: Path) -> None:
    from skills.ingest.scripts.inbox_packet_consume import consume_packet
    from skills.ingest.scripts.inbox_unified_models import (
        InboxArchiveMove,
        InboxArchivePlan,
        InboxPacket,
        InboxRouteProposal,
        InboxVaultTarget,
    )

    docs = tmp_path / "docs"
    packet_dir = docs / "inbox" / "claude" / "packet"
    packet_dir.mkdir(parents=True)
    staged_payload = packet_dir / "deck-v2.pptx"
    staged_payload.write_bytes(b"new")
    target_folder = docs / "decks"
    target_folder.mkdir(parents=True)
    existing_same_version = target_folder / "deck-v2-final.pptx"
    existing_same_version.write_bytes(b"existing same version")
    packet = InboxPacket(
        packet_id="packet",
        source_id="claude-chat",
        source_type="chat_mcp",
        capture_mode="filesystem_mcp",
        packet_dir=str(packet_dir),
        title="Deck",
        status="staged",
        target_vault="personal",
        payload_paths=["deck-v2.pptx"],
    )
    target = InboxVaultTarget("personal", "private", "Personal", str(tmp_path / "vault"), str(docs), True, True)
    proposal = InboxRouteProposal(
        packet_id="packet",
        target_vault="personal",
        target_domain="docs",
        target_folder="decks",
        final_filename="deck-v2.pptx",
        route_reason="manual",
        version_group="deck",
        status="ready",
        archive_plan=InboxArchivePlan(
            ask=[
                InboxArchiveMove(
                    relative_path="decks/deck-v2-final.pptx",
                    reason="same version as incoming deck-v2.pptx",
                    artifact_group="deck",
                    status="needs_input",
                    refusal_category="same_version_ambiguous",
                )
            ]
        ),
    )

    result = consume_packet(packet=packet, target=target, proposal=proposal)

    assert result.status == "needs_input"
    assert result.failure_state == "needs_version_choice"
    assert result.questions == ["same version as incoming deck-v2.pptx"]
    assert staged_payload.read_bytes() == b"new"
    assert existing_same_version.read_bytes() == b"existing same version"
    assert not (target_folder / "deck-v2.pptx").exists()


def test_consume_packet_rejects_nested_final_filename(tmp_path: Path) -> None:
    from skills.ingest.scripts.inbox_packet_consume import consume_packet
    from skills.ingest.scripts.inbox_unified_models import InboxPacket, InboxRouteProposal, InboxVaultTarget

    docs = tmp_path / "docs"
    packet_dir = docs / "inbox" / "claude" / "packet"
    packet_dir.mkdir(parents=True)
    staged_payload = packet_dir / "deck.pptx"
    staged_payload.write_bytes(b"new")
    packet = InboxPacket(
        packet_id="packet",
        source_id="claude-chat",
        source_type="chat_mcp",
        capture_mode="filesystem_mcp",
        packet_dir=str(packet_dir),
        title="Deck",
        status="staged",
        target_vault="personal",
        payload_paths=["deck.pptx"],
    )
    target = InboxVaultTarget("personal", "private", "Personal", str(tmp_path / "vault"), str(docs), True, True)
    proposal = InboxRouteProposal(
        packet_id="packet",
        target_vault="personal",
        target_domain="docs",
        target_folder="decks",
        final_filename="subdir/deck.pptx",
        route_reason="bad filename",
        version_group="deck",
        status="ready",
    )

    result = consume_packet(packet=packet, target=target, proposal=proposal)

    assert result.status == "failed"
    assert result.failure_state == "blocked_permission"
    assert staged_payload.read_bytes() == b"new"
    assert not (docs / "decks" / "subdir" / "deck.pptx").exists()


def test_consume_packet_rejects_mismatched_proposal_identity(tmp_path: Path) -> None:
    from skills.ingest.scripts.inbox_packet_consume import consume_packet
    from skills.ingest.scripts.inbox_unified_models import InboxPacket, InboxRouteProposal, InboxVaultTarget

    docs = tmp_path / "docs"
    packet_dir = docs / "inbox" / "claude" / "packet"
    packet_dir.mkdir(parents=True)
    staged_payload = packet_dir / "deck.pptx"
    staged_payload.write_bytes(b"new")
    packet = InboxPacket(
        packet_id="packet",
        source_id="claude-chat",
        source_type="chat_mcp",
        capture_mode="filesystem_mcp",
        packet_dir=str(packet_dir),
        title="Deck",
        status="staged",
        target_vault="personal",
        payload_paths=["deck.pptx"],
    )
    target = InboxVaultTarget("personal", "private", "Personal", str(tmp_path / "vault"), str(docs), True, True)
    stale_packet_proposal = InboxRouteProposal(
        packet_id="other-packet",
        target_vault="personal",
        target_domain="docs",
        target_folder="decks",
        final_filename="deck.pptx",
        route_reason="stale",
        version_group="deck",
        status="ready",
    )
    wrong_target_proposal = InboxRouteProposal(
        packet_id="packet",
        target_vault="team",
        target_domain="docs",
        target_folder="decks",
        final_filename="deck.pptx",
        route_reason="wrong target",
        version_group="deck",
        status="ready",
    )

    stale_result = consume_packet(packet=packet, target=target, proposal=stale_packet_proposal)
    wrong_target_result = consume_packet(packet=packet, target=target, proposal=wrong_target_proposal)

    assert stale_result.status == "failed"
    assert stale_result.failure_state == "blocked_permission"
    assert wrong_target_result.status == "failed"
    assert wrong_target_result.failure_state == "blocked_permission"
    assert staged_payload.read_bytes() == b"new"
    assert not (docs / "decks" / "deck.pptx").exists()
