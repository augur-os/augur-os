"""Session-aware /keep artifact reconcile tools (spec 2026-06-11).

artifact-locate  — read-only sweep of ~/Downloads + the Google Drive mirror
                   for exported artifact version families.
artifact-keep    — file a payload into Documents by delegating to the existing
                   ingest packet lifecycle (stage -> route -> consume).
artifact-cleanup — trash-only cleanup of approved intermediates plus an
                   optional canonical move inside the Drive mirror.

The client agent owns judgment (which artifact, destination, approval); these
tools are atomic operations per CLAUDE.md rule 19.
"""

from __future__ import annotations

import base64
import json
import os
import re
import shutil
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

from src.mcp.augur_shared.annotations import tool_annotations
from src.mcp.augur_shared.logging import get_entity_logger

logger = get_entity_logger("mcp")

DEFAULT_EXTENSIONS = [".pptx", ".key", ".pdf", ".docx", ".html", ".md"]
MAX_CONTENT_BYTES = 25 * 1024 * 1024  # lane-2 base64 size guard
_MAX_WALK_DEPTH = 4

# Counter branch is end-anchored AND bounded to 1-3 digits: browser download
# counters are small integers ("deck (1)"), while 4-digit parentheticals are
# years ("Report (2024)") and must stay part of the family identity.
_VERSION_NOISE_RE = re.compile(
    r"(?:\s*\(\d{1,3}\)$)|(?:[\s_-]+v\d+$)|(?:[\s_-]+(?:final|draft|copy|latest)$)",
    re.IGNORECASE,
)


def drive_mirror_root() -> Path | None:
    """Google Drive for Desktop mount, resolved by glob (never hardcoded)."""
    cloud = Path.home() / "Library" / "CloudStorage"
    if not cloud.is_dir():
        return None
    for entry in sorted(cloud.glob("GoogleDrive-*")):
        my_drive = entry / "My Drive"
        if my_drive.is_dir():
            return my_drive
    return None


def default_roots() -> list[Path]:
    roots = [Path.home() / "Downloads"]
    mirror = drive_mirror_root()
    if mirror is not None:
        roots.append(mirror)
    return [r for r in roots if r.is_dir()]


def normalize_stem(filename: str) -> str:
    stem = Path(filename).stem
    prev = None
    while prev != stem:
        prev = stem
        stem = _VERSION_NOISE_RE.sub("", stem).strip()
    return re.sub(r"[\s_-]+", " ", stem).strip().lower()


def group_version_families(paths: list[Path]) -> list[dict[str, Any]]:
    """Group files into version families by (normalized stem, extension)."""
    buckets: dict[tuple[str, str], list[Path]] = {}
    for path in paths:
        key = (normalize_stem(path.name), path.suffix.lower())
        buckets.setdefault(key, []).append(path)

    families = []
    for (stem, suffix), members in sorted(buckets.items()):
        with_meta = []
        for member in members:
            try:
                stat = member.stat()
            except OSError:
                continue  # file vanished between walk and grouping
            with_meta.append({"path": str(member), "mtime": stat.st_mtime, "size": stat.st_size})
        if not with_meta:
            continue
        with_meta.sort(key=lambda m: m["mtime"])
        families.append(
            {
                "family": f"{stem}{suffix}",
                "members": with_meta,
                "latest": with_meta[-1]["path"],
            }
        )
    return families


def _iter_candidate_files(root: Path, cutoff: float, extensions: set[str]) -> list[Path]:
    hits: list[Path] = []
    root_depth = len(root.parts)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        if len(Path(dirpath).parts) - root_depth >= _MAX_WALK_DEPTH:
            dirnames[:] = []
        for name in filenames:
            if name.startswith("."):
                continue
            candidate = Path(dirpath) / name
            if candidate.suffix.lower() not in extensions:
                continue
            try:
                if candidate.stat().st_mtime < cutoff:
                    continue
            except OSError:
                continue
            hits.append(candidate)
    return hits


def _matches_hints(path: Path, normalized_hints: list[str]) -> bool:
    if not normalized_hints:
        return True
    stem = normalize_stem(path.name)
    if not stem:
        return False
    return any(hint in stem or stem in hint for hint in normalized_hints)


def artifact_locate_impl(
    name_hints: list[str],
    extensions: list[str] | None = None,
    hours_back: int = 48,
    roots: list[str] | None = None,
) -> str:
    try:
        search_roots = [Path(r).expanduser() for r in roots] if roots else default_roots()
        search_roots = [r for r in search_roots if r.is_dir()]
        ext_set = {e.lower() if e.startswith(".") else f".{e.lower()}" for e in (extensions or DEFAULT_EXTENSIONS)}
        cutoff = time.time() - max(1, hours_back) * 3600
        normalized_hints = [normalize_stem(h) for h in name_hints if h.strip()]

        candidates: list[Path] = []
        for root in search_roots:
            candidates.extend(
                p for p in _iter_candidate_files(root, cutoff, ext_set) if _matches_hints(p, normalized_hints)
            )

        return json.dumps(
            {
                "success": True,
                "families": group_version_families(candidates),
                "searched_roots": [str(r) for r in search_roots],
                "drive_mirror_mounted": drive_mirror_root() is not None,
                "hours_back": hours_back,
            }
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("artifact-locate failed")
        return json.dumps({"success": False, "error": str(exc)})


def _send_to_trash(path: Path) -> None:
    """Isolated for test monkeypatching. send2trash gives real Trash semantics:
    local files -> macOS Trash; Drive-mirror files -> Drive trash (30-day
    recovery). Never a hard delete."""
    from send2trash import send2trash

    send2trash(str(path))


def _under_allowed_root(path: Path, allowed: list[Path]) -> bool:
    """Return True if path resolves to (or under) at least one allowed root."""
    try:
        resolved = path.resolve(strict=True)
        return any(resolved.is_relative_to(root.resolve()) for root in allowed)
    except OSError:
        return False


def artifact_cleanup_impl(
    trash_paths: list[str],
    canonical_move: dict[str, str] | None = None,
    allowed_roots: list[str] | None = None,
) -> str:
    """Execute an approved cleanup plan. All-or-nothing: any invalid entry
    refuses the entire plan with nothing touched."""
    moved: dict[str, str] | None = None
    trashed: list[str] = []
    try:
        allowed = [Path(r).expanduser() for r in allowed_roots] if allowed_roots else default_roots()

        refused: list[dict[str, str]] = []

        # Validate all trash paths first, silently deduping by resolved path
        # (first occurrence wins).
        seen_resolved: set[Path] = set()
        valid_trash: list[Path] = []
        for raw in trash_paths:
            p = Path(raw).expanduser()
            if not p.is_file():
                refused.append({"path": raw, "reason": "not an existing file"})
                continue
            if not _under_allowed_root(p, allowed):
                refused.append({"path": raw, "reason": "outside allowed roots"})
                continue
            resolved = p.resolve()
            if resolved in seen_resolved:
                continue
            seen_resolved.add(resolved)
            valid_trash.append(p)

        # Validate canonical_move if provided.
        move_source: Path | None = None
        move_dest_folder: Path | None = None
        if canonical_move is not None:
            src_raw = canonical_move.get("source")
            dest_raw = canonical_move.get("dest_folder")
            if not src_raw:
                refused.append({"path": "", "reason": "canonical_move missing source"})
            elif not dest_raw:
                refused.append({"path": src_raw, "reason": "canonical_move missing dest_folder"})
            else:
                src = Path(src_raw).expanduser()
                dest_folder = Path(dest_raw).expanduser()
                if not src.is_file() or not _under_allowed_root(src, allowed):
                    refused.append({"path": str(src), "reason": "canonical source invalid"})
                elif src.resolve() in seen_resolved:
                    refused.append(
                        {
                            "path": str(src),
                            "reason": "canonical source also listed in trash_paths",
                        }
                    )
                elif not dest_folder.is_dir() or not _under_allowed_root(dest_folder, allowed):
                    refused.append(
                        {
                            "path": str(dest_folder),
                            "reason": (
                                "dest_folder must be an existing folder under an"
                                " allowed root (never create Drive folders)"
                            ),
                        }
                    )
                elif (dest_folder / src.name).exists():
                    refused.append({"path": str(dest_folder / src.name), "reason": "dest exists"})
                else:
                    move_source = src
                    move_dest_folder = dest_folder

        if refused:
            return json.dumps({"success": False, "refused": refused, "trashed": []})

        # Execute: canonical move first, then trash.
        if move_source is not None and move_dest_folder is not None:
            dest_path = move_dest_folder / move_source.name
            shutil.move(str(move_source), str(dest_path))
            moved = {"from": str(move_source), "to": str(dest_path)}
            logger.info("artifact-cleanup moved %s -> %s", move_source, dest_path)

        for p in valid_trash:
            _send_to_trash(p)
            trashed.append(str(p))
            logger.info("artifact-cleanup trashed %s", p)

        return json.dumps({"success": True, "moved": moved, "trashed": trashed, "refused": []})
    except Exception as exc:  # noqa: BLE001
        # Include any completed work so a mid-plan failure never hides it.
        return json.dumps({"success": False, "error": str(exc), "moved": moved, "trashed": trashed})


def _load_ingest_lifecycle():
    """Lazy import of the existing ingest packet lifecycle (the 'existing keep
    file path' from the spec). PYTHONPATH includes project-brain/capabilities
    in the framework server process (config/system/mcp_servers.yaml). Isolated
    in one function for test monkeypatching and to keep server startup light."""
    from skills.ingest.scripts.inbox_packet_consume import consume_packet
    from skills.ingest.scripts.inbox_packet_routing import propose_packet_route
    from skills.ingest.scripts.inbox_packets import stage_packet
    from skills.ingest.scripts.inbox_registry import load_inbox_registry

    def resolve_target(packet):
        registry = load_inbox_registry()
        # vault_by_id raises KeyError listing the available vault ids.
        return registry.vault_by_id(packet.target_vault or "personal")

    return stage_packet, resolve_target, propose_packet_route, consume_packet


def artifact_keep_impl(
    source_path: str = "",
    content_base64: str = "",
    filename: str = "",
    title: str = "",
    target_folder: str = "",
    user_instruction: str = "",
    source_id: str = "claude-chat",
) -> str:
    """File a payload into Documents via the existing ingest packet lifecycle
    (stage -> route -> consume). No new write path."""
    try:
        stage_packet, resolve_target, propose_route, consume = _load_ingest_lifecycle()

        if source_path:
            path = Path(source_path).expanduser()
            if not path.is_file():
                return json.dumps({"success": False, "error": f"not a file: {source_path}"})
            # Whole-file read is inherent to stage_packet(content: bytes); no
            # cap by design — lane-1 files come from Downloads/Drive mirror.
            content = path.read_bytes()
            final_name = filename or path.name
        elif content_base64:
            approx_size = len(content_base64) * 3 // 4
            if approx_size > MAX_CONTENT_BYTES:
                return json.dumps(
                    {
                        "success": False,
                        "error": (
                            f"content size ~{approx_size} bytes exceeds the"
                            f" {MAX_CONTENT_BYTES}-byte limit; download the file"
                            " locally and pass source_path instead"
                        ),
                    }
                )
            if not filename:
                return json.dumps(
                    {
                        "success": False,
                        "error": "filename is required with content_base64",
                    }
                )
            # validate=True: non-alphabet bytes (e.g. a pasted data-URI
            # prefix) raise binascii.Error -> caught by the broad except
            # below, instead of being silently discarded as corruption.
            content = base64.b64decode(content_base64, validate=True)
            final_name = filename
        else:
            return json.dumps({"success": False, "error": "provide source_path or content_base64"})

        packet = stage_packet(
            source_id=source_id,
            title=title or Path(final_name).stem,
            filename=final_name,
            content=content,
            user_instruction=user_instruction or "/keep session artifact reconcile",
            capture_mode="mcp_content",
        )
        target = resolve_target(packet)
        proposal = propose_route(packet, target)
        if target_folder and proposal.status == "ready":
            proposal = replace(
                proposal,
                target_folder=target_folder,
                route_reason="agent session judgment (/keep reconcile)",
            )
        result = consume(packet=packet, target=target, proposal=proposal)

        return json.dumps(
            {
                "success": result.status == "success",
                "status": result.status,
                "final_paths": list(result.final_paths),
                "sidecar_paths": list(result.sidecar_paths),
                "questions": list(result.questions),
            }
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("artifact-keep failed")
        return json.dumps({"success": False, "error": str(exc)})


def register_artifact_reconcile_tools(
    mcp: Any,
    mcp_tool_interceptor: Any,
    metrics: Any,
) -> None:
    """Wire session-reconcile tools onto the framework MCP server."""

    @mcp.tool(
        name="artifact-locate",
        annotations=tool_annotations(
            {
                "title": "Locate Exported Artifact Versions",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def artifact_locate(
        name_hints: list[str] | None = None,
        extensions: list[str] | None = None,
        hours_back: int = 48,
        roots: list[str] | None = None,
    ) -> str:
        metrics.track_tool("artifact_locate")
        return artifact_locate_impl(
            name_hints=name_hints or [],
            extensions=extensions,
            hours_back=hours_back,
            roots=roots,
        )

    @mcp.tool(
        name="artifact-keep",
        annotations=tool_annotations(
            {
                "title": "Keep Session Artifact in Documents",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def artifact_keep(
        source_path: str = "",
        content_base64: str = "",
        filename: str = "",
        title: str = "",
        target_folder: str = "",
        user_instruction: str = "",
    ) -> str:
        metrics.track_tool("artifact_keep")
        return artifact_keep_impl(
            source_path=source_path,
            content_base64=content_base64,
            filename=filename,
            title=title,
            target_folder=target_folder,
            user_instruction=user_instruction,
        )

    @mcp.tool(
        name="artifact-cleanup",
        annotations=tool_annotations(
            {
                "title": "Cleanup Approved Artifact Intermediates",
                "readOnlyHint": False,
                "destructiveHint": True,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def artifact_cleanup(
        trash_paths: list[str] | None = None,
        canonical_move: dict[str, str] | None = None,
    ) -> str:
        metrics.track_tool("artifact_cleanup")
        return artifact_cleanup_impl(
            trash_paths=trash_paths or [],
            canonical_move=canonical_move,
        )


__all__ = [
    "artifact_cleanup_impl",
    "artifact_keep_impl",
    "artifact_locate_impl",
    "drive_mirror_root",
    "default_roots",
    "normalize_stem",
    "group_version_families",
    "register_artifact_reconcile_tools",
]
