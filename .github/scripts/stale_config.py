"""
Configuration and data structures for the stale path scanner.

Contains known renames, scan patterns, file type configs, and data classes.
"""

from __future__ import annotations

import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

# Ensure project root is importable
_project_root = Path(__file__).resolve().parents[2]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from src.lib.adr_utils import get_adr_dir


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

# Known directory renames (hardcoded fallback for squashed/rebased commits).
# IMPORTANT: This list must include skill-level renames (hub rebalancing moves
# individual skills between hubs without renaming the whole parent directory).
KNOWN_RENAMES: dict[str, str] = {
    # ADR-601: Shared/team skills moved under project-brain/capabilities/skills.
    # All legacy plugin skill paths map to project-brain/capabilities/skills/*.
    ".claude/skills/": "project-brain/capabilities/skills/",
    "plugins/dev/skills/": "project-brain/capabilities/skills/",
    "plugins/ai/skills/": "project-brain/capabilities/skills/",
    "plugins/admin/skills/": "project-brain/capabilities/skills/",
    "plugins/observability/skills/": "project-brain/capabilities/skills/",
    "plugins/career/skills/": "project-brain/capabilities/skills/",
    "plugins/consulting/skills/": "project-brain/capabilities/skills/",
    "plugins/enterprise/skills/": "project-brain/capabilities/skills/",
    "plugins/finance/skills/": "project-brain/capabilities/skills/",
    "plugins/health/skills/": "project-brain/capabilities/skills/",
    "plugins/home/skills/": "project-brain/capabilities/skills/",
    "plugins/lifestyle/skills/": "project-brain/capabilities/skills/",
    "plugins/orchestration/skills/": "project-brain/capabilities/skills/",
    "plugins/productivity/skills/": "project-brain/capabilities/skills/",
    "plugins/professional/skills/": "project-brain/capabilities/skills/",
    "plugins/custom/skills/": "project-brain/capabilities/skills/",
    "plugins/core/skills/": "project-brain/capabilities/skills/",
    # Legacy top-level directories (completely removed)
    "kernel/": "project-brain/capabilities/skills/ai/",
    "kernel/dashboard/": "apps/dashboard/",
    "kernel/scripts/": "project-brain/capabilities/skills/ai/scripts/",
    "packages/augur-mcp/": "src/mcp/",
    "packages/": "project-brain/capabilities/skills/",
    "shared/": "src/lib/",
    # Legacy data directory structure
    "data/core/runtime": "runtime",
    "data/core/executor/": "project-brain/capabilities/skills/executor/augur/data/",
    "data/config/": "config/",
    "data/plugins/": "project-brain/capabilities/skills/",
    "data/apps/": "project-brain/capabilities/skills/",
    # Pre-ADR-479 hub-level renames (old → old, kept for scanning git history)
    "plugins/crew/": "plugins/dev/",
    "plugins/factory/": "plugins/dev/",
    "plugins/orchestrator/": "plugins/core/",
    "plugins/services/skills/": "project-brain/capabilities/skills/",
    "plugins/business/skills/": "project-brain/capabilities/skills/",
    "plugins/apps/skills/": "project-brain/capabilities/skills/",
    "plugins/venture/skills/": "project-brain/capabilities/skills/",
    "plugins/creative/skills/": "project-brain/capabilities/skills/",
    "plugins/growth/skills/": "project-brain/capabilities/skills/",
    "plugins/wealth/skills/": "project-brain/capabilities/skills/",
    "plugins/observe/skills/": "project-brain/capabilities/skills/",
    "plugins/integrations/skills/": "project-brain/capabilities/skills/",
}

# File extensions to scan in the codebase
CODEBASE_GLOBS = [
    "*.py", "*.ts", "*.tsx", "*.js", "*.jsx",
    "*.yaml", "*.yml", "*.json", "*.md", "*.sh",
    "*.plist", "*.toml",
]

# Directories to skip during codebase scan
IGNORE_DIRS = {
    "node_modules", ".venv", ".next", "dist", ".git",
    "__pycache__", ".mypy_cache", ".pytest_cache",
    ".turbo", "coverage", ".agent",
}

# Files in these paths reference old names intentionally (history/docs).
# Mark as not auto-fixable to prevent corrupting documentation.
NO_AUTOFIX_PREFIXES = (
    str(get_adr_dir()) + "/",
    "docs/memory/",
    "docs/guides/",
    "docs/references/",
    "CONTRIBUTING.md",
    "CHANGELOG.md",
)

# External config files to check
EXTERNAL_SHELL_FILES = [
    Path.home() / ".zshrc",
    Path.home() / ".bashrc",
    Path.home() / ".zprofile",
    Path.home() / ".bash_profile",
]

EXTERNAL_LAUNCHAGENT_DIR = Path.home() / "Library" / "LaunchAgents"
LAUNCHAGENT_PREFIX = "com.augur."

IDE_CONFIG_DIRS = [".cursor", ".claude", ".vscode"]
GIT_HOOK_DIRS = [".git/hooks", ".husky"]

# Data segment validation patterns (ADR-087/ADR-126 compliance)
DATA_SEGMENT_PATTERNS: list[tuple[str, str, str]] = [
    (
        r'project-brain/capabilities/skills/[a-zA-Z_-]+/data/(?!\.)',
        "augur_segment",
        "Path missing augur/ segment: should be project-brain/capabilities/skills/{skill}/augur/data/",
    ),
    (
        r'apps-data/',
        "legacy_global",
        "Legacy apps-data/ path: should use project-brain/capabilities/skills/{skill}/augur/data/",
    ),
    (
        r'''["']/data["']$''',
        "global_data_root",
        "Global data/ root eliminated by ADR-087: use get_project_root() without /data suffix",
    ),
    (
        r'["/]factory/(?:executor|agent)',
        "stale_bundle",
        "Stale factory/ bundle: should be project-brain/capabilities/skills/executor/",
    ),
]

# Fragile path patterns that should use src.config.paths
FRAGILE_PATTERNS: list[tuple[str, str]] = [
    (r'Path\(__file__\)\.parents?\[\d+\]', "Use get_project_root() from src.config.paths"),
    (r'PROJECT_ROOT\s*/\s*"runtime"', "Use get_runtime_dir() from src.config.paths"),
    (r'PROJECT_ROOT\s*/\s*"logs"', "Use get_logs_dir() from src.config.paths"),
    (r'PROJECT_ROOT\s*/\s*"config"', "Use get_config_dir() from src.config.paths"),
    (r'"/Users/[^"]*augur', "Use Path.home() or src.config.paths functions"),
]


# ═══════════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class StaleFinding:
    """A single stale path reference found during scanning."""
    file: str
    line: int
    match: str
    replacement: str
    category: str       # hub_rename | data_structure | fragile_path
    risk: str           # high | medium | low
    auto_fixable: bool
    external: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ScanResult:
    """Aggregated scan results."""
    findings: list[StaleFinding] = field(default_factory=list)
    rename_map: dict[str, str] = field(default_factory=dict)
    git_renames_detected: int = 0

    @property
    def high_risk(self) -> list[StaleFinding]:
        return [f for f in self.findings if f.risk == "high"]

    @property
    def auto_fixable(self) -> list[StaleFinding]:
        return [f for f in self.findings if f.auto_fixable and not f.external]

    @property
    def external_findings(self) -> list[StaleFinding]:
        return [f for f in self.findings if f.external]

    @property
    def review_needed(self) -> list[StaleFinding]:
        return [f for f in self.findings if not f.auto_fixable and not f.external]
