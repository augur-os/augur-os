---
title: "Memory Synthesis Consolidation — Wiki Compounding as the Single Engine + User-Configurable Query Registry"
type: spec
status: draft
created: 2026-05-11
authors:
  - gsannikov
related:
  - ADR-642 — Central ADR JSON index (sets the precedent for "single source of truth" registries)
  - ADR-722 — Setup Completeness Widget (milestone 6 "Set wiki compounding queries" — this spec makes that milestone meaningful)
  - ADR-727 — Background Routines (informs the "manual refresh only" decision)
  - ADR-728 — Browse Page Lifecycle Ordering (this spec adds a new Browse category)
  - ADR-729 — Voice Profile (the user-authored half of /brain/profile; this spec is the auto-derived half)
governance:
  next_step: writing-plans → /adr write (ADR-731) → /adr implement
tags:
  - memory
  - wiki
  - compounding
  - consolidation
  - context-injection
  - dashboard
  - browse
  - mcp
  - agent-synthesis
---

# Memory Synthesis Consolidation

## 1. Problem

Augur has accumulated multiple parallel "auto-derived markdown from corpus" pipelines that each solve a slice of the same problem. The current state, as surfaced by a full audit (see §4):

- **Two synthesis engines coexist.** `src/lib/knowledge/profile_generator.py` produces `HUMAN_API.md` via deterministic regex extraction from `MEMORY.md`. The wiki compounding engine (`wiki_concept_compiler`, `wiki_pages`, `ask-sync-clusters`) produces wiki pages through agent-orchestrated synthesis from inbox / source folders / `/ask` retention.
- **Three "profile of the user" surfaces.** `HUMAN_API.md` (regex-derived), `about-me.md` (user-authored via ADR-729), and Claude Code's own auto-memory `user_*` files (per-conversation). The first two render side-by-side on `/brain/profile`; the third is invisible to Augur.
- **Decisions tracked in four places.** Daily logs `decision` events, `MEMORY.md` `## Decisions` section, ADRs themselves, and Claude Code's `feedback_*` / `project_*` files.
- **No user-configurable query registry.** The wiki `page_type: query` exists in the schema (`shared-vault/skills/ingest/assets/seeds/wiki-schema/page-types.yaml`) but there is no surface for users to define, name, edit, or trigger queries. Whatever queries the engine runs today are implicit — derived from `/ask` clusters, not declared.

This spec consolidates onto **one synthesis engine** (the wiki engine, native-agent-synthesized through handoff, with a configurable query registry) and retires the parallel regex pipeline. It also adds the user-configurable wiki compounding queries feature that ADR-722 milestone 6 anticipates but never specified.

The audit also surfaced a `/adr` workflow gap (the post-write hook never upserted into the central JSON, so ADR-730 drifted out of `adrs-index.json`). That gap was fixed in-session via the new `.github/scripts/adr_upsert_live.py` and a hook contract update — it is **not** part of this spec, only noted here for context.

## 2. Goals and non-goals

### Goals

1. **One synthesis engine.** The wiki engine becomes the single mechanism that produces auto-derived markdown from accumulated corpora. The regex pipeline at `profile_generator.py` retires.
2. **User-configurable query registry.** Users can define, name, edit, refresh, and delete wiki compounding queries via `vault/wiki/queries.yaml` and the new `/brain/wiki` dashboard page. Four useful queries ship as defaults.
3. **HUMAN_API.md replacement that preserves consumers.** `context_injector` (the load-bearing consumer that injects the profile into every agent session) keeps working. Its parser swaps from "read YAML frontmatter fields" to "read named H2 sections" — same field set, different markdown surface.
4. **Path cleanup.** The profile moves from `runtime/memory/HUMAN_API.md` (Application Support, non-syncable) to `vault/wiki/profile-human-api.md` (vault, syncable, user-editable). The path migration follows from the wiki engine being the new owner.
5. **Browse discoverability.** The MEMORY.md + daily-log content surfaces as a `memory` Browse category in journey_group=knowledge so the second brain's actual content is browseable, not just dashboard-reachable.

### Non-goals

- **Daemon-scheduled refresh.** Manual only for v1. Matches the insight_scanner / ADR-727 lesson — don't auto-burn LLM tokens.
- **Sub-tabs anywhere in the dashboard.** Confirmed by scanning all 12 Accepted ADRs and their linked specs/plans — no prior decision introduces sub-tabs and this spec doesn't either.
- **Touching Claude Code's auto-memory.** That surface is owned by Claude Code's harness, not Augur. Overlap noted in §4 but out of scope for consolidation.
- **Multi-language memory profile.** Voice Profile already supports EN/HE per ADR-729 amendment, but the auto-derived memory profile (HUMAN_API replacement) is single-language for v1 — the user's interaction-corpus language. Bilingual auto-profile is a follow-on if asked.
- **Migration of `about-me.md` (Voice Profile)** — that's user-authored, not corpus-derived. Stays exactly as ADR-729 specifies. The two profile halves coexist on `/brain/profile`.
- **Retiring the daily logger or MEMORY.md.** Layers 1 (daily logs) and 2 (MEMORY.md) of the two-layer memory architecture stay. They become *sources* the wiki engine reads from, not parallel synthesis machinery.
- **Concept-page generation overhaul.** Existing `wiki_concept_compiler` keeps producing concept pages from `/ask` clusters. The new query registry adds a *named, user-driven* surface alongside the existing cluster-derived one; it does not replace it.

## 3. Decision summary

Make the wiki compounding engine the single auto-synthesis engine in Augur. Introduce a user-configurable query registry at `vault/wiki/queries.yaml`. Seed it with four default queries (`profile-human-api`, `active-projects`, `recent-decisions`, `knowledge-gaps`). Retire the regex `profile_generator.py` pipeline; the `profile-human-api` query replaces it via native-agent synthesis with structured H2 sections that match `context_injector`'s existing field set. Move the profile from `runtime/memory/HUMAN_API.md` to `vault/wiki/profile-human-api.md`. Add a `/brain/wiki` dashboard page for query CRUD + manual refresh. Add a `memory` Browse category for MEMORY.md / daily-log entries. Cutover is big-bang in one PR. No sub-tabs anywhere.

## 4. Memory surface map (audit findings)

This section is reference material — the audit landscape that motivated the consolidation. The map covers what exists *today*; subsequent sections describe what changes.

### 4.1 Storage artifacts

| # | Path | Owner | Mechanism | Mutability |
|---|---|---|---|---|
| 1 | `vault/memory/daily/YYYY-MM-DD.md` | knowledge skill (`src/lib/knowledge/daily_logger.py`) | Auto-captured raw events: `context_switch`, `decision`, `tool_execution`, `error`, `user_preference`, `pattern_detected` | Append-only (Layer 1) |
| 2 | `vault/memory/MEMORY.md` | knowledge skill (`memory-curate`) | Curated distillation of daily logs + direct entries via `memory-add-decision` / `memory-log-decision` / `memory-log-preference` | Manual + auto (Layer 2) |
| 3 | `runtime/memory/HUMAN_API.md` | knowledge skill (`src/lib/knowledge/profile_generator.py`) | **Deterministic regex** over MEMORY.md → structured frontmatter (role, expertise, communication_style, success_criteria, context_gaps) | Auto-regenerated |
| 4 | `vault/profile/{en,he}/about-me.md` | knowledge skill (ADR-729) | User-authored via `/profile interview` (Almaya 100Q + LLM compression) | Manual |
| 5 | `vault/wiki/*.md` | ingest skill (`wiki_pages.py`, `wiki_concept_compiler`) | **Agent-synthesized** prose pages: `concept`, `query`, `overview`, `topic`, `comparison`, `entity` | Auto + manual |
| 6 | `~/.claude/projects/<path>/memory/MEMORY.md` + sub-files | Claude Code harness (NOT Augur) | Per-conversation auto-memory: `user_*`, `feedback_*`, `project_*`, `reference_*` files | Auto |
| 7 | Episodic-memory plugin store | episodic-memory plugin (NOT Augur) | Conversation history search via `search-conversations` MCP | Read-only |

### 4.2 Mechanisms

- **Raw event capture (auto)** → daily logs, 6 event types.
- **Decision/preference logging (auto + manual)** → daily log entries AND MEMORY.md inserts via three MCP tools.
- **Curation (semi-auto)** → `memory-curate` distills daily logs → MEMORY.md sections.
- **HUMAN_API regeneration (auto, deterministic regex)** → reads MEMORY.md sections, infers expertise from keyword maps, writes structured-frontmatter file.
- **Voice profile authoring (manual, native-agent LLM)** → 100Q interview + Almaya Prompt 2 compression → `about-me.md`.
- **Wiki concept compilation (auto, native-agent synthesis)** → `wiki_concept_compiler` evidence-merges sources into concept pages.
- **Wiki query synthesis (auto, native-agent synthesis)** → page_type `query` exists in schema but no user-configurable registry today.
- **/ask retention (auto)** → retained `/ask` outcomes feed wiki compounding via `ask-sync-data` + `ask-sync-clusters`.
- **Claude Code auto-memory (auto, harness-owned)** → Claude updates per-conversation memory files; out of Augur's control surface.

### 4.3 Dashboard pages (all owned by knowledge skill)

| Page | Renders |
|---|---|
| `/brain/memory` | MEMORY.md viewer |
| `/brain/daily-logs` | Daily log list + reader |
| `/brain/profile` | `HumanApiProfile` component (HUMAN_API.md) + `VoiceProfile` (ADR-729) |
| `/brain/workspace` | File-shortcut opener (not a distinct artifact — opens MEMORY.md / HUMAN_API.md / daily logs in system editor) |
| `/brain/search` | Unified search across memory + wiki |
| `/brain/harness` | Augur self-diagnostics (not a memory artifact) |
| `/brain/inbox` | Inbox items |
| `/brain/insights` | Wiki-synthesized output viewer |

### 4.4 Overlaps detected

| # | Overlap | Surfaces |
|---|---|---|
| 1 | "Decisions" tracked in 4 places | daily logs, MEMORY.md `## Decisions`, ADR index, Claude Code `feedback_*` / `project_*` |
| 2 | "Preferences" tracked in 3 places | daily logs, MEMORY.md `## Preferences`, Claude Code `feedback_*` |
| 3 | "Profile of the user" — 3 parallel surfaces | HUMAN_API.md, about-me.md, Claude Code `user_*` |
| 4 | "Auto-derived synthesis from corpus" — 3 engines | `profile_generator.py` (regex), `wiki_concept_compiler` (agent-synthesized), wiki query pipeline (agent-synthesized, no registry) |
| 5 | "Raw session capture" | daily logs, episodic-memory plugin, /ask retention, Claude Code conversation history |
| 6 | Search tool layering | `memory-search` (FTS over MEMORY.md), `unified-search` (memory + wiki + docs), `wiki-search` (wiki only) |

**Overlaps addressed by this spec**: #3 (third-party Claude Code surface stays out) and #4 (regex retires, single LLM engine via query registry). Overlaps #1, #2, #5, #6 are noted; #1 and #2 are partially addressed (daily logs and MEMORY.md become sources for queries — fewer parallel synthesis machines, but the *capture* surfaces stay). Overlaps #5 and #6 are deferred to a follow-on cleanup ADR.

## 5. Architecture — single synthesis engine

The wiki compounding engine gains a **query-driven mode** that complements its existing cluster-driven mode (concept pages from `/ask` clusters). Both modes coexist:

- **Cluster-driven (existing)**: implicit, derived from `/ask` retention via `ask-sync-clusters`. Produces concept pages dynamically as clusters form.
- **Query-driven (NEW)**: explicit, declared in `vault/wiki/queries.yaml`. Produces named query pages on manual refresh.

The wiki engine reads `queries.yaml` on startup and on every `wiki-queries-write` call. Each query has:

1. A **prompt template** the engine interpolates with concatenated source content.
2. A **source list** (closed enum of `kind`s — see §6.1) the engine resolves to actual file content at run time.
3. An **output path** under `vault/wiki/` where the synthesized page lands.
4. A list of **required H2 sections** the engine validates the agent-produced output against before writing.
5. A **refresh policy** (manual only for v1).

The query runner prepares an agent handoff prompt; the active native AI client performs synthesis and submits `synthesis_markdown`; the runner validates sections and writes output. No provider call or LLM client is introduced by the runner. Direct provider calls remain out of scope unless separately approved as an explicit exception.

## 6. Query registry

### 6.1 Schema

File: `vault/wiki/queries.yaml`

```yaml
version: 1
queries:
  <query-id>:                          # kebab-case, used as identifier in MCP tools
    title:            <human-readable name>
    description:      <one-line purpose>
    prompt_template: |
      <multi-line synthesis prompt with {{sources}} placeholder>
    sources:
      - kind:         memory_md | daily_logs | ask_retention | adr_index | git_recent_commits | inbox | linked_folder
        path:         <optional path scope, e.g. specific MEMORY.md path>
        recent_days:  <optional time filter, integer>
        section:      <optional named section, for memory_md only>
        status:       <optional ADR status filter, for adr_index only>
    output:           vault/wiki/<slug>.md
    page_type:        query
    required_sections: ["Role", "Expertise", ...]   # exact H2 headers the LLM must produce
    refresh_policy:   manual            # only "manual" for v1; "weekly", "on-source-change" reserved
    system:           false             # true for system-required queries (e.g. profile-human-api); UI flags deletion warning
```

Source `kind`s are a **closed enum** — adding a new kind requires a code change (a new corpus adapter in the wiki engine). Users compose existing kinds with paths/filters in their queries; they cannot invent new kinds at config time.

Initial source-kind set:

| Kind | Reads | Adapter |
|---|---|---|
| `memory_md` | `vault/memory/MEMORY.md` (full or by section) | NEW |
| `daily_logs` | `vault/memory/daily/*.md` (filterable by recent_days) | NEW |
| `ask_retention` | retained `/ask` outcomes (existing pipeline via `ask-sync-data`) | EXTEND existing |
| `adr_index` | `docs/adrs/adrs-index.json` (filterable by status, recent_days) | NEW |
| `git_recent_commits` | `git log` output via subprocess (filterable by recent_days) | NEW |
| `inbox` | inbox folder contents (existing inbox pipeline) | REUSE existing |
| `linked_folder` | configured linked folders (existing `knowledge-linked-folders` config) | REUSE existing |

### 6.2 CRUD model

| Operation | Surface |
|---|---|
| List | `wiki-queries-list` MCP tool. Returns all queries + status (`last_run`, `last_output_size`, `source_fingerprint`, `last_error`). |
| Read one | `wiki-queries-read <id>` MCP tool. Returns the full query spec. |
| Create / edit | User edits `queries.yaml` directly, OR uses `/brain/wiki` UI which calls `wiki-queries-write`. |
| Delete | Removes entry from `queries.yaml`. Output page becomes orphaned — left in place; wiki lint surfaces it as "no query owns this page". |
| Trigger run | `wiki-queries-run <id>` MCP tool. Synchronous; returns run summary. |
| Validate | On every write, schema validation runs — required fields, valid source kinds, output-path uniqueness, no circular dependencies. |
| Seed defaults | `wiki-queries-seed-defaults` MCP tool. Idempotent. Writes the four default queries if absent; never overwrites a user-edited query of the same id. |

### 6.3 Seeded default queries

Four queries ship as the default `queries.yaml` content. Loaded via `wiki-queries-seed-defaults` on first install or via a "Seed defaults" UI button.

#### `profile-human-api` — load-bearing

```yaml
profile-human-api:
  title: "Memory Profile — What has the user been doing?"
  description: "Auto-synthesized memory profile from curated decisions and recent activity. Replaces deterministic HUMAN_API.md."
  prompt_template: |
    You are synthesizing a memory profile for an AI assistant to load as standing context.
    Read the sources below — the user's curated memory file (MEMORY.md) and recent daily activity logs.
    Produce a structured wiki query page with the following required H2 sections in order:

    ## Role
    Concise statement of what the user does professionally / functionally.

    ## Expertise
    Bulleted list of domains the evidence shows the user works in.

    ## Communication Style
    How the user prefers to interact, derived from observed patterns.

    ## Success Criteria
    What constitutes a successful working session — derived from preferences and feedback.

    ## Context Gaps
    What the AI assistant typically does not know about the user yet.

    ## Evidence
    Direct quotes / line references from the sources that ground each claim above. Cite by file:line.

    ## Source Basis
    The exact source files read, with timestamps and line counts.

    Sources:
    {{sources}}

    Do NOT invent claims unsupported by the sources. If a section has insufficient evidence, write "Insufficient data — needs more daily-log activity" rather than hallucinating.
  sources:
    - kind: memory_md
      path: vault/memory/MEMORY.md
    - kind: daily_logs
      recent_days: 30
  output: vault/wiki/profile-human-api.md
  page_type: query
  required_sections: ["Role", "Expertise", "Communication Style", "Success Criteria", "Context Gaps", "Evidence", "Source Basis"]
  refresh_policy: manual
  system: true
```

Required sections **must** match the field set `context_injector` parses. Changing this requires updating both this spec and the consumer in lockstep.

#### `active-projects` — demonstration

```yaml
active-projects:
  title: "Active Projects — What am I working on?"
  description: "Recent focus extracted from daily logs and recent commits."
  prompt_template: |
    Synthesize a snapshot of the user's current focus areas from the sources below.

    Required H2 sections:
    ## Current Threads
    ## Recent Commits Theme
    ## Open Loops
    ## Evidence
    ## Source Basis

    Sources:
    {{sources}}
  sources:
    - kind: daily_logs
      recent_days: 14
    - kind: git_recent_commits
      recent_days: 14
  output: vault/wiki/active-projects.md
  page_type: query
  required_sections: ["Current Threads", "Recent Commits Theme", "Open Loops", "Evidence", "Source Basis"]
  refresh_policy: manual
  system: false
```

#### `recent-decisions` — demonstration

```yaml
recent-decisions:
  title: "Recent Decisions — What have I decided lately?"
  description: "Digest of recent load-bearing decisions from ADRs + MEMORY.md."
  prompt_template: |
    Summarize the load-bearing decisions the user has made in the last 30 days.

    Required H2 sections:
    ## Architectural Decisions
    ## Product / Workflow Decisions
    ## Open Tensions
    ## Evidence
    ## Source Basis

    Sources:
    {{sources}}
  sources:
    - kind: adr_index
      status: [Accepted, Implemented]
      recent_days: 30
    - kind: memory_md
      section: "Decisions"
  output: vault/wiki/recent-decisions.md
  page_type: query
  required_sections: ["Architectural Decisions", "Product / Workflow Decisions", "Open Tensions", "Evidence", "Source Basis"]
  refresh_policy: manual
  system: false
```

#### `knowledge-gaps` — demonstration

```yaml
knowledge-gaps:
  title: "Knowledge Gaps — Open questions"
  description: "Recurring /ask questions without clear answers."
  prompt_template: |
    Read the retained /ask outcomes and identify questions the user has asked repeatedly that lack clear answers.

    Required H2 sections:
    ## Recurring Open Questions
    ## Patterns
    ## Suggested Investigations
    ## Evidence
    ## Source Basis

    Sources:
    {{sources}}
  sources:
    - kind: ask_retention
      recent_days: 60
  output: vault/wiki/knowledge-gaps.md
  page_type: query
  required_sections: ["Recurring Open Questions", "Patterns", "Suggested Investigations", "Evidence", "Source Basis"]
  refresh_policy: manual
  system: false
```

`profile-human-api` has `system: true` — the `/brain/wiki` UI surfaces a warning if the user attempts to delete it ("This query is required by context injection. Deleting will break agent profile loading. Use `--force` or expect to re-seed."). The other three have `system: false` and can be deleted freely.

## 7. Data flow

```
SOURCES (existing, unchanged):
  vault/memory/MEMORY.md
  vault/memory/daily/*.md
  /ask retention (via existing ask-sync-data / ask-sync-clusters)
  inbox folder
  linked folders (per knowledge-linked-folders config)
  docs/adrs/adrs-index.json
  git log

      │
      ▼
QUERY REGISTRY (new):
  vault/wiki/queries.yaml
      │
      ▼
WIKI ENGINE (existing, gains query-driven mode):
  Read query → resolve sources via adapters → concatenate +
  truncate per recent_days → prepare agent handoff prompt_template →
  agent returns synthesis → validate required H2 sections → write output

      │
      ▼
OUTPUT PAGES:
  vault/wiki/profile-human-api.md
  vault/wiki/active-projects.md
  vault/wiki/recent-decisions.md
  vault/wiki/knowledge-gaps.md
  (+ user-added queries)

      │
      ├─→ context_injector (reads profile-human-api.md H2 sections → injects into agent sessions)
      ├─→ /brain/profile (renders profile-human-api.md alongside about-me.md)
      ├─→ /brain/wiki (query management surface — list, edit, refresh, view results)
      ├─→ /brain/insights (existing wiki output viewer — query pages appear here too)
      └─→ Browse `wiki` card (lists all wiki pages including query outputs)
```

## 8. Retirement plan

| Component | Disposition |
|---|---|
| `src/lib/knowledge/profile_generator.py` | **Retire** — regex extractor deleted. Git history preserves it. |
| `src/lib/human_api_profile_parser.py` | **Refactor** — switch from YAML-frontmatter parsing to H2-section parsing. Consider relocating into `src/mcp/augur_shared/context_injector.py` since that's the only remaining consumer; if it has tests worth preserving, keep as a sibling module. |
| `runtime/memory/HUMAN_API.md` | **Deprecate location** — new home is `vault/wiki/profile-human-api.md`. The runtime path can be left as a symlink for one release, then removed; symlink target tracks the new vault path. |
| `memory-profile-regenerate` MCP tool | **Replace with thin wrapper** — tool name + capability-exposure entry stay. Implementation becomes a one-line call to `wiki-queries-run profile-human-api`. Existing callers (dashboard buttons, `/regenerate-profile` slash command) keep working without changes. |
| `knowledge-memory-profile` MCP tool (CRUD on HUMAN_API.md) | **Refactor path resolution** — `file_id="profile"` now resolves to `vault/wiki/profile-human-api.md`. CRUD surface unchanged. |
| `apps/dashboard/features/pages/brain/profile/components/HumanApiProfile.tsx` | **Refactor** — reads from new path; renders the new H2-section structure. Visual layout unchanged; only the data source and field-extraction logic shift. |
| `apps/dashboard/features/pages/brain/profile/components/HumanApiProfileSection.tsx` | **Refactor** — same pattern. |
| `apps/dashboard/features/pages/brain/profile/hooks.ts` (useHumanApiProfile) | **Refactor** — same MCP tool surface, new return shape (H2 sections instead of YAML fields). |
| Tests: `tests/.../HumanApi*`, `test_profile_generator.py`, `test_human_api_profile_parser.py` | **Replace / adapt** — `test_profile_generator.py` deletes. Parser test adapts to H2-section parsing. Dashboard component tests update to new render shape. |

## 9. Migration sequence — big-bang

One PR (the ADR-731 implementation). Sequence:

1. Add the wiki engine's query-driven mode + source adapters (new code, no consumer impact yet).
2. Add `wiki-queries-list`, `wiki-queries-read`, `wiki-queries-write`, `wiki-queries-run`, `wiki-queries-seed-defaults` MCP tools.
3. Run `wiki-queries-seed-defaults` — writes `vault/wiki/queries.yaml` with the four defaults and produces the first version of all four output pages.
4. Validate `profile-human-api.md` output covers `context_injector`'s field set by running the new parser against it.
5. Swap `context_injector` to read from `vault/wiki/profile-human-api.md` via the new parser.
6. Refactor dashboard components / hooks to point at the new path + shape.
7. Refactor `memory-profile-regenerate` into a thin shim that calls `wiki-queries-run profile-human-api`.
8. Add the `/brain/wiki` dashboard page.
9. Add the `memory` Browse category.
10. Retire `profile_generator.py`. Delete `runtime/memory/HUMAN_API.md` (the file moves to vault; the runtime path is gone, no symlink).
11. Update CLAUDE.md rule about memory paths if any reference points at runtime/memory/HUMAN_API.md.
12. Tests pass; ship.

A one-time A/B comparison test (kept in `tests/migration/`, deleted post-merge) runs both the old regex pipeline and the new wiki query in a sandbox, diffs the structured output, and confirms field coverage. This is verification, not a transitional gate — it's a PR-review tool.

## 10. Dashboard surfaces

### 10.1 `/brain/wiki` (NEW)

Query management page. Owned by **ingest skill** — the wiki engine and all `wiki-*` MCP tools live in ingest. The `/brain/` hub mount stays consistent (the dashboard hub-routing collapses skill ownership into the `/brain/*` URL space), so the user-visible URL is the same regardless.

Layout — single layer, no sub-tabs:

```
┌─ Wiki Queries ──────────────────────────────────────────────┐
│  [+ New query]   [Seed defaults]                            │
│                                                             │
│  ┌─ profile-human-api (system) ──────────────────────────┐  │
│  │  Memory Profile — What has the user been doing?       │  │
│  │  ● Last run: 2 hours ago    Sources: MEMORY.md, daily │  │
│  │  Output: vault/wiki/profile-human-api.md              │  │
│  │  [Refresh]  [Edit]  [View output]                     │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌─ active-projects ─────────────────────────────────────┐  │
│  │  ...                                                  │  │
│  └───────────────────────────────────────────────────────┘  │
│  ...                                                        │
└─────────────────────────────────────────────────────────────┘
```

Each query card shows: title, freshness indicator (`●` green/amber/red — green = current with sources, amber = sources changed since last run, red = errored), inline source list, action buttons. Click `Edit` → opens an inline editor with the YAML query spec. Click `View output` → navigates to `/brain/insights` filtered to that page (or to the wiki page directly).

### 10.2 `/brain/profile` (refactored)

Renders three cards stacked:

1. Voice Profile (EN) — `vault/profile/en/about-me.md` (ADR-729)
2. Voice Profile (HE) — `vault/profile/he/about-me.md` (ADR-729 amendment)
3. Memory Profile — `vault/wiki/profile-human-api.md` (this spec)

Card 3 renders the H2 sections (Role, Expertise, Communication Style, Success Criteria, Context Gaps) as labeled chips/blocks rather than a YAML-frontmatter render. Visual style consistent with the Voice Profile cards.

### 10.3 Browse — `memory` category (NEW)

Added to `BROWSE_CATEGORIES`:

```typescript
{
  id: "memory",
  label: "Memory",
  singularLabel: "Memory Entry",
  icon: "Brain",
  devOnly: false,
  group: "content",
  journey_group: "knowledge",
  journey_order: 5,     // after notes=1, wiki=2, pages=3 (ADR-723), profile=4 (ADR-729). wiki-queries are page-only, not in Browse.
  viewLayout: "card",
}
```

Each card represents one logical memory entry — a MEMORY.md decision/preference section line OR a daily-log entry. Browse list view filters by source (MEMORY.md vs daily logs) and by section (Decisions / Preferences / Patterns / etc.).

Wiki queries do **not** appear as a Browse category. They are configuration, not content. Their *outputs* appear in the existing `wiki` card naturally.

## 11. MCP tool changes

### 11.1 New tools (ingest skill)

| Tool | Args | Returns |
|---|---|---|
| `wiki-queries-list` | none | Array of query specs + status (last_run, source_fingerprint, last_error) |
| `wiki-queries-read` | `id: string` | Full query spec |
| `wiki-queries-write` | `id: string, spec: object` | Validates + writes to `queries.yaml`; returns confirmation |
| `wiki-queries-run` | `id: string` initially; `id: string, synthesis_markdown: string` on submit | First call prepares an agent handoff prompt; second call validates agent-produced synthesis, writes output, and returns run summary (sections validated, output path, errors) |
| `wiki-queries-seed-defaults` | none | Idempotent seed of the four default queries; returns which were newly written vs already present |

Capability-exposure entries under `config/system/capability_exposure.yaml` — all five tools owned by `ingest` skill. `wiki-queries-list` exposed to `mcp via dashboard` (read-only safe). `wiki-queries-write` and `wiki-queries-run` exposed to `cli via shell` (write actions, follow the agent-mediation pattern per `references/agent-vs-mcp-checklist.md`).

### 11.2 Refactored tools (knowledge skill)

| Tool | Change |
|---|---|
| `memory-profile-regenerate` | Implementation swaps from `regenerate_human_api_profile()` call to `wiki-queries-run("profile-human-api")` call. Public contract unchanged. |
| `knowledge-memory-profile` (CRUD) | `file_id="profile"` path resolution updates from `runtime/memory/HUMAN_API.md` to `vault/wiki/profile-human-api.md`. |
| `knowledge-memory-workspace-open` | `file_id="profile"` and `"report"` resolutions update to the new vault path. |

### 11.3 Retired internal modules

- `src/lib/knowledge/profile_generator.py` — deleted.
- `src/lib/human_api_profile_parser.py` — either deleted (if absorbed into `context_injector`) or refactored to parse H2 sections.

No MCP tools are deleted — `memory-profile-regenerate` retains its name and capability-exposure entry, just becomes a wrapper. This preserves all existing callers (dashboard buttons, `/regenerate-profile` slash command, anything that scripts against the MCP).

## 12. Edge cases and risks

### Edge cases

- **Empty corpus.** Query produces a "Insufficient data — needs more daily-log activity" stub page rather than a hallucinated profile. The validation step (required H2 sections present) still passes — the handoff prompt instructs the agent to write the placeholder text in each section when evidence is thin.
- **Token budgeting.** Daily logs over 30 days can exceed prompt budgets. The `daily_logs` adapter applies tail-N truncation (most recent first) when the concatenated source exceeds a configurable budget (default 100K tokens). The handoff prompt includes a truncation marker so the agent knows older content was elided.
- **Manual user edits to output pages.** Next refresh overwrites them. Matches current behavior (regex pipeline also fully regenerates). Users who want hand-edits should edit `MEMORY.md` (the source), not the synthesized page. The `/brain/wiki` UI surfaces this warning before manual refresh of a recently-edited page.
- **`queries.yaml` schema errors.** Wiki engine refuses to run with an invalid `queries.yaml` and surfaces the validation error in the dashboard. The previous good version of `queries.yaml` is preserved as `.queries.yaml.last-valid` for quick rollback.
- **Concurrent refresh of the same query.** `wiki-queries-run` acquires a per-query lock; a second concurrent call returns "already running, run_id=X" rather than starting a second synthesis.
- **Agent handoff failure.** Run records `last_error`; output page is not overwritten. UI surfaces error state on the query card.

### Risks

- **`context_injector` parser regression.** Changing the parser is a hot-path change — every agent session touches it. Mitigation: the migration's step 4 (validate output covers field set) runs before step 5 (parser swap). The A/B comparison test in `tests/migration/` documents the field-set equivalence.
- **Agent output drift.** If the agent output stops producing the required H2 sections, queries fail validation and outputs aren't written. Stale outputs remain in place. Mitigation: validation surfaces the error early; the prompt template is explicit about required sections; system queries (`profile-human-api`) get extra UI attention when they fail.
- **Cost.** Each query refresh consumes native AI-client reasoning. Direct provider/API cost is zero in the default path and allowed only for separately approved exceptions. Mitigation in the spec: manual-only refresh policy.
- **Vault path migration.** Moving `HUMAN_API.md` from `runtime/memory/` to `vault/wiki/` means it now syncs across machines via the vault repo. If a user has multiple machines, the wiki page replicates. The first sync may produce a merge if both machines regenerated independently — standard vault-merge handling applies, but it's a new vector. Mitigation: documented; vault.yaml already handles wiki/ sync; we're not introducing new infrastructure.

## 13. Out of scope (deferred follow-ons)

| Item | Why deferred |
|---|---|
| Memory surface cleanup — retire `knowledge-memory-workspace`, rationalize `knowledge-memory-*` vs `memory-*` tool naming, retire `human_api_profile_parser.py` if absorbed | Cleanup, not load-bearing; separate ADR (proposed: ADR-732) |
| Daemon-scheduled refresh policies (`weekly`, `on-source-change`) | Manual only for v1 per ADR-727 lesson |
| Concept-page generation overhaul | Existing cluster-driven mode stays; query registry adds named queries alongside it |
| Multi-language auto-derived memory profile | Single-language for v1; if needed, follow-on adds `language` field to query spec |
| Claude Code auto-memory unification | Out of Augur's control surface — `~/.claude/projects/...` is owned by Claude Code's harness |
| Search tool layer consolidation (`memory-search` vs `unified-search` vs `wiki-search`) | Real overlap noted in §4 but separable from synthesis consolidation; deferred to memory-cleanup ADR |
| Migration of `about-me.md` (Voice Profile) into wiki | It's user-authored, not corpus-derived. Wiki is for synthesis. Stays in `vault/profile/<lang>/about-me.md` per ADR-729 |

## 14. Alternatives considered

| Alternative | Why rejected |
|---|---|
| Storage-only unification (move HUMAN_API.md into wiki/ but keep regex) | Doesn't actually unify the synthesis engine; we'd still have two engines, just one of them happens to write into wiki/. No quality gain. |
| Full native-agent prose-only output (no structured sections) | Big blast radius for `context_injector` and downstream agents that consume field-shaped data. Forces all consumers to migrate to prose parsing simultaneously. The hybrid (structured H2 sections produced by the agent and validated by tools) preserves the consumer interface. |
| Read-old-write-new staged migration | Feeding a regex extraction back into agent synthesis is architectural mush. Staged migrations buy safety we don't need — git revert is always available. |
| Daemon-scheduled refresh in v1 | insight_scanner / ADR-727 lesson. Auto-burning LLM tokens silently is exactly the failure mode that lesson cites. |
| `/brain/sources` page (source-centric) | Sources have no meaning except relative to queries. Standalone source management is an orphan abstraction. Sources surface inline per query on `/brain/wiki` instead. |
| Sub-tabs on wiki Browse card to separate Pages / Queries | Scanned all 12 Accepted ADRs — none introduce sub-tabs. Wiki queries are configuration (page-only), wiki pages are content (Browse). Keeping them separate by purpose rather than nesting by tab. |
| Memory as part of `notes` Browse category | MEMORY.md is structurally distinct from notes — it's curated decisions/preferences, not free-form notes. Separate Browse card clarifies the surface. |
| Folding the entire consolidation into ADR-729 | ADR-729 is about Voice Profile (user-authored). The memory-synthesis-via-wiki refactor is a separate concern affecting different consumers and pipelines. Mixing them grows ADR-729 unnecessarily. |

## 15. References

- ADR-642 — Central ADR JSON index (the "single source of truth" precedent this spec mirrors for queries.yaml)
- ADR-722 — Setup Completeness Widget (milestone 6 anticipates user-configurable wiki queries; this spec ships that feature)
- ADR-727 — Background Routines (informs the manual-refresh-only decision)
- ADR-728 — Browse Page Lifecycle Ordering (adds `memory` Browse category at order 6 in journey_group=knowledge)
- ADR-729 — Voice Profile Personalization Journey (the user-authored half of `/brain/profile`; this spec is the auto-derived half)
- `shared-vault/skills/ingest/assets/seeds/wiki-schema/page-types.yaml` — defines `page_type: query`
- `shared-vault/skills/ingest/scripts/wiki_concept_compiler` — the existing agent-orchestrated synthesis engine the query-driven mode extends
- `src/lib/knowledge/daily_logger.py` — Layer 1 daily logger (becomes a source for queries)
- `src/lib/knowledge/profile_generator.py` — retiring; the regex pipeline
- `src/lib/human_api_profile_parser.py` — refactoring to H2-section parser
- `src/mcp/augur_shared/context_injector.py` — the load-bearing consumer; parser swap target
- `apps/dashboard/lib/browse/types.ts` — Browse categories registry
- CLAUDE.md rule 1 (user-visible correctness — the migration's A/B test enforces field-set equivalence before consumer swap)
- CLAUDE.md rule 11 (dashboard uses MCP — `/brain/wiki` follows the same MCP-only data flow as existing pages)
- CLAUDE.md rule 29 (slash commands, not raw runners — applies to dev workflow, not this user-facing consolidation)

## 16. Governance

This brainstorming spec is the design record. After approval:

1. `/superpowers:writing-plans` produces the multi-task implementation plan covering the steps in §9.
2. `/adr write` adopts this design as **ADR-731** (thin index ADR pointing at spec + plan).
3. `/adr implement ADR-731` drives the plan through worktree + subagent-driven flow.
4. Completion gates run per the standard `/adr` workflow.
5. Memory surface cleanup follow-on (ADR-732) drafts after ADR-731 lands and the deferred items in §13 stabilize.

## 17. Self-review

- **Placeholder scan**: No TBDs. The default-query prompt templates in §6.3 are intentionally verbatim and complete — they're the canonical content that ships in `queries.yaml`.
- **Internal consistency**: §3 decision summary ↔ §5 architecture ↔ §6 registry ↔ §7 data flow ↔ §8 retirement ↔ §9 migration sequence — all reference the same artifacts (`vault/wiki/queries.yaml`, `vault/wiki/profile-human-api.md`, the four default queries, the H2-section field set).
- **Scope check**: One PR sized for ~10 implementation steps in §9; field-set parity for `context_injector` is the only hot-path concern, and it's covered by the A/B test in step 4. ✓
- **Ambiguity check**: Required H2 section set is explicit in §6.3 for each default query. Source kinds are a closed enum. `system: true` deletion behavior is specified. Manual-refresh-only is unambiguous. ✓
- **No sub-tabs**: Verified by scanning all 12 Accepted ADRs and their linked specs; this spec doesn't introduce any either.
