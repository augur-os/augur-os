"""auto-command-evolution: Scan execution logs and evolve SKILL.md files.

Extracted from CommandEvolutionLoop (ADR-200).
Wraps existing ADR-102 infrastructure. Triggered post-execution.
Analyzes command runs and applies auto-safe improvements to SKILL.md files.
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
import json
import subprocess as sp
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from src.lib.git_ops import commit_files
from src.lib.ops_protocol import FixResult, OpsContext, ScanResult

# Re-use existing ADR-102 infrastructure
# The adaptive package lives in the sibling directory
# (skills/ai/scripts/adaptive/). The daemon's adaptive
# package shadows it on sys.path, so we register the ai copy
# under a distinct package name (adr102_adaptive) to avoid collisions.
import sys as _sys


def _load_adr102_adaptive():
    """Import the ai adaptive package under the name 'adr102_adaptive'.

    The daemon's 'adaptive' package shadows the ai copy on sys.path,
    so we register the ai version under a distinct name and load its
    real package __init__ to keep relative-import metadata coherent.
    """
    import importlib.util as _ilu

    pkg_name = "adr102_adaptive"
    if pkg_name in _sys.modules:
        return _sys.modules[pkg_name]

    pkg_dir = Path(__file__).resolve().parent.parent / "adaptive"
    spec = _ilu.spec_from_file_location(
        pkg_name,
        pkg_dir / "__init__.py",
        submodule_search_locations=[str(pkg_dir)],
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load adaptive package from {pkg_dir}")
    pkg = _ilu.module_from_spec(spec)
    _sys.modules[pkg_name] = pkg
    spec.loader.exec_module(pkg)
    return pkg


try:
    _adr102 = _load_adr102_adaptive()
    _ae = _sys.modules["adr102_adaptive.analyze_execution"]
    AutoApply = _ae.AutoApply
    Improvement = _ae.Improvement
    ImprovementPriority = _ae.ImprovementPriority
    ImprovementType = _ae.ImprovementType
    _cr = _sys.modules["adr102_adaptive.command_rewriter"]
    apply_improvement_to_skill = _cr.apply_improvement_to_skill
    find_skill_definition = _cr.find_skill_definition
    log_improvement = _cr.log_improvement

    HAS_ADR102 = True
except ImportError:
    HAS_ADR102 = False

    class ImprovementType(str, Enum):
        FIX_ERROR_PATTERN = "fix_error_pattern"

    class ImprovementPriority(str, Enum):
        HIGH = "high"

    class AutoApply(str, Enum):
        YES = "yes"
        CONDITIONAL = "conditional"

    @dataclass
    class Improvement:
        type: ImprovementType
        priority: ImprovementPriority
        auto_apply: AutoApply
        description: str
        target_phase: str | None = None
        target_step: str | None = None
        suggested_content: str | None = None
        evidence: str | None = None

    def apply_improvement_to_skill(*a, **kw):
        return False

    def find_skill_definition(*a, **kw):
        return None

    def log_improvement(*a, **kw):
        return None


name = "auto-command-evolution"

# Category -> ImprovementType mapping (preserved from original loop)
CATEGORY_TYPES = {
    "timeout-hints": {"add_timeout", "add_hint"},
    "cache-keys": {"add_cache"},
    "missing-steps": {"add_step", "add_check"},
    "reorder-phases": {"reorder_phase"},
    "remove-steps": {"remove_step"},
}


def _commit(project_root: Path, message: str, paths: list[str] | None = None) -> str | None:
    """Stage specific paths (or all) and commit. Returns short hash or None."""
    return commit_files(project_root, message, paths)


def _scan_log(cmd_name: str, data: dict) -> list[dict]:
    """Extract improvement issues from a single execution log."""
    issues: list[dict] = []
    outcome = data.get("outcome", "success")

    # Skip logs from the PostToolUse hook — they only record that a command
    # was invoked, not real execution telemetry. Real telemetry comes from
    # --evolve flag via emit-execution-event (ADR-102).
    if outcome == "executed":
        return issues

    # Failed phases → timeout/splitting hints
    if outcome in ("failure", "partial_success"):
        for phase in data.get("phases", []):
            if phase.get("status") == "failed":
                issues.append(
                    {
                        "action": "add-timeout-hint",
                        "category": "timeout-hints",
                        "command": cmd_name,
                        "improvement": {
                            "type": "add_timeout",
                            "description": f"Add timeout hint to {phase['name']}",
                            "suggested_content": (
                                f'timeout_hint: "Consider splitting {phase["name"]}"'
                            ),
                        },
                    }
                )

    # Recoverable errors → add pre-check steps
    for error in data.get("errors", []):
        if error.get("recoverable"):
            issues.append(
                {
                    "action": "add-pre-check",
                    "category": "missing-steps",
                    "command": cmd_name,
                    "improvement": {
                        "type": "add_check",
                        "description": (
                            f"Add pre-check for recoverable error in "
                            f"{error.get('phase', 'unknown')}: {error.get('message', '')}"
                        ),
                    },
                }
            )

    # Non-recoverable errors → capture as learnings for manual review
    for error in data.get("errors", []):
        if not error.get("recoverable"):
            issues.append(
                {
                    "action": "capture-learning",
                    "category": "timeout-hints",
                    "command": cmd_name,
                    "improvement": {
                        "type": "add_hint",
                        "description": (
                            f"Non-recoverable error in {error.get('phase', 'unknown')}: "
                            f"{error.get('message', '')}"
                        ),
                    },
                }
            )

    # Assessment: what_was_slow → performance hints
    assessment = data.get("assessment", {})
    if assessment.get("what_was_slow"):
        issues.append(
            {
                "action": "add-perf-hint",
                "category": "cache-keys",
                "command": cmd_name,
                "improvement": {
                    "type": "add_cache",
                    "description": f"Performance: {assessment['what_was_slow']}",
                },
            }
        )

    # Assessment: what_to_improve → hint additions
    if assessment.get("what_to_improve"):
        issues.append(
            {
                "action": "capture-learning",
                "category": "timeout-hints",
                "command": cmd_name,
                "improvement": {
                    "type": "add_hint",
                    "description": assessment["what_to_improve"],
                },
            }
        )

    # Learnings → hint additions (always safe tier)
    for learning in data.get("learnings", []):
        issues.append(
            {
                "action": "capture-learning",
                "category": "timeout-hints",
                "command": cmd_name,
                "improvement": {
                    "type": "add_hint",
                    "description": learning,
                },
            }
        )

    return issues


def _scan_self_repair_plan(plan_path: Path, data: dict, *, difficulty: int = 0) -> dict | None:
    """Convert an engine self-repair plan into a queued command-evolution issue.

    Self-repair plans are structural fixes that require d2+ to apply.
    At d0-d1, issues are marked ``kind="maintenance"`` so the engine
    treats them as informational rather than inflating the actionable
    issue count.  At d2+ they become ``kind="manual"`` (actionable)
    so the engine will attempt the fix.
    """
    command = str(data.get("category") or "").strip()
    if not command:
        return None

    stagnation = int(data.get("stagnation_streak") or 0)
    module_path = str(data.get("module_path") or "")
    recommended_focus = str(data.get("recommended_focus") or "repair recurring scanner logic")
    fingerprints = data.get("actionable_fingerprints") or data.get("scanner_defect_fingerprints") or []
    fingerprint_text = ", ".join(str(item) for item in fingerprints[:5])
    evidence = (
        f"self-repair plan from {plan_path.name}; "
        f"stagnation_streak={stagnation}; "
        f"module={module_path or 'unknown'}; "
        f"fingerprints={fingerprint_text or 'none'}"
    )
    plugin_root = str(data.get("plugin_root") or "")
    skill_path = str((Path(plugin_root) / "SKILL.md")) if plugin_root else ""
    candidate_test_files = data.get("candidate_test_files") or []
    auto_apply_safe = bool(
        plugin_root
        and skill_path
        and candidate_test_files
        and Path(skill_path).exists()
        and stagnation <= 3
    )

    # At d0-d1 these are deferred (maintenance); at d2+ they become actionable
    issue_kind = "manual" if difficulty >= 2 else "maintenance"

    return {
        "action": "queue-self-repair",
        "category": "self-repair-plans",
        "command": command,
        "kind": issue_kind,
        "root_cause_type": "scanner_bug",
        "path": str(plan_path),
        "source": "self-repair-plan",
        "plugin_root": plugin_root,
        "skill_path": skill_path,
        "auto_apply_safe": auto_apply_safe,
        "improvement": {
            "type": "fix_error_pattern",
            "description": f"Self-repair needed for {command}",
            "suggested_content": recommended_focus,
            "evidence": evidence,
        },
    }


def scan(ctx: OpsContext) -> ScanResult:
    """Scan state/command-evolution/ for execution logs.

    Finds failure patterns, error recovery opportunities, performance hints,
    and learnings in execution logs. Returns one issue dict per improvement
    opportunity found.
    """
    from src.config.paths import get_runtime_dir

    runtime_dir = get_runtime_dir()
    evo_dir = runtime_dir / "command-evolution"
    issues: list[dict] = []

    self_repair_dir = runtime_dir / "adaptive" / "self_repair"
    if self_repair_dir.exists():
        for plan_path in sorted(self_repair_dir.glob("*.json")):
            try:
                data = json.loads(plan_path.read_text())
            except (json.JSONDecodeError, OSError):
                continue
            issue = _scan_self_repair_plan(plan_path, data, difficulty=ctx.difficulty)
            if issue:
                issues.append(issue)

    if evo_dir.exists():
        for cmd_dir in evo_dir.iterdir():
            if not cmd_dir.is_dir():
                continue
            exec_dir = cmd_dir / "executions"
            if not exec_dir.exists():
                continue

            # Use the most recent execution log only
            logs = sorted(exec_dir.glob("*.json"), reverse=True)
            if not logs:
                continue

            try:
                data = json.loads(logs[0].read_text())
            except (json.JSONDecodeError, OSError):
                continue

            issues.extend(_scan_log(cmd_dir.name, data))

    # At d0-d1 the engine's structural gate defers all fixes, so issues
    # that lack an explicit kind (defaulting to "actionable") would inflate
    # the actionable count every cycle despite being intentionally deferred.
    # Mark them as "maintenance" until difficulty reaches d2+ where they can
    # actually be fixed.  This way deferred items naturally transition to
    # actionable as trust grows.
    if ctx.difficulty < 2:
        _SAFE_KINDS = {"clean", "maintenance", "environment"}
        for issue in issues:
            if issue.get("kind", "actionable") not in _SAFE_KINDS:
                issue["kind"] = "maintenance"

    severity = "warning" if issues else "info"
    summary = (
        f"Found {len(issues)} improvement opportunities across command execution logs"
        if issues
        else "No improvement opportunities found in execution logs or self-repair plans"
    )
    return ScanResult(issues=issues, summary=summary, severity=severity)


def _resolve_self_repair_skill_path(issue: dict, project_root: Path) -> Path | None:
    """Resolve the owning SKILL.md for a self-repair plan issue."""
    explicit = str(issue.get("skill_path") or "").strip()
    if explicit:
        path = Path(explicit)
        if path.exists():
            return path

    plugin_root = str(issue.get("plugin_root") or "").strip()
    if plugin_root:
        candidate = Path(plugin_root) / "SKILL.md"
        if candidate.exists():
            return candidate

    command = str(issue.get("command") or "").strip()
    if command:
        return find_skill_definition(command, project_root)
    return None


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Apply improvements to SKILL.md files using ADR-102 infrastructure.

    Each issue dict must contain 'command' and 'improvement' keys.
    Commits changes per-file when not in dry_run mode.
    After processing, cleans up old execution logs so commands can be
    re-analyzed on future runs.
    """
    if not issues:
        return FixResult(success=True, summary="No issues to fix")

    if not HAS_ADR102:
        return FixResult(
            success=False,
            summary="ADR-102 infrastructure not importable; cannot apply improvements",
        )

    if ctx.dry_run:
        return FixResult(
            success=True,
            summary=f"Dry run: would apply {len(issues)} improvements",
            actions=[{"command": i.get("command"), "action": i.get("action")} for i in issues],
        )

    from src.config.paths import get_runtime_dir

    runtime_dir = get_runtime_dir()
    applied_actions: list[dict] = []
    changed_files: list[str] = []
    failed: list[str] = []
    processed_commands: set[str] = set()
    processed_self_repair_plans: list[Path] = []

    for issue in issues:
        command = issue.get("command", "unknown")
        improvement_data = issue.get("improvement", {})
        if issue.get("source") == "self-repair-plan":
            try:
                improvement = Improvement(
                    type=ImprovementType(str(improvement_data.get("type", "fix_error_pattern"))),
                    priority=ImprovementPriority.HIGH,
                    auto_apply=AutoApply.YES if issue.get("auto_apply_safe") else AutoApply.CONDITIONAL,
                    description=str(improvement_data.get("description") or f"Self-repair needed for {command}"),
                    suggested_content=improvement_data.get("suggested_content"),
                    evidence=improvement_data.get("evidence"),
                )
                skill_path = _resolve_self_repair_skill_path(issue, ctx.project_root)
                auto_applied = False
                if issue.get("auto_apply_safe") and skill_path is not None:
                    auto_applied = apply_improvement_to_skill(skill_path, improvement)
                    if auto_applied:
                        path_str = str(skill_path)
                        commit = _commit(
                            ctx.project_root,
                            f"chore(adaptive): self-repair hint for '{command}'",
                            paths=[path_str],
                        )
                        log_improvement(command, improvement, runtime_dir, applied=True)
                        applied_actions.append(
                            {
                                "command": command,
                                "action": issue.get("action"),
                                "commit": commit,
                            }
                        )
                        changed_files.append(path_str)

                if not auto_applied:
                    queued_path = log_improvement(command, improvement, runtime_dir, applied=False)
                    if queued_path:
                        applied_actions.append(
                            {
                                "command": command,
                                "action": issue.get("action"),
                                "queued": str(queued_path),
                            }
                        )
                plan_path = Path(str(issue.get("path", "")))
                if plan_path.exists():
                    processed_self_repair_plans.append(plan_path)
                processed_commands.add(command)
            except Exception as exc:
                failed.append(f"{command}: failed to queue self-repair plan ({exc})")
            continue

        skill_path = find_skill_definition(command, ctx.project_root)
        if not skill_path:
            failed.append(f"{command}: no SKILL.md found")
            processed_commands.add(command)
            continue

        try:
            applied = apply_improvement_to_skill(skill_path, improvement_data)
        except Exception as exc:
            failed.append(f"{command}: {exc}")
            processed_commands.add(command)
            continue

        if applied:
            path_str = str(skill_path)
            commit = _commit(
                ctx.project_root,
                f"chore(adaptive): evolve command '{command}'",
                paths=[path_str],
            )
            applied_actions.append(
                {
                    "command": command,
                    "action": issue.get("action"),
                    "commit": commit,
                }
            )
            changed_files.append(path_str)
        processed_commands.add(command)

    # Clean up processed execution logs so future runs can re-analyze
    _cleanup_processed_logs(ctx.project_root, processed_commands)
    for plan_path in processed_self_repair_plans:
        plan_path.unlink(missing_ok=True)

    success = len(failed) == 0
    parts = [f"Applied {len(applied_actions)} improvements"]
    if failed:
        parts.append(f"{len(failed)} failed: {'; '.join(failed)}")
    return FixResult(
        success=success,
        actions=applied_actions,
        changes=changed_files,
        summary=". ".join(parts),
    )


_MAX_LOGS_PER_COMMAND = 5


def _cleanup_processed_logs(project_root: Path, commands: set[str]) -> None:
    """Delete old execution logs for processed commands.

    Keeps the most recent _MAX_LOGS_PER_COMMAND logs per command so the
    scanner can re-analyze fresh executions on the next cycle.
    """
    from src.config.paths import get_runtime_dir

    evo_dir = get_runtime_dir() / "command-evolution"
    if not evo_dir.exists():
        return
    for cmd_name in commands:
        exec_dir = evo_dir / cmd_name / "executions"
        if not exec_dir.exists():
            continue
        logs = sorted(exec_dir.glob("*.json"), reverse=True)
        # Keep only the most recent N; delete the rest
        for old_log in logs[_MAX_LOGS_PER_COMMAND:]:
            old_log.unlink(missing_ok=True)
