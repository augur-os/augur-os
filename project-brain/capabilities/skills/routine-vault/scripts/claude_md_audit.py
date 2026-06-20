"""auto-claude-md-audit: Validate CLAUDE.md content accuracy.

Checks that the agent-rules.md source file (which generates CLAUDE.md)
accurately reflects the actual project state: hub list, slash commands,
file references. Also ensures claude-md-management plugin is installed.

Weekly cadence via SKILL.md trigger: weekly (engine-managed).
"""
from __future__ import annotations


import importlib.util as _augur_importlib_util
import sys as _augur_sys
from pathlib import Path as _AugurPath

_augur_bootstrap_start = _AugurPath(__file__).resolve()
for _augur_bootstrap_parent in (_augur_bootstrap_start.parent, *_augur_bootstrap_start.parents):
    _augur_bootstrap_path = _augur_bootstrap_parent / "daemon" / "scripts" / "bootstrap_paths.py"
    if _augur_bootstrap_path.is_file():
        break
else:
    raise RuntimeError(f"Unable to locate shared skill bootstrap from {_augur_bootstrap_start}")

_augur_bootstrap_spec = _augur_importlib_util.spec_from_file_location(
    "_augur_shared_bootstrap_paths", _augur_bootstrap_path
)
if _augur_bootstrap_spec is None or _augur_bootstrap_spec.loader is None:
    raise RuntimeError(f"Unable to load shared skill bootstrap from {_augur_bootstrap_path}")
_augur_bootstrap_module = _augur_importlib_util.module_from_spec(_augur_bootstrap_spec)
_augur_sys.modules[_augur_bootstrap_spec.name] = _augur_bootstrap_module
_augur_bootstrap_spec.loader.exec_module(_augur_bootstrap_module)
_augur_bootstrap_module.ensure_project_paths(__file__)
import json
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path

from src.config.paths import get_python_executable
from src.lib.frontmatter_utils import load_skill_contract
from src.lib.ops_protocol import FixResult, OpsContext, ScanResult

logger = logging.getLogger(__name__)

name = "auto-claude-md-audit"

_REPO_SOURCE_RULES = Path("docs") / "agent-topics" / "agent-rules.md"
_INSTALLED_PLUGINS_PATH = Path.home() / ".claude" / "plugins" / "installed_plugins.json"
_REQUIRED_PLUGIN = "claude-md-management@claude-plugins-official"

# Action constants — used in both scan() and fix()
_ACTION_STALE_COMMANDS = "stale-commands"
_ACTION_INSTALL_PLUGIN = "install-plugin"
_ACTION_TOPIC_DOC_DRIFT = "topic-doc-drift"

# Dashboard surfaces/routes (ADR-802, rule 13) are written `/browse` and
# `/workspace` — backtick-wrapped URL routes, NOT slash commands. They live in
# the dashboard route namespace, not the command namespace, so the phantom-command
# detector must not flag them. The regex below only matches single-segment tokens
# (`/[a-z][\w-]*`), so the bare surface roots are all that can collide; `/workspace/*`
# subpages carry a slash and never match.
_DASHBOARD_ROUTES = {"browse", "workspace"}

# Minimum required sections in agent-rules.md to consider it intact.
# If any of these are missing, the source is corrupted and must not be overwritten.
_REQUIRED_SECTIONS = [
    "## Critical Rules",
    "## Topic Docs",
    "## Directory Layout",
]
_MIN_SOURCE_BYTES = 1000


def _legacy_peer_data_dir(peer_name: str) -> Path:
    from src.lib.skill_paths import get_peer_data_dir

    return get_peer_data_dir(__file__, peer_name)


def _legacy_source_rules() -> Path:
    return _legacy_peer_data_dir("ai") / "agent-rules.md"


def _resolve_source_rules(project_root: Path) -> Path:
    """Prefer the canonical repo source, fall back to the legacy vault copy."""
    repo_source = project_root / _REPO_SOURCE_RULES
    if repo_source.exists():
        return repo_source
    return _legacy_source_rules()


def _normalise_command_name(raw: object) -> str:
    return str(raw or "").strip().lstrip("/")


def _add_skill_declared_commands(skill_md: Path, names: set[str]) -> None:
    contract = load_skill_contract(skill_md)
    frontmatter = contract.get("frontmatter")
    if not isinstance(frontmatter, dict):
        frontmatter = {}

    if str(frontmatter.get("x-augur-type") or "").strip() == "command":
        cmd_name = _normalise_command_name(contract.get("name"))
        if cmd_name:
            names.add(cmd_name)

    for command in contract.get("commands") or []:
        if not isinstance(command, dict):
            continue
        cmd_name = _normalise_command_name(command.get("id"))
        if cmd_name:
            names.add(cmd_name)

    contributions = contract.get("contributions")
    if not isinstance(contributions, dict):
        return
    for command in contributions.get("commands") or []:
        if not isinstance(command, dict):
            continue
        cmd_name = _normalise_command_name(command.get("id"))
        if cmd_name:
            names.add(cmd_name)


def _get_actual_commands(project_root: Path) -> set[str]:
    """Discover slash commands from both SKILL.md frontmatter and skill command dirs.

    Two sources contribute commands:
      1. Command-type SKILL.md files and declared x-augur command surfaces.
      2. `skills/{skill}/commands/*.md` files (subcommands like `/dev-build`,
         `/dev-merge`, `/auto-lint`, `/auto-format`). These are NOT declared in
         any SKILL.md but they ARE real slash commands.

    Previously this function only consulted `command_discovery.discover_commands`,
    which returns SKILL.md commands only. Subcommands therefore appeared in
    CLAUDE.md but not in the "actual" set, so the audit reported them as stale
    and surfaced a manual-review issue every run with no possible fix.
    """
    from src.config.paths import get_all_client_skill_dirs

    names: set[str] = set()

    # Source 1: command registry declarations.
    try:
        from src.plugins.command_discovery import discover_commands
        names.update(cmd.id for cmd in discover_commands())
    except Exception as exc:
        logger.debug("command_discovery unavailable, using direct SKILL.md scan: %s", exc)

    # Source 2: direct SKILL.md scan for command-type skills and declarations
    # under x-augur-config.contributions.commands.
    for skills_dir in get_all_client_skill_dirs(project_root):
        for skill_md in skills_dir.glob("*/SKILL.md"):
            try:
                _add_skill_declared_commands(skill_md, names)
            except Exception:
                continue

    # Source 3: subcommands stored as skills/{skill}/commands/{cmd}.md
    for skills_dir in get_all_client_skill_dirs(project_root):
        for cmd_md in skills_dir.glob("*/commands/*.md"):
            stem = cmd_md.stem
            if stem and not stem.startswith("_"):
                names.add(stem)

    return names


def _get_declared_commands(content: str) -> set[str]:
    """Extract slash command names from the Slash Commands and Dev Commands sections."""
    commands: set[str] = set()
    in_section = False
    for line in content.splitlines():
        if re.match(r"^##\s+(Slash Commands|Development Commands)", line):
            in_section = True
            continue
        if in_section and re.match(r"^##\s+", line):
            in_section = False
            continue
        if in_section:
            commands.update(re.findall(r"`/([a-z][\w-]*)`", line))
    return commands


def _check_topic_doc_drift(project_root: Path, actual_commands: set[str]) -> list[str]:
    """Check topic docs for phantom commands and stale path references."""
    topic_dir = project_root / "docs" / "agent-topics"
    if not topic_dir.is_dir():
        topic_dir = _legacy_peer_data_dir("ai") / "agent-topics"
    if not topic_dir.is_dir():
        return []

    drift_items: list[str] = []
    for doc in topic_dir.glob("*.md"):
        content = doc.read_text(encoding="utf-8")
        name = doc.name

        # Check for phantom slash commands (referenced but don't exist).
        # Exclude dashboard routes (`/browse`, `/workspace`) — those are URL
        # surfaces in the route namespace, not slash commands.
        referenced_cmds = set(re.findall(r"`/([a-z][\w-]*)`", content))
        phantom = referenced_cmds - actual_commands - _DASHBOARD_ROUTES
        if phantom:
            drift_items.append(f"{name}: phantom commands {sorted(phantom)}")

        # Check for stale plugins/ paths that reference removed directories
        stale_paths = re.findall(r"`plugins/(?:dev|orchestration|career|ai)/`", content)
        if stale_paths:
            drift_items.append(f"{name}: stale bundle paths {stale_paths} (skills moved to client dirs per ADR-426)")

    return drift_items


def _is_plugin_installed() -> bool:
    """Check if claude-md-management plugin is installed."""
    if not _INSTALLED_PLUGINS_PATH.exists():
        return False
    try:
        data = json.loads(_INSTALLED_PLUGINS_PATH.read_text())
        return _REQUIRED_PLUGIN in data.get("plugins", {})
    except (json.JSONDecodeError, OSError):
        return False


def _claude_command() -> str | None:
    """Resolve the Claude CLI executable, including .cmd shims on Windows."""
    return shutil.which("claude.cmd") or shutil.which("claude")


def _commit_files(project_root: Path, message: str, paths: list[str]) -> str | None:
    subprocess.run(["git", "add"] + paths, capture_output=True, cwd=str(project_root))
    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        capture_output=True,
        cwd=str(project_root),
    )
    if result.returncode == 0:
        return None
    result = subprocess.run(
        ["git", "commit", "-m", message],
        capture_output=True,
        text=True,
        cwd=str(project_root),
    )
    if result.returncode == 0:
        rev = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )
        return rev.stdout.strip() if rev.returncode == 0 else None
    return None


def scan(ctx: OpsContext) -> ScanResult:
    source = _resolve_source_rules(ctx.project_root)
    if not source.exists():
        return ScanResult(
            issues=[],
            summary=f"Source not found: {source}",
            severity="warning",
        )

    content = source.read_text(encoding="utf-8")
    issues: list[dict] = []

    # Slash command accuracy (hubs were retired in ADR-802; the former hub-list
    # consistency check is gone with them).
    actual_cmds = _get_actual_commands(ctx.project_root)
    declared_cmds = _get_declared_commands(content)
    stale_cmds = declared_cmds - actual_cmds
    if stale_cmds:
        issues.append({
            "action": _ACTION_STALE_COMMANDS,
            "stale": sorted(stale_cmds),
        })

    # Topic doc drift (phantom commands, stale paths)
    drift_items = _check_topic_doc_drift(ctx.project_root, actual_cmds)
    if drift_items:
        issues.append({
            "action": _ACTION_TOPIC_DOC_DRIFT,
            "items": drift_items,
        })

    # Plugin installation check
    if not _is_plugin_installed():
        claude_cmd = _claude_command()
        issues.append({
            "action": _ACTION_INSTALL_PLUGIN,
            "plugin": _REQUIRED_PLUGIN,
            "kind": "environment" if not claude_cmd else "maintenance",
            "root_cause_type": "external_dependency",
            "detail": (
                "Claude CLI unavailable; cannot install optional claude-md-management plugin"
                if not claude_cmd
                else "claude-md-management plugin missing"
            ),
        })

    if not issues:
        return ScanResult(issues=[], summary="CLAUDE.md content is accurate", severity="info")

    parts = []
    for iss in issues:
        if iss["action"] == _ACTION_STALE_COMMANDS:
            parts.append(f"{len(iss['stale'])} stale command refs")
        elif iss["action"] == _ACTION_TOPIC_DOC_DRIFT:
            parts.append(f"{len(iss['items'])} topic doc drift items")
        elif iss["action"] == _ACTION_INSTALL_PLUGIN:
            parts.append("claude-md-management plugin missing")

    return ScanResult(
        issues=issues,
        summary=f"CLAUDE.md issues: {', '.join(parts)}",
        severity="warning",
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    if ctx.dry_run:
        return FixResult(success=True, summary=f"Dry run: {len(issues)} issues found")

    source = _resolve_source_rules(ctx.project_root)
    if not source.exists():
        return FixResult(success=False, summary=f"Source not found: {source}")

    content = source.read_text(encoding="utf-8")

    # Guard: refuse to write back to a truncated/corrupted source file.
    # If required sections are missing, the source was externally corrupted
    # and writing back would propagate the damage through sync_agents.
    if len(content) < _MIN_SOURCE_BYTES:
        return FixResult(
            success=False,
            summary=f"Source file appears truncated ({len(content)} bytes < {_MIN_SOURCE_BYTES}). Refusing to modify.",
        )
    missing_sections = [s for s in _REQUIRED_SECTIONS if s not in content]
    if missing_sections:
        return FixResult(
            success=False,
            summary=f"Source file missing required sections: {missing_sections}. Refusing to modify.",
        )

    changes: list[str] = []
    modified = False

    for issue in issues:
        if issue["action"] == _ACTION_STALE_COMMANDS:
            changes.append(
                f"Stale command refs (manual review): {', '.join(issue['stale'])}"
            )

        elif issue["action"] == _ACTION_TOPIC_DOC_DRIFT:
            changes.append(
                f"Topic doc drift (manual review): {'; '.join(issue['items'])}"
            )

        elif issue["action"] == _ACTION_INSTALL_PLUGIN:
            claude_cmd = _claude_command()
            if not claude_cmd:
                changes.append(
                    "Skipped claude-md-management install: Claude CLI unavailable"
                )
                continue
            try:
                result = subprocess.run(
                    [claude_cmd, "plugin", "install", "claude-md-management"],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                changes.append(f"Failed to install claude-md-management: {exc}")
                continue
            if result.returncode == 0:
                changes.append("Installed claude-md-management plugin")
            else:
                changes.append(
                    f"Failed to install claude-md-management: {result.stderr[:200]}"
                )

    if modified:
        source.write_text(content, encoding="utf-8")
        # `skills.ai.scripts.sync_agents` resolves from project-brain/capabilities
        # (ADR-770 layout). The subprocess inherits os.environ, which only carries
        # that root in MCP context — add it explicitly so the sync works from any
        # shell (mirrors brain_init.py / the MCP runtime contract).
        sync_env = os.environ.copy()
        sync_roots = [
            str(ctx.project_root / "project-brain" / "capabilities"),
            str(ctx.project_root),
            str(ctx.project_root / "src" / "mcp"),
        ]
        if sync_env.get("PYTHONPATH"):
            sync_roots.append(sync_env["PYTHONPATH"])
        sync_env["PYTHONPATH"] = os.pathsep.join(sync_roots)
        subprocess.run(
            [str(get_python_executable()), "-m", "skills.ai.scripts.sync_agents", "sync", "all"],
            capture_output=True,
            cwd=str(ctx.project_root),
            timeout=120,
            env=sync_env,
        )
        sha = _commit_files(
            ctx.project_root,
            "fix(adaptive): update CLAUDE.md content accuracy",
            [str(source), "CLAUDE.md"],
        )
        if sha:
            changes.append(f"Committed {sha}")

    return FixResult(
        success=True,
        changes=changes,
        summary="; ".join(changes) if changes else "No fixable issues",
    )
