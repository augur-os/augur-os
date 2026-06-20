"""Auto-command discovery for the adaptive loop engine.

Pass 1: Scans SKILL.md x-augur-commands declarations for commands with
protocol: scan-fix.
Pass 2: Scans SKILL.md x-augur-loop frontmatter declarations for
standalone loop skills that do not declare explicit commands.

Dynamically loads their Python modules and validates they implement the
OpsCommand protocol (scan/fix functions).

See ADR-200 Section 5 (Engine Discovery).
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
import importlib
import importlib.machinery
import importlib.util
import logging
import sys
import types
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.config.paths import get_adaptive_loop_skill_dirs
from src.lib.ops_protocol import OpsCapabilities, coerce_ops_capabilities, declare_ops_capabilities

logger = logging.getLogger(__name__)


def normalize_metadata_value(value: Any, default: str | None = None) -> str | None:
    """Normalize scheduler/trigger metadata values from SKILL.md frontmatter."""
    if isinstance(value, str):
        normalized = value.strip().lower()
        return normalized or default
    return default


def normalize_trigger(trigger: Any, default: str = "nightly") -> str:
    """Normalize adaptive loop trigger metadata."""
    normalized = normalize_metadata_value(trigger, default)
    return normalized if normalized is not None else default


def normalize_scheduler(scheduler: Any) -> str | None:
    """Normalize adaptive loop scheduler metadata."""
    return normalize_metadata_value(scheduler)


def default_scheduler_for_trigger(trigger: str) -> str:
    """Return the default scheduler owner for an adaptive loop trigger."""
    return "daemon" if normalize_trigger(trigger) == "continuous" else "codex"


def resolve_scheduler(
    loop_config: dict[str, Any],
    fallback_config: dict[str, Any] | None = None,
) -> str:
    """Resolve scheduler owner from explicit metadata or trigger defaults."""
    scheduler = normalize_scheduler(loop_config.get("scheduler"))
    if scheduler:
        return scheduler
    if isinstance(fallback_config, dict):
        scheduler = normalize_scheduler(fallback_config.get("scheduler"))
        if scheduler:
            return scheduler

    trigger = normalize_trigger(loop_config.get("trigger"), "")
    if not trigger and isinstance(fallback_config, dict):
        trigger = normalize_trigger(fallback_config.get("trigger"), "")
    if not trigger:
        trigger = "nightly"
    return default_scheduler_for_trigger(trigger)


@dataclass
class AutoCommandEntry:
    """A discovered auto-command ready for engine registration."""

    name: str
    module: Any  # Loaded Python module implementing scan()/fix()
    loop_name: str
    capabilities: OpsCapabilities = field(default_factory=declare_ops_capabilities)
    tier: int = 0
    trigger: str = "nightly"
    scheduler: str = "codex"
    plugin_root: Path = field(default_factory=lambda: Path.cwd())
    config: dict = field(default_factory=dict)  # Per-module config from x-augur loop config
    initial_trust: float = 0.0  # Bootstrap trust from skill metadata
    runner: str = "legacy"


def _prepend_sys_path(path: Path) -> None:
    path_text = str(path)
    if path_text in sys.path:
        sys.path.remove(path_text)
    sys.path.insert(0, path_text)


def _find_namespace_parent(path: Path, namespace: str) -> Path | None:
    for parent in (path.parent, *path.parents):
        if parent.name == namespace:
            return parent.parent
    return None


def _find_skill_dir(path: Path) -> Path | None:
    for parent in (path.parent, *path.parents):
        if parent.parent.name == "skills":
            return parent
    return None


def _prepend_package_path(module_name: str, path: Path) -> None:
    path_text = str(path)
    module = sys.modules.get(module_name)
    if module is None:
        module = types.ModuleType(module_name)
        module.__package__ = module_name
        module.__path__ = []  # type: ignore[attr-defined]
        module.__spec__ = importlib.machinery.ModuleSpec(
            module_name,
            loader=None,
            is_package=True,
        )
        module.__spec__.submodule_search_locations = module.__path__  # type: ignore[union-attr,attr-defined]
        sys.modules[module_name] = module
        if "." in module_name:
            parent_name, child_name = module_name.rsplit(".", 1)
            parent = sys.modules.get(parent_name)
            if parent is not None:
                setattr(parent, child_name, module)

    package_path = getattr(module, "__path__", None)
    if package_path is None:
        return
    if not hasattr(package_path, "insert") or not hasattr(package_path, "remove"):
        package_path = list(package_path)
        module.__path__ = package_path  # type: ignore[attr-defined]
    existing = [str(entry) for entry in package_path]
    if path_text in existing:
        package_path.remove(path_text)
    package_path.insert(0, path_text)
    spec = getattr(module, "__spec__", None)
    if spec is not None and getattr(spec, "submodule_search_locations", None) is not None:
        spec.submodule_search_locations = package_path


def _prepare_skill_namespace_imports(module_path: Path) -> None:
    skill_dir = _find_skill_dir(module_path)
    if skill_dir is None:
        return

    skills_dir = skill_dir.parent
    skill_name = skill_dir.name
    scripts_dir = skill_dir / "scripts"

    _prepend_package_path("skills", skills_dir)
    _prepend_package_path(f"skills.{skill_name}", skill_dir)
    if scripts_dir.is_dir():
        _prepend_package_path(f"skills.{skill_name}.scripts", scripts_dir)


def _local_bootstrap_path(module_path: Path) -> Path | None:
    candidates = [module_path.parent / "bootstrap_paths.py"]
    if module_path.parent.name == "ops":
        candidates.append(module_path.parent.parent / "bootstrap_paths.py")
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def _prepare_local_imports(module_path: Path) -> None:
    """Make sibling imports behave like direct script execution for ops modules."""
    _prepend_sys_path(module_path.parent)
    if module_path.parent.name == "ops":
        # Keep the scripts root ahead of scripts/ops so package imports like
        # `self_heal.classifier` resolve to scripts/self_heal/ instead of the
        # sibling ops/self_heal.py module.
        _prepend_sys_path(module_path.parent.parent)
    _prepare_skill_namespace_imports(module_path)
    local_bootstrap = _local_bootstrap_path(module_path)
    if local_bootstrap is None:
        return

    loaded_bootstrap = sys.modules.get("bootstrap_paths")
    loaded_file = getattr(loaded_bootstrap, "__file__", None)
    if loaded_file and Path(loaded_file).resolve() != local_bootstrap.resolve():
        sys.modules.pop("bootstrap_paths", None)
    importlib.invalidate_caches()


def load_ops_module(module_path: Path, *, project_root: Path | None = None) -> Any:
    """Dynamically load a Python module from a file path and validate it.

    The module must expose:
    - name: str
    - scan(ctx) -> ScanResult
    - fix(ctx, issues) -> FixResult

    Returns the loaded module object.
    Raises ImportError if the module cannot be loaded or is invalid.
    """
    if not module_path.exists():
        raise ImportError(f"Module file not found: {module_path}")

    module_name = f"ops_cmd_{module_path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, str(module_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot create module spec for: {module_path}")

    module = importlib.util.module_from_spec(spec)

    # Ensure project root resolves top-level `plugins/*` first.
    # Do not prepend `src/` to sys.path: it can shadow stdlib modules
    # (for example `logging` via `src/logging`).
    _prepare_local_imports(module_path)
    resolved_project_root = _find_project_root(module_path) or project_root
    if resolved_project_root:
        _prepend_sys_path(resolved_project_root)
        skills_namespace_parent = _find_namespace_parent(module_path, "skills")
        if skills_namespace_parent:
            _prepend_sys_path(skills_namespace_parent)
        # Canonicalize protocol import path. Some modules import
        # `lib.ops_protocol`, while tests and newer modules import
        # `src.lib.ops_protocol`. Bind both to the same module object so
        # isinstance checks remain stable across legacy/new modules.
        if "lib" not in sys.modules:
            src_lib = importlib.import_module("src.lib")
            src_ops_protocol = importlib.import_module("src.lib.ops_protocol")
            sys.modules["lib"] = src_lib
            sys.modules["lib.ops_protocol"] = src_ops_protocol

    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise

    # Validate the module exposes scan and fix
    if not callable(getattr(module, "scan", None)):
        raise ImportError(
            f"Module {module_path} missing required 'scan' function"
        )
    if not callable(getattr(module, "fix", None)):
        raise ImportError(
            f"Module {module_path} missing required 'fix' function"
        )

    return module


def _read_frontmatter(skill_md: Path) -> dict[str, Any]:
    """Read YAML frontmatter from a SKILL.md file. Returns empty dict on failure."""
    try:
        text = skill_md.read_text()
        if not text.startswith("---"):
            return {}
        end = text.index("---", 3)
        import yaml

        return yaml.safe_load(text[3:end]) or {}
    except Exception:
        return {}


def _find_project_root(path: Path) -> Path | None:
    """Walk up from path to find the project root (contains src/ and config/)."""
    current = path.parent
    for _ in range(10):  # Safety bound
        if (current / "src").is_dir() and (current / "config").is_dir():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def discover_auto_commands(
    project_root: Path,
) -> dict[str, AutoCommandEntry]:
    """Scan all skills for protocol: scan-fix commands and x-augur-loop entries.

    Uses canonical skill_discovery for skill enumeration, then reads
    SKILL.md-derived metadata from each skill directory.

    Returns a registry dict keyed by command id (e.g. "auto-lint").
    Commands with missing or invalid modules are logged and skipped.
    """
    registry: dict[str, AutoCommandEntry] = {}
    all_skills: list[dict[str, Any]] = []

    # Only scan real Augur source skill dirs, not generated client exports.
    for skills_dir in get_adaptive_loop_skill_dirs(project_root):
        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.is_file():
                continue
            frontmatter = _read_frontmatter(skill_md)
            all_skills.append(
                {
                    "name": frontmatter.get("name") or skill_dir.name,
                    "path": skill_dir,
                    "commands": frontmatter.get("x-augur-commands"),
                    "loop_config": frontmatter.get("x-augur-loop") if isinstance(frontmatter.get("x-augur-loop"), dict) else {},
                }
            )

    # --- Pass 1: x-augur-commands entries with protocol: scan-fix ---
    for rec in all_skills:
        plugin_root = rec["path"]
        commands = rec["commands"] if isinstance(rec["commands"], list) else []
        if not commands:
            continue

        for cmd in commands:
            if not isinstance(cmd, dict):
                continue
            if cmd.get("protocol") != "scan-fix":
                continue

            cmd_id = cmd.get("id")
            callable_path = cmd.get("callable")
            if not cmd_id:
                logger.warning(
                    "Skipping scan-fix command in %s: missing id",
                    plugin_root / "SKILL.md",
                )
                continue

            module_path = (
                plugin_root / callable_path
                if isinstance(callable_path, str) and callable_path
                else _find_callable_script(plugin_root)
            )
            if module_path is None:
                logger.warning(
                    "Skipping %s in %s: missing callable",
                    cmd_id,
                    plugin_root / "SKILL.md",
                )
                continue
            loop_config = cmd.get("loop", {})
            if not isinstance(loop_config, dict):
                loop_config = {}

            loop_name = loop_config.get("name") or rec["loop_config"].get("name")
            if not loop_name:
                logger.warning(
                    "Skipping %s in %s: missing loop.name",
                    cmd_id,
                    plugin_root / "SKILL.md",
                )
                continue

            try:
                module = load_ops_module(module_path, project_root=project_root)
            except Exception as exc:
                logger.warning(
                    "Skipping %s: failed to load module %s: %s",
                    cmd_id,
                    module_path,
                    exc,
                )
                continue

            # Extract per-module config from loop.config block (ADR-216)
            module_config = loop_config.get("config", {})
            if not isinstance(module_config, dict):
                module_config = {}

            try:
                capabilities = coerce_ops_capabilities(getattr(module, "OPS_CAPABILITIES", None))
            except TypeError as exc:
                logger.warning(
                    "Skipping %s: invalid OPS_CAPABILITIES in %s: %s",
                    cmd_id,
                    module_path,
                    exc,
                )
                continue

            trigger = normalize_trigger(
                loop_config.get("trigger", rec["loop_config"].get("trigger", "nightly"))
            )
            registry[cmd_id] = AutoCommandEntry(
                name=cmd_id,
                module=module,
                capabilities=capabilities,
                loop_name=loop_name,
                tier=loop_config.get("tier", rec["loop_config"].get("tier", 0)),
                trigger=trigger,
                scheduler=resolve_scheduler(loop_config, rec["loop_config"]),
                plugin_root=plugin_root,
                config=module_config,
                initial_trust=float(loop_config.get("trust", rec["loop_config"].get("trust", 0.0))),
            )

    # --- Pass 2: Discover from SkillRecord.loop_config (x-augur-loop) ---
    # Uses canonical discovery data — no manual SKILL.md re-parsing needed.
    seen_ids = set(registry.keys())

    for rec in all_skills:
        loop_config = rec["loop_config"]
        if not loop_config or not isinstance(loop_config, dict):
            continue

        cmd_name = rec["name"] or rec["path"].name
        if cmd_name in seen_ids:
            continue  # Already found via x-augur-commands

        loop_name = loop_config.get("name")
        if not loop_name:
            continue

        skill_dir = rec["path"]

        # Read frontmatter for x-augur-callable resolution
        frontmatter = _read_frontmatter(skill_dir / "SKILL.md")

        # Find callable script in scripts/ directory
        callable_script = _find_callable_script(skill_dir, frontmatter=frontmatter)
        if not callable_script:
            continue

        try:
            module = load_ops_module(callable_script, project_root=project_root)
        except Exception as exc:
            logger.warning(
                "Skipping %s (SKILL.md): failed to load %s: %s",
                cmd_name, callable_script, exc,
            )
            continue

        module_config = loop_config.get("config", {})
        if not isinstance(module_config, dict):
            module_config = {}

        try:
            capabilities = coerce_ops_capabilities(getattr(module, "OPS_CAPABILITIES", None))
        except TypeError as exc:
            logger.warning(
                "Skipping %s: invalid OPS_CAPABILITIES in %s: %s",
                cmd_name,
                callable_script,
                exc,
            )
            continue

        trigger = normalize_trigger(loop_config.get("trigger", "nightly"))
        registry[cmd_name] = AutoCommandEntry(
            name=cmd_name,
            module=module,
            capabilities=capabilities,
            loop_name=loop_name,
            tier=loop_config.get("tier", 0),
            trigger=trigger,
            scheduler=resolve_scheduler(loop_config),
            plugin_root=skill_dir,
            config=module_config,
            initial_trust=float(loop_config.get("trust", 0.0)),
        )
        seen_ids.add(cmd_name)

    logger.info(
        "Discovered %d auto-commands across %d loops",
        len(registry),
        len({e.loop_name for e in registry.values()}),
    )
    return registry


def _find_callable_script(skill_dir: Path, frontmatter: dict[str, Any] | None = None) -> Path | None:
    """Find the callable script for a standalone SKILL.md auto-command.

    Resolution order:
    1. `x-augur-callable` frontmatter path
    2. First non-underscore `.py` in `scripts/`
    """
    if isinstance(frontmatter, dict):
        explicit = frontmatter.get("x-augur-callable")
        if isinstance(explicit, str) and explicit.strip():
            explicit_path = Path(explicit.strip())
            project_root = _find_project_root(skill_dir)
            candidates = []
            if explicit_path.is_absolute():
                candidates.append(explicit_path)
            else:
                candidates.append(skill_dir / explicit_path)
                if project_root is not None:
                    candidates.append(project_root / explicit_path)
            for candidate in candidates:
                if candidate.is_file():
                    return candidate.resolve()

    scripts_dir = skill_dir / "scripts"
    if not scripts_dir.exists():
        return None
    for py_file in sorted(scripts_dir.glob("*.py")):
        if py_file.name.startswith("_"):
            continue
        return py_file
    return None


def group_by_loop(
    registry: dict[str, AutoCommandEntry],
) -> dict[str, list[AutoCommandEntry]]:
    """Group auto-command entries by their loop_name, sorted by tier."""
    loops: dict[str, list[AutoCommandEntry]] = {}
    for entry in registry.values():
        loops.setdefault(entry.loop_name, []).append(entry)
    # Sort each loop's commands by tier (lower tier first)
    for loop_name in loops:
        loops[loop_name].sort(key=lambda e: e.tier)
    return loops
