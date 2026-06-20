"""
adr_utils._parse — ADR numbering, filename parsing, status normalisation,
and markdown file parsing helpers.

Internal use by the adr_utils package; do not import directly from outside.
"""

from __future__ import annotations

import re
from pathlib import Path

from src.lib.adr_utils._index import (
    _empty_impact,
    _extract_number,
    load_adrs_index,
)

# ---------------------------------------------------------------------------
# Numbering helpers
# ---------------------------------------------------------------------------


def find_next_adr_number(decisions_dir: Path) -> int:
    """Return the next available ADR number from the central JSON index.

    Falls back to scanning live ``ADR-*.md`` files for backward compatibility
    with environments that haven't been migrated yet.
    """
    decisions_dir = Path(decisions_dir)
    max_num = 0
    for record in load_adrs_index(decisions_dir):
        number = _extract_number(record.get("adr_number"))
        if number is not None and number > max_num:
            max_num = number
    # Backward-compat: also scan stray ADR-*.md files.
    if decisions_dir.is_dir():
        for f in decisions_dir.iterdir():
            match = re.match(r"ADR-(\d+)", f.name)
            if match:
                num = int(match.group(1))
                if num > max_num:
                    max_num = num
    return max_num + 1


# ---------------------------------------------------------------------------
# Filename parsing helpers
# ---------------------------------------------------------------------------


def parse_adr_number(name: str) -> int | None:
    """Extract the ADR number from a filename or stem string."""
    match = re.search(r"ADR-(\d+)", name, re.IGNORECASE)
    if not match:
        return None
    try:
        return int(match.group(1))
    except Exception:
        return None


def parse_adr_slug(name: str) -> str | None:
    """Extract the slug portion from an ADR filename."""
    match = re.search(r"ADR-\d+-(.+)\.md$", name, re.IGNORECASE)
    if not match:
        return None
    slug = match.group(1).strip().lower()
    if slug.endswith("-hardening"):
        slug = slug[: -len("-hardening")]
    return slug or None


# ---------------------------------------------------------------------------
# Status normalisation
# ---------------------------------------------------------------------------


def normalize_adr_status(raw: str) -> str:
    """Normalise a free-form ADR status string to a canonical value."""
    # Coerce non-string inputs (e.g. a numeric/bool status from malformed YAML
    # frontmatter) instead of raising AttributeError on .strip().
    stripped = str(raw or "").strip()
    lower = stripped.lower()

    if lower in ("in progress", "pending execution"):
        return "Accepted"
    if lower.startswith("partially implemented"):
        return "Accepted"
    if lower.startswith("accepted (phase 1"):
        return "Accepted"
    if lower.startswith("accepted (phases") and "implemented" in lower:
        return "Implemented"
    if lower.startswith("accepted (implemented"):
        return "Implemented"
    if lower.startswith("superseded"):
        return "Superseded"
    if lower.startswith("implemented"):
        return "Implemented"
    if stripped in ("Accepted", "Proposed", "Deprecated", "Cancelled", "Future"):
        return stripped

    return "Other"


# ---------------------------------------------------------------------------
# Canonical status set
# ---------------------------------------------------------------------------

CANONICAL_STATUSES = {"Proposed", "Accepted", "Implemented", "Deprecated", "Superseded", "Future", "Cancelled"}


# ---------------------------------------------------------------------------
# Internal markdown parsing helpers
# ---------------------------------------------------------------------------


def _first_prose_paragraph(body: str) -> str:
    in_body = False
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            in_body = True
            continue
        if not in_body or not stripped:
            continue
        if stripped.startswith("|") or stripped.startswith("-") or stripped.startswith("**"):
            continue
        return stripped
    return ""


def _record_from_adr_file(adr_path: Path) -> dict | None:
    """Parse a live ADR markdown file into a central-index entry.

    Kept for one-off migrations and for tests that still want to write a
    ``.md`` file and have it absorbed into the index. Production code should
    write entries directly via ``upsert_adr_entry``.
    """
    from src.lib.frontmatter_utils import parse_frontmatter

    number = parse_adr_number(adr_path.name)
    if number is None:
        return None

    try:
        meta, body = parse_frontmatter(adr_path)
    except OSError:
        return None

    title = ""
    for line in body.splitlines():
        if line.startswith("# "):
            title = re.sub(r"^ADR-\d+:\s*", "", line[2:].strip())
            break
    if not title:
        title = adr_path.stem

    raw_status = str(meta.get("status", ""))
    raw_date = str(meta.get("date", ""))
    if not raw_status or not raw_date:
        for line in body.splitlines()[:15]:
            if not raw_status:
                status_match = re.match(r"\*\*Status\*\*:?\s*(.*)", line)
                if not status_match:
                    status_match = re.match(r"\*\*Status:\*\*\s*(.*)", line)
                if status_match:
                    raw_status = status_match.group(1).strip()
            if not raw_date:
                date_match = re.match(r"\*\*Date\*\*:\s*(.*)", line)
                if not date_match:
                    date_match = re.match(r"\*\*Date:\*\*\s*(.*)", line)
                if date_match:
                    raw_date = date_match.group(1).strip()

    description = _first_prose_paragraph(body) or title
    return {
        "adr_number": f"ADR-{number:03d}",
        "title": title,
        "state": "live",
        "status": normalize_adr_status(raw_status),
        "date": raw_date,
        "deciders": list(meta.get("deciders") or []),
        "related": _normalize_related_field(meta.get("related")),
        "hub": meta.get("hub"),
        "tags": list(meta.get("tags") or []),
        "decision_summary": description[:300],
        "status_notes": "",
        "impact": _empty_impact(),
        "spec_file": meta.get("spec_file") or None,
        "plan_file": meta.get("plan_file") or None,
        "superseded_by": meta.get("superseded_by") or None,
        # Convenience fields used by tests that pre-date the migration:
        "_legacy_filename": adr_path.name,
        "_legacy_body": body,
    }


def _normalize_related_field(value) -> list[str]:
    if not value or not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        if isinstance(item, int):
            out.append(f"ADR-{item:03d}")
        elif isinstance(item, str):
            s = item.strip()
            if not s:
                continue
            m = re.match(r"ADR-?(\d+)", s, re.IGNORECASE)
            if m:
                out.append(f"ADR-{int(m.group(1)):03d}")
            elif s.isdigit():
                out.append(f"ADR-{int(s):03d}")
            else:
                out.append(s)
    return out


def _materialize_live_md(record: dict) -> bytes:
    """Render a live JSON entry into a plain ADR markdown file for the archive directory.

    The file keeps the standard frontmatter ``.md`` shape so extraction and
    scanning tools work without change.
    """
    import yaml as _yaml

    fm: dict = {
        "status": record.get("status") or "Implemented",
        "date": record.get("date") or "",
        "deciders": record.get("deciders") or [],
        "related": record.get("related") or [],
        "hub": record.get("hub"),
        "tags": record.get("tags") or [],
        "superseded_by": record.get("superseded_by"),
    }
    if record.get("spec_file"):
        fm["spec_file"] = record["spec_file"]
    if record.get("plan_file"):
        fm["plan_file"] = record["plan_file"]
    fm_text = _yaml.safe_dump(fm, sort_keys=False).strip()

    number = _extract_number(record.get("adr_number")) or 0
    title = record.get("title") or f"ADR-{number:03d}"
    decision = record.get("decision_summary") or ""
    status_notes = record.get("status_notes") or ""
    impact = record.get("impact") or _empty_impact()

    sections = [f"# ADR-{number:03d}: {title}", ""]
    if decision:
        sections.extend(["## Decision summary", "", decision, ""])
    if status_notes:
        sections.extend(["## Status notes", "", status_notes, ""])
    has_impact = any(impact.get(k) for k in ("paths_renamed", "apis_changed", "patterns_deprecated", "files_affected"))
    if has_impact:
        sections.extend(
            ["## Impact Manifest", "", "```yaml", _yaml.safe_dump(impact, sort_keys=False).strip(), "```", ""]
        )

    body = "\n".join(sections).rstrip() + "\n"
    return f"---\n{fm_text}\n---\n\n{body}".encode("utf-8")


def _slug_from_title(title: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (title or "").lower()).strip("-")
    return s or "untitled"


def _plain_member_for_record(record: dict) -> str:
    """Return the plain archive filename for an index-only ADR record (ADR-811)."""
    # Prefer existing archive_member if already set (idempotency).
    if record.get("archive_member"):
        return str(record["archive_member"])
    number = _extract_number(record.get("adr_number")) or 0
    title = record.get("title") or "untitled"
    return f"ADR-{number:03d}-{_slug_from_title(title)}.md"


def _merge_live_file_record_with_index(parsed_record: dict, indexed_record: dict | None) -> dict:
    """Preserve richer central-index metadata when archiving a live Markdown file."""
    if not indexed_record:
        return parsed_record

    merged = dict(indexed_record)
    for key in (
        "adr_number",
        "title",
        "state",
        "status",
        "date",
        "deciders",
        "related",
        "hub",
        "tags",
        "spec_file",
        "plan_file",
        "superseded_by",
    ):
        value = parsed_record.get(key)
        if value not in (None, "", []):
            merged[key] = value

    for key in ("decision_summary", "status_notes", "impact"):
        if not merged.get(key) and parsed_record.get(key):
            merged[key] = parsed_record[key]

    return merged
