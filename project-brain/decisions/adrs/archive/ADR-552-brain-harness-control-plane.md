---
status: Implemented
date: '2026-04-19'
deciders:
- Gur Sannikov
related:
- ADR-005
- ADR-162
- ADR-163
- ADR-172
- ADR-270
- ADR-404
- ADR-422
- ADR-490
- ADR-546
- ADR-547
hub: brain
tags:
- brain
- second-brain
- dashboard
- mcp
- observability
- harness
superseded_by: null
implemented_date: '2026-04-19'
implementation_commits:
- 2f7af670cf
- 6a04cfedfe
- a9c4b3c05a
- 9fd65a3d53
- 1a07bcd605
- fd28387dbe
- 5232457cd8
- 970a14bc03
- 4700e5f865
---


# ADR-552: Brain Harness Control Plane

## Context

Augur already contains the ingredients of a harnessed second brain: skills, memory, wiki pages, ADRs, MCP tools, dashboard pages, autoloops, commands, and IDE action dispatch. These pieces are discoverable through Browse and through agent instructions, but the product lacks one Brain hub surface that explains how those pieces form an operating harness.

Browse is intentionally a catalog. It answers what exists across skills, pages, documents, wiki, vault data, prompts, actions, integrations, and scheduled execution entries. It should not become the place where users debug readiness, inspect provenance, or decide which repair path to trigger.

The missing product surface is a control plane that answers:

- what makes up this second brain
- how memory, skills, tools, pages, loops, commands, protocols, and document surfaces connect
- which parts are stale, weakly connected, or broken
- where each claim came from
- what safe next action the user can take

This decision is motivated by the harnessed-agent model from the linked article: the LLM should stay relatively thin, while the durable intelligence lives in memory, skills, protocols, mediators, observability, and action routing. Augur already has those layers, but needs to make them visible and operable.

## Decision

Augur will add a Brain hub control-plane surface called the Brain Harness Control Plane at `/brain/harness`.

The first implementation will be a snapshot-backed Harness Map with balanced starter diagnostics and action triggers.

### 1. Brain Hub Placement

The page belongs in the Brain hub because its primary user value is second-brain quality, trust, provenance, and reasoning context. It may link to Browse detail pages, but it must not duplicate Browse catalog search and filtering.

### 2. Browse Boundary

Browse remains the catalog surface:

- inventory
- discovery
- metadata
- detail pages
- search and filters

Brain Harness is the control-plane surface:

- readiness
- provenance
- relationships
- diagnostics
- repair routing
- safe operational triggers

### 3. Snapshot-Backed Architecture

The Harness Map will use a generated snapshot. The snapshot is runtime/cache state derived from existing decentralized sources. It is not a new central registry and must not become a source of truth.

Canonical sources remain:

- `skills/*/SKILL.md` frontmatter and `x-augur-*` metadata
- MCP `@mcp.tool(name=...)` registrations
- dashboard page discovery outputs
- command and action metadata
- ADR/wiki/index metadata
- loop and ops scanner outputs
- runtime state where relevant

A Python assembler reads those sources and writes a generated snapshot under Augur external runtime/cache paths resolved by `src.config.paths`.

MCP tools expose the snapshot and safe refresh actions to the dashboard. The `/brain/harness` page reads those tools with MCP hooks.

### 4. Snapshot Data Model

The snapshot contains five top-level concepts:

- capabilities
- relationships
- diagnostics
- actions
- provenance

Initial capability types are:

- `memory`
- `skill`
- `mcp_tool`
- `dashboard_page`
- `command`
- `protocol`
- `loop`
- `document_surface`

Initial relationship types include:

- `skill_declares_tool`
- `skill_declares_command`
- `skill_owns_page`
- `page_calls_tool`
- `loop_scans_source`
- `protocol_governs_action`
- `memory_surface_indexes_source`

Every warning or error diagnostic must include:

- reason
- affected capability IDs
- source path or scanner source
- recommended next action
- whether the action is safe/direct or IDE-dispatched

### 5. Balanced Starter Diagnostics

The MVP starts with shallow diagnostics across three families.

Structural integrity:

- missing or unparsable `SKILL.md` frontmatter
- missing `x-augur-hub`
- hub alignment issues
- missing owner/source information
- evidence of central registry drift

Dashboard and MCP wiring:

- dashboard page references an MCP tool that is not registered
- declared skill tool is missing from MCP registrations
- page discovery mismatch
- stale generated tab/page metadata
- response-shape risk where a page expects a shape different from the tool family

Knowledge quality:

- missing source provenance for memory or document surfaces
- stale wiki or project index timestamp
- missing ADR reference for architectural decisions
- knowledge source exists but is not discoverable through expected indexes

### 6. Action Trigger Boundary

The page can include safe direct triggers:

- refresh snapshot
- rerun read-only diagnostics
- reindex knowledge
- reindex Browse
- open source file

Code-changing repair work must dispatch an IDE action through the central action infrastructure with `dispatch: ide`. The dashboard must not directly run LLM calls, shell commands, Python scripts, or file-editing fixers for repair work.

### 7. Failure Honesty

The page must disclose failure states:

- no snapshot: show generate action
- stale snapshot: show snapshot age and refresh action
- partial scan: show which scanner failed and keep valid partial results visible
- missing source: show a diagnostic instead of dropping the row silently
- repair needed: dispatch IDE repair action rather than mutating directly

## Consequences

### Positive

- Users get a clear Brain surface for second-brain readiness and trust.
- Browse stays focused on catalog/discovery rather than absorbing operational debugging.
- Harness facts remain decentralized and traceable.
- The dashboard gets a stable MCP data contract instead of expensive ad hoc scans.
- Safe operational buttons become possible without violating dashboard AI and execution boundaries.
- Code-changing repair work stays in agent/IDE workflows where it can use full context, checkpoints, and verification.

### Negative

- The snapshot assembler introduces a generated state artifact that must be kept visibly non-authoritative.
- The MVP needs tests across Python snapshot assembly and dashboard rendering/action wiring.
- The initial diagnostics are intentionally shallow and will not replace deeper hardening loops.
- The first version adds one more Brain page that must maintain a clear boundary with Browse and existing Brain AI/Knowledge pages.

### Neutral

- Existing Browse behavior remains intact.
- Existing skill frontmatter remains the canonical source for skill-owned metadata.
- Existing MCP hooks and action dispatch patterns remain the dashboard integration model.
- Full agent run tracing is deferred to a later ADR or implementation phase.

## Alternatives Considered

### Alternative 1: Extend Browse

Add harness diagnostics and repair buttons directly to Browse. Rejected because Browse already has a catalog mandate. Mixing catalog discovery with readiness and repair would make the user model muddy and conflict with existing Brain IA decisions.

### Alternative 2: Live Assembly Only

Have `/brain/harness` scan skills, tools, pages, wiki, and runtime state on every page load. Rejected for the MVP because it risks slow UI loads and unclear failure behavior as diagnostics grow. A snapshot gives the page a stable contract and lets refresh failures be explicit.

### Alternative 3: Trace-First Harness

Instrument agent runs first, then derive the harness map from real execution traces. This is powerful long-term, but too broad for the first MVP. The map and snapshot contract should exist before run tracing depends on it.

### Alternative 4: Direct Repair Buttons

Allow the dashboard to run repair fixers that edit files or mutate state. Rejected because it violates Augur's dashboard execution boundary and removes the agent/IDE approval and verification model from code-changing work.

## References

- `~/Projects/Augur/.worktrees/harness-layer-design/docs/superpowers/specs/2026-04-19-augur-harness-layer-design.md`
- `docs/agent-topics/DASHBOARD.md`
- `docs/agent-topics/ARCHITECTURE.md`
- `docs/agent-topics/WORKFLOWS.md`
- `skills/knowledge/SKILL.md`
- `skills/ai/SKILL.md`
- `src/mcp/augur_mcp/infrastructure/__init__.py`
- `src/mcp/augur_mcp/domain/__init__.py`
- `https://www.linkedin.com/posts/akshay-pachaar_a-harnessed-llm-agent-and-why-llm-is-a-share-7451280005042704384-ff0_`

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - "new MCP tools for reading and refreshing the Brain Harness snapshot"
    - "new Brain dashboard route /brain/harness"
  patterns_deprecated: []
  files_affected:
    - "src/mcp/augur_mcp/infrastructure/harness.py"
    - "src/mcp/augur_mcp/infrastructure/__init__.py"
    - "src/mcp/augur_mcp/tests/test_harness.py"
    - "apps/dashboard/features/pages/brain/harness/page.tsx"
    - "tests/dashboard/features/pages/brain/harness-page.test.tsx"
    - "skills/knowledge/SKILL.md"
```

## Implementation Status

Implemented on 2026-04-19 in branch `codex/harness-layer-design`. The delivered MVP includes the snapshot assembler, read/refresh MCP tools, the `/brain/harness` Brain hub page, decentralized registration through `skills/knowledge/SKILL.md`, and route discovery support for declared flat feature pages.

Verification evidence:

- `PYTHONPATH=.:src/mcp pytest src/mcp/augur_mcp/tests/test_harness.py -v` — 9 passed.
- `pnpm test --runInBand harness-page.test.tsx page-discovery.test.ts generate-registry.test.ts generate-tab-registry.test.ts` — 4 suites / 28 tests passed.
- `pnpm exec tsc --noEmit --pretty false` — passed.
- `pnpm run build:safe` — passed after adding `dashboard_pages` to the canonical dashboard metadata type.
- Browser verification on `http://localhost:3002/brain/harness` confirmed real snapshot data: 146 mapped capabilities, 20 skills, 3 diagnostics, `/brain/harness` route provenance, and successful refresh through MCP.

Runtime note: during verification, adding `skills/daemon/scripts` to the dashboard process `PYTHONPATH` shadowed the PyPI `mcp` package via `skills/daemon/scripts/mcp/`. The verified dashboard run uses only the repo root and `src/mcp` in `PYTHONPATH`, matching the normal dashboard startup contract.

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

**Team name**: `adr-552-brain-harness`

### Phase 1: Snapshot Contract
**Strategy**: `PIPELINE`

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | mcp | medium | Add typed snapshot models and an assembler that reads decentralized skill/page/tool sources and writes runtime/cache snapshot state | `src/mcp/augur_mcp/infrastructure/harness.py`, `src/mcp/augur_mcp/tests/test_harness.py` |
| 1.2 | mcp | medium | Register read and refresh MCP tools for the snapshot and safe triggers | `src/mcp/augur_mcp/infrastructure/__init__.py`, `src/mcp/augur_mcp/infrastructure/harness.py` |

### Phase 2: Brain Page
**Strategy**: `PIPELINE`

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | dashboard | medium | Add `/brain/harness` page that renders readiness, capability map, diagnostics, provenance, and trigger panel from MCP snapshot data | `apps/dashboard/features/pages/brain/harness/page.tsx`, `tests/dashboard/features/pages/brain/harness-page.test.tsx` |
| 2.2 | metadata | low | Register the Brain page through decentralized skill metadata, without central dashboard config edits | `skills/knowledge/SKILL.md` |

### Phase 3: Verification
**Strategy**: `PIPELINE`

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | tests | medium | Run Python and dashboard tests, mount plugin generation, approved dashboard build path, and browser verification for `/brain/harness` | test/build scripts, browser |
| 3.2 | docs | low | Update generated ADR references if the project has a generator command for ADR indexes and update ADR status after implementation passes | ADR tooling, `docs/generated/adr-index.md` if generated |

### Completion Criteria

- [x] `/brain/harness` shows real snapshot-backed capability data.
- [x] Snapshot facts include provenance and do not create a new central registry.
- [x] Balanced starter diagnostics render with source and recommended action.
- [x] Safe triggers use MCP calls and do not execute direct dashboard scripts.
- [x] Repair triggers dispatch IDE actions.
- [x] Python and dashboard tests pass.
- [x] Browser verification confirms real data and working safe triggers on the correct checkout.
- [x] ADR status is updated after implementation lands.
