from datetime import date
import hashlib
from pathlib import Path

import pytest
import yaml

from src.lib.frontmatter_utils import parse_frontmatter
from src.lib.vault_promotion import PromotionPacketRequest, create_promotion_packet


def test_create_promotion_packet_writes_append_only_folder(tmp_path: Path) -> None:
    source_file = tmp_path / "source.md"
    source_file.write_text("source evidence\n", encoding="utf-8")

    packet = create_promotion_packet(
        tmp_path / "project-brain",
        PromotionPacketRequest(
            topic="Enterprise Overlay",
            contributor="Guri QO",
            synthesis="  Project brain promotion synthesis.  ",
            source_paths=[source_file],
            proposed_actions=["Review with admins", "Promote to shared wiki"],
            proposed_links=["[[Enterprise Overlay]]"],
            roles=["admin", "editor"],
            domains=["enterprise"],
            packet_date=date(2026, 5, 3),
        ),
    )

    assert packet.path == (
        tmp_path / "project-brain" / "inbox" / "promotions" / "2026-05-03-guri-qo-enterprise-overlay"
    )
    assert packet.manifest_path == packet.path / "manifest.yaml"
    assert packet.synthesis_path == packet.path / "synthesis.md"
    assert (packet.path / "proposed-actions.md").is_file()
    assert (packet.path / "proposed-links.md").is_file()
    assert (packet.path / "sources" / "README.md").is_file()

    manifest = yaml.safe_load(packet.manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["kind"] == "project-brain-promotion-packet"
    assert manifest["status"] == "packet"
    assert manifest["topic"] == "Enterprise Overlay"
    assert manifest["contributor"] == "Guri QO"
    assert manifest["date"] == "2026-05-03"
    assert manifest["sensitivity"] == "internal"
    assert manifest["roles"] == ["admin", "editor"]
    assert manifest["domains"] == ["enterprise"]
    assert manifest["outputs"] == {
        "synthesis": "synthesis.md",
        "proposed_actions": "proposed-actions.md",
        "proposed_links": "proposed-links.md",
    }
    copied_source = packet.path / "sources" / "source.md"
    expected_sha256 = hashlib.sha256(copied_source.read_bytes()).hexdigest()

    assert copied_source.read_text(encoding="utf-8") == "source evidence\n"
    assert manifest["source_refs"][0]["path"] == "sources/source.md"
    assert Path(manifest["source_refs"][0]["path"]).is_absolute() is False
    assert manifest["source_refs"][0]["source_name"] == "source.md"
    assert manifest["source_refs"][0]["exists"] is True
    assert manifest["source_refs"][0]["is_file"] is True
    assert manifest["source_refs"][0]["sha256"] == expected_sha256
    assert len(manifest["source_refs"][0]["sha256"]) == 64
    assert str(source_file) not in packet.manifest_path.read_text(encoding="utf-8")

    frontmatter, body = parse_frontmatter(packet.synthesis_path)
    assert frontmatter == {
        "title": "Enterprise Overlay",
        "brain_scope": "project",
        "promotion_state": "packet",
        "contributor": "Guri QO",
        "roles": ["admin", "editor"],
        "domains": ["enterprise"],
        "sensitivity": "internal",
    }
    assert body.strip() == "Project brain promotion synthesis."


def test_create_promotion_packet_records_brain_route_and_enforces_source_containment(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "personal"
    source_file = source_root / "notes" / "source.md"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("source evidence\n", encoding="utf-8")

    packet = create_promotion_packet(
        tmp_path / "team",
        PromotionPacketRequest(
            topic="Routing",
            contributor="Guri QO",
            synthesis="Route this through an explicit packet.",
            source_paths=[source_file],
            source_brain_id="personal",
            target_brain_id="team-core",
            source_root=source_root,
            packet_date=date(2026, 5, 21),
        ),
    )

    manifest = yaml.safe_load(packet.manifest_path.read_text(encoding="utf-8"))
    assert manifest["kind"] == "brain-propagation-packet"
    assert manifest["source_brain_id"] == "personal"
    assert manifest["target_brain_id"] == "team-core"
    assert manifest["source_refs"][0]["path"] == "sources/source.md"
    assert str(source_root) not in packet.manifest_path.read_text(encoding="utf-8")


def test_create_promotion_packet_rejects_sources_outside_source_brain(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "personal"
    outside = tmp_path / "outside.md"
    outside.write_text("leak\n", encoding="utf-8")

    with pytest.raises(ValueError, match="source path is outside source brain"):
        create_promotion_packet(
            tmp_path / "team",
            PromotionPacketRequest(
                topic="Routing",
                contributor="Guri QO",
                synthesis="Route this through an explicit packet.",
                source_paths=[outside],
                source_brain_id="personal",
                target_brain_id="team-core",
                source_root=source_root,
                packet_date=date(2026, 5, 21),
            ),
        )


def test_create_promotion_packet_uses_unique_suffix_when_folder_exists(
    tmp_path: Path,
) -> None:
    promotions_dir = tmp_path / "project-brain" / "inbox" / "promotions"
    existing = promotions_dir / "2026-05-03-guri-qo-enterprise-overlay"
    existing.mkdir(parents=True)

    packet = create_promotion_packet(
        tmp_path / "project-brain",
        PromotionPacketRequest(
            topic="Enterprise Overlay",
            contributor="Guri QO",
            synthesis="Project brain promotion synthesis.",
            packet_date=date(2026, 5, 3),
        ),
    )

    assert packet.path == promotions_dir / "2026-05-03-guri-qo-enterprise-overlay-2"


def test_create_promotion_packet_rejects_empty_topic(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="^topic is required$"):
        create_promotion_packet(
            tmp_path / "project-brain",
            PromotionPacketRequest(topic=" ", contributor="Guri", synthesis="Synthesis"),
        )


def test_create_promotion_packet_rejects_empty_contributor(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="^contributor is required$"):
        create_promotion_packet(
            tmp_path / "project-brain",
            PromotionPacketRequest(topic="Enterprise Overlay", contributor="\t", synthesis="Synthesis"),
        )


def test_create_promotion_packet_rejects_empty_synthesis(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="^synthesis is required$"):
        create_promotion_packet(
            tmp_path / "project-brain",
            PromotionPacketRequest(topic="Enterprise Overlay", contributor="Guri", synthesis="\n"),
        )
