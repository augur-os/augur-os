"""Browse-related MCP tools: file actions and listing tools.

This package splits browse functionality into focused modules:
- _helpers: path security utilities
- file_actions: reveal_in_finder_impl, open_file_impl
- vault: list_vault_items_impl, list_knowledge_hub_files_impl
- skills: list_prompts_impl, list_scripts_impl, list_cli_commands_impl
- cli: CLI registry, status, install, help, integrations listing
- agents: list_agents_impl, list_adrs_impl
- dev: list_tests_impl, list_api_routes_impl
- index: browse_index_impl, skill enrichment cache
"""

# Re-export the full public API so that existing imports continue to work.
from src.config.paths import get_all_client_skill_dirs, get_project_root, get_vault_dir

from ._helpers import _allowed_roots, _is_path_allowed
from .agents import list_adrs_impl, list_agents_impl
from .background_routines import get_background_routine_detail_impl
from .cli import (
    _CLI_REGISTRY_TTL,
    _CLI_STATUS_TTL,
    _build_cli_registry,
    _check_cli_status,
    _cli_registry,
    _cli_registry_ts,
    _cli_status_cache,
    _cli_status_ts,
    cli_help_impl,
    cli_install_impl,
    cli_status_impl,
    get_skill_cli_help_impl,
    list_integrations_impl,
)
from .dev import list_api_routes_impl, list_tests_impl
from .document_sources import (
    attach_project_document_source_impl,
    list_project_document_sources_impl,
    update_project_document_source_summary_impl,
    upsert_document_catalog_summary_impl,
)
from .file_actions import open_file_impl, reveal_in_finder_impl, subprocess
from .index import (
    _SKILL_ENRICHMENT_TTL,
    _get_skill_enrichment,
    _populate_skill_enrichment,
    _skill_enrichment_cache,
    _skill_enrichment_ts,
    browse_index_impl,
)
from .promotion import promote_browse_item_impl
from .scheduled_conflict import adopt_cloud_impl, push_local_impl
from .scheduled_executions import (
    get_scheduled_execution_detail_impl,
    refresh_cloud_routines_impl,
    refresh_codex_routines_impl,
)
from .skills import list_cli_commands_impl, list_prompts_impl, list_scripts_impl
from .vault import list_knowledge_hub_files_impl, list_vault_items_impl

# Stable public interface re-exported by this package (WS5 split). Listed in
# __all__ so the backward-compatible re-exports are not flagged as unused.
__all__ = [
    "register_browse_tools",
    # paths
    "get_all_client_skill_dirs",
    "get_project_root",
    "get_vault_dir",
    # helpers
    "_allowed_roots",
    "_is_path_allowed",
    # agents
    "list_adrs_impl",
    "list_agents_impl",
    # background routines
    "get_background_routine_detail_impl",
    # cli
    "_CLI_REGISTRY_TTL",
    "_CLI_STATUS_TTL",
    "_build_cli_registry",
    "_check_cli_status",
    "_cli_registry",
    "_cli_registry_ts",
    "_cli_status_cache",
    "_cli_status_ts",
    "cli_help_impl",
    "cli_install_impl",
    "cli_status_impl",
    "get_skill_cli_help_impl",
    "list_integrations_impl",
    # dev
    "list_api_routes_impl",
    "list_tests_impl",
    # document sources
    "attach_project_document_source_impl",
    "list_project_document_sources_impl",
    "update_project_document_source_summary_impl",
    "upsert_document_catalog_summary_impl",
    # file actions
    "open_file_impl",
    "reveal_in_finder_impl",
    "subprocess",
    # index
    "_SKILL_ENRICHMENT_TTL",
    "_get_skill_enrichment",
    "_populate_skill_enrichment",
    "_skill_enrichment_cache",
    "_skill_enrichment_ts",
    "browse_index_impl",
    # promotion
    "promote_browse_item_impl",
    # scheduled conflict
    "adopt_cloud_impl",
    "push_local_impl",
    # scheduled executions
    "get_scheduled_execution_detail_impl",
    "refresh_cloud_routines_impl",
    "refresh_codex_routines_impl",
    # skills
    "list_cli_commands_impl",
    "list_prompts_impl",
    "list_scripts_impl",
    # vault
    "list_knowledge_hub_files_impl",
    "list_vault_items_impl",
]


def register_browse_tools(mcp, mcp_tool_interceptor=None, metrics=None):
    """Register browse-related MCP tools."""
    from src.mcp.augur_shared.annotations import tool_annotations

    @mcp.tool(
        name="reveal-in-finder",
        annotations=tool_annotations(
            {
                "title": "Reveal in Finder",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def reveal_in_finder(path: str) -> str:
        """Reveal a file or directory in the system file manager."""
        return await reveal_in_finder_impl(path)

    @mcp.tool(
        name="open-file",
        annotations=tool_annotations(
            {
                "title": "Open File",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def open_file(path: str = "", file: str = "") -> str:
        """Open a file in its default application.

        Args:
            path: File path to open (dashboard alias: file)
            file: Dashboard alias for path
        """
        return await open_file_impl(path or file)

    @mcp.tool(
        name="list-vault-items",
        annotations=tool_annotations(
            {
                "title": "List Vault Items",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def list_vault_items() -> str:
        """List all items in the user vault."""
        return await list_vault_items_impl()

    @mcp.tool(
        name="list-prompts",
        annotations=tool_annotations(
            {
                "title": "List Prompts",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def list_prompts() -> str:
        """List all prompt templates across plugins."""
        return await list_prompts_impl()

    @mcp.tool(
        name="list-scripts",
        annotations=tool_annotations(
            {
                "title": "List Scripts",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def list_scripts() -> str:
        """List all scripts across plugins."""
        return await list_scripts_impl()

    @mcp.tool(
        name="list-cli-commands",
        annotations=tool_annotations(
            {
                "title": "List Commands",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def list_cli_commands() -> str:
        """List command docs from skill command folders."""
        return await list_cli_commands_impl()

    @mcp.tool(
        name="list-integrations",
        annotations=tool_annotations(
            {
                "title": "List Integrations",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def list_integrations() -> str:
        """List all integration declarations across Augur integrations."""
        return await list_integrations_impl()

    @mcp.tool(
        name="list-agents",
        annotations=tool_annotations(
            {
                "title": "List Agents",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def list_agents() -> str:
        """List all agent declarations from config and canonical agent definitions."""
        return await list_agents_impl()

    @mcp.tool(
        name="list-adrs",
        annotations=tool_annotations(
            {
                "title": "List ADRs",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def list_adrs() -> str:
        """List all Architecture Decision Records."""
        return await list_adrs_impl()

    @mcp.tool(
        name="list-tests",
        annotations=tool_annotations(
            {
                "title": "List Tests",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def list_tests() -> str:
        """List all test files across the project."""
        return await list_tests_impl()

    @mcp.tool(
        name="list-api-routes",
        annotations=tool_annotations(
            {
                "title": "List API Routes",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def list_api_routes() -> str:
        """List all API routes from the dashboard."""
        return await list_api_routes_impl()

    @mcp.tool(
        name="browse-index",
        annotations=tool_annotations(
            {
                "title": "Browse Index",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def browse_index(
        category: str,
        hub: str | None = None,
        limit: int = 0,
        search: str | None = None,
        journey_category: str | None = None,
        scope: str | None = None,
    ) -> str:
        """List items from the unified RAG index for browse display.

        Args:
            category: One of: skills, adrs, actions, prompts, vault, documents,
                      agents, integrations, commands, mcp-tools, scripts,
                      api-routes, tests, pages, blocks, workflows, wiki, logs,
                      background-routines, scheduled-executions, profile
            hub: Optional hub filter (career, finance, health, etc.)
            limit: Max items to return (0 = default limit of 1000)
            search: Optional text search (filters on name + description server-side)
            journey_category: Optional vault journey filter for inbox, notes,
                              sources, drafts, archive, or system-metadata.
            scope: Optional overlay scope filter: shared, private, or packet.
        """
        return browse_index_impl(category, hub, limit, search, journey_category, scope)

    @mcp.tool(
        name="attach-project-document-source",
        annotations=tool_annotations(
            {
                "title": "Attach Project Document Source",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    async def attach_project_document_source(
        source_id: str,
        name: str,
        provider: str,
        remote_id: str,
        attached_brain_ids: list[str] | str | None = None,
        catalog_title: str = "",
        catalog_summary: str = "",
        summary_status: str = "human",
        summary_generated_from_revision: str = "",
        remote_revision: str = "",
        remote_modified_at: str = "",
        replace: bool = False,
    ) -> str:
        """Attach a shared project document source through git-tracked config."""
        return await attach_project_document_source_impl(
            source_id=source_id,
            name=name,
            provider=provider,
            remote_id=remote_id,
            attached_brain_ids=attached_brain_ids,
            catalog_title=catalog_title,
            catalog_summary=catalog_summary,
            summary_status=summary_status,
            summary_generated_from_revision=summary_generated_from_revision,
            remote_revision=remote_revision,
            remote_modified_at=remote_modified_at,
            replace=replace,
        )

    @mcp.tool(
        name="list-project-document-sources",
        annotations=tool_annotations(
            {
                "title": "List Project Document Sources",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def list_project_document_sources() -> str:
        """List git-tracked project document source records."""
        return await list_project_document_sources_impl()

    @mcp.tool(
        name="update-project-document-source-summary",
        annotations=tool_annotations(
            {
                "title": "Update Project Document Source Summary",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    async def update_project_document_source_summary(
        source_id: str,
        catalog_summary: str,
        catalog_title: str = "",
        summary_status: str = "human",
        summary_generated_from_revision: str = "",
    ) -> str:
        """Update the human-approved summary for a configured source."""
        return await update_project_document_source_summary_impl(
            source_id=source_id,
            catalog_summary=catalog_summary,
            catalog_title=catalog_title,
            summary_status=summary_status,
            summary_generated_from_revision=summary_generated_from_revision,
        )

    @mcp.tool(
        name="upsert-document-catalog-summary",
        annotations=tool_annotations(
            {
                "title": "Upsert Document Catalog Summary",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    async def upsert_document_catalog_summary(
        source_id: str,
        title: str,
        summary: str,
        remote_id: str = "",
        canonical_document_id: str = "",
        source_relative_path: str = "",
        provider: str = "",
        attached_brain_ids: list[str] | str | None = None,
        summary_status: str = "human",
        summary_generated_from_revision: str = "",
        remote_revision: str = "",
        remote_modified_at: str = "",
    ) -> str:
        """Write or update one git-tracked document catalog summary card."""
        return await upsert_document_catalog_summary_impl(
            source_id=source_id,
            title=title,
            summary=summary,
            remote_id=remote_id,
            canonical_document_id=canonical_document_id,
            source_relative_path=source_relative_path,
            provider=provider,
            attached_brain_ids=attached_brain_ids,
            summary_status=summary_status,
            summary_generated_from_revision=summary_generated_from_revision,
            remote_revision=remote_revision,
            remote_modified_at=remote_modified_at,
        )

    @mcp.tool(
        name="promote-browse-item",
        annotations=tool_annotations(
            {
                "title": "Promote Browse Item",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    async def promote_browse_item(
        category: str,
        title: str,
        source_path: str,
        description: str = "",
        roles: list[str] | str | None = None,
        domains: list[str] | str | None = None,
        to: str | None = None,
    ) -> str:
        """Create an append-only promotion packet for a browse item.

        Default (no ``to``): a project-brain promotion packet for a private-vault
        item. With ``to`` set: a source-contained source-brain -> target-brain
        propagation packet written into the target brain's promotions inbox.

        Args:
            category: One of notes, sources, wiki, or skills.
            title: Human-readable packet topic.
            source_path: Existing file path inside the source brain.
            description: Packet synthesis body.
            roles: Optional roles for packet metadata.
            domains: Optional domains for packet metadata.
            to: Optional target brain id for explicit cross-brain propagation.
        """
        return promote_browse_item_impl(
            category=category,
            title=title,
            source_path=source_path,
            description=description,
            roles=roles,
            domains=domains,
            to=to,
        )

    @mcp.tool(
        name="get-background-routine-detail",
        annotations=tool_annotations(
            {
                "title": "Background Routine Detail",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def get_background_routine_detail(routine_id: str) -> str:
        """Return one normalized background routine detail record."""
        return get_background_routine_detail_impl(routine_id)

    @mcp.tool(
        name="get-scheduled-execution-detail",
        annotations=tool_annotations(
            {
                "title": "Scheduled Execution Detail",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def get_scheduled_execution_detail(execution_id: str) -> str:
        """Return one normalized scheduled execution detail record."""
        return get_scheduled_execution_detail_impl(execution_id)

    @mcp.tool(
        name="routine-refresh-codex",
        annotations=tool_annotations(
            {
                "title": "Refresh Codex Routine Status",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def routine_refresh_codex() -> str:
        """Rescan ~/.codex/automations/ and return Codex routine rows with drift status."""
        return refresh_codex_routines_impl()

    @mcp.tool(
        name="routine-refresh-cloud",
        annotations=tool_annotations(
            {
                "title": "Refresh Claude Cloud Routine Cache",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": True,
            }
        ),
    )
    async def routine_refresh_cloud() -> str:
        """Refresh the Claude remote routines cache via a `claude --print` subprocess.

        Spawns a one-shot Claude Code session that uses RemoteTrigger to list
        cloud routines and writes them to the local cache file. Avoids
        embedding the user's OAuth token in server-side Python.
        """
        return refresh_cloud_routines_impl()

    @mcp.tool(
        name="routine-adopt-cloud",
        annotations=tool_annotations(
            {
                "title": "Adopt Surface State into Seed",
                "readOnlyHint": False,
                "destructiveHint": True,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def routine_adopt_cloud(routine_id: str) -> str:
        """Pull the installed surface state into the seed file for one routine.

        Args:
            routine_id: Browse id, e.g. "codex:codex-dev-loop-testing".
        """
        return adopt_cloud_impl(routine_id)

    @mcp.tool(
        name="routine-push-local",
        annotations=tool_annotations(
            {
                "title": "Push Seed over Installed Surface",
                "readOnlyHint": False,
                "destructiveHint": True,
                "idempotentHint": True,
                "openWorldHint": True,
            }
        ),
    )
    async def routine_push_local(routine_id: str) -> str:
        """Force-sync seed state over the installed surface for one routine.

        Args:
            routine_id: Browse id, e.g. "codex:codex-dev-loop-testing"
                or "claude-remote:trig_abc123".
        """
        return push_local_impl(routine_id)

    @mcp.tool(
        name="cli-install",
        annotations=tool_annotations(
            {
                "title": "CLI Install",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": True,
            }
        ),
    )
    async def cli_install(name: str) -> str:
        """Install a CLI tool by name. Only accepts names declared in skill frontmatter.

        Args:
            name: CLI tool name (e.g. "gws", "openhue", "sonos")
        """
        return await cli_install_impl(name)

    @mcp.tool(
        name="cli-status",
        annotations=tool_annotations(
            {
                "title": "CLI Status",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def cli_status(name: str) -> str:
        """Check install/version/config status of a CLI tool, bypassing cache.

        Args:
            name: CLI tool name (e.g. "gws", "openhue", "sonos")
        """
        return await cli_status_impl(name)

    @mcp.tool(
        name="cli-help",
        annotations=tool_annotations(
            {
                "title": "CLI Help",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def cli_help(cli_names: str = "", tools: str = "") -> str:
        """Run --help for CLI tools and return formatted markdown.

        Args:
            cli_names: Comma-separated CLI tool names (e.g. "openhue,sonos")
            tools: Alias for cli_names (used by dashboard query param)
        """
        resolved = cli_names or tools
        return cli_help_impl(resolved)

    @mcp.tool(
        name="get-skill-cli-help",
        annotations=tool_annotations(
            {
                "title": "Skill CLI Help",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def get_skill_cli_help(skill_id: str = "", skill: str = "") -> str:
        """Return CLI help/reference markdown for one Augur skill.

        Args:
            skill_id: Skill id, e.g. "knowledge"
            skill: Alias for skill_id
        """
        return get_skill_cli_help_impl(skill_id, skill)
