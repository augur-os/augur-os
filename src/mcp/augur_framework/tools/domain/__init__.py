"""
Domain-specific tools - Augur verticals and specialized features.

This module contains tools for specific verticals like health, career, etc.
These tools handle domain-specific data and workflows.

## Skill- and Integration-Provided Tools (ADR-012)

The following tools are now provided by skills and integrations and loaded dynamically:

### Virtual Doctor (apps/virtual-doctor/mcp/)
- `get-virtual-doctor-data`: Get virtual doctor data
- `save-virtual-doctor-data`: Save virtual doctor data
- `get-virtual-doctor-documents`: Get medical documents list
- `get-virtual-doctor-history`: Get medical history entries
- `add-history-entry`: Add medical history entry
- `get-virtual-doctor-medications`: Get medications list
- `add-medication`: Add medication entry
- `delete-medication`: Delete medication by ID
- `get-virtual-doctor-symptoms`: Get symptoms list
- `add-symptom`: Add symptom entry
- `delete-symptom`: Delete symptom by ID

### Careers/Job Analyzer (apps/careers/mcp/)
- `get-career-jobs`: Get all career jobs from queues
- `add-career-job`: Add a job URL to inbox
- `delete-career-job`: Delete a job file
- `get-career-companies`: Get researched companies list
- `get-career-job-counts`: Get job counts by queue

### Project Manager (orchestrator/executor/mcp/)
- `get-sprint-info`: Get information about current sprint

### Knowledge (knowledge/knowledge/mcp/)
- `list-rag-projects`: List all RAG projects
- `create-rag-project`: Create a new RAG project

### File Manager (file-manager/mcp/)
- `scan-folder`: Scan directory for file organization suggestions

### Daemon (daemon/daemon/mcp/)
- `check-expirations`: Check data files for expired items
- `set-expiry`: Set expiry policy or date on a data item
- `get-expiry-status`: Get overview of expiry status

## Core Domain Tools (remaining in augur-mcp)

### Agent Management — advisor is staged/draft-only; keep active exposure disabled until promotion
- `get-agent-weights`: Get agent weights configuration
- `update-agent-weights`: Update agent weights
- `get-agent-telemetry`: Get comprehensive agent telemetry data

### Inbox & Routing - provided by Apple and channels skills
- `apple-refresh-inbox`: Get inbox items from Apple Notes and desktop files
- `route-inbox-item`: Route inbox item to target skill
- `route-all-inbox-items`: Auto-route all high-confidence inbox items
- `route-agent-request`: Route a user request to the most appropriate agent

### Cowork Integration (cowork.py) — ADR-135
- `sync-cowork-results`: Scan state/cowork-dispatch/ for completed tasks and ingest results
- `get-cowork-status`: Report pending/completed task counts and dispatch dir health
- `classify-collateral`: Trigger LLM-powered routing of stray repo-root files to skill assets dirs

### IDE Integration (ide.py)
- `send-ide-prompt`: Send prompt to IDE for LLM processing
- `ide-integrations`: Manage IDE integrations and configurations
- `get-ide-history`: Get recent IDE prompt history
- `get-ide-status`: Get current IDE connection status

### Plugin Factory (factory/mcp-app-factory/mcp/) - includes:
- `generate-ide-instructions`: Generate IDE-specific instructions (moved from ide.py)

### Plugin & Skill Management (plugins.py)
- `list-plugins`: List all plugins
- `toggle-plugin`: Enable/disable a plugin
- `install-plugin`: Install a plugin from source
- `uninstall-plugin`: Uninstall a plugin
- `plugin-health`: Health check on all plugins
- `reload-plugin`: Reload a plugin
- `toggle-skill`: Toggle skill enabled state
- `uninstall-skill`: Uninstall a skill

### Memory (knowledge/knowledge/mcp/) - ADR-028: Two-Layer Memory Architecture
Memory tools are part of the Knowledge plugin:
- `memory-search`: Search decisions, patterns, preferences
- `memory-log-decision`: Log a decision to daily log
- `memory-log-preference`: Log a user preference
- `memory-curate`: Distill daily logs to MEMORY.md
- `memory-stats`: Get memory system statistics
- `memory-add-decision`: Add decision directly to MEMORY.md
- `memory-rebuild-index`: Rebuild YAML search index
"""

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from src.mcp.augur_shared.logging import get_entity_logger

# Dynamic skill/integration tool loading (ADR-012)
from src.mcp.augur_shared.plugin_tools import register_plugin_tools as register_dynamic_plugin_tools

from ..hubs import register_hub_tools
from .cowork import register_cowork_tools
from .ide import register_ide_tools
from .plugins import register_plugin_tools
from .vault_sync import register_vault_sync_tools

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

logger = get_entity_logger("mcp.domain")


def register_domain_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable,
    metrics: Any,
) -> None:
    """
    Register domain tools with the MCP server.

    Args:
        mcp: FastMCP server instance
        mcp_tool_interceptor: Decorator for tool interception
        metrics: MetricsTracker instance for telemetry
    """
    # =========================================================================
    # Training Mode Tools (Job Analyzer) - MOVED TO PLUGINS (apps/careers)
    # =========================================================================

    # =========================================================================
    # Hub Tools (ADR-442: Capabilities Discovery)
    # =========================================================================
    try:
        register_hub_tools(mcp, interceptor=mcp_tool_interceptor, metrics=metrics)
    except Exception as e:
        logger.error(f"Failed to register hub tools: {e}")

    # =========================================================================
    # Plugin-Provided Tools (ADR-012: Community Package Extraction)
    # =========================================================================
    # These tools are loaded dynamically from plugin mcp/ directories.
    # This enables community plugins to provide their own MCP tools.
    # Plugins scanned: vertical-life/virtual-doctor, vertical-work/careers, etc.
    try:
        register_dynamic_plugin_tools(mcp, mcp_tool_interceptor, metrics)
    except Exception as e:
        logger.error(f"Failed to load plugin tools: {e}")

    # =========================================================================
    # Cowork Integration Tools (ADR-135)
    # =========================================================================
    try:
        register_cowork_tools(mcp, mcp_tool_interceptor, metrics)
    except Exception as e:
        logger.error(f"Failed to register cowork tools: {e}")

    # =========================================================================
    # IDE Integration Tools
    # =========================================================================
    register_ide_tools(mcp, mcp_tool_interceptor, metrics)

    # =========================================================================
    # Vault Sync Tools - status + one-click commit/pull/push
    # =========================================================================
    register_vault_sync_tools(mcp, mcp_tool_interceptor, metrics)

    # =========================================================================
    # Agent Management Tools - review queue now lives with the channels skill
    # =========================================================================

    # =========================================================================
    # Inbox & Routing Tools - PROVIDED BY PLUGIN (see plugins/productivity/ or plugins/observability/ for inbox skill)
    # =========================================================================

    # =========================================================================
    # Unified Agent Management Tools - MOVED TO PLUGINS (crew/agent-manager)
    # Tools: sync-agents, get-agent-health
    # =========================================================================

    # =========================================================================
    # Plugin & Skill Management Tools (merged plugins.py + skills.py)
    # =========================================================================
    register_plugin_tools(mcp, mcp_tool_interceptor, metrics)

    # =========================================================================
    # Memory Tools - MOVED TO PLUGIN (knowledge/knowledge/mcp/)
    # ADR-028: Two-Layer Memory Architecture
    # Tools: memory-search, memory-log-decision, memory-log-preference,
    #        memory-curate, memory-stats, memory-add-decision, memory-rebuild-index
    # =========================================================================

    # =========================================================================
    # Data Expiration Tools - MOVED TO PLUGINS (daemon/daemon)
    # Tools: check-expirations, set-expiry, get-expiry-status
    # =========================================================================

    # =========================================================================
    # Bossanova Automation Tools - MOVED TO PLUGINS (apps/bossanova)
    # =========================================================================

    # =========================================================================
    # IDE Backlog Tools - MOVED TO PLUGINS (factory/mcp-app-factory)
    # Tools: skill-generate, command-execute, backlog-list, backlog-read, skill-analyze
    # =========================================================================


__all__ = ["register_domain_tools"]
