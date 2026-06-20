---
title: "Augur Architecture Docs — Meta-Spec for 10 Topic Docs Across 4 Clusters"
type: spec
status: draft
created: 2026-05-11
authors:
  - gsannikov
related:
  - docs/architecture-overview.md — existing precedent for voice/depth/format
  - docs/architecture-mcp-gateway.md — existing precedent for inline ASCII topology diagrams
  - docs/agent-topics/ — agent-facing rule docs that gain drill-down pointers
  - docs/generated/adr-index.md — load-bearing ADR resolution
governance:
  next_step: writing-plans → implementation (write 10 docs in cluster order, one commit per doc)
tags:
  - architecture
  - documentation
  - meta-spec
  - oss-release
---

# Augur Architecture Docs — Meta-Spec

## 1. Problem

Augur has two architecture documents under `docs/` — `architecture-overview.md` (the Harness, the five layers, the Inversion, the browse page, the onboarding journey) and `architecture-mcp-gateway.md` (the Connection Layer's seven channels). They are public-release-quality, written for technical contributors and OSS readers, and serve as the canonical reference for those subsystems.

The rest of Augur's architecture has no equivalent. Vault layout, wiki compounding, memory tiers, skill anatomy, bundle assembly, `sync_agents` projection, capability exposure, dashboard data flow, daemon and Adaptive Loop Engine, onboarding state machine, and agent tiering / dispatch all exist as working code, scattered ADRs, and agent-facing topic rules under `docs/agent-topics/` — but no contributor-facing architectural explanation.

This meta-spec defines the conventions and section outlines for **11 new `docs/architecture-<topic>.md` files**, grouped into **4 clusters**, that close that gap.

## 2. Goals and non-goals

### Goals

- Produce 11 contributor-facing architecture docs matching the depth, voice, and format of `architecture-overview.md`.
- Fix the recurring decisions (file location, naming, audience, diagram tooling, doc skeleton, frontmatter, cross-link conventions, ADR strategy) once in this spec so the 10 docs are coherent rather than each re-litigating them.
- Make every doc self-contained for a reader who has not read the others, while cross-linking related docs and ADRs.
- Add a one-line "see also" drill-down pointer from each `agent-topics/<X>.md` that has an `architecture-<X>.md` counterpart, so an agent loading the rules doc has a clear path to the design doc.

### Non-goals

- **No new ADRs.** These docs explain existing decisions; they do not make new ones. Gaps surface as `TODO_OUTDATED` markers.
- **No consolidation of `agent-topics/`.** Rules-for-agents and design-for-humans stay as separate surfaces. The only coupling is the one-line drill-down pointer.
- **No binary diagram assets.** Inline mermaid and ASCII only.
- **No changes to `sync_agents`, generated per-client files, or the dashboard build pipeline.**
- **No new subdirectory.** Flat `docs/architecture-<topic>.md` matches existing precedent and the OSS allowlist's URL stability requirement.

## 3. Decisions made during brainstorming

Two structural choices were made during the brainstorming session that drove this spec:

**Slicing — clustered (over per-doc or single-mega-spec).** Ten docs is too many for one design spec (contradictions slip through) and too few for ten independent brainstorming cycles (each cycle would re-decide the same conventions). Clustering by topical adjacency (data → projection → user-facing → coordination) lets related docs share context and lets recurring decisions get made once here.

**Relationship to `agent-topics/` — complement + drill-down link (over ignore-and-duplicate or consolidate).** Consolidation would refactor the `sync_agents` projection pipeline that generates per-client instructions for five AI clients — too much blast radius for a documentation pass. Ignoring agent-topics leaves an agent reading the rules with no signpost to the design rationale. A one-line "see also" pointer is additive, low-risk, and gives agents a clear drill-down path when they need more context than the rules doc provides.

## 4. Shared conventions

These apply to all 10 docs.

### 4.1 File layout & naming

- Flat: `docs/architecture-<short-noun>.md`. Same level as the existing two.
- Short nouns over hyphenated phrases (e.g., `architecture-vault.md`, not `architecture-vault-layout-and-sync.md`).
- URL stability matters — these paths are in the OSS public-release allowlist.

### 4.2 Audience & voice

- Technical contributor reading the OSS release. Not an agent following rules.
- Active voice. Concrete file paths, concrete ADR-### numbers, concrete component names.
- Avoid agent-instruction phrasing ("you must…", "do NOT…"). Use descriptive prose ("the daemon …", "the bundle assembler …").
- Match the tone of `architecture-overview.md` and `architecture-mcp-gateway.md` exactly.

### 4.3 Diagram tooling

Inline only. Two formats:

- **Mermaid** for flows, state machines, sequences, dependency graphs — anything with directed edges or temporal order.
- **ASCII fenced code blocks** for topology diagrams with many parallel lanes (matches the Connection Layer diagram in `architecture-mcp-gateway.md`, which mermaid renders poorly).

Each doc has at least one primary diagram. Subsystems may have additional smaller diagrams for zooming in.

### 4.4 Doc skeleton

Every architecture doc follows this structure:

1. **Title + one-paragraph lede** — what this is and why it matters.
2. **Load-bearing ADRs** — bulleted list of ADR-### + one-line purpose. Format matches `architecture-overview.md` lines 11–20.
3. **Primary diagram** — mermaid or ASCII, depending on the subject.
4. **Numbered or named sections** covering each major subsystem or flow.
5. **Cross-links** — inline `[architecture-<sibling>.md](./architecture-<sibling>.md)` references where related architecture docs exist.
6. **Implementation pointers** — closing section with key file paths, the SKILL.md or daemon entrypoint to read, the MCP tools or commands involved.

### 4.5 Frontmatter

None. Matches the existing two architecture docs. Rule 16 of CLAUDE.md (user-facing files use frontmatter) applies to ADRs, actions, vault files, and generated agent Markdown — not to top-level `docs/architecture-*.md`.

### 4.6 Cross-links and drill-down pointers

- **Architecture-to-architecture.** Inline relative-path links where related. No central index; the docs reference each other as needed.
- **agent-topics → architecture.** For each `agent-topics/<X>.md` that has an `architecture-<X>.md` counterpart, add a one-line "see also" near the top of the agent-topics doc. We update only the files where a counterpart actually exists — no blanket sweep.
- **ADR references.** Cite ADR-### inline; verify against `docs/generated/adr-index.md`.

## 5. The 10 docs, organized by cluster

Delivery order is top-to-bottom: Cluster 1 first, Cluster 4 last. Within a cluster the docs can land in any order. Each entry below specifies the doc filename, its anchor concept, and the H2 sections the doc will use (the section list locks scope — see §7 risks).

### 5.1 Cluster 1 — Storage & Knowledge (3 docs)

**`architecture-vault.md`** — How the vault stores user-editable content and how it's separated from code/runtime.

Sections:
- ADR-270 path split (project, vault, documents, runtime, logs, cache)
- Vault layout (`skills/`, memory, drafts, archive)
- Shared vs private vault (ADR-563 / ADR-601)
- Frontmatter conventions (ADR-571) and relationship discovery
- Draft staging and publish flow
- Vault sync (`vault.yaml`, `/dev-merge full` coverage)
- Implementation pointers

**`architecture-wiki.md`** — How user inputs compound into queryable knowledge.

Sections:
- Pipeline overview diagram (inbox → extraction → insights → wiki pages → RAG index)
- Inbox scanning and consumption
- Document extraction (OCR, summarization, URL/YouTube/podcast ingest)
- Wiki rewrite proposals and concept batches
- Wiki page compiler (ADR-560)
- RAG reindex and search surface
- `/ask` retention loop
- Implementation pointers

**`architecture-memory.md`** — The three memory tiers and how they relate.

Sections:
- Auto-memory (per-project, agent-managed)
- Vault memory (durable, user-curated)
- Conversation / episodic memory (session-scoped)
- Memory profile regeneration
- Decision and preference logging
- Memory search and rebuild
- Boundary rules (what goes where, what never gets memorized)
- Implementation pointers

### 5.2 Cluster 2 — Skill Distribution (3 docs)

**`architecture-skills.md`** — Anatomy of a skill and how skills assemble into bundles.

Sections:
- Skill file structure (`SKILL.md`, `scripts/`, `dashboard/`, `pages/`, `commands/`, `agents/`)
- Shared vs private skill placement
- Skill frontmatter contract (`x-augur-mcp-tools`, `x-augur-hub`, etc.)
- Bundle assembly pipeline (ADR-522, ADR-567, ADR-670, ADR-671)
- Plugin-pack multi-target assembly
- Skill group and release enablement (ADR-551)
- Skill discovery (manifest, registry, browse)
- Implementation pointers

**`architecture-sync-agents.md`** — How one source tree projects into N client formats.

Sections:
- Source → renderer → output diagram (5 clients)
- Per-client output mapping (Claude Code, Codex, Gemini, Cursor, Copilot)
- Generated vs hand-edited boundary (`CLAUDE.md`, `.cursorrules`, etc. are generated)
- Hooks sync (cross-agent git hooks)
- Settings sync (per-client config gen)
- Reverse direction (clients writing back to vault)
- Instruction precedence (project > global)
- Implementation pointers

**`architecture-capability-exposure.md`** — Why most MCP tools are agent-only, not directly client-exposed.

Sections:
- The capability exposure policy and its rationale
- Direct MCP tools vs agent-mediated vs CLI-via-shell vs dashboard-only
- `config/system/capability_exposure.yaml` schema
- The decision matrix (when to expose where) — pulls from `references/agent-vs-mcp-checklist.md`
- Drift detection (auto-agent-config-parity scanner)
- Implementation pointers

### 5.3 Cluster 3 — Runtime & Surfaces (3 docs)

**`architecture-dashboard.md`** — How the Next.js dashboard renders data without touching the OS.

Sections:
- Import architecture (ADR-490 — `@/` framework vs `@/features/`)
- MCP-only data flow (no `fs`, no `spawn`, no direct Python)
- `POST /api/mcp/tool` boundary
- Hub auto-generation from skill manifests
- Block renderer and config-driven pages (ADR-491)
- Browse page taxonomy (ADR-540, ADR-541)
- Setup Completeness Widget (ADR-722) — sidebar surface
- Implementation pointers

**`architecture-daemon.md`** — Background runtimes, adaptive loops, healing.

Sections:
- Daemon process model
- Adaptive Loop Engine (loop registry, difficulty escalation, promotion, demotion thresholds)
- Healing / autonomous cycles
- Loop history and status surfaces
- Notification pipeline (plugin events, expiry, dismissal)
- Scheduling vs orchestration (daemons schedule, agents orchestrate — CLAUDE.md rule 19)
- Implementation pointers

**`architecture-onboarding.md`** — The 11-milestone journey state machine.

Sections:
- Three phases (Foundation, Knowledge, Personalization) — ADR-722
- Milestone state model and persistence
- Setup widget lifecycle (full card → compact bar → tiny chip → amber regression)
- Voice profile personalization journey (ADR-729)
- Milestone evidence sources (what counts as "done")
- Re-assertion / regression detection
- Implementation pointers

### 5.4 Cluster 4 — Coordination & Process (2 docs)

**`architecture-agents.md`** — How agents are tiered, dispatched, and orchestrated.

Sections:
- Agent tiering model (from `agent-topics/AGENTS.md`)
- Mode system and team protocol
- Dispatch / escalation pattern (from `references/dispatch-escalation-pattern.md`)
- Agent-vs-MCP boundary (judgment vs atomic operation — CLAUDE.md rule 19)
- Subagent dispatch (when to delegate, parallelization rules)
- Agent registry and capabilities surface
- Implementation pointers

**`architecture-sdlc.md`** — Augur's internal software development lifecycle: how any unit of work moves from idea to ship.

The doc covers the full pipeline that Augur uses for every change, regardless of scope. Architectural decisions, new features, website updates, dashboard tweaks, bug fixes, debugging sessions, refactors, dependency bumps — all flow through the same 8-stage pipeline anchored on the ADR governance model. The "ADRs for any work" stance is the load-bearing claim of this doc: ADR-### is the universal change record in Augur, not a "big architectural decisions only" surface.

Sections:
- The Augur SDLC pipeline (primary diagram)
- Stage 1 — Design via `superpowers:brainstorming` → spec at `docs/superpowers/specs/`
- Stage 2 — Plan via `superpowers:writing-plans` → plan at `docs/superpowers/plans/`
- Stage 3 — Governance via `/adr write` → thin index ADR pointing at spec + plan
- Stage 4 — Index maintenance (post-write hook: `generate_adr_index.py`, `unified_indexer.py --category adrs`, `sync_agents sync agents all`) and cross-references to prior ADRs that the new ADR supersedes or relates to
- Stage 5 — Implementation via `/adr implement` → worktree + `superpowers:subagent-driven-development` + native Team primitives for parallel-safe clusters
- Stage 6 — Auto-loops as the build/lint/test substrate (`/dev-build`, `/auto-lint`, `/auto-test-pytest`, `/auto-test-build`, `/auto-test-dashboard`, the `/dev-loops` catalog — CLAUDE.md rule 29: never invoke raw `pytest` / `pnpm dev`)
- Stage 7 — Testing + feedback (`/adr test`, completion gates from `/adr implement`, browser verification per CLAUDE.md rule 28)
- Stage 8 — Release (`/dev-merge`, `/adr set <N> Implemented`, `superpowers:finishing-a-development-branch`)
- ADRs for any work — why features, website updates, debugging sessions, bug fixes, refactors, and dependency bumps all go through the same ADR-driven flow (the universal-change-record stance)
- Cross-links to `architecture-agents.md`, `architecture-skills.md`, `architecture-capability-exposure.md`, `architecture-daemon.md`
- Implementation pointers (key slash commands, the superpowers skill set, the `/adr` workflow phases, the auto-loop registry source)

The primary diagram is a Mermaid flowchart of the 8 stages with artifacts and loop-back arrows (testing failure → fix → re-verify; sub-agent task failure → systematic-debugging → retry).

## 6. ADR strategy, commit cadence, verification

### 6.1 ADR strategy

No new ADRs in this work. Each architecture doc opens with a "Load-bearing ADRs" callout listing existing ADR-### numbers with one-line purposes. If, while writing a doc, the author discovers a topic whose architecture has no governing ADR (a documented behavior that was never formally decided), they flag it inline as a `TODO_OUTDATED` marker referencing the gap. ADR creation goes through `/adr` separately, in a subsequent pass — not bundled into the same commit.

### 6.2 Commit cadence

One commit per doc. Each commit also includes the corresponding `agent-topics/<X>.md` drill-down pointer update when a counterpart exists. Cluster boundaries are not commit boundaries — the architecture doc and its drill-down pointer land atomically.

Commit message format: `docs(architecture): add architecture-<topic>.md` (matches the existing voice in recent commits).

### 6.3 Verification per doc

Three checks before each commit:

1. **Structural** — has lede paragraph, load-bearing ADRs block, at least one primary diagram, named sections, implementation pointers, cross-links to siblings where relevant.
2. **Diagram renderability** — paste each mermaid block into the GitHub mermaid live preview (or `mmdc` if installed locally) to catch syntax errors before pushing. ASCII blocks need no check.
3. **Reference integrity** — every ADR-### cited resolves in `docs/generated/adr-index.md`; every relative path link points at a file that exists.

No build or test gate. Markdown docs do not trigger a Next.js rebuild and do not interact with `/dev-build`, `/auto-test-*`, or the auto-loop matrix.

## 7. Risks and mitigations

- **Mermaid syntax errors invisible until GitHub renders them.** Step 2 of §6.3 catches them before commit.
- **Scope creep within a doc** — e.g., `architecture-wiki.md` ballooning into the full RAG architecture. The section outline in §5 is the contract; if a doc needs more sections than listed, that's a scope change requiring a meta-spec amendment, not a silent expansion.
- **Drift between `agent-topics/` and `architecture-*.md`.** By design; we are not consolidating. The drill-down pointer is the only coupling. If the agent-topics doc gets edited and the architecture doc goes stale, that's a normal documentation maintenance burden, not a contradiction in the design.
- **ADR numbering churn** — low risk (numbers are stable post-acceptance), but the `docs/generated/adr-index.md` check in §6.3 catches breakage if an ADR is renumbered or retired.
- **Public-release URL stability** — flat `docs/architecture-<topic>.md` filenames match the precedent set for the OSS allowlist. No path migration needed.
- **Author discovers an architectural gap** — `TODO_OUTDATED` marker per §6.1, deferred to a separate `/adr` pass. Do not block doc landing on ADR creation.

## 8. Open questions

None at this time. The slicing strategy (clustered) and the relationship to `agent-topics/` (complement + drill-down link) were settled during brainstorming. Section outlines for all 10 docs are locked above. Per-doc content decisions are author-time judgment calls, not meta-spec questions.

## 9. Next step

Invoke the **writing-plans** skill to produce the implementation plan that delivers the 10 docs in cluster order, one commit per doc, with the verification checks from §6.3 wired into the per-doc workflow.
