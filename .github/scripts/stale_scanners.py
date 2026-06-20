"""
Phases 2-6: Codebase, external config, fragile path, phantom path,
and data segment scanners.

Each phase scans for a different category of stale path references.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Optional

try:
    from .stale_config import (
        DATA_SEGMENT_PATTERNS,
        EXTERNAL_LAUNCHAGENT_DIR,
        EXTERNAL_SHELL_FILES,
        FRAGILE_PATTERNS,
        GIT_HOOK_DIRS,
        IDE_CONFIG_DIRS,
        IGNORE_DIRS,
        LAUNCHAGENT_PREFIX,
        NO_AUTOFIX_PREFIXES,
        StaleFinding,
        get_adr_dir,
    )
except ImportError:
    from stale_config import (
        DATA_SEGMENT_PATTERNS,
        EXTERNAL_LAUNCHAGENT_DIR,
        EXTERNAL_SHELL_FILES,
        FRAGILE_PATTERNS,
        GIT_HOOK_DIRS,
        IDE_CONFIG_DIRS,
        IGNORE_DIRS,
        LAUNCHAGENT_PREFIX,
        NO_AUTOFIX_PREFIXES,
        StaleFinding,
        get_adr_dir,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════


def relative_path(file_path: str, project_root: Path) -> str:
    """Convert absolute path to relative."""
    try:
        return str(Path(file_path).relative_to(project_root))
    except ValueError:
        return file_path


def _get_rg_base_cmd() -> list[str]:
    """Build base ripgrep command with exclusions."""
    cmd = ["rg", "-n", "--no-heading"]
    for d in IGNORE_DIRS:
        cmd.extend(["-g", f"!{d}"])
    cmd.extend(["-g", "!*.lock"])
    cmd.extend(["-g", "!scan_stale_paths.py"])  # skip self
    return cmd


def _scan_codebase_for_pattern(
    project_root: Path,
    pattern: str,
    replacement: str,
    category: str,
    risk: str,
    auto_fixable: bool,
) -> list[StaleFinding]:
    """Run ripgrep for a pattern across the codebase."""
    findings: list[StaleFinding] = []
    cmd = _get_rg_base_cmd() + [pattern, str(project_root)]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split(":", 2)
            if len(parts) < 3:
                continue
            file_path, line_num_str, content = parts[0], parts[1], parts[2]
            try:
                line_num = int(line_num_str)
            except ValueError:
                continue

            rel_path = relative_path(file_path, project_root)

            is_historical_doc = any(
                rel_path.startswith(p) for p in NO_AUTOFIX_PREFIXES
            )
            is_fixable = auto_fixable and not is_historical_doc
            finding_risk = "low" if is_historical_doc else risk

            findings.append(StaleFinding(
                file=rel_path,
                line=line_num,
                match=content.strip(),
                replacement=replacement,
                category=category,
                risk=finding_risk,
                auto_fixable=is_fixable,
            ))
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    return findings


def _scan_file_for_patterns(
    file_path: Path,
    patterns: list[tuple[str, str]],
    category: str,
    risk: str,
    external: bool = True,
) -> list[StaleFinding]:
    """Scan a single file for stale patterns using plain grep."""
    findings: list[StaleFinding] = []
    if not file_path.exists():
        return findings

    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except (OSError, PermissionError):
        return findings

    for line_num, line in enumerate(content.split("\n"), start=1):
        for pattern, replacement in patterns:
            if re.search(pattern, line):
                findings.append(StaleFinding(
                    file=str(file_path),
                    line=line_num,
                    match=line.strip(),
                    replacement=replacement,
                    category=category,
                    risk=risk,
                    auto_fixable=False,
                    external=external,
                ))

    return findings


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2: CODEBASE SCAN
# ═══════════════════════════════════════════════════════════════════════════════


def scan_codebase(
    project_root: Path,
    rename_map: dict[str, str],
) -> list[StaleFinding]:
    """Scan codebase for all stale path references."""
    findings: list[StaleFinding] = []

    for old_path, new_path in rename_map.items():
        stripped = old_path.rstrip("/")
        path_token = old_path if "/" not in stripped else stripped
        escaped_token = re.escape(path_token)
        pattern = rf"(?:^|[\s\"'`(\[{{=]){escaped_token}"
        replacement_hint = f"{old_path.rstrip('/')} -> {new_path.rstrip('/')}"

        is_data_rename = old_path.startswith("data/")
        category = "data_structure" if is_data_rename else "hub_rename"

        found = _scan_codebase_for_pattern(
            project_root,
            pattern,
            replacement_hint,
            category=category,
            risk="high",
            auto_fixable=True,
        )
        findings.extend(found)

    return findings


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 3: EXTERNAL CONFIG SCAN
# ═══════════════════════════════════════════════════════════════════════════════


def scan_external_configs(
    project_root: Path,
    rename_map: dict[str, str],
) -> list[StaleFinding]:
    """Scan shell configs, LaunchAgents, IDE configs, and git hooks."""
    findings: list[StaleFinding] = []

    path_patterns: list[tuple[str, str]] = []
    for old_path, new_path in rename_map.items():
        escaped = re.escape(old_path.rstrip("/"))
        path_patterns.append((escaped, f"{old_path.rstrip('/')} -> {new_path.rstrip('/')}"))

    # Shell configs
    for shell_file in EXTERNAL_SHELL_FILES:
        findings.extend(_scan_file_for_patterns(
            shell_file, path_patterns,
            category="hub_rename", risk="high", external=True,
        ))

    # LaunchAgents
    if EXTERNAL_LAUNCHAGENT_DIR.exists():
        for plist in EXTERNAL_LAUNCHAGENT_DIR.iterdir():
            if plist.name.startswith(LAUNCHAGENT_PREFIX) and plist.suffix == ".plist":
                findings.extend(_scan_file_for_patterns(
                    plist, path_patterns,
                    category="hub_rename", risk="medium", external=True,
                ))

    # IDE configs
    for ide_dir_name in IDE_CONFIG_DIRS:
        ide_dir = project_root / ide_dir_name
        if not ide_dir.exists():
            continue
        for config_file in ide_dir.rglob("*"):
            if config_file.is_file() and config_file.suffix in {
                ".json", ".yaml", ".yml", ".md", ".toml"
            }:
                findings.extend(_scan_file_for_patterns(
                    config_file, path_patterns,
                    category="hub_rename", risk="medium", external=False,
                ))

    # Git hooks
    for hook_dir_name in GIT_HOOK_DIRS:
        hook_dir = project_root / hook_dir_name
        if not hook_dir.exists():
            continue
        for hook_file in hook_dir.iterdir():
            if hook_file.is_file():
                findings.extend(_scan_file_for_patterns(
                    hook_file, path_patterns,
                    category="hub_rename", risk="high", external=False,
                ))

    return findings


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 4: FRAGILE PATHS
# ═══════════════════════════════════════════════════════════════════════════════


def scan_fragile_paths(project_root: Path) -> list[StaleFinding]:
    """Find paths that should use centralized src.config.paths functions."""
    findings: list[StaleFinding] = []

    for pattern, suggestion in FRAGILE_PATTERNS:
        found = _scan_codebase_for_pattern(
            project_root,
            pattern,
            suggestion,
            category="fragile_path",
            risk="medium",
            auto_fixable=False,
        )
        for f in found:
            if "/test" in f.file or "migration" in f.file or "scan_stale_paths" in f.file:
                continue
            if f.file.endswith("paths.py") and "src/config" in f.file:
                continue
            if f.file.endswith(".json"):
                continue
            if any(
                p in f.file
                for p in [
                    str(get_adr_dir()) + "/",
                    "agent-topics/",
                    "config/agents/",
                    "/executor/data/",
                    "/venture-augur/data/",
                ]
            ):
                continue
            findings.append(f)

    return findings


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 5: PHANTOM PATH DETECTION
# ═══════════════════════════════════════════════════════════════════════════════


def _build_truth_map(project_root: Path) -> dict[str, set[str]]:
    """Build ground-truth map of existing hubs and their skills from the filesystem."""
    plugins_dir = project_root / "plugins"
    if not plugins_dir.exists():
        return {}

    truth: dict[str, set[str]] = {}
    for hub_dir in plugins_dir.iterdir():
        if not hub_dir.is_dir() or hub_dir.name.startswith("."):
            continue
        skills_dir = hub_dir / "skills"
        if not skills_dir.exists():
            continue
        skill_names = set()
        for skill_dir in skills_dir.iterdir():
            if skill_dir.is_dir() and not skill_dir.name.startswith("."):
                skill_names.add(skill_dir.name)
        truth[hub_dir.name] = skill_names
    return truth


def _find_skill_hub(skill_name: str, truth: dict[str, set[str]]) -> Optional[str]:
    """Find which hub a skill actually lives in."""
    for hub, skills in truth.items():
        if skill_name in skills:
            return hub
    return None


def scan_phantom_paths(
    project_root: Path,
    rename_map: dict[str, str],
) -> list[StaleFinding]:
    """Find paths in code that reference non-existent plugin/skill directories."""
    truth = _build_truth_map(project_root)
    if not truth:
        return []

    findings: list[StaleFinding] = []

    pattern = r"plugins/[a-zA-Z_-]+/skills/[a-zA-Z_-]+"
    cmd = _get_rg_base_cmd() + ["-o", pattern, str(project_root)]

    data_pattern = r"data/(?:apps|business|services|crew|orchestrator)/[a-zA-Z_-]+"

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)

        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split(":", 2)
            if len(parts) < 3:
                continue
            file_path, line_num_str, matched_path = parts[0], parts[1], parts[2].strip()

            try:
                line_num = int(line_num_str)
            except ValueError:
                continue

            rel_path = relative_path(file_path, project_root)

            if "scan_stale_paths" in rel_path:
                continue
            if "/test" in rel_path:
                continue
            if any(
                p in rel_path
                for p in [
                    "/data/planning/",
                    "/data/analytics/",
                    "/data/backlog/",
                    "/data/agent-workflows/",
                    "/data/agent-topics/",
                    str(get_adr_dir()) + "/",
                    "docs/guides/",
                    "docs/agent-topics/",
                ]
            ):
                continue

            path_parts = matched_path.split("/")
            if len(path_parts) < 4:
                continue
            hub = path_parts[1]
            skill = path_parts[3]

            if hub in truth and skill in truth[hub]:
                continue

            actual_hub = _find_skill_hub(skill, truth)
            if actual_hub:
                replacement = f"plugins/{actual_hub}/skills/{skill}"
                category = "phantom_path"
                risk = "high"
            else:
                replacement = f"[skill '{skill}' not found in any hub]"
                category = "phantom_path"
                risk = "medium"

            already_covered = False
            for old in rename_map:
                if matched_path.startswith(old.rstrip("/")):
                    already_covered = True
                    break
            if already_covered:
                continue

            is_fixable = actual_hub is not None
            if any(rel_path.startswith(p) for p in NO_AUTOFIX_PREFIXES):
                is_fixable = False

            findings.append(StaleFinding(
                file=rel_path,
                line=line_num,
                match=matched_path,
                replacement=f"{matched_path} -> {replacement}",
                category=category,
                risk=risk,
                auto_fixable=is_fixable,
            ))

    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # Phase 5b: Check data/apps/*, data/business/* etc.
    try:
        result2 = subprocess.run(
            _get_rg_base_cmd() + ["-o", "-n", data_pattern, str(project_root)],
            capture_output=True, text=True,
        )
        for line in result2.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split(":", 2)
            if len(parts) < 3:
                continue
            file_path, line_num_str, matched_path = parts[0], parts[1], parts[2].strip()
            try:
                line_num = int(line_num_str)
            except ValueError:
                continue
            rel_path = relative_path(file_path, project_root)
            if "scan_stale_paths" in rel_path:
                continue

            data_parts = matched_path.split("/")
            if len(data_parts) >= 3:
                skill_name = data_parts[2]
                actual_hub = _find_skill_hub(skill_name, truth)
                if actual_hub:
                    replacement = f"plugins/{actual_hub}/skills/{skill_name}/data"
                else:
                    replacement = f"[skill '{skill_name}' not found]"

                already_covered = any(
                    matched_path.startswith(old.rstrip("/"))
                    for old in rename_map
                )
                if already_covered:
                    continue

                findings.append(StaleFinding(
                    file=rel_path,
                    line=line_num,
                    match=matched_path,
                    replacement=f"{matched_path} -> {replacement}",
                    category="phantom_path",
                    risk="high",
                    auto_fixable=not any(rel_path.startswith(p) for p in NO_AUTOFIX_PREFIXES),
                ))

    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    return findings


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 6: DATA SEGMENT VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════


def scan_data_segments(project_root: Path) -> list[StaleFinding]:
    """Validate that plugin data paths use the canonical augur/data/ structure."""
    findings: list[StaleFinding] = []

    for pattern_str, sub_category, suggestion in DATA_SEGMENT_PATTERNS:
        found = _scan_codebase_for_pattern(
            project_root,
            pattern_str,
            suggestion,
            category="data_segment",
            risk="high",
            auto_fixable=False,
        )

        for f in found:
            if "scan_stale_paths" in f.file:
                continue
            if any(f.file.startswith(p) for p in NO_AUTOFIX_PREFIXES):
                f.risk = "low"
                continue

            if sub_category == "augur_segment":
                abs_path = project_root / f.file
                if abs_path.exists():
                    try:
                        lines = abs_path.read_text(encoding="utf-8").split("\n")
                        if f.line <= len(lines):
                            line = lines[f.line - 1]
                            if "augur/data" in line:
                                continue
                            if "data_dir:" in line:
                                continue
                    except (OSError, UnicodeDecodeError):
                        pass

            if "/test" in f.file and sub_category == "global_data_root":
                continue

            findings.append(f)

    return findings
