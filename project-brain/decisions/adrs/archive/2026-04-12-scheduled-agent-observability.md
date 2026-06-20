# Scheduled Agent Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a unified Browse surface for scheduled agent executions across `augur-internal`, `codex`, and `claude`, then retire daemon-owned nightly `dev-loops` execution by moving the nightly loop family to split Codex-native schedules.

**Architecture:** Keep scheduling native to each client and make Augur the read-only observability plane. Implement backend source adapters that normalize Codex, Claude, and Augur-internal schedules into one entity shape, expose that shape through `browse-index` plus a dedicated detail tool, then add a schedule-specific table/detail UI in Browse. On the daemon side, add per-command scheduler ownership metadata so nightly `dev-loops` categories can be marked `codex` and skipped by the daemon while `augur-internal` remains available for other schedules.

**Tech Stack:** Python 3.11, FastMCP, sqlite3, tomllib, Next.js 16, React 19, TanStack Query, Jest, pytest, YAML config

**Spec:** `docs/superpowers/specs/2026-04-12-scheduled-agent-observability-design.md`

---

## File Structure

### Create

| File | Responsibility |
|---|---|
| `src/mcp/augur_mcp/infrastructure/browse/scheduled_executions.py` | Unified scheduled-execution model, list/detail helpers, source-loader orchestration |
| `src/mcp/augur_mcp/infrastructure/browse/scheduled_sources/__init__.py` | Source-loader exports |
| `src/mcp/augur_mcp/infrastructure/browse/scheduled_sources/codex.py` | Codex automation adapter (`automation.toml` + sqlite runtime state) |
| `src/mcp/augur_mcp/infrastructure/browse/scheduled_sources/claude.py` | Claude scheduled-task adapter (`scheduled-tasks.json` + prompt body files) |
| `src/mcp/augur_mcp/infrastructure/browse/scheduled_sources/augur_internal.py` | Augur-internal adapter for daemon-owned schedulable loops/commands |
| `src/mcp/augur_mcp/tests/test_scheduled_executions.py` | MCP/backend tests for list/detail normalization and dynamic browse category behavior |
| `apps/dashboard/components/shared/ScheduledExecutionTableView.tsx` | Schedule-specific table view with source/status/schedule columns and detail affordance |
| `apps/dashboard/components/shared/ScheduledExecutionDetailPanel.tsx` | Detail panel for full prompt/body, raw schedule, warnings, and runtime metadata |
| `apps/dashboard/lib/browse/useScheduledExecutionDetail.ts` | React hook to fetch scheduled-execution detail via MCP |
| `tests/dashboard/browse/ScheduledExecutionTableView.test.tsx` | Jest coverage for schedule row rendering and detail button behavior |
| `tests/dashboard/browse/ScheduledExecutionDetailPanel.test.tsx` | Jest coverage for prompt/raw-schedule/warning rendering |
| `skills/daemon/assets/seeds/codex-dev-loop-schedules.yaml` | Canonical split-loop Codex automation manifest for nightly `dev-loops` migration |

### Modify

| File | Change |
|---|---|
| `src/mcp/augur_mcp/infrastructure/browse/index.py` | Special-case `scheduled-executions` as a dynamic browse category |
| `src/mcp/augur_mcp/infrastructure/browse/__init__.py` | Register `get-scheduled-execution-detail` MCP tool and document new category in `browse-index` |
| `apps/dashboard/lib/browse/types.ts` | Add `scheduled-executions` view mode plus schedule detail types |
| `apps/dashboard/lib/browse/transforms.ts` | Transform normalized schedule records into `BrowseItem` rows |
| `apps/dashboard/app/(views)/browse/useBrowseState.ts` | Add schedule category support, schedule selection state, and schedule-source filters |
| `apps/dashboard/app/(views)/browse/BrowseContentGrid.tsx` | Route `scheduled-executions` rows through the new schedule table component |
| `apps/dashboard/app/(views)/browse/page.tsx` | Render the schedule detail panel when the schedule category is active |
| `tests/dashboard/lib/browse-transforms-index.test.ts` | Add `scheduled-executions` transform assertions |
| `tests/dashboard/browse/useBrowseState.test.tsx` | Add schedule-category state and detail-selection assertions |
| `skills/daemon/config.yaml` | Add per-command `scheduler` ownership for daemon vs Codex-managed loop commands |
| `skills/daemon/commands/dev-loops.md` | Document that nightly loop ownership moves to split Codex schedules and `run --all` remains manual only |
| `skills/daemon/references/dev-loops-implementation.md` | Update execution model and cutover notes for Codex-owned nightly loops |
| `skills/daemon/scripts/adaptive/discovery.py` | Parse `scheduler` metadata into discovered auto-command entries |
| `skills/daemon/scripts/adaptive/engine.py` | Skip externally owned nightly commands during daemon execution |
| `skills/daemon/scripts/adaptive/engine_registration.py` | Preserve scheduler ownership in loop registration/reporting |
| `skills/daemon/scripts/adaptive/loop_reporter.py` | Surface scheduler ownership so `/dev-loops report` matches reality |
| `skills/daemon/augur/tests/test_adaptive_discovery.py` | Verify `scheduler` metadata survives discovery |
| `skills/daemon/augur/tests/test_adaptive_loop_executor.py` | Verify daemon nightly runs skip Codex-owned loop commands |

---

## Task 1: Add The Dynamic Browse Category Contract

**Files:**
- Create: `src/mcp/augur_mcp/infrastructure/browse/scheduled_executions.py`
- Modify: `src/mcp/augur_mcp/infrastructure/browse/index.py`
- Modify: `src/mcp/augur_mcp/infrastructure/browse/__init__.py`
- Create: `src/mcp/augur_mcp/tests/test_scheduled_executions.py`

- [ ] **Step 1: Write the failing backend contract tests**

Create `src/mcp/augur_mcp/tests/test_scheduled_executions.py`:

```python
from __future__ import annotations

import json


def test_browse_index_returns_dynamic_scheduled_execution_rows(monkeypatch) -> None:
    from augur_mcp.infrastructure.browse.index import browse_index_impl

    monkeypatch.setattr(
        "augur_mcp.infrastructure.browse.scheduled_executions.list_scheduled_execution_items",
        lambda search=None: [
            {
                "id": "codex:update-agents-md",
                "title": "Update AGENTS.md",
                "description": "Update AGENTS.md with newly discovered workflows/commands",
                "hub": "system",
                "type": "scheduled-executions",
                "source_path": "/Users/test/.codex/automations/update-agents-md/automation.toml",
                "metadata": {
                    "source": "codex",
                    "kind": "native-schedule",
                    "status": "active",
                    "schedule": "Weekly on Sunday at 11:00",
                },
            }
        ],
    )

    payload = json.loads(browse_index_impl("scheduled-executions"))
    assert payload["count"] == 1
    assert payload["items"][0]["metadata"]["source"] == "codex"
    assert payload["items"][0]["type"] == "scheduled-executions"


def test_scheduled_execution_detail_returns_not_found_for_unknown_id() -> None:
    from augur_mcp.infrastructure.browse.scheduled_executions import get_scheduled_execution_detail_impl

    payload = json.loads(get_scheduled_execution_detail_impl("codex:missing"))
    assert payload["success"] is False
    assert payload["error"] == "Scheduled execution 'codex:missing' not found"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
pytest src/mcp/augur_mcp/tests/test_scheduled_executions.py -q
```

Expected:

```text
FAILED ... ModuleNotFoundError: No module named 'augur_mcp.infrastructure.browse.scheduled_executions'
```

- [ ] **Step 3: Implement the dynamic category branch and detail tool**

Create `src/mcp/augur_mcp/infrastructure/browse/scheduled_executions.py`:

```python
from __future__ import annotations

import json
from typing import Any


def list_scheduled_execution_records(search: str | None = None) -> list[dict[str, Any]]:
    del search
    return []


def list_scheduled_execution_items(search: str | None = None) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for record in list_scheduled_execution_records(search):
        items.append(
            {
                "id": record["id"],
                "title": record["title"],
                "description": record.get("prompt_summary", ""),
                "hub": "system",
                "type": "scheduled-executions",
                "source_path": record.get("source_path", ""),
                "metadata": {
                    "source": record["source"],
                    "kind": record["kind"],
                    "status": record.get("status", "unknown"),
                    "schedule": record.get("schedule_human", ""),
                    "workspace": record.get("workspace", ""),
                    "model": record.get("model", ""),
                    "lastRun": record.get("last_run_at", ""),
                    "nextRun": record.get("next_run_at", ""),
                },
            }
        )
    return items


def get_scheduled_execution_detail_impl(execution_id: str) -> str:
    for record in list_scheduled_execution_records():
        if record["id"] == execution_id:
            return json.dumps({"success": True, "detail": record})
    return json.dumps(
        {"success": False, "error": f"Scheduled execution '{execution_id}' not found"}
    )
```

Patch `src/mcp/augur_mcp/infrastructure/browse/index.py`:

```python
from .scheduled_executions import list_scheduled_execution_items


def browse_index_impl(category: str, hub: str | None = None, limit: int = 0, search: str | None = None) -> str:
    if category == "scheduled-executions":
        items = list_scheduled_execution_items(search=search)
        if hub:
            items = [item for item in items if item.get("hub") == hub]
        effective_limit = limit if limit > 0 else _BROWSE_LIMIT
        items = items[:effective_limit]
        return json.dumps({"items": items, "count": len(items)})
```

Patch `src/mcp/augur_mcp/infrastructure/browse/__init__.py`:

```python
from .scheduled_executions import get_scheduled_execution_detail_impl

    @mcp.tool(
        name="get-scheduled-execution-detail",
        annotations=tool_annotations(
            {
                "title": "Scheduled Execution Detail",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def get_scheduled_execution_detail(execution_id: str) -> str:
        """Return one normalized scheduled execution detail record."""
        return get_scheduled_execution_detail_impl(execution_id)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
pytest src/mcp/augur_mcp/tests/test_scheduled_executions.py -q
```

Expected:

```text
2 passed
```

- [ ] **Step 5: Commit**

```bash
git add src/mcp/augur_mcp/infrastructure/browse/scheduled_executions.py src/mcp/augur_mcp/infrastructure/browse/index.py src/mcp/augur_mcp/infrastructure/browse/__init__.py src/mcp/augur_mcp/tests/test_scheduled_executions.py
git commit -m "feat(browse): add scheduled execution browse contract"
```

## Task 2: Implement Codex And Claude Native Schedule Adapters

**Files:**
- Create: `src/mcp/augur_mcp/infrastructure/browse/scheduled_sources/__init__.py`
- Create: `src/mcp/augur_mcp/infrastructure/browse/scheduled_sources/codex.py`
- Create: `src/mcp/augur_mcp/infrastructure/browse/scheduled_sources/claude.py`
- Modify: `src/mcp/augur_mcp/infrastructure/browse/scheduled_executions.py`
- Modify: `src/mcp/augur_mcp/tests/test_scheduled_executions.py`

- [ ] **Step 1: Add failing adapter tests**

Append to `src/mcp/augur_mcp/tests/test_scheduled_executions.py`:

```python
from __future__ import annotations

import json
import sqlite3
from pathlib import Path


def test_load_codex_schedules_reads_toml_and_runtime_state(tmp_path, monkeypatch) -> None:
    home = tmp_path / "home"
    automation_dir = home / ".codex" / "automations" / "update-agents-md"
    sqlite_dir = home / ".codex" / "sqlite"
    automation_dir.mkdir(parents=True)
    sqlite_dir.mkdir(parents=True)

    (automation_dir / "automation.toml").write_text(
        """name = "Update AGENTS.md"
prompt = "Update AGENTS.md with newly discovered workflows/commands"
model = "gpt-5.4"
rrule = "RRULE:FREQ=WEEKLY;BYDAY=SU;BYHOUR=11;BYMINUTE=0"
cwds = ["~/Projects/Augur"]
""",
        encoding="utf-8",
    )

    db = sqlite3.connect(sqlite_dir / "codex-dev.db")
    db.execute(
        "create table automations (automation_id text primary key, status text, last_run_at text, next_run_at text)"
    )
    db.execute(
        "insert into automations values (?, ?, ?, ?)",
        (
            "update-agents-md",
            "ACTIVE",
            "2026-04-12T08:00:25.728000+00:00",
            "2026-04-19T08:00:00+00:00",
        ),
    )
    db.commit()
    db.close()

    monkeypatch.setenv("HOME", str(home))

    from augur_mcp.infrastructure.browse.scheduled_sources.codex import load_codex_schedules

    rows = load_codex_schedules()
    assert rows[0]["id"] == "codex:update-agents-md"
    assert rows[0]["status"] == "active"
    assert rows[0]["raw_schedule"]["value"].startswith("RRULE:")
    assert rows[0]["last_run_at"] == "2026-04-12T08:00:25.728000+00:00"


def test_load_claude_schedules_reads_prompt_body_and_warning(tmp_path, monkeypatch) -> None:
    home = tmp_path / "home"
    support = home / "Library" / "Application Support" / "Claude" / "local-agent-mode-sessions" / "session-a" / "window-a"
    prompt_dir = home / "Documents" / "Claude" / "Scheduled" / "claude-second-brain-report"
    support.mkdir(parents=True)
    prompt_dir.mkdir(parents=True)

    (support / "scheduled-tasks.json").write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "claude-second-brain-report",
                        "enabled": True,
                        "cronExpression": "0 16 * * 5",
                        "model": "claude-opus-4-6",
                        "filePath": str(prompt_dir / "SKILL.md"),
                        "createdAt": 1775982575820,
                        "userSelectedFolders": ["~/Projects/Augur"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (prompt_dir / "SKILL.md").write_text(
        "---\nname: claude-second-brain-report\n---\nRun `/wiki report --style demo`.\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("HOME", str(home))

    from augur_mcp.infrastructure.browse.scheduled_sources.claude import load_claude_schedules

    rows = load_claude_schedules()
    assert rows[0]["id"] == "claude:claude-second-brain-report"
    assert rows[0]["prompt_body"].startswith("---")
    assert rows[0]["warnings"] == [
        "Claude schedule interpretation is provisional until timezone semantics are verified."
    ]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
pytest src/mcp/augur_mcp/tests/test_scheduled_executions.py -q
```

Expected:

```text
FAILED ... No module named 'augur_mcp.infrastructure.browse.scheduled_sources'
```

- [ ] **Step 3: Implement the Codex and Claude loaders**

Create `src/mcp/augur_mcp/infrastructure/browse/scheduled_sources/__init__.py`:

```python
from .augur_internal import load_augur_internal_schedules
from .claude import load_claude_schedules
from .codex import load_codex_schedules

__all__ = [
    "load_augur_internal_schedules",
    "load_claude_schedules",
    "load_codex_schedules",
]
```

Create `src/mcp/augur_mcp/infrastructure/browse/scheduled_sources/codex.py`:

```python
from __future__ import annotations

import sqlite3
import tomllib
from pathlib import Path


def load_codex_schedules() -> list[dict]:
    home = Path.home()
    db_path = home / ".codex" / "sqlite" / "codex-dev.db"
    runtime: dict[str, dict[str, str]] = {}
    if db_path.exists():
        conn = sqlite3.connect(db_path)
        rows = conn.execute(
            "select automation_id, status, last_run_at, next_run_at from automations"
        ).fetchall()
        conn.close()
        runtime = {
            automation_id: {
                "status": status,
                "last_run_at": last_run_at,
                "next_run_at": next_run_at,
            }
            for automation_id, status, last_run_at, next_run_at in rows
        }

    records: list[dict] = []
    for toml_path in sorted((home / ".codex" / "automations").glob("*/automation.toml")):
        data = tomllib.loads(toml_path.read_text(encoding="utf-8"))
        automation_id = toml_path.parent.name
        state = runtime.get(automation_id, {})
        records.append(
            {
                "id": f"codex:{automation_id}",
                "title": data.get("name", automation_id),
                "source": "codex",
                "kind": "native-schedule",
                "status": str(state.get("status", "unknown")).lower(),
                "workspace": (data.get("cwds") or [""])[0],
                "schedule_human": data.get("rrule", ""),
                "raw_schedule": {"type": "rrule", "value": data.get("rrule", "")},
                "prompt_summary": data.get("prompt", ""),
                "prompt_body": data.get("prompt", ""),
                "native_id": automation_id,
                "source_path": str(toml_path),
                "model": data.get("model", ""),
                "last_run_at": state.get("last_run_at"),
                "next_run_at": state.get("next_run_at"),
                "warnings": [],
            }
        )
    return records
```

Create `src/mcp/augur_mcp/infrastructure/browse/scheduled_sources/claude.py`:

```python
from __future__ import annotations

import json
from pathlib import Path


def load_claude_schedules() -> list[dict]:
    home = Path.home()
    base = home / "Library" / "Application Support" / "Claude" / "local-agent-mode-sessions"
    records: list[dict] = []
    for task_file in sorted(base.glob("**/scheduled-tasks.json")):
        payload = json.loads(task_file.read_text(encoding="utf-8"))
        for task in payload.get("tasks", []):
            prompt_path = Path(task.get("filePath", ""))
            prompt_body = prompt_path.read_text(encoding="utf-8") if prompt_path.is_file() else ""
            native_id = task["id"]
            workspace = (task.get("userSelectedFolders") or [""])[0]
            records.append(
                {
                    "id": f"claude:{native_id}",
                    "title": native_id.replace("-", " ").title(),
                    "source": "claude",
                    "kind": "native-schedule",
                    "status": "active" if task.get("enabled") else "disabled",
                    "workspace": workspace,
                    "schedule_human": task.get("cronExpression", ""),
                    "raw_schedule": {"type": "cron", "value": task.get("cronExpression", "")},
                    "prompt_summary": prompt_body.splitlines()[-1] if prompt_body else "",
                    "prompt_body": prompt_body,
                    "native_id": native_id,
                    "source_path": str(prompt_path),
                    "model": task.get("model", ""),
                    "last_run_at": None,
                    "next_run_at": None,
                    "warnings": [
                        "Claude schedule interpretation is provisional until timezone semantics are verified."
                    ],
                }
            )
    return records
```

Patch `src/mcp/augur_mcp/infrastructure/browse/scheduled_executions.py`:

```python
from .scheduled_sources import load_claude_schedules, load_codex_schedules


def list_scheduled_execution_records(search: str | None = None) -> list[dict[str, Any]]:
    records = [*load_codex_schedules(), *load_claude_schedules()]
    if not search:
        return records
    needle = search.strip().lower()
    return [
        record
        for record in records
        if needle in record["title"].lower()
        or needle in record.get("prompt_summary", "").lower()
        or needle in record["source"].lower()
    ]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
pytest src/mcp/augur_mcp/tests/test_scheduled_executions.py -q
```

Expected:

```text
4 passed
```

- [ ] **Step 5: Commit**

```bash
git add src/mcp/augur_mcp/infrastructure/browse/scheduled_sources/__init__.py src/mcp/augur_mcp/infrastructure/browse/scheduled_sources/codex.py src/mcp/augur_mcp/infrastructure/browse/scheduled_sources/claude.py src/mcp/augur_mcp/infrastructure/browse/scheduled_executions.py src/mcp/augur_mcp/tests/test_scheduled_executions.py
git commit -m "feat(browse): observe codex and claude schedules"
```

## Task 3: Add The Augur-Internal Adapter And Dev-Loop Scheduler Ownership

**Files:**
- Create: `src/mcp/augur_mcp/infrastructure/browse/scheduled_sources/augur_internal.py`
- Modify: `src/mcp/augur_mcp/infrastructure/browse/scheduled_executions.py`
- Modify: `skills/daemon/config.yaml`
- Modify: `skills/daemon/scripts/adaptive/discovery.py`
- Modify: `skills/daemon/scripts/adaptive/engine.py`
- Modify: `skills/daemon/scripts/adaptive/engine_registration.py`
- Modify: `skills/daemon/scripts/adaptive/loop_reporter.py`
- Modify: `skills/daemon/augur/tests/test_adaptive_discovery.py`
- Modify: `skills/daemon/augur/tests/test_adaptive_loop_executor.py`

- [ ] **Step 1: Write the failing daemon ownership tests**

Append to `skills/daemon/augur/tests/test_adaptive_discovery.py`:

```python
    def test_discovers_scheduler_ownership(self, tmp_path):
        skill_dir = _write_skill(
            tmp_path,
            "daemon",
            commands=[
                {
                    "id": "auto-nightly-testing",
                    "protocol": "scan-fix",
                    "callable": "scripts/ops/testing.py",
                    "loop": {
                        "name": "testing",
                        "tier": 1,
                        "trigger": "nightly",
                        "scheduler": "codex",
                    },
                }
            ],
        )
        _create_ops_module(skill_dir / "scripts" / "ops" / "testing.py", "auto-nightly-testing")

        registry = discover_auto_commands(tmp_path)
        assert registry["auto-nightly-testing"].scheduler == "codex"
```

Append to `skills/daemon/augur/tests/test_adaptive_loop_executor.py`:

```python
def test_run_all_by_trigger_skips_codex_owned_entries(monkeypatch, tmp_path):
    from adaptive.discovery import AutoCommandEntry
    from adaptive.engine import AdaptiveLoopEngine

    class _Module:
        name = "auto-nightly-testing"

        @staticmethod
        def scan(ctx):
            raise AssertionError("codex-owned nightly entry should not execute")

        @staticmethod
        def fix(ctx, issues):
            return None

    engine = AdaptiveLoopEngine({"engine": {"enabled": True}, "loops": {"testing": {"enabled": True, "budget": 2}}})
    engine.register_auto_commands(
        {
            "auto-nightly-testing": AutoCommandEntry(
                name="auto-nightly-testing",
                module=_Module,
                loop_name="testing",
                trigger="nightly",
                scheduler="codex",
            )
        }
    )

    result = engine.run_all_by_trigger("nightly")
    assert result == {}
```

- [ ] **Step 2: Run the daemon tests to verify they fail**

Run:

```bash
pytest skills/daemon/augur/tests/test_adaptive_discovery.py::TestDiscoverAutoCommands::test_discovers_scheduler_ownership skills/daemon/augur/tests/test_adaptive_loop_executor.py::test_run_all_by_trigger_skips_codex_owned_entries -q
```

Expected:

```text
FAILED ... AttributeError: 'AutoCommandEntry' object has no attribute 'scheduler'
```

- [ ] **Step 3: Add scheduler ownership to daemon discovery and execution**

Patch `skills/daemon/scripts/adaptive/discovery.py`:

```python
@dataclass
class AutoCommandEntry:
    name: str
    module: Any
    loop_name: str
    tier: int = 0
    trigger: str = "nightly"
    scheduler: str = "daemon"
    plugin_root: Path = field(default_factory=lambda: Path.cwd())
    config: dict = field(default_factory=dict)
    initial_trust: float = 0.0
```

and in `discover_auto_commands()`:

```python
            registry[cmd_id] = AutoCommandEntry(
                name=cmd_id,
                module=module,
                loop_name=loop_name,
                tier=loop_config.get("tier", rec.loop_config.get("tier", 0)),
                trigger=loop_config.get("trigger", rec.loop_config.get("trigger", "nightly")),
                scheduler=loop_config.get("scheduler", rec.loop_config.get("scheduler", "daemon")),
                plugin_root=plugin_root,
                config=module_config,
                initial_trust=float(loop_config.get("trust", rec.loop_config.get("trust", 0.0))),
            )
```

Patch `skills/daemon/scripts/adaptive/engine.py` inside `run_all_by_trigger()` before executing auto-command loops:

```python
            eligible_entries = [
                entry
                for entry in entries
                if entry.trigger == trigger and getattr(entry, "scheduler", "daemon") == "daemon"
            ]
            if not eligible_entries:
                continue
```

Patch `skills/daemon/config.yaml` so nightly dev-loop commands declare Codex ownership while daemon-only flows stay daemon-owned:

```yaml
  - id: auto-mcp-hygiene
    type: workflow
    visibility: auto
    description: Per-plugin MCP tool naming, registration, dead-tool, and duplicate audit
    callable: scripts/ops/mcp_hygiene.py
    protocol: scan-fix
    loop:
      name: code-quality
      tier: 1
      trigger: nightly
      scheduler: codex

  - id: auto-heal-validate
    type: workflow
    visibility: auto
    description: Validate self-heal daemon health and clear stuck journal entries
    callable: scripts/ops/heal_validate.py
    protocol: scan-fix
    loop:
      name: self-heal
      tier: 1
      trigger: nightly
      scheduler: daemon
```

Patch `skills/daemon/scripts/adaptive/loop_reporter.py` to surface ownership:

```python
                scheduler = getattr(entry, "scheduler", "daemon")
                lines.append(
                    f"{loop_name:<20} {trigger:<15} {scheduler:<10} {last_event:<20} {last_result:<24} {source}"
                )
```

Create `src/mcp/augur_mcp/infrastructure/browse/scheduled_sources/augur_internal.py`:

```python
from __future__ import annotations

import yaml
from src.config.paths import get_project_root, get_runtime_dir


def load_augur_internal_schedules() -> list[dict]:
    project_root = get_project_root()
    config_path = project_root / "skills" / "daemon" / "config.yaml"
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    commands = (payload.get("contributions") or {}).get("commands") or []

    rows: list[dict] = []
    for command in commands:
        loop_cfg = command.get("loop") or {}
        if loop_cfg.get("scheduler", "daemon") != "daemon":
            continue
        if not loop_cfg.get("trigger"):
            continue
        rows.append(
            {
                "id": f"augur-internal:{command['id']}",
                "title": command["id"].replace("-", " ").title(),
                "source": "augur-internal",
                "kind": "internal-schedule",
                "status": "active",
                "workspace": str(project_root),
                "schedule_human": loop_cfg.get("trigger", ""),
                "raw_schedule": {"type": "trigger", "value": loop_cfg.get("trigger", "")},
                "prompt_summary": command.get("description", ""),
                "prompt_body": f"/dev-loops run {loop_cfg.get('name', command['id'])}",
                "native_id": command["id"],
                "source_path": str(config_path),
                "model": "",
                "last_run_at": None,
                "next_run_at": None,
                "warnings": [],
            }
        )
    return rows
```

Patch `src/mcp/augur_mcp/infrastructure/browse/scheduled_executions.py`:

```python
from .scheduled_sources import (
    load_augur_internal_schedules,
    load_claude_schedules,
    load_codex_schedules,
)

    records = [
        *load_augur_internal_schedules(),
        *load_codex_schedules(),
        *load_claude_schedules(),
    ]
```

- [ ] **Step 4: Run the daemon and backend tests to verify they pass**

Run:

```bash
pytest skills/daemon/augur/tests/test_adaptive_discovery.py::TestDiscoverAutoCommands::test_discovers_scheduler_ownership skills/daemon/augur/tests/test_adaptive_loop_executor.py::test_run_all_by_trigger_skips_codex_owned_entries src/mcp/augur_mcp/tests/test_scheduled_executions.py -q
```

Expected:

```text
6 passed
```

- [ ] **Step 5: Commit**

```bash
git add skills/daemon/config.yaml skills/daemon/scripts/adaptive/discovery.py skills/daemon/scripts/adaptive/engine.py skills/daemon/scripts/adaptive/engine_registration.py skills/daemon/scripts/adaptive/loop_reporter.py skills/daemon/augur/tests/test_adaptive_discovery.py skills/daemon/augur/tests/test_adaptive_loop_executor.py src/mcp/augur_mcp/infrastructure/browse/scheduled_sources/augur_internal.py src/mcp/augur_mcp/infrastructure/browse/scheduled_executions.py
git commit -m "feat(daemon): add scheduler ownership for dev-loop migration"
```

## Task 4: Add The Browse Category And Schedule Table UI

**Files:**
- Modify: `apps/dashboard/lib/browse/types.ts`
- Modify: `apps/dashboard/lib/browse/transforms.ts`
- Modify: `apps/dashboard/app/(views)/browse/useBrowseState.ts`
- Modify: `apps/dashboard/app/(views)/browse/BrowseContentGrid.tsx`
- Create: `apps/dashboard/components/shared/ScheduledExecutionTableView.tsx`
- Modify: `tests/dashboard/lib/browse-transforms-index.test.ts`
- Modify: `tests/dashboard/browse/useBrowseState.test.tsx`
- Create: `tests/dashboard/browse/ScheduledExecutionTableView.test.tsx`

- [ ] **Step 1: Write the failing dashboard tests**

Create `tests/dashboard/browse/ScheduledExecutionTableView.test.tsx`:

```tsx
/**
 * @jest-environment jsdom
 */
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import { ScheduledExecutionTableView } from "@/components/shared/ScheduledExecutionTableView";

const rows = [
  {
    id: "codex:update-agents-md",
    title: "Update AGENTS.md",
    description: "Update AGENTS.md with newly discovered workflows/commands",
    hub: "system",
    primaryAction: { label: "View", type: "navigate", target: "codex:update-agents-md" },
    metadata: {
      source: "codex",
      status: "active",
      schedule: "Weekly on Sunday at 11:00",
      workspace: "~/Projects/Augur",
      lastRun: "2026-04-12T08:00:25.728000+00:00",
      nextRun: "2026-04-19T08:00:00+00:00",
    },
  },
];

describe("ScheduledExecutionTableView", () => {
  it("renders source, schedule, status, and workspace columns", () => {
    render(<ScheduledExecutionTableView items={rows} onSelectExecution={jest.fn()} />);
    expect(screen.getByText("Update AGENTS.md")).toBeInTheDocument();
    expect(screen.getByText("codex")).toBeInTheDocument();
    expect(screen.getByText("Weekly on Sunday at 11:00")).toBeInTheDocument();
    expect(screen.getByText("active")).toBeInTheDocument();
  });

  it("opens detail when View is clicked", () => {
    const onSelectExecution = jest.fn();
    render(<ScheduledExecutionTableView items={rows} onSelectExecution={onSelectExecution} />);
    fireEvent.click(screen.getByRole("button", { name: /view/i }));
    expect(onSelectExecution).toHaveBeenCalledWith("codex:update-agents-md");
  });
});
```

Append to `tests/dashboard/lib/browse-transforms-index.test.ts`:

```ts
  it("maps scheduled execution rows into browse metadata", () => {
    const entry = {
      id: "codex:update-agents-md",
      title: "Update AGENTS.md",
      description: "Update AGENTS.md with newly discovered workflows/commands",
      hub: "system",
      metadata: {
        source: "codex",
        kind: "native-schedule",
        status: "active",
        schedule: "Weekly on Sunday at 11:00",
      },
    };

    const result = transformIndexEntry(entry, "scheduled-executions");
    expect(result.metadata?.source).toBe("codex");
    expect(result.metadata?.schedule).toBe("Weekly on Sunday at 11:00");
  });
```

- [ ] **Step 2: Run the dashboard tests to verify they fail**

Run:

```bash
pnpm --filter dashboard test -- --runTestsByPath tests/dashboard/browse/ScheduledExecutionTableView.test.tsx tests/dashboard/lib/browse-transforms-index.test.ts
```

Expected:

```text
FAIL ... Cannot find module '@/components/shared/ScheduledExecutionTableView'
```

- [ ] **Step 3: Implement the category, transform, and schedule table**

Patch `apps/dashboard/lib/browse/types.ts`:

```ts
export type ViewMode =
  | "skills"
  | "pages"
  | "documents"
  | "actions"
  | "commands"
  | "prompts"
  | "integrations"
  | "scheduled-executions"
  | "vault"
  | "wiki"
  | "agents"
  | "workflows"
  | "mcp-tools"
  | "tests"
  | "api-routes"
  | "scripts"
  | "logs";

export interface ScheduledExecutionDetail {
  id: string;
  title: string;
  source: string;
  kind: string;
  status: string;
  workspace?: string;
  schedule_human?: string;
  raw_schedule?: { type: string; value: string };
  prompt_summary: string;
  prompt_body?: string;
  native_id?: string;
  source_path?: string;
  model?: string;
  last_run_at?: string | null;
  next_run_at?: string | null;
  warnings?: string[];
}

  { id: "scheduled-executions", label: "Scheduled Executions", singularLabel: "Scheduled Execution", icon: "CalendarClock", devOnly: false, group: "system", viewLayout: "table" },
```

Patch `apps/dashboard/lib/browse/transforms.ts`:

```ts
    case "scheduled-executions":
      primaryAction = {
        label: "View",
        type: "navigate",
        target: entry.id || entryId,
      };
      break;
```

Create `apps/dashboard/components/shared/ScheduledExecutionTableView.tsx`:

```tsx
'use client';

import type { BrowseItem } from '@/lib/browse/types';

interface ScheduledExecutionTableViewProps {
  items: BrowseItem[];
  onSelectExecution: (executionId: string) => void;
}

export function ScheduledExecutionTableView({
  items,
  onSelectExecution,
}: ScheduledExecutionTableViewProps) {
  return (
    <div className="rounded-xl border border-[var(--border-color)] overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-[var(--bg-secondary)] border-b border-[var(--border-color)]">
          <tr>
            <th className="px-3 py-2 text-left text-xs font-medium text-[var(--text-secondary)]">Execution</th>
            <th className="px-3 py-2 text-left text-xs font-medium text-[var(--text-secondary)]">Source</th>
            <th className="px-3 py-2 text-left text-xs font-medium text-[var(--text-secondary)]">Schedule</th>
            <th className="px-3 py-2 text-left text-xs font-medium text-[var(--text-secondary)]">Workspace</th>
            <th className="px-3 py-2 text-left text-xs font-medium text-[var(--text-secondary)]">Status</th>
            <th className="px-3 py-2 text-left text-xs font-medium text-[var(--text-secondary)]">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--border-color)]">
          {items.map((item) => (
            <tr key={item.id} className="hover:bg-[var(--bg-secondary)]/60 transition-colors">
              <td className="px-3 py-2">{item.title}</td>
              <td className="px-3 py-2">{item.metadata?.source ?? "\u2014"}</td>
              <td className="px-3 py-2">{item.metadata?.schedule ?? "\u2014"}</td>
              <td className="px-3 py-2">{item.metadata?.workspace ?? "\u2014"}</td>
              <td className="px-3 py-2">{item.metadata?.status ?? "\u2014"}</td>
              <td className="px-3 py-2">
                <button
                  onClick={() => onSelectExecution(item.id)}
                  className="px-2 py-1 rounded text-xs font-medium bg-[var(--accent-primary)] text-white hover:opacity-90"
                >
                  View
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

Patch `apps/dashboard/app/(views)/browse/BrowseContentGrid.tsx`:

```tsx
import { ScheduledExecutionTableView } from "@/components/shared/ScheduledExecutionTableView";

  onSelectExecution?: (executionId: string) => void;

  if (effectiveViewMode === "scheduled-executions") {
    return (
      <>
        <ScheduledExecutionTableView
          items={displayItems}
          onSelectExecution={onSelectExecution ?? (() => {})}
        />
        {loadMoreSentinel}
      </>
    );
  }
```

Patch `apps/dashboard/app/(views)/browse/useBrowseState.ts`:

```ts
  const selectedExecution = searchParams.get("execution");

  const selectExecution = useCallback(
    (executionId: string) => {
      const params = new URLSearchParams(searchParams.toString());
      params.set("execution", executionId);
      router.replace(`/browse?${params.toString()}`);
    },
    [router, searchParams],
  );
```

- [ ] **Step 4: Run the dashboard tests to verify they pass**

Run:

```bash
pnpm --filter dashboard test -- --runTestsByPath tests/dashboard/browse/ScheduledExecutionTableView.test.tsx tests/dashboard/lib/browse-transforms-index.test.ts
```

Expected:

```text
PASS tests/dashboard/browse/ScheduledExecutionTableView.test.tsx
PASS tests/dashboard/lib/browse-transforms-index.test.ts
```

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/lib/browse/types.ts apps/dashboard/lib/browse/transforms.ts apps/dashboard/app/(views)/browse/useBrowseState.ts apps/dashboard/app/(views)/browse/BrowseContentGrid.tsx apps/dashboard/components/shared/ScheduledExecutionTableView.tsx tests/dashboard/lib/browse-transforms-index.test.ts tests/dashboard/browse/ScheduledExecutionTableView.test.tsx
git commit -m "feat(dashboard): add scheduled execution browse category"
```

## Task 5: Add Schedule Detail Hooks, Panel, And Browse Wiring

**Files:**
- Create: `apps/dashboard/lib/browse/useScheduledExecutionDetail.ts`
- Create: `apps/dashboard/components/shared/ScheduledExecutionDetailPanel.tsx`
- Modify: `apps/dashboard/app/(views)/browse/useBrowseState.ts`
- Modify: `apps/dashboard/app/(views)/browse/page.tsx`
- Modify: `tests/dashboard/browse/useBrowseState.test.tsx`
- Create: `tests/dashboard/browse/ScheduledExecutionDetailPanel.test.tsx`

- [ ] **Step 1: Write the failing detail-panel tests**

Create `tests/dashboard/browse/ScheduledExecutionDetailPanel.test.tsx`:

```tsx
/**
 * @jest-environment jsdom
 */
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { ScheduledExecutionDetailPanel } from "@/components/shared/ScheduledExecutionDetailPanel";

describe("ScheduledExecutionDetailPanel", () => {
  it("renders prompt body, raw schedule, and warnings", () => {
    render(
      <ScheduledExecutionDetailPanel
        detail={{
          id: "claude:claude-second-brain-report",
          title: "Claude Second Brain Report",
          source: "claude",
          kind: "native-schedule",
          status: "active",
          schedule_human: "Every Friday at 16:00 (raw value, timezone unverified)",
          raw_schedule: { type: "cron", value: "0 16 * * 5" },
          prompt_summary: "Run /wiki report --style demo",
          prompt_body: "Run `/wiki report --style demo`.",
          warnings: ["Claude schedule interpretation is provisional until timezone semantics are verified."],
        }}
        onClose={jest.fn()}
      />
    );

    expect(screen.getByText("Claude Second Brain Report")).toBeInTheDocument();
    expect(screen.getByText("0 16 * * 5")).toBeInTheDocument();
    expect(screen.getByText(/timezone semantics are verified/i)).toBeInTheDocument();
    expect(screen.getByText("Run `/wiki report --style demo`.")).toBeInTheDocument();
  });
});
```

Append to `tests/dashboard/browse/useBrowseState.test.tsx`:

```tsx
  it("keeps selected execution id in the URL state", async () => {
    mockUseSearchParams.mockReturnValue(new URLSearchParams("execution=codex:update-agents-md"));
    mockUseMcpQuery.mockReturnValue({
      data: {
        items: [
          {
            id: "codex:update-agents-md",
            title: "Update AGENTS.md",
            description: "Update AGENTS.md with newly discovered workflows/commands",
            hub: "system",
            type: "scheduled-executions",
            metadata: { source: "codex", schedule: "Weekly on Sunday at 11:00", status: "active" },
          },
        ],
      },
      loading: false,
      error: null,
      refetch: jest.fn(),
    });

    const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
    const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

    await waitFor(() => {
      expect(result.current.filtered[0].id).toBe("codex:update-agents-md");
    });
  });
```

- [ ] **Step 2: Run the dashboard tests to verify they fail**

Run:

```bash
pnpm --filter dashboard test -- --runTestsByPath tests/dashboard/browse/ScheduledExecutionDetailPanel.test.tsx tests/dashboard/browse/useBrowseState.test.tsx
```

Expected:

```text
FAIL ... Cannot find module '@/components/shared/ScheduledExecutionDetailPanel'
```

- [ ] **Step 3: Implement the detail hook and detail panel**

Create `apps/dashboard/lib/browse/useScheduledExecutionDetail.ts`:

```ts
'use client';

import { useMcpQuery } from '@/lib/mcp/useMcpQuery';
import type { ScheduledExecutionDetail } from './types';

export function useScheduledExecutionDetail(executionId: string | null) {
  const { data, loading, error } = useMcpQuery<{ success?: boolean; detail?: ScheduledExecutionDetail; error?: string }>(
    ['scheduled-execution-detail', executionId ?? '__none__'],
    'get-scheduled-execution-detail',
    'config',
    {
      args: executionId ? { execution_id: executionId } : {},
      enabled: !!executionId,
    },
  );

  return {
    detail: data?.detail ?? null,
    loading,
    error: data?.success === false ? data.error ?? 'Failed to load schedule detail' : error,
  };
}
```

Create `apps/dashboard/components/shared/ScheduledExecutionDetailPanel.tsx`:

```tsx
'use client';

import { X } from 'lucide-react';
import type { ScheduledExecutionDetail } from '@/lib/browse/types';

export function ScheduledExecutionDetailPanel({
  detail,
  onClose,
}: {
  detail: ScheduledExecutionDetail;
  onClose: () => void;
}) {
  return (
    <div className="h-full flex flex-col overflow-hidden" role="region" aria-label={`${detail.title} detail panel`}>
      <div className="flex items-start gap-3 p-4 border-b border-[var(--border-color)]">
        <div className="flex-1 min-w-0">
          <h2 className="text-lg font-semibold text-[var(--text-primary)]">{detail.title}</h2>
          <div className="flex items-center gap-2 mt-1 text-xs text-[var(--text-muted)]">
            <span>{detail.source}</span>
            <span>{detail.kind}</span>
            <span>{detail.status}</span>
          </div>
        </div>
        <button title="Close (Esc)" aria-label="Close detail panel" onClick={onClose}>
          <X className="w-4 h-4" />
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <section>
          <h3 className="text-xs font-medium uppercase tracking-wider text-[var(--text-muted)] mb-2">Prompt</h3>
          <pre className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4 whitespace-pre-wrap text-sm">
            {detail.prompt_body || detail.prompt_summary}
          </pre>
        </section>
        <section>
          <h3 className="text-xs font-medium uppercase tracking-wider text-[var(--text-muted)] mb-2">Schedule</h3>
          <div className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4 text-sm space-y-1">
            <div>{detail.schedule_human ?? "\u2014"}</div>
            <code>{detail.raw_schedule?.value ?? "\u2014"}</code>
          </div>
        </section>
        {detail.warnings && detail.warnings.length > 0 && (
          <section>
            <h3 className="text-xs font-medium uppercase tracking-wider text-[var(--text-muted)] mb-2">Warnings</h3>
            <ul className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4 text-sm space-y-2">
              {detail.warnings.map((warning) => <li key={warning}>{warning}</li>)}
            </ul>
          </section>
        )}
      </div>
    </div>
  );
}
```

Patch `apps/dashboard/app/(views)/browse/useBrowseState.ts`:

```ts
import { useScheduledExecutionDetail } from "@/lib/browse/useScheduledExecutionDetail";

  selectedExecution: string | null;
  scheduledExecutionDetail: ReturnType<typeof useScheduledExecutionDetail>["detail"];
  scheduledExecutionLoading: boolean;
  selectExecution: (executionId: string) => void;
  closeExecutionDetail: () => void;

  const { detail: scheduledExecutionDetail, loading: scheduledExecutionLoading } =
    useScheduledExecutionDetail(selectedExecution);

  const closeExecutionDetail = useCallback(() => {
    const params = new URLSearchParams(searchParams.toString());
    params.delete("execution");
    const qs = params.toString();
    router.replace(qs ? `/browse?${qs}` : "/browse");
  }, [router, searchParams]);
```

Patch `apps/dashboard/app/(views)/browse/page.tsx` so the right panel chooses the schedule panel when `effectiveViewMode === "scheduled-executions"`:

```tsx
import { ScheduledExecutionDetailPanel } from "@/components/shared/ScheduledExecutionDetailPanel";

{state.effectiveViewMode === "scheduled-executions" && state.scheduledExecutionDetail ? (
  <ScheduledExecutionDetailPanel
    detail={state.scheduledExecutionDetail}
    onClose={state.closeExecutionDetail}
  />
) : state.skillDetail ? (
  <BrowseDetailPanel detail={state.skillDetail} onClose={state.closeDetail} />
) : null}
```

- [ ] **Step 4: Run the dashboard tests to verify they pass**

Run:

```bash
pnpm --filter dashboard test -- --runTestsByPath tests/dashboard/browse/ScheduledExecutionDetailPanel.test.tsx tests/dashboard/browse/useBrowseState.test.tsx tests/dashboard/browse/ScheduledExecutionTableView.test.tsx
```

Expected:

```text
PASS tests/dashboard/browse/ScheduledExecutionDetailPanel.test.tsx
PASS tests/dashboard/browse/useBrowseState.test.tsx
PASS tests/dashboard/browse/ScheduledExecutionTableView.test.tsx
```

- [ ] **Step 5: Verify in the real browser**

Run:

```bash
/dev-build
```

Then verify manually in Chrome:

```text
1. Open /browse
2. Click "Scheduled Executions"
3. Confirm Codex and Claude rows appear with visible source tags and schedules
4. Open one Codex row and one Claude row
5. Confirm the detail panel shows the full prompt, raw schedule, and Claude warning text
```

Expected:

```text
The page shows real schedule rows and the detail panel renders actual schedule metadata, not an empty skill panel.
```

- [ ] **Step 6: Commit**

```bash
git add apps/dashboard/lib/browse/useScheduledExecutionDetail.ts apps/dashboard/components/shared/ScheduledExecutionDetailPanel.tsx apps/dashboard/app/(views)/browse/useBrowseState.ts apps/dashboard/app/(views)/browse/page.tsx tests/dashboard/browse/ScheduledExecutionDetailPanel.test.tsx tests/dashboard/browse/useBrowseState.test.tsx
git commit -m "feat(dashboard): add scheduled execution detail panel"
```

## Task 6: Define Split Codex Nightly Dev-Loop Jobs And Retire Daemon Nightly Ownership

**Files:**
- Create: `skills/daemon/assets/seeds/codex-dev-loop-schedules.yaml`
- Modify: `skills/daemon/commands/dev-loops.md`
- Modify: `skills/daemon/references/dev-loops-implementation.md`
- Modify: `skills/daemon/config.yaml`

- [ ] **Step 1: Write the failing migration contract test**

Append to `src/mcp/augur_mcp/tests/test_scheduled_executions.py`:

```python
import yaml
from pathlib import Path


def test_codex_dev_loop_schedule_manifest_contains_split_nightly_jobs() -> None:
    payload = yaml.safe_load(
        Path("skills/daemon/assets/seeds/codex-dev-loop-schedules.yaml").read_text(encoding="utf-8")
    )
    ids = [row["id"] for row in payload["schedules"]]
    assert ids == [
        "codex-dev-loop-testing",
        "codex-dev-loop-code-quality",
        "codex-dev-loop-hardening",
        "codex-dev-loop-knowledge-enrichment",
        "codex-dev-loop-skill-standards",
        "codex-dev-loop-skill-quality",
        "codex-dev-loop-observability",
        "codex-dev-loop-duplication",
        "codex-dev-loop-ui-quality",
    ]
```

- [ ] **Step 2: Run the migration contract test to verify it fails**

Run:

```bash
pytest src/mcp/augur_mcp/tests/test_scheduled_executions.py::test_codex_dev_loop_schedule_manifest_contains_split_nightly_jobs -q
```

Expected:

```text
FAILED ... FileNotFoundError: [Errno 2] No such file or directory: 'skills/daemon/assets/seeds/codex-dev-loop-schedules.yaml'
```

- [ ] **Step 3: Create the split Codex schedule manifest and update daemon docs**

Create `skills/daemon/assets/seeds/codex-dev-loop-schedules.yaml`:

```yaml
schedules:
  - id: codex-dev-loop-testing
    loop: testing
    source: codex
    rrule: "RRULE:FREQ=WEEKLY;BYDAY=SU;BYHOUR=3;BYMINUTE=0"
    prompt: "/dev-loops run testing"
  - id: codex-dev-loop-code-quality
    loop: code-quality
    source: codex
    rrule: "RRULE:FREQ=WEEKLY;BYDAY=MO;BYHOUR=3;BYMINUTE=0"
    prompt: "/dev-loops run code-quality"
  - id: codex-dev-loop-hardening
    loop: hardening
    source: codex
    rrule: "RRULE:FREQ=WEEKLY;BYDAY=TU;BYHOUR=3;BYMINUTE=0"
    prompt: "/dev-loops run hardening"
  - id: codex-dev-loop-knowledge-enrichment
    loop: knowledge-enrichment
    source: codex
    rrule: "RRULE:FREQ=WEEKLY;BYDAY=WE;BYHOUR=3;BYMINUTE=0"
    prompt: "/dev-loops run knowledge-enrichment"
  - id: codex-dev-loop-skill-standards
    loop: skill-standards
    source: codex
    rrule: "RRULE:FREQ=WEEKLY;BYDAY=TH;BYHOUR=3;BYMINUTE=0"
    prompt: "/dev-loops run skill-standards"
  - id: codex-dev-loop-skill-quality
    loop: skill-quality
    source: codex
    rrule: "RRULE:FREQ=WEEKLY;BYDAY=FR;BYHOUR=3;BYMINUTE=0"
    prompt: "/dev-loops run skill-quality"
  - id: codex-dev-loop-observability
    loop: observability
    source: codex
    rrule: "RRULE:FREQ=WEEKLY;BYDAY=SA;BYHOUR=3;BYMINUTE=0"
    prompt: "/dev-loops run observability"
  - id: codex-dev-loop-duplication
    loop: duplication
    source: codex
    rrule: "RRULE:FREQ=WEEKLY;BYDAY=SA;BYHOUR=3;BYMINUTE=20"
    prompt: "/dev-loops run duplication"
  - id: codex-dev-loop-ui-quality
    loop: ui-quality
    source: codex
    rrule: "RRULE:FREQ=WEEKLY;BYDAY=SA;BYHOUR=3;BYMINUTE=40"
    prompt: "/dev-loops run ui-quality"
```

Patch `skills/daemon/commands/dev-loops.md` in the `Loops` section and usage notes:

```markdown
| `code-quality` | Codex-native nightly | Lint, format, backlog cleanup |
| `hardening` | Codex-native nightly | Build health, YAML lint, mount checks |
| `knowledge-enrichment` | Codex-native nightly | RAG reindex, data gap filling |
| `skill-standards` | Codex-native nightly | SKILL.md validation, migration, refs |
| `observability` | Codex-native nightly | Repo sync, context audit, perf profiling |
| `testing` | Codex-native nightly | Build, API, MCP, Jest, pytest validation |
| `duplication` | Codex-native nightly | Detect duplicate implementations and consolidate safe mirrors |
| `skill-quality` | Codex-native nightly | Score and improve skills across instruction, product, UI, and wiring |
| `ui-quality` | Codex-native nightly | Audit and improve dashboard UI quality and consistency |

Nightly `dev-loops` ownership is externalized to split Codex automations defined in `assets/seeds/codex-dev-loop-schedules.yaml`. `/dev-loops run --all` remains available for manual worktree-driven maintenance only; it is no longer the daemon's nightly trigger path.
```

Patch `skills/daemon/references/dev-loops-implementation.md`:

```markdown
## Scheduler Ownership

- `self-heal` remains daemon-owned (`continuous` / daemon health remediation)
- `command-evolution` remains daemon-owned (`post-execution`)
- nightly loop families are owned by split Codex-native schedules
- the canonical Codex split-job manifest lives in `../assets/seeds/codex-dev-loop-schedules.yaml`
```

- [ ] **Step 4: Run the migration and doc tests to verify they pass**

Run:

```bash
pytest src/mcp/augur_mcp/tests/test_scheduled_executions.py::test_codex_dev_loop_schedule_manifest_contains_split_nightly_jobs -q
```

Expected:

```text
1 passed
```

- [ ] **Step 5: Perform the cutover check**

Run:

```bash
python - <<'PY'
import yaml
from pathlib import Path
cfg = yaml.safe_load(Path("skills/daemon/config.yaml").read_text())
nightly = [
    (cmd["id"], (cmd.get("loop") or {}).get("name"), (cmd.get("loop") or {}).get("scheduler"))
    for cmd in cfg["contributions"]["commands"]
    if (cmd.get("loop") or {}).get("trigger") == "nightly"
]
print(nightly)
PY
```

Expected:

```text
All nightly dev-loop commands print with scheduler 'codex'; daemon-only flows remain 'daemon' or omit scheduler only when intentionally internal.
```

- [ ] **Step 6: Commit**

```bash
git add skills/daemon/assets/seeds/codex-dev-loop-schedules.yaml skills/daemon/commands/dev-loops.md skills/daemon/references/dev-loops-implementation.md skills/daemon/config.yaml
git commit -m "docs(daemon): define codex-native nightly dev-loop split"
```

---

## Self-Review

### Spec Coverage

- Unified browse surface with source tags: covered by Tasks 1, 4, and 5.
- Adapters for `augur-internal`, `codex`, and `claude`: covered by Tasks 2 and 3.
- Compact table plus detail panel with raw prompt/schedule: covered by Tasks 4 and 5.
- Explicit warning handling for uncertain Claude schedule parsing: covered by Task 2 and verified in Task 5.
- Keep `augur-internal` as a supported source while removing nightly `dev-loops` from daemon ownership: covered by Tasks 3 and 6.
- Split nightly `dev-loops` into distinct Codex jobs: covered by Task 6.

### Placeholder Scan

Search for placeholders:

```bash
python - <<'PY'
from pathlib import Path

text = Path("docs/superpowers/plans/2026-04-12-scheduled-agent-observability.md").read_text()
needles = [
    "TB" "D",
    "imple" "ment later",
    "fill in " "details",
    "appropriate error " "handling",
    "edge " "cases",
    "similar to " "Task",
]
hits = [needle for needle in needles if needle in text]
print("\n".join(hits))
PY
```

Expected:

```text
No matches
```

### Type Consistency

Check the final plan for consistent identifiers:

```bash
rg -n "scheduled-executions|get-scheduled-execution-detail|selectExecution|scheduler|codex-dev-loop" docs/superpowers/plans/2026-04-12-scheduled-agent-observability.md
```

Expected:

```text
Each identifier is spelled consistently across backend, frontend, and daemon migration tasks.
```
