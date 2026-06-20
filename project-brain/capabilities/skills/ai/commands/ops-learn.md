---
description: Extract learnings from current thread and persist to memory + docs
visibility: ops
x-augur-export-command: false
---

# /dev-learn - Capture Learning from Thread

Extract learnings from the current conversation and persist them. Feeds the two-layer memory pipeline (ADR-028) and optionally updates documentation.

## Usage

```
/dev-learn              → Capture learnings from current thread (default)
/dev-learn refactor     → Analyze recent learnings and suggest priority infrastructure refactors
/dev-learn execute      → Capture learnings AND execute actions (TODO markers, fixes, rule updates)
```

If the `refactor` flag is provided, skip the normal capture flow and jump directly to the [Refactor Analysis](#refactor-analysis) section below.

If the `execute` flag is provided, run the normal capture flow (Steps 1-5) first, then continue to the [Execute Actions](#execute-actions) section below.

## Step 1: Analyze the Thread

Scan the conversation and identify ALL learnings. A single session often produces multiple learnings of different types.

**Learning Types:**

| Type | Trigger | Example |
|------|---------|---------|
| **Bug/Fix** | Fixed a bug, solved an error | "Layout renders twice because both layout.tsx and page.tsx have `<h1>`" |
| **Decision** | Made an architectural or design choice | "Chose ripgrep over SQLite for search" |
| **Concept** | Learned something new (tool, API, pattern) | "MCP tools need explicit registration in __init__.py" |
| **Preference** | Discovered a workflow or style preference | "User prefers tables over prose for comparisons" |
| **Pattern** | Noticed a recurring behavior or anti-pattern | "Format mismatch between curator.py and memory_sync.py" |

For each learning found, determine its type.

## Step 2: Write to Daily Log (ALWAYS)

Every learning gets appended to today's daily log. Use the exact format `memory_sync.py` expects:

**File**: `get_memory_dir()/daily/YYYY-MM-DD.md`

Create the file with `# Session Log: YYYY-MM-DD` header if it doesn't exist.

**Format by type:**

```markdown
## Decision: [concise one-line summary of what was decided and why]

## Pattern: [concise one-line description of the observed pattern]

## Preference: [concise one-line description of the preference and its value]
```

For Bug/Fix and Concept types, use `## Decision:` format (they represent a decision about how to handle something).

**CRITICAL**: Each entry MUST be a `## Type: <single line>` — this is the format the curation regex parses. Multi-line entries under `##` headers will NOT be extracted.

## Step 3: Write to Documentation (CONDITIONAL)

Only Bug/Fix and Critical Rule learnings need documentation beyond the daily log.

| Learning Type | Also Write To | Format |
|---------------|---------------|--------|
| **Bug/Fix (UI)** | `skills/dashboard/references/design-standards.md` | Anti-pattern block (see below) |
| **Bug/Fix (Critical)** | `docs/agent-topics/agent-rules.md` | Rule with rationale |
| **Bug/Fix (Skill)** | `plugins/{bundle}/skills/{skill}/SKILL.md` → Anti-patterns section | Anti-pattern block |
| **Bug/Fix (Backend)** | `docs/architecture-*.md` or `docs/developer-guide.md` | Solution block |
| **Decision** | Daily log only (curated to MEMORY.md by `memory_sync.py`) | — |
| **Concept** | Daily log only | — |
| **Preference** | Daily log only | — |
| **Pattern** | Daily log only | — |

**Anti-pattern block format** (for docs):

```markdown
### [Short Title]

**Issue**: [What went wrong]
**Root Cause**: [Why it happened]
**Solution**: [How to do it correctly]

**Anti-Pattern**:
// code showing the wrong way

**Correct**:
// code showing the right way
```

## Step 4: Sync to All IDEs

// turbo
```bash
PYTHONPATH=project-brain/capabilities python3 -m skills.ai.scripts.sync_agents sync all
```

Only needed if Step 3 modified `docs/agent-topics/agent-rules.md` (which feeds CLAUDE.md generation). Skip if only daily log was written.

**Note (ADR-057):** `/dev-learn` feeds all agents via `/ops-memory`. After capturing learnings, run `python3 .github/scripts/memory_sync.py --sync` to distribute curated memory to Claude Code, Kimi, Codex, Cursor, and Copilot.

## Step 5: Report

Report what was captured:

```
Learning captured:

Type: Decision
Entry: "Chose post-commit hook over pre-push for memory logging — fires on every commit, simpler"
Written to: get_memory_dir()/daily/2026-02-04.md
Curate with: python3 .github/scripts/memory_sync.py --sync
```

If multiple learnings were captured, list them all.

---

## Examples

### Example 1: Bug Fix Session

**Thread**: Fixed duplicate headers on /health page

**Agent captures**:
- Type: Bug/Fix
- Daily log: `## Decision: Hub pages must only render title in layout.tsx, not page.tsx — prevents duplicate headers`
- Also writes anti-pattern block to `design-standards.md`
- Runs `PYTHONPATH=project-brain/capabilities python -m skills.ai.scripts.sync_agents sync all` (modified docs)

### Example 2: Architecture Discussion

**Thread**: Debated SQLite vs ripgrep for search, chose ripgrep

**Agent captures**:
- Type: Decision
- Daily log: `## Decision: Use ripgrep over SQLite for knowledge search — simpler, no DB overhead, fits local-first philosophy (ADR-004)`
- No doc update needed (memory_sync.py will curate to MEMORY.md)

### Example 3: Mixed Session

**Thread**: Fixed a build error, learned about Next.js App Router caching, decided to use Tailwind `cn()` helper

**Agent captures 3 learnings**:
1. `## Decision: Next.js App Router caches route handlers by default — must add export const dynamic = 'force-dynamic' for API routes`
2. `## Pattern: Build errors from plugin mounting often caused by stale TypeScript configs in auto-generated files`
3. `## Decision: Use cn() utility from shadcn for conditional Tailwind classes instead of template literals`

---

## Execute Actions

Triggered by `/dev-learn execute`. Runs the normal capture flow (Steps 1-5) first, then translates each captured learning into a concrete action.

### E1. Classify Actionability

For each learning captured in Steps 1-2, determine what action to take:

| Learning Type | Action | Safety |
|---|---|---|
| **Bug/Fix (simple, code visible in thread)** | Apply the code fix directly | Ask user to confirm |
| **Bug/Fix (complex or external)** | Create `TODO_BUG` marker at the relevant code location | Auto-safe |
| **Pattern (anti-pattern in code)** | Create `TODO_CLEANUP` markers in files exhibiting the pattern | Auto-safe |
| **Pattern (process/workflow)** | Add rule to agent-rules.md or relevant topic doc | Auto-safe |
| **Decision (new rule)** | Add to agent-rules.md or relevant topic doc | Auto-safe |
| **Decision (architectural, significant)** | Draft ADR via `/adr new "<title>"` | Ask user to confirm |
| **Preference** | Update relevant config or topic doc | Auto-safe |
| **Concept** | No action — knowledge capture is sufficient | Skip |

**ADR-249 rule**: when the same infra/setup failure is observed repeatedly, normalize it to a stable incident fingerprint first. Do not create a new TODO marker for every wording variant of the same failure.

### E2. Execute Safe Actions

For each learning classified as "auto-safe", execute immediately:
1. **TODO markers**: Add `TODO_CLEANUP`, `TODO_BUG`, or `TODO_OUTDATED` comment at the relevant code location with a one-line description
2. **Rule updates**: Append the rule to `docs/agent-topics/agent-rules.md` or the relevant topic doc in `docs/agent-topics/`
3. **Config updates**: Update the relevant config file for preferences

**Promotion rules for recurring incidents**:
- Deduplicate by incident fingerprint and owner path before adding a marker
- Prefer the executable owner file that can prevent recurrence, not the transient caller that merely surfaced the failure
- Use `TODO_CLEANUP` for structural bootstrap debt, `TODO_BUG(integration/high)` for unresolved user-visible failures, and `TODO_OUTDATED` only when the real issue is stale operational guidance

### E3. Propose Risky Actions

For actions requiring user confirmation (code fixes, ADR drafts):
1. Show the proposed change (diff or summary)
2. Wait for approval
3. Apply if approved, skip if declined

### E4. Sync

Run syncs as needed:
```bash
# If agent-rules.md or topic docs were modified:
PYTHONPATH=project-brain/capabilities python3 -m skills.ai.scripts.sync_agents sync all

# Always distribute updated memory:
python3 .github/scripts/memory_sync.py --sync
```

### E5. Report Execution

Summarize what was actioned:

```
Execute complete (N learnings → M actions):

1. [Bug/Fix] Disabled watchdog for Claude Desktop
   → Code fix applied to src/mcp/server.py:1069 ✓

2. [Pattern] PPID orphan detection unreliable for Claude Desktop
   → TODO_CLEANUP added to instance_lock.py:524 ✓

3. [Decision] Rejected Python→Node.js MCP migration
   → No action (knowledge only)

Synced to all IDEs ✓
```

---

## Refactor Analysis

Triggered by `/dev-learn refactor`. Reads recent learnings, identifies recurring failure patterns, and produces a prioritized refactoring backlog.

### R1. Load Recent Learnings

Read the last 7 daily logs from `get_memory_dir()/daily/`:

```bash
ls -t get_memory_dir()/daily/*.md | head -7
```

Read each file. Extract all `## Decision:`, `## Pattern:`, and `## Preference:` entries into a flat list. Each entry is one line of text.

Also read `MEMORY.md` (the curated memory) for broader context on past decisions.

### R2. Classify into Infrastructure Areas

Group each learning entry into one of these infrastructure areas based on its content:

| Area | Signal Words | Example |
|------|-------------|---------|
| **mount-system** | mount-plugins, dashboard.yaml, hub.id, symlink, copyDir, src/app/ | "Two skills with same hub.id causes silent overwrite" |
| **path-resolution** | stale path, hardcoded, vault/state paths, get_project_root | "Stale path scanner should exclude non-executable data" |
| **self-heal** | self-heal, LLM retry, backoff, escalation, daemon | "Guard against None last_exc in LLM retry" |
| **build-cache** | .next cache, Turbopack, ENOENT, HMR, manifest | "Clear corrupted .next cache causing ENOENT" |
| **plugin-lifecycle** | plugin, bundle, PLUGIN_BUNDLES, skill discovery, dashboard.yaml | "Skills with dashboard/ but no dashboard.yaml won't mount" |
| **agent-config** | sync_agents, IDE configs, CLAUDE.md, workflow, slash command | "Workflow visibility reclassified to 5 categories" |
| **test-stability** | test failure, flaky, jest, playwright, mock | "Wizard flow test must self-manage dashboard server" |
| **process-management** | daemon, HMR, SIGTERM, detach, child process, port | "Detached:true insufficient — cleanup handlers still kill child" |
| **refactor-safety** | bulk refactor, find-replace, word-boundary, rename | "Bulk find-replace must use word-boundary matching" |
| **other** | Anything that doesn't fit above | — |

An entry can belong to multiple areas if it spans concerns.

### R3. Score and Prioritize

For each area that has entries, compute a priority score:

```
priority = (fix_count × 3) + (pattern_count × 2) + (decision_count × 1)
```

Where:
- **fix_count** = entries that describe fixing a bug or error (look for `fix(`, `clear corrupted`, `guard against`, `resolve`, `prevent`)
- **pattern_count** = entries typed as `## Pattern:` (recurring anti-patterns)
- **decision_count** = other `## Decision:` entries (one-time choices, less urgent)

Higher score = more time spent firefighting in this area = higher refactoring priority.

### R4. Generate Refactoring Recommendations

For each area (sorted by priority score, descending), produce a refactoring recommendation:

1. **Read the relevant code** for the top 3 areas — don't just guess, actually open the key files and identify the specific weakness
2. For each area, write:
   - **Area**: name
   - **Score**: N (X fixes, Y patterns, Z decisions)
   - **Recurring issue**: one-sentence summary of what keeps going wrong
   - **Root cause**: why the infrastructure allows this to recur
   - **Proposed refactor**: specific, actionable change (file path, function, approach)
   - **Effort**: S/M/L
   - **Impact**: how many future issues this would prevent

### R5. Output Report

Print the report as a prioritized table:

```
Refactor Priority Report (last 7 days, N total learnings)

| # | Area | Score | Recurring Issue | Proposed Refactor | Effort |
|---|------|-------|-----------------|-------------------|--------|
| 1 | ...  | ...   | ...             | ...               | ...    |
| 2 | ...  | ...   | ...             | ...               | ...    |
| 3 | ...  | ...   | ...             | ...               | ...    |

Top recommendation: [1-sentence summary of the highest-impact refactor]
```

Then ask: "Want me to create an ADR or TODO markers for any of these?"

### R6. Save Report (optional)

If the user approves, save the report to `get_memory_dir()/refactor-reports/YYYY-MM-DD.md` for tracking over time.
