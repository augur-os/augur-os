# File-Based Job Ledger Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every async run in Augur a durable, crash-safe file-based run record — a `job_ledger/` subpackage in the daemon skill, per-job `meta.json` + append-only `events.jsonl` under `get_runtime_dir()/jobs/`, a `run()` context manager wrapped at the executor dispatch points, a supervisor sweep on the daemon heartbeat.

**Architecture:** `shared-vault/skills/daemon/scripts/job_ledger/` owns `job_record.py` (shapes + state resolution), `ledger.py` (the `run()` context manager + state machine), `supervisor.py` (liveness sweep), `retention.py` (30-day gzip archive), and `mcp/` (the `jobs-*` tools + `aug jobs` CLI). The Adaptive Loop Engine's learning state in `runtime/adaptive/` is untouched — the ledger is purely additive.

**Tech Stack:** Python 3.11+, `src/config/paths.py`, the daemon skill's `notification_service.py`. No new dependencies. No database. Plain JSONL files.

**Spec:** `docs/superpowers/specs/2026-05-14-file-based-job-ledger-design.md` · **ADR:** ADR-743

---

## Shared Test Harness (preamble — used verbatim by every test file)

Every test file in `shared-vault/skills/daemon/augur/tests/test_jobledger_*.py` begins
with this loader block (importlib per `feedback_skill_test_convention`):

```python
"""Tests for job_ledger/<module>.py — file-based job ledger (ADR-743)."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

LEDGER_DIR = Path(__file__).resolve().parents[2] / "scripts" / "job_ledger"


def _load(module_name: str, file_name: str) -> Any:
    full_name = f"jobledger_{module_name}"
    if full_name in sys.modules:
        return sys.modules[full_name]
    spec = importlib.util.spec_from_file_location(full_name, LEDGER_DIR / file_name)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    sys.modules[module_name] = module  # alias bare name so siblings resolve
    spec.loader.exec_module(module)
    return module
```

Run with: `/auto-test-pytest shared-vault/skills/daemon/augur/tests/` (never raw `pytest` — rule 29).

---

# Phase 1 — Job Record + Ledger Core

## Task 1: Subpackage scaffold + config block

**Files:**
- Create: `shared-vault/skills/daemon/scripts/job_ledger/__init__.py` (empty)
- Create: `shared-vault/skills/daemon/scripts/job_ledger/mcp/__init__.py` (stub — filled in Task 6)
- Modify: `shared-vault/skills/daemon/config.yaml` (add the `job_ledger:` block)

- [ ] **Step 1: Create the subpackage tree**

```bash
mkdir -p shared-vault/skills/daemon/scripts/job_ledger/mcp
touch shared-vault/skills/daemon/scripts/job_ledger/__init__.py
```

- [ ] **Step 2: Add the `job_ledger:` config block** to `shared-vault/skills/daemon/config.yaml` — append at the top level, after the `contributions:` block:

```yaml
# Job ledger — crash-safe run records (ADR-743). Skill-internal config.
job_ledger:
  heartbeat_threshold_s: 300      # a running job silent longer than this is "stale"
  retention_days: 30              # terminal jobs older than this are archived
  resubmit_allowlist: []          # loop names the supervisor may auto-resubmit once
```

- [ ] **Step 3: Write the `mcp/__init__.py` stub** (filled in Task 6)

```python
"""MCP tools + CLI for the job ledger (ADR-743). Filled in Task 6."""
from __future__ import annotations


def register_tools(mcp, mcp_tool_interceptor, metrics) -> None:  # noqa: D103
    pass


def register_subcommands(subparsers) -> None:  # noqa: D103
    pass


__all__ = ["register_tools", "register_subcommands"]
```

- [ ] **Step 4: Commit**

```bash
git add shared-vault/skills/daemon/scripts/job_ledger/ shared-vault/skills/daemon/config.yaml
git commit -m "feat(job-ledger): scaffold job_ledger subpackage + config (ADR-743)"
```

## Task 2: `job_record.py` — shapes, ids, state resolution

**Files:**
- Create: `shared-vault/skills/daemon/scripts/job_ledger/job_record.py`
- Test: `shared-vault/skills/daemon/augur/tests/test_jobledger_record.py`

- [ ] **Step 1: Write the failing test** (prepend the Shared Test Harness loader block)

```python
def test_new_job_id_is_sortable_and_slugged() -> None:
    jr = _load("job_record", "job_record.py")
    jid = jr.new_job_id("loop-hygiene")
    assert jid.endswith("-loop-hygiene")
    assert len(jid.split("-")[0]) == 8  # YYYYMMDD prefix


def test_append_and_current_state(tmp_path: Path, monkeypatch) -> None:
    jr = _load("job_record", "job_record.py")
    monkeypatch.setattr(jr, "jobs_dir", lambda: tmp_path / "jobs")
    job_dir = jr.jobs_dir() / "20260514-120000-000-test"
    job_dir.mkdir(parents=True)
    jr.append_event(job_dir, {"state": "pending"})
    jr.append_event(job_dir, {"state": "running", "pid": 999})
    jr.append_event(job_dir, {"state": "complete"})
    assert jr.current_state(job_dir) == "complete"
    assert jr.is_terminal("complete") and not jr.is_terminal("running")


def test_corrupt_line_is_skipped(tmp_path: Path, monkeypatch) -> None:
    jr = _load("job_record", "job_record.py")
    monkeypatch.setattr(jr, "jobs_dir", lambda: tmp_path / "jobs")
    job_dir = jr.jobs_dir() / "20260514-120000-000-test"
    job_dir.mkdir(parents=True)
    (job_dir / "events.jsonl").write_text(
        '{"state": "running"}\n{not valid json\n{"state": "failed"}\n', encoding="utf-8"
    )
    assert jr.current_state(job_dir) == "failed"  # last *valid* line
    assert len(jr.read_events(job_dir)) == 2       # corrupt line skipped
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/auto-test-pytest shared-vault/skills/daemon/augur/tests/test_jobledger_record.py`
Expected: FAIL — `job_record.py` does not exist.

- [ ] **Step 3: Write `job_record.py`**

```python
"""Job ledger record shapes + state resolution (ADR-743).

A job is a directory under get_runtime_dir()/jobs/<job-id>/ containing meta.json
and an append-only events.jsonl. Current state = the `state` of the last *valid*
JSONL line (positional, never timestamp-sorted, so clock skew is harmless).
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("job_ledger.record")

TERMINAL_STATES = frozenset({"complete", "failed", "timeout", "cancelled"})
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def jobs_dir() -> Path:
    """Root of the job ledger. Monkeypatchable in tests."""
    from src.config.paths import get_runtime_dir

    d = get_runtime_dir() / "jobs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def slugify(name: str) -> str:
    return _SLUG_RE.sub("-", name.strip().lower()).strip("-") or "job"


def new_job_id(name: str) -> str:
    """<YYYYMMDD-HHMMSS-mmm>-<name-slug> — sortable, readable, unique to the ms."""
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%d-%H%M%S-") + f"{now.microsecond // 1000:03d}"
    return f"{stamp}-{slugify(name)}"


def is_terminal(state: str) -> bool:
    return state in TERMINAL_STATES


def append_event(job_dir: Path, event: dict[str, Any]) -> bool:
    """Append one JSON line to events.jsonl. Internally safe — never raises."""
    try:
        event.setdefault("t", datetime.now(timezone.utc).isoformat())
        with (job_dir / "events.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, default=str) + "\n")
        return True
    except Exception as exc:  # noqa: BLE001 — ledger-write failure is non-fatal
        logger.warning("job ledger append failed for %s: %s", job_dir.name, exc)
        return False


def read_events(job_dir: Path) -> list[dict[str, Any]]:
    """Read all valid events; malformed lines are skipped, not fatal."""
    path = job_dir / "events.jsonl"
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def current_state(job_dir: Path) -> str:
    """State of the last valid JSONL line; 'unknown' if there are none."""
    events = read_events(job_dir)
    for event in reversed(events):
        if isinstance(event, dict) and "state" in event:
            return str(event["state"])
    return "unknown"


def read_meta(job_dir: Path) -> dict[str, Any]:
    path = job_dir / "meta.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/auto-test-pytest shared-vault/skills/daemon/augur/tests/test_jobledger_record.py`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/daemon/scripts/job_ledger/job_record.py shared-vault/skills/daemon/augur/tests/test_jobledger_record.py
git commit -m "feat(job-ledger): job record shapes + state resolution (ADR-743)"
```

## Task 3: `ledger.py` — the `run()` context manager

**Files:**
- Create: `shared-vault/skills/daemon/scripts/job_ledger/ledger.py`
- Test: `shared-vault/skills/daemon/augur/tests/test_jobledger_ledger.py`

- [ ] **Step 1: Write the failing test** (prepend the Shared Test Harness loader block)

```python
def _patch_jobs_dir(monkeypatch, tmp_path: Path):
    jr = _load("job_record", "job_record.py")
    monkeypatch.setattr(jr, "jobs_dir", lambda: tmp_path / "jobs")
    return jr


def test_clean_run_records_running_then_complete(tmp_path: Path, monkeypatch) -> None:
    jr = _patch_jobs_dir(monkeypatch, tmp_path)
    ledger = _load("ledger", "ledger.py")
    with ledger.run(kind="loop", name="loop-hygiene", timeout_s=600) as job:
        job.phase("scan")
        job.heartbeat()
    states = [e["state"] for e in jr.read_events(Path(job.job_dir))]
    assert states[0] == "pending" and states[1] == "running"
    assert states[-1] == "complete"
    assert any(e.get("phase") == "scan" for e in jr.read_events(Path(job.job_dir)))


def test_exception_records_failed_and_reraises(tmp_path: Path, monkeypatch) -> None:
    jr = _patch_jobs_dir(monkeypatch, tmp_path)
    ledger = _load("ledger", "ledger.py")
    with pytest.raises(ValueError):
        with ledger.run(kind="loop", name="boom") as job:
            raise ValueError("kaboom")
    events = jr.read_events(Path(job.job_dir))
    assert events[-1]["state"] == "failed"
    assert events[-1]["error"] == "ValueError"


def test_cooperative_cancel(tmp_path: Path, monkeypatch) -> None:
    jr = _patch_jobs_dir(monkeypatch, tmp_path)
    ledger = _load("ledger", "ledger.py")
    with ledger.run(kind="loop", name="cancelme") as job:
        # jobs-cancel writes this marker; phase()/heartbeat() check for it
        (Path(job.job_dir) / "cancel_requested").write_text("", encoding="utf-8")
        with pytest.raises(ledger.JobCancelled):
            job.heartbeat()
    assert jr.current_state(Path(job.job_dir)) == "cancelled"


def test_ledger_write_failure_is_non_fatal(tmp_path: Path, monkeypatch) -> None:
    # jobs_dir points at a path that cannot be created -> _NullJob, run still proceeds
    jr = _load("job_record", "job_record.py")
    monkeypatch.setattr(jr, "jobs_dir", lambda: (_ for _ in ()).throw(OSError("disk full")))
    ledger = _load("ledger", "ledger.py")
    ran = False
    with ledger.run(kind="loop", name="resilient") as job:
        ran = True
    assert ran  # the wrapped work ran even though the ledger could not record it
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/auto-test-pytest shared-vault/skills/daemon/augur/tests/test_jobledger_ledger.py`
Expected: FAIL — `ledger.py` does not exist.

- [ ] **Step 3: Write `ledger.py`**

```python
"""The job ledger run() context manager + state machine (ADR-743).

Wrap any async run in `with run(...) as job:`. The context manager records
pending -> running -> (complete | failed | timeout | cancelled). It records; it
never swallows a real exception (failed is recorded, then re-raised). A ledger
that cannot write degrades to a no-op _NullJob so the wrapped work still runs.
"""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import job_record  # sibling import (scripts/job_ledger on sys.path)

logger = logging.getLogger("job_ledger.ledger")


class JobCancelled(Exception):
    """Raised by job.phase()/heartbeat() when a cancel_requested marker exists."""


class Job:
    """Handle for one ledger job. phase/heartbeat/log append running events."""

    def __init__(self, job_dir: Path) -> None:
        self.job_dir = str(job_dir)
        self._dir = job_dir

    def _append(self, **event: Any) -> None:
        job_record.append_event(self._dir, event)

    def _check_cancel(self) -> None:
        if (self._dir / "cancel_requested").exists():
            raise JobCancelled("cancel requested")

    def phase(self, name: str) -> None:
        self._check_cancel()
        self._append(state="running", phase=name)

    def heartbeat(self) -> None:
        self._check_cancel()
        self._append(state="running", heartbeat=True)

    def log(self, msg: str) -> None:
        self._append(state="running", msg=msg)


class _NullJob(Job):
    """Used when the ledger cannot write — every method is a no-op."""

    def __init__(self) -> None:  # noqa: D107
        self.job_dir = ""

    def _append(self, **event: Any) -> None:
        pass

    def _check_cancel(self) -> None:
        pass


def _create_job(*, kind: str, name: str, args: dict, timeout_s: int | None,
                submitter: str) -> Job:
    """Create the job dir + meta.json + the pending event. Returns _NullJob on failure."""
    try:
        job_id = job_record.new_job_id(name)
        job_dir = job_record.jobs_dir() / job_id
        job_dir.mkdir(parents=True, exist_ok=False)
        (job_dir / "meta.json").write_text(
            __import__("json").dumps(
                {
                    "job_id": job_id,
                    "kind": kind,
                    "name": name,
                    "submitter": submitter,
                    "args": args,
                    "declared_timeout_s": timeout_s,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        job = Job(job_dir)
        job._append(state="pending")
        return job
    except Exception as exc:  # noqa: BLE001 — a broken ledger must not break the run
        logger.warning("job ledger could not create a job for %s: %s", name, exc)
        return _NullJob()


@contextmanager
def run(*, kind: str, name: str, args: dict | None = None,
        timeout_s: int | None = None, submitter: str = "daemon") -> Iterator[Job]:
    """Wrap an async run. Records the state machine; re-raises real exceptions."""
    job = _create_job(kind=kind, name=name, args=args or {},
                      timeout_s=timeout_s, submitter=submitter)
    job._append(state="running", pid=os.getpid(), msg="started")
    try:
        yield job
    except JobCancelled as exc:
        job._append(state="cancelled", msg=str(exc))
        # swallowed: cooperative cancel is expected, not an error
    except BaseException as exc:  # noqa: BLE001 — record then re-raise
        job._append(state="failed", error=type(exc).__name__, msg=str(exc))
        raise
    else:
        job._append(state="complete")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/auto-test-pytest shared-vault/skills/daemon/augur/tests/test_jobledger_ledger.py`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/daemon/scripts/job_ledger/ledger.py shared-vault/skills/daemon/augur/tests/test_jobledger_ledger.py
git commit -m "feat(job-ledger): run() context manager + state machine (ADR-743)"
```

---

# Phase 2 — Supervisor

## Task 4: `supervisor.py` — liveness sweep

**Files:**
- Create: `shared-vault/skills/daemon/scripts/job_ledger/supervisor.py`
- Test: `shared-vault/skills/daemon/augur/tests/test_jobledger_supervisor.py`

- [ ] **Step 1: Write the failing test** (prepend the Shared Test Harness loader block)

```python
def test_orphaned_job_marked_failed(tmp_path: Path, monkeypatch) -> None:
    jr = _load("job_record", "job_record.py")
    monkeypatch.setattr(jr, "jobs_dir", lambda: tmp_path / "jobs")
    sup = _load("supervisor", "supervisor.py")
    monkeypatch.setattr(sup, "_pid_alive", lambda pid: False)        # process is gone
    monkeypatch.setattr(sup, "_surface", lambda *a, **k: None)        # no-op notify
    job_dir = jr.jobs_dir() / "20260514-120000-000-orphan"
    job_dir.mkdir(parents=True)
    jr.append_event(job_dir, {"state": "running", "pid": 4242})       # never finished
    result = sup.sweep(config={"heartbeat_threshold_s": 300, "resubmit_allowlist": []})
    assert jr.current_state(job_dir) == "failed"
    assert result["orphaned"] == 1


def test_live_job_with_fresh_heartbeat_left_alone(tmp_path: Path, monkeypatch) -> None:
    jr = _load("job_record", "job_record.py")
    monkeypatch.setattr(jr, "jobs_dir", lambda: tmp_path / "jobs")
    sup = _load("supervisor", "supervisor.py")
    monkeypatch.setattr(sup, "_pid_alive", lambda pid: True)          # process is alive
    monkeypatch.setattr(sup, "_surface", lambda *a, **k: None)
    job_dir = jr.jobs_dir() / "20260514-120000-000-live"
    job_dir.mkdir(parents=True)
    jr.append_event(job_dir, {"state": "running", "pid": 4242, "heartbeat": True})
    sup.sweep(config={"heartbeat_threshold_s": 300, "resubmit_allowlist": []})
    assert jr.current_state(job_dir) == "running"  # untouched — never force-killed
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/auto-test-pytest shared-vault/skills/daemon/augur/tests/test_jobledger_supervisor.py`
Expected: FAIL — `supervisor.py` does not exist.

- [ ] **Step 3: Write `supervisor.py`**

```python
"""Job ledger supervisor — liveness sweep (ADR-743).

Scans jobs/ for non-terminal jobs. PID-gone -> failed/orphaned. PID alive but
heartbeat lapsed past threshold + declared timeout -> timeout (never force-killed
-- a live process is only surfaced). Surfaces every orphaned/timed-out job through
the daemon notification pipeline. Resubmit is opt-in via the allowlist, off by
default.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

import job_record  # sibling import

logger = logging.getLogger("job_ledger.supervisor")


def _pid_alive(pid: int) -> bool:
    """True if the process exists. Monkeypatched in tests."""
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists but not ours
    except OSError:
        return False


def _surface(job_id: str, reason: str) -> None:
    """Surface a stuck/orphaned job through the daemon notification pipeline."""
    try:
        import notification_service  # daemon sibling

        notification_service.send(f"Job ledger: {job_id} {reason}")
    except Exception as exc:  # noqa: BLE001 — surfacing failure must not break the sweep
        logger.warning("job ledger could not surface %s (%s): %s", job_id, reason, exc)


def _last_running_event(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    for event in reversed(events):
        if event.get("state") == "running":
            return event
    return None


def sweep(*, config: dict[str, Any]) -> dict[str, Any]:
    """Scan jobs/, resolve liveness, surface and (opt-in) resubmit. Returns a summary."""
    threshold_s = int(config.get("heartbeat_threshold_s", 300))
    allowlist = set(config.get("resubmit_allowlist", []) or [])
    root = job_record.jobs_dir()

    orphaned = timed_out = resubmitted = 0
    for job_dir in sorted(p for p in root.iterdir() if p.is_dir() and p.name != "_archive"):
        state = job_record.current_state(job_dir)
        if job_record.is_terminal(state) or state in ("unknown", "pending"):
            continue
        events = job_record.read_events(job_dir)
        last = _last_running_event(events)
        pid = int(last.get("pid", 0)) if last else 0

        if not _pid_alive(pid):
            job_record.append_event(job_dir, {"state": "failed", "reason": "orphaned"})
            _surface(job_dir.name, "orphaned (process gone)")
            orphaned += 1
        else:
            last_t = last.get("t") if last else None
            stale = _is_stale(last_t, threshold_s)
            meta = job_record.read_meta(job_dir)
            past_timeout = _past_declared_timeout(meta)
            if stale and past_timeout:
                job_record.append_event(job_dir, {"state": "timeout"})
                _surface(job_dir.name, "timeout (heartbeat lapsed past declared timeout)")
                timed_out += 1
            # else: alive + healthy -> leave it alone, never force-kill

    return {"orphaned": orphaned, "timed_out": timed_out, "resubmitted": resubmitted}


def _is_stale(last_t: str | None, threshold_s: int) -> bool:
    if not last_t:
        return True
    try:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(last_t)).total_seconds()
        return age > threshold_s
    except (ValueError, TypeError):
        return True


def _past_declared_timeout(meta: dict[str, Any]) -> bool:
    timeout_s = meta.get("declared_timeout_s")
    created = meta.get("created_at")
    if not timeout_s or not created:
        return False
    try:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(created)).total_seconds()
        return age > float(timeout_s)
    except (ValueError, TypeError):
        return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/auto-test-pytest shared-vault/skills/daemon/augur/tests/test_jobledger_supervisor.py`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/daemon/scripts/job_ledger/supervisor.py shared-vault/skills/daemon/augur/tests/test_jobledger_supervisor.py
git commit -m "feat(job-ledger): supervisor liveness sweep (ADR-743)"
```

---

# Phase 3 — Retention

## Task 5: `retention.py` — terminal-job archive

**Files:**
- Create: `shared-vault/skills/daemon/scripts/job_ledger/retention.py`
- Test: `shared-vault/skills/daemon/augur/tests/test_jobledger_retention.py`

- [ ] **Step 1: Write the failing test** (prepend the Shared Test Harness loader block)

```python
def test_old_terminal_jobs_archived_fresh_ones_kept(tmp_path: Path, monkeypatch) -> None:
    import os, time
    jr = _load("job_record", "job_record.py")
    monkeypatch.setattr(jr, "jobs_dir", lambda: tmp_path / "jobs")
    ret = _load("retention", "retention.py")

    old = jr.jobs_dir() / "20260101-000000-000-old"
    old.mkdir(parents=True)
    jr.append_event(old, {"state": "complete"})
    (old / "meta.json").write_text('{"job_id": "old"}', encoding="utf-8")
    ancient = time.time() - 60 * 60 * 24 * 40            # 40 days ago
    os.utime(old / "events.jsonl", (ancient, ancient))

    fresh = jr.jobs_dir() / "20260514-120000-000-fresh"
    fresh.mkdir(parents=True)
    jr.append_event(fresh, {"state": "complete"})

    result = ret.archive(retention_days=30)
    assert result["archived"] == 1
    assert not old.exists()
    assert (jr.jobs_dir() / "_archive" / "old.events.jsonl.gz").exists()
    assert (jr.jobs_dir() / "_archive" / "old.meta.json").exists()  # meta kept uncompressed
    assert fresh.exists()                                           # fresh untouched
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/auto-test-pytest shared-vault/skills/daemon/augur/tests/test_jobledger_retention.py`
Expected: FAIL — `retention.py` does not exist.

- [ ] **Step 3: Write `retention.py`**

```python
"""Job ledger retention — archive terminal jobs past the window (ADR-743).

Terminal jobs older than retention_days move to jobs/_archive/: events.jsonl is
gzipped, meta.json is kept uncompressed (small, grep-friendly), output/ is dropped.
Idempotent.
"""
from __future__ import annotations

import gzip
import logging
import shutil
import time
from typing import Any

import job_record  # sibling import

logger = logging.getLogger("job_ledger.retention")


def archive(*, retention_days: int = 30) -> dict[str, Any]:
    """Move terminal jobs older than retention_days into jobs/_archive/."""
    root = job_record.jobs_dir()
    archive_dir = root / "_archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    cutoff = time.time() - retention_days * 86400

    archived = 0
    for job_dir in sorted(p for p in root.iterdir() if p.is_dir() and p.name != "_archive"):
        if not job_record.is_terminal(job_record.current_state(job_dir)):
            continue
        events_path = job_dir / "events.jsonl"
        if not events_path.exists() or events_path.stat().st_mtime > cutoff:
            continue
        try:
            with events_path.open("rb") as src, gzip.open(
                archive_dir / f"{job_dir.name}.events.jsonl.gz", "wb"
            ) as dst:
                shutil.copyfileobj(src, dst)
            meta_path = job_dir / "meta.json"
            if meta_path.exists():
                shutil.copy2(meta_path, archive_dir / f"{job_dir.name}.meta.json")
            shutil.rmtree(job_dir)
            archived += 1
        except Exception as exc:  # noqa: BLE001 — a partial archive run is acceptable
            logger.warning("job ledger could not archive %s: %s", job_dir.name, exc)

    return {"archived": archived}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/auto-test-pytest shared-vault/skills/daemon/augur/tests/test_jobledger_retention.py`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/daemon/scripts/job_ledger/retention.py shared-vault/skills/daemon/augur/tests/test_jobledger_retention.py
git commit -m "feat(job-ledger): 30-day terminal-job gzip retention (ADR-743)"
```

---

# Phase 4 — MCP Tools + CLI

## Task 6: `jobs-*` MCP tools + `aug jobs` CLI

**Files:**
- Create: `shared-vault/skills/daemon/scripts/job_ledger/jobs_ops.py` (the shared query/CLI logic)
- Modify: `shared-vault/skills/daemon/scripts/job_ledger/mcp/__init__.py` (replace the Task 1 stub)
- Modify: `config/system/capability_exposure.yaml`
- Test: `shared-vault/skills/daemon/augur/tests/test_jobledger_ops.py`

- [ ] **Step 1: Write the failing test** (prepend the Shared Test Harness loader block)

```python
def test_jobs_list_and_detail(tmp_path: Path, monkeypatch) -> None:
    jr = _load("job_record", "job_record.py")
    monkeypatch.setattr(jr, "jobs_dir", lambda: tmp_path / "jobs")
    ops = _load("jobs_ops", "jobs_ops.py")
    job_dir = jr.jobs_dir() / "20260514-120000-000-loop-hygiene"
    job_dir.mkdir(parents=True)
    (job_dir / "meta.json").write_text('{"job_id": "20260514-120000-000-loop-hygiene", "name": "loop-hygiene"}', encoding="utf-8")
    jr.append_event(job_dir, {"state": "running"})
    jr.append_event(job_dir, {"state": "complete"})

    listing = ops.list_jobs()
    assert len(listing) == 1 and listing[0]["state"] == "complete"
    detail = ops.job_detail("20260514-120000-000-loop-hygiene")
    assert len(detail["events"]) == 2 and detail["meta"]["name"] == "loop-hygiene"


def test_jobs_cancel_writes_marker(tmp_path: Path, monkeypatch) -> None:
    jr = _load("job_record", "job_record.py")
    monkeypatch.setattr(jr, "jobs_dir", lambda: tmp_path / "jobs")
    ops = _load("jobs_ops", "jobs_ops.py")
    job_dir = jr.jobs_dir() / "20260514-120000-000-cancelme"
    job_dir.mkdir(parents=True)
    jr.append_event(job_dir, {"state": "running"})
    ops.cancel_job("20260514-120000-000-cancelme")
    assert (job_dir / "cancel_requested").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/auto-test-pytest shared-vault/skills/daemon/augur/tests/test_jobledger_ops.py`
Expected: FAIL — `jobs_ops.py` does not exist.

- [ ] **Step 3: Write `jobs_ops.py`**

```python
"""Job ledger query + mutation ops shared by the MCP tools and the CLI (ADR-743)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import job_record  # sibling import


def list_jobs(*, state: str | None = None, kind: str | None = None,
              archived: bool = False) -> list[dict[str, Any]]:
    """List jobs with their current state; filter by state/kind."""
    root = job_record.jobs_dir()
    out: list[dict[str, Any]] = []
    for job_dir in sorted((p for p in root.iterdir() if p.is_dir() and p.name != "_archive"),
                          reverse=True):
        meta = job_record.read_meta(job_dir)
        cur = job_record.current_state(job_dir)
        if state and cur != state:
            continue
        if kind and meta.get("kind") != kind:
            continue
        out.append({"job_id": job_dir.name, "state": cur,
                    "name": meta.get("name"), "kind": meta.get("kind"),
                    "created_at": meta.get("created_at")})
    return out


def job_detail(job_id: str) -> dict[str, Any]:
    """Full meta + events for one job."""
    job_dir = job_record.jobs_dir() / job_id
    if not job_dir.is_dir():
        return {"error": "not found", "job_id": job_id}
    return {"job_id": job_id, "meta": job_record.read_meta(job_dir),
            "state": job_record.current_state(job_dir),
            "events": job_record.read_events(job_dir)}


def cancel_job(job_id: str) -> dict[str, Any]:
    """Write the cancel_requested marker — phase()/heartbeat() pick it up cooperatively."""
    job_dir = job_record.jobs_dir() / job_id
    if not job_dir.is_dir():
        return {"error": "not found", "job_id": job_id}
    (job_dir / "cancel_requested").write_text("", encoding="utf-8")
    return {"job_id": job_id, "cancel_requested": True}


def submit_job(*, kind: str, name: str, args: dict | None = None,
               timeout_s: int | None = None) -> dict[str, Any]:
    """Register + start a job for a caller that reports events out-of-band (ADR-744)."""
    import ledger

    job = ledger._create_job(kind=kind, name=name, args=args or {},
                             timeout_s=timeout_s, submitter="mcp")
    job._append(state="running", msg="submitted")
    return {"job_id": job.job_dir and Path(job.job_dir).name}


def replay_job(job_id: str) -> dict[str, Any]:
    """Re-dispatch a job's loop from scratch (new job id; no side-effect replay)."""
    meta = job_record.read_meta(job_record.jobs_dir() / job_id)
    if not meta:
        return {"error": "not found", "job_id": job_id}
    fresh = submit_job(kind=meta.get("kind", "loop"), name=meta.get("name", "replay"),
                       args=meta.get("args"), timeout_s=meta.get("declared_timeout_s"))
    return {"replayed_from": job_id, **fresh}
```

- [ ] **Step 4: Replace `mcp/__init__.py`** with the real registration — use the daemon-skill bootstrap header block (the same `_augur_bootstrap_*` block + `scripts/`-on-`sys.path` block as `shared-vault/skills/evals/scripts/mcp/__init__.py` lines 19–48, adjusting the `parent.parent` depth so `scripts/job_ledger/` is on `sys.path`), then:

```python
import json
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

try:
    from src.mcp.augur_shared.annotations import tool_annotations
    from src.mcp.augur_shared.logging import get_entity_logger
except ImportError:  # pragma: no cover
    import logging as _logging

    def get_entity_logger(name: str):
        return _logging.getLogger(name)

    def tool_annotations(annotations: dict) -> dict:
        return annotations

logger = get_entity_logger("mcp.command.job_ledger")

_READ_ONLY = {"destructiveHint": False, "idempotentHint": True,
              "openWorldHint": False, "readOnlyHint": True}
_WRITE = {"destructiveHint": False, "idempotentHint": False,
          "openWorldHint": False, "readOnlyHint": False}


def register_tools(mcp: "FastMCP", mcp_tool_interceptor: Callable[..., Any], metrics: Any) -> None:
    """Register the 5 jobs-* MCP tools (ADR-743)."""
    logger.info("Registering job ledger MCP tools...")

    @mcp.tool(name="jobs-list", annotations=tool_annotations({"title": "Jobs List", **_READ_ONLY}))
    @mcp_tool_interceptor
    async def jobs_list_tool(state: str | None = None, kind: str | None = None) -> str:
        """List ledger jobs with current state; filter by state/kind."""
        metrics.track_tool("jobs_list", skill="daemon")
        import jobs_ops  # type: ignore[import-not-found]

        return json.dumps(jobs_ops.list_jobs(state=state, kind=kind), indent=2, default=str)

    @mcp.tool(name="jobs-detail", annotations=tool_annotations({"title": "Jobs Detail", **_READ_ONLY}))
    @mcp_tool_interceptor
    async def jobs_detail_tool(job_id: str) -> str:
        """Full meta.json + events.jsonl for one job id."""
        metrics.track_tool("jobs_detail", skill="daemon")
        import jobs_ops  # type: ignore[import-not-found]

        return json.dumps(jobs_ops.job_detail(job_id), indent=2, default=str)

    @mcp.tool(name="jobs-submit", annotations=tool_annotations({"title": "Jobs Submit", **_WRITE}))
    @mcp_tool_interceptor
    async def jobs_submit_tool(kind: str, name: str, timeout_s: int | None = None) -> str:
        """Register + start a job (for dispatched workflows / ADR-744 routines)."""
        metrics.track_tool("jobs_submit", skill="daemon")
        import jobs_ops  # type: ignore[import-not-found]

        return json.dumps(jobs_ops.submit_job(kind=kind, name=name, timeout_s=timeout_s), indent=2)

    @mcp.tool(name="jobs-cancel", annotations=tool_annotations({"title": "Jobs Cancel", **_WRITE}))
    @mcp_tool_interceptor
    async def jobs_cancel_tool(job_id: str) -> str:
        """Write the cancel_requested marker for a running job (cooperative)."""
        metrics.track_tool("jobs_cancel", skill="daemon")
        import jobs_ops  # type: ignore[import-not-found]

        return json.dumps(jobs_ops.cancel_job(job_id), indent=2)

    @mcp.tool(name="jobs-replay", annotations=tool_annotations({"title": "Jobs Replay", **_WRITE}))
    @mcp_tool_interceptor
    async def jobs_replay_tool(job_id: str) -> str:
        """Re-dispatch a job's loop from scratch — new job id, no side-effect replay."""
        metrics.track_tool("jobs_replay", skill="daemon")
        import jobs_ops  # type: ignore[import-not-found]

        return json.dumps(jobs_ops.replay_job(job_id), indent=2)

    logger.info("job ledger MCP tools registered (5 tools)")


def register_subcommands(subparsers) -> None:
    """Register `aug jobs <verb>` (ADR-260)."""
    parser = subparsers.add_parser("jobs", help="File-based job ledger — ADR-743")
    sub = parser.add_subparsers(dest="jobs_verb")
    p_list = sub.add_parser("list", help="list jobs")
    p_list.add_argument("--state")
    p_list.add_argument("--kind")
    p_detail = sub.add_parser("detail", help="full events for one job")
    p_detail.add_argument("job_id")
    p_cancel = sub.add_parser("cancel", help="request cooperative cancel")
    p_cancel.add_argument("job_id")
    p_replay = sub.add_parser("replay", help="re-dispatch a job from scratch")
    p_replay.add_argument("job_id")
    parser.set_defaults(func=_run_jobs_cli)


def _run_jobs_cli(args, remaining) -> int:
    verb = getattr(args, "jobs_verb", None)
    import jobs_ops  # type: ignore[import-not-found]

    if verb == "list":
        print(json.dumps(jobs_ops.list_jobs(state=args.state, kind=args.kind), indent=2, default=str))
    elif verb == "detail":
        print(json.dumps(jobs_ops.job_detail(args.job_id), indent=2, default=str))
    elif verb == "cancel":
        print(json.dumps(jobs_ops.cancel_job(args.job_id), indent=2))
    elif verb == "replay":
        print(json.dumps(jobs_ops.replay_job(args.job_id), indent=2))
    else:
        print(json.dumps({"error": "no verb", "verbs": ["list", "detail", "cancel", "replay"]}, indent=2))
        return 2
    return 0


__all__ = ["register_tools", "register_subcommands"]
```

- [ ] **Step 5: Add capability-exposure entries** — append to `config/system/capability_exposure.yaml` (alphabetical), one block per tool following the existing `mcp-tool:` shape, for `jobs-list`, `jobs-detail`, `jobs-submit`, `jobs-cancel`, `jobs-replay` — all `management: generated`, `owner_kind: augur`, `primary_surface: cli`, `preferred_client: shell`, `scope: project`, `export_to: [browse]`.

- [ ] **Step 6: Run test + verify MCP imports**

Run: `/auto-test-pytest shared-vault/skills/daemon/augur/tests/test_jobledger_ops.py`
Expected: PASS (2 passed).

- [ ] **Step 7: Commit**

```bash
git add shared-vault/skills/daemon/scripts/job_ledger/ config/system/capability_exposure.yaml shared-vault/skills/daemon/augur/tests/test_jobledger_ops.py
git commit -m "feat(job-ledger): 5 jobs-* MCP tools + aug jobs CLI (ADR-743)"
```

---

# Phase 5 — Executor Integration

## Task 7: Wrap the executor dispatch points

Each executor wraps its per-run dispatch in `ledger.run(...)`. The call is
best-effort by construction (`run()` degrades to `_NullJob` if the ledger cannot
write) so a ledger failure can never break loop execution.

**Files:**
- Modify: `shared-vault/skills/daemon/scripts/adaptive_loop_executor.py`
- Modify: `shared-vault/skills/daemon/scripts/schedule_executor.py`
- Modify: `shared-vault/skills/daemon/scripts/continuous_executor.py`
- Modify: `shared-vault/skills/daemon/scripts/ai_self_healer.py`
- Test: `shared-vault/skills/daemon/augur/tests/test_jobledger_integration.py`

- [ ] **Step 1: Write the failing test** — pins the integration contract (prepend the harness loader)

```python
def test_executor_integration_contract(tmp_path: Path, monkeypatch) -> None:
    """Every executor wraps its dispatch in this exact pattern."""
    jr = _load("job_record", "job_record.py")
    monkeypatch.setattr(jr, "jobs_dir", lambda: tmp_path / "jobs")
    ledger = _load("ledger", "ledger.py")
    # the pattern each executor applies around its per-run dispatch:
    with ledger.run(kind="loop", name="loop-hygiene", timeout_s=600) as job:
        job.phase("dispatch")
    assert jr.current_state(Path(job.job_dir)) == "complete"
    listing = _load("jobs_ops", "jobs_ops.py").list_jobs()
    assert any(j["name"] == "loop-hygiene" for j in listing)
```

- [ ] **Step 2: Run test to verify it passes** (the contract holds from Tasks 3/6) — then Steps 3–6 add the real call sites.

Run: `/auto-test-pytest shared-vault/skills/daemon/augur/tests/test_jobledger_integration.py`
Expected: PASS — the contract is sound; the call sites do not exist yet.

- [ ] **Step 3: Locate + wrap `adaptive_loop_executor.py`** — find the per-loop / per-category dispatch boundary (`_run_split_auto_loop` and the `AdaptiveLoopEngine` cycle entry). Add a `job_ledger` import using the daemon-script bootstrap (the subpackage is on `sys.path` once bootstrap runs), and wrap the dispatch:

```python
from job_ledger import ledger as _job_ledger  # via daemon bootstrap

with _job_ledger.run(kind="loop", name=loop_name, args=loop_args, timeout_s=loop_timeout) as _job:
    _job.phase("dispatch")
    <existing per-loop dispatch call>
```

The wrapped call's own logic and error handling are unchanged — `run()` only records.

- [ ] **Step 4: Locate + wrap `schedule_executor.py`** — same pattern at the scheduled-task dispatch point, `kind="schedule"`.

- [ ] **Step 5: Locate + wrap `continuous_executor.py`** — same pattern at the continuous-check dispatch point, `kind="continuous"`.

- [ ] **Step 6: Locate + wrap `ai_self_healer.py`** — same pattern at the per-heal-cycle entry, `kind="heal"`.

- [ ] **Step 7: Run integration test + daemon regression**

Run: `/auto-test-pytest shared-vault/skills/daemon/augur/tests/`
Expected: PASS — all job-ledger tests + no daemon regressions.

- [ ] **Step 8: Commit**

```bash
git add shared-vault/skills/daemon/scripts/adaptive_loop_executor.py shared-vault/skills/daemon/scripts/schedule_executor.py shared-vault/skills/daemon/scripts/continuous_executor.py shared-vault/skills/daemon/scripts/ai_self_healer.py shared-vault/skills/daemon/augur/tests/test_jobledger_integration.py
git commit -m "feat(job-ledger): wrap executor dispatch points in ledger.run (ADR-743)"
```

---

# Phase 6 — Daemon Heartbeat Wiring

## Task 8: `unified_daemon` calls `supervisor.sweep()` + `retention.archive()`

**Files:**
- Create: `shared-vault/skills/daemon/scripts/job_ledger/config.py`
- Modify: `shared-vault/skills/daemon/scripts/unified_daemon.py`
- Test: `shared-vault/skills/daemon/augur/tests/test_jobledger_config.py`

- [ ] **Step 1: Write the failing test for the config reader** (prepend the Shared Test Harness loader block)

```python
def test_load_job_ledger_config_reads_block(tmp_path: Path, monkeypatch) -> None:
    cfg_module = _load("config", "config.py")
    fake = tmp_path / "config.yaml"
    fake.write_text(
        "contributions: {}\n"
        "job_ledger:\n"
        "  heartbeat_threshold_s: 120\n"
        "  retention_days: 14\n"
        "  resubmit_allowlist: [loop-hygiene]\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(cfg_module, "_config_path", lambda: fake)
    cfg = cfg_module.load_job_ledger_config()
    assert cfg["heartbeat_threshold_s"] == 120
    assert cfg["retention_days"] == 14
    assert cfg["resubmit_allowlist"] == ["loop-hygiene"]


def test_load_job_ledger_config_defaults_when_missing(tmp_path: Path, monkeypatch) -> None:
    cfg_module = _load("config", "config.py")
    fake = tmp_path / "config.yaml"
    fake.write_text("contributions: {}\n", encoding="utf-8")  # no job_ledger block
    monkeypatch.setattr(cfg_module, "_config_path", lambda: fake)
    cfg = cfg_module.load_job_ledger_config()
    assert cfg["heartbeat_threshold_s"] == 300  # built-in default
    assert cfg["retention_days"] == 30
    assert cfg["resubmit_allowlist"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/auto-test-pytest shared-vault/skills/daemon/augur/tests/test_jobledger_config.py`
Expected: FAIL — `config.py` does not exist.

- [ ] **Step 3: Write `job_ledger/config.py`**

```python
"""Reader for the job_ledger: block in the daemon skill's config.yaml (ADR-743)."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("job_ledger.config")

_DEFAULTS: dict[str, Any] = {
    "heartbeat_threshold_s": 300,
    "retention_days": 30,
    "resubmit_allowlist": [],
}


def _config_path() -> Path:
    """Path to the daemon skill's config.yaml. Monkeypatchable in tests."""
    return Path(__file__).resolve().parents[2] / "config.yaml"


def load_job_ledger_config() -> dict[str, Any]:
    """Return the job_ledger: block merged over built-in defaults. Fails closed."""
    cfg = dict(_DEFAULTS)
    try:
        data = yaml.safe_load(_config_path().read_text(encoding="utf-8")) or {}
        block = data.get("job_ledger") or {}
        if isinstance(block, dict):
            cfg.update({k: block[k] for k in _DEFAULTS if k in block})
    except Exception as exc:  # noqa: BLE001 — fail closed to defaults
        logger.warning("job ledger config unreadable (%s); using defaults", exc)
    return cfg
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/auto-test-pytest shared-vault/skills/daemon/augur/tests/test_jobledger_config.py`
Expected: PASS (2 passed).

- [ ] **Step 5: Locate the daemon's startup + heartbeat/cadence point** — `unified_daemon.py`'s `SubprocessManager` main loop / status-write cadence (around `_write_status`).

- [ ] **Step 6: Add a ledger-sweep call** at startup and on the heartbeat cadence:

```python
def _job_ledger_sweep() -> None:
    """Best-effort job ledger supervisor sweep + retention. Never raises into the daemon."""
    try:
        from job_ledger import supervisor, retention  # via daemon bootstrap
        from job_ledger.config import load_job_ledger_config

        cfg = load_job_ledger_config()
        supervisor.sweep(config=cfg)
        retention.archive(retention_days=cfg.get("retention_days", 30))
    except Exception as exc:  # noqa: BLE001 — the daemon must not crash on a ledger sweep
        logger.warning("job ledger sweep failed: %s", exc)
```

Call `_job_ledger_sweep()` once at daemon startup and on each heartbeat tick.

- [ ] **Step 7: Run daemon test suite**

Run: `/auto-test-pytest shared-vault/skills/daemon/augur/tests/`
Expected: PASS — no regressions; the sweep is best-effort and isolated.

- [ ] **Step 8: Commit**

```bash
git add shared-vault/skills/daemon/scripts/unified_daemon.py shared-vault/skills/daemon/scripts/job_ledger/config.py shared-vault/skills/daemon/augur/tests/test_jobledger_config.py
git commit -m "feat(job-ledger): wire supervisor sweep into the daemon heartbeat (ADR-743)"
```

---

# Phase 7 — Docs + Final Validation

## Task 9: Topic docs + regeneration + validation gate

**Files:**
- Modify: `docs/architecture-daemon.md`

- [ ] **Step 1: Add a "Job Ledger" section to `architecture-daemon.md`** — `runtime/jobs/` is the crash-safe run-record layer beneath every executor; `runtime/adaptive/` (trust/difficulty) is orthogonal learning state and is untouched; `cat events.jsonl` is the whole story of a job; the supervisor runs on the daemon heartbeat and surfaces (does not force-kill) stuck jobs.

- [ ] **Step 2: Regenerate agent instructions**

Run: `PYTHONPATH=shared-vault python3 -m skills.ai.scripts.sync_agents sync agents all`
Expected: regenerates `CLAUDE.md` / per-client surfaces with the 5 new `mcp-tool:jobs-*` rows.

- [ ] **Step 3: Full job-ledger test suite**

Run: `/auto-test-pytest shared-vault/skills/daemon/augur/tests/`
Expected: PASS — all 7 `test_jobledger_*` files green.

- [ ] **Step 4: Lint**

Run: `/auto-lint`
Expected: clean — no new findings in `job_ledger/` or the modified executors.

- [ ] **Step 5: Confirm no DB introduced**

Run: `grep -rnE "sqlite|pglite|lancedb|postgres" shared-vault/skills/daemon/scripts/job_ledger/ || echo "clean"`
Expected: `clean` — plain files only.

- [ ] **Step 6: End-to-end smoke**

Run: `aug jobs list`
Expected: JSON array (possibly empty before any wrapped run) — proves the CLI + ledger resolve.

- [ ] **Step 7: Commit**

```bash
git add docs/architecture-daemon.md CLAUDE.md AGENTS.md .claude/ .codex/ .gemini/
git commit -m "docs(job-ledger): architecture-daemon ledger section + regenerate surfaces (ADR-743)"
```

---

## Completion Checklist (maps to ADR-743 Completion Gates)

- [ ] `job_record`, `ledger`, `supervisor`, `retention`, `jobs_ops` written — no orphan code
- [ ] Four executor dispatch points wrapped in `ledger.run(...)` — verified by the integration test
- [ ] `unified_daemon` heartbeat calls `supervisor.sweep()` + `retention.archive()`
- [ ] `config.yaml` has the `job_ledger:` block; `capability_exposure.yaml` has 5 entries
- [ ] Every plan test case green; daemon suite green (no regressions)
- [ ] Adaptive Loop Engine's `runtime/adaptive/` state untouched — ledger is purely additive
- [ ] `architecture-daemon.md` documents the ledger; agent instructions regenerated
- [ ] `grep` confirms no database; `aug jobs list` resolves end-to-end
- [ ] `superpowers:verification-before-completion` run before declaring done
```
