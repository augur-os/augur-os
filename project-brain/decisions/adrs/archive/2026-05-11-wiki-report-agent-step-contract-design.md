---
title: "Wiki Report Agent-Step Contract"
type: spec
status: draft
created: 2026-05-11
authors:
  - gsannikov
related:
  - ADR-723 Augur Pages HTML Artifacts (Accepted) — output location + sidecar schema
  - shared-vault/skills/rag/commands/wiki.md — slash command surface
  - shared-vault/skills/ingest/scripts/mcp/wiki_tools.py — MCP tool implementation
  - shared-vault/skills/ingest/scripts/wiki_report.py — aggregator
  - shared-vault/skills/ingest/scripts/wiki_report_render.py — renderer
  - shared-vault/skills/ingest/assets/templates/report.html.j2 — Jinja2 template
governance:
  next_step: ADR (via /adr write) → implementation plan (writing-plans)
tags:
  - wiki
  - mcp
  - agent-contract
  - ai-client-execution-model
---

# Wiki Report Agent-Step Contract

## 1. Problem

The `/wiki report` flow is structurally incomplete. The renderer template (`report.html.j2`) expects a **rich report dict** with editorial content — synthesis paragraph, "Who You Are" narratives, expertise stack, per-hub icon/color/summary, patterns, blind spots. The aggregator (`wiki-report-data`) produces only **raw aggregated stats** — page counts, source counts, tag arrays. There's a load-bearing **agent step** between them that synthesizes the editorial content from the raw data — but it's undefined: no contract, no MCP tool, no documented surface.

Symptoms observed 2026-05-11:

- Invoking the chain directly from a Python script (no AI client involved) produces a 955KB HTML with section labels but zero narrative content — "empty colors".
- The renderer docstring acknowledges this: *"Both accept the report dict produced by the wiki_report **agent step**."* The agent step is named but nowhere implemented.
- The two MCP tools (`wiki-report-data` and `wiki-report-generate`) disagree on dict shape — the data tool returns `hubs` as a dict; the generate tool expects `hub_sections` as a list. An unwritten contract bridges them in the agent's head, not in code.
- When invoked from inside an AI client session, the agent (Claude Code / Codex / etc.) improvises the synthesis ad-hoc. Quality is unpredictable across sessions and clients.

ADR-723 (Augur Pages HTML Artifacts — Accepted) covers artifact **storage and discovery** but does NOT define the synthesis interface. ADR-607 (Wiki Signal Priority — Accepted) covers wiki **update cadence** but does NOT cover report generation.

This design defines the contract.

## 2. Goals and non-goals

### Goals

1. **Make `/wiki report` a deterministic flow** with a defined input/output contract for the agent step.
2. **Fail loud when invoked outside an AI client** — no skeleton fallback, no degraded output (CLAUDE.md rule 1).
3. **Tier the contract** so the most-visible sections are required and supplementary sections degrade gracefully.
4. **Surface the contract in three coordinated places** — machine-readable schema, slash command docs, runtime validation.
5. **Land outputs at the ADR-723-canonical location** — `get_documents_dir()/brain/artifacts/<slug>.html` + `<slug>.html.meta.yaml`.
6. **Fix the existing shape divergence** between `wiki-report-data` and `wiki-report-generate`.

### Non-goals

- Server-side LLM synthesis (breaks the harness/native-agent boundary — `docs/what-is-augur.md`)
- Auto-spawning AI client sessions from CLI/daemon
- Multi-hub reports (whole-brain only for v1)
- Generalizing the contract to non-wiki reports (deferred to a follow-on ADR when a second use case appears)
- PDF generation changes (existing `render_pdf` reads the same dict; should "just work" once HTML is correct)
- Schema-driven deterministic synthesis (loses the personalized narrative)

## 3. Decision summary

**Pipeline (executed by the AI-client agent):**

```
/wiki report     (invoked from inside an AI client session)
   │
   ├─ Step 1:  agent calls  wiki-report-data       MCP
   │           → returns { raw_data, synthesis_schema }
   │
   ├─ Step 2:  agent synthesizes editorial fields per the schema
   │
   └─ Step 3:  agent calls  wiki-report-generate(rich_dict)  MCP
               → writes HTML + sidecar to
                 get_documents_dir()/brain/artifacts/
                   second-brain-report-<YYYY-MM-DD>.html
                   second-brain-report-<YYYY-MM-DD>.html.meta.yaml
```

**Three coordinated contract surfaces:**

| Surface | Purpose | Where it lives |
|---|---|---|
| `synthesis_schema` field in `wiki-report-data` output | Machine-readable contract — agent reads to know what to produce | Returned alongside raw_data |
| `/wiki report` action documentation | Human-readable contract — walks the agent through the 3-step flow with examples | `shared-vault/skills/rag/commands/wiki.md` |
| `wiki-report-generate` input validation | Enforcement — rejects missing required fields with a structured error | `shared-vault/skills/ingest/scripts/mcp/wiki_tools.py` |

## 4. Contract: rich dict shape

`wiki-report-generate` accepts this dict shape:

```yaml
# REQUIRED (agent must synthesize)
synthesis: "1-2 sentence cover paragraph (string, 100-400 chars)"
hub_sections:
  - name: "<hub-id>"          # e.g. "brain", "career"
    source_count: <int>       # passed through from raw_data
    summary: "<one-line summary, 60-200 chars>"
    icon:    "<emoji or unicode, 1-2 chars>"   # default chosen by renderer if missing
    color:   "<hex color, e.g. #6366f1>"        # default chosen by renderer if missing

# OPTIONAL (rendered when present; section omitted when absent)
title: "What Your AI Knows About You"   # defaults to this literal if missing
name:  "<user name from portfolio profile or 'You'>"
date:  "<today's date, formatted>"

who_you_are:
  what_you_do:   "<2-4 sentence narrative>"
  how_you_think: "<2-4 sentence narrative>"

expertise:
  - domain:     "<e.g. 'Cross-Client AI Harness'>"
    level:      "Expert | Advanced | Intermediate | Building | Beginner"
    percentage: <int 0-100>
    color:      "<hex>"

patterns:
  - title:       "<short title, 3-7 words>"
    description: "<2-3 sentence description>"

blind_spots:
  - title:       "<short title, 3-7 words>"
    description: "<2-3 sentence description>"
    severity:    "low | medium | high"

# PASSED-THROUGH (raw aggregator output; not synthesized)
stats:
  pages:      <int>
  hubs:       <int>
  sources:    <int>
  words:      "<string with commas, e.g. '34,286'>"   # template renders verbatim
  cross_refs: <int>

portfolio:
  profile:    "<path or empty>"
  logo:       "<path or empty>"
  cover:      "<path or empty>"
  hub_images: { "<hub>": [path, ...], ... }

charts:                                # generated by wiki-report-generate itself
  radar:        "<path>"
  graph:        "<path>"
  distribution: "<path>"
```

### 4.1 Tier semantics

- **Required tier**: `synthesis` + every `hub_sections[i].summary` (one per hub). These are the most visible sections; missing them produces obvious gaps on the cover and the "What Your Brain Contains" section.
- **Optional tier**: `who_you_are`, `expertise`, `patterns`, `blind_spots`. Renderer template wraps each in `{% if report.X %}` so absent sections are silently omitted. Short reports legitimately skip these.
- **Defaults**: `title`, `name`, `date` are technically optional but the renderer fills in defaults if missing (literal title, "You", today's date).

### 4.2 Failure mode

`wiki-report-generate` validates input on entry. If any required field is missing or wrongly shaped:

```json
{
  "success": false,
  "error": "agent_step_required",
  "missing_required": ["synthesis", "hub_sections[0].summary", "hub_sections[2].summary"],
  "contract_path": "shared-vault/skills/rag/commands/wiki.md#report-action",
  "hint": "Run /wiki report from inside Claude Code, Codex, Gemini CLI, Cursor, or Copilot. The agent layer is required for editorial synthesis."
}
```

No skeleton render. No auto-spawn. No fallback that leaves the product in a degraded state. (CLAUDE.md rule 1.)

## 5. Contract surface 1: `synthesis_schema` in `wiki-report-data`

`wiki-report-data` is extended to return a `synthesis_schema` field alongside the raw aggregated data:

```json
{
  "success": true,
  "raw_data": {
    "stats": { "pages": 74, "hubs": 7, ... },
    "hubs":  { "brain": { "source_count": 136, ... }, ... },
    "portfolio": { ... },
    "consolidation": [...]
  },
  "synthesis_schema": {
    "version": 1,
    "required": [
      { "path": "synthesis",                    "type": "string",  "min_len": 100, "max_len": 400 },
      { "path": "hub_sections[*].summary",      "type": "string",  "min_len": 60,  "max_len": 200 }
    ],
    "optional": [
      { "path": "who_you_are.what_you_do",      "type": "string" },
      { "path": "who_you_are.how_you_think",    "type": "string" },
      { "path": "expertise[*]",                 "shape": { "domain": "string", "level": "enum:Expert|Advanced|Intermediate|Building|Beginner", "percentage": "int:0-100", "color": "hex" } },
      { "path": "patterns[*]",                  "shape": { "title": "string", "description": "string" } },
      { "path": "blind_spots[*]",               "shape": { "title": "string", "description": "string", "severity": "enum:low|medium|high" } }
    ],
    "passed_through": [
      { "path": "stats",     "from": "raw_data.stats" },
      { "path": "portfolio", "from": "raw_data.portfolio" }
    ]
  }
}
```

The agent reads `synthesis_schema` and produces the rich dict per the contract.

## 6. Contract surface 2: `/wiki report` action

Add a `report` action to `/wiki` command in `shared-vault/skills/rag/commands/wiki.md`:

```markdown
- `report` — generate a Second Brain Intelligence Report (HTML + PDF artifact)

## /wiki report

Three-step agent flow:

1. **Call `wiki-report-data` MCP tool.** Read the returned `raw_data` and `synthesis_schema`.
2. **Synthesize the editorial fields** the schema requires:
   - `synthesis` — 1-2 sentence cover paragraph that captures what the brain reveals
     (e.g., dominant themes, quality posture, overall shape).
   - `hub_sections[*].summary` — one-line description per hub explaining what content lives there,
     drawing from each hub's tags and source-count distribution.
   - Optional: `who_you_are.{what_you_do, how_you_think}`, `expertise` ranked list,
     `patterns` and `blind_spots` from the data.
3. **Call `wiki-report-generate(rich_dict)` MCP tool.** Pass the synthesized fields + the
   passed-through `stats` and `portfolio` from step 1.

Output lands at `get_documents_dir()/brain/artifacts/second-brain-report-<YYYY-MM-DD>.html`
with a `.meta.yaml` sidecar per ADR-723.

### Synthesis prompt examples

(Example inputs + sample outputs for each editorial field, so an agent reading this
command can produce consistent output across sessions and clients.)
```

Examples-driven so any client (Claude Code, Codex, Gemini CLI, Cursor, Copilot) produces consistent output.

## 7. Contract surface 3: validation in `wiki-report-generate`

`wiki-report-generate` gains a validation step at the top of the function. Validation logic lives in a small helper `_validate_rich_dict(report)` that:

1. Walks the `synthesis_schema.required` paths and asserts each field is present and of the right shape.
2. Collects missing/wrong-shaped fields into a list.
3. If non-empty, returns the structured `agent_step_required` error (§4.2). No HTML is written.
4. If empty, proceeds with chart rendering + Jinja2 templating.

The validator also fixes the existing shape divergence: it expects `hub_sections` as a list (not `hubs` as a dict). `wiki-report-data` is updated to return `hubs` AND a derived `hub_sections` skeleton (with `name` and `source_count` filled, awaiting agent-supplied `summary`/`icon`/`color`) so the agent has a clean array to enrich.

## 8. ADR-723 alignment

The output path and sidecar follow ADR-723's `Au-docs/<hub>/artifacts/` convention:

- HTML: `get_documents_dir()/brain/artifacts/second-brain-report-<YYYY-MM-DD>.html`
- Sidecar: `get_documents_dir()/brain/artifacts/second-brain-report-<YYYY-MM-DD>.html.meta.yaml`

Sidecar schema:

```yaml
---
slug: second-brain-report-<YYYY-MM-DD>
title: "Second Brain Intelligence Report — <YYYY-MM-DD>"
kind: generated
hub: brain
source:
  type: agent-synthesized
  origin: "Augur wiki snapshot — <N> pages across <H> hubs, <S> sources, <W> words, <CR> cross-references"
  generator: "shared-vault/skills/ingest/scripts/mcp/wiki_tools.py + agent-step synthesis per /wiki report"
tags: [wiki, report, second-brain]
created_at: <ISO-8601>
notes: ""
---
```

ADR-723's Browse `pages` ViewMode will discover this artifact automatically once that ADR is implemented.

## 9. Implementation order

Five verifiable checkpoints in one PR:

| # | Checkpoint | Verifiable by |
|---|---|---|
| **C1** | `wiki-report-data` returns `synthesis_schema` + `hub_sections` skeleton | pytest: schema field present, hub_sections is a list with `name`+`source_count` |
| **C2** | `wiki-report-generate` validates rich dict, returns structured `agent_step_required` error on missing required fields | pytest: invalid input → success=false, error="agent_step_required", missing_required correctly populated |
| **C3** | Renderer template wraps every optional section in `{% if %}` (where it doesn't already) | pytest: render with `who_you_are=None, patterns=[], blind_spots=[]` → HTML contains no empty section chrome for those |
| **C4** | `/wiki report` action documented in `shared-vault/skills/rag/commands/wiki.md` with synthesis examples | manual: agent in Claude Code reads command, produces a valid rich dict on first try |
| **C5** | End-to-end test: mock agent fills rich dict → `wiki-report-generate` → HTML on disk; assert DOM tokens (synthesis paragraph, who_you_are narratives, hub summaries, patterns, blind_spots) | pytest: end-to-end happy path |

## 10. Edge cases

| Case | Behavior |
|---|---|
| Wiki has zero pages | `wiki-report-data` succeeds with `stats.pages=0`; agent can still synthesize a "first-run / empty brain" report. Required fields still apply. |
| Wiki has one hub | `hub_sections` has one entry; agent synthesizes one summary; renderer renders one hub card. |
| Agent provides extra fields not in schema | Ignored. Renderer only reads what the template uses. No reject. |
| Agent provides malformed `severity` value | Validator rejects with `error: agent_step_required`, `missing_required: ["blind_spots[N].severity"]` (treats invalid as missing). |
| Required `synthesis` is too short / too long | Validator rejects (length is part of the schema). |
| Multiple agents / parallel calls | Each call is independent; output filename includes date but not time → same-day re-runs overwrite. Acceptable for v1 (artifacts are easily regenerated). |
| Output dir doesn't exist | `wiki-report-generate` mkdirs `get_documents_dir()/brain/artifacts/` on first run. |

## 11. Testing

- **pytest** — Five unit tests at the validator level (each required field missing → correct error), one round-trip test (rich dict in → HTML on disk → DOM-token assertions).
- **Manual** — One real-agent run in Claude Code: invoke `/wiki report`, verify HTML renders with all sections populated, verify sidecar present.
- **Cross-client** — One real run in each flagship client (Codex, Gemini, Cursor, Copilot) producing valid output. Smoke-level, not full parity.
- **No browser test required** — HTML is self-contained, no JS, no MCP at view time.

## 12. Out of scope (explicit)

| Item | Why deferred |
|---|---|
| Server-side LLM synthesis (Ollama or remote) | Breaks the harness/native-agent boundary |
| Auto-spawn an AI client session from CLI/daemon | Adds heavyweight orchestration; user can invoke from any AI client they have |
| Multi-hub reports / per-hub reports | Whole-brain is the primary use case; per-hub is a follow-on |
| Generic agent-step framework (reusable for career / finance / project reports) | Premature abstraction; one use case doesn't prove the pattern |
| PDF generation changes | `render_pdf` reads the same dict; fixes from this ADR cascade to PDF automatically |
| Schema versioning beyond `version: 1` | Add version bump path only when a v2 is needed |

## 13. Alternatives considered

| Alternative | Why rejected |
|---|---|
| Server-side LLM synthesis (Ollama for offline, remote LLM for online) | Breaks the default native-agent handoff path; adds offline-mode complexity and a new failure axis (LLM unavailable) |
| Schema-driven deterministic synthesis (YAML rules → narrative templates) | Loses the personalized narrative; "Who You Are" becomes generic boilerplate; defeats the report's value |
| Skeleton render when no agent present | CLAUDE.md rule 1 violation — produces a half-baked HTML that masks the missing-agent problem |
| Generic agent-step framework now (reusable for any HTML artifact) | Premature abstraction. One use case (wiki report) doesn't prove the pattern. Wait for a second concrete case. |
| Drop the rich-dict idea, simplify the template to render raw stats only | Loses the report's identity (narrative + synthesis); the value of a "Second Brain Report" is the editorial layer, not the stats |

## 14. References

- ADR-723 Augur Pages HTML Artifacts (Accepted) — artifact storage location + sidecar schema
- ADR-001 Three-Layer Architecture
- ADR-006 Local-First Architecture
- `docs/what-is-augur.md` — Augur is not an agent invariant
- `docs/references/ai-client-execution-model.md` — "Trigger → AI Client Session → Agent orchestrates → MCP tools execute"
- CLAUDE.md rule 1 — User-visible correctness; no fallbacks that leave the product worse
- CLAUDE.md rule 11 — Dashboard uses MCP, not direct local execution
- `shared-vault/skills/rag/commands/wiki.md` — current `/wiki` command surface
- `shared-vault/skills/ingest/scripts/mcp/wiki_tools.py:810` — `wiki-report-data`
- `shared-vault/skills/ingest/scripts/mcp/wiki_tools.py:923` — `wiki-report-generate`
- `shared-vault/skills/ingest/scripts/wiki_report_render.py:81` — `render_html` docstring naming the "agent step"
- `shared-vault/skills/ingest/assets/templates/report.html.j2` — Jinja2 template (restored 2026-05-11)

## 15. Governance

This brainstorming spec is the design record. After approval:

1. `/adr write` adopts this design as a numbered ADR under `get_adr_dir()`.
2. `superpowers:writing-plans` skill produces an implementation plan against the ADR.
3. Implementation executes against the plan in one PR with the five checkpoints (§9).

The brainstorming spec is not the architectural commitment — the ADR is.

## Self-review

- **Placeholder scan**: No TBDs, no TODOs. "Synthesis prompt examples" section in §6 is a structured placeholder filled in during implementation (writing the actual examples), not a design gap. The spec specifies that examples must exist; the exact prose is an authoring task.
- **Internal consistency**: §4 (contract shape) ↔ §5 (schema) ↔ §6 (slash command) ↔ §7 (validator) — all three contract surfaces describe the same field set. §9 (implementation order) maps each checkpoint to one of the surfaces.
- **Scope check**: Wiki-only (per user decision in brainstorm). Five-checkpoint implementation order is shippable in one PR. ✓
- **Ambiguity check**: "Required tier" precisely listed. Failure error precisely structured. Output path precisely specified.
