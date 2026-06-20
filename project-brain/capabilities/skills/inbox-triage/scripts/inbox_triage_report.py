"""Render and persist the daily inbox-triage report."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def render_report(
    date_str: str,
    entries: list[dict[str, Any]],
    *,
    left_in_inbox: list[dict[str, Any]],
) -> str:
    """Render the daily triage report as Markdown."""
    lines = [
        f"# Inbox Triage — {date_str}",
        "",
        f"Filed {len(entries)} card(s); {len(left_in_inbox)} left in inbox.",
        "",
    ]
    if entries:
        lines.append("## Filed")
        lines.append("")
        for e in entries:
            flag = " _(created folder)_" if e.get("created_folder") else ""
            lines.append(
                f"- **{e.get('title', '?')}** → `{e.get('filed_to', '?')}`{flag} "
                f"— {e.get('reason', '')}"
            )
        lines.append("")
    if left_in_inbox:
        lines.append("## Left in inbox")
        lines.append("")
        for e in left_in_inbox:
            lines.append(f"- **{e.get('title', '?')}** — {e.get('reason', 'unresolved')}")
        lines.append("")
    return "\n".join(lines)


def write_report(
    output_root: Path,
    date_str: str,
    entries: list[dict[str, Any]],
    *,
    left_in_inbox: list[dict[str, Any]],
) -> str:
    """Write the report under ``<output_root>/inbox-triage/<date>.md``."""
    out_dir = Path(output_root) / "inbox-triage"
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{date_str}.md"
    target.write_text(render_report(date_str, entries, left_in_inbox=left_in_inbox),
                      encoding="utf-8")
    return str(target)
