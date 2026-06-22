"""
Vault/actions/reindex skill discovery tool implementations.

Covers listing a skill's page-surface actions, listing a skill's vault
notes, and reindexing a single browse category.
"""

import json
from collections.abc import Callable
from pathlib import Path

from src.mcp.augur_shared.config import get_skill_data_dir

from .skills_common import _resolve_skill_note_brain_id


def list_skill_actions_impl(
    skill_name: str = "",
    resolve_skill_entry: Callable | None = None,
    *,
    skill_id: str = "",
) -> dict:
    """List page-surface actions declared by a skill.

    Reads the skill's ``augur/actions.yaml`` (the unified action source,
    ADR-807), filters to actions whose ``surfaces`` includes ``"page"``,
    and emits full passthrough of the unified ``Action`` fields that the
    page action-bar / useActionRunner consume.

    Args:
        skill_name: Name of the skill (positional, kept for the MCP wrapper).
        resolve_skill_entry: Function to resolve a skill to its entry. When
            omitted, falls back to the default filesystem resolver.
        skill_id: Alias for ``skill_name`` (keyword form used by callers).

    Returns:
        dict: ``{"actions": [...]}`` — JSON-serializable mapping.
    """
    from src.lib.actions.action_schema import load_actions_yaml

    name = skill_name or skill_id
    if resolve_skill_entry is None:
        from src.plugins.skill_discovery import resolve_skill as resolve_skill_entry

    skill_entry = resolve_skill_entry(name)
    if not skill_entry:
        return {"actions": []}

    actions_yaml = skill_entry.path / "augur" / "actions.yaml"
    if not actions_yaml.exists():
        return {"actions": []}

    actions = []
    for action in load_actions_yaml(actions_yaml):
        if "page" not in (action.surfaces or []):
            continue
        actions.append(
            {
                "id": action.id,
                "label": action.label,
                "icon": action.icon,
                "dispatch": action.dispatch,
                "description": action.label,
                "mcp_tools": [action.mcp_tool] if action.mcp_tool else [],
                "args": action.args or {},
                "page": getattr(action, "page", None),
                "modal": action.modal,
            }
        )

    return {"actions": actions}


async def list_skill_vault_notes_impl(
    skill_name: str,
    resolve_skill_entry: Callable,
) -> str:
    """List vault notes for a skill.

    Reads markdown files from the skill's vault data directory and returns
    a backwards-compatible flat ``notes`` array plus a new ``groups`` array
    organised by subdirectory, with type and line-count metadata.

    Args:
        skill_name: Name of the skill
        resolve_skill_entry: Function to resolve skill by name

    Returns:
        str: JSON with notes[], groups[], and stats{}
    """
    from collections import defaultdict
    from datetime import datetime, timezone

    empty = {"notes": [], "groups": [], "stats": {"total_files": 0, "total_dirs": 0}}

    skill_entry = resolve_skill_entry(skill_name)
    if not skill_entry:
        return json.dumps(empty)

    vault_dir = get_skill_data_dir(skill_entry.name)
    if not vault_dir.is_dir():
        return json.dumps(empty)

    # Collect .md files up to 3 levels deep
    all_md: list[Path] = []
    for pattern in ("*.md", "*/*.md", "*/*/*.md", "*/*/*/*.md"):
        all_md.extend(vault_dir.glob(pattern))

    # Deduplicate and sort by modification time (newest first)
    seen: set[Path] = set()
    md_files: list[Path] = []
    for p in sorted(all_md, key=lambda p: p.stat().st_mtime, reverse=True):
        if p not in seen:
            seen.add(p)
            md_files.append(p)

    md_files = md_files[:50]

    def _parse_file(md_file: Path) -> dict:
        stat = md_file.stat()
        content = md_file.read_text(encoding="utf-8", errors="replace")
        lines = content.count("\n") + (1 if content and not content.endswith("\n") else 0)

        # Extract frontmatter type field
        file_type: str | None = None
        body = content
        if content.startswith("---"):
            end = content.find("\n---", 4)
            if end != -1:
                fm_block = content[4:end]
                for line in fm_block.splitlines():
                    if line.startswith("type:"):
                        file_type = line[5:].strip().strip('"').strip("'")
                        break
                body = content[end + 4 :].lstrip("\n")

        preview = body[:500].strip() if body else ""
        rel_name = md_file.relative_to(vault_dir).as_posix()
        modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()

        entry = {
            "name": rel_name,
            "type": file_type,
            "modified": modified,
            "lines": lines,
            "preview": preview,
        }
        brain_id = _resolve_skill_note_brain_id(md_file)
        if brain_id:
            entry["brain_id"] = brain_id
        return entry

    parsed = [_parse_file(f) for f in md_files]

    # Flat backwards-compatible notes array (subset of fields)
    notes = [
        {
            "name": p["name"],
            "modified": p["modified"],
            "preview": p["preview"],
            **({"brain_id": p["brain_id"]} if p.get("brain_id") else {}),
        }
        for p in parsed
    ]

    # Group by immediate parent directory relative to vault root
    grouped: dict[str, list[dict]] = defaultdict(list)
    for entry in parsed:
        rel = Path(entry["name"])
        directory = str(rel.parent) if str(rel.parent) != "." else "."
        # Use only the first path component as the group key
        parts = rel.parts
        directory = parts[0] if len(parts) > 1 else "."
        grouped[directory].append(entry)

    groups = [
        {
            "directory": directory,
            "count": len(files),
            "files": files,
        }
        for directory, files in sorted(grouped.items())
    ]

    stats = {
        "total_files": len(parsed),
        "total_dirs": len(groups),
    }

    return json.dumps({"notes": notes, "groups": groups, "stats": stats})


async def reindex_browse_category_impl(category: str) -> str:
    """Reindex a single browse category (pages, skills, actions, etc.).

    Shells out to the unified_indexer CLI with --category to avoid
    internal import issues when loading scanner modules in isolation.

    Args:
        category: Category name matching a scanner (e.g., "pages", "skills")

    Returns:
        str: JSON with success, category, count
    """
    import asyncio
    import subprocess
    from datetime import datetime, timezone

    from src.mcp.augur_shared.config import get_project_root

    VALID_CATS = {
        "skills",
        "adrs",
        "actions",
        "prompts",
        "agents",
        "integrations",
        "commands",
        "scripts",
        "api-routes",
        "tests",
        "pages",
        "blocks",
        "mcp-tools",
        "mcp-servers",
        "vault",
        "documents",
        "wiki",
        "logs",
        "profile",
    }

    if category not in VALID_CATS:
        return json.dumps({"success": False, "error": f"Unknown category: {category}"})

    root = get_project_root()
    if category == "profile":
        return json.dumps({"success": True, "category": category, "count": 1, "synthetic": True})

    script = root / "src" / "lib" / "index" / "unified_indexer.py"

    if not script.exists():
        return json.dumps({"success": False, "error": "Indexer script not found"})

    proc = await asyncio.to_thread(
        subprocess.run,
        ["python3", str(script), "--category", category, "--root", str(root)],
        capture_output=True,
        text=True,
        cwd=str(root),
        timeout=60,
        env={**__import__("os").environ, "PYTHONPATH": str(root)},
    )

    if proc.returncode != 0:
        return json.dumps(
            {
                "success": False,
                "error": proc.stderr.strip()[:300] or f"Indexer exited with code {proc.returncode}",
            }
        )

    # Parse count from output like "Indexed 42 pages entries"
    output = proc.stdout.strip()
    count = 0
    if "Indexed" in output:
        try:
            count = int(output.split("Indexed")[1].split()[0])
        except (ValueError, IndexError):
            pass

    return json.dumps(
        {
            "success": True,
            "category": category,
            "count": count,
            "indexedAt": datetime.now(timezone.utc).isoformat(),
        }
    )
