---
status: Implemented
date: '2026-02-21'
deciders:
- Project team
related:
- ADR-130 (Action Button Dispatch Modes)
- ADR-106 (LLM-Assisted Retry)
hub: null
tags:
- dispatch
- escalation
- pattern
superseded_by: null
---

# ADR-134: Dispatch Escalation Pattern

## Context

ADR-130 established four dispatch modes (`fire`, `oneshot`, `ide`, `modal`) for dashboard action buttons. The content pipeline currently uses `dispatch: 'ide'` for all LLM-driven stages (tailor, translate, split), sending every request to the full IDE agent. This works but is inefficient:

- **Token waste**: The IDE agent loads ~10,000 tokens of system prompt (CLAUDE.md, memory, tool definitions) even for a structured 3,000-token pipeline stage that needs zero agent reasoning.
- **Latency**: Each stage takes 30-90s because the agent must parse the workflow, decide on tool calls, and orchestrate — even though the prompt is pre-assembled and the output location is fixed.
- **Cost**: A full 3-stage pipeline costs ~$0.15-0.25 via IDE dispatch vs ~$0.05-0.07 if executed as direct prompt→response.
- **No automatic recovery**: If the LLM produces structurally broken output (missing frontmatter, JSON syntax error, preamble text before content), the user must manually re-run. There is no validation or auto-repair layer.

The pattern affects every skill that needs LLM processing from the dashboard — content pipeline, code generation, invoice formatting, career content — not just the current consulting skill.

## Decision

### 1. Three-Tier Dispatch Escalation

Introduce an automatic escalation controller that routes LLM tasks through three tiers, defaulting to the cheapest/fastest and escalating on failure:

```
Tier 1: Oneshot CLI (default)
  ↓ validation fails
Tier 0: Auto-repair (no LLM)
  ↓ still broken
Tier 2: Embedded CLI (chat bar agent)
  ↓ validation fails
Tier 3: IDE Dispatch (full agent)
```

**Tier 1 — Oneshot CLI** (default for all structured tasks):
- Headless execution: spawn minimal CLI process or use `dispatch: 'oneshot'`
- Prompt pre-assembled via MCP tools (e.g., `get-smb-stage-prompt`)
- System prompt: ~500-2,000 tokens (task instructions only, no agent overhead)
- Writes output directly to file, exits
- Budget: ~12,000-15,000 tokens for full 3-stage pipeline, 20-60s

**Tier 0 — Auto-repair** (no LLM, deterministic):
- Runs after Tier 1 if validation detects structural issues
- Fixes: strip LLM preamble, repair frontmatter delimiters, fix JSON trailing commas, strip markdown code fences, normalize encoding
- Implemented as a shared Augur lib (`src/dashboard/lib/output-repair.ts`)
- Budget: 0 tokens, <100ms

**Tier 2 — Embedded CLI** (chat bar fallback):
- Uses the already-running CLI instance in the dashboard chat bar
- Receives a focused fix prompt with the validation error description
- Can self-recover with agent reasoning
- Budget: ~23,000-25,000 tokens, 1-3 min

**Tier 3 — IDE Dispatch** (last resort):
- Full IDE agent with complete context and tool access
- For exploration, debugging, or repeated failures
- Budget: ~32,000-50,000 tokens, 2-6 min

### 2. File-Based Result Delivery

All tiers write results to files. The dashboard NEVER receives LLM output through HTTP response bodies.

- LLM writes output to canonical file location (e.g., `posts/{slug}/tailored.md`)
- Dashboard polls lightweight GET endpoint checking file existence and mtime
- Polling interval: 3s, timeout: 60s (Tier 1), 180s (Tier 2), 300s (Tier 3)

**Actions**:
- Create `src/dashboard/lib/output-polling.ts` — shared polling utility with configurable timeout per tier
- Update `PipelineStages.tsx` polling to use shared utility

### 3. Output Validation Library

Create `src/dashboard/lib/output-validation.ts` with validators per output format:

**Markdown with frontmatter** (tailored.md, translated.md, variants):
- Has `---` delimiters (opening and closing)
- Required fields present (configurable per skill)
- Body non-empty and > 50 characters
- No raw JSON/code blocks as entire body

**JSON files**:
- Valid JSON (parseable)
- Required top-level keys present
- No null/undefined in required fields

**Platform variants** (split stage):
- All expected variant files exist
- Each has frontmatter with `platform` field matching filename
- Character count within platform rules

### 4. Auto-Repair Library

Create `src/dashboard/lib/output-repair.ts` with deterministic fixes:

| Issue | Repair |
|-------|--------|
| LLM preamble ("Here is the content:", "Sure, here's...") | Strip lines before first `---` or `{` |
| Missing frontmatter delimiters | Wrap with `---` if key-value lines detected |
| Markdown code fences around JSON | Strip `` ```json `` and `` ``` `` |
| Trailing comma in JSON | Remove before `}` or `]` |
| Empty body after frontmatter | Cannot fix — escalate |
| BOM / encoding issues | Strip BOM, normalize to UTF-8 |

### 5. Escalation Controller

Create `src/dashboard/lib/dispatch-escalation.ts` — shared controller that any skill can use:

```typescript
interface EscalationConfig {
  slug: string;
  stage: string;
  promptAssembler: () => Promise<string>;  // MCP tool call to get prompt
  outputPath: string;                       // Where to expect the file
  validator: (content: string) => ValidationResult;
  timeouts: { tier1: number; tier2: number; tier3: number };
}

async function executeWithEscalation(config: EscalationConfig): Promise<EscalationResult>;
```

**Actions**:
- Create `src/dashboard/lib/dispatch-escalation.ts`
- Create `src/dashboard/lib/output-validation.ts`
- Create `src/dashboard/lib/output-repair.ts`
- Create `src/dashboard/lib/output-polling.ts`
- Update `PipelineStages.tsx` to use `executeWithEscalation()` instead of direct `runAction()`
- Update action YAML for content pipeline stages to use `dispatch: 'oneshot'` (Tier 1 default)

### 6. CLI Pre-Loading

On dashboard load, immediately verify and connect the default CLI agent (Claude Code):
- The embedded CLI chat bar auto-detects and connects on mount
- Add a readiness check: `GET /api/ide/detect` cached with 5s TTL
- If no CLI connected after 10s, show subtle indicator (not blocking)
- First-time case is out of scope (user already instructed to ignore)

## Consequences

**Positive**:
- 3-4x cheaper token cost for the default path (~$0.05 vs ~$0.20)
- 3-6x faster execution (20-60s vs 2-6 min)
- Automatic recovery from common LLM output issues without user intervention
- Pattern reusable across all skills with LLM-driven workflows
- Non-blocking — Tier 1 doesn't occupy IDE or chat bar

**Negative**:
- New shared libraries to maintain (4 files: escalation, validation, repair, polling)
- Tier 1 has no feedback loop — if the prompt is wrong, user gets broken output + repair attempt before seeing useful error
- Validation rules must be configured per skill/output format

**Neutral**:
- File-based delivery is already the pattern (content pipeline already polls files)
- IDE dispatch (Tier 3) remains available for complex/exploratory tasks
- No changes to MCP tools — they already support headless execution

## Implementation Order

```
Phase 1: Shared Libraries (no UI changes)
├── Step 1: Create output-validation.ts (validators for md+frontmatter, JSON, variants)
├── Step 2: Create output-repair.ts (deterministic auto-fix for common LLM issues)
├── Step 3: Create output-polling.ts (shared polling with configurable timeouts)
└── Step 4: Create dispatch-escalation.ts (orchestrates tiers + validation + repair)

Phase 2: Content Pipeline Integration (depends on Phase 1)
├── Step 5: Update PipelineStages.tsx to use executeWithEscalation()
├── Step 6: Update content pipeline action YAMLs to dispatch: 'oneshot'
└── Step 7: Add CLI readiness indicator to dashboard layout

Phase 3: Verification
├── Step 8: Manual test — run pipeline via dashboard, verify Tier 1 succeeds
├── Step 9: Test escalation — intentionally break output, verify Tier 0 → 2 escalation
└── Step 10: Type check clean (npx tsc --noEmit)
```

## Alternatives Considered

### A. Direct Anthropic API calls from dashboard API routes

Reintroduce `callLlm()` in pipeline.ts but call the Anthropic API directly from Next.js API routes instead of routing through agents.

**Rejected**: Violates Critical Rule 7 (no direct LLM calls from dashboard). Creates API key management burden. Loses the ability to switch between LLM providers transparently.

### B. Always use IDE dispatch (current approach)

Keep all pipeline execution routed through `dispatch: 'ide'` to the connected IDE agent.

**Rejected**: 3-4x more expensive, 3-6x slower. The IDE agent loads full CLAUDE.md context (~10K tokens) for a task that needs ~3K tokens of actual content. Blocks the IDE for other user work during processing.

### C. WebSocket-based result streaming

Instead of file polling, use WebSocket to stream LLM output back to the dashboard in real-time.

**Rejected**: Adds significant infrastructure complexity (WebSocket server, connection management, reconnection logic). File-based delivery is simpler, works across all surfaces (MCP, CLI, IDE), and provides natural audit trail. Real-time streaming is not needed for 20-60s tasks.

## References

- [ADR-130: Action Button Dispatch Modes](ADR-130-action-button-dispatch-modes.md)
- [ADR-106: LLM-Assisted Retry](ADR-106-llm-assisted-retry.md)
- Dispatch Escalation Pattern — full reference doc with token budgets, code examples, and validation rules
- DASHBOARD.md topic doc — Critical Rule 7 (no direct LLM calls)

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-134: Dispatch Escalation Pattern**.

Read the full ADR: `docs/decisions/ADR-134-dispatch-escalation-pattern.md`
Read the reference pattern: `docs/references/dispatch-escalation-pattern.md`

### Team Orchestration

Create a team and spawn teammates to execute the plan below:

1. **Create team**: `TeamCreate(team_name="adr-134-dispatch-escalation", description="Implementing ADR-134: Dispatch Escalation Pattern")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role in the Execution Plan, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-134-dispatch-escalation", name="{role}",
        model="{tier-model}", prompt="You are '{role}' on the adr-134 team.
        Read your profile: .claude/agents/{role}.md
        Check TaskList for your assigned tasks. After each task: TaskUpdate to complete,
        SendMessage to team lead. If blocked, move to next available task.")
   ```
4. **Profile loading**: Each teammate MUST read `.claude/agents/{name}.md` for iron laws and constraints
5. **Communication**: Teammates use `SendMessage` to report completion, request reviews, and debate
6. **Dependencies**: PARALLEL phases -> spawn all at once. PIPELINE phases -> use task blocking
7. **Review cycle**: After implementation, validator reviews changes and debates with developer via `SendMessage`
8. **Shutdown**: When all phases pass, send `shutdown_request` to all teammates, then `TeamDelete()`

**Model mapping**: `low` -> haiku, `medium` -> sonnet, `high` -> opus

### Execution Plan

**Team name**: `adr-134-dispatch-escalation`

#### Phase 1: Shared Libraries
**Strategy**: PARALLEL (steps 1-3 have no deps, step 4 depends on 1-3)

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | Create output validation library with validators for markdown+frontmatter, JSON, and platform variant files. Include configurable required fields per format. | `src/dashboard/lib/output-validation.ts` |
| 1.2 | developer | medium | Create auto-repair library with deterministic fixes: strip LLM preamble, repair frontmatter delimiters, fix JSON trailing commas, strip markdown code fences, normalize encoding. | `src/dashboard/lib/output-repair.ts` |
| 1.3 | developer | medium | Create shared polling utility with configurable timeout per tier (60s/180s/300s), interval (3s), and file existence/mtime checking. | `src/dashboard/lib/output-polling.ts` |
| 1.4 | developer | high | Create escalation controller that orchestrates Tier 1 → Tier 0 → Tier 2 → Tier 3 using the validation, repair, and polling libs. Must accept a config object per skill. Depends on 1.1-1.3. | `src/dashboard/lib/dispatch-escalation.ts` |

#### Phase 2: Content Pipeline Integration
**Strategy**: PIPELINE (depends on Phase 1)

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Update PipelineStages.tsx to use `executeWithEscalation()` from the shared lib instead of direct `runAction()`. Wire up validation config for content pipeline output formats. | `plugins/consulting/skills/client-smb-design/augur/dashboard/content-pipeline/PipelineStages.tsx` |
| 2.2 | developer | low | Update or create content pipeline action YAMLs with `dispatch: 'oneshot'` as default tier. | `plugins/consulting/skills/client-smb-design/augur/data/actions/pipeline.yaml` |
| 2.3 | developer | low | Run `npm run mount-plugins` to propagate changes to src/dashboard/ | N/A |

#### Phase 3: Verification
**Strategy**: PIPELINE

| Step | Agent | Tier | Task |
|------|-------|------|------|
| 3.1 | validator | low | Run `npx tsc --noEmit` — must pass clean |
| 3.2 | validator | low | Verify no `callLlm` or `/api/llm` references remain in dashboard code |
| 3.3 | architect | low | Review escalation controller logic matches ADR intent — verify all 4 tiers are wired correctly |

### Completion Criteria
- [ ] All phases executed
- [ ] Type check passes (`npx tsc --noEmit`)
- [ ] No direct LLM calls in dashboard code
- [ ] Escalation controller handles Tier 1 → 0 → 2 → 3 progression
- [ ] Content pipeline uses `executeWithEscalation()` for Run buttons
- [ ] ADR status updated to "Accepted" or "Implemented"

### How to Run
```
# Option 1: Use /implement-adr (handles team orchestration automatically)
/implement-adr docs/decisions/ADR-134-dispatch-escalation-pattern.md

# Option 2: Paste this prompt into Claude Code
# The agent will create the team, spawn teammates, and coordinate
```
