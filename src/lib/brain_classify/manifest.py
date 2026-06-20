"""Reviewable classification manifest for the brain-separation cleanup."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import yaml

VALID_VERDICTS = {"project", "venture", "career", "personal"}
VALID_CONFIDENCE = {"high", "medium", "low"}


@dataclass
class ManifestRow:
    source: str  # repo-relative path under its brain root
    verdict: str  # project | venture | career | personal
    target: str  # repo-relative destination path
    confidence: str  # high | medium | low
    rationale: str  # one-line evidence summary


def write_manifest(path: Path, rows: list[ManifestRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"schema": "brain.cleanup.manifest.v1", "rows": [asdict(r) for r in rows]}
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")


def read_manifest(path: Path) -> list[ManifestRow]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return [ManifestRow(**row) for row in data.get("rows", [])]


def validate_manifest(rows: list[ManifestRow]) -> list[str]:
    errors: list[str] = []
    for r in rows:
        if r.verdict not in VALID_VERDICTS:
            errors.append(f"{r.source}: invalid verdict {r.verdict!r}")
        if not r.target:
            errors.append(f"{r.source}: empty target")
        if r.confidence not in VALID_CONFIDENCE:
            errors.append(f"{r.source}: invalid confidence {r.confidence!r}")
    return errors


def sort_for_review(rows: list[ManifestRow]) -> list[ManifestRow]:
    """Low-confidence rows first so the reviewer sees the risky calls up top."""
    rank = {"low": 0, "medium": 1, "high": 2}
    return sorted(rows, key=lambda r: (rank.get(r.confidence, 1), r.source))
