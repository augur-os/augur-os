"""auto-vault-hygiene: Monitor vault for structural violations and git health.

Expanded from ADR-416 structural checks + ADR-474 git health:
  d0: binary detection, orphan dirs, stale files, hardening-reports, git health
  d1: large file guard, cross-refs, plugin alignment, repo size, config.yaml,
      misplaced root files, permission checks
  d2: binary eviction to Documents, duplicate folders
  d3: full structure audit, nested self-duplicates
  d4: evolution gaps for untested areas

Fix escalation:
  d0: report only
  d1+: commit, gitignore, git gc, config/hardening migration, remove empty dirs,
       fix file permissions (0o644 for files, 0o755 for dirs), move misplaced
       root-level files into matching skill dirs
  d2+: evict binaries to Documents
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
import logging
import shutil
import subprocess
import time
from pathlib import Path

from src.lib.brain_manifest import STANDARD_BRAIN_FILES
from src.lib.ops_protocol import OpsContext, ScanResult, FixResult, evolution_gap

name = "auto-vault-hygiene"

# Vault junk removal operates on the external vault repo, not the project repo.
# The mechanical fix engine (apply_mechanical_fixes) must not attempt a
# project-git commit for these findings — set external_commit=True so it
# records the fix as applied without a project-side git commit.
external_commit = True

DIFFICULTY_SPEC = {
    0: "Surface — binary detection, orphan dirs, stale files, hardening-reports, git health",
    1: "Content — large file guard, cross-refs, plugin alignment, repo size, config.yaml",
    2: "Deep — binary eviction to Documents, duplicate folders",
    3: "Exhaustive — full structure audit, nested self-duplicates",
    4: "Expert — evolution gaps for untested areas",
}

logger = logging.getLogger(__name__)

SKIP_DIRS = {"_config", "_cache", ".DS_Store"}
# Post-ADR-771: content lives under knowledge/ and capabilities/; the legacy
# flat names (notes, sources, wiki, skills, memory) are no longer sanctioned.
ALLOWED_TOP_DIRS = {"inbox", "drafts", "archive", "config", ".git"}
LEGACY_TOP_DIRS = {"_drafts", "_system"}
# Canonical brain root files (ADR-771 brain layout): the brain manifest plus the
# standard brain files legitimately live AT the vault/brain root, so they must
# never be flagged as "misplaced root files".
CANONICAL_ROOT_FILES = {"BRAIN.yaml", *STANDARD_BRAIN_FILES}

BINARY_EXTENSIONS = {
    ".m4a", ".xlsx", ".docx", ".png", ".svg", ".jpg", ".jpeg",
    ".pdf", ".zip", ".tar", ".gz", ".mp3", ".mp4", ".wav",
}

# Patterns that vault .gitignore should exclude (ADR-474)
EXPECTED_GITIGNORE_PATTERNS = {".DS_Store", "__pycache__/", "*.pyc", "._*", "_cache/", "_config/"}


def _is_binary(path: Path) -> bool:
    return path.suffix.lower() in BINARY_EXTENSIONS


def _is_skill_owned(rel: Path) -> bool:
    """True for files inside a skill dir (skills/* or capabilities/skills/*).

    Skill-owned binary assets (e.g. pandoc reference.docx templates) are part
    of the skill, not vault content — evicting them breaks the skill.
    """
    return rel.parts[:1] == ("skills",) or rel.parts[:2] == ("capabilities", "skills")


def _get_vault(project_root: Path | None = None) -> Path:
    from src.config.paths import get_configured_vault_dir
    return get_configured_vault_dir(project_root)


def _get_registered_plugins() -> set[str]:
    """Get all x-augur-plugin values from project-brain/capabilities/skills/*/SKILL.md."""
    from src.config.paths import get_project_root
    import yaml as _yaml
    plugins: set[str] = set()
    skills_dir = get_project_root() / "project-brain" / "capabilities" / "skills"
    if not skills_dir.exists():
        return plugins
    for skill_dir in skills_dir.iterdir():
        if not skill_dir.is_dir() or skill_dir.name.startswith("."):
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            continue
        try:
            content = skill_md.read_text()
            if not content.startswith("---"):
                continue
            end = content.index("---", 3)
            fm = _yaml.safe_load(content[3:end])
            if isinstance(fm, dict) and fm.get("x-augur-plugin"):
                plugins.add(fm["x-augur-plugin"])
        except Exception:
            continue
    return plugins


def _run_git(vault: Path, *args: str) -> tuple[bool, str]:
    """Run a git command in the vault. Returns (success, stdout)."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(vault), capture_output=True, text=True, timeout=10,
        )
        return result.returncode == 0, result.stdout.strip()
    except Exception:
        return False, ""


def _is_git_metadata(path: Path, vault: Path) -> bool:
    try:
        rel = path.relative_to(vault)
    except ValueError:
        return False
    return bool(rel.parts) and rel.parts[0] == ".git"


def _is_valid_top_dir(vault: Path, name: str) -> bool:
    if name in LEGACY_TOP_DIRS:
        return False
    if name in ALLOWED_TOP_DIRS:
        return True
    from src.config.paths import get_skill_vault_relative_dir

    if get_skill_vault_relative_dir(name) != Path(name):
        return False

    from src.lib.dir_alignment import ManagedLocation, validate_dir_name

    return validate_dir_name(ManagedLocation(path=vault), name)


def _unique_destination(path: Path) -> Path:
    """Return a non-existing sibling path by appending a numeric suffix."""
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    counter = 1
    while True:
        candidate = parent / f"{stem}-{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def check_git_health(vault: Path) -> list[dict]:
    """ADR-474: Check vault git health.

    Checks:
    1. Vault is a git repo
    2. Uncommitted changes
    3. Unpushed commits
    4. .gitignore excludes binary files
    """
    issues: list[dict] = []

    # 1. Is the vault a git repo?
    if not (vault / ".git").exists():
        issues.append({
            "file": ".git",
            "message": "vault is not a git repo — run: cd <vault_dir> && git init",
            "severity": "warning",
            "kind": "actionable",
        })
        return issues  # Cannot check further without git

    # 2. Uncommitted changes
    ok, status_output = _run_git(vault, "status", "--porcelain")
    if ok and status_output:
        dirty_count = len(status_output.splitlines())
        issues.append({
            "file": "vault-wide",
            "message": f"{dirty_count} uncommitted changes in vault",
            "severity": "warning",
            "kind": "maintenance",
        })

    # 3. Unpushed commits
    ok, unpushed = _run_git(vault, "log", "--oneline", "@{u}..HEAD")
    if ok and unpushed:
        unpushed_count = len(unpushed.splitlines())
        issues.append({
            "file": "vault-wide",
            "message": f"{unpushed_count} unpushed commits in vault",
            "severity": "info",
            "kind": "maintenance",
        })

    # 4. .gitignore excludes binary files
    gitignore = vault / ".gitignore"
    if not gitignore.exists():
        issues.append({
            "file": ".gitignore",
            "message": "vault has no .gitignore — binary files may be tracked",
            "severity": "warning",
            "kind": "maintenance",
        })
    else:
        gitignore_content = gitignore.read_text()
        gitignore_lines = {line.strip() for line in gitignore_content.splitlines() if line.strip() and not line.startswith("#")}
        missing = EXPECTED_GITIGNORE_PATTERNS - gitignore_lines
        if missing:
            issues.append({
                "file": ".gitignore",
                "message": f"vault .gitignore missing patterns: {', '.join(sorted(missing))}",
                "severity": "info",
                "kind": "maintenance",
            })

    return issues


def _scan_os_cache_junk(vault_root: Path) -> list[dict]:
    """Scan vault_root for OS/cache junk files (.DS_Store, Thumbs.db, .pyc).

    These are gitignored by vault policy and invisible to ``git status``, so
    they must be discovered by a direct disk scan.  Each returned finding
    carries ``finding_band: "mechanical"`` so the adaptive-loop engine
    auto-applies the fix even in headless (no-LLM) mode.
    """
    findings: list[dict] = []
    _JUNK_SKIP_DIRS = {".venv", "node_modules", ".git"}
    for f in vault_root.rglob("*"):
        if _is_git_metadata(f, vault_root):
            continue
        try:
            rel = f.relative_to(vault_root)
        except ValueError:
            continue
        if any(part in _JUNK_SKIP_DIRS for part in rel.parts[:-1]):
            continue
        if f.is_file() and (f.name in {".DS_Store", "Thumbs.db"} or f.suffix == ".pyc"):
            findings.append({
                "file": str(f.relative_to(vault_root)),
                "path": str(f),
                "message": f"OS/cache junk: {f.name}",
                "severity": "info",
                "kind": "cache_junk",
                # Band as mechanical: deletion is atomic, safe at any difficulty,
                # and requires no LLM reasoning — this is pure file removal.
                "finding_band": "mechanical",
                # auto_command is also injected by scan_phase, but set it here
                # explicitly so _scan_os_cache_junk works in isolation (tests).
                "auto_command": name,
            })
    return findings


def scan(ctx: OpsContext) -> ScanResult:
    """Scan vault for structural violations and git health issues."""
    vault = _get_vault(ctx.project_root)
    if not vault.exists():
        issues = []
        if ctx.difficulty >= 1:
            issues.append({
                "file": str(vault),
                "message": f"configured vault path does not exist: {vault}",
                "severity": "info",
                "kind": "environment",
            })
        return ScanResult(
            issues=issues,
            summary=f"Configured vault not found: {vault}",
            severity="info",
            health="verified",
        )

    issues: list[dict] = []

    # --- d0 checks ---

    # Git health (ADR-474)
    issues.extend(check_git_health(vault))

    # Hardening-reports in vault (should be in state dir)
    for d in vault.rglob("hardening-reports"):
        if d.is_dir() and any(d.iterdir()):
            file_count = sum(1 for f in d.rglob("*") if f.is_file())
            issues.append({
                "file": str(d.relative_to(vault)),
                "message": f"hardening-reports/ in vault ({file_count} files) — run: python3 scripts/vault_hygiene/migrate_hardening.py --apply",
                "severity": "warning",
                "kind": "actionable",
            })

    # OS/cache junk — gitignored, so invisible to git status; scan disk directly.
    # Applies vault-wide including drafts/staging: removing cache junk does not
    # consume staged payloads, it just keeps the store clean.
    issues.extend(_scan_os_cache_junk(vault))

    # Binary files in vault (text-only policy; skill-owned assets are exempt)
    for f in vault.rglob("*"):
        if _is_git_metadata(f, vault):
            continue
        if f.is_file() and _is_binary(f) and not _is_skill_owned(f.relative_to(vault)):
            issues.append({
                "file": str(f.relative_to(vault)),
                "message": f"binary file in vault: {f.name} — will be evicted to Documents",
                "severity": "warning",
                "kind": "binary_eviction",
            })

    # Orphan vault dirs (flat structure: each top-level dir is a skill or reserved dir)
    from src.config.paths import get_all_client_skill_dirs, get_skills_dir
    skills_dir = get_skills_dir()
    for entry in vault.iterdir():
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        if _is_valid_top_dir(vault, entry.name):
            continue
        skill_name = entry.name
        skill_found = (skills_dir / skill_name).is_dir()
        if not skill_found:
            for client_dir in get_all_client_skill_dirs():
                if (client_dir / skill_name).is_dir():
                    skill_found = True
                    break
        if not skill_found:
            issues.append({
                "file": skill_name,
                "message": f"orphan vault dir: no matching skill '{skill_name}' in any client or plugin source",
                "severity": "info",
                "kind": "maintenance",
            })

    # Stale files (not modified in 90+ days)
    ninety_days_ago = time.time() - (90 * 86400)
    stale_count = 0
    for f in vault.rglob("*"):
        if _is_git_metadata(f, vault):
            continue
        if f.is_file() and not f.name.startswith("."):
            try:
                if f.stat().st_mtime < ninety_days_ago:
                    stale_count += 1
            except OSError:
                continue
    if stale_count > 0:
        issues.append({
            "file": "vault-wide",
            "message": f"{stale_count} files not modified in 90+ days",
            "severity": "info",
            "kind": "maintenance",
        })

    # Empty dirs (brain skeleton dirs are intentional structure — never flag)
    from src.lib.brain_manifest import brain_skeleton_paths, is_brain_root
    from src.lib.brain_layout import brain_layout
    skeleton_paths = brain_skeleton_paths(brain_layout(vault)) if is_brain_root(vault) else frozenset()
    for d in vault.rglob("*"):
        if d.parent == vault and _is_valid_top_dir(vault, d.name):
            continue
        if str(d.relative_to(vault)) in skeleton_paths:
            continue
        if d.is_dir() and not any(d.iterdir()) and d.name not in SKIP_DIRS:
            issues.append({
                "file": str(d.relative_to(vault)),
                "message": "empty directory",
                "severity": "info",
                "kind": "maintenance",
            })

    # Misplaced root files (files directly in vault root that should be in a
    # subdir). Canonical brain root files (BRAIN.yaml + the standard brain files)
    # legitimately live here and are never misplaced.
    for entry in vault.iterdir():
        if (
            entry.is_file()
            and not entry.name.startswith(".")
            and entry.name not in CANONICAL_ROOT_FILES
        ):
            issues.append({
                "file": entry.name,
                "message": f"misplaced root file: {entry.name} — vault root should only contain directories",
                "severity": "warning",
                "kind": "misplaced_file",
            })

    # --- d1 checks ---

    if ctx.difficulty >= 1:
        # File permission checks (non-standard permissions)
        import stat as stat_mod
        for f in vault.rglob("*"):
            if f.name.startswith(".") or _is_git_metadata(f, vault):
                continue
            try:
                mode = f.stat().st_mode
                if f.is_file():
                    # Files should be 0o644 (owner rw, group/other r)
                    file_perms = stat_mod.S_IMODE(mode)
                    if file_perms & 0o111:  # executable bit set on a data file
                        issues.append({
                            "file": str(f.relative_to(vault)),
                            "message": f"executable permission on data file (mode {oct(file_perms)})",
                            "severity": "info",
                            "kind": "permission_fix",
                        })
                elif f.is_dir():
                    dir_perms = stat_mod.S_IMODE(mode)
                    if not (dir_perms & 0o100):  # owner execute missing on dir
                        issues.append({
                            "file": str(f.relative_to(vault)),
                            "message": f"missing execute permission on directory (mode {oct(dir_perms)})",
                            "severity": "info",
                            "kind": "permission_fix",
                        })
            except OSError:
                continue

        # config.yaml alongside .md user data
        for config_file in vault.rglob("config.yaml"):
            parent = config_file.parent
            if parent.name in SKIP_DIRS or parent.name.startswith("_"):
                continue
            if list(parent.glob("*.md")):
                issues.append({
                    "file": str(config_file.relative_to(vault)),
                    "message": "config.yaml alongside .md files — move to _config/",
                    "severity": "warning",
                    "kind": "actionable",
                })

        # Large file guard (>1MB)
        for f in vault.rglob("*"):
            if _is_git_metadata(f, vault):
                continue
            if f.is_file():
                try:
                    size = f.stat().st_size
                    if size > 1_000_000:
                        issues.append({
                            "file": str(f.relative_to(vault)),
                            "message": f"large file: {size / 1_000_000:.1f}MB — review if this belongs in vault",
                            "severity": "warning",
                            "kind": "maintenance",
                        })
                except OSError:
                    continue

        # Plugin alignment: unknown top-level dirs
        registered_plugins = _get_registered_plugins()
        for d in vault.iterdir():
            if not d.is_dir() or d.name.startswith("."):
                continue
            if d.name not in registered_plugins and not _is_valid_top_dir(vault, d.name):
                issues.append({
                    "file": d.name,
                    "message": f"unknown top-level dir '{d.name}' — not a registered x-augur-plugin value",
                    "severity": "info",
                    "kind": "maintenance",
                })

        # Repo size monitoring
        git_dir = vault / ".git"
        if git_dir.exists():
            try:
                git_size = sum(f.stat().st_size for f in git_dir.rglob("*") if f.is_file())
                if git_size > 100_000_000:
                    issues.append({
                        "file": ".git",
                        "message": f".git dir is {git_size / 1_000_000:.0f}MB — running git gc recommended",
                        "severity": "warning",
                        "kind": "actionable",
                    })
            except OSError:
                pass

    # --- d2 checks ---

    if ctx.difficulty >= 2:
        # Duplicate folder names within a skill (flat vault: top-level dirs are skills)
        for skill_dir in vault.iterdir():
            if not skill_dir.is_dir() or skill_dir.name.startswith("."):
                continue
            if _is_valid_top_dir(vault, skill_dir.name):
                continue
            seen_names: dict[str, Path] = {}
            for d in skill_dir.rglob("*"):
                if not d.is_dir() or d.name.startswith("_"):
                    continue
                if d.name in seen_names:
                    issues.append({
                        "file": str(d.relative_to(vault)),
                        "message": f"duplicate folder name '{d.name}' (also at {seen_names[d.name].relative_to(vault)})",
                        "severity": "info",
                        "kind": "maintenance",
                    })
                else:
                    seen_names[d.name] = d

    # --- d3 checks ---

    if ctx.difficulty >= 3:
        # Nested self-duplicates (parent.name == child.name)
        for d in vault.rglob("*"):
            if d.is_dir() and d.parent.name == d.name and d.parent != vault:
                issues.append({
                    "file": str(d.relative_to(vault)),
                    "message": f"nested self-duplicate: {d.parent.name}/{d.name}/",
                    "severity": "warning",
                    "kind": "actionable",
                })

    # --- d4: evolution gaps ---

    if ctx.difficulty >= 4 and not issues:
        issues.append(evolution_gap(
            "All vault hygiene checks (including git health) pass at max difficulty. "
            "Consider adding: frontmatter validation for vault .md files, "
            "vault-to-code bidirectional sync verification, git hook validation.",
            category="vault-hygiene",
        ))

    severity = "warning" if any(i.get("severity") == "warning" for i in issues) else "info"
    health = "degraded" if severity == "warning" else "verified"

    return ScanResult(
        issues=issues,
        summary=f"{len(issues)} vault hygiene issues" if issues else "Vault clean",
        severity=severity,
        health=health,
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Fix vault hygiene issues based on difficulty level.

    Difficulty escalation:
    - d0: remove OS/cache junk (mechanical, always safe) — no other modifications
    - d1+: commit uncommitted changes, fix .gitignore, git gc, config migration,
            hardening migration, remove empty dirs, fix permissions, move misplaced
            root files into the best-matching skill subdirectory
    - d2+: evict binary files to Documents
    """
    if ctx.dry_run:
        return FixResult(success=True, summary=f"Dry run: {len(issues)} issues found")

    if not issues:
        return FixResult(success=True, summary="No issues to fix")

    vault = _get_vault(ctx.project_root)
    actions: list[dict] = []
    changes: list[str] = []
    errors: list[str] = []

    # Remove OS/cache junk at d0+ — junk removal is always safe regardless of
    # difficulty because .DS_Store/.pyc files are gitignored ephemera with no
    # semantic value.  Banded as "mechanical" in _scan_os_cache_junk so the
    # orchestrator's apply_mechanical_fixes path can auto-apply even headless.
    junk_issues = [i for i in issues if i.get("kind") == "cache_junk"]
    for issue in junk_issues:
        junk_path = vault / issue["file"]
        if junk_path.is_file():
            try:
                junk_path.unlink()
                # Return the vault-relative path so apply_mechanical_fixes can
                # record it (external_commit=True means no project git commit).
                changes.append(issue["file"])
                parent = junk_path.parent
                if parent.name == "__pycache__" and not any(parent.iterdir()):
                    parent.rmdir()
            except OSError:
                pass
    if junk_issues:
        actions.append({"action": "remove_cache_junk", "count": len(junk_issues)})

    if ctx.difficulty < 1:
        # Only junk removal runs at d0; all other fixes require d1+.
        if not junk_issues:
            return FixResult(
                success=True,
                actions=[{"action": "report", "description": "Difficulty 0 — report only"}],
                summary=f"No actionable fixes at d0; report only: {len(issues)} vault hygiene issue(s) detected",
                fix_type="report",
            )
        summary = f"Removed {len(changes)} junk file(s) at d0 (mechanical)"
        return FixResult(
            success=True,
            actions=actions,
            changes=changes,
            summary=summary,
            fix_type="code-fix",
        )

    # Hardening migration
    actionable = [i for i in issues if i.get("kind") == "actionable"]
    hardening_issues = [i for i in actionable if "hardening-reports" in i.get("message", "")]
    if hardening_issues:
        migrate_script = ctx.project_root / "scripts" / "vault_hygiene" / "migrate_hardening.py"
        if migrate_script.exists():
            result = subprocess.run(
                ["python3", str(migrate_script), "--apply"],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode == 0:
                actions.append({"action": "migrate_hardening", "success": True, "output": result.stdout[-200:]})
                changes.append("Migrated hardening-reports out of vault")
            else:
                detail = (result.stderr or result.stdout or "").strip()
                actions.append({"action": "migrate_hardening", "success": False, "output": result.stdout[-200:]})
                errors.append(f"hardening migration failed{f': {detail}' if detail else ''}")

    # Config migration
    config_issues = [i for i in actionable if "config.yaml" in i.get("message", "")]
    if config_issues:
        migrate_script = ctx.project_root / "scripts" / "vault_hygiene" / "migrate_config.py"
        if migrate_script.exists():
            result = subprocess.run(
                ["python3", str(migrate_script), "--apply"],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode == 0:
                actions.append({"action": "migrate_config", "success": True, "output": result.stdout[-200:]})
                changes.append("Migrated config.yaml files to _config/")
            else:
                detail = (result.stderr or result.stdout or "").strip()
                actions.append({"action": "migrate_config", "success": False, "output": result.stdout[-200:]})
                errors.append(f"config migration failed{f': {detail}' if detail else ''}")

    # Fix .gitignore missing patterns
    gitignore_issues = [i for i in issues if "gitignore" in i.get("message", "").lower()]
    for issue in gitignore_issues:
        msg = issue.get("message", "")
        if "no .gitignore" in msg:
            # Create .gitignore with expected patterns
            gitignore_path = vault / ".gitignore"
            content = "# Auto-generated vault .gitignore (ADR-474)\n"
            for pattern in sorted(EXPECTED_GITIGNORE_PATTERNS):
                content += f"{pattern}\n"
            gitignore_path.write_text(content)
            actions.append({"action": "create_gitignore", "file": ".gitignore"})
            changes.append("Created vault .gitignore with standard patterns")
        elif "missing patterns" in msg:
            # Append missing patterns to existing .gitignore
            gitignore_path = vault / ".gitignore"
            if gitignore_path.exists():
                existing = gitignore_path.read_text()
                existing_lines = {line.strip() for line in existing.splitlines() if line.strip() and not line.startswith("#")}
                missing = EXPECTED_GITIGNORE_PATTERNS - existing_lines
                if missing:
                    append_text = "\n# Added by auto-vault-hygiene\n"
                    for pattern in sorted(missing):
                        append_text += f"{pattern}\n"
                    gitignore_path.write_text(existing.rstrip("\n") + "\n" + append_text)
                    actions.append({"action": "update_gitignore", "added": sorted(missing)})
                    changes.append(f"Added {len(missing)} missing pattern(s) to vault .gitignore")

    # Git health: commit uncommitted changes
    uncommitted_issues = [i for i in issues if "uncommitted changes" in i.get("message", "")]
    if uncommitted_issues and vault.exists() and (vault / ".git").exists():
        subprocess.run(
            ["git", "add", "-u"],
            cwd=str(vault), capture_output=True, timeout=10,
        )
        result = subprocess.run(
            ["git", "commit", "-m", "chore(auto): vault-hygiene auto-commit"],
            cwd=str(vault), capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            actions.append({"action": "vault_commit", "success": True})
            changes.append("Committed uncommitted vault changes")
        else:
            actions.append({"action": "vault_commit", "success": False})
            errors.append("vault git commit failed")

    # Remove empty directories
    empty_dir_issues = [i for i in issues if i.get("message") == "empty directory"]
    for issue in empty_dir_issues:
        empty_path = vault / issue["file"]
        if empty_path.is_dir() and not any(empty_path.iterdir()):
            try:
                empty_path.rmdir()
                actions.append({"action": "remove_empty_dir", "dir": issue["file"]})
                changes.append(f"Removed empty dir {issue['file']}")
            except OSError:
                pass  # Race condition or permissions — skip

    # Move misplaced root-level files into the best-matching skill subdir
    misplaced_issues = [i for i in issues if i.get("kind") == "misplaced_file"]
    if misplaced_issues:
        from src.config.paths import get_skills_dir
        skill_names = set()
        skills_dir = get_skills_dir()
        if skills_dir.is_dir():
            skill_names = {d.name for d in skills_dir.iterdir() if d.is_dir() and not d.name.startswith(".")}
        for issue in misplaced_issues:
            src_path = vault / issue["file"]
            if not src_path.exists() or not src_path.is_file():
                continue
            # Try to match filename stem to a skill name
            stem = src_path.stem.lower().replace("_", "-").replace(" ", "-")
            matched_skill = None
            for sn in skill_names:
                if sn in stem or stem in sn:
                    matched_skill = sn
                    break
            if matched_skill:
                dest_dir = vault / matched_skill
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest = dest_dir / src_path.name
                if not dest.exists():
                    try:
                        shutil.move(str(src_path), str(dest))
                        actions.append({"action": "move_misplaced", "from": issue["file"], "to": str(dest.relative_to(vault))})
                        changes.append(f"Moved {src_path.name} to {matched_skill}/")
                    except OSError as e:
                        logger.warning(f"Failed to move {src_path.name}: {e}")
            # If no skill match, leave in place (ambiguous — report only)

    # Fix file permissions
    import stat as stat_mod
    permission_issues = [i for i in issues if i.get("kind") == "permission_fix"]
    for issue in permission_issues:
        target = vault / issue["file"]
        if not target.exists():
            continue
        try:
            if target.is_file():
                # Remove executable bits from data files: set to 0o644
                target.chmod(0o644)
                actions.append({"action": "fix_permission", "file": issue["file"], "mode": "0o644"})
                changes.append(f"Fixed permissions on {issue['file']} to 0o644")
            elif target.is_dir():
                # Ensure directories have owner execute: set to 0o755
                target.chmod(0o755)
                actions.append({"action": "fix_permission", "file": issue["file"], "mode": "0o755"})
                changes.append(f"Fixed permissions on {issue['file']} to 0o755")
        except OSError as e:
            logger.warning(f"Failed to fix permissions on {issue['file']}: {e}")

    # Binary eviction (d2+)
    binary_issues = [i for i in issues if i.get("kind") == "binary_eviction"]
    if binary_issues and ctx.difficulty >= 2:
        from src.config.paths import get_documents_dir
        for issue in binary_issues:
            src_path = vault / issue["file"]
            if not src_path.exists():
                continue
            parts = Path(issue["file"]).parts
            if len(parts) >= 1:
                skill_name = parts[0]
                try:
                    # Mirror the vault top-level dir under Documents. Use the
                    # documents root directly (not get_skill_documents_dir, which
                    # validates against skill names) so binaries in legitimate
                    # vault content dirs that are NOT skills — meetings, notes,
                    # finance, voice-memos — still evict instead of erroring.
                    dest_dir = get_documents_dir() / skill_name
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    dest = _unique_destination(dest_dir / src_path.name)
                    shutil.move(str(src_path), str(dest))
                    subprocess.run(
                        ["git", "add", "-u"],
                        cwd=str(vault), capture_output=True,
                    )
                    commit_result = subprocess.run(
                        ["git", "commit", "-m", f"vault: evict binary {src_path.name} to Documents"],
                        cwd=str(vault), capture_output=True,
                    )
                    if commit_result.returncode == 0:
                        actions.append({"action": "evict_binary", "file": issue["file"], "dest": str(dest), "success": True})
                        changes.append(f"Evicted {src_path.name} to Documents")
                    else:
                        actions.append({"action": "evict_binary", "file": issue["file"], "dest": str(dest), "success": False})
                        errors.append(f"vault binary eviction commit failed for {src_path.name}")
                except Exception as e:
                    logger.warning(f"Failed to evict {src_path.name}: {e}")
                    errors.append(f"binary eviction failed for {src_path.name}: {e}")

    # Repo size fix (d1+)
    git_size_issues = [i for i in issues if ".git dir is" in i.get("message", "")]
    if git_size_issues:
        result = subprocess.run(
            ["git", "gc", "--aggressive"],
            cwd=str(vault), capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0:
            actions.append({"action": "git_gc", "success": True})
            changes.append("Ran git gc --aggressive on vault")
        else:
            detail = (result.stderr or result.stdout or "").strip()
            actions.append({"action": "git_gc", "success": False})
            errors.append(f"vault git gc failed{f': {detail}' if detail else ''}")

    success = all(a.get("success", True) for a in actions) and not errors
    if errors:
        summary = f"Fix failed: {'; '.join(errors)}"
    else:
        summary = f"Applied {len(actions)} vault hygiene fix(es), {len(changes)} change(s)" if actions else "No actionable fixes at current difficulty"
    return FixResult(
        success=success,
        actions=actions,
        changes=changes,
        summary=summary,
        fix_type="code-fix" if changes else "report",
    )
