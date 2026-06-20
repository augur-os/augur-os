"""Dry-run-first concept page migration for ADR-740."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
import difflib
import re
from typing import Any

import yaml

from src.lib.frontmatter_utils import (
    merge_vault_frontmatter,
    parse_frontmatter,
    write_frontmatter,
)


V3_COMPILER_VERSION = "concept-article-v3"
V4_COMPILER_VERSION = "concept-article-v4"
_EVIDENCE_HEADING = "## Evidence"
_H2_PREFIX = "## "
_H3_PREFIX = "### "
_EVIDENCE_BULLET_RE = re.compile(r"^- `(?P<source>[^`]+)`: (?P<observation>.+?)\s*$")


@dataclass(frozen=True)
class MigrationResult:
    changed_pages: list[Path]
    diffs: dict[str, str]
    backup_dir: Path | None = None
    skipped_pages: list[Path] = field(default_factory=list)
    warnings: dict[str, str] = field(default_factory=dict)


class UnsafeMigrationError(ValueError):
    """Raised when a page cannot be migrated without dropping evidence."""


def migrate_concept_page_text(raw: str, *, fallback_updated: str) -> str:
    """Migrate one v3 concept page string to the ADR-740 v4 layout."""
    metadata, body, has_frontmatter = _parse_raw_frontmatter(raw)
    migrated_metadata, migrated_body = _migrate_parts(
        metadata,
        body,
        fallback_updated=fallback_updated,
    )
    if not has_frontmatter:
        return migrated_body
    return _render_frontmatter_text(migrated_metadata, migrated_body)


def migrate_wiki_dir(
    wiki_dir: Path,
    runtime_dir: Path,
    apply: bool = False,
) -> MigrationResult:
    """Dry-run or apply the v3-to-v4 migration for eligible concept pages."""
    wiki_root = Path(wiki_dir)
    runtime_root = Path(runtime_dir)
    changed_pages: list[Path] = []
    skipped_pages: list[Path] = []
    diffs: dict[str, str] = {}
    warnings: dict[str, str] = {}
    planned_writes: list[tuple[Path, str, dict[str, Any], str]] = []

    for page in sorted(wiki_root.rglob("*.md")):
        if _is_relative_to(page, runtime_root):
            continue
        metadata, body = parse_frontmatter(page, include_sidecar_config=False)
        if not _is_v3_concept(metadata):
            continue

        original = page.read_text(encoding="utf-8")
        fallback_updated = _page_fallback_timestamp(page, metadata)
        try:
            migrated_metadata, migrated_body = _migrate_parts(
                metadata,
                body,
                fallback_updated=fallback_updated,
            )
        except UnsafeMigrationError as exc:
            skipped_pages.append(page)
            warnings[str(page)] = str(exc)
            continue
        final_metadata = merge_vault_frontmatter(metadata, migrated_metadata)
        migrated = _render_frontmatter_text(final_metadata, migrated_body)
        if migrated == original:
            continue

        changed_pages.append(page)
        diffs[str(page)] = _unified_diff(page, original, migrated)
        planned_writes.append((page, original, final_metadata, migrated_body))

    backup_dir: Path | None = None
    if apply and planned_writes:
        backup_dir = (
            runtime_root
            / "garbage_collector"
            / f"wiki-pre-740-{_backup_timestamp()}"
        )
        for page, original, final_metadata, migrated_body in planned_writes:
            backup_path = backup_dir / page.relative_to(wiki_root)
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            backup_path.write_text(original, encoding="utf-8")
            write_frontmatter(page, final_metadata, migrated_body)

    return MigrationResult(
        changed_pages=changed_pages,
        diffs=diffs,
        backup_dir=backup_dir,
        skipped_pages=skipped_pages,
        warnings=warnings,
    )


def _is_v3_concept(metadata: dict[str, Any]) -> bool:
    return (
        str(metadata.get("page_type") or "").strip() == "concept"
        and str(metadata.get("compiler_version") or "").strip() == V3_COMPILER_VERSION
    )


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _migrate_parts(
    metadata: dict[str, Any],
    body: str,
    *,
    fallback_updated: str,
) -> tuple[dict[str, Any], str]:
    migrated_metadata = dict(metadata)
    if "_compiler_version" in migrated_metadata:
        migrated_metadata["_compiler_version"] = V4_COMPILER_VERSION
        migrated_metadata.pop("compiler_version", None)
    else:
        migrated_metadata["compiler_version"] = V4_COMPILER_VERSION

    entry_timestamp = _metadata_timestamp(metadata) or _normalize_timestamp(fallback_updated)
    if entry_timestamp is None:
        raise UnsafeMigrationError("migration_timestamp_invalid")
    compiled_lines, timeline_blocks = _extract_compiled_truth_and_timeline(
        body,
        entry_timestamp=entry_timestamp,
    )
    migrated_body = _render_v4_body(compiled_lines, timeline_blocks)
    return migrated_metadata, migrated_body


def _extract_compiled_truth_and_timeline(
    body: str,
    *,
    entry_timestamp: str,
) -> tuple[list[str], list[str]]:
    compiled: list[str] = []
    evidence_lines: list[str] = []
    in_evidence = False

    for line in body.splitlines():
        if line.strip() == _EVIDENCE_HEADING:
            in_evidence = True
            continue
        if in_evidence and line.startswith(_H2_PREFIX):
            in_evidence = False
        if in_evidence:
            evidence_lines.append(line)
            continue
        if line.startswith(_H2_PREFIX):
            compiled.append(f"{_H3_PREFIX}{line[len(_H2_PREFIX):]}")
            continue
        compiled.append(line)

    timeline = _evidence_lines_to_timeline(
        evidence_lines,
        entry_timestamp=entry_timestamp,
    )
    return compiled, timeline


def _evidence_lines_to_timeline(
    lines: list[str],
    *,
    entry_timestamp: str,
) -> list[str]:
    timeline: list[str] = []
    current: list[str] = []
    for line in lines:
        if not line.strip():
            continue
        if line.lstrip().startswith("- "):
            if current:
                timeline.append(
                    _evidence_block_to_timeline(
                        current,
                        entry_timestamp=entry_timestamp,
                    )
                )
            current = [line]
            continue
        if current and line.startswith((" ", "\t")):
            current.append(line)
            continue
        raise UnsafeMigrationError(f"unparsed_evidence_line: {line.strip()}")
    if current:
        timeline.append(_evidence_block_to_timeline(current, entry_timestamp=entry_timestamp))
    return timeline


def _evidence_block_to_timeline(block: list[str], *, entry_timestamp: str) -> str:
    first_line = block[0].strip() if block else ""
    match = _EVIDENCE_BULLET_RE.match(first_line)
    if match is None:
        raise UnsafeMigrationError(f"unparsed_evidence_line: {first_line}")
    source = match.group("source").strip()
    observation_lines = [match.group("observation").strip()]
    observation_lines.extend(line.strip() for line in block[1:] if line.strip())
    observation = " ".join(observation_lines).strip()
    if not source or not observation:
        raise UnsafeMigrationError(f"unparsed_evidence_line: {first_line}")
    return f"- _at: {entry_timestamp}  _source: {source}\n  {observation}"


def _render_v4_body(compiled_lines: list[str], timeline_blocks: list[str]) -> str:
    preamble, truth_lines = _split_preamble(compiled_lines)
    sections: list[str] = []
    if preamble:
        sections.append(preamble)
    sections.append("## Compiled truth\n\n" + "\n".join(truth_lines).strip())
    timeline = "\n\n".join(timeline_blocks).strip()
    sections.append("## Timeline" + (f"\n\n{timeline}" if timeline else ""))
    return "\n\n".join(section.rstrip() for section in sections).strip() + "\n"


def _split_preamble(lines: list[str]) -> tuple[str, list[str]]:
    for index, line in enumerate(lines):
        if line.startswith(_H3_PREFIX):
            return "\n".join(lines[:index]).strip(), lines[index:]
    return "", lines


def _page_fallback_timestamp(page: Path, metadata: dict[str, Any]) -> str:
    return _metadata_timestamp(metadata) or _file_mtime_timestamp(page)


def _metadata_timestamp(metadata: dict[str, Any]) -> str | None:
    for key in ("updated", "_updated", "created", "_created"):
        timestamp = _normalize_timestamp(metadata.get(key))
        if timestamp is not None:
            return timestamp
    return None


def _normalize_timestamp(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _render_datetime_timestamp(value)
    if isinstance(value, date):
        return f"{value.isoformat()}T00:00:00Z"
    text = str(value).strip()
    if not text:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return f"{text}T00:00:00Z"
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    rendered = _render_datetime_timestamp(parsed)
    return rendered if "T" in rendered else f"{rendered}T00:00:00Z"


def _file_mtime_timestamp(path: Path) -> str:
    return _render_datetime_timestamp(datetime.fromtimestamp(path.stat().st_mtime, UTC))


def _render_datetime_timestamp(value: datetime) -> str:
    if value.tzinfo is not None:
        value = value.astimezone(UTC)
        return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return value.replace(microsecond=0).isoformat() + "Z"


def _parse_raw_frontmatter(raw: str) -> tuple[dict[str, Any], str, bool]:
    if not raw.startswith("---"):
        return {}, raw, False
    end = raw.find("\n---", 4)
    if end == -1:
        return {}, raw, False
    yaml_block = raw[4:end]
    body = raw[end + 4 :]
    if body.startswith("\n"):
        body = body[1:]
    try:
        metadata = yaml.safe_load(yaml_block) or {}
    except yaml.YAMLError:
        return {}, raw, False
    if not isinstance(metadata, dict):
        return {}, raw, False
    return metadata, body, True


def _render_frontmatter_text(metadata: dict[str, Any], body: str) -> str:
    yaml_text = yaml.dump(
        dict(metadata),
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    ).rstrip("\n")
    content = "\n".join(["---", yaml_text, "---", "", body.rstrip(), ""])
    return content


def _unified_diff(page: Path, original: str, migrated: str) -> str:
    return "".join(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            migrated.splitlines(keepends=True),
            fromfile=str(page),
            tofile=str(page),
        )
    )


def _backup_timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
