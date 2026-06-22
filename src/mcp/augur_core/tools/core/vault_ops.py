"""Vault file read/write operations.

Generic tools for reading and writing individual vault files.
Used by TSX pages that need full file content (not just previews).
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config.paths import get_runtime_dir
from src.lib.frontmatter_utils import (
    merge_system_user,
    parse_frontmatter,
    split_system_user,
    write_frontmatter,
)
from src.mcp.augur_shared.config import get_skill_data_dir


async def vault_file_read_impl(skill: str, path: str) -> str:
    """Read full content of a vault file by relative path."""
    vault_dir = get_skill_data_dir(skill)
    if not vault_dir.is_dir():
        return json.dumps({"success": False, "error": f"Skill vault dir not found: {skill}"})

    target = (vault_dir / path).resolve()

    # Security: prevent path traversal outside skill vault dir
    try:
        target.relative_to(vault_dir.resolve())
    except ValueError:
        return json.dumps({"success": False, "error": "Path outside skill vault directory"})

    if not target.is_file():
        return json.dumps({"success": False, "error": f"File not found: {path}"})

    try:
        content = target.read_text(encoding="utf-8", errors="replace")
        frontmatter, body = parse_frontmatter(target, include_sidecar_config=False)
    except OSError as e:
        return json.dumps({"success": False, "error": str(e)})

    stat = target.stat()
    return json.dumps(
        {
            "success": True,
            "frontmatter": frontmatter,
            "body": body,
            "lines": content.count("\n") + 1,
            "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            "path": target.relative_to(vault_dir).as_posix(),
        },
        default=str,
    )


async def vault_file_write_impl(
    skill: str,
    path: str,
    title: str,
    body: str,
    metadata: dict[str, Any] | None = None,
) -> str:
    """Write a vault file with frontmatter."""
    vault_dir = get_skill_data_dir(skill)
    target = (vault_dir / path).resolve()

    # Security: prevent path traversal
    try:
        target.relative_to(vault_dir.resolve())
    except ValueError:
        return json.dumps({"success": False, "error": "Path outside skill vault directory"})

    created = not target.exists()

    try:
        existing_system: dict[str, Any] = {}
        existing_user: dict[str, Any] = {}
        if target.exists():
            existing_meta, _ = parse_frontmatter(target, include_sidecar_config=False)
            existing_system, existing_user = split_system_user(existing_meta)

        incoming_system, incoming_user = split_system_user(metadata or {})
        user = dict(existing_user)
        user.update(incoming_user)
        user["title"] = title
        system = dict(existing_system)
        system.update(incoming_system)
        fm = merge_system_user(system, user)
        write_frontmatter(target, fm, body)
    except OSError as e:
        return json.dumps({"success": False, "error": str(e)})

    return json.dumps(
        {
            "success": True,
            "path": target.relative_to(vault_dir).as_posix(),
            "created": created,
        }
    )


def _slugify(text: str, max_len: int = 60) -> str:
    """Convert text to a filesystem-safe slug."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:max_len]


async def save_synthesis_impl(
    query: str,
    synthesis: str,
    sources: list[str] | None = None,
    tags: list[str] | None = None,
    knowledge_dir: Path | None = None,
) -> str:
    """Persist a valuable query synthesis as runtime source material.

    This implements the "query compounding" pattern: instead of letting
    valuable search results disappear into chat history, they are filed
    as knowledge notes that become searchable in future queries.

    The note is saved to runtime knowledge state at:
        syntheses/{date}-{query-slug}.md
    """
    now = datetime.now(tz=timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    slug = _slugify(query)
    filename = f"{date_str}-{slug}.md"
    rel_path = f"syntheses/{filename}"

    fm: dict[str, Any] = {
        "title": query,
        "type": "synthesis",
        "query": query,
        "date": date_str,
        "created": now.isoformat(),
    }
    if sources:
        fm["sources"] = sources
    if tags:
        fm["tags"] = tags

    resolved_knowledge_dir = knowledge_dir or get_runtime_dir() / "knowledge"
    target = (resolved_knowledge_dir / rel_path).resolve()

    # Security: prevent path traversal
    try:
        target.relative_to(resolved_knowledge_dir.resolve())
    except ValueError:
        return json.dumps({"success": False, "error": "Path outside runtime knowledge directory"})

    try:
        write_frontmatter(target, fm, synthesis)
    except OSError as e:
        return json.dumps({"success": False, "error": str(e)})

    return json.dumps(
        {
            "success": True,
            "path": rel_path,
            "full_path": str(target),
            "created": True,
            "note": "Synthesis saved. Wiki maintenance now happens through ingest and session update flows.",
        }
    )
