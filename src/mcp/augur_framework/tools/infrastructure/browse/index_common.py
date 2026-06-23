"""Shared constants and small value helpers for the browse index modules."""

# Max items per browse request to prevent MCP timeout. Sized above the largest
# real category (tests ~1038) so dev-tier tabs aren't silently truncated; the
# result still carries total_count/truncated as a safety net past this bound.
_BROWSE_LIMIT = 1500

_FILESYSTEM_BACKED_CATEGORIES = {
    "actions",
    "commands",
    "documents",
    "mcp-tools",
    "pages",
    "scripts",
    "skills",
}

_AI_ARTIFACT_PROBLEM_IDS = {
    "permission_denied",
    "unreadable",
    "unknown_source",
    "low_confidence",
    "duplicate",
    "stale_generated",
    "conflicting_instruction",
    "missing_mcp_config",
}

_VAULT_JOURNEY_ROOTS = {
    "inbox": "inbox",
    "notes": "notes",
    "sources": "sources",
    "drafts": "drafts",
    "archive": "archive",
}

_ARCHIVE_SEARCH_METADATA_KEYS = (
    "archive_source",
    "archive_mode",
    "source_tab",
    "apply_run_id",
    "original_path",
    "archived_path",
    "repo_root",
    "repository_root",
    "git_action",
    "reason",
    "artifact_group",
    "journey_category",
    "source_path",
    "email_from",
    "email_to",
    "email_date",
    "message_id",
)


def _as_string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    if isinstance(value, tuple):
        return [str(item) for item in value if str(item)]
    if isinstance(value, str):
        if not value:
            return []
        return [part.strip() for part in value.split(",") if part.strip()]
    return []


def _metadata_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return ",".join(str(item).strip() for item in value if str(item).strip())
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)
