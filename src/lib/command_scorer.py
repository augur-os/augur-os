"""Command quality scorer used by Browse enrichment.

Plain library module. No LLM calls; pure functions over command markdown,
capability exposure policy, and best-effort command KPI aggregates.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

import yaml

from src.config.paths import get_project_root

DOCS_WEIGHT = 0.60
WIRING_WEIGHT = 0.40
_CACHE: dict[str, Any] = {}
_CACHE_TS = 0.0
_CACHE_TTL = 60.0


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    try:
        frontmatter = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        frontmatter = {}
    return (frontmatter if isinstance(frontmatter, dict) else {}), parts[2]


def score_docs(md_text: str) -> float:
    """Score a command's documentation quality on a 0-100 scale."""
    frontmatter, body = _split_frontmatter(md_text)
    description = str(frontmatter.get("description", "") or "")
    desc_words = len(description.split()) if description.strip() else 0
    lines = body.strip().split("\n") if body.strip() else []
    body_lines = len(lines)
    sections = len(re.findall(r"^#{1,3}\s+", body, re.MULTILINE))

    desc_score = (
        25 if desc_words >= 20 else 15 if desc_words >= 10 else 8 if desc_words >= 5 else 3 if desc_words else 0
    )
    body_score = (
        30 if body_lines >= 60 else 22 if body_lines >= 30 else 15 if body_lines >= 8 else 5 if body_lines >= 4 else 0
    )
    section_score = 20 if sections >= 4 else 14 if sections >= 2 else 8 if sections >= 1 else 0

    has_usage = bool(re.search(r"(?i)^#{1,3}\s+(usage|dispatch|arguments?)", body, re.MULTILINE))
    has_examples = bool(re.search(r"(?i)(example|```)", body))
    has_contract = bool(re.search(r"(?i)(argument|\$ARGUMENTS|--help|sub-?command)", body))
    richness = sum([10 if has_usage else 0, 10 if has_examples else 0, 5 if has_contract else 0])

    return float(min(100, desc_score + body_score + section_score + richness))


def score_wiring(entry: dict[str, Any] | None, *, file_exists: bool) -> float:
    """Score a command's policy wiring and source-file presence on a 0-100 scale."""
    score = 0.0
    if entry is not None:
        score += 40.0
        if str(entry.get("classification_status", "")).lower() == "approved":
            score += 25.0
        export_to = entry.get("export_to") or []
        if isinstance(export_to, list) and export_to:
            score += 20.0
    if file_exists:
        score += 15.0
    return float(min(100.0, score))


def blend_score(docs: float, wiring: float) -> float:
    """Blend docs and wiring dimensions into the overall command health score."""
    return round(docs * DOCS_WEIGHT + wiring * WIRING_WEIGHT, 1)


def score_to_tier(score: float) -> str:
    """Map a numeric command health score to the Browse quality tier."""
    if score >= 80:
        return "A"
    if score >= 65:
        return "B"
    if score >= 45:
        return "C"
    if score >= 25:
        return "D"
    return "F"


def kpi_status_map(*, documents_dir: Path | None = None) -> dict[str, str]:
    """Load best-effort per-command KPI status from the latest aggregate report."""
    if documents_dir is None:
        from src.config.paths import get_documents_machine_dir

        reports = get_documents_machine_dir("evals") / "commands" / "reports"
    else:
        # documents_dir is a test-supplied base; machine outputs live under _augur/
        reports = Path(documents_dir) / "_augur" / "evals" / "commands" / "reports"
    try:
        aggregates = sorted(reports.glob("*-aggregate.json"), key=lambda path: path.stat().st_mtime)
    except OSError:
        return {}
    if not aggregates:
        return {}
    try:
        data = json.loads(aggregates[-1].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    statuses: dict[str, str] = {}
    for command_id, stats in (data.get("by_command") or {}).items():
        if not isinstance(stats, dict) or int(stats.get("total") or 0) <= 0:
            continue
        statuses[str(command_id)] = "fail" if int(stats.get("fail") or 0) > 0 else "pass"
    return statuses


def _load_capability_command_entries() -> dict[str, dict[str, Any]]:
    path = get_project_root() / "config" / "system" / "capability_exposure.yaml"
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}

    capabilities = data.get("capabilities", data) if isinstance(data, dict) else {}
    entries: dict[str, dict[str, Any]] = {}
    if not isinstance(capabilities, dict):
        return entries

    for key, value in capabilities.items():
        if isinstance(key, str) and key.startswith("command:") and isinstance(value, dict):
            entries[key.split("command:", 1)[1].rstrip(":")] = value
    return entries


def score_command(command: Any, entry: dict[str, Any] | None, kpi: dict[str, str]) -> dict[str, Any]:
    """Score one discovered command and return Browse-ready score metadata."""
    path = getattr(command, "path", None)
    md_text = ""
    file_exists = False
    if path is not None:
        try:
            md_text = Path(path).read_text(encoding="utf-8")
            file_exists = True
        except OSError:
            file_exists = False

    docs = score_docs(md_text) if md_text else (15.0 if getattr(command, "description", "") else 0.0)
    wiring = score_wiring(entry, file_exists=file_exists)
    overall = blend_score(docs, wiring)
    command_id = str(getattr(command, "id", ""))
    return {
        "id": command_id,
        "score": overall,
        "tier": score_to_tier(overall),
        "dimensions": {"docs": round(docs, 1), "wiring": round(wiring, 1)},
        "kpiStatus": kpi.get(command_id, "untested"),
    }


def score_all_commands() -> dict[str, Any]:
    """Score every discovered command, cached for the current process."""
    global _CACHE, _CACHE_TS
    if _CACHE and time.time() - _CACHE_TS < _CACHE_TTL:
        return _CACHE

    from src.plugins.command_discovery import discover_commands

    entries = _load_capability_command_entries()
    kpi = kpi_status_map()
    scored: list[dict[str, Any]] = []
    for command in discover_commands():
        try:
            scored.append(score_command(command, entries.get(command.id), kpi))
        except Exception:
            continue

    scored.sort(key=lambda item: item["id"])
    tier_distribution: dict[str, int] = {}
    for item in scored:
        tier_distribution[item["tier"]] = tier_distribution.get(item["tier"], 0) + 1
    average_score = round(sum(item["score"] for item in scored) / max(len(scored), 1), 1)
    _CACHE = {
        "commands": scored,
        "summary": {
            "total": len(scored),
            "tier_distribution": tier_distribution,
            "average_score": average_score,
        },
    }
    _CACHE_TS = time.time()
    return _CACHE
