"""Client-specific MCP discovery surfaces.

Resource and resource-template filters affect what clients see in
discovery; they do not unregister backend capabilities from the server.

The legacy tool visibility filter (CURATED_VISIBLE_TOOLS,
COWORK_VISIBLE_TOOLS, filter_tools_for_client) was removed in Track 4
of the cross-client bundle migration. After Tracks 1-3a, no MCP server
registers more than ~114 tools, so the filter became dead code.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import TypeVar

T = TypeVar("T")


# Tool→owning-skill mapping retained as data for diagnostics and the
# architecture allowlist (tests/architecture/test_no_vault_skill_refs.py).
# Not a discovery enumeration — values just record which skill registers
# each tool. Entries here aren't required for tools to work.
PLUGIN_TOOL_SOURCES: dict[str, str] = {
    "get-attention-items": "attention",
    "get-attention-summary": "attention",
    "list-notifications": "daemon",
    "list-commands": "ai",
    "memory-search": "knowledge",
    "get-daemon-status": "daemon",
    "insights-pending": "daemon",
    "plugin-events-list": "daemon",
    "plugin-events-acknowledge": "daemon",
    "scan-folder": "file-manager",
    "get-context-files": "file-manager",
    "manage-cli-agents": "ai",
    "manage-tools-catalog": "ai",
    "run-adaptive-growth": "platform-admin",
    "generate-ide-instructions": "ai",
    "validate-agent-wizard": "ai",
    "reflect-context": "knowledge",
    "unified-search": "knowledge",
    "knowledge-project-index-rebuild": "knowledge",
    "knowledge-summarize-url": "knowledge",
    "knowledge-summarize-file": "knowledge",
    "start-rag-indexing": "knowledge",
    "search-skill-knowledge": "rag",
}


CURATED_VISIBLE_RESOURCE_URIS: frozenset[str] = frozenset(
    {
        "augur://core/mcp-registry",
    }
)

CURATED_VISIBLE_RESOURCE_TEMPLATES: frozenset[str] = frozenset(
    {
        "augur://skill/{skill}/overview",
        "augur://skill/{skill}/module/{module}",
        "augur://skill/{skill}/reference/{reference}",
    }
)


def filter_resources_for_client(client: str | None, resources: Iterable[T]) -> list[T]:
    return [resource for resource in resources if str(getattr(resource, "uri", "")) in CURATED_VISIBLE_RESOURCE_URIS]


def filter_resource_templates_for_client(client: str | None, templates: Iterable[T]) -> list[T]:
    return [
        template
        for template in templates
        if str(getattr(template, "uriTemplate", "")) in CURATED_VISIBLE_RESOURCE_TEMPLATES
    ]


def should_register_dynamic_markdown_resource(path: Path) -> bool:
    """Hide low-signal placeholder docs from MCP discovery."""
    return path.stem.lower() != "readme"
