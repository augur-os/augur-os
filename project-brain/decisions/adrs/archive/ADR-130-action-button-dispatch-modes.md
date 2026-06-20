---
status: Implemented
date: '2026-02-20'
deciders:
- Augur Team
related:
- ADR-035 (CLI Chat Enhancements)
- ADR-036 (Chat Window vs Action Bar Partition)
- ADR-077 (Service Gating)
- ADR-124 (Focus Button)
- ADR-230 (Per-Skill Config Files)
- ADR-122 (Filesystem-Driven Plugin Lifecycle)
hub: null
tags:
- action
- button
- dispatch
- modes
superseded_by: null
---

# ADR-130: Action Button Dispatch Modes

## Context

Augur's dashboard has ~50 action buttons across 17 hubs. Today, every non-fast action follows the same path:

1. User clicks action button
2. `useActionRunner` resolves flow → `fast` or `llm`
3. **Fast**: POST `/api/actions/run`, show toast result
4. **LLM**: Open `ActionDialogView` → user adds remarks → sends to active CLI via stdin

This one-size-fits-all dispatch has four problems:

### Problem 1: All LLM actions go to the same dialog

A "Fix Bug" action (needs Cursor open, multi-file edits, interactive debugging) and an "AI Recipe Ideas" action (needs a text response, no file edits) both route through `ActionDialogView` → CLI paste. The recipe action doesn't need an IDE session — it just needs a one-shot call that returns text.

### Problem 2: No direct IDE dispatch

The `mode: 'ide'` field on `ActionDef` exists but is unused. Every LLM action opens ActionDialogView regardless. The IDE bridge infrastructure (`send-ide-prompt` MCP tool, `useIdeBridge` hook, `/api/ide/prompt` route) is fully built but not wired into ActionDialogView. Users who always use Cursor must click through the dialog every time.

### Problem 3: Results always go to the terminal

One-shot content generation (analyze a job posting, recommend recipes, prepare interview materials) produces text that belongs on the page, not buried in a CLI terminal session. Users lose context switching between the dashboard page and the terminal.

### Problem 4: No recurring execution

Many fire-and-forget and oneshot actions are useful on a schedule (sync jobs every Monday, refresh telemetry daily, reindex weekly). Today there's no way to schedule actions from the dashboard — users must manually set up cron jobs or rely on the nightly daemon.

## Decision

**Clean break**: Remove the legacy `flow` / `mode` fields entirely. Replace with a single `dispatch` field on all action definitions. All ~50 actions are migrated — no fallback resolution, no dual support.

**Distributed architecture**: Each action button config lives in the plugin that owns it. The central `config/dashboard/action_buttons.yaml` is eliminated. The action schema template is centralized in the ai_bridge plugin.

### Distributed Ownership Model

#### Principle: config lives where the code lives

Today `config/dashboard/action_buttons.yaml` defines ~25 actions that belong to 8 different plugins. This violates Augur's distributed architecture — a career action shouldn't be configured in a central dashboard file. Each plugin should be self-contained: clone the plugin, get its actions.

#### File layout

```
plugins/ai/skills/ai_bridge/augur/data/
  action-schema.yaml              ← TEMPLATE: defines allowed fields, dispatch modes, validation rules

plugins/{bundle}/skills/{skill}/augur/data/
  actions/                        ← Per-plugin action configs
    {action-id}.yaml
  schedules/                      ← Per-plugin schedule configs (created by user via clock icon)
    {action-id}-{frequency}.yaml
```

**Examples after migration**:

```
plugins/career/skills/career/augur/data/actions/
  sync-jobs.yaml                  ← was in config/dashboard/action_buttons.yaml
  calculate-match-scores.yaml     ← was in config/dashboard/action_buttons.yaml
  analyze-job.yaml                ← was in config/dashboard/action_buttons.yaml
  prepare-interview.yaml          ← was in config/dashboard/action_buttons.yaml
  manage-career-pipeline.yaml     ← already here
  research-company.yaml           ← already here
  refresh-companies-data.yaml     ← already here
  update-company-profiles.yaml    ← already here

plugins/dev/skills/developer/augur/data/actions/
  code-review.yaml                ← was in config/dashboard/action_buttons.yaml
  fix-bug.yaml                    ← was in config/dashboard/action_buttons.yaml
  refactor-component.yaml         ← was in config/dashboard/action_buttons.yaml
  execute-task.yaml               ← was in config/dashboard/action_buttons.yaml
  refactor-code.yaml              ← already here
  verify-test.yaml                ← already here
  write-tests.yaml                ← already here

plugins/dev/skills/advisor/augur/data/actions/
  refresh-bugs.yaml               ← was in config/dashboard/action_buttons.yaml
  sync-bugs-gh.yaml               ← was in config/dashboard/action_buttons.yaml
  refresh-telemetry.yaml          ← was in config/dashboard/action_buttons.yaml
  analyze-usage-patterns.yaml     ← was in config/dashboard/action_buttons.yaml
  triage-backlog.yaml             ← was in config/dashboard/action_buttons.yaml

plugins/ai/skills/knowledge/augur/data/actions/
  reindex-all.yaml                ← was in config/dashboard/action_buttons.yaml
  refresh-graph.yaml              ← was in config/dashboard/action_buttons.yaml
  smart-search.yaml               ← was in config/dashboard/action_buttons.yaml
  analyze-knowledge-gaps.yaml     ← was in config/dashboard/action_buttons.yaml

plugins/professional/skills/venture/augur/data/actions/
  generate-campaign.yaml          ← was in config/dashboard/action_buttons.yaml
  analyze-metrics.yaml            ← was in config/dashboard/action_buttons.yaml

plugins/dev/skills/frontend/augur/data/actions/
  enhance-dashboard.yaml          ← was in config/dashboard/action_buttons.yaml

plugins/observability/skills/daemon/augur/data/actions/
  run-nightly.yaml                ← was in config/dashboard/action_buttons.yaml

plugins/admin/skills/admin/augur/data/actions/
  system-review.yaml              ← was in config/dashboard/action_buttons.yaml
  system-review-batch.yaml        ← was in config/dashboard/action_buttons.yaml
  open-data-folder.yaml           ← was in config/dashboard/action_buttons.yaml
```

#### Central schema template

The ai_bridge plugin owns the **schema definition** — what fields are valid, what dispatch modes exist, validation rules. Stored at:

```
plugins/ai/skills/ai_bridge/augur/data/action-schema.yaml
```

```yaml
# Action Button Schema v2 — ADR-130
# Defines valid fields and dispatch modes for all action YAML files.
# Individual action configs live in plugins/{bundle}/skills/{skill}/augur/data/actions/
schema_version: 2

dispatch_modes:
  fire:
    description: "Headless script execution, result as toast"
    requires_prompt: false
    schedulable_default: true
  oneshot:
    description: "Headless AI call, result inline or in chat"
    requires_prompt: true
    schedulable_default: true
  ide:
    description: "Send prompt to IDE for interactive work"
    requires_prompt: true
    schedulable_default: false
  modal:
    description: "Open local UI form/modal"
    requires_prompt: false
    schedulable_default: false

required_fields: [id, label, description, dispatch, page]
optional_fields: [agents, args, confirmation, recommended_agent, prompt, prompt_file, requires_service, unavailable_label, schedulable, icon, script, script_path]

validation:
  id: "^[a-z0-9][a-z0-9-]*$"       # kebab-case
  dispatch: ["fire", "oneshot", "ide", "modal"]
  page: "^/.*"                       # must start with /
```

#### Action discovery

The `/api/actions` route discovers actions by walking the plugin tree:

```
plugins/*/skills/*/augur/data/actions/*.yaml
```

No central registry file. Actions are discovered at startup with a 30-second cache. Each YAML file is validated against the schema. Files with legacy `flow`/`mode` fields are rejected with a warning log.

#### Schedule storage (per-plugin)

When a user schedules an action, the schedule config is stored alongside the action in the owning plugin:

```
plugins/career/skills/career/augur/data/schedules/
  sync-jobs-weekly.yaml
  analyze-job-daily.yaml
```

The daemon discovers schedules the same way — walk `plugins/*/skills/*/augur/data/schedules/*.yaml`. This means:
- Cloning a plugin brings its schedules
- Disabling a plugin automatically disables its schedules (no orphan cleanup needed)
- Each plugin is fully self-contained

#### Elimination of central file

`config/dashboard/action_buttons.yaml` is **deleted**. All 25 actions are distributed to their owning plugins. The `_meta` and `schema_version` fields move to the central schema template.

### New ActionDef Interface

```typescript
interface ActionDef {
  id: string;                         // kebab-case unique identifier
  label: string;
  description: string;
  dispatch: 'fire' | 'oneshot' | 'ide' | 'modal';
  page: string;                       // dashboard page path (required)
  agents?: string[];
  args?: Record<string, any>;
  confirmation?: string;
  recommended_agent?: string;
  prompt?: string;                    // Inline prompt text
  prompt_file?: string;              // Path to .md file relative to plugin (loaded at discovery)
  icon?: string;                     // Lucide icon name
  script?: string;                   // For fire dispatch: command to run
  script_path?: string;              // For fire dispatch: Python script path
  requires_service?: string | string[];
  unavailable_label?: string;
  schedulable?: boolean;              // Overrides dispatch_mode default
  // Populated at runtime by discovery:
  _plugin?: string;                  // e.g., "career/career" — set by discovery, not in YAML
}
```

**Removed fields**: `flow`, `mode`, `name` (use `id`), `category` (inferred from plugin), `promptOverride`, `prompt_template`, `instruction_script`, `json_output`, `ide_type`, `tab`

The `prompt_file` field points to a markdown file relative to the plugin root. At discovery time, the file is read and its contents populate the `prompt` field. This keeps large prompts (like the 50-line code review template) out of the YAML and in version-controlled .md files.

### YAML Schema (v2) — Examples

```yaml
# plugins/career/skills/career/augur/data/actions/analyze-job.yaml
id: analyze-job
label: Analyze Job
description: Deep analysis of job posting with match scoring
dispatch: oneshot
page: /career/pipeline
agents: [careers, data-scientist]
prompt_file: prompts/analyze-job.md
schedulable: true
icon: FileSearch

# plugins/dev/skills/developer/augur/data/actions/fix-bug.yaml
id: fix-bug
label: Fix Bug
description: Investigate and fix a specific bug
dispatch: ide
page: /workshop
agents: [developer, devops]
prompt_file: prompts/fix-bug.md
icon: Bug

# plugins/career/skills/career/augur/data/actions/sync-jobs.yaml
id: sync-jobs
label: Sync Jobs
description: Update job listings from all tracked sources
dispatch: fire
page: /career/pipeline
script_path: actions/sync_jobs.py
schedulable: true
icon: RefreshCw
```

Action discovery walks all plugins, validates against the central schema, and rejects files with legacy fields.

### Skills and Chains Are Just Actions

There is no separate "chain" concept in the action system. A chain is a **skill** — its orchestration logic lives in its `SKILL.md`, its MCP tools, and its scripts. The action button is just the trigger config.

A skill that orchestrates multiple agents (e.g., redesign-page with architect → developer → validator steps) is triggered exactly the same way as a single-agent skill. The `dispatch` field determines **how** the user triggers it:

| Skill type | dispatch | Why |
|---|---|---|
| Multi-step coding workflow (redesign-page, build-feature) | `ide` | Needs IDE for code changes, multi-file edits |
| Multi-step analysis (content-pipeline, auto-fix-markers) | `oneshot` | Returns analysis results, no IDE needed |
| Data refresh pipeline (refresh-all-data) | `fire` | Script execution, no AI reasoning |

The action YAML for a skill-backed action is identical to any other action:

```yaml
# plugins/dev/skills/frontend/augur/data/actions/redesign-page.yaml
id: redesign-page
label: Redesign Page
description: Redesign a UI page with capture, analysis, and implementation
dispatch: ide
page: /workshop
agents: [architect, developer, validator]
prompt_file: prompts/redesign-page.md
icon: Layout
```

The `prompt_file` references the skill's instructions. The skill's `SKILL.md` defines the multi-step workflow. The action system doesn't know or care about steps — it just dispatches.

**Eliminated**: `ChainsMenu`, `ChainTriggerModal`, `ChainCard`, `ChainsSection`, `/api/agents/chains` route. All replaced by the unified action system. Skills that were previously only accessible as "chains" now appear as regular action buttons on their relevant pages.

**Legacy chain YAML files** (`plugins/*/skills/*/chains/*.yaml`) are migrated: their metadata (description, agents, triggers, success_criteria) is absorbed into the skill's `SKILL.md`, and a corresponding action YAML is created in `augur/data/actions/`.

### Dispatch Mode 1: `fire` — Headless script, toast result

- Runs a backend script via `/api/actions/run`
- Shows result as toast notification
- No terminal, no dialog, no IDE

**Actions** (~13):

| Action | Page |
|--------|------|
| refresh-companies-data | /career/companies |
| sync-jobs | /career/pipeline |
| calculate-match-scores | /career/pipeline |
| refresh-bugs | /workshop |
| sync-bugs-gh | /workshop |
| run-nightly | /workshop |
| refresh-telemetry | /brain |
| reindex-all | /brain/memory |
| refresh-graph | /brain/memory |
| refresh-inbox | /inbox |
| route-all-auto | /inbox |
| open-data-folder | / |
| Install actions (4) | /install |

### Dispatch Mode 2: `oneshot` — Headless AI call, inline results

Runs a one-shot CLI/MCP call, captures output, displays results on the page. No ActionDialogView. No interactive CLI session.

**Dispatch flow**:
1. User clicks button → loading spinner replaces button icon
2. POST `/api/actions/oneshot` with prompt + page context
3. Backend runs headless AI call (MCP tool or `claude --print`)
4. Response returned as structured text
5. **Short results** (< 500 chars): expandable toast/card on the page
6. **Long results** (>= 500 chars): FloatingChat opens, result rendered as chat message
7. Button returns to idle state

If user wants to follow up on a long result in FloatingChat, they type in the chat input — the CLI starts on demand with the original result as context.

**Shift+Click override**: Opens ActionDialogView so user can add remarks before the oneshot runs.

**Actions** (~21):

| Action | Page |
|--------|------|
| analyze-job | /career/pipeline |
| prepare-interview | /career/pipeline |
| ai-tailor-resume | /career/resume |
| ats-review | /career/resume |
| improve-writing | /career/resume |
| generate-campaign | /venture/gtm/marketing |
| analyze-metrics | /venture/metrics |
| triage-backlog | /workshop |
| analyze-usage-patterns | /brain |
| smart-search | /brain/memory |
| analyze-knowledge-gaps | /brain/memory |
| ai-recipe-ideas | /lifestyle/recipes |
| ai-meal-plan | /lifestyle/recipes |
| ai-find-similar | /lifestyle/recipes |
| ai-recommend-movies | /lifestyle/movies |
| suggest-courses | /growth/learning |
| learning-roadmap | /growth/learning |
| summarize-inbox | /inbox |
| virtual-doctor-chat | /health |
| extract-career-emails | /google-workspace |
| prioritize | /eisenhower/inbox |

### Dispatch Mode 3: `ide` — Direct IDE dispatch

Sends the prompt to the user's IDE for interactive coding work.

**Dispatch flow**:
1. User clicks button
2. System calls `get-ide-status` to detect running IDEs
3. **One IDE detected**: Send prompt directly via `send-ide-prompt`. Toast: "Sent to Cursor ✓"
4. **Multiple IDEs detected**: Open ActionDialogView with one button per IDE ("Send to Cursor", "Send to VS Code"), plus "Copy" fallback
5. **No IDE detected**: Open ActionDialogView with "Start CLI & Send" as primary, plus "Copy" fallback
6. User remarks textarea available when dialog is shown

**Shift+Click override**: Always opens the full dialog regardless of IDE count.

**Actions** (~17):

| Action | Page |
|--------|------|
| code-review | /workshop |
| fix-bug | /workshop |
| refactor-component | /workshop |
| execute-task | /workshop |
| enhance-dashboard | * (all pages) |
| system-review | /workshop |
| refactor-code | /hands |
| verify-test | /hands |
| write-tests | /hands |
| manage-career-pipeline | /career/pipeline |
| research-company | /career/companies/[slug] |
| update-company-profiles | /career/companies |
| add-prompt-helper | /cortex |
| improve-prompt | /cortex |
| draft-reply | /google-workspace/gmail |
| post-lifecycle-assistant | /content-pipeline |
| linkedin-post-generator | /venture/gtm/social |

### Dispatch Mode 4: `modal` — Local UI form

Opens a frontend modal/form. No AI, no CLI, no backend call.

**Actions** (~8):

| Action | Page |
|--------|------|
| create-note | /apple |
| create-reminder | /apple |
| add-course | /growth/learning |
| add-star | /career/star |
| add-detailed-recipe | /lifestyle/recipes |
| import-recipe-url | /lifestyle/recipes |
| rate-movie | /lifestyle/movies |
| import-from-imdb | /lifestyle/movies |

### Cron Scheduling (clock icon)

Actions with `schedulable: true` display a small clock icon (⏱) next to the action button. Clicking the clock opens a **schedule popover**:

#### Schedule Popover UI

```
┌─────────────────────────────────┐
│ Schedule: Analyze Job           │
├─────────────────────────────────┤
│ Frequency:                      │
│ ○ Once       ○ Daily            │
│ ○ Weekly     ○ Monthly          │
│                                 │
│ Day: [Mon ▼]  Time: [09:00 ▼]  │
│                                 │
│ [Schedule]  [Cancel]            │
└─────────────────────────────────┘
```

- **Once**: Run at a specific date+time (one-off deferred execution)
- **Daily**: Run every day at specified time
- **Weekly**: Run on specified day at specified time
- **Monthly**: Run on specified day-of-month at specified time

#### Schedule Storage (per-plugin)

Schedules are persisted as YAML files alongside the action they belong to, in each plugin's `augur/data/schedules/` directory:

```yaml
# plugins/career/skills/career/augur/data/schedules/sync-jobs-weekly.yaml
action_id: sync-jobs
plugin: career/career                 # owning plugin (discovery validates this matches the directory)
schedule:
  frequency: weekly
  day: monday
  time: "09:00"
  timezone: America/Los_Angeles
created: 2026-02-20T14:30:00Z
last_run: 2026-02-20T09:00:12Z
next_run: 2026-02-27T09:00:00Z
enabled: true
run_count: 4
last_result:
  status: success
  message: "Synced 12 jobs"
  duration_ms: 3400
```

**Discovery**: The daemon walks `plugins/*/skills/*/augur/data/schedules/*.yaml` — same pattern as action discovery. Disabling a plugin automatically hides its schedules (mount-plugins skips disabled plugins, daemon follows the same filter).

#### Schedule Executor

The daemon (`plugins/observability/skills/daemon`) gains a **schedule tick** that runs every minute:

1. Walk `plugins/*/skills/*/augur/data/schedules/*.yaml` (respecting plugin enabled state)
2. For each enabled schedule where `next_run <= now`:
   - Resolve the action by loading `../actions/{action_id}.yaml` from the same plugin
   - Execute via the same backend path as manual clicks (`/api/actions/run` for `fire`, `/api/actions/oneshot` for `oneshot`)
   - Update `last_run`, `next_run`, `run_count`, `last_result` in-place in the schedule YAML
   - Log execution to `runtime/logs/schedules.jsonl`
3. Skip disabled schedules and schedules in disabled plugins

#### Schedules Management Page

A dedicated page at `/ai/schedules` (under the AI hub) provides full visibility:

```
┌─────────────────────────────────────────────────────────────────┐
│ Scheduled Actions                                    [+ New]    │
├──────────────────┬──────────┬──────────┬────────┬──────────────┤
│ Action           │ Frequency│ Next Run │ Status │ Actions      │
├──────────────────┼──────────┼──────────┼────────┼──────────────┤
│ Sync Jobs        │ Weekly   │ Mon 9am  │ ✓ OK   │ [Run] [⏸] [🗑]│
│ Refresh Telemetry│ Daily    │ Tomorrow │ ✓ OK   │ [Run] [⏸] [🗑]│
│ Reindex All      │ Weekly   │ Sun 2am  │ ⚠ Slow │ [Run] [⏸] [🗑]│
│ Analyze Metrics  │ Monthly  │ Mar 1    │ ✓ OK   │ [Run] [⏸] [🗑]│
└──────────────────┴──────────┴──────────┴────────┴──────────────┘

│ Run History (last 7 days)                                       │
│ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │
│ Mon  Tue  Wed  Thu  Fri  Sat  Sun                               │
│ 3/3  2/2  3/3  2/3  3/3  1/1  2/2   (success/total)            │
```

**Page features**:
- View all scheduled actions with next run time and last status
- **Run Now**: Execute immediately regardless of schedule
- **Pause/Resume**: Toggle `enabled` without deleting
- **Delete**: Remove schedule YAML from the owning plugin's `augur/data/schedules/`
- **Run history**: Timeline chart showing executions over last 7 days
- **Failed runs**: Highlighted with error message and retry button
- **Plugin column**: Shows which plugin owns each schedule (e.g., "career/career", "dev/advisor")
- **Orphan detection**: If a schedule references an action_id that no longer exists in the same plugin's `actions/` directory, show warning with cleanup button
- **Disabled plugins**: Schedules from disabled plugins shown greyed out with "Plugin disabled" badge

#### Which actions are schedulable?

By default:
- All `fire` actions are schedulable (scripts that refresh/sync data)
- All `oneshot` actions are schedulable (AI analysis that benefits from periodic refresh)
- `ide` and `modal` actions are NOT schedulable (require human interaction)

Override via `schedulable: false` on any `fire`/`oneshot` action, or `schedulable: true` on an `ide` action (edge case: scheduled IDE prompts that auto-send to the default IDE).

### ActionDialogView Refactor

ActionDialogView is refactored to serve only the `ide` dispatch mode (shown when multiple/no IDEs detected):

**Buttons**:
- Primary: one button per detected IDE ("Send to Cursor", "Send to VS Code")
- If no IDE detected: "Start CLI & Send" as primary
- Secondary row: "Copy to Clipboard"
- Dismiss

**Removed from ActionDialogView**:
- "Other CLI" picker (absorbed into IDE picker — CLIs are just another target)
- Generic "Continue" button (replaced by IDE-specific buttons)

The `onContinueWithCli` / `onSendToOtherCli` callbacks are replaced by a single `onSendToTarget(targetId: string)` callback where targetId is an IDE name or CLI id.

### CLI Conflict Handling

When user clicks an `ide` action while CLI is mid-conversation:
- Show confirmation: "CLI is busy. Send anyway?"
- If yes, paste prompt into active session
- No queuing — keep it simple

### useActionRunner Refactor

The hook is rewritten around `dispatch`:

```typescript
export function useActionRunner() {
  const runAction = async (action: ActionDef) => {
    if (action.confirmation && !window.confirm(action.confirmation)) return;

    switch (action.dispatch) {
      case 'fire':
        return runFire(action);
      case 'oneshot':
        return runOneshot(action);
      case 'ide':
        return runIde(action);
      case 'modal':
        return; // handled by component-level modal state
    }
  };
}
```

No `resolveFlow()`. No `mode` fallback. One field, one switch.

## Consequences

### Positive

- **Faster for content actions**: ~21 oneshot actions skip ActionDialogView entirely. One click → result on page.
- **Faster for IDE actions**: ~17 IDE actions with a single detected IDE send directly. One click → sent to Cursor.
- **Better result locality**: Analysis results appear on the page where they're relevant, not buried in a terminal.
- **Recurring automation**: Any fire/oneshot action can be scheduled with a clock icon. Managed from one page.
- **Clean interface**: One `dispatch` field replaces three (`flow`, `mode`, `promptOverride`). No ambiguity.
- **Progressive complexity**: Simple actions are instant. Complex actions show the full dialog. Shift+Click overrides.
- **Distributed ownership**: Each plugin owns its action configs and schedule configs. Self-contained, portable, no central bottleneck.
- **No central file**: Eliminating `config/dashboard/action_buttons.yaml` removes a 788-line monolith that mixed 8 plugins' concerns.
- **Unified model**: Chains, actions, and skill triggers all collapse into one concept — an action YAML with a dispatch mode. No separate chain UI, no separate chain discovery, no separate chain API.

### Negative

- **Breaking migration**: All ~50 action definitions must be rewritten to v2 schema AND relocated to their owning plugins. No fallback.
- **25 actions relocated**: The central file's 25 actions are split across ~10 plugin directories. Requires careful mapping.
- **Chain UI deleted**: `ChainsMenu`, `ChainTriggerModal`, `ChainCard`, `ChainsSection`, `/api/agents/chains` are removed. Skills that were only accessible as chains must get action YAMLs or lose their dashboard entry point.
- **New infrastructure**: `oneshot` endpoint, schedule executor, schedules management page, per-plugin schedule YAML storage.
- **Two result display paths**: Inline cards and FloatingChat messages need consistent styling.
- **Prompt extraction**: Large inline prompts in the central YAML must be extracted to `.md` files in each plugin's `prompts/` directory.

## Implementation Plan

### Swarm Team Structure

Implementation uses a 5-agent swarm with a lead coordinator. All agents work from a dedicated worktree.

```
┌─────────────────────────────────────────────────────┐
│                    LEAD (coordinator)                │
│  Owns: worktree setup, task assignment, merge gates │
│  Does NOT write code — orchestrates and unblocks    │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐          │
│  │ SCHEMA   │  │ MIGRATOR │  │ FRONTEND │          │
│  │ (python) │  │ (yaml)   │  │ (tsx)    │          │
│  └──────────┘  └──────────┘  └──────────┘          │
│                                                     │
│  ┌──────────┐  ┌──────────┐                         │
│  │ BACKEND  │  │ DAEMON   │                         │
│  │ (api)    │  │ (python) │                         │
│  └──────────┘  └──────────┘                         │
└─────────────────────────────────────────────────────┘
```

| Agent | Type | Owns | Key files |
|-------|------|------|-----------|
| **lead** | coordinator | Task list, merge gates, verification | — |
| **schema** | general-purpose | Schema template, ActionDef interface, validation, MCP tool updates | `action-schema.yaml`, `useActionRunner.ts`, `ActionDef` type, MCP chain tools |
| **migrator** | general-purpose | YAML migration — central file distribution, chain absorption, prompt extraction | `config/dashboard/action_buttons.yaml` → `plugins/*/augur/data/actions/`, `chains/*.yaml` → `actions/*.yaml` |
| **frontend** | general-purpose | Dashboard components — ActionDialogView, InlineResultCard, SchedulePopover, IDE picker, chain UI deletion | `ActionDialogView.tsx`, `ActionButton.tsx`, `FloatingChat.tsx`, `ChainsMenu.tsx` (delete), `ChainTriggerModal.tsx` (delete) |
| **backend** | general-purpose | API routes — action discovery, oneshot endpoint, schedule CRUD, IDE bridge wiring | `/api/actions/route.ts`, `/api/actions/oneshot/route.ts`, `/api/schedules/route.ts` |
| **daemon** | general-purpose | Schedule executor, daemon tick, schedule page | `schedule_executor.py`, daemon integration, `/ai/schedules/page.tsx` |

### Phase 1: Foundation (all agents, parallel)

**Merge gate**: Phase 1 must complete before Phase 2-3 can start. Agents work in parallel within Phase 1.

#### lead
1. Set up worktree: `./scripts/worktree-launch.sh --setup adr-130 action-dispatch`
2. Create task list with all Phase 1 tasks
3. Assign tasks to agents
4. Monitor progress, unblock dependencies
5. Run `npm run build` after all Phase 1 agents complete — must pass before moving to Phase 2

#### schema (blocks: migrator, frontend, backend)
1. Create `plugins/ai/skills/ai_bridge/augur/data/action-schema.yaml` — central schema template with dispatch modes, required/optional fields, validation rules
2. Rewrite `ActionDef` TypeScript interface in `src/dashboard/hooks/useActionRunner.ts`:
   - Remove: `flow`, `mode`, `name`, `category`, `promptOverride`, `prompt_template`, `instruction_script`, `json_output`, `ide_type`, `tab`
   - Add: `dispatch: 'fire' | 'oneshot' | 'ide' | 'modal'`, `prompt?: string`, `prompt_file?: string`, `schedulable?: boolean`, `_plugin?: string`
3. Rewrite `useActionRunner` hook as clean switch on `dispatch` (no `resolveFlow`, no fallbacks)
4. Update `ActionDef` exports and all TypeScript imports that reference removed fields
5. Signal **migrator** and **frontend** that the interface is ready

**Files touched**: `useActionRunner.ts`, `action-schema.yaml`, any src/lib type files that re-export ActionDef

#### migrator (waits for: schema interface)
1. Parse `config/dashboard/action_buttons.yaml` (all 25 actions)
2. For each action, determine owning plugin by `category`/`page`/`script_path`:
   - `category: careers` → `plugins/career/skills/career/`
   - `category: development` → `plugins/dev/skills/developer/`
   - `category: workshop` + `refresh_bugs/sync_bugs` → `plugins/dev/skills/advisor/`
   - `category: memory` → `plugins/ai/skills/knowledge/`
   - `category: venture` → `plugins/professional/skills/venture/`
   - `category: factory` + `triage/execute` → `plugins/dev/skills/advisor/`
   - `category: intelligence` → `plugins/dev/skills/advisor/`
   - `enhance_dashboard` → `plugins/dev/skills/frontend/`
   - `run_nightly` → `plugins/observability/skills/daemon/`
   - `system_review*` → `plugins/admin/skills/admin/`
   - `open_data_folder` → `plugins/admin/skills/admin/`
3. For each action, write v2 YAML to `plugins/{bundle}/skills/{skill}/augur/data/actions/{id}.yaml`
4. Extract large `prompt_template` values (>10 lines) to `plugins/{bundle}/skills/{skill}/prompts/{id}.md`, set `prompt_file` in YAML
5. Migrate existing ~14 skill-specific action YAMLs to v2 schema (already in correct dirs — just rewrite fields)
6. Migrate legacy chain YAMLs (`plugins/*/skills/*/chains/*.yaml`):
   - For each chain YAML: read agents, triggers, success_criteria
   - Append chain metadata to the skill's `SKILL.md` (agents section, trigger phrases)
   - Create action YAML in `augur/data/actions/` with `dispatch: ide` (or `oneshot` for analysis chains)
   - Delete the source `chains/*.yaml` file and empty `chains/` directories
7. Delete `config/dashboard/action_buttons.yaml`
8. Signal **backend** that action files are in place for discovery testing

**Files touched**: ~40 YAML files created/modified, ~10 prompt .md files extracted, `config/dashboard/action_buttons.yaml` deleted, `chains/` dirs deleted

#### frontend (waits for: schema interface)
1. Migrate ~20 inline `ActionDef` objects in TSX components to v2 schema:
   - `src/app/apple/page.tsx` — quick-capture, transcribe-memo, triage-inbox, refresh-inbox
   - `src/app/career/resume/page.tsx` — upload-resume, ai-tailor, ats-review, improve-writing
   - `src/app/career/star/page.tsx` — prep-interview
   - `src/app/lifestyle/recipes/RecipesActions.tsx` — ai-recipe-ideas, ai-meal-plan, ai-find-similar, etc.
   - `src/app/lifestyle/movies/MoviesContent.tsx` — ai-recommend-movies, ai-where-to-watch, etc.
   - `src/app/growth/learning/page.tsx` — suggest-courses, learning-roadmap
   - `src/app/growth/hardening/page.tsx` — harden-knowledge, suggest-roles
   - `src/app/google-workspace/AiActions.tsx` — extract-career-emails
   - `src/app/google-workspace/gmail/EmailDetail.tsx` — draft-reply, schedule-follow-up
   - `src/app/eisenhower/inbox/page.tsx` — prioritize
   - `src/app/health/virtual-doctor/page.tsx` — virtual-doctor-chat
   - `src/dashboard/components/GlobalSearchBar.tsx` — global-search
   - `src/dashboard/components/ProductizationTaskRow.tsx` — refactor actions
2. Delete chain UI components:
   - `src/dashboard/components/action-bar/ChainsMenu.tsx`
   - `src/dashboard/components/ChainTriggerModal.tsx`
   - `src/dashboard/components/ChainCard.tsx`
   - `src/dashboard/components/agents/ChainsSection.tsx`
3. Remove chain imports and chain-specific code from:
   - `src/dashboard/hooks/usePageActionsData.ts` — remove chain fetching, ChainDefinition interface
   - `src/dashboard/components/action-bar/` — remove chain menu references
   - `src/dashboard/components/PageActionButtons.tsx` — remove chains section
4. Update `ActionButton.tsx` — remove flow-based badge logic (fast/agent), replace with dispatch-based rendering

**Files touched**: ~20 TSX files modified, ~4 TSX files deleted

#### backend (waits for: schema interface + migrator action files)
1. Rewrite `/api/actions/route.ts`:
   - Discovery: walk `plugins/*/skills/*/augur/data/actions/*.yaml`
   - Validation: load `action-schema.yaml`, reject files with `flow`/`mode` fields
   - Cache: 30-second TTL on discovery results
   - Populate `_plugin` field from directory path
   - Load `prompt_file` contents into `prompt` field at discovery time
2. Delete `/api/agents/chains/route.ts`
3. Verify all action endpoints work with new schema

**Files touched**: `/api/actions/route.ts`, `/api/agents/chains/route.ts` (delete)

### Phase 2: `oneshot` dispatch (frontend + backend, parallel)

**Merge gate**: Phase 1 must pass build. Phase 2 agents work in parallel.

#### backend
1. Create `/api/actions/oneshot/route.ts`:
   - POST handler: receives `{actionId, prompt, pageContext}`
   - Resolves action from discovered actions
   - Runs headless AI call via MCP tool (or `claude --print` subprocess)
   - Returns `{result: string, truncated: boolean, duration_ms: number}`
   - 60-second timeout, streaming not required (headless)
2. Add error handling: action not found, AI call timeout, prompt too large

**Files touched**: `/api/actions/oneshot/route.ts` (new)

#### frontend
1. Create `src/dashboard/components/InlineResultCard.tsx`:
   - Expandable card component for short oneshot results
   - Shows: action label, result text, timestamp, "Open in Chat" link
   - Expand/collapse animation
   - GlassCard styling per design standards
2. Add `runOneshot()` function to `useActionRunner`:
   - POST to `/api/actions/oneshot`
   - If result < 500 chars → render InlineResultCard via toast/portal
   - If result >= 500 chars → open FloatingChat, inject as read-only chat message
   - Loading spinner on action button during execution
3. Add Shift+Click detection to action buttons:
   - If Shift held → override to show ActionDialogView for user remarks input
   - Works for both `oneshot` and `ide` dispatch modes
4. Wire FloatingChat to display oneshot results as chat messages without starting CLI:
   - New chat message type: `oneshot-result`
   - If user types follow-up → start CLI on demand with original result as context

**Files touched**: `InlineResultCard.tsx` (new), `useActionRunner.ts`, `ActionButton.tsx`, `FloatingChat.tsx`

### Phase 3: `ide` direct dispatch (frontend + backend, parallel)

**Merge gate**: Phase 1 must pass build. Can run in parallel with Phase 2.

#### backend
1. Create `/api/ide/detect/route.ts`:
   - GET handler: calls `get-ide-status` MCP tool
   - Returns `{ides: [{name, status, pid}], count: number}`
   - 5-second cache TTL
2. Verify `send-ide-prompt` MCP tool works end-to-end from API route

**Files touched**: `/api/ide/detect/route.ts` (new or extend existing `/api/ide/status`)

#### frontend
1. Add `runIde()` function to `useActionRunner`:
   - Call `/api/ide/detect` to get running IDEs
   - If exactly 1 IDE → call `/api/ide/prompt` directly, show toast "Sent to {ide} ✓"
   - If multiple IDEs → open ActionDialogView with IDE picker
   - If no IDEs → open ActionDialogView with "Start CLI & Send" fallback
2. Refactor `ActionDialogView.tsx`:
   - Remove: `onContinueWithCli`, `onSendToOtherCli`, `selectedCli`, `cliConfigs` props
   - Add: `onSendToTarget(targetId: string)`, `targets: Array<{id, label, type: 'ide'|'cli'}>` props
   - Primary buttons: one per detected IDE/CLI target
   - Secondary: "Copy to Clipboard"
   - Dismiss
3. Update `FloatingChat.tsx` to pass new ActionDialogView props
4. Add Shift+Click override: always show dialog regardless of IDE count

**Files touched**: `useActionRunner.ts`, `ActionDialogView.tsx`, `FloatingChat.tsx`

### Phase 4: Cron scheduling (daemon + frontend + backend, parallel)

**Merge gate**: Phase 1 must pass build. Can run in parallel with Phase 2-3.

#### daemon
1. Create `plugins/observability/skills/daemon/scripts/schedule_executor.py`:
   - `discover_schedules()`: walk `plugins/*/skills/*/augur/data/schedules/*.yaml`, respect plugin enabled state
   - `tick()`: for each enabled schedule where `next_run <= now`, execute action
   - Action execution: resolve action YAML from `../actions/{action_id}.yaml`, dispatch via `/api/actions/run` (fire) or `/api/actions/oneshot` (oneshot)
   - Update schedule YAML in-place: `last_run`, `next_run`, `run_count`, `last_result`
   - Calculate `next_run` from frequency/day/time
   - Log each execution to `runtime/logs/schedules.jsonl`
2. Wire `tick()` into daemon's main loop (1-minute interval)
3. Add schedule schema definition to `action-schema.yaml`

**Files touched**: `schedule_executor.py` (new), daemon main script, `action-schema.yaml`

#### backend
1. Create `/api/schedules/route.ts`:
   - GET: discover all schedules from `plugins/*/skills/*/augur/data/schedules/*.yaml`
   - POST: create schedule — write YAML to owning plugin's `augur/data/schedules/`
   - PUT: update schedule (enable/disable, change frequency)
   - DELETE: remove schedule YAML file
   - POST `?action=run-now`: trigger immediate execution of a schedule's action
2. Validate: action_id must exist in the same plugin's `actions/` directory

**Files touched**: `/api/schedules/route.ts` (new)

#### frontend
1. Create `src/dashboard/components/SchedulePopover.tsx`:
   - Trigger: clock icon button next to schedulable action buttons
   - Content: frequency radio (once/daily/weekly/monthly), day picker, time picker
   - Submit: POST to `/api/schedules`
   - Cancel: close popover
   - GlassCard styling, Popover component from design system
2. Add clock icon to `ActionButton.tsx` for actions with `schedulable: true`
3. Wire popover open/close state

**Files touched**: `SchedulePopover.tsx` (new), `ActionButton.tsx`

### Phase 5: Schedules management page (daemon, single agent)

**Merge gate**: Phase 4 must complete (schedule backend + executor exist).

#### daemon (or frontend agent if available)
1. Create skill dashboard page: `plugins/ai/skills/ai_bridge/augur/schedules/page.tsx`
   - Table columns: Action, Plugin, Frequency, Next Run, Last Status, Actions
   - Actions per row: Run Now, Pause/Resume toggle, Delete (with confirmation)
   - Plugin column: badge showing `{bundle}/{skill}`
   - Disabled plugins: grey row with "Plugin disabled" badge
   - Orphan detection: warning icon + "Action deleted" tooltip if `action_id` not found in same plugin
2. Add run history section:
   - Timeline chart (last 7 days): stacked bars per day (success=green, fail=red)
   - Data source: `runtime/logs/schedules.jsonl`
3. Add `/api/schedules/history/route.ts`:
   - GET: read `runtime/logs/schedules.jsonl`, return last 7 days aggregated by day
4. Register page in skill's `dashboard.yaml`

**Files touched**: `schedules/page.tsx` (new), `/api/schedules/history/route.ts` (new), `dashboard.yaml`

### Dependency Graph

```
Phase 1 (all parallel within phase):
  schema ──┬──→ migrator ──→ backend (discovery)
           ├──→ frontend (inline ActionDef migration)
           └──→ frontend (chain UI deletion)

  ← MERGE GATE: npm run build must pass →

Phase 2-4 (parallel across phases):
  Phase 2: backend (oneshot API) ║ frontend (InlineResultCard + runOneshot)
  Phase 3: backend (IDE detect)  ║ frontend (runIde + ActionDialogView refactor)
  Phase 4: daemon (executor)     ║ backend (schedule CRUD) ║ frontend (SchedulePopover)

  ← MERGE GATE: Phase 4 complete →

Phase 5: daemon (schedules page)
```

### Verification Checklist (lead runs after each phase)

#### After Phase 1
- [ ] `npm run build` passes with zero TypeScript errors
- [ ] No files reference `flow`, `mode`, `promptOverride`, `prompt_template` in action definitions
- [ ] `config/dashboard/action_buttons.yaml` does not exist
- [ ] No `chains/` directories exist under any plugin
- [ ] `ChainsMenu.tsx`, `ChainTriggerModal.tsx`, `ChainCard.tsx`, `ChainsSection.tsx` do not exist
- [ ] GET `/api/actions` returns all migrated actions with `dispatch` field
- [ ] GET `/api/agents/chains` returns 404

#### After Phase 2
- [ ] POST `/api/actions/oneshot` returns AI-generated result for a test action
- [ ] Short result (< 500 chars) renders as InlineResultCard
- [ ] Long result (>= 500 chars) opens FloatingChat with chat message
- [ ] Shift+Click on oneshot button opens ActionDialogView

#### After Phase 3
- [ ] Click `ide` action with one IDE → sends directly, toast confirms
- [ ] Click `ide` action with no IDE → ActionDialogView opens with CLI fallback
- [ ] Shift+Click on `ide` action → always opens dialog
- [ ] ActionDialogView shows IDE-specific buttons, no legacy "Other CLI" picker

#### After Phase 4
- [ ] Clock icon visible on schedulable actions
- [ ] SchedulePopover opens, creates schedule YAML in correct plugin directory
- [ ] Daemon tick executes due schedules and updates YAML
- [ ] GET `/api/schedules` returns all schedules with plugin ownership

#### After Phase 5
- [ ] `/ai/schedules` page renders table with all scheduled actions
- [ ] Run Now / Pause / Delete work correctly
- [ ] Orphan detection shows warning for deleted actions
- [ ] Run history chart renders last 7 days
