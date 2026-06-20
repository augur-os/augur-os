"""One-shot migration: ADR archive zips -> plain markdown (ADR-811).

Extracts every member of project-brain/decisions/adrs/archive/archived-adrs-*.zip into the
archive directory as plain files, rewrites adrs-index.json entries from
zip_path/zip_member to archive_member, verifies counts, then deletes the zips.
"""
from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config.paths import get_adr_dir
from src.lib.adr_utils import get_archive_dir, load_adrs_index, scan_adrs, write_adrs_index


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    decisions_dir = get_adr_dir()
    archive_dir = get_archive_dir(decisions_dir)
    zips = sorted(archive_dir.glob("archived-adrs-*.zip"))
    if not zips:
        print("No archive zips found — nothing to migrate.")
        return 0

    before = scan_adrs(decisions_dir)
    before_total, before_archived = len(before), sum(1 for a in before if a["archived"])
    print(f"before: total={before_total} archived={before_archived} zips={len(zips)}")

    extracted: set[str] = set()
    for zip_path in zips:
        with zipfile.ZipFile(zip_path, "r") as zf:
            for member in zf.namelist():
                name = Path(member).name
                if not name or member.endswith("/"):
                    continue
                if Path(member).is_absolute() or ".." in Path(member).parts:
                    raise SystemExit(f"unsafe member {member!r} in {zip_path.name}")
                target = archive_dir / name
                if name in extracted or target.exists():
                    existing = target.read_bytes() if target.exists() else b""
                    if existing and existing != zf.read(member):
                        raise SystemExit(f"collision with different content: {name}")
                    continue
                if not args.dry_run:
                    target.write_bytes(zf.read(member))
                extracted.add(name)
    print(f"extracted {len(extracted)} members")

    records = load_adrs_index(decisions_dir)
    rewritten = 0
    for record in records:
        if record.get("state") != "archived":
            continue
        member = str(record.get("zip_member") or "").strip()
        if member:
            record["archive_member"] = Path(member).name
        for key in ("zip_path", "zip_member"):
            record.pop(key, None)
        for key in ("spec_member", "plan_member"):
            value = str(record.get(key) or "").strip()
            if value:
                record[key] = Path(value).name
        rewritten += 1
    if not args.dry_run:
        write_adrs_index(decisions_dir, records)
    print(f"rewrote {rewritten} archived index entries")

    after = scan_adrs(decisions_dir)
    after_total, after_archived = len(after), sum(1 for a in after if a["archived"])
    print(f"after: total={after_total} archived={after_archived}")
    if (after_total, after_archived) != (before_total, before_archived):
        raise SystemExit("COUNT MISMATCH — investigate before deleting zips")

    missing = [
        a["number"]
        for a in after
        if a["archived"] and a["archive_member"] and not (archive_dir / a["archive_member"]).is_file()
    ]
    if missing:
        raise SystemExit(f"archived entries without on-disk body: {missing[:10]} ...")

    if not args.dry_run:
        for zip_path in zips:
            zip_path.unlink()
        print(f"deleted {len(zips)} zips")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
