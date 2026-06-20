#!/usr/bin/env python3
"""Generate ADR Index — imports scan logic from adr_utils."""

import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.lib.adr_utils import get_adr_dir, scan_adrs  # noqa: E402
from src.lib.generated_artifacts import write_stable_text  # noqa: E402

DECISIONS_DIR = get_adr_dir()
OUTPUT = PROJECT_ROOT / "docs" / "generated" / "adr-index.md"
STATUS_ORDER = [
    "Implemented",
    "Accepted",
    "Proposed",
    "Future",
    "Superseded",
    "Deprecated",
    "Cancelled",
    "Other",
]


def generate_markdown(adrs: list[dict]) -> str:
    """Generate the ADR index markdown."""
    status_counts = Counter(a["status"] for a in adrs)
    summary_parts = [f"{status_counts[s]} {s}" for s in STATUS_ORDER if status_counts.get(s)]

    lines = [
        "# ADR Index",
        "",
        f"> Auto-generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}. Do not hand-edit.",
        "",
        f"**{len(adrs)} ADRs**: {', '.join(summary_parts)}",
        "",
        "## Status Summary",
        "",
        "| Status | Count | ADRs |",
        "|--------|-------|------|",
    ]

    for s in STATUS_ORDER:
        count = status_counts.get(s, 0)
        if not count:
            continue
        adr_nums = sorted(a["number"] for a in adrs if a["status"] == s)
        adr_list = ", ".join(f"ADR-{n:03d}" for n in adr_nums)
        lines.append(f"| {s} | {count} | {adr_list} |")

    lines.extend(["", "## Full Index", "", "| ADR | Title | Status | Date | Hub |", "|-----|-------|--------|------|-----|"])

    for a in adrs:
        adr_ref = f"ADR-{a['number']:03d}"
        hub = a.get("hub") or ""
        lines.append(f"| {adr_ref} | {a['title']} | {a['status']} | {a['date']} | {hub} |")

    lines.append("")
    return "\n".join(lines)


def main() -> int:
    adrs = scan_adrs(DECISIONS_DIR)
    if not adrs:
        if OUTPUT.exists():
            print(
                f"No ADRs found in {DECISIONS_DIR}; keeping existing "
                f"{OUTPUT.relative_to(PROJECT_ROOT)}"
            )
        else:
            content = generate_markdown([])
            write_stable_text(
                OUTPUT,
                content,
                volatile_line_prefixes=["> Auto-generated on "],
            )
            print(
                f"No ADRs found in {DECISIONS_DIR}; generated empty "
                f"{OUTPUT.relative_to(PROJECT_ROOT)}"
            )
        return 0
    content = generate_markdown(adrs)
    wrote = write_stable_text(
        OUTPUT,
        content,
        volatile_line_prefixes=["> Auto-generated on "],
    )
    action = "Generated" if wrote else "Unchanged"
    print(f"{action} {OUTPUT.relative_to(PROJECT_ROOT)} ({len(adrs)} ADRs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
