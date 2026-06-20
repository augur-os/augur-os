from __future__ import annotations

import json
from pathlib import Path

from src.lib.frontmatter_utils import write_frontmatter


def _write_adr(path: Path, number: int, status: str, title: str, body: str = "Decision body.") -> Path:
    adr_path = path / f"ADR-{number:03d}-{title.lower().replace(' ', '-')}.md"
    write_frontmatter(
        adr_path,
        {"status": status, "date": "2026-06-11", "hub": "workspace", "tags": [], "related": []},
        f"# ADR-{number:03d}: {title}\n\n## Context\n\n{body}\n",
    )
    return adr_path


def test_archive_eligible_adrs_moves_md_into_archive_dir(tmp_path):
    """ADR-811: archiving moves the plain .md into archive/, no zips."""
    from src.lib.adr_utils import archive_eligible_adrs, get_archive_dir, load_adrs_index

    _write_adr(tmp_path, 7, "Implemented", "First Archived")
    _write_adr(tmp_path, 23, "Accepted", "Active")

    archive_eligible_adrs(tmp_path)

    archive_dir = get_archive_dir(tmp_path)
    archived_files = sorted(p.name for p in archive_dir.glob("ADR-*.md"))
    assert archived_files == ["ADR-007-first-archived.md"]
    assert not list(archive_dir.glob("*.zip"))
    assert (tmp_path / "ADR-023-active.md").exists()

    records = {r["adr_number"]: r for r in load_adrs_index(tmp_path)}
    assert records["ADR-007"]["state"] == "archived"
    assert records["ADR-007"]["archive_member"] == "ADR-007-first-archived.md"


def test_extract_archived_adr_copies_plain_file(tmp_path):
    """ADR-811: extraction copies the plain archived .md to the destination."""
    from src.lib.adr_utils import archive_eligible_adrs, extract_archived_adr

    _write_adr(tmp_path, 7, "Implemented", "First Archived", "Body to extract.")
    archive_eligible_adrs(tmp_path)

    dest = tmp_path / "out"
    extracted = extract_archived_adr(tmp_path, 7, destination_dir=dest)
    assert extracted.name == "ADR-007-first-archived.md"
    assert "Body to extract." in extracted.read_text(encoding="utf-8")


def test_rebuild_archive_index_walks_plain_files(tmp_path):
    """ADR-811: rebuild regenerates archived entries from archive/*.md."""
    from src.lib.adr_utils import (
        archive_eligible_adrs,
        get_adrs_index_path,
        rebuild_archive_index,
        scan_adrs,
    )

    _write_adr(tmp_path, 7, "Implemented", "First Archived")
    _write_adr(tmp_path, 19, "Superseded", "Second Archived")
    archive_eligible_adrs(tmp_path)

    get_adrs_index_path(tmp_path).unlink()  # blow the index away
    rebuild_archive_index(tmp_path)

    numbers = sorted(a["number"] for a in scan_adrs(tmp_path) if a["archived"])
    assert numbers == [7, 19]


def test_extract_archived_adr_companions_only_no_primary(tmp_path):
    """ADR-811: records with no primary member (promoted-from-superpowers ADRs)
    still extract — the first available companion is returned."""
    from src.lib.adr_utils import extract_archived_adr, get_archive_dir, write_adrs_index

    archive_dir = get_archive_dir(tmp_path)
    archive_dir.mkdir(parents=True)
    spec_name = "ADR-042-spec.md"
    (archive_dir / spec_name).write_text("# Spec\n\nCompanion body.\n", encoding="utf-8")

    write_adrs_index(
        tmp_path,
        [
            {
                "adr_number": "ADR-042",
                "title": "Companions Only",
                "state": "archived",
                "status": "Implemented",
                "spec_member": spec_name,
                "plan_member": None,
            }
        ],
    )

    dest = tmp_path / "out"
    extracted = extract_archived_adr(tmp_path, 42, destination_dir=dest)
    assert extracted == dest / spec_name
    assert extracted.read_text(encoding="utf-8") == "# Spec\n\nCompanion body.\n"


def test_archive_eligible_adrs_is_idempotent(tmp_path):
    """ADR-811: a second archive sweep changes nothing — no duplicates, same index."""
    from src.lib.adr_utils import archive_eligible_adrs, get_adrs_index_path, get_archive_dir

    _write_adr(tmp_path, 7, "Implemented", "First Archived")

    archive_eligible_adrs(tmp_path)
    index_path = get_adrs_index_path(tmp_path)
    index_after_first = index_path.read_text(encoding="utf-8")

    archive_eligible_adrs(tmp_path)

    archive_dir = get_archive_dir(tmp_path)
    archived_files = sorted(p.name for p in archive_dir.glob("ADR-*.md"))
    assert archived_files == ["ADR-007-first-archived.md"]

    records = json.loads(index_path.read_text(encoding="utf-8"))
    entries_for_seven = [r for r in records if r.get("adr_number") == "ADR-007"]
    assert len(entries_for_seven) == 1

    assert index_path.read_text(encoding="utf-8") == index_after_first


def test_scan_adrs_reports_archive_member(tmp_path):
    from src.lib.adr_utils import archive_eligible_adrs, scan_adrs

    _write_adr(tmp_path, 7, "Implemented", "First Archived")
    archive_eligible_adrs(tmp_path)

    [record] = [a for a in scan_adrs(tmp_path) if a["number"] == 7]
    assert record["archived"] is True
    assert record["archive_member"] == "ADR-007-first-archived.md"
