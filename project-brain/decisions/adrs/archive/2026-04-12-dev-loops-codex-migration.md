# Dev-Loops Codex Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move all slower scheduled `dev-loops` execution to local Codex automations, leaving the daemon responsible only for fast self-heal sensing and event capture.

**Architecture:** Derive a canonical migration manifest from the live adaptive loop registry, split mixed loop families into explicit scheduled units, materialize those units as local Codex `automation.toml` files, and remove daemon ownership of nightly and drain execution paths. Keep Augur Browse as the observability surface by surfacing execution environment, ownership, and cutover health for the migrated schedules.

**Tech Stack:** Python 3.11, PyYAML, tomllib, sqlite3, FastMCP, pytest, Jest, Next.js dashboard

**Spec:** `docs/superpowers/specs/2026-04-12-dev-loops-codex-migration-design.md`

**Prerequisite:** `docs/superpowers/plans/2026-04-12-scheduled-agent-observability.md` is already in place and provides the `scheduled-executions` browse surface that this migration will feed.

---

## File Structure

### Create

| File | Responsibility |
|---|---|
| `skills/daemon/scripts/adaptive/codex_schedule_manifest.py` | Build the canonical `loop + trigger + owner + cadence` migration manifest from the live adaptive registry |
| `skills/daemon/scripts/sync_codex_automations.py` | Convert the manifest into local Codex `automation.toml` directories with `execution_environment = "local"` |
| `skills/daemon/augur/tests/test_codex_schedule_manifest.py` | Verify manifest generation, split loop units, cadence defaults, and local-only metadata |
| `skills/daemon/augur/tests/test_codex_schedule_sync.py` | Verify automation file generation and local-only Codex sync behavior |

### Modify

| File | Change |
|---|---|
| `skills/daemon/assets/seeds/codex-dev-loop-schedules.yaml` | Expand from the first nightly batch to the full migration inventory, including drains and validation jobs |
| `skills/daemon/config.yaml` | Remove daemon ownership from nightly validation and make split scheduler ownership explicit |
| `skills/daemon/scripts/adaptive_loop_executor.py` | Add manifest/export/sync entrypoints plus explicit `--drain` and `--validate` execution modes |
| `skills/daemon/scripts/adaptive/engine_queue.py` | Separate queue materialization from queue-triggered execution so daemon no longer drains scheduled work |
| `skills/daemon/scripts/adaptive/loop_reporter.py` | Report split ownership and cutover health instead of treating loop families as implicitly daemon-owned |
| `skills/daemon/scripts/mcp/_loops.py` | Surface split ownership and trigger details through MCP loop-status data used by dashboard/ops surfaces |
| `skills/daemon/commands/dev-loops.md` | Document the new split execution units, local Codex ownership, and manual-only `run --all` path |
| `skills/daemon/references/dev-loops-implementation.md` | Replace legacy daemon nightly ownership notes with Codex-owned scheduled units and fast-daemon-only boundary |
| `skills/daemon/augur/tests/test_adaptive_loop_executor.py` | Cover drain/validate entrypoints and daemon loop-mode cutover behavior |
| `skills/daemon/augur/tests/test_adaptive_discovery.py` | Verify scheduler ownership for split units after config changes |
| `skills/daemon/augur/tests/test_loop_reporter.py` | Verify mixed-family ownership reporting and cutover visibility |
| `src/mcp/augur_mcp/infrastructure/browse/scheduled_sources/codex.py` | Surface `execution_environment`, enforce local warnings, and normalize new Codex automation records |
| `src/mcp/augur_mcp/tests/test_scheduled_executions.py` | Verify Codex schedules expose `execution_environment = local` and warnings for non-local entries |
| `apps/dashboard/lib/browse/types.ts` | Add execution-environment fields to the schedule detail contract |
| `apps/dashboard/components/shared/ScheduledExecutionDetailPanel.tsx` | Show `Runs In` / execution environment in the schedule detail panel |
| `tests/dashboard/browse/ScheduledExecutionDetailPanel.test.tsx` | Verify the detail panel renders `Runs In: local` for Codex schedules |

---

## Task 1: Build The Canonical Codex Migration Manifest

**Files:**
- Create: `skills/daemon/scripts/adaptive/codex_schedule_manifest.py`
- Modify: `skills/daemon/scripts/adaptive_loop_executor.py`
- Create: `skills/daemon/augur/tests/test_codex_schedule_manifest.py`

- [ ] **Step 1: Write the failing manifest-generation tests**

Create `skills/daemon/augur/tests/test_codex_schedule_manifest.py`:

```python
from __future__ import annotations

from skills.daemon.scripts.adaptive.discovery import AutoCommandEntry


class _Module:
    name = "test-module"


def _entry(name: str, loop: str, trigger: str, scheduler: str = "daemon") -> AutoCommandEntry:
    return AutoCommandEntry(
        name=name,
        module=_Module(),
        loop_name=loop,
        trigger=trigger,
        scheduler=scheduler,
    )


def test_build_codex_schedule_manifest_splits_mixed_families() -> None:
    from skills.daemon.scripts.adaptive.codex_schedule_manifest import build_codex_schedule_manifest

    registry = {
        "auto-self-heal": _entry("auto-self-heal", "self-heal", "continuous", "daemon"),
        "auto-heal-validate": _entry("auto-heal-validate", "self-heal", "nightly", "daemon"),
        "auto-command-evolution": _entry("auto-command-evolution", "command-evolution", "post-execution", "daemon"),
        "auto-memory-consolidation": _entry("auto-memory-consolidation", "knowledge-enrichment", "nightly", "daemon"),
        "auto-testing": _entry("auto-testing", "testing", "nightly", "daemon"),
    }

    manifest = build_codex_schedule_manifest(registry)
    ids = {row["id"] for row in manifest}

    assert "codex-dev-loop-testing" in ids
    assert "codex-dev-loop-self-heal-validate" in ids
    assert "codex-command-evolution-drain" in ids
    assert "codex-knowledge-enrichment-nightly" in ids
    assert "codex-knowledge-enrichment-drain" in ids
    assert "self-heal-fast" not in ids


def test_manifest_marks_every_codex_unit_local() -> None:
    from skills.daemon.scripts.adaptive.codex_schedule_manifest import build_codex_schedule_manifest

    manifest = build_codex_schedule_manifest(
        {
            "auto-testing": _entry("auto-testing", "testing", "nightly", "daemon"),
        }
    )

    assert manifest[0]["id"] == "codex-dev-loop-testing"
    assert all(row["runs_in"] == "local" for row in manifest)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
pytest skills/daemon/augur/tests/test_codex_schedule_manifest.py -q
```

Expected: `ModuleNotFoundError` for `codex_schedule_manifest` or assertion failures because the manifest builder does not exist yet.

- [ ] **Step 3: Implement the manifest builder and CLI export**

Create `skills/daemon/scripts/adaptive/codex_schedule_manifest.py`:

```python
from __future__ import annotations

from dataclasses import asdict, dataclass


WEEKLY_SLOTS = {
    "testing": "weekly-sunday-03:00",
    "code-quality": "weekly-monday-03:00",
    "hardening": "weekly-tuesday-03:00",
    "knowledge-enrichment-nightly": "weekly-wednesday-03:00",
    "skill-standards": "weekly-thursday-03:00",
    "skill-quality": "weekly-friday-03:00",
    "observability": "weekly-saturday-03:00",
    "duplication": "weekly-saturday-03:20",
    "ui-quality": "weekly-saturday-03:40",
    "auto-agent-digest": "weekly-saturday-04:00",
    "file-organizer": "weekly-saturday-04:20",
    "page-health": "weekly-saturday-04:40",
}


@dataclass(frozen=True)
class ManifestUnit:
    id: str
    loop: str
    mode: str
    source_commands: list[str]
    current_owner: str
    target_owner: str
    client: str
    runs_in: str
    cadence: str
    workspace: str
    prompt: str
    depends_on: list[str]
    cutover_state: str
    browse_title: str


def build_codex_schedule_manifest(registry: dict[str, object]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str], list[str]] = {}
    for command_id, entry in registry.items():
        key = (getattr(entry, "loop_name"), getattr(entry, "trigger"))
        grouped.setdefault(key, []).append(command_id)

    rows: list[ManifestUnit] = []
    for (loop_name, trigger), command_ids in sorted(grouped.items()):
        if loop_name == "self-heal" and trigger == "continuous":
            continue
        if loop_name == "command-evolution" and trigger == "post-execution":
            rows.append(
                ManifestUnit(
                    id="codex-command-evolution-drain",
                    loop="command-evolution",
                    mode="drain",
                    source_commands=sorted(command_ids),
                    current_owner="daemon",
                    target_owner="codex",
                    client="codex",
                    runs_in="local",
                    cadence="every-15-minutes",
                    workspace="~/Projects/Augur",
                    prompt="/dev-loops run command-evolution --drain",
                    depends_on=[],
                    cutover_state="planned",
                    browse_title="Command Evolution Drain",
                )
            )
            continue
        normalized_loop = (
            "knowledge-enrichment-nightly"
            if loop_name == "knowledge-enrichment" and trigger == "nightly"
            else "self-heal-nightly-validate"
            if loop_name == "self-heal" and trigger == "nightly"
            else loop_name
        )
        rows.append(
            ManifestUnit(
                id=f"codex-dev-loop-{normalized_loop}",
                loop=normalized_loop,
                mode="nightly",
                source_commands=sorted(command_ids),
                current_owner="daemon",
                target_owner="codex",
                client="codex",
                runs_in="local",
                cadence=WEEKLY_SLOTS.get(normalized_loop, "nightly-03:00"),
                workspace="~/Projects/Augur",
                prompt=f"/dev-loops run {loop_name}" + (" --validate" if loop_name == "self-heal" and trigger == "nightly" else ""),
                depends_on=[],
                cutover_state="planned",
                browse_title=normalized_loop.replace("-", " ").title(),
            )
        )
        if loop_name == "knowledge-enrichment" and trigger == "nightly":
            rows.append(
                ManifestUnit(
                    id="codex-knowledge-enrichment-drain",
                    loop="knowledge-enrichment",
                    mode="drain",
                    source_commands=sorted(command_ids),
                    current_owner="daemon",
                    target_owner="codex",
                    client="codex",
                    runs_in="local",
                    cadence="hourly",
                    workspace="~/Projects/Augur",
                    prompt="/dev-loops run knowledge-enrichment --drain",
                    depends_on=[],
                    cutover_state="planned",
                    browse_title="Knowledge Enrichment Drain",
                )
            )
    return [asdict(row) for row in rows]
```

Patch `skills/daemon/scripts/adaptive_loop_executor.py` to expose the manifest:

```python
from skills.daemon.scripts.adaptive.codex_schedule_manifest import build_codex_schedule_manifest
from skills.daemon.scripts.adaptive.discovery import discover_auto_commands
import yaml

parser.add_argument("--manifest", action="store_true", help="Print Codex migration manifest and exit")

if args.manifest:
    registry = discover_auto_commands(project_root)
    print(yaml.safe_dump({"schedules": build_codex_schedule_manifest(registry)}, sort_keys=False))
    return
```

- [ ] **Step 4: Run the focused tests and CLI export**

Run:

```bash
pytest skills/daemon/augur/tests/test_codex_schedule_manifest.py -q
python skills/daemon/scripts/adaptive_loop_executor.py manifest | sed -n '1,120p'
```

Expected:
- `2 passed`
- CLI output starts with `schedules:` and includes `codex-command-evolution-drain`, `codex-dev-loop-self-heal-validate`, and `runs_in: local`

- [ ] **Step 5: Commit**

```bash
git add skills/daemon/scripts/adaptive/codex_schedule_manifest.py skills/daemon/scripts/adaptive_loop_executor.py skills/daemon/augur/tests/test_codex_schedule_manifest.py
git commit -m "feat: generate codex migration manifest for dev loops"
```

---

## Task 2: Split Mixed Loop Entry Points And Stop Daemon-Owned Scheduled Execution

**Files:**
- Modify: `skills/daemon/config.yaml`
- Modify: `skills/daemon/scripts/adaptive_loop_executor.py`
- Modify: `skills/daemon/scripts/adaptive/engine_queue.py`
- Modify: `skills/daemon/augur/tests/test_adaptive_loop_executor.py`
- Modify: `skills/daemon/augur/tests/test_adaptive_discovery.py`

- [ ] **Step 1: Write the failing executor and discovery tests**

Append to `skills/daemon/augur/tests/test_adaptive_loop_executor.py`:

```python
def test_daemon_loop_mode_no_longer_drains_post_exec_queue(monkeypatch, tmp_path):
    from skills.daemon.scripts import adaptive_loop_executor as executor

    class StubEngine:
        def __init__(self):
            self.drained = False
            self.triggers = []
        def run_all_by_trigger(self, trigger):
            self.triggers.append(trigger)
            return {}
        def drain_post_exec_queue(self):
            self.drained = True
            return 1

    engine = StubEngine()
    monkeypatch.setattr(executor, "_build_engine", lambda *args, **kwargs: engine)
    monkeypatch.setattr(executor.time, "sleep", lambda _: (_ for _ in ()).throw(KeyboardInterrupt()))

    try:
        executor.main(["--loop"])
    except KeyboardInterrupt:
        pass

    assert engine.drained is False
    assert engine.triggers == ["continuous"]


def test_run_command_evolution_drain_uses_post_execution_filter(monkeypatch):
    from skills.daemon.scripts import adaptive_loop_executor as executor

    called = {}

    class StubEngine:
        def run_auto_cycle(self, loop_name, trigger_filter=None):
            called["loop_name"] = loop_name
            called["trigger_filter"] = trigger_filter
            return object()

    monkeypatch.setattr(executor, "_build_engine", lambda *args, **kwargs: StubEngine())
    executor.main(["run", "command-evolution", "--drain"])
    assert called == {"loop_name": "command-evolution", "trigger_filter": "post-execution"}
```

Append to `skills/daemon/augur/tests/test_adaptive_discovery.py`:

```python
def test_daemon_config_marks_self_heal_validate_codex_owned():
    from pathlib import Path
    import yaml

    config = yaml.safe_load(Path("skills/daemon/config.yaml").read_text())
    auto_heal_validate = next(
        command for command in config["contributions"]["commands"] if command["id"] == "auto-heal-validate"
    )

    assert auto_heal_validate["loop"]["scheduler"] == "codex"
    assert auto_heal_validate["loop"]["trigger"] == "nightly"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
pytest skills/daemon/augur/tests/test_adaptive_loop_executor.py::test_daemon_loop_mode_no_longer_drains_post_exec_queue skills/daemon/augur/tests/test_adaptive_loop_executor.py::test_run_command_evolution_drain_uses_post_execution_filter skills/daemon/augur/tests/test_adaptive_discovery.py::test_daemon_config_marks_self_heal_validate_codex_owned -q
```

Expected: failures because daemon loop mode still drains the queue, `--drain` is unsupported, and `auto-heal-validate` is still daemon-owned.

- [ ] **Step 3: Implement split entrypoints and daemon cutover**

Patch `skills/daemon/config.yaml`:

```yaml
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
      scheduler: codex
```

Patch `skills/daemon/scripts/adaptive/engine_queue.py` to split queue consumption from execution:

```python
class QueueMixin:
    def consume_post_exec_queue(self) -> list[dict]:
        queue_path = self._resolve_post_exec_queue_path()
        if not queue_path.exists():
            return []
        content = queue_path.read_text().strip()
        if not content:
            return []
        events = [json.loads(line) for line in content.splitlines() if line.strip()]
        queue_path.write_text("")
        return events

    def materialize_post_exec_events(self, events: list[dict]) -> None:
        for event in events:
            cmd = event.get("command", "unknown")
            log_dir = self._runtime_dir / "command-evolution" / cmd / "executions"
            log_dir.mkdir(parents=True, exist_ok=True)
            ts = event.get("timestamp", datetime.now(timezone.utc).isoformat()).replace(":", "-")[:19]
            (log_dir / f"{ts}.json").write_text(json.dumps(event, indent=2))
```

Patch `skills/daemon/scripts/adaptive_loop_executor.py`:

```python
parser.add_argument("--drain", action="store_true", help="Run drain-only mode for drain-capable loops")
parser.add_argument("--validate", action="store_true", help="Run validation-only mode for validation-capable loops")

if args.run == "command-evolution" and args.drain:
    events = engine.consume_post_exec_queue()
    engine.materialize_post_exec_events(events)
    engine.run_auto_cycle("command-evolution", trigger_filter="post-execution")
    return

if args.run == "knowledge-enrichment" and args.drain:
    engine.run_auto_cycle("knowledge-enrichment")
    return

if args.run == "self-heal" and args.validate:
    engine.run_auto_cycle("self-heal", trigger_filter="nightly")
    return

# In daemon --loop mode, delete the automatic nightly, weekly, and post-exec drain blocks entirely.
# After cutover, daemon loop mode only runs continuous work.
```

- [ ] **Step 4: Run the focused tests**

Run:

```bash
pytest skills/daemon/augur/tests/test_adaptive_loop_executor.py::test_daemon_loop_mode_no_longer_drains_post_exec_queue skills/daemon/augur/tests/test_adaptive_loop_executor.py::test_run_command_evolution_drain_uses_post_execution_filter skills/daemon/augur/tests/test_adaptive_discovery.py::test_daemon_config_marks_self_heal_validate_codex_owned -q
```

Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add skills/daemon/config.yaml skills/daemon/scripts/adaptive_loop_executor.py skills/daemon/scripts/adaptive/engine_queue.py skills/daemon/augur/tests/test_adaptive_loop_executor.py skills/daemon/augur/tests/test_adaptive_discovery.py
git commit -m "feat: split dev loop execution ownership for codex cutover"
```

---

## Task 3: Materialize Full Local Codex Automations From The Manifest

**Files:**
- Modify: `skills/daemon/assets/seeds/codex-dev-loop-schedules.yaml`
- Create: `skills/daemon/scripts/sync_codex_automations.py`
- Create: `skills/daemon/augur/tests/test_codex_schedule_sync.py`

- [ ] **Step 1: Write the failing sync tests**

Create `skills/daemon/augur/tests/test_codex_schedule_sync.py`:

```python
from __future__ import annotations

from pathlib import Path


def test_sync_codex_automations_writes_local_execution_environment(tmp_path, monkeypatch) -> None:
    from skills.daemon.scripts.sync_codex_automations import sync_codex_automations

    monkeypatch.setenv("HOME", str(tmp_path))
    schedules = [
        {
            "id": "codex-command-evolution-drain",
            "browse_title": "Command Evolution Drain",
            "rrule": "RRULE:FREQ=MINUTELY;INTERVAL=15",
            "prompt": "/dev-loops run command-evolution --drain",
            "workspace": "~/Projects/Augur",
            "model": "gpt-5.4",
            "reasoning_effort": "high",
            "runs_in": "local",
        }
    ]

    written = sync_codex_automations(schedules, apply=True)
    automation_toml = Path(tmp_path) / ".codex" / "automations" / "codex-command-evolution-drain" / "automation.toml"

    assert written == [automation_toml]
    content = automation_toml.read_text()
    assert 'execution_environment = "local"' in content
    assert 'prompt = "/dev-loops run command-evolution --drain"' in content
    assert 'cwds = ["~/Projects/Augur"]' in content
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
pytest skills/daemon/augur/tests/test_codex_schedule_sync.py -q
```

Expected: `ModuleNotFoundError` for `sync_codex_automations`.

- [ ] **Step 3: Expand the seed manifest and implement the sync tool**

Patch `skills/daemon/assets/seeds/codex-dev-loop-schedules.yaml` so it includes the full migration inventory and local execution metadata:

```yaml
schedules:
  - id: codex-dev-loop-self-heal-validate
    loop: self-heal-nightly-validate
    source: codex
    rrule: "RRULE:FREQ=DAILY;BYHOUR=3;BYMINUTE=55"
    prompt: "/dev-loops run self-heal --validate"
    workspace: "~/Projects/Augur"
    model: "gpt-5.4"
    reasoning_effort: "high"
    runs_in: local
  - id: codex-command-evolution-drain
    loop: command-evolution
    source: codex
    rrule: "RRULE:FREQ=MINUTELY;INTERVAL=15"
    prompt: "/dev-loops run command-evolution --drain"
    workspace: "~/Projects/Augur"
    model: "gpt-5.4"
    reasoning_effort: "high"
    runs_in: local
  - id: codex-knowledge-enrichment-drain
    loop: knowledge-enrichment
    source: codex
    rrule: "RRULE:FREQ=HOURLY"
    prompt: "/dev-loops run knowledge-enrichment --drain"
    workspace: "~/Projects/Augur"
    model: "gpt-5.4"
    reasoning_effort: "high"
    runs_in: local
```

Create `skills/daemon/scripts/sync_codex_automations.py`:

```python
from __future__ import annotations

from pathlib import Path
import tomli_w


def sync_codex_automations(schedules: list[dict[str, object]], *, apply: bool) -> list[Path]:
    home = Path.home()
    root = home / ".codex" / "automations"
    written: list[Path] = []
    for schedule in schedules:
        automation_dir = root / str(schedule["id"])
        automation_toml = automation_dir / "automation.toml"
        payload = {
            "version": 1,
            "id": str(schedule["id"]),
            "kind": "cron",
            "name": str(schedule["browse_title"]),
            "prompt": str(schedule["prompt"]),
            "status": "ACTIVE",
            "rrule": str(schedule["rrule"]),
            "model": str(schedule["model"]),
            "reasoning_effort": str(schedule["reasoning_effort"]),
            "execution_environment": str(schedule["runs_in"]),
            "cwds": [str(schedule["workspace"])],
        }
        if apply:
            automation_dir.mkdir(parents=True, exist_ok=True)
            automation_toml.write_text(tomli_w.dumps(payload), encoding="utf-8")
            written.append(automation_toml)
    return written
```

- [ ] **Step 4: Run the tests and a dry-run/apply smoke check**

Run:

```bash
pytest skills/daemon/augur/tests/test_codex_schedule_sync.py -q
python skills/daemon/scripts/sync_codex_automations.py --dry-run | sed -n '1,80p'
```

Expected:
- `1 passed`
- dry-run output lists the full automation ids, including `codex-dev-loop-self-heal-validate` and `codex-command-evolution-drain`

- [ ] **Step 5: Commit**

```bash
git add skills/daemon/assets/seeds/codex-dev-loop-schedules.yaml skills/daemon/scripts/sync_codex_automations.py skills/daemon/augur/tests/test_codex_schedule_sync.py
git commit -m "feat: sync full dev loop migration into local codex automations"
```

---

## Task 4: Surface Local Codex Execution And Split Ownership In Observability

**Files:**
- Modify: `skills/daemon/scripts/adaptive/loop_reporter.py`
- Modify: `skills/daemon/scripts/mcp/_loops.py`
- Modify: `src/mcp/augur_mcp/infrastructure/browse/scheduled_sources/codex.py`
- Modify: `src/mcp/augur_mcp/tests/test_scheduled_executions.py`
- Modify: `apps/dashboard/lib/browse/types.ts`
- Modify: `apps/dashboard/components/shared/ScheduledExecutionDetailPanel.tsx`
- Modify: `tests/dashboard/browse/ScheduledExecutionDetailPanel.test.tsx`
- Modify: `skills/daemon/augur/tests/test_loop_reporter.py`

- [ ] **Step 1: Write the failing observability tests**

Append to `src/mcp/augur_mcp/tests/test_scheduled_executions.py`:

```python
def test_codex_loader_exposes_execution_environment_and_non_local_warning(tmp_path, monkeypatch):
    from augur_mcp.infrastructure.browse.scheduled_sources.codex import load_codex_schedules

    home = tmp_path
    automation_dir = home / ".codex" / "automations" / "non-local"
    automation_dir.mkdir(parents=True)
    (automation_dir / "automation.toml").write_text(
        '\n'.join(
            [
                'version = 1',
                'id = "non-local"',
                'kind = "cron"',
                'name = "Non Local"',
                'prompt = "/dev-loops run testing"',
                'status = "ACTIVE"',
                'rrule = "RRULE:FREQ=DAILY;BYHOUR=3;BYMINUTE=0"',
                'model = "gpt-5.4"',
                'reasoning_effort = "high"',
                'execution_environment = "remote"',
                'cwds = ["~/Projects/Augur"]',
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("pathlib.Path.home", lambda: home)

    record = load_codex_schedules()[0]
    assert record["execution_environment"] == "remote"
    assert record["warnings"] == ["Codex schedule is not local; cutover is blocked until execution_environment = local."]
```

Append to `tests/dashboard/browse/ScheduledExecutionDetailPanel.test.tsx`:

```tsx
it("renders the runs-in field for codex schedules", async () => {
  const { ScheduledExecutionDetailPanel } = await import(
    "@/components/shared/ScheduledExecutionDetailPanel"
  );

  render(
    <ScheduledExecutionDetailPanel
      detail={{
        id: "codex:command-evolution-drain",
        title: "Command Evolution Drain",
        source: "codex",
        kind: "native-schedule",
        status: "active",
        workspace: "~/Projects/Augur",
        schedule_human: "Every 15 minutes",
        prompt_summary: "/dev-loops run command-evolution --drain",
        prompt_body: "/dev-loops run command-evolution --drain",
        raw_schedule: { type: "rrule", value: "RRULE:FREQ=MINUTELY;INTERVAL=15" },
        source_path: "/Users/test/.codex/automations/codex-command-evolution-drain/automation.toml",
        model: "gpt-5.4",
        execution_environment: "local",
        last_run_at: null,
        next_run_at: null,
        warnings: [],
      }}
      onClose={jest.fn()}
    />,
  );

  expect(screen.getByText("Runs In")).toBeInTheDocument();
  expect(screen.getByText("local")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
pytest src/mcp/augur_mcp/tests/test_scheduled_executions.py -q
cd apps/dashboard && pnpm jest ../../tests/dashboard/browse/ScheduledExecutionDetailPanel.test.tsx --runInBand
```

Expected:
- pytest fails because Codex records do not expose `execution_environment`
- Jest fails because the detail panel does not render `Runs In`

- [ ] **Step 3: Implement local-execution observability**

Patch `src/mcp/augur_mcp/infrastructure/browse/scheduled_sources/codex.py`:

```python
execution_environment = str(data.get("execution_environment", "unknown")).lower()
warnings: list[str] = []
if execution_environment != "local":
    warnings.append(
        "Codex schedule is not local; cutover is blocked until execution_environment = local."
    )

records.append(
    {
        "id": f"codex:{native_id}",
        "title": str(data.get("name", native_id)),
        "source": "codex",
        "kind": "native-schedule",
        "status": str(status).lower(),
        "workspace": workspace,
        "execution_environment": execution_environment,
        "schedule_human": rrule,
        "raw_schedule": {"type": "rrule", "value": rrule},
        "prompt_summary": prompt,
        "prompt_body": prompt,
        "native_id": native_id,
        "source_path": str(toml_path),
        "model": str(data.get("model", "")),
        "last_run_at": state.get("last_run_at"),
        "next_run_at": state.get("next_run_at"),
        "warnings": warnings,
    }
)
```

Patch `apps/dashboard/components/shared/ScheduledExecutionDetailPanel.tsx`:

```tsx
<DetailRow label="Runs In" value={detail.execution_environment} />
```

Patch `skills/daemon/scripts/adaptive/loop_reporter.py` so split-family ownership is explicit:

```python
if loop_name == "self-heal":
    scheduler = "mixed"
    source = "daemon continuous + codex nightly-validate"
elif loop_name == "command-evolution":
    scheduler = "codex"
    source = "codex drain + daemon event-capture"
```

- [ ] **Step 4: Run the focused backend and dashboard tests**

Run:

```bash
PYTHONPATH=~/Projects/Augur:~/Projects/Augur/src/mcp pytest src/mcp/augur_mcp/tests/test_scheduled_executions.py skills/daemon/augur/tests/test_loop_reporter.py -q
cd apps/dashboard && pnpm jest ../../tests/dashboard/browse/ScheduledExecutionDetailPanel.test.tsx --runInBand
```

Expected:
- pytest passes, including the new execution-environment assertions
- Jest passes and renders `Runs In: local`

- [ ] **Step 5: Commit**

```bash
git add skills/daemon/scripts/adaptive/loop_reporter.py skills/daemon/scripts/mcp/_loops.py src/mcp/augur_mcp/infrastructure/browse/scheduled_sources/codex.py src/mcp/augur_mcp/tests/test_scheduled_executions.py apps/dashboard/lib/browse/types.ts apps/dashboard/components/shared/ScheduledExecutionDetailPanel.tsx tests/dashboard/browse/ScheduledExecutionDetailPanel.test.tsx skills/daemon/augur/tests/test_loop_reporter.py
git commit -m "feat: expose local codex execution in dev loop observability"
```

---

## Task 5: Finalize Docs, Apply The Cutover, And Verify End-To-End

**Files:**
- Modify: `skills/daemon/commands/dev-loops.md`
- Modify: `skills/daemon/references/dev-loops-implementation.md`
- Modify: `skills/daemon/assets/seeds/codex-dev-loop-schedules.yaml`

- [ ] **Step 1: Write the failing documentation/acceptance checks**

Add a lightweight acceptance test to `skills/daemon/augur/tests/test_adaptive_loop_executor.py`:

```python
def test_manifest_contains_no_run_all_schedule(tmp_path, monkeypatch):
    from skills.daemon.scripts.adaptive.codex_schedule_manifest import build_codex_schedule_manifest
    from skills.daemon.scripts.adaptive.discovery import AutoCommandEntry

    manifest = build_codex_schedule_manifest(
        {
            "auto-testing": AutoCommandEntry(
                name="auto-testing",
                module=type("M", (), {"name": "m"})(),
                loop_name="testing",
                trigger="nightly",
                scheduler="daemon",
            )
        }
    )

    assert all("--all" not in row["prompt"] for row in manifest)
```

- [ ] **Step 2: Run the acceptance check**

Run:

```bash
pytest skills/daemon/augur/tests/test_adaptive_loop_executor.py::test_manifest_contains_no_run_all_schedule -q
```

Expected: `1 passed`

- [ ] **Step 3: Update docs and perform the cutover sequence**

Patch `skills/daemon/commands/dev-loops.md`:

```md
| `self-heal` | Continuous in daemon, nightly validate in Codex | Fast local healing stays in daemon; scheduled validation runs as a local Codex automation |
| `command-evolution` | Codex drain | Queue capture stays local, scheduled drain runs in Codex every 15 minutes |
| `knowledge-enrichment` | Codex nightly + hourly drain | Nightly maintenance and slower follow-up work are both Codex-owned |

`/dev-loops run --all` remains manual-only and must never appear in a scheduled automation.
```

Patch `skills/daemon/references/dev-loops-implementation.md`:

```md
- daemon owns only `self-heal-fast` and event capture
- all nightly `dev-loops` units are local Codex automations
- scheduled drains (`command-evolution`, `knowledge-enrichment`) are local Codex automations
- any Codex automation with `execution_environment != local` blocks cutover
```

Run the implementation acceptance commands:

```bash
python skills/daemon/scripts/adaptive_loop_executor.py manifest > /tmp/dev-loops-codex-manifest.yaml
python skills/daemon/scripts/sync_codex_automations.py --apply
ls ~/.codex/automations | rg 'codex-(dev-loop|command-evolution|knowledge-enrichment)'
sed -n '1,80p' ~/.codex/automations/codex-command-evolution-drain/automation.toml
```

Expected:
- manifest file exists in `/tmp`
- local Codex automation directories exist for every planned unit
- `automation.toml` contains `execution_environment = "local"`

- [ ] **Step 4: Run the full verification suite**

Run:

```bash
PYTHONPATH=~/Projects/Augur:~/Projects/Augur/src/mcp pytest \
  skills/daemon/augur/tests/test_codex_schedule_manifest.py \
  skills/daemon/augur/tests/test_codex_schedule_sync.py \
  skills/daemon/augur/tests/test_adaptive_discovery.py \
  skills/daemon/augur/tests/test_adaptive_loop_executor.py \
  skills/daemon/augur/tests/test_loop_reporter.py \
  src/mcp/augur_mcp/tests/test_scheduled_executions.py -q

cd apps/dashboard && pnpm jest \
  ../../tests/dashboard/browse/ScheduledExecutionDetailPanel.test.tsx \
  ../../tests/dashboard/browse/useBrowseState.test.tsx \
  ../../tests/dashboard/lib/browse-transforms-index.test.ts \
  --runInBand
```

Expected:
- pytest passes for the migration-specific backend suite
- Jest passes for the schedule-detail browse path

Then perform browser verification on `/browse`:

1. Open `Scheduled Executions`
2. Confirm Codex rows exist for nightly, drain, and validate units
3. Open one Codex detail panel and verify `Runs In: local`
4. Confirm no daemon-owned nightly `dev-loops` rows remain

- [ ] **Step 5: Commit**

```bash
git add skills/daemon/commands/dev-loops.md skills/daemon/references/dev-loops-implementation.md skills/daemon/assets/seeds/codex-dev-loop-schedules.yaml skills/daemon/augur/tests/test_adaptive_loop_executor.py
git commit -m "docs: finalize dev loops codex cutover"
```

---

## Self-Review Checklist

- Spec coverage:
  - canonical manifest from live registry: Task 1
  - daemon keeps only fast self-heal and event capture: Task 2
  - full local Codex automation materialization: Task 3
  - Browse shows local execution semantics: Task 4
  - `run --all` stays manual-only and docs/cutover are explicit: Task 5
- Placeholder scan:
  - no `TBD`, `TODO`, or “implement later” text remains in this plan
- Type consistency:
  - `execution_environment`, `runs_in`, `cutover_state`, and split ids use one consistent naming scheme throughout
