---
status: Implemented
date: 2026-03-21
deciders:
  - Gur Sannikov
related:
  - ADR-426
hub: brain
tags:
  - skills
  - quality
  - context-engineering
superseded_by: null
---

# ADR-463: Skill Taxonomy Alignment

## Context

Thariq Shihipar (Anthropic, Claude Code team lead) published "Lessons from Building Claude Code: How We Use Skills" documenting 9 skill categories that recur across Anthropic's hundreds of internal skills, along with structural best practices for skill quality. A gap analysis of Augur's 139 skills against this taxonomy revealed:

**Category gaps** — 3 of 9 categories are underserved:

| Category | Gap Level | Issue |
|----------|-----------|-------|
| Library & API Reference | Moderate | No skills teaching Claude gotchas for key dependencies (Next.js, ShadCN, Python libs) |
| Data Fetching & Analysis | Significant | No skills connecting to data/monitoring infrastructure, no query patterns |
| Runbooks | Moderate | `dev-debug` exists but no structured symptom-to-report investigation playbooks |

**Structural gaps** — Skills don't follow Anthropic's recommended skill folder patterns:

| Practice | Current State |
|----------|---------------|
| Gotchas sections | Missing from most skills |
| Progressive disclosure (`references/`, `scripts/`, `examples/` subdirs) | Skills are mostly single SKILL.md files |
| Description field as trigger | Quality varies, many are summaries not triggers |
| Per-skill scripts/helpers | Automation centralized in `src/`, not per-skill |
| On-demand hooks | Not systematically used |
| Skill usage tracking | No PreToolUse hook instrumentation |

The existing 139 skills are strong in verification (15+ auto-test-* skills), code quality (6 review/lint skills), infrastructure operations, CI/CD, and scaffolding. The gap is not quantity but taxonomy coverage and per-skill structural quality.

## Decision

### Part 1: Fill Category Gaps

Create skills for the 3 underserved categories:

**Library & API Reference** (new skills):
- `nextjs-patterns` — Next.js App Router gotchas, server/client boundaries, caching, Turbopack issues specific to the Augur dashboard
- `shadcn-patterns` — ShadCN component usage patterns, composition, theming, form integration
- `python-patterns` — Python library gotchas for the automation stack (click, pydantic, pytest patterns)
- `mcp-sdk-patterns` — MCP tool authoring gotchas, parameter validation, error handling patterns

**Data Fetching & Analysis** (new skills):
- `data-query` — Patterns for querying SQLite (vault), JSON data files, and log analysis across Augur's data layer

**Runbooks** (new skills):
- `runbook-dashboard` — Symptom-to-diagnosis playbook for common dashboard failures (blank pages, API 500s, MCP tool failures) using the wiring audit protocol from CLAUDE.md rule 17
- `runbook-mcp` — MCP server failures, tool registration issues, handshake problems

### Part 2: Structural Quality Upgrade

Upgrade the top 15 most-used skills with Anthropic-recommended structure:

1. **Add Gotchas sections** — Document Claude's known failure points per skill, sourced from conversation history and auto-self-heal logs
2. **Progressive disclosure** — For skills with >200 lines, split into `SKILL.md` (overview + gotchas) with `references/` subdir for detailed API docs, examples, and templates
3. **Description field audit** — Rewrite descriptions as trigger conditions ("Use when...") not summaries ("This skill does...")
4. **Per-skill scripts** — Where skills currently shell out to centralized Python, extract the relevant helper into the skill's own `scripts/` dir
5. **On-demand hooks** — Create 2-3 session hooks following the `/careful` and `/freeze` pattern (e.g., `/strict` for enforcing lint on every file save)

### Part 3: Skill Usage Instrumentation

Add a PreToolUse hook that logs skill invocations to `~/Library/Logs/Augur/skill-usage.jsonl`, enabling:
- Identification of undertriggered skills (description field needs improvement)
- Popular skills (prioritize for quality upgrades)
- Skills that fire but shouldn't (false positive triggers)

## Consequences

### Positive

- Claude can correctly use Next.js, ShadCN, and Python libraries without repeating known mistakes
- Dashboard debugging follows a structured runbook instead of ad-hoc investigation
- Skills with gotchas sections reduce repeated failures, saving tokens and time
- Progressive disclosure reduces context window pressure for complex skills
- Usage data enables evidence-based skill improvement

### Negative

- ~10 new skills increase the skill registry, adding to discovery surface
- Structural upgrades to 15 skills require reading conversation history to extract actual gotchas (not synthetic ones)
- PreToolUse hook adds small latency to every tool call

### Neutral

- Existing skills in well-covered categories (verification, code quality, CI/CD) remain unchanged
- The adaptive engine's auto-skill-quality loop can incorporate the new structural requirements

## Alternatives Considered

### Alternative 1: Comprehensive Skill Rewrite

Restructure all 139 skills to match the taxonomy. Rejected because the existing verification and code quality skills are already effective — the gap is in specific categories, not systemic quality.

### Alternative 2: Merge into Fewer Skills

Consolidate related skills (e.g., merge all auto-test-* into one). Rejected because granular skills give Claude better trigger precision and reduce context loaded per invocation.

### Alternative 3: External Skill Marketplace Only

Install community skills for the gaps instead of building custom ones. Rejected because the highest-value skills (library gotchas, runbooks) are project-specific — generic community skills won't know Augur's dashboard patterns or MCP wiring conventions.

## References

- [Thariq's thread on X](https://x.com/trq212/status/2033949937936085378)
- [Full article on LinkedIn](https://www.linkedin.com/pulse/lessons-from-building-claude-code-how-we-use-skills-thariq-shihipar-iclmc/)
- ADR-426: Claude Code-mastered skills
- CLAUDE.md rules 5 (no workarounds), 17 (wiring audit)

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

**Team name**: `adr-463-skill-taxonomy`

### Phase 1: Library & API Reference Skills
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | skill-author | medium | Create `nextjs-patterns` skill with App Router gotchas, Turbopack issues, server/client boundaries. Source gotchas from `feedback_nextjs-turbopack-dashboard.md` memory and recent build failures | `.claude/skills/nextjs-patterns/SKILL.md` |
| 1.2 | skill-author | medium | Create `shadcn-patterns` skill with component composition, theming, form patterns. Source from dashboard component usage | `.claude/skills/shadcn-patterns/SKILL.md` |
| 1.3 | skill-author | medium | Create `python-patterns` skill with click CLI, pydantic, pytest gotchas from the automation stack | `.claude/skills/python-patterns/SKILL.md` |
| 1.4 | skill-author | medium | Create `mcp-sdk-patterns` skill with tool authoring patterns, parameter validation, error handling | `.claude/skills/mcp-sdk-patterns/SKILL.md` |

### Phase 2: Data & Runbook Skills
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | skill-author | medium | Create `data-query` skill for SQLite vault queries, JSON data analysis, log parsing | `.claude/skills/data-query/SKILL.md` |
| 2.2 | skill-author | high | Create `runbook-dashboard` skill codifying CLAUDE.md rule 17 wiring audit as a structured symptom-to-report flow | `.claude/skills/runbook-dashboard/SKILL.md` |
| 2.3 | skill-author | medium | Create `runbook-mcp` skill for MCP server failure diagnosis | `.claude/skills/runbook-mcp/SKILL.md` |

### Phase 3: Structural Quality Upgrades
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | analyst | medium | Identify top 15 most-used skills from conversation patterns and auto-command frequency. Produce ranked list | `docs/plans/adr-463-top-skills.md` |
| 3.2 | skill-author | high | For each of the top 15: add Gotchas section, rewrite description as trigger, add progressive disclosure where >200 lines | `.claude/skills/*/SKILL.md` |
| 3.3 | skill-author | medium | Create 2-3 on-demand hook skills (`/strict`, `/careful`) following Thariq's pattern | `.claude/skills/strict/SKILL.md`, `.claude/skills/careful/SKILL.md` |

### Phase 4: Usage Instrumentation
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | developer | medium | Create PreToolUse hook that logs skill invocations to `~/Library/Logs/Augur/skill-usage.jsonl` | `config/hooks/skill-usage-tracker.sh` |
| 4.2 | developer | low | Add `/auto-skill-usage` adaptive command that analyzes the log and reports undertriggered/overtriggered skills | `.claude/skills/auto-skill-usage/SKILL.md` |

### Completion Criteria
- [x] All 7 new skills created with SKILL.md, description-as-trigger, and Gotchas section
- [x] Top 15 skills upgraded with Gotchas and progressive disclosure
- [x] PreToolUse hook installed and logging
- [x] `auto-skill-usage` command operational
- [x] ADR status updated to Implemented

## Implementation Summary

Implemented 2026-03-21 on branch `feature/adr-463-skill-taxonomy-alignment`.

| Metric | Before | After |
|--------|--------|-------|
| Total skills | 203 | 192 |
| Skills with x-augur-type | 0 | 193 |
| Skills with Gotchas section | 0 | 21 |
| Library reference skills | 0 | 4 |
| Runbook skills | 0 | 3 |
| Stale augur.yaml doc references | 20+ | 0 |
| Skill usage tracking | None | PreToolUse hook + auto-skill-usage |
| Browse page filtering | Hub only | Hub + Type + Tags |

## Future Capabilities (Deferred from Stub Skills)

These capabilities were tracked as placeholder skills with no implementation. They are preserved here for future consideration.

| Capability | Former Skill | Description |
|-----------|-------------|-------------|
| Accessibility validation | auto-a11y | ARIA roles, keyboard navigation, contrast checks |
| Asset existence checks | auto-broken-assets | Verify image/asset references resolve |
| Circular dependency detection | auto-circular-deps | Detect circular imports in Python/TypeScript |
| Empty state validation | auto-empty-states | Verify pages handle empty data gracefully |
| Environment variable validation | auto-env-check | Verify required env vars are set |
| Internationalization | auto-i18n | i18n string extraction and validation |
| Onboarding validation | auto-onboarding | First-run experience completeness |
| Performance budgets | auto-perf-budget | Page load time and bundle size limits |
| TODO marker scanning | auto-markers | Replaced by auto-fix and auto-tidy |

## Future Work: Duplicate Skill Merges

The classification scan identified 13 skills with overlapping descriptions that should be merged in a future pass:

| Keep | Merge Into It | Reason |
|------|--------------|--------|
| sync-agents | auto-agent-sync | Auto is daemon version |
| auto-tech-debt | tech-debt-triage | Triage is manual version |
| auto-tidy | review-markers | Overlapping scope |
| dev-learn | learn, ops-learn | Adapted copies |
| dev-loops | ops-loops | Adapted copy |
| nightly | test-nightly | Adapted copy |
