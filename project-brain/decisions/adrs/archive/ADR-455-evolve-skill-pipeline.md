---
status: Implemented
date: 2026-03-19
deciders:
  - Gur Sannikov
related: [ADR-450, ADR-454, ADR-432]
hub: null
tags: [skill-evolution, user-journey, orchestration, augur-ops]
superseded_by: null
---

# ADR-455: Evolve Skill Pipeline

## Context

Augur users who encounter new problems have no unified way to grow their second brain. The pieces exist separately — `import` for data ingestion, `skillstore` for community skills, `mcp-app-factory` for scaffolding, `page-builder` for dashboards — but there's no single flow that guides from "I have a problem" to "I have a working skill." Users must know which tool to use when, and manually connect the steps.

The user journey for growing Augur should start from one of three entry points: new collateral (docs, photos), a problem description in chat, or a provided SKILL.md. At each step, Augur needs to understand whether to extend an existing skill or create a new one.

## Decision

Create `/evolve` — a thin orchestrator skill in the `augur-ops` plugin that provides a unified 8-step pipeline:

```
INTAKE → CLASSIFY → SEARCH → SCAFFOLD → ENRICH → WIRE → VERIFY → PAGE (optional)
```

### Architecture: Thin Orchestrator

`/evolve` is a conversational state machine. It manages pipeline steps and user decisions, delegating all real work to existing skills via MCP tool calls:

- **import** tools — collateral extraction, data processing
- **discovery/classify-problem** — semantic matching against installed skills
- **skillstore** tools — community/GitHub skill search
- **mcp-app-factory** tools — plugin scaffolding, MCP wiring
- **verify/test** tools — smoke testing, wiring audits
- **ADR-450 template system** — dashboard page composition

Existing skills stay independent and testable. Each step can still be invoked standalone via the original skill.

### Skill Identity

- **Plugin:** `augur-ops`
- **Location:** `.claude/skills/evolve/` (Claude Code-mastered, `x-augur-plugin: augur-ops`)
- **Visibility:** `app` (system-wide)
- **Surfaces:** CLI (`/evolve`) + Dashboard (horizontal stepper page via ADR-450 template)

### Entry Points

Three ways to start, normalizing into the same internal pipeline state:

1. **Collateral** (`/evolve --from-docs <path>`) — scan directory, extract content, produce problem summary
2. **Chat** (`/evolve`) — interactive problem description, optionally attach collateral
3. **SKILL.md** (`/evolve --from-skill <path>`) — parse frontmatter, skip search step

### Classification (Hybrid)

Keyword-based semantic matching via `classify-problem` MCP tool, with confidence tiers:
- **High (>0.8):** Pre-select, user confirms or overrides
- **Medium (0.4-0.8):** Show top matches with gap analysis
- **Low (<0.4):** Suggest search or create new

Gap analysis shows what the problem asks for that the matched skill doesn't cover. User always makes the final decision.

### Search

When no SKILL.md provided and classification needs more options: search skillstore (skills.sh) and GitHub, present matches with gap analysis. User decides: install and extend, build new, or skip.

### State Persistence

Pipeline state at `{get_state_dir()}/evolve/<pipeline-id>.yaml` — project-scoped per ADR-454. All steps are idempotent. `/evolve --resume <id>` picks up from last completed step.

### MCP Tools

4 tools registered by the evolve skill:
- `get-evolve-pipelines` — list all pipelines (dashboard)
- `get-evolve-pipeline-detail` — single pipeline with step history (dashboard)
- `evolve-step-action` — create/complete/skip/fail/resume pipeline steps
- `classify-problem` — semantic skill matching with gap analysis

### Dashboard UI

Horizontal stepper layout (ADR-450 YAML template at `plugins/ui/templates/command/evolve.yaml`):
- Stepper block (top) — 8 steps with progress indicators, active step expanded
- History table (bottom) — completed pipelines

### Existing Skill Relationship

| Skill | Role after evolve |
|-------|------------------|
| **mcp-app-factory** | Low-level scaffolding engine — evolve calls it |
| **skillstore** | Search backend — evolve calls it in search step |
| **import** | Intake engine — evolve calls it for collateral processing |
| **page-builder** | Absorbed by ADR-450 template system |
| **discovery** | Classification backend — evolve's `classify-problem` replaces the need |

## Consequences

### Positive

- Users have a single entry point for growing their Augur — no need to know which tool to use
- Existing skills stay independent — evolve is a thin layer, not a replacement
- Pipeline state is persistent and resumable — interrupted work isn't lost
- Dashboard provides visibility into evolution history

### Negative

- Depends on ADR-450 and ADR-454 being implemented first
- Classification is keyword-based, not semantic — accuracy depends on good skill descriptions
- Orchestration logic lives in SKILL.md instructions, not executable code — harder to test end-to-end

### Neutral

- No changes to existing skills required — evolve calls their MCP tools as-is
- The `classify-problem` tool is a lightweight addition, not a replacement for discovery

## Alternatives Considered

### Alternative 1: Pipeline Engine

Build a generic pipeline engine in `src/lib/` that any multi-step workflow can use, with YAML pipeline definitions. Rejected — YAGNI. We don't know if other pipelines need this yet, and the generic engine would add complexity before `/evolve` even works.

### Alternative 2: Smart Intake + Dumb Steps

Invest all intelligence in the intake/classify layer — heavy NLP, document analysis, semantic search — and make remaining steps simple execution of the resulting plan. Rejected — front-loads all user interaction, less opportunity for course correction mid-pipeline.

### Alternative 3: Consolidation

Replace mcp-app-factory, skillstore, and import with a single monolithic skill. Rejected — violates decentralization principle (ADR-163). Existing skills serve users who want to call them directly.

## References

- Design spec: `~/Vault/Augur/dev/specs/2026-03-19-evolve-skill-pipeline-design.md`
- Implementation plan: `docs/superpowers/plans/2026-03-19-evolve-skill-pipeline.md`
- ADR-450: Template-Driven Dashboard
- ADR-454: Augur Project Framework (multi-project)
- ADR-432: Frontmatter Migration (no augur.yaml)
- ADR-163: Decentralized Plugin Config

## Implementation Prompt

> Already implemented. See implementation plan at `docs/superpowers/plans/2026-03-19-evolve-skill-pipeline.md`.

**Team name**: `adr-455-evolve-pipeline`

### Phase 1: Core (PIPELINE)

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | backend | low | Pipeline state model + YAML persistence | `.claude/skills/evolve/augur/lib/pipeline_state.py` |
| 1.2 | backend | low | Keyword classifier with gap analysis | `.claude/skills/evolve/augur/lib/classifier.py` |
| 1.3 | backend | low | MCP tool registrations (4 tools) | `.claude/skills/evolve/scripts/mcp/__init__.py` |
| 1.4 | architect | high | SKILL.md orchestration instructions | `.claude/skills/evolve/SKILL.md` |

### Phase 2: Dashboard (PARALLEL)

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | frontend | low | ADR-450 stepper template | `plugins/ui/templates/command/evolve.yaml` |

### Completion Criteria

- [x] All phases executed
- [x] All tests pass (16/16)
- [x] MCP module loads with register_tools
- [x] Skill discovered by skill_registry (master=claude-code, plugin=augur-ops)
- [x] SKILL.md covers all 8 steps and 5 CLI flags
- [x] Dashboard template created
- [x] ADR status updated to Implemented
