"""Git-aware archive primitive for tracked sweep targets."""
from __future__ import annotations

# TODO_CLEANUP: This file is 1135 lines — consider splitting into smaller modules
import subprocess
import hashlib
import json
import shlex
import shutil
from datetime import datetime, timezone
from os import path as os_path
from pathlib import Path
from typing import Any

ALLOWED_SOURCE_TABS = {"sources", "notes", "pages", "skills"}
ARCHIVE_SWEEP_ROOT = Path("archive") / "sweep"
LEDGER_REL_PATH = Path("archive") / "_ledger" / "sweep.jsonl"
GIT_HISTORY_PURGE_MODE = "git-history-purge"


def apply_git_archive(
    *,
    repo_root: Path,
    source_path: Path,
    source_tab: str,
    reason: str,
    artifact_group: str | None,
    apply_run_id: str,
) -> dict[str, Any]:
    """Archive a clean tracked file with `git mv`.

    The function stages only the rename produced by git. It never commits.
    """
    refusal, plan = _prepare_git_archive(
        repo_root=repo_root,
        source_path=source_path,
        source_tab=source_tab,
        reason=reason,
        artifact_group=artifact_group,
        apply_run_id=apply_run_id,
        refusal_status="refused",
    )
    if refusal is not None:
        return refusal
    assert plan is not None

    resolved_repo_root = plan["repo_root"]
    resolved_source_path = plan["source_path"]
    original_rel = plan["original_rel"]
    archived_rel = plan["archived_rel"]
    archived_path = plan["archived_path"]

    created_archive_dirs = _missing_parent_chain(
        repo_root=resolved_repo_root,
        parent=archived_path.parent,
    )
    archived_path.parent.mkdir(parents=True, exist_ok=True)
    moved = _git(resolved_repo_root, "mv", "--", original_rel, archived_rel)
    if moved.returncode != 0:
        _remove_empty_dirs(created_archive_dirs)
        return _refused(
            "git_mv_failed",
            repo_root=resolved_repo_root,
            source_path=resolved_source_path,
            reason=reason,
            artifact_group=artifact_group,
            apply_run_id=apply_run_id,
            original_rel=original_rel,
            archived_rel=archived_rel,
            archived_path=archived_path,
            error=_git_error(moved),
        )

    return {
        "status": "succeeded",
        "git_action": "mv",
        "from": original_rel,
        "to": archived_rel,
        "original_path": str(resolved_source_path),
        "archived_path": archived_rel,
        "repo_root": str(resolved_repo_root),
        "reason": reason,
        "artifact_group": artifact_group,
        "apply_run_id": apply_run_id,
        "recovery_hint": (
            f"Review the staged git mv from {original_rel} to {archived_rel}; "
            "commit it or restore it with git restore --staged --worktree -- "
            f"{original_rel} {archived_rel}."
        ),
    }


def preview_git_archive(
    *,
    repo_root: Path,
    source_path: Path,
    source_tab: str,
    reason: str,
    artifact_group: str | None,
    apply_run_id: str,
) -> dict[str, Any]:
    """Side-effect-free preview of the `git mv` archive decision."""
    refusal, plan = _prepare_git_archive(
        repo_root=repo_root,
        source_path=source_path,
        source_tab=source_tab,
        reason=reason,
        artifact_group=artifact_group,
        apply_run_id=apply_run_id,
        refusal_status="would_refuse",
    )
    if refusal is not None:
        return refusal
    assert plan is not None

    return {
        "status": "would_succeed",
        "git_action": "mv",
        "from": plan["original_rel"],
        "to": plan["archived_rel"],
        "original_path": str(plan["source_path"]),
        "archived_path": plan["archived_rel"],
        "repo_root": str(plan["repo_root"]),
        "reason": reason,
        "artifact_group": artifact_group,
        "apply_run_id": apply_run_id,
        "recovery_hint": None,
    }


def apply_git_history_purge_archive(
    *,
    repo_root: Path,
    source_path: Path,
    source_tab: str,
    source_kind: str,
    reason: str,
    artifact_group: str | None,
    apply_run_id: str,
    brain_id: str = "default",
    remote: str = "origin",
    branch: str | None = None,
) -> dict[str, Any]:
    """Archive a clean tracked file through a push-gated commit/purge lifecycle."""
    refusal, plan = _prepare_git_archive(
        repo_root=repo_root,
        source_path=source_path,
        source_tab=source_tab,
        reason=reason,
        artifact_group=artifact_group,
        apply_run_id=apply_run_id,
        refusal_status="refused",
    )
    if refusal is not None:
        return _with_history_metadata(refusal, source_kind=source_kind, brain_id=brain_id)
    assert plan is not None

    product_refusal = _core_product_skill_refusal(
        plan=plan,
        reason=reason,
        artifact_group=artifact_group,
        apply_run_id=apply_run_id,
        status="refused",
    )
    if product_refusal is not None:
        return _with_history_metadata(product_refusal, source_kind=source_kind, brain_id=brain_id)

    resolved_repo_root = plan["repo_root"]
    resolved_source_path = plan["source_path"]
    original_rel = plan["original_rel"]
    archived_rel = plan["archived_rel"]
    archived_path = plan["archived_path"]
    archive_record_id = _archive_record_id(
        apply_run_id=apply_run_id,
        original_rel=original_rel,
        archived_rel=archived_rel,
    )

    branch_name = branch
    if branch_name is None:
        branch_ok, branch_value, branch_error = _current_branch(resolved_repo_root)
        if not branch_ok:
            return _history_refused_from_plan(
                "branch_unavailable",
                plan=plan,
                reason=reason,
                artifact_group=artifact_group,
                apply_run_id=apply_run_id,
                source_kind=source_kind,
                brain_id=brain_id,
                error=branch_error,
            )
        branch_name = branch_value

    created_archive_dirs = _missing_parent_chain(
        repo_root=resolved_repo_root,
        parent=archived_path.parent,
    )
    archived_path.parent.mkdir(parents=True, exist_ok=True)
    moved = _git(resolved_repo_root, "mv", "--", original_rel, archived_rel)
    if moved.returncode != 0:
        _remove_empty_dirs(created_archive_dirs)
        return _history_refused_from_plan(
            "git_mv_failed",
            plan=plan,
            reason=reason,
            artifact_group=artifact_group,
            apply_run_id=apply_run_id,
            source_kind=source_kind,
            brain_id=brain_id,
            error=_git_error(moved),
        )

    archive_event = {
        "event": "archive_prepared",
        "archive_record_id": archive_record_id,
        "brain_id": brain_id,
        "source_kind": source_kind,
        "source_tab": source_tab,
        "original_path": original_rel,
        "archived_path": archived_rel,
        "reason": reason,
        "artifact_group": artifact_group,
        "apply_run_id": apply_run_id,
        "archived_at": _utc_now_iso(),
    }
    try:
        _append_ledger_event(resolved_repo_root, archive_event)
    except OSError as exc:
        return _history_partial_result(
            failure_phase="ledger_append",
            plan=plan,
            source_kind=source_kind,
            brain_id=brain_id,
            archive_record_id=archive_record_id,
            reason=reason,
            artifact_group=artifact_group,
            apply_run_id=apply_run_id,
            archive_commit=None,
            archive_pushed=False,
            purged=False,
            purge_commit=None,
            purge_pushed=False,
            error=str(exc),
            recovery_hint=(
                f"Archive payload moved to {archived_rel}, but ledger append failed. "
                "Inspect the repository before retrying."
            ),
        )

    staged = _git(resolved_repo_root, "add", "--", LEDGER_REL_PATH.as_posix(), archived_rel)
    if staged.returncode != 0:
        return _history_partial_result(
            failure_phase="archive_stage",
            plan=plan,
            source_kind=source_kind,
            brain_id=brain_id,
            archive_record_id=archive_record_id,
            reason=reason,
            artifact_group=artifact_group,
            apply_run_id=apply_run_id,
            archive_commit=None,
            archive_pushed=False,
            purged=False,
            purge_commit=None,
            purge_pushed=False,
            error=_git_error(staged),
            recovery_hint=f"Archive payload moved to {archived_rel}; fix git staging and retry.",
        )

    archive_committed, archive_commit, archive_commit_error = _commit_staged(
        resolved_repo_root,
        f"archive sweep payload: {Path(original_rel).name}",
    )
    if not archive_committed:
        return _history_partial_result(
            failure_phase="archive_commit",
            plan=plan,
            source_kind=source_kind,
            brain_id=brain_id,
            archive_record_id=archive_record_id,
            reason=reason,
            artifact_group=artifact_group,
            apply_run_id=apply_run_id,
            archive_commit=None,
            archive_pushed=False,
            purged=False,
            purge_commit=None,
            purge_pushed=False,
            error=archive_commit_error,
            recovery_hint=f"Archive payload is staged at {archived_rel}; resolve commit failure.",
        )

    archive_pushed, archive_push_error = _push_branch(resolved_repo_root, remote, branch_name)
    if not archive_pushed:
        return _history_partial_result(
            failure_phase="archive_push",
            plan=plan,
            source_kind=source_kind,
            brain_id=brain_id,
            archive_record_id=archive_record_id,
            reason=reason,
            artifact_group=artifact_group,
            apply_run_id=apply_run_id,
            archive_commit=archive_commit,
            archive_pushed=False,
            purged=False,
            purge_commit=None,
            purge_pushed=False,
            error=archive_push_error,
            recovery_hint=(
                f"Archive commit {archive_commit} is local only. Resolve push failure, "
                f"then run git -C {resolved_repo_root} push {remote} {branch_name}. "
                f"Do not delete {archived_rel} until that push succeeds."
            ),
        )

    deleted, delete_error = _delete_archived_payload(resolved_repo_root, archived_rel)
    if not deleted:
        return _history_partial_result(
            failure_phase="purge_delete",
            plan=plan,
            source_kind=source_kind,
            brain_id=brain_id,
            archive_record_id=archive_record_id,
            reason=reason,
            artifact_group=artifact_group,
            apply_run_id=apply_run_id,
            archive_commit=archive_commit,
            archive_pushed=True,
            purged=False,
            purge_commit=None,
            purge_pushed=False,
            error=delete_error or "delete failed",
            recovery_hint=f"Archive commit {archive_commit} is pushed; inspect {archived_rel}.",
        )

    recovery_hint = _recovery_hint_for_commit(
        archive_commit=archive_commit,
        archived_rel=archived_rel,
        original_rel=original_rel,
    )
    purge_event = {
        "event": "purged",
        "archive_record_id": archive_record_id,
        "brain_id": brain_id,
        "archived_path": archived_rel,
        "archive_commit": archive_commit,
        "archive_pushed": True,
        "purged_at": _utc_now_iso(),
        "recovery_hint": recovery_hint,
    }
    try:
        _append_ledger_event(resolved_repo_root, purge_event)
    except OSError as exc:
        return _history_partial_result(
            failure_phase="purge_ledger_append",
            plan=plan,
            source_kind=source_kind,
            brain_id=brain_id,
            archive_record_id=archive_record_id,
            reason=reason,
            artifact_group=artifact_group,
            apply_run_id=apply_run_id,
            archive_commit=archive_commit,
            archive_pushed=True,
            purged=True,
            purge_commit=None,
            purge_pushed=False,
            error=str(exc),
            recovery_hint=recovery_hint,
        )

    purge_staged = _git(resolved_repo_root, "add", "--", LEDGER_REL_PATH.as_posix(), archived_rel)
    if purge_staged.returncode != 0:
        return _history_partial_result(
            failure_phase="purge_stage",
            plan=plan,
            source_kind=source_kind,
            brain_id=brain_id,
            archive_record_id=archive_record_id,
            reason=reason,
            artifact_group=artifact_group,
            apply_run_id=apply_run_id,
            archive_commit=archive_commit,
            archive_pushed=True,
            purged=True,
            purge_commit=None,
            purge_pushed=False,
            error=_git_error(purge_staged),
            recovery_hint=recovery_hint,
        )

    purge_committed, purge_commit, purge_commit_error = _commit_staged(
        resolved_repo_root,
        f"purge swept archive payload: {Path(original_rel).name}",
    )
    if not purge_committed:
        return _history_partial_result(
            failure_phase="purge_commit",
            plan=plan,
            source_kind=source_kind,
            brain_id=brain_id,
            archive_record_id=archive_record_id,
            reason=reason,
            artifact_group=artifact_group,
            apply_run_id=apply_run_id,
            archive_commit=archive_commit,
            archive_pushed=True,
            purged=True,
            purge_commit=None,
            purge_pushed=False,
            error=purge_commit_error,
            recovery_hint=recovery_hint,
        )

    purge_pushed, purge_push_error = _push_branch(resolved_repo_root, remote, branch_name)
    if not purge_pushed:
        return _history_partial_result(
            failure_phase="purge_push",
            plan=plan,
            source_kind=source_kind,
            brain_id=brain_id,
            archive_record_id=archive_record_id,
            reason=reason,
            artifact_group=artifact_group,
            apply_run_id=apply_run_id,
            archive_commit=archive_commit,
            archive_pushed=True,
            purged=True,
            purge_commit=purge_commit,
            purge_pushed=False,
            error=purge_push_error,
            recovery_hint=(
                f"Purge commit {purge_commit} is local only. Push it with "
                f"git -C {resolved_repo_root} push {remote} {branch_name}. "
                f"Recovery payload is preserved in archive commit {archive_commit}."
            ),
        )

    result = _history_success_result(
        plan=plan,
        source_kind=source_kind,
        brain_id=brain_id,
        archive_record_id=archive_record_id,
        reason=reason,
        artifact_group=artifact_group,
        apply_run_id=apply_run_id,
        archive_commit=archive_commit,
        purge_commit=purge_commit,
        recovery_hint=recovery_hint,
    )
    return result


def preview_git_history_purge_archive(
    *,
    repo_root: Path,
    source_path: Path,
    source_tab: str,
    source_kind: str,
    reason: str,
    artifact_group: str | None,
    apply_run_id: str,
    brain_id: str = "default",
    remote: str = "origin",
    branch: str | None = None,
) -> dict[str, Any]:
    """Side-effect-free preview of the git-history purge archive decision."""
    del remote, branch
    refusal, plan = _prepare_git_archive(
        repo_root=repo_root,
        source_path=source_path,
        source_tab=source_tab,
        reason=reason,
        artifact_group=artifact_group,
        apply_run_id=apply_run_id,
        refusal_status="would_refuse",
    )
    if refusal is not None:
        return _with_history_metadata(refusal, source_kind=source_kind, brain_id=brain_id)
    assert plan is not None

    product_refusal = _core_product_skill_refusal(
        plan=plan,
        reason=reason,
        artifact_group=artifact_group,
        apply_run_id=apply_run_id,
        status="would_refuse",
    )
    if product_refusal is not None:
        return _with_history_metadata(product_refusal, source_kind=source_kind, brain_id=brain_id)

    archive_record_id = _archive_record_id(
        apply_run_id=apply_run_id,
        original_rel=plan["original_rel"],
        archived_rel=plan["archived_rel"],
    )
    return {
        "status": "would_succeed",
        "archive_mode": GIT_HISTORY_PURGE_MODE,
        "git_action": "mv+purge",
        "from": plan["original_rel"],
        "to": plan["archived_rel"],
        "original_path": str(plan["source_path"]),
        "archived_path": plan["archived_rel"],
        "repo_root": str(plan["repo_root"]),
        "ledger_path": LEDGER_REL_PATH.as_posix(),
        "archive_record_id": archive_record_id,
        "archive_commit": None,
        "archive_pushed": False,
        "purge_commit": None,
        "purge_pushed": False,
        "purged": False,
        "reason": reason,
        "artifact_group": artifact_group,
        "apply_run_id": apply_run_id,
        "brain_id": brain_id,
        "source_kind": source_kind,
        "recovery_hint": None,
    }


def _prepare_git_archive(
    *,
    repo_root: Path,
    source_path: Path,
    source_tab: str,
    reason: str,
    artifact_group: str | None,
    apply_run_id: str,
    refusal_status: str,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    original_source_path = Path(source_path)
    lexical_repo_root = Path(os_path.abspath(repo_root))
    resolved_repo_root = lexical_repo_root.resolve()
    lexical_source_path = _lexical_absolute_path(original_source_path, lexical_repo_root)

    if source_tab not in ALLOWED_SOURCE_TABS:
        return _refused(
            "invalid_source_tab",
            repo_root=resolved_repo_root,
            source_path=original_source_path,
            reason=reason,
            artifact_group=artifact_group,
            apply_run_id=apply_run_id,
            status=refusal_status,
        ), None

    try:
        lexical_rel_path = lexical_source_path.relative_to(lexical_repo_root)
    except ValueError:
        lexical_rel_path = None

    resolved_source_path = lexical_source_path.resolve()
    if not _is_inside_repo(resolved_source_path, resolved_repo_root):
        return _refused(
            "outside_repo",
            repo_root=resolved_repo_root,
            source_path=resolved_source_path,
            reason=reason,
            artifact_group=artifact_group,
            apply_run_id=apply_run_id,
            status=refusal_status,
        ), None

    if lexical_rel_path is None:
        if lexical_source_path != resolved_source_path:
            return _refused(
                "outside_repo",
                repo_root=resolved_repo_root,
                source_path=resolved_source_path,
                reason=reason,
                artifact_group=artifact_group,
                apply_run_id=apply_run_id,
                status=refusal_status,
            ), None
        symlink_rel_path = resolved_source_path.relative_to(resolved_repo_root)
    else:
        symlink_rel_path = lexical_rel_path

    symlink_check_path = resolved_repo_root / symlink_rel_path
    if lexical_source_path.is_symlink() or _has_symlink_parent(
        repo_root=resolved_repo_root,
        path=symlink_check_path,
    ):
        return _refused(
            "symlink",
            repo_root=resolved_repo_root,
            source_path=original_source_path,
            reason=reason,
            artifact_group=artifact_group,
            apply_run_id=apply_run_id,
            status=refusal_status,
        ), None

    if not resolved_source_path.exists() or not resolved_source_path.is_file():
        return _refused(
            "source_missing",
            repo_root=resolved_repo_root,
            source_path=resolved_source_path,
            reason=reason,
            artifact_group=artifact_group,
            apply_run_id=apply_run_id,
            status=refusal_status,
        ), None

    repo_validation = _git(resolved_repo_root, "rev-parse", "--show-toplevel")
    if repo_validation.returncode != 0:
        return _refused(
            "not_git_repository",
            repo_root=resolved_repo_root,
            source_path=resolved_source_path,
            reason=reason,
            artifact_group=artifact_group,
            apply_run_id=apply_run_id,
            error=_git_error(repo_validation),
            status=refusal_status,
        ), None

    git_toplevel = Path(repo_validation.stdout.strip()).resolve()
    if git_toplevel != resolved_repo_root:
        return _refused(
            "repo_root_mismatch",
            repo_root=resolved_repo_root,
            source_path=resolved_source_path,
            reason=reason,
            artifact_group=artifact_group,
            apply_run_id=apply_run_id,
            error=f"git toplevel is {git_toplevel}",
            status=refusal_status,
        ), None

    try:
        original_rel_path = resolved_source_path.relative_to(resolved_repo_root)
    except ValueError:
        return _refused(
            "outside_repo",
            repo_root=resolved_repo_root,
            source_path=resolved_source_path,
            reason=reason,
            artifact_group=artifact_group,
            apply_run_id=apply_run_id,
            status=refusal_status,
        ), None

    original_rel = original_rel_path.as_posix()
    tracked = _git(resolved_repo_root, "ls-files", "--error-unmatch", "--", original_rel)
    if tracked.returncode != 0:
        return _refused(
            "untracked",
            repo_root=resolved_repo_root,
            source_path=resolved_source_path,
            reason=reason,
            artifact_group=artifact_group,
            apply_run_id=apply_run_id,
            original_rel=original_rel,
            error=_git_error(tracked),
            status=refusal_status,
        ), None

    status = _git(resolved_repo_root, "status", "--porcelain", "--", original_rel)
    if status.returncode != 0:
        return _refused(
            "git_status_failed",
            repo_root=resolved_repo_root,
            source_path=resolved_source_path,
            reason=reason,
            artifact_group=artifact_group,
            apply_run_id=apply_run_id,
            original_rel=original_rel,
            error=_git_error(status),
            status=refusal_status,
        ), None
    if status.stdout.strip():
        return _refused(
            "dirty",
            repo_root=resolved_repo_root,
            source_path=resolved_source_path,
            reason=reason,
            artifact_group=artifact_group,
            apply_run_id=apply_run_id,
            original_rel=original_rel,
            error=status.stdout.strip(),
            status=refusal_status,
        ), None

    utc_date = datetime.now(timezone.utc).date().isoformat()
    archived_rel_path = Path("archive") / "sweep" / source_tab / utc_date / original_rel_path
    archived_rel = archived_rel_path.as_posix()
    archived_path = resolved_repo_root / archived_rel_path
    if archived_path.exists() or archived_path.is_symlink():
        return _refused(
            "archive_destination_exists",
            repo_root=resolved_repo_root,
            source_path=resolved_source_path,
            reason=reason,
            artifact_group=artifact_group,
            apply_run_id=apply_run_id,
            original_rel=original_rel,
            archived_rel=archived_rel,
            archived_path=archived_path,
            status=refusal_status,
        ), None

    parent_refusal = _archive_parent_refusal(
        repo_root=resolved_repo_root,
        archived_parent=archived_path.parent,
    )
    if parent_refusal is not None:
        return _refused(
            parent_refusal,
            repo_root=resolved_repo_root,
            source_path=resolved_source_path,
            reason=reason,
            artifact_group=artifact_group,
            apply_run_id=apply_run_id,
            original_rel=original_rel,
            archived_rel=archived_rel,
            archived_path=archived_path,
            status=refusal_status,
        ), None

    return None, {
        "repo_root": resolved_repo_root,
        "source_path": resolved_source_path,
        "original_rel": original_rel,
        "archived_rel": archived_rel,
        "archived_path": archived_path,
    }


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _append_ledger_event(repo_root: Path, event: dict[str, Any]) -> None:
    ledger = repo_root / LEDGER_REL_PATH
    parent_refusal = _archive_parent_refusal(repo_root=repo_root, archived_parent=ledger.parent)
    if parent_refusal is not None:
        raise OSError(parent_refusal)
    if ledger.is_symlink():
        raise OSError("ledger_symlink")
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")


def _commit_staged(repo_root: Path, message: str) -> tuple[bool, str, str]:
    committed = _git(repo_root, "commit", "-m", message)
    if committed.returncode != 0:
        return False, "", _git_error(committed)
    head = _git(repo_root, "rev-parse", "HEAD")
    if head.returncode != 0:
        return False, "", _git_error(head)
    return True, head.stdout.strip(), ""


def _current_branch(repo_root: Path) -> tuple[bool, str, str]:
    branch = _git(repo_root, "branch", "--show-current")
    if branch.returncode != 0:
        return False, "", _git_error(branch)
    name = branch.stdout.strip()
    if not name:
        return False, "", "repository is detached or branch name is unavailable"
    return True, name, ""


def _push_branch(repo_root: Path, remote: str, branch: str) -> tuple[bool, str]:
    pushed = _git(repo_root, "push", remote, branch)
    if pushed.returncode != 0:
        return False, _git_error(pushed)
    return True, ""


def _delete_archived_payload(repo_root: Path, archived_rel: str) -> tuple[bool, str | None]:
    relative = Path(archived_rel)
    if relative.is_absolute() or ".." in relative.parts:
        return False, "unsafe_archive_path"
    if not _is_relative_to_path(relative, ARCHIVE_SWEEP_ROOT):
        return False, "outside_archive_sweep"
    path = repo_root / relative
    archive_root = repo_root / ARCHIVE_SWEEP_ROOT
    resolved = path.resolve(strict=False)
    if not _is_inside_repo(resolved, archive_root.resolve(strict=False)):
        return False, "outside_archive_sweep"
    if path.is_symlink():
        return False, "archive_payload_symlink"
    if path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)
    else:
        return False, "archive_payload_missing"
    _prune_empty_archive_dirs(repo_root=repo_root, start=path.parent)
    return True, None


def _prune_empty_archive_dirs(*, repo_root: Path, start: Path) -> None:
    stop = repo_root / ARCHIVE_SWEEP_ROOT
    current = start
    while current != stop and _is_inside_repo(current.resolve(strict=False), stop.resolve(strict=False)):
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent


def _archive_record_id(*, apply_run_id: str, original_rel: str, archived_rel: str) -> str:
    digest = hashlib.sha256(
        f"{apply_run_id}\0{original_rel}\0{archived_rel}".encode("utf-8")
    ).hexdigest()
    return f"sha256:{digest}"


def _recovery_hint_for_commit(*, archive_commit: str, archived_rel: str, original_rel: str) -> str:
    original_parent = Path(original_rel).parent.as_posix()
    mkdir_command = (
        f"mkdir -p {shlex.quote(original_parent)}; "
        if original_parent and original_parent != "."
        else ""
    )
    return (
        f"Restore with git restore --source={archive_commit} --staged --worktree -- "
        f"{shlex.quote(archived_rel)}; {mkdir_command}"
        f"git mv {shlex.quote(archived_rel)} {shlex.quote(original_rel)}."
    )


def _core_product_skill_refusal(
    *,
    plan: dict[str, Any],
    reason: str,
    artifact_group: str | None,
    apply_run_id: str,
    status: str,
) -> dict[str, Any] | None:
    if not _is_core_product_skill_target(plan["repo_root"], plan["original_rel"]):
        return None
    return _refused(
        "core_product_skill",
        repo_root=plan["repo_root"],
        source_path=plan["source_path"],
        reason=reason,
        artifact_group=artifact_group,
        apply_run_id=apply_run_id,
        original_rel=plan["original_rel"],
        archived_rel=plan["archived_rel"],
        archived_path=plan["archived_path"],
        status=status,
    )


def _is_core_product_skill_target(repo_root: Path, original_rel: str) -> bool:
    return (
        original_rel.startswith("project-brain/capabilities/skills/")
        and (repo_root / "pyproject.toml").is_file()
        and (repo_root / "docs" / "adrs").is_dir()
    )


def _with_history_metadata(
    result: dict[str, Any],
    *,
    source_kind: str,
    brain_id: str,
) -> dict[str, Any]:
    enriched = dict(result)
    enriched["archive_mode"] = GIT_HISTORY_PURGE_MODE
    enriched["source_kind"] = source_kind
    enriched["brain_id"] = brain_id
    enriched.setdefault("ledger_path", LEDGER_REL_PATH.as_posix())
    return enriched


def _history_refused_from_plan(
    refusal_category: str,
    *,
    plan: dict[str, Any],
    reason: str,
    artifact_group: str | None,
    apply_run_id: str,
    source_kind: str,
    brain_id: str,
    error: str | None = None,
) -> dict[str, Any]:
    return _with_history_metadata(
        _refused(
            refusal_category,
            repo_root=plan["repo_root"],
            source_path=plan["source_path"],
            reason=reason,
            artifact_group=artifact_group,
            apply_run_id=apply_run_id,
            original_rel=plan["original_rel"],
            archived_rel=plan["archived_rel"],
            archived_path=plan["archived_path"],
            error=error,
        ),
        source_kind=source_kind,
        brain_id=brain_id,
    )


def _history_success_result(
    *,
    plan: dict[str, Any],
    source_kind: str,
    brain_id: str,
    archive_record_id: str,
    reason: str,
    artifact_group: str | None,
    apply_run_id: str,
    archive_commit: str,
    purge_commit: str,
    recovery_hint: str,
) -> dict[str, Any]:
    return {
        "status": "succeeded",
        "archive_mode": GIT_HISTORY_PURGE_MODE,
        "git_action": "mv+purge",
        "from": plan["original_rel"],
        "to": plan["archived_rel"],
        "original_path": str(plan["source_path"]),
        "archived_path": plan["archived_rel"],
        "repo_root": str(plan["repo_root"]),
        "ledger_path": LEDGER_REL_PATH.as_posix(),
        "archive_record_id": archive_record_id,
        "archive_commit": archive_commit,
        "archive_pushed": True,
        "purge_commit": purge_commit,
        "purge_pushed": True,
        "purged": True,
        "reason": reason,
        "artifact_group": artifact_group,
        "apply_run_id": apply_run_id,
        "brain_id": brain_id,
        "source_kind": source_kind,
        "recovery_hint": recovery_hint,
    }


def _history_partial_result(
    *,
    failure_phase: str,
    plan: dict[str, Any],
    source_kind: str,
    brain_id: str,
    archive_record_id: str,
    reason: str,
    artifact_group: str | None,
    apply_run_id: str,
    archive_commit: str | None,
    archive_pushed: bool,
    purged: bool,
    purge_commit: str | None,
    purge_pushed: bool,
    error: str | None,
    recovery_hint: str,
) -> dict[str, Any]:
    result = {
        "status": "partial",
        "failure_phase": failure_phase,
        "archive_mode": GIT_HISTORY_PURGE_MODE,
        "git_action": "mv+purge",
        "from": plan["original_rel"],
        "to": plan["archived_rel"],
        "original_path": str(plan["source_path"]),
        "archived_path": plan["archived_rel"],
        "repo_root": str(plan["repo_root"]),
        "ledger_path": LEDGER_REL_PATH.as_posix(),
        "archive_record_id": archive_record_id,
        "archive_commit": archive_commit,
        "archive_pushed": archive_pushed,
        "purge_commit": purge_commit,
        "purge_pushed": purge_pushed,
        "purged": purged,
        "reason": reason,
        "artifact_group": artifact_group,
        "apply_run_id": apply_run_id,
        "brain_id": brain_id,
        "source_kind": source_kind,
        "recovery_hint": recovery_hint,
    }
    if error:
        result["error"] = error
    return result


def _is_relative_to_path(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        shell=False,
        text=True,
        capture_output=True,
        check=False,
    )


def _lexical_absolute_path(path: Path, repo_root: Path) -> Path:
    if not path.is_absolute():
        path = repo_root / path
    return Path(os_path.abspath(path))


def _has_symlink_parent(*, repo_root: Path, path: Path) -> bool:
    try:
        rel_parent = path.parent.relative_to(repo_root)
    except ValueError:
        return False

    current = repo_root
    for part in rel_parent.parts:
        current = current / part
        if current.is_symlink():
            return True
    return False


def _is_inside_repo(path: Path, repo_root: Path) -> bool:
    try:
        path.relative_to(repo_root)
    except ValueError:
        return False
    return True


def _archive_parent_refusal(*, repo_root: Path, archived_parent: Path) -> str | None:
    try:
        rel_parent = archived_parent.relative_to(repo_root)
    except ValueError:
        return "outside_repo"

    current = repo_root
    for part in rel_parent.parts:
        current = current / part
        if current.exists() or current.is_symlink():
            if current.is_symlink():
                return "archive_parent_symlink"
            if not current.is_dir():
                return "archive_parent_not_directory"
            continue
        break
    return None


def _missing_parent_chain(*, repo_root: Path, parent: Path) -> list[Path]:
    missing: list[Path] = []
    current = parent
    while current != repo_root:
        if current.exists() or current.is_symlink():
            break
        try:
            current.relative_to(repo_root)
        except ValueError:
            break
        missing.append(current)
        current = current.parent
    return missing


def _remove_empty_dirs(paths: list[Path]) -> None:
    for path in paths:
        try:
            path.rmdir()
        except OSError:
            continue


def _refused(
    refusal_category: str,
    *,
    repo_root: Path,
    source_path: Path,
    reason: str,
    artifact_group: str | None,
    apply_run_id: str,
    original_rel: str | None = None,
    archived_rel: str | None = None,
    archived_path: Path | None = None,
    error: str | None = None,
    status: str = "refused",
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": status,
        "git_action": "none",
        "refusal_category": refusal_category,
        "from": original_rel,
        "to": archived_rel,
        "original_path": str(source_path),
        "archived_path": str(archived_path) if archived_path is not None else None,
        "repo_root": str(repo_root),
        "reason": reason,
        "artifact_group": artifact_group,
        "apply_run_id": apply_run_id,
        "recovery_hint": _recovery_hint(refusal_category),
    }
    if error:
        result["error"] = error
    return result


def _git_error(result: subprocess.CompletedProcess[str]) -> str:
    return (result.stderr or result.stdout or f"git exited with {result.returncode}").strip()


def _recovery_hint(refusal_category: str) -> str:
    hints = {
        "archive_parent_not_directory": "Move or remove the archive parent path collision before retrying.",
        "archive_parent_symlink": "Replace the archive parent symlink with a real directory before retrying.",
        "archive_destination_exists": "Move or inspect the existing archive destination before retrying.",
        "dirty": "Commit, stash, or restore source changes before retrying.",
        "git_mv_failed": "Inspect the git error and retry after resolving the repository state.",
        "git_status_failed": "Inspect the git status error and retry after resolving the repository state.",
        "invalid_source_tab": "Use one of: sources, notes, pages, skills.",
        "not_git_repository": "Pass a repo_root that is a git repository.",
        "outside_repo": "Pass a source path inside repo_root.",
        "repo_root_mismatch": "Pass the git repository root, not a nested directory.",
        "source_missing": "Pass an existing regular file.",
        "symlink": "Resolve or replace the symlink before archiving.",
        "untracked": "Add and commit the file before using the git-aware archive primitive.",
        "branch_unavailable": "Check out a branch before using git-history purge archive.",
        "core_product_skill": (
            "Core Augur product skills are retired through product git history, not brain archive purge."
        ),
    }
    return hints.get(refusal_category, "Resolve the refusal reason and retry.")
