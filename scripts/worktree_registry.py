#!/usr/bin/env python3
"""
Worktree Registry - Port allocation and tracking for git worktrees

Manages dynamic port allocation for parallel worktree development.
Each worktree gets unique ports to avoid collisions with the main repo.

Usage:
    worktree_registry.py register --path PATH --name NAME
    worktree_registry.py register --from-hook  (auto-detect from env vars)
    worktree_registry.py unregister --path PATH
    worktree_registry.py list
    worktree_registry.py get-port --path PATH

Registry file: state/worktree_registry.yaml
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config.paths import get_runtime_dir  # noqa: E402

RUNTIME_DIR = get_runtime_dir()
REGISTRY_FILE = RUNTIME_DIR / "worktree_registry.yaml"

DASHBOARD_PORT_RANGE = (3001, 3010)
MCP_PORT_OFFSET = 5080
MAX_WORKTREES = 10


def _ensure_runtime_dir() -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        import yaml

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if data and "worktrees" in data:
                return data["worktrees"]
            return data if data else {}
    except ImportError:
        content = path.read_text(encoding="utf-8")
        if not content.strip():
            return {}
        lines = content.split("\n")
        result: dict[str, Any] = {}
        current_key = None
        current_block: list[str] = []
        in_worktrees = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("worktrees:"):
                in_worktrees = True
                continue
            if not in_worktrees:
                continue
            if stripped.startswith("#") or not stripped:
                continue
            if line.startswith("  /") or (
                line.startswith("  ")
                and ":" in stripped
                and not stripped.startswith(" ")
            ):
                if current_key and current_block:
                    result[current_key] = _parse_yaml_block(current_block)
                current_key = stripped.rstrip(":")
                current_block = []
            elif line.startswith("    "):
                current_block.append(stripped)
        if current_key and current_block:
            result[current_key] = _parse_yaml_block(current_block)
        return result
    except Exception:
        return {}


def _parse_yaml_block(lines: list[str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for line in lines:
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            elif value.isdigit():
                value = int(value)
            elif value == "true":
                value = True
            elif value == "false":
                value = False
            result[key] = value
    return result


def _save_yaml(path: Path, data: dict[str, Any]) -> None:
    try:
        import yaml

        content = {"worktrees": data}
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(content, f, default_flow_style=False, sort_keys=False)
    except ImportError:
        lines = ["# Auto-managed by worktree_registry.py", "worktrees:"]
        for wt_path, info in data.items():
            lines.append(f"  {wt_path}:")
            for key, value in info.items():
                if isinstance(value, str):
                    lines.append(f'    {key}: "{value}"')
                elif isinstance(value, bool):
                    lines.append(f"    {key}: {str(value).lower()}")
                else:
                    lines.append(f"    {key}: {value}")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_worktree_registry() -> dict[str, Any]:
    _ensure_runtime_dir()
    return _load_yaml(REGISTRY_FILE)


def save_worktree_registry(registry: dict[str, Any]) -> None:
    _ensure_runtime_dir()
    _save_yaml(REGISTRY_FILE, registry)


def prune_dead_entries() -> dict[str, Any]:
    """Remove registry entries whose worktree directories no longer exist."""
    registry = load_worktree_registry()
    pruned = []
    for wt_path in list(registry.keys()):
        if not Path(wt_path).is_dir():
            pruned.append(wt_path)
            del registry[wt_path]
    if pruned:
        save_worktree_registry(registry)
    return {"pruned": pruned, "pruned_count": len(pruned), "remaining": len(registry)}


def allocate_worktree_port(worktree_path: str) -> dict[str, int]:
    registry = load_worktree_registry()
    used_ports = {
        w.get("dashboard_port") for w in registry.values() if w.get("dashboard_port")
    }

    start_port, end_port = DASHBOARD_PORT_RANGE
    for port in range(start_port, end_port + 1):
        if port not in used_ports:
            return {
                "dashboard_port": port,
                "mcp_port": port + MCP_PORT_OFFSET,
            }
    raise RuntimeError(f"No available worktree ports (max {MAX_WORKTREES})")


def get_worktree_branch(worktree_path: str) -> str:
    """Resolve the branch checked out *at* worktree_path.

    Every git worktree shares one object store but keeps its own HEAD, so the
    branch must be read from inside the target worktree via `git -C`. Reading
    it from the calling process's cwd records the caller's branch instead —
    the bug that let one session register another session's worktree under the
    wrong branch (see docs/architecture-overview.md, Worktree Registry).
    """
    try:
        result = subprocess.run(
            ["git", "-C", worktree_path, "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def is_main_working_tree(path: str) -> bool:
    """True if `path` is a repository's main working tree (not a linked worktree).

    The main checkout must never hold a worktree-registry entry: it uses the
    default dashboard port, and a registry row for the main repo path moves the
    main instance off that port (breaking `aug dev build`'s scoped restart and
    readiness poll). A linked worktree's git dir lives under
    `<main>/.git/worktrees/<name>` while its common dir is `<main>/.git`; for the
    main working tree the two resolve to the same path. Non-git paths return
    False (registration is governed by other validation).
    """
    try:
        git_dir = subprocess.run(
            ["git", "-C", path, "rev-parse", "--absolute-git-dir"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
        common_raw = subprocess.run(
            ["git", "-C", path, "rev-parse", "--git-common-dir"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
    except Exception:
        return False
    if not git_dir or not common_raw:
        return False
    common = Path(common_raw)
    if not common.is_absolute():
        common = Path(path) / common
    try:
        return Path(git_dir).resolve() == common.resolve()
    except Exception:
        return False


def cmd_prune() -> dict[str, Any]:
    result = prune_dead_entries()
    return {"success": True, **result}


def cmd_register(path: str, name: str) -> dict[str, Any]:
    prune_dead_entries()

    registry = load_worktree_registry()

    abs_path = str(Path(path).resolve())

    # Never register the main checkout. The `--from-hook` path defaults to
    # os.getcwd(), so a session hook firing in the main repo (no
    # CLAUDE_WORKTREE_PATH) would otherwise register main as a worktree and
    # allocate it a non-default port — the source of the `aug dev build`
    # false-ok:false / orphaned-server bug.
    if is_main_working_tree(abs_path):
        return {
            "success": False,
            "error": (
                "refusing to register the main checkout as a worktree; the main "
                "dashboard instance uses the default port and must not hold a "
                "worktree-registry entry"
            ),
            "path": abs_path,
        }

    if abs_path in registry:
        return {
            "success": True,
            "already_registered": True,
            "worktree": registry[abs_path],
        }

    try:
        ports = allocate_worktree_port(abs_path)
    except RuntimeError as e:
        return {"success": False, "error": str(e)}

    entry = {
        "name": name,
        "dashboard_port": ports["dashboard_port"],
        "mcp_port": ports["mcp_port"],
        "branch": get_worktree_branch(abs_path),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "status": "active",
    }

    registry[abs_path] = entry
    save_worktree_registry(registry)

    return {
        "success": True,
        "path": abs_path,
        **entry,
    }


def cmd_unregister(path: str) -> dict[str, Any]:
    registry = load_worktree_registry()

    abs_path = str(Path(path).resolve())

    if abs_path not in registry:
        return {
            "success": False,
            "error": f"Worktree not registered: {abs_path}",
        }

    entry = registry.pop(abs_path)
    save_worktree_registry(registry)

    return {
        "success": True,
        "path": abs_path,
        "freed_ports": {
            "dashboard_port": entry.get("dashboard_port"),
            "mcp_port": entry.get("mcp_port"),
        },
    }


def cmd_list() -> dict[str, Any]:
    registry = load_worktree_registry()

    worktrees = []
    for wt_path, info in registry.items():
        worktrees.append(
            {
                "path": wt_path,
                **info,
            }
        )

    start_port, end_port = DASHBOARD_PORT_RANGE
    used_count = len(registry)

    return {
        "success": True,
        "count": used_count,
        "max": MAX_WORKTREES,
        "available": MAX_WORKTREES - used_count,
        "port_range": {
            "dashboard": f"{start_port}-{end_port}",
            "mcp": f"{start_port + MCP_PORT_OFFSET}-{end_port + MCP_PORT_OFFSET}",
        },
        "worktrees": worktrees,
    }


def cmd_get_port(path: str) -> dict[str, Any]:
    registry = load_worktree_registry()

    abs_path = str(Path(path).resolve())

    if abs_path not in registry:
        return {
            "success": False,
            "error": f"Worktree not registered: {abs_path}",
        }

    entry = registry[abs_path]

    return {
        "success": True,
        "path": abs_path,
        "dashboard_port": entry.get("dashboard_port"),
        "mcp_port": entry.get("mcp_port"),
    }


def main() -> None:
    if len(sys.argv) < 2:
        print(
            json.dumps(
                {
                    "success": False,
                    "error": "No command specified",
                    "usage": "worktree_registry.py {register|unregister|list|get-port|prune} [options]",
                }
            )
        )
        sys.exit(1)

    command = sys.argv[1]

    if command == "list":
        result = cmd_list()
    elif command == "prune":
        result = cmd_prune()
    elif command == "register":
        from_hook = "--from-hook" in sys.argv
        if from_hook:
            # Auto-detect from environment variables set by Claude Code hooks
            path = os.environ.get("CLAUDE_WORKTREE_PATH") or os.getcwd()
            name = os.environ.get("CLAUDE_WORKTREE_NAME") or Path(path).name
            result = cmd_register(path, name)
        elif len(sys.argv) < 5:
            result = {
                "success": False,
                "error": "register requires --path PATH --name NAME (or --from-hook)",
            }
        else:
            path = None
            name = None
            i = 2
            while i < len(sys.argv):
                if sys.argv[i] == "--path" and i + 1 < len(sys.argv):
                    path = sys.argv[i + 1]
                    i += 2
                elif sys.argv[i] == "--name" and i + 1 < len(sys.argv):
                    name = sys.argv[i + 1]
                    i += 2
                else:
                    i += 1

            if not path or not name:
                result = {
                    "success": False,
                    "error": "register requires --path PATH --name NAME (or --from-hook)",
                }
            else:
                result = cmd_register(path, name)
    elif command == "unregister":
        if len(sys.argv) < 4 or sys.argv[2] != "--path":
            result = {
                "success": False,
                "error": "unregister requires --path PATH",
            }
        else:
            result = cmd_unregister(sys.argv[3])
    elif command == "get-port":
        if len(sys.argv) < 4 or sys.argv[2] != "--path":
            result = {
                "success": False,
                "error": "get-port requires --path PATH",
            }
        else:
            result = cmd_get_port(sys.argv[3])
    else:
        result = {
            "success": False,
            "error": f"Unknown command: {command}",
            "valid_commands": ["register", "unregister", "list", "get-port", "prune"],
        }

    print(json.dumps(result, indent=2))

    if not result.get("success", True):
        sys.exit(1)


if __name__ == "__main__":
    main()
