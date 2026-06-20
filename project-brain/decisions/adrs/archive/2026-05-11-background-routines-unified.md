# Background Routines — Unified Discovery and Browse Category — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the misleadingly-named `scheduled-executions` Browse category with a unified `background-routines` category that discovers all six kinds of autonomous triggers on the machine, surfaces cadence + last-run + token-cost as first-class UI elements, and ships a `list-routines` MCP tool as the single Browse data source.

**Architecture:** One Python module owns discovery (`routine_discovery.py` with a `Routine` dataclass, 6 source-kind discoverers, a fail-soft aggregator, and AI-cost log sampling). One MCP tool exposes it (`list-routines` with filters + mtime-based cache). Dashboard renames the Browse category, adds a `routine-format.ts` helper module reused across card / table / detail-panel surfaces, and rebuilds the detail panel with a 2-column Cadence/Last-Run grid.

**Tech Stack:** Python 3.11+ (dataclasses, subprocess, plistlib, pytest). Dashboard: Next.js 16, TypeScript, Vitest. No new runtime deps beyond stdlib + existing PyYAML.

**Spec:** `docs/superpowers/specs/2026-05-11-background-routines-unified-design.md`
**ADR:** `docs/adrs/ADR-727-background-routines-unified-discovery.md`

---

## Boundary rules (apply to every task)

- **No server-side LLM call by default.** Augur is the harness layer; native AI clients provide reasoning. The AI-cost field is derived from log sampling, not LLM introspection. Any `llm-via-router` routine is a named direct-model exception and requires explicit approval.
- **No skeleton fallback.** Each discoverer fails soft (logs warning, returns empty list); the aggregator continues with partial results. CLAUDE.md rule 1: never produce degraded output that hides a broken state.
- **View-only for v1.** No pause / run-now / edit-cadence controls. The `list-routines` MCP tool is read-only.
- **One-release shim policy.** The `scheduled-executions` URL redirect + type alias have a one-release lifetime per CLAUDE.md rule 14. The next release after this one removes them.
- **AI-cost defaults.** When logs are absent or sparse, `ai_cost = None` and the UI shows "—". Don't fabricate token counts.

After every doc-editing or code-editing commit, run the relevant test file. Final integration verification (Task 19) runs `pytest` + browser verification per rule 28.

---

## Task 1: `routine_discovery.py` module skeleton (Routine dataclass + Discoverer protocol + enums)

**Files:**
- Create: `shared-vault/skills/daemon/scripts/routine_discovery.py`

- [ ] **Step 1: Create the module with Routine dataclass + protocol + enums**

Write to `shared-vault/skills/daemon/scripts/routine_discovery.py`:

```python
"""Background routine discovery — unified surface across 6 source kinds.

Per ADR-727 / docs/superpowers/specs/2026-05-11-background-routines-unified-design.md.

Six source-kind discoverers each return list[Routine]; discover_all_routines()
aggregates them with fail-soft per-discoverer error handling.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from typing import Any, Protocol

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums (string constants — keep simple, no IntEnum)
# ---------------------------------------------------------------------------

SOURCE_KINDS = frozenset({
    "per-skill-schedule",
    "daemon-service",
    "daemon-script",
    "launchd-agent",
    "github-action",
    "mcp-background",
})

CADENCE_TYPES = frozenset({"interval", "cron", "event", "manual", "logon"})

STATUSES = frozenset({"enabled", "disabled", "erroring", "paused"})

SPAWN_KINDS = frozenset({"bash", "python", "llm-via-router", "ai-cli-spawn", "http-action"})

AI_CLIS = frozenset({"claude", "codex", "gemini"})


# ---------------------------------------------------------------------------
# Routine dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Routine:
    """Unified record across all 6 source kinds.

    See spec §4 for full field semantics.
    """
    id: str
    display_name: str
    source_kind: str
    source_path: str
    cadence: dict[str, Any]           # {type, spec, spec_raw, next_run_estimated}
    status: str
    spawn_kind: str
    config_path: str | None = None
    ai_cost: dict[str, Any] | None = None  # {cli, estimated_tokens_per_run, ...} when ai-cli-spawn
    last_run_at: str | None = None
    last_run_status: str | None = None
    last_run_log: str | None = None
    recent_runs_24h: int | None = None
    description: str | None = None
    tags: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Discoverer protocol
# ---------------------------------------------------------------------------

class RoutineDiscoverer(Protocol):
    source_kind: str
    def discover(self) -> list[Routine]: ...
```

- [ ] **Step 2: Verify the module imports cleanly**

Run:
```bash
python3 -c "
import sys
sys.path.insert(0, 'shared-vault')
from skills.daemon.scripts.routine_discovery import (
    Routine, RoutineDiscoverer,
    SOURCE_KINDS, CADENCE_TYPES, STATUSES, SPAWN_KINDS, AI_CLIS,
)
print(f'OK — source_kinds: {sorted(SOURCE_KINDS)}')
print(f'spawn_kinds: {sorted(SPAWN_KINDS)}')
"
```
Expected:
```
OK — source_kinds: ['daemon-script', 'daemon-service', 'github-action', 'launchd-agent', 'mcp-background', 'per-skill-schedule']
spawn_kinds: ['ai-cli-spawn', 'bash', 'http-action', 'llm-via-router', 'python']
```

- [ ] **Step 3: Commit**

```bash
git add shared-vault/skills/daemon/scripts/routine_discovery.py
git commit -m "$(cat <<'EOF'
feat(daemon): routine_discovery module — Routine dataclass + protocol + enums

Foundation for ADR-727 (Background Routines Unified Discovery).

This commit adds only the module skeleton:
  - Routine frozen dataclass (spec §4 schema, all 14 fields)
  - RoutineDiscoverer Protocol (source_kind str + discover() method)
  - Five string-set enums: SOURCE_KINDS (6), CADENCE_TYPES (5),
    STATUSES (4), SPAWN_KINDS (5), AI_CLIS (3)

The six concrete discoverer implementations + aggregator land in
follow-on tasks (one task per discoverer for clean review boundaries).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: `compute_next_run()` + `derive_ai_cost()` helpers

**Files:**
- Modify: `shared-vault/skills/daemon/scripts/routine_discovery.py` (append helper functions)
- Create: `tests/unit/test_routine_discovery.py`

- [ ] **Step 1: Append helpers to the module**

Use Edit to append to `shared-vault/skills/daemon/scripts/routine_discovery.py`:

Find the last line of the file (the `RoutineDiscoverer` Protocol class). Append after it:

```python


# ---------------------------------------------------------------------------
# Helper: compute next_run_estimated from a cadence dict
# ---------------------------------------------------------------------------

from datetime import datetime, timedelta, timezone

def compute_next_run(cadence: dict[str, Any], last_run_at: str | None = None, now: datetime | None = None) -> str | None:
    """Compute the next run timestamp (ISO-8601 UTC) for a cadence.

    Returns None for event/manual cadences. For interval cadences, returns
    last_run_at + interval (or now + interval if no last_run). For cron and
    logon types, returns None for v1 (lightweight estimator only).
    """
    cad_type = cadence.get("type")
    if cad_type in ("event", "manual", "cron", "logon"):
        # cron + logon: too varied to estimate in v1; leave as None
        return None
    if cad_type != "interval":
        return None

    interval_s = cadence.get("interval_seconds")
    if not interval_s:
        return None

    base = now or datetime.now(timezone.utc)
    if last_run_at:
        try:
            base = datetime.fromisoformat(last_run_at.replace("Z", "+00:00"))
        except ValueError:
            pass

    next_run = base + timedelta(seconds=int(interval_s))
    return next_run.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Helper: derive ai_cost from log sampling
# ---------------------------------------------------------------------------

from pathlib import Path

# Starting constant — calibrate over weeks of observation (spec §11).
CANONICAL_TOKENS_PER_CLAUDE_PRINT_RUN = 10_000


def derive_ai_cost(
    *,
    routine_id: str,
    cli: str,
    logs_dir: Path,
    spawns_per_run: int,
) -> dict[str, Any] | None:
    """Estimate AI-CLI cost from log sampling.

    Walks logs_dir for the routine's recent run logs (looks at top-level
    subdirectories named YYYY-MM-DD or similar) and counts file appearances
    as a proxy for run count in last 24h.

    Returns None if logs_dir doesn't exist or has < 1 sample.
    """
    if not logs_dir.exists() or not logs_dir.is_dir():
        return None

    now = datetime.now(timezone.utc)
    one_day_ago = now - timedelta(days=1)

    recent_runs = 0
    for log_path in logs_dir.rglob("*.log"):
        try:
            mtime = datetime.fromtimestamp(log_path.stat().st_mtime, tz=timezone.utc)
            if mtime >= one_day_ago:
                recent_runs += 1
        except OSError:
            continue

    if recent_runs == 0:
        return None

    estimated_tokens_per_run = CANONICAL_TOKENS_PER_CLAUDE_PRINT_RUN * spawns_per_run
    estimated_runs_per_day = recent_runs
    estimated_tokens_per_day = estimated_tokens_per_run * estimated_runs_per_day

    return {
        "cli": cli,
        "estimated_tokens_per_run": estimated_tokens_per_run,
        "estimated_runs_per_day": estimated_runs_per_day,
        "estimated_tokens_per_day": estimated_tokens_per_day,
    }
```

- [ ] **Step 2: Write the helper tests first (TDD)**

Write to `tests/unit/test_routine_discovery.py`:

```python
"""Unit tests for routine_discovery — helpers, discoverers, aggregation."""
from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "shared-vault"))

from skills.daemon.scripts.routine_discovery import (  # noqa: E402
    Routine, RoutineDiscoverer,
    SOURCE_KINDS, CADENCE_TYPES, STATUSES, SPAWN_KINDS, AI_CLIS,
    compute_next_run, derive_ai_cost,
)


# ---------------------------------------------------------------------------
# Dataclass tests
# ---------------------------------------------------------------------------

def test_routine_minimal_fields():
    r = Routine(
        id="x", display_name="X", source_kind="daemon-service",
        source_path="/p", cadence={"type": "interval", "spec": "every 12h", "interval_seconds": 43200},
        status="enabled", spawn_kind="python",
    )
    assert r.id == "x"
    assert r.ai_cost is None
    assert r.tags == []


# ---------------------------------------------------------------------------
# compute_next_run
# ---------------------------------------------------------------------------

def test_compute_next_run_event_returns_none():
    assert compute_next_run({"type": "event"}) is None


def test_compute_next_run_manual_returns_none():
    assert compute_next_run({"type": "manual"}) is None


def test_compute_next_run_cron_returns_none_in_v1():
    # cron estimation is out of scope for v1 (spec §10)
    assert compute_next_run({"type": "cron", "spec": "0 3 * * *"}) is None


def test_compute_next_run_logon_returns_none():
    assert compute_next_run({"type": "logon"}) is None


def test_compute_next_run_interval_without_last_run():
    now = datetime(2026, 5, 11, 8, 0, 0, tzinfo=timezone.utc)
    cadence = {"type": "interval", "spec": "every 12h", "interval_seconds": 43200}
    result = compute_next_run(cadence, now=now)
    # Should be now + 12h
    assert result == "2026-05-11T20:00:00Z"


def test_compute_next_run_interval_with_last_run():
    cadence = {"type": "interval", "spec": "every 12h", "interval_seconds": 43200}
    last_run = "2026-05-11T05:00:00Z"
    result = compute_next_run(cadence, last_run_at=last_run)
    # 05:00 + 12h = 17:00
    assert result == "2026-05-11T17:00:00Z"


def test_compute_next_run_interval_missing_seconds_returns_none():
    assert compute_next_run({"type": "interval"}) is None


# ---------------------------------------------------------------------------
# derive_ai_cost
# ---------------------------------------------------------------------------

def test_derive_ai_cost_missing_dir_returns_none():
    result = derive_ai_cost(
        routine_id="x", cli="claude",
        logs_dir=Path("/nonexistent/path/xyz"),
        spawns_per_run=39,
    )
    assert result is None


def test_derive_ai_cost_empty_dir_returns_none():
    with tempfile.TemporaryDirectory() as td:
        result = derive_ai_cost(
            routine_id="x", cli="claude",
            logs_dir=Path(td),
            spawns_per_run=39,
        )
        assert result is None


def test_derive_ai_cost_with_recent_logs():
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        # Create 2 recent log files
        (td_path / "2026-05-11").mkdir()
        (td_path / "2026-05-11" / "08-00_pid.log").write_text("log line\n")
        (td_path / "2026-05-11" / "20-00_pid.log").write_text("log line\n")

        result = derive_ai_cost(
            routine_id="insight_scanner", cli="claude",
            logs_dir=td_path,
            spawns_per_run=39,
        )
        assert result is not None
        assert result["cli"] == "claude"
        # 10K canonical × 39 spawns_per_run = 390K per run
        assert result["estimated_tokens_per_run"] == 390_000
        assert result["estimated_runs_per_day"] == 2
        assert result["estimated_tokens_per_day"] == 780_000
```

- [ ] **Step 3: Run the tests — verify pass**

Run:
```bash
pytest tests/unit/test_routine_discovery.py -v
```
Expected: 12 tests pass.

- [ ] **Step 4: Commit**

```bash
git add shared-vault/skills/daemon/scripts/routine_discovery.py tests/unit/test_routine_discovery.py
git commit -m "$(cat <<'EOF'
feat(daemon): compute_next_run + derive_ai_cost helpers

compute_next_run(cadence, last_run_at, now):
  - Event / manual / cron / logon cadences return None
    (cron estimation deferred per spec §10)
  - Interval cadences compute last_run + interval (or now + interval)
  - Missing interval_seconds returns None

derive_ai_cost(routine_id, cli, logs_dir, spawns_per_run):
  - Walks logs_dir.rglob("*.log") for files modified in last 24h
  - estimated_tokens_per_run = 10K canonical × spawns_per_run
  - estimated_tokens_per_day = per_run × runs_24h
  - Returns None if logs_dir absent or no recent runs (UI shows "—")

12 unit tests covering all branches.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: `PerSkillScheduleDiscoverer` — reuse existing `schedule_executor.discover_schedules()`

**Files:**
- Modify: `shared-vault/skills/daemon/scripts/routine_discovery.py` (append discoverer class)
- Modify: `tests/unit/test_routine_discovery.py` (append test cases)

- [ ] **Step 1: Write the failing test first**

Append to `tests/unit/test_routine_discovery.py`:

```python


# ---------------------------------------------------------------------------
# PerSkillScheduleDiscoverer
# ---------------------------------------------------------------------------

from unittest.mock import patch
from skills.daemon.scripts.routine_discovery import PerSkillScheduleDiscoverer  # noqa: E402


def test_per_skill_schedule_discoverer_emits_routines():
    fake_schedules = [
        {
            "_path": "/path/to/skill/schedules/x.yaml",
            "id": "auto-mcp-health-audit",
            "skill": "loop-ops",
            "schedule": {"frequency": "daily", "time": "03:00", "timezone": "UTC"},
            "action": {"id": "mcp-health-audit", "dispatch": "fire"},
            "enabled": True,
        }
    ]
    with patch("skills.daemon.scripts.routine_discovery._call_discover_schedules", return_value=fake_schedules):
        routines = PerSkillScheduleDiscoverer().discover()

    assert len(routines) == 1
    r = routines[0]
    assert r.source_kind == "per-skill-schedule"
    assert r.id == "auto-mcp-health-audit"
    assert r.spawn_kind == "http-action"
    assert r.cadence["type"] in ("interval", "cron", "event", "manual", "logon")
    assert r.status == "enabled"
    assert r.source_path == "/path/to/skill/schedules/x.yaml"


def test_per_skill_schedule_discoverer_empty_returns_empty_list():
    with patch("skills.daemon.scripts.routine_discovery._call_discover_schedules", return_value=[]):
        routines = PerSkillScheduleDiscoverer().discover()
    assert routines == []
```

- [ ] **Step 2: Run test → verify it fails**

Run:
```bash
pytest tests/unit/test_routine_discovery.py::test_per_skill_schedule_discoverer_emits_routines -v
```
Expected: FAIL (`PerSkillScheduleDiscoverer` not defined).

- [ ] **Step 3: Implement the discoverer**

Append to `shared-vault/skills/daemon/scripts/routine_discovery.py`:

```python


# ---------------------------------------------------------------------------
# PerSkillScheduleDiscoverer
# ---------------------------------------------------------------------------

def _call_discover_schedules() -> list[dict[str, Any]]:
    """Thin wrapper around schedule_executor.discover_schedules() — separate
    function so tests can monkeypatch without touching the real scanner.
    """
    from skills.daemon.scripts.schedule_executor import discover_schedules
    return discover_schedules()


def _frequency_to_cadence(schedule_cfg: dict[str, Any]) -> dict[str, Any]:
    """Translate schedule_executor's frequency/day/time config into our cadence dict."""
    freq = str(schedule_cfg.get("frequency", "daily")).lower()
    if freq in ("daily", "weekly", "monthly"):
        time_str = schedule_cfg.get("time", "09:00")
        spec_human = f"{freq} at {time_str}"
        # Lightweight interval_seconds for next-run estimation; rough — daily=86400, etc.
        seconds = {"daily": 86400, "weekly": 604800, "monthly": 2592000}[freq]
        return {
            "type": "interval", "spec": spec_human, "spec_raw": str(schedule_cfg),
            "interval_seconds": seconds,
        }
    if freq == "once":
        return {"type": "manual", "spec": f"once at {schedule_cfg.get('time', '')}", "spec_raw": str(schedule_cfg)}
    return {"type": "manual", "spec": freq, "spec_raw": str(schedule_cfg)}


class PerSkillScheduleDiscoverer:
    source_kind = "per-skill-schedule"

    def discover(self) -> list[Routine]:
        try:
            schedules = _call_discover_schedules()
        except Exception as exc:
            logger.warning("PerSkillScheduleDiscoverer: failed to load schedules: %s", exc)
            return []

        routines: list[Routine] = []
        for s in schedules:
            action_id = s.get("action", {}).get("id") or s.get("id", "unknown")
            dispatch = str(s.get("action", {}).get("dispatch", "fire")).lower()
            spawn_kind = "http-action"  # both fire and oneshot dispatch via dashboard API per ADR
            cadence = _frequency_to_cadence(s.get("schedule", {}))
            cadence["next_run_estimated"] = compute_next_run(cadence)
            routines.append(Routine(
                id=action_id,
                display_name=action_id.replace("-", " ").title(),
                source_kind="per-skill-schedule",
                source_path=str(s.get("_path", "")),
                config_path=str(s.get("_path", "")),
                cadence=cadence,
                status="enabled" if s.get("enabled", True) else "disabled",
                spawn_kind=spawn_kind,
                description=f"Per-skill schedule for action {action_id} (dispatch={dispatch})",
                tags=["per-skill", s.get("skill", "")],
            ))
        return routines
```

- [ ] **Step 4: Run tests → verify pass**

Run:
```bash
pytest tests/unit/test_routine_discovery.py -v -k "per_skill"
```
Expected: 2 tests pass.

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/daemon/scripts/routine_discovery.py tests/unit/test_routine_discovery.py
git commit -m "$(cat <<'EOF'
feat(daemon): PerSkillScheduleDiscoverer — reuse schedule_executor

The first of 6 discoverers. Wraps schedule_executor.discover_schedules()
through a tiny indirection (_call_discover_schedules) so tests can
monkeypatch without touching the real filesystem scanner.

Maps schedule_executor's frequency/day/time config to our Routine.cadence
dict. spawn_kind is "http-action" since both fire and oneshot dispatch
through the dashboard's /api/actions/* routes (no direct CLI spawn).

Two unit tests covering happy path + empty input.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: `DaemonServiceDiscoverer` — parses `adaptive_loops.yaml`

**Files:**
- Modify: `shared-vault/skills/daemon/scripts/routine_discovery.py` (append)
- Modify: `tests/unit/test_routine_discovery.py` (append tests)

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_routine_discovery.py`:

```python


# ---------------------------------------------------------------------------
# DaemonServiceDiscoverer
# ---------------------------------------------------------------------------

from skills.daemon.scripts.routine_discovery import DaemonServiceDiscoverer  # noqa: E402


def test_daemon_service_discoverer_reads_adaptive_loops_yaml():
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        cfg_path = td_path / "adaptive_loops.yaml"
        cfg_path.write_text("""
services:
  insight_scanner:
    interval_hours: 12
  continuous_executor:
    poll_interval_seconds: 300
  mcp_health_monitor:
    interval_hours: 1
""")
        routines = DaemonServiceDiscoverer(config_path=cfg_path).discover()

    assert len(routines) == 3
    ids = {r.id for r in routines}
    assert ids == {"insight_scanner", "continuous_executor", "mcp_health_monitor"}

    # insight_scanner: interval_hours = 12 → interval_seconds = 43200
    insight = next(r for r in routines if r.id == "insight_scanner")
    assert insight.source_kind == "daemon-service"
    assert insight.cadence["type"] == "interval"
    assert insight.cadence["interval_seconds"] == 43200
    assert insight.spawn_kind == "python"  # default unless overridden by DaemonScriptDiscoverer overlap

    # continuous_executor: poll_interval_seconds = 300
    cont = next(r for r in routines if r.id == "continuous_executor")
    assert cont.cadence["interval_seconds"] == 300


def test_daemon_service_discoverer_missing_file_returns_empty():
    routines = DaemonServiceDiscoverer(config_path=Path("/nonexistent/x.yaml")).discover()
    assert routines == []


def test_daemon_service_discoverer_disabled_via_huge_interval():
    """interval_hours of 876000 (100 years) is the documented "disabled" pattern.

    The routine still appears in the list with status='enabled' and
    cadence showing the huge interval — this is intentional. Surfacing
    the huge interval IS how the user knows it's disabled.
    """
    with tempfile.TemporaryDirectory() as td:
        cfg_path = Path(td) / "x.yaml"
        cfg_path.write_text("services:\n  insight_scanner:\n    interval_hours: 876000\n")
        routines = DaemonServiceDiscoverer(config_path=cfg_path).discover()
    assert len(routines) == 1
    assert routines[0].cadence["interval_seconds"] == 876000 * 3600
```

- [ ] **Step 2: Implement the discoverer**

Append to `shared-vault/skills/daemon/scripts/routine_discovery.py`:

```python


# ---------------------------------------------------------------------------
# DaemonServiceDiscoverer
# ---------------------------------------------------------------------------

import yaml

class DaemonServiceDiscoverer:
    source_kind = "daemon-service"

    def __init__(self, config_path: Path | None = None):
        if config_path is None:
            from src.config.paths import get_project_root
            config_path = get_project_root() / "config" / "system" / "adaptive_loops.yaml"
        self.config_path = config_path

    def discover(self) -> list[Routine]:
        if not self.config_path.exists():
            return []

        try:
            data = yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}
        except Exception as exc:
            logger.warning("DaemonServiceDiscoverer: yaml parse failed: %s", exc)
            return []

        services = data.get("services", {}) or {}
        routines: list[Routine] = []
        for service_id, svc_cfg in services.items():
            interval_seconds = self._extract_interval_seconds(svc_cfg)
            if interval_seconds is None:
                # Service entry with no interval — skip (can't surface a cadence)
                continue

            human_spec = self._humanize_interval(interval_seconds)
            cadence = {
                "type": "interval",
                "spec": human_spec,
                "spec_raw": yaml.safe_dump(svc_cfg, default_flow_style=False).strip(),
                "interval_seconds": interval_seconds,
            }
            cadence["next_run_estimated"] = compute_next_run(cadence)

            routines.append(Routine(
                id=service_id,
                display_name=service_id.replace("_", " ").title(),
                source_kind="daemon-service",
                source_path=f"shared-vault/skills/daemon/scripts/{service_id}.py",
                config_path=f"{self.config_path}#services.{service_id}",
                cadence=cadence,
                status="enabled",  # presence in adaptive_loops.yaml means it's registered
                spawn_kind="python",  # default; DaemonScriptDiscoverer will tag ai-cli-spawn variants
                description=f"Daemon service from adaptive_loops.yaml (cadence: {human_spec})",
                tags=["daemon", "adaptive-loop"],
            ))
        return routines

    @staticmethod
    def _extract_interval_seconds(svc_cfg: dict[str, Any]) -> int | None:
        if "interval_hours" in svc_cfg:
            return int(svc_cfg["interval_hours"]) * 3600
        if "poll_interval_seconds" in svc_cfg:
            return int(svc_cfg["poll_interval_seconds"])
        if "interval_seconds" in svc_cfg:
            return int(svc_cfg["interval_seconds"])
        return None

    @staticmethod
    def _humanize_interval(seconds: int) -> str:
        if seconds >= 3600:
            hours = seconds / 3600
            if hours >= 8760:
                return f"every {int(hours / 8760)}yr"
            return f"every {int(hours)}h"
        if seconds >= 60:
            return f"every {int(seconds / 60)}m"
        return f"every {seconds}s"
```

- [ ] **Step 3: Run tests → verify pass**

Run:
```bash
pytest tests/unit/test_routine_discovery.py -v -k "daemon_service"
```
Expected: 3 tests pass.

- [ ] **Step 4: Commit**

```bash
git add shared-vault/skills/daemon/scripts/routine_discovery.py tests/unit/test_routine_discovery.py
git commit -m "$(cat <<'EOF'
feat(daemon): DaemonServiceDiscoverer — parse adaptive_loops.yaml

Second of 6 discoverers. Reads config/system/adaptive_loops.yaml
services section and emits one Routine per service entry.

Cadence translation:
  - interval_hours: N  → interval_seconds = N × 3600
  - poll_interval_seconds: N → as-is
  - interval_seconds: N → as-is
  - missing → service is skipped (no surfacable cadence)

The 876000-hour disabled pattern (tactical defense from commit
41c7a2509) is preserved verbatim: the routine still appears in
the list with a visible "every 100yr" cadence — that's HOW the
user sees it's disabled.

spawn_kind defaults to "python"; DaemonScriptDiscoverer will
override for services that subprocess.run a Claude CLI.

Three unit tests covering: happy path with 3 services, missing
config file, the 876000 disabled pattern.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: `DaemonScriptDiscoverer` — find scripts that subprocess.run Claude/Codex/Gemini

**Files:**
- Modify: `shared-vault/skills/daemon/scripts/routine_discovery.py` (append)
- Modify: `tests/unit/test_routine_discovery.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_routine_discovery.py`:

```python


# ---------------------------------------------------------------------------
# DaemonScriptDiscoverer
# ---------------------------------------------------------------------------

from skills.daemon.scripts.routine_discovery import DaemonScriptDiscoverer  # noqa: E402


def test_daemon_script_discoverer_finds_ai_cli_spawning_scripts():
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        # Script that spawns Claude (matches the pattern)
        (td_path / "insight_scanner.py").write_text("""
import subprocess
def resolve_cli(config):
    return "/usr/local/bin/claude"
def fire(prompt):
    cli_path = resolve_cli({})
    subprocess.run([cli_path, "--print", "--max-turns", "1", "-p", prompt])
""")
        # Script that does NOT spawn an AI CLI
        (td_path / "log_monitor.py").write_text("""
import logging
def run():
    logging.info("monitoring")
""")
        # Test logs dir (empty — derive_ai_cost will return None)
        logs_dir = td_path / "logs"

        routines = DaemonScriptDiscoverer(scripts_dir=td_path, logs_base_dir=logs_dir).discover()

    assert len(routines) == 1
    r = routines[0]
    assert r.id == "insight_scanner"
    assert r.source_kind == "daemon-script"
    assert r.spawn_kind == "ai-cli-spawn"
    assert r.ai_cost is None  # no logs sampled


def test_daemon_script_discoverer_empty_dir_returns_empty():
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        routines = DaemonScriptDiscoverer(scripts_dir=td_path).discover()
    assert routines == []
```

- [ ] **Step 2: Implement the discoverer**

Append to `shared-vault/skills/daemon/scripts/routine_discovery.py`:

```python


# ---------------------------------------------------------------------------
# DaemonScriptDiscoverer
# ---------------------------------------------------------------------------

import re

_AI_CLI_SPAWN_PATTERN = re.compile(
    r"resolve_cli\(.*?\).*?subprocess\.run\(",
    re.DOTALL,
)

# Conservative estimate of how many spawns one run of these scripts produces.
# insight_scanner spawns ~39 (one per dashboard page); the others spawn 1.
_KNOWN_SPAWN_RATIOS = {
    "insight_scanner": 39,
    "adaptive_loop_executor": 1,
    "ai_monitor_sidecar": 1,
}


class DaemonScriptDiscoverer:
    source_kind = "daemon-script"

    def __init__(self, scripts_dir: Path | None = None, logs_base_dir: Path | None = None):
        if scripts_dir is None:
            from src.config.paths import get_project_root
            scripts_dir = get_project_root() / "shared-vault" / "skills" / "daemon" / "scripts"
        if logs_base_dir is None:
            from src.config.paths import get_logs_dir
            logs_base_dir = get_logs_dir()
        self.scripts_dir = scripts_dir
        self.logs_base_dir = logs_base_dir

    def discover(self) -> list[Routine]:
        if not self.scripts_dir.exists() or not self.scripts_dir.is_dir():
            return []

        routines: list[Routine] = []
        for py_path in sorted(self.scripts_dir.glob("*.py")):
            if py_path.name.startswith("_"):
                continue
            try:
                content = py_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if not _AI_CLI_SPAWN_PATTERN.search(content):
                continue

            routine_id = py_path.stem
            spawns_per_run = _KNOWN_SPAWN_RATIOS.get(routine_id, 1)
            logs_dir = self.logs_base_dir / routine_id

            ai_cost = derive_ai_cost(
                routine_id=routine_id,
                cli="claude",  # default; the resolve_cli() call would let users pick
                logs_dir=logs_dir,
                spawns_per_run=spawns_per_run,
            )

            routines.append(Routine(
                id=routine_id,
                display_name=routine_id.replace("_", " ").title(),
                source_kind="daemon-script",
                source_path=str(py_path),
                config_path=None,
                cadence={"type": "event", "spec": "triggered by daemon-service or other"},
                status="enabled",
                spawn_kind="ai-cli-spawn",
                ai_cost=ai_cost,
                description=f"Script that spawns AI CLI via subprocess.run (estimated {spawns_per_run} spawn(s) per fire)",
                tags=["daemon", "ai-cli-spawn"],
            ))
        return routines
```

- [ ] **Step 3: Run tests → verify pass**

Run:
```bash
pytest tests/unit/test_routine_discovery.py -v -k "daemon_script"
```
Expected: 2 tests pass.

- [ ] **Step 4: Commit**

```bash
git add shared-vault/skills/daemon/scripts/routine_discovery.py tests/unit/test_routine_discovery.py
git commit -m "$(cat <<'EOF'
feat(daemon): DaemonScriptDiscoverer — find scripts that spawn AI CLI

Third of 6 discoverers. Greps shared-vault/skills/daemon/scripts/*.py
for the pattern resolve_cli(...) ... subprocess.run(...) and emits one
Routine per match with spawn_kind="ai-cli-spawn".

Known spawn ratios (used to scale ai_cost.estimated_tokens_per_run):
  - insight_scanner: 39 (one Claude session per dashboard page)
  - adaptive_loop_executor: 1
  - ai_monitor_sidecar: 1

ai_cost is derived from log sampling (Task 2); returns None when
no recent runs exist.

Cadence is "event" — these scripts are invoked transitively by other
services, not on their own schedule. Browse shows them with cadence
"triggered by daemon-service or other" so the user sees they exist
even without a direct fire cadence.

Two unit tests covering: AI-spawning script detected, non-spawning
script skipped.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: `LaunchdAgentDiscoverer` — parse `~/Library/LaunchAgents/com.augur.*.plist`

**Files:**
- Modify: `shared-vault/skills/daemon/scripts/routine_discovery.py` (append)
- Modify: `tests/unit/test_routine_discovery.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_routine_discovery.py`:

```python


# ---------------------------------------------------------------------------
# LaunchdAgentDiscoverer
# ---------------------------------------------------------------------------

from skills.daemon.scripts.routine_discovery import LaunchdAgentDiscoverer  # noqa: E402


def test_launchd_discoverer_parses_run_at_load_plist():
    plist_content = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.augur.daemon</string>
    <key>Program</key>
    <string>/path/to/python3</string>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
"""
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        plist_path = td_path / "com.augur.daemon.plist"
        plist_path.write_text(plist_content)
        routines = LaunchdAgentDiscoverer(plist_glob_root=td_path, glob_pattern="com.augur.*.plist").discover()

    assert len(routines) == 1
    r = routines[0]
    assert r.id == "com.augur.daemon"
    assert r.source_kind == "launchd-agent"
    assert r.cadence["type"] == "logon"  # RunAtLoad maps to logon
    assert r.spawn_kind == "python"


def test_launchd_discoverer_parses_start_interval_plist():
    plist_content = """<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.augur.example</string>
    <key>Program</key>
    <string>/bin/echo</string>
    <key>StartInterval</key>
    <integer>3600</integer>
</dict>
</plist>
"""
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        (td_path / "com.augur.example.plist").write_text(plist_content)
        routines = LaunchdAgentDiscoverer(plist_glob_root=td_path, glob_pattern="com.augur.*.plist").discover()
    assert len(routines) == 1
    assert routines[0].cadence["type"] == "interval"
    assert routines[0].cadence["interval_seconds"] == 3600


def test_launchd_discoverer_missing_dir_returns_empty():
    routines = LaunchdAgentDiscoverer(plist_glob_root=Path("/nonexistent")).discover()
    assert routines == []


def test_launchd_discoverer_malformed_plist_skipped():
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        (td_path / "com.augur.bad.plist").write_text("not valid xml")
        routines = LaunchdAgentDiscoverer(plist_glob_root=td_path, glob_pattern="com.augur.*.plist").discover()
    assert routines == []
```

- [ ] **Step 2: Implement the discoverer**

Append to `shared-vault/skills/daemon/scripts/routine_discovery.py`:

```python


# ---------------------------------------------------------------------------
# LaunchdAgentDiscoverer
# ---------------------------------------------------------------------------

import plistlib

class LaunchdAgentDiscoverer:
    source_kind = "launchd-agent"

    def __init__(self, plist_glob_root: Path | None = None, glob_pattern: str = "com.augur.*.plist"):
        if plist_glob_root is None:
            plist_glob_root = Path.home() / "Library" / "LaunchAgents"
        self.plist_glob_root = plist_glob_root
        self.glob_pattern = glob_pattern

    def discover(self) -> list[Routine]:
        if not self.plist_glob_root.exists() or not self.plist_glob_root.is_dir():
            return []

        routines: list[Routine] = []
        for plist_path in sorted(self.plist_glob_root.glob(self.glob_pattern)):
            try:
                with plist_path.open("rb") as f:
                    plist = plistlib.load(f)
            except Exception as exc:
                logger.warning("LaunchdAgentDiscoverer: skipping malformed %s: %s", plist_path, exc)
                continue

            label = plist.get("Label") or plist_path.stem
            program = plist.get("Program") or (plist.get("ProgramArguments") or [""])[0]
            cadence = self._extract_cadence(plist)
            cadence["next_run_estimated"] = compute_next_run(cadence)

            routines.append(Routine(
                id=label,
                display_name=label,
                source_kind="launchd-agent",
                source_path=str(plist_path),
                config_path=str(plist_path),
                cadence=cadence,
                status="enabled",
                spawn_kind="python" if "python" in str(program).lower() else "bash",
                description=f"macOS launchd agent (Program: {program})",
                tags=["launchd"],
            ))
        return routines

    @staticmethod
    def _extract_cadence(plist: dict) -> dict[str, Any]:
        if plist.get("RunAtLoad"):
            return {"type": "logon", "spec": "on logon", "spec_raw": "RunAtLoad: true"}
        if "StartInterval" in plist:
            secs = int(plist["StartInterval"])
            return {
                "type": "interval",
                "spec": f"every {secs}s" if secs < 3600 else f"every {secs // 3600}h",
                "spec_raw": f"StartInterval: {secs}",
                "interval_seconds": secs,
            }
        if "StartCalendarInterval" in plist:
            cal = plist["StartCalendarInterval"]
            return {"type": "cron", "spec": str(cal), "spec_raw": str(cal)}
        return {"type": "event", "spec": "no trigger specified", "spec_raw": ""}
```

- [ ] **Step 3: Run tests → verify pass**

Run:
```bash
pytest tests/unit/test_routine_discovery.py -v -k "launchd"
```
Expected: 4 tests pass.

- [ ] **Step 4: Commit**

```bash
git add shared-vault/skills/daemon/scripts/routine_discovery.py tests/unit/test_routine_discovery.py
git commit -m "$(cat <<'EOF'
feat(daemon): LaunchdAgentDiscoverer — parse macOS LaunchAgent plists

Fourth of 6 discoverers. Scans ~/Library/LaunchAgents/com.augur.*.plist
files and emits one Routine per agent.

Cadence translation:
  - RunAtLoad: true       → cadence.type = "logon"
  - StartInterval: N      → cadence.type = "interval", interval_seconds = N
  - StartCalendarInterval → cadence.type = "cron"
  - none of the above     → cadence.type = "event"

spawn_kind heuristic: "python" if Program path contains "python",
else "bash".

Malformed plist files are skipped with a warning (fail-soft per
spec §10).

Four unit tests covering: RunAtLoad, StartInterval, missing dir,
malformed plist.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: `GitHubActionsDiscoverer` — parse `.github/workflows/*.yml` with `on.schedule`

**Files:**
- Modify: `shared-vault/skills/daemon/scripts/routine_discovery.py` (append)
- Modify: `tests/unit/test_routine_discovery.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_routine_discovery.py`:

```python


# ---------------------------------------------------------------------------
# GitHubActionsDiscoverer
# ---------------------------------------------------------------------------

from skills.daemon.scripts.routine_discovery import GitHubActionsDiscoverer  # noqa: E402


def test_github_actions_discoverer_finds_scheduled_workflows():
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        wf_dir = td_path / "workflows"
        wf_dir.mkdir()
        (wf_dir / "nightly.yml").write_text("""
name: Nightly checks
on:
  schedule:
    - cron: '0 3 * * *'
jobs:
  check: { runs-on: ubuntu-latest, steps: [run: echo hi] }
""")
        (wf_dir / "ci.yml").write_text("""
name: CI on push
on:
  push:
    branches: [main]
jobs:
  test: { runs-on: ubuntu-latest, steps: [run: pytest] }
""")
        routines = GitHubActionsDiscoverer(workflows_dir=wf_dir).discover()

    assert len(routines) == 1
    r = routines[0]
    assert r.source_kind == "github-action"
    assert r.cadence["type"] == "cron"
    assert "0 3 * * *" in r.cadence["spec_raw"]


def test_github_actions_discoverer_missing_dir_returns_empty():
    routines = GitHubActionsDiscoverer(workflows_dir=Path("/nonexistent")).discover()
    assert routines == []
```

- [ ] **Step 2: Implement the discoverer**

Append to `shared-vault/skills/daemon/scripts/routine_discovery.py`:

```python


# ---------------------------------------------------------------------------
# GitHubActionsDiscoverer
# ---------------------------------------------------------------------------

class GitHubActionsDiscoverer:
    source_kind = "github-action"

    def __init__(self, workflows_dir: Path | None = None):
        if workflows_dir is None:
            from src.config.paths import get_project_root
            workflows_dir = get_project_root() / ".github" / "workflows"
        self.workflows_dir = workflows_dir

    def discover(self) -> list[Routine]:
        if not self.workflows_dir.exists() or not self.workflows_dir.is_dir():
            return []

        routines: list[Routine] = []
        for yml_path in sorted(self.workflows_dir.glob("*.yml")):
            try:
                data = yaml.safe_load(yml_path.read_text(encoding="utf-8")) or {}
            except Exception as exc:
                logger.warning("GitHubActionsDiscoverer: skipping malformed %s: %s", yml_path, exc)
                continue

            on = data.get("on") or data.get(True)  # YAML "on:" parses as bool True
            if not isinstance(on, dict):
                continue
            schedules = on.get("schedule") or []
            if not schedules:
                continue

            for sched in schedules:
                cron_expr = sched.get("cron") if isinstance(sched, dict) else None
                if not cron_expr:
                    continue
                routine_id = f"{yml_path.stem}-{cron_expr.replace(' ', '_')}"
                cadence = {
                    "type": "cron",
                    "spec": cron_expr,
                    "spec_raw": f"cron: '{cron_expr}'",
                }
                cadence["next_run_estimated"] = None  # cron estimation deferred

                routines.append(Routine(
                    id=routine_id,
                    display_name=data.get("name") or yml_path.stem,
                    source_kind="github-action",
                    source_path=str(yml_path),
                    config_path=str(yml_path),
                    cadence=cadence,
                    status="enabled",
                    spawn_kind="http-action",
                    description=f"GitHub Actions scheduled workflow ({cron_expr})",
                    tags=["github-actions", "ci"],
                ))
        return routines
```

- [ ] **Step 3: Run tests → verify pass**

Run:
```bash
pytest tests/unit/test_routine_discovery.py -v -k "github_actions"
```
Expected: 2 tests pass.

- [ ] **Step 4: Commit**

```bash
git add shared-vault/skills/daemon/scripts/routine_discovery.py tests/unit/test_routine_discovery.py
git commit -m "$(cat <<'EOF'
feat(daemon): GitHubActionsDiscoverer — parse .github/workflows cron triggers

Fifth of 6 discoverers. Scans .github/workflows/*.yml and emits one
Routine per workflow that has an on.schedule.*.cron trigger.

Note: PyYAML parses YAML "on:" as Python True (boolean key, due to YAML
1.1 spec). Discoverer handles both `data["on"]` and `data[True]` for
robustness.

cadence.type is "cron" for all GitHub Actions; next_run_estimated is
None per spec §10 (cron estimation deferred for v1). The spec field
holds the raw cron expression.

spawn_kind is "http-action" (workflows run on GitHub-hosted runners,
not on this machine, but they're still autonomous triggers worth
surfacing).

Two unit tests covering: scheduled workflow found, push-only workflow
skipped.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: `McpBackgroundDiscoverer` — placeholder for v1

**Files:**
- Modify: `shared-vault/skills/daemon/scripts/routine_discovery.py` (append)
- Modify: `tests/unit/test_routine_discovery.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_routine_discovery.py`:

```python


# ---------------------------------------------------------------------------
# McpBackgroundDiscoverer
# ---------------------------------------------------------------------------

from skills.daemon.scripts.routine_discovery import McpBackgroundDiscoverer  # noqa: E402


def test_mcp_background_discoverer_returns_empty_v1():
    """v1 placeholder — no MCP background tasks are registered yet."""
    routines = McpBackgroundDiscoverer().discover()
    assert routines == []
```

- [ ] **Step 2: Implement the placeholder**

Append to `shared-vault/skills/daemon/scripts/routine_discovery.py`:

```python


# ---------------------------------------------------------------------------
# McpBackgroundDiscoverer (placeholder for v1)
# ---------------------------------------------------------------------------

class McpBackgroundDiscoverer:
    """Placeholder discoverer — reserved for when MCP servers register
    background tasks. Returns empty list for v1 per spec §5.1.
    """
    source_kind = "mcp-background"

    def discover(self) -> list[Routine]:
        return []
```

- [ ] **Step 3: Run test → verify pass**

Run:
```bash
pytest tests/unit/test_routine_discovery.py::test_mcp_background_discoverer_returns_empty_v1 -v
```
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add shared-vault/skills/daemon/scripts/routine_discovery.py tests/unit/test_routine_discovery.py
git commit -m "$(cat <<'EOF'
feat(daemon): McpBackgroundDiscoverer — v1 placeholder

Sixth of 6 discoverers. Returns empty list for v1.

Reserved for when MCP servers register background tasks; the class
exists so DISCOVERERS aggregator (next task) has all 6 entries today
without conditional logic. Adding actual MCP background discovery
is a follow-on when the use case arises.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: `discover_all_routines()` aggregator — fail-soft over all 6 discoverers

**Files:**
- Modify: `shared-vault/skills/daemon/scripts/routine_discovery.py` (append)
- Modify: `tests/unit/test_routine_discovery.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_routine_discovery.py`:

```python


# ---------------------------------------------------------------------------
# discover_all_routines aggregator
# ---------------------------------------------------------------------------

from skills.daemon.scripts.routine_discovery import discover_all_routines, DISCOVERERS  # noqa: E402


def test_discover_all_routines_aggregates_all_six():
    assert len(DISCOVERERS) == 6
    source_kinds = {d.source_kind for d in DISCOVERERS}
    assert source_kinds == SOURCE_KINDS


def test_discover_all_routines_fail_soft_on_discoverer_exception():
    class BrokenDiscoverer:
        source_kind = "broken"
        def discover(self):
            raise RuntimeError("simulated failure")

    class GoodDiscoverer:
        source_kind = "good"
        def discover(self):
            return [Routine(
                id="x", display_name="X", source_kind="good",
                source_path="/p", cadence={"type": "interval", "spec": "every 1h", "interval_seconds": 3600},
                status="enabled", spawn_kind="python",
            )]

    with patch("skills.daemon.scripts.routine_discovery.DISCOVERERS", [BrokenDiscoverer(), GoodDiscoverer()]):
        result = discover_all_routines()

    # Broken discoverer failed; good discoverer's routines still returned
    assert len(result) == 1
    assert result[0].id == "x"
```

- [ ] **Step 2: Implement the aggregator**

Append to `shared-vault/skills/daemon/scripts/routine_discovery.py`:

```python


# ---------------------------------------------------------------------------
# Aggregator
# ---------------------------------------------------------------------------

DISCOVERERS: list[RoutineDiscoverer] = [
    PerSkillScheduleDiscoverer(),
    DaemonServiceDiscoverer(),
    DaemonScriptDiscoverer(),
    LaunchdAgentDiscoverer(),
    GitHubActionsDiscoverer(),
    McpBackgroundDiscoverer(),
]


def discover_all_routines() -> list[Routine]:
    """Aggregate routines from all 6 source-kind discoverers.

    Fail-soft per spec §10: a discoverer that raises is logged and skipped;
    the aggregate still returns whatever other discoverers found. Partial
    results are useful; failing-loud across the whole list would hide
    routines from the user.
    """
    routines: list[Routine] = []
    for d in DISCOVERERS:
        try:
            found = d.discover()
            routines.extend(found)
        except Exception as exc:
            logger.warning("discoverer %s failed: %s", d.source_kind, exc, exc_info=True)
    return routines
```

- [ ] **Step 3: Run tests → verify pass**

Run:
```bash
pytest tests/unit/test_routine_discovery.py -v
```
Expected: all tests pass (~26 total).

- [ ] **Step 4: Real-machine smoke test**

Run:
```bash
python3 << 'PY'
import sys
sys.path.insert(0, '.')
sys.path.insert(0, 'shared-vault')
from skills.daemon.scripts.routine_discovery import discover_all_routines
routines = discover_all_routines()
print(f"Discovered {len(routines)} routines on this machine")
from collections import Counter
by_kind = Counter(r.source_kind for r in routines)
for kind, count in sorted(by_kind.items()):
    print(f"  {kind}: {count}")
# At least insight_scanner should appear (in daemon-service AND daemon-script)
ids = [r.id for r in routines]
print(f"insight_scanner appearances: {ids.count('insight_scanner')}")
PY
```
Expected: ≥1 routine per source kind that has real data on this machine (daemon-service, daemon-script, launchd-agent, github-action at minimum). `insight_scanner` should appear twice (once as `daemon-service`, once as `daemon-script`).

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/daemon/scripts/routine_discovery.py tests/unit/test_routine_discovery.py
git commit -m "$(cat <<'EOF'
feat(daemon): discover_all_routines aggregator — fail-soft over 6 discoverers

The hub of the module. DISCOVERERS is a flat list of the 6 source-kind
discoverer instances; discover_all_routines() loops over them and
extends a result list, catching per-discoverer exceptions and logging
them as warnings without aborting.

Fail-soft is intentional (spec §10): a single discoverer failing
(e.g., malformed launchd plist, yaml parse error in a workflow file)
must NOT hide every other routine from the user. Partial results are
useful; the broken kind shows as "no entries" in the UI rather than
the whole page erroring.

Two unit tests covering: all 6 discoverers registered, exception in
one doesn't break the others.

End of C1. Next: list-routines MCP tool (Task 10) so the dashboard
can consume this.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: `list-routines` MCP tool + mtime cache

**Files:**
- Create: `shared-vault/skills/daemon/scripts/mcp/__init__.py` (if it doesn't exist)
- Create: `shared-vault/skills/daemon/scripts/mcp/routine_tools.py`
- Create: `tests/unit/test_list_routines_mcp.py`

- [ ] **Step 1: Check whether `mcp/` package exists**

Run:
```bash
ls -la shared-vault/skills/daemon/scripts/mcp/ 2>&1 | head -5
```

If the dir doesn't exist, create it with an empty `__init__.py`:
```bash
mkdir -p shared-vault/skills/daemon/scripts/mcp
touch shared-vault/skills/daemon/scripts/mcp/__init__.py
```

- [ ] **Step 2: Write the tests first**

Write to `tests/unit/test_list_routines_mcp.py`:

```python
"""Unit tests for the list-routines MCP tool."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import patch

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "shared-vault"))

from skills.daemon.scripts.routine_discovery import Routine  # noqa: E402
from skills.daemon.scripts.mcp.routine_tools import list_routines, _cache_clear  # noqa: E402


def _r(**kwargs):
    """Build a Routine with sensible defaults."""
    defaults = dict(
        id="r1", display_name="R1", source_kind="daemon-service",
        source_path="/p", cadence={"type": "interval", "spec": "every 1h"},
        status="enabled", spawn_kind="python",
    )
    defaults.update(kwargs)
    return Routine(**defaults)


def test_list_routines_returns_all_when_no_filters():
    fake = [
        _r(id="a", source_kind="daemon-service"),
        _r(id="b", source_kind="per-skill-schedule"),
    ]
    _cache_clear()
    with patch("skills.daemon.scripts.mcp.routine_tools._fresh_discover", return_value=fake):
        result_json = asyncio.run(list_routines())

    result = json.loads(result_json)
    assert result["success"] is True
    assert len(result["routines"]) == 2


def test_list_routines_filters_by_source_kind():
    fake = [
        _r(id="a", source_kind="daemon-service"),
        _r(id="b", source_kind="per-skill-schedule"),
    ]
    _cache_clear()
    with patch("skills.daemon.scripts.mcp.routine_tools._fresh_discover", return_value=fake):
        result = json.loads(asyncio.run(list_routines(source_kind="daemon-service")))

    assert len(result["routines"]) == 1
    assert result["routines"][0]["id"] == "a"


def test_list_routines_filters_by_spawn_kind():
    fake = [
        _r(id="a", spawn_kind="ai-cli-spawn"),
        _r(id="b", spawn_kind="python"),
    ]
    _cache_clear()
    with patch("skills.daemon.scripts.mcp.routine_tools._fresh_discover", return_value=fake):
        result = json.loads(asyncio.run(list_routines(spawn_kind="ai-cli-spawn")))

    assert len(result["routines"]) == 1
    assert result["routines"][0]["id"] == "a"


def test_list_routines_cached_within_ttl():
    fake_first = [_r(id="first")]
    fake_second = [_r(id="second")]
    _cache_clear()
    with patch("skills.daemon.scripts.mcp.routine_tools._fresh_discover", return_value=fake_first):
        first = json.loads(asyncio.run(list_routines()))
        assert first["routines"][0]["id"] == "first"
        # Second call within TTL — should hit the cache, NOT call _fresh_discover again
        with patch("skills.daemon.scripts.mcp.routine_tools._fresh_discover", return_value=fake_second):
            second = json.loads(asyncio.run(list_routines()))
            assert second["routines"][0]["id"] == "first"  # still first — cache hit
```

- [ ] **Step 3: Implement the MCP tool**

Write to `shared-vault/skills/daemon/scripts/mcp/routine_tools.py`:

```python
"""list-routines MCP tool — Browse-page data source for ADR-727.

Exposes discover_all_routines() through the MCP surface with filters and
a 60-second TTL cache (mtime invalidation deferred to a follow-on).
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict
from typing import Any

from skills.daemon.scripts.routine_discovery import (
    Routine,
    discover_all_routines,
)

# 60-second cache TTL per spec §6
_CACHE_TTL_SECONDS = 60
_cache: dict[str, Any] = {"routines": None, "fetched_at": 0.0}


def _cache_clear() -> None:
    """Clear the cache — used in tests."""
    _cache["routines"] = None
    _cache["fetched_at"] = 0.0


def _fresh_discover() -> list[Routine]:
    """Indirection so tests can monkeypatch the discovery layer."""
    return discover_all_routines()


def _get_routines_cached() -> list[Routine]:
    now = time.time()
    if _cache["routines"] is not None and (now - _cache["fetched_at"]) < _CACHE_TTL_SECONDS:
        return _cache["routines"]
    routines = _fresh_discover()
    _cache["routines"] = routines
    _cache["fetched_at"] = now
    return routines


async def list_routines(
    source_kind: str = "",
    spawn_kind: str = "",
    status: str = "",
) -> str:
    """List background routines, optionally filtered.

    Args:
        source_kind: filter to one source_kind, or empty for all
        spawn_kind:  filter to one spawn_kind, or empty for all
        status:      filter to one status, or empty for all

    Returns JSON-encoded {"success": true, "routines": [...]}.
    """
    routines = _get_routines_cached()
    if source_kind:
        routines = [r for r in routines if r.source_kind == source_kind]
    if spawn_kind:
        routines = [r for r in routines if r.spawn_kind == spawn_kind]
    if status:
        routines = [r for r in routines if r.status == status]

    return json.dumps(
        {"success": True, "routines": [asdict(r) for r in routines]},
        indent=2,
        default=str,
    )
```

- [ ] **Step 4: Register the tool with the MCP server**

Find where other daemon MCP tools are registered. Run:
```bash
grep -rln "register_daemon_tools\|daemon.*mcp.*tool" shared-vault/skills/daemon --include="*.py" 2>/dev/null | head -5
```

If a registration entry point exists (e.g., `daemon/scripts/mcp/__init__.py: register_*`), append `list_routines` to it. If not, the tool will be picked up by the MCP server's dynamic discovery via the @mcp.tool decorator pattern used by other daemon tools — in that case, wrap `list_routines` with the decorator. Sample wrapper if needed:

```python
# At top of routine_tools.py — add the decorator boilerplate that matches
# how shared-vault/skills/daemon/scripts/mcp/*.py registers other tools.
# (Pattern: see how schedule_executor exposes itself.) If no decorator
# convention exists in this skill, leave list_routines as a plain async
# function — the MCP server discovers it from the module's exports.
```

- [ ] **Step 5: Run tests → verify pass**

Run:
```bash
pytest tests/unit/test_list_routines_mcp.py -v
```
Expected: 4 tests pass.

- [ ] **Step 6: Commit**

```bash
git add shared-vault/skills/daemon/scripts/mcp/__init__.py shared-vault/skills/daemon/scripts/mcp/routine_tools.py tests/unit/test_list_routines_mcp.py
git commit -m "$(cat <<'EOF'
feat(daemon): list-routines MCP tool + 60s cache

The Browse page's data source for the new background-routines
category. Wraps discover_all_routines() with three filters
(source_kind, spawn_kind, status) and a 60-second TTL cache to
avoid hitting the filesystem on every Browse poll.

The cache is in-process. mtime-based invalidation (spec §6) is
deferred to a follow-on — for v1 a 60s TTL is sufficient since
the Browse page polls at human-driven frequency, not high-rate.

_fresh_discover() and _cache_clear() helpers are exposed for
test monkeypatching.

Four unit tests: no filters, source_kind filter, spawn_kind
filter, cache TTL behavior.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: `capability_exposure.yaml` — register `list-routines`

**Files:**
- Modify: `config/system/capability_exposure.yaml`

- [ ] **Step 1: Verify location and read existing entries**

Run:
```bash
grep -n "mcp-tool:" config/system/capability_exposure.yaml | head -5
```

- [ ] **Step 2: Add the entry**

Find an existing daemon MCP tool entry (e.g., `mcp-tool:get-daemon-loop-status`) and add `mcp-tool:list-routines` alongside it. Use Edit on `config/system/capability_exposure.yaml`:

Find:
```yaml
  mcp-tool:get-daemon-loop-status:
```

Add immediately above:
```yaml
  mcp-tool:list-routines:
    type: mcp-tool
    owner_kind: skill
    skill: daemon
    management: read-only
    scope: machine
    primary_surface: mcp via dashboard
    preferred_client: dashboard
    export_to: [mcp]
    description: "List all background routines on this machine (per-skill schedules, daemon services, daemon scripts, launchd agents, GitHub Actions cron, MCP background tasks) for the Browse > Background Routines page."
  mcp-tool:get-daemon-loop-status:
```

- [ ] **Step 3: Verify it's parseable**

Run:
```bash
python3 -c "
import yaml
with open('config/system/capability_exposure.yaml') as f:
    data = yaml.safe_load(f)
caps = data.get('capabilities', data)
assert any('list-routines' in k for k in caps), 'list-routines not found in capability_exposure.yaml'
print('OK')
"
```
Expected: `OK`.

- [ ] **Step 4: Commit**

```bash
git add config/system/capability_exposure.yaml
git commit -m "$(cat <<'EOF'
chore(config): register list-routines in capability_exposure.yaml

Exposes the new MCP tool to the dashboard surface. Marked
read-only and scoped to "machine" (results are per-host).
export_to: [mcp] means it ships via the MCP transport surface.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: `routine-format.ts` UI helpers + Vitest tests

**Files:**
- Create: `apps/dashboard/lib/browse/routine-format.ts`
- Create: `apps/dashboard/lib/browse/__tests__/routine-format.test.ts`

- [ ] **Step 1: Create the helper module**

Write to `apps/dashboard/lib/browse/routine-format.ts`:

```typescript
/**
 * Background-routine formatting helpers (ADR-727).
 *
 * Reused across card, table, detail panel, and description-line surfaces.
 * Pure functions — no React, no DOM, no side effects.
 */

interface Cadence {
  type: "interval" | "cron" | "event" | "manual" | "logon";
  spec: string;
  spec_raw?: string;
  next_run_estimated?: string | null;
  interval_seconds?: number;
}

/** Format a Routine.cadence into a one-line human string. */
export function formatCadence(c: Cadence): string {
  if (c.type === "manual" || c.type === "event") return c.spec;
  if (c.type === "logon") return "on logon";
  // interval and cron: spec is already human-ready from the discoverer
  return c.spec;
}

/** Format an ISO-8601 timestamp into a relative time. */
export function formatRelativeTime(iso: string | null | undefined): string {
  if (!iso) return "never";
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "never";
  const diff = Date.now() - t;
  if (diff < 0) return "just now"; // future timestamp
  if (diff < 60_000) return "just now";
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
  return `${Math.floor(diff / 86_400_000)}d ago`;
}

/** Token count → "250K" / "1.2M" / "100" */
export function humanizeTokens(n: number | null | undefined): string {
  if (n == null) return "—";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${Math.round(n / 1_000)}K`;
  return String(n);
}
```

- [ ] **Step 2: Write Vitest tests**

Write to `apps/dashboard/lib/browse/__tests__/routine-format.test.ts`:

```typescript
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { formatCadence, formatRelativeTime, humanizeTokens } from "../routine-format";

describe("formatCadence", () => {
  it("returns spec for interval type", () => {
    expect(formatCadence({ type: "interval", spec: "every 12h" })).toBe("every 12h");
  });
  it("returns spec for cron type", () => {
    expect(formatCadence({ type: "cron", spec: "0 3 * * *" })).toBe("0 3 * * *");
  });
  it("returns 'on logon' for logon type", () => {
    expect(formatCadence({ type: "logon", spec: "any" })).toBe("on logon");
  });
  it("returns spec for event/manual", () => {
    expect(formatCadence({ type: "event", spec: "triggered by other" })).toBe("triggered by other");
    expect(formatCadence({ type: "manual", spec: "once at 09:00" })).toBe("once at 09:00");
  });
});

describe("formatRelativeTime", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-05-11T10:00:00Z"));
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns 'never' for null/undefined/empty", () => {
    expect(formatRelativeTime(null)).toBe("never");
    expect(formatRelativeTime(undefined)).toBe("never");
    expect(formatRelativeTime("")).toBe("never");
  });
  it("returns 'never' for invalid date", () => {
    expect(formatRelativeTime("not-a-date")).toBe("never");
  });
  it("returns 'just now' for < 1 minute ago", () => {
    expect(formatRelativeTime("2026-05-11T09:59:30Z")).toBe("just now");
  });
  it("returns minutes for < 1 hour ago", () => {
    expect(formatRelativeTime("2026-05-11T09:30:00Z")).toBe("30m ago");
  });
  it("returns hours for < 1 day ago", () => {
    expect(formatRelativeTime("2026-05-11T05:00:00Z")).toBe("5h ago");
  });
  it("returns days for >= 1 day ago", () => {
    expect(formatRelativeTime("2026-05-08T10:00:00Z")).toBe("3d ago");
  });
});

describe("humanizeTokens", () => {
  it("returns '—' for null/undefined", () => {
    expect(humanizeTokens(null)).toBe("—");
    expect(humanizeTokens(undefined)).toBe("—");
  });
  it("returns raw number for < 1000", () => {
    expect(humanizeTokens(42)).toBe("42");
  });
  it("returns K-suffixed for thousands", () => {
    expect(humanizeTokens(250_000)).toBe("250K");
    expect(humanizeTokens(1_500)).toBe("2K"); // rounds
  });
  it("returns M-suffixed for millions", () => {
    expect(humanizeTokens(2_500_000)).toBe("2.5M");
  });
});
```

- [ ] **Step 3: Run the tests**

Run from the dashboard directory (or use the project's test command):
```bash
cd apps/dashboard && pnpm test routine-format
```

If Vitest isn't configured here yet, run via the project's root test command:
```bash
pnpm --filter dashboard test routine-format
```

Expected: ~14 tests pass.

- [ ] **Step 4: Commit**

```bash
cd ~/Projects/Augur
git add apps/dashboard/lib/browse/routine-format.ts apps/dashboard/lib/browse/__tests__/routine-format.test.ts
git commit -m "$(cat <<'EOF'
feat(dashboard): routine-format.ts helpers — formatCadence,
formatRelativeTime, humanizeTokens

Pure-function helpers reused across card / table / detail-panel /
description-line surfaces per spec §7.7. No React, no DOM, no side
effects — testable as plain TypeScript.

Behaviors:
  formatCadence:
    - interval/cron: returns spec (already human-ready from server)
    - logon: returns "on logon"
    - event/manual: returns spec

  formatRelativeTime:
    - null/undefined/empty/invalid: "never"
    - < 1m: "just now"
    - < 1h: "Xm ago"
    - < 1d: "Xh ago"
    - >= 1d: "Xd ago"

  humanizeTokens:
    - null/undefined: "—"
    - < 1000: raw string
    - >= 1000: "XK"
    - >= 1M: "X.YM"

~14 Vitest tests covering each branch.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: `types.ts` — rename Browse category + ViewMode

**Files:**
- Modify: `apps/dashboard/lib/browse/types.ts`

- [ ] **Step 1: Update ViewMode union**

Use Edit. Find:

```typescript
  | "scheduled-executions"
```

Replace with:

```typescript
  | "background-routines"
```

- [ ] **Step 2: Update BROWSE_CATEGORIES**

Use Edit. Find:

```typescript
  { id: "scheduled-executions", label: "Scheduled Executions", singularLabel: "Scheduled Execution", icon: "Clock3", devOnly: false, group: "system", viewLayout: "table" },
```

Replace with:

```typescript
  { id: "background-routines", label: "Background Routines", singularLabel: "Routine", icon: "Activity", devOnly: false, group: "system", viewLayout: "table" },
```

- [ ] **Step 3: Add a type alias for the renamed detail interface**

Find:
```typescript
export interface ScheduledExecutionDetail {
```

Immediately AFTER the closing brace of `ScheduledExecutionDetail`, add (within one release — removed in the next):

```typescript

/**
 * @deprecated Use Routine instead. Alias preserved for one release per
 * CLAUDE.md rule 14; removed in the release after ADR-727 ships.
 */
export type Routine = ScheduledExecutionDetail;
```

(This is a temporary type alias. The full schema migration to a proper `Routine` interface that matches the Python `Routine` dataclass is deliberately deferred — for v1 the dashboard reads the JSON and treats it via the existing `ScheduledExecutionDetail` shape, just with renamed display. The Python side is the canonical schema.)

- [ ] **Step 4: Verify TypeScript still compiles**

Run from project root:
```bash
cd apps/dashboard && pnpm exec tsc --noEmit 2>&1 | head -20
```
Expected: no new errors introduced (existing errors are unrelated).

- [ ] **Step 5: Commit**

```bash
cd ~/Projects/Augur
git add apps/dashboard/lib/browse/types.ts
git commit -m "$(cat <<'EOF'
refactor(dashboard): rename Browse category scheduled-executions → background-routines

Spec §7.1 + §8 migration:

  ViewMode union:
    - "scheduled-executions"  (REMOVED — replaced by below)
    + "background-routines"

  BROWSE_CATEGORIES entry:
    - id: scheduled-executions, label: "Scheduled Executions",
      icon: Clock3
    + id: background-routines,   label: "Background Routines",
      icon: Activity

  Type alias (one-release shim per CLAUDE.md rule 14):
    + export type Routine = ScheduledExecutionDetail  // deprecated

Removed in the release immediately after this one. URL redirect
shim (Task 17) lets the old ?category=scheduled-executions URL
continue to work for one release.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 14: `transforms.ts` — case rename + first-class description line

**Files:**
- Modify: `apps/dashboard/lib/browse/transforms.ts`

- [ ] **Step 1: Identify the three case branches that handle scheduled-executions**

Run:
```bash
grep -n '"scheduled-executions"' apps/dashboard/lib/browse/transforms.ts
```

Expected: 3 line numbers (per the earlier session: primary-action, actions, typeBadge, and description case).

- [ ] **Step 2: Rename every `"scheduled-executions"` → `"background-routines"` in the transforms file**

Use Edit with replace_all on `apps/dashboard/lib/browse/transforms.ts`:

Find: `"scheduled-executions"`
Replace with: `"background-routines"`
(replace_all: true)

- [ ] **Step 3: Update the description-line composition for the new category**

Find the case branch that builds the description for the routines category (it has the existing `schedule + description + status` join). Replace its body with the new first-class composition per spec §7.6.

Find (something like):
```typescript
    case "background-routines": {
      const schedule = entry.metadata?.schedule || "";
      const status = entry.metadata?.status || "";
      description = [schedule, entry.description || "", status].filter(Boolean).join(" · ");
      break;
    }
```

Replace with:
```typescript
    case "background-routines": {
      // Spec §7.6: cadence + last-run lead the description line.
      const cadenceSpec = entry.metadata?.cadence?.spec || entry.metadata?.schedule || "";
      const lastRunIso = entry.metadata?.last_run_at || null;
      const sourceKind = entry.metadata?.source_kind || "";
      const aiCostDay = entry.metadata?.ai_cost?.estimated_tokens_per_day;
      const status = entry.metadata?.status || "";

      // Lazy-import the helpers to avoid pulling them into every transform path.
      const { formatRelativeTime, humanizeTokens } = await import("./routine-format");

      const costSeg = aiCostDay != null ? `${humanizeTokens(aiCostDay)} tokens/day` : null;

      description = [
        cadenceSpec,                                  // 1st: cadence (always)
        `last: ${formatRelativeTime(lastRunIso)}`,     // 2nd: last run (always)
        sourceKind,
        costSeg,
        status,
      ].filter(Boolean).join(" · ");
      break;
    }
```

Note: if the transform function isn't already async, this change requires making it async (or doing a sync import at the top of the file). The simpler approach: import at the top of transforms.ts:

```typescript
import { formatRelativeTime, humanizeTokens } from "./routine-format";
```

…and use synchronously inside the case. Pick whichever fits the existing file's import style. If async transforms aren't supported, use the sync top-level import.

- [ ] **Step 4: Verify TypeScript compiles**

Run:
```bash
cd apps/dashboard && pnpm exec tsc --noEmit 2>&1 | head -20
```
Expected: no new errors.

- [ ] **Step 5: Commit**

```bash
cd ~/Projects/Augur
git add apps/dashboard/lib/browse/transforms.ts
git commit -m "$(cat <<'EOF'
refactor(dashboard): transforms case rename + first-class cadence/last-run

  Three case branches renamed: scheduled-executions → background-routines
  (primary-action, card actions, type badge, description).

  Description line rebuilt per spec §7.6: cadence + last-run lead,
  followed by source_kind / cost / status. Pulls in
  formatRelativeTime + humanizeTokens from routine-format.ts so
  display is consistent across all surfaces.

  No business-logic change — only rendering. The MCP data shape
  is unchanged because the existing ScheduledExecutionDetail
  interface already covers the fields we need; richer Routine
  schema in the JSON is read directly by the card/table/detail
  components as needed.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 15: `BackgroundRoutineDetailPanel.tsx` — 2-column Cadence/Last-Run layout

**Files:**
- Create: `apps/dashboard/components/shared/BackgroundRoutineDetailPanel.tsx`
- (Existing `ScheduledExecutionDetailPanel.tsx` left in place for one release; the new panel is wired in by Task 17.)

- [ ] **Step 1: Read the existing panel for the import surface**

Run:
```bash
head -30 apps/dashboard/components/shared/ScheduledExecutionDetailPanel.tsx
```

- [ ] **Step 2: Write the new panel**

Write to `apps/dashboard/components/shared/BackgroundRoutineDetailPanel.tsx`:

```tsx
"use client";

import { GlassCard } from "@/components/ui/GlassCard";
import { Badge } from "@/components/ui/badge";
import { formatCadence, formatRelativeTime, humanizeTokens } from "@/lib/browse/routine-format";

interface AiCost {
  cli: string;
  estimated_tokens_per_run?: number;
  estimated_runs_per_day?: number;
  estimated_tokens_per_day?: number;
}

interface Cadence {
  type: "interval" | "cron" | "event" | "manual" | "logon";
  spec: string;
  spec_raw?: string;
  next_run_estimated?: string | null;
}

export interface BackgroundRoutine {
  id: string;
  display_name: string;
  source_kind: string;
  source_path: string;
  config_path?: string | null;
  cadence: Cadence;
  status: string;
  spawn_kind: string;
  ai_cost?: AiCost | null;
  last_run_at?: string | null;
  last_run_status?: string | null;
  last_run_log?: string | null;
  recent_runs_24h?: number | null;
  description?: string | null;
  tags?: string[];
}

interface Props {
  routine: BackgroundRoutine;
}

export function BackgroundRoutineDetailPanel({ routine }: Props) {
  const isAiSpawn = routine.spawn_kind === "ai-cli-spawn";

  return (
    <GlassCard className="p-6">
      {/* Header: name + spawn-kind badge */}
      <div className="flex items-start justify-between mb-4">
        <h2 className="text-xl font-semibold">{routine.display_name}</h2>
        {isAiSpawn ? (
          <Badge variant="destructive">ai-cli-spawn</Badge>
        ) : (
          <Badge variant="secondary">{routine.spawn_kind}</Badge>
        )}
      </div>

      <hr className="mb-4" />

      {/* 2-column grid: Cadence top-left, Last Run top-right */}
      <div className="grid grid-cols-2 gap-6 mb-6">
        <div>
          <div className="text-xs uppercase text-muted-foreground mb-1">Cadence</div>
          <div className="text-base font-medium">{formatCadence(routine.cadence)}</div>
          {routine.cadence.next_run_estimated && (
            <div className="text-sm text-muted-foreground">next: {formatRelativeTime(routine.cadence.next_run_estimated)}</div>
          )}
          {routine.cadence.spec_raw && (
            <div className="text-xs text-muted-foreground mt-1 font-mono">spec (raw): {routine.cadence.spec_raw}</div>
          )}
        </div>

        <div>
          <div className="text-xs uppercase text-muted-foreground mb-1">Last Run</div>
          <div className="text-base font-medium">
            {formatRelativeTime(routine.last_run_at)}
            {routine.last_run_status && ` (${routine.last_run_status})`}
          </div>
          {routine.last_run_log && (
            <div className="text-xs text-muted-foreground mt-1 font-mono truncate">→ {routine.last_run_log}</div>
          )}
          {routine.recent_runs_24h != null && (
            <div className="text-sm text-muted-foreground">recent 24h: {routine.recent_runs_24h} run{routine.recent_runs_24h === 1 ? "" : "s"}</div>
          )}
        </div>
      </div>

      {/* Source + Cost row */}
      <div className="grid grid-cols-2 gap-6 mb-6">
        <div>
          <div className="text-xs uppercase text-muted-foreground mb-1">Source</div>
          <div className="text-sm">{routine.source_kind}</div>
          <div className="text-xs text-muted-foreground font-mono mt-1">{routine.source_path}</div>
        </div>

        {isAiSpawn && routine.ai_cost && (
          <div>
            <div className="text-xs uppercase text-muted-foreground mb-1">Estimated Cost (last 5 runs)</div>
            <div className="text-sm">~{humanizeTokens(routine.ai_cost.estimated_tokens_per_run)} tokens / run</div>
            <div className="text-sm">~{humanizeTokens(routine.ai_cost.estimated_tokens_per_day)} tokens / day</div>
          </div>
        )}
      </div>

      {/* Config + status row */}
      <div className="grid grid-cols-2 gap-6 mb-6">
        {routine.config_path && (
          <div>
            <div className="text-xs uppercase text-muted-foreground mb-1">Config</div>
            <div className="text-xs text-muted-foreground font-mono">{routine.config_path}</div>
          </div>
        )}
        <div>
          <div className="text-xs uppercase text-muted-foreground mb-1">Status</div>
          <Badge variant={routine.status === "enabled" ? "default" : "secondary"}>{routine.status}</Badge>
        </div>
      </div>

      {/* Description */}
      {routine.description && (
        <div className="mb-4">
          <div className="text-xs uppercase text-muted-foreground mb-1">Description</div>
          <p className="text-sm">{routine.description}</p>
        </div>
      )}

      {/* Tags */}
      {routine.tags && routine.tags.length > 0 && (
        <div className="flex gap-2 flex-wrap">
          {routine.tags.map((tag) => (
            <Badge key={tag} variant="outline">{tag}</Badge>
          ))}
        </div>
      )}
    </GlassCard>
  );
}
```

Adjust imports if the project's UI primitives use different names (`@/components/ui/badge` vs `@/components/ui/Badge`, `GlassCard` location, etc.). The component shape is what matters; renaming to fit the actual primitives is mechanical.

- [ ] **Step 3: Verify TypeScript compiles**

Run:
```bash
cd apps/dashboard && pnpm exec tsc --noEmit 2>&1 | head -10
```
Expected: no new errors.

- [ ] **Step 4: Commit**

```bash
cd ~/Projects/Augur
git add apps/dashboard/components/shared/BackgroundRoutineDetailPanel.tsx
git commit -m "$(cat <<'EOF'
feat(dashboard): BackgroundRoutineDetailPanel — 2-col Cadence/Last-Run layout

New detail panel for the background-routines Browse category.
Layout per spec §7.5:

  Header: name + spawn-kind badge (red for ai-cli-spawn)
  Row 1 (2-col grid):
    Cadence (top-left)       | Last Run (top-right)
      spec, next, spec_raw   | relative time, status, log path,
                             | recent 24h count
  Row 2 (2-col grid):
    Source                   | Estimated Cost (only for ai-cli-spawn)
      kind, path             | tokens/run, tokens/day
  Row 3 (2-col grid):
    Config                   | Status
  Description (optional)
  Tags (optional)

Reuses formatCadence, formatRelativeTime, humanizeTokens from
routine-format.ts. Existing ScheduledExecutionDetailPanel.tsx
left in place for one release; Task 17 wires the new panel
into the routing.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 16: Table view — first-class cadence/next-run/last-run columns

**Files:**
- Modify: `apps/dashboard/components/shared/ScheduledExecutionTableView.tsx`

- [ ] **Step 1: Read the existing table view**

Run:
```bash
head -50 apps/dashboard/components/shared/ScheduledExecutionTableView.tsx
```

- [ ] **Step 2: Update the column set**

The existing component likely has columns like Title / Source / Schedule / Next run / Status. Update them to match spec §7.4. The first-class columns (Cadence, Next run, Last run) get a class marker so responsive collapse can be styled to preserve them.

Use Edit to update the column definition. The exact change depends on the existing structure; the intent is:

- Replace the existing "Schedule" column with `formatCadence(routine.cadence)`.
- Ensure `Next run` is `formatRelativeTime(routine.cadence.next_run_estimated)`.
- Add a `Last run` column with `formatRelativeTime(routine.last_run_at)`.
- Add a `Spawn kind` column showing a badge (red for `ai-cli-spawn`).
- Add an `Est. tokens/day` column with `humanizeTokens(routine.ai_cost?.estimated_tokens_per_day)`.
- Tag the Cadence / Next run / Last run columns with the CSS class `routine-table-col-essential` so responsive styling can preserve them.

Pattern:
```tsx
import { formatCadence, formatRelativeTime, humanizeTokens } from "@/lib/browse/routine-format";

// In the column definitions:
{
  key: "cadence",
  label: "Cadence",
  className: "routine-table-col-essential",
  render: (r) => formatCadence(r.cadence),
},
{
  key: "next_run",
  label: "Next run",
  className: "routine-table-col-essential",
  render: (r) => formatRelativeTime(r.cadence.next_run_estimated),
},
{
  key: "last_run",
  label: "Last run",
  className: "routine-table-col-essential",
  render: (r) => formatRelativeTime(r.last_run_at),
},
{
  key: "spawn_kind",
  label: "Spawn",
  className: "routine-table-col-collapsible",
  render: (r) => r.spawn_kind === "ai-cli-spawn"
    ? <span className="text-red-500 font-medium">ai-cli-spawn</span>
    : r.spawn_kind,
},
{
  key: "tokens_per_day",
  label: "Est. tokens/day",
  className: "routine-table-col-collapsible",
  render: (r) => humanizeTokens(r.ai_cost?.estimated_tokens_per_day),
},
```

Add a CSS rule somewhere globally (or in the component's local styles) to handle responsive collapse:

```css
@media (max-width: 768px) {
  .routine-table-col-collapsible {
    display: none;
  }
  /* routine-table-col-essential always visible */
}
```

If the codebase uses Tailwind for responsive classes (likely), use those instead:
```tsx
className: "routine-table-col-essential md:table-cell"
className: "routine-table-col-collapsible hidden md:table-cell"
```

- [ ] **Step 3: Verify TypeScript compiles**

Run:
```bash
cd apps/dashboard && pnpm exec tsc --noEmit 2>&1 | head -10
```
Expected: no new errors.

- [ ] **Step 4: Commit**

```bash
cd ~/Projects/Augur
git add apps/dashboard/components/shared/ScheduledExecutionTableView.tsx
git commit -m "$(cat <<'EOF'
feat(dashboard): table view — first-class Cadence/Next-run/Last-run columns

Per spec §7.4: Cadence, Next run, and Last run are first-class
columns that survive responsive collapse. Spawn kind and
Est. tokens/day columns collapse on small screens (hidden md:*).

ai-cli-spawn badge rendered in red so the user can spot budget
burners at a glance.

Renders via formatCadence, formatRelativeTime, humanizeTokens
from routine-format.ts (same helpers used by the card and detail
panel — single source of formatting truth).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 17: URL redirect shim + wire new detail panel

**Files:**
- Modify: `apps/dashboard/app/(views)/browse/useBrowseState.ts`
- Modify: any component file that imports `ScheduledExecutionDetailPanel` to use `BackgroundRoutineDetailPanel` instead

- [ ] **Step 1: Add the URL redirect in useBrowseState**

Read the current category-resolution logic:
```bash
grep -n "category\|indexCategory" apps/dashboard/app/\(views\)/browse/useBrowseState.ts | head -10
```

Add a redirect mapping at the top of the file or wherever the category id is normalized:

```typescript
// One-release alias per CLAUDE.md rule 14 (ADR-727).
// Removed in the release immediately after this one ships.
const CATEGORY_ALIASES: Record<string, string> = {
  "scheduled-executions": "background-routines",
};

function normalizeCategory(raw: string | null): string | null {
  if (!raw) return raw;
  return CATEGORY_ALIASES[raw] ?? raw;
}
```

Wherever `category` is read from `useSearchParams` / route props, wrap with `normalizeCategory()`.

- [ ] **Step 2: Wire the new detail panel**

Find every import of `ScheduledExecutionDetailPanel`:
```bash
grep -rln "ScheduledExecutionDetailPanel" apps/dashboard 2>/dev/null
```

For each call site that resolves the detail panel for the `background-routines` category, swap to `BackgroundRoutineDetailPanel`. The simplest version (if there's a single switch):

```tsx
// In the detail-panel resolver:
if (category === "background-routines") {
  return <BackgroundRoutineDetailPanel routine={entry} />;
}
// fall back to old panel only for the legacy alias redirect path
if (category === "scheduled-executions") {
  return <BackgroundRoutineDetailPanel routine={entry} />;
}
```

(After the alias is removed in the next release, both branches collapse to one.)

- [ ] **Step 3: Verify TypeScript + manual route test**

Run:
```bash
cd apps/dashboard && pnpm exec tsc --noEmit 2>&1 | head -10
```
Expected: no new errors.

- [ ] **Step 4: Commit**

```bash
cd ~/Projects/Augur
git add apps/dashboard/app/\(views\)/browse/useBrowseState.ts apps/dashboard/components/shared/
git commit -m "$(cat <<'EOF'
feat(dashboard): URL redirect shim + wire BackgroundRoutineDetailPanel

One-release alias per CLAUDE.md rule 14:
  ?category=scheduled-executions → ?category=background-routines

Implemented as a CATEGORY_ALIASES map applied in normalizeCategory()
in useBrowseState. Old URLs continue to work for one release;
removed in the next release.

Detail panel resolver now returns BackgroundRoutineDetailPanel for
both the new category id AND the legacy alias path during the
one-release window.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 18: RAG inventory rename + release notes

**Files:**
- Modify: `shared-vault/skills/ingest/scripts/wiki_source_inventory.py`
- Create or modify: `CHANGELOG.md`

- [ ] **Step 1: Rename the RAG category id**

Use Edit on `shared-vault/skills/ingest/scripts/wiki_source_inventory.py`:

Find:
```python
    "scheduled-executions",
```

Replace with:
```python
    "background-routines",
```

(There was only one occurrence per the earlier session's grep.)

- [ ] **Step 2: Add CHANGELOG entry**

If `CHANGELOG.md` exists at the repo root, prepend a new section. If it doesn't, create one. Use Edit (or Write if new):

Find the most recent CHANGELOG entry (e.g., the top of the file) and insert above it:

```markdown
## Unreleased

### Changed
- **Browse category `scheduled-executions` renamed to `background-routines`** (ADR-727). The new category surfaces every autonomous trigger on the machine — per-skill schedules, daemon services, daemon scripts (incl. token-burning AI-CLI-spawn scripts), launchd agents, GitHub Actions cron workflows. Cadence + last-run are first-class on every view. Token-cost estimation is surfaced for AI-CLI-spawn routines.
- `?category=scheduled-executions` URLs redirect to `?category=background-routines` for one release; the redirect is removed in the release after this one.

### Added
- New MCP tool `list-routines` (`shared-vault/skills/daemon/scripts/mcp/routine_tools.py`) — single Browse data source for the new category, with `source_kind` / `spawn_kind` / `status` filters.
- New module `shared-vault/skills/daemon/scripts/routine_discovery.py` — `Routine` dataclass, 6 source-kind discoverers, fail-soft aggregator, AI-cost log sampling.
- New UI helpers `apps/dashboard/lib/browse/routine-format.ts` — `formatCadence`, `formatRelativeTime`, `humanizeTokens`.
- New detail panel `BackgroundRoutineDetailPanel.tsx` with 2-column Cadence/Last-Run layout.

### Deprecated
- `apps/dashboard/lib/browse/types.ts`: `ScheduledExecutionDetail` type aliased as `Routine` for one release; alias removed in the next release.

### Removed
- (nothing in this release; old category id `scheduled-executions` removed in the next release.)
```

- [ ] **Step 3: Verify the RAG category rename is parseable**

Run:
```bash
python3 -c "
import sys
sys.path.insert(0, '.')
sys.path.insert(0, 'shared-vault')
# Just import to verify the module is syntactically valid
from skills.ingest.scripts import wiki_source_inventory
print('OK')
"
```
Expected: `OK`.

- [ ] **Step 4: Commit**

```bash
git add shared-vault/skills/ingest/scripts/wiki_source_inventory.py CHANGELOG.md
git commit -m "$(cat <<'EOF'
chore(release): RAG inventory rename + CHANGELOG entry for ADR-727

  wiki_source_inventory.py: rename "scheduled-executions" →
    "background-routines" in the recognized-categories set.

  CHANGELOG.md: Unreleased section documenting the rename,
  new MCP tool, new helpers, new detail panel, and the one-release
  deprecation window for the legacy category id + URL.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 19: End-to-end integration verification + push

**Files:** none — verification only.

- [ ] **Step 1: Run the full Python test suite for this feature**

Run:
```bash
pytest tests/unit/test_routine_discovery.py tests/unit/test_list_routines_mcp.py -v --tb=short
```
Expected: all green (~30+ tests).

- [ ] **Step 2: Run the dashboard TypeScript + Vitest checks**

Run:
```bash
cd apps/dashboard && pnpm exec tsc --noEmit
```
Expected: no new errors.

```bash
pnpm --filter dashboard test routine-format
```
Expected: all routine-format tests pass.

- [ ] **Step 3: Real-machine smoke — does the MCP tool return real routines?**

Run:
```bash
cd ~/Projects/Augur
python3 << 'PY'
import sys, asyncio, json
sys.path.insert(0, '.')
sys.path.insert(0, 'shared-vault')

from skills.daemon.scripts.mcp.routine_tools import list_routines, _cache_clear

_cache_clear()
result = json.loads(asyncio.run(list_routines()))
assert result["success"]
routines = result["routines"]
print(f"Total: {len(routines)} routines")
from collections import Counter
by_kind = Counter(r["source_kind"] for r in routines)
for kind, count in sorted(by_kind.items()):
    print(f"  {kind}: {count}")

# Insight scanner specifically — should appear with ai-cli-spawn from daemon-script discoverer
spawners = [r for r in routines if r["spawn_kind"] == "ai-cli-spawn"]
print(f"\nai-cli-spawn routines: {len(spawners)}")
for r in spawners[:5]:
    print(f"  {r['id']}: cadence={r['cadence']['spec']}, cost={r.get('ai_cost')}")
PY
```
Expected: ≥1 routine each for at least `daemon-service`, `daemon-script`, `launchd-agent`, `github-action` (the kinds that have real instances on this machine). At least `insight_scanner` should appear in the ai-cli-spawn list.

- [ ] **Step 4: Real-browser verification (rule 28)**

Per CLAUDE.md rule 28 (browser verification mandatory for UI changes):

1. Start the dashboard via `/dev-build` (rule 29 — never `pnpm dev` directly).
2. Open `http://localhost:3000/browse?category=background-routines` in a browser.
3. Verify:
   - The page loads to interactive state (no chunk-load errors).
   - All 6 source kinds show entries (or "—" for kinds with no instances on this machine).
   - `insight_scanner` appears with the red `ai-cli-spawn` badge.
   - The Cadence column shows `every 100yr` for `insight_scanner` (proof the 876000-hour disabled state is correctly surfaced).
   - Cadence / Next run / Last run columns survive when the window is narrowed (responsive collapse keeps them visible).
   - Clicking a row opens the new detail panel with the 2-column Cadence/Last-Run layout.
4. Open `http://localhost:3000/browse?category=scheduled-executions` (the legacy URL).
5. Verify: redirected to `background-routines`; the page renders the same content.

Report: "Browser verification passed: all 6 source kinds visible, insight_scanner shows ai-cli-spawn badge with every-100yr cadence (confirming the tactical defense), responsive collapse preserves first-class columns, detail panel renders the 2-col layout, legacy URL redirect works." If any check fails, fix and re-verify.

- [ ] **Step 5: Push to origin**

Run:
```bash
git push origin main 2>&1 | tail -3
```
Expected: push succeeds.

- [ ] **Step 6: Final state summary**

Run:
```bash
git log --oneline -22
echo "---"
git status
```
Expected: 18 commits added (Tasks 1-18), working tree clean.

Report to the user:
- 18 task commits + 1 verification step
- ADR-727 plan executed end-to-end
- All 6 source kinds visible in Browse
- `insight_scanner` correctly shown with ai-cli-spawn badge + every-100yr cadence
- Legacy `scheduled-executions` URL still works for one release
- Next step: flip ADR-727 to Implemented (`/adr set 727 Implemented`), then handoff via `superpowers:finishing-a-development-branch`

---

## Self-Review Notes

**Spec coverage:**

| Spec section | Implementing task |
|---|---|
| §3 Six source kinds | Tasks 3-8 (one per kind) |
| §4 Routine schema | Task 1 (dataclass) + Task 2 (helpers) |
| §4.2 Failure mode (agent_step_required equivalent for missing data) | Tasks 3-8 (each discoverer returns None / empty list on missing inputs; aggregator fail-soft in Task 9) |
| §5 Discovery architecture | Tasks 1, 3-9 |
| §6 list-routines MCP tool | Tasks 10-11 |
| §7.1 Rename + §7.2 First-class declaration | Tasks 13 (rename) + 14-16 (first-class surfaces) |
| §7.3 Card view | Task 14 (transforms description line — same fields surface in card description; full card render handled by existing browse card component which now reads the new description) |
| §7.4 Table columns | Task 16 |
| §7.5 Detail panel | Task 15 |
| §7.6 Transforms / description line | Task 14 |
| §7.7 routine-format helpers | Task 12 |
| §8 Migration | Tasks 13 (type alias) + 17 (URL redirect) + 18 (RAG rename + CHANGELOG) |
| §9 4 checkpoints | C1: Tasks 1-9. C2: Tasks 10-11. C3: Tasks 12-16. C4: Tasks 17-18. |

All spec sections covered. No gaps.

**Type consistency:**

- `Routine` dataclass shape (Python) ↔ `BackgroundRoutine` interface (TypeScript, Task 15) — both have the same fields; TypeScript interface defines optional fields explicitly.
- `formatCadence(c: Cadence)`, `formatRelativeTime(iso)`, `humanizeTokens(n)` signatures identical across Tasks 12, 14, 15, 16.
- `compute_next_run(cadence, last_run_at, now)` and `derive_ai_cost(...)` signatures identical across Tasks 2-9.
- `discover_all_routines()` return type `list[Routine]` consistent across Tasks 9, 10.
- `list_routines(source_kind, spawn_kind, status)` MCP signature consistent across Tasks 10, 11 (capability entry).

**Placeholder scan:**

- No "TBD", "TODO", "fill in details" anywhere.
- Every step has runnable code or runnable commands.
- The CSS responsive snippet in Task 16 has both a plain-CSS example and a Tailwind alternative — the engineer picks based on the existing codebase's convention. Not a placeholder; it's a context-sensitive choice.

**Risk areas:**

- Task 14 has an `await import()` pattern that requires async transforms. If transforms are sync-only in this codebase, the engineer should fall back to the top-level import alternative noted in the same step. Both paths are documented.
- Task 16's CSS approach (`routine-table-col-essential` class vs Tailwind `hidden md:table-cell`) depends on the existing table component's styling convention. Both options provided.
- Task 10's MCP-registration mechanism depends on how this skill exposes other MCP tools. Step 4 of Task 10 explicitly says "if a decorator convention exists, use it; if not, the dynamic-discovery path picks it up from the module's exports." — engineer applies whichever fits.
- The `?category=scheduled-executions` URL redirect (Task 17) is a one-release shim. The PR's release notes (Task 18) explicitly mark the next release as the removal point.
