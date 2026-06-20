# Skill Taxonomy Alignment — Design Spec

**Date**: 2026-03-21
**ADR**: ADR-463
**Status**: Draft
**Source**: Gap analysis of Augur's 206 skills against Thariq Shihipar's "Lessons from Building Claude Code: How We Use Skills" (9-category taxonomy + structural best practices)

## Problem

Augur has 206 skills but three taxonomy categories are underserved (Library Reference, Data Fetching, Runbooks), 19 skills are stubs/duplicates, skills lack structural quality (no Gotchas sections, poor description triggers), stale documentation references the retired `augur.yaml` pattern, and there's no way to filter or classify skills by type.

## Goals

1. Net skill reduction (206 → ~197) while filling taxonomy gaps
2. Formal skill type system (`x-augur-type`) with enforced infrastructure contracts
3. Full classification of all skills with anomaly flagging
4. Structural quality upgrades (Gotchas, triggers, progressive disclosure) for top 15 skills
5. Usage instrumentation to enable data-driven skill improvement
6. Stale `augur.yaml` doc references fixed across all agent-facing files

## Non-Goals

- Dashboard pages for library-reference or runbook skills (they don't need UI)
- Merging the auto-test-* suite (10 skills, distinct layers, keep as-is)
- Merging the auto-skill-* pipeline (6 skills, sequential tiers, keep as-is)
- Restructuring knowledge retrieval (ask/search/knowledge — clarify boundaries only)

---

## Phase 0: Cleanup

### 0.1 Convert 9 Stub Skills to ADR Future Items

These skills have TODO-only scan() implementations returning 0 issues. Convert their intent to a "Future Capabilities" section in ADR-463, then delete the skill directories.

| Skill | Intent to Preserve |
|-------|-------------------|
| `auto-a11y` | ARIA/keyboard/contrast validation for dashboard |
| `auto-broken-assets` | Image/asset existence checks |
| `auto-circular-deps` | Circular dependency detection |
| `auto-empty-states` | Empty data graceful handling validation |
| `auto-env-check` | Environment variable validation |
| `auto-i18n` | Internationalization validation |
| `auto-onboarding` | First-run experience validation |
| `auto-perf-budget` | Page load time and bundle size monitoring |
| `auto-markers` | Broken — 13 sequential failed self-repair attempts |

### 0.2 Delete 8 Duplicate/Absorbed Skills

| Delete | Canonical Version |
|--------|------------------|
| `auto-debt` | `auto-tech-debt` |
| `auto-debt-scan` | `auto-tech-debt` (explicitly absorbed) |
| `documentation-sync` | `auto-docs` |
| `rollback-recovery` | `ops-rollback` |
| `test-heal` | `ops-self-heal-test` |
| `dev-retro` | `dev-improve` (identical content) |
| `fix-build` | `runbook-dashboard` (new, absorbs build diagnosis) |
| `reindex-rag` | `auto-rag-reindex` (stub, auto version is functional) |

### 0.3 Merge 2 Skills

| Delete | Merge Into | Action |
|--------|-----------|--------|
| `ops-daemon` | `daemon` | Absorb unique launchd management content into daemon |
| `file-bug` | `dev-improve` | Absorb TODO_ marker bug-filing into dev-improve |

### 0.4 Fix Stale `augur.yaml` Documentation

`augur.yaml` is fully retired (ADR-430, zero instances exist). All references must be updated to `x-augur-*` SKILL.md frontmatter.

| File | Lines | Fix |
|------|-------|-----|
| `docs/agent-topics/SKILLS.md` | 68, 82, 89, 133 | Rewrite skill creation steps: SKILL.md frontmatter replaces augur.yaml |
| `docs/agent-topics/ARCHITECTURE.md` | 132, 213, 215 | Update skill structure description |
| `docs/agent-topics/CONTEXT.md` | 98 | Update tool scoping reference |
| `docs/agent-topics/agent-rules.md` | 28, 43 | Sync with CLAUDE.md updates |
| `CLAUDE.md` Rule 2 | 33 | Change "augur.yaml" to "SKILL.md x-augur-* frontmatter" |
| `CLAUDE.md` Rule 16 | 48 | Remove augur.yaml from machine config examples |
| `config/system/skill-template.yaml` | 38, 75, 284 | Remove augur.yaml from scaffold, add x-augur-type |
| `config/system/adaptive_loops.yaml` | 2 | Update comment |
| Memory: `feedback_mcp-api-testing-misc.md` | 9 | Update augur.yaml reference to SKILL.md |
| Memory: `feedback_sync-mount-registry.md` | 41, 52, 54 | Update Plugin State section |
| Memory: `feedback_autoloop-regression-patterns.md` | 9, 11 | Update augur.yaml deletion context |

### 0.5 Update Registries

- Run `/reindex-project` to rebuild skill registry
- Update daemon loop configs that reference deleted skills
- Verify no CLAUDE.md slash commands reference deleted skills

**Phase 0 outcome**: 206 → 187 skills. All stale docs fixed.

---

## Phase 1: Skill Type Classification

### 1.1 Type Taxonomy

Every skill gets `x-augur-type` in SKILL.md frontmatter.

| Type | Description | Has UI? | Has MCP? | Has Scripts? | Daemon? |
|------|-------------|---------|----------|-------------|---------|
| `domain` | Full-stack feature with dashboard, data, API | Yes | Yes | Yes | No |
| `library-reference` | Teaches Claude library/framework gotchas | No | No | No | No |
| `runbook` | Structured diagnosis playbook (symptom → report) | No | No | Optional | No |
| `autoloop` | Daemon-managed scanning/hardening | No | No | Yes | Yes |
| `command` | CLI workflow, no persistent UI | No | Optional | Optional | No |
| `template` | Scaffolding for new skills/hubs | No | No | No | No |
| `meta` | Skills about skills / system orchestration | Optional | Optional | Optional | No |

### 1.2 Agent Behavior by Type

| Type | Loads as context? | Creates dashboard? | Registers MCP? | Daemon loop? |
|------|------------------|-------------------|----------------|-------------|
| `domain` | Yes | Yes | Yes | No |
| `library-reference` | Yes (passive, before coding) | Never | Never | Never |
| `runbook` | Yes (step-by-step protocol) | Never | Never | Never |
| `autoloop` | Yes (via ops_protocol) | Never | Never | Yes |
| `command` | Yes (workflow steps) | Never | Optional | Never |
| `template` | Yes (scaffolding recipe) | Never | Never | Never |
| `meta` | Yes | Optional | Optional | Never |

### 1.3 Type-Specific Infrastructure Contracts

| Type | Required | Forbidden |
|------|----------|-----------|
| `domain` | SKILL.md with x-augur-mcp-tools, x-augur-dashboard-pages | — |
| `library-reference` | SKILL.md with `## Gotchas` section | augur/api/, augur/dashboard/, scripts/*_ops.py |
| `runbook` | SKILL.md with `## Steps` section | augur/api/, augur/dashboard/ |
| `autoloop` | SKILL.md, scripts/*_ops.py with scan() | augur/dashboard/ |
| `command` | SKILL.md | — |
| `template` | SKILL.md | scripts/*_ops.py |
| `meta` | SKILL.md | — |

### 1.4 Classification Scan

Scan all ~187 remaining skills using this algorithm:

```
1. Read SKILL.md frontmatter + first 50 lines
2. Check directory structure:
   - Has augur/api/ or augur/dashboard/ → domain candidate
   - Has scripts/*_ops.py with scan() → autoloop candidate
   - Has x-augur-loop in frontmatter → autoloop confirmed
   - Name starts with auto- → autoloop candidate
   - Name ends with -template → template confirmed
3. Cross-reference with daemon loop configs
4. Assign x-augur-type based on strongest signal
5. Flag conflicts for user review
```

Expected distribution (approximate — exact counts determined by scan):

| Type | Estimated Count |
|------|----------------|
| `autoloop` | ~60 |
| `domain` | ~45 |
| `command` | ~35 |
| `meta` | ~20 |
| `library-reference` | 0 (new skills fill this) |
| `runbook` | 1 (debug-protocol) |
| `template` | ~4 |
| **Subtotal** | ~165 |

> Note: Estimates are illustrative. The remaining ~22 skills will be classified during the scan. Some skills may not fit cleanly into one type and will be flagged as anomalies for user review per section 1.5.

### 1.5 Anomaly Detection

Flag skills matching these patterns for user decision:

| Problem | Detection |
|---------|-----------|
| Type-straddler | Has dashboard pages AND ops_protocol scan() |
| Underpowered domain | Has x-augur-dashboard-pages but pages are empty/broken |
| Overpowered autoloop | auto-* with dashboard pages or MCP tools |
| Orphan command | Command skill with no slash command registration |
| Empty meta | Meta skill <100 lines, no scripts, no references |
| Duplicate trigger | Two skills with nearly identical description fields |

Output: classification report with clean assignments and flagged anomalies for user review.

### 1.6 Write Frontmatter

After user reviews flagged skills, write `x-augur-type` and `x-augur-tags` to every SKILL.md.

**Phase 1 outcome**: All 187 skills classified with `x-augur-type` + `x-augur-tags`.

---

## Phase 2: New Skills

### 2.1 Library Reference Skills (4)

All follow the same structure: SKILL.md with Gotchas + optional `references/` subdir.

**`nextjs-patterns`** (`x-augur-type: library-reference`, hub: studio)
- Trigger: "Use when editing files in apps/dashboard/, touching route.ts, page.tsx, layout.tsx, or server/client components"
- Gotchas sourced from: `feedback_nextjs-turbopack-dashboard.md` memory, recent build failures
- Content: App Router caching traps, Turbopack dev/prod divergence, server action boundaries, dynamic route pitfalls, named exports for API routes

**`shadcn-patterns`** (`x-augur-type: library-reference`, hub: studio)
- Trigger: "Use when creating/modifying UI components, adding dashboard blocks, form work"
- Content: Component nesting rules, theme extension, form + zod integration, DataTable patterns, correct imports

**`python-patterns`** (`x-augur-type: library-reference`, hub: studio)
- Trigger: "Use when writing Python scripts, MCP tools, CLI commands"
- Content: Click CLI gotchas, pydantic v2 patterns, pytest fixtures for MCP, `src.config.paths` usage rules, PYTHONPATH requirements

**`mcp-sdk-patterns`** (`x-augur-type: library-reference`, hub: studio)
- Trigger: "Use when authoring @mcp.tool functions, registering tools, handling parameters"
- Content: Tool naming conventions (snake_case), parameter validation, error response format, transformResponse contracts between Python and TypeScript

### 2.2 Data Query Skill (1)

**`data-query`** (`x-augur-type: command`, hub: brain)
- Trigger: "Use when querying vault data, analyzing logs, checking metrics, inspecting skill data files"
- Scripts: Query helpers for vault SQLite, JSON/YAML traversal, log parsing with grep/jq
- Content: Vault data locations, frontmatter query patterns, cross-skill data correlation

### 2.3 Runbook Skills (2)

**`runbook-dashboard`** (`x-augur-type: runbook`, hub: studio)
- Trigger: "Use when dashboard page is blank, API returns 500, block shows no data, MCP tool fails silently"
- Absorbs: `fix-build` scope (build + runtime diagnosis)
- Steps: Codifies CLAUDE.md Rule 17 wiring audit as executable protocol
  1. Grep every API route `toolName` against `@mcp.tool(name=...)` registrations
  2. Check `transformResponse` field names match MCP tool output
  3. Confirm no `fs`/`spawn`/`exec` bypasses in API routes
  4. Verify `gracefulFallback` isn't masking a failed MCP call
  5. Browser verify: open page, check console errors, confirm content renders
- Scripts: Diagnostic helpers for wiring grep, route validation

**`runbook-mcp`** (`x-augur-type: runbook`, hub: studio)
- Trigger: "Use when MCP server won't start, tools don't appear in listing, handshake fails"
- Steps:
  1. Check MCP server process running
  2. Verify PYTHONPATH includes project root and src/mcp
  3. Test `list_tools` response
  4. Validate tool names match API route expectations
  5. Check parameter schema compliance
  6. Verify response shape contracts

### 2.4 On-Demand Hook Skills (2)

> **Implementation note**: These skills use SKILL.md instructions to modify Claude's behavior within the current session — they do NOT depend on dynamic hook registration infrastructure. When `/careful` is invoked, the SKILL.md content is loaded into context and instructs Claude to self-enforce the blocking rules (refuse destructive commands, ask for confirmation). When `/freeze <dir>` is invoked, the SKILL.md instructs Claude to refuse edits outside the boundary. This is a prompt-based approach, not a system hook. If a PreToolUse hook API becomes available in the future, these skills can be upgraded to use it.

**`careful`** (`x-augur-type: command`, hub: command)
- Trigger: "Use when user invokes /careful"
- Loaded into context, instructs Claude to block: `rm -rf`, `git reset --hard`, `git push --force`, `DROP TABLE`, `kill-augur`
- Shows blocked command, requires explicit confirmation before proceeding
- Active for duration of session (skill stays in context)

**`freeze`** (`x-augur-type: command`, hub: command)
- Trigger: "Use when user invokes /freeze <dir>"
- Loaded into context, instructs Claude to refuse Write/Edit outside specified directory
- `/freeze off` to deactivate (clears the instruction from context)

**Phase 2 outcome**: 187 → 196 skills (+9 new).

---

## Phase 3: Structural Upgrades

Upgrade top 15 most complex skills.

### Target Skills

career, advisor, apple, knowledge, validator, frontend, daemon, dev-build, dev-debug, evolve, attention, content, google-workspace, coach, dev-merge

### Per-Skill Checklist

1. **Add `## Gotchas` section** — Minimum 3 gotchas from: memory files, git blame, auto-self-heal logs, CLAUDE.md rules
2. **Rewrite description as trigger** — "Use when..." format
3. **Add `x-augur-type`** — Already done in Phase 1
4. **Add `x-augur-tags`** — 2-5 filterable tags
5. **Progressive disclosure** — For skills >200 lines, split detailed content into `references/` subdir

### Gotchas Sourcing

| Source | Method |
|--------|--------|
| Memory files | Extract patterns from `feedback_*.md` |
| Git history | `git log --grep="fix" -- .claude/skills/{skill}/` |
| Auto-self-heal logs | `~/Library/Logs/Augur/` recurring errors |
| CLAUDE.md rules | Rules referencing specific skill behaviors |

**Phase 3 outcome**: 15 skills upgraded with Gotchas, trigger descriptions, progressive disclosure.

---

## Phase 4: Usage Instrumentation

### 4.1 PreToolUse Hook

Add to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": { "tool_name": "Skill" },
        "command": "scripts/hooks/skill-usage-tracker.sh"
      }
    ]
  }
}
```

Log format (append-only JSONL at `~/Library/Logs/Augur/skill-usage.jsonl`):

```jsonl
{"ts":"2026-03-21T14:30:00Z","skill":"career","session":"abc123"}
```

### 4.2 `auto-skill-usage` Autoloop

New skill (`x-augur-type: autoloop`, hub: adaptive) analyzing the usage log:

| Metric | Insight |
|--------|---------|
| Invocation count per skill | Popular skills (upgrade priority) |
| Skills with 0 invocations in 30 days | Undertriggered (bad description or unused) |
| Skills that fire but user switches away | False positive triggers |
| Type distribution | Are library-reference skills loading? |

Runs in `skill-standards` loop at tier 5.

**Phase 4 outcome**: 196 → 197 skills (+1 auto-skill-usage).

---

## Phase 5: Standards Enforcement

Update existing auto-skills to enforce the type system permanently.

| Auto-Skill | Update |
|------------|--------|
| `auto-skill-md` | Require `x-augur-type` in frontmatter. Fail if missing. Auto-suggest type. |
| `auto-skill-structure` | Validate directory structure matches declared type (forbidden files per type contract). Flag lingering `augur.yaml` files as retired artifacts. |
| `auto-skill-quality` | Score per type: library-reference on gotchas depth, autoloop on ops_protocol, domain on dashboard completeness |
| `auto-skill-enhance` | Format generated descriptions as triggers ("Use when..."), infer `x-augur-tags` |
| `auto-loop-advisor` | Auto-assign `x-augur-type: autoloop` when suggesting new auto-commands |
| `evolve` | Prompt for type during scaffolding, enforce correct skeleton per type |
| `config/system/skill-template.yaml` | Remove augur.yaml from scaffold, add x-augur-type to template |

**Phase 5 outcome**: Type system permanently enforced by CI/nightly loops.

---

## Phase 6: Browse Page Filtering

Update the dashboard skill browse page with:

- **Type filter dropdown**: Domain / Library Reference / Runbook / Autoloop / Command / Template / Meta
- **Tag filter**: Freeform tags from `x-augur-tags`
- **Hub filter**: Existing hub grouping (brain, life, career, command, studio, adaptive)

**Phase 6 outcome**: Users can filter skills by type and tag in the dashboard.

---

## Final Scorecard

| Metric | Before | After |
|--------|--------|-------|
| Total skills | 206 | 197 |
| Stub/duplicate skills | 19 | 0 |
| Skills with `x-augur-type` | 0 | 197 |
| Skills with Gotchas section | 0 | 22 (7 new + 15 upgraded) |
| Library reference skills | 0 | 4 |
| Runbook skills | 1 | 3 |
| Stale augur.yaml doc references | 20+ | 0 |
| Skill usage tracking | None | PreToolUse hook + analytics |
| Browse page filtering | Hub only | Hub + Type + Tags |

## Dependencies

- ADR-430 (augur.yaml retirement — already implemented)
- ADR-426 (client-native skill mastering — already implemented)
- CLAUDE.md Rule 17 (wiring audit protocol — referenced by runbook-dashboard)

## Risks

- Classification scan may surface more anomalies than expected — budget time for user review
- Gotchas sections require mining conversation history — quality depends on available failure data
- PreToolUse hook adds latency to every Skill tool call — keep the shell script fast (<50ms)
