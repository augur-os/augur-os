"""Helpers for MCP diagnostics payload construction."""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from src.config.mcp_config_drift import scan_global_mcp_config_references
from src.mcp.augur_shared.config import get_config_dir
from src.mcp.augur_shared.safe_subprocess import safe_run as subprocess_run  # nosec B404


def load_toml_file(path: Path) -> dict[str, Any]:
    """Load TOML config using the stdlib parser on Python 3.11+."""
    if not path.exists():
        return {}
    try:
        import tomllib
    except ModuleNotFoundError:  # pragma: no cover
        import tomli as tomllib  # type: ignore
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _expand_environment_tokens(raw_path: str) -> str:
    """Expand POSIX and Windows-style environment variables in config paths."""
    expanded = os.path.expandvars(raw_path)

    def replace_windows_var(match: re.Match[str]) -> str:
        name = match.group(1)
        return os.environ.get(name, match.group(0))

    return re.sub(r"%([A-Za-z_][A-Za-z0-9_]*)%", replace_windows_var, expanded)


def platform_config_path(config_path: Any, project_root: Path) -> str:
    """Resolve platform-specific config path definitions from ide_mcp_configs."""
    if isinstance(config_path, str):
        raw = config_path
    elif isinstance(config_path, dict):
        platform_key = {
            "darwin": "darwin",
            "linux": "linux",
            "win32": "windows",
        }.get(sys.platform, "all")
        raw = config_path.get(platform_key) or config_path.get("all") or ""
    else:
        raw = ""

    return _expand_environment_tokens(raw.replace("{repo_root}", str(project_root)))


def read_server_map(
    config_path: Path,
    *,
    config_format: str,
    server_key: str,
    config_structure: str,
    project_root: Path,
) -> tuple[dict[str, Any], str | None]:
    """Read the MCP server map from a client config file."""
    if not config_path.exists():
        return {}, None

    try:
        if config_format == "toml":
            content = load_toml_file(config_path)
        else:
            raw_content = config_path.read_text(encoding="utf-8")
            content = json.loads(raw_content) if raw_content.strip() else {}
    except Exception as exc:
        return {}, f"Failed to parse config: {exc}"

    if not isinstance(content, dict):
        return {}, "Failed to parse config: expected top-level object"

    container: Any = content
    if config_structure == "per_project":
        projects = content.get("projects", {})
        if not isinstance(projects, dict):
            return {}, "Failed to parse config: expected 'projects' object"

        target_path = project_root.resolve()
        matched_key = None
        for k in projects:
            try:
                if Path(k).resolve() == target_path:
                    matched_key = k
                    break
            except Exception:
                pass
        container = projects.get(matched_key or str(project_root), {})
        if not isinstance(container, dict):
            return {}, f"Project not configured for {project_root}"

    server_map = container.get(server_key, {})
    if not isinstance(server_map, dict):
        return {}, f"Failed to parse config: expected '{server_key}' object"

    return server_map, None


def _is_augur_server_name(name: str) -> bool:
    return name == "augur" or name.startswith("augur-")


def build_client_report(
    key: str,
    *,
    config_path: Path,
    config_format: str,
    server_key: str,
    config_structure: str,
    project_root: Path,
) -> dict[str, Any]:
    """Build the dashboard MCP client summary for one integration."""
    report: dict[str, Any] = {
        "configPath": str(config_path),
        "exists": config_path.exists(),
        "servers": [],
    }

    server_map, parse_error = read_server_map(
        config_path,
        config_format=config_format,
        server_key=server_key,
        config_structure=config_structure,
        project_root=project_root,
    )
    if parse_error:
        report["error"] = parse_error
        return report

    report["servers"] = [{"name": name, "status": "ok", "issues": []} for name in sorted(server_map.keys())]
    report["augurServers"] = [server for server in report["servers"] if _is_augur_server_name(server["name"])]

    if report["exists"] and not any(_is_augur_server_name(name) for name in server_map):
        report["error"] = "Augur MCP not configured."
    elif not report["exists"]:
        report["error"] = "Config file not found."

    return report


def _normalize_path(path: Path) -> Path:
    """Return a best-effort normalized path without failing on missing targets."""
    try:
        return path.expanduser().resolve(strict=False)
    except OSError:
        return path.expanduser()


def _is_augur_checkout(path: Path) -> bool:
    """True when the path is an existing Augur checkout or worktree."""
    root = _normalize_path(path)
    return root.exists() and (root / "project.yaml").exists()


def _extract_augur_root_candidates(server_config: Any) -> set[Path]:
    """Collect explicit Augur root hints from a client MCP server config."""
    if not isinstance(server_config, dict):
        return set()

    candidates: set[Path] = set()

    cwd = server_config.get("cwd")
    if isinstance(cwd, str) and cwd.strip():
        candidates.add(_normalize_path(Path(cwd.strip())))

    env = server_config.get("env")
    if isinstance(env, dict):
        for env_key in ("AUGUR_ROOT", "AUGUR_CORE"):
            env_path = env.get(env_key)
            if isinstance(env_path, str) and env_path.strip():
                candidates.add(_normalize_path(Path(env_path.strip())))

        pythonpath = env.get("PYTHONPATH")
        if isinstance(pythonpath, str):
            for raw_part in pythonpath.split(os.pathsep):
                part = raw_part.strip()
                if not part:
                    continue
                candidate = _normalize_path(Path(part))
                if candidate.name == "mcp" and candidate.parent.name == "src":
                    candidates.add(candidate.parent.parent)
                    continue
                candidates.add(candidate)

    return candidates


def _has_stale_augur_config(
    *,
    config_path: Path,
    config_format: str,
    server_key: str,
    config_structure: str,
    project_root: Path,
) -> bool:
    """Detect truly stale Augur config paths without flagging valid worktrees."""
    server_map, parse_error = read_server_map(
        config_path,
        config_format=config_format,
        server_key=server_key,
        config_structure=config_structure,
        project_root=project_root,
    )
    if parse_error:
        return False

    normalized_project_root = _normalize_path(project_root)

    for server_name, augur_config in server_map.items():
        if not _is_augur_server_name(str(server_name)):
            continue

        candidate_roots = _extract_augur_root_candidates(augur_config)
        if not candidate_roots:
            continue

        if normalized_project_root in candidate_roots:
            continue

        if not any(_is_augur_checkout(root) for root in candidate_roots):
            return True

    return False


def collect_mcp_config_issues(
    *,
    project_root: Path,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Return client reports plus actionable config issues for MCP clients."""
    project_root = project_root.resolve()
    config_catalog_path = get_config_dir() / "agents" / "ide_mcp_configs.yaml"
    config_catalog = yaml.safe_load(config_catalog_path.read_text(encoding="utf-8")) or {}
    ides = config_catalog.get("ides", {}) if isinstance(config_catalog, dict) else {}

    client_specs = {
        "claudeDesktop": {
            "label": "Claude Desktop",
            "config_path": (ides.get("claude_desktop", {}) or {}).get("config_path"),
            "config_format": "json",
            "server_key": "mcpServers",
            "config_structure": "flat",
        },
        "cursor": {
            "label": "Cursor",
            "config_path": (ides.get("cursor", {}) or {}).get("config_path"),
            "config_format": "json",
            "server_key": "mcpServers",
            "config_structure": "flat",
        },
        "claudeCode": {
            "label": "Claude Code",
            "config_path": (ides.get("claude_code", {}) or {}).get("config_path"),
            "config_format": "json",
            "server_key": "mcpServers",
            "config_structure": "per_project",
        },
        "codex": {
            "label": "Codex",
            "config_path": (ides.get("codex_cli", {}) or {}).get("config_path"),
            "config_format": "toml",
            "server_key": "mcp_servers",
            "config_structure": "flat",
        },
        "opencode": {
            "label": "OpenCode",
            "config_path": (ides.get("opencode", {}) or {}).get("config_path"),
            "config_format": "json",
            "server_key": "mcp",
            "config_structure": "flat",
        },
        "antigravity": {
            "label": "Antigravity",
            "config_path": (ides.get("antigravity", {}) or {}).get("config_path"),
            "config_format": "json",
            "server_key": "mcpServers",
            "config_structure": "flat",
        },
        "gemini": {
            "label": "Gemini",
            "config_path": (ides.get("gemini", {}) or {}).get("config_path"),
            "config_format": "json",
            "server_key": "mcpServers",
            "config_structure": "flat",
        },
    }

    reports: dict[str, Any] = {}
    issues: list[dict[str, str]] = []

    for path_issue in scan_global_mcp_config_references(
        project_root=project_root,
        config_catalog_path=config_catalog_path,
    ):
        issues.append(path_issue.as_dict())

    for client_key, spec in client_specs.items():
        raw_path = platform_config_path(spec["config_path"], project_root)
        if not raw_path.strip():
            continue
        config_path = Path(raw_path).expanduser()
        report = build_client_report(
            client_key,
            config_path=config_path,
            config_format=spec["config_format"],
            server_key=spec["server_key"],
            config_structure=spec["config_structure"],
            project_root=project_root,
        )
        reports[client_key] = report

        parse_error = report.get("error")
        if report["exists"] and isinstance(parse_error, str) and parse_error.startswith("Failed to parse config:"):
            issues.append(
                {
                    "kind": "parse_error",
                    "clientKey": client_key,
                    "clientLabel": spec["label"],
                    "configPath": str(config_path),
                    "error": parse_error,
                }
            )

    return reports, issues


def count_api_routes(project_root: Path) -> dict[str, Any]:
    """Return a lightweight API route count for the browse stats widget."""
    api_root = project_root / "apps" / "dashboard" / "app" / "api"
    route_files = list(api_root.rglob("route.ts")) if api_root.exists() else []
    total = len(route_files)
    return {
        "stats": {
            "total": total,
            "byStatus": {
                "migrated": total,
                "legacy": 0,
            },
        }
    }


def build_mcp_diagnostics_summary(
    *,
    include_processes: bool,
    include_configs: bool,
    project_root: Path,
) -> dict[str, Any]:
    """Build the MCP summary payload expected by dashboard clients."""
    project_root = project_root.resolve()
    diagnostics: dict[str, Any] = {
        "generatedAt": datetime.now().isoformat(),
        "dataDir": str(project_root),
        "migrationInProgress": False,
        "staleMcpConfig": False,
        "clients": {},
        "runtime": {
            "candidate": {
                "client": "dashboard",
                "name": "Augur MCP",
            },
            "transport": {
                "transport": "stdio",
                "host": "127.0.0.1",
                "port": 0,
            },
            "processMatches": [],
            "portOpen": False,
        },
    }

    if include_configs:
        reports, issues = collect_mcp_config_issues(project_root=project_root)
        diagnostics["clients"] = reports
        diagnostics["configIssues"] = issues
        diagnostics["staleMcpConfig"] = any(
            issue["kind"] in {"linked_worktree", "missing_path", "stale"} for issue in issues
        )

    if include_processes:
        try:
            result = subprocess_run(  # nosec B603
                ["ps", "-ax", "-o", "pid=,command="],
                capture_output=True,
                text=True,
                timeout=2,
            )
            processes = []
            for line in result.stdout.splitlines():
                lowered = line.lower()
                if not any(
                    marker in lowered
                    for marker in (
                        "-m augur_framework",
                        "-m augur_core",
                        "mcp_health_monitor.py",
                        "augur_mcp",
                        "augur-mcp",
                    )
                ):
                    continue
                parts = line.strip().split(None, 1)
                if len(parts) < 2:
                    continue
                try:
                    pid = int(parts[0])
                except ValueError:
                    continue
                processes.append({"pid": pid, "command": parts[1][:240]})
            diagnostics["runtime"]["processMatches"] = processes[:10]
            diagnostics["runtime"]["portOpen"] = len(processes) > 0
        except Exception:
            diagnostics["runtime"]["processMatches"] = []
            diagnostics["runtime"]["portOpen"] = False

    return diagnostics
