"""Walk candidate roots, attach evidence, pre-fill manifest rows."""

from __future__ import annotations

from pathlib import Path

from src.lib.brain_classify.evidence import extract_brain_evidence
from src.lib.brain_classify.manifest import ManifestRow


def _target_for(source: Path, verdict: str, *, project_root: Path, vault_root: Path) -> str:
    """Default target path for a verdict. Concrete dest is refined in review."""
    name = source.name
    if verdict == "project":
        if "memory" in source.parts:
            return f"project-brain/knowledge/memory/entries/{name}"
        return f"project-brain/knowledge/wiki/concepts/{name}"
    if verdict == "venture":
        return f"Au-vault/venture/{name}"
    if verdict == "career":
        return f"Au-vault/career/{name}"
    # personal
    if "memory" in source.parts:
        return f"Au-vault/_augur/memory/entries/{name}"
    return f"Au-vault/wiki/concepts/{name}"


def collect_candidates(*, roots: list[Path], project_root: Path, vault_root: Path) -> list[ManifestRow]:
    rows: list[ManifestRow] = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.md")):
            if path.name in ("index.md", "overview.md", "README.md"):
                continue
            ev = extract_brain_evidence(path)
            if ev.subject_brain == "project":
                verdict, confidence = "project", "high" if ev.project_refs >= 2 else "medium"
            elif ev.subject_brain == "personal":
                # personal splits into personal/venture/career — deterministic guess
                # is "personal"; the AI pass refines to venture/career. Medium so
                # those refinements are reviewed.
                verdict, confidence = "personal", "medium"
            else:
                verdict, confidence = "personal", "low"
            try:
                source_rel = str(path.relative_to(project_root))
            except ValueError:
                source_rel = str(path)
            rows.append(
                ManifestRow(
                    source=source_rel,
                    verdict=verdict,
                    target=_target_for(path, verdict, project_root=project_root, vault_root=vault_root),
                    confidence=confidence,
                    rationale="; ".join(ev.signals[:4]) or "no artifact references",
                )
            )
    return rows
