---
status: Implemented
date: '2026-02-17'
deciders:
- Project owner
related:
- ADR-062 (observability hub)
- ADR-076 (AI self-healing)
- ADR-059 (MCP context focus)
- ADR-005 (MCP as execution gateway)
- ADR-019 (agent tiering)
hub: null
tags:
- observability
- skill
- performance
- tracking
superseded_by: null
---

# ADR-113: Observability Skill Performance Tracking

## Context

### The Problem

The observe hub (ADR-062) monitors system health — daemon processes, MCP connections, self-heal events, memory stats. But it has no visibility into **how well individual skills perform when invoked**. We know *if* the daemon is running, but not:

- Does a skill trigger automatically on relevant queries, or does the user have to explicitly invoke it?
- How many tool calls does a skill need to complete a workflow vs. how many it *should* need?
- Are MCP API calls failing silently during skill execution?
- Do users need to redirect or correct Claude mid-workflow?
- Are results consistent across sessions for the same query?

The observe hub watches infrastructure. Nothing watches **skill effectiveness**.

### What We Have Today

| Component | What It Tracks | Gap |
|-----------|---------------|-----|
| `metrics_service.py` | Plugin health (test pass/fail per bundle) | Static — tests, not runtime behavior |
| `insight_scanner.py` | Page improvement suggestions via LLM | Usage-gated (needs 5 views/7d) — most pages never qualify |
| `usage_stats.yaml` | Page views (7d/30d) | Extremely sparse — only 1 entry (`/knowledge: 1 view`) |
| `self_heal_registry.json` | Error detection/fix events | Reactive — only fires on log errors, not on skill quality |
| `save-performance-metric` MCP tool | Page load/render times | UI performance only — not skill workflow performance |
| `chain_telemetry.jsonl` | Chain execution pass/fail | Chain-level, not skill-level |

No component answers: "Is the career skill working well? Does it trigger correctly? Does it complete workflows efficiently?"

### Success Criteria (From Acceptance Requirements)

The ADR must address these measurable targets:

**Quantitative**:
1. **Trigger rate**: Skill triggers on 90% of relevant queries — measured by running 10-20 test queries that should trigger the skill, tracking auto-load vs. explicit invocation
2. **Workflow efficiency**: Skill completes workflow in X tool calls — measured by comparing same task with/without skill, counting tool calls and tokens consumed
3. **API reliability**: 0 failed API calls per workflow — measured by monitoring MCP server logs during runs, tracking retry rates and error codes

**Qualitative**:
4. **User autonomy**: Users don't need to prompt Claude about next steps — assessed during testing by noting redirect/clarify frequency, plus beta user feedback
5. **Correction-free completion**: Workflows complete without user correction — assessed by running same request 3-5 times, comparing structural consistency and quality
6. **Cross-session consistency**: Consistent results across sessions — assessed by whether a new user can accomplish the task on first try with minimal guidance

### Why This Matters

Skills are Augur's product surface. A skill that triggers 40% of the time or needs 15 tool calls for a 5-call task is wasting tokens (cost) and user patience (UX). Without tracking, degradation is invisible until someone notices manually.

### Placement: Not a New Skill

This is **not a new skill or bundle**. All work enhances the two existing skills in the `observe` bundle (`plugins/observability/`):

| Component | Skill | Path | Rationale |
|-----------|-------|------|-----------|
| `skill_perf_collector.py` | **daemon** | `plugins/observability/skills/daemon/scripts/` | Daemon manages all background collection processes — collector is a daemon child process |
| `skill_perf_benchmark.py` | **daemon** | `plugins/observability/skills/daemon/scripts/` | Benchmark runner invoked by daemon (scheduled) or CLI (manual) |
| Collector config | **daemon** | `plugins/observability/skills/daemon/config/` | Follows daemon's existing config pattern (`self_heal.yaml`) |
| `PerformanceTab.tsx` | **observe** | `plugins/observability/skills/observe/augur/tabs/` | Observe skill owns the observability dashboard UI |
| `/api/observe/skill-perf/route.ts` | **observe** | `plugins/observability/skills/observe/augur/api/observe/skill-perf/` | API route serves the Performance tab |
| MCP tools (`get-skill-performance`, etc.) | **observe** | `plugins/observability/skills/observe/mcp/` | Observe skill's MCP surface for external access |
| Runtime telemetry data | — | `runtime/skill_perf/` | Ephemeral data, gitignored, not part of any skill |

The split follows the existing observe hub architecture: **daemon** handles backend processes and data collection, **observe** handles the dashboard and MCP interface.

## Decision

### 1. Skill Performance Telemetry Collector

Add a new script `skill_perf_collector.py` to `plugins/observability/skills/daemon/scripts/` that captures per-skill performance data from existing sources.

**Data sources** (no new instrumentation — reads existing logs/files):

| Source | Extracts |
|--------|----------|
| `runtime/logs/mcp-updates.log` | Tool call counts per skill invocation, error codes, retry events |
| `runtime/chain_telemetry.jsonl` | Chain execution times, step counts, failure points |
| `runtime/offload-log.jsonl` | Offload acceptance rates per skill tier |
| `runtime/daemon/usage_stats.yaml` | Page view frequency (proxy for skill engagement) |
| `runtime/self_heal_registry.json` | Fix success rate for skill-related errors |
| MCP `get-performance-metrics` | Page load/render times per skill route |

**Output**: Writes to `runtime/skill_perf/` as YAML files per skill (e.g., `runtime/skill_perf/career.yaml`):

```yaml
skill: career
last_updated: "2026-02-17T14:30:00Z"
period: 7d

trigger:
  total_relevant_queries: 0       # Populated by benchmark runs
  auto_triggered: 0               # Populated by benchmark runs
  explicit_invoked: 0             # Populated by benchmark runs
  trigger_rate: null              # Calculated after benchmark

workflow:
  avg_tool_calls: null            # Populated after telemetry collection
  target_tool_calls: null         # Set by skill author in SKILL.md
  efficiency_ratio: null          # avg / target
  total_invocations: 0

api:
  total_calls: 0
  failed_calls: 0
  retry_count: 0
  error_codes: {}                 # { "500": 2, "timeout": 1 }
  reliability: null               # (total - failed) / total

quality:
  user_corrections: null          # Manual assessment
  consistency_score: null         # Manual assessment (1-5)
  first_try_success: null         # Manual assessment (boolean)
```

**Collection schedule**: Runs as a daemon child process every 30 minutes (appended to `unified_daemon.py` service list).

### 2. Skill Performance Benchmark Runner

Add `skill_perf_benchmark.py` to `plugins/observability/skills/daemon/scripts/` — a test harness that measures the quantitative success criteria.

**What it does**:

1. **Trigger rate test**: For each skill that declares `benchmark_queries` in its `SKILL.md`, sends 10-20 test queries to the MCP context system (`focus-context` tool) and checks if the skill's tools are activated. Records auto-trigger vs. explicit invocation count.

2. **Workflow efficiency test**: For each skill that declares `benchmark_workflows` in its `SKILL.md`, replays a recorded workflow and counts tool calls. Compares against the skill's declared `target_tool_calls`.

3. **API reliability test**: During benchmark execution, intercepts MCP tool calls via the daemon's log monitor and records success/failure/retry per call.

**SKILL.md extension** — skills opt into benchmarking by adding a `## Performance` section:

```markdown
## Performance

benchmark_queries:
  - "show me my job applications"
  - "what's my career status"
  - "add a new job application for Google"

target_tool_calls: 5
benchmark_workflows:
  - name: "view applications"
    expected_steps: 3
  - name: "add application"
    expected_steps: 5
```

Skills without this section are tracked passively (API reliability from logs) but not actively benchmarked.

**Execution**: Manual via `/ops-perf` slash command or scheduled weekly via nightly maintainer.

### 3. Performance Dashboard Tab

Add a `PerformanceTab` to the observe hub (`plugins/observability/skills/observe/augur/tabs/PerformanceTab.tsx`).

**Tab content**:

| Section | Shows |
|---------|-------|
| Skill Scorecard | Table of all skills with trigger rate, avg tool calls, API reliability, overall health grade (A-F) |
| Trend Charts | 7d/30d trend lines for trigger rate and API reliability per skill |
| Efficiency Matrix | Scatter plot: actual tool calls vs. target tool calls per skill — skills above the diagonal are inefficient |
| Failure Log | Recent API failures grouped by skill, with error codes and timestamps |
| Benchmark Results | Latest benchmark run results with pass/fail per skill per metric |

**Health grade calculation**:

| Grade | Criteria |
|-------|----------|
| A | Trigger >= 90%, efficiency ratio <= 1.2, API reliability >= 99% |
| B | Trigger >= 75%, efficiency ratio <= 1.5, API reliability >= 95% |
| C | Trigger >= 60%, efficiency ratio <= 2.0, API reliability >= 90% |
| D | Trigger >= 40%, efficiency ratio <= 3.0, API reliability >= 80% |
| F | Below D thresholds |

Grades are aspirational targets — rough benchmarks, not hard SLAs. The value is in surfacing trends, not enforcing thresholds.

### 4. MCP Tools for Skill Performance

Register three MCP tools in the observe skill:

| Tool | Purpose |
|------|---------|
| `get-skill-performance` | Returns performance data for a specific skill or all skills. Parameters: `skill_name` (optional), `period` (7d/30d) |
| `run-skill-benchmark` | Triggers benchmark run for a specific skill or all. Parameters: `skill_name` (optional), `dry_run` (boolean) |
| `get-performance-summary` | Returns aggregate health grades and top issues across all skills |

These enable:
- `/inspect performance` to show skill health via CLI
- AI analysis of skill performance ("which skills are degrading?")
- Automated nightly quality reports

### 5. Qualitative Assessment Framework

For the three qualitative metrics (user autonomy, correction-free completion, cross-session consistency), provide a structured manual assessment workflow:

**`/ops-perf assess`** slash command extension:

1. Presents a checklist per skill:
   - "Did the user need to redirect Claude?" (yes/no + count)
   - "Did the workflow complete without correction?" (yes/no)
   - "Would a new user succeed on first try?" (yes/no/maybe)
2. Records responses to `runtime/skill_perf/{skill}_qualitative.yaml`
3. Aggregates into the Performance tab as a "User Experience" column

This accepts that qualitative metrics have "an element of vibes-based assessment" — the framework structures the vibes without pretending they're precise measurements.

## Consequences

### Positive

- **Visibility into skill quality** — First time we can answer "is this skill working well?" with data, not guesswork
- **Degradation detection** — Trend lines surface regressions before users notice (e.g., trigger rate dropping from 90% to 60% after a refactor)
- **Cost optimization** — Efficiency ratios identify skills burning excessive tokens. A skill using 15 tool calls for a 5-call task costs 3x more than necessary
- **Benchmarkable** — Skills with `## Performance` sections become testable artifacts. CI can flag regressions
- **No new instrumentation overhead** — Reads existing logs/telemetry. Collection runs every 30 min as a daemon child process

### Negative

- **Benchmark queries require skill author effort** — Each skill needs to define test queries in SKILL.md. Without them, only passive API tracking works
- **Qualitative assessment is manual** — User autonomy and consistency can't be fully automated. The `/ops-perf assess` workflow structures it but still needs human input
- **Trigger rate measurement is indirect** — We measure whether `focus-context` activates the skill's tools, not whether Claude actually *uses* them. A skill can be activated but ignored

### Neutral

- Observe hub gains a 10th tab (Performance) — consistent with the hub's role as the observability center
- Existing `save-performance-metric` / `get-performance-metrics` MCP tools remain for UI performance. New tools are for skill workflow performance — different concerns
- SKILL.md format extended with optional `## Performance` section — no breaking changes to existing skills
- Grades are informational, not enforcement. No skill is blocked from running based on its grade

## Implementation Order

```
Phase 1: Data Collection (PARALLEL)
├── Step 1: Create skill_perf_collector.py — reads existing logs, writes per-skill YAML to runtime/skill_perf/
├── Step 2: Register collector as daemon child process in unified_daemon.py (30-min interval)
└── Step 3: Create runtime/skill_perf/ directory structure with README

Phase 2: Benchmarking (depends on Phase 1)
├── Step 4: Create skill_perf_benchmark.py — trigger rate test, workflow efficiency test, API reliability test
├── Step 5: Add ## Performance sections to 5 pilot skills (career, knowledge, health, finance, organizer)
└── Step 6: Wire benchmark runner into /ops-perf slash command

Phase 3: Dashboard (PARALLEL with Phase 2)
├── Step 7: Create PerformanceTab.tsx in observe dashboard — scorecard, trends, efficiency matrix, failures
├── Step 8: Create /api/observe/skill-perf API route — serves runtime/skill_perf/ data
└── Step 9: Add performance tab to observe dashboard.yaml

Phase 4: MCP Tools (depends on Phase 1)
├── Step 10: Register get-skill-performance MCP tool
├── Step 11: Register run-skill-benchmark MCP tool
└── Step 12: Register get-performance-summary MCP tool

Phase 5: Qualitative Framework (PARALLEL)
├── Step 13: Extend /ops-perf with assess subcommand — structured checklist per skill
└── Step 14: Create qualitative assessment YAML schema and storage

Phase 6: Verification (depends on all)
├── Step 15: Run benchmark on 5 pilot skills — verify data collection works
├── Step 16: Verify Performance tab renders with real data
├── Step 17: Verify MCP tools return correct data
└── Step 18: Run /ops-perf assess on 3 skills — verify qualitative flow
```

## Completion Criteria

- [ ] `skill_perf_collector.py` runs as daemon child process, writes per-skill YAML every 30 min
- [ ] `skill_perf_benchmark.py` measures trigger rate, workflow efficiency, and API reliability
- [ ] 5 pilot skills have `## Performance` sections in SKILL.md with benchmark queries
- [ ] Performance tab renders in observe hub with scorecard, trends, and efficiency matrix
- [ ] `/api/observe/skill-perf` API route serves collected data
- [ ] 3 MCP tools registered: `get-skill-performance`, `run-skill-benchmark`, `get-performance-summary`
- [ ] `/ops-perf assess` workflow captures qualitative assessment per skill
- [ ] At least one skill shows health grade A or B after initial benchmark run
- [ ] Trigger rate measurement works: benchmark sends test queries, records auto-trigger count
- [ ] API reliability tracking captures failures from MCP logs with error codes

### Success Metrics (Aspirational Targets)

These are rough benchmarks, not precise thresholds. Aim for rigor but accept vibes-based assessment where automation falls short.

| Metric | Target | Measurement Method |
|--------|--------|--------------------|
| Trigger rate | 90% of relevant queries | Run 10-20 test queries per skill, track auto-load vs. explicit |
| Workflow efficiency | Completes in target tool calls (per-skill) | Compare with/without skill, count tool calls and tokens |
| API reliability | 0 failed calls per workflow | Monitor MCP server logs, track retry rates and error codes |
| User autonomy | No next-step prompting needed | Note redirect/clarify frequency during testing, beta feedback |
| Correction-free completion | Workflows complete without user correction | Run same request 3-5 times, compare structural consistency |
| Cross-session consistency | New user succeeds on first try | Qualitative assessment via `/ops-perf assess` |

## Alternatives Considered

### Alternative 1: Instrument Every Tool Call With Inline Telemetry

Add timing/success tracking directly inside each MCP tool function — wrap every tool with a decorator that logs call duration, success/failure, and parameters.

**Rejected because**: Invasive — requires modifying every tool across 40+ plugins. Increases coupling between observe and all other skills. The passive log-reading approach achieves 80% of the signal with 0% of the instrumentation overhead.

### Alternative 2: Use External APM (DataDog, Sentry, etc.)

Send telemetry to a cloud observability platform for dashboarding and alerting.

**Rejected because**: Violates ADR-006 (local-first architecture). No external API dependencies for core features. All performance data stays on disk in `runtime/skill_perf/`.

### Alternative 3: Only Track API Reliability, Skip Trigger Rate and Efficiency

Simplify to just monitoring MCP call success/failure — the easiest metric to automate.

**Rejected because**: API reliability alone misses the most impactful quality signals. A skill can have 100% API reliability but only trigger 30% of the time or use 3x the necessary tool calls. Trigger rate and efficiency are where the real optimization opportunities lie.

### Alternative 4: Full Automated Qualitative Testing With LLM Judges

Use an LLM to evaluate whether workflows needed user correction by analyzing conversation transcripts.

**Rejected because**: Over-engineering for current scale. LLM judges add cost, latency, and their own accuracy concerns. The structured manual checklist via `/ops-perf assess` is honest about the vibes-based nature of qualitative assessment while still producing trackable data.

## References

- ADR-062: Observability hub — established the observe hub and `/inspect` command
- ADR-076: AI self-healing — daemon's error detection and auto-fix pipeline
- ADR-059: MCP context focus — skill-aware tool scoping (relevant for trigger rate measurement)
- ADR-005: MCP as execution gateway — all tool interactions go through MCP
- ADR-006: Local-first architecture — no external telemetry services
- ADR-019: Agent tiering — cost control via model selection (efficiency tracking helps optimize tier usage)
- `plugins/observability/skills/daemon/scripts/unified_daemon.py` — daemon process manager (new collector registered here)
- `plugins/observability/skills/observe/augur.yaml` — observe hub tabs (new Performance tab added here)
- `plugins/observability/skills/daemon/config/self_heal.yaml` — self-heal configuration (pattern for collector config)

## Implementation Prompt

> Paste this into Claude Code to execute this ADR.

You are implementing **ADR-113: Observability Skill Performance Tracking**.

Read the full ADR: `docs/decisions/ADR-113-observability-skill-performance-tracking.md`

### Offload Protocol (ADR-054)

Before dispatching each step, check if it can be offloaded to a cheap CLI:

1. Read offload config: `cat config/system/llm.yaml` → look for `offload:` section
2. If `offload.enabled: true` AND the step's tier is `low`:
   ```bash
   python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py \
     --task "STEP DESCRIPTION" \
     --files "TARGET_FILE_1,TARGET_FILE_2" \
     --context-files "REFERENCE_FILE_FOR_PATTERNS" \
     --work-dir $(pwd)
   ```
3. Review the JSON output — check `success`, `files_changed`, and `diff` fields
4. Record the verdict
5. If `offload.enabled: false` OR tier is `medium`/`high` → do the step yourself

### Team Orchestration

Create a team and spawn teammates:

1. **Create team**: `TeamCreate(team_name="adr-113-skill-perf-tracking", description="Implementing ADR-113: Observability Skill Performance Tracking")`
2. **Create tasks** from the Implementation Order phases
3. **Spawn teammates**:
   - `developer` (sonnet) — collector script, benchmark runner, daemon integration
   - `frontend` (sonnet) — Performance tab, API route, dashboard.yaml update
   - `validator` (haiku) — verification phase

**Model mapping**: `low` → haiku, `medium` → sonnet, `high` → opus

### Execution Plan

**Team name**: `adr-113-skill-perf-tracking`

#### Phase 1: Data Collection
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | Create `skill_perf_collector.py` that reads existing log sources (mcp-updates.log, chain_telemetry.jsonl, offload-log.jsonl, usage_stats.yaml, self_heal_registry.json) and writes per-skill performance YAML to `runtime/skill_perf/{skill}.yaml`. Use the schema from Decision 1. Reference `insight_scanner.py` for daemon child process patterns. | `plugins/observability/skills/daemon/scripts/skill_perf_collector.py` |
| 1.2 | developer | low | Register `skill_perf_collector.py` as a daemon child process in `unified_daemon.py` with 30-minute interval. Follow existing child process registration pattern. | `plugins/observability/skills/daemon/scripts/unified_daemon.py` |
| 1.3 | developer | low | Create `runtime/skill_perf/README.md` explaining the directory structure and YAML schema. | `runtime/skill_perf/README.md` |

#### Phase 2: Benchmarking
**Strategy**: PIPELINE (depends on Phase 1)

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Create `skill_perf_benchmark.py` with three test types: (1) trigger rate — sends benchmark queries to `focus-context` MCP tool, checks if skill tools are activated; (2) workflow efficiency — counts tool calls for recorded workflows against target; (3) API reliability — reads recent MCP logs for error/retry events. Output updates `runtime/skill_perf/{skill}.yaml`. | `plugins/observability/skills/daemon/scripts/skill_perf_benchmark.py` |
| 2.2 | developer | low | Add `## Performance` sections to 5 pilot skill SKILL.md files: career, knowledge, health, finance, organizer. Include 3-5 benchmark_queries and target_tool_calls per skill. Read each SKILL.md first to understand the skill's capabilities. | 5 SKILL.md files |
| 2.3 | developer | low | Wire benchmark runner into `/ops-perf` slash command. Read the existing ops-perf command definition and add a `benchmark` subcommand that invokes `skill_perf_benchmark.py`. | Slash command config |

#### Phase 3: Dashboard
**Strategy**: PARALLEL with Phase 2

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | frontend | medium | Create `PerformanceTab.tsx` in observe dashboard with: (1) Skill Scorecard table — all skills with trigger rate, avg tool calls, API reliability, health grade; (2) Trend section placeholder (7d/30d); (3) Efficiency matrix — actual vs target tool calls; (4) Failure log — recent API failures by skill; (5) Benchmark results. Fetch data from `/api/observe/skill-perf`. Use existing observe tab patterns (reference `HealthTab.tsx` for layout). | `plugins/observability/skills/observe/augur/tabs/PerformanceTab.tsx` |
| 3.2 | frontend | medium | Create `/api/observe/skill-perf/route.ts` API route that reads `runtime/skill_perf/*.yaml` files and returns aggregated JSON. Support query params: `?skill=career` for single skill, `?period=7d` for time filter, `?summary=true` for grades only. | `plugins/observability/skills/observe/augur/api/observe/skill-perf/route.ts` |
| 3.3 | frontend | low | Add `performance` tab to `plugins/observability/skills/observe/augur.yaml` — id: performance, label: Performance, icon: Gauge, href: /observe?tab=performance. | `plugins/observability/skills/observe/augur.yaml` |

#### Phase 4: MCP Tools
**Strategy**: PARALLEL (depends on Phase 1)

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | developer | medium | Register 3 MCP tools in observe skill's MCP module: `get-skill-performance` (reads runtime/skill_perf/ YAML), `run-skill-benchmark` (invokes skill_perf_benchmark.py), `get-performance-summary` (aggregates health grades). Reference existing MCP tool patterns in the observe skill. | `plugins/observability/skills/observe/mcp/` |
| 4.2 | developer | low | Add the 3 new tools to observe `dashboard.yaml` mcp.tools list. | `plugins/observability/skills/observe/augur.yaml` |

#### Phase 5: Qualitative Framework
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 5.1 | developer | low | Extend `/ops-perf` slash command with `assess` subcommand. The command presents a structured checklist per skill (3 yes/no questions from Decision 5) and writes responses to `runtime/skill_perf/{skill}_qualitative.yaml`. | Slash command script + YAML schema |

#### Phase 6: Verification
**Strategy**: PIPELINE (depends on all)

| Step | Agent | Tier | Task |
|------|-------|------|------|
| 6.1 | validator | low | Run skill_perf_collector.py manually. Verify it creates YAML files in runtime/skill_perf/ with correct schema. |
| 6.2 | validator | low | Run skill_perf_benchmark.py on 1 pilot skill (career). Verify trigger rate and API reliability data are recorded. |
| 6.3 | validator | low | Verify Performance tab is listed in dashboard.yaml and API route returns valid JSON. |
| 6.4 | validator | low | Verify 3 MCP tools are registered and return data (use get-skill-performance and get-performance-summary). |
| 6.5 | validator | low | Run /ops-perf assess on 1 skill. Verify qualitative YAML is written correctly. |

### Completion Criteria

- [ ] `skill_perf_collector.py` creates per-skill YAML in `runtime/skill_perf/`
- [ ] Collector registered as daemon child process (30-min interval)
- [ ] `skill_perf_benchmark.py` measures trigger rate, efficiency, and API reliability
- [ ] 5 pilot skills have `## Performance` sections in SKILL.md
- [ ] Performance tab renders in observe hub
- [ ] `/api/observe/skill-perf` returns aggregated skill performance data
- [ ] 3 MCP tools registered and functional
- [ ] `/ops-perf assess` captures qualitative assessment
- [ ] At least 1 skill shows grade A or B after benchmark
- [ ] Trigger rate measurement sends test queries and records results

### How to Run
```
# Option 1: Use /implement-adr
/implement-adr docs/decisions/ADR-113-observability-skill-performance-tracking.md

# Option 2: Paste the Implementation Prompt into Claude Code
```
