#!/usr/bin/env python3
"""One-shot migration: build the central ``project-brain/decisions/adrs/adrs-index.json`` from the
existing live ADR ``.md`` files and the legacy
``project-brain/decisions/adrs/archive/archived-adrs-index.json``.

After this runs the user is expected to delete the live ``.md`` files (the
script also generates a ``git rm`` plan as stdout). The new schema is
described in ADR-642 (central ADR index, no per-file markdown).

Run:
    python3 scripts/migrate_adr_central_index.py
    python3 scripts/migrate_adr_central_index.py --apply  # also git-rm the .md

⚠️  DANGER — DO NOT RE-RUN IN A POPULATED REPO  ⚠️
This script is a ONE-SHOT migration, not a repeatable rebuild. It writes
``adrs-index.json`` from scratch using ONLY (a) the legacy
``archived-adrs-index.json`` sidecar and (b) the live ADR ``.md`` files
on disk. If the legacy sidecar is missing or stale (which it now is —
all archived ADR data lives in ``adrs-index.json`` itself), running this
script silently DESTROYS the archived rows in the central JSON.

For repeatable upsert of live ADR .md files into the central JSON
without touching archived rows, use ``.github/scripts/adr_upsert_live.py``
instead. That script is idempotent and is the canonical step 1 of the
``/adr`` command's post-write hook.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import yaml  # noqa: E402

ADR_DIR = PROJECT_ROOT / "docs" / "adrs"
ARCHIVE_DIR = ADR_DIR / "archive"
LEGACY_INDEX = ARCHIVE_DIR / "archived-adrs-index.json"
NEW_INDEX = ADR_DIR / "adrs-index.json"

DECISION_HEADINGS = (
    "## Decision summary",
    "## Decision Summary",
    "## Decision",
    "## Summary",
)
STATUS_HEADINGS = (
    "## Status notes",
    "## Status Notes",
    "## Status",
)
IMPACT_HEADINGS = (
    "## Impact Manifest",
    "## Impact",
)


def _section_text(body: str, headings: tuple[str, ...]) -> str:
    """Return the prose under the first matching heading (until next ## heading)."""
    lines = body.splitlines()
    start = None
    for i, line in enumerate(lines):
        if any(line.strip().startswith(h) for h in headings):
            start = i + 1
            break
    if start is None:
        return ""
    out: list[str] = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        out.append(line)
    return "\n".join(out).strip()


def _first_paragraph(text: str) -> str:
    for block in text.split("\n\n"):
        cleaned = block.strip()
        if not cleaned:
            continue
        if cleaned.startswith("```") or cleaned.startswith("|"):
            continue
        # Strip leading list markers
        cleaned = re.sub(r"^[-*]\s+", "", cleaned, flags=re.MULTILINE)
        return cleaned
    return ""


def _truncate_decision_summary(text: str, max_chars: int = 300) -> str:
    para = _first_paragraph(text) or text
    para = re.sub(r"\s+", " ", para).strip()
    if len(para) <= max_chars:
        return para
    return para[:max_chars].rsplit(" ", 1)[0] + "..."


def _impact_manifest(body: str) -> dict:
    """Pull a YAML/JSON-ish impact manifest if the ADR has one, else empty dict."""
    section = _section_text(body, IMPACT_HEADINGS)
    if not section:
        return {
            "paths_renamed": [],
            "apis_changed": [],
            "patterns_deprecated": [],
            "files_affected": [],
        }
    # Look for a fenced YAML block under the heading.
    m = re.search(r"```(?:yaml|yml)?\n(.*?)```", section, re.DOTALL)
    if m:
        try:
            parsed = yaml.safe_load(m.group(1)) or {}
            if isinstance(parsed, dict):
                return {
                    "paths_renamed": parsed.get("paths_renamed", []) or [],
                    "apis_changed": parsed.get("apis_changed", []) or [],
                    "patterns_deprecated": parsed.get("patterns_deprecated", []) or [],
                    "files_affected": parsed.get("files_affected", []) or [],
                }
        except yaml.YAMLError:
            pass
    return {
        "paths_renamed": [],
        "apis_changed": [],
        "patterns_deprecated": [],
        "files_affected": [],
    }


def _normalize_status(raw: str) -> str:
    """Map free-form status to canonical."""
    stripped = (raw or "").strip()
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


def _normalize_related(value) -> list[str]:
    if not value:
        return []
    if not isinstance(value, list):
        return []
    out = []
    for item in value:
        if isinstance(item, int):
            out.append(f"ADR-{item:03d}")
        elif isinstance(item, str):
            s = item.strip()
            if not s:
                continue
            if s.upper().startswith("ADR-"):
                m = re.match(r"ADR-?(\d+)", s, re.IGNORECASE)
                if m:
                    out.append(f"ADR-{int(m.group(1)):03d}")
                else:
                    out.append(s)
            elif s.isdigit():
                out.append(f"ADR-{int(s):03d}")
            else:
                out.append(s)
    return out


def _normalize_superseded_by(value) -> str | None:
    if not value:
        return None
    if isinstance(value, int):
        return f"ADR-{value:03d}"
    if isinstance(value, str):
        s = value.strip()
        if not s or s.lower() == "null":
            return None
        m = re.match(r"ADR-?(\d+)", s, re.IGNORECASE)
        if m:
            return f"ADR-{int(m.group(1)):03d}"
        if s.isdigit():
            return f"ADR-{int(s):03d}"
        return s
    return None


def _adr_number_from_filename(name: str) -> int | None:
    m = re.match(r"ADR-(\d+)", name, re.IGNORECASE)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def _parse_live_adr(adr_path: Path) -> dict | None:
    number = _adr_number_from_filename(adr_path.name)
    if number is None:
        return None
    raw = adr_path.read_text(encoding="utf-8")
    meta: dict = {}
    body = raw
    if raw.startswith("---"):
        end = raw.find("\n---", 4)
        if end != -1:
            try:
                parsed = yaml.safe_load(raw[4:end]) or {}
                if isinstance(parsed, dict):
                    meta = parsed
            except yaml.YAMLError:
                meta = {}
            body = raw[end + 4:].lstrip("\n")

    title = ""
    for line in body.splitlines():
        if line.startswith("# "):
            title = re.sub(r"^ADR-\d+:\s*", "", line[2:].strip())
            break
    if not title:
        title = adr_path.stem

    raw_status = str(meta.get("status", ""))
    decision = _section_text(body, DECISION_HEADINGS)
    decision_summary = _truncate_decision_summary(decision) if decision else _truncate_decision_summary(body)
    status_notes_raw = _section_text(body, STATUS_HEADINGS)
    status_notes = re.sub(r"\s+", " ", status_notes_raw).strip()

    return {
        "adr_number": f"ADR-{number:03d}",
        "title": title,
        "state": "live",
        "status": _normalize_status(raw_status),
        "date": str(meta.get("date", "")),
        "deciders": list(meta.get("deciders") or []),
        "related": _normalize_related(meta.get("related")),
        "hub": meta.get("hub"),
        "tags": list(meta.get("tags") or []),
        "decision_summary": decision_summary,
        "status_notes": status_notes,
        "impact": _impact_manifest(body),
        "spec_file": meta.get("spec_file") or None,
        "plan_file": meta.get("plan_file") or None,
        "superseded_by": _normalize_superseded_by(meta.get("superseded_by")),
    }


def _convert_archived_entry(entry: dict) -> dict:
    """Convert a legacy archived-adrs-index.json entry to the new schema."""
    number_str = str(entry.get("adr_number", "")).strip()
    title = str(entry.get("title") or "")
    status = _normalize_status(str(entry.get("status") or "Implemented"))
    date = str(entry.get("date") or "")
    hub = entry.get("hub")
    tags_raw = entry.get("tags") or []
    tags = [str(t) for t in tags_raw if str(t).strip()] if isinstance(tags_raw, list) else []
    description = str(entry.get("description") or "")
    decision_summary = _truncate_decision_summary(description) if description else ""

    return {
        "adr_number": number_str,
        "title": title,
        "state": "archived",
        "status": status,
        "date": date,
        "deciders": [],
        "related": [],
        "hub": hub,
        "tags": tags,
        "decision_summary": decision_summary,
        "status_notes": "",
        "impact": {
            "paths_renamed": [],
            "apis_changed": [],
            "patterns_deprecated": [],
            "files_affected": [],
        },
        "spec_file": entry.get("spec_member") or None,
        "plan_file": entry.get("plan_member") or None,
        "superseded_by": None,
        "zip_path": entry.get("zip") or "",
        "zip_member": entry.get("archive_member") or "",
        "spec_member": entry.get("spec_member") or None,
        "plan_member": entry.get("plan_member") or None,
    }


def build_central_index() -> tuple[list[dict], list[Path]]:
    archived = []
    if LEGACY_INDEX.exists():
        try:
            archived = json.loads(LEGACY_INDEX.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            archived = []

    archived_records = [_convert_archived_entry(e) for e in archived if isinstance(e, dict)]

    live_files = sorted(ADR_DIR.glob("ADR-*.md"))
    live_records: list[dict] = []
    for path in live_files:
        record = _parse_live_adr(path)
        if record:
            live_records.append(record)

    # Combine; live wins on conflicts.
    by_number: dict[str, dict] = {}
    for r in archived_records:
        by_number[r["adr_number"]] = r
    for r in live_records:
        by_number[r["adr_number"]] = r

    combined = sorted(by_number.values(), key=lambda r: r["adr_number"])
    return combined, live_files


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="git rm the live ADR .md files and the legacy archived-adrs-index.json")
    args = parser.parse_args()

    records, live_files = build_central_index()

    NEW_INDEX.write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {NEW_INDEX} with {len(records)} entries.")
    n_live = sum(1 for r in records if r["state"] == "live")
    n_archived = sum(1 for r in records if r["state"] == "archived")
    print(f"  live: {n_live}")
    print(f"  archived: {n_archived}")
    print(f"  live .md files folded: {len(live_files)}")

    if args.apply:
        # git rm live .md files (keep TEMPLATE.md) and the legacy archived-adrs-index.json
        targets: list[str] = [str(p.relative_to(PROJECT_ROOT)) for p in live_files]
        if LEGACY_INDEX.exists():
            targets.append(str(LEGACY_INDEX.relative_to(PROJECT_ROOT)))
        if not targets:
            print("Nothing to git-rm.")
            return 0
        # Run `git rm` in batches.
        cmd = ["git", "rm", "--", *targets]
        result = subprocess.run(cmd, cwd=PROJECT_ROOT)
        if result.returncode != 0:
            return result.returncode
        print(f"git-rm'd {len(targets)} file(s).")
    else:
        print("\nDry-run: pass --apply to git-rm the live .md files and legacy archive index.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
