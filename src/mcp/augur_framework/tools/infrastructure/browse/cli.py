"""CLI integration tools: registry, status, install, help, integrations listing."""

import json
import re
import shlex
import shutil
import subprocess
import time as _time

import yaml
from src.config.paths import (
    get_all_client_skill_dirs,
    get_project_root,
    get_vault_config_dir,
    get_vault_dir,
)
from src.lib.frontmatter_utils import parse_frontmatter
from src.mcp.augur_shared.safe_subprocess import safe_run

# ── CLI integration status cache (60s TTL, invalidated on install) ──
_cli_status_cache: dict[str, dict] = {}
_cli_status_ts: dict[str, float] = {}
_CLI_STATUS_TTL = 60.0

# ── CLI integration registry (built from frontmatter) ──
_cli_registry: dict[str, dict] = {}
_cli_registry_ts: float = 0.0
_CLI_REGISTRY_TTL = 300.0


def _resolve_default_cli_name() -> str:
    """Return the configured default dashboard CLI name."""
    cli_agents_path = get_vault_config_dir() / "ai" / "cli_agents.yaml"
    try:
        data = yaml.safe_load(cli_agents_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return "unknown"

    agents = data.get("agents")
    if not isinstance(agents, dict) or not agents:
        return "unknown"
    if "claude" in agents:
        return "claude"
    return next(iter(agents))


def _find_skill_dir(skill_id: str):
    project_root = get_project_root()
    for skills_dir in get_all_client_skill_dirs(project_root):
        candidate = skills_dir / skill_id
        if (candidate / "SKILL.md").exists():
            return candidate
    return None


def get_skill_cli_help_impl(skill_id: str = "", skill: str = "") -> str:
    """Return dashboard-ready CLI help markdown for one skill."""
    resolved_skill_id = (skill_id or skill or "").strip().strip("/")
    default_cli = _resolve_default_cli_name()
    if not resolved_skill_id:
        return json.dumps(
            {
                "success": False,
                "error": "skill_id is required",
                "default_cli": default_cli,
                "markdown": "",
            }
        )

    skill_dir = _find_skill_dir(resolved_skill_id)
    if skill_dir is None:
        return json.dumps(
            {
                "success": False,
                "error": f"Skill not found: {resolved_skill_id}",
                "default_cli": default_cli,
                "markdown": "",
            }
        )

    skill_title = resolved_skill_id
    try:
        skill_fm, _ = parse_frontmatter(skill_dir / "SKILL.md")
        if isinstance(skill_fm, dict):
            skill_title = skill_fm.get("x-augur-tab") or skill_fm.get("name") or resolved_skill_id
    except Exception:
        pass

    commands: list[dict[str, str]] = []
    commands_dir = skill_dir / "commands"
    if commands_dir.exists():
        for command_file in sorted(commands_dir.glob("*.md")):
            try:
                fm, body = parse_frontmatter(command_file)
            except Exception:
                fm, body = {}, command_file.read_text(errors="ignore")
            if not isinstance(fm, dict):
                fm = {}

            command_id = str(fm.get("id") or command_file.stem).strip()
            label = str(fm.get("label") or command_id.replace("-", " ").title())
            description = str(fm.get("description") or "").strip()
            body_summary = body.strip().splitlines()[0].strip() if body.strip() else ""
            commands.append(
                {
                    "id": command_id,
                    "label": label,
                    "description": description or body_summary,
                    "command": f"/{command_id}",
                }
            )

    lines = [
        f"# {skill_title} CLI Reference",
        "",
        f"Default CLI: `{default_cli}`",
        "",
        f"Skill: `{resolved_skill_id}`",
    ]

    if commands:
        lines.extend(["", "## Commands", ""])
        for command in commands:
            lines.append(f"### `{command['command']}`")
            lines.append("")
            lines.append(command["description"] or command["label"])
            lines.append("")
    else:
        lines.extend(["", "No command files were found for this skill."])

    return json.dumps(
        {
            "success": True,
            "skill_id": resolved_skill_id,
            "default_cli": default_cli,
            "markdown": "\n".join(lines).strip() + "\n",
            "commands": commands,
            "command_count": len(commands),
        }
    )


def _build_cli_registry() -> dict[str, dict]:
    """Build a registry of all CLI integrations from SKILL.md frontmatter."""
    global _cli_registry, _cli_registry_ts
    now = _time.time()
    if _cli_registry and now - _cli_registry_ts < _CLI_REGISTRY_TTL:
        return _cli_registry

    registry: dict[str, dict] = {}
    project_root = get_project_root()
    for skills_dir in get_all_client_skill_dirs(project_root):
        for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
            try:
                fm, _ = parse_frontmatter(skill_md)
            except Exception:
                continue
            if not isinstance(fm, dict):
                continue
            integrations = fm.get("x-augur-cli-integrations")
            if not integrations or not isinstance(integrations, list):
                continue
            for cli_def in integrations:
                if not isinstance(cli_def, dict) or "name" not in cli_def:
                    continue
                cli_name = cli_def["name"]
                registry[cli_name] = {
                    "install": cli_def.get("install", ""),
                    "version_cmd": cli_def.get("version_cmd", f"{cli_name} --version"),
                    "requires_config": cli_def.get("requires_config", False),
                    "config_check": cli_def.get("config_check", ""),
                    "homepage": cli_def.get("homepage", ""),
                    "skill": fm.get("name", skill_md.parent.name),
                    "skill_md": str(skill_md),
                }
    _cli_registry = registry
    _cli_registry_ts = now
    return registry


def _check_cli_status(cli_name: str, cli_def: dict, bypass_cache: bool = False) -> dict:
    """Check install/version/config status for a single CLI tool."""
    now = _time.time()
    if not bypass_cache and cli_name in _cli_status_cache:
        if now - _cli_status_ts.get(cli_name, 0) < _CLI_STATUS_TTL:
            return _cli_status_cache[cli_name]

    result: dict = {
        "name": cli_name,
        "installed": False,
        "version": None,
        "configured": None,
        "install_hint": cli_def.get("install", ""),
        "homepage": cli_def.get("homepage") or None,
    }

    # Check if installed
    which = shutil.which(cli_name)
    if not which:
        _cli_status_cache[cli_name] = result
        _cli_status_ts[cli_name] = now
        return result

    result["installed"] = True

    # Get version
    version_cmd = cli_def.get("version_cmd", f"{cli_name} --version")
    try:
        proc = safe_run(shlex.split(version_cmd), capture_output=True, text=True, timeout=3)
        output = (proc.stdout or proc.stderr or "").strip()
        if output:
            # Extract first non-empty line
            first_line = next((line for line in output.splitlines() if line.strip()), "")
            # Try to extract semver pattern
            ver_match = re.search(r"(\d+\.\d+[\.\d]*)", first_line)
            if ver_match:
                result["version"] = ver_match.group(1)[:40]
            else:
                result["version"] = first_line[:40]
    except (subprocess.TimeoutExpired, Exception):
        pass

    # Check config if required
    if cli_def.get("requires_config") and cli_def.get("config_check"):
        try:
            proc = safe_run(shlex.split(cli_def["config_check"]), capture_output=True, timeout=3)
            result["configured"] = proc.returncode == 0
        except (subprocess.TimeoutExpired, Exception):
            result["configured"] = None
    elif not cli_def.get("requires_config"):
        result["configured"] = None  # not applicable

    _cli_status_cache[cli_name] = result
    _cli_status_ts[cli_name] = now
    return result


async def list_integrations_impl() -> str:
    """List skills with CLI or vault integrations, discovered from SKILL.md frontmatter.

    Reads x-augur-cli-integrations and x-augur-integration-type from each
    skill's SKILL.md, checks install/version/config status live, and returns
    enriched data. Includes both IDE/CLI and vault integrations (ADR-436).
    """
    project_root = get_project_root()
    items = []

    for skills_dir in get_all_client_skill_dirs(project_root):
        for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
            skill = skill_md.parent.name

            try:
                fm, _ = parse_frontmatter(skill_md)
            except Exception:
                continue
            if not isinstance(fm, dict):
                continue

            integrations = fm.get("x-augur-cli-integrations")
            integration_type = fm.get("x-augur-integration-type")

            # Skip skills with neither CLI integrations nor vault integration type
            if (not integrations or not isinstance(integrations, list)) and not integration_type:
                continue

            skill_name = fm.get("name", skill)
            hub = "system"  # x-augur-hub removed by ADR-802
            description = fm.get("description", "")

            # Get MCP tool names from x-augur-mcp-tools frontmatter
            mcp_tools = fm.get("x-augur-mcp-tools") or []
            if not isinstance(mcp_tools, list):
                mcp_tools = []

            cli_tools = []
            overall_status = "ready"

            if integrations and isinstance(integrations, list):
                # Check status for each CLI tool
                for cli_def in integrations:
                    if not isinstance(cli_def, dict) or "name" not in cli_def:
                        continue
                    status = _check_cli_status(cli_def["name"], cli_def)
                    cli_tools.append(status)

                # Derive overall status (priority: missing > needs_config > ready)
                if any(not ct["installed"] for ct in cli_tools):
                    overall_status = "missing"
                elif any(
                    ct.get("configured") is False or ct.get("configured") is None and cli_def.get("requires_config")
                    for ct, cli_def in zip(cli_tools, integrations, strict=False)
                    if isinstance(cli_def, dict)
                ):
                    needs_config = False
                    for ct, cli_def_raw in zip(cli_tools, integrations, strict=False):
                        if not isinstance(cli_def_raw, dict):
                            continue
                        if cli_def_raw.get("requires_config") and ct.get("configured") in (False, None):
                            needs_config = True
                            break
                    overall_status = "needs_config" if needs_config else "ready"

            elif integration_type == "vault":
                # Vault integrations: check if vault dir exists
                vault_dir = get_vault_dir()
                # ADR-Track-3a: the literal "obsidian" check below is NOT a
                # vault-tier skill hardcode — it's an Obsidian-specific
                # configuration probe (the `.obsidian/` dir is unique to
                # Obsidian). Other vault-tier skills (apple, lifestyle,
                # file-manager, ingest) only need vault_dir.exists().
                if skill == "obsidian":
                    # Obsidian: check for .obsidian/ directory
                    obsidian_dir = vault_dir / ".obsidian"
                    overall_status = "ready" if obsidian_dir.exists() else "needs_config"
                else:
                    overall_status = "ready" if vault_dir.exists() else "missing"

            item = {
                "id": f"{hub}/{skill}",
                "title": skill_name.replace("-", " ").replace("_", " ").title(),
                "description": description,
                "hub": hub,
                "skill": skill,
                "path": str(skill_md),
                "cli_tools": cli_tools,
                "mcp_tool_count": len(mcp_tools),
                "status": overall_status,
            }
            if integration_type:
                item["integration_type"] = integration_type
            items.append(item)

    return json.dumps({"items": items, "count": len(items)})


async def cli_install_impl(name: str) -> str:
    """Install a CLI tool by name, looking up the install command from frontmatter.

    Only accepts CLI names declared in x-augur-cli-integrations — never runs
    caller-controlled commands.
    """
    registry = _build_cli_registry()
    if name not in registry:
        return json.dumps(
            {"success": False, "error": f"Unknown CLI tool: {name}. Not declared in any skill's frontmatter."}
        )

    cli_def = registry[name]
    install_cmd = cli_def.get("install", "")
    if not install_cmd or install_cmd.startswith("Built-in"):
        return json.dumps({"success": False, "error": f"{name} is a built-in utility and cannot be installed."})

    logs = []
    try:
        proc = safe_run(shlex.split(install_cmd), capture_output=True, text=True, timeout=120)
        if proc.stdout:
            logs.append(proc.stdout.strip())
        if proc.stderr:
            logs.append(proc.stderr.strip())

        # Invalidate cache for this CLI
        _cli_status_cache.pop(name, None)
        _cli_status_ts.pop(name, None)

        # Check if now installed
        status = _check_cli_status(name, cli_def, bypass_cache=True)

        return json.dumps(
            {
                "success": proc.returncode == 0,
                "installed": status["installed"],
                "version": status["version"],
                "logs": logs,
            }
        )
    except subprocess.TimeoutExpired:
        return json.dumps({"success": False, "error": "Install command timed out after 120s", "logs": logs})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e), "logs": logs})


async def cli_status_impl(name: str) -> str:
    """Check status of a CLI tool by name, bypassing cache."""
    registry = _build_cli_registry()
    if name not in registry:
        return json.dumps({"error": f"Unknown CLI tool: {name}. Not declared in any skill's frontmatter."})

    cli_def = registry[name]
    status = _check_cli_status(name, cli_def, bypass_cache=True)
    return json.dumps(status)


def cli_help_impl(cli_names: str) -> str:
    """Run --help for one or more CLI tools and return markdown output.

    Args:
        cli_names: Comma-separated CLI tool names (e.g. "openhue,sonos")

    Returns:
        JSON with markdown-formatted help output for each CLI.
    """
    names = [n.strip() for n in cli_names.split(",") if n.strip()]
    sections = []

    for name in names:
        # Skip osascript — it's a system tool, not a third-party CLI
        if name in ("osascript", "brew"):
            continue

        which = shutil.which(name)
        if not which:
            sections.append(
                f"## {name}\n\n" f"**Not installed.** Check install instructions in the integration config."
            )
            continue

        try:
            result = safe_run(
                [name, "--help"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            output = result.stdout or result.stderr or "(no output)"
            # Trim to reasonable length
            if len(output) > 3000:
                output = output[:3000] + "\n... (truncated)"
            sections.append(f"## {name}\n\n" f"**Path:** `{which}`\n\n" f"```\n{output.strip()}\n```")
        except subprocess.TimeoutExpired:
            sections.append(f"## {name}\n\n**Timed out** running `{name} --help`.")
        except Exception as e:
            sections.append(f"## {name}\n\n**Error:** {e}")

    if not sections:
        return json.dumps({"markdown": "No CLI tools to inspect.", "cli_count": 0})

    markdown = "\n\n---\n\n".join(sections)
    return json.dumps({"markdown": markdown, "cli_count": len(sections)})
