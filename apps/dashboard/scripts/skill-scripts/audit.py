"""
Plugin Compliance Audit Script

Audit Augur plugins against the plugin specification.

Usage:
    python audit.py                    # Audit all plugins
    python audit.py --name career      # Audit specific plugin
    python audit.py --fix              # Auto-fix simple issues

Sub-modules:
    audit_checks  — individual compliance check functions
    audit_report  — report formatting and CLI entry point
"""

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import yaml


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


# Add project root to path
SCRIPT_DIR = Path(__file__).parent
PLUGIN_ROOT = SCRIPT_DIR.parent

try:
    from src.config.paths import get_project_root
    PROJECT_ROOT = get_project_root()
except ImportError:
    PROJECT_ROOT = PLUGIN_ROOT.parent.parent.parent.parent  # fallback

sys.path.insert(0, str(PROJECT_ROOT))

from src.logging import get_entity_logger  # noqa: E402

logger = get_entity_logger("mcp-app-factory")

# Plugin spec location
SPEC_PATH = PLUGIN_ROOT / "plugin-spec.yaml"
EXCLUDED_SCAN_DIRS = {
    ".git",
    ".next",
    ".venv",
    ".pytest_cache",
    ".mypy_cache",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "venv",
}


def _is_excluded_scan_path(plugin_path: Path, file_path: Path) -> bool:
    """Return True for generated/vendor paths that should not be audited."""
    try:
        relative = file_path.relative_to(plugin_path)
    except ValueError:
        return False
    return any(part in EXCLUDED_SCAN_DIRS for part in relative.parts)


def _collect_code_files(plugin_path: Path, *patterns: str) -> List[Path]:
    files: List[Path] = []
    for pattern in patterns:
        for file_path in plugin_path.rglob(pattern):
            if file_path.is_file() and not _is_excluded_scan_path(plugin_path, file_path):
                files.append(file_path)
    return files


@dataclass
class AuditResult:
    """Result of a single audit check."""

    rule: str
    passed: bool
    message: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    fixable: bool = False


@dataclass
class PluginAudit:
    """Audit results for a plugin."""

    plugin_name: str
    plugin_path: str
    bundle: str
    results: List[AuditResult] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if not r.passed)

    @property
    def score(self) -> float:
        if not self.results:
            return 0.0
        return (self.passed / len(self.results)) * 100

    @property
    def status(self) -> str:
        if self.score >= 90:
            return "pass"
        elif self.score >= 70:
            return "warn"
        else:
            return "fail"


def load_spec() -> dict:
    """Load the plugin specification."""
    if not SPEC_PATH.exists():
        logger.warning(f"Plugin spec not found at {SPEC_PATH}, utilizing defaults")
        return {}
    with open(SPEC_PATH) as f:
        return yaml.safe_load(f)


def detect_profile(skill_path: Path) -> str:
    """Auto-detect plugin profile from directory contents (ADR-040 Section 3).

    Returns:
        'full' if api/ directory exists
        'standard' if dashboard.yaml exists AND dashboard/ directory exists
        'minimal' if dashboard.yaml exists but NO dashboard/ directory (tab contributor)
        'minimal' otherwise
    """
    if (skill_path / "api").is_dir():
        return "full"
    elif (skill_path / "dashboard.yaml").exists() and (skill_path / "dashboard").is_dir():
        return "standard"
    else:
        return "minimal"


def discover_plugins(profile_filter: str | None = None) -> List[tuple]:
    """Discover all plugins in the plugins/ directory and external app directories.

    Now discovers ALL plugins with SKILL.md (not just dashboard.yaml ones).
    Each result includes the auto-detected profile.

    Args:
        profile_filter: If set, only return plugins matching this profile
                       ('minimal', 'standard', 'full')

    Returns:
        List[(bundle_name, skill_name, skill_path, profile)]
    """
    plugins = []

    # 1. Internal skills
    plugins_dir = PROJECT_ROOT / "plugins"
    if plugins_dir.exists():
        for bundle_dir in sorted(plugins_dir.iterdir()):
            if not bundle_dir.is_dir():
                continue
            bundle_name = bundle_dir.name

            skills_dir = bundle_dir / "skills"
            if not skills_dir.exists():
                continue

            for skill_dir in sorted(skills_dir.iterdir()):
                if not skill_dir.is_dir() or skill_dir.name.startswith("."):
                    continue
                # Any directory with SKILL.md is a plugin (ADR-040)
                if (skill_dir / "SKILL.md").exists():
                    profile = detect_profile(skill_dir)
                    if profile_filter is None or profile == profile_filter:
                        plugins.append((bundle_name, skill_dir.name, skill_dir, profile))

    # 2. External skills
    external_skill_dirs = [
        ("codex", Path.home() / ".codex" / "skills"),
        ("claude", Path.home() / ".claude" / "plugins"),
        ("cowork", Path.home() / ".cowork" / "skills"),
    ]
    for ext_bundle, ext_dir in external_skill_dirs:
        if ext_dir.exists() and ext_dir.is_dir():
            for skill_dir in sorted(ext_dir.iterdir()):
                if not skill_dir.is_dir() or skill_dir.name.startswith("."):
                    continue
                if (skill_dir / "SKILL.md").exists():
                    profile = detect_profile(skill_dir)
                    if profile_filter is None or profile == profile_filter:
                        plugins.append((ext_bundle, skill_dir.name, skill_dir, profile))

    return plugins


def audit_plugin(
    plugin_path: Path,
    plugin_name: str,
    bundle: str,
    spec: dict,
    profile: str | None = None,
) -> PluginAudit:
    """Run full audit on a plugin (profile-aware, ADR-040).

    Args:
        plugin_path: Path to the plugin directory
        plugin_name: Name of the plugin
        bundle: Bundle the plugin belongs to
        spec: Loaded plugin specification
        profile: Plugin profile (auto-detected if None)
    """
    from audit_checks import (
        check_required_files,
        check_dashboard_yaml,
        check_code_quality,
        check_logging,
        check_naming,
        check_size_limits,
    )

    if profile is None:
        profile = detect_profile(plugin_path)

    audit = PluginAudit(
        plugin_name=plugin_name,
        plugin_path=str(plugin_path),
        bundle=bundle,
    )

    # Run profile-aware file checks
    audit.results.extend(check_required_files(plugin_path, spec, profile))

    # Dashboard checks only for standard+ profiles
    if profile in ("standard", "full"):
        audit.results.extend(check_dashboard_yaml(plugin_path, spec))
        audit.results.extend(check_naming(plugin_path, plugin_name))

    # Code quality and logging checks for all profiles
    audit.results.extend(check_code_quality(plugin_path, spec))
    audit.results.extend(check_logging(plugin_path, spec))

    # Size checks for all profiles
    audit.results.extend(check_size_limits(plugin_path, plugin_name, spec))

    return audit


def audit_all_plugins(spec: dict, profile_filter: str | None = None) -> List[PluginAudit]:
    """Audit all discovered plugins (ADR-040: discovers ALL plugins, not just UI ones).

    Args:
        spec: Loaded plugin specification
        profile_filter: If set, only audit plugins matching this profile
    """
    plugins = discover_plugins(profile_filter)
    audits = []

    for bundle, plugin_name, plugin_path, profile in plugins:
        audit = audit_plugin(plugin_path, plugin_name, bundle, spec, profile)
        audits.append(audit)

    return audits


# Re-export from sub-modules for backward compatibility
def format_audit_report(audits: List[PluginAudit], show_profiles: bool = True) -> str:
    """Format audit results as a report. Delegates to audit_report module."""
    from audit_report import format_audit_report as _fmt
    return _fmt(audits, show_profiles)


def cli():
    """CLI entry point. Delegates to audit_report module."""
    from audit_report import cli as _cli
    _cli()


if __name__ == "__main__":
    cli()
