"""Browse index tool and skill enrichment cache.

Split into cohesive sibling modules (index_common / index_paths / index_sweep /
index_email / index_enrichment / index_synthetic / index_wiki / index_metadata /
index_resolve / index_search / index_merge). ``browse_index_impl`` and the public
surface re-exported below remain importable from this module.
"""

import json

from src.config.paths import (
    get_cache_dir,
    get_documents_dir,
    get_project_root,
    get_runtime_dir,
    get_vault_dir,
)
from src.lib.ai_artifact_inventory import inventory_browse_entries_for_category
from src.lib.staged_skill_catalog import find_skill_file

from . import background_routines, scheduled_executions
from .index_common import (
    _AI_ARTIFACT_PROBLEM_IDS,
    _ARCHIVE_SEARCH_METADATA_KEYS,
    _BROWSE_LIMIT,
    _FILESYSTEM_BACKED_CATEGORIES,
    _VAULT_JOURNEY_ROOTS,
    _as_string_list,
    _metadata_text,
)
from .index_enrichment import (
    _SKILL_ENRICHMENT_TTL,
    _command_enrichment_cache,
    _command_enrichment_populating,
    _command_enrichment_ts,
    _get_command_enrichment,
    _get_skill_enrichment,
    _load_install_registry,
    _populate_command_enrichment,
    _populate_skill_enrichment,
    _skill_enrichment_cache,
    _skill_enrichment_populating,
    _skill_enrichment_ts,
)
from .index_merge import (
    _external_integration_entries,
    _filter_missing_inventory_entries,
    _merge_external_integration_entries,
    _merge_inventory_entries,
    _merge_inventory_metadata,
    _source_path_dedupe_key,
)
from .index_metadata import (
    _CAPABILITY_AUTHORITATIVE_KEYS,
    _apply_capability_metadata,
    _capability_collision_key,
    _capability_metadata_for_browse_entry,
    _copy_document_metadata_aliases,
    _document_source_config_error_entry,
    _document_source_entries_for_browse,
    _merge_capability_metadata,
)
from .index_resolve import (
    _entry_has_existing_source_path,
    _filter_missing_source_path_entries,
    _resolve_entry_brain_id,
    _resolve_local_source_path,
    _resolve_project_brain_id_for_path,
    _resolve_safe_project_relative_source_path,
    _source_path_for_output,
)
from .index_search import (
    _entry_matches_scope,
    _entry_matches_search,
    _entry_matches_vault_journey,
    _entry_search_score,
    _entry_search_sort_key,
    _entry_search_values,
    _entry_timestamp,
    _latest_indexed_at,
)
from .index_synthetic import _synthetic_entries_for_category
from .index_wiki import _wiki_maintenance_metadata

__all__ = [
    "browse_index_impl",
    # Enrichment cache surface (monkeypatched/imported by tests).
    "_get_skill_enrichment",
    "_populate_skill_enrichment",
    "_skill_enrichment_cache",
    "_SKILL_ENRICHMENT_TTL",
    "_skill_enrichment_ts",
    # Capability metadata surface (imported/monkeypatched by tests).
    "_apply_capability_metadata",
    "_merge_capability_metadata",
    "_capability_metadata_for_browse_entry",
    # Path helpers retargetable on this module's namespace.
    "find_skill_file",
    "get_project_root",
    "get_documents_dir",
    "get_runtime_dir",
    "get_vault_dir",
    "get_cache_dir",
    "inventory_browse_entries_for_category",
    # WS5-split re-exports kept as a stable surface for tests/monkeypatching.
    "_AI_ARTIFACT_PROBLEM_IDS",
    "_ARCHIVE_SEARCH_METADATA_KEYS",
    "_CAPABILITY_AUTHORITATIVE_KEYS",
    "_capability_collision_key",
    "_command_enrichment_cache",
    "_command_enrichment_populating",
    "_command_enrichment_ts",
    "_get_command_enrichment",
    "_populate_command_enrichment",
    "_document_source_config_error_entry",
    "_entry_has_existing_source_path",
    "_entry_search_score",
    "_entry_search_values",
    "_entry_timestamp",
    "_external_integration_entries",
    "_filter_missing_inventory_entries",
    "_load_install_registry",
    "_merge_external_integration_entries",
    "_merge_inventory_entries",
    "_merge_inventory_metadata",
    "_resolve_local_source_path",
    "_resolve_project_brain_id_for_path",
    "_resolve_safe_project_relative_source_path",
    "_skill_enrichment_populating",
    "_source_path_dedupe_key",
]


def browse_index_impl(
    category: str,
    hub: str | None = None,
    limit: int = 0,
    search: str | None = None,
    journey_category: str | None = None,
    scope: str | None = None,
) -> str:
    """List items from the RAG index for a given category, optionally filtered by hub/search."""
    if category in {"background-routines", "scheduled-executions"}:
        items = background_routines.list_background_routine_items(search=search)
        scheduled_items = scheduled_executions.list_scheduled_execution_items(search=search)
        for entry in scheduled_items:
            entry["type"] = "background-routines"
        items = [*items, *scheduled_items]
        if hub:
            items = [item for item in items if item.get("hub") == hub]
        effective_limit = limit if limit > 0 else _BROWSE_LIMIT
        items = items[:effective_limit]
        result: dict = {"items": items, "count": len(items)}
        return json.dumps(result)

    from src.config.paths import get_rag_category_dir
    from src.lib.index.index_reader import (
        count_category_entries,
        list_category_entries,
    )

    external_entries = _external_integration_entries() if category == "integrations" else []
    synthetic_entries = _synthetic_entries_for_category(category, journey_category)
    if hub and synthetic_entries:
        synthetic_entries = [entry for entry in synthetic_entries if entry.get("hub") == hub]
    inventory_entries = inventory_browse_entries_for_category(category)
    if hub and inventory_entries:
        inventory_entries = [entry for entry in inventory_entries if entry.get("hub") == hub]
    inventory_candidate_count = len(inventory_entries)
    inventory_entries, missing_inventory_count = _filter_missing_inventory_entries(inventory_entries)
    stale_inventory_filtered = missing_inventory_count > 0
    cat_dir = get_rag_category_dir(category)
    # Set when a filesystem-backed category's on-disk index existed with entries
    # but every one was dropped because its source_path is missing (a stale
    # index, e.g. after files moved). Surfaced as status="stale" so the UI can
    # offer reindex instead of rendering a silent, unrecoverable empty grid.
    stale_filtered = False
    missing_category_status: str | None = None
    if not cat_dir.exists():
        if not external_entries and not synthetic_entries and not inventory_entries:
            missing_category_status = "stale" if inventory_candidate_count else "not_indexed"
            entries = []
        else:
            entries, _inventory_added_count = _merge_inventory_entries(
                [*external_entries, *synthetic_entries],
                inventory_entries,
            )
        total_count = len(entries)
        last_indexed: str | None = None
    else:
        effective_limit = limit if limit > 0 else _BROWSE_LIMIT

        journey_root = _VAULT_JOURNEY_ROOTS.get(journey_category or "") if category == "vault" else None
        # The physical journey-subdir shortcut predates the domains layout:
        # private-vault entries now live under private/<domain>/ with their
        # journey carried as entry metadata, so a subdir scan silently drops
        # them. Always metadata-filter vault journeys instead.
        scan_dir = cat_dir
        using_journey_subdir = False

        total_count = count_category_entries(scan_dir, hub=hub)

        # When searching, filter before applying the caller's display limit.
        search_lower = search.strip().lower() if search else ""
        needs_source_filter = category in _FILESYSTEM_BACKED_CATEGORIES
        if (
            search_lower
            or scope
            or needs_source_filter
            or inventory_entries
            or (journey_root and not using_journey_subdir)
        ):
            # Scan the full category when it is reasonably bounded; cap oversized
            # categories to avoid MCP timeouts.
            fetch_limit = 0 if total_count <= 50000 else 50000
        else:
            fetch_limit = effective_limit
        entries_represent_full_set = fetch_limit == 0 or fetch_limit >= total_count

        entries = list_category_entries(scan_dir, hub=hub, limit=fetch_limit)

        if external_entries:
            entries = _merge_external_integration_entries(entries, external_entries)
            total_count = len(entries)

        if synthetic_entries:
            if category == "vault" and journey_category == "inbox":
                entries = [*synthetic_entries, *entries]
            else:
                entries = [*entries, *synthetic_entries]
            if (
                not search_lower
                and not scope
                and not needs_source_filter
                and not (journey_root and not using_journey_subdir)
            ):
                total_count += len(synthetic_entries)
            else:
                total_count = len(entries)

        if inventory_entries:
            entries, inventory_added_count = _merge_inventory_entries(entries, inventory_entries)
            if search_lower or scope or needs_source_filter or (journey_root and not using_journey_subdir):
                total_count = len(entries)
            elif entries_represent_full_set:
                total_count = len(entries)
            else:
                total_count += inventory_added_count

        if journey_root and not using_journey_subdir:
            entries = [e for e in entries if _entry_matches_vault_journey(e, cat_dir, journey_root)]
            total_count = len(entries)

        if needs_source_filter:
            pre_filter_count = len(entries)
            entries = _filter_missing_source_path_entries(category, entries)
            if pre_filter_count > 0 and not entries:
                stale_filtered = True
            total_count = len(entries)

        # Track most recent indexed_at across all entries (ADR-478)
        last_indexed = None

    if category == "documents":
        source_entries = _document_source_entries_for_browse(entries)
        if hub and source_entries:
            source_entries = [
                entry
                for entry in source_entries
                if entry.get("hub") == hub or entry.get("id") == "document-source-config:error"
            ]
        if source_entries:
            entries = [*entries, *source_entries]
            total_count = len(entries)

    effective_limit = limit if limit > 0 else _BROWSE_LIMIT
    search_lower = search.strip().lower() if search else ""
    if hub and not cat_dir.exists():
        entries = [entry for entry in entries if entry.get("hub") == hub]
        total_count = len(entries)

    if scope:
        entries = [entry for entry in entries if _entry_matches_scope(entry, scope)]
        total_count = len(entries)

    if category == "mcp-servers":
        from src.lib.mcp_runtime_inventory import enrich_mcp_server_entries_with_runtime

        entries = enrich_mcp_server_entries_with_runtime(entries)
        total_count = len(entries)

    # Server-side text search: filter and rank before applying the display limit.
    if search_lower:
        entries = [e for e in entries if _entry_matches_search(e, search_lower)]
        entries.sort(key=lambda entry: _entry_search_sort_key(entry, search_lower))
        total_count = len(entries)  # total matching entries

    last_indexed = _latest_indexed_at(entries)
    entries = entries[:effective_limit]

    # Enrichment data is cached so Browse can attach quality signals without
    # rescanning command/skill sources on every request.
    skill_enrichment: dict[str, dict[str, str]] = {}
    if category == "skills":
        skill_enrichment = _get_skill_enrichment()
    elif category == "commands":
        skill_enrichment = _get_command_enrichment()

    wiki_maintenance = _wiki_maintenance_metadata(last_indexed) if category == "wiki" else {}
    items = []
    for entry in entries:
        name = entry.get("name", "")
        item_id = entry.get("id", "") or name
        item_title = entry.get("title", "") or name
        entry_metadata = entry.get("metadata")
        metadata: dict[str, str] = {}

        def add_metadata_values(
            values: object,
            *,
            skip: set[str] | None = None,
            target: dict[str, str] = metadata,
        ) -> None:
            if not isinstance(values, dict):
                return
            skipped = skip or set()
            for key, raw_value in values.items():
                if not key or key in skipped:
                    continue
                value = _metadata_text(raw_value)
                if value:
                    target[key] = value

        add_metadata_values(entry_metadata)
        add_metadata_values(
            entry,
            skip={
                "id",
                "title",
                "type",
                "hub",
                "name",
                "description",
                "source_path",
                "tags",
                "related",
                "manual_related",
                "combined_related",
                "relationships",
                "relationship_targets",
                "metadata",
                "_index_path",
                "_body",
                "checksum",
                "indexed_at",
            },
        )
        enrich_key = name if name in skill_enrichment else item_id
        if skill_enrichment and enrich_key in skill_enrichment:
            enrichment = dict(skill_enrichment[enrich_key])
            if metadata.get("ownership") == "user" and enrichment.get("ownership") == "external":
                enrichment.pop("ownership", None)
            metadata.update(enrichment)

        client_sources = _as_string_list(entry.get("client_sources") or metadata.get("client_sources"))
        skill_clients = _as_string_list(entry.get("skill_clients") or metadata.get("skill_clients"))
        if client_sources:
            metadata["clientSources"] = ",".join(client_sources)
        if skill_clients:
            metadata["skillClients"] = ",".join(skill_clients)
        if category == "integrations" and isinstance(entry.get("cli_tools"), list):
            metadata.pop("cli_tools", None)

        _apply_capability_metadata(category, entry, metadata)
        if category == "documents":
            _copy_document_metadata_aliases(metadata)
        if wiki_maintenance:
            metadata.update(wiki_maintenance)

        brain_id = str(entry.get("brain_id") or metadata.get("brain_id") or "")
        if not brain_id:
            resolved_brain_id = _resolve_entry_brain_id(entry)
            brain_id = resolved_brain_id or ""
        if brain_id:
            metadata["brain_id"] = brain_id

        item = {
            "id": item_id,
            "title": item_title,
            "description": entry.get("description", ""),
            "hub": entry.get("hub", "system"),
            "type": entry.get("type", category),
            "source_path": _source_path_for_output(category, entry),
            "tags": entry.get("tags", []),
            "related": entry.get("relationship_targets", []),
            "metadata": metadata,
        }
        for top_level_key in ("source", "ownership", "skill_client", "skill_origin"):
            value = entry.get(top_level_key) or metadata.get(top_level_key)
            if value:
                item[top_level_key] = str(value)
        # Prompt cards (ADR-748): the prompt text is stored in the index
        # entry's body section, surfaced by read_index_entry as `_body`.
        # The dashboard transform reads `entry.body` at top level to
        # dispatch via the Trigger button, so promote `_body` there.
        if category == "prompts":
            prompt_body = entry.get("_body")
            if prompt_body:
                item["body"] = str(prompt_body)
        if client_sources:
            item["client_sources"] = client_sources
        if skill_clients:
            item["skill_clients"] = skill_clients
        if category == "integrations" and isinstance(entry.get("cli_tools"), list):
            item["cli_tools"] = entry["cli_tools"]
        items.append(item)

    result: dict = {"items": items, "count": len(items)}
    if missing_category_status and not items:
        result["status"] = missing_category_status
    if (stale_filtered or stale_inventory_filtered) and not items:
        result["status"] = "stale"
    if total_count > len(items):
        result["total_count"] = total_count
        result["truncated"] = True
    if last_indexed:
        result["last_indexed"] = last_indexed
    return json.dumps(result)
