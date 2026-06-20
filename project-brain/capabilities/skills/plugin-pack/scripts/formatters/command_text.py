"""Shared command-text sanitizers for packaged native-client skills."""
from __future__ import annotations

import re

_COMMAND_DOC_LINK_RE = re.compile(
    r"\[[^\]]*commands/([A-Za-z0-9_-]+)\.md[^\]]*\]\((?:[^)\s]*/)?commands/\1\.md\)"
)
_COMMAND_DOC_PATH_RE = re.compile(r"(?:[A-Za-z0-9_.-]+/)*commands/([A-Za-z0-9_-]+)\.md")
_RETIRED_TOP_LEVEL_COMMAND_RE = re.compile(
    r"(?<![\w/.-])/(?P<namespace>augur:)?(?P<command>dev-merge|dev-build|dev-debug|dev-loops|adr|dev|sweep)(?![\w/-])"
)
_TOP_LEVEL_COMMANDS = {"ask", "discover", "keep", "project", "routines", "skillify"}
_PROJECT_ROUTER_VERBS = {"ask", "keep", "skillify", "routines", "adr", "dev", "sweep"}
_RETIRED_COMMAND_VERBS = {
    "adr": "adr",
    "dev": "dev",
    "sweep": "sweep",
    "dev-merge": "dev merge",
    "dev-build": "dev build",
    "dev-debug": "dev debug",
    "dev-loops": "dev loops",
}


def _packaged_command_reference(command_name: str) -> str:
    if command_name == "project":
        return "the packaged project command"
    if command_name in _TOP_LEVEL_COMMANDS:
        return f"the packaged /{command_name} command"
    if command_name in _RETIRED_COMMAND_VERBS:
        return f"/project {_RETIRED_COMMAND_VERBS[command_name]}"
    return f"the packaged Augur workflow '{command_name.replace('-', ' ')}'"


def _project_router_reference(command_name: str) -> str:
    if command_name in _PROJECT_ROUTER_VERBS:
        return f"the packaged project router implementation for {command_name.replace('-', ' ')}"
    if command_name in _TOP_LEVEL_COMMANDS:
        return f"the packaged /{command_name} command"
    return f"the packaged Augur workflow '{command_name.replace('-', ' ')}'"


def sanitize_command_doc_references(content: str) -> str:
    """Replace source command-doc paths with packaged command/workflow references."""
    sanitized = _COMMAND_DOC_LINK_RE.sub(
        lambda match: _packaged_command_reference(match.group(1)),
        content,
    )
    return _COMMAND_DOC_PATH_RE.sub(
        lambda match: _packaged_command_reference(match.group(1)),
        sanitized,
    )


def sanitize_project_router_content(content: str) -> str:
    """Remove source command-doc paths from /project without creating recursive dispatch text."""
    sanitized = _COMMAND_DOC_LINK_RE.sub(
        lambda match: _project_router_reference(match.group(1)),
        content,
    )
    return _COMMAND_DOC_PATH_RE.sub(
        lambda match: _project_router_reference(match.group(1)),
        sanitized,
    )


def sanitize_packaged_skill_content(content: str) -> str:
    """Remove command-doc links and retired top-level command cues from packaged skills."""
    sanitized = sanitize_command_doc_references(content)
    return _RETIRED_TOP_LEVEL_COMMAND_RE.sub(_replace_retired_command, sanitized)


def _replace_retired_command(match: re.Match[str]) -> str:
    namespace = match.group("namespace") or ""
    command = match.group("command")
    verb = _RETIRED_COMMAND_VERBS[command]
    if namespace:
        return f"/{namespace}project {verb}"
    return f"/project {verb}"
