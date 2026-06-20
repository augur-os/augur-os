#!/usr/bin/env python3
"""Deferred worktree purge queue (hooks-driven, no daemon).

A ``/dev-merge`` that completes a clean, verified merge from *inside* a worktree
cannot remove that worktree synchronously: the live session — and frequently a
second client such as Cowork — still owns the path, and ``worktree_guard``
correctly refuses to delete the ground a live AI/client stands on. The merge
therefore used to "defer and report" with nothing that ever came back to finish
the job, so the worktree lingered until a human purged it from a clean session.

This module closes that gap with a file-based queue:

  - ``enqueue`` records a pending purge once the branch is proven fully merged
    into its target (no-loss precondition).
  - ``sweep`` is called from the ``session-start`` (and best-effort
    ``session-end``) hook. It reaps every queued worktree the moment all of its
    live AI/client owners have released the path, re-verifying the no-loss
    preconditions immediately before deletion.

The queue lives in the shared runtime dir, so a worktree enqueued from worktree
A is reaped by a later session started anywhere (main checkout or worktree B).

Commands::

    enqueue --path <wt> [--branch B] [--target main]
    sweep [--from-hook]
    list [--json]
    remove --name <name>
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

# Make ``src.config.paths`` importable regardless of cwd/PYTHONPATH: the hook
# runner and a manual ``/dev-merge`` invocation both reach this script, and only
# one of them sets PYTHONPATH. parents[5] is the repo root
# (scripts → platform-admin → skills → capabilities → project-brain → <root>).
_PROJECT_ROOT = Path(__file__).resolve().parents[5]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
# Sibling-script imports (worktree_guard lives in this same scripts dir).
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from worktree_guard import active_ai_processes_for_path  # noqa: E402


# ──────────────────────────────────────────────────────────────────────────────
# Queue location + logging
# ──────────────────────────────────────────────────────────────────────────────


def queue_dir() -> Path:
    """Directory holding one ``<name>.json`` record per pending purge.

    ``AUGUR_WORKTREE_PURGE_DIR`` overrides the location (used by tests). Falls
    back to a temp path if the runtime dir cannot be resolved so the hook never
    crashes on an unexpected environment.
    """
    override = os.environ.get("AUGUR_WORKTREE_PURGE_DIR")
    if override:
        path = Path(override)
    else:
        try:
            from src.config.paths import get_runtime_dir

            path = Path(get_runtime_dir()) / "worktree_purge_queue"
        except Exception:
            path = Path.home() / ".cache" / "augur" / "worktree_purge_queue"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _log(message: str) -> None:
    try:
        from src.config.paths import get_logs_dir

        log_dir = Path(get_logs_dir())
    except Exception:
        log_dir = queue_dir()
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with (log_dir / "worktree-purge.log").open("a", encoding="utf-8") as handle:
            handle.write(f"{stamp} {message}\n")
    except Exception:
        pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ──────────────────────────────────────────────────────────────────────────────
# Record model + persistence
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class PurgeRecord:
    name: str
    path: str
    branch: str
    target: str
    merged_sha: str = ""
    enqueued_at: str = ""
    requested_by: str = ""
    attempts: int = 0
    last_attempt_at: str = ""
    last_status: str = "pending"
    last_reason: str = ""


def _record_file(name: str) -> Path:
    safe = name.replace("/", "_")
    return queue_dir() / f"{safe}.json"


def save_record(record: PurgeRecord) -> None:
    _record_file(record.name).write_text(
        json.dumps(asdict(record), indent=2) + "\n", encoding="utf-8"
    )


def load_records() -> list[PurgeRecord]:
    records: list[PurgeRecord] = []
    for file in sorted(queue_dir().glob("*.json")):
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
            records.append(PurgeRecord(**{k: data.get(k) for k in PurgeRecord.__annotations__ if k in data}))
        except Exception:
            _log(f"skip unreadable record {file.name}")
    return records


def remove_record(name: str) -> None:
    file = _record_file(name)
    if file.exists():
        file.unlink()


# ──────────────────────────────────────────────────────────────────────────────
# Git / worktree helpers (module-level so tests can monkeypatch them)
# ──────────────────────────────────────────────────────────────────────────────


def _git(repo: str, *args: str) -> tuple[int, str]:
    proc = subprocess.run(
        ["git", "-C", repo, *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return proc.returncode, (proc.stdout or "").strip()


def main_checkout_for(path: str) -> str:
    """Return the main checkout that owns the worktree at ``path``."""
    code, out = _git(path, "worktree", "list", "--porcelain")
    if code == 0:
        for line in out.splitlines():
            if line.startswith("worktree "):
                return line.removeprefix("worktree ").strip()
    return path


def worktree_exists(path: str) -> bool:
    return Path(path).is_dir()


def branch_exists(main: str, branch: str) -> bool:
    code, _ = _git(main, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}")
    return code == 0


def _resolve_merge_target(main: str, target: str) -> str | None:
    """Resolve the no-loss comparison ref, most-specific first:
      1. local ``<target>`` branch (normal developer checkout);
      2. its remote-tracking ref ``origin/<target>`` (fresh clone where main was
         never checked out locally);
      3. the main checkout's own ``HEAD`` — last resort for a detached PR-merge
         checkout (CI with fetch-depth 1) that has NEITHER a local nor a
         remote-tracking ``main``. There, HEAD is the effective main, so a branch
         with no commits beyond HEAD is no-loss. This branch only triggers when
         both (1) and (2) are absent — which never happens in a normal checkout
         (main always exists), so it cannot mis-compare a feature-branch HEAD.
    Always returns a resolvable ref; unmerged branches still produce commits in
    ``<ref>..<branch>`` and are correctly refused."""
    if _git(main, "rev-parse", "--verify", "--quiet", f"refs/heads/{target}")[0] == 0:
        return target
    if _git(main, "rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{target}")[0] == 0:
        return f"origin/{target}"
    if _git(main, "rev-parse", "--verify", "--quiet", "HEAD")[0] == 0:
        return "HEAD"
    return None


def branch_merged(main: str, target: str, branch: str) -> bool:
    """True when ``branch`` has no commits missing from ``target`` (no-loss)."""
    resolved = _resolve_merge_target(main, target)
    if resolved is None:
        return False
    code, out = _git(main, "log", "--oneline", f"{resolved}..{branch}")
    if code != 0:
        return False
    return out.strip() == ""


def worktree_dirty(path: str) -> bool:
    """True when the worktree has uncommitted changes worth preserving."""
    code, out = _git(path, "status", "--porcelain")
    if code != 0:
        # Cannot determine — treat as dirty (refuse to purge) to be safe.
        return True
    return out.strip() != ""


def active_owners(path: str) -> list:
    return active_ai_processes_for_path(Path(path))


def do_purge(main: str, path: str) -> tuple[bool, str]:
    """Run the canonical worktree cleanup (unregister + remove + codex repair + branch -D)."""
    script = Path(main) / "scripts" / "worktree-launch.sh"
    if not script.exists():
        return False, f"worktree-launch.sh not found at {script}"
    proc = subprocess.run(
        ["bash", str(script), "cleanup", path],
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )
    ok = proc.returncode == 0 and not Path(path).is_dir()
    return ok, (proc.stdout or "") + (proc.stderr or "")


# ──────────────────────────────────────────────────────────────────────────────
# Decision logic (pure, given the helpers above)
# ──────────────────────────────────────────────────────────────────────────────

# Decisions: "purge" | "gone" | "skip_owned" | "skip_dirty" | "skip_unmerged"


def purge_decision(record: PurgeRecord) -> tuple[str, str]:
    """Decide what to do with a queued record right now.

    Order matters: cheap "already gone" checks first, then the no-loss safety
    gates (merged + clean), then the ownership gate last (the only one that
    flips from blocked to ready over time).
    """
    if not worktree_exists(record.path):
        return "gone", "worktree directory no longer exists"

    main = main_checkout_for(record.path)

    if not branch_exists(main, record.branch):
        # Branch already deleted but dir remains — safe to finish removal.
        if not active_owners(record.path):
            return "purge", "branch already merged/deleted; finishing worktree removal"
        return "skip_owned", "branch gone but path still owned by a live client"

    if not branch_merged(main, record.target, record.branch):
        return "skip_unmerged", f"{record.branch} has commits not in {record.target}; not safe to purge"

    if worktree_dirty(record.path):
        return "skip_dirty", "worktree has uncommitted changes; not safe to purge"

    owners = active_owners(record.path)
    if owners:
        pids = ",".join(str(o.pid) for o in owners)
        return "skip_owned", f"path still owned by live client pids {pids}"

    return "purge", "merged, clean, and no live owners"


# ──────────────────────────────────────────────────────────────────────────────
# Commands
# ──────────────────────────────────────────────────────────────────────────────


def cmd_enqueue(args: argparse.Namespace) -> int:
    path = str(Path(args.path).expanduser().resolve())
    if not worktree_exists(path):
        print(f"enqueue refused: not a directory: {path}", file=sys.stderr)
        return 2

    main = main_checkout_for(path)
    code, branch = (0, args.branch) if args.branch else _git(path, "rev-parse", "--abbrev-ref", "HEAD")
    branch = (branch or "").strip()
    if not branch or branch == "HEAD":
        print("enqueue refused: could not resolve worktree branch", file=sys.stderr)
        return 2

    target = args.target
    if not branch_merged(main, target, branch):
        print(
            f"enqueue refused: {branch} is not fully merged into {target} — "
            "refusing to queue a worktree that could lose commits",
            file=sys.stderr,
        )
        return 3

    _, sha = _git(main, "rev-parse", "--short", branch)
    record = PurgeRecord(
        name=Path(path).name,
        path=path,
        branch=branch,
        target=target,
        merged_sha=sha,
        enqueued_at=_now(),
        requested_by=args.requested_by,
        last_status="pending",
        last_reason="enqueued",
    )
    save_record(record)
    _log(f"enqueued {record.name} ({branch} -> {target}, merged {sha})")
    print(
        f"Queued worktree '{record.name}' for automatic purge once every client "
        f"releases it (branch {branch} verified merged into {target})."
    )
    return 0


def cmd_sweep(args: argparse.Namespace) -> int:
    records = load_records()
    if not records:
        if not args.from_hook:
            print("worktree purge queue is empty")
        return 0

    purged: list[str] = []
    for record in records:
        try:
            decision, reason = purge_decision(record)
        except Exception as exc:  # never let a sweep crash a hook
            _log(f"decision error for {record.name}: {exc}")
            continue

        record.attempts += 1
        record.last_attempt_at = _now()
        record.last_status = decision
        record.last_reason = reason

        if decision == "gone":
            remove_record(record.name)
            _log(f"reaped {record.name}: {reason}")
            purged.append(record.name)
            continue

        if decision == "purge":
            main = main_checkout_for(record.path)
            ok, output = do_purge(main, record.path)
            if ok:
                remove_record(record.name)
                _log(f"purged {record.name}: {reason}")
                purged.append(record.name)
            else:
                record.last_status = "error"
                record.last_reason = f"purge failed: {output.strip()[:300]}"
                save_record(record)
                _log(f"purge FAILED for {record.name}: {output.strip()[:300]}")
            continue

        # skip_* — keep the record, persist the latest status for visibility.
        save_record(record)
        if not args.from_hook:
            print(f"skip {record.name}: {reason}")

    if purged and not args.from_hook:
        print(f"auto-purged: {', '.join(purged)}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    records = load_records()
    if args.json:
        print(json.dumps([asdict(r) for r in records], indent=2))
        return 0
    if not records:
        print("worktree purge queue is empty")
        return 0
    for r in records:
        print(f"{r.name:40s} {r.last_status:14s} {r.branch} -> {r.target}  ({r.last_reason})")
    return 0


def cmd_remove(args: argparse.Namespace) -> int:
    remove_record(args.name)
    print(f"removed {args.name} from purge queue")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_enq = sub.add_parser("enqueue", help="Queue a merged worktree for deferred purge")
    p_enq.add_argument("--path", required=True, help="Worktree path")
    p_enq.add_argument("--branch", default="", help="Branch (default: the worktree's HEAD branch)")
    p_enq.add_argument("--target", default="main", help="Branch the work was merged into")
    p_enq.add_argument("--requested-by", dest="requested_by", default="dev-merge")
    p_enq.set_defaults(func=cmd_enqueue)

    p_sweep = sub.add_parser("sweep", help="Reap any queued worktree that is now free")
    p_sweep.add_argument("--from-hook", action="store_true", help="Quiet output for hook context")
    p_sweep.set_defaults(func=cmd_sweep)

    p_list = sub.add_parser("list", help="Show the purge queue")
    p_list.add_argument("--json", action="store_true")
    p_list.set_defaults(func=cmd_list)

    p_rm = sub.add_parser("remove", help="Drop a record from the queue")
    p_rm.add_argument("--name", required=True)
    p_rm.set_defaults(func=cmd_remove)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
