"""Dashboard-facing memory MCP tools: read payload, daily logs.

Split from tools_memory.py for module size management.
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
import asyncio
import json
import subprocess
import re
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter
from typing import TYPE_CHECKING, Any, Callable

from src.config.paths import get_runtime_dir

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

try:
    from src.mcp.augur_shared.annotations import tool_annotations
except ImportError:

    def tool_annotations(annotations: dict) -> dict:
        return annotations

try:
    from src.mcp.augur_shared.logging import get_entity_logger
except ImportError:
    import importlib

    def get_entity_logger(name: str):
        logging = importlib.import_module("logging")
        return logging.getLogger(name)


logger = get_entity_logger("mcp.knowledge.memory.dashboard")

# Category metadata for PluginCategory shape expected by dashboard
_CATEGORY_META: dict[str, dict[str, str]] = {
    "decision": {"id": "decision", "name": "Decisions", "icon": "CheckCircle", "color": "text-emerald-400", "bundle": "knowledge"},
    "pattern": {"id": "pattern", "name": "Patterns", "icon": "Lightbulb", "color": "text-purple-400", "bundle": "knowledge"},
    "preference": {"id": "preference", "name": "Preferences", "icon": "Heart", "color": "text-pink-400", "bundle": "knowledge"},
    "event": {"id": "event", "name": "Events", "icon": "Calendar", "color": "text-blue-400", "bundle": "knowledge"},
    "insight": {"id": "insight", "name": "Insights", "icon": "Brain", "color": "text-amber-400", "bundle": "knowledge"},
}
_LEGACY_TYPE_MAP = {
    "feedback": "decision",
    "project": "pattern",
    "preference": "preference",
    "reference": "insight",
}
_SECTION_TYPE_MAP = {
    "decisions": "decision",
    "learned patterns": "pattern",
    "user preferences": "preference",
}


def _iso_mtime(path: Path) -> str | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def _path_size(path: Path) -> int | None:
    if not path.exists():
        return None
    if path.is_file():
        return path.stat().st_size
    if path.is_dir():
        return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())
    return None


def _build_source_metadata(path: Path, *, label: str, kind: str) -> dict[str, Any]:
    return {
        "label": label,
        "kind": kind,
        "path": str(path),
        "exists": path.exists(),
        "modifiedAt": _iso_mtime(path),
        "sizeBytes": _path_size(path),
    }


def _memory_file_kind(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".md", ".markdown"}:
        return "markdown"
    if suffix in {".yaml", ".yml"}:
        return "yaml"
    if suffix in {".json", ".jsonl"}:
        return "json"
    if suffix in {".html", ".htm"}:
        return "html"
    if suffix == ".txt":
        return "text"
    return "file"


def _memory_inventory_id(source: str, relative_path: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", f"{source}-{relative_path}").strip("-").lower()
    return f"memory-file-{slug or source}"


def _relative_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


def _memory_file_record(path: Path, *, root: Path, source: str, description: str) -> dict[str, Any]:
    relative_path = _relative_path(path, root)
    return {
        "id": _memory_inventory_id(source, relative_path),
        "label": relative_path,
        "description": description,
        "kind": _memory_file_kind(path),
        "path": str(path),
        "exists": path.exists(),
        "source": source,
        "relativePath": relative_path,
        "sizeBytes": _path_size(path),
        "modifiedAt": _iso_mtime(path),
    }


def _iter_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    if root.is_file():
        return [root]
    return sorted(path for path in root.rglob("*") if path.is_file())


def _iter_direct_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    if root.is_file():
        return [root]
    return sorted(path for path in root.iterdir() if path.is_file())


def _is_client_memory_file(path: Path) -> bool:
    name = path.name.lower()
    suffix = path.suffix.lower()
    if suffix in {".md", ".markdown", ".txt"}:
        return True
    if suffix not in {".json", ".jsonl", ".yaml", ".yml"}:
        return False
    return any(token in name for token in ("memory", "session", "history", "conversation", "transcript"))


def _seen_path_key(path: Path) -> str:
    try:
        return str(path.resolve()).lower()
    except OSError:
        return str(path.absolute()).lower()


def _resolve_client_memory_plan(project_root: Path) -> dict[str, Any]:
    try:
        skills_dir = Path(__file__).resolve().parents[3]
        ops_dir = skills_dir / "ai" / "scripts" / "ops"
        if str(ops_dir) not in _augur_sys.path:
            _augur_sys.path.insert(0, str(ops_dir))
        from memory_assembler import resolve_default_client_memory_plan

        return resolve_default_client_memory_plan(project_root=project_root)
    except Exception as exc:
        logger.debug("Unable to resolve client memory plan: %s", exc)
        return {"sources": {}, "outputs": []}


def _collect_memory_file_inventory(
    *,
    mem_dir: Path,
    runtime_mem_dir: Path,
    profile_file: Path,
    client_memory_plan: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(path: Path, *, root: Path, source: str, description: str) -> None:
        key = _seen_path_key(path)
        if key in seen:
            return
        seen.add(key)
        files.append(_memory_file_record(path, root=root, source=source, description=description))

    for path in _iter_files(mem_dir):
        add(path, root=mem_dir, source="vault-memory", description="Vault-backed memory file")

    for path in _iter_files(runtime_mem_dir):
        add(path, root=runtime_mem_dir, source="runtime-memory", description="Runtime memory file")

    if profile_file.exists():
        add(profile_file, root=profile_file.parent, source="memory-profile", description="Wiki-backed memory profile")

    if client_memory_plan is not None:
        plan = client_memory_plan
    else:
        try:
            from src.config.paths import get_project_root

            project_root = Path(get_project_root())
        except Exception:
            project_root = Path.cwd()
        plan = _resolve_client_memory_plan(project_root)
    for client, root in (plan.get("sources") or {}).items():
        root_path = Path(root)
        for path in _iter_direct_files(root_path):
            if not _is_client_memory_file(path):
                continue
            add(path, root=root_path, source=f"client-memory:{client}", description=f"{client} memory source file")

    for output in plan.get("outputs") or []:
        client = str(output.get("client") or "client")
        if output.get("path"):
            path = Path(output["path"])
            if path.exists():
                add(path, root=path.parent, source=f"client-memory:{client}", description=f"{client} memory projection")
        elif output.get("dir"):
            root_path = Path(output["dir"])
            for path in _iter_direct_files(root_path):
                if not _is_client_memory_file(path):
                    continue
                add(path, root=root_path, source=f"client-memory:{client}", description=f"{client} memory projection")

    return sorted(files, key=lambda item: (str(item.get("source", "")), str(item.get("relativePath", ""))))


def _build_stats_payload(stats: dict[str, Any], sources: dict[str, Any]) -> dict[str, Any]:
    return {**stats, "sources": sources}


def _normalize_signal_kind(value: str) -> str:
    normalized = value.strip().lower()
    if normalized == "user preference":
        return "preference"
    if normalized in {"decision", "preference", "event"}:
        return normalized
    return "event"


def _extract_daily_log_preview(content: str) -> str:
    for label in ("Decision", "Preference", "Event"):
        match = re.search(rf"\*\*{label}\*\*:\s*(.+)", content)
        if match:
            return match.group(1).strip()

    for line in content.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith("**"):
            return stripped

    return ""


def _extract_daily_log_kind_counts(content: str) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for match in re.finditer(r"##\s+\d{2}:\d{2}\s+-\s+(.+)", content):
        counts[_normalize_signal_kind(match.group(1))] += 1
    return dict(counts)


def _list_daily_logs_from_runtime() -> list[dict[str, Any]]:
    daily_dir = get_runtime_dir() / "memory" / "daily"
    if not daily_dir.exists():
        return []

    logs: list[dict[str, Any]] = []
    for log_path in sorted(daily_dir.glob("*.md"), reverse=True):
        content = log_path.read_text(encoding="utf-8")
        kind_counts = _extract_daily_log_kind_counts(content)
        logs.append(
            {
                "date": log_path.stem,
                "hasLog": True,
                "entryCount": sum(kind_counts.values()),
                "preview": _extract_daily_log_preview(content),
                "kindCounts": kind_counts,
                "path": str(log_path),
                "modifiedAt": _iso_mtime(log_path),
                "sizeBytes": _path_size(log_path),
            }
        )
    return logs


def _read_daily_log_from_runtime(date: str) -> dict[str, Any]:
    file_path = get_runtime_dir() / "memory" / "daily" / f"{date}.md"
    if not file_path.exists():
        return {"date": date, "content": "", "size": 0, "error": f"Log not found for {date}"}

    content = file_path.read_text(encoding="utf-8")
    kind_counts = _extract_daily_log_kind_counts(content)
    return {
        "date": date,
        "content": content,
        "size": sum(kind_counts.values()),
        "preview": _extract_daily_log_preview(content),
        "kindCounts": kind_counts,
        "path": str(file_path),
        "modifiedAt": _iso_mtime(file_path),
        "sizeBytes": _path_size(file_path),
    }


def _parse_memory_table(content: str) -> list[dict[str, str]]:
    """Parse MEMORY.md table format into structured entries.

    Expected format:
        | Date | Client | Type | Name | Description |
        |------|--------|------|------|-------------|
        | 2026-03-31 | claude-code | feedback | ... | ... |
    """
    entries: list[dict[str, str]] = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        # Skip header and separator rows
        if stripped.startswith("| Date") or stripped.startswith("|--"):
            continue
        cells = [c.strip() for c in stripped.split("|")]
        # cells[0] and cells[-1] are empty from leading/trailing |
        if len(cells) < 6:
            continue
        entries.append({
            "date": cells[1],
            "client": cells[2],
            "type": _LEGACY_TYPE_MAP.get(cells[3].lower(), cells[3].lower()),
            "name": cells[4],
            "description": cells[5],
            "category": "",
        })
    return entries


def _parse_memory_sections(content: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    current_section: str | None = None
    current_subsection: str | None = None

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if line.startswith("## "):
            current_section = line[3:].strip().lower()
            current_subsection = None
            continue
        if line.startswith("### "):
            current_subsection = line[4:].strip().lower()
            continue

        entry_type = _SECTION_TYPE_MAP.get(current_section or "")
        if not entry_type or not line.startswith("- **"):
            continue

        match = re.match(r"- \*\*(.+?)\*\*:\s*(.+)", line)
        if not match:
            continue

        description = match.group(2).strip()
        date_match = re.search(r"\((\d{4}-\d{2}-\d{2})\)\s*$", description)
        date = date_match.group(1) if date_match else ""
        if date_match:
            description = description[:date_match.start()].rstrip()

        entries.append(
            {
                "date": date,
                "client": "",
                "type": entry_type,
                "name": match.group(1).strip(),
                "description": description,
                "category": current_subsection or "",
            }
        )

    return entries


def _parse_memory_entries(content: str) -> list[dict[str, str]]:
    deduped: dict[tuple[str, str, str, str], dict[str, str]] = {}

    for entry in [*_parse_memory_table(content), *_parse_memory_sections(content)]:
        key = (
            entry.get("type", ""),
            entry.get("name", ""),
            entry.get("description", ""),
            entry.get("date", ""),
        )
        deduped[key] = entry

    return list(deduped.values())


_PROFILE_LANGUAGES = ("en", "he")
_LANGUAGE_LABEL = {"en": "English", "he": "Hebrew"}

# Recognized client prefixes in memory/entries/ filenames.
# Convention: <client>_<type>_<slug>.md   (e.g. "claude-code_feedback_x.md")
# Anything unrecognized falls back to "user" (manually-authored entries).
_KNOWN_CLIENTS = {"claude-code", "codex", "gemini", "copilot", "user", "augur"}


def _client_from_filename(stem: str) -> str:
    """Extract the originating client/agent from a memory-entry filename stem."""
    if "_" not in stem:
        return "user"
    prefix = stem.split("_", 1)[0]
    return prefix if prefix in _KNOWN_CLIENTS else "user"


def _iso_mtime_str(path: Path) -> str:
    """Return ISO-8601 mtime string for a file, or empty string if missing."""
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
    except (OSError, ValueError):
        return ""


def _read_entry_meta(entry_file: Path) -> dict[str, Any] | None:
    """Parse frontmatter from one entry file, returning normalized dict or None."""
    from src.lib.frontmatter_utils import parse_frontmatter

    try:
        meta, _body = parse_frontmatter(entry_file, include_sidecar_config=False)
    except Exception:  # noqa: BLE001
        return None
    raw_type = (meta.get("type") or "").strip().lower()
    if not raw_type:
        return None
    return {
        "raw_type": raw_type,
        "normalized_type": _LEGACY_TYPE_MAP.get(raw_type, raw_type),
        "name": str(meta.get("name") or entry_file.stem),
        "description": str(meta.get("description") or ""),
        "category": str(meta.get("category") or ""),
    }


def _build_browse_items(*, memory_dirs: list[Path], vault_dir: Path | None) -> list[dict[str, Any]]:
    """Produce one BrowseItem record per memory entry, voice profile, and
    interview slot. Drives the Browse Profile tab card grid (CLAUDE.md rule 32
    — every tab is the shared file-card mechanism; no bespoke panels)."""
    items: list[dict[str, Any]] = []

    # 1. One card per memory entry (feedback / preference / project / reference)
    seen_entry_keys: set[tuple[str, str]] = set()
    for memory_dir in memory_dirs:
        entries_dir = memory_dir / "entries"
        if not entries_dir.exists():
            continue
        for entry_file in sorted(entries_dir.iterdir()):
            if entry_file.suffix != ".md":
                continue
            meta = _read_entry_meta(entry_file)
            if meta is None:
                continue
            key = (meta["name"], meta["description"])
            if key in seen_entry_keys:
                continue
            seen_entry_keys.add(key)
            client = _client_from_filename(entry_file.stem)
            items.append(
                {
                    "id": f"memory-entry:{entry_file.stem}",
                    "title": meta["name"],
                    "description": meta["description"] or "(no description)",
                    "hub": "brain",
                    "icon": "Brain",
                    "typeBadge": meta["normalized_type"].capitalize(),
                    "path": str(entry_file),
                    "primaryAction": {
                        "label": "Open Entry",
                        "type": "open-file",
                        "target": str(entry_file),
                    },
                    "actions": [
                        {
                            "id": "reveal",
                            "label": "Reveal in Finder",
                            "icon": "FolderOpen",
                            "type": "reveal-file",
                            "target": str(entry_file),
                        },
                        {
                            "id": "copy-path",
                            "label": "Copy Path",
                            "icon": "Copy",
                            "type": "copy",
                            "target": str(entry_file),
                        },
                    ],
                    "metadata": {
                        "kind": "memory-entry",
                        "type": meta["normalized_type"],
                        "rawType": meta["raw_type"],
                        "category": meta["category"],
                        "source": f"{client} memory entry",
                        "client": client,
                        "modified": _iso_mtime_str(entry_file),
                    },
                }
            )

    # 2. One card per voice profile (en, he) — only emit when at least one
    #    artifact exists; pending-only profiles emerge in interview-slot cards.
    if vault_dir is not None:
        for lang in _PROFILE_LANGUAGES:
            about = vault_dir / "profile" / lang / "about-me.md"
            if not about.is_file():
                continue
            size = about.stat().st_size
            items.append(
                {
                    "id": f"voice-profile:{lang}",
                    "title": f"{_LANGUAGE_LABEL[lang]} Voice Profile",
                    "description": f"Compiled about-me.md ({size:,} bytes). Drives reflective /ask voice.",
                    "hub": "brain",
                    "icon": "User",
                    "typeBadge": "Voice Profile",
                    "path": str(about),
                    "primaryAction": {
                        "label": "Open Profile",
                        "type": "open-file",
                        "target": str(about),
                    },
                    "actions": [
                        {
                            "id": "update",
                            "label": f"Update {lang.upper()}",
                            "icon": "RefreshCcw",
                            "type": "copy",
                            "target": f"/profile update {lang}",
                        },
                        {
                            "id": "reveal",
                            "label": "Reveal in Finder",
                            "icon": "FolderOpen",
                            "type": "reveal-file",
                            "target": str(about),
                        },
                        {
                            "id": "copy-path",
                            "label": "Copy Path",
                            "icon": "Copy",
                            "type": "copy",
                            "target": str(about),
                        },
                    ],
                    "metadata": {
                        "kind": "voice-profile",
                        "language": lang,
                        "status": "ready",
                        "sizeBytes": str(size),
                        "source": f"profile/{lang}",
                        "client": "user",
                        "modified": _iso_mtime_str(about),
                    },
                }
            )

        # 3. One card per interview slot (always en + he so the user sees the
        #    bilingual surface even before starting)
        for lang in _PROFILE_LANGUAGES:
            in_progress = vault_dir / "profile" / lang / "interview-in-progress.yaml"
            about = vault_dir / "profile" / lang / "about-me.md"
            if in_progress.is_file():
                status = "in-progress"
                desc = f"Interview in progress. Resume with /profile interview ({lang})."
            elif about.is_file():
                status = "complete"
                desc = f"Interview complete. Refresh with /profile update {lang}."
            else:
                status = "not-started"
                desc = f"Run /profile interview and choose {lang} to begin."
            # Pick the most recent artifact mtime (in-progress yaml or about-me) for sort
            slot_mtime = ""
            for candidate in (in_progress, about):
                ts = _iso_mtime_str(candidate)
                if ts and ts > slot_mtime:
                    slot_mtime = ts
            slot_actions = [
                {
                    "id": "copy-update",
                    "label": f"Copy /profile update {lang}",
                    "icon": "Copy",
                    "type": "copy",
                    "target": f"/profile update {lang}",
                },
                {
                    "id": "copy-fresh",
                    "label": f"Copy /profile interview",
                    "icon": "Copy",
                    "type": "copy",
                    "target": f"/profile interview",
                },
            ]
            if in_progress.is_file():
                slot_actions.insert(0, {
                    "id": "reveal-progress",
                    "label": "Reveal in-progress YAML",
                    "icon": "FolderOpen",
                    "type": "reveal-file",
                    "target": str(in_progress),
                })
            items.append(
                {
                    "id": f"interview-slot:{lang}",
                    "title": f"{_LANGUAGE_LABEL[lang]} Interview",
                    "description": desc,
                    "hub": "brain",
                    "icon": "Languages",
                    "typeBadge": f"Interview · {lang.upper()}",
                    "primaryAction": {
                        "label": "Copy Command",
                        "type": "copy",
                        "target": f"/profile interview" if status == "not-started" else f"/profile update {lang}",
                    },
                    "actions": slot_actions,
                    "metadata": {
                        "kind": "interview-slot",
                        "language": lang,
                        "status": status,
                        "source": f"profile/{lang}/interview",
                        "client": "user",
                        "modified": slot_mtime,
                    },
                }
            )

    return items


def _parse_memory_entries_with_dir(*memory_dirs: Path) -> list[dict[str, str]]:
    """Merge MEMORY.md table/section entries + per-file ``entries/`` frontmatter.

    Walks one or more memory roots (vault + runtime in production). Mirrors the
    ``tools_reflect.py:243`` entries-dir walk so the dashboard sees the same
    consolidated feedback/project/preference/reference files that ``/ask``
    retrieval already reads. Without this, ``/browse?view=profile`` and
    ``/workspace/memory`` undercount memories massively.
    """
    from src.lib.frontmatter_utils import parse_frontmatter

    table_entries: list[dict[str, str]] = []
    file_entries: list[dict[str, str]] = []

    for memory_dir in memory_dirs:
        memory_md = memory_dir / "MEMORY.md"
        if memory_md.exists():
            table_entries.extend(_parse_memory_entries(memory_md.read_text(encoding="utf-8")))

        entries_dir = memory_dir / "entries"
        if not entries_dir.exists():
            continue
        for entry_file in sorted(entries_dir.iterdir()):
            if entry_file.suffix != ".md":
                continue
            try:
                meta, _body = parse_frontmatter(entry_file, include_sidecar_config=False)
            except Exception:  # noqa: BLE001 — best-effort per-file parsing
                continue
            raw_type = (meta.get("type") or "").strip().lower()
            if not raw_type:
                continue
            normalized_type = _LEGACY_TYPE_MAP.get(raw_type, raw_type)
            file_entries.append(
                {
                    "date": str(meta.get("created") or meta.get("updated") or ""),
                    "client": str(meta.get("written-by") or ""),
                    "type": normalized_type,
                    "name": str(meta.get("name") or entry_file.stem),
                    "description": str(meta.get("description") or ""),
                    "category": str(meta.get("category") or ""),
                }
            )

    deduped: dict[tuple[str, str, str, str], dict[str, str]] = {}
    for entry in [*table_entries, *file_entries]:
        key = (
            entry.get("type", ""),
            entry.get("name", ""),
            entry.get("description", ""),
            entry.get("date", ""),
        )
        deduped[key] = entry
    return list(deduped.values())


def _parse_last_curated(content: str) -> str | None:
    match = re.search(r"\*Last curated:\s*(\d{4}-\d{2}-\d{2})\*", content)
    return match.group(1) if match else None


def _build_stats(
    entries: list[dict[str, str]],
    daily_logs: int,
    last_curated: str | None,
) -> dict[str, Any]:
    """Build MemoryStats dict from parsed table entries."""
    type_counts = Counter(entry["type"] for entry in entries)
    recent = sorted(
        (e for e in entries if e["type"] == "decision" and e["date"]),
        key=lambda x: x["date"],
        reverse=True,
    )
    recent_decisions = [
        {
            "topic": e["name"],
            "decision": e["description"],
            "category": e.get("category") or "general",
            "date": e["date"],
            "confidence": "high",
        }
        for e in recent[:5]
    ]
    category_counts = Counter(
        entry.get("category", "").lower()
        for entry in entries
        if entry["type"] == "decision" and entry.get("category")
    )

    return {
        "totalDecisions": type_counts.get("decision", 0),
        "totalPatterns": type_counts.get("pattern", 0),
        "totalPreferences": type_counts.get("preference", 0),
        "dailyLogs": daily_logs,
        "lastCurated": last_curated,
        "recentDecisions": recent_decisions,
        "categoryCounts": dict(category_counts),
    }


def _build_categories(type_counts: dict[str, int]) -> list[dict[str, Any]]:
    """Build PluginCategory list from type counts."""
    categories: list[dict[str, Any]] = []
    for type_key, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        meta = _CATEGORY_META.get(type_key, {
            "id": type_key,
            "name": type_key.capitalize(),
            "icon": "Tag",
            "color": "text-[var(--text-muted)]",
            "bundle": "knowledge",
        })
        categories.append({**meta, "count": count})
    return categories


def register_memory_dashboard_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
    project_root: Path,
) -> None:
    """Register dashboard-facing memory tools (read payload, daily logs)."""

    # =========================================================================
    # Memory Read (bootstrap payload for dashboard)
    # =========================================================================

    @mcp.tool(
        name="knowledge-memory-read",
        annotations=tool_annotations(
            {
                "title": "Read Memory Dashboard Data",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def knowledge_memory_read_tool(
        mode: str = "bootstrap",
        includeHtml: bool = False,
    ) -> str:
        """Read memory data for the dashboard.

        Args:
            mode: What to return — bootstrap (all), stats, categories, workspace, report
            includeHtml: Include Markdown rendering of the wiki-backed memory profile (report/bootstrap modes only)
        """
        _VALID_MODES = {"bootstrap", "stats", "categories", "workspace", "report"}
        if mode not in _VALID_MODES:
            return json.dumps({"error": f"Unknown mode: {mode!r}. Valid: {sorted(_VALID_MODES)}"})

        metrics.track_tool("knowledge_memory_read", skill="knowledge")

        from src.config.paths import get_memory_dir, get_runtime_dir, get_vault_dir
        mem_dir = get_memory_dir()
        runtime_mem_dir = get_runtime_dir() / "memory"
        memory_file = mem_dir / "MEMORY.md"
        index_file = mem_dir / "index.yaml"
        daily_dir = runtime_mem_dir / "daily"
        profile_file = get_vault_dir() / "wiki" / "profile-human-api.md"

        # Parse memory only when needed (stats/categories/bootstrap).
        # Walk BOTH vault and runtime memory dirs so per-file entries/ files
        # (used by claude-code session consolidation) are not invisible.
        entries: list[dict[str, str]] = []
        type_counts: dict[str, int] = {}
        memory_content = ""
        if mode in ("stats", "categories", "bootstrap"):
            try:
                if memory_file.exists():
                    memory_content = memory_file.read_text()
                entries = _parse_memory_entries_with_dir(mem_dir, runtime_mem_dir)
                type_counts = Counter(e["type"] for e in entries)
            except Exception as e:
                logger.error(f"Failed to parse memory entries: {e}")

        def _get_stats() -> dict[str, Any]:
            try:
                from src.lib.knowledge.search import MemorySearcher
                raw = MemorySearcher().get_stats()
                daily_logs = raw.get("daily_logs", 0)
                last_curated = _parse_last_curated(memory_content) or raw.get("index_updated")
            except Exception:
                daily_logs = 0
                last_curated = _parse_last_curated(memory_content)
            return _build_stats(entries, daily_logs, last_curated)

        def _get_workspace() -> dict[str, Any]:
            try:
                workspace_files: list[dict[str, Any]] = []
                items = [
                    (mem_dir, "memory", "MEMORY.md", "Curated Memory", "Persistent decisions, patterns, and preferences", "markdown"),
                    (profile_file.parent, "profile", profile_file.name, "Memory Profile", "Wiki-backed user profile for AI context", "markdown"),
                    (runtime_mem_dir, "daily", "daily", "Daily Logs", "Session-level decision and preference logs", "directory"),
                    (mem_dir, "index", "index.yaml", "Memory Index", "Search index for memory entries", "yaml"),
                ]
                for base_dir, item_id, rel_path, label, description, kind in items:
                    full_path = base_dir / rel_path
                    exists = full_path.exists()
                    size_bytes = None
                    modified_at = None
                    entry_count = None
                    if exists:
                        stat = full_path.stat()
                        if full_path.is_file():
                            size_bytes = stat.st_size
                            modified_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
                        elif full_path.is_dir():
                            md_files = list(full_path.glob("*.md"))
                            entry_count = len(md_files)
                            size_bytes = sum(f.stat().st_size for f in md_files)
                    workspace_files.append({
                        "id": item_id, "label": label, "description": description,
                        "kind": kind, "path": str(full_path), "exists": exists,
                        "sizeBytes": size_bytes, "modifiedAt": modified_at, "entryCount": entry_count,
                    })
                return {
                    "rootPath": str(mem_dir),
                    "files": workspace_files,
                    "allFiles": _collect_memory_file_inventory(
                        mem_dir=mem_dir,
                        runtime_mem_dir=runtime_mem_dir,
                        profile_file=profile_file,
                    ),
                }
            except Exception:
                return {"rootPath": "", "files": []}

        def _get_report() -> dict[str, Any]:
            try:
                if profile_file.exists():
                    stat = profile_file.stat()
                    report: dict[str, Any] = {
                        "exists": True,
                        "path": str(profile_file),
                        "title": "Memory Profile",
                        "modifiedAt": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                        "sizeBytes": stat.st_size,
                    }
                    if includeHtml:
                        report["html"] = profile_file.read_text()
                    return report
                return {"exists": False, "path": "", "title": None, "modifiedAt": None, "sizeBytes": None}
            except Exception:
                return {"exists": False}

        def _get_sources() -> dict[str, Any]:
            return {
                "memory": _build_source_metadata(memory_file, label="Curated memory", kind="file"),
                "index": _build_source_metadata(index_file, label="Memory index", kind="file"),
                "daily": _build_source_metadata(daily_dir, label="Daily logs", kind="directory"),
                "profile": _build_source_metadata(profile_file, label="Human API profile", kind="file"),
                "generatedAt": datetime.now(timezone.utc).isoformat(),
            }

        if mode == "stats":
            return json.dumps(_build_stats_payload(_get_stats(), _get_sources()), default=str)
        if mode == "categories":
            return json.dumps({"categories": _build_categories(type_counts), "sources": _get_sources()}, default=str)
        if mode == "workspace":
            return json.dumps({"workspace": _get_workspace(), "sources": _get_sources()}, default=str)
        if mode == "report":
            return json.dumps({"report": _get_report(), "sources": _get_sources()}, default=str)

        # bootstrap
        stats = _get_stats()
        browse_items = _build_browse_items(
            memory_dirs=[mem_dir, runtime_mem_dir],
            vault_dir=get_vault_dir(),
        )
        return json.dumps({
            "stats": stats,
            "categories": _build_categories(type_counts),
            "workspace": _get_workspace(),
            "report": _get_report(),
            "sources": _get_sources(),
            "browseItems": browse_items,
        }, default=str)

    # =========================================================================
    # Daily Logs Tools (knowledge dashboard memory page)
    # =========================================================================

    @mcp.tool(
        name="knowledge-memory-daily-logs",
        annotations=tool_annotations(
            {
                "title": "List Daily Logs",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def knowledge_memory_daily_logs_tool() -> str:
        """List available daily log dates with metadata.

        Returns:
            str: JSON with logs list including date, path, size, preview
        """
        metrics.track_tool("knowledge_memory_daily_logs", skill="knowledge")

        try:
            logs = await asyncio.to_thread(_list_daily_logs_from_runtime)
            daily_dir = get_runtime_dir() / "memory" / "daily"
            return json.dumps(
                {
                    "logs": logs,
                    "source": {
                        "label": "Daily memory logs",
                        "kind": "markdown-directory",
                        "path": str(daily_dir),
                        "exists": daily_dir.exists(),
                        "modifiedAt": _iso_mtime(daily_dir),
                    },
                    "generatedAt": datetime.now(timezone.utc).isoformat(),
                },
                indent=2,
                default=str,
            )
        except Exception as e:
            logger.error(f"Failed to list daily logs: {e}", exc_info=True)
            return json.dumps({"logs": []})

    @mcp.tool(
        name="knowledge-memory-daily-logs-read",
        annotations=tool_annotations(
            {
                "title": "Read Daily Log",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def knowledge_memory_daily_logs_read_tool(date: str) -> str:
        """Read content of a specific daily log by date.

        Args:
            date: Date string (e.g. '2026-03-14')

        Returns:
            str: JSON with date, content, and size
        """
        metrics.track_tool("knowledge_memory_daily_logs_read", skill="knowledge")

        try:
            result = await asyncio.to_thread(_read_daily_log_from_runtime, date)
            daily_dir = get_runtime_dir() / "memory" / "daily"
            result["source"] = {
                "label": "Daily memory logs",
                "kind": "markdown-directory",
                "path": str(daily_dir),
                "exists": daily_dir.exists(),
                "modifiedAt": _iso_mtime(daily_dir),
            }
            result["generatedAt"] = datetime.now(timezone.utc).isoformat()
            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to read daily log {date}: {e}", exc_info=True)
            return json.dumps({"date": date, "content": "", "size": 0, "error": str(e)})

    @mcp.tool(
        name="knowledge-memory-daily-logs-open",
        annotations=tool_annotations(
            {
                "title": "Open Daily Log in Editor",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def knowledge_memory_daily_logs_open_tool(date: str) -> str:
        """Open a daily log file in the system editor.

        Args:
            date: Date string (e.g. '2026-03-14')

        Returns:
            str: JSON confirmation
        """
        metrics.track_tool("knowledge_memory_daily_logs_open", skill="knowledge")

        def _open_daily_log(d: str) -> dict[str, Any]:
            from src.config.paths import get_runtime_dir

            daily_dir = get_runtime_dir() / "memory" / "daily"
            file_path = daily_dir / f"{d}.md"
            if not file_path.exists():
                return {"success": False, "error": f"Log not found for {d}"}
            subprocess.Popen(["open", str(file_path)])
            return {"success": True, "opened": str(file_path), "editor": "system default"}

        try:
            result = await asyncio.to_thread(_open_daily_log, date)
            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to open daily log {date}: {e}", exc_info=True)
            return json.dumps({"success": False, "error": str(e)})
