"""ADR creation for adaptive loop centralized issue inventory.

Generates ADR documents from pending issue scans across all adaptive loops.
"""
from __future__ import annotations


import importlib.util as _augur_importlib_util
import sys as _augur_sys
from pathlib import Path as _AugurPath

_augur_bootstrap_start = _AugurPath(__file__).resolve()
for _augur_bootstrap_parent in (_augur_bootstrap_start.parent, *_augur_bootstrap_start.parents):
    _augur_bootstrap_path = _augur_bootstrap_parent / "daemon" / "scripts" / "bootstrap_paths.py"
    if _augur_bootstrap_path.is_file():
        break
else:
    raise RuntimeError(f"Unable to locate shared skill bootstrap from {_augur_bootstrap_start}")

_augur_bootstrap_spec = _augur_importlib_util.spec_from_file_location(
    "_augur_shared_bootstrap_paths", _augur_bootstrap_path
)
if _augur_bootstrap_spec is None or _augur_bootstrap_spec.loader is None:
    raise RuntimeError(f"Unable to load shared skill bootstrap from {_augur_bootstrap_path}")
_augur_bootstrap_module = _augur_importlib_util.module_from_spec(_augur_bootstrap_spec)
_augur_sys.modules[_augur_bootstrap_spec.name] = _augur_bootstrap_module
_augur_bootstrap_spec.loader.exec_module(_augur_bootstrap_module)
_augur_bootstrap_module.ensure_project_paths(__file__)
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _next_adr_number(project_root: Path) -> int:
    """Return next ADR number using the central index (ADR-642)."""
    from src.lib.adr_utils import find_next_adr_number, get_adr_dir
    decisions_dir = get_adr_dir()
    decisions_dir.mkdir(parents=True, exist_ok=True)
    return find_next_adr_number(decisions_dir)


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return re.sub(r"-{2,}", "-", slug)


def _severity_rank(severity: str) -> int:
    ranks = {"error": 0, "warning": 1, "info": 2}
    return ranks.get(str(severity).lower(), 3)


def create_centralized_adr(
    project_root: Path,
    pending: list[dict[str, Any]],
    total_issues: int,
) -> Path:
    """Create a centralized ADR summarizing all pending issues."""
    adr_num = _next_adr_number(project_root)
    today = datetime.now(timezone.utc).date().isoformat()
    title = f"ADR-{adr_num:03d}: Centralized Ops-Loops Issue Inventory ({today})"
    slug = _slugify(f"ops-loops-centralized-issue-inventory-{today}")
    from src.config.paths import get_runtime_dir
    from src.lib.adr_utils import get_adr_dir as _get_adr_dir
    decisions_dir = _get_adr_dir()
    # ADR-642: stage the body in runtime extracts; durable record lives in the
    # central JSON index (added at the end of this function).
    runtime_dir = get_runtime_dir() / "adr-extracts" / f"ADR-{adr_num:03d}"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    adr_path = runtime_dir / f"ADR-{adr_num:03d}-{slug}.md"

    loop_totals: dict[str, int] = {}
    for row in pending:
        loop_totals[row["loop"]] = loop_totals.get(row["loop"], 0) + int(row["count"])

    top_commands = sorted(
        pending,
        key=lambda r: (
            -int(r["count"]),
            _severity_rank(str(r.get("severity", "info"))),
            int(r.get("tier", 0)),
            str(r.get("command", "")),
        ),
    )[:20]
    first_wave = [
        row
        for row in sorted(
            pending,
            key=lambda r: (
                _severity_rank(str(r.get("severity", "info"))),
                -int(r.get("count", 0)),
                int(r.get("tier", 0)),
                str(r.get("command", "")),
            ),
        )
        if int(row.get("count", 0)) > 0
    ][:5]
    unique_loops = len({r["loop"] for r in pending})

    lines = [
        f"# {title}",
        "",
        f"- Status: Proposed",
        f"- Date: {today}",
        f"- Deciders: Observability / Daemon maintainers",
        (
            "- Source Command: "
            "`python project-brain/capabilities/skills/daemon/scripts/adaptive_loop_executor.py "
            "pending --create-adr`"
        ),
        "",
        "## Context",
        "",
        "`/routines pending --create-adr` produced a cross-loop scan snapshot of pending findings.",
        "",
        "This ADR captures that snapshot as a temporary centralized planning artifact for",
        "cross-loop prioritization and sequencing. It does not replace decentralized ownership",
        "of scan/fix logic in plugin auto-commands.",
        "",
        "## Summary",
        "",
        f"- Total pending issues: {total_issues}",
        f"- Total pending fixes: {total_issues}",
        f"- Loops scanned: {unique_loops}",
        f"- Commands scanned: {len(pending)}",
        "",
        "### Per-Loop Totals",
        "",
        "| Loop | Pending Issues | Share |",
        "|------|----------------|-------|",
    ]
    for loop_name in sorted(loop_totals):
        count = loop_totals[loop_name]
        share = (count / total_issues * 100.0) if total_issues > 0 else 0.0
        lines.append(f"| {loop_name} | {count} | {share:.1f}% |")

    lines.extend(
        [
            "",
            "### Top Commands By Pending Count",
            "",
            "| Loop | Command | Tier | Trigger | Issues | Severity |",
            "|------|---------|------|---------|--------|----------|",
        ]
    )
    for row in top_commands:
        lines.append(
            f"| {row['loop']} | {row['command']} | {row['tier']} | "
            f"{row['trigger']} | {row['count']} | {row['severity']} |"
        )

    lines.extend(
        [
            "",
            "## Decision",
            "",
            "Use this centralized inventory as a short-lived coordination artifact for",
            "cross-loop triage and remediation sequencing.",
            "",
            "Keep implementation decentralized:",
            "- each auto-command remains owned and fixed in its plugin,",
            "- loop behavior remains configured via `config/system/adaptive_loops.yaml`,",
            "- regenerate this ADR when snapshot drift becomes material.",
            "",
            "## Prioritization Policy",
            "",
            "Apply remediation in this order:",
            "1. `severity=error` commands with highest issue count.",
            "2. Commands causing runtime failures or loader skips.",
            "3. High-volume `warning` commands that degrade nightly signal quality.",
            "4. `info` items after error/warning backlog stabilizes.",
            "",
            "First wave for this snapshot:",
        "",
        ]
    )
    if first_wave:
        for idx, row in enumerate(first_wave, start=1):
            lines.append(
                f"{idx}. `{row['loop']}/{row['command']}` "
                f"({row['count']}, {row['severity']})"
            )
    else:
        lines.append("1. No pending issues in this snapshot.")

    lines.extend(
        [
            "",
            "## Consequences",
            "",
            "### Positive",
            "- Single, comparable view across loops and triggers.",
            "- Faster cross-loop prioritization for nightly remediation.",
            "",
            "### Negative",
            "- Snapshot staleness: counts drift as fixes land.",
            "",
            "### Neutral",
            "- Plugin-first architecture and command ownership remain unchanged.",
            "",
            "## Alternatives Considered",
            "",
            "### Alternative 1: Loop-local only (no centralized ADR)",
            "Rejected: high friction for cross-loop risk comparison.",
            "",
            "### Alternative 2: Permanent centralized backlog file",
            "Rejected: central drift risk and ownership ambiguity.",
            "",
            "## Operational Workflow",
            "",
            "1. Generate snapshot with `--pending --create-adr`.",
            "2. Execute fixes in owning plugins/commands.",
            "3. Re-run pending scan.",
            "4. Regenerate ADR if counts shift materially.",
            "",
            "## Regeneration",
            "",
            "Regenerate via:",
            "`python project-brain/capabilities/skills/daemon/scripts/adaptive_loop_executor.py --pending --create-adr`",
            "",
            "## References",
            "",
            "- `project-brain/capabilities/skills/daemon/commands/routines.md`",
            "- `project-brain/capabilities/skills/daemon/scripts/adaptive/discovery.py`",
            "- `config/system/adaptive_loops.yaml`",
            "- ADR-176 (Adaptive Loop Engine)",
            "- ADR-200 (scan-fix auto-command protocol/discovery)",
            "",
        ]
    )

    adr_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Persist a stub entry in the central JSON index (ADR-642). The full body
    # remains in runtime extracts for human review and promotion.
    try:
        from src.lib.adr_utils import upsert_adr_entry

        upsert_adr_entry(
            decisions_dir,
            {
                "adr_number": f"ADR-{adr_num:03d}",
                "title": f"Centralized Ops-Loops Issue Inventory ({today})",
                "state": "live",
                "status": "Proposed",
                "date": today,
                "deciders": ["Observability / Daemon maintainers"],
                "related": ["ADR-176", "ADR-200"],
                "hub": "adaptive",
                "tags": ["ops-loops", "inventory"],
                "decision_summary": (
                    f"Centralized snapshot of {total_issues} pending issues across "
                    f"{len({r['loop'] for r in pending})} loops."
                ),
                "status_notes": "",
                "impact": {
                    "paths_renamed": [],
                    "apis_changed": [],
                    "patterns_deprecated": [],
                    "files_affected": [],
                },
                "spec_file": None,
                "plan_file": None,
                "superseded_by": None,
            },
        )
    except Exception:
        # Index write is advisory; the body file is the authoritative artifact.
        pass

    return adr_path
