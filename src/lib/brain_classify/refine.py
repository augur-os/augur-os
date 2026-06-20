"""Refine non-high-confidence manifest rows via a pluggable classifier.

The classifier itself is the one AI step in the cleanup; it is invoked at
execution time (an agent per gray-zone row). This harness is deterministic and
unit-tested around a pluggable ``classify_fn`` so the orchestration is testable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from src.lib.brain_classify.evidence import extract_brain_evidence
from src.lib.brain_classify.manifest import ManifestRow

ClassifyFn = Callable[[Path, str, tuple, ManifestRow], dict]


def refine_rows(rows: list[ManifestRow], *, classify_fn: ClassifyFn, root: Path) -> list[ManifestRow]:
    refined: list[ManifestRow] = []
    for row in rows:
        if row.confidence == "high":
            refined.append(row)
            continue
        path = Path(row.source) if Path(row.source).is_absolute() else (root / row.source)
        try:
            body = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            body = ""
        ev = extract_brain_evidence(path)
        verdict = classify_fn(path, body, ev.signals, row)
        refined.append(
            ManifestRow(
                source=row.source,
                verdict=verdict.get("verdict", row.verdict),
                target=verdict.get("target", row.target),
                confidence=verdict.get("confidence", row.confidence),
                rationale=verdict.get("rationale", row.rationale),
            )
        )
    return refined
