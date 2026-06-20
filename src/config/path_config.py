#!/usr/bin/env python3
"""
Dynamic Path Configuration System.

Provides a unified configuration for the 4 primary path categories:
- CORE: Framework code in the repository
- DATA: External user content (vault/documents/rag)
- PLUGINS: Plugin bundles in the repository
- RUNTIME: External state/logs/cache storage

ADR-270 moved mutable data and state/log/cache storage out of repo-local
plugin folders. This module reflects the canonical split layout.
"""

from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from subprocess import CompletedProcess, SubprocessError, run  # nosec B404
from typing import Optional

from src.config.paths import (
    get_cache_dir,
    get_documents_dir,
    get_ipc_dir,
    get_logs_dir,
    get_project_brain_skills_dir,
    get_project_root,
    get_rag_dir,
    get_runtime_dir,
    get_vault_dir,
)

# Cache for path config
_path_config: Optional["PathConfig"] = None


def get_monorepo_root() -> Path:
    """Get the monorepo root directory using the canonical path helper."""
    return get_project_root()


@dataclass
class SizeAlert:
    """Alert for size threshold violations."""

    category: str
    level: str  # 'warning', 'critical', 'large_file'
    size_mb: float


@dataclass
class Recommendation:
    """Recommendation for path configuration."""

    id: str
    message: str
    auto_fixable: bool = False


@dataclass
class AlertThresholds:
    """Size alert thresholds."""

    warning_mb: float = 500.0
    critical_mb: float = 1000.0
    large_file_mb: float = 50.0


@dataclass
class PathCategory:
    """A single path category with metadata."""

    id: str  # 'core', 'data', 'plugins', 'runtime'
    path: Path
    git_root: Optional[Path] = None
    size_mb: float = 0.0
    gitignored: bool = False
    subdirs: list[str] = field(default_factory=list)

    def __post_init__(self):
        """Resolve path and detect git root."""
        if isinstance(self.path, str):
            self.path = Path(self.path).expanduser().resolve()
        if self.git_root is None:
            self.git_root = find_git_root(self.path)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "path": str(self.path),
            "git_root": str(self.git_root) if self.git_root else None,
            "size_mb": self.size_mb,
            "gitignored": self.gitignored,
            "subdirs": self.subdirs,
        }

    def exists(self) -> bool:
        """Check if the path exists."""
        return self.path.exists()


def _unique_paths(*paths: Path | str) -> list[Path]:
    unique: list[Path] = []
    seen: set[Path] = set()
    for raw in paths:
        path = raw if isinstance(raw, Path) else Path(raw)
        resolved = path.expanduser().resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(resolved)
    return unique


def _category_locations(category: PathCategory) -> list[Path]:
    return _unique_paths(category.path, *category.subdirs)


def is_migration_in_progress() -> bool:
    """Check if a repository migration is currently in progress."""
    try:
        flag_file = get_runtime_dir() / "MIGRATION_IN_PROGRESS"
        return flag_file.exists()
    except Exception:
        return False


@dataclass
class PathConfig:
    """Complete path configuration for all categories."""

    core: PathCategory
    data: PathCategory
    plugins: PathCategory
    runtime: PathCategory
    alerts: AlertThresholds = field(default_factory=AlertThresholds)

    @property
    def is_monorepo(self) -> bool:
        """True if all paths share the same .git root."""
        roots = {c.git_root for c in self.categories if c.git_root}
        return len(roots) == 1

    @property
    def repo_count(self) -> int:
        """Number of distinct git repositories."""
        roots = {c.git_root for c in self.categories if c.git_root}
        return len(roots)

    @property
    def categories(self) -> list[PathCategory]:
        """All path categories."""
        return [self.core, self.data, self.plugins, self.runtime]

    @property
    def unique_git_roots(self) -> list[Path]:
        """Get unique git roots across all categories."""
        seen = set()
        roots = []
        for cat in self.categories:
            if cat.git_root and cat.git_root not in seen:
                seen.add(cat.git_root)
                roots.append(cat.git_root)
        return roots

    def get_category(self, category_id: str) -> Optional[PathCategory]:
        """Get a category by ID."""
        for cat in self.categories:
            if cat.id == category_id:
                return cat
        return None

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "core": self.core.to_dict(),
            "data": self.data.to_dict(),
            "plugins": self.plugins.to_dict(),
            "runtime": self.runtime.to_dict(),
            "is_monorepo": self.is_monorepo,
            "repo_count": self.repo_count,
            "alerts": {
                "warning_mb": self.alerts.warning_mb,
                "critical_mb": self.alerts.critical_mb,
                "large_file_mb": self.alerts.large_file_mb,
            },
        }

    def refresh_sizes(self) -> None:
        """Recalculate sizes for all categories."""
        for cat in self.categories:
            cat.size_mb = sum(
                calculate_directory_size(location) for location in _category_locations(cat) if location.exists()
            )

    def refresh_gitignored(self) -> None:
        """Check if paths are gitignored."""
        for cat in self.categories:
            cat.gitignored = bool(cat.git_root and is_path_gitignored(cat.path, cat.git_root))

    @classmethod
    def defaults(cls) -> "PathConfig":
        """Create default configuration for the ADR-270 split layout."""
        return cls(
            core=PathCategory(id="core", path=get_project_root()),
            data=PathCategory(
                id="data",
                path=get_vault_dir(),
                subdirs=[str(get_documents_dir()), str(get_rag_dir())],
            ),
            plugins=PathCategory(id="plugins", path=get_project_brain_skills_dir()),
            runtime=PathCategory(
                id="runtime",
                path=get_runtime_dir(),
                subdirs=[str(get_logs_dir()), str(get_cache_dir()), str(get_ipc_dir())],
            ),
        )

    def save(self, config_path: Path | None = None) -> None:
        """Save vault/documents paths back to project.yaml."""
        from src.config.path_discovery import update_project_yaml
        from src.config.paths import get_documents_dir

        update_project_yaml("vault", self.data.path)
        update_project_yaml("documents", get_documents_dir())


def find_git_root(path: Path) -> Optional[Path]:
    """Find the .git directory for a path, walking up the tree."""
    if not path.exists():
        return None

    current = path.resolve()
    while current != current.parent:
        git_dir = current / ".git"
        if git_dir.exists():
            return current
        current = current.parent
    return None


def calculate_directory_size(
    path: Path,
    exclude_patterns: Optional[list[str]] = None,
) -> float:
    """
    Calculate directory size in MB, excluding patterns.

    Args:
        path: Directory to measure
        exclude_patterns: Patterns to exclude (default: .git, node_modules, etc.)

    Returns:
        Size in megabytes
    """
    if not path.exists():
        return 0.0

    exclude = exclude_patterns or [
        ".git",
        "node_modules",
        ".next",
        "__pycache__",
        ".venv",
        "venv",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
    ]

    total = 0
    try:
        for entry in path.rglob("*"):
            # Skip excluded patterns
            if any(exc in entry.parts for exc in exclude):
                continue
            if entry.is_file():
                try:
                    total += entry.stat().st_size
                except (OSError, PermissionError):
                    pass
    except (OSError, PermissionError):
        pass

    return total / (1024 * 1024)


def is_path_gitignored(path: Path, git_root: Path) -> bool:
    """Check if a path is gitignored."""
    if not git_root or not path.exists():
        return False

    try:
        git_bin = shutil.which("git")
        if not git_bin:
            return False

        result: CompletedProcess[bytes] = run(
            [git_bin, "check-ignore", "-q", str(path)],
            cwd=git_root,
            capture_output=True,
            check=False,
        )  # nosec B603
        return result.returncode == 0
    except (SubprocessError, FileNotFoundError):
        return False


def check_size_alerts(config: PathConfig) -> list[SizeAlert]:
    """Check all paths against size thresholds."""
    alerts = []

    for category in config.categories:
        if not category.path.exists():
            continue

        size = category.size_mb
        if size > config.alerts.critical_mb:
            alerts.append(SizeAlert(category.id, "critical", size))
        elif size > config.alerts.warning_mb:
            alerts.append(SizeAlert(category.id, "warning", size))

    return alerts


def generate_recommendations(config: PathConfig) -> list[Recommendation]:
    """Generate recommendations based on current config."""
    recs = []

    # Repo-local runtime state should be gitignored if a user points runtime back into the repo.
    if config.runtime.path.exists() and config.runtime.git_root and not config.runtime.gitignored:
        recs.append(
            Recommendation(
                "gitignore_runtime",
                "Add the runtime state directory to .gitignore to prevent committing mutable state files",
                auto_fixable=True,
            )
        )

    # Suggest monorepo if sizes are small
    if config.repo_count > 1 and config.data.size_mb < 100:
        recs.append(
            Recommendation(
                "consider_monorepo",
                "Data repo is small - consider consolidating to single repo for simpler workflow",
            )
        )

    # Check for large runtime folder
    if config.runtime.size_mb > 200:
        recs.append(
            Recommendation(
                "cleanup_runtime",
                f"Runtime storage is {config.runtime.size_mb:.0f}MB - consider running cleanup",
                auto_fixable=True,
            )
        )

    return recs


def load_path_config() -> PathConfig:
    """Load path configuration from paths.py functions (project.yaml backed)."""
    config = PathConfig.defaults()
    config.refresh_sizes()
    config.refresh_gitignored()
    return config


def get_path_config(refresh: bool = False) -> PathConfig:
    """
    Get the current path configuration (cached).

    Args:
        refresh: Force reload from file

    Returns:
        PathConfig instance
    """
    global _path_config

    if _path_config is None or refresh:
        _path_config = load_path_config()

    return _path_config


def refresh_path_config() -> PathConfig:
    """Force reload of path configuration."""
    return get_path_config(refresh=True)


# === File Classification Utilities ===


def is_user_data_file(path: Path) -> bool:
    """
    Detect if file contains user data vs code config.

    User data files typically contain timestamps, IDs, or user-specific content.
    """
    if not path.exists() or not path.is_file():
        return False

    if path.suffix not in [".yaml", ".json"]:
        return False

    try:
        content = path.read_text(encoding="utf-8")
        # User data patterns
        data_patterns = [
            r"created_at:",
            r"updated_at:",
            r"user_id:",
            r"entries:",
            r"^\s*-\s+id:",  # List of items with IDs
            r"last_modified:",
            r"timestamp:",
        ]
        return any(re.search(p, content, re.MULTILINE) for p in data_patterns)
    except (OSError, UnicodeDecodeError):
        return False


def is_runtime_file(path: Path) -> bool:
    """Detect if file is state, log, cache, or temp data."""
    runtime_root = re.escape(str(get_runtime_dir()).replace("\\", "/"))
    runtime_patterns = [
        r"\.log$",
        r"\.tmp$",
        r"\.cache$",
        r"\.pid$",
        r"/logs/",
        r"/temp/",
        r"/cache/",
        r"/ipc/",
        r"_archive/",
        runtime_root,
    ]
    path_str = str(path).replace("\\", "/")
    return any(re.search(p, path_str) for p in runtime_patterns)


def is_script_file(path: Path) -> bool:
    """Check if a Python file is a script (vs a module)."""
    if path.suffix != ".py":
        return False

    try:
        content = path.read_text(encoding="utf-8")
        # Scripts typically have if __name__ == "__main__"
        return 'if __name__ == "__main__"' in content or "if __name__ == '__main__'" in content
    except (OSError, UnicodeDecodeError):
        return False


def get_forbidden_patterns() -> list[str]:
    """Get forbidden path patterns based on current user."""
    username = os.environ.get("USER", os.environ.get("USERNAME", ""))
    if not username:
        return []

    return [
        f"/Users/{username}",
        f"/home/{username}",
        f"C:\\Users\\{username}",
    ]
