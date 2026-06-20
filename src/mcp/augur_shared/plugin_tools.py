"""
Dynamic MCP Tool Loading from Skills.

Skills can provide MCP tools by creating:
    project-brain/capabilities/skills/{skill}/scripts/mcp/__init__.py

With a register_tools(mcp, interceptor, metrics) function.

This enables community plugins to provide their own backend tools
without modifying the core framework.

Part of ADR-012: Community Package Extraction
"""

from __future__ import annotations

import functools
import hashlib
import importlib.abc
import importlib.machinery
import importlib.util
import inspect
import os
import shutil
import sys
import threading
import types
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.config.paths import (
    get_managed_skill_source_dirs,
    project_tier_skill_source_dirs,
)
from src.mcp.augur_shared.config import get_project_root as get_mcp_project_root
from src.plugins.skill_ui_state import is_skill_enabled

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

from src.mcp.augur_shared.logging import get_entity_logger

# The SDK pinner moved to augur_shared.mcp_sdk in Track 3a PR 1; re-import
# the helpers here so existing callers that reach into this module
# (`from ...plugin_tools import _pin_mcp_sdk_package`) keep working.
from src.mcp.augur_shared.mcp_sdk import (  # noqa: F401
    _is_managed_skill_import_path,
    _module_is_managed_skill_import,
    _pin_mcp_sdk_package,
)

logger = get_entity_logger("mcp.plugins")

# Track loaded plugins to avoid double-registration
_loaded_plugins: set[str] = set()

# Track plugins that failed to load (skill_name -> error message)
_failed_plugins: dict[str, str] = {}

_bundle_import_lock = threading.RLock()


def allowed_generated_names(
    capability_type: str,
    names: list[str],
    target: str,
    existing_names: set[str],
) -> set[str]:
    """Return policy-allowed generated names, imported lazily for MCP startup."""
    from src.lib.capabilities.export_filter import allowed_generated_names as allowed

    return allowed(capability_type, names, target, existing_names)


def allowed_mcp_runtime_tool_names(names: list[str], target: str = "mcp") -> set[str]:
    """Return MCP tools explicitly approved for runtime registration."""
    from src.lib.capabilities.export_filter import (
        allowed_mcp_runtime_tool_names as allowed,
    )

    return allowed(names, target=target)


@functools.lru_cache(maxsize=2048)
def _mcp_tool_policy_allows_runtime_registration(tool_name: str, target: str) -> bool:
    """Return whether the generated MCP runtime may register ``tool_name``."""
    cleaned = str(tool_name or "").strip()
    if not cleaned:
        return True
    policy_target = str(target or "mcp").strip() or "mcp"

    try:
        allowed = allowed_mcp_runtime_tool_names([cleaned], target=policy_target)
    except Exception:  # noqa: BLE001
        logger.warning(
            "Capability policy filtering failed for MCP tool %s; preserving runtime registration",
            cleaned,
            exc_info=True,
        )
        return True
    return cleaned in allowed


class _PolicyFilteredMCP:
    """Proxy FastMCP tool registration through the capability exposure policy."""

    def __init__(self, mcp: FastMCP, *, skill_name: str, target: str) -> None:
        object.__setattr__(self, "_mcp", mcp)
        object.__setattr__(self, "_skill_name", skill_name)
        object.__setattr__(self, "_target", target)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._mcp, name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name in {"_mcp", "_skill_name", "_target"}:
            object.__setattr__(self, name, value)
            return
        setattr(self._mcp, name, value)

    def tool(self, name: Any = None, *args: Any, **kwargs: Any) -> Any:
        """Wrap ``FastMCP.tool`` and skip policy-denied generated tools."""
        if callable(name) and not args and not kwargs:
            return self._decorate_tool(name, None, (), {})

        def decorator(func: Callable[..., Any]) -> Any:
            return self._decorate_tool(func, name, args, kwargs)

        return decorator

    def _decorate_tool(
        self,
        func: Callable[..., Any],
        name: Any,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> Any:
        tool_name = str(name or getattr(func, "__name__", "")).strip()
        if not _mcp_tool_policy_allows_runtime_registration(tool_name, self._target):
            logger.info(
                "Skipping MCP tool %s from %s due to capability exposure policy",
                tool_name,
                self._skill_name,
            )
            return func
        return self._mcp.tool(name, *args, **kwargs)(func)


def create_capability_policy_filtered_mcp(
    mcp: FastMCP,
    *,
    source_name: str,
    target: str = "mcp",
) -> _PolicyFilteredMCP:
    """Return an MCP proxy that filters tool registration through policy."""
    return _PolicyFilteredMCP(mcp, skill_name=source_name, target=target)


def reset_capability_policy_filter_cache() -> None:
    """Clear the runtime capability policy decision cache."""
    _mcp_tool_policy_allows_runtime_registration.cache_clear()
    try:
        from src.lib.capabilities.export_filter import reset_export_filter_cache

        reset_export_filter_cache()
    except Exception:  # noqa: BLE001
        logger.debug("Could not reset capability export filter cache", exc_info=True)


def _remove_bundle_local_sys_path(skill_dir: Path) -> None:
    """Remove bundle-local import paths without disturbing managed parents."""
    local_paths = {
        str(skill_dir.resolve()),
        str((skill_dir / "scripts").resolve()),
    }
    sys.path[:] = [entry for entry in sys.path if entry not in local_paths]


def _bundle_module_spec(
    parent_name: str,
    skill_dir: Path,
    fullname: str,
) -> importlib.machinery.ModuleSpec | None:
    """Create a spec for a synthetic bundle module under ``parent_name``."""
    if fullname != parent_name and not fullname.startswith(f"{parent_name}."):
        return None

    suffix = fullname[len(parent_name) :].lstrip(".")
    parts = suffix.split(".") if suffix else []
    scripts_dir = skill_dir / "scripts"
    module_base = scripts_dir.joinpath(*parts)

    package_init = module_base / "__init__.py"
    if package_init.is_file():
        loader = _BundleSyntheticLoader(fullname, str(package_init), parent_name, skill_dir)
        return importlib.util.spec_from_file_location(
            fullname,
            package_init,
            loader=loader,
            submodule_search_locations=[str(module_base)],
        )

    module_file = module_base.with_suffix(".py")
    if module_file.is_file():
        loader = _BundleSyntheticLoader(fullname, str(module_file), parent_name, skill_dir)
        return importlib.util.spec_from_file_location(fullname, module_file, loader=loader)

    if fullname == parent_name and scripts_dir.is_dir():
        spec = importlib.machinery.ModuleSpec(fullname, None, is_package=True)
        spec.submodule_search_locations = [str(scripts_dir)]
        return spec

    return None


class _BundleSyntheticLoader(importlib.machinery.SourceFileLoader):
    """Loader that installs bundle-local import builtins before execution."""

    def __init__(self, fullname: str, path: str, parent_name: str, skill_dir: Path):
        super().__init__(fullname, path)
        self._parent_name = parent_name
        self._skill_dir = skill_dir

    def exec_module(self, module: Any) -> None:
        _install_bundle_import_alias(module, self._parent_name, self._skill_dir)
        super().exec_module(module)
        _install_bundle_import_aliases(self._parent_name, self._skill_dir)

    def get_code(self, fullname: str) -> Any:
        """Compile from source so repeated bundle loads see changed files."""
        path = self.get_filename(fullname)
        source_bytes = self.get_data(path)
        return self.source_to_code(source_bytes, path)


class _BundleSyntheticFinder(importlib.abc.MetaPathFinder):
    """Find synthetic bundle modules without exposing top-level ``scripts``."""

    def __init__(self, parent_name: str, skill_dir: Path):
        self._parent_name = parent_name
        self._skill_dir = skill_dir

    def find_spec(
        self,
        fullname: str,
        path: Any = None,
        target: Any = None,
    ) -> importlib.machinery.ModuleSpec | None:
        return _bundle_module_spec(self._parent_name, self._skill_dir, fullname)


@contextmanager
def _bundle_synthetic_imports(parent_name: str, skill_dir: Path):
    """Temporarily install a finder for synthetic bundle modules only."""
    finder = _BundleSyntheticFinder(parent_name, skill_dir)
    with _bundle_import_lock:
        sys.meta_path.insert(0, finder)
    try:
        yield
    finally:
        with _bundle_import_lock:
            sys.meta_path = [entry for entry in sys.meta_path if entry is not finder]


def _make_bundle_import(
    skill_dir: Path,
    parent_name: str,
    base_import: Callable[..., Any],
) -> Callable[..., Any]:
    """Map bundle-local absolute ``scripts.*`` imports to the synthetic package."""

    def attach_child(mapped_name: str) -> None:
        if "." not in mapped_name:
            return
        parent_module_name, child_name = mapped_name.rsplit(".", 1)
        parent_module = sys.modules.get(parent_module_name)
        child_module = sys.modules.get(mapped_name)
        if parent_module is not None and child_module is not None:
            setattr(parent_module, child_name, child_module)

    def bundle_import(
        name: str,
        globals: dict[str, Any] | None = None,
        locals: dict[str, Any] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> Any:
        if level == 0 and (name == "scripts" or name.startswith("scripts.")):
            suffix = name[len("scripts") :]
            mapped_name = f"{parent_name}{suffix}"
            with _bundle_synthetic_imports(parent_name, skill_dir):
                module = importlib.import_module(mapped_name)
            attach_child(mapped_name)
            _install_bundle_import_aliases(parent_name, skill_dir)
            if name == "scripts" and fromlist:
                for item in fromlist:
                    if item == "*":
                        continue
                    with _bundle_synthetic_imports(parent_name, skill_dir):
                        child = importlib.import_module(f"{parent_name}.{item}")
                    attach_child(f"{parent_name}.{item}")
                    setattr(module, item, child)
            elif not fromlist and name.startswith("scripts."):
                module = importlib.import_module(parent_name)
            return module
        return base_import(name, globals, locals, fromlist, level)

    return bundle_import


def _install_bundle_import_aliases(parent_name: str, skill_dir: Path) -> None:
    """Install bundle-local import builtins on synthetic bundle modules."""
    for module_name, module in list(sys.modules.items()):
        if module_name != parent_name and not module_name.startswith(f"{parent_name}."):
            continue
        _install_bundle_import_alias(module, parent_name, skill_dir)


def _install_bundle_import_alias(module: Any, parent_name: str, skill_dir: Path) -> None:
    """Install a bundle-local import builtin on one module."""
    builtins_obj = getattr(module, "__builtins__", __builtins__)
    if isinstance(builtins_obj, dict):
        builtins_dict = dict(builtins_obj)
        base_import = builtins_obj.get("__augur_base_import__", builtins_obj.get("__import__", __import__))
    else:
        builtins_dict = dict(vars(builtins_obj))
        base_import = getattr(builtins_obj, "__augur_base_import__", getattr(builtins_obj, "__import__", __import__))
    builtins_dict["__augur_base_import__"] = base_import
    builtins_dict["__import__"] = _make_bundle_import(skill_dir, parent_name, base_import)
    module.__builtins__ = builtins_dict


def _rebind_function_bundle_imports(
    func: Callable[..., Any],
    parent_name: str,
    skill_dir: Path,
) -> Callable[..., Any]:
    """Return ``func`` with globals that use the bundle import mapper."""
    builtins_obj = func.__globals__.get("__builtins__", __builtins__)
    if isinstance(builtins_obj, dict):
        builtins_dict = dict(builtins_obj)
        base_import = builtins_obj.get("__augur_base_import__", builtins_obj.get("__import__", __import__))
    else:
        builtins_dict = dict(vars(builtins_obj))
        base_import = getattr(builtins_obj, "__augur_base_import__", getattr(builtins_obj, "__import__", __import__))
    builtins_dict["__augur_base_import__"] = base_import
    builtins_dict["__import__"] = _make_bundle_import(skill_dir, parent_name, base_import)

    globals_copy = dict(func.__globals__)
    globals_copy["__builtins__"] = builtins_dict

    def clone_function(source: Callable[..., Any]) -> Callable[..., Any]:
        cloned = types.FunctionType(
            source.__code__,
            globals_copy,
            source.__name__,
            source.__defaults__,
            source.__closure__,
        )
        cloned.__kwdefaults__ = getattr(source, "__kwdefaults__", None)
        cloned.__annotations__ = dict(getattr(source, "__annotations__", {}))
        cloned.__dict__.update(getattr(source, "__dict__", {}))
        return functools.update_wrapper(cloned, source)

    for name, value in func.__globals__.items():
        if isinstance(value, types.FunctionType) and value.__globals__ is func.__globals__:
            globals_copy[name] = clone_function(value)

    rebound = clone_function(func)
    return functools.update_wrapper(rebound, func)


def _bundle_tool_interceptor(
    skill_dir: Path,
    parent_name: str,
    mcp_tool_interceptor: Callable[..., Any],
) -> Callable[[Callable[..., Any]], Any]:
    """Wrap tool execution so lazy bundle-local ``scripts.*`` imports work."""

    def decorator(func: Callable[..., Any]) -> Any:
        bundle_func = _rebind_function_bundle_imports(func, parent_name, skill_dir)

        @functools.wraps(func)
        async def bundle_wrapped(*args: Any, **kwargs: Any) -> Any:
            try:
                with _bundle_synthetic_imports(parent_name, skill_dir):
                    result = bundle_func(*args, **kwargs)
                if inspect.isawaitable(result):
                    with _bundle_synthetic_imports(parent_name, skill_dir):
                        return await result
                return result
            finally:
                _remove_bundle_local_sys_path(skill_dir)

        bundle_wrapped.__wrapped__ = bundle_func
        return mcp_tool_interceptor(bundle_wrapped)

    return decorator


def _register_bundle_tools(
    module: Any,
    skill_dir: Path,
    mcp: FastMCP,
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
    *,
    target: str = "mcp",
) -> None:
    """Register a bundle's tools with bundle-local import context."""
    parent_name = module.__name__.split(".", 1)[0]
    bundle_interceptor = _bundle_tool_interceptor(skill_dir, parent_name, mcp_tool_interceptor)
    filtered_mcp = _PolicyFilteredMCP(mcp, skill_name=skill_dir.name, target=target)
    try:
        with _bundle_synthetic_imports(parent_name, skill_dir):
            module.register_tools(filtered_mcp, bundle_interceptor, metrics)
        _install_bundle_import_aliases(parent_name, skill_dir)
    finally:
        _remove_bundle_local_sys_path(skill_dir)


def _clear_bundle_modules(parent_name: str) -> None:
    """Remove cached synthetic bundle modules before loading bundle code."""
    for module_name in [name for name in sys.modules if name == parent_name or name.startswith(f"{parent_name}.")]:
        sys.modules.pop(module_name, None)


def _clear_absolute_skill_modules(skill_name: str) -> None:
    """Remove cached absolute ``skills.<bundle>`` modules for this bundle only."""
    package_name = f"skills.{skill_name}"
    for module_name in [name for name in sys.modules if name == package_name or name.startswith(f"{package_name}.")]:
        sys.modules.pop(module_name, None)


def _remove_bundle_pycache(skill_dir: Path) -> None:
    """Remove bundle bytecode caches so fast repeated reloads see source edits."""
    for pycache_dir in (skill_dir / "scripts").rglob("__pycache__"):
        shutil.rmtree(pycache_dir, ignore_errors=True)


def _runtime_skill_source_dirs(project_root: Path) -> list[Path]:
    """Return runtime skill roots in managed shared/private authority order."""
    return list(get_managed_skill_source_dirs(project_root))


def _env_flag_enabled(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def get_failed_plugins() -> dict[str, str]:
    """Return a copy of the failed plugin registry."""
    return dict(_failed_plugins)


def get_all_plugin_dirs() -> list[Path]:
    """Return managed skill roots for backward compat."""
    project_root = get_mcp_project_root()
    return [skills_dir for skills_dir in _runtime_skill_source_dirs(project_root) if skills_dir.exists()]


def _collect_skill_dirs(
    *,
    apply_exclusions: bool = True,
    apply_monolith_exclusions: bool = True,
    scope: str = "all",
) -> list[tuple[str, Path]]:
    """Collect all skill directories as (plugin_id, skill_dir) tuples.

    Scans managed skill roots. Shared-vault skills have precedence over
    private-vault skills with the same name because ``get_managed_skill_source_dirs`` returns
    roots in authority order.

    Args:
        apply_exclusions: When True (default), drop bundles listed in
            ``config/system/mcp_servers.yaml`` ``monolith_exclusions``.
            The per-bundle launcher (`augur_mcp.bundle_server`) sets this
            to False so it can resolve excluded bundles by name.
        apply_monolith_exclusions: When False, keep split-server bundles while
            still applying platform compatibility exclusions. The in-process
            CLI runtime uses this so `aug <tool>` can reach CLI-approved tools
            from bundles that are excluded from the MCP monolith.
        scope: ``"all"`` (default) scans every managed skill root, including
            the private vault. ``"project"`` restricts to project-tier roots
            (project-brain only), so the project-tier ``augur-framework``
            monolith never loads private vault skills — those are served only
            by dedicated vault-tier ``bundle_server`` instances. See ADR-795.
    """
    result: list[tuple[str, Path]] = []
    seen_names: set[str] = set()

    project_root = get_mcp_project_root()
    source_dirs = (
        project_tier_skill_source_dirs(project_root) if scope == "project" else _runtime_skill_source_dirs(project_root)
    )
    for skills_dir in source_dirs:
        if not skills_dir.is_dir():
            continue
        for skill_dir in skills_dir.iterdir():
            if not skill_dir.is_dir() or skill_dir.name.startswith("."):
                continue
            if skill_dir.name in seen_names:
                continue
            seen_names.add(skill_dir.name)
            # Hubs were retired (ADR-802); skills no longer declare a bundle.
            plugin_id = f"unknown/{skill_dir.name}"
            result.append((plugin_id, skill_dir))

    if apply_exclusions:
        try:
            from src.cli_config.manifest import load_manifest

            manifest = load_manifest()
            excluded = {entry.bundle for entry in manifest.vault_tier if entry.bundle and not entry.supports_platform()}
            if apply_monolith_exclusions and not _env_flag_enabled("AUGUR_MCP_INCLUDE_VAULT_TIER_TOOLS"):
                excluded.update(manifest.monolith_exclusions)
            if excluded:
                result = [(pid, sd) for (pid, sd) in result if sd.name not in excluded]
        except FileNotFoundError:
            # Manifest not yet committed (e.g., during PR 0). Skip exclusions.
            pass
        except Exception as exc:  # noqa: BLE001
            # Manifest exists but is malformed — log and continue without exclusions.
            logger.warning(f"Could not apply monolith_exclusions from manifest: {exc}")

    return result


def _load_bundle_mcp_module(skill_dir: Path) -> Any:
    """Load and return the bundle's scripts/mcp/__init__.py as a module.

    Sets up a synthetic parent package so relative imports like ``from ..foo``
    in scripts/mcp/*.py resolve to scripts/foo.py within the bundle.

    Used by both ``register_plugin_tools`` (monolith) and
    ``bundle_server.run()`` (per-bundle stdio launcher).
    """
    safe_name = skill_dir.name.replace("-", "_")
    source_hash = hashlib.sha1(str(skill_dir.resolve()).encode("utf-8"), usedforsecurity=False).hexdigest()[:10]
    parent_name = f"plugin_scripts_{safe_name}_{source_hash}"
    module_name = f"{parent_name}.mcp"

    project_root = get_mcp_project_root()
    resolved_skill_dir = skill_dir.resolve()
    skills_root = skill_dir.parent.resolve()
    skills_parent = skills_root.parent

    # Shared-vault is the canonical team skill root, but vault-tier bundles may
    # still use absolute `from skills.<name>.X` imports. Install managed
    # parents as one stable authority-ordered block.
    import_parents: list[Path] = []
    temporary_import_parents: list[Path] = []
    seen_import_parents: set[Path] = set()
    for managed_root in _runtime_skill_source_dirs(project_root):
        resolved_root = managed_root.resolve()
        if resolved_root.name != "skills":
            continue
        parent = resolved_root.parent
        if parent not in seen_import_parents:
            import_parents.append(parent)
            seen_import_parents.add(parent)

    # Ad-hoc/test bundles under <parent>/skills/<bundle> may still rely on
    # top-level `skills.<bundle>` imports while loading, but only configured
    # managed parents should persist after the load.
    if (
        skills_root.name == "skills"
        and resolved_skill_dir.is_relative_to(skills_root)
        and skills_parent not in seen_import_parents
    ):
        temporary_import_parents.append(skills_parent)

    original_sys_path = list(sys.path)
    if import_parents or temporary_import_parents:
        ordered = [str(parent) for parent in [*import_parents, *temporary_import_parents]]
        sys.path[:] = ordered + [entry for entry in sys.path if entry not in ordered]

    try:
        _clear_bundle_modules(parent_name)
        _clear_absolute_skill_modules(skill_dir.name)
        _remove_bundle_pycache(skill_dir)
        importlib.invalidate_caches()
        with _bundle_synthetic_imports(parent_name, skill_dir):
            importlib.import_module(parent_name)
            module = importlib.import_module(module_name)
        _install_bundle_import_aliases(parent_name, skill_dir)
        return module
    finally:
        _remove_bundle_local_sys_path(skill_dir)
        for parent in temporary_import_parents:
            parent_text = str(parent)
            if parent_text not in original_sys_path:
                sys.path[:] = [entry for entry in sys.path if entry != parent_text]


def register_plugin_tools(
    mcp: FastMCP,
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
    *,
    capability_target: str | None = None,
) -> int:
    """
    Dynamically load and register MCP tools from plugins.

    Scans all plugin directories (legacy and client-native) for skills
    with scripts/mcp/__init__.py and calls their register_tools() function.

    Args:
        mcp: FastMCP server instance
        mcp_tool_interceptor: Tool interceptor for metrics/logging
        metrics: Metrics collector

    Returns:
        Number of plugins that provided tools
    """
    global _loaded_plugins

    _pin_mcp_sdk_package()
    target = capability_target or str(getattr(mcp, "_target", "") or "mcp")

    loaded_count = 0
    # The project-tier monolith never loads private vault skills; they are
    # served only by dedicated vault-tier servers (ADR-795). This applies to
    # every consumer of the monolith — AI clients, the dashboard bridge, and
    # the in-process `aug` CLI runtime alike.
    skill_entries = _collect_skill_dirs(
        apply_monolith_exclusions=target != "cli",
        scope="project",
    )

    logger.info(f"Scanning {len(skill_entries)} skill directories for MCP tools...")

    for plugin_id, skill_dir in skill_entries:
        if not is_skill_enabled(skill_dir.name):
            logger.debug(f"Skipping {plugin_id} (skill disabled via local skill state)")
            continue

        mcp_init = skill_dir / "scripts" / "mcp" / "__init__.py"
        if not mcp_init.exists():
            continue

        # Skip if already loaded (user plugins override core)
        if plugin_id in _loaded_plugins:
            logger.debug(f"Skipping {plugin_id} (already loaded)")
            continue

        try:
            module = _load_bundle_mcp_module(skill_dir)

            # Call register_tools if it exists
            if hasattr(module, "register_tools"):
                logger.info(f"Loading MCP tools from {plugin_id}")
                _register_bundle_tools(
                    module,
                    skill_dir,
                    mcp,
                    mcp_tool_interceptor,
                    metrics,
                    target=target,
                )
                _loaded_plugins.add(plugin_id)
                loaded_count += 1
            else:
                message = f"Plugin {plugin_id} has an MCP entrypoint but no register_tools()"
                _failed_plugins[plugin_id] = message
                logger.warning(message)

        except Exception as e:
            _failed_plugins[plugin_id] = str(e)
            logger.warning(f"Failed to load MCP tools from {plugin_id}: {e}")
            import traceback

            logger.debug(traceback.format_exc())

    logger.info(f"Loaded MCP tools from {loaded_count} plugins")
    return loaded_count


def reset_plugin_registry() -> None:
    """Reset the loaded plugins registry. Useful for testing."""
    global _loaded_plugins, _failed_plugins
    _loaded_plugins = set()
    _failed_plugins = {}
    reset_capability_policy_filter_cache()


__all__ = [
    "register_plugin_tools",
    "get_all_plugin_dirs",
    "reset_plugin_registry",
    "get_failed_plugins",
    "create_capability_policy_filtered_mcp",
    "reset_capability_policy_filter_cache",
    "_collect_skill_dirs",
    "_load_bundle_mcp_module",
    "_register_bundle_tools",
    "_pin_mcp_sdk_package",
]
