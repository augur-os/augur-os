---
description: "Manage the shared wiki layer that compiles durable knowledge across conversations. Usage: /wiki [status|reindex|rebuild|update|migrate-v4|lint|purge|reset|report]"
x-augur-export-command: false
visibility: core
---
# /wiki Command Execution

1. Command format is `/wiki <action>`.
2. Actions available:
   - `status` — return structure, compiler backlog, batch, coverage, and index state
   - `reindex` — refresh the wiki browse/search index for existing wiki pages only
   - `rebuild` — prepare a concept-first compile from current sources
   - `update` — prepare an incremental concept-first compile for changed sources
   - `migrate-v4` — dry-run the ADR-740 v3-to-v4 concept page migration; pass `--apply` only after reviewing diffs
   - `lint` — detect missing required pages, broken internal wiki links, and orphan pages
   - `purge` — delete the compiled wiki plus runtime/browse artifacts for a clean rebuild
   - `reset` — run a safe clean-slate reset that purges generated wiki pages and compiler state, rebuilds source indexes, reindexes wiki pages, lints, then prepares a bounded concept extraction batch by default
   - `report` — generate a Second Brain Intelligence Report (HTML, PDF, and sidecar artifact)
3. Parse the action and call the matching MCP tool:
   - `status` -> `wiki-status`
   - `reindex` -> `wiki-reindex`
   - `rebuild` -> `wiki-rebuild`
   - `update` -> `wiki-update`
   - `migrate-v4` -> `wiki-migrate-v4` with `apply=false` by default; map an explicit `--apply` flag to `apply=true`
   - `lint` -> `wiki-lint`
   - `purge` -> `wiki-purge`
   - `reset` -> `wiki-reset`
   - `report` -> three-step agent flow; see [the `/wiki report` section](#wiki-report)
4. Print the JSON output in a readable format.
5. `/wiki reindex` only refreshes browse/search indexing for pages that already exist. For wiki creation, bootstrapping, repair, or hardening, direct the user to `/wiki rebuild` or `/wiki update`.
6. `/wiki rebuild` and `/wiki update` return an agent-action concept extraction batch. Read the batch file, run the extraction prompts in the IDE/CLI agent, and apply the extracted concept JSON with `wiki-apply-concept-batch`.
7. `/wiki purge` is destructive. Use it immediately before `/wiki rebuild` or a clean compile/bootstrap flow.
8. `/wiki reset` is the safest recovery path after a full wipe. It uses a bounded concept extraction batch by default; add `--all` only when you intentionally want an exhaustive whole-graph compile.
9. If `lint` reports missing links or orphan pages, surface them directly and suggest `/wiki update` for focused repair or `/wiki rebuild` for broader bootstrap and repair work.
10. Concept pages use ADR-740 v4 layout. `wiki-update` and `wiki-apply-concept-batch` append cited observations to `## Timeline`; they do not overwrite an existing `## Compiled truth` section. Truth changes are proposed through the rewrite proposal flow and applied only by the explicit `wiki-apply-top-rewrite-proposal` step.

## Usage

```bash
/wiki status
/wiki reindex
/wiki rebuild
/wiki update
/wiki migrate-v4
/wiki migrate-v4 --apply
/wiki lint
/wiki purge
/wiki reset
/wiki reset --all
/wiki report
```

## /wiki report

Generate a Second Brain Intelligence Report from your compiled wiki. The flow is three steps executed by the AI client agent, per `docs/superpowers/specs/2026-05-11-wiki-report-agent-step-contract-design.md`.

### Step 1 — Call `wiki-report-data`

Read the returned raw data fields (`stats`, `hubs`, `hub_sections`, `pages`, `connections`, `portfolio`) and `synthesis_schema`. The schema names every required and optional field the agent must produce.

### Step 2 — Synthesize the editorial fields

The agent reads the raw data and produces a rich dict combining passed-through fields with synthesized editorial content. Required fields:

- `synthesis` — 1-2 sentence cover paragraph (100-400 chars) that captures what the brain reveals: dominant themes, quality posture, and overall shape.
- `hub_sections[*].summary` — one-line description per hub (60-200 chars) explaining what content lives there, drawn from each hub's tags and source-count distribution.

Optional fields, rendered when present and skipped when absent:

- `who_you_are.what_you_do` — 2-4 sentence narrative of what the user is building or doing.
- `who_you_are.how_you_think` — 2-4 sentence narrative of cognitive patterns.
- `expertise` — ranked list of `{domain, level, percentage, color}`. Level enum: `Expert | Advanced | Intermediate | Building | Beginner`.
- `patterns` — list of `{title, description}` patterns the agent notices.
- `blind_spots` — list of `{title, description, severity}` gaps. Severity enum: `low | medium | high`.

### Step 3 — Call `wiki-report-generate`

Pass the rich dict as `report_json` to `wiki-report-generate`. The MCP tool validates input on entry and:

- On success: writes `get_documents_dir()/brain/artifacts/second-brain-report-<YYYY-MM-DD>.html`, the PDF alongside it, and a `.meta.yaml` sidecar per ADR-723. Returns paths.
- On failure: returns `{success: false, error: "agent_step_required", missing_required: [...], contract_path, hint}`. No HTML is written.

### Synthesis Examples

**`synthesis` cover paragraph:**

> "A 74-page wiki anchored in AI infrastructure and career positioning, with 422 cross-references across seven hubs. The graph is dense, quality-gated, and strongest around agent workflows, dashboard surfaces, and durable decision records."

**`hub_sections[*].summary` examples:**

| Hub | Example summary |
|---|---|
| `brain` | "Control plane for advisor analytics, agent-learning compounding, architecture review, and observability work." |
| `career` | "AI-transformation and platform-engineering leadership positioning, career strategy, and content operations." |
| `studio` | "Content idea capture, publishing workflows, brand/campaign/collateral work, and compounding loops." |

**`patterns` examples:**

| Title | Description shape |
|---|---|
| `Discipline beats velocity` | Reference quality-gate stats and the maintenance cadence. |
| `Knowledge compounds at the cross-ref level` | Reference cross-reference counts and average outgoing links. |
| `Heavy ingest, deliberate compounding` | Reference source-to-page ratio and merged concept batches. |

**`blind_spots` examples:**

| Title | Severity guidance |
|---|---|
| `Life hub underrepresented` | `medium` if life is one of the smallest hubs by page count. |
| `Workspace: high ingest, lower compounding` | `medium` if source-to-page ratio is much higher than other hubs. |
| `General hub is a catch-all` | `low` if general has fewer than five pages. |

### Failure Mode — No Agent Layer Present

If the agent step is skipped, the tool returns:

```json
{
  "success": false,
  "error": "agent_step_required",
  "missing_required": ["synthesis", "hub_sections[0].summary"],
  "contract_path": "project-brain/capabilities/skills/rag/commands/wiki.md#wiki-report",
  "hint": "Run /wiki report from inside Claude Code, Codex, Gemini CLI, Cursor, or Copilot. The agent layer is required for editorial synthesis."
}
```

No skeleton HTML is written. The CLI/daemon path is intentionally not supported; invoke from an AI client.
