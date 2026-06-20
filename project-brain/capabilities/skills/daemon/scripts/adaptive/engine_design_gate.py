"""Design-gate artifact writer for structural adaptive fixes."""

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
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config.paths import get_runtime_dir
from src.lib.adr_utils import find_next_adr_number, get_adr_dir
from src.lib.frontmatter_utils import write_frontmatter


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return re.sub(r"-{2,}", "-", slug)


def _issue_summary(issue: dict[str, Any]) -> str:
    for key in ("detail", "message", "summary", "title"):
        value = issue.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "structural change requires a design gate"


def _context_source_kinds(context: dict[str, Any]) -> list[str]:
    sources = context.get("sources") or []
    kinds: list[str] = []
    for source in sources:
        if isinstance(source, dict):
            kind = source.get("kind")
            if isinstance(kind, str) and kind and kind not in kinds:
                kinds.append(kind)
    return kinds


def _runtime_note_path(loop_name: str, issue: dict[str, Any]) -> Path:
    runtime_dir = get_runtime_dir() / "adaptive" / "design-gates"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    issue_slug = _slugify(_issue_summary(issue)) or "design-gate"
    return runtime_dir / f"{_slugify(loop_name)}-{issue_slug}.md"


def _adr_note_path(loop_name: str, issue: dict[str, Any]) -> Path:
    """Return a runtime path for the ADR-style design gate artifact.

    ADR-642 retired per-file ADR markdown in ``docs/adrs/`` (now ``project-brain/decisions/adrs/`` per ADR-811). The design gate
    still writes a markdown stub for human review, but stores it under the
    runtime dir alongside other adaptive notes; promotion to a real ADR
    happens through ``/adr write`` and an explicit ``upsert_adr_entry`` call.
    """
    runtime_dir = get_runtime_dir() / "adaptive" / "design-gates" / "adr"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    adr_num = find_next_adr_number(get_adr_dir())
    issue_slug = _slugify(_issue_summary(issue)) or "design-gate"
    return runtime_dir / f"ADR-{adr_num:03d}-{_slugify(loop_name)}-{issue_slug}.md"


def write_design_gate(
    *,
    issue: dict[str, Any],
    loop_name: str,
    project_root: Path,
    context: dict[str, Any],
    use_adr: bool,
) -> dict[str, Any]:
    """Write a runtime note or ADR-style note before a structural fix.

    The helper keeps the artifact intentionally small:
    - frontmatter for machine-readable provenance
    - a short body that captures the loop, issue summary, and context sources
    """
    issue_summary = _issue_summary(issue)
    source_kinds = _context_source_kinds(context)
    path = _adr_note_path(loop_name, issue) if use_adr else _runtime_note_path(loop_name, issue)
    note_kind = "adr" if use_adr else "runtime-note"
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    title = f"Design Gate: {loop_name}"

    metadata = {
        "title": title,
        "type": "design-gate",
        "kind": note_kind,
        "loop": loop_name,
        "project_root": str(project_root),
        "issue_summary": issue_summary,
        "ownership_change": bool(issue.get("ownership_change")),
        "use_adr": use_adr,
        "created_at": now,
        "context_source_count": len(source_kinds),
        "context_source_kinds": source_kinds,
    }

    body_lines = [
        f"# {title}",
        "",
        f"- Kind: {note_kind}",
        f"- Loop: {loop_name}",
        f"- Issue: {issue_summary}",
        f"- Project root: {project_root}",
        f"- Context sources: {len(source_kinds)}",
    ]
    if source_kinds:
        body_lines.append(f"- Context kinds: {', '.join(source_kinds)}")
    if issue.get("ownership_change"):
        body_lines.append("- Ownership change: yes")

    write_frontmatter(path, metadata, "\n".join(body_lines))
    return {
        "written": True,
        "path": str(path),
        "kind": note_kind,
        "title": title,
        "source_count": len(source_kinds),
    }
