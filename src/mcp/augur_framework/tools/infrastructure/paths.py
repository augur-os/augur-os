"""
Path Configuration MCP Tools.

These tools expose the dynamic path configuration system to the dashboard.
They provide access to the 4 path categories (CORE, DATA, PLUGINS, RUNTIME)
and support both monorepo and multi-repo setups.

Note: Full path configuration requires the ai kernel to be available.
In standalone mode, fallback paths are provided.
"""

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

from src.mcp.augur_shared.annotations import tool_annotations
from src.mcp.augur_shared.compat import (
    calculate_directory_size,
    get_path_config_functions,
)
from src.mcp.augur_shared.config import (
    get_cache_dir,
    get_logs_dir,
    get_memory_dir,
    get_rag_dir,
    get_state_dir,
    get_vault_dir,
)
from src.mcp.augur_shared.logging import get_entity_logger

logger = get_entity_logger("mcp")

RAG_SKILL_PATH_RE = re.compile(r"^(?P<bundle>[^/]+)/(?P<skill>[^/]+)$")
RAG_BUNDLE_PATH_RE = re.compile(r"^_bundles/(?P<bundle>[^/]+)$")


def _iter_rag_directories(rag_root: Path) -> list[tuple[str, Path]]:
    """Find centralized rag directories in ~/Library/Application Support/Augur/rag/."""
    if not rag_root.exists():
        return []

    rag_directories: list[tuple[str, Path]] = []
    seen_relative_paths: set[str] = set()

    for rag_dir in sorted(rag_root.glob("*/*")):
        if not rag_dir.is_dir():
            continue
        relative_path = rag_dir.relative_to(rag_root).as_posix()
        if relative_path in seen_relative_paths:
            continue
        match = RAG_SKILL_PATH_RE.match(relative_path)
        if not match:
            continue
        rag_directories.append((f"{match.group('bundle')}/{match.group('skill')}", rag_dir))
        seen_relative_paths.add(relative_path)

    bundles_root = rag_root / "_bundles"
    if bundles_root.exists():
        for rag_dir in sorted(bundles_root.iterdir()):
            if not rag_dir.is_dir():
                continue
            relative_path = rag_dir.relative_to(rag_root).as_posix()
            if relative_path in seen_relative_paths:
                continue
            match = RAG_BUNDLE_PATH_RE.match(relative_path)
            if not match:
                continue
            rag_directories.append((f"{match.group('bundle')} (bundle)", rag_dir))
            seen_relative_paths.add(relative_path)

    rag_directories.sort(key=lambda item: item[1].as_posix())
    return rag_directories


def _get_path_config():
    """Get path configuration, handling import errors gracefully."""
    funcs = get_path_config_functions()
    if funcs is None:
        logger.warning("Path config not available (ai kernel not installed)")
        return None, None, None

    get_config, _, check_alerts, gen_recs = funcs
    return get_config(), check_alerts, gen_recs


def register_path_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable,
    metrics: Any,
) -> None:
    """
    Register Path Configuration tools with the MCP server.

    Args:
        mcp: FastMCP server instance
        mcp_tool_interceptor: Decorator for tool interception
        metrics: MetricsTracker instance for telemetry
    """

    @mcp.tool(
        name="get-path-config",
        annotations=tool_annotations(
            {
                "title": "Get Path Configuration",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def get_path_config_tool(refresh: bool = False) -> str:
        """Get current path configuration with git topology and sizes.

        Returns the configuration for all 4 path categories:
        - CORE: Framework code
        - DATA: User data (3 folders)
        - PLUGINS: User plugins
        - RUNTIME: Logs, temp, IPC

        Args:
            refresh: Force refresh from config file

        Returns:
            str: JSON with path configuration, git topology, sizes, and alerts
        """
        metrics.track_tool("get_path_config")

        try:
            config, check_alerts, gen_recs = _get_path_config()

            if config is None:
                # Fallback to monorepo paths when config not available
                core_repo = Path(__file__).parent.parent.parent.parent.parent
                return json.dumps(
                    {
                        "success": False,
                        "error": "Path configuration not available",
                        "fallback": {
                            "core": str(core_repo),
                            "data": str(get_vault_dir()),
                            "plugins": str(core_repo / "plugins"),
                            "runtime": str(get_state_dir()),
                            "memory": str(get_memory_dir()),
                            "logs": str(get_logs_dir()),
                            "cache": str(get_cache_dir()),
                            "rag": str(get_rag_dir()),
                        },
                    }
                )

            # Refresh if requested
            if refresh:
                funcs = get_path_config_functions()
                if funcs:
                    _, refresh_config, _, _ = funcs
                    config = refresh_config()

            # Build response
            response = config.to_dict()
            response["success"] = True

            # Add RAG index info — scan per-plugin rag directories
            try:
                rag_root = get_rag_dir()
                rag_total_size = 0.0
                rag_plugin_count = 0
                rag_plugins = []

                for skill_label, rag_dir in _iter_rag_directories(rag_root):
                    size = calculate_directory_size(rag_dir)
                    rag_plugins.append(
                        {
                            "skill": skill_label,
                            "path": str(rag_dir),
                            "size_mb": round(float(size), 2),
                        }
                    )
                    rag_total_size += size
                    rag_plugin_count += 1

                response["rag_index"] = {
                    "path": str(rag_root),
                    "size_mb": round(float(rag_total_size), 2),
                    "project_count": rag_plugin_count,
                    "exists": rag_plugin_count > 0,
                    "plugins": rag_plugins,
                }
            except Exception as e:
                logger.warning(f"Failed to get RAG index info: {e}")
                response["rag_index"] = {"size_mb": 0, "project_count": 0, "exists": False}

            # Add alerts if any
            if check_alerts:
                alerts = check_alerts(config)
                response["alerts"] = [{"category": a.category, "level": a.level, "size_mb": a.size_mb} for a in alerts]

            # Add recommendations
            if gen_recs:
                recs = gen_recs(config)
                response["recommendations"] = [
                    {"id": r.id, "message": r.message, "auto_fixable": r.auto_fixable} for r in recs
                ]

            return json.dumps(response, indent=2)

        except Exception as e:
            logger.error(f"Failed to get path config: {e}")
            return json.dumps({"success": False, "error": str(e)})

    @mcp.tool(
        name="update-path-config",
        annotations=tool_annotations(
            {
                "title": "Update Path Configuration",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def update_path_config_tool(
        category: str,
        path: str,
    ) -> str:
        """Update a path category configuration.

        Args:
            category: Category to update ('core', 'data', 'plugins', 'runtime')
            path: New path for the category

        Returns:
            str: JSON with updated configuration
        """
        metrics.track_tool("update_path_config")

        try:
            funcs = get_path_config_functions()
            if funcs is None:
                return json.dumps(
                    {
                        "success": False,
                        "error": "Path configuration requires the full Augur src.",
                    }
                )

            get_path_config, refresh_path_config, _, _ = funcs

            # Validate category
            valid_categories = ["core", "data", "plugins", "runtime"]
            if category not in valid_categories:
                return json.dumps({"success": False, "error": f"Invalid category. Must be one of: {valid_categories}"})

            # Validate path exists
            new_path = Path(path).expanduser().resolve()
            if not new_path.exists():
                return json.dumps(
                    {
                        "success": False,
                        "error": f"Path does not exist: {new_path}",
                        "suggestion": "Create the directory first or use an existing path",
                    }
                )

            # Get current config
            config = get_path_config()

            # Update the category
            cat = config.get_category(category)
            if cat:
                cat.path = new_path

            # Save to project.yaml
            config.save()

            # Refresh and return new config
            new_config = refresh_path_config()

            return json.dumps(
                {
                    "success": True,
                    "message": f"Updated {category} path to {new_path}",
                    "config": new_config.to_dict(),
                },
                indent=2,
            )

        except Exception as e:
            logger.error(f"Failed to update path config: {e}")
            return json.dumps({"success": False, "error": str(e)})

    @mcp.tool(
        name="validate-paths",
        annotations=tool_annotations(
            {
                "title": "Validate Path Configuration",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def validate_paths_tool() -> str:
        """Validate all configured paths exist and are accessible.

        Checks:
        - All 4 category paths exist
        - Git topology is detected correctly
        - Runtime is gitignored (if applicable)

        Returns:
            str: JSON with validation results
        """
        metrics.track_tool("validate_paths")

        try:
            config, check_alerts, gen_recs = _get_path_config()

            if config is None:
                return json.dumps({"success": False, "error": "Path configuration not available"})

            results: dict[str, Any] = {"success": True, "categories": {}, "issues": [], "warnings": []}

            # Check each category
            for cat in config.categories:
                cat_result = {
                    "path": str(cat.path),
                    "exists": cat.path.exists(),
                    "git_root": str(cat.git_root) if cat.git_root else None,
                    "size_mb": cat.size_mb,
                    "gitignored": cat.gitignored,
                }

                if not cat.path.exists():
                    results["issues"].append(f"{cat.id}: Path does not exist: {cat.path}")
                    results["success"] = False

                if cat.id == "runtime" and cat.git_root and not cat.gitignored:
                    results["warnings"].append("runtime: Path is tracked by git but should be gitignored")

                results["categories"][cat.id] = cat_result

            # Add topology info
            results["topology"] = {
                "is_monorepo": config.is_monorepo,
                "repo_count": config.repo_count,
                "git_roots": [str(r) for r in config.unique_git_roots],
            }

            return json.dumps(results, indent=2)

        except Exception as e:
            logger.error(f"Failed to validate paths: {e}")
            return json.dumps({"success": False, "error": str(e)})

    @mcp.tool(
        name="get-path-sizes",
        annotations=tool_annotations(
            {
                "title": "Get Path Sizes",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def get_path_sizes_tool() -> str:
        """Get size information for all path categories.

        Returns:
            str: JSON with sizes and any alerts
        """
        metrics.track_tool("get_path_sizes")

        try:

            config, check_alerts, _ = _get_path_config()

            if config is None:
                return json.dumps({"success": False, "error": "Path configuration not available"})

            # Refresh sizes
            config.refresh_sizes()

            sizes: dict[str, Any] = {
                "categories": {},
                "total_mb": 0,
                "alerts": [],
            }

            for cat in config.categories:
                sizes["categories"][cat.id] = {
                    "path": str(cat.path),
                    "size_mb": round(cat.size_mb, 2),
                }
                sizes["total_mb"] += cat.size_mb

            sizes["total_mb"] = round(sizes["total_mb"], 2)

            # Check for alerts
            if check_alerts:
                alerts = check_alerts(config)
                sizes["alerts"] = [{"category": a.category, "level": a.level, "size_mb": a.size_mb} for a in alerts]

            # Check for large files
            for cat in config.categories:
                if cat.path.exists():
                    for file in cat.path.rglob("*"):
                        if file.is_file():
                            try:
                                file_mb = file.stat().st_size / (1024 * 1024)
                                if file_mb > config.alerts.large_file_mb:
                                    rel_path = file.relative_to(cat.path)
                                    sizes["alerts"].append(
                                        {
                                            "category": f"{cat.id}/{rel_path}",
                                            "level": "large_file",
                                            "size_mb": round(file_mb, 2),
                                        }
                                    )
                            except (OSError, ValueError):
                                pass

            return json.dumps(sizes, indent=2)

        except Exception as e:
            logger.error(f"Failed to get path sizes: {e}")
            return json.dumps({"success": False, "error": str(e)})

    @mcp.tool(
        name="cleanup-path",
        annotations=tool_annotations(
            {
                "title": "Cleanup Path Category",
                "readOnlyHint": False,
                "destructiveHint": True,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def cleanup_path_tool(
        category: str,
        dry_run: bool = True,
    ) -> str:
        """Clean up a path category by removing temporary and cache files.

        Cleans:
        - runtime: logs older than 7 days, temp files, cache
        - data: empty directories, orphaned files
        - rag_index: stale indexes, orphaned project dirs

        Args:
            category: Category to clean ('runtime', 'data', 'rag_index', 'all')
            dry_run: If True, only report what would be cleaned (default: True)

        Returns:
            str: JSON with cleanup results
        """
        import shutil
        from datetime import datetime, timedelta

        metrics.track_tool("cleanup_path")

        try:
            config, _, _ = _get_path_config()

            if config is None:
                return json.dumps({"success": False, "error": "Path configuration not available"})

            results: dict[str, Any] = {
                "success": True,
                "dry_run": dry_run,
                "cleaned": [],
                "freed_mb": 0.0,
                "errors": [],
            }

            def cleanup_runtime():
                """Clean runtime directory."""
                runtime_path = config.runtime.path
                if not runtime_path.exists():
                    return

                freed = 0.0
                cutoff = datetime.now() - timedelta(days=7)

                # Clean old logs
                logs_dir = runtime_path / "logs"
                if logs_dir.exists():
                    for log_file in logs_dir.glob("*.log*"):
                        try:
                            mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                            if mtime < cutoff:
                                size_mb = log_file.stat().st_size / (1024 * 1024)
                                if not dry_run:
                                    log_file.unlink()
                                freed += size_mb
                                results["cleaned"].append(f"logs/{log_file.name}")
                        except Exception as e:
                            results["errors"].append(f"Failed to clean {log_file}: {e}")

                # Clean temp directory
                temp_dir = runtime_path / "temp"
                if temp_dir.exists():
                    for item in temp_dir.iterdir():
                        try:
                            if item.is_file():
                                size_mb = item.stat().st_size / (1024 * 1024)
                                if not dry_run:
                                    item.unlink()
                                freed += size_mb
                            elif item.is_dir():
                                size_mb = calculate_directory_size(item)
                                if not dry_run:
                                    shutil.rmtree(item)
                                freed += size_mb
                            results["cleaned"].append(f"state/temp/{item.name}")
                        except Exception as e:
                            results["errors"].append(f"Failed to clean {item}: {e}")

                # Clean cache directory
                cache_dir = runtime_path / "cache"
                if cache_dir.exists():
                    for item in cache_dir.iterdir():
                        try:
                            mtime = datetime.fromtimestamp(item.stat().st_mtime)
                            if mtime < cutoff:
                                if item.is_file():
                                    size_mb = item.stat().st_size / (1024 * 1024)
                                    if not dry_run:
                                        item.unlink()
                                elif item.is_dir():
                                    size_mb = calculate_directory_size(item)
                                    if not dry_run:
                                        shutil.rmtree(item)
                                freed += size_mb
                                results["cleaned"].append(f"state/cache/{item.name}")
                        except Exception as e:
                            results["errors"].append(f"Failed to clean {item}: {e}")

                return freed

            def cleanup_rag_index():
                """Clean RAG indexes — scan per-plugin rag directories."""
                rag_root = get_rag_dir()
                if not rag_root.exists():
                    return 0.0

                freed = 0.0

                for skill_label, rag_dir in _iter_rag_directories(rag_root):
                    cache_dir = rag_dir / "cache"
                    if cache_dir.exists():
                        try:
                            size_mb = calculate_directory_size(cache_dir)
                            if not dry_run:
                                shutil.rmtree(cache_dir)
                            freed += size_mb
                            results["cleaned"].append(f"rag_index/{skill_label}/cache")
                        except Exception as e:
                            results["errors"].append(f"Failed to clean {cache_dir}: {e}")

                return freed

            def cleanup_data():
                """Clean data directory - remove empty directories."""
                data_path = config.data.path
                if not data_path.exists():
                    return 0.0

                freed = 0.0

                # Remove empty directories (excluding .git-related)
                for root, dirs, files in data_path.walk(top_down=False):
                    root_path = Path(root)
                    if ".git" in root_path.parts:
                        continue

                    if not files and not dirs:
                        try:
                            if not dry_run:
                                root_path.rmdir()
                            results["cleaned"].append(f"data/{root_path.relative_to(data_path)} (empty)")
                        except OSError as error:
                            logger.debug("Skipping directory cleanup for %s: %s", root_path, error)

                return freed

            # Execute cleanup based on category
            if category in ("runtime", "all"):
                results["freed_mb"] += cleanup_runtime()

            if category in ("rag_index", "all"):
                results["freed_mb"] += cleanup_rag_index()

            if category in ("data", "all"):
                results["freed_mb"] += cleanup_data()

            results["freed_mb"] = round(float(results["freed_mb"]), 2)

            return json.dumps(results, indent=2)

        except Exception as e:
            logger.error(f"Failed to cleanup path: {e}")
            return json.dumps({"success": False, "error": str(e)})


__all__ = ["register_path_tools"]
