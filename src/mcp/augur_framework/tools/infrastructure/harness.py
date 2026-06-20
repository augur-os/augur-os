"""Brain Harness snapshot assembly and MCP tools.

The snapshot is generated runtime and cache state. Canonical facts remain in
decentralized sources such as SKILL.md frontmatter, MCP registrations, page
discovery, docs, and runtime scanner outputs.
"""

from __future__ import annotations

import ast
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.config.paths import get_cache_dir, get_project_brain_skills_dir, get_project_root
from src.lib.brain_manager_snapshot import (
    harness_demote_capability,
    harness_manager_snapshot,
    harness_promote_capability,
)
from src.lib.brain_stack import resolve_active_stack
from src.lib.frontmatter_utils import parse_frontmatter
from src.mcp.augur_shared.annotations import tool_annotations

CAPABILITY_TYPES = {
    "memory",
    "skill",
    "mcp_tool",
    "dashboard_page",
    "command",
    "protocol",
    "loop",
    "document_surface",
}

SNAPSHOT_VERSION = "1.0"
SNAPSHOT_FILENAME = "brain-harness-snapshot.json"


if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _iter_skill_files(project_root: Path) -> list[Path]:
    skills_dir = get_project_brain_skills_dir(project_root)
    if not skills_dir.is_dir():
        return []
    return sorted(skills_dir.glob("*/SKILL.md"))


def _is_mcp_tool_decorator(func: ast.AST) -> bool:
    return (
        isinstance(func, ast.Attribute)
        and func.attr == "tool"
        and isinstance(func.value, ast.Name)
        and func.value.id == "mcp"
    )


def _extract_mcp_tool_name(decorator: ast.AST) -> str | None:
    if not isinstance(decorator, ast.Call):
        return None
    if not _is_mcp_tool_decorator(decorator.func):
        return None

    for keyword in decorator.keywords:
        if keyword.arg != "name":
            continue
        if isinstance(keyword.value, ast.Constant):
            value = keyword.value.value
            if isinstance(value, str) and value.strip():
                return value.strip()
    if decorator.args:
        first = decorator.args[0]
        if isinstance(first, ast.Constant):
            value = first.value
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _scan_failure_diagnostic(path: str, message: str) -> dict[str, Any]:
    return {
        "id": f"diagnostic:scan-failure:{path.replace('/', '_')}",
        "severity": "warning",
        "family": "structural_integrity",
        "reason": f"Failed to scan MCP source '{path}': {message}",
        "affected_capability_ids": [],
        "source_path": path,
        "recommended_action": {
            "kind": "dispatch_ide_repair",
            "label": "Review malformed MCP source and repair scanner-safe declaration",
        },
    }


def _duplicate_capability_diagnostic(capability_id: str, canonical_path: str, duplicate_path: str) -> dict[str, Any]:
    return {
        "id": f"diagnostic:duplicate-capability:{capability_id.replace(':', '-')}",
        "severity": "warning",
        "family": "structural_integrity",
        "reason": (
            f"Duplicate capability '{capability_id}' declared in '{duplicate_path}'. "
            f"Using canonical declaration from '{canonical_path}'."
        ),
        "affected_capability_ids": [capability_id],
        "source_path": duplicate_path,
        "recommended_action": {
            "kind": "dispatch_ide_repair",
            "label": "Resolve duplicate capability declaration",
        },
    }


def _scan_mcp_tool_registrations(project_root: Path) -> tuple[dict[str, str], list[dict[str, Any]]]:
    registrations: dict[str, str] = {}
    partial_failures: list[dict[str, Any]] = []
    for search_dir in (project_root / "src" / "mcp", get_project_brain_skills_dir(project_root)):
        if not search_dir.is_dir():
            continue
        for py_file in sorted(search_dir.rglob("*.py")):
            rel_path = _rel(py_file, project_root)
            try:
                content = py_file.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                partial_failures.append({"path": rel_path, "phase": "read", "error": str(exc)})
                continue
            try:
                module = ast.parse(content)
            except SyntaxError as exc:
                partial_failures.append(
                    {
                        "path": rel_path,
                        "phase": "parse",
                        "error": str(exc),
                        "line": exc.lineno,
                    }
                )
                continue

            for node in ast.walk(module):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                for decorator in node.decorator_list:
                    tool_name = _extract_mcp_tool_name(decorator)
                    if not tool_name:
                        continue
                    registrations.setdefault(tool_name, rel_path)
    return registrations, partial_failures


def _capability(
    *,
    capability_id: str,
    capability_type: str,
    label: str,
    source_path: str,
    hub: str | None = None,
    owner_skill: str | None = None,
    summary: str = "",
    status: str = "mapped",
    tags: list[str] | None = None,
    declared_by: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": capability_id,
        "type": capability_type,
        "label": label,
        "hub": hub,
        "owner_skill": owner_skill,
        "source_path": source_path,
        "summary": summary,
        "tags": tags or [],
        "status": status,
        "declared_by": declared_by if declared_by is not None else ([owner_skill] if owner_skill else []),
    }


def _relationship(
    *,
    from_id: str,
    to_id: str,
    kind: str,
    source_path: str,
    confidence: str = "high",
) -> dict[str, str]:
    return {
        "from_id": from_id,
        "to_id": to_id,
        "kind": kind,
        "source_path": source_path,
        "confidence": confidence,
    }


def _missing_tool_diagnostic(tool_name: str, source_path: str) -> dict[str, Any]:
    return {
        "id": f"diagnostic:missing-mcp-tool:{tool_name}",
        "severity": "warning",
        "family": "dashboard_mcp_wiring",
        "reason": f"Skill declares MCP tool '{tool_name}' but no @mcp.tool registration was found.",
        "affected_capability_ids": [f"mcp_tool:{tool_name}"],
        "source_path": source_path,
        "recommended_action": {
            "kind": "dispatch_ide_repair",
            "label": "Ask IDE agent to repair missing MCP tool wiring",
        },
    }


def _register_capability(
    *,
    capability: dict[str, Any],
    capability_index: dict[str, dict[str, Any]],
    capabilities: list[dict[str, Any]],
    diagnostics: list[dict[str, Any]],
) -> None:
    capability_id = capability["id"]
    existing = capability_index.get(capability_id)
    if existing is None:
        capabilities.append(capability)
        capability_index[capability_id] = capability
        return

    existing_declared_by = existing.setdefault(
        "declared_by",
        [existing.get("owner_skill")] if existing.get("owner_skill") else [],
    )
    owner_skill = capability.get("owner_skill")
    if owner_skill and owner_skill not in existing_declared_by:
        existing_declared_by.append(owner_skill)

    diagnostics.append(
        _duplicate_capability_diagnostic(
            capability_id,
            canonical_path=existing.get("source_path", ""),
            duplicate_path=capability.get("source_path", ""),
        )
    )


def build_harness_snapshot(project_root: Path | None = None, *, generated_at: str | None = None) -> dict[str, Any]:
    root = (project_root or get_project_root()).resolve()
    generated = generated_at or _utc_now()
    tool_registrations, partial_failures = _scan_mcp_tool_registrations(root)

    capabilities: list[dict[str, Any]] = []
    relationships: list[dict[str, str]] = []
    diagnostics: list[dict[str, Any]] = []
    capability_index: dict[str, dict[str, Any]] = {}

    for failure in partial_failures:
        diagnostics.append(_scan_failure_diagnostic(failure["path"], failure["error"]))

    for skill_md in _iter_skill_files(root):
        source_path = _rel(skill_md, root)
        frontmatter, _body = parse_frontmatter(skill_md)
        skill_name = str(frontmatter.get("name") or skill_md.parent.name)
        hub = None  # x-augur-hub removed by ADR-802
        description = frontmatter.get("description")
        summary = description if isinstance(description, str) else ""
        skill_id = f"skill:{skill_name}"

        _register_capability(
            capability=_capability(
                capability_id=skill_id,
                capability_type="skill",
                label=skill_name,
                hub=hub,
                owner_skill=skill_name,
                source_path=source_path,
                summary=summary,
            ),
            capability_index=capability_index,
            capabilities=capabilities,
            diagnostics=diagnostics,
        )

        for tool_name in frontmatter.get("x-augur-mcp-tools") or []:
            if not isinstance(tool_name, str) or not tool_name:
                continue
            tool_id = f"mcp_tool:{tool_name}"
            _register_capability(
                capability=_capability(
                    capability_id=tool_id,
                    capability_type="mcp_tool",
                    label=tool_name,
                    hub=hub,
                    owner_skill=skill_name,
                    source_path=tool_registrations.get(tool_name, source_path),
                    status="registered" if tool_name in tool_registrations else "declared_missing_registration",
                ),
                capability_index=capability_index,
                capabilities=capabilities,
                diagnostics=diagnostics,
            )
            relationships.append(
                _relationship(
                    from_id=skill_id,
                    to_id=tool_id,
                    kind="skill_declares_tool",
                    source_path=source_path,
                )
            )
            if tool_name not in tool_registrations:
                diagnostics.append(_missing_tool_diagnostic(tool_name, source_path))

        for page_path in frontmatter.get("x-augur-dashboard-pages") or []:
            if not isinstance(page_path, str) or not page_path:
                continue
            page_id = f"dashboard_page:{page_path}"
            _register_capability(
                capability=_capability(
                    capability_id=page_id,
                    capability_type="dashboard_page",
                    label=page_path,
                    hub=hub,
                    owner_skill=skill_name,
                    source_path=source_path,
                ),
                capability_index=capability_index,
                capabilities=capabilities,
                diagnostics=diagnostics,
            )
            relationships.append(
                _relationship(
                    from_id=skill_id,
                    to_id=page_id,
                    kind="skill_owns_page",
                    source_path=source_path,
                )
            )

        for command in frontmatter.get("x-augur-commands") or []:
            if not isinstance(command, dict) or not command.get("id"):
                continue
            command_id = f"command:{skill_name}:{command['id']}"
            _register_capability(
                capability=_capability(
                    capability_id=command_id,
                    capability_type="command",
                    label=str(command["id"]),
                    hub=hub,
                    owner_skill=skill_name,
                    source_path=source_path,
                    summary=str(command.get("description") or ""),
                ),
                capability_index=capability_index,
                capabilities=capabilities,
                diagnostics=diagnostics,
            )
            relationships.append(
                _relationship(
                    from_id=skill_id,
                    to_id=command_id,
                    kind="skill_declares_command",
                    source_path=source_path,
                )
            )

    return {
        "version": SNAPSHOT_VERSION,
        "generated_at": generated,
        "capabilities": capabilities,
        "relationships": relationships,
        "diagnostics": diagnostics,
        "actions": _safe_actions(),
        "provenance": {
            "project_root": str(root),
            "source_counts": {
                "skills": len(_iter_skill_files(root)),
                "mcp_tool_registrations": len(tool_registrations),
            },
            "partial_failures": partial_failures,
        },
    }


def harness_snapshot_path(cache_dir: Path | None = None) -> Path:
    return (cache_dir or get_cache_dir()) / "harness" / SNAPSHOT_FILENAME


def write_harness_snapshot_file(path: Path, snapshot: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_harness_snapshot_file(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_actions() -> list[dict[str, Any]]:
    return [
        {"kind": "refresh_snapshot", "label": "Refresh snapshot", "direct": True},
        {
            "kind": "reindex_knowledge",
            "label": "Rebuild memory index",
            "direct": True,
            "mcp_tool": "memory-rebuild-index",
        },
        {
            "kind": "reindex_browse",
            "label": "Reindex Browse category",
            "direct": True,
            "mcp_tool": "reindex-browse-category",
        },
        {"kind": "dispatch_ide_repair", "label": "Ask IDE agent to repair", "direct": False},
    ]


def _manager_actions() -> list[dict[str, Any]]:
    return [
        {"kind": "refresh_manager_snapshot", "label": "Refresh manager snapshot", "direct": True},
        {
            "kind": "promote_capability",
            "label": "Promote capability",
            "direct": True,
            "mcp_tool": "harness-promote-capability",
        },
        {
            "kind": "demote_capability",
            "label": "Demote capability",
            "direct": True,
            "mcp_tool": "harness-demote-capability",
        },
    ]


def get_brain_harness_snapshot_impl(*, snapshot_path: Path | None = None) -> dict[str, Any]:
    path = snapshot_path or harness_snapshot_path()
    if not path.exists():
        return {
            "success": True,
            "state": "missing",
            "snapshot": None,
            "actions": _safe_actions(),
        }
    return {
        "success": True,
        "state": "ready",
        "snapshot": read_harness_snapshot_file(path),
        "actions": _safe_actions(),
    }


def harness_manager_snapshot_impl(*, project_root: Path | None = None) -> dict[str, Any]:
    root = project_root or get_project_root()
    stack = resolve_active_stack(cwd=root)
    return {
        "success": True,
        "state": "ready",
        "snapshot": harness_manager_snapshot(stack, project_root=root),
        "actions": _manager_actions(),
    }


def harness_promote_capability_impl(
    *,
    capability_type: str,
    name: str,
    source_path: str,
    target_tier: str,
    replace: bool = False,
    remove_source: bool = False,
    project_root: Path | None = None,
) -> dict[str, Any]:
    root = project_root or get_project_root()
    stack = resolve_active_stack(cwd=root)
    return harness_promote_capability(
        stack,
        capability_type=capability_type,
        name=name,
        source_path=source_path,
        target_tier=target_tier,
        project_root=root,
        replace=replace,
        remove_source=remove_source,
    )


def harness_demote_capability_impl(
    *,
    capability_type: str,
    name: str,
    target_client: str,
    target_scope: str = "local",
    replace: bool = False,
    remove_source: bool = False,
    project_root: Path | None = None,
) -> dict[str, Any]:
    root = project_root or get_project_root()
    stack = resolve_active_stack(cwd=root)
    return harness_demote_capability(
        stack,
        capability_type=capability_type,
        name=name,
        target_client=target_client,
        target_scope=target_scope,
        project_root=root,
        replace=replace,
        remove_source=remove_source,
    )


def refresh_brain_harness_snapshot_impl(
    *,
    project_root: Path | None = None,
    snapshot_path: Path | None = None,
) -> dict[str, Any]:
    snapshot = build_harness_snapshot(project_root)
    path = snapshot_path or harness_snapshot_path()
    write_harness_snapshot_file(path, snapshot)
    return {
        "success": True,
        "state": "ready",
        "snapshot": snapshot,
        "actions": _safe_actions(),
    }


def register_harness_tools(mcp: FastMCP, mcp_tool_interceptor: Callable[..., Any], metrics: Any) -> None:
    """Register Brain Harness control-plane MCP tools."""

    @mcp.tool(
        name="harness-manager-snapshot",
        annotations=tool_annotations(
            {
                "title": "Harness Manager Snapshot",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def harness_manager_snapshot_tool() -> str:
        return json.dumps(harness_manager_snapshot_impl())

    @mcp.tool(
        name="harness-promote-capability",
        annotations=tool_annotations(
            {
                "title": "Harness Promote Capability",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def harness_promote_capability_tool(
        capability_type: str,
        name: str,
        source_path: str,
        target_tier: str,
        replace: bool = False,
        remove_source: bool = False,
    ) -> str:
        return json.dumps(
            harness_promote_capability_impl(
                capability_type=capability_type,
                name=name,
                source_path=source_path,
                target_tier=target_tier,
                replace=replace,
                remove_source=remove_source,
            )
        )

    @mcp.tool(
        name="harness-demote-capability",
        annotations=tool_annotations(
            {
                "title": "Harness Demote Capability",
                "readOnlyHint": False,
                "destructiveHint": True,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def harness_demote_capability_tool(
        capability_type: str,
        name: str,
        target_client: str,
        target_scope: str = "local",
        replace: bool = False,
        remove_source: bool = False,
    ) -> str:
        return json.dumps(
            harness_demote_capability_impl(
                capability_type=capability_type,
                name=name,
                target_client=target_client,
                target_scope=target_scope,
                replace=replace,
                remove_source=remove_source,
            )
        )

    @mcp.tool(
        name="get-brain-harness-snapshot",
        annotations=tool_annotations(
            {
                "title": "Get Brain Harness Snapshot",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def get_brain_harness_snapshot() -> str:
        return json.dumps(get_brain_harness_snapshot_impl())

    @mcp.tool(
        name="refresh-brain-harness-snapshot",
        annotations=tool_annotations(
            {
                "title": "Refresh Brain Harness Snapshot",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def refresh_brain_harness_snapshot() -> str:
        if metrics is not None:
            metrics.track_tool("refresh_brain_harness_snapshot", skill="augur-core")
        return json.dumps(refresh_brain_harness_snapshot_impl())


__all__ = [
    "CAPABILITY_TYPES",
    "SNAPSHOT_VERSION",
    "SNAPSHOT_FILENAME",
    "_rel",
    "_iter_skill_files",
    "_safe_actions",
    "build_harness_snapshot",
    "harness_snapshot_path",
    "read_harness_snapshot_file",
    "write_harness_snapshot_file",
    "get_brain_harness_snapshot_impl",
    "harness_manager_snapshot_impl",
    "harness_promote_capability_impl",
    "harness_demote_capability_impl",
    "refresh_brain_harness_snapshot_impl",
    "register_harness_tools",
]
