"""Structural category scanners for the unified RAG indexer.

Scanners:
  - index_vault()       -- external vault *.md files
  - index_scripts()     -- managed skills' scripts/ (.py/.sh)
  - index_api_routes()  -- apps/dashboard/app/api/**/route.ts
  - index_tests()       -- plugin augur/tests/ and dashboard tests/
  - index_pages()       -- SKILL.md frontmatter contributions.pages lists
  - index_blocks()      -- SKILL.md frontmatter contributions.blocks lists
  - index_mcp_tools()   -- managed skills' scripts/**/mcp/*.py
  - index_mcp_servers() -- config/system/mcp_servers.yaml
  - index_logs()        -- runtime logs from get_logs_dir() and job ledger state
"""

# TODO_CLEANUP: This file is 976 lines — consider splitting into smaller modules

from __future__ import annotations

import json
import re
import yaml
from pathlib import Path
from typing import Any

from src.config.paths import get_logs_dir, get_project_root, get_runtime_dir
from src.lib.frontmatter_utils import extract_relationships, parse_frontmatter, write_frontmatter
from src.logging import get_entity_logger

try:
    from ._indexer_helpers import (
        _checksum,
        _mtime_iso,
        _discover_skill_dirs,
        _read_skill_config,
        _write_entry,
        humanize_slug,
        source_path_for,
    )
    from ._overlay import OverlayScope, overlay_entry_id, overlay_metadata, vault_overlay_output_path
except ImportError:
    from _indexer_helpers import (
        _checksum,
        _mtime_iso,
        _discover_skill_dirs,
        _read_skill_config,
        _write_entry,
        humanize_slug,
        source_path_for,
    )
    from _overlay import OverlayScope, overlay_entry_id, overlay_metadata, vault_overlay_output_path


_LOG_SOURCE_CONFIG: dict[str, dict[str, str]] = {
    "mcp": {
        "label": "MCP",
        "description": "MCP Gateway logs",
    },
    "llm": {
        "label": "LLM",
        "description": "Language model interactions",
    },
    "plugins": {
        "label": "Plugins",
        "description": "Plugin activity logs",
    },
    "daemon": {
        "label": "Daemon",
        "description": "Daemon services and background job logs",
    },
    "self-heal": {
        "label": "Self-Heal",
        "description": "Self-heal scans, classifier output, and remediation logs",
    },
    "system": {
        "label": "System",
        "description": "System and runtime logs",
    },
    "claude": {
        "label": "Claude",
        "description": "Claude Code logs",
    },
}

_LOG_SOURCE_ORDER = tuple(_LOG_SOURCE_CONFIG.keys())
_SELF_HEAL_LOG_SOURCES = {
    "ai-self-healer",
    "boundaries",
    "cleanup-processes",
    "runtime-marker-scanner",
    "service-healer",
}
_DAEMON_LOG_SOURCES = {
    "adaptive-loop-engine",
    "adaptive-loop-reporter",
    "continuous-executor",
    "daemon",
    "dashboard-lifecycle",
    "dashboard-monitor",
    "schedule-executor",
    "unified-daemon",
}

_JOB_LEDGER_TERMINAL_STATES = {"complete", "failed", "timeout", "cancelled"}


def _human_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    units = ("KB", "MB", "GB", "TB")
    size = float(size_bytes)
    unit = "B"
    for unit in units:
        size /= 1024.0
        if size < 1024.0:
            break
    precision = 0 if size >= 100 else 1
    return f"{size:.{precision}f} {unit}"


def _classify_log_category(source_name: str) -> str:
    normalized = source_name.lower().replace("_", "-")

    if "claude" in normalized:
        return "claude"
    if normalized == "llm" or normalized.startswith("llm-"):
        return "llm"
    if (
        normalized.startswith("mcp")
        or ".mcp." in normalized
        or "-mcp" in normalized
        or "mcp-" in normalized
        or normalized.startswith("configure-mcp")
    ):
        return "mcp"
    if normalized in _SELF_HEAL_LOG_SOURCES or "self-heal" in normalized:
        return "self-heal"
    if normalized.startswith("plugin") or normalized.startswith("plugins") or normalized == "cli-plugins":
        return "plugins"
    if normalized in _DAEMON_LOG_SOURCES or normalized.startswith("adaptive-loop-"):
        return "daemon"
    return "system"


def _last_job_state(events_file: Path) -> str:
    """Return the last valid state in a job ledger events file."""
    state = "unknown"
    try:
        for line in events_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            value = event.get("state")
            if value:
                state = str(value)
    except OSError:
        return state
    return state


def _write_job_ledger_log_entry(category_dir: Path) -> bool:
    """Add the ADR-743 runtime job ledger inspector to Browse Logs."""
    jobs_root = get_runtime_dir() / "jobs"
    try:
        if not jobs_root.is_dir():
            return False
    except OSError:
        return False

    job_dirs: list[Path] = []
    for candidate in sorted(jobs_root.iterdir()):
        try:
            if candidate.is_dir() and not candidate.name.startswith(".") and candidate.name != "_archive":
                job_dirs.append(candidate)
        except OSError:
            continue
    if not job_dirs:
        return False

    event_files = [job_dir / "events.jsonl" for job_dir in job_dirs if (job_dir / "events.jsonl").is_file()]
    meta_files = [job_dir / "meta.json" for job_dir in job_dirs if (job_dir / "meta.json").is_file()]
    readable_files = event_files or meta_files
    if not readable_files:
        return False

    latest_file = max(readable_files, key=lambda path: path.stat().st_mtime)
    latest_job_dir = latest_file.parent
    modified = _mtime_iso(latest_file)
    state_counts: dict[str, int] = {}
    for event_file in event_files:
        state = _last_job_state(event_file)
        state_counts[state] = state_counts.get(state, 0) + 1

    terminal_count = sum(state_counts.get(state, 0) for state in _JOB_LEDGER_TERMINAL_STATES)
    active_count = max(0, len(job_dirs) - terminal_count)
    state_summary = ", ".join(f"{state}:{count}" for state, count in sorted(state_counts.items()) if count)
    total_size = sum(path.stat().st_size for path in readable_files)
    description = (
        f"{len(job_dirs)} job ledger record(s), {active_count} active, "
        f"{terminal_count} terminal. Latest: {latest_job_dir.name}."
    )

    entry_meta = {
        "type": "job-ledger",
        "hub": "command",
        "id": "job-ledger",
        "name": "job-ledger",
        "title": "Job Ledger",
        "source_path": str(latest_file),
        "description": description,
        "category": "job-ledger",
        "category_label": "Job Ledger",
        "jobs_root_path": str(jobs_root),
        "latest_file_path": str(latest_file),
        "latest_file_name": latest_file.name,
        "latest_folder_path": str(latest_job_dir),
        "latest_relative_path": latest_file.relative_to(jobs_root).as_posix(),
        "latest_job_id": latest_job_dir.name,
        "job_count": str(len(job_dirs)),
        "event_file_count": str(len(event_files)),
        "active_job_count": str(active_count),
        "terminal_job_count": str(terminal_count),
        "state_counts": state_summary,
        "total_size_bytes": str(total_size),
        "total_size_human": _human_size(total_size),
        "checksum": _checksum(latest_file),
        "modified": modified,
    }

    body = (
        "# Job Ledger\n\n"
        f"{description}\n\n"
        f"- Jobs root: `{jobs_root}`\n"
        f"- Latest job: `{latest_job_dir.name}`\n"
        f"- Latest file: `{latest_file}`\n"
        f"- State counts: `{state_summary or 'none'}`\n"
    )
    _write_entry(category_dir / "job-ledger.md", entry_meta, body)
    return True


# ---------------------------------------------------------------------------
# Vault scanner
# ---------------------------------------------------------------------------


def _vault_journey_category(vault_file: Path, vault_dir: Path) -> str:
    """Return the operation-mode Browse journey bucket for a vault file."""
    try:
        rel = vault_file.relative_to(vault_dir)
    except ValueError:
        return "other"
    from src.lib.brain_layout import brain_layout

    return _vault_journey_category_for_rel(rel, layout=brain_layout(vault_dir))


def _vault_journey_category_for_rel(rel: Path, layout: str = "knowledge") -> str:
    """Return the Browse journey bucket for a vault-relative path."""
    rel = _shared_vault_logical_rel(rel)
    if not rel.parts:
        return "other"
    root = rel.parts[0]
    if layout == "domains":
        # Domains layout: infra dirs keep their journey; every user domain
        # folder (career/, books/, ...) IS the notes surface.
        if root in {"inbox", "wiki", "sources"}:
            return root
        return "notes"
    if root in {"inbox", "notes", "sources", "wiki", "archive", "skills", "drafts", "memory"}:
        return root
    return "other"


def _shared_vault_logical_rel(rel: Path) -> Path:
    """Map standard brain knowledge paths onto Browse vault journeys."""
    if len(rel.parts) >= 3 and rel.parts[0] == "knowledge" and rel.parts[1] in {"notes", "sources", "wiki", "memory"}:
        return Path(rel.parts[1], *rel.parts[2:])
    return rel


def _vault_note_collection(rel: Path, journey_category: str, layout: str = "knowledge") -> str:
    """Content sub-collection folder under the notes journey root.

    Legacy layout: journey_category is ``parts[0]`` (e.g. ``notes``), so the
    collection that distinguishes Books / Career / ... is ``parts[1]``
    (``notes/books/x.md`` -> ``books``). Domains layout: the domain folder
    itself is the collection (``career/cv.md`` -> ``career``). Loose files
    directly under the scan root have no collection and return ``""``.
    """
    if journey_category != "notes":
        return ""
    if layout == "domains":
        return rel.parts[0] if len(rel.parts) >= 2 else ""
    if len(rel.parts) >= 3:
        return rel.parts[1]
    return ""


_VAULT_BROWSE_METADATA_KEYS = {
    "x-augur-note-type",
    "x-augur-prompt-triggerable",
    "x-augur-note-source",
    "canonical_url",
    "source_url",
    "source_domain",
    "enrichment_status",
    "transcript_status",
    "transcript_preview",
    "duration_seconds",
    "attendee_count",
    "attendee_slugs",
    "audio_path",
    "provider",
    "provider_version",
    "image_url",
    "caption",
    "trigger_count",
    "variable_count",
    "placeholders",
}


def _browse_metadata_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list) and all(isinstance(item, (str, int, float, bool)) for item in value):
        return ",".join(str(item) for item in value)
    return None


def _vault_browse_metadata(meta: dict[str, Any]) -> dict[str, Any]:
    """Return whitelisted frontmatter needed by Browse cards and filters."""
    browse_meta: dict[str, Any] = {}
    for key in _VAULT_BROWSE_METADATA_KEYS:
        if key in meta:
            value = _browse_metadata_value(meta[key])
            if value is not None:
                browse_meta[key] = value

    if "canonical_url" not in browse_meta:
        for key in ("url", "source_url"):
            value = _browse_metadata_value(meta.get(key))
            if value:
                browse_meta["canonical_url"] = value
                break
    if "source_domain" not in browse_meta:
        value = _browse_metadata_value(meta.get("domain"))
        if value:
            browse_meta["source_domain"] = value

    return browse_meta


def _vault_body_description(body: str, *, limit: int = 300) -> str:
    """Extract the first useful prose from a vault note body for Browse cards."""
    parts: list[str] = []
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            if parts:
                break
            continue
        if line.startswith(">"):
            line = line[1:].strip()
        if not line:
            continue
        if line.startswith("[!") and line.endswith("]"):
            continue
        if line.startswith("!["):
            continue
        parts.append(line)
        if len(" ".join(parts)) >= limit:
            break
    return " ".join(" ".join(parts).split())[:limit]


def _staged_skill_draft_metadata(rel: Path, meta: dict[str, Any]) -> dict[str, str]:
    """Return identity metadata for draft skills staged under drafts/staging."""
    if len(rel.parts) >= 5 and rel.parts[0] == "drafts" and rel.parts[1] == "staging" and rel.parts[3] == "skills":
        skill_name = str(meta.get("name") or rel.parts[4]) if rel.name == "SKILL.md" else rel.parts[4]
        metadata = {
            "draft_kind": "skill" if rel.name == "SKILL.md" else "skill-file",
            "promotion_state": "staged-draft",
            "staging_batch": rel.parts[2],
            "skill": skill_name,
        }
        if rel.name == "SKILL.md":
            metadata.update(
                {
                    "name": skill_name,
                    "title": skill_name,
                    "format": "skill",
                }
            )
            if description := str(meta.get("description") or "").strip():
                metadata["description"] = description
            # hub metadata removed with the x-augur-hub field (ADR-802)
        return metadata
    return {}


def index_vault(
    vault_dir: Path,
    rag_dir: Path,
    *,
    shared_vault_dir: Path | None = None,
    root: Path | None = None,
) -> int:
    """Recursively scan vault_dir for *.md files and write pointer entries.

    NOTE: vault_dir is the external vault root (resolved via get_vault_dir()), NOT the
    project root. ``root`` is the project root used to store in-repo (shared-scope)
    ``source_path`` values project-relative (POSIX) so the machine-shared index
    resolves from any checkout/worktree (ADR-270/759); external paths stay absolute.

    Output layout:
        rag_dir/vault/{journey-category}/{scope}/{relative-path-after-root}
    """
    import shutil

    root = (root or get_project_root()).resolve()
    category_dir = rag_dir / "vault"
    if category_dir.exists():
        shutil.rmtree(category_dir)
    count = 0

    _VAULT_EXTENSIONS = {".md", ".yaml", ".yml", ".json", ".txt", ".csv"}

    def _is_shared_vault_rel(rel: Path) -> bool:
        rel = _shared_vault_logical_rel(rel)
        if not rel.parts:
            return False
        if rel.parts[0] in {"notes", "sources", "memory"}:
            return True
        return len(rel.parts) >= 3 and rel.parts[0] == "inbox" and rel.parts[1] == "promotions"

    from src.lib.brain_layout import is_machine_path as _is_machine_path

    def _iter_vault_files(root_dir: Path, scope: OverlayScope):
        if not root_dir.is_dir():
            return
        for vault_file in sorted(root_dir.rglob("*")):
            # Skip symlinks. CPython rglob does not follow symlinked dirs;
            # guard retained for defense in depth.
            if vault_file.is_symlink():
                continue
            if not vault_file.is_file() or vault_file.suffix.lower() not in _VAULT_EXTENSIONS:
                continue
            # Skip machine-owned paths: _augur/ subtree and root brain-contract
            # files (MEMORY.md, IDENTITY.md, etc.) in the domains layout.
            if _is_machine_path(root_dir, vault_file):
                continue
            try:
                rel = vault_file.relative_to(root_dir)
            except ValueError:
                continue
            if not rel.parts:
                continue
            # Hidden dirs (.pytest_cache, .obsidian, ...) are never user content.
            if any(part.startswith(".") for part in rel.parts):
                continue
            if scope == "shared" and not _is_shared_vault_rel(rel):
                continue
            # Wiki pages are indexed by index_wiki — skip them here whether the
            # vault uses the legacy flat layout or the ADR-771 knowledge layout.
            if scope == "private" and _shared_vault_logical_rel(rel).parts[0] == "wiki":
                continue
            # Skip memory index/summary files — they are regenerated metadata, not
            # individual knowledge cards.
            logical = _shared_vault_logical_rel(rel)
            if logical.parts[0:1] == ("memory",) and vault_file.name in {"README.md", "MEMORY.md"}:
                continue
            yield vault_file, rel

    roots: list[tuple[OverlayScope, Path]] = []
    if shared_vault_dir is not None:
        roots.append(("shared", shared_vault_dir))
    roots.append(("private", vault_dir))

    from src.lib.brain_layout import brain_layout

    for scope, root_dir in roots:
        root_layout = brain_layout(root_dir)
        for vault_file, rel in _iter_vault_files(root_dir, scope):
            # Both scopes use the ADR-771 knowledge layout — map knowledge/*
            # paths onto their Browse journey names for skill/journey metadata.
            logical_rel = _shared_vault_logical_rel(rel)
            # Flat vault: parts[0] is the skill name (no bundle prefix).
            skill = logical_rel.parts[0]

            # Parse frontmatter for markdown files; skip for others
            meta: dict[str, Any] = {}
            title = ""
            body = ""
            relationships: dict[str, list[str]] = {}
            relationship_targets: list[str] = []
            parse_error = ""
            if vault_file.suffix.lower() == ".md":
                try:
                    meta, body = parse_frontmatter(vault_file)
                    title = meta.get("title", "")
                    relationships = extract_relationships(meta)
                    relationship_targets = list(
                        dict.fromkeys(target for field_targets in relationships.values() for target in field_targets)
                    )
                except (OSError, UnicodeDecodeError) as exc:
                    title = vault_file.stem
                    parse_error = f"{type(exc).__name__}: {exc}"

            name = vault_file.stem
            staged_skill_metadata = _staged_skill_draft_metadata(logical_rel, meta)
            body_description = _vault_body_description(body)
            description = str(meta.get("description") or "").strip() or body_description or str(title or "").strip()

            entry_meta: dict[str, Any] = {
                "id": overlay_entry_id("vault", scope, rel),
                "type": "vault",
                "skill": skill,
                "journey_category": _vault_journey_category_for_rel(logical_rel, layout=root_layout),
                "format": vault_file.suffix.lstrip(".").lower(),
                "name": name,
                "title": (str(title or meta.get("label") or "").strip() or humanize_slug(name)),
                "tags": meta.get("tags") or [],
                "source_path": source_path_for(vault_file, root),
                "description": description,
                "checksum": _checksum(vault_file),
                "modified": _mtime_iso(vault_file),
                **overlay_metadata(scope=scope, rel=logical_rel),
            }
            entry_meta.update(staged_skill_metadata)
            note_collection = _vault_note_collection(logical_rel, entry_meta["journey_category"], layout=root_layout)
            if note_collection:
                entry_meta["note_category"] = note_collection
            # Memory entries get a "memory" tag so Browse cards show the badge
            # (ADR-811 follow-up — memory entries ride the vault card mechanism, rule 32).
            if entry_meta["journey_category"] == "memory":
                existing_tags = list(entry_meta.get("tags") or [])
                if "memory" not in existing_tags:
                    entry_meta["tags"] = ["memory", *existing_tags]
            if parse_error:
                entry_meta["frontmatter_parse_error"] = parse_error
            if vault_file.suffix.lower() == ".md":
                entry_meta.update(_vault_browse_metadata(meta))
            if entry_meta["journey_category"] in {"drafts", "archive"}:
                entry_meta["inactive_scope"] = "true"
                entry_meta["active_search_scope"] = "false"
            else:
                entry_meta["active_search_scope"] = "true"
            if relationships:
                entry_meta["relationships"] = relationships
                entry_meta["relationship_targets"] = relationship_targets

            output_path = vault_overlay_output_path(category_dir, scope, logical_rel)
            _write_entry(output_path, entry_meta)
            count += 1

    return count


# ---------------------------------------------------------------------------
# Scripts scanner
# ---------------------------------------------------------------------------


def index_scripts(root: Path, rag_dir: Path) -> int:
    """Scan skill scripts/ directories recursively for .py and .sh files.

    Output layout:
        rag_dir/scripts/{bundle}/{skill}/{safe_name}.md
    """
    import shutil

    category_dir = rag_dir / "scripts"
    if category_dir.exists():
        shutil.rmtree(category_dir)
    count = 0
    root_resolved = Path(root).resolve()

    for bundle_name, skill_dir in _discover_skill_dirs(root):
        scripts_dir = skill_dir / "scripts"
        if not scripts_dir.is_dir():
            continue

        skill_name = skill_dir.name
        skill_ref = f"skills/{bundle_name}/{skill_name}"

        for script_file in sorted(scripts_dir.rglob("*")):
            if not script_file.is_file():
                continue
            if script_file.suffix not in {".py", ".sh"}:
                continue
            if script_file.name == "__init__.py":
                continue  # Python package marker, not a user-facing script
            try:
                rel = script_file.relative_to(scripts_dir)
            except ValueError:
                continue

            if any(part.startswith((".", "__pycache__")) for part in rel.parts):
                continue

            # Project-root containment guard: skip skill copies discovered
            # outside the project root (e.g. installed ~/.claude plugin-cache
            # duplicates) — they are projections, not this project's source.
            try:
                source_path = str(script_file.resolve().relative_to(root_resolved))
            except ValueError:
                continue

            safe_name = "__".join(rel.with_suffix("").parts)
            language = "python" if script_file.suffix == ".py" else "shell"

            description = ""
            try:
                src = script_file.read_text(encoding="utf-8", errors="ignore")[:2000]
                if script_file.suffix == ".py":
                    m = re.search(r'"""(.*?)"""', src, re.DOTALL)
                    if not m:
                        m = re.search(r"'''(.*?)'''", src, re.DOTALL)
                    if m:
                        description = m.group(1).strip().split("\n")[0]
                elif script_file.suffix == ".sh":
                    for line in src.splitlines()[1:5]:  # skip shebang
                        if line.startswith("#") and line.strip() != "#":
                            description = line.lstrip("# ").strip()
                            break
            except Exception:
                pass

            entry_meta: dict[str, Any] = {
                "type": "script",
                "hub": bundle_name,
                "bundle": bundle_name,
                "skill": skill_name,
                "name": script_file.stem,
                "source_path": source_path,
                "description": description,
                "language": language,
                "related": [skill_ref],
                "checksum": _checksum(script_file),
                "modified": _mtime_iso(script_file),
            }

            output_path = category_dir / bundle_name / skill_name / f"{safe_name}.md"
            _write_entry(output_path, entry_meta, "")
            count += 1

    return count


# ---------------------------------------------------------------------------
# API routes scanner
# ---------------------------------------------------------------------------

_HTTP_METHOD_RE = re.compile(r"export\s+(?:async\s+)?function\s+(GET|POST|PUT|DELETE|PATCH)\b")


def index_api_routes(root: Path, rag_dir: Path) -> int:
    """Scan apps/dashboard/app/api/**/route.ts and write pointer entries.

    Output layout:
        rag_dir/api-routes/{safe_name}.md
    """
    import shutil

    api_root = root / "apps" / "dashboard" / "app" / "api"
    category_dir = rag_dir / "api-routes"
    if category_dir.exists():
        shutil.rmtree(category_dir)
    count = 0

    if not api_root.is_dir():
        return count

    for route_file in sorted(api_root.rglob("route.ts")):
        try:
            rel = route_file.parent.relative_to(api_root)
        except ValueError:
            continue

        parts = rel.parts
        hub = parts[0] if parts else "api"
        route_path = "/" + "/".join(parts) if parts else "/"
        safe_name = "__".join(parts) if parts else "root"

        source_path = str(route_file.relative_to(root))
        content_text = route_file.read_text(errors="replace")
        methods = sorted(set(_HTTP_METHOD_RE.findall(content_text)))

        method_fallback = ", ".join(f"{m} {route_path}" for m in methods) if methods else route_path

        description = ""
        try:
            src = content_text[:3000]
            # Try JSDoc
            m = re.search(r'/\*\*\s*\n?\s*\*?\s*(.+?)[\n*]', src)
            if m:
                description = m.group(1).strip().rstrip('*').strip()
            # Fallback: first // comment after imports
            if not description:
                for line in src.splitlines():
                    stripped = line.strip()
                    if stripped.startswith("//") and not stripped.startswith("///"):
                        candidate = stripped.lstrip("/ ").strip()
                        if len(candidate) > 10:
                            description = candidate
                            break
        except Exception:
            pass
        # Keep the method+path as fallback
        if not description:
            description = method_fallback

        entry_meta: dict[str, Any] = {
            "type": "api-route",
            "hub": hub,
            "name": route_path,
            "source_path": source_path,
            "description": description,
            "methods": methods,
            "checksum": _checksum(route_file),
            "modified": _mtime_iso(route_file),
        }

        output_path = category_dir / f"{safe_name}.md"
        _write_entry(output_path, entry_meta, "")
        count += 1

    return count


# ---------------------------------------------------------------------------
# Tests scanner
# ---------------------------------------------------------------------------


def index_tests(root: Path, rag_dir: Path) -> int:
    """Scan Python plugin tests and TypeScript dashboard tests.

    Output layout:
        rag_dir/tests/{skill}/{safe_name}.md   (pytest — per-skill so no single
                                                dir scales with the whole corpus)
        rag_dir/tests/dashboard/{safe_name}.md (jest)
    """
    import shutil

    category_dir = rag_dir / "tests"
    if category_dir.exists():
        shutil.rmtree(category_dir)
    count = 0

    # --- pytest: plugin augur/tests/test_*.py ---
    for bundle_name, skill_dir in _discover_skill_dirs(root):
        tests_dir = skill_dir / "augur" / "tests"
        if not tests_dir.is_dir():
            continue

        skill_name = skill_dir.name
        skill_ref = f"skills/{bundle_name}/{skill_name}"

        for test_file in sorted(tests_dir.glob("test_*.py")):
            try:
                source_path = str(test_file.relative_to(root))
            except ValueError:
                source_path = str(test_file)
            safe_name = test_file.stem

            description = ""
            try:
                src = test_file.read_text(encoding="utf-8", errors="ignore")[:2000]
                m = re.search(r'"""(.*?)"""', src, re.DOTALL)
                if not m:
                    m = re.search(r"'''(.*?)'''", src, re.DOTALL)
                if m:
                    description = m.group(1).strip().split("\n")[0]
            except Exception:
                pass

            entry_meta: dict[str, Any] = {
                "type": "test",
                "hub": skill_name,
                "name": safe_name,
                "source_path": source_path,
                "description": description,
                "test_type": "pytest",
                "related": [skill_ref],
                "checksum": _checksum(test_file),
                "modified": _mtime_iso(test_file),
            }

            output_path = category_dir / skill_name / f"{safe_name}.md"
            _write_entry(output_path, entry_meta, "")
            count += 1

    # --- jest: root/tests/dashboard/**/*.test.* ---
    dashboard_tests_dir = root / "tests" / "dashboard"
    if dashboard_tests_dir.is_dir():
        for test_file in sorted(dashboard_tests_dir.rglob("*.test.*")):
            if not test_file.is_file():
                continue
            try:
                rel = test_file.relative_to(dashboard_tests_dir)
            except ValueError:
                continue

            safe_name = "__".join(rel.with_suffix("").parts)
            safe_name = safe_name.replace(".test", "")
            source_path = str(test_file.relative_to(root))

            description = ""
            try:
                src = test_file.read_text(encoding="utf-8", errors="ignore")[:2000]
                m = re.search(r'describe\(["\'](.+?)["\']', src)
                if m:
                    description = m.group(1).strip()
            except Exception:
                pass

            entry_meta = {
                "type": "test",
                "hub": "dev",
                "name": test_file.name,
                "source_path": source_path,
                "description": description,
                "test_type": "jest",
                "related": [],
                "checksum": _checksum(test_file),
                "modified": _mtime_iso(test_file),
            }

            output_path = category_dir / "dashboard" / f"{safe_name}.md"
            _write_entry(output_path, entry_meta, "")
            count += 1

    return count


# ---------------------------------------------------------------------------
# Logs scanner
# ---------------------------------------------------------------------------


def index_logs(root: Path, rag_dir: Path) -> int:
    """Scan runtime diagnostics from logs plus the ADR-743 job ledger.

    Output layout:
        rag_dir/logs/{category}.md
    """
    import shutil

    category_dir = rag_dir / "logs"
    if category_dir.exists():
        shutil.rmtree(category_dir)
    count = 0

    logs_dir = get_logs_dir()
    grouped: dict[str, dict[str, Any]] = {
        category: {
            "files": [],
            "sources": set(),
            "total_size": 0,
            "latest_file": None,
            "latest_rel": "",
            "latest_folder": "",
            "latest_name": "",
            "latest_modified": "",
        }
        for category in _LOG_SOURCE_ORDER
    }

    if logs_dir.is_dir():
        for log_file in sorted(logs_dir.rglob("*")):
            if not log_file.is_file():
                continue
            if any(part.startswith(".") for part in log_file.relative_to(logs_dir).parts):
                continue

            rel = log_file.relative_to(logs_dir)
            rel_str = rel.as_posix()
            parts = rel.parts
            source_name = parts[0] if len(parts) > 1 else log_file.stem
            category = _classify_log_category(source_name)
            stat = log_file.stat()
            modified = _mtime_iso(log_file)

            bucket = grouped[category]
            bucket["files"].append(log_file)
            bucket["sources"].add(source_name)
            bucket["total_size"] += stat.st_size

            if not bucket["latest_modified"] or modified > bucket["latest_modified"]:
                bucket["latest_file"] = str(log_file)
                bucket["latest_rel"] = rel_str
                bucket["latest_folder"] = str(log_file.parent)
                bucket["latest_name"] = log_file.name
                bucket["latest_modified"] = modified

    for category in _LOG_SOURCE_ORDER:
        bucket = grouped[category]
        files: list[Path] = bucket["files"]
        if not files:
            continue

        config = _LOG_SOURCE_CONFIG[category]
        file_count = len(files)
        source_count = len(bucket["sources"])
        total_size = bucket["total_size"]
        latest_file = bucket["latest_file"] or str(logs_dir)
        latest_rel = bucket["latest_rel"] or ""
        latest_folder = bucket["latest_folder"] or str(logs_dir)
        latest_name = bucket["latest_name"] or Path(latest_file).name
        latest_modified = bucket["latest_modified"] or ""

        entry_meta = {
            "type": "log",
            "hub": "system",
            "id": category,
            "name": category,
            "title": config["label"],
            "source_path": latest_file,
            "description": config["description"],
            "category": category,
            "category_label": config["label"],
            "logs_root_path": str(logs_dir),
            "latest_file_path": latest_file,
            "latest_file_name": latest_name,
            "latest_folder_path": latest_folder,
            "latest_relative_path": latest_rel,
            "file_count": str(file_count),
            "source_count": str(source_count),
            "total_size_bytes": str(total_size),
            "total_size_human": _human_size(total_size),
            "checksum": _checksum(files[0]),
            "modified": latest_modified,
        }

        output_path = category_dir / f"{category}.md"
        _write_entry(output_path, entry_meta)
        count += 1

    if _write_job_ledger_log_entry(category_dir):
        count += 1

    return count


# ---------------------------------------------------------------------------
# Pages scanner
# ---------------------------------------------------------------------------


_RESERVED_PAGE_IDS = {"overview", "settings", "layout", "login"}


def index_pages(root: Path, rag_dir: Path, documents_dir: Path | None = None) -> int:
    """Scan contributions.pages, YAML page files, and sidecar-backed HTML artifacts.

    Three sources:
        1. contributions.pages declared in SKILL.md (namespaced by skill)
        2. YAML page files under augur/pages/ not declared in contributions
        3. Sidecar-backed HTML artifacts under the documents dir (Pass 3),
           written as {hub}/artifact--{slug}.md

    Output layout:
        rag_dir/pages/{hub}/{skill}--{page_id}.md
        rag_dir/pages/{hub}/artifact--{slug}.md

    Collision protection: every skill page is keyed as {hub}/{skill}/{pageId}.
    Reserved page IDs (overview, settings, layout) are rejected with a warning.
    """
    import shutil

    log = get_entity_logger("lib.index._scanners_structural.pages")
    category_dir = rag_dir / "pages"
    if category_dir.exists():
        shutil.rmtree(category_dir)

    # Collect all pages first, keyed by (hub, skill, pageId)
    all_pages: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()  # (hub, skill, pageId)

    # ── Pass 1: contributions.pages from SKILL.md ──────────────────────
    for bundle_name, skill_dir in _discover_skill_dirs(root):
        skill_md = skill_dir / "SKILL.md"
        config_source = skill_md if skill_md.exists() else skill_dir / "augur" / "augur.yaml"
        data = _read_skill_config(skill_md)
        if not data:
            continue

        contributions = data.get("contributions") or {}
        if not isinstance(contributions, dict):
            continue

        pages = contributions.get("pages") or []
        if not isinstance(pages, list):
            continue

        skill_name = skill_dir.name
        try:
            source_path = str(config_source.relative_to(root))
        except ValueError:
            source_path = str(config_source)

        for page in pages:
            if not isinstance(page, dict):
                continue
            page_id = page.get("id")
            if not page_id:
                continue
            if page_id in _RESERVED_PAGE_IDS:
                log.debug(
                    "Skill %s declares reserved page ID '%s' — remapped to '%s'",
                    skill_name,
                    page_id,
                    skill_name,
                )
                page_id = skill_name

            key = (bundle_name, skill_name, page_id)
            if key in seen:
                continue
            seen.add(key)

            # Determine page type
            page_type = page.get("page_type", "")
            if not page_type:
                yaml_path = skill_dir / "augur" / "pages" / f"{page_id}.yaml"
                page_type = "yaml" if yaml_path.exists() else "custom"

            # Construct route
            explicit_route = page.get("route", "")
            if not explicit_route:
                if page_id == skill_name:
                    explicit_route = f"/{bundle_name}/{page_id}"
                else:
                    explicit_route = f"/{bundle_name}/{skill_name}/{page_id}"

            all_pages.append(
                {
                    "hub": bundle_name,
                    "skill": skill_name,
                    "page_id": page_id,
                    "source_path": source_path,
                    "description": page.get("problem_statement") or page.get("purpose") or page.get("title", ""),
                    "route": explicit_route,
                    "state": page.get("state", ""),
                    "pageType": page_type,
                    "checksum": _checksum(config_source),
                    "modified": _mtime_iso(config_source),
                }
            )

    # ── Pass 2: YAML page files not declared in contributions ──────────
    for bundle_name, skill_dir in _discover_skill_dirs(root):
        yaml_dir = skill_dir / "augur" / "pages"
        if not yaml_dir.is_dir():
            continue
        skill_name = skill_dir.name
        skill_md = skill_dir / "SKILL.md"
        try:
            rel_source = str(skill_md.relative_to(root)) if skill_md.exists() else ""
        except ValueError:
            rel_source = ""

        for yaml_file in sorted(yaml_dir.glob("*.yaml")):
            page_id = yaml_file.stem
            if page_id in _RESERVED_PAGE_IDS:
                log.debug(
                    "YAML page %s uses reserved ID '%s' — remapped to '%s'",
                    yaml_file.name,
                    page_id,
                    skill_name,
                )
                page_id = skill_name
            key = (bundle_name, skill_name, page_id)
            if key in seen:
                continue
            seen.add(key)

            # Read title and route from YAML
            title = ""
            yaml_route = ""
            try:
                for line in yaml_file.read_text(encoding="utf-8").splitlines():
                    if line.startswith("title:"):
                        title = line.split(":", 1)[1].strip().strip("'\"")
                    elif line.startswith("route:"):
                        yaml_route = line.split(":", 1)[1].strip().strip("'\"")
            except Exception:
                pass

            # Use explicit route from YAML, prefix with hub if relative
            if yaml_route:
                route = yaml_route if yaml_route.startswith("/") else f"/{bundle_name}/{yaml_route}"
            else:
                route = (
                    f"/{bundle_name}/{skill_name}/{page_id}" if page_id != skill_name else f"/{bundle_name}/{page_id}"
                )
            all_pages.append(
                {
                    "hub": bundle_name,
                    "skill": skill_name,
                    "page_id": page_id,
                    "source_path": rel_source or str(yaml_file),
                    "description": title or f"{page_id} YAML page",
                    "route": route,
                    "state": "",
                    "pageType": "yaml",
                    "checksum": _checksum(yaml_file),
                    "modified": _mtime_iso(yaml_file),
                }
            )

    # ── Collision detection: warn when same hub+pageId from different skills ──
    from collections import defaultdict

    hub_page_map: dict[tuple[str, str], list[str]] = defaultdict(list)
    for p in all_pages:
        hub_page_map[(p["hub"], p["page_id"])].append(p["skill"])
    for (hub, pid), skills in hub_page_map.items():
        if len(skills) > 1:
            log.warning("Page ID collision: %s/%s claimed by skills: %s", hub, pid, ", ".join(skills))

    # ── Write all pages with skill-namespaced filenames ────────────────
    count = 0
    for p in all_pages:
        safe_id = f"{p['skill']}--{p['page_id']}".replace("/", "__")
        entry_meta: dict[str, Any] = {
            "type": "page",
            "hub": p["hub"],
            "name": p["page_id"],
            "skill": p["skill"],
            "source_path": p["source_path"],
            "description": p["description"],
            "route": p["route"],
            "state": p["state"],
            "pageType": p["pageType"],
            "related": [f"skills/{p['hub']}/{p['skill']}"],
            "checksum": p["checksum"],
            "modified": p["modified"],
        }
        output_path = category_dir / p["hub"] / f"{safe_id}.md"
        _write_entry(output_path, entry_meta, "")
        count += 1

    # ── Pass 3: sidecar-backed HTML artifacts (Browse pages category) ──
    # Folds the artifacts-list live scan into the passive index so the
    # dashboard pages tab needs a single browse-index call (spec
    # 2026-06-10-browse-pages-load-speed-design.md).
    if documents_dir is None:
        try:
            from src.config.paths import get_documents_dir

            documents_dir = get_documents_dir()
        except Exception:
            documents_dir = None
    if documents_dir is not None and Path(documents_dir).is_dir():
        from src.lib.artifacts_sidecar import iter_artifact_files, read_sidecar

        for html_path, sidecar_path in iter_artifact_files(Path(documents_dir)):
            try:
                sc = read_sidecar(sidecar_path)
            except Exception:
                log.warning("Unreadable artifact sidecar: %s", sidecar_path)
                continue
            if not sc.slug:
                continue
            kind = sc.kind if sc.kind in ("generated", "saved") else "saved"
            hub = sc.hub or "uncategorized"
            entry_meta = {
                "type": "page",
                "hub": hub,
                "name": sc.slug,
                "title": sc.title or sc.slug,
                "description": f"{kind} HTML artifact",
                "source_path": str(html_path),
                "kind": kind,
                "slug": sc.slug,
                "url": f"/artifact/{sc.slug}",
                "path": str(html_path),
                "promoted_at": sc.promoted_at,
                "created_at": sc.created_at,
                "tags": list(sc.tags or []),
                "checksum": _checksum(html_path),
                "modified": _mtime_iso(html_path),
            }
            safe_id = f"artifact--{sc.slug}".replace("/", "__")
            _write_entry(category_dir / hub / f"{safe_id}.md", entry_meta, "")
            count += 1

    return count


# ---------------------------------------------------------------------------
# Blocks scanner
# ---------------------------------------------------------------------------


def index_blocks(root: Path, rag_dir: Path) -> int:
    """Scan skill SKILL.md frontmatter for contributions.blocks lists.

    Output layout:
        rag_dir/blocks/{block-id}.md
    """
    import shutil

    category_dir = rag_dir / "blocks"
    if category_dir.exists():
        shutil.rmtree(category_dir)
    count = 0

    for bundle_name, skill_dir in _discover_skill_dirs(root):
        skill_md = skill_dir / "SKILL.md"
        data = _read_skill_config(skill_md)
        if not data:
            continue

        contributions = data.get("contributions") or {}
        if not isinstance(contributions, dict):
            continue

        blocks = contributions.get("blocks") or []
        if not isinstance(blocks, list):
            continue

        skill_name = skill_dir.name
        try:
            source_path = str(skill_md.relative_to(root))
        except ValueError:
            source_path = str(skill_md)
        skill_ref = f"skills/{bundle_name}/{skill_name}"

        # Build page context map: block_id -> page problem_statement
        # so blocks can inherit their parent page's description
        pages = contributions.get("pages") or []
        page_context: dict[str, str] = {}
        if isinstance(pages, list):
            for page in pages:
                if not isinstance(page, dict):
                    continue
                ps = page.get("problem_statement") or page.get("purpose") or ""
                if ps:
                    # Associate this description with all blocks on this page
                    page_context["_default"] = ps  # fallback for all blocks

        for block in blocks:
            if not isinstance(block, dict):
                continue
            block_id = block.get("id")
            if not block_id:
                continue

            block_title = block.get("title", "")
            block_type = block.get("type", "")
            data_source = block.get("data_source", {})
            mcp_tool = data_source.get("mcp_tool", "") if isinstance(data_source, dict) else ""

            # Build rich description: title + context from data source and parent page
            desc_parts = []
            if block_title:
                desc_parts.append(block_title)
            if block_type:
                desc_parts.append(block_type)
            # Add parent page context if available
            parent_desc = page_context.get("_default", "")
            if parent_desc:
                desc_parts.append(parent_desc)
            elif mcp_tool:
                desc_parts.append(f"via {mcp_tool}")

            description = " · ".join(desc_parts) if desc_parts else f"{skill_name} block"

            entry_meta: dict[str, Any] = {
                "type": "block",
                "hub": bundle_name,
                "name": block_id,
                "source_path": source_path,
                "description": description,
                "block_type": block_type,
                "skill": skill_name,
                "related": [skill_ref],
                "checksum": _checksum(skill_md),
                "modified": _mtime_iso(skill_md),
            }
            if mcp_tool:
                entry_meta["mcp_tool"] = mcp_tool

            output_path = category_dir / f"{block_id}.md"
            _write_entry(output_path, entry_meta, "")
            count += 1

    return count


# ---------------------------------------------------------------------------
# MCP tools scanner
# ---------------------------------------------------------------------------


def _extract_tool_name(decorator_node) -> "str | None":
    """Extract tool name from @mcp.tool(name='...') decorator."""
    import ast

    if isinstance(decorator_node, ast.Call):
        for kw in decorator_node.keywords:
            if kw.arg == "name" and isinstance(kw.value, ast.Constant):
                return kw.value.value
    return None


def _scan_py_for_mcp_tools(
    py_file: Path,
    root: Path,
    category_dir: Path,
    hub: str,
    skill_name: str,
    skill_ref: str,
) -> int:
    """Parse a single .py file for @mcp.tool() decorators and write index entries.

    Returns the number of tools found.
    """
    import ast

    try:
        tree = ast.parse(py_file.read_text(errors="replace"))
    except SyntaxError:
        return 0

    try:
        source_path = str(py_file.relative_to(root))
    except ValueError:
        source_path = str(py_file)

    count = 0
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        for decorator in node.decorator_list:
            tool_name = _extract_tool_name(decorator)
            if tool_name is None:
                continue

            description = ""
            if (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            ):
                first_line = node.body[0].value.value.strip().splitlines()[0]
                description = first_line.strip()

            entry_meta: dict[str, Any] = {
                "type": "mcp-tool",
                "hub": hub,
                "bundle": hub,
                "skill": skill_name,
                "name": tool_name,
                "source_path": source_path,
                "description": description,
                "related": [skill_ref],
                "checksum": _checksum(py_file),
                "modified": _mtime_iso(py_file),
            }

            output_path = category_dir / f"{tool_name}.md"
            _write_entry(output_path, entry_meta, "")
            count += 1

    return count


def _iter_skill_mcp_dirs(skill_dir: Path) -> list[Path]:
    """Return skill-owned MCP package dirs under scripts/, including subpackages."""
    scripts_dir = skill_dir / "scripts"
    if not scripts_dir.is_dir():
        return []

    dirs: list[Path] = []
    for candidate in sorted(scripts_dir.rglob("mcp")):
        if not candidate.is_dir():
            continue
        if any(part.startswith(".") or part == "__pycache__" for part in candidate.parts):
            continue
        dirs.append(candidate)
    return dirs


def index_mcp_tools(root: Path, rag_dir: Path) -> int:
    """Scan skill scripts/**/mcp dirs and framework MCP packages for @mcp.tool() decorators.

    Sources:
      1. managed skills' scripts/**/mcp/**/*.py — all Python files, not just __init__.py
      2. src/mcp/augur_core|augur_framework|augur_shared/**/*.py — MCP server tools

    Output layout:
        rag_dir/mcp-tools/{tool-name}.md
    """
    import shutil

    category_dir = rag_dir / "mcp-tools"
    if category_dir.exists():
        shutil.rmtree(category_dir)
    count = 0

    # 1. Skill MCP tools — scan ALL .py files in skill-owned scripts/**/mcp directories
    for bundle_name, skill_dir in _discover_skill_dirs(root):
        skill_name = skill_dir.name
        skill_ref = f"skills/{bundle_name}/{skill_name}"

        for mcp_dir in _iter_skill_mcp_dirs(skill_dir):
            for py_file in mcp_dir.rglob("*.py"):
                count += _scan_py_for_mcp_tools(
                    py_file,
                    root,
                    category_dir,
                    bundle_name,
                    skill_name,
                    skill_ref,
                )

    # 2. Framework MCP tools — scan canonical MCP packages for infrastructure/domain tools.
    for namespace in ("augur_core", "augur_framework", "augur_shared"):
        mcp_dir = root / "src" / "mcp" / namespace
        if not mcp_dir.is_dir():
            continue
        for py_file in mcp_dir.rglob("*.py"):
            # Skip test files and non-tool files.
            if "/tests/" in str(py_file) or py_file.name.startswith("test_"):
                continue
            count += _scan_py_for_mcp_tools(
                py_file,
                root,
                category_dir,
                "system",
                "core",
                f"src/mcp/{namespace}",
            )

    return count


def index_mcp_servers(root: Path, rag_dir: Path) -> int:
    """Index configured MCP servers from config/system/mcp_servers.yaml."""
    import shutil
    from src.cli_config.manifest import load_manifest

    manifest = root / "config" / "system" / "mcp_servers.yaml"
    category_dir = rag_dir / "mcp-servers"
    if not manifest.exists():
        if category_dir.exists():
            shutil.rmtree(category_dir)
        return 0

    def manifest_error(reason: str) -> int:
        _write_mcp_server_manifest_error(category_dir, manifest, reason)
        return 0

    try:
        parsed = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    except OSError as exc:
        return manifest_error(f"Unable to read MCP server manifest: {exc}")
    except yaml.YAMLError as exc:
        return manifest_error(f"Invalid MCP server manifest YAML: {exc}")
    if not isinstance(parsed, dict):
        return manifest_error("MCP server manifest must be a YAML mapping.")
    if not any(key in parsed for key in ("project_tier", "vault_tier")):
        return manifest_error(
            "MCP server manifest must define project_tier or vault_tier.",
        )
    for key in ("project_tier", "vault_tier"):
        if key in parsed and not isinstance(parsed[key], list):
            return manifest_error(f"MCP server manifest field {key} must be a list.")

    try:
        manifest_data = load_manifest(manifest)
    except (OSError, yaml.YAMLError, ValueError, TypeError, AttributeError) as exc:
        return manifest_error(f"Invalid MCP server manifest: {exc}")

    entries: list[tuple[str, dict[str, Any], str]] = []
    used_filenames: set[str] = set()

    def reserve_safe_name(server_id: str) -> str:
        safe_base = re.sub(r"[^A-Za-z0-9_.-]+", "-", server_id).strip("-") or "server"
        safe_name = safe_base
        suffix = 2
        while f"{safe_name}.md" in used_filenames:
            safe_name = f"{safe_base}-{suffix}"
            suffix += 1
        used_filenames.add(f"{safe_name}.md")
        return safe_name

    for servers, tier in (
        (manifest_data.project_tier, "project-tier"),
        (manifest_data.vault_tier, "vault-tier"),
    ):
        for server in servers:
            server_id = server.id.strip()
            if not server_id:
                return manifest_error("MCP server manifest entry has a blank id.")
            safe_name = reserve_safe_name(server_id)
            args_text = " ".join(server.args)
            entry_meta = {
                "id": server_id,
                "title": server_id,
                "name": server_id,
                "description": server.description,
                "category": "mcp-servers",
                "tier": tier,
                "command": server.command,
                "args": args_text,
                "bundle": server.bundle or "",
                "bundle_path": server.bundle_path or "",
                "source_path": source_path_for(manifest, root),
                "status": "configured",
                "mtime": _mtime_iso(manifest),
                "checksum": _checksum(manifest),
            }
            body = "\n".join(
                line
                for line in [
                    f"# {server_id}",
                    "",
                    server.description,
                    "",
                    f"Tier: {tier}",
                    f"Command: {entry_meta['command']} {args_text}".strip(),
                    f"Bundle: {entry_meta['bundle']}" if entry_meta["bundle"] else "",
                    f"Bundle path: {entry_meta['bundle_path']}" if entry_meta["bundle_path"] else "",
                ]
                if line != ""
            )
            entries.append((safe_name, entry_meta, body))

    if category_dir.exists():
        shutil.rmtree(category_dir)
    count = 0
    for safe_name, entry_meta, body in entries:
        _write_entry(category_dir / f"{safe_name}.md", entry_meta, body)
        count += 1
    return count


def _write_mcp_server_manifest_error(category_dir: Path, manifest: Path, reason: str) -> None:
    """Keep previous MCP server output visible but mark it stale."""
    root = get_project_root().resolve()
    if category_dir.exists():
        for entry_file in sorted(category_dir.glob("*.md")):
            if entry_file.name == "__manifest-error.md":
                continue
            try:
                entry_meta, body = parse_frontmatter(entry_file)
            except Exception:
                continue
            entry_meta["status"] = "stale"
            entry_meta["index_status"] = "error"
            entry_meta["source_error"] = reason
            entry_meta.setdefault("source_path", source_path_for(manifest, root))
            write_frontmatter(entry_file, entry_meta, body)

    try:
        manifest_mtime = _mtime_iso(manifest)
    except OSError:
        manifest_mtime = ""
    try:
        manifest_checksum = _checksum(manifest)
    except OSError:
        manifest_checksum = ""

    error_meta = {
        "id": "mcp-server-manifest-error",
        "title": "MCP server manifest error",
        "name": "mcp-server-manifest-error",
        "description": reason,
        "category": "mcp-servers",
        "tier": "error",
        "command": "",
        "args": "",
        "bundle": "",
        "source_path": source_path_for(manifest, root),
        "status": "error",
        "index_status": "error",
        "source_error": reason,
        "mtime": manifest_mtime,
        "checksum": manifest_checksum,
    }
    _write_entry(
        category_dir / "__manifest-error.md",
        error_meta,
        f"# MCP server manifest error\n\n{reason}\n",
    )
