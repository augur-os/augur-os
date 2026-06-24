---
name: dream
x-augur-type: skill
x-augur-group: brain
x-augur-release: mvp
x-augur-license: MIT
x-augur-tags:
- routine
- synthesis
- compounding
- cross-client
- wiki
description: Overnight knowledge-compounding routine projected into every supported AI client. The client's session drives all judgment phases — compiled-truth refresh, pattern extraction, wiki concept merging — while deterministic phases (orphan detection, dead-citation scanning, cache GC, entity-tier recompute) delegate to skill-owned entry points. Client scheduling and inference stay entirely outside Augur. Implements ADR-744.
x-augur-callable: project-brain/capabilities/skills/dream/scripts/mcp/__init__.py
x-augur-mcp-tools:
- dream-orphans
- dream-stale-pages
- dream-merge-candidates
- dream-dead-citations
- dream-cache-gc
- dream-report-write
- dream-last-report
- dream-status
- dream-config
x-augur-data-dir: dream
x-augur-config:
  commands:
  - id: dream
    type: routine
    visibility: user
    description: Overnight knowledge-compounding routine. Activated per-client via its native routine surface (Codex automations, Claude Code `/schedule`, etc.).
    callable: commands/dream.md
    protocol: routine
x-augur-loop:
  id: dream
  skill: dream
  automation:
    trigger: nightly
    runner: auto
    discover: commands/dream.md
  memory:
    trust: oneshot
---

# dream

Augur's overnight compounding pass.

## Standard core

Portable workflow guidance for this capability lives in:

- `recurring-reflection/dream-routine`

This skill remains the Augur adapter. It owns MCP tools, dashboard/Browse/routine
projection, path-helper access, runtime state, and real-data verification for
Augur.

Three non-negotiable principles:

1. **No Augur-side scheduling.** The client's routine system owns the cron
   (Codex automations, Claude Code `/schedule`, Gemini equivalents). `launchd` /
   Task Scheduler keep scheduling *other* auto-loops; the dream cycle
   specifically delegates scheduling to the client.
2. **No direct LLM calls from Augur** — enforced by construction. The client
   runs the routine in its own session and owns the LLM context. Augur exposes
   MCP entry points and records ledger state.
3. **No autonomous destructive operations.** Orphans, dead citations, and merge
   candidates are *proposals*. The user confirms before any delete / merge.

## Phases

**Deterministic (MCP, zero LLM cost):**

| Phase | Tool | Owner / delegation |
|---|---|---|
| Orphan cleanup | `dream-orphans` | dream (aggregates ADR-738 inbound edges + ADR-740 timeline counts) |
| Citation fixing | `dream-dead-citations` | dream (scans timeline `_source:` URIs for dead targets) |
| Stale-cache GC | `dream-cache-gc` | dream (filesystem GC of `get_cache_dir()` per `config.yaml` retention) |
| Entity tiering recompute | *delegated to ADR-738* `entity-tier-recompute` | graph skill |

**Judgment (run inline in the client's session):**

| Phase | Supporting tool | What the client does |
|---|---|---|
| Compiled-truth refresh | `dream-stale-pages` | reads recent ADR-740 timeline entries, emits a compiled-truth *proposal* (never a write) |
| Pattern extraction | *(reads recent ingestions)* | proposes new wiki seeds |
| Wiki concept merging | `dream-merge-candidates` | reviews high-similarity pairs, proposes merges |

Every phase opens a job via ADR-743 `jobs-submit`. Failure of one deterministic
phase does not block subsequent deterministic phases. Output report lands at
`get_documents_dir()/reports/dream/<YYYY-MM-DD>.md`.

## Configuration

Skill-local at `project-brain/capabilities/skills/dream/config.yaml`. Per Rule #2, dream
config is NOT in central config — only the dream routine reads it.

## Activation

Per-client, via the client's native routine surface:

- **Codex** — auto-activated from the skill-local routine seed at
  `project-brain/capabilities/skills/dream/assets/seeds/routine-schedule.yaml`
- **Claude Code** — one-time `/schedule /dream` after `sync_agents` projects
  the slash command
- **Gemini** — equivalent native surface (per current Gemini capability)
- **Cursor / Copilot** — manual `/dream` (graceful degradation; no native
  routine surface)

See `docs/superpowers/specs/2026-05-14-dream-cycle-design.md` and
`project-brain/decisions/adrs/archive/ADR-744-dream-cycle-overnight-synthesis-auto-loop.md`.

## Examples

```bash
# A client runs the dream routine in its own session (Augur owns no scheduling)
/a-loops run dream
```

The deterministic phases call MCP tools in `scripts/`; judgment phases run inline in the client session and emit proposals only.
