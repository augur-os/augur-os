---
status: Implemented
date: '2026-01-18'
deciders:
- '@gsannikov'
related: []
hub: null
tags:
- unified
- task
- runner
superseded_by: null
---

# ADR-010: Unified Task Runner

## Context

Augur has multiple mechanisms for running scheduled/background tasks:

1. **Cron jobs** - Traditional Unix scheduler (via user's crontab)
2. **Makefile targets** - Developer-friendly manual triggers (`make scrape-competitors`)
3. **GitHub Actions** - CI/CD nightly jobs (`.github/workflows/cron-nightly.yml`)
4. **Launchd** - macOS native scheduler (`com.augur.nightly.plist`)
5. **Nightly Maintainer** - Existing Python script (`.github/scripts/nightly_maintainer.py`)
6. **Goodnight routine** - Conceptual end-of-day maintenance

This fragmentation causes:
- Tasks scattered across multiple systems (hard to discover)
- Inconsistent scheduling (cron vs launchd vs GitHub Actions)
- No unified visibility (can't see all scheduled tasks in one place)
- Silent failures (no dashboard integration)
- Duplication (same logic implemented differently per mechanism)

### Triggering Use Case

Adding competitor scraping for Claude Code Templates revealed the need to choose between cron, makefile, or goodnight routine - highlighting the lack of a unified approach.

## Decision

Consolidate all scheduled task mechanisms into a **Unified Task Runner** that:

1. **Single task registry** (`src/tasks/tasks.yaml`) defines all scheduled tasks
2. **Single runner script** (`.github/scripts/task_runner.py`) executes tasks
3. **Single launchd/cron entry** calls the runner with `--scheduled` flag
4. **Multiple entry points** all route through the same runner:
   - Launchd (macOS) - existing `com.augur.nightly.plist` → calls `task_runner.py`
   - Makefile - `make task TASK=name` → calls `task_runner.py --task name`
   - CLI - `exo run-task name` → calls `task_runner.py --task name`
   - Dashboard - API endpoint → calls `task_runner.py`

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    UNIFIED TASK RUNNER                          │
│              .github/scripts/task_runner.py                      │
├─────────────────────────────────────────────────────────────────┤
│  • Reads task registry (tasks.yaml)                             │
│  • Checks schedule + last_run to determine due tasks            │
│  • Executes tasks via subprocess                                │
│  • Logs results to operations/runtime/logs/tasks.jsonl          │
│  • Raises reviews on failure                                    │
│  • Updates last_run timestamps                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         │                    │                    │
    ┌────▼────┐         ┌────▼────┐         ┌────▼────┐
    │ Launchd │         │Makefile │         │   CLI   │
    │ (3am)   │         │(manual) │         │(manual) │
    └─────────┘         └─────────┘         └─────────┘
         │                    │                    │
         └────────────────────┴────────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │   tasks.yaml      │
                    │   ────────────    │
                    │   scrape-comps:   │
                    │     schedule:     │
                    │       weekly      │
                    │     script: ...   │
                    └───────────────────┘
```

### Task Registry Schema

```yaml
# src/tasks/tasks.yaml
version: "1.0"
tasks:
  scrape-competitors:
    description: "Scrape GitHub stars and metrics for tracked competitors"
    script: plugins/dev/skills/advisor/scripts/analytics/scrape_competitors.py
    schedule: weekly        # daily | weekly | monthly | manual
    day_of_week: 0          # 0=Sunday (for weekly)
    enabled: true
    timeout_seconds: 300
    on_failure: review      # review | notify | silent
    last_run: null
    next_run: null

  nightly-maintenance:
    description: "Log rotation, analytics generation, backlog ingestion"
    script: .github/scripts/nightly_maintainer.py
    schedule: daily
    enabled: true
    timeout_seconds: 600
    on_failure: notify

  process-notifications:
    description: "Send due scheduled notifications"
    script: plugins/observability/skills/daemon/scripts/notification_service.py
    args: ["--process-due"]
    schedule: hourly
    enabled: true
    timeout_seconds: 60
```

### Entry Points

| Entry Point | Command | Use Case |
|-------------|---------|----------|
| **Launchd** | Runs at 3am daily | Automated nightly |
| **Makefile** | `make task TASK=scrape-competitors` | Manual developer trigger |
| **CLI** | `exo run-task scrape-competitors` | Manual user trigger |
| **Dashboard** | POST `/api/tasks/run` | UI-triggered execution |
| **All tasks** | `make tasks` or `exo run-tasks --all` | Run all due tasks now |

### Integration with Existing Systems

1. **Nightly Maintainer** - Becomes a task in the registry (not standalone)
2. **Launchd plist** - Updated to call `task_runner.py --scheduled` instead of `nightly_maintainer.py`
3. **GitHub Actions** - Remains separate (runs in CI, not local machine)
4. **Notification Service** - `process_due()` becomes a scheduled task

## Consequences

### Positive

- **Single source of truth** for all scheduled tasks
- **Discoverable** - `exo list-tasks` shows everything
- **Visible** - Dashboard shows task status, last run, next run
- **Debuggable** - Unified logging to `tasks.jsonl`
- **Flexible** - Multiple entry points, same execution
- **Failure handling** - Raises reviews on errors
- **Testable** - Can run any task manually via Makefile

### Negative

- **Migration effort** - Need to refactor existing nightly_maintainer.py
- **Complexity** - Another abstraction layer
- **macOS bias** - Launchd is macOS-specific (Windows uses Task Scheduler)

### Neutral

- GitHub Actions nightly remains separate (CI vs local execution)
- Existing plist file location unchanged

## Alternatives Considered

### Alternative 1: Keep Separate Mechanisms

Keep cron, makefile, and goodnight as separate systems.

**Rejected because**: Leads to fragmentation, no unified visibility, tasks get forgotten.

### Alternative 2: Use Only GitHub Actions

Move all scheduled tasks to GitHub Actions.

**Rejected because**: Requires internet, can't run on local machine, no offline support.

### Alternative 3: Use Only Launchd/Cron

Pure system scheduler without task registry.

**Rejected because**: No dashboard visibility, no unified logging, hard to discover tasks.

## Implementation Plan

1. [x] Create ADR (this document)
2. [ ] Create `src/tasks/tasks.yaml` with initial tasks
3. [ ] Create `.github/scripts/task_runner.py`
4. [ ] Update `com.augur.nightly.plist` to call task_runner
5. [ ] Add `make task` target to Makefile
6. [ ] Add dashboard API endpoint `/api/tasks`
7. [ ] Add dashboard UI for task visibility
8. [ ] Migrate nightly_maintainer.py to be a registered task

## References

- Existing nightly maintainer: `.github/scripts/nightly_maintainer.py`
- Existing launchd plist: `.github/scripts/com.augur.nightly.plist`
- GitHub Actions nightly: `.github/workflows/cron-nightly.yml`
- Competitor scraping trigger: `plugins/dev/skills/advisor/scripts/analytics/scrape_competitors.py`
- Review system: `src/reviews/registry.py`
