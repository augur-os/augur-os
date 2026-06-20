from __future__ import annotations

import pytest
import yaml

from scripts import create_promotion_packet


def test_main_creates_packet_from_inline_synthesis(tmp_path, monkeypatch, capsys):
    project_brain = tmp_path / "project-brain"
    monkeypatch.setattr(create_promotion_packet, "get_project_brain_dir", lambda: project_brain)

    rc = create_promotion_packet.main(
        [
            "--topic",
            "Team Wiki Conflict Control",
            "--contributor",
            "Guri",
            "--synthesis",
            "Promotion packets keep canonical wiki edits out of contributor PRs.",
            "--date",
            "2026-05-03",
            "--role",
            "architect",
            "--domain",
            "knowledge",
            "--action",
            "Integrate accepted packets in a batch",
            "--link",
            "Project Brain Enterprise Overlay",
        ]
    )

    captured = capsys.readouterr()
    assert rc == 0
    packet_path = project_brain / "inbox" / "promotions" / "2026-05-03-guri-team-wiki-conflict-control"
    assert str(packet_path) in captured.out
    assert (packet_path / "synthesis.md").is_file()

    manifest = yaml.safe_load((packet_path / "manifest.yaml").read_text(encoding="utf-8"))
    assert manifest["roles"] == ["architect"]
    assert manifest["domains"] == ["knowledge"]


def test_main_creates_packet_from_synthesis_file(tmp_path, monkeypatch):
    project_brain = tmp_path / "project-brain"
    synthesis_file = tmp_path / "synthesis.md"
    synthesis_file.write_text("Packet body from a file.\n", encoding="utf-8")
    monkeypatch.setattr(create_promotion_packet, "get_project_brain_dir", lambda: project_brain)

    rc = create_promotion_packet.main(
        [
            "--topic",
            "File Based Packet",
            "--contributor",
            "Guri",
            "--synthesis-file",
            str(synthesis_file),
            "--date",
            "2026-05-03",
        ]
    )

    assert rc == 0
    packet_path = project_brain / "inbox" / "promotions" / "2026-05-03-guri-file-based-packet"
    assert "Packet body from a file." in (packet_path / "synthesis.md").read_text(encoding="utf-8")


def test_main_reports_invalid_packet_date_as_usage_error(capsys):
    with pytest.raises(SystemExit) as exc_info:
        create_promotion_packet.main(
            [
                "--topic",
                "Invalid Date Packet",
                "--contributor",
                "Guri",
                "--synthesis",
                "Packet body.",
                "--date",
                "not-a-date",
            ]
        )

    captured = capsys.readouterr()
    assert exc_info.value.code == 2
    assert "date must be YYYY-MM-DD" in captured.err
