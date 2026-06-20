#!/usr/bin/env python3
"""
Validate repository folder structure.

Enforces (will block commits):
1. Hub-driven plugin architecture (ADR-105/ADR-108)
2. src/ for framework code, plugins/ for skills
3. data/ for user data (mirrors plugins structure)

Transient files (allowed anywhere, won't block commit):
- __pycache__/, .pyc, .pyo
- .DS_Store
- *.log, *.tmp

Usage:
  python3 .github/scripts/validate_structure.py [--staged-only] [--skip-required-files]
"""

import sys
import subprocess
from pathlib import Path
from typing import List, Set

# === CONFIGURATION ===

# Root directories that are allowed
ALLOWED_ROOT_DIRS = {
    "src",  # Source code (framework)
    "packages",  # MCP packages and other installable packages
    "plugins",  # 4-bundle plugin architecture (ADR-020)
    "data",  # User data directory
    "docs",  # Documentation
    "scripts",  # Install and utility scripts
    "config",  # Configuration files
    ".agent",  # Agent workflows and config
    ".github",  # GitHub workflows
    ".vscode",  # Editor config
    "tests",  # Test files
    "runtime",  # Runtime logs/cache/temp
    ".archive",  # Archived/deprecated scripts (not deleted for reference)
}

# Root files that are allowed
ALLOWED_ROOT_FILES = {
    # Documentation
    "README.md",
    "CLAUDE.md",
    "AGENTS.md",
    "LICENSE",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CODEX.md",
    "COMMERCIAL.md",
    "CODE_OF_CONDUCT.md",
    # IDE config (must be in root per IDE requirements)
    ".cursorrules",
    ".windsurfrules",
    ".mcp.json",
    # Config
    ".gitignore",
    ".prettierrc",
    ".eslintrc.json",
    "package.json",
    "package-lock.json",
    "tsconfig.json",
    "next.config.js",
    "next.config.mjs",
    "tailwind.config.js",
    "tailwind.config.ts",
    "postcss.config.js",
    "postcss.config.mjs",
    "components.json",
    "pyproject.toml",
    "requirements.txt",
    "requirements-rag.txt",
    ".python-version",
    "dependencies.yaml",
    "Makefile",
    "api_summary.json",
    "mcp_config.template.json",
    "test_ctypes.py",
    # CLI entry points
    "augur",
    "uv.lock",
    "VERSION",
    "wrap.sh",
    "trace_fail.zip",
    # mprocs.yaml removed — CLI agent configs now managed via MCP tool manage_cli_agents
    "tsconfig.base.json",
    # Project config + public-launch / GEO files (legit at root)
    "project.yaml",
    "KNOWN-ISSUES.md",
    "ROADMAP.md",
    "NOTICE",
    "llms.txt",
    "llms-full.txt",
    "worktreeinclude",
}

# Conservative fallback. The validator discovers current hubs from plugins/* at runtime.
# ADR-601: shared/team skills live under project-brain/capabilities/skills.
# This fallback is kept for legacy validation of any remaining plugin config files.
DEFAULT_PLUGIN_HUBS: set[str] = set()

# Required files in each skill folder
SKILL_REQUIRED_FILES = {"SKILL.md"}

# Optional skill files
SKILL_OPTIONAL_FILES = {"BACKLOG.md"}

# Allowed folders in skill directory
SKILL_ALLOWED_DIRS = {
    "scripts",  # Python scripts
    "modules",  # Markdown modules
    "references",  # Reference docs
    "chains",  # Chain definitions (owned by skill)
    "dashboard",  # Dashboard UI components
    "api",  # API routes
    "lib",  # TypeScript/Python libraries
    "mcp",  # MCP tool definitions
    "tests",  # Tests
    "config",  # Skill-specific config
    "templates",  # Template files
    "backlog",  # Backlog items
    "_dev",  # Development files
    "examples",  # Examples
    "__pycache__",  # Python cache (transient)
    # Legacy/special folders
    "knowledge",
    "services",
    "workflows",
    "data-template",
    "parsers",
    "actions",
    "hooks",
    "augur",  # Augur-specific metadata (version.yaml, .config status)
    # RAG Component folders
    "adapters",
    "ingestion",
    "search",
    "storage",
    "utils",
    "core",
    "interfaces",
}

# Allowed files in skill directory (besides required)
SKILL_ALLOWED_FILES = {
    "README.md",
    "CHANGELOG.md",
    "ACCEPTANCE_CRITERIA.md",
    "requirements.txt",
    "package.json",
    "dashboard.yaml",
    ".gitignore",
    "__init__.py",
    "config.yaml",
    "context.py",
}

# src/ directory structure
SRC_ALLOWED_DIRS = {
    "config",  # Configuration and path resolution
    "dashboard",  # Next.js dashboard
    "lib",  # Shared framework libraries
    "logging",  # Logging infrastructure
    "mcp",  # Canonical MCP server package
    "plugins",  # Plugin registry, loader, migrator
    "scripts",  # Source-side utility scripts
    "cli_config",  # CLI config adapters (manifest/config_sync)
    "tests",  # Source-side unit tests (cli logging, tokenizer, vault status)
}

# data/ directory structure (mirrors plugins/ hubs)
DATA_ALLOWED_DIRS = {
    "core",  # Core system data (runtime, config)
    "career",  # Career skill data
    "finance",  # Finance skill data
    "health",  # Health skill data
    "productivity",  # Productivity skill data
    "lifestyle",  # Lifestyle skill data
    "home",  # Home skill data
    "business",  # Business skill data
    "ai",  # AI skill data
    "system",  # System skill data
    "dev",  # Dev skill data
    # Legacy/Existing folders (allowed for now)
    "terminal-automation-template",
    "capture",
    "career",
    "config",
    "content",
    "daemon",
    "smb-client-template",
    "consulting-template",
    "eisenhower",
    "enterprise",
    "factory",
    "finance",
    "health",
    "home",
    "icloud",
    "ideas",
    "knowledge",
    "lifestyle",
    "file-manager",
    "platform",
    "runtime",
    "scraper",
    "services-core",
    "venture",
    "ai-bridge",
    "install",
    "temp",
}

# Transient patterns (ignored, won't block)
TRANSIENT_PATTERNS = {
    "__pycache__",
    ".pyc",
    ".pyo",
    ".DS_Store",
    ".log",
    ".tmp",
    "node_modules",
    ".next",
    ".turbo",
    ".venv",
}


def is_transient(path: str) -> bool:
    """Check if path matches transient patterns."""
    for pattern in TRANSIENT_PATTERNS:
        if pattern in path:
            return True
    return False


def get_staged_files() -> List[str]:
    """Get list of staged files for commit."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        capture_output=True,
        text=True,
    )
    return [f for f in result.stdout.strip().split("\n") if f]


def discover_plugin_hubs(repo_root: Path) -> Set[str]:
    """Discover current hub directories under plugins/."""
    plugins_dir = repo_root / "plugins"
    if not plugins_dir.exists():
        return set(DEFAULT_PLUGIN_HUBS)

    hubs = {
        item.name
        for item in plugins_dir.iterdir()
        if item.is_dir() and not item.name.startswith(".")
    }
    return hubs or set(DEFAULT_PLUGIN_HUBS)


def validate_root_level(repo_root: Path, files: List[str]) -> List[str]:
    """Validate root-level files and directories."""
    issues = []

    for item in files:
        # Only check root level
        if "/" in item:
            continue

        path = repo_root / item

        # Skip files that don't exist (deleted but not yet committed)
        if not path.exists() and not path.is_symlink():
            continue

        if path.is_dir():
            if item not in ALLOWED_ROOT_DIRS and not item.startswith("."):
                issues.append(f"Unexpected directory at root: {item}")
        else:
            if item not in ALLOWED_ROOT_FILES and not item.startswith("."):
                issues.append(f"Unexpected file at root: {item}")

    return issues


def validate_plugins_structure(
    repo_root: Path, files: List[str], plugin_hubs: Set[str]
) -> List[str]:
    """Validate project-brain/capabilities/skills/ directory structure."""
    issues = []

    skills_files = [f for f in files if f.startswith("project-brain/capabilities/skills/")]

    for file_path in skills_files:
        parts = file_path.split("/")

        # Allow files in project-brain/capabilities/skills/ root
        if len(parts) == 4:
            continue

        # Check skill name (project-brain/capabilities/skills/{skill}/)
        if len(parts) >= 4:
            skill_name = parts[3]
            if skill_name.startswith("."):
                continue

        # Check for expected subdirectories (project-brain/capabilities/skills/{skill}/{subdir}/)
        if len(parts) >= 5:
            if parts[4].startswith("."):
                # Allow bundle-level files like SKILL.md
                if len(parts) == 5 and parts[4] in {
                    "SKILL.md",
                    ".gitkeep",
                }:
                    continue

    return issues


def validate_src_structure(repo_root: Path, files: List[str]) -> List[str]:
    """Validate src/ directory structure."""
    issues = []

    src_files = [f for f in files if f.startswith("src/")]

    for file_path in src_files:
        parts = file_path.split("/")

        if len(parts) >= 2:
            subdir = parts[1]
            if subdir not in SRC_ALLOWED_DIRS and not subdir.startswith("."):
                if (repo_root / "src" / subdir).is_dir():
                    issues.append(f"Unexpected folder in src/: {subdir}")

    return issues


def validate_data_structure(repo_root: Path, files: List[str]) -> List[str]:
    """Validate data/ directory structure."""
    issues = []

    data_files = [f for f in files if f.startswith("data/")]

    for file_path in data_files:
        parts = file_path.split("/")

        if len(parts) >= 2:
            subdir = parts[1]
            if subdir not in DATA_ALLOWED_DIRS and not subdir.startswith("."):
                if (repo_root / "data" / subdir).is_dir():
                    issues.append(
                        f"data/{subdir}: Invalid directory. "
                        f"Must be one of: {', '.join(sorted(DATA_ALLOWED_DIRS))}"
                    )

    return issues


def check_missing_skill_files(repo_root: Path, plugin_hubs: Set[str]) -> List[str]:
    """Check for skills missing required files (SKILL.md)."""
    issues = []

    skills_dir = repo_root / "project-brain" / "capabilities" / "skills"
    if not skills_dir.exists():
        # ADR-084: emit event instead of silent skip
        try:
            from src.logging.self_heal_event import emit_heal_event

            emit_heal_event(
                source="validate_structure",
                category="path_missing",
                severity="medium",
                message=f"project-brain/capabilities/skills/ directory not found: {skills_dir}",
                context={"repo_root": str(repo_root)},
            )
        except ImportError:
            pass
        issues.append(f"project-brain/capabilities/skills/ directory not found at {skills_dir}")
        return issues

    for skill_dir in skills_dir.iterdir():
        if not skill_dir.is_dir() or skill_dir.name.startswith("."):
            continue

        # A skill is valid with a top-level SKILL.md, OR as a "collection" skill:
        # a DESCRIPTION.md at the top plus one or more named sub-skill folders that
        # each carry their own SKILL.md (e.g. local-audio-processing/audio-transcription).
        skill_md = skill_dir / "SKILL.md"
        if skill_md.exists():
            continue
        is_collection = (skill_dir / "DESCRIPTION.md").exists() and any(
            (sub / "SKILL.md").exists()
            for sub in skill_dir.iterdir()
            if sub.is_dir() and not sub.name.startswith(".")
        )
        if not is_collection:
            issues.append(
                f"project-brain/capabilities/skills/{skill_dir.name}: Missing SKILL.md"
            )

    return issues


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Validate repository structure")
    parser.add_argument(
        "--fix", action="store_true", help="Attempt to fix issues (not implemented)"
    )
    parser.add_argument(
        "--staged-only", action="store_true", help="Only check staged files"
    )
    parser.add_argument(
        "--skip-required-files",
        action="store_true",
        help="Skip checking for missing required skill files",
    )
    parser.add_argument("repo_path", nargs="?", default=".", help="Repository path")

    args = parser.parse_args()
    repo_root = Path(args.repo_path).resolve()

    print(f"\n📁 Validating Structure: {repo_root}")
    print("=" * 60)

    # Get files to check
    if args.staged_only:
        files = get_staged_files()
        if not files:
            print("✅ No staged files to check")
            return 0
        print(f"Checking {len(files)} staged files...")
    else:
        # Get all tracked files
        result = subprocess.run(
            ["git", "ls-files"], capture_output=True, text=True, cwd=repo_root
        )
        files = [f for f in result.stdout.strip().split("\n") if f]
        print(f"Checking {len(files)} tracked files...")

    # Filter out transient files
    files = [f for f in files if not is_transient(f)]

    plugin_hubs = discover_plugin_hubs(repo_root)

    # Run validations
    all_issues = []

    # 1. Root level
    issues = validate_root_level(repo_root, files)
    all_issues.extend(issues)

    # 2. Plugins structure (hub-driven architecture)
    issues = validate_plugins_structure(repo_root, files, plugin_hubs)
    all_issues.extend(issues)

    # 3. src/ structure
    issues = validate_src_structure(repo_root, files)
    all_issues.extend(issues)

    # 4. data/ structure
    issues = validate_data_structure(repo_root, files)
    all_issues.extend(issues)

    # 5. Required skill files (SKILL.md)
    if not args.skip_required_files:
        issues = check_missing_skill_files(repo_root, plugin_hubs)
        all_issues.extend(issues)

    # Report issues
    if all_issues:
        print(f"\n❌ Found {len(all_issues)} structure issues:\n")
        for issue in all_issues:
            print(f"  • {issue}")
        print()
        return 1
    else:
        print("\n✅ No structure issues found!")

    return 0


if __name__ == "__main__":
    sys.exit(main())
