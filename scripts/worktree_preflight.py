#!/usr/bin/env python3
"""Shared bootstrap + verify contract for worktree/runtime startup."""

from __future__ import annotations

import argparse
import copy
import importlib.util
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


DEFAULT_DASHBOARD_PORT = 3000
DEFAULT_MCP_PORT = 8080
WORKTREE_SYNC_BOOTSTRAP_CODE = (
    "from skills.ai.scripts.sync_agents.engine import sync_all; "
    "raise SystemExit(sync_all(do_vaults=False))"
)
WORKTREE_SYNC_FLAGS = {
    "do_rules": True,
    "do_subagents": True,
    "do_memory": True,
    "do_plugins": True,
    "do_skill_exports": True,
    "do_prompt_exports": True,
    "do_command_exports": True,
}
OPTIONAL_REPO_LOCAL_SYNC_OUTPUTS = {
    ".codex/prompts",
    ".gemini/memory",
    ".gemini/topics",
    ".gemini/workflows",
    ".opencode/skills",
}
REQUIRED_SHARED_DEPENDENCY_PATHS = [".venv"]
OPTIONAL_SHARED_DEPENDENCY_PATHS = [".venv-test"]
PROFILE_REQUIREMENTS = {
    "worktree": {"runtime", "python", "ruff", "dashboard_deps", "sync_outputs"},
    "shell": {"runtime", "python", "main_checkout_branch"},
    "mcp": {"runtime", "python", "main_checkout_branch"},
    "dashboard": {"runtime", "python", "dashboard_deps", "main_checkout_branch"},
}
AUTO_FOCUS_HUBS = {
    "adaptive",
    "brain",
    "business",
    "career",
    "command",
    "life",
    "studio",
    "templates",
    "websites",
}
AUTO_FOCUS_PREFIXES = (
    ("apps/dashboard/app/api/brain/", "brain"),
    ("apps/dashboard/app/api/chat/", "brain"),
    ("apps/dashboard/components/chat/", "brain"),
    ("apps/dashboard/features/components/chat/", "brain"),
    ("apps/dashboard/features/components/FloatingChat", "brain"),
    ("apps/dashboard/features/components/PageActionButtons", "brain"),
    ("apps/dashboard/lib/chat/", "brain"),
)
AUTO_FOCUS_IGNORED_PREFIXES = (
    "docs/",
    "tests/",
)
AUTO_FOCUS_IGNORED_PATHS = {
    "apps/dashboard/scripts/start-dev.sh",
}


def _is_windows() -> bool:
    """Windows detection seam. Tests patch THIS (not the global os.name) so that
    simulating Windows never mutates os.name globally — mutating os.name makes
    pathlib.Path() construct WindowsPath, which raises on non-Windows runners and
    leaks into unrelated fixture teardowns under CI collection order."""
    return os.name == "nt"


def _add_project_root_to_sys_path(project_root: Path) -> None:
    for path in (project_root, project_root / "project-brain" / "capabilities"):
        if not path.exists():
            continue
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)


@dataclass
class Check:
    name: str
    ok: bool
    details: str


@dataclass
class Repair:
    type: str
    path: str
    target: str | None = None


@dataclass
class Incident:
    fingerprint: str
    severity: str
    message: str
    owner_path: str
    safe_to_repair: bool
    repaired: bool
    category: str = "bootstrap"


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _discover_repo_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        has_src = (candidate / "src").exists()
        has_config = (candidate / "config").exists()
        has_git = (candidate / ".git").exists()
        if has_src and has_config and has_git:
            return candidate
    raise FileNotFoundError(f"Could not discover repo root from {start}")


def _load_marker(project_root: Path) -> dict[str, str]:
    marker_path = project_root / ".augur-worktree.yaml"
    if not marker_path.exists():
        return {}

    marker: dict[str, str] = {}
    for raw_line in marker_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        marker[key.strip()] = _strip_quotes(value)
    return marker


def _load_worktree_registry(runtime_dir: Path) -> dict[str, dict[str, object]]:
    registry_path = runtime_dir / "worktree_registry.yaml"
    if not registry_path.exists():
        return {}

    try:
        import yaml  # type: ignore

        raw = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}

    if isinstance(raw, dict) and isinstance(raw.get("worktrees"), dict):
        raw = raw["worktrees"]

    if not isinstance(raw, dict):
        return {}

    return {
        _registry_path_key(path): entry
        for path, entry in raw.items()
        if isinstance(path, str) and isinstance(entry, dict)
    }


def _registry_path_key(path: str | Path) -> str:
    try:
        normalized = str(Path(path).expanduser().resolve())
    except Exception:
        normalized = str(path)
    return normalized.lower() if _is_windows() else normalized


def _resolve_ports(
    project_root: Path,
    marker: dict[str, str],
    runtime_dir: Path,
) -> dict[str, int]:
    dashboard_port = marker.get("dashboard_port")
    mcp_port = marker.get("mcp_port")
    if dashboard_port or mcp_port:
        return {
            "dashboard_port": int(dashboard_port or DEFAULT_DASHBOARD_PORT),
            "mcp_port": int(mcp_port or DEFAULT_MCP_PORT),
        }

    entry = _load_worktree_registry(runtime_dir).get(_registry_path_key(project_root), {})
    return {
        "dashboard_port": int(entry.get("dashboard_port", DEFAULT_DASHBOARD_PORT)),
        "mcp_port": int(entry.get("mcp_port", DEFAULT_MCP_PORT)),
    }


def _resolve_main_repo(project_root: Path, marker: dict[str, str]) -> Path:
    if marker.get("main_repo"):
        return Path(marker["main_repo"]).expanduser().resolve()

    try:
        common_dir = subprocess.check_output(
            ["git", "-C", str(project_root), "rev-parse", "--git-common-dir"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return project_root

    common_path = (project_root / common_dir).resolve() if not os.path.isabs(common_dir) else Path(common_dir).resolve()
    if common_path.name == ".git":
        return common_path.parent
    return project_root


def _detect_main_worktree(project_root: Path) -> Path | None:
    """Return the main checkout path if it's a sibling worktree with a populated node_modules.

    Reuses the existing main-repo resolution and additionally verifies the source has a
    materialized .bin/next — otherwise there's nothing worth cloning from.
    """
    try:
        main_repo = _resolve_main_repo(project_root, _load_marker(project_root))
    except Exception:
        return None
    if main_repo == project_root:
        return None  # we're already in main; no sibling source
    candidate_next = main_repo / "apps" / "dashboard" / "node_modules" / ".bin" / "next"
    if not candidate_next.exists():
        return None
    return main_repo


def _run_git_lines(project_root: Path, *args: str) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(project_root), *args],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError:
        return []

    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _git_ok(project_root: Path, *args: str) -> bool:
    return (
        subprocess.run(
            ["git", "-C", str(project_root), *args],
            check=False,
            capture_output=True,
            text=True,
        ).returncode
        == 0
    )


def _changed_paths_since_main(project_root: Path, main_repo: Path) -> set[str]:
    base_ref = "main"
    if not _git_ok(main_repo, "show-ref", "--verify", "--quiet", "refs/heads/main"):
        if _git_ok(main_repo, "show-ref", "--verify", "--quiet", "refs/remotes/origin/main"):
            base_ref = "origin/main"

    paths: set[str] = set()
    paths.update(_run_git_lines(project_root, "diff", "--name-only", f"{base_ref}...HEAD"))
    paths.update(_run_git_lines(project_root, "diff", "--name-only"))
    paths.update(_run_git_lines(project_root, "diff", "--name-only", "--cached"))
    paths.update(_run_git_lines(project_root, "ls-files", "--others", "--exclude-standard"))
    return paths


def _infer_dev_hubs_from_paths(paths: set[str]) -> list[str]:
    hubs: set[str] = set()
    saw_dashboard_scope = False

    for raw_path in sorted(paths):
        path = raw_path.strip()
        if (
            not path
            or path in AUTO_FOCUS_IGNORED_PATHS
            or path.startswith(AUTO_FOCUS_IGNORED_PREFIXES)
        ):
            continue

        mapped_hub = None
        for prefix, hub in AUTO_FOCUS_PREFIXES:
            if path.startswith(prefix):
                mapped_hub = hub
                break
        if mapped_hub is not None:
            saw_dashboard_scope = True
            hubs.add(mapped_hub)
            continue

        if path.startswith("apps/dashboard/app/"):
            saw_dashboard_scope = True
            relative = path.removeprefix("apps/dashboard/app/")
            top_level = relative.split("/", 1)[0]
            if top_level in AUTO_FOCUS_HUBS:
                hubs.add(top_level)
                continue
            return []

        if path.startswith("apps/dashboard/features/generated-skill-pages/"):
            saw_dashboard_scope = True
            relative = path.removeprefix("apps/dashboard/features/generated-skill-pages/")
            top_level = relative.split("/", 1)[0]
            if top_level in AUTO_FOCUS_HUBS:
                hubs.add(top_level)
                continue
            return []

        if path.startswith("apps/dashboard/"):
            saw_dashboard_scope = True
            return []

    if not saw_dashboard_scope:
        return []
    return sorted(hubs)


def _resolve_dev_hubs(
    project_root: Path,
    main_repo: Path,
    marker: dict[str, str],
) -> str | None:
    marker_dev_hubs = marker.get("dev_hubs", "").strip()
    if marker_dev_hubs:
        return marker_dev_hubs

    inferred = _infer_dev_hubs_from_paths(_changed_paths_since_main(project_root, main_repo))
    if not inferred:
        return None
    return ",".join(inferred)


def _worktree_guard_path() -> Path:
    project_root = Path(__file__).resolve().parents[1]
    return (
        project_root
        / "project-brain"
        / "capabilities"
        / "skills"
        / "platform-admin"
        / "scripts"
        / "worktree_guard.py"
    )


def _load_worktree_guard_module() -> tuple[object | None, str | None]:
    guard_path = _worktree_guard_path()
    if not guard_path.exists():
        return None, f"guard module missing: {guard_path}"

    module_name = "platform_admin_worktree_guard"
    module = sys.modules.get(module_name)
    if module is not None:
        return module, None

    spec = importlib.util.spec_from_file_location(module_name, guard_path)
    if spec is None or spec.loader is None:
        return None, f"could not load guard module import spec: {guard_path}"

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        sys.modules.pop(module_name, None)
        return None, f"failed to import guard module {guard_path}: {exc}"
    return module, None


def _safe_link(target: Path, source: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.symlink_to(source, target_is_directory=source.is_dir())
        return
    except OSError as exc:
        if not _is_windows() or getattr(exc, "winerror", None) != 1314:
            raise

    if source.is_dir():
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(target), str(source)],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and target.exists():
            return
        shutil.copytree(source, target)
        return

    shutil.copy2(source, target)


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _ensure_symlink(
    target: Path,
    source: Path,
    repairs: list[Repair],
    incidents: list[Incident],
    owner_path: Path,
    fingerprint: str,
) -> bool:
    if target.is_symlink() and not target.exists():
        target.unlink()
    elif target.exists():
        return True
    if not source.exists():
        incidents.append(
            Incident(
                fingerprint=fingerprint,
                severity="high",
                message=f"Shared dependency source missing: {source}",
                owner_path=str(owner_path),
                safe_to_repair=False,
                repaired=False,
            )
        )
        return False

    _safe_link(target, source)
    repairs.append(Repair(type="symlink", path=str(target), target=str(source)))
    incidents.append(
        Incident(
            fingerprint=fingerprint,
            severity="medium",
            message=f"Bootstrapped missing shared dependency at {target}",
            owner_path=str(owner_path),
            safe_to_repair=True,
            repaired=True,
        )
    )
    return True


def _run_dashboard_install(
    dashboard_dir: Path,
    incidents: list[Incident],
    repairs: list[Repair],
    owner_path: Path,
) -> bool:
    install_cmd = _dashboard_install_command(dashboard_dir)
    try:
        subprocess.run(
            install_cmd,
            cwd=dashboard_dir,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or exc.stdout or "").strip()
        incidents.append(
            Incident(
                fingerprint="worktree/bootstrap/missing-dashboard-node-modules",
                severity="high",
                message=(
                    f"Dashboard dependency bootstrap failed in {dashboard_dir}: "
                    f"{stderr[:500] or 'npm install exited non-zero'}"
                ),
                owner_path=str(owner_path),
                safe_to_repair=False,
                repaired=False,
            )
        )
        return False

    repairs.append(
        Repair(
            type="npm-install",
            path=str(dashboard_dir),
            target=" ".join(shlex.quote(part) for part in install_cmd),
        )
    )
    incidents.append(
        Incident(
            fingerprint="worktree/bootstrap/missing-dashboard-node-modules",
            severity="medium",
            message=f"Installed dashboard dependencies in {dashboard_dir}",
            owner_path=str(owner_path),
            safe_to_repair=True,
            repaired=True,
        )
    )
    return True


def _dashboard_install_command(dashboard_dir: Path) -> list[str]:
    package_json = dashboard_dir / "package.json"
    lockfile = dashboard_dir / "pnpm-lock.yaml"
    package_manager = ""

    if package_json.exists():
        try:
            package_manager = json.loads(package_json.read_text(encoding="utf-8")).get("packageManager", "")
        except Exception:
            package_manager = ""

    if package_manager.startswith("pnpm@") or lockfile.exists():
        pnpm = shutil.which("pnpm")
        if pnpm:
            return [pnpm, "install"]
        corepack = shutil.which("corepack")
        if corepack:
            return [corepack, "pnpm", "install"]

    return ["npm", "install", "--no-fund", "--no-audit"]


def _venv_tool_path(project_root: Path, tool: str) -> Path:
    candidates = [
        project_root / ".venv" / "bin" / tool,
        project_root / ".venv" / "bin" / f"{tool}.exe",
        project_root / ".venv" / "Scripts" / tool,
        project_root / ".venv" / "Scripts" / f"{tool}.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _is_windows_store_python_alias(candidate: Path) -> bool:
    normalized = str(candidate).replace("/", "\\").lower()
    return "\\windowsapps\\" in normalized and candidate.name.lower() in {
        "python.exe",
        "python3.exe",
    }


def _path_like(reference: Path, value: str) -> Path:
    return type(reference)(value)


def _resolve_python_path(project_root: Path) -> Path:
    explicit = os.environ.get("AUGUR_PYTHON", "").strip()
    if explicit:
        explicit_path = _path_like(project_root, _strip_quotes(explicit))
        if not (_is_windows() and _is_windows_store_python_alias(explicit_path)):
            return explicit_path

    if _is_windows():
        candidates = [
            project_root / ".venv" / "Scripts" / "python.exe",
            project_root / ".venv" / "Scripts" / "python3.exe",
            project_root / ".venv" / "bin" / "python3",
        ]
        fallback_commands = ("python", "python3")
    else:
        candidates = [
            project_root / ".venv" / "bin" / "python3",
            project_root / ".venv" / "bin" / "python",
            project_root / ".venv" / "Scripts" / "python.exe",
        ]
        fallback_commands = ("python3", "python")

    for candidate in candidates:
        if candidate.exists():
            return candidate

    for command in fallback_commands:
        fallback = shutil.which(command)
        if not fallback:
            continue
        fallback_path = _path_like(project_root, fallback)
        if _is_windows() and _is_windows_store_python_alias(fallback_path):
            continue
        return fallback_path

    return _path_like(project_root, os.path.realpath(sys.executable))


def _check_pnpm_alignment(project_root: Path) -> Incident | None:
    """Wrapper around worktree_toolchain.verify_pnpm_alignment for the preflight contract."""
    import worktree_toolchain  # lazy: avoid circular import (toolchain imports Incident from here)

    return worktree_toolchain.verify_pnpm_alignment(project_root)


def _ensure_dashboard_dependencies(
    project_root: Path,
    repairs: list[Repair],
    incidents: list[Incident],
    owner_path: Path,
    repair: bool,
) -> bool:
    dashboard_dir = project_root / "apps" / "dashboard"
    node_modules_dir = dashboard_dir / "node_modules"
    next_bin = node_modules_dir / ".bin" / "next"

    if next_bin.exists() and not node_modules_dir.is_symlink():
        return True

    if node_modules_dir.is_symlink():
        resolved = node_modules_dir.resolve()
        if not _is_relative_to(resolved, project_root):
            incidents.append(
                Incident(
                    fingerprint="worktree/bootstrap/missing-dashboard-node-modules",
                    severity="high",
                    message=(
                        f"Dashboard node_modules points outside worktree root: "
                        f"{node_modules_dir} -> {resolved}"
                    ),
                    owner_path=str(owner_path),
                    safe_to_repair=repair,
                    repaired=False,
                )
            )
        if repair:
            node_modules_dir.unlink()
            repairs.append(Repair(type="unlink", path=str(node_modules_dir), target=str(resolved)))

    if next_bin.exists():
        return True

    if not repair:
        incidents.append(
            Incident(
                fingerprint="worktree/bootstrap/missing-dashboard-node-modules",
                severity="high",
                message=f"Dashboard dependencies missing in {dashboard_dir}",
                owner_path=str(owner_path),
                safe_to_repair=True,
                repaired=False,
            )
        )
        return False

    import worktree_toolchain  # lazy: avoid circular import

    source_worktree = _detect_main_worktree(project_root)
    result = worktree_toolchain.materialize_node_modules(
        worktree_root=project_root,
        source_worktree=source_worktree,
    )
    for incident in result.incidents:
        incidents.append(incident)
    if result.method == "clone":
        repairs.append(
            Repair(
                type="cow-clone",
                path=str(dashboard_dir),
                target=(
                    f"source={result.source_worktree} "
                    f"primitive={result.clone_primitive} "
                    f"ms={result.duration_ms}"
                ),
            )
        )
    elif result.method == "install":
        repairs.append(
            Repair(
                type="npm-install",
                path=str(dashboard_dir),
                target=f"pnpm install --frozen-lockfile ms={result.duration_ms}",
            )
        )
    return result.method in {"clone", "install", "skip"}


def _ensure_runtime(
    runtime_dir: Path,
    repairs: list[Repair],
    incidents: list[Incident],
    owner_path: Path,
) -> None:
    if runtime_dir.exists():
        return
    runtime_dir.mkdir(parents=True, exist_ok=True)
    repairs.append(Repair(type="mkdir", path=str(runtime_dir)))
    incidents.append(
        Incident(
            fingerprint="worktree/bootstrap/missing-runtime",
            severity="medium",
            message=f"Created missing runtime directory at {runtime_dir}",
            owner_path=str(owner_path),
            safe_to_repair=True,
            repaired=True,
        )
    )


def _run_sync_bootstrap(
    project_root: Path,
    repairs: list[Repair],
    incidents: list[Incident],
    owner_path: Path,
    mcp_port: int,
) -> bool:
    env = os.environ.copy()
    env["AUGUR_ROOT"] = str(project_root)
    env["AUGUR_CORE"] = str(project_root)
    env["AUGUR_REPO"] = str(project_root)
    env["AUGUR_SYNC_PROJECT_ROOT"] = str(project_root)
    env["AUGUR_SYNC_REPO_LOCAL_ONLY"] = "1"
    pythonpath_parts = [
        str(project_root / "project-brain" / "capabilities"),
        str(project_root),
        str(project_root / "src" / "mcp"),
    ]
    if env.get("PYTHONPATH"):
        pythonpath_parts.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)

    python_cmd = str(_resolve_python_path(project_root))
    sync_cmd = [python_cmd, "-c", WORKTREE_SYNC_BOOTSTRAP_CODE]
    try:
        subprocess.run(
            sync_cmd,
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or exc.stdout or "").strip()
        incidents.append(
            Incident(
                fingerprint="worktree/bootstrap/missing-sync-outputs",
                severity="high",
                message=(
                    f"Sync bootstrap failed in {project_root}: "
                    f"{stderr[:500] or 'worktree-local sync bootstrap exited non-zero'}"
                ),
                owner_path=str(owner_path),
                safe_to_repair=False,
                repaired=False,
            )
        )
        return False

    repairs.append(
        Repair(
            type="sync",
            path=str(project_root),
            target=" ".join(shlex.quote(part) for part in sync_cmd),
        )
    )

    mcp_script = project_root / "scripts" / "generate-worktree-mcp.py"
    if not mcp_script.exists():
        incidents.append(
            Incident(
                fingerprint="worktree/bootstrap/missing-sync-outputs",
                severity="high",
                message=f"Worktree MCP config generator missing: {mcp_script}",
                owner_path=str(owner_path),
                safe_to_repair=False,
                repaired=False,
            )
        )
        return False

    mcp_cmd = [
        python_cmd,
        str(mcp_script),
        "--path",
        str(project_root),
        "--all",
        "--mcp-port",
        str(mcp_port),
    ]
    try:
        subprocess.run(
            mcp_cmd,
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or exc.stdout or "").strip()
        incidents.append(
            Incident(
                fingerprint="worktree/bootstrap/missing-sync-outputs",
                severity="high",
                message=(
                    f"Worktree MCP config bootstrap failed in {project_root}: "
                    f"{stderr[:500] or 'generate-worktree-mcp.py exited non-zero'}"
                ),
                owner_path=str(owner_path),
                safe_to_repair=False,
                repaired=False,
            )
        )
        return False

    repairs.append(
        Repair(
            type="mcp-config",
            path=str(project_root),
            target=" ".join(shlex.quote(part) for part in mcp_cmd),
        )
    )
    return True


def _repo_local_sync_output_paths(project_root: Path) -> list[Path]:
    """Return repo-local sync outputs that the worktree bootstrap must produce.

    Asks each active adapter via get_required_outputs(**WORKTREE_SYNC_FLAGS)
    rather than enumerating get_managed_files() — get_managed_files() is the
    cleanup contract (everything we own), get_required_outputs() is the
    verification contract (what must materialize given the active flags).
    Older adapters that have not implemented get_required_outputs() fall back
    to get_managed_files(), with optional cleanup-only surfaces filtered out.
    """
# TODO_CLEANUP: This file is 1003 lines — consider splitting into smaller modules
    from skills.ai.scripts.sync_agents.engine import (
        _get_all_adapters,
        _is_adapter_active,
        _load_enabled_groups,
        _load_ide_integrations,
    )

    required_paths: set[Path] = set()
    config = _load_ide_integrations(project_root)
    enabled_groups = _load_enabled_groups()

    for adapter in _get_all_adapters():
        if not _is_adapter_active(adapter, config, enabled_groups):
            continue
        if hasattr(adapter, "get_required_outputs"):
            raw_paths = adapter.get_required_outputs(project_root, **WORKTREE_SYNC_FLAGS)
        elif hasattr(adapter, "get_managed_files"):
            raw_paths = adapter.get_managed_files()
        else:
            raw_paths = []

        for raw_path in raw_paths:
            path = Path(raw_path)
            if path.is_absolute():
                try:
                    path = path.resolve().relative_to(project_root)
                except ValueError:
                    continue
            target = project_root / path
            rel = target.relative_to(project_root).as_posix().rstrip("/")
            if rel in OPTIONAL_REPO_LOCAL_SYNC_OUTPUTS:
                continue
            required_paths.add(target)
    return sorted(required_paths)


def _sync_output_ready(path: Path) -> bool:
    """Return True when a required sync output is present.

    Directory outputs must contain at least one entry. If an adapter can
    legitimately produce an empty directory, it should omit that path from
    get_required_outputs() or mark it optional.
    """
    if not path.exists():
        return False
    if path.is_dir():
        return any(path.iterdir())
    return True


def _verify_worktree_sync_outputs(
    project_root: Path,
    incidents: list[Incident],
    owner_path: Path,
) -> tuple[bool, str]:
    try:
        required_paths = _repo_local_sync_output_paths(project_root)
    except Exception as exc:
        message = f"Unable to resolve sync-managed outputs for {project_root}: {exc}"
        incidents.append(
            Incident(
                fingerprint="worktree/bootstrap/missing-sync-outputs",
                severity="high",
                message=message,
                owner_path=str(owner_path),
                safe_to_repair=False,
                repaired=False,
            )
        )
        return False, message

    missing_paths = [path for path in required_paths if not _sync_output_ready(path)]
    if not missing_paths:
        return True, f"managed_outputs={len(required_paths)}"

    preview = [path.relative_to(project_root).as_posix() for path in missing_paths[:8]]
    remaining = len(missing_paths) - len(preview)
    details = f"missing={', '.join(preview)}"
    if remaining > 0:
        details = f"{details} (+{remaining} more)"

    incidents.append(
        Incident(
            fingerprint="worktree/bootstrap/missing-sync-outputs",
            severity="high",
            message=f"Missing repo-local sync outputs in {project_root}: {details}",
            owner_path=str(owner_path),
            safe_to_repair=True,
            repaired=False,
        )
    )
    return False, details


def _client_id(project_root: Path) -> str:
    base = project_root.name or "dashboard"
    digest = hashlib.sha1(str(project_root).encode("utf-8")).hexdigest()[:8]
    return f"dashboard-{base}-{digest}"


def _load_json(path: Path) -> object | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write_json_atomic(path: Path, data: object) -> None:
    tmp = path.with_name(path.name + ".augur-tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    # Re-parse before swapping so we never replace the registry with invalid JSON.
    json.loads(tmp.read_text(encoding="utf-8"))
    os.replace(tmp, path)  # atomic on POSIX and Windows (same filesystem)


def _claude_config_dir() -> Path:
    override = os.environ.get("CLAUDE_CONFIG_DIR")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".claude"


def _claude_settings_enabled_plugins(project_root: Path) -> dict[str, bool]:
    data = _load_json(project_root / ".claude" / "settings.json")
    if not isinstance(data, dict):
        return {}
    enabled = data.get("enabledPlugins")
    if not isinstance(enabled, dict):
        return {}
    return {str(name): bool(on) for name, on in enabled.items()}


def _plan_claude_worktree_plugins(
    project_root: Path,
    enabled_plugins: dict[str, bool],
    installed_data: dict[str, object],
) -> tuple[dict[str, object], list[str], list[str]]:
    """Pure planner for Claude project-scoped plugin registration.

    Returns ``(updated_data, registered, missing_cache)`` without performing any
    I/O. ``installed_data`` is not mutated. ``registered`` are plugins for which a
    new project-scope install record was added (cloned from an existing record
    that already points at the shared plugin cache); ``missing_cache`` are plugins
    enabled in settings that have no install cache to clone.
    """
    from datetime import datetime, timezone

    data = copy.deepcopy(installed_data)
    plugins = data.get("plugins")
    if not isinstance(plugins, dict):
        plugins = {}
        data["plugins"] = plugins

    want_key = _registry_path_key(project_root)
    project_path_str = str(Path(project_root).resolve())
    moment = datetime.now(timezone.utc)
    now = moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{moment.microsecond // 1000:03d}Z"

    registered: list[str] = []
    missing_cache: list[str] = []

    for name, on in enabled_plugins.items():
        if not on:
            continue
        entries = plugins.get(name)
        if not isinstance(entries, list):
            entries = []
        covered = any(
            isinstance(entry, dict)
            and (
                entry.get("scope") == "user"
                or (
                    entry.get("scope") in {"project", "local"}
                    and entry.get("projectPath")
                    and _registry_path_key(entry["projectPath"]) == want_key
                )
            )
            for entry in entries
        )
        if covered:
            continue
        template = next(
            (
                entry
                for entry in entries
                if isinstance(entry, dict)
                and entry.get("installPath")
                and Path(entry["installPath"]).exists()
            ),
            None,
        )
        if template is None:
            missing_cache.append(name)
            continue
        new_entry = {
            "scope": "project",
            "projectPath": project_path_str,
            "installPath": template["installPath"],
            "version": template.get("version"),
            "installedAt": now,
            "lastUpdated": now,
        }
        if template.get("gitCommitSha"):
            new_entry["gitCommitSha"] = template["gitCommitSha"]
        entries.append(new_entry)
        plugins[name] = entries
        registered.append(name)

    return data, registered, missing_cache


def _ensure_client_plugin_registrations(
    project_root: Path,
    repairs: list[Repair],
    incidents: list[Incident],
    owner_path: Path,
    *,
    repair: bool,
) -> tuple[bool, str]:
    """Register project-scoped AI-client plugin installs for this worktree path.

    Why this exists
    ---------------
    A git worktree inherits the committed ``.claude/settings.json`` (so
    ``enabledPlugins`` is present) but NOT the per-path install records, which
    live in the user-global plugin registry. Claude Code keys project-scoped
    plugin installs by exact ``projectPath``, so a fresh worktree reports every
    enabled plugin as "enabled in project settings but isn't installed here"
    until a record exists for the new path. We clone an existing install record
    (which already points at the shared, version-pinned plugin cache) under this
    worktree's ``projectPath`` — the same effect as
    ``claude plugin install <name> --scope project``, but deterministic, atomic,
    and runnable from any client on any OS.

    Cross-client scope
    ------------------
    Only Claude Code is path-scoped, so it is the only client repaired here. The
    other clients Augur launches do not break per worktree, so they are
    intentional no-ops (documented so nobody "fixes" a non-bug):

      * Gemini CLI keys extension activation by GLOB overrides in
        ``~/.gemini/extensions/extension-enablement.json`` — a pattern such as
        ``.../Projects/*`` already spans every worktree.
      * Codex CLI enables plugins globally via ``[plugins."<id>"]`` in
        ``~/.codex/config.toml`` — not keyed by project path at all.

    If either client ever adds path-scoped installs, add its registrar here.

    Returns ``(ok, details)`` for the preflight check. ``ok`` is False only when a
    plugin is enabled in settings but has no install cache to clone (the user
    must run the client's install command once). This never blocks worktree
    creation: ``client_plugins`` is not a profile requirement.
    """
    enabled = _claude_settings_enabled_plugins(project_root)
    if not enabled or not any(enabled.values()):
        return True, "no client plugins enabled in project settings"

    registry_path = _claude_config_dir() / "plugins" / "installed_plugins.json"
    installed_data = _load_json(registry_path)
    if not isinstance(installed_data, dict):
        # Claude Code not present on this machine (e.g. a Gemini/Codex-only host).
        return True, f"claude plugin registry absent at {registry_path}"

    updated_data, registered, missing_cache = _plan_claude_worktree_plugins(
        project_root, enabled, installed_data
    )

    if registered and repair:
        _write_json_atomic(registry_path, updated_data)
        for name in registered:
            repairs.append(
                Repair(type="claude-plugin-register", path=name, target=str(project_root))
            )
    elif registered and not repair:
        incidents.append(
            Incident(
                fingerprint="worktree/bootstrap/claude-plugins-unregistered",
                severity="low",
                message=(
                    "Claude plugins enabled in project settings lack a project-scope "
                    f"install record for this worktree: {', '.join(registered)} "
                    "(run with --repair to register)"
                ),
                owner_path=str(owner_path),
                safe_to_repair=True,
                repaired=False,
            )
        )

    for name in missing_cache:
        incidents.append(
            Incident(
                fingerprint="worktree/bootstrap/claude-plugin-not-installed",
                severity="medium",
                message=(
                    f"Plugin '{name}' is enabled in project settings but no install "
                    "cache exists to register; install it once with "
                    f"`claude plugin install {name} --scope project`"
                ),
                owner_path=str(owner_path),
                safe_to_repair=False,
                repaired=False,
            )
        )

    parts: list[str] = []
    if registered:
        parts.append(f"{'registered' if repair else 'pending'}={len(registered)}")
    if missing_cache:
        parts.append(f"missing_cache={len(missing_cache)}")
    if not parts:
        parts.append("all enabled plugins already registered")
    return not missing_cache, "; ".join(parts)


def _check(name: str, ok: bool, details: str, checks: list[Check]) -> None:
    checks.append(Check(name=name, ok=ok, details=details))


def _record_incident_index(
    project_root: Path,
    incidents: list[Incident],
    profile: str,
    *,
    verify_passed: bool,
) -> None:
    if not incidents:
        return

    _add_project_root_to_sys_path(project_root)
    try:
        from src.config.paths import get_runtime_dir
        from skills.ai.scripts.adaptive.incidents import (
            IncidentRecord,
            aggregate_incidents,
        )
    except Exception:
        return

    timestamp = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
    records = []
    for incident in incidents:
        records.append(
            IncidentRecord(
                fingerprint=incident.fingerprint,
                category=incident.category,
                severity=incident.severity,
                owner_path=incident.owner_path,
                message=incident.message,
                command=f"worktree-preflight:{profile}",
                first_seen_at=timestamp,
                last_seen_at=timestamp,
                occurrences=1,
                commands=[f"worktree-preflight:{profile}"],
                worktrees=[str(project_root)],
                sample_errors=[incident.message],
                auto_heal_status="applied" if incident.repaired else "not_attempted",
                verify_status="passed" if verify_passed else "failed",
            )
        )

    aggregate_incidents(get_runtime_dir(), records)


def build_contract(
    project_root: Path,
    profile: str,
    repair: bool,
    interactive: bool = False,
) -> dict[str, object]:
    project_root = project_root.resolve()
    _add_project_root_to_sys_path(project_root)

    from src.config.paths import get_runtime_dir
    from src.lib.dashboard_instance import resolve_dashboard_instance

    marker = _load_marker(project_root)
    runtime_dir = get_runtime_dir()
    instance = resolve_dashboard_instance(
        project_root, runtime_dir=runtime_dir, interactive=interactive
    )
    main_repo = instance.main_repo
    is_worktree = instance.kind == "worktree"
    is_non_main_instance = instance.kind != "main"

    dev_hubs = _resolve_dev_hubs(project_root, main_repo, marker) if is_non_main_instance else None
    checks: list[Check] = []
    repairs: list[Repair] = []
    incidents: list[Incident] = []

    if not is_non_main_instance:
        guard_path = _worktree_guard_path()
        guard_module, guard_error = _load_worktree_guard_module()
        if guard_module is None:
            guard_details = guard_error or f"guard module missing: {guard_path}"
            checks.append(
                Check(
                    name="main_checkout_branch",
                    ok=False,
                    details=guard_details,
                )
            )
            incidents.append(
                Incident(
                    fingerprint="worktree/bootstrap/missing-main-checkout-guard",
                    severity="high",
                    message=f"Missing main checkout branch guard module: {guard_details}",
                    owner_path=str(project_root / "scripts" / "worktree_preflight.py"),
                    safe_to_repair=False,
                    repaired=False,
                    category="environment",
                )
            )
        else:
            try:
                guard_result = guard_module.check_main_checkout_branch(project_root)
            except Exception as exc:
                checks.append(
                    Check(
                        name="main_checkout_branch",
                        ok=False,
                        details=f"main checkout guard check failed: {exc}",
                    )
                )
                incidents.append(
                    Incident(
                        fingerprint="worktree/bootstrap/main-checkout-guard-failed",
                        severity="high",
                        message=f"Main checkout branch guard failed for {project_root}: {exc}",
                        owner_path=str(project_root / "scripts" / "worktree_preflight.py"),
                        safe_to_repair=False,
                        repaired=False,
                        category="environment",
                    )
                )
            else:
                checks.append(
                    Check(
                        name="main_checkout_branch",
                        ok=bool(guard_result.ok),
                        details=str(guard_result.message),
                    )
                )

    inherited_root = os.environ.get("AUGUR_ROOT")
    if inherited_root:
        inherited = Path(inherited_root).expanduser().resolve()
        if inherited != project_root:
            incidents.append(
                Incident(
                    fingerprint="worktree/root/env-drift",
                    severity="high",
                    message=f"Inherited AUGUR_ROOT points to {inherited}, canonical root is {project_root}",
                    owner_path=str(project_root / "wrap.sh"),
                    safe_to_repair=True,
                    repaired=False,
                    category="environment",
                )
            )

    if repair:
        _ensure_runtime(
            runtime_dir,
            repairs,
            incidents,
            project_root / "scripts" / "worktree_preflight.py",
        )

    _check("runtime", runtime_dir.exists(), f"runtime_dir={runtime_dir}", checks)

    sync_outputs_ok = True
    sync_outputs_details = "bootstrap=worktree-local sync_agents + generate-worktree-mcp"
    if is_non_main_instance:
        client_plugins_ok, client_plugins_details = _ensure_client_plugin_registrations(
            project_root,
            repairs,
            incidents,
            project_root / ".claude" / "settings.json",
            repair=repair,
        )
        _check("client_plugins", client_plugins_ok, client_plugins_details, checks)

        for rel_path in REQUIRED_SHARED_DEPENDENCY_PATHS:
            target = project_root / rel_path
            source = main_repo / rel_path
            if repair:
                _ensure_symlink(
                    target,
                    source,
                    repairs,
                    incidents,
                    project_root / "wrap.sh",
                    f"worktree/bootstrap/missing-{rel_path.lstrip('.').replace('.', '-')}",
                )
            _check(rel_path, target.exists(), f"target={target}", checks)

        for rel_path in OPTIONAL_SHARED_DEPENDENCY_PATHS:
            target = project_root / rel_path
            source = main_repo / rel_path
            if repair and source.exists():
                _ensure_symlink(
                    target,
                    source,
                    repairs,
                    incidents,
                    project_root / "wrap.sh",
                    f"worktree/bootstrap/missing-{rel_path.lstrip('.').replace('.', '-')}",
                )
            if target.exists():
                _check(rel_path, True, f"target={target}", checks)
            elif source.exists():
                _check(rel_path, False, f"target={target}", checks)
            else:
                _check(rel_path, True, f"optional source missing={source}", checks)

        dashboard_ready = _ensure_dashboard_dependencies(
            project_root,
            repairs,
            incidents,
            project_root / "apps" / "dashboard" / "scripts" / "start-dev.sh",
            repair,
        )
        node_modules_target = project_root / "apps" / "dashboard" / "node_modules"
        _check("dashboard_node_modules", dashboard_ready, f"target={node_modules_target}", checks)

        alignment_incident = _check_pnpm_alignment(project_root)
        _check(
            "pnpm_alignment",
            alignment_incident is None,
            f"store_aligned={alignment_incident is None}",
            checks,
        )
        if alignment_incident is not None:
            incidents.append(alignment_incident)

        if profile == "worktree":
            if repair:
                sync_outputs_ok = _run_sync_bootstrap(
                    project_root,
                    repairs,
                    incidents,
                    project_root / "scripts" / "worktree_preflight.py",
                    instance.mcp_port,
                )
            if sync_outputs_ok:
                sync_outputs_ok, sync_outputs_details = _verify_worktree_sync_outputs(
                    project_root,
                    incidents,
                    project_root / "scripts" / "worktree_preflight.py",
                )

    _check("sync_outputs", sync_outputs_ok, sync_outputs_details, checks)

    python_path = _resolve_python_path(project_root)
    _check("python", python_path.exists(), f"python_path={python_path}", checks)
    ruff_path = _venv_tool_path(project_root, "ruff")
    _check("ruff", ruff_path.exists(), f"ruff_path={ruff_path}", checks)

    dashboard_node_modules = project_root / "apps" / "dashboard" / "node_modules" / ".bin" / "next"
    _check(
        "dashboard_deps",
        dashboard_node_modules.exists(),
        f"next_bin={dashboard_node_modules}",
        checks,
    )

    profile_requirements = PROFILE_REQUIREMENTS[profile]
    verify_passed = all(check.ok for check in checks if check.name in profile_requirements)

    report = {
        "profile": profile,
        "project_root": str(project_root),
        "main_repo": str(main_repo),
        "worktree": is_worktree,
        "instance_id": instance.instance_id,
        "instance_kind": instance.kind,
        "browser_mode": instance.browser_mode,
        "heal_policy": instance.heal_policy,
        "visibility_policy": instance.visibility_policy,
        "lifecycle_dir": str(instance.lifecycle_dir),
        "build_lock_dir": str(instance.build_lock_dir),
        "browser_artifact_dir": str(instance.browser_artifact_dir),
        "dashboard_port": instance.dashboard_port,
        "mcp_port": instance.mcp_port,
        "dev_hubs": dev_hubs,
        "mcp_client_id": _client_id(project_root),
        "runtime_dir": str(runtime_dir),
        "python_path": str(python_path),
        "ruff_path": str(ruff_path),
        "checks": [asdict(check) for check in checks],
        "repairs_applied": [asdict(repair) for repair in repairs],
        "incidents_detected": [asdict(incident) for incident in incidents],
        "verify_passed": verify_passed,
    }

    _record_incident_index(project_root, incidents, profile, verify_passed=verify_passed)

    runtime_dir.mkdir(parents=True, exist_ok=True)
    report_path = runtime_dir / "worktree-preflight.json"
    report["report_path"] = str(report_path)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=os.getcwd(), help="Repo root or path inside repo")
    parser.add_argument(
        "--profile",
        choices=sorted(PROFILE_REQUIREMENTS),
        default="shell",
        help="Caller profile with specific verification requirements",
    )
    parser.add_argument("--repair", action="store_true", help="Apply safe repairs before verification")
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Resolve dashboard instance with browser_mode=isolated_visible for non-main checkouts",
    )
    args = parser.parse_args()

    start = Path(args.root).expanduser().resolve()
    project_root = _discover_repo_root(start)
    report = build_contract(project_root, args.profile, args.repair, args.interactive)
    json.dump(report, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if report["verify_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
