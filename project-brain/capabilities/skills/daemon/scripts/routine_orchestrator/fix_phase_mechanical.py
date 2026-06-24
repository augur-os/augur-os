"""Pure-Python mechanical fix path for the ADR-755 routine orchestrator."""
from __future__ import annotations

import shlex
import subprocess
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

import yaml

from src.lib.ops_protocol import OpsContext, SessionContext

try:  # Package import in normal runtime.
    from .trust import COMMIT_TRUST_INCREMENT, DIFFICULTY_COMMIT_GATE_BUFFER, TrustLedger
except ImportError:  # Direct importlib.spec_from_file_location tests.
    from routine_orchestrator.trust import (  # type: ignore[no-redef]
        COMMIT_TRUST_INCREMENT,
        DIFFICULTY_COMMIT_GATE_BUFFER,
        TrustLedger,
    )

try:
    from adaptive.engine_quality import (
        LOCAL_SEMANTIC as ADAPTIVE_LOCAL_SEMANTIC,
        MECHANICAL as ADAPTIVE_MECHANICAL,
        STRUCTURAL as ADAPTIVE_STRUCTURAL,
        classify_finding_band,
    )
except ModuleNotFoundError:
    from skills.daemon.scripts.adaptive.engine_quality import (  # type: ignore[no-redef]
        LOCAL_SEMANTIC as ADAPTIVE_LOCAL_SEMANTIC,
        MECHANICAL as ADAPTIVE_MECHANICAL,
        STRUCTURAL as ADAPTIVE_STRUCTURAL,
        classify_finding_band,
    )


MECHANICAL = ADAPTIVE_MECHANICAL
LOCAL_SEMANTIC = ADAPTIVE_LOCAL_SEMANTIC
STRUCTURAL = ADAPTIVE_STRUCTURAL


VerifyRunner = Callable[..., bool]
CommitRunner = Callable[..., str]


@dataclass(frozen=True)
class FixCommand:
    """Small command wrapper for fix dispatch."""

    name: str
    module: Any
    loop_name: str
    config: dict[str, Any] = field(default_factory=dict)
    tier: int = 0


@dataclass(frozen=True)
class AppliedMechanicalFix:
    """A verified mechanical fix committed to git."""

    finding: dict[str, Any]
    command: str
    changed_files: list[str]
    commit: str
    trust_notifications: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FailedMechanicalFix:
    """A mechanical finding that was attempted but not kept."""

    finding: dict[str, Any]
    command: str
    changed_files: list[str]
    reason: str
    trust_notifications: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class MechanicalFixResult:
    """Result of one pure-Python mechanical fix pass."""

    applied: list[AppliedMechanicalFix] = field(default_factory=list)
    deferred: list[dict[str, Any]] = field(default_factory=list)
    failed: list[FailedMechanicalFix] = field(default_factory=list)


@dataclass(frozen=True)
class DirtyPathSnapshot:
    """Pre-fix content snapshot for a dirty file path."""

    path: str
    data: bytes | None


def apply_mechanical_fixes(
    findings: Iterable[dict[str, Any]],
    *,
    commands: Iterable[Any] | Mapping[str, Any],
    project_root: Path | str,
    state_dir: Path | str,
    trust_config: dict[str, Any] | None = None,
    verify_command: Any | None = None,
    verify_runner: VerifyRunner | None = None,
    commit_runner: CommitRunner | None = None,
    subagent_dispatch: Callable[..., Any] | None = None,
    difficulty: int = 0,
    loop_config: dict[str, Any] | None = None,
    shared_snapshot: dict[str, Any] | None = None,
    client: str | None = None,
) -> MechanicalFixResult:
    """Apply only mechanical findings, verify, commit, and record trust.

    ``subagent_dispatch`` is accepted to make the no-session contract explicit
    in tests and future call sites; this function never calls it. Semantic and
    structural findings are returned in ``deferred`` for later phases.
    """
    del subagent_dispatch

    root = Path(project_root)
    state_path = Path(state_dir)
    entries = _resolve_commands(commands)
    config = trust_config or _build_trust_config(entries)
    ledger = TrustLedger(config, state_dir=state_path)
    run_verify = verify_runner or _default_verify_runner
    run_commit = commit_runner or _default_commit_runner

    applied: list[AppliedMechanicalFix] = []
    deferred: list[dict[str, Any]] = []
    failed: list[FailedMechanicalFix] = []

    for finding in findings:
        if _finding_band(finding) != MECHANICAL:
            deferred.append(finding)
            continue

        command_name = str(finding.get("auto_command") or "")
        command_entry = entries.get(command_name)
        if command_entry is None:
            failed.append(
                FailedMechanicalFix(
                    finding=finding,
                    command=command_name,
                    changed_files=[],
                    reason="command not found",
                )
            )
            continue

        pre_status = _status_paths(root)
        dirty_snapshots = _snapshot_dirty_paths(root, pre_status)
        preexisting_targets = _preexisting_overlaps(_finding_paths(finding), pre_status)
        if preexisting_targets:
            failed.append(
                FailedMechanicalFix(
                    finding=finding,
                    command=command_entry.name,
                    changed_files=preexisting_targets,
                    reason="pre-existing changes in target path",
                )
            )
            continue

        ctx = OpsContext(
            project_root=root,
            difficulty=difficulty,
            dry_run=False,
            config=dict(command_entry.config),
            loop_config=dict(loop_config or {}),
            shared_snapshot=dict(shared_snapshot or {}),
            session=SessionContext(has_tool_access=False, has_llm=False),
            client=client,
        )
        try:
            fix_result = command_entry.module.fix(ctx, [finding])
        except Exception as exc:  # noqa: BLE001 - command crashes are recorded as failed fixes.
            actual_changed = _actual_changed_files(root, pre_status)
            _revert_files(root, actual_changed, pre_status=pre_status)
            notifications = _record_failure(
                ledger,
                str(finding.get("loop") or command_entry.loop_name),
                command_entry.name,
            )
            failed.append(
                FailedMechanicalFix(
                    finding=finding,
                    command=command_entry.name,
                    changed_files=actual_changed,
                    reason=f"fix raised: {exc}",
                    trust_notifications=notifications,
                )
            )
            continue

        try:
            changed_files = _normalize_changed_files(root, _changed_files(fix_result))
        except ValueError as exc:
            actual_changed = _actual_changed_files(root, pre_status)
            _revert_files(root, actual_changed, pre_status=pre_status)
            notifications = _record_failure(
                ledger,
                str(finding.get("loop") or command_entry.loop_name),
                command_entry.name,
            )
            failed.append(
                FailedMechanicalFix(
                    finding=finding,
                    command=command_entry.name,
                    changed_files=actual_changed,
                    reason=str(exc),
                    trust_notifications=notifications,
                )
            )
            continue

        actual_changed = _actual_changed_files(root, pre_status)
        changed_dirty = _changed_dirty_paths(root, dirty_snapshots)
        if changed_dirty:
            _restore_dirty_snapshots(root, dirty_snapshots, changed_dirty)
            _revert_files(root, actual_changed, pre_status=pre_status)
            notifications = _record_failure(
                ledger,
                str(finding.get("loop") or command_entry.loop_name),
                command_entry.name,
            )
            failed.append(
                FailedMechanicalFix(
                    finding=finding,
                    command=command_entry.name,
                    changed_files=sorted(set(actual_changed + changed_dirty)),
                    reason="fix changed pre-existing dirty paths",
                    trust_notifications=notifications,
                )
            )
            continue

        unreported_changed = _unreported_changes(actual_changed, changed_files)
        if unreported_changed:
            _revert_files(root, actual_changed, pre_status=pre_status)
            notifications = _record_failure(
                ledger,
                str(finding.get("loop") or command_entry.loop_name),
                command_entry.name,
            )
            failed.append(
                FailedMechanicalFix(
                    finding=finding,
                    command=command_entry.name,
                    changed_files=actual_changed,
                    reason="fix changed unreported paths",
                    trust_notifications=notifications,
                )
            )
            continue

        preexisting_changed = _preexisting_overlaps(changed_files, pre_status)
        if preexisting_changed:
            _revert_files(root, actual_changed, pre_status=pre_status)
            notifications = _record_failure(
                ledger,
                str(finding.get("loop") or command_entry.loop_name),
                command_entry.name,
            )
            failed.append(
                FailedMechanicalFix(
                    finding=finding,
                    command=command_entry.name,
                    changed_files=actual_changed,
                    reason="fix touched pre-existing changes",
                    trust_notifications=notifications,
                )
            )
            continue

        if not getattr(fix_result, "success", False):
            _revert_files(root, actual_changed, pre_status=pre_status)
            notifications = _record_failure(
                ledger,
                str(finding.get("loop") or command_entry.loop_name),
                command_entry.name,
            )
            failed.append(
                FailedMechanicalFix(
                    finding=finding,
                    command=command_entry.name,
                    changed_files=changed_files,
                    reason=getattr(fix_result, "summary", "") or "fix failed",
                    trust_notifications=notifications,
                )
            )
            continue

        if not changed_files:
            continue

        command_verify = _verify_command(command_entry, root, verify_command)
        verified = run_verify(
            verify_command=command_verify,
            ctx=ctx,
            changed_files=changed_files,
            finding=finding,
            command_entry=command_entry,
        )
        if not verified:
            _revert_files(root, actual_changed, pre_status=pre_status)
            notifications = _record_failure(
                ledger,
                str(finding.get("loop") or command_entry.loop_name),
                command_entry.name,
            )
            failed.append(
                FailedMechanicalFix(
                    finding=finding,
                    command=command_entry.name,
                    changed_files=changed_files,
                    reason="verify failed",
                    trust_notifications=notifications,
                )
            )
            continue

        # If the command operates on files outside the project git repo (e.g. the
        # external vault), skip the project-side git commit.  The module declares
        # this by setting ``external_commit = True`` at module level.  The fix is
        # still recorded as applied and the trust ledger updated normally.
        if getattr(command_entry.module, "external_commit", False):
            commit = ""
        else:
            commit = run_commit(
                project_root=root,
                changed_files=changed_files,
                message=_commit_message(command_entry, finding),
                finding=finding,
                command_entry=command_entry,
            )
        loop_name = str(finding.get("loop") or command_entry.loop_name)
        notifications = _record_verified_commit_success(
            ledger,
            loop_name,
            command_entry.name,
            commit_hash=commit,
            difficulty=difficulty,
        )
        applied.append(
            AppliedMechanicalFix(
                finding=finding,
                command=command_entry.name,
                changed_files=changed_files,
                commit=commit,
                trust_notifications=notifications,
            )
        )

    return MechanicalFixResult(applied=applied, deferred=deferred, failed=failed)


def _resolve_commands(commands: Iterable[Any] | Mapping[str, Any]) -> dict[str, FixCommand]:
    raw_commands: Iterable[Any]
    if isinstance(commands, Mapping):
        raw_commands = [
            command if _looks_like_entry(command) else _mapping_entry(name, command)
            for name, command in commands.items()
        ]
    else:
        raw_commands = commands

    entries: dict[str, FixCommand] = {}
    for command in raw_commands:
        entry = _coerce_command_entry(command)
        entries[entry.name] = entry
    return entries


def _coerce_command_entry(command: Any) -> FixCommand:
    if _looks_like_entry(command):
        module = command.module
        name = str(getattr(command, "name", "") or getattr(module, "name", ""))
        loop_name = str(getattr(command, "loop_name", "") or "")
        config = getattr(command, "config", {}) or {}
        tier = int(getattr(command, "tier", 0) or 0)
        return FixCommand(name=name, module=module, loop_name=loop_name, config=dict(config), tier=tier)

    name = str(getattr(command, "name", "") or getattr(command, "__name__", "auto-command"))
    return FixCommand(name=name, module=command, loop_name="", config={})


def _looks_like_entry(command: Any) -> bool:
    return hasattr(command, "module") and callable(getattr(command.module, "fix", None))


def _mapping_entry(name: str, module: Any) -> FixCommand:
    return FixCommand(name=str(name), module=module, loop_name="", config={})


def _finding_band(finding: Mapping[str, Any]) -> str:
    explicit = finding.get("finding_band") or finding.get("band")
    if explicit:
        return _normalize_band(str(explicit))
    return classify_finding_band(dict(finding))


def _normalize_band(value: str) -> str:
    normalized = value.strip().lower().replace("_", "-")
    if normalized in {"localsemantic", "local-semantic"}:
        return LOCAL_SEMANTIC
    if normalized == STRUCTURAL:
        return STRUCTURAL
    return MECHANICAL if normalized == MECHANICAL else normalized


def _changed_files(fix_result: Any) -> list[str]:
    return [str(path) for path in (getattr(fix_result, "changes", None) or [])]


def _verify_command(
    command_entry: FixCommand,
    project_root: Path,
    explicit_verify_command: Any | None,
) -> Any:
    if explicit_verify_command is not None:
        return explicit_verify_command
    command_verify = getattr(command_entry, "verify_command", None) or getattr(
        command_entry.module, "verify_command", None
    )
    if command_verify:
        return command_verify
    return _project_verify_command(project_root)


def _default_verify_runner(
    *,
    verify_command: Any,
    ctx: OpsContext,
    changed_files: list[str],
    finding: dict[str, Any],
    command_entry: FixCommand,
) -> bool:
    del changed_files, finding, command_entry
    if not verify_command:
        return True
    if callable(verify_command):
        return bool(verify_command(ctx=ctx))
    if isinstance(verify_command, (list, tuple)):
        result = subprocess.run(
            [str(part) for part in verify_command],
            cwd=ctx.project_root,
            text=True,
            capture_output=True,
            check=False,
        )
        return result.returncode == 0
    result = subprocess.run(
        shlex.split(str(verify_command)),
        cwd=ctx.project_root,
        text=True,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def _default_commit_runner(
    *,
    project_root: Path,
    changed_files: list[str],
    message: str,
    finding: dict[str, Any],
    command_entry: FixCommand,
) -> str:
    del finding, command_entry
    subprocess.run(
        ["git", "add", "--", *changed_files],
        cwd=project_root,
        check=True,
        text=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", message, "--only", "--", *changed_files],
        cwd=project_root,
        check=True,
        text=True,
        capture_output=True,
    )
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=project_root,
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


def _revert_files(
    project_root: Path,
    changed_files: list[str],
    *,
    pre_status: Mapping[str, str],
) -> None:
    for changed_file in changed_files:
        if _preexisting_overlaps([changed_file], pre_status):
            continue
        path = project_root / changed_file
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", changed_file],
            cwd=project_root,
            text=True,
            capture_output=True,
            check=False,
        )
        if tracked.returncode == 0:
            subprocess.run(
                ["git", "restore", "--staged", "--worktree", "--", changed_file],
                cwd=project_root,
                text=True,
                capture_output=True,
                check=False,
            )
        elif path.exists():
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()


def _project_verify_command(project_root: Path) -> Any:
    config_path = project_root / "config" / "system" / "adaptive_loops.yaml"
    if not config_path.is_file():
        return None
    loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        return None
    command = loaded.get("engine", {}).get("verify_command")
    return command or None


def _parse_porcelain_paths(output: str) -> dict[str, str]:
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
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=project_root,
        check=True,
        text=True,
        capture_output=True,
    )
    return _parse_porcelain_paths(result.stdout)


def _paths_overlap(left: str, right: str) -> bool:
    left_clean = left.rstrip("/")
    right_clean = right.rstrip("/")
    return (
        left_clean == right_clean
        or left_clean.startswith(f"{right_clean}/")
        or right_clean.startswith(f"{left_clean}/")
    )


def _preexisting_overlaps(paths: Iterable[str], pre_status: Mapping[str, str]) -> list[str]:
    overlaps: list[str] = []
    for path in paths:
        path_text = str(path)
        if any(_paths_overlap(path_text, dirty_path) for dirty_path in pre_status):
            overlaps.append(path_text)
    return overlaps


def _snapshot_dirty_paths(
    project_root: Path,
    pre_status: Mapping[str, str],
) -> dict[str, DirtyPathSnapshot]:
    snapshots: dict[str, DirtyPathSnapshot] = {}
    for path in pre_status:
        abs_path = project_root / path
        if abs_path.is_file():
            snapshots[path] = DirtyPathSnapshot(path=path, data=abs_path.read_bytes())
        elif not abs_path.exists():
            snapshots[path] = DirtyPathSnapshot(path=path, data=None)
    return snapshots


def _changed_dirty_paths(
    project_root: Path,
    snapshots: Mapping[str, DirtyPathSnapshot],
) -> list[str]:
    changed: list[str] = []
    for path, snapshot in snapshots.items():
        abs_path = project_root / path
        if snapshot.data is None:
            if abs_path.exists():
                changed.append(path)
            continue
        if not abs_path.is_file() or abs_path.read_bytes() != snapshot.data:
            changed.append(path)
    return changed


def _restore_dirty_snapshots(
    project_root: Path,
    snapshots: Mapping[str, DirtyPathSnapshot],
    paths: Iterable[str],
) -> None:
    for path in paths:
        snapshot = snapshots.get(path)
        if snapshot is None:
            continue
        abs_path = project_root / path
        if snapshot.data is None:
            if abs_path.is_dir():
                shutil.rmtree(abs_path)
            elif abs_path.exists():
                abs_path.unlink()
            continue
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_bytes(snapshot.data)


def _actual_changed_files(project_root: Path, pre_status: Mapping[str, str]) -> list[str]:
    post_status = _status_paths(project_root)
    changed = [
        path for path, status in post_status.items()
        if pre_status.get(path) != status
    ]
    return sorted(changed)


def _unreported_changes(actual_changed: Iterable[str], reported_changed: Iterable[str]) -> list[str]:
    reported = list(reported_changed)
    unreported: list[str] = []
    for actual in actual_changed:
        if not any(_paths_overlap(actual, reported_path) for reported_path in reported):
            unreported.append(actual)
    return unreported


def _finding_paths(finding: Mapping[str, Any]) -> list[str]:
    paths: list[str] = []
    for key in ("primary_file", "path", "file_path", "file"):
        value = finding.get(key)
        if value:
            paths.append(str(value))
    return paths


def _normalize_changed_files(project_root: Path, changed_files: Iterable[str]) -> list[str]:
    normalized: list[str] = []
    root = project_root.resolve()
    for changed_file in changed_files:
        path = Path(changed_file)
        candidate = path if path.is_absolute() else root / path
        try:
            relative = candidate.resolve().relative_to(root)
        except ValueError as exc:
            raise ValueError(f"changed file escapes project root: {changed_file}") from exc
        relative_text = relative.as_posix()
        if not relative_text or relative_text == ".":
            raise ValueError("changed file path is empty")
        normalized.append(relative_text)
    return normalized


def _record_failure(ledger: TrustLedger, loop_name: str, command_name: str) -> list[str]:
    try:
        return ledger.record_failure(loop_name, command_name)
    except KeyError:
        return []


def _record_verified_commit_success(
    ledger: TrustLedger,
    loop_name: str,
    command_name: str,
    *,
    commit_hash: str,
    difficulty: int,
) -> list[str]:
    notifications = ledger.record_success(loop_name, command_name)
    loop_state = ledger.get_loop_state(loop_name)
    category = loop_state.categories.get(command_name)
    if category is None:
        return notifications

    category.total_fixes += 1
    if commit_hash:
        category.total_commits += 1
        commit_credit = (1.0 - category.commit_trust) * COMMIT_TRUST_INCREMENT
        category.commit_trust = min(1.0, category.commit_trust + commit_credit)
        category.last_commit_trust_credit = commit_credit
        category.max_committed_difficulty = max(category.max_committed_difficulty, difficulty)
        category.pending_commit_verification = True

    cap = category.max_committed_difficulty + DIFFICULTY_COMMIT_GATE_BUFFER
    if category.difficulty > cap:
        category.difficulty = cap
    ledger.save()
    return notifications


def _commit_message(command_entry: FixCommand, finding: Mapping[str, Any]) -> str:
    detail = str(finding.get("detail") or "mechanical finding").strip()
    if len(detail) > 72:
        detail = detail[:69].rstrip() + "..."
    return f"ADR-755 mechanical fix: {command_entry.name} - {detail}"


def _build_trust_config(commands: Mapping[str, FixCommand]) -> dict[str, Any]:
    categories = {
        name: {"enabled": True, "trust": 0.0, "tier": entry.tier}
        for name, entry in commands.items()
    }
    loop_name = next((entry.loop_name for entry in commands.values() if entry.loop_name), "routine")
    return {
        "loops": {
            loop_name: {
                "enabled": True,
                "trigger": "manual",
                "budget": max(1, len(categories)),
                "budget_growth_rate": 1,
                "categories": categories,
            }
        }
    }
