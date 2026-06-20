"""auto-self-heal: Scan runtime logs for errors and delegate fixes to ai_self_healer.

Extracted from SelfHealLoop (ADR-200). The adaptive engine discovers this module
via SKILL.md frontmatter and calls scan() then trust-gated fix().

ADR-572 main-checkout gate: fix() never mutates from a linked worktree.
scan() still reports findings in validation-only mode so worktree dashboard
verification can see failures without prompting IDE/window updates for main.
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
import importlib.util
import subprocess
import sys
from pathlib import Path

from src.lib.ops_protocol import FixResult, OpsContext, ScanResult


def _is_inside_worktree(project_root: Path) -> bool:
    """ADR-572 gate: load worktree_guard.is_inside_worktree without depending on PYTHONPATH.

    Fail-open: returns False when the guard module can't be loaded so that
    a deployment where platform-admin is missing still runs self-heal.
    """
    guard_path = (
        Path(__file__).resolve().parents[3]
        / "platform-admin"
        / "scripts"
        / "worktree_guard.py"
    )
    if not guard_path.exists():
        return False
    spec = importlib.util.spec_from_file_location(
        "_self_heal_worktree_guard", guard_path
    )
    if spec is None or spec.loader is None:
        return False
    module = sys.modules.get("_self_heal_worktree_guard")
    if module is None:
        module = importlib.util.module_from_spec(spec)
        sys.modules["_self_heal_worktree_guard"] = module
        spec.loader.exec_module(module)
    return bool(module.is_inside_worktree(project_root))

# Severity -> engine category mapping (preserved from SelfHealLoop)
SEVERITY_CATEGORY_MAP = {
    "critical": "import-fixes",  # Most urgent, lowest tier
    "high": "config-fixes",
    "medium": "logic-fixes",
    "low": "logic-fixes",
}

# Terminal statuses where the registry entry is resolved — no further action needed
_TERMINAL_STATUSES = frozenset({
    "abandoned", "dismissed", "wont_fix", "fixed", "todo_created",
})
_MAX_FIX_ATTEMPTS = 3

# Graceful optional import — tests can patch _healer at module level
try:
    import ai_self_healer as _healer_mod

    class _HealerAdapter:
        """Thin adapter bridging ai_self_healer module functions to the scan/fix interface."""

        def __init__(self):
            self._config = _healer_mod.load_config()

        def scan_for_errors(self):
            """Scan runtime logs, filtering out already-resolved registry entries."""
            findings = _healer_mod.scan_runtime(self._config)
            if not findings:
                return findings
            registry = _healer_mod.load_registry()
            if not registry:
                return findings
            filtered = []
            for f in findings:
                entry = registry.get(f.dedup_key)
                if entry and entry.status in _TERMINAL_STATUSES:
                    continue
                if (
                    entry
                    and entry.status == "failed"
                    and entry.fix_attempts >= _MAX_FIX_ATTEMPTS
                ):
                    continue
                filtered.append(f)
            return filtered

        def fix_entry(self, entry_key: str) -> dict:
            """Run the classify->route->fix pipeline for a single registry entry."""
            registry = _healer_mod.load_registry()
            entry = registry.get(entry_key)
            if entry and (
                entry.status in _TERMINAL_STATUSES
                or (
                    entry.status == "failed"
                    and entry.fix_attempts >= _MAX_FIX_ATTEMPTS
                )
            ):
                return {"success": True, "skipped": True}
            summary = _healer_mod.run_pipeline(self._config)
            succeeded = summary.get("fixes_succeeded", 0) if summary else 0
            return {
                "success": succeeded > 0,
                "error": summary.get("error") if summary else None,
            }

    _healer = _HealerAdapter()
except ImportError:
    _healer = None

# Module-level reference so tests can patch without import-time failures
healer = _healer

name = "auto-self-heal"


def _commit_files(project_root: Path, message: str, paths: list[str]) -> str | None:
    """Stage specific paths and commit. Returns commit hash or None."""
    for p in paths:
        subprocess.run(
            ["git", "add", p],
            capture_output=True,
            cwd=str(project_root),
        )
    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        capture_output=True,
        cwd=str(project_root),
    )
    if result.returncode == 0:
        return None  # No staged changes
    result = subprocess.run(
        ["git", "commit", "-m", message],
        capture_output=True,
        text=True,
        cwd=str(project_root),
    )
    if result.returncode == 0:
        rev = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )
        return rev.stdout.strip() if rev.returncode == 0 else None
    return None


def scan(ctx: OpsContext) -> ScanResult:
    """Delegate to healer's scan cycle; translate findings into issues."""
    worktree_validation_only = _is_inside_worktree(ctx.project_root)

    if healer is None:
        issue = {
            "kind": "scanner-defect",
            "detail": "ai_self_healer not importable",
            "fixability": "manual",
        }
        if worktree_validation_only:
            issue["worktree_validation_only"] = True
        return ScanResult(
            issues=[issue],
            summary="ai_self_healer not importable — self-heal scan disabled",
            severity="error",
            health="broken",
        )

    try:
        findings = healer.scan_for_errors()
    except Exception as exc:
        return ScanResult(
            issues=[],
            summary=f"Healer scan raised: {exc}",
            severity="info",
        )

    # Read min_severity from config (ADR-216), default to "high"
    min_severity = ctx.config.get("min_severity", "high")
    severity_levels = ["low", "medium", "high", "critical"]
    min_idx = severity_levels.index(min_severity) if min_severity in severity_levels else 2
    allowed_severities = set(severity_levels[min_idx:])

    issues = []
    for finding in findings:
        severity = getattr(finding, "severity", "medium")
        if severity not in allowed_severities:
            continue
        issues.append({
            "action": f"fix-{finding.dedup_key[:8]}",
            "category": SEVERITY_CATEGORY_MAP.get(severity, "logic-fixes"),
            "entry_key": finding.dedup_key,
            "message": finding.message,
            "file": finding.file,
            "worktree_validation_only": worktree_validation_only,
        })

    if not issues:
        summary = (
            "No runtime errors found in validation-only worktree mode"
            if worktree_validation_only
            else "No runtime errors found"
        )
        return ScanResult(issues=[], summary=summary, severity="info")

    # Derive overall severity from the most urgent finding
    categories = {i["category"] for i in issues}
    overall = (
        "error"
        if "import-fixes" in categories
        else "warning"
        if "config-fixes" in categories
        else "info"
    )
    return ScanResult(
        issues=issues,
        summary=(
            f"{len(issues)} runtime error(s) found in validation-only worktree mode"
            if worktree_validation_only
            else f"{len(issues)} runtime error(s) found"
        ),
        severity=overall,
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Delegate each issue's fix to healer's fix_entry(); commit changed files."""
    if _is_inside_worktree(ctx.project_root):
        actions = [
            {
                "entry_key": issue.get("entry_key"),
                "skipped": True,
                "reason": "validation-only worktree mode",
            }
            for issue in issues
        ]
        return FixResult(
            success=True,
            actions=actions,
            changes=[],
            summary=(
                "Worktree self-heal is validation-only; "
                f"reported {len(issues)} issue(s) without mutation"
            ),
            fix_type="report",
        )

    if healer is None:
        return FixResult(
            success=False,
            summary="ai_self_healer not importable — cannot fix",
        )

    if ctx.dry_run:
        return FixResult(
            success=True,
            summary=f"Dry run: would attempt fixes for {len(issues)} issue(s)",
        )

    all_actions: list[dict] = []
    all_changes: list[str] = []
    overall_success = True

    for issue in issues:
        entry_key = issue.get("entry_key", "")
        if not entry_key:
            continue
        try:
            result = healer.fix_entry(entry_key)
        except Exception as exc:
            overall_success = False
            all_actions.append({"entry_key": entry_key, "error": str(exc)})
            continue

        if result.get("skipped"):
            all_actions.append({"entry_key": entry_key, "skipped": True})
            continue

        if result.get("success"):
            file_path = issue.get("file", "")
            if file_path:
                all_changes.append(file_path)
                commit = _commit_files(
                    ctx.project_root,
                    f"fix(adaptive): self-heal {entry_key[:8]}",
                    paths=[file_path],
                )
                all_actions.append({"entry_key": entry_key, "commit": commit})
            else:
                all_actions.append({"entry_key": entry_key, "success": True})
        else:
            overall_success = False
            all_actions.append({
                "entry_key": entry_key,
                "error": result.get("error", "unknown"),
            })

    fixed = sum(1 for a in all_actions if a.get("success") or a.get("commit"))
    skipped = sum(1 for a in all_actions if a.get("skipped"))
    return FixResult(
        success=overall_success,
        actions=all_actions,
        changes=all_changes,
        summary=(
            f"Fixed {fixed} issue(s), skipped {skipped}"
            if all_actions
            else "No issues processed"
        ),
    )
