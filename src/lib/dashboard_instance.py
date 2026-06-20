from __future__ import annotations

import hashlib
import os
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from src.config.paths import get_cache_dir, get_runtime_dir

DEFAULT_DASHBOARD_PORT = 3000
DEFAULT_MCP_PORT = 8080

InstanceKind = Literal["main", "worktree", "isolated"]
BrowserMode = Literal["visible_allowed", "headless_only", "isolated_visible"]
HealPolicy = Literal["enabled", "validation_only", "disabled"]
VisibilityPolicy = Literal["visible_allowed", "no_visible_mutation"]


@dataclass(frozen=True)
class AugurDashboardInstance:
    instance_id: str
    kind: InstanceKind
    name: str
    project_root: Path
    main_repo: Path
    branch: str
    dashboard_port: int
    mcp_port: int
    runtime_dir: Path
    lifecycle_dir: Path
    build_lock_dir: Path
    browser_artifact_dir: Path
    browser_mode: BrowserMode
    heal_policy: HealPolicy
    visibility_policy: VisibilityPolicy

    def to_json_dict(self) -> dict[str, object]:
        data = asdict(self)
        for key in (
            "project_root",
            "main_repo",
            "runtime_dir",
            "lifecycle_dir",
            "build_lock_dir",
            "browser_artifact_dir",
        ):
            data[key] = str(data[key])
        return data


def _strip_quotes(value: object) -> str:
    text = str(value).strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        return text[1:-1]
    return text


def _coerce_port(value: object, default: int) -> int:
    if value in (None, ""):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_name(value: object) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in str(value).strip())
    return cleaned.strip("-_") or "unnamed"


def _registry_key(path: str | Path) -> str:
    resolved = str(Path(path).expanduser().resolve())
    return resolved.lower() if os.name == "nt" else resolved


def _load_yaml_mapping(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        import yaml

        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return _load_flat_yaml_mapping(path)


def _load_flat_yaml_mapping(path: Path) -> dict[str, object]:
    data: dict[str, object] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = _strip_quotes(value)
    return data


def load_worktree_marker(project_root: Path) -> dict[str, object]:
    marker_path = project_root / ".augur-worktree.yaml"
    return _load_yaml_mapping(marker_path)


def load_worktree_registry(runtime_dir: Path) -> dict[str, dict[str, object]]:
    registry_path = runtime_dir / "worktree_registry.yaml"
    raw = _load_yaml_mapping(registry_path)
    worktrees = raw.get("worktrees", raw)
    if not isinstance(worktrees, dict):
        return {}

    registry: dict[str, dict[str, object]] = {}
    for path, entry in worktrees.items():
        if isinstance(path, str) and isinstance(entry, dict):
            registry[_registry_key(path)] = entry
    return registry


def _main_repo_from_git_common_dir(project_root: Path) -> Path | None:
    try:
        common_dir = subprocess.check_output(
            ["git", "-C", str(project_root), "rev-parse", "--git-common-dir"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception:
        return None
    if not common_dir:
        return None

    common_path = Path(common_dir)
    if not common_path.is_absolute():
        common_path = project_root / common_path
    common_path = common_path.resolve()

    if common_path.name == ".git":
        return common_path.parent

    parts = common_path.parts
    if ".git" in parts:
        git_index = parts.index(".git")
        if git_index > 0:
            return Path(*parts[:git_index])
    return None


def resolve_main_repo(project_root: Path, marker: dict[str, object]) -> Path:
    marker_main_repo = marker.get("main_repo")
    if marker_main_repo:
        return Path(_strip_quotes(marker_main_repo)).expanduser().resolve()
    return _main_repo_from_git_common_dir(project_root) or project_root.resolve()


def _current_branch(
    project_root: Path,
    marker: dict[str, object],
    registry_entry: dict[str, object],
) -> str:
    for value in (marker.get("branch"), registry_entry.get("branch")):
        if value:
            return _strip_quotes(value)
    try:
        result = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            check=False,
            text=True,
        )
    except Exception:
        return "unknown"
    return result.stdout.strip() or "unknown"


def _instance_dirs(runtime_dir: Path, kind: InstanceKind, name: str) -> tuple[Path, Path, Path]:
    if kind == "main":
        suffix = Path("main")
    elif kind == "worktree":
        suffix = Path("worktrees") / name
    else:
        suffix = Path("isolated") / name
    return (
        runtime_dir / "daemon" / "dashboard" / suffix,
        runtime_dir / "locks" / "dashboard" / suffix,
        runtime_dir / "browser-verification" / suffix,
    )


def _isolated_id(project_root: Path) -> str:
    digest = hashlib.sha1(str(project_root).encode("utf-8"), usedforsecurity=False).hexdigest()[:10]
    return f"isolated:{digest}"


def resolve_dashboard_instance(
    project_root: Path,
    runtime_dir: Path | None = None,
    explicit_instance: str | None = None,
    interactive: bool = False,
) -> AugurDashboardInstance:
    project_root = project_root.expanduser().resolve()
    runtime_dir = (runtime_dir or get_runtime_dir()).expanduser().resolve()
    marker = load_worktree_marker(project_root)
    registry = load_worktree_registry(runtime_dir)
    registry_entry = registry.get(_registry_key(project_root), {})
    main_repo = resolve_main_repo(project_root, marker).expanduser().resolve()

    marker_says_worktree = str(marker.get("worktree", "")).lower() == "true"
    registered = bool(registry_entry)
    is_main = project_root == main_repo and not marker_says_worktree

    if explicit_instance:
        instance_id = explicit_instance
    elif is_main:
        instance_id = "main"
    elif marker_says_worktree or registered:
        name_value = marker.get("name") or registry_entry.get("name") or project_root.name
        instance_id = f"worktree:{_safe_name(name_value)}"
    else:
        instance_id = _isolated_id(project_root)

    if instance_id == "main":
        kind: InstanceKind = "main"
        name = "main"
    elif instance_id.startswith("worktree:"):
        kind = "worktree"
        name = _safe_name(instance_id.split(":", 1)[1])
    else:
        kind = "isolated"
        name = _safe_name(instance_id.split(":", 1)[-1])

    if kind == "main":
        # The main checkout is canonical: its dashboard/MCP ports come from an
        # explicit .augur-worktree.yaml marker or the defaults — never a
        # worktree-registry row. A stray registry entry keyed to the main repo
        # path (which must not exist) would otherwise move main off the default
        # port, so the scoped restart and readiness poll in `aug dev build`
        # target the wrong port (the false ok:false / orphaned-server bug).
        dashboard_port = _coerce_port(marker.get("dashboard_port"), DEFAULT_DASHBOARD_PORT)
        mcp_port = _coerce_port(marker.get("mcp_port"), DEFAULT_MCP_PORT)
    else:
        dashboard_port = _coerce_port(
            marker.get("dashboard_port") or registry_entry.get("dashboard_port"),
            DEFAULT_DASHBOARD_PORT,
        )
        mcp_port = _coerce_port(
            marker.get("mcp_port") or registry_entry.get("mcp_port"),
            DEFAULT_MCP_PORT,
        )
    lifecycle_dir, build_lock_dir, browser_artifact_dir = _instance_dirs(runtime_dir, kind, name)

    if kind == "main":
        browser_mode: BrowserMode = "visible_allowed"
        heal_policy: HealPolicy = "enabled"
        visibility_policy: VisibilityPolicy = "visible_allowed"
    elif kind == "worktree":
        browser_mode = "isolated_visible" if interactive else "headless_only"
        heal_policy = "validation_only"
        visibility_policy = "no_visible_mutation"
    else:
        browser_mode = "isolated_visible" if interactive else "headless_only"
        heal_policy = "disabled"
        visibility_policy = "no_visible_mutation"

    return AugurDashboardInstance(
        instance_id=instance_id,
        kind=kind,
        name=name,
        project_root=project_root,
        main_repo=main_repo,
        branch=_current_branch(project_root, marker, registry_entry),
        dashboard_port=dashboard_port,
        mcp_port=mcp_port,
        runtime_dir=runtime_dir,
        lifecycle_dir=lifecycle_dir,
        build_lock_dir=build_lock_dir,
        browser_artifact_dir=browser_artifact_dir,
        browser_mode=browser_mode,
        heal_policy=heal_policy,
        visibility_policy=visibility_policy,
    )


def external_dashboard_cache_dir(instance: AugurDashboardInstance, cache_root: Path | None = None) -> Path | None:
    """Per-instance Next/SWC cache dir that start-dev.sh creates under get_cache_dir().

    Mirrors start-dev.sh's CACHE_NAMESPACE derivation (sanitized instance id
    appended to "dashboard-worktree-") — keep the two in sync. The main
    checkout shares the "dashboard" namespace, which must never be removed by
    per-worktree cleanup, so main resolves to None.
    """
    if instance.kind == "main":
        return None
    root = (cache_root or get_cache_dir()).expanduser()
    slug = re.sub(r"[^A-Za-z0-9._-]", "-", instance.instance_id)
    slug = slug.removesuffix("-") or str(instance.dashboard_port)
    return root / f"dashboard-worktree-{slug}"
