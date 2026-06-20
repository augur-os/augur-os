"""Memory profile, workspace, config, and cleanup MCP tools.

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
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

import yaml

from src.lib.frontmatter_utils import parse_frontmatter, write_frontmatter

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


logger = get_entity_logger("mcp.knowledge.memory.profile")

_H2_SECTION_RE = re.compile(r"^##\s+(?P<title>.+?)\s*$", re.MULTILINE)


def _resolve_workspace_target(path: str = "", file_id: str = "") -> str:
    if path:
        return path

    if not file_id:
        return path

    from src.config.paths import get_memory_dir, get_runtime_dir, get_vault_dir

    mem_dir = get_memory_dir()
    runtime_mem_dir = get_runtime_dir() / "memory"
    profile_path = get_vault_dir() / "wiki" / "profile-human-api.md"
    file_id_map = {
        "memory": str(mem_dir / "MEMORY.md"),
        "profile": str(profile_path),
        "report": str(profile_path),
        "daily": str(runtime_mem_dir / "daily"),
        "index": str(mem_dir / "index.yaml"),
    }
    return file_id_map.get(file_id, str(mem_dir / file_id))


def _profile_payload_to_markdown(payload: dict[str, Any]) -> str:
    frontmatter = {
        "role": payload.get("role") or "",
        "expertise": payload.get("expertise", []) or [],
        "communicationStyle": payload.get("communicationStyle") or "",
        "successCriteria": payload.get("successCriteria", []) or [],
        "contextGaps": payload.get("contextGaps", []) or [],
        "lastUpdated": payload.get("lastUpdated") or datetime.now(timezone.utc).isoformat(),
    }
    frontmatter_yaml = yaml.dump(
        frontmatter,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    ).strip()

    role = frontmatter["role"]
    expertise = frontmatter["expertise"]
    communication_style = frontmatter["communicationStyle"]
    success_criteria = frontmatter["successCriteria"]
    context_gaps = frontmatter["contextGaps"]

    lines = [
        "---",
        frontmatter_yaml,
        "---",
        "# Human API Profile",
        "",
        "## Role",
        str(role),
        "",
        "## Expertise",
    ]
    if expertise:
        lines.extend(f"- {item}" for item in expertise)
    else:
        lines.append("")
    lines.extend([
        "",
        "## Communication Style",
        str(communication_style),
        "",
        "## Success Criteria",
    ])
    if success_criteria:
        lines.extend(f"- {item}" for item in success_criteria)
    else:
        lines.append("")
    lines.extend([
        "",
        "## Context Gaps",
    ])
    if context_gaps:
        lines.extend(f"- {item}" for item in context_gaps)
    else:
        lines.append("")
    lines.append("")
    return "\n".join(lines)


def _profile_path() -> Path:
    from src.config.paths import get_vault_dir

    return get_vault_dir() / "wiki" / "profile-human-api.md"


def _extract_h2_sections(content: str) -> dict[str, str]:
    matches = list(_H2_SECTION_RE.finditer(content))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        title = match.group("title").strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        sections[title] = content[start:end].strip()
    return sections


def _normalize_text(section: str) -> str:
    return " ".join(line.strip() for line in section.splitlines() if line.strip())


def _first_text(section: str) -> str:
    for paragraph in section.split("\n\n"):
        text = _normalize_text(paragraph)
        if text:
            return text
    return ""


def _list_items(section: str) -> list[str]:
    items: list[str] = []
    for line in section.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            item = stripped[2:].strip()
            if item:
                items.append(item)
    if items:
        return items
    text = _normalize_text(section)
    return [text] if text else []


def _handle_profile(act: str, new_content: str | None) -> dict[str, Any]:
    profile_path = _profile_path()

    if act == "write":
        if new_content is None:
            return {"success": False, "error": "Content is required for write action"}
        profile_path.parent.mkdir(parents=True, exist_ok=True)
        if new_content.startswith("---"):
            profile_path.write_text(new_content, encoding="utf-8")
        else:
            write_frontmatter(
                profile_path,
                {"lastUpdated": datetime.now(timezone.utc).isoformat()},
                new_content,
            )

        # ADR-738 — emit typed edges for the profile note just written.
        try:
            import sys as _sys
            _graph_scripts = str(
                Path(__file__).resolve().parents[3] / "graph" / "scripts"
            )
            if _graph_scripts not in _sys.path:
                _sys.path.insert(0, _graph_scripts)
            import graph_ops  # type: ignore[import-not-found]

            graph_ops.index_page_from_write_path(profile_path, source_type="profile")
        except Exception:  # noqa: BLE001 — graph is best-effort, never breaks /profile
            pass

        return {"success": True}

    if not profile_path.exists():
        return {
            "exists": False,
            "role": "",
            "expertise": [],
            "communicationStyle": "",
            "successCriteria": [],
            "contextGaps": [],
            "lastUpdated": None,
            "rawContent": "",
        }

    metadata, body = parse_frontmatter(profile_path)
    raw = profile_path.read_text(encoding="utf-8")
    sections = _extract_h2_sections(body)
    stat = profile_path.stat()
    last_updated = (
        metadata.get("lastUpdated")
        or metadata.get("updated")
        or datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
    )

    return {
        "exists": True,
        "role": _first_text(sections.get("Role", "")),
        "expertise": _list_items(sections.get("Expertise", "")),
        "communicationStyle": _normalize_text(sections.get("Communication Style", "")),
        "successCriteria": _list_items(sections.get("Success Criteria", "")),
        "contextGaps": _list_items(sections.get("Context Gaps", "")),
        "lastUpdated": str(last_updated) if last_updated else None,
        "rawContent": raw,
    }


def register_memory_profile_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register memory profile, workspace, config, and cleanup tools."""

    # =========================================================================
    # Memory Profile & Workspace Tools
    # =========================================================================

    @mcp.tool(
        name="knowledge-memory-profile",
        annotations=tool_annotations(
            {
                "title": "Memory Profile (HUMAN_API)",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def knowledge_memory_profile_tool(
        action: str = "read",
        content: str | None = None,
        profile: dict | str | None = None,
        role: str | None = None,
        expertise: list[str] | None = None,
        communicationStyle: str | None = None,
        successCriteria: list[str] | None = None,
        contextGaps: list[str] | None = None,
    ) -> str:
        """Read or update the wiki-backed memory profile.

        Args:
            action: 'read' to get profile, 'update'/'write' to update it
            content: New content for write action
            profile: Profile data dict or string (dashboard alias for content)

        Returns:
            str: JSON with profile data or write confirmation
        """
        # Accept dashboard param name and 'update' action alias
        if action == "update":
            action = "write"
        structured_profile = {
            "role": role,
            "expertise": expertise,
            "communicationStyle": communicationStyle,
            "successCriteria": successCriteria,
            "contextGaps": contextGaps,
        }
        if content is None and any(value is not None for value in structured_profile.values()):
            content = _profile_payload_to_markdown(structured_profile)
        if content is None and profile is not None:
            if isinstance(profile, dict) and not any(value is not None for value in structured_profile.values()):
                content = json.dumps(profile)
            elif isinstance(profile, str):
                content = profile
        metrics.track_tool("knowledge_memory_profile", skill="knowledge")

        try:
            result = await asyncio.to_thread(_handle_profile, action, content)
            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to handle memory profile: {e}", exc_info=True)
            return json.dumps({"success": False, "error": str(e)})

    @mcp.tool(
        name="knowledge-memory-workspace-open",
        annotations=tool_annotations(
            {
                "title": "Open Workspace File",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def knowledge_memory_workspace_open_tool(
        path: str = "",
        file_id: str = "",
        fileId: str = "",
    ) -> str:
        """Open a workspace file in the system editor.

        Args:
            path: Relative or absolute path to a file in the memory workspace
            file_id: File ID to resolve to a workspace path (dashboard alias: fileId)
            fileId: Dashboard alias for file_id

        Returns:
            str: JSON confirmation
        """
        # Accept dashboard param names
        file_id = file_id or fileId
        path = _resolve_workspace_target(path=path, file_id=file_id)
        metrics.track_tool("knowledge_memory_workspace_open", skill="knowledge")

        def _open_workspace_file(file_path: str) -> dict[str, Any]:
            from src.config.paths import get_memory_dir

            p = Path(file_path)
            if not p.is_absolute():
                p = get_memory_dir() / p
            p = p.resolve()
            if not p.exists():
                return {"success": False, "error": f"File not found: {p}"}
            subprocess.Popen(["open", str(p)])
            return {"success": True, "fileId": p.name, "opened": str(p)}

        try:
            result = await asyncio.to_thread(_open_workspace_file, path)
            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to open workspace file: {e}", exc_info=True)
            return json.dumps({"success": False, "error": str(e)})

    @mcp.tool(
        name="knowledge-memory-config",
        annotations=tool_annotations(
            {
                "title": "Memory Configuration",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def knowledge_memory_config_tool() -> str:
        """Return memory system configuration and stats.

        Returns:
            str: JSON with memory config and stats
        """
        metrics.track_tool("knowledge_memory_config", skill="knowledge")

        def _get_memory_config() -> dict[str, Any]:
            from src.config.paths import get_memory_dir, get_runtime_dir

            mem_dir = get_memory_dir()
            daily_dir = get_runtime_dir() / "memory" / "daily"
            memory_file = mem_dir / "MEMORY.md"

            daily_count = 0
            total_size = 0
            if daily_dir.exists():
                for f in daily_dir.glob("*.md"):
                    daily_count += 1
                    total_size += f.stat().st_size

            last_curated = None
            if memory_file.exists():
                total_size += memory_file.stat().st_size
                # Try to parse last curated date from content
                try:
                    content = memory_file.read_text(encoding="utf-8")
                    match = re.search(r"\*Last curated:\s*(\d{4}-\d{2}-\d{2})\*", content)
                    if match:
                        last_curated = match.group(1)
                except Exception:
                    pass

            cleanup_targets: list[str] = []
            if daily_count > 30:
                cleanup_targets.append("old-logs")

            return {
                "success": True,
                "memoryDir": str(mem_dir),
                "dailyDir": str(daily_dir),
                "memoryFile": str(memory_file),
                "dailyLogs": daily_count,
                "memoryExists": memory_file.exists(),
                "lastCurated": last_curated,
                "cleanupTargets": cleanup_targets,
                "totalSize": total_size,
            }

        try:
            result = await asyncio.to_thread(_get_memory_config)
            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to get memory config: {e}", exc_info=True)
            return json.dumps({"success": False, "error": str(e)})

    @mcp.tool(
        name="knowledge-memory-cleanup",
        annotations=tool_annotations(
            {
                "title": "Cleanup Memory Logs",
                "readOnlyHint": False,
                "destructiveHint": True,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def knowledge_memory_cleanup_tool(
        target: str = "old-logs",
        days_keep: int = 30,
        save_memory: bool = True,
        saveMemory: bool = True,
    ) -> str:
        """Clean up old daily logs.

        Args:
            target: Cleanup target ('old-logs' or 'all-logs')
            days_keep: Number of days to keep (default 30)
            save_memory: Whether to save memory after cleanup (dashboard alias: saveMemory)
            saveMemory: Dashboard alias for save_memory

        Returns:
            str: JSON with cleanup results
        """
        # Accept dashboard param name
        save_memory = save_memory and saveMemory  # both default True, either False wins
        metrics.track_tool("knowledge_memory_cleanup", skill="knowledge")

        def _cleanup_logs(t: str, keep: int) -> dict[str, Any]:
            from src.config.paths import get_runtime_dir

            daily_dir = get_runtime_dir() / "memory" / "daily"
            if not daily_dir.exists():
                return {"success": True, "target": t, "filesRemoved": 0, "sizeMb": 0.0, "memorySaved": True}

            now = datetime.now()
            removed = 0
            total_bytes = 0

            for f in sorted(daily_dir.glob("*.md")):
                should_remove = False
                if t == "all-logs":
                    should_remove = True
                else:
                    # Parse date from filename
                    try:
                        file_date = datetime.strptime(f.stem, "%Y-%m-%d")
                        age_days = (now - file_date).days
                        if age_days > keep:
                            should_remove = True
                    except ValueError:
                        continue

                if should_remove:
                    size = f.stat().st_size
                    f.unlink()
                    removed += 1
                    total_bytes += size

            return {
                "success": True,
                "target": t,
                "filesRemoved": removed,
                "sizeMb": round(total_bytes / (1024 * 1024), 2),
                "memorySaved": True,
            }

        try:
            result = await asyncio.to_thread(_cleanup_logs, target, days_keep)
            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to cleanup memory logs: {e}", exc_info=True)
            return json.dumps({"success": False, "error": str(e)})
