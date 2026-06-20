"""Vault and knowledge/documents listing tools."""

import json

from src.config.paths import get_documents_dir, get_vault_dir
from src.lib.brain_layout import is_machine_path
from src.lib.index.document_sources import default_document_sources, should_index_source_file


async def list_vault_items_impl() -> str:
    """List all items in the user vault directory (flat layout)."""
    vault_dir = get_vault_dir()
    items = []
    if not vault_dir.exists():
        return json.dumps({"items": [], "count": 0})
    # Flat vault: get_vault_dir()/{skill}/...
    for skill_dir in sorted(vault_dir.iterdir()):
        if skill_dir.is_symlink() or not skill_dir.is_dir() or skill_dir.name.startswith("."):
            continue
        # Domains layout: skip the machine subtree (_augur/).
        if is_machine_path(vault_dir, skill_dir):
            continue
        skill = skill_dir.name
        for file_path in sorted(skill_dir.rglob("*")):
            # Symlink-only guard suffices here: the outer loop already excludes
            # machine dirs, so files inside skill_dir can never be machine paths.
            if file_path.is_symlink():
                continue
            if not file_path.is_file() or file_path.name.startswith("."):
                continue
            rel = file_path.relative_to(skill_dir)
            items.append(
                {
                    "id": f"{skill}/{rel}",
                    "title": file_path.stem,
                    "description": f"{skill} / {rel.parent}" if str(rel.parent) != "." else skill,
                    "skill": skill,
                    "path": str(file_path),
                    "file_type": file_path.suffix.lstrip(".") or "unknown",
                }
            )
    return json.dumps({"items": items, "count": len(items)})


async def list_knowledge_hub_files_impl(hub: str = "all") -> str:
    """List document files from get_documents_dir()/ and knowledge files from get_vault_dir()/."""
    documents_dir = get_documents_dir()
    items = []

    if documents_dir is None:
        return json.dumps({"files": [], "count": 0})

    for source in default_document_sources(documents_dir=documents_dir):
        if not source.resolved_path.exists():
            continue
        for file_path in sorted(source.resolved_path.rglob("*")):
            if not should_index_source_file(file_path, source):
                continue

            rel = file_path.relative_to(source.resolved_path)
            if source.id == "documents" and len(rel.parts) > 1:
                file_skill = rel.parts[0]
            else:
                file_skill = source.id

            if hub != "all" and file_skill != hub:
                continue

            items.append(
                {
                    "path": str(file_path),
                    "name": file_path.name,
                    "skill": file_skill,
                    "source_root": source.id,
                    "source_root_name": source.name,
                    "source_relative_path": rel.as_posix(),
                }
            )

    return json.dumps({"files": items, "count": len(items)})
