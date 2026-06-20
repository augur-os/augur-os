"""Augur capabilities discovery tool (ADR-442).

Returns currently enabled domains and their tool counts.
Used by Cowork Claude to understand what's available at conversation start.

Track 3a PR 3 replaced the hardcoded `_DOMAIN_DEFS` map with dynamic
discovery: capabilities now come from each registered skill's SKILL.md
frontmatter (`x-augur-description` or the leading paragraph) so adding
or removing a skill no longer requires editing this file.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server import Server

logger = logging.getLogger(__name__)


def _load_capabilities() -> dict[str, str]:
    """Discover skill capability descriptions from SKILL.md frontmatter."""

    from src.mcp.augur_shared.plugin_tools import _collect_skill_dirs

    out: dict[str, str] = {}
    for _plugin_id, skill_dir in _collect_skill_dirs(apply_exclusions=False):
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue
        try:
            text = skill_md.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            logger.debug(f"capabilities: could not read {skill_md}: {exc}")
            continue
        # Pull frontmatter (delimited by --- ... ---). Look for `x-augur-description`
        # first, then fall back to the top-level `description` key.
        description = _extract_frontmatter_description(text)
        if description:
            out[skill_dir.name] = description
    return out


def _extract_frontmatter_description(text: str) -> str | None:
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 4)
    if end == -1:
        return None
    block = text[4:end]
    description: str | None = None
    augur_description: str | None = None
    for raw_line in block.splitlines():
        if raw_line.startswith("description:"):
            description = raw_line.split(":", 1)[1].strip().strip('"').strip("'")
        elif raw_line.startswith("x-augur-description:"):
            augur_description = raw_line.split(":", 1)[1].strip().strip('"').strip("'")
    return augur_description or description


def _build_capabilities_response(client: str = "cowork") -> dict:
    """Build capabilities response without MCP dependency (testable)."""
    capabilities = _load_capabilities()
    domains = [{"name": name, "description": description} for name, description in sorted(capabilities.items())]
    return {
        "domains": domains,
        "total_tools": len(domains),
        "client": client,
    }


def register_tools(mcp: Server, interceptor=None, metrics=None) -> None:
    """Register augur-list-capabilities tool."""

    @mcp.tool(name="augur-list-capabilities")
    async def list_capabilities() -> dict:
        """List available Augur capability domains.

        Returns the currently enabled domains and their descriptions.
        Call this early in conversation to understand what Augur can help with.
        """
        return _build_capabilities_response()
