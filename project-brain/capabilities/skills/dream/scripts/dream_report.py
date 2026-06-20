"""Dream-cycle report writer + last-report reader (ADR-744 task 6).

Consolidates per-phase results into a dated Markdown report under
``<output_root>/<YYYY-MM-DD>.md``. The MCP wrapper resolves ``output_root``
from ``get_documents_machine_dir("reports") / "dream"`` (per the skill's
``config.yaml: report.output_dir``); tests pass an arbitrary tmp path.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

_REPORT_NAME_RE = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2})\.md$")


def dream_report_write(
    *,
    phase_results: dict[str, Any],
    run_date: date | None = None,
    output_root: Path,
) -> Path:
    """Render the per-phase results to ``<output_root>/<YYYY-MM-DD>.md``.

    Same-day re-writes overwrite (idempotent within a day). The report is a
    human-readable Markdown digest; programmatic consumers should read the
    ADR-743 ledger directly via ``dream-status``.
    """
    if run_date is None:
        run_date = datetime.now(timezone.utc).date()
    output_root.mkdir(parents=True, exist_ok=True)
    report_path = output_root / f"{run_date.isoformat()}.md"
    report_path.write_text(_render(phase_results, run_date), encoding="utf-8")
    return report_path


def dream_last_report(*, output_root: Path) -> dict[str, str | None]:
    """Return the most recent report under ``output_root``.

    Returns ``{"date": "YYYY-MM-DD", "path": "<abs path>"}`` or
    ``{"date": None, "path": None}`` if there are no reports yet.
    """
    if not output_root.is_dir():
        return {"date": None, "path": None}
    dated: list[tuple[str, Path]] = []
    for candidate in output_root.iterdir():
        if not candidate.is_file():
            continue
        match = _REPORT_NAME_RE.match(candidate.name)
        if not match:
            continue
        dated.append((match.group("date"), candidate))
    if not dated:
        return {"date": None, "path": None}
    dated.sort(key=lambda pair: pair[0], reverse=True)
    latest_date, latest_path = dated[0]
    return {"date": latest_date, "path": str(latest_path)}


# ----------------------------------------------------------------------------
# Renderer
# ----------------------------------------------------------------------------


def _render(phase_results: dict[str, Any], run_date: date) -> str:
    lines: list[str] = [f"# Dream Cycle Report — {run_date.isoformat()}", ""]

    job_id = phase_results.get("job_id")
    if job_id:
        lines.append(f"_Run id (ADR-743 ledger): `{job_id}`_")
        lines.append("")

    phases = phase_results.get("phases", [])
    if not phases:
        lines.append("_No phase results captured._")
        return "\n".join(lines) + "\n"

    summary_lines = ["## Summary", ""]
    summary_lines.append("| Phase | Kind | State | Count |")
    summary_lines.append("|---|---|---|---|")
    for phase in phases:
        count = _count_for_summary(phase)
        summary_lines.append(
            f"| `{phase.get('id', '?')}` | {phase.get('kind', '?')} | "
            f"{phase.get('state', '?')} | {count} |"
        )
    summary_lines.append("")

    lines.extend(summary_lines)

    for phase in phases:
        lines.extend(_render_phase(phase))

    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _render_phase(phase: dict[str, Any]) -> list[str]:
    phase_id = phase.get("id", "?")
    state = phase.get("state", "?")
    lines = [f"## {phase_id}", "", f"**state:** {state}", ""]

    if state == "failed":
        error = phase.get("error", "(no error message)")
        lines.append(f"**error:** {error}")
        lines.append("")
        return lines

    result = phase.get("result") or {}
    if phase_id == "orphans":
        items = result.get("flagged", [])
        lines.append(f"**flagged:** {len(items)}")
        lines.append("")
        for item in items:
            lines.append(
                f"- [[{item['slug']}]] — {item['inbound_edges']} inbound edges, "
                f"{item['timeline_entries']} timeline entries"
            )
        lines.append("")
    elif phase_id == "stale-pages":
        items = result.get("flagged", [])
        lines.append(f"**flagged:** {len(items)}")
        lines.append("")
        for item in items:
            lines.append(
                f"- [[{item['slug']}]] — gap: {item['gap_days']} days "
                f"(compiled {item['last_compiled_at']}, latest timeline {item['latest_timeline_at']})"
            )
        lines.append("")
    elif phase_id == "merge-candidates":
        items = result.get("candidates", [])
        lines.append(f"**candidates:** {len(items)}")
        lines.append("")
        for item in items:
            lines.append(
                f"- [[{item['left_slug']}]] ↔ [[{item['right_slug']}]] — "
                f"jaccard {item['jaccard']}, shared {item['shared_tokens']}"
            )
        lines.append("")
    elif phase_id == "dead-citations":
        items = result.get("flagged", [])
        lines.append(f"**flagged:** {len(items)}")
        lines.append("")
        for item in items:
            lines.append(
                f"- [[{item['page_slug']}]] — `{item['source_uri']}` "
                f"({item['scheme']}, {item['reason']}, at {item['timeline_at']})"
            )
        lines.append("")
    elif phase_id == "cache-gc":
        purged = result.get("purged", [])
        lines.append(f"**purged:** {len(purged)} files, "
                     f"{result.get('bytes_freed', 0)} bytes")
        lines.append("")
        for path in purged:
            lines.append(f"- `{path}`")
        lines.append("")
    elif phase_id == "tier-recompute":
        lines.append(f"**entities tiered:** {result.get('entities', 0)}")
        lines.append("")
    else:
        # Unknown / judgment phases — dump the result raw so nothing is silently dropped.
        lines.append("```json")
        lines.append(_json_dump(result))
        lines.append("```")
        lines.append("")

    return lines


def _count_for_summary(phase: dict[str, Any]) -> str:
    if phase.get("state") == "failed":
        return "—"
    result = phase.get("result") or {}
    for key in ("flagged", "candidates", "purged"):
        if isinstance(result.get(key), list):
            return str(len(result[key]))
    if "entities" in result:
        return str(result["entities"])
    return "—"


def _json_dump(obj: Any) -> str:
    import json

    return json.dumps(obj, indent=2, default=str)


__all__ = ["dream_report_write", "dream_last_report"]
