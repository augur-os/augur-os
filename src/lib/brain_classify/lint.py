"""Cross-brain contamination lint (drift guard)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.lib.brain_classify.evidence import extract_brain_evidence


@dataclass(frozen=True)
class Finding:
    path: str
    host: str  # "personal" | "project"
    subject: str  # evidence subject_brain
    rationale: str


def _scan(roots: list[Path], host: str) -> list[Finding]:
    out: list[Finding] = []
    for root in roots:
        if not root.is_dir():
            continue
        for md in sorted(root.rglob("*.md")):
            if md.name in ("index.md", "overview.md", "README.md"):
                continue
            ev = extract_brain_evidence(md)
            # only flag a confident disagreement
            if ev.subject_brain != "ambiguous" and ev.subject_brain != host:
                out.append(Finding(str(md), host, ev.subject_brain, "; ".join(ev.signals[:3])))
    return out


def scan_contamination(*, personal_roots: list[Path], project_roots: list[Path]) -> list[Finding]:
    return _scan(personal_roots, "personal") + _scan(project_roots, "project")
