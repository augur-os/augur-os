"""Gather retained `/ask` outcomes for later wiki compounding."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    from src.mcp.augur_shared.config import get_skill_data_dir
except ImportError:
    from src.config.paths import get_skill_data_dir
from src.config.paths import get_daily_logs_dir, get_project_brain_dir, get_runtime_dir
from src.lib.frontmatter_utils import parse_frontmatter

_SECTION_RE = re.compile(r"^## (?P<time>\d{2}:\d{2}) - (?P<kind>.+)$", re.MULTILINE)
_FIELD_RE = re.compile(r"^\*\*(?P<key>[^*]+)\*\*: (?P<value>.+)$", re.MULTILINE)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _clip(text: str, limit: int = 220) -> str:
    single = " ".join(text.split())
    if len(single) <= limit:
        return single
    return single[: limit - 1].rstrip() + "…"


def _extract_summary(body: str) -> str:
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        return _clip(stripped)
    return _clip(body)


def _parse_memory_sections(text: str) -> list[dict[str, Any]]:
    matches = list(_SECTION_RE.finditer(text))
    sections: list[dict[str, Any]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        block = text[start:end].strip()
        fields = {
            field.group("key").strip().lower(): field.group("value").strip() for field in _FIELD_RE.finditer(block)
        }
        sections.append(
            {
                "kind": match.group("kind").strip().lower(),
                "time": match.group("time"),
                "fields": fields,
                "body": block,
            }
        )
    return sections


def _load_recent_ask_syntheses(
    *,
    knowledge_dirs: list[Path],
    since: datetime,
    limit: int,
) -> list[dict[str, Any]]:
    outcomes: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    for knowledge_dir in knowledge_dirs:
        synth_dir = knowledge_dir / "syntheses"
        if not synth_dir.exists():
            continue
        for path in sorted(synth_dir.glob("*.md"), reverse=True):
            if path.name in seen_names:
                continue
            seen_names.add(path.name)
            meta, body = parse_frontmatter(path)
            tags = meta.get("tags", [])
            if "ask" not in tags:
                continue
            created = _parse_iso(meta.get("created")) or datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            if created < since:
                continue
            outcomes.append(
                {
                    "kind": "synthesis",
                    "question": meta.get("query") or meta.get("title") or path.stem,
                    "summary": _extract_summary(body),
                    "confidence": meta.get("confidence", "medium"),
                    "tags": tags,
                    "created": created.isoformat(),
                    "path": str(path),
                    "source_type": "synthesis",
                }
            )
    outcomes.sort(key=lambda item: item["created"], reverse=True)
    return outcomes[:limit]


def _load_recent_ask_memory_events(
    *,
    since: datetime,
    limit: int,
) -> list[dict[str, Any]]:
    daily_dir = get_daily_logs_dir()
    if not daily_dir.exists():
        return []

    outcomes: list[dict[str, Any]] = []
    for path in sorted(daily_dir.glob("*.md"), reverse=True):
        try:
            day = datetime.strptime(path.stem, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if day < since.replace(hour=0, minute=0, second=0, microsecond=0):
            continue
        text = path.read_text(encoding="utf-8")
        for section in _parse_memory_sections(text):
            fields = section["fields"]
            kind = section["kind"]
            created = datetime.fromisoformat(f"{path.stem}T{section['time']}:00+00:00")
            if created < since:
                continue
            if kind == "user preference":
                source = fields.get("source", "")
                if "/ask" not in source.lower():
                    continue
                outcomes.append(
                    {
                        "kind": "preference",
                        "question": fields.get("preference", "Preference"),
                        "summary": fields.get("value", ""),
                        "confidence": "high",
                        "tags": ["ask", "preference"],
                        "created": created.isoformat(),
                        "path": str(path),
                        "source_type": "memory",
                    }
                )
            elif kind == "decision":
                if fields.get("category", "").lower() != "ask":
                    continue
                outcomes.append(
                    {
                        "kind": "decision",
                        "question": fields.get("topic", "Decision"),
                        "summary": fields.get("decision", ""),
                        "confidence": fields.get("confidence", "medium").lower(),
                        "tags": ["ask", "decision"],
                        "created": created.isoformat(),
                        "path": str(path),
                        "source_type": "memory",
                    }
                )
            if len(outcomes) >= limit:
                break
        if len(outcomes) >= limit:
            break

    return outcomes


def _knowledge_dirs(runtime_dir: Path) -> list[Path]:
    candidates = [
        runtime_dir / "knowledge",
        get_project_brain_dir() / "knowledge",
        get_skill_data_dir("knowledge"),
    ]
    result: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            resolved = candidate
        if resolved in seen:
            continue
        result.append(candidate)
        seen.add(resolved)
    return result


def load_recent_ask_outcomes(*, days_back: int = 7, limit: int = 20) -> list[dict[str, Any]]:
    """Return recent retained `/ask` outcomes for compounding flows."""
    since = datetime.now(tz=timezone.utc) - timedelta(days=max(days_back, 0))
    runtime_dir = get_runtime_dir()

    outcomes = _load_recent_ask_syntheses(
        knowledge_dirs=_knowledge_dirs(runtime_dir),
        since=since,
        limit=limit,
    )
    remaining = max(limit - len(outcomes), 0)
    if remaining:
        outcomes.extend(
            _load_recent_ask_memory_events(
                since=since,
                limit=remaining,
            )
        )

    outcomes.sort(key=lambda item: item["created"], reverse=True)
    return outcomes[:limit]
