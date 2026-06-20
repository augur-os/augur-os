#!/usr/bin/env python3
# TODO_CLEANUP: This file is 856 lines — consider splitting into smaller modules
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
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


CORE_CHECKS = (
    "prerequisites_installed",
    "codex_installed",
    "codex_authenticated",
    "repo_ready",
    "dependencies_ready",
    "vault_ready",
    "mcp_configured",
    "indexes_built",
    "daemon_registered",
    "dashboard_verified",
    "onboard_status_clean",
)

MCP_TOOL_LOAD_FAILURE_MARKERS = (
    "Failed to load MCP tools",
    "[MCPBridge] Server error:",
    "[MCPBridge] Process error:",
)

VAULT_STARTER_DIRS = (
    "archive",
    "config",
    "drafts",
    "memory",
    "notes",
    "skills",
    "wiki",
)


def bootstrap_state_path() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "Augur" / "setup" / "bootstrap-state.json"
    return Path.home() / "AppData" / "Local" / "Augur" / "setup" / "bootstrap-state.json"


def read_bootstrap_state(state_path: Path | None = None) -> dict[str, Any]:
    path = state_path or bootstrap_state_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"state_read_error": f"invalid bootstrap state JSON: {path}"}


def write_bootstrap_state(payload: dict[str, Any], state_path: Path | None = None) -> None:
    path = state_path or bootstrap_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def classify_readiness(checks: dict[str, Any]) -> dict[str, str]:
    normalized = {key: bool(checks.get(key)) for key in CORE_CHECKS}
    if normalized["codex_installed"] and not normalized["codex_authenticated"]:
        return {
            "state": "Needs sign-in",
            "summary": "Codex is installed but not authenticated.",
            "next_action": (
                "Run codex login, complete OpenAI sign-in, then rerun the Windows one-click setup."
            ),
        }

    missing = [key for key in CORE_CHECKS if not normalized[key]]
    if not missing:
        return {
            "state": "Ready",
            "summary": (
                "Augur is installed, vault is connected, indexes are built, "
                "Codex is connected, daemon is running, dashboard verified."
            ),
            "next_action": "Open a fresh Codex session in the Augur repo and run /commands.",
        }

    return {
        "state": "Blocked",
        "summary": f"Augur setup is incomplete: {', '.join(missing)}.",
        "next_action": "Open the setup log and fix the first failed check before rerunning setup.",
    }


def _ensure_sys_path(path: Path) -> None:
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)


def _pythonpath_with_shared_vault(repo_root: Path) -> str:
    """Return PYTHONPATH with canonical Augur paths first."""
    root_text = str(repo_root)
    shared_text = str(repo_root / "project-brain")
    mcp_text = str(repo_root / "src" / "mcp")

    def is_stale_augur_entry(entry: str) -> bool:
        if not entry:
            return True
        try:
            path = Path(entry).expanduser().resolve()
        except (OSError, RuntimeError):
            return False
        current = {
            (repo_root / "project-brain").resolve(),
            repo_root.resolve(),
            (repo_root / "src" / "mcp").resolve(),
        }
        if path in current:
            return True
        if len(path.parts) >= 2 and path.parts[-2:] == ("src", "mcp"):
            return True
        if path.name == "project-brain":
            return True
        if path.name == "Augur":
            return True
        return False

    existing = [
        entry
        for entry in os.environ.get("PYTHONPATH", "").split(os.pathsep)
        if not is_stale_augur_entry(entry)
    ]
    return os.pathsep.join([shared_text, root_text, mcp_text, *existing])


def _ensure_shared_vault_sys_path(repo_root: Path) -> None:
    """Ensure project-brain precedes repo root for final top-level skills imports."""
    root_text = str(repo_root)
    shared_text = str(repo_root / "project-brain")
    mcp_text = str(repo_root / "src" / "mcp")
    sys.path[:] = [entry for entry in sys.path if entry not in {shared_text, root_text, mcp_text}]
    sys.path.insert(0, mcp_text)
    sys.path.insert(0, root_text)
    sys.path.insert(0, shared_text)


def run_checked(
    command: list[str],
    cwd: Path,
    timeout: int = 600,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=timeout,
        env=env,
        check=True,
    )


def run_dependencies(repo_root: Path) -> bool:
    repo_root = Path(repo_root)
    dashboard_dir = repo_root / "apps" / "dashboard"
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")

    run_checked(
        [
            "uv",
            "sync",
            "--group",
            "dev",
            "--extra",
            "windows",
            "--python",
            sys.executable,
        ],
        repo_root,
        timeout=1800,
        env=env,
    )
    ensure_corepack_pnpm(dashboard_dir, env=env)
    run_checked(["corepack", "pnpm", "install"], dashboard_dir, timeout=1200, env=env)
    return True


def ensure_corepack_pnpm(cwd: Path, env: dict[str, str] | None = None) -> bool:
    """Enable pnpm shims when possible, but do not require admin rights on Windows."""
    try:
        run_checked(["corepack", "enable"], cwd, timeout=300, env=env)
    except (subprocess.CalledProcessError, FileNotFoundError):
        run_checked(["corepack", "pnpm", "--version"], cwd, timeout=120, env=env)
    return True


def _env_flag(name: str) -> bool:
    return (os.environ.get(name) or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _expand_user_path(raw: str | os.PathLike[str], base: Path | None = None) -> Path:
    path = Path(os.path.expandvars(os.path.expanduser(str(raw))))
    if not path.is_absolute() and base is not None:
        path = Path(base) / path
    return path.resolve()


def _parse_simple_yaml_scalar(raw: str) -> Any:
    value = raw.strip()
    if value in {"''", '""'}:
        return ""
    if (value.startswith("'") and value.endswith("'")) or (
        value.startswith('"') and value.endswith('"')
    ):
        return value[1:-1]
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    try:
        return int(value)
    except ValueError:
        return value


def _read_simple_yaml_file(path: Path) -> dict[str, Any]:
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        key, separator, raw_value = line.strip().partition(":")
        if not separator or not key:
            continue
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1] if stack else root
        value = raw_value.strip()
        if value:
            parent[key] = _parse_simple_yaml_scalar(value)
            continue
        child: dict[str, Any] = {}
        parent[key] = child
        stack.append((indent, child))
    return root


def _format_simple_yaml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    text = "" if value is None else str(value)
    if not text:
        return "''"
    if any(ch in text for ch in [":", "#", "{", "}", "[", "]"]) or text.strip() != text:
        return json.dumps(text)
    return text


def _dump_simple_yaml_lines(data: dict[str, Any], indent: int = 0) -> list[str]:
    lines: list[str] = []
    prefix = " " * indent
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            lines.extend(_dump_simple_yaml_lines(value, indent + 2))
        else:
            lines.append(f"{prefix}{key}: {_format_simple_yaml_scalar(value)}")
    return lines


def _read_yaml_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        import yaml
    except ImportError:
        return _read_simple_yaml_file(path)

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def _write_yaml_file(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import yaml
    except ImportError:
        path.write_text("\n".join(_dump_simple_yaml_lines(data)) + "\n", encoding="utf-8")
    else:
        path.write_text(
            yaml.safe_dump(data, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )


def configured_vault_dir(repo_root: Path, override: str | None = None) -> Path:
    repo_root = Path(repo_root)
    if override:
        return _expand_user_path(override, base=repo_root)
    env_vault = os.environ.get("AUGUR_VAULT")
    if env_vault:
        return _expand_user_path(env_vault)

    project_yaml = _read_yaml_file(Path(repo_root) / "project.yaml")
    paths_block = project_yaml.get("paths")
    if isinstance(paths_block, dict):
        vault_path = paths_block.get("vault")
        if isinstance(vault_path, str) and vault_path.strip():
            return _expand_user_path(vault_path, base=repo_root)

    return Path.home() / "Projects" / "Au-vault"


def _set_git_origin(repo_dir: Path, remote_url: str) -> None:
    existing = subprocess.run(
        ["git", "-C", str(repo_dir), "remote", "get-url", "origin"],
        text=True,
        capture_output=True,
        check=False,
    )
    if existing.returncode == 0:
        run_checked(["git", "-C", str(repo_dir), "remote", "set-url", "origin", remote_url], repo_dir)
    else:
        run_checked(["git", "-C", str(repo_dir), "remote", "add", "origin", remote_url], repo_dir)


def update_vault_configuration(
    repo_root: Path,
    vault_dir: Path,
    vault_repo: str | None = None,
) -> None:
    """Persist the vault path/remote for first-run recovery checks."""
    repo_root = Path(repo_root)

    project_yaml_path = repo_root / "project.yaml"
    project_yaml = _read_yaml_file(project_yaml_path)
    paths_block = project_yaml.setdefault("paths", {})
    if isinstance(paths_block, dict):
        paths_block["vault"] = str(vault_dir)
    _write_yaml_file(project_yaml_path, project_yaml)

    vault_yaml_path = repo_root / "config" / "system" / "vault.yaml"
    vault_yaml = _read_yaml_file(vault_yaml_path)
    vault_block = vault_yaml.setdefault("vault", {})
    if isinstance(vault_block, dict):
        vault_block["path"] = str(vault_dir)
        if vault_repo:
            vault_block["remote"] = vault_repo
    _write_yaml_file(vault_yaml_path, vault_yaml)


def _create_vault_skeleton(vault_dir: Path) -> None:
    vault_dir.mkdir(parents=True, exist_ok=True)
    for name in VAULT_STARTER_DIRS:
        (vault_dir / name).mkdir(parents=True, exist_ok=True)
    marker = vault_dir / ".augur-vault"
    if not marker.exists():
        marker.write_text("project: Augur\n", encoding="utf-8")


def _directory_has_user_content(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        return any(path.iterdir())
    except OSError:
        return True


def _initialize_local_vault(vault_dir: Path, vault_repo: str | None = None) -> dict[str, Any]:
    _create_vault_skeleton(vault_dir)
    if not (vault_dir / ".git").exists():
        try:
            run_checked(["git", "-C", str(vault_dir), "init", "-b", "main"], vault_dir)
        except subprocess.CalledProcessError:
            run_checked(["git", "-C", str(vault_dir), "init"], vault_dir)
            run_checked(["git", "-C", str(vault_dir), "checkout", "-B", "main"], vault_dir)
    if vault_repo:
        _set_git_origin(vault_dir, vault_repo)
    return {
        "ok": True,
        "detail": f"local vault git repo initialized at {vault_dir}",
        "path": str(vault_dir),
    }


def _clone_vault_repo(vault_dir: Path, vault_repo: str) -> dict[str, Any]:
    vault_dir.parent.mkdir(parents=True, exist_ok=True)
    run_checked(["git", "clone", vault_repo, str(vault_dir)], vault_dir.parent, timeout=1800)
    return {
        "ok": True,
        "detail": f"vault cloned from {vault_repo} to {vault_dir}",
        "path": str(vault_dir),
    }


def _prompt_for_vault_plan(vault_dir: Path) -> dict[str, str] | None:
    if not sys.stdin.isatty():
        return None

    print("")
    print(f"Vault is not configured as a git repo at: {vault_dir}")
    print("Choose vault setup:")
    print("  1. Clone an existing vault git repo")
    print("  2. Use/create a local vault folder and initialize git")
    print("  3. Skip for now")
    try:
        choice = input("Selection [1/2/3]: ").strip()
    except (EOFError, KeyboardInterrupt):
        return None

    if choice == "1":
        repo = input("Vault git repo URL: ").strip()
        target = input(f"Vault folder [{vault_dir}]: ").strip()
        return {"mode": "clone", "repo": repo, "dir": target or str(vault_dir)}
    if choice == "2":
        target = input(f"Vault folder [{vault_dir}]: ").strip()
        repo = input("Optional remote URL for this vault [blank for none]: ").strip()
        return {"mode": "init", "repo": repo, "dir": target or str(vault_dir)}
    return {"mode": "skip", "dir": str(vault_dir)}


def ensure_vault_ready(
    repo_root: Path,
    vault_repo: str | None = None,
    vault_dir_override: str | None = None,
    init_local_vault: bool = False,
    prompt_for_vault: bool = True,
) -> dict[str, Any]:
    repo_root = Path(repo_root)
    vault_repo = (vault_repo or "").strip() or None
    vault_dir = configured_vault_dir(repo_root, vault_dir_override)

    if (vault_dir / ".git").exists():
        if vault_repo:
            _set_git_origin(vault_dir, vault_repo)
            update_vault_configuration(repo_root, vault_dir, vault_repo)
        elif vault_dir_override:
            update_vault_configuration(repo_root, vault_dir)
        return {
            "ok": True,
            "detail": f"vault git repo present at {vault_dir}",
            "path": str(vault_dir),
        }

    if init_local_vault:
        result = _initialize_local_vault(vault_dir, vault_repo)
        if vault_repo or vault_dir_override:
            update_vault_configuration(repo_root, vault_dir, vault_repo)
        return result

    if vault_repo and not _directory_has_user_content(vault_dir):
        result = _clone_vault_repo(vault_dir, vault_repo)
        update_vault_configuration(repo_root, vault_dir, vault_repo)
        return result

    if prompt_for_vault:
        plan = _prompt_for_vault_plan(vault_dir)
        if plan:
            planned_dir = configured_vault_dir(repo_root, plan.get("dir") or str(vault_dir))
            planned_repo = (plan.get("repo") or "").strip() or None
            if plan["mode"] == "clone" and planned_repo:
                if _directory_has_user_content(planned_dir):
                    return {
                        "ok": False,
                        "detail": (
                            f"vault target is not empty and is not a git repo: {planned_dir}; "
                            "choose an empty folder or rerun with --init-local-vault to preserve it"
                        ),
                        "path": str(planned_dir),
                    }
                result = _clone_vault_repo(planned_dir, planned_repo)
                update_vault_configuration(repo_root, planned_dir, planned_repo)
                return result
            if plan["mode"] == "init":
                result = _initialize_local_vault(planned_dir, planned_repo)
                update_vault_configuration(repo_root, planned_dir, planned_repo)
                return result

    detail = (
        f"vault is missing or not a git repo at {vault_dir}. "
        "Rerun with --vault-repo <git-url> to clone an existing vault, "
        "or --init-local-vault to create/use a local vault folder."
    )
    if vault_repo and _directory_has_user_content(vault_dir):
        detail = (
            f"vault target is not empty and is not a git repo: {vault_dir}. "
            "Choose an empty --vault-dir for cloning, or rerun with --init-local-vault "
            "to preserve this folder and attach the remote."
        )
    return {"ok": False, "detail": detail, "path": str(vault_dir)}


def _project_python(repo_root: Path) -> Path:
    repo_root = Path(repo_root)
    candidates = (
        repo_root / ".venv" / "Scripts" / "python.exe",
        repo_root / ".venv" / "Scripts" / "python3.exe",
        repo_root / ".venv" / "bin" / "python3",
        repo_root / ".venv" / "bin" / "python",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return Path(sys.executable)


def run_indexes(repo_root: Path, vault_dir: Path | str | None = None) -> dict[str, Any]:
    repo_root = Path(repo_root)
    vault_path = Path(vault_dir) if vault_dir else configured_vault_dir(repo_root)
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env["AUGUR_VAULT"] = str(vault_path)

    indexer = repo_root / "src" / "lib" / "index" / "unified_indexer.py"
    result = run_checked(
        [
            str(_project_python(repo_root)),
            str(indexer),
            "--root",
            str(repo_root),
            "--vault-dir",
            str(vault_path),
        ],
        repo_root,
        timeout=1800,
        env=env,
    )
    output = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part and part.strip())
    detail = output.splitlines()[-1] if output else "unified indexer completed"
    return {"ok": True, "detail": detail, "path": str(vault_path)}


def sync_codex(repo_root: Path) -> bool:
    repo_root = Path(repo_root)
    env = os.environ.copy()
    env["PYTHONPATH"] = _pythonpath_with_shared_vault(repo_root)
    run_checked(
        [
            sys.executable,
            "-m",
            "skills.ai.scripts.sync_agents",
            "sync",
            "all",
            "codex",
        ],
        repo_root,
        timeout=600,
        env=env,
    )
    return True


def codex_runtime_config_issues(repo_root: Path) -> list[str]:
    repo_root = Path(repo_root)
    _ensure_shared_vault_sys_path(repo_root)
    from src.cli_config.codex_runtime import (
        codex_runtime_config_issues as collect_issues,
    )

    return collect_issues(project_root=repo_root)


def verify_codex(repo_root: Path) -> dict[str, Any]:
    issues = codex_runtime_config_issues(repo_root)
    if issues:
        return {"ok": False, "detail": "; ".join(issues)}
    return {"ok": True, "detail": "codex runtime config is current"}


def install_or_heal_daemon(repo_root: Path) -> bool:
    repo_root = Path(repo_root)
    healer_script = _resolve_daemon_skill_root(repo_root) / "scripts" / "service_healer.py"
    run_checked([sys.executable, str(healer_script), "install"], repo_root, timeout=300)
    run_checked([sys.executable, str(healer_script), "heal"], repo_root, timeout=300)
    return True


def _resolve_daemon_skill_root(repo_root: Path) -> Path:
    """Resolve the canonical migrated daemon skill root."""
    return repo_root / "project-brain" / "capabilities" / "skills" / "daemon"


def collect_windows_daemon_status(repo_root: Path) -> dict[str, str]:
    repo_root = Path(repo_root)
    _ensure_sys_path(repo_root)
    _ensure_sys_path(_resolve_daemon_skill_root(repo_root) / "scripts")
    import service_healer

    return service_healer._collect_windows_status_results(repo_root)


def verify_daemon(repo_root: Path) -> dict[str, Any]:
    status = collect_windows_daemon_status(repo_root)
    daemon_status = status.get("daemon")
    if daemon_status == "running":
        return {"ok": True, "detail": f"daemon={daemon_status}"}
    return {"ok": False, "detail": f"daemon={daemon_status or 'missing'}"}


def verify_dashboard(repo_root: Path) -> dict[str, Any]:
    dashboard_dir = Path(repo_root) / "apps" / "dashboard"
    try:
        run_checked(
            ["corepack", "pnpm", "run", "prebuild"],
            cwd=dashboard_dir,
            timeout=600,
        )
        smoke = run_checked(
            [
                "corepack",
                "pnpm",
                "exec",
                "playwright",
                "test",
                "windows-onboarding-smoke.spec.ts",
                "--config",
                "playwright.windows-onboarding.config.ts",
                "--project=chromium",
                "--reporter=line",
            ],
            cwd=dashboard_dir,
            timeout=180,
        )
    except (
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        FileNotFoundError,
    ) as exc:
        return {"ok": False, "detail": _command_error_detail(exc)}
    mcp_failure_detail = _mcp_tool_load_failure_detail(smoke)
    if mcp_failure_detail:
        return {"ok": False, "detail": mcp_failure_detail}
    return {"ok": True, "detail": "dashboard browser smoke passed"}


def _mcp_tool_load_failure_detail(result: subprocess.CompletedProcess[str]) -> str | None:
    output = "\n".join(
        part for part in (result.stdout or "", result.stderr or "") if part
    )
    for line in output.splitlines():
        if any(marker in line for marker in MCP_TOOL_LOAD_FAILURE_MARKERS):
            return f"dashboard MCP backend failure: {line.strip()}"
    return None


def is_codex_installed() -> bool:
    return shutil.which("codex") is not None


def is_codex_authenticated() -> bool:
    try:
        result = subprocess.run(
            ["codex", "login", "status"],
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    if result.returncode == 0:
        return True

    # Older Codex builds did not expose `codex login status`; keep a fallback
    # for those versions, but avoid it on current builds because it uses a model call.
    unsupported = f"{result.stdout}\n{result.stderr}".lower()
    if "unrecognized" not in unsupported and "unknown" not in unsupported:
        return False

    try:
        fallback = subprocess.run(
            ["codex", "exec", "Respond exactly with AUGUR_AUTH_OK."],
            text=True,
            capture_output=True,
            timeout=120,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    return fallback.returncode == 0


def verify_onboard_status(checks: dict[str, Any]) -> dict[str, Any]:
    candidate = dict(checks)
    candidate["onboard_status_clean"] = True
    report = classify_readiness(candidate)
    if report["state"] == "Ready":
        return {"ok": True, "detail": report["summary"]}
    return {"ok": False, "detail": report["summary"]}


def _command_error_detail(
    exc: subprocess.CalledProcessError | subprocess.TimeoutExpired | FileNotFoundError,
) -> str:
    if isinstance(exc, subprocess.CalledProcessError):
        parts = [
            str(exc.stderr or "").strip(),
            str(exc.output or "").strip(),
            str(exc),
        ]
        return " ".join(part for part in parts if part)
    if isinstance(exc, subprocess.TimeoutExpired):
        command = " ".join(str(part) for part in exc.cmd)
        return f"command timed out after {exc.timeout} seconds: {command}"
    return str(exc)


def _blocked_report(checks: dict[str, Any], detail: str | None = None) -> dict[str, Any]:
    write_bootstrap_state(checks)
    missing = [key for key in CORE_CHECKS if not checks.get(key)]
    report: dict[str, Any] = {
        "state": "Blocked",
        "summary": f"Augur setup is incomplete: {', '.join(missing)}.",
        "next_action": "Open the setup log and fix the first failed check before rerunning setup.",
        "checks": checks,
    }
    if detail:
        report["detail"] = detail
    return report


def _step_failure_report(
    checks: dict[str, Any],
    step: str,
    exc: subprocess.CalledProcessError | subprocess.TimeoutExpired | FileNotFoundError,
) -> dict[str, Any]:
    return _blocked_report(checks, f"{step} failed: {_command_error_detail(exc)}")


def run_setup(
    repo_root: Path,
    vault_repo: str | None = None,
    vault_dir: str | None = None,
    init_local_vault: bool = False,
    prompt_for_vault: bool = True,
) -> dict[str, Any]:
    repo_root = Path(repo_root)
    checks = {key: False for key in CORE_CHECKS}
    checks["prerequisites_installed"] = True
    checks["codex_installed"] = is_codex_installed()
    checks["repo_ready"] = (repo_root / "project.yaml").exists()

    if not checks["repo_ready"]:
        return _blocked_report(
            checks,
            f"missing project.yaml at {repo_root / 'project.yaml'}",
        )

    checks["codex_authenticated"] = is_codex_authenticated()

    if not checks["codex_authenticated"]:
        report = classify_readiness(checks)
        report["checks"] = checks
        return report

    expected_errors = (
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        FileNotFoundError,
    )

    try:
        checks["dependencies_ready"] = run_dependencies(repo_root)
    except expected_errors as exc:
        return _step_failure_report(checks, "dependency setup", exc)

    try:
        vault_report = ensure_vault_ready(
            repo_root,
            vault_repo=vault_repo,
            vault_dir_override=vault_dir,
            init_local_vault=init_local_vault,
            prompt_for_vault=prompt_for_vault,
        )
    except expected_errors as exc:
        return _step_failure_report(checks, "vault setup", exc)

    checks["vault_ready"] = bool(vault_report["ok"])
    if not checks["vault_ready"]:
        return _blocked_report(
            checks,
            f"vault setup required: {vault_report['detail']}",
        )

    try:
        sync_codex(repo_root)
    except expected_errors as exc:
        return _step_failure_report(checks, "Codex sync", exc)

    try:
        codex_report = verify_codex(repo_root)
    except expected_errors as exc:
        return _step_failure_report(checks, "Codex verification", exc)

    checks["mcp_configured"] = bool(codex_report["ok"])
    if not checks["mcp_configured"]:
        return _blocked_report(
            checks,
            f"Codex verification failed: {codex_report['detail']}",
        )

    try:
        index_report = run_indexes(repo_root, vault_report.get("path"))
    except expected_errors as exc:
        return _step_failure_report(checks, "index rebuild", exc)

    checks["indexes_built"] = bool(index_report["ok"])
    if not checks["indexes_built"]:
        return _blocked_report(
            checks,
            f"index rebuild failed: {index_report['detail']}",
        )

    try:
        install_or_heal_daemon(repo_root)
    except expected_errors as exc:
        return _step_failure_report(checks, "daemon setup", exc)

    try:
        daemon_report = verify_daemon(repo_root)
    except expected_errors as exc:
        return _step_failure_report(checks, "daemon verification", exc)

    checks["daemon_registered"] = bool(daemon_report["ok"])
    if not checks["daemon_registered"]:
        return _blocked_report(
            checks,
            f"daemon verification failed: {daemon_report['detail']}",
        )

    dashboard_report = verify_dashboard(repo_root)
    checks["dashboard_verified"] = bool(dashboard_report["ok"])
    if not checks["dashboard_verified"]:
        return _blocked_report(
            checks,
            f"dashboard verification failed: {dashboard_report['detail']}",
        )

    checks["onboard_status_clean"] = verify_onboard_status(checks)["ok"]

    write_bootstrap_state(checks)
    report = classify_readiness(checks)
    report["checks"] = checks
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inspect Windows one-click onboarding readiness."
    )
    parser.add_argument("--status", action="store_true", help="print readiness status")
    parser.add_argument("--run", action="store_true", help="run Windows one-click setup")
    parser.add_argument("--repo-root", default=".", help="Augur repository root")
    parser.add_argument(
        "--vault-repo",
        default=os.environ.get("AUGUR_VAULT_REPO", ""),
        help="git URL for an existing private vault repo",
    )
    parser.add_argument(
        "--vault-dir",
        default=os.environ.get("AUGUR_VAULT", ""),
        help="local vault directory override",
    )
    parser.add_argument(
        "--init-local-vault",
        action="store_true",
        default=_env_flag("AUGUR_INIT_LOCAL_VAULT"),
        help="initialize/use the local vault folder as a git repo when no vault repo is cloned",
    )
    parser.add_argument(
        "--no-vault-prompt",
        action="store_true",
        help="fail with instructions instead of prompting for first-run vault setup",
    )
    args = parser.parse_args()

    if args.status:
        state = read_bootstrap_state()
        checks = {key: bool(state.get(key)) for key in CORE_CHECKS}
        print(json.dumps(classify_readiness(checks), indent=2, sort_keys=True))
        return 0

    if args.run:
        report = run_setup(
            Path(args.repo_root).resolve(),
            vault_repo=args.vault_repo,
            vault_dir=args.vault_dir,
            init_local_vault=args.init_local_vault,
            prompt_for_vault=not args.no_vault_prompt,
        )
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["state"] == "Ready" else 1

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
