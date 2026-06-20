"""Fix-phase execution for auto-command entries.

Extracted from engine.py's run_entry inner function.
Handles fix() invocation, commit verification, trust updates,
self-repair transitions, and result recording.

ADR-444: LLM escalation dispatch with safety harness.
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
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .engine_context import collect_context
from .engine_design_gate import write_design_gate
from .engine_quality import (
    LOCAL_SEMANTIC,
    STRUCTURAL,
    classify_finding_band,
    classify_fix_outcome as classify_fix_outcome_v2,
)
from .trust_ledger import (
    CLEAN_SCAN_SATURATION,
    CLEAN_SCAN_TRUST_INCREMENT,
    DIFFICULTY_ESCALATION_THRESHOLD,
    MAX_DIFFICULTY,
)
from .trust_constants import (
    COMMIT_TRUST_INCREMENT,
    DIFFICULTY_COMMIT_GATE_BUFFER,
    PRODUCTIVE_FIX_TRUST_INCREMENT,
    REPORT_ONLY_DEMOTION_THRESHOLD,
    module_has_self_repair,
)
from .loops.base_loop import LoopResult
from .reporting import CategoryReport
from src.lib.ops_protocol import (
    FixClassification,
    FixResult,
    ModificationInfo,
    check_intentional_skip,
    classify_fix,
    make_migration_incomplete_issue,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LLM escalation budget tracking — per engine run, not persisted
# ---------------------------------------------------------------------------
_llm_dispatch_counts: dict[str, int] = {}  # loop_name -> count this run

_LLM_DISPATCH_TIMEOUT_DEFAULT = 120  # fallback if ctx.session.timeout is unset
_LLM_MAX_PER_LOOP = 5                # max LLM invocations per loop per run (was 3)

# Generic LLM escalation: minimum difficulty for report-only categories
# to attempt LLM-based fixing (lower than module-specific llm_fix threshold)
_GENERIC_LLM_MIN_DIFFICULTY = 1
_GENERIC_LLM_MAX_ISSUES_IN_PROMPT = 8  # Cap issues sent to LLM to control token usage


def _parse_porcelain_paths(output: str) -> dict[str, str]:
    """Return paths and status codes from `git status --porcelain` output."""
    paths: dict[str, str] = {}
    for line in output.splitlines():
        if not line:
            continue
        status = line[:2]
        raw_path = line[3:].strip() if len(line) > 3 else ""
        if " -> " in raw_path:
            raw_path = raw_path.rsplit(" -> ", 1)[1]
        path = raw_path.strip('"')
        if status == "??":
            path = path.rstrip("/")
        if path:
            paths[path] = status if status == "??" else status.strip()
    return paths


def _status_paths(project_root: Path) -> dict[str, str]:
    """Return current dirty/untracked paths from `git status --porcelain`."""
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        capture_output=True,
        text=True,
        check=True,
        cwd=str(project_root),
    )
    return _parse_porcelain_paths(result.stdout)


def _run_git_checked(project_root: Path, args: list[str], failure: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            check=True,
            cwd=str(project_root),
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        raise RuntimeError(f"{failure}: {detail}") from exc


def _paths_overlap(left: str, right: str) -> bool:
    left_clean = left.rstrip("/")
    right_clean = right.rstrip("/")
    return (
        left_clean == right_clean
        or left_clean.startswith(f"{right_clean}/")
        or right_clean.startswith(f"{left_clean}/")
    )


def _changed_paths_since(
    project_root: Path,
    base_ref: str,
    head_ref: str = "HEAD",
) -> set[str]:
    """Return paths changed by commits between base_ref and head_ref."""
    result = _run_git_checked(
        project_root,
        ["diff", "--name-status", "-M", f"{base_ref}..{head_ref}"],
        "Unable to inspect LLM commits",
    )
    paths: set[str] = set()
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        status = parts[0]
        if status.startswith(("R", "C")) and len(parts) >= 3:
            paths.add(parts[1])
            paths.add(parts[2])
        elif len(parts) >= 2:
            paths.add(parts[-1])
    return paths


def _commits_since(project_root: Path, base_ref: str, head_ref: str = "HEAD") -> list[str]:
    result = _run_git_checked(
        project_root,
        ["rev-list", "--reverse", f"{base_ref}..{head_ref}"],
        "Unable to inspect LLM commits",
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _path_exists_at_ref(project_root: Path, ref: str, path: str) -> bool:
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{ref}:{path}"],
        capture_output=True,
        cwd=str(project_root),
    )
    return result.returncode == 0


def _path_has_tracked_entries_at_ref(project_root: Path, ref: str, path: str) -> bool:
    result = _run_git_checked(
        project_root,
        ["ls-tree", "-r", "--name-only", ref, "--", path],
        f"Unable to inspect tracked entries under {path}",
    )
    return bool(result.stdout.strip())


def _remove_path(project_root: Path, path: str) -> None:
    target = project_root / path
    if target.is_dir():
        shutil.rmtree(target)
    elif target.exists() or target.is_symlink():
        target.unlink()


@dataclass(frozen=True)
class _DirtyPathSnapshot:
    kind: str
    data: bytes | None = None
    target: str | None = None


def _snapshot_dirty_path(project_root: Path, path: str) -> _DirtyPathSnapshot:
    target = project_root / path
    if target.is_symlink():
        return _DirtyPathSnapshot(kind="symlink", target=os.readlink(target))
    if target.is_file():
        return _DirtyPathSnapshot(kind="file", data=target.read_bytes())
    if target.is_dir():
        return _DirtyPathSnapshot(kind="dir")
    return _DirtyPathSnapshot(kind="absent")


def _snapshot_preexisting_dirty_paths(
    project_root: Path,
    status_before: dict[str, str],
) -> dict[str, _DirtyPathSnapshot]:
    return {
        path: _snapshot_dirty_path(project_root, path)
        for path in status_before
    }


def _dirty_path_matches_snapshot(
    project_root: Path,
    path: str,
    snapshot: _DirtyPathSnapshot,
) -> bool:
    target = project_root / path
    if snapshot.kind == "symlink":
        return target.is_symlink() and os.readlink(target) == snapshot.target
    if snapshot.kind == "file":
        return target.is_file() and not target.is_symlink() and target.read_bytes() == snapshot.data
    if snapshot.kind == "dir":
        return target.is_dir() and not target.is_symlink()
    return not target.exists() and not target.is_symlink()


def _restore_dirty_path_snapshot(
    project_root: Path,
    path: str,
    snapshot: _DirtyPathSnapshot,
) -> None:
    target = project_root / path
    if target.is_dir() and not target.is_symlink():
        shutil.rmtree(target)
    elif target.exists() or target.is_symlink():
        target.unlink()

    if snapshot.kind == "file":
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(snapshot.data or b"")
    elif snapshot.kind == "symlink":
        target.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(snapshot.target or "", target)
    elif snapshot.kind == "dir":
        target.mkdir(parents=True, exist_ok=True)


def _restore_preexisting_dirty_mutations(
    project_root: Path,
    snapshots: dict[str, _DirtyPathSnapshot],
) -> list[str]:
    restored: list[str] = []
    for path, snapshot in snapshots.items():
        if _dirty_path_matches_snapshot(project_root, path, snapshot):
            continue
        _restore_dirty_path_snapshot(project_root, path, snapshot)
        restored.append(path)
    return sorted(restored)


def _preexisting_untracked_owner_dirs(
    project_root: Path,
    status_before: dict[str, str],
) -> list[str]:
    owner_dirs: set[str] = set()
    for path, status in status_before.items():
        if status != "??":
            continue
        candidate = project_root / path
        if candidate.is_dir():
            owner_dirs.add(path.rstrip("/"))
            continue
        rel = Path(path)
        for parent in rel.parents:
            if str(parent) == ".":
                continue
            if (project_root / parent).is_dir():
                owner_dirs.add(parent.as_posix())
    return sorted(owner_dirs)


def _rollback_llm_owned_changes(
    project_root: Path,
    head_before: str,
    status_before: dict[str, str],
) -> list[str]:
    """Rollback only paths introduced or cleanly owned by an LLM dispatch."""
    committed_paths = _changed_paths_since(project_root, head_before)
    commits = _commits_since(project_root, head_before)
    dirty_before = set(status_before)
    owner_dirs = _preexisting_untracked_owner_dirs(project_root, status_before)
    blocked = sorted(
        path for path in committed_paths
        if any(_paths_overlap(path, dirty_path) for dirty_path in dirty_before)
    )
    if blocked:
        joined = ", ".join(blocked)
        raise RuntimeError(
            "LLM rollback blocked: committed path(s) were already dirty before "
            f"LLM dispatch: {joined}"
        )

    status_after = _status_paths(project_root)
    dirty_introduced = set(status_after) - dirty_before
    introduced_under_owner_dir = sorted(
        path for path in dirty_introduced
        if any(_paths_overlap(path, owner_dir) for owner_dir in owner_dirs)
    )
    if introduced_under_owner_dir:
        joined = ", ".join(introduced_under_owner_dir)
        owners = ", ".join(owner_dirs)
        raise RuntimeError(
            "LLM rollback blocked: introduced path(s) under pre-existing "
            f"untracked owner directory ({owners}): {joined}"
        )
    tracked_dirty_introduced = {
        path for path in dirty_introduced
        if status_after.get(path) != "??"
    }
    untracked_introduced = {
        path for path in dirty_introduced
        if status_after.get(path) == "??"
    }
    collapsed_untracked_introduced: set[str] = set()
    for path in untracked_introduced:
        collapsed = path
        parts = Path(path).parts
        for index in range(1, len(parts)):
            parent = Path(*parts[:index]).as_posix()
            if parent in dirty_before:
                break
            if (
                (project_root / parent).is_dir()
                and not _path_has_tracked_entries_at_ref(project_root, head_before, parent)
            ):
                collapsed = parent
                break
        collapsed_untracked_introduced.add(collapsed)

    reverted: list[str] = []
    for path in sorted(tracked_dirty_introduced):
        if any(_paths_overlap(path, dirty_path) for dirty_path in dirty_before):
            continue
        if _path_exists_at_ref(project_root, "HEAD", path):
            _run_git_checked(
                project_root,
                ["checkout", "HEAD", "--", path],
                f"LLM rollback failed while restoring {path}",
            )
        else:
            _remove_path(project_root, path)
            _run_git_checked(
                project_root,
                ["rm", "--cached", "--ignore-unmatch", "--", path],
                f"LLM rollback failed while untracking {path}",
            )
        reverted.append(path)

    if commits:
        revert_args = ["revert", "--no-edit", *reversed(commits)]
        try:
            _run_git_checked(
                project_root,
                revert_args,
                "LLM rollback failed while reverting LLM commit range",
            )
        except RuntimeError as exc:
            abort_detail = ""
            try:
                _run_git_checked(
                    project_root,
                    ["revert", "--abort"],
                    "LLM rollback failed and revert abort failed",
                )
            except RuntimeError as abort_exc:
                abort_detail = f"; revert abort failed: {abort_exc}"
            raise RuntimeError(
                "LLM rollback failed before completion; partial rollback risk "
                f"was handled with git revert --abort{abort_detail}: {exc}"
            ) from exc
        reverted.extend(sorted(committed_paths))

    for path in sorted(collapsed_untracked_introduced):
        if any(_paths_overlap(path, dirty_path) for dirty_path in dirty_before):
            continue
        _remove_path(project_root, path)
        reverted.append(path)

    return sorted(dict.fromkeys(reverted))


def _committed_paths_overlap_preexisting_dirty(
    committed_paths: set[str],
    status_before: dict[str, str],
) -> bool:
    return any(
        _paths_overlap(committed_path, dirty_path)
        for committed_path in committed_paths
        for dirty_path in status_before
    )


def _dispatch_llm_fix(engine: Any, ctx: Any, prompt: str, loop_name: str) -> dict:
    """Dispatch an LLM fix via CLI subprocess with safety harness (ADR-444).

    Uses build_headless_cmd() with the CLI resolved at engine startup.
    Safety harness:
    - Git snapshot before dispatch (rev-parse HEAD)
    - Budget: max 3 invocations per loop per run
    - Timeout: ctx.session.timeout (from adaptive_loops.yaml engine.llm_escalation.timeout_s)
    - Build verify after (npm run build --if-present for TS changes)
    - Path-scoped rollback of LLM-owned changes on failure

    Returns {"success": bool, "summary": str, "changes": list, "error": str}.
    """
    session = ctx.session
    dispatch_timeout = session.timeout if session.timeout is not None else _LLM_DISPATCH_TIMEOUT_DEFAULT
    if not session.cli_path:
        return {"success": False, "error": "No CLI available for LLM dispatch"}

    # Budget check
    budget_limit = getattr(engine, "_llm_budget_multiplier", _LLM_MAX_PER_LOOP)
    current_count = _llm_dispatch_counts.get(loop_name, 0)
    if current_count >= budget_limit:
        return {"success": False, "error": f"LLM budget exhausted ({current_count}/{budget_limit})"}

    try:
        from src.lib.llm_retry import build_headless_cmd

        cmd = build_headless_cmd(
            cli_path=session.cli_path,
            prompt=prompt,
            max_turns=session.max_turns,
            allowed_tools="Read,Edit,Bash,Grep,Glob,Write",
            bypass_approvals=True,
            no_session=True,
        )

        env = os.environ.copy()
        env["CLAUDECODE"] = ""
        env["CLAUDE_CODE"] = ""

        # Safety: snapshot HEAD before LLM dispatch
        head_before = _run_git_checked(
            ctx.project_root,
            ["rev-parse", "HEAD"],
            "Unable to snapshot HEAD before LLM dispatch",
        ).stdout.strip()
        status_before = _status_paths(ctx.project_root)
        dirty_snapshots = _snapshot_preexisting_dirty_paths(ctx.project_root, status_before)

        # Track budget
        _llm_dispatch_counts[loop_name] = current_count + 1

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=dispatch_timeout,
            cwd=str(ctx.project_root),
            env=env,
        )

        if result.returncode == 0:
            # Check if LLM actually made a new commit
            after_head = _run_git_checked(
                ctx.project_root,
                ["rev-parse", "HEAD"],
                "Unable to inspect HEAD after LLM dispatch",
            ).stdout.strip()

            if after_head != head_before:
                committed_paths = _changed_paths_since(ctx.project_root, head_before)
                changed_files = sorted(committed_paths)
                mutated_dirty_paths = _restore_preexisting_dirty_mutations(
                    ctx.project_root,
                    dirty_snapshots,
                )
                if mutated_dirty_paths:
                    rollback_payload: dict[str, Any] = {}
                    if not _committed_paths_overlap_preexisting_dirty(committed_paths, status_before):
                        try:
                            rollback_paths = _rollback_llm_owned_changes(
                                ctx.project_root, head_before, status_before,
                            )
                            rollback_payload["rollback_paths"] = rollback_paths
                        except RuntimeError as exc:
                            rollback_payload["rollback_error"] = str(exc)
                    return {
                        "success": False,
                        "error": (
                            "LLM fix mutated pre-existing dirty path(s); "
                            "restored pre-dispatch content and refused success: "
                            f"{', '.join(mutated_dirty_paths)}"
                        ),
                        "changes": changed_files,
                        "preexisting_dirty_paths": mutated_dirty_paths,
                        "_head_before": head_before,
                        "_status_before": status_before,
                        **rollback_payload,
                    }
                preexisting_dirty_paths = sorted(
                    dirty_path for dirty_path in status_before
                    if any(_paths_overlap(changed_file, dirty_path) for changed_file in changed_files)
                )
                if preexisting_dirty_paths:
                    return {
                        "success": False,
                        "error": (
                            "LLM fix committed pre-existing dirty path(s); "
                            "refusing to mark dispatch successful without rollback: "
                            f"{', '.join(preexisting_dirty_paths)}"
                        ),
                        "changes": changed_files,
                        "preexisting_dirty_paths": preexisting_dirty_paths,
                        "_head_before": head_before,
                        "_status_before": status_before,
                    }

                # Safety: build verify if TS files were touched
                ts_exts = {".ts", ".tsx", ".js", ".jsx", ".json"}
                has_ts_changes = any(
                    Path(f).suffix in ts_exts for f in changed_files
                )
                if has_ts_changes:
                    build_ok = _verify_build_after_llm(ctx.project_root, engine)
                    if not build_ok:
                        logger.warning(
                            "LLM fix failed build verify, rolling back owned paths to %s",
                            head_before[:8],
                        )
                        try:
                            rollback_paths = _rollback_llm_owned_changes(
                                ctx.project_root, head_before, status_before,
                            )
                        except RuntimeError as exc:
                            return {"success": False, "error": str(exc)}
                        return {
                            "success": False,
                            "error": "LLM fix reverted: build verification failed",
                            "rollback_paths": rollback_paths,
                        }

                status_after = _status_paths(ctx.project_root)
                dirty_introduced = sorted(
                    path for path in status_after
                    if path not in status_before
                )
                if dirty_introduced:
                    logger.warning(
                        "LLM fix committed but left dirty state, rolling back owned paths to %s: %s",
                        head_before[:8],
                        ", ".join(dirty_introduced),
                    )
                    try:
                        rollback_paths = _rollback_llm_owned_changes(
                            ctx.project_root, head_before, status_before,
                        )
                    except RuntimeError as exc:
                        return {"success": False, "error": str(exc)}
                    return {
                        "success": False,
                        "error": (
                            "LLM fix left dirty state after commit; "
                            f"rolled back {len(rollback_paths)} path(s): "
                            f"{', '.join(dirty_introduced)}"
                        ),
                        "rollback_paths": rollback_paths,
                    }

                return {
                    "success": True,
                    "summary": f"LLM applied changes to {len(changed_files)} files",
                    "changes": changed_files,
                    "_head_before": head_before,
                    "_status_before": status_before,
                }
            else:
                mutated_dirty_paths = _restore_preexisting_dirty_mutations(
                    ctx.project_root,
                    dirty_snapshots,
                )
                try:
                    rollback_paths = _rollback_llm_owned_changes(
                        ctx.project_root, head_before, status_before,
                    )
                except RuntimeError as exc:
                    return {"success": False, "error": str(exc)}
                response = {
                    "success": False,
                    "error": "LLM completed but made no commits",
                    "rollback_paths": rollback_paths,
                }
                if mutated_dirty_paths:
                    response["error"] = (
                        "LLM completed but mutated pre-existing dirty path(s) "
                        "without making commits; restored pre-dispatch content: "
                        f"{', '.join(mutated_dirty_paths)}"
                    )
                    response["preexisting_dirty_paths"] = mutated_dirty_paths
                return response
        else:
            mutated_dirty_paths = _restore_preexisting_dirty_mutations(
                ctx.project_root,
                dirty_snapshots,
            )
            try:
                rollback_paths = _rollback_llm_owned_changes(
                    ctx.project_root, head_before, status_before,
                )
            except RuntimeError as exc:
                return {"success": False, "error": str(exc)}
            error = result.stderr[:500] if result.stderr else "non-zero exit"
            response = {
                "success": False,
                "error": error,
                "rollback_paths": rollback_paths,
            }
            if mutated_dirty_paths:
                response["error"] = (
                    "LLM failed and mutated pre-existing dirty path(s); "
                    "restored pre-dispatch content. Original error: "
                    f"{error}"
                )
                response["preexisting_dirty_paths"] = mutated_dirty_paths
            return response

    except subprocess.TimeoutExpired:
        mutated_dirty_paths = _restore_preexisting_dirty_mutations(
            ctx.project_root,
            dirty_snapshots,
        )
        try:
            rollback_paths = _rollback_llm_owned_changes(
                ctx.project_root, head_before, status_before,
            )
        except RuntimeError as exc:
            return {"success": False, "error": str(exc)}
        response = {
            "success": False,
            "error": f"LLM timed out after {dispatch_timeout}s",
            "rollback_paths": rollback_paths,
        }
        if mutated_dirty_paths:
            response["error"] = (
                "LLM timed out and mutated pre-existing dirty path(s); "
                "restored pre-dispatch content: "
                f"{', '.join(mutated_dirty_paths)}"
            )
            response["preexisting_dirty_paths"] = mutated_dirty_paths
        return response
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def _verify_build_after_llm(project_root: Path, engine: Any) -> bool:
    """Run build verification after LLM changes (ADR-444 safety harness)."""
    verify_cmd = getattr(engine, "_verify_command", "")
    if not verify_cmd:
        return True  # no verify command configured — assume OK
    try:
        result = subprocess.run(
            verify_cmd, shell=True, capture_output=True,  # nosec B602  # operator-supplied trusted config (SKILL.md frontmatter / engine verify config), not attacker-controllable input
            text=True,
            timeout=300,
            cwd=str(project_root),
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, Exception):
        return False


def _build_generic_llm_prompt(
    entry_name: str,
    project_root: Path,
    issues: list[dict[str, Any]],
) -> str:
    """Build an LLM fix prompt from scan findings for categories without llm_fix().

    This is the generic escalation path — it turns any report-only category
    into a potential fixer by providing the LLM with structured issue context.
    """
    issue_lines: list[str] = []
    for issue in issues[:_GENERIC_LLM_MAX_ISSUES_IN_PROMPT]:
        path = issue.get("path") or issue.get("file") or ""
        detail = issue.get("detail") or issue.get("message") or issue.get("action") or ""
        kind = issue.get("kind", "actionable")
        if kind not in ("actionable", "broken"):
            continue
        line = issue.get("line", "")
        loc = f" (line {line})" if line else ""
        issue_lines.append(f"- [{path}{loc}] {detail}")

    if not issue_lines:
        return ""

    return f"""You are an automated code fixer for the '{entry_name}' scanner.
Fix these issues in {project_root}:

{chr(10).join(issue_lines)}

Rules:
- Only edit files mentioned in the issues above
- Make minimal, targeted changes — fix the reported issue, nothing else
- Do NOT add comments explaining your fix
- Do NOT refactor surrounding code
- If a fix would require understanding business logic you don't have, skip it
- After fixing, verify by reading the changed files to confirm correctness
"""


def _verify_fix_reduced_issues(
    entry: Any,
    ctx: Any,
    original_count: int,
) -> tuple[bool, int]:
    """Re-scan after a fix to verify issues were actually reduced.

    Returns (reduced, new_count).
    """
    try:
        verify_result = entry.module.scan(ctx)
        verify_issues = getattr(verify_result, "issues", []) or []
        actionable = sum(
            1 for i in verify_issues
            if (i.get("kind", "actionable") if isinstance(i, dict) else "actionable") == "actionable"
        )
        return actionable < original_count, actionable
    except Exception as exc:
        logger.warning("Post-fix scanner verification failed closed for %s: %s", entry.name, exc)
        return False, original_count


def _needs_context(finding_band: str, issue: dict[str, Any]) -> bool:
    """Decide whether this finding should pull extra context."""
    if finding_band == STRUCTURAL:
        return True
    if finding_band != LOCAL_SEMANTIC:
        return False
    return bool(issue.get("design_ambiguous") or issue.get("intent_unclear"))


def _revert_structural_commit(project_root: Path, commit_hash: str | None) -> bool:
    """Revert the structural commit without assuming it is still HEAD."""
    if not commit_hash:
        return False
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit_hash, "HEAD"],
        capture_output=True,
        cwd=str(project_root),
    )
    if ancestor.returncode != 0:
        return False
    result = subprocess.run(
        ["git", "revert", commit_hash, "--no-edit"],
        capture_output=True,
        cwd=str(project_root),
    )
    if result.returncode == 0:
        return True
    subprocess.run(
        ["git", "revert", "--abort"],
        capture_output=True,
        cwd=str(project_root),
    )
    return False


def _verify_structural_fix(
    *,
    engine: Any,
    entry: Any,
    ctx: Any,
    issue_counts: dict[str, int],
    commit_hash: str | None,
    llm_rollback: tuple[str, dict[str, str]] | None = None,
) -> tuple[bool, bool, str]:
    """Run the stronger post-fix gate for structural changes.

    Structural fixes must satisfy both the normal verify command and a runtime
    re-scan that proves the actionable issue count dropped.
    """
    actionable_count = issue_counts.get("actionable", 0)
    if actionable_count <= 0:
        return True, False, ""

    reduced, remaining = _verify_fix_reduced_issues(entry, ctx, actionable_count)
    if reduced:
        return True, False, ""

    summary = (
        f"structural runtime verification failed: actionable issues remained "
        f"({actionable_count}->{remaining})"
    )
    if llm_rollback:
        head_before, status_before = llm_rollback
        try:
            rollback_paths = _rollback_llm_owned_changes(
                engine._project_root,
                head_before,
                status_before,
            )
            summary = f"{summary}; rolled back {len(rollback_paths)} LLM-owned path(s)"
            return False, True, summary
        except RuntimeError as exc:
            summary = f"{summary}; LLM rollback failed: {exc}"
            return False, False, summary

    reverted = _revert_structural_commit(engine._project_root, commit_hash) if commit_hash else False
    return False, reverted, summary


def _store_cat_report(cat_reports: list[CategoryReport], report: CategoryReport) -> None:
    """Store or replace a category report in the list."""
    for idx, existing in enumerate(cat_reports):
        if existing.name == report.name:
            cat_reports[idx] = report
            return
    cat_reports.append(report)


def run_fix_phase(
    *,
    engine: Any,
    loop_name: str,
    loop_state: Any,
    entry: Any,
    ctx: Any,
    issues: list[dict[str, Any]],
    issue_counts: dict[str, int],
    scan_duration_ms: int,
    trust_before: float,
    diff_before: int,
    strategy_before: str,
    deepening_reason: str,
    execution_mode: str,
    should_short_circuit: bool,
    snap_fp: str,
    yc: str,
    new_count: int,
    repeated_count: int,
    resolved_count: int,
    results: list[LoopResult],
    cat_reports: list[CategoryReport],
    invalidated_categories: set[str],
    dep_invalidations: dict[str, set[str]],
    allow_invalidations: bool,
    t0: float,
) -> bool:
    """Run fix() and process results. Returns True if budget remains."""

    # -------------------------------------------------------------------
    # ADR-443: Pre-fix classification gate — check issue paths for
    # reverting risk or recent user modifications before allowing fix().
    # -------------------------------------------------------------------
    _SAFE_ISSUE_KINDS = {"clean", "maintenance", "environment"}
    blocked_reversions: list[tuple[dict, Any]] = []
    blocked_modifications: list[tuple[dict, ModificationInfo]] = []
    blocked_skips: list[tuple[dict, str]] = []
    finding_band = LOCAL_SEMANTIC
    representative_issue: dict[str, Any] = issues[0] if issues else {}
    context_bundle: dict[str, Any] = {"finding_band": LOCAL_SEMANTIC, "sources": []}
    context_insufficient = False
    design_gate_info: dict[str, Any] | None = None
    design_gate_written = False
    design_gate_error = ""

    project_root = getattr(ctx, "project_root", None)

    for issue in issues:
        path = issue.get("path", "")
        if not path:
            continue
        kind = issue.get("kind", "actionable")
        if kind in _SAFE_ISSUE_KINDS:
            continue

        # Check INTENTIONAL_SKIP marker in the target file
        skip_reason = check_intentional_skip(path)
        if skip_reason:
            blocked_skips.append((issue, skip_reason))
            continue

        classification, change_info = classify_fix(
            "structural", path, project_root,
        )
        if classification == FixClassification.REVERTING:
            blocked_reversions.append((issue, change_info))
        elif classification == FixClassification.MODIFIED:
            blocked_modifications.append((issue, change_info))
    # Collect blocked issue paths for filtering
    all_blocked = blocked_reversions + blocked_modifications + blocked_skips
    if all_blocked:
        block_parts = []
        migration_issues = []

        # Reverting — recreating recently deleted files
        for issue, deletion in blocked_reversions:
            mi = make_migration_incomplete_issue(
                deletion, issue.get("path", ""), category=entry.name,
            )
            block_parts.append(mi.get("detail", ""))
            migration_issues.append(mi)

        # Modified — user recently changed the target file
        for issue, mod_info in blocked_modifications:
            detail = (
                f"File '{issue.get('path', '')}' was modified by user "
                f"({mod_info.commit_hash[:8]}: {mod_info.commit_message[:60]}). "
                f"Autoloop fix blocked to protect intentional change."
            )
            block_parts.append(detail)

        # INTENTIONAL_SKIP — explicit opt-out marker
        for issue, reason in blocked_skips:
            block_parts.append(
                f"File '{issue.get('path', '')}' has INTENTIONAL_SKIP: {reason}"
            )

        issues.extend(migration_issues)

        # Filter out blocked issues instead of blocking the entire fix.
        # Only fully block if ALL actionable issues are blocked (or if any
        # reversions exist, which are always a hard block).
        blocked_paths = set()
        for issue, _ in blocked_modifications:
            blocked_paths.add(issue.get("path", ""))
        for issue, _ in blocked_skips:
            blocked_paths.add(issue.get("path", ""))

        if blocked_reversions:
            # Reversions are always a full block — they recreate deleted files
            total_duration_ms = int((time.monotonic() - t0) * 1000)
            fix_duration_ms = max(0, total_duration_ms - scan_duration_ms)
            block_summary = (
                f"Blocked: {len(blocked_reversions)} reversion(s), "
                f"{len(blocked_modifications)} user-modified file(s), "
                f"{len(blocked_skips)} INTENTIONAL_SKIP(s). "
                f"{block_parts[0][:100]}"
            )
            logger.warning("ADR-443 fix blocked for %s: %s", entry.name, block_summary[:200])
            engine.journal_writer.log(
                loop=loop_name, action="fix-blocked", category=entry.name,
                result="blocked", files=[], error=block_summary,
                duration_ms=total_duration_ms,
            )
            results.append(LoopResult(
                success=False, action="fix-blocked", category=entry.name,
                error=block_summary, duration_ms=total_duration_ms,
            ))
            _store_cat_report(cat_reports, engine._make_cat_report(
                entry.name, trust_before, diff_before, loop_state,
                "blocked", block_summary[:120], outcome="blocked",
                issue_count=len(issues), issue_counts=issue_counts,
                deepening_reason=deepening_reason, yield_class=yc,
                new_fingerprint_count=new_count,
                repeated_fingerprint_count=repeated_count,
                resolved_fingerprint_count=resolved_count,
                execution_mode=execution_mode,
                short_circuit_used=should_short_circuit,
                scan_duration_ms=scan_duration_ms,
                fix_duration_ms=fix_duration_ms,
                total_duration_ms=total_duration_ms,
            ))
            return True

        # Filter blocked paths from issues — proceed with safe issues only
        safe_issues = [
            i for i in issues
            if i.get("path", "") not in blocked_paths
        ]
        if not safe_issues:
            # All issues are blocked — report-only
            total_duration_ms = int((time.monotonic() - t0) * 1000)
            fix_duration_ms = max(0, total_duration_ms - scan_duration_ms)
            block_summary = (
                f"All {len(issues)} issues blocked: "
                f"{len(blocked_modifications)} user-modified, "
                f"{len(blocked_skips)} skipped"
            )
            logger.info("ADR-443 all issues blocked for %s: %s", entry.name, block_summary)
            engine.journal_writer.log(
                loop=loop_name, action="fix-blocked", category=entry.name,
                result="blocked", files=[], error=block_summary,
                duration_ms=total_duration_ms,
            )
            results.append(LoopResult(
                success=False, action="fix-blocked", category=entry.name,
                error=block_summary, duration_ms=total_duration_ms,
            ))
            _store_cat_report(cat_reports, engine._make_cat_report(
                entry.name, trust_before, diff_before, loop_state,
                "blocked", block_summary[:120], outcome="blocked",
                issue_count=len(issues), issue_counts=issue_counts,
                deepening_reason=deepening_reason, yield_class=yc,
                new_fingerprint_count=new_count,
                repeated_fingerprint_count=repeated_count,
                resolved_fingerprint_count=resolved_count,
                execution_mode=execution_mode,
                short_circuit_used=should_short_circuit,
                scan_duration_ms=scan_duration_ms,
                fix_duration_ms=fix_duration_ms,
                total_duration_ms=total_duration_ms,
            ))
            return True

        # Proceed with safe issues, log the exclusions
        n_excluded = len(issues) - len(safe_issues)
        if n_excluded > 0:
            logger.info(
                "ADR-443: excluded %d blocked issues for %s, proceeding with %d safe issues",
                n_excluded, entry.name, len(safe_issues),
            )
        issues = safe_issues
        issue_counts = engine._count_issue_kinds(issues)

    if issues:
        for issue in issues:
            issue_band = classify_finding_band(issue)
            if issue_band == STRUCTURAL:
                representative_issue = issue
                finding_band = STRUCTURAL
                break
            if finding_band != STRUCTURAL:
                representative_issue = issue
                finding_band = issue_band
    if _needs_context(finding_band, representative_issue):
        context_bundle = collect_context(
            issue=representative_issue,
            project_root=engine._project_root,
            loop_name=loop_name,
        )

    if finding_band == STRUCTURAL:
        requires_context = bool(representative_issue.get("design_ambiguous"))
        context_insufficient = requires_context and not context_bundle.get("sources")
        if not context_insufficient:
            try:
                design_gate_info = write_design_gate(
                    issue=representative_issue,
                    loop_name=loop_name,
                    project_root=engine._project_root,
                    context=context_bundle,
                    use_adr=bool(
                        representative_issue.get("ownership_change")
                        or representative_issue.get("scheduler_change")
                    ),
                )
                design_gate_written = bool(design_gate_info.get("written"))
            except Exception as exc:
                design_gate_error = str(exc)
                logger.warning("Design gate write failed for %s: %s", entry.name, exc)

    if finding_band == STRUCTURAL and (ctx.difficulty < 1 or context_insufficient or not design_gate_written):
        # Structural fixes either stop for design/context or emit a design gate at d0.
        total_duration_ms = int((time.monotonic() - t0) * 1000)
        fix_duration_ms = max(0, total_duration_ms - scan_duration_ms)
        if context_insufficient:
            skip_summary = (
                f"Structural fix for {entry.name} needs more design context "
                f"before changes can be applied"
            )
        elif not design_gate_written:
            skip_summary = (
                f"Structural fix for {entry.name} is blocked until a design gate "
                f"can be written: {design_gate_error or 'writer returned no artifact'}"
            )
        else:
            skip_summary = (
                f"Design gate written for {entry.name} at d{ctx.difficulty}: "
                f"{design_gate_info.get('path', 'n/a')}"
            )
        structural_outcome = classify_fix_outcome_v2(
            success=design_gate_written and not context_insufficient,
            changes=[],
            fix_result={"actions": []},
            finding_band=finding_band,
            design_gate_written=design_gate_written,
            reverted=False,
            context_insufficient=context_insufficient,
        )
        logger.info("Loop quality gate for %s: %s", entry.name, skip_summary)
        engine.journal_writer.log(
            loop=loop_name,
            action="design-gate" if design_gate_written else "fix-deferred",
            category=entry.name,
            result="success" if design_gate_written and not context_insufficient else "blocked",
            files=[design_gate_info["path"]] if design_gate_written and design_gate_info else [],
            error=None if design_gate_written and not context_insufficient else skip_summary,
            duration_ms=total_duration_ms,
        )
        results.append(LoopResult(
            success=design_gate_written and not context_insufficient,
            action="design-gate" if design_gate_written else "fix-deferred",
            category=entry.name,
            files=[design_gate_info["path"]] if design_gate_written and design_gate_info else [],
            error=None if design_gate_written and not context_insufficient else skip_summary,
            duration_ms=total_duration_ms,
        ))
        _store_cat_report(cat_reports, engine._make_cat_report(
            entry.name, trust_before, diff_before, loop_state,
            "ok" if design_gate_written and not context_insufficient else "blocked",
            skip_summary[:120],
            outcome=structural_outcome,
            issue_count=len(issues), issue_counts=issue_counts,
            deepening_reason=deepening_reason, yield_class=yc,
            new_fingerprint_count=new_count,
            repeated_fingerprint_count=repeated_count,
            resolved_fingerprint_count=resolved_count,
            execution_mode=execution_mode,
            short_circuit_used=should_short_circuit,
            scan_duration_ms=scan_duration_ms,
            fix_duration_ms=fix_duration_ms,
            total_duration_ms=total_duration_ms,
        ))
        return True
    # -------------------------------------------------------------------

    platform_fix_mode = str(ctx.config.get("_ops_fix_mode", "auto_fix"))
    platform_skip_reason = str(ctx.config.get("_ops_skip_reason", "")).strip()
    if platform_fix_mode == "report_only":
        summary = "Platform contract: report-only on this platform"
        if platform_skip_reason:
            summary = f"{summary} ({platform_skip_reason})"
        fix_result = FixResult(
            success=True,
            actions=[{"kind": "platform-report-only", "reason": platform_skip_reason}],
            changes=[],
            summary=summary,
            fix_type="report",
        )
    else:
        try:
            fix_result = entry.module.fix(ctx, issues)
        except Exception as exc:
            logger.warning("fix() failed for %s: %s", entry.name, exc)
            total_duration_ms = int((time.monotonic() - t0) * 1000)
            fix_duration_ms = max(0, total_duration_ms - scan_duration_ms)
            engine.journal_writer.log(
                loop=loop_name, action="fix", category=entry.name,
                result="failure", files=[], error=str(exc),
                duration_ms=total_duration_ms,
            )
            engine.ledger.record_failure(loop_name, entry.name)
            results.append(LoopResult(
                success=False, action="fix", category=entry.name,
                error=f"fix exception: {exc}", duration_ms=total_duration_ms,
            ))
            _store_cat_report(cat_reports, engine._make_cat_report(
                entry.name, trust_before, diff_before, loop_state,
                "broken", f"fix exception: {exc}"[:120], outcome="broken",
                issue_count=len(issues), issue_counts=issue_counts,
                deepening_reason=deepening_reason, yield_class=yc,
                new_fingerprint_count=new_count,
                repeated_fingerprint_count=repeated_count,
                resolved_fingerprint_count=resolved_count,
                execution_mode=execution_mode,
                short_circuit_used=should_short_circuit,
                scan_duration_ms=scan_duration_ms,
                fix_duration_ms=fix_duration_ms,
                total_duration_ms=total_duration_ms,
            ))
            return True

    total_duration_ms = int((time.monotonic() - t0) * 1000)
    fix_duration_ms = max(0, total_duration_ms - scan_duration_ms)
    success = getattr(fix_result, "success", False)
    changes = getattr(fix_result, "changes", [])
    fix_summary = getattr(fix_result, "summary", "")
    fix_actions = getattr(fix_result, "actions", [])
    llm_rollback: tuple[str, dict[str, str]] | None = None

    # ADR-444/ADR-446: LLM escalation
    # Two paths:
    #   1. fix() returned llm_escalation actions (internal plateau signal, ADR-446)
    #   2. fix() returned no changes and module has llm_fix() (external plateau, ADR-444)
    entry_config = getattr(entry, "config", {}) or {}
    llm_escalation_actions = [
        a for a in fix_actions
        if isinstance(a, dict) and a.get("kind") == "llm_escalation"
    ]
    non_escalation_actions = [
        a for a in fix_actions
        if not (isinstance(a, dict) and a.get("kind") == "llm_escalation")
    ]

    # Path 1: fix() self-escalated and returned llm_escalation sentinel(s)
    if (
        llm_escalation_actions
        and getattr(engine, "_llm_escalation_enabled", False)
        and ctx.session.has_llm
    ):
        cat_state = loop_state.categories.get(entry.name)
        cat_trust = cat_state.trust if cat_state else 0.0
        min_trust = getattr(engine, "_llm_min_trust", 0.5)
        if cat_trust >= min_trust:
            for esc_action in llm_escalation_actions:
                llm_prompt = esc_action.get("prompt", "")
                if not llm_prompt:
                    continue
                skill = esc_action.get("skill", entry.name)
                reason = esc_action.get("reason", "plateau")
                logger.info(
                    "LLM escalation (internal) for %s/%s (trust=%.2f, d=%d): %s",
                    entry.name, skill, cat_trust, ctx.difficulty, reason,
                )
                try:
                    llm_result = _dispatch_llm_fix(engine, ctx, llm_prompt, loop_name)
                    if llm_result.get("success"):
                        head_before = llm_result.get("_head_before", "")
                        status_before = llm_result.get("_status_before", {})
                        if head_before and isinstance(status_before, dict):
                            llm_rollback = (head_before, status_before)
                        fix_result = FixResult(
                            success=True,
                            changes=llm_result.get("changes", ["llm-fix"]),
                            summary=f"LLM({skill}): {llm_result.get('summary', 'applied')}",
                            fix_type="code-fix",
                        )
                        success = True
                        changes = fix_result.changes
                        fix_summary = fix_result.summary
                        fix_actions = non_escalation_actions
                    else:
                        logger.warning(
                            "LLM fix (internal) failed for %s/%s: %s",
                            entry.name, skill, llm_result.get("error", "unknown"),
                        )
                except Exception as llm_exc:
                    logger.warning("LLM escalation (internal) error for %s/%s: %s", entry.name, skill, llm_exc)

    # Path 2: fix() made no changes and module has llm_fix() (external plateau)
    elif (
        not changes
        and not non_escalation_actions
        and not llm_escalation_actions
        and hasattr(entry.module, "llm_fix")
        and getattr(engine, "_llm_escalation_enabled", False)
        and ctx.session.has_llm
        and ctx.difficulty >= entry_config.get("llm_min_difficulty", 2)
    ):
        cat_state = loop_state.categories.get(entry.name)
        cat_trust = cat_state.trust if cat_state else 0.0
        min_trust = getattr(engine, "_llm_min_trust", 0.5)

        if cat_trust >= min_trust:
            logger.info("LLM escalation for %s (trust=%.2f, d=%d)", entry.name, cat_trust, ctx.difficulty)
            try:
                llm_prompt = entry.module.llm_fix(ctx, issues)
                if llm_prompt:
                    llm_result = _dispatch_llm_fix(engine, ctx, llm_prompt, loop_name)
                    if llm_result.get("success"):
                        head_before = llm_result.get("_head_before", "")
                        status_before = llm_result.get("_status_before", {})
                        if head_before and isinstance(status_before, dict):
                            llm_rollback = (head_before, status_before)
                        fix_result = FixResult(
                            success=True,
                            changes=llm_result.get("changes", ["llm-fix"]),
                            summary=f"LLM: {llm_result.get('summary', 'applied')}",
                            fix_type="code-fix",
                        )
                        success = True
                        changes = fix_result.changes
                        fix_summary = fix_result.summary
                        fix_actions = getattr(fix_result, "actions", [])
                    else:
                        logger.warning("LLM fix failed for %s: %s", entry.name, llm_result.get("error", "unknown"))
            except Exception as llm_exc:
                logger.warning("LLM escalation error for %s: %s", entry.name, llm_exc)

    # Path 3: Generic LLM fallback — fix() returned report-only (no changes),
    # module has NO llm_fix(), but LLM is available. Build a prompt from the
    # scan findings and let the LLM attempt the fix directly.
    # This turns every report-only category into a potential fixer.
    elif (
        not changes
        and not non_escalation_actions
        and not llm_escalation_actions
        and not hasattr(entry.module, "llm_fix")
        and getattr(engine, "_llm_escalation_enabled", False)
        and ctx.session.has_llm
        and ctx.difficulty >= _GENERIC_LLM_MIN_DIFFICULTY
        and issue_counts.get("actionable", 0) > 0
    ):
        cat_state = loop_state.categories.get(entry.name)
        # Use commit_trust for generic escalation — only categories that
        # have proven they can commit (or are new) should get LLM budget.
        cat_commit_trust = getattr(cat_state, "commit_trust", 0.0) if cat_state else 0.0
        cat_trust = cat_state.trust if cat_state else 0.0
        min_trust = getattr(engine, "_llm_min_trust", 0.3)
        # For generic path: allow if either trust OR commit_trust qualifies,
        # or if the category has never been tried (total_fixes < 5)
        total_fixes = getattr(cat_state, "total_fixes", 0) if cat_state else 0
        qualifies = (
            cat_trust >= min_trust
            or cat_commit_trust >= min_trust
            or total_fixes < 5  # New category — give it a chance
        )

        if qualifies:
            actionable_count = issue_counts.get("actionable", 0)
            llm_prompt = _build_generic_llm_prompt(
                entry.name, engine._project_root, issues,
            )
            if llm_prompt:
                logger.info(
                    "Generic LLM escalation for %s (trust=%.2f, commit_trust=%.2f, "
                    "d=%d, %d actionable issues)",
                    entry.name, cat_trust, cat_commit_trust,
                    ctx.difficulty, actionable_count,
                )
                try:
                    llm_result = _dispatch_llm_fix(engine, ctx, llm_prompt, loop_name)
                    if llm_result.get("success"):
                        head_before = llm_result.get("_head_before", "")
                        status_before = llm_result.get("_status_before", {})
                        if head_before and isinstance(status_before, dict):
                            llm_rollback = (head_before, status_before)
                        # Post-fix verification: re-scan to confirm issues reduced
                        reduced, new_count = _verify_fix_reduced_issues(
                            entry, ctx, actionable_count,
                        )
                        if reduced:
                            fix_result = FixResult(
                                success=True,
                                changes=llm_result.get("changes", ["llm-generic-fix"]),
                                summary=f"LLM(generic/{entry.name}): {actionable_count}→{new_count} issues",
                                fix_type="code-fix",
                            )
                            success = True
                            changes = fix_result.changes
                            fix_summary = fix_result.summary
                            fix_actions = getattr(fix_result, "actions", [])
                        else:
                            # LLM fix didn't help — roll back owned paths only.
                            logger.warning(
                                "Generic LLM fix for %s didn't reduce issues "
                                "(%d→%d), rolling back owned paths",
                                entry.name, actionable_count, new_count,
                            )
                            head_before = llm_result.get("_head_before", "")
                            status_before = llm_result.get("_status_before", {})
                            if not head_before:
                                success = False
                                fix_summary = "Generic LLM rollback blocked: missing rollback token"
                            else:
                                try:
                                    rollback_paths = _rollback_llm_owned_changes(
                                        engine._project_root,
                                        head_before,
                                        status_before if isinstance(status_before, dict) else {},
                                    )
                                    changes = rollback_paths
                                    fix_summary = (
                                        "Generic LLM fix did not reduce issues; "
                                        f"rolled back {len(rollback_paths)} path(s)"
                                    )
                                    success = False
                                except RuntimeError as exc:
                                    success = False
                                    changes = []
                                    fix_summary = str(exc)
                    else:
                        logger.info(
                            "Generic LLM fix declined for %s: %s",
                            entry.name, llm_result.get("error", "unknown"),
                        )
                except Exception as llm_exc:
                    logger.warning("Generic LLM escalation error for %s: %s", entry.name, llm_exc)

    commit_hash = None
    reverted = False
    for fa in fix_actions:
        if isinstance(fa, dict) and fa.get("commit"):
            commit_hash = fa["commit"]
            break

    if success and commit_hash and engine._verify_command:
        if entry.name not in engine._SKIP_VERIFY_CATEGORIES:
            if not engine.verify_commit(commit_hash):
                success = False
                fix_summary = "regression: verify failed, commit reverted"
                reverted = True
                commit_hash = None

    if success and changes and finding_band == STRUCTURAL:
        success, reverted, structural_summary = _verify_structural_fix(
            engine=engine,
            entry=entry,
            ctx=ctx,
            issue_counts=issue_counts,
            commit_hash=commit_hash,
            llm_rollback=llm_rollback,
        )
        if not success:
            fix_summary = structural_summary
            commit_hash = None

    result = LoopResult(
        success=success, action="fix", category=entry.name,
        files=changes, commit=commit_hash,
        error=None if success else fix_summary,
        duration_ms=total_duration_ms,
    )

    engine.journal_writer.log(
        loop=loop_name, action="fix", category=entry.name,
        files=changes,
        result="success" if success else "failure",
        commit=commit_hash,
        error=None if success else fix_summary,
        duration_ms=total_duration_ms,
    )

    fix_outcome = _classify_fix_outcome(
        fix_result,
        success,
        changes,
        finding_band=finding_band,
        design_gate_written=design_gate_written,
        reverted=reverted,
        context_insufficient=context_insufficient,
    )
    reported_changes = list(changes)
    if fix_outcome == "design-written" and design_gate_info:
        reported_changes.append(design_gate_info["path"])

    # ADR-417: Post-fix verification — after any fix_type="code-fix",
    # run tsc --noEmit (if TS touched) or pytest (if Python touched)
    # to verify the fix didn't break anything. Phase 2 will implement
    # automatic verification here; for now the verify_commit guard above
    # handles regression detection when engine._verify_command is set.

    _update_trust_after_fix(
        engine, loop_name, loop_state, entry.name,
        success, fix_outcome, issue_counts,
        invalidated_categories, dep_invalidations, allow_invalidations,
        commit_hash=commit_hash,
        difficulty=ctx.difficulty,
        fix_result=fix_result,
    )

    engine.ledger.record_convergence(
        loop_name, entry.name, issues=issues, snapshot_fingerprint=snap_fp,
        entry_module=getattr(entry, "module", None),
    )

    cs = loop_state.categories.get(entry.name)
    self_repair_transition = ""
    if strategy_before != (cs.strategy if cs else "scan"):
        self_repair_transition = (
            "entered" if (cs and cs.strategy == "self-repair") else "recovered"
        )
    self_repair_plan = ""
    if cs and cs.strategy == "self-repair":
        self_repair_plan = engine._write_self_repair_plan(
            loop_name, entry, issues, fix_summary[:120],
        )
        engine.journal_writer.log(
            loop=loop_name, action="self-repair-plan", category=entry.name,
            result="success", files=[self_repair_plan], duration_ms=0,
        )

    _store_cat_report(cat_reports, engine._make_cat_report(
        entry.name, trust_before, diff_before, loop_state,
        "ok" if success else "broken", fix_summary[:120],
        outcome=fix_outcome,
        issue_count=len(issues), issue_counts=issue_counts,
        self_repair_plan=self_repair_plan,
        self_repair_transition=self_repair_transition,
        deepening_reason=deepening_reason, yield_class=yc,
        new_fingerprint_count=new_count,
        repeated_fingerprint_count=repeated_count,
        resolved_fingerprint_count=resolved_count,
        execution_mode=execution_mode,
        short_circuit_used=should_short_circuit,
        scan_duration_ms=scan_duration_ms,
        fix_duration_ms=fix_duration_ms,
        total_duration_ms=total_duration_ms,
        files_changed=reported_changes,
    ))

    results.append(result)
    return engine.ledger.check_allowed(loop_name, entry.name)


def _classify_fix_outcome(
    fix_result: Any,
    success: bool,
    changes: list,
    *,
    finding_band: str = LOCAL_SEMANTIC,
    design_gate_written: bool = False,
    reverted: bool = False,
    context_insufficient: bool = False,
) -> str:
    """Determine the fix outcome category."""
    return classify_fix_outcome_v2(
        success=success,
        changes=changes,
        fix_result={
            "fix_type": getattr(fix_result, "fix_type", "auto"),
            "actions": getattr(fix_result, "actions", []),
        },
        finding_band=finding_band,
        design_gate_written=design_gate_written,
        reverted=reverted,
        context_insufficient=context_insufficient,
    )


def _update_trust_after_fix(
    engine: Any,
    loop_name: str,
    loop_state: Any,
    entry_name: str,
    success: bool,
    fix_outcome: str,
    issue_counts: dict[str, int],
    invalidated_categories: set[str],
    dep_invalidations: dict[str, set[str]],
    allow_invalidations: bool,
    commit_hash: str | None = None,
    difficulty: int = 0,
    fix_result: Any = None,
) -> None:
    """Update trust ledger and invalidation sets after a fix.

    Key behavioral changes (trust algorithm v2):
    - Fix #1: Report-only fixes get ZERO trust credit. Only code-fix
      outcomes (auto-fixed with commit) build trust.
    - Fix #2: Difficulty escalation is gated on max_committed_difficulty.
    - Fix #3: Categories with 0 commits after 20+ fixes get demoted to d0.
    - Fix #4: Commits set pending_commit_verification for next-cycle check.
    """
    cs = loop_state.categories.get(entry_name)

    if success and fix_outcome in {"auto-fixed", "design-gated-fixed"}:
        engine.ledger.record_success(loop_name, entry_name)

        # Track fix stats for commit rate calculation
        if cs:
            cs.total_fixes += 1

            if commit_hash:
                # Real commit — update commit-specific tracking
                cs.total_commits += 1
                commit_credit = (1.0 - cs.commit_trust) * COMMIT_TRUST_INCREMENT
                cs.commit_trust = min(1.0, cs.commit_trust + commit_credit)
                cs.last_commit_trust_credit = commit_credit

                # Fix #2: Track highest difficulty that produced a commit
                cs.max_committed_difficulty = max(cs.max_committed_difficulty, difficulty)

                # Fix #4: Flag for next-cycle verification
                cs.pending_commit_verification = True

            # Fix #2: Cap difficulty at proven capability + buffer.
            # Even at max_committed_difficulty=0, cap at BUFFER (d1) until
            # a real commit proves the category can fix at higher levels.
            cap = cs.max_committed_difficulty + DIFFICULTY_COMMIT_GATE_BUFFER
            if cs.difficulty > cap:
                cs.difficulty = cap

        if allow_invalidations:
            invalidated_categories.update(
                dep_invalidations.get(entry_name, set())
            )

    elif success and fix_outcome in {
        "report-only",
        "design-written",
        "context-insufficient",
        "blocked-needs-design",
    }:
        # Fix #1 (v2): Report-only fixes get ZERO trust credit by default.
        # However, productive fixes that produce real side effects (sync,
        # index rebuild, cache update) get partial credit — enough to
        # advance difficulty over time, not enough to game trust.
        has_real_actions = bool(getattr(fix_result, "actions", None) or getattr(fix_result, "changes", None)) if fix_result else False
        fix_type_val = getattr(fix_result, "fix_type", "report") if fix_result else "report"

        if cs:
            cs.total_fixes += 1
            cs.consecutive_failures = 0

            # Productive fixes (sync, index, etc.) with real actions get partial credit
            if has_real_actions and fix_type_val not in ("report", None):
                productive_credit = (1.0 - cs.trust) * PRODUCTIVE_FIX_TRUST_INCREMENT
                cs.trust = min(1.0, cs.trust + productive_credit)
                cs.consecutive_successes += 1
            # Pure report-only: no trust credit, no success increment

            # Bootstrap promotion: when a category is report-only because its
            # DIFFICULTY_SPEC requires a higher difficulty for real fixes, AND the
            # commit gate caps it at the current level (no commits yet), promote
            # difficulty to break the deadlock. Without this, categories that are
            # scan-only at d0-d1 can never reach the fix threshold (d2+) because
            # the commit gate prevents escalation past max_committed_difficulty+1.
            cap = cs.max_committed_difficulty + DIFFICULTY_COMMIT_GATE_BUFFER
            if (
                cs.difficulty >= 1
                and cs.difficulty == cap
                and cs.total_commits == 0
                and cs.trust >= 0.3  # Minimum trust to earn promotion
                and cs.consecutive_successes >= 3  # Proven scan stability
                and issue_counts.get("actionable", 0) == 0  # Issues are maintenance at this diff
            ):
                cs.difficulty += 1
                cs.max_committed_difficulty = max(
                    cs.max_committed_difficulty, difficulty
                )
                logger.info(
                    "Bootstrap promotion for %s: d%d→d%d (report-only bottleneck, "
                    "trust=%.2f, %d consecutive successes)",
                    entry_name, cs.difficulty - 1, cs.difficulty,
                    cs.trust, cs.consecutive_successes,
                )

            # Fix #3: Demote categories that only produce reports after many attempts.
            # If a category has had 20+ fix attempts with zero commits, cap at d0.
            # Skip demotion if the category just got a bootstrap promotion.
            if (
                cs.total_fixes >= REPORT_ONLY_DEMOTION_THRESHOLD
                and cs.total_commits == 0
                and cs.difficulty > 0
                and cs.difficulty == cap  # Not just bootstrapped
            ):
                cs.difficulty = 0

        # Refund budget — report-only didn't consume real fix capacity
        loop_state.budget_remaining = min(
            loop_state.budget_remaining + 1, loop_state.budget
        )
        if allow_invalidations and issue_counts.get("maintenance", 0) > 0:
            invalidated_categories.update(
                dep_invalidations.get(entry_name, set())
            )
    else:
        if cs:
            cs.total_fixes += 1
        engine.ledger.record_failure(loop_name, entry_name)
