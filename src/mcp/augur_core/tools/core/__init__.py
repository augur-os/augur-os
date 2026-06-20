"""
Core MCP tools - skill discovery, context injection, and system health.

This module contains the foundational tools for Augur operation.

## Tools in this category

### System Health (extracted)
- `health`: Simple health check for monitoring
- `metrics`: Get usage statistics and system health
- `cache-control`: Manage the internal skill cache

### Skill Discovery (extracted)
- `list-skills`: List all available skills
- `get-skill`: Get skill overview
- `find-skill`: Find best skill for a query
- `load-module`: Load specific module
- `load-reference`: Load reference documentation
- `get-config`: Get skill configuration

### Context Injection (extracted)
- `get-context`: Get enriched context (KEY MOAT)
- `get-design-standards`: Get UI design standards
- `cross-skill`: Get cross-skill integration guidance

### Pending extraction
- Tool Management: list-mcp-tools, get-focused-tools, switch-mcp-context, etc.

## Usage

```python
from src.mcp.augur_core.tools.core import register_core_tools

# In server.py
mcp = FastMCP(...)
register_core_tools(mcp)
```
"""

# TODO_CLEANUP: This file is 833 lines — consider splitting into smaller modules

import json
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.mcp.augur_shared.annotations import tool_annotations

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

from .ask_retention import retain_ask_outcome_impl
from .brain_discovery import (
    brain_active_context_impl,
    brain_discovery_impl,
    brain_folder_scan_impl,
    brain_init_impl,
    brain_set_active_context_impl,
)
from .context import cross_skill_impl, get_context_impl, get_design_standards_impl
from .health import cache_control_impl, get_metrics_impl, health_check_impl
from .hub_vault_notes import list_hub_vault_notes_impl
from .hygiene import (
    hygiene_apply_impl,
    hygiene_apply_selection_impl,
    hygiene_create_selection_impl,
    hygiene_scan_impl,
    hygiene_scan_selection_impl,
)
from .memory_review import (
    memory_review_approve_impl,
    memory_review_queue_impl,
    memory_review_reject_impl,
    memory_review_submit_impl,
)
from .models import (
    CacheControlInput,
    FindSkillInput,
    GetContextInput,
    GetPreferencesInput,
    GetSkillInput,
    ListSkillsInput,
    LoadModuleInput,
    LoadReferenceInput,
    ResponseFormat,
    UpdatePreferenceInput,
)
from .preferences import get_preferences_impl, update_preference_impl
from .skill_lifecycle import adopt_skill, skill_status, skill_upstream_status
from .skills import (
    find_skill_impl,
    get_config_impl,
    get_skill_doc_impl,
    get_skill_health_impl,
    get_skill_impl,
    list_skill_actions_impl,
    list_skill_vault_notes_impl,
    list_skills_impl,
    load_module_impl,
    load_reference_impl,
    reindex_browse_category_impl,
    update_skill_doc_impl,
)
from .vault_ops import save_synthesis_impl


def register_core_tools(
    mcp: "FastMCP",
    skill_cache=None,
    metrics=None,
    registry_list_skills: Callable[..., Any] | None = None,
    resolve_skill_entry: Callable[..., Any] | None = None,
    available_skill_ids: Callable[..., Any] | None = None,
    mcp_tool_interceptor=None,
    logger=None,
) -> None:
    """
    Register core tools with the MCP server.

    Args:
        mcp: The FastMCP server instance
        skill_cache: SkillCache instance for cache operations
        metrics: MetricsTracker instance
        registry_list_skills: Function to list skills
        resolve_skill_entry: Function to resolve skill by name
        available_skill_ids: Function to get list of skill IDs
        mcp_tool_interceptor: Optional decorator for correlation ID tracking
        logger: Logger instance for error logging
    """
    if registry_list_skills is None:
        raise ValueError("registry_list_skills is required")
    if resolve_skill_entry is None:
        raise ValueError("resolve_skill_entry is required")
    if available_skill_ids is None:
        raise ValueError("available_skill_ids is required")

    # ==========================================================================
    # System Health Tools
    # ==========================================================================

    @mcp.tool(
        name="metrics",
        annotations=tool_annotations(
            {
                "title": "Get Server Metrics",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def get_metrics() -> str:
        """Get usage statistics and system health."""
        return await get_metrics_impl(metrics)

    @mcp.tool(
        name="health",
        annotations=tool_annotations(
            {
                "title": "Check Health",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def health_check() -> str:
        """Simple health check for monitoring."""
        return await health_check_impl(skill_cache, registry_list_skills)

    @mcp.tool(
        name="cache-control",
        annotations=tool_annotations(
            {
                "title": "Cache Management",
                "readOnlyHint": False,
                "destructiveHint": True,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    async def cache_control(params: CacheControlInput) -> str:
        """Manage the internal skill cache."""
        return await cache_control_impl(params, skill_cache, metrics)

    # ==========================================================================
    # Skill Discovery Tools
    # ==========================================================================

    @mcp.tool(
        name="list-skills",
        annotations=tool_annotations(
            {
                "title": "List Available Skills",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def list_skills(params: ListSkillsInput) -> str:
        """List all available skills with ownership metadata."""
        return await list_skills_impl(params, skill_cache, metrics, registry_list_skills)

    if mcp_tool_interceptor:
        list_skills = mcp_tool_interceptor(list_skills)

    @mcp.tool(
        name="get-skill",
        annotations=tool_annotations(
            {
                "title": "Get Skill Overview",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def get_skill(params: GetSkillInput) -> str:
        """Load a skill's SKILL.md overview and command reference."""
        return await get_skill_impl(params, resolve_skill_entry, available_skill_ids, metrics)

    if mcp_tool_interceptor:
        get_skill = mcp_tool_interceptor(get_skill)

    @mcp.tool(
        name="load-module",
        annotations=tool_annotations(
            {
                "title": "Load Skill Module",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def load_module(params: LoadModuleInput) -> str:
        """Load a specific module's detailed documentation."""
        return await load_module_impl(params, resolve_skill_entry, metrics)

    if mcp_tool_interceptor:
        load_module = mcp_tool_interceptor(load_module)

    @mcp.tool(
        name="load-reference",
        annotations=tool_annotations(
            {
                "title": "Load Reference Documentation",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def load_reference(params: LoadReferenceInput) -> str:
        """Load reference documentation for a skill."""
        return await load_reference_impl(params, resolve_skill_entry)

    if mcp_tool_interceptor:
        load_reference = mcp_tool_interceptor(load_reference)

    @mcp.tool(
        name="get-config",
        annotations=tool_annotations(
            {
                "title": "Get Skill Configuration",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def get_config(skill_name: str) -> str:
        """Get configuration file for a skill if available."""
        return await get_config_impl(skill_name, resolve_skill_entry)

    @mcp.tool(
        name="find-skill",
        annotations=tool_annotations(
            {
                "title": "Smart Skill Matching",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def find_skill(params: FindSkillInput) -> str:
        """Find the best skill for a user query."""
        return await find_skill_impl(params, skill_cache, metrics, registry_list_skills)

    # ==========================================================================
    # Browse Auto-Page Tools (ADR-491)
    # ==========================================================================

    @mcp.tool(
        name="get-skill-health",
        annotations=tool_annotations(
            {
                "title": "Get Skill Health",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def get_skill_health(skill_name: str = "", skillId: str = "", skill_id: str = "") -> str:
        """Get health status for a skill (used by browse auto-page HealthBlock)."""
        name = skill_name or skillId or skill_id
        return await get_skill_health_impl(name, resolve_skill_entry)

    if mcp_tool_interceptor:
        get_skill_health = mcp_tool_interceptor(get_skill_health)

    @mcp.tool(
        name="list-skill-actions",
        annotations=tool_annotations(
            {
                "title": "List Skill Actions",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def list_skill_actions(skill_name: str = "", skillId: str = "", skill_id: str = "") -> str:
        """List actions declared by a skill (used by browse auto-page ActionBarBlock)."""
        name = skill_name or skillId or skill_id
        return json.dumps(list_skill_actions_impl(name, resolve_skill_entry))

    if mcp_tool_interceptor:
        list_skill_actions = mcp_tool_interceptor(list_skill_actions)

    @mcp.tool(
        name="get-skill-doc",
        annotations=tool_annotations(
            {
                "title": "Get Skill Documentation",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def get_skill_doc(skill_name: str = "", skillId: str = "", skill_id: str = "") -> str:
        """Get SKILL.md documentation content (used by browse auto-page MarkdownBlock)."""
        name = skill_name or skillId or skill_id
        return await get_skill_doc_impl(name, resolve_skill_entry)

    if mcp_tool_interceptor:
        get_skill_doc = mcp_tool_interceptor(get_skill_doc)

    @mcp.tool(
        name="update-skill-doc",
        annotations=tool_annotations(
            {
                "title": "Update Skill Documentation",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    async def update_skill_doc(
        content: str,
        skill_name: str = "",
        skillId: str = "",
        skill_id: str = "",
        create_backup: bool = True,
    ) -> str:
        """Update the markdown body of a skill's SKILL.md."""
        name = skill_name or skillId or skill_id
        return await update_skill_doc_impl(
            name,
            content,
            resolve_skill_entry,
            create_backup=create_backup,
        )

    if mcp_tool_interceptor:
        update_skill_doc = mcp_tool_interceptor(update_skill_doc)

    @mcp.tool(
        name="list-skill-vault-notes",
        annotations=tool_annotations(
            {
                "title": "List Skill Vault Notes",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def list_skill_vault_notes(skill_name: str = "", skillId: str = "", skill_id: str = "") -> str:
        """List vault notes for a skill (used by browse auto-page VaultNotesBlock)."""
        name = skill_name or skillId or skill_id
        return await list_skill_vault_notes_impl(name, resolve_skill_entry)

    if mcp_tool_interceptor:
        list_skill_vault_notes = mcp_tool_interceptor(list_skill_vault_notes)

    @mcp.tool(
        name="list-hub-vault-notes",
        annotations=tool_annotations(
            {
                "title": "List Hub Vault Notes",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def list_hub_vault_notes(
        hub_id: str = "",
        hubId: str = "",
        limit: int = 50,
        per_skill_limit: int = 8,
    ) -> str:
        """List vault notes across all skills in a hub."""
        from src.mcp.augur_shared.config import get_vault_dir
        from src.plugins.skill_discovery import discover_all_skills

        resolved_hub = hub_id or hubId
        if not resolved_hub:
            return json.dumps({"success": True, "notes": [], "count": 0})

        try:
            all_skills = discover_all_skills(tiers=(0,))
            skill_names = [s.name for s in all_skills if s.hub == resolved_hub]
        except Exception:
            skill_names = []

        if not skill_names:
            return json.dumps({"success": True, "hub_id": resolved_hub, "notes": [], "count": 0})

        vault_dir = get_vault_dir()

        return await list_hub_vault_notes_impl(
            hub_id=resolved_hub,
            skill_names=skill_names,
            vault_dir=vault_dir,
            limit=limit,
            per_skill_limit=per_skill_limit,
        )

    if mcp_tool_interceptor:
        list_hub_vault_notes = mcp_tool_interceptor(list_hub_vault_notes)

    # ==========================================================================
    # Brain Discovery & Federation (ADR-772)
    # ==========================================================================

    @mcp.tool(
        name="brain-discovery",
        annotations=tool_annotations(
            {
                "title": "Discover Registered & Detected Brains",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def brain_discovery(include_git_status: bool = True) -> str:
        """List registered/detected brains, per-brain index & git state,
        current-project status, and per-client projection status."""
        return await brain_discovery_impl(include_git_status=include_git_status)

    if mcp_tool_interceptor:
        brain_discovery = mcp_tool_interceptor(brain_discovery)

    @mcp.tool(
        name="brain-init",
        annotations=tool_annotations(
            {
                "title": "Initialize Project Brain (augur init)",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def brain_init(project_root: str = "", run_sync: bool = False) -> str:
        """Create or re-attach a repo-local project brain and register it."""
        return await brain_init_impl(
            project_root=project_root or None,
            run_sync=run_sync,
        )

    if mcp_tool_interceptor:
        brain_init = mcp_tool_interceptor(brain_init)

    @mcp.tool(
        name="brain-active-context",
        annotations=tool_annotations(
            {
                "title": "Get Active Browse Folder Context",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def brain_active_context() -> str:
        """Return active folder context and selectable folder options."""
        return await brain_active_context_impl()

    if mcp_tool_interceptor:
        brain_active_context = mcp_tool_interceptor(brain_active_context)

    @mcp.tool(
        name="brain-set-active-context",
        annotations=tool_annotations(
            {
                "title": "Set Active Browse Folder Context",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def brain_set_active_context(scope: str = "all", brain_id: str = "") -> str:
        """Persist active folder context for Browse and item actions."""
        return await brain_set_active_context_impl(scope=scope, brain_id=brain_id)

    if mcp_tool_interceptor:
        brain_set_active_context = mcp_tool_interceptor(brain_set_active_context)

    @mcp.tool(
        name="brain-folder-scan",
        annotations=tool_annotations(
            {
                "title": "Scan Folder AI Artifacts Without Init",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def brain_folder_scan(project_root: str) -> str:
        """Preview AI artifact inventory for a folder without writing project-brain metadata."""
        return await brain_folder_scan_impl(project_root=project_root)

    if mcp_tool_interceptor:
        brain_folder_scan = mcp_tool_interceptor(brain_folder_scan)

    # ==========================================================================
    # Memory Review — reviewed promotion into canonical brain memory (ADR-772)
    # ==========================================================================

    @mcp.tool(
        name="memory-review-queue",
        annotations=tool_annotations(
            {
                "title": "Memory Review Queue",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def memory_review_queue(brain: str = "", include_resolved: bool = False) -> str:
        """List candidate facts (un-promoted client memory + agent submissions)
        awaiting review for the active or named brain."""
        return await memory_review_queue_impl(
            brain=brain or None,
            include_resolved=include_resolved,
        )

    if mcp_tool_interceptor:
        memory_review_queue = mcp_tool_interceptor(memory_review_queue)

    @mcp.tool(
        name="memory-review-approve",
        annotations=tool_annotations(
            {
                "title": "Approve Memory Candidate",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def memory_review_approve(candidate_id: str = "", brain: str = "") -> str:
        """Approve one candidate and write it as a canonical brain memory entry."""
        return await memory_review_approve_impl(candidate_id=candidate_id, brain=brain or None)

    if mcp_tool_interceptor:
        memory_review_approve = mcp_tool_interceptor(memory_review_approve)

    @mcp.tool(
        name="memory-review-reject",
        annotations=tool_annotations(
            {
                "title": "Reject Memory Candidate",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def memory_review_reject(candidate_id: str = "", reason: str = "", brain: str = "") -> str:
        """Reject one candidate so it never resurfaces in the review queue."""
        return await memory_review_reject_impl(
            candidate_id=candidate_id,
            reason=reason,
            brain=brain or None,
        )

    if mcp_tool_interceptor:
        memory_review_reject = mcp_tool_interceptor(memory_review_reject)

    @mcp.tool(
        name="memory-review-submit",
        annotations=tool_annotations(
            {
                "title": "Submit Memory Candidate",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    async def memory_review_submit(
        name: str = "",
        description: str = "",
        body: str = "",
        kind: str = "insight",
        brain: str = "",
    ) -> str:
        """Stage an agent-curated observation as a pending review candidate."""
        return await memory_review_submit_impl(
            name=name,
            description=description,
            body=body,
            kind=kind,
            brain=brain or None,
        )

    if mcp_tool_interceptor:
        memory_review_submit = mcp_tool_interceptor(memory_review_submit)

    @mcp.tool(
        name="save-synthesis",
        annotations=tool_annotations(
            {
                "title": "Save Synthesis",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def save_synthesis(
        query: str = "",
        synthesis: str = "",
        sources: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> str:
        """Save a valuable search synthesis as a persistent knowledge note.

        Use after /search or /ask produces an answer worth keeping.
        The note is saved to the knowledge vault and becomes searchable
        in future queries — making explorations compound over time.
        """
        return await save_synthesis_impl(query, synthesis, sources, tags)

    if mcp_tool_interceptor:
        save_synthesis = mcp_tool_interceptor(save_synthesis)

    @mcp.tool(
        name="ask-retain",
        annotations=tool_annotations(
            {
                "title": "Retain /ask Outcome",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    async def ask_retain(
        question: str = "",
        answer: str = "",
        explicit_signals: list[str] | None = None,
        inferred_signals: list[str] | None = None,
        kinds: list[str] | None = None,
        retain_mode: str = "default",
        sources: list[str] | None = None,
        tags: list[str] | None = None,
        surface_footer: bool = False,
        to: str | None = None,
        cwd: str | None = None,
    ) -> str:
        """Persist a durable `/ask` outcome into memory and synthesis layers.

        Use after an `/ask` answer is complete. This keeps answer generation in
        the AI session while making retention one atomic MCP call.
        """
        return await retain_ask_outcome_impl(
            question=question,
            answer=answer,
            explicit_signals=explicit_signals,
            inferred_signals=inferred_signals,
            kinds=kinds,
            retain_mode=retain_mode,
            sources=sources,
            tags=tags,
            surface_footer=surface_footer,
            to=to,
            cwd=Path(cwd) if cwd else None,
        )

    if mcp_tool_interceptor:
        ask_retain = mcp_tool_interceptor(ask_retain)

    @mcp.tool(
        name="list-hub-recent-files",
        annotations=tool_annotations(
            {
                "title": "List Hub Recent Files",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def list_hub_recent_files(
        hub_id: str = "",
        hubId: str = "",
        limit: int = 10,
        per_skill_limit: int = 2,
    ) -> str:
        """List recent vault files across all skills in a hub."""
        from src.mcp.augur_shared.config import get_vault_dir
        from src.plugins.skill_discovery import discover_all_skills

        from .hub_recent import list_hub_recent_files_impl

        resolved_hub = hub_id or hubId
        if not resolved_hub:
            return json.dumps({"success": True, "files": [], "count": 0})

        # Find all skills belonging to this hub
        try:
            all_skills = discover_all_skills(tiers=(0,))
            skill_names = [s.name for s in all_skills if s.hub == resolved_hub]
        except Exception:
            skill_names = []

        if not skill_names:
            return json.dumps({"success": True, "files": [], "count": 0})

        vault_dir = get_vault_dir()

        return await list_hub_recent_files_impl(
            hub_id=resolved_hub,
            skill_names=skill_names,
            vault_dir=vault_dir,
            limit=limit,
            per_skill_limit=per_skill_limit,
        )

    if mcp_tool_interceptor:
        list_hub_recent_files = mcp_tool_interceptor(list_hub_recent_files)

    @mcp.tool(
        name="reindex-browse-category",
        annotations=tool_annotations(
            {
                "title": "Reindex Browse Category",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def reindex_browse_category(category: str) -> str:
        """Reindex a single browse category (pages, skills, actions, etc.)."""
        return await reindex_browse_category_impl(category)

    if mcp_tool_interceptor:
        reindex_browse_category = mcp_tool_interceptor(reindex_browse_category)

    # ==========================================================================
    # Skill Lifecycle Tools
    # ==========================================================================

    @mcp.tool(
        name="skill-adopt",
        annotations=tool_annotations(
            {
                "title": "Adopt External Skill",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    async def skill_adopt(name: str, source: str) -> str:
        """Adopt an external skill into skills/ for Augur management."""
        from src.mcp.augur_shared.config import get_project_root

        result = adopt_skill(name, source, get_project_root())
        return json.dumps(result)

    if mcp_tool_interceptor:
        skill_adopt = mcp_tool_interceptor(skill_adopt)

    @mcp.tool(
        name="skill-status",
        annotations=tool_annotations(
            {
                "title": "Get Skill Lifecycle Status",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def skill_status_tool(name: str) -> str:
        """Get the lifecycle status of a skill (ownership, source, location, upstream)."""
        from src.mcp.augur_shared.config import get_project_root

        result = skill_status(name, get_project_root())
        return json.dumps(result)

    if mcp_tool_interceptor:
        skill_status_tool = mcp_tool_interceptor(skill_status_tool)

    @mcp.tool(
        name="skill-upstream-status",
        annotations=tool_annotations(
            {
                "title": "Get Adopted Skill Upstream Status",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def skill_upstream_status_tool(name: str) -> str:
        """Get upstream metadata and update state for an adopted skill."""
        from src.mcp.augur_shared.config import get_project_root

        result = skill_upstream_status(name, get_project_root())
        return json.dumps(result)

    if mcp_tool_interceptor:
        skill_upstream_status_tool = mcp_tool_interceptor(skill_upstream_status_tool)

    @mcp.tool(
        name="skill-resync",
        annotations=tool_annotations(
            {
                "title": "Resync Managed Skill Exports",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def skill_resync_tool() -> str:
        """Rescan managed skill inventory and invalidate discovery for fresh repo-scoped exports."""
        from src.plugins.skill_discovery import invalidate_discovery_cache

        invalidate_discovery_cache()
        return json.dumps(
            {
                "success": True,
                "message": "Managed skill discovery invalidated. Repo-scoped exports will be refreshed on the next sync.",
            }
        )

    if mcp_tool_interceptor:
        skill_resync_tool = mcp_tool_interceptor(skill_resync_tool)

    # ==========================================================================
    # Context Injection Tools (KEY MOAT)
    # ==========================================================================

    @mcp.tool(
        name="get-context",
        annotations=tool_annotations(
            {
                "title": "Get Enriched Augur Context",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def get_context(params: GetContextInput) -> str:
        """Get enriched context for IDE agents - KEY MOAT TOOL."""
        return await get_context_impl(params, metrics, logger)

    if mcp_tool_interceptor:
        get_context = mcp_tool_interceptor(get_context)

    @mcp.tool(
        name="get-design-standards",
        annotations=tool_annotations(
            {
                "title": "Get UI Design Standards",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def get_design_standards() -> str:
        """Get UI design standards for dashboard development."""
        return await get_design_standards_impl(metrics, logger)

    if mcp_tool_interceptor:
        get_design_standards = mcp_tool_interceptor(get_design_standards)

    @mcp.tool(
        name="cross-skill",
        annotations=tool_annotations(
            {
                "title": "Cross-Skill Integration",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def cross_skill(source: str, target: str) -> str:
        """Get integration guidance between two skills."""
        return await cross_skill_impl(source, target, metrics)

    # ==========================================================================
    # Preference Tools
    # ==========================================================================

    @mcp.tool(
        name="get-preferences",
        annotations=tool_annotations(
            {
                "title": "Get User Preferences",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def get_preferences(params: GetPreferencesInput) -> str:
        """Get user preferences from config file."""
        return await get_preferences_impl(params)

    @mcp.tool(
        name="update-preference",
        annotations=tool_annotations(
            {
                "title": "Update User Preference",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def update_preference(params: UpdatePreferenceInput) -> str:
        """Update a user preference in config file."""
        return await update_preference_impl(params)

    # ==========================================================================
    # Hygiene Tools (routine-vault skill: store-wide artifact retention)
    # ==========================================================================

    @mcp.tool(
        name="hygiene-scan",
        annotations=tool_annotations(
            {
                "title": "Hygiene: Scan Folder for Stale Artifacts",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def hygiene_scan(path: str) -> str:
        """Read-only recursive scan of a folder under Documents. Returns files, lifecycle configs, milestone pins, never-touch skips. The agent in your session reasons over this output to propose archives."""
        return await hygiene_scan_impl(path)

    if mcp_tool_interceptor:
        hygiene_scan = mcp_tool_interceptor(hygiene_scan)

    @mcp.tool(
        name="hygiene-apply",
        annotations=tool_annotations(
            {
                "title": "Hygiene: Apply Archive Moves",
                "readOnlyHint": False,
                "destructiveHint": True,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    async def hygiene_apply(root: str, moves: list[dict[str, Any]], dry_run: bool = True) -> str:
        """Apply (or dry-run) a list of archive moves. dry_run defaults to True. Moves are atomic per file; refusal of one does not abort others. See response 'moves[].status' and 'moves[].refusal_category' for per-move outcomes."""
        return await hygiene_apply_impl(root=root, moves=moves, dry_run=dry_run)

    if mcp_tool_interceptor:
        hygiene_apply = mcp_tool_interceptor(hygiene_apply)

    @mcp.tool(
        name="hygiene-create-selection",
        annotations=tool_annotations(
            {
                "title": "Hygiene: Create Browse Sweep Selection",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    async def hygiene_create_selection(
        source_tab: str,
        filter_summary: dict[str, Any] | None,
        targets: list[dict[str, Any]],
    ) -> str:
        """Validate and persist an exact Browse Sweep visible selection."""
        return await hygiene_create_selection_impl(source_tab, filter_summary, targets)

    if mcp_tool_interceptor:
        hygiene_create_selection = mcp_tool_interceptor(hygiene_create_selection)

    @mcp.tool(
        name="hygiene-scan-selection",
        annotations=tool_annotations(
            {
                "title": "Hygiene: Scan Browse Sweep Selection",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def hygiene_scan_selection(selection_id: str) -> str:
        """Read-only scan of a previously validated Browse Sweep selection."""
        return await hygiene_scan_selection_impl(selection_id)

    if mcp_tool_interceptor:
        hygiene_scan_selection = mcp_tool_interceptor(hygiene_scan_selection)

    @mcp.tool(
        name="hygiene-apply-selection",
        annotations=tool_annotations(
            {
                "title": "Hygiene: Apply Browse Sweep Selection",
                "readOnlyHint": False,
                "destructiveHint": True,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    async def hygiene_apply_selection(
        selection_id: str,
        moves: list[dict[str, Any]],
        dry_run: bool = True,
    ) -> str:
        """Apply approved archive moves for a previously validated Browse Sweep selection."""
        return await hygiene_apply_selection_impl(selection_id, moves, dry_run)

    if mcp_tool_interceptor:
        hygiene_apply_selection = mcp_tool_interceptor(hygiene_apply_selection)


__all__ = [
    "register_core_tools",
    "ResponseFormat",
    "ListSkillsInput",
    "GetSkillInput",
    "LoadModuleInput",
    "LoadReferenceInput",
    "FindSkillInput",
    "CacheControlInput",
    "GetContextInput",
    "GetPreferencesInput",
    "UpdatePreferenceInput",
]
