---
status: Implemented
date: 2026-03-17
deciders:
  - Gur Sannikov
related:
  - ADR-430
  - ADR-431
  - ADR-432
  - ADR-433
hub: dev
tags:
  - plugins
  - testing
  - verification
  - migration
superseded_by: null
---

# ADR-434: Plugin Distribution — Migration Verification

> Sub-ADR of ADR-430. Phase 4. Comprehensive parity testing — the quality gate.

## Context

ADRs 431-433 executed the migration: cleanup, framework update, plugin packaging. This sub-ADR is the final quality gate — it verifies the entire migration produces identical behavior to the pre-migration state. Every test category runs as a parallel team agent.

## Decision

Execute Phase 4 (integration testing, 7 test categories) from ADR-430. All categories are parallel.

**Prerequisite**: ADR-433 must be Implemented (all plugins packaged and validated).

## Implementation Prompt

**Team name**: `adr-434-verification`

### Gate 0: Pre-flight
Verify ADRs 431-433 are all Implemented. All plugins pass `claude plugin validate`. Marketplace installs cleanly.

### Full Parallel: 7 test categories
**Strategy**: PARALLEL via team agents

| Agent | Category | Tests |
|-------|----------|-------|
| `test-fresh` | Fresh Install (CLI only) | (1) Create clean user profile (temp HOME). (2) `claude plugin marketplace add ./augur-marketplace`. (3) `claude plugin install augur`. (4) Run `/onboard` — verify platform installs, MCP connects, vault created. (5) Verify `augur-system` + `augur-knowledge` installed. (6) Test `/ask "hello"`, `/search test`, `/commands`. (7) Verify NO Node.js required. (8) Clean up temp profile. |
| `test-full` | Fresh Install (full stack) | (1) Create clean profile. (2) Install all 8 plugins. (3) Run `/onboard --full`. (4) Dashboard: `npm run build` passes. (5) All hub pages render (mount-plugins found resources). (6) All auto-commands appear in `/commands`. (7) All MCP tools respond. (8) Clean up. |
| `test-migrate` | Existing User Migration | (1) Use current repo state. (2) Run `/onboard --migrate`. (3) Verify plugins installed match current hubs. (4) Personal skills (consulting, enterprise) preserved in `.claude/skills/`. (5) No duplicate skills in `/commands`. (6) Vault data untouched (`~/Vault/Augur/` unchanged). (7) RAG indices still valid. |
| `test-parity` | Skill Parity (per-plugin) | For each of the 8 plugins: (1) Install plugin. (2) For each skill in plugin: run slash command, verify response. (3) For skills with MCP tools: call each tool, verify response schema matches pre-migration baseline. (4) For skills with dashboard pages: verify page mounts at correct route. (5) For skills with API routes: hit each route, verify response. (6) Report any parity failures. |
| `test-sync` | Cross-Client Sync | (1) Install `augur-career` plugin. (2) Run `sync_agents --all`. (3) Verify `.gemini/skills/career/SKILL.md` created with `AUGUR-ADAPTED-COPY` marker. (4) Verify `.codex/prompts/career/SKILL.md` created (if codex adapter active). (5) Run `sync_agents --fix` — no orphan deletions. (6) Modify plugin skill, re-sync — freshness detected, adapted copies updated. |
| `test-adr` | ADR System | (1) `/adr status` shows dashboard from vault. (2) `/adr query 430` returns ADR-430 content. (3) `/adr write` creates new ADR in vault. (4) Simulate brainstorm: create `docs/superpowers/specs/test-design.md`. (5) `/adr plan` moves spec to vault, creates ADR. (6) Verify `docs/superpowers/specs/test-design.md` deleted (moved). (7) Browse ADR category shows all ADRs. (8) `/ask "what is ADR-430"` returns RAG result. (9) Clean up test ADR. |
| `test-rollback` | Rollback Verification | (1) Record current state (skill count, MCP tools, pages). (2) `claude plugin uninstall augur-career`. (3) Verify career skills gone from `/commands`. (4) Verify career MCP tools not registered. (5) Verify personal skills still work. (6) `claude plugin install augur-career`. (7) Verify career skills restored. (8) Full uninstall all plugins. (9) Restore `.claude/skills/` from git. (10) Verify system works exactly as pre-migration. |

### Gate 1: Test results
All 7 agents must report PASS. Any FAIL blocks completion.

**Failure protocol**: If an agent reports failures:
1. Categorize: is it a packaging issue (ADR-433), framework issue (ADR-432), or cleanup issue (ADR-431)?
2. Create a targeted fix in the responsible sub-ADR
3. Re-run only the failed test category after fix

### Gate 2: Performance baseline
After all functional tests pass, run performance checks:
```bash
# MCP tool discovery time
time augur mcp serve --health-check

# mount-plugins build time
time npm run mount-plugins

# RAG index time (full reindex)
time python3 -m sync_agents.rag_reindex --all

# Compare against pre-migration baselines (stored in vault)
```

No specific thresholds — just record baselines for future regression detection.

### Gate 3: CLAUDE.md update
Update CLAUDE.md to reflect:
- Plugin-based skill discovery
- Vault-based ADR storage
- New Browse source badges
- Updated slash command count
- ADR status count (now from vault)

### Completion Criteria
- [ ] Fresh install (CLI only) passes — zero Node.js required
- [ ] Fresh install (full) passes — dashboard builds, all pages render
- [ ] Existing user migration preserves all personal skills and vault data
- [ ] 100% skill parity — every slash command, MCP tool, and page works identically
- [ ] Cross-client sync discovers plugin masters, generates adapted copies
- [ ] ADR system works fully from vault (/adr query, write, plan, status)
- [ ] Rollback to pre-migration state succeeds cleanly
- [ ] Performance baselines recorded
- [ ] CLAUDE.md updated
- [ ] ADR-434 status → Implemented
- [ ] ADR-430 status → Implemented (master ADR)
