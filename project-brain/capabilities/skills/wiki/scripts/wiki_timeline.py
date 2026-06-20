"""Compiled-truth and timeline helpers for wiki concept pages (ADR-740)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import re


COMPILED_TRUTH_HEADING = "Compiled truth"
TIMELINE_HEADING = "Timeline"
_H2_RE = re.compile(r"(?m)^## (?P<title>.+?)\s*$")
_ENTRY_RE = re.compile(r"(?m)^- _at: (?P<at>\S+)\s+_source: (?P<source>\S+)\s*$")
_URI_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:.+")


@dataclass(frozen=True)
class TimelineEntry:
    at: str
    source: str
    observation: str

    def __post_init__(self) -> None:
        if not _is_valid_iso_timestamp(self.at):
            raise ValueError("Timeline entry requires ISO _at")
        if not _is_valid_uri(self.source):
            raise ValueError("Timeline entry requires URI _source")
        if not self.observation.strip():
            raise ValueError("Timeline entry requires observation text")

    def render(self) -> str:
        lines = [f"- _at: {self.at.strip()}  _source: {self.source.strip()}"]
        for line in self.observation.strip().splitlines():
            lines.append(f"  {line.strip()}")
        return "\n".join(lines)


@dataclass(frozen=True)
class TimelineValidation:
    errors: list[str]
    warnings: list[str]


def _section_bounds(body: str, heading: str) -> tuple[int, int] | None:
    matches = list(_H2_RE.finditer(body))
    for index, match in enumerate(matches):
        if match.group("title").strip().lower() != heading.lower():
            continue
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        return start, end
    return None


def _replace_section(body: str, heading: str, content: str) -> str:
    bounds = _section_bounds(body, heading)
    replacement = f"## {heading}\n\n{content.strip()}\n"
    if bounds is None:
        return body.rstrip() + "\n\n" + replacement
    start, end = bounds
    return body[:start].rstrip() + "\n\n" + content.strip() + "\n" + body[end:]


def extract_compiled_truth(body: str) -> str:
    bounds = _section_bounds(body, COMPILED_TRUTH_HEADING)
    return body[bounds[0] : bounds[1]].strip() if bounds else ""


def extract_timeline(body: str) -> str:
    bounds = _section_bounds(body, TIMELINE_HEADING)
    return body[bounds[0] : bounds[1]].strip() if bounds else ""


def replace_compiled_truth(body: str, compiled_truth: str) -> str:
    return _replace_section(body, COMPILED_TRUTH_HEADING, compiled_truth).rstrip() + "\n"


def append_timeline_entries(body: str, entries: list[TimelineEntry]) -> str:
    if not entries:
        return body
    existing = extract_timeline(body)
    blocks = _timeline_blocks(existing)
    for entry in sorted(
        entries,
        key=lambda item: _parse_iso_timestamp(item.at) or datetime.min,
        reverse=True,
    ):
        entry_at = _parse_iso_timestamp(entry.at) or datetime.min
        insert_at = len(blocks)
        for index, block in enumerate(blocks):
            block_at = _timeline_sort_key(block, index)[0]
            if block_at is not None and block_at < entry_at:
                insert_at = index
                break
        blocks.insert(insert_at, entry.render())
    rendered = "\n\n".join(blocks)
    return _replace_section(body, TIMELINE_HEADING, rendered).rstrip() + "\n"


def validate_timeline_entries(body: str) -> TimelineValidation:
    timeline = extract_timeline(body)
    errors: list[str] = []
    warnings: list[str] = []
    seen_times: list[datetime] = []
    for block in _timeline_blocks(timeline):
        header, *observation_lines = block.splitlines()
        match = _ENTRY_RE.match(header)
        if match is None:
            errors.append("timeline_entry_missing_at_or_source")
            continue
        at = _parse_iso_timestamp(match.group("at"))
        if at is None or not _is_valid_uri(match.group("source")):
            errors.append("timeline_entry_missing_at_or_source")
            continue
        if not any(line.strip() for line in observation_lines):
            errors.append("timeline_entry_missing_observation")
        seen_times.append(at)
    if seen_times != sorted(seen_times, reverse=True):
        warnings.append("timeline_out_of_order")
    return TimelineValidation(errors=errors, warnings=warnings)


def _timeline_blocks(timeline: str) -> list[str]:
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in timeline.splitlines():
        if line.startswith("- "):
            if current:
                blocks.append(current)
            current = [line]
            continue
        if current:
            current.append(line)
    if current:
        blocks.append(current)
    return ["\n".join(block).strip() for block in blocks if "\n".join(block).strip()]


def _timeline_sort_key(block: str, index: int) -> tuple[datetime | None, int, str]:
    first_line = block.splitlines()[0] if block.splitlines() else ""
    match = _ENTRY_RE.match(first_line)
    at = _parse_iso_timestamp(match.group("at")) if match else None
    return at, index, block


def _is_valid_iso_timestamp(value: str) -> bool:
    return _parse_iso_timestamp(value) is not None


def _parse_iso_timestamp(value: str) -> datetime | None:
    text = value.strip()
    if "T" not in text:
        return None
    try:
        normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        return parsed.astimezone(UTC).replace(tzinfo=None)
    return parsed


def _is_valid_uri(value: str) -> bool:
    return bool(_URI_RE.match(value.strip()))
