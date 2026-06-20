---
status: Implemented
date: '2026-03-06'
deciders:
- Gur Sannikov
related:
- ADR-200 (Adaptive Loops)
- ADR-251 (Command Registry)
- ADR-252 (Commands to Skills)
hub: null
tags:
- test
- vertical
- decomposition
superseded_by: null
---

# ADR-255: Test Vertical Decomposition

## Context

The test infrastructure is monolithic. Three standalone commands (`/test-nightly`, `/test-ui`, `/client-test`) run as indivisible blocks with no granular loop integration:

- `/test-nightly` runs a 7-step pipeline (pytest, jest, lint, security, build, metrics, context audit) as one monolith — a single failure blocks visibility into other steps
- `/test-ui` is a standalone browser-based QA command outside the auto-loop system
- `/client-test` is a standalone CLI agent E2E test outside the auto-loop system
- Only `auto-test-coverage` (Jest coverage) participates in the adaptive loop engine

This prevents: independent budget/trust control per test concern, hub-scoped testing for daily development, granular failure tracking in the adaptive engine journal, and nightly auto-loop execution with scan/fix protocol.

The TEST visibility group contains only 2 user-facing commands and doesn't justify its own group when DEV already exists.

## Decision

### 1. New `testing` Loop

Add a dedicated loop to `config/system/adaptive_loops.yaml`:

```yaml
testing:
  budget: 12
  budget_growth_rate: 2
```

Separate from `code-quality` (which handles lint/coverage) to give test concerns independent budget control.

### 2. Seven Auto-Loop Verticals

Each vertical is a self-contained skill in `plugins/dev/skills/auto-test-*` implementing the OpsCommand scan/fix protocol (`src/lib/ops_protocol.py`).

| Tier | Skill | Scan | Fix |
|------|-------|------|-----|
| 0 | `auto-test-build` | `npm run build` | Report only |
| 0 | `auto-test-mcp` | MCP handshake + tool listing (no LLM) | Report unreachable |
| 1 | `auto-test-pytest` | `pytest` with hub filtering | Report failures |
| 1 | `auto-test-dashboard` | `npm test` with hub filtering | Report failures |
| 2 | `auto-test-pages` | HTTP GET page routes, check 200s | Flag broken routes |
| 2 | `auto-test-api` | HTTP GET API routes, validate responses | Flag broken endpoints |
| 3 | `auto-test-mcp-commands` | Categorized tool invocation | Flag broken tools |

### 3. MCP Command Testing Categories

`auto-test-mcp-commands` classifies tools by name prefix:
- **Read-safe** (get-*, list-*, search-*, check-*, find-*): Full invocation with minimal args, validate response
- **Mutating** (create-*, delete-*, update-*, run-*, add-*, set-*, toggle-*, publish-*, send-*): Schema-only validation, no side effects

### 4. Hub Scoping

Each vertical accepts an optional `hub` parameter:
- `auto-test-pytest` filters to `plugins/{hub}/skills/*/tests/`
- `auto-test-dashboard` filters jest via `--testPathPattern {hub}`
- `auto-test-pages` filters routes under `/{hub}/*`
- `auto-test-api` filters routes under `/api/{hub}/*`
- `auto-test-mcp-commands` filters tools from `plugins/{hub}/skills/*/augur.yaml`
- `auto-test-build` and `auto-test-mcp` are not hub-scoped (foundational)

### 5. Unified `/dev-test` Command

```
/dev-test                    # fast: tiers 0-1, whole project
/dev-test career             # fast: tiers 0-1, scoped to career hub
/dev-test --full             # all tiers 0-3, whole project
/dev-test career --full      # all tiers 0-3, scoped to career hub
```

The orchestrator imports scan modules directly from auto-test-* skills — single source of truth shared with the nightly auto-loop.

### 6. Retire TEST Group

- `/test-nightly` replaced by nightly auto-loop trigger of all 7 verticals
- `/test-ui` absorbed into `auto-test-pages`
- `/client-test` absorbed into `auto-test-mcp` + `auto-test-mcp-commands`
- TEST visibility group removed; `/dev-test` joins DEV group

### 7. File Structure

```
plugins/dev/skills/dev-test/               # /dev-test orchestrator
  SKILL.md, augur.yaml, scripts/test_orchestrator.py

plugins/dev/skills/auto-test-build/        # tier 0
plugins/dev/skills/auto-test-mcp/          # tier 0
plugins/dev/skills/auto-test-pytest/       # tier 1
plugins/dev/skills/auto-test-dashboard/    # tier 1
plugins/dev/skills/auto-test-pages/        # tier 2
plugins/dev/skills/auto-test-api/          # tier 2
plugins/dev/skills/auto-test-mcp-commands/ # tier 3
```

Each: `SKILL.md` (x-augur-visibility: auto, x-augur-loop), `augur.yaml`, `scripts/*_ops.py`, `tests/test_*_ops.py`

## Consequences

### Positive

- Each test concern has independent trust gating, budget control, and journal tracking
- Hub-scoped testing enables fast daily feedback (`/dev-test career` ~2min)
- Nightly daemon runs all 7 verticals automatically with exponential backoff on failures
- MCP command testing catches broken tools without manual invocation
- Single `/dev-test` entry point replaces 3 separate commands
- Categorized MCP testing prevents side effects from mutating tools at 3am

### Negative

- 7 new skill directories (more files to maintain)
- Tier 2-3 verticals require dev server running (pages/API route checks hit localhost:3000)
- MCP command classification by prefix is heuristic — new naming conventions need prefix list updates

### Neutral

- `auto-test-coverage` remains in `code-quality` loop (different concern: coverage thresholds vs test execution)
- Legacy test skill directories (`test-ui`, `test-client`) kept but hidden (visibility: hidden)

## Implementation Order

### Phase 1: Infrastructure
1. Add `testing` loop to `adaptive_loops.yaml`
2. Create hub filter utility in `plugins/dev/skills/dev-test/scripts/hub_filter.py`

### Phase 2: Tier 0 Verticals
3. `auto-test-build` (build verification)
4. `auto-test-mcp` (MCP handshake)

### Phase 3: Tier 1 Verticals
5. `auto-test-pytest` (Python tests with hub scoping)
6. `auto-test-dashboard` (Jest tests with hub scoping)

### Phase 4: Tier 2 Verticals
7. `auto-test-pages` (page route validation)
8. `auto-test-api` (API route health)

### Phase 5: Tier 3 Vertical
9. `auto-test-mcp-commands` (categorized tool invocation)

### Phase 6: Orchestrator + Retirement
10. `/dev-test` orchestrator skill
11. Retire TEST group commands
12. Regenerate agent configs via sync_agents.py

### Phase 7: Integration Testing
13. End-to-end orchestrator tests

## Alternatives Considered

### A: Expand existing `code-quality` loop

Add all test verticals to the existing `code-quality` loop. Rejected because code-quality is already at budget 18 with lint/coverage/health concerns mixed in. A dedicated testing loop gives independent budget control and cleaner journal tracking.

### B: Keep monolithic commands, add new ones alongside

Keep `/test-nightly` as-is and add new `/test-mcp`, `/test-api`, `/test-pages` commands. Rejected because this doubles the command count without solving the auto-loop integration problem, and leaves the nightly pipeline monolithic.

## References

- ADR-200: Adaptive Loop Engine
- ADR-251: Command Registry Parity
- ADR-252: Commands to Skills Migration
- Design doc: `docs/plans/2026-03-06-test-vertical-decomposition-design.md`
- Implementation plan: `docs/plans/2026-03-06-test-vertical-decomposition-plan.md`
