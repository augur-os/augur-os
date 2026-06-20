"""Shared repository hygiene policy for root scanning and collateral routing."""

from __future__ import annotations

from pathlib import Path

ROOT_ALLOWED_DIRS: set[str] = {
    ".agents",
    ".antigravity",
    ".claude",
    ".claude-plugin",
    ".codex",
    ".cowork",
    ".cursor",
    ".cursor-plugin",
    ".gemini",
    ".git",
    ".github",
    ".githooks",
    ".opencode",
    ".pytest_cache",
    ".superpowers",
    ".venv",
    ".venv-test",
    ".vscode",
    ".windsurf",
    ".worktrees",
    "apps",
    "config",
    "docs",
    "node_modules",
    "packages",
    "plugins",
    "project-brain",
    "scripts",
    "shared-vault",
    "skills",
    "src",
    "tests",
}

ROOT_ALLOWED_FILES: set[str] = {
    ".clinerules",
    ".cursorignore",
    ".envrc",
    ".gitattributes",
    ".gitignore",
    ".gitleaksignore",
    ".mcp.json",
    ".npmrc",
    ".pre-commit-config.yaml",
    "LICENSE",
    "Makefile",
    "project.yaml",
    "pyproject.toml",
    "uv.lock",
    "VERSION",
    "worktreeinclude",
}

ROOT_ALLOWED_FILE_PREFIXES: tuple[str, ...] = (
    "README",
    "CLAUDE",
    "AGENTS",
    "CODEX",
    "CHANGELOG",
    "CONTRIBUTING",
    "SECURITY",
    ".env",
    ".eslintrc",
    ".prettierrc",
    "jest.config",
    "pnpm-",
    "requirements",
    "tsconfig",
)

ROOT_ALLOWED_FILE_SUFFIXES: tuple[str, ...] = (
    ".md",
    ".txt",
)


def is_allowed_root_item(name: str) -> bool:
    """Return whether a repo-root entry is part of the canonical layout."""
    if name in ROOT_ALLOWED_DIRS or name in ROOT_ALLOWED_FILES:
        return True
    if any(name.startswith(prefix) for prefix in ROOT_ALLOWED_FILE_PREFIXES):
        return True
    if any(name.endswith(suffix) for suffix in ROOT_ALLOWED_FILE_SUFFIXES):
        return True
    return False


def collect_root_strays(project_root: Path) -> list[Path]:
    """Collect repo-root items that do not belong in the canonical layout."""
    return [item for item in sorted(project_root.iterdir()) if not is_allowed_root_item(item.name)]
