"""Sweep client-native memory entries into the canonical brain stores (ADR-811).

Deterministic, engine-free: parse client memory markdown, route by tier,
copy with provenance, dedupe by content hash, regenerate MEMORY.md indexes.
Client stores are never modified — this is a mirror, not a move.

Provenance (ADR-814): swept entries record ``source_file`` (basename only) and
``source_client`` (client id).  Absolute ``source_path`` is intentionally not
stored — machine paths must not enter the brain tree, which ships publicly.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

from src.lib.brain_memory_tiers import memory_dir_for_brain
from src.lib.brain_registry_models import BrainType
from src.lib.frontmatter_utils import parse_frontmatter, write_frontmatter

SKIP_FILES = {"MEMORY.md", "README.md"}
PROJECT_TYPES = {"project"}
_SLUG_RE = re.compile(r"[^a-z0-9-]+")


@dataclass
class SweepResult:
    swept: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def claude_project_memory_dir(project_root: Path, home: Path | None = None) -> Path:
    """Claude Code's per-project auto-memory dir (path slug: '/' -> '-')."""
    home = home or Path.home()
    slug = str(Path(project_root).resolve()).replace("/", "-")
    return home / ".claude" / "projects" / slug / "memory"


def _slugify(value: str) -> str:
    slug = _SLUG_RE.sub("-", value.strip().lower()).strip("-")
    return slug or "entry"


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _entry_type(meta: dict) -> str:
    metadata = meta.get("metadata")
    if isinstance(metadata, dict) and metadata.get("type"):
        return str(metadata["type"]).strip().lower()
    return str(meta.get("type") or "").strip().lower()


def effective_memory_brain_type(meta: dict, body: str) -> str:
    """Brain type for a memory entry, correcting a mis-declared ``type`` from the
    subject's referenced artifacts.

    Privacy-safe: when the entry's subject artifacts live in the personal vault
    (e.g. a private-vault skill or the user's resume), it is personal regardless
    of a ``type: project`` frontmatter declaration. This is the resume-tailor
    regression guard.
    """
    import re

    from src.lib.brain_classify.evidence import _classify_token

    declared = str(_entry_type(meta) or "").strip().lower()
    tokens = re.findall(r"\[\[([^\]]+)\]\]", body) + re.findall(
        r"`?([A-Za-z0-9_.~][A-Za-z0-9_./~-]*/[A-Za-z0-9_./~-]*)`?", body
    )
    project = sum(1 for t in tokens if _classify_token(t) == "project")
    personal = sum(1 for t in tokens if _classify_token(t) == "personal")
    if personal > project:
        return "personal"
    if project > personal:
        return "project"
    return declared if declared in {"project", "personal"} else "personal"


def sweep_client_memory(
    source_dir: Path,
    *,
    project_brain,
    personal_brain,
    source_client: str,
    dry_run: bool = False,
) -> SweepResult:
    """Mirror client memory entries into canonical brain stores.

    Routes entries by type: ``project`` → project brain, all others → personal
    brain.  Deduplicates by content hash so unchanged entries are skipped.
    The source directory is never modified.
    """
    result = SweepResult()
    source_dir = Path(source_dir)
    if not source_dir.is_dir():
        return result

    for path in sorted(source_dir.glob("*.md")):
        if path.name in SKIP_FILES:
            continue
        try:
            meta, body = parse_frontmatter(path, include_sidecar_config=False)
        except Exception as exc:  # noqa: BLE001 - malformed entries must not break the sweep
            result.errors.append(f"{path.name}: {exc}")
            continue

        # Empty or missing frontmatter — skip, do not sweep
        if not isinstance(meta, dict) or not meta:
            result.errors.append(f"{path.name}: no frontmatter")
            continue

        name = _slugify(str(meta.get("name") or path.stem))
        mem_type = _entry_type(meta)
        effective = effective_memory_brain_type(meta, body)
        brain = project_brain if effective == "project" else personal_brain
        # Correct a mis-declared project type when the subject routed personal, so
        # the written entry is self-consistent and never re-misroutes (resume-tailor).
        out_type = mem_type
        if mem_type in PROJECT_TYPES and effective != "project":
            out_type = "insight"
        if brain is None:
            result.skipped.append(name)
            continue

        entries_dir = memory_dir_for_brain(brain) / "entries"
        target = entries_dir / f"{name}.md"
        digest = _content_hash(body)

        if target.exists():
            try:
                existing_meta, _ = parse_frontmatter(target, include_sidecar_config=False)
            except Exception:  # noqa: BLE001
                existing_meta = {}
            if str(existing_meta.get("source_hash") or "") == digest:
                result.skipped.append(name)
                continue

        if dry_run:
            result.swept.append(name)
            continue

        entries_dir.mkdir(parents=True, exist_ok=True)
        out_meta = {
            "title": str(meta.get("name") or name),
            "name": name,
            "description": str(meta.get("description") or ""),
            "brain_scope": "project" if brain.type is BrainType.PROJECT else "personal",
            "type": out_type or "insight",
            "status": "active",
            "source_client": source_client,
            # source_file stores the basename only (ADR-814: no machine paths in brain tree).
            # source_client + project context identify the origin adequately.
            "source_file": path.name,
            "source_hash": digest,
        }
        write_frontmatter(target, out_meta, body)
        result.swept.append(name)

    result.swept.sort()
    result.skipped.sort()
    return result


def render_memory_index(brain) -> str:
    """Render a brain's MEMORY.md as a generated index of memory entries."""
    root = Path(brain.data_root)
    entries_dir = memory_dir_for_brain(brain) / "entries"
    scope = "project" if brain.type is BrainType.PROJECT else "personal"

    lines = [
        "---",
        f"title: {scope.capitalize()} Brain Memory Index",
        f"brain_scope: {scope}",
        "status: active",
        "generated: true",
        "---",
        "",
        "# Memory",
        "",
        "Generated index of memory entries. Do not hand-edit — regenerated by",
        "the client-memory sweep (ADR-811). Canonical entries live in",
        "`knowledge/memory/entries/`.",
        "",
    ]
    if entries_dir.is_dir():
        for path in sorted(entries_dir.glob("*.md")):
            if path.name in SKIP_FILES:
                continue
            try:
                meta, _ = parse_frontmatter(path, include_sidecar_config=False)
            except Exception:  # noqa: BLE001
                continue
            name = str(meta.get("name") or path.stem)
            description = str(meta.get("description") or "").strip()
            rel = path.relative_to(root).as_posix()
            lines.append(f"- [{name}]({rel}) — {description}")
    lines.append("")
    return "\n".join(lines)


def write_memory_index(brain, *, dry_run: bool = False) -> Path:
    """Write the generated MEMORY.md index to the brain root."""
    target = Path(brain.data_root) / "MEMORY.md"
    if not dry_run:
        target.write_text(render_memory_index(brain), encoding="utf-8")
    return target
