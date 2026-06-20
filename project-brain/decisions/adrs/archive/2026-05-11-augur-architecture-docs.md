# Augur Architecture Docs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver 11 contributor-facing architecture docs at `docs/architecture-<topic>.md` per the meta-spec at `docs/superpowers/specs/2026-05-11-augur-architecture-docs-design.md`, plus 4 drill-down pointers in `docs/agent-topics/`.

**Architecture:** Each doc is a self-contained markdown file matching the depth, voice, and format of the existing `docs/architecture-overview.md` and `docs/architecture-mcp-gateway.md`. Inline mermaid + ASCII diagrams only; no binary assets, no frontmatter, no new ADRs. Delivery in cluster order (Storage & Knowledge → Skill Distribution → Runtime & Surfaces → Coordination & Process), one commit per doc with the corresponding `agent-topics/` drill-down pointer bundled atomically when a counterpart exists.

**Tech Stack:** Markdown, Mermaid (rendered by GitHub), ASCII fenced code blocks. No build/test pipeline.

---

## Per-Doc Workflow Template

Every doc task in this plan follows the same six-step workflow. Defining it once here so each task below can reference it without repetition.

### Step A — Confirm load-bearing ADRs exist

For each ADR-### the doc will cite, verify it resolves in the ADR index:

```bash
grep -n "ADR-<NNN>" docs/generated/adr-index.md
```

Expected: one or more matches with the ADR's current status. If an ADR-### the spec mentions does not resolve, flag it inline in the doc with `<!-- TODO_OUTDATED: ADR-NNN not found in adr-index -->` per spec §6.1 and proceed.

If the spec did not pre-list ADRs for the topic (memory, sync-agents, capability-exposure, daemon), discover candidates by:

```bash
grep -rEn "ADR-[0-9]{3}" docs/agent-topics/<COUNTERPART>.md docs/references/ 2>/dev/null | head -30
```

…and by reading the relevant `SKILL.md` and code comments. Capture the list before writing.

### Step B — Read source files the doc will cite

Read every file the doc names as an implementation pointer or quotes from. Concrete file paths in docs are commitments — they must exist and contain what the doc claims they contain. Use the `Read` tool.

### Step C — Draft the doc

Write the full file using the spec's §4.4 skeleton:

1. Title + one-paragraph lede.
2. Load-bearing ADRs callout (matching the format used in `docs/architecture-overview.md` lines 11–20).
3. At least one primary diagram (mermaid or ASCII per spec §4.3).
4. The H2 sections listed in the task below, in order.
5. Cross-links to sibling `architecture-*.md` docs where related.
6. **Implementation pointers** closing section: bullet list of key file paths, SKILL.md / entrypoint references, MCP tools or commands involved.

Voice: technical contributor reading the OSS release, active voice, concrete paths and ADR numbers. No agent-instruction phrasing ("you must…"). No frontmatter.

### Step D — Verify per spec §6.3

Three checks before committing:

1. **Structural** — confirm the doc has all six skeleton elements above.

   ```bash
   awk '/^## /{print NR": "$0}' docs/architecture-<TOPIC>.md
   ```

   Expected: H2 headers in the order listed in the task, plus an Implementation pointers section at the end.

2. **Diagram renderability** — extract each mermaid block and confirm it parses. If `mmdc` (mermaid-cli) is installed locally:

   ```bash
   awk '/^```mermaid$/,/^```$/' docs/architecture-<TOPIC>.md > /tmp/diagram.mmd && mmdc -i /tmp/diagram.mmd -o /tmp/diagram.svg
   ```

   Expected: exit 0, SVG produced. If `mmdc` is not installed, paste each mermaid block into <https://mermaid.live> and confirm it renders without syntax errors. ASCII blocks need no check.

3. **Reference integrity** — every ADR-### resolves, every relative-path link points at a real file.

   ```bash
   # ADRs
   grep -oE "ADR-[0-9]{3}" docs/architecture-<TOPIC>.md | sort -u | while read adr; do
     grep -q "$adr" docs/generated/adr-index.md && echo "OK $adr" || echo "MISSING $adr"
   done

   # Relative paths
   grep -oE '\(\.\./?[a-zA-Z0-9_/.-]+\.md\)' docs/architecture-<TOPIC>.md | tr -d '()' | while read p; do
     [ -f "docs/$p" ] || [ -f "$p" ] && echo "OK $p" || echo "MISSING $p"
   done
   ```

   Expected: all `OK`, no `MISSING`. Fix or remove broken references before commit.

### Step E — Add drill-down pointer (only if counterpart exists)

For docs with an `agent-topics/<X>.md` counterpart (DASHBOARD, SKILLS, WIKI, AGENTS), open the agent-topics doc and add a one-line "see also" pointer near the top, after the first paragraph or the existing header block:

```markdown
> See also: [`docs/architecture-<TOPIC>.md`](../architecture-<TOPIC>.md) — system design and rationale for this subsystem.
```

The 6 docs without an agent-topics counterpart (vault, memory, sync-agents, capability-exposure, daemon, onboarding) skip this step.

### Step F — Commit

Bundle the architecture doc and (if applicable) the agent-topics drill-down pointer in one commit:

```bash
git add docs/architecture-<TOPIC>.md [docs/agent-topics/<COUNTERPART>.md]
git commit -m "docs(architecture): add architecture-<TOPIC>.md

<one-paragraph commit body summarizing what the doc covers>

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

Use `docs(architecture): add architecture-<TOPIC>.md` as the subject — matches the recent `spec(...)` / `adr(...)` commit voice in the repo.

---

## Cluster 1 — Storage & Knowledge

### Task 1: architecture-vault.md

**Files:**
- Create: `docs/architecture-vault.md`
- Modify: none (no agent-topics counterpart named "VAULT")

**ADRs to cite:** ADR-270 (path split), ADR-563 (vault-owned user skills/pages/draft staging), ADR-601 (skills moved under shared-vault), ADR-571 (frontmatter conventions).

**Files to read in Step B:** `src/config/paths.py`, `config/system/vault.yaml`, `docs/agent-topics/ARCHITECTURE.md` (for path rules context), `shared-vault/skills/vault/SKILL.md` (if exists), `docs/adrs/ADR-270.*`, `docs/adrs/ADR-563.*`, `docs/adrs/ADR-601.*`, `docs/adrs/ADR-571.*`.

**H2 sections (in order):**
1. `## ADR-270 path split`
2. `## Vault layout`
3. `## Shared vs private vault`
4. `## Frontmatter conventions and relationship discovery`
5. `## Draft staging and publish flow`
6. `## Vault sync`
7. `## Implementation pointers`

**Primary diagram:** ASCII topology diagram showing `<project_root>/` vs `get_vault_dir()` vs `get_documents_dir()` vs `get_runtime_dir()` vs `get_logs_dir()` vs `get_cache_dir()` lanes, with arrows showing what each holds.

- [ ] **Step 1: Confirm ADRs** — apply template Step A for ADR-270, 563, 601, 571.
- [ ] **Step 2: Read source files** — apply template Step B for the file list above.
- [ ] **Step 3: Draft doc** — apply template Step C with the section list above.
- [ ] **Step 4: Verify** — apply template Step D (structural, mermaid, references).
- [ ] **Step 5: Drill-down pointer** — N/A (no agent-topics counterpart).
- [ ] **Step 6: Commit** — apply template Step F.

### Task 2: architecture-wiki.md

**Files:**
- Create: `docs/architecture-wiki.md`
- Modify: `docs/agent-topics/WIKI.md` (drill-down pointer)

**ADRs to cite:** ADR-560 (semantic wiki page compiler), ADR-564 (open-source brain inbox and wiki insights), plus any inbox/RAG ADRs discovered in Step A.

**Files to read in Step B:** `docs/agent-topics/WIKI.md`, `shared-vault/skills/ingest/SKILL.md`, `shared-vault/skills/knowledge/SKILL.md`, `shared-vault/skills/rag/SKILL.md`, relevant ADR files.

**H2 sections (in order):**
1. `## Pipeline overview`
2. `## Inbox scanning and consumption`
3. `## Document extraction`
4. `## Wiki rewrite proposals and concept batches`
5. `## Wiki page compiler`
6. `## RAG reindex and search surface`
7. `## /ask retention loop`
8. `## Implementation pointers`

**Primary diagram:** Mermaid flowchart `inbox → extraction → insights → wiki pages → RAG index → /ask` with side-arrows for proposals/concepts feeding back.

- [ ] **Step 1: Confirm ADRs** — template Step A for ADR-560, 564, plus discovery for inbox/RAG.
- [ ] **Step 2: Read source files** — template Step B.
- [ ] **Step 3: Draft doc** — template Step C with the section list above.
- [ ] **Step 4: Verify** — template Step D.
- [ ] **Step 5: Drill-down pointer** — apply template Step E to `docs/agent-topics/WIKI.md`.
- [ ] **Step 6: Commit** — template Step F. Bundle WIKI.md drill-down pointer in the same commit.

### Task 3: architecture-memory.md

**Files:**
- Create: `docs/architecture-memory.md`
- Modify: none

**ADRs to cite:** discover in Step A — likely candidates: ADRs covering auto-memory, vault memory, conversation/episodic memory. Search `docs/generated/adr-index.md` for "memory".

**Files to read in Step B:** `CLAUDE.md` (auto memory section), `shared-vault/skills/knowledge/SKILL.md` (memory-search, memory-curate, decisions), `docs/agent-topics/CONTEXT.md`, the memory profile and decision-log scripts in `shared-vault/skills/knowledge/scripts/`.

**H2 sections (in order):**
1. `## The three memory tiers`
2. `## Auto-memory`
3. `## Vault memory`
4. `## Conversation and episodic memory`
5. `## Memory profile regeneration`
6. `## Decision and preference logging`
7. `## Memory search and rebuild`
8. `## Boundary rules`
9. `## Implementation pointers`

**Primary diagram:** Mermaid diagram with three lanes (auto / vault / episodic), arrows showing what flows between them and what is forbidden (e.g., session-state must NOT promote to auto-memory).

- [ ] **Step 1: Confirm ADRs** — template Step A with discovery pass.
- [ ] **Step 2: Read source files** — template Step B.
- [ ] **Step 3: Draft doc** — template Step C.
- [ ] **Step 4: Verify** — template Step D.
- [ ] **Step 5: Drill-down pointer** — N/A.
- [ ] **Step 6: Commit** — template Step F.

---

## Cluster 2 — Skill Distribution

### Task 4: architecture-skills.md

**Files:**
- Create: `docs/architecture-skills.md`
- Modify: `docs/agent-topics/SKILLS.md` (drill-down pointer)

**ADRs to cite:** ADR-522 (plugin-pack multi-target plugin assembly), ADR-567 (bundle architecture phase 0 cleanup), ADR-670 (cross-client bundle architecture), ADR-671 (cross-client bundle migration), ADR-551 (skill group and release enablement), ADR-601 (skills moved under shared-vault).

**Files to read in Step B:** `docs/agent-topics/SKILLS.md`, sample `shared-vault/skills/<X>/SKILL.md` (pick 2–3 representative skills covering different surfaces), `config/dashboard/README.md` (for hub mapping), `docs/generated/skill-manifest.json`, the bundle assembly script entrypoint under `shared-vault/skills/ai/scripts/` or wherever it lives.

**H2 sections (in order):**
1. `## Skill file structure`
2. `## Shared vs private skill placement`
3. `## Skill frontmatter contract`
4. `## Bundle assembly pipeline`
5. `## Plugin-pack multi-target assembly`
6. `## Skill group and release enablement`
7. `## Skill discovery`
8. `## Implementation pointers`

**Primary diagram:** ASCII tree showing a representative skill's file structure (SKILL.md, scripts/, dashboard/, pages/, commands/, agents/) annotated with what each subdirectory's contract is.

- [ ] **Step 1: Confirm ADRs** — template Step A for ADR-522, 567, 670, 671, 551, 601.
- [ ] **Step 2: Read source files** — template Step B.
- [ ] **Step 3: Draft doc** — template Step C.
- [ ] **Step 4: Verify** — template Step D.
- [ ] **Step 5: Drill-down pointer** — template Step E on `docs/agent-topics/SKILLS.md`.
- [ ] **Step 6: Commit** — template Step F with SKILLS.md drill-down bundled.

### Task 5: architecture-sync-agents.md

**Files:**
- Create: `docs/architecture-sync-agents.md`
- Modify: none

**ADRs to cite:** discover in Step A — search for "sync_agents", "client sync", "instruction precedence". Likely candidates include the ADRs that established per-client output formats.

**Files to read in Step B:** `shared-vault/skills/ai/scripts/sync_agents/` (entrypoint and renderer modules), `docs/architecture-mcp-gateway.md` (existing reference for what sync_agents fits into), `docs/agent-topics/agent-rules.md` (canonical source it reads), `config/system/mcp_servers.yaml` (referenced by per-client MCP generation), a sample generated file like `.cursor/rules/augur.mdc` to confirm output format.

**H2 sections (in order):**
1. `## Source → renderer → output`
2. `## Per-client output mapping`
3. `## Generated vs hand-edited boundary`
4. `## Hooks sync`
5. `## Settings sync`
6. `## Reverse direction`
7. `## Instruction precedence`
8. `## Implementation pointers`

**Primary diagram:** ASCII fan-out from the canonical sources at the top into the five client output trees at the bottom (matches the precedent of the Connection Layer diagram in `architecture-mcp-gateway.md`). Cross-link to `architecture-mcp-gateway.md` §2 explicitly — this doc deepens that section.

- [ ] **Step 1: Confirm ADRs** — template Step A with discovery pass.
- [ ] **Step 2: Read source files** — template Step B.
- [ ] **Step 3: Draft doc** — template Step C.
- [ ] **Step 4: Verify** — template Step D.
- [ ] **Step 5: Drill-down pointer** — N/A.
- [ ] **Step 6: Commit** — template Step F.

### Task 6: architecture-capability-exposure.md

**Files:**
- Create: `docs/architecture-capability-exposure.md`
- Modify: none

**ADRs to cite:** discover in Step A — search for "capability_exposure", "MCP tool exposure", "agent-vs-MCP".

**Files to read in Step B:** `config/system/capability_exposure.yaml`, `docs/references/agent-vs-mcp-checklist.md`, `docs/references/agent-vs-mcp-examples.md`, the `auto-agent-config-parity` scanner source (search `shared-vault/skills/` for the scanner), the capability table in `CLAUDE.md` (huge — that's the *output* this doc explains).

**H2 sections (in order):**
1. `## Policy and rationale`
2. `## The four exposure tiers`
3. `## capability_exposure.yaml schema`
4. `## The decision matrix`
5. `## Drift detection`
6. `## Implementation pointers`

**Primary diagram:** Mermaid decision tree: "Should this capability be a direct MCP tool? Should it be agent-mediated? CLI-via-shell? Dashboard-only?" — answers branching on user-facing vs internal, frequency, judgment required, latency tolerance.

- [ ] **Step 1: Confirm ADRs** — template Step A with discovery pass.
- [ ] **Step 2: Read source files** — template Step B.
- [ ] **Step 3: Draft doc** — template Step C.
- [ ] **Step 4: Verify** — template Step D.
- [ ] **Step 5: Drill-down pointer** — N/A.
- [ ] **Step 6: Commit** — template Step F.

---

## Cluster 3 — Runtime & Surfaces

### Task 7: architecture-dashboard.md

**Files:**
- Create: `docs/architecture-dashboard.md`
- Modify: `docs/agent-topics/DASHBOARD.md` (drill-down pointer)

**ADRs to cite:** ADR-490 (dashboard import architecture `@/` vs `@/features/`), ADR-491 (config-driven pages from YAML), ADR-540 (browse workbench redesign), ADR-541 (browse taxonomy / visibility / logs), ADR-722 (setup completeness widget), ADR-728 (browse page lifecycle ordering).

**Files to read in Step B:** `docs/agent-topics/DASHBOARD.md`, `apps/dashboard/` (top-level structure — list of `app/`, `features/`, key shared modules), `apps/dashboard/app/api/mcp/tool/route.ts` (the MCP boundary), a sample hub-generated file under `apps/dashboard/app/{hub}/`, a sample YAML-driven page declaration under `shared-vault/skills/<X>/pages/`, the block renderer entrypoint.

**H2 sections (in order):**
1. `## Import architecture (@/ vs @/features/)`
2. `## MCP-only data flow`
3. `## The /api/mcp/tool boundary`
4. `## Hub auto-generation from skill manifests`
5. `## Block renderer and config-driven pages`
6. `## Browse page taxonomy`
7. `## Setup Completeness Widget`
8. `## Implementation pointers`

**Primary diagram:** Mermaid sequence diagram showing a single user click in the dashboard → block renderer → `POST /api/mcp/tool` → MCP server → skill action → result rendered. Highlight what the dashboard never does (no `fs`, no `spawn`, no direct Python).

- [ ] **Step 1: Confirm ADRs** — template Step A for ADR-490, 491, 540, 541, 722, 728.
- [ ] **Step 2: Read source files** — template Step B.
- [ ] **Step 3: Draft doc** — template Step C.
- [ ] **Step 4: Verify** — template Step D.
- [ ] **Step 5: Drill-down pointer** — template Step E on `docs/agent-topics/DASHBOARD.md`.
- [ ] **Step 6: Commit** — template Step F with DASHBOARD.md drill-down bundled.

### Task 8: architecture-daemon.md

**Files:**
- Create: `docs/architecture-daemon.md`
- Modify: none

**ADRs to cite:** ADR-727 (background routines unified — most recent), plus discovery for Adaptive Loop Engine ADRs (search "loop engine", "adaptive loop", "promotion", "demotion").

**Files to read in Step B:** the daemon entrypoint (search `src/` and `shared-vault/skills/` for daemon launcher), the loop registry and engine source, `MEMORY.md`'s "adaptive loop engine difficulty + promotion quirks" entry for the non-obvious semantics (REPORT_ONLY_DEMOTION_THRESHOLD, --promote resets, DIFFICULTY_ESCALATION_THRESHOLD, fix:commit ratio), the notification pipeline source, CLAUDE.md rule 19 (scheduling vs orchestration boundary).

**H2 sections (in order):**
1. `## Daemon process model`
2. `## Adaptive Loop Engine`
3. `## Healing and autonomous cycles`
4. `## Loop history and status surfaces`
5. `## Notification pipeline`
6. `## Scheduling vs orchestration`
7. `## Implementation pointers`

**Primary diagram:** Mermaid state diagram for a loop's lifecycle: registered → scheduled → running → succeeded/failed → difficulty-recalculated → (promoted | demoted | retained). Annotate the threshold names.

- [ ] **Step 1: Confirm ADRs** — template Step A for ADR-727 plus discovery.
- [ ] **Step 2: Read source files** — template Step B. Memory entry on engine quirks is load-bearing — quote thresholds accurately.
- [ ] **Step 3: Draft doc** — template Step C.
- [ ] **Step 4: Verify** — template Step D.
- [ ] **Step 5: Drill-down pointer** — N/A.
- [ ] **Step 6: Commit** — template Step F.

### Task 9: architecture-onboarding.md

**Files:**
- Create: `docs/architecture-onboarding.md`
- Modify: none

**ADRs to cite:** ADR-722 (setup completeness widget — 11 milestones), ADR-729 (voice profile personalization journey).

**Files to read in Step B:** `docs/superpowers/specs/2026-05-10-setup-completeness-widget-design.md`, `docs/superpowers/specs/2026-05-11-voice-profile-personalization-design.md`, the widget component under `apps/dashboard/`, the milestone evidence sources (whichever MCP tools feed it — likely under the onboarding-related skill), `docs/architecture-overview.md` (existing reference for the 11-milestone summary).

**H2 sections (in order):**
1. `## The three phases and 11 milestones`
2. `## Milestone state model and persistence`
3. `## Setup widget lifecycle (full → compact → chip → amber)`
4. `## Voice profile personalization journey`
5. `## Milestone evidence sources`
6. `## Re-assertion and regression detection`
7. `## Implementation pointers`

**Primary diagram:** Mermaid state diagram for the widget's UI lifecycle (full card → compact bar → tiny chip → amber on regression). Optional second diagram: phase/milestone matrix.

- [ ] **Step 1: Confirm ADRs** — template Step A for ADR-722, 729.
- [ ] **Step 2: Read source files** — template Step B.
- [ ] **Step 3: Draft doc** — template Step C.
- [ ] **Step 4: Verify** — template Step D.
- [ ] **Step 5: Drill-down pointer** — N/A.
- [ ] **Step 6: Commit** — template Step F.

---

## Cluster 4 — Coordination & Process

### Task 10: architecture-agents.md

**Files:**
- Create: `docs/architecture-agents.md`
- Modify: `docs/agent-topics/AGENTS.md` (drill-down pointer)

**ADRs to cite:** discover in Step A — search for agent tiering, dispatch, orchestration, subagent. Also pull from CLAUDE.md rule 19 (judgment vs atomic operation).

**Files to read in Step B:** `docs/agent-topics/AGENTS.md`, `docs/references/dispatch-escalation-pattern.md`, `docs/references/agent-vs-mcp-checklist.md`, `docs/references/agent-vs-mcp-examples.md`, the agent registry source (search `src/` and `shared-vault/skills/`), CLAUDE.md sections on rule 19.

**H2 sections (in order):**
1. `## Agent tiering model`
2. `## Mode system and team protocol`
3. `## Dispatch and escalation pattern`
4. `## Agent-vs-MCP boundary`
5. `## Subagent dispatch`
6. `## Agent registry and capabilities`
7. `## Implementation pointers`

**Primary diagram:** Mermaid diagram showing dispatch decision flow: user request → agent receives → judgment call (delegate? parallel? escalate? direct MCP call?) → outcome. Cross-link to `architecture-capability-exposure.md` (Task 6 output) for the MCP-vs-agent boundary.

- [ ] **Step 1: Confirm ADRs** — template Step A with discovery pass.
- [ ] **Step 2: Read source files** — template Step B.
- [ ] **Step 3: Draft doc** — template Step C.
- [ ] **Step 4: Verify** — template Step D.
- [ ] **Step 5: Drill-down pointer** — template Step E on `docs/agent-topics/AGENTS.md`.
- [ ] **Step 6: Commit** — template Step F with AGENTS.md drill-down bundled.

### Task 11: architecture-sdlc.md

**Files:**
- Create: `docs/architecture-sdlc.md`
- Modify: none (no agent-topics counterpart named "SDLC")

**ADRs to cite:** discover in Step A — there is no single governing ADR. Cite the recurring decisions that shaped the pipeline: the `/adr` command spec (read `shared-vault/skills/augur-core/commands/adr.md`), the superpowers skills the doc references (`brainstorming`, `writing-plans`, `subagent-driven-development`, `executing-plans`, `using-git-worktrees`, `finishing-a-development-branch`, `verification-before-completion`, `systematic-debugging`), CLAUDE.md rules 19 (scheduling vs orchestration), 28 (browser verification), 29 (slash commands, never raw runners), and the auto-loop ADRs (search "auto-loop", "adaptive loop"). If specific ADRs surface during discovery, cite them; otherwise this doc legitimately has more reference-doc citations than ADR citations, which is acceptable per spec §6.1's `TODO_OUTDATED` allowance.

**Files to read in Step B:** `shared-vault/skills/augur-core/commands/adr.md` (the canonical `/adr` workflow spec, including Phase 0 ADR-as-index, `/adr implement`, `/adr test`, `/adr plan`, `/adr harden`, completion gates), `shared-vault/skills/augur-core/commands/dev-build.md` / `dev-merge.md` / `dev-debug.md` / `dev-loops.md` (the auto-loop catalog and its slash-command contract), the superpowers skill source under `~/.claude/plugins/cache/claude-plugins-official/superpowers/<version>/skills/` (read `brainstorming/SKILL.md`, `writing-plans/SKILL.md`, `subagent-driven-development/SKILL.md`, `using-git-worktrees/SKILL.md`, `finishing-a-development-branch/SKILL.md`, `verification-before-completion/SKILL.md`, `systematic-debugging/SKILL.md`), CLAUDE.md rules 19/28/29, `docs/superpowers/specs/` and `docs/superpowers/plans/` directories to confirm artifact-path conventions, recent ADRs that exercise the full flow (ADR-722, ADR-728, ADR-729, ADR-730 as worked examples).

**H2 sections (in order):**
1. `## The Augur SDLC pipeline` — opening prose + primary diagram
2. `## Stage 1 — Design via brainstorming`
3. `## Stage 2 — Plan via writing-plans`
4. `## Stage 3 — Governance via /adr write`
5. `## Stage 4 — Index maintenance and cross-references`
6. `## Stage 5 — Implementation via /adr implement`
7. `## Stage 6 — Auto-loops (build, lint, test)`
8. `## Stage 7 — Testing and feedback`
9. `## Stage 8 — Release`
10. `## ADRs for any work` — the universal-change-record stance: features, website updates, debugging, bug fixes, refactors, dependency bumps all flow through the same ADR-driven pipeline
11. `## Implementation pointers`

**Primary diagram:** Mermaid flowchart top-to-bottom showing the 8 stages with the artifact produced/consumed at each transition (spec → plan → ADR → indexes → worktree → loops → gates → merged branch). Include loop-back arrows: testing failure → systematic-debugging → re-verify; sub-agent task failure → debug-and-retry; ADR status flip → finishing-a-development-branch hand-off. Annotate each transition with the tool that drives it (slash command or superpowers skill).

**Cross-links to add (Step 3 → Skeleton element 5):** `architecture-agents.md` (Task 10) for how agents handle each pipeline stage, `architecture-skills.md` (Task 4) for where the slash commands live, `architecture-capability-exposure.md` (Task 6) for why some operations are CLI-via-shell vs MCP-via-dashboard, `architecture-daemon.md` (Task 8) for the loop-engine substrate that auto-loops run on.

**Section 10 — "ADRs for any work" — content guidance.** This section is the load-bearing claim of the doc and the user-stated motivation. It must be explicit, not implicit. Cover:
- The traditional "ADR" framing in industry (big architectural decisions only) and how Augur diverges (any non-trivial change).
- Concrete examples from the repo: ADR-728 (Browse page lifecycle ordering — a UI change), ADR-729 (voice profile — a feature), ADR-730 (architecture docs — pure documentation), plus a hypothetical website-update ADR, a debugging-session ADR, a dependency-bump ADR.
- The "why" — every change benefits from spec + plan + governance + index updates + completion gates + status-tracked landing. The cost of running the full SDLC for small changes is amortized by the consistency (anyone can find the record of any change via the ADR index) and by the safety (completion gates and verification-before-completion catch regressions even for "small" changes).
- The escape hatch — trivial fixes (typos, one-line CLAUDE.md edits, lint auto-fix runs) do not require an ADR. The threshold is "would a future reader want to find a record of this decision?" If yes, ADR.

- [ ] **Step 1: Confirm ADRs** — template Step A with discovery pass; expect this doc to cite reference docs and CLAUDE.md rules more than ADRs.
- [ ] **Step 2: Read source files** — template Step B with the extensive source list above.
- [ ] **Step 3: Draft doc** — template Step C. Section 10 is load-bearing; do not skimp on it.
- [ ] **Step 4: Verify** — template Step D.
- [ ] **Step 5: Drill-down pointer** — N/A (no agent-topics counterpart).
- [ ] **Step 6: Commit** — template Step F.

---

## Self-Review Notes

**Spec coverage:** Every section of the meta-spec maps to a task here.
- Spec §4 (conventions) → encoded in the per-doc workflow template above; each task inherits all conventions.
- Spec §5.1 (Cluster 1) → Tasks 1, 2, 3.
- Spec §5.2 (Cluster 2) → Tasks 4, 5, 6.
- Spec §5.3 (Cluster 3) → Tasks 7, 8, 9.
- Spec §5.4 (Cluster 4 — Coordination & Process) → Tasks 10, 11.
- Spec §6.1 (no new ADRs, `TODO_OUTDATED` markers) → encoded in template Step A.
- Spec §6.2 (one commit per doc, drill-down bundled) → encoded in template Step F.
- Spec §6.3 (3-check verification) → encoded in template Step D.
- Spec §7 (risks) → mitigations are wired into the verification steps; no separate task needed.

**Placeholders:** None. Where the spec did not pre-list ADRs (Tasks 3, 5, 6, 8, 10), the task explicitly calls for a discovery pass in Step A using a concrete grep command. This is not a placeholder — it's an instruction to discover specific ADR numbers at execution time, since the spec author legitimately did not know them.

**Type consistency:** Cross-references between tasks are explicit. Task 5 (`architecture-sync-agents.md`) cross-links to `architecture-mcp-gateway.md`. Task 10 (`architecture-agents.md`) cross-links to `architecture-capability-exposure.md` (Task 6). No mismatches between filenames as referenced across tasks.
