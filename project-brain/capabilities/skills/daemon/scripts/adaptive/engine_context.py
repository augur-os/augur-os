"""Targeted context collection for adaptive loop fixes.

The collector follows the approved escalation order:
1. local code and nearby docs
2. loop implementation references
3. ADRs
4. wiki pages
5. recent loop reports and ledger-derived loop history

Mechanical issues stay context-free. Local-semantic issues stay local unless
intent is ambiguous. Structural issues escalate through the full stack.
"""
from __future__ import annotations


import importlib.util as _augur_importlib_util
import sys as _augur_sys
from pathlib import Path as _AugurPath

_augur_bootstrap_start = _AugurPath(__file__).resolve()
for _augur_bootstrap_parent in (_augur_bootstrap_start.parent, *_augur_bootstrap_start.parents):
    _augur_bootstrap_path = _augur_bootstrap_parent / "daemon" / "scripts" / "bootstrap_paths.py"
    if _augur_bootstrap_path.is_file():
        break
else:
    raise RuntimeError(f"Unable to locate shared skill bootstrap from {_augur_bootstrap_start}")

_augur_bootstrap_spec = _augur_importlib_util.spec_from_file_location(
    "_augur_shared_bootstrap_paths", _augur_bootstrap_path
)
if _augur_bootstrap_spec is None or _augur_bootstrap_spec.loader is None:
    raise RuntimeError(f"Unable to load shared skill bootstrap from {_augur_bootstrap_path}")
_augur_bootstrap_module = _augur_importlib_util.module_from_spec(_augur_bootstrap_spec)
_augur_sys.modules[_augur_bootstrap_spec.name] = _augur_bootstrap_module
_augur_bootstrap_spec.loader.exec_module(_augur_bootstrap_module)
_augur_bootstrap_module.ensure_project_paths(__file__)
import json
import re
from pathlib import Path
from typing import Any

from src.config.paths import get_adr_dir, get_compiled_wiki_dir, get_runtime_dir
from src.lib.frontmatter_utils import parse_frontmatter

from .engine_quality import LOCAL_SEMANTIC, MECHANICAL, STRUCTURAL, classify_finding_band
from routine_orchestrator.ledger_view import LedgerJournalReader

_LOCAL_DOC_NAMES = ("README.md", "README.mdx", "NOTES.md", "docs.md")
_LOOP_REFERENCE_PATHS = (
    Path("project-brain/capabilities/skills/daemon/references/routines-implementation.md"),
    Path("project-brain/capabilities/skills/daemon/commands/routines.md"),
)


def _build_journal_reader(runtime_dir: Path):
    del runtime_dir
    return LedgerJournalReader()


def collect_context(
    *,
    issue: dict[str, Any],
    project_root: Path,
    loop_name: str,
    adr_dir: Path | None = None,
    wiki_dir: Path | None = None,
    runtime_dir: Path | None = None,
    max_sources_per_kind: int = 1,
) -> dict[str, Any]:
    """Return a deterministic context bundle for a fix attempt."""
    finding_band = classify_finding_band(issue)
    if finding_band == MECHANICAL:
        return _empty_bundle(finding_band, loop_name, project_root)

    terms = _context_terms(issue, loop_name)
    sources: list[dict[str, Any]] = []

    sources.extend(
        _collect_local_sources(
            issue=issue,
            terms=terms,
            project_root=project_root,
            limit=max_sources_per_kind,
        )
    )
    sources.extend(
        _collect_loop_references(
            terms=terms,
            project_root=project_root,
            limit=max_sources_per_kind,
        )
    )

    if finding_band == STRUCTURAL:
        resolved_adr_dir = Path(adr_dir) if adr_dir is not None else get_adr_dir()
        resolved_wiki_dir = Path(wiki_dir) if wiki_dir is not None else get_compiled_wiki_dir()
        resolved_runtime_dir = (
            Path(runtime_dir) if runtime_dir is not None else get_runtime_dir() / "adaptive"
        )
        sources.extend(
            _collect_markdown_sources(
                resolved_adr_dir,
                kind="adr",
                terms=terms,
                project_root=project_root,
                limit=max_sources_per_kind,
            )
        )
        sources.extend(
            _collect_markdown_sources(
                resolved_wiki_dir,
                kind="wiki",
                terms=terms,
                project_root=project_root,
                limit=max_sources_per_kind,
            )
        )
        sources.extend(
            _collect_runtime_sources(
                runtime_dir=resolved_runtime_dir,
                loop_name=loop_name,
                project_root=project_root,
                limit=max_sources_per_kind,
            )
        )

    return {
        "finding_band": finding_band,
        "loop_name": loop_name,
        "project_root": str(project_root),
        "sources": sources,
    }


def _empty_bundle(finding_band: str, loop_name: str, project_root: Path) -> dict[str, Any]:
    return {
        "finding_band": finding_band,
        "loop_name": loop_name,
        "project_root": str(project_root),
        "sources": [],
    }


def _context_terms(issue: dict[str, Any], loop_name: str) -> list[str]:
    candidates: list[str] = [loop_name]
    for key in ("path", "detail", "message", "summary", "reason", "title", "name"):
        value = issue.get(key)
        if isinstance(value, str) and value.strip():
            candidates.append(value)

    terms: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        for token in re.split(r"[^a-zA-Z0-9]+", candidate.lower()):
            if len(token) < 4 or token in seen:
                continue
            seen.add(token)
            terms.append(token)
    return terms


def _collect_local_sources(
    *,
    issue: dict[str, Any],
    terms: list[str],
    project_root: Path,
    limit: int,
) -> list[dict[str, Any]]:
    if limit <= 0:
        return []

    path_value = str(issue.get("path") or "").strip()
    if not path_value:
        return []

    issue_path = project_root / path_value
    if not issue_path.is_file():
        return []

    sources: list[dict[str, Any]] = [
        _read_text_source(issue_path, kind="local-code", terms=terms, project_root=project_root)
    ]
    parent = issue_path.parent
    for name in _LOCAL_DOC_NAMES:
        doc_path = parent / name
        if doc_path.is_file():
            sources.append(
                _read_text_source(doc_path, kind="local-doc", terms=terms, project_root=project_root)
            )
            break
    return sources[:limit + 1]


def _collect_loop_references(
    *,
    terms: list[str],
    project_root: Path,
    limit: int,
) -> list[dict[str, Any]]:
    if limit <= 0:
        return []

    sources: list[dict[str, Any]] = []
    for rel_path in _LOOP_REFERENCE_PATHS:
        abs_path = project_root / rel_path
        if not abs_path.is_file():
            continue
        sources.append(
            _read_text_source(abs_path, kind="loop-reference", terms=terms, project_root=project_root)
        )
        if len(sources) >= limit:
            break
    return sources


def _collect_markdown_sources(
    directory: Path,
    *,
    kind: str,
    terms: list[str],
    project_root: Path,
    limit: int,
) -> list[dict[str, Any]]:
    if limit <= 0 or not directory.is_dir():
        return []

    fallback: dict[str, Any] | None = None
    matches: list[dict[str, Any]] = []
    for md_path in sorted(directory.glob("*.md")):
        source = _read_text_source(md_path, kind=kind, terms=terms, project_root=project_root)
        if fallback is None:
            fallback = source
        if source["match_score"] > 0:
            matches.append(source)
            if len(matches) >= limit:
                break

    return _strip_match_score(matches or ([fallback] if fallback else []), limit)


def _collect_runtime_sources(
    *,
    runtime_dir: Path,
    loop_name: str,
    project_root: Path,
    limit: int,
) -> list[dict[str, Any]]:
    if limit <= 0:
        return []

    sources: list[dict[str, Any]] = []
    report_path = runtime_dir / "reports" / f"{loop_name}-latest.json"
    if report_path.is_file():
        try:
            payload = json.loads(report_path.read_text(encoding="utf-8"))
            summary = str(payload.get("summary") or payload.get("loop_name") or loop_name)
            excerpt = str(payload.get("next_actions") or payload.get("highlights") or summary)
            sources.append(
                {
                    "kind": "recent-report",
                    "path": _relative_label(report_path, project_root),
                    "title": f"{loop_name} latest report",
                    "excerpt": str(excerpt)[:180],
                }
            )
        except (OSError, json.JSONDecodeError):
            pass

    try:
        reader = _build_journal_reader(runtime_dir)
        for entry in reversed(reader.read_all()):
            if entry.loop != loop_name:
                continue
            excerpt = f"{entry.result}:{entry.action} {entry.category}".strip()
            if entry.error:
                excerpt = f"{excerpt} — {entry.error}"
            sources.append(
                {
                    "kind": "recent-ledger",
                    "path": _relative_label(runtime_dir.parent / "jobs", project_root),
                    "title": f"{loop_name} recent ledger history",
                    "excerpt": excerpt[:180],
                }
            )
            break
    except Exception:
        pass

    return sources[:limit + 1]


def _read_text_source(
    path: Path,
    *,
    kind: str,
    terms: list[str],
    project_root: Path,
) -> dict[str, Any]:
    if path.suffix.lower() == ".md":
        meta, body = parse_frontmatter(path)
        title = str(meta.get("title") or path.stem)
        labels = [path.name.lower(), path.stem.lower(), title.lower(), body.lower()]
        for value in meta.values():
            if isinstance(value, str):
                labels.append(value.lower())
            elif isinstance(value, list):
                labels.extend(str(item).lower() for item in value)
        content = body
    else:
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            content = ""
        title = path.name
        labels = [path.name.lower(), path.stem.lower(), content.lower()]

    score = sum(1 for term in terms if any(term in label for label in labels))
    return {
        "kind": kind,
        "path": _relative_label(path, project_root),
        "title": title,
        "excerpt": _build_excerpt(content, terms),
        "match_score": score,
    }


def _build_excerpt(body: str, terms: list[str], max_chars: int = 180) -> str:
    if not body:
        return ""

    lowered = body.lower()
    for term in terms:
        idx = lowered.find(term)
        if idx >= 0:
            start = max(0, idx - 60)
            end = min(len(body), idx + len(term) + 120)
            excerpt = " ".join(body[start:end].split())
            return excerpt if len(excerpt) <= max_chars else excerpt[: max_chars - 3].rstrip() + "..."

    excerpt = " ".join(body.split())
    return excerpt if len(excerpt) <= max_chars else excerpt[: max_chars - 3].rstrip() + "..."


def _relative_label(path: Path, project_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root.resolve()))
    except Exception:
        return str(path)


def _strip_match_score(items: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for item in items[:limit]:
        cleaned.append(
            {
                "kind": item["kind"],
                "path": item["path"],
                "title": item["title"],
                "excerpt": item["excerpt"],
            }
        )
    return cleaned
