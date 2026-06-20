#!/usr/bin/env python3
"""Upsert all live ADR ``.md`` files into the central ``adrs-index.json``.

Idempotent. Reads every ``project-brain/decisions/adrs/ADR-NNN-*.md`` file, parses its YAML
frontmatter + section bodies via the same parser the one-shot migration
uses, and upserts each into the central index via ``adr_utils``. Archived
entries (state="archived") are preserved untouched — this script only
inserts/updates rows where ``state="live"``.

Run:
    python .github/scripts/adr_upsert_live.py

Part of the ``/adr`` post-write hook contract (see
``project-brain/capabilities/skills/augur-core/commands/adr.md``).
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from migrate_adr_central_index import _parse_live_adr  # noqa: E402
from src.lib.adr_utils import get_adr_dir, load_adrs_index, upsert_adr_entry  # noqa: E402


def main() -> int:
    adr_dir = get_adr_dir()
    before = len(load_adrs_index(adr_dir))
    upserted = 0
    skipped = 0
    for adr_path in sorted(adr_dir.glob("ADR-*.md")):
        if adr_path.name == "TEMPLATE.md":
            continue
        record = _parse_live_adr(adr_path)
        if record is None:
            skipped += 1
            continue
        upsert_adr_entry(adr_dir, record)
        upserted += 1
    after = len(load_adrs_index(adr_dir))
    print(f"Live ADRs upserted: {upserted} (skipped: {skipped})")
    print(f"Central index size: {before} -> {after}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
