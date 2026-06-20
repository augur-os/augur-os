---
status: Implemented
date: '2026-02-24'
deciders:
- Augur project team
related:
- ADR-130 (action button dispatch modes)
- ADR-145 (workflow capability refactor)
- ADR-124 (focus button)
hub: null
tags:
- ide
- dispatch
- continuity
- structured
- prompts
superseded_by: null
---

# ADR-146: IDE Dispatch Continuity — Structured Prompts, Progress Polling, and Stage Chaining

## Context

ADR-130 established five dispatch modes (`fire`, `oneshot`, `chat`, `ide`, `modal`) and distributed action configs to plugins. The `ide` dispatch mode sends prompts to Claude Desktop, Cursor, or other IDE agents. Today there are ~79 IDE-dispatched actions across 17 hubs.

Three UX problems remain unsolved for IDE dispatch:

### Problem 1: Vague prompts produce unreliable IDE execution

The majority of `ide` action prompts are 1-2 sentences with no reference to available MCP tools:

```yaml
# Typical vague prompt
prompt: >
  Refine and polish the draft for post "{slug}". Read the draft file,
  improve clarity, fix grammar, tighten the writing, and save the
  improved version back.
```

Claude Desktop doesn't know which MCP tools to call, where files live, or how to write results back. Some prompts reference `/app-dd` slash commands that only exist in the Augur CLI agent — Claude Desktop doesn't have them. The result: IDE either guesses wrong, asks the user for clarification, or silently produces incorrect output.

The content pipeline fix (preceding commit) proved that **MCP-aware structured prompts** produce reliable IDE execution:

```
You have access to the Augur MCP server with content pipeline tools.

Step 1: Call the MCP tool `get-smb-content-post` with slug "{slug}"...
Step 2: Refine and polish the draft content...
Step 3: Call the MCP tool `update-smb-draft` with slug "{slug}"...
Step 4: Confirm completion with the file path and character count...

The next pipeline step is "Tailor Voice". Ask if I'd like you to run it now.
```

This pattern should be the standard for all IDE-dispatched actions, not a one-off fix.

### Problem 2: No progress feedback after IDE dispatch

After clicking an action button:
- `fire` → toast with result (immediate feedback)
- `oneshot` → inline card or chat (feedback in seconds)
- `ide` → toast "Sent to Cursor" → **nothing** (user must manually switch to IDE)

The dashboard goes dark. There is no indication whether the IDE started working, how long it's been running, or when it finished. For multi-minute tasks (code refactors, content pipelines, research), users lose confidence and context.

The content pipeline added per-component polling (5s intervals against the post API), but this is baked into a single component — not reusable.

### Problem 3: No continuation after IDE completes

When an IDE finishes a task, the user must manually navigate back to the dashboard and figure out what to do next. For multi-step workflows (refine → tailor → translate → split, or architect → develop → validate → review), this is a significant UX gap.

The content pipeline added `NEXT_STAGE` constants and a "Next: Tailor Voice" button — again, baked into one component.

## Decision

Generalize the content pipeline's three innovations into reusable infrastructure that any `ide` action can opt into. The work is split into three layers — each is independently valuable and can be adopted incrementally.

### Layer 1: MCP-Aware Prompt Standard

**Principle**: Every `ide` action that calls MCP tools must name them explicitly in the prompt.

#### New optional YAML fields

Add to the action schema (`plugins/ai/skills/ai_bridge/augur/data/action-schema.yaml`):

```yaml
optional_fields:
  # ... existing fields ...
  - mcp_tools         # list of MCP tool names this action uses
  - completion_hint   # how to detect completion (see Layer 2)
  - next_action       # action ID to suggest after completion (see Layer 3)
```

#### `mcp_tools` field

A list of MCP tool names that the action's prompt references. Discovery enriches the prompt at runtime with a preamble:

```yaml
# plugins/career/skills/career/augur/data/actions/research-company.yaml
id: research-company
label: Research Company
dispatch: ide
page: /career/companies/[slug]
mcp_tools:
  - get-career-companies
  - update-career-company
prompt: |
  Step 1: Call `get-career-companies` with slug "{slug}" to read the current profile.
  Step 2: Research the company online — news, Glassdoor, tech stack, hiring.
  Step 3: Call `update-career-company` with the updated profile data.
  Step 4: Confirm what was updated.
```

**Discovery behavior**: When `mcp_tools` is present, discovery prepends to the resolved prompt:

```
You have access to the Augur MCP server. The following tools are available for this task:
- get-career-companies: Get career company data
- update-career-company: Update career company profile

```

Tool descriptions are read from the MCP tool registry (the same registry used by Tool Search). If a listed tool doesn't exist, discovery logs a warning and omits it.

This ensures Claude Desktop knows which tools are available without requiring prompt authors to write the preamble manually.

#### Prompt template standard

Prompts for `ide` actions that use MCP tools should follow this structure:

```
Step 1: Call `{read-tool}` with {params} to read current state.
Step 2: {transform instruction}.
Step 3: Call `{write-tool}` with {params} to write the result.
Step 4: Confirm completion with {output details}.
```

This is a convention, not enforced by schema. A linter rule in `/ops-plugin-lint` warns when `mcp_tools` is set but the prompt doesn't reference all listed tools.

### Layer 2: Dispatch Progress Polling

**Principle**: After IDE dispatch, the dashboard should show progress and detect completion.

#### New `completion_hint` field

```yaml
# Action that polls an API endpoint for completion
id: tailor-voice
dispatch: ide
completion_hint:
  type: poll
  url: /api/consulting/client-smb-design/content-pipeline/posts/{slug}
  field: stages.tailor        # JSON path to check
  done_value: done            # value that signals completion
  interval_ms: 5000           # polling interval (default: 5000)
  timeout_ms: 300000          # max wait time (default: 300000 = 5 min)
```

```yaml
# Action with no completion detection (manual check)
id: fix-bug
dispatch: ide
# No completion_hint — dashboard shows "Sent to IDE" toast only
```

#### `useDispatchProgress` hook

New hook extracted from the content pipeline's polling logic:

```typescript
// src/dashboard/hooks/useDispatchProgress.ts

interface DispatchProgressOptions {
  /** Polling endpoint URL (template vars like {slug} are resolved) */
  url: string;
  /** JSON path to the completion field (dot notation) */
  field: string;
  /** Value that signals completion */
  doneValue: string;
  /** Polling interval in ms (default: 5000) */
  intervalMs?: number;
  /** Timeout in ms (default: 300000) */
  timeoutMs?: number;
}

interface DispatchProgressState {
  /** Currently active dispatch action ID, or null */
  activeDispatch: string | null;
  /** Action ID that just completed, or null */
  completedAction: string | null;
  /** Number of polls elapsed */
  pollCount: number;
  /** Whether polling timed out */
  timedOut: boolean;
  /** Start tracking a dispatch */
  startTracking: (actionId: string) => void;
  /** Stop tracking (manual dismiss) */
  stopTracking: () => void;
  /** Clear the completed state */
  clearCompleted: () => void;
}

function useDispatchProgress(
  options: DispatchProgressOptions | null,
  templateVars?: Record<string, string>,
): DispatchProgressState;
```

**Behavior**:
1. When `startTracking(actionId)` is called, begins polling `url` at `intervalMs` intervals
2. Each poll fetches the URL, extracts the value at `field` (JSON path), compares to `doneValue`
3. When match found: sets `completedAction`, calls `stopTracking()`
4. After `timeoutMs`: sets `timedOut`, calls `stopTracking()`
5. Template variables in `url` (e.g. `{slug}`) are resolved from `templateVars`

Components that need progress tracking import this hook instead of reimplementing polling logic.

#### `DispatchProgressBar` component

Reusable UI component for showing progress:

```typescript
// src/dashboard/components/DispatchProgressBar.tsx

interface DispatchProgressBarProps {
  activeDispatch: string | null;
  actionLabel: string;
  pollCount: number;
  intervalMs: number;
  timedOut: boolean;
  onDismiss?: () => void;
}
```

Renders the spinner + elapsed time + timeout warning. Extracted from the content pipeline's inline JSX.

#### Integration with `useActionRunner`

`useActionRunner` gains awareness of `completion_hint`:

```typescript
case 'ide':
  await runIde(action, chatStore, setState);
  // If action has completion_hint, return it for caller to use
  if (action.completion_hint) {
    setState(prev => ({
      ...prev,
      completionHint: action.completion_hint,
    }));
  }
  return;
```

Components that render action buttons can use the returned `completionHint` to wire up `useDispatchProgress`. Components that don't care about progress (e.g. simple action lists) ignore it.

### Layer 3: Action Continuation Chain

**Principle**: After an action completes, the dashboard suggests the next action.

#### New `next_action` field

```yaml
id: refine-draft
dispatch: ide
next_action: tailor-voice     # suggest this action after completion

id: tailor-voice
dispatch: ide
next_action: translate-content

id: translate-content
dispatch: ide
next_action: split-platforms

id: split-platforms
dispatch: ide
# No next_action — terminal stage
```

#### `ActionContinuationBanner` component

```typescript
// src/dashboard/components/ActionContinuationBanner.tsx

interface ActionContinuationBannerProps {
  completedAction: ActionDef;
  nextAction: ActionDef | null;
  onRunNext: (action: ActionDef) => void;
  onDismiss: () => void;
}
```

Renders the success banner with "Next: {label}" button. The parent component resolves `next_action` ID to a full `ActionDef` via the discovered actions list.

#### Discovery enrichment

When discovery processes an action with `next_action`, it validates that the referenced action ID exists. If not found, it logs a warning and sets `next_action` to `undefined`.

### Layer Summary

| Layer | Field | Component/Hook | Adoptable independently? |
|-------|-------|----------------|--------------------------|
| 1. Structured prompts | `mcp_tools` | Discovery enrichment | Yes — just add field to YAML |
| 2. Progress polling | `completion_hint` | `useDispatchProgress`, `DispatchProgressBar` | Yes — opt-in per component |
| 3. Continuation | `next_action` | `ActionContinuationBanner` | Yes — opt-in per action |

### Migration path for content pipeline

After these components exist, `PipelineStages.tsx` is refactored to use them:

```diff
- const [activeDispatch, setActiveDispatch] = useState<string | null>(null);
- const [completedStage, setCompletedStage] = useState<string | null>(null);
- const [pollCount, setPollCount] = useState(0);
- // ... 40 lines of polling useEffect ...

+ const progress = useDispatchProgress(
+   activeAction?.completion_hint ?? null,
+   { slug },
+ );
```

The per-action YAML files get `completion_hint` and `next_action` fields. The inline `NEXT_STAGE` constants and polling logic are deleted. The component becomes a thin action-grid renderer.

### What this ADR does NOT change

- **Dispatch modes**: Still `fire`, `oneshot`, `chat`, `ide`, `modal` as defined in ADR-130
- **Action discovery**: Still walks `plugins/*/skills/*/augur/data/actions/*.yaml`
- **ActionDialogView**: Still shown for 0/multiple IDEs — no changes
- **`fire`/`oneshot`/`modal` actions**: Unaffected — these already have adequate feedback
- **Prompt content**: Each skill author writes their own prompts — this ADR provides structure, not content

## Implementation

### Phase 1: Schema + Discovery (S)

1. Add `mcp_tools`, `completion_hint`, `next_action` to action schema YAML
2. Update discovery to read new fields and add to `ActionDef`
3. Update `ActionDef` TypeScript interface
4. Add MCP tool preamble generation in discovery when `mcp_tools` is set
5. Add `/ops-plugin-lint` check: warn when `mcp_tools` is set but prompt doesn't reference all tools

### Phase 2: Progress hook + component (M)

1. Extract `useDispatchProgress` hook from `PipelineStages.tsx` logic
2. Build `DispatchProgressBar` component
3. Wire into `useActionRunner` return value
4. Refactor `PipelineStages.tsx` to use the new hook

### Phase 3: Continuation component (S)

1. Build `ActionContinuationBanner` component
2. Wire into components that use `useDispatchProgress`
3. Add `next_action` to content pipeline action YAMLs
4. Refactor `PipelineStages.tsx` to use the new component

### Phase 4: Prompt migration (L — incremental)

Migrate existing `ide` action prompts to MCP-aware format. Priority order:
1. Actions with known MCP tool dependencies (~25 actions)
2. Actions with `prompt_file` that need restructuring (~15 actions)
3. Simple actions where generic prompts are sufficient (~39 actions — lower priority)

## Consequences

### Positive

- **Reliable IDE execution**: Explicit tool references eliminate guesswork for Claude Desktop
- **User confidence**: Progress UI shows the system is working, not hung
- **Workflow continuity**: Users flow through multi-step workflows without manual navigation
- **Incremental adoption**: Each layer is independently valuable — skills can adopt one at a time
- **DRY**: Polling logic, progress UI, continuation banner extracted from one-off implementations

### Negative

- **Three new YAML fields** to learn for action authors (all optional — zero migration burden)
- **Prompt verbosity**: MCP-aware prompts are 8-12 lines vs 1-2 lines (but produce better results)
- **Polling overhead**: ~1 fetch/5s per active dispatch (negligible — local API, no external calls)

### Risks

- **MCP tool names change**: If a tool is renamed, prompts and `mcp_tools` lists break. Mitigate: the lint rule catches stale tool references
- **Completion detection races**: Polling might miss a rapid completion. Mitigate: poll also runs immediately on start, and components can manually trigger recheck
- **Over-chaining**: Long chains (5+ stages) might feel like the user lost control. Mitigate: each continuation is a suggestion (button), not automatic execution
