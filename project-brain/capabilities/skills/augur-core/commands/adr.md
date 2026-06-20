---
description: Project-scoped Architecture Decision Record workflow. Use through /project adr.
visibility: project
x-augur-export-command: false
x-augur-parent-command: project
x-augur-project-verb: adr
---

# /project adr
<!-- AUGUR_ARGUMENT_CONTRACT_V1 -->
## Argument Handling (Auto)

1. Parse runtime arguments from `$ARGUMENTS`.
2. If `$ARGUMENTS` is empty, parse text after `/project adr` in the user request.
3. Preserve argument tokens exactly (including flags and order).
4. If arguments are present, execute the matching sub-command/flag path in this command.
5. Only use the command's default behavior when arguments are truly empty.
6. If arguments are unrecognized, return valid usage instead of silently defaulting.

This command body is no longer a top-level slash command. It executes only when `/project adr` dispatches to it after the project status gate passes.

Manage Architecture Decision Records (ADRs). Query by status, update statuses, search, create new ADRs, write thin index ADRs that point at superpowers spec + plan, implement ADRs (or standalone plan files) through the active implementation worktree + subagent-driven flow with native team primitives for parallel clusters, test implementations, convert orphan plans to ADRs, and run hardening audits.

## Usage

```
/project adr                           → list live (non-archived) ADRs — open/active work (default)
/project adr live                      → same as bare /project adr — list live ADRs
/project adr status                    → show status summary with counts
/project adr list <status>             → list ADRs filtered by status
/project adr recent [N]                → show N most recent ADRs across all states (default 10)
/project adr latest [N]                → alias for /project adr recent
/project adr set <number> <status>     → update an ADR's status
/project adr search <query>            → search ADR titles for keyword
/project adr new <title>               → create a new ADR from template
/project adr write <description>       → write ADR from an existing spec/plan; create the missing spec first when absent
/project adr implement <ADR-NNN | plan-file>  → execute via superpowers worktree + subagent-driven flow
/project adr test [ADR-NNN]            → test ADR implementation against acceptance criteria
/project adr plan                      → scan docs/plans/ for orphaned designs, generate ADRs
/project adr harden <target>           → audit a skill or hub, generate hardening ADR
/project adr gaps <ADR-list>            → scan ADRs for implementation gaps
/project adr gaps ADR-400..ADR-430     → scan a range of ADRs
/project adr gaps --status Accepted    → scan all ADRs matching status
/project adr cleanup                   → scan recent ADRs for data quality issues
/project adr cleanup --all             → scan all ADRs
/project adr cleanup --range 200-222   → scan specific range
/project adr cleanup --dry-run         → report issues without fixing
/project adr archive implemented       → gap-check each Implemented ADR; archive only those with zero gaps (default; safe)
/project adr archive implemented --force → bulk-archive ALL archivable ADRs without gap-checking (old behavior; fast)
/project adr archive implemented --dry-run → list candidates with per-ADR gap status without archiving
/project adr archive implemented --adr ADR-NNN → process one ADR (gap-checked unless --force)
/project adr extract ADR-NNN           → extract one archived Implemented ADR to runtime temp
```

### Default: live ADRs

Bare `/project adr` (and the explicit `/project adr live`) lists the **live** ADRs — the rows with `state="live"` in `adrs-index.json`, i.e. everything that is *not* archived. These are the open/active decisions (statuses `Proposed`, `Accepted`, `Future`) that still need attention; the ~589 archived `Implemented`/`Superseded`/`Deprecated`/`Cancelled` ADRs are excluded by default because they are settled history.

**Steps**:
1. Load `get_adr_dir()/adrs-index.json`.
2. Filter to entries where `state == "live"`.
3. Sort by ADR number descending.
4. Print a table: `ADR-NNN | Status | Title | decision_summary`.
5. Footer line: total live count, plus a hint that `/project adr recent` (or `/project adr latest`) shows the most recent ADRs across all states and `/project adr status` shows the full status-count summary.

Only show the status-count summary or the most-recent-across-all-states view when the user explicitly asks for it (`/project adr status`, `/project adr recent`, `/project adr latest`). Do not default to them.

This is a read-only subcommand — it does NOT trigger the post-write hook.

## Gap Analysis: N ADRs scanned

| Severity | Count |
|----------|-------|
| Critical | X     |
| High     | Y     |

### ADR-NNN: Title

| # | Requirement | Gap Type | Severity | Evidence |
|---|-------------|----------|----------|----------|
| 1 | MCP tool `plugin_list` | Unimplemented | Critical | No @mcp.tool found |
```

**Rules**: Read-only analysis — do NOT modify any files. Sort by severity (Critical first). `--severity` filters the report, not the scan. `--format summary` omits suggested fixes.

For archived ADRs, treat missing `Impact Manifest.files_affected` paths as historical evidence drift unless the ADR body or status notes explicitly require those paths to remain current live implementation surfaces. Report historical evidence drift in a separate section with the archive member and missing-path examples, but do not count it as Critical/High/Medium/Low implementation gap severity. Do not recreate retired paths or add compatibility shims to satisfy historical manifests.

### `cleanup`

Scan ADR files for data quality issues and fix them interactively. Operates in 3 phases: **scan** (detect duplicates, gaps, stale statuses via `src.lib.adr_utils`), **plan** (interactive user approval per issue), **apply** (renumber, normalize, regenerate index, validate).

**Args** (all optional):
- `--all` — scan all ADRs (default: last 30 days by file mtime)
- `--range NNN-MMM` — scan a specific ADR number range
- `--dry-run` — report issues without applying fixes

**Detailed phase walkthrough**: `docs/references/adr-cleanup-reference.md`

### `new <title>`

Create a new ADR from the template with auto-numbered filename.

**Steps**:
1. Scan `get_adr_dir()/ADR-*.md` to find the highest existing number
2. Increment by 1 for the new ADR number
3. Slugify the title: lowercase, replace spaces with hyphens, remove special characters
4. Read `get_adr_dir()/TEMPLATE.md`
5. Replace placeholders:
   - `ADR-NNN` → `ADR-{number}`
   - `[Title]` → user's title
   - `[Proposed | Accepted | ...]` → `Proposed`
   - `YYYY-MM-DD` → today's date
6. Write to `get_adr_dir()/ADR-{number}-{slug}.md`
7. Confirm:

```
Created ADR-116: Plugin Lifecycle Management
File: get_adr_dir()/ADR-116-plugin-lifecycle-management.md
Status: Proposed

Next steps:
  1. Fill in Context, Decision, and Consequences sections
  2. Run /project adr write to generate implementation prompt
  3. Or edit the file directly
```

## Post-Write Hook: Index and Doc Sync

Any `/project adr` subcommand that creates or modifies ADR files (`new`, `write`, `set`, `cleanup`, `plan`, `harden`) MUST run these steps **in order** after the ADR change is saved. Step 1 is the new source-of-truth update; steps 2–4 are the downstream regenerations. Skipping step 1 leaves the central JSON drifted from the live `.md` files and the markdown rollup will re-emit stale content.

1. **Upsert live ADR `.md` files into the central JSON** (the single source of truth per ADR-642):
   ```bash
   python .github/scripts/adr_upsert_live.py
   ```
   The script is idempotent — it scans every `project-brain/decisions/adrs/ADR-NNN-*.md`, parses each, and upserts via `adr_utils.upsert_adr_entry`. Archived entries are preserved untouched.
2. **Regenerate the markdown rollup** (`docs/generated/adr-index.md`) from the central JSON:
   ```bash
   python .github/scripts/generate_adr_index.py
   ```
3. **Regenerate ADR RAG pointer index**:
   ```bash
   python src/lib/index/unified_indexer.py --category adrs
   ```
4. **Regenerate agent instructions** (so ADR status table stays current):
   ```bash
   PYTHONPATH=project-brain/capabilities python3 -m skills.ai.scripts.sync_agents sync agents all
   ```
5. **Stage all outputs** alongside the ADR file or archive ledger in the same commit — never leave generated indexes stale.

Read-only subcommands (`live`, `status`, `list`, `recent`, `latest`, `search`, `gaps`) do NOT trigger this hook.

## Notes

- Status normalization uses `src/lib/adr_utils.py:normalize_adr_status()` — the canonical shared implementation
- The `set` action edits the actual ADR file — changes are reflected in the next `sync_agents sync agents all` run
- ADR records live in the central index at `get_adr_dir()/adrs-index.json` (ADR-642). The Markdown rollup is regenerated at `docs/generated/adr-index.md`.
- Archivable ADRs (status `Implemented`, `Deprecated`, `Superseded`, or `Cancelled`) are bundled under `get_adr_dir()/archive/archived-adrs-NNN-MMM.zip`. The same `adrs-index.json` is the search-first surface for both live and archived rows; extract a specific historical ADR only when the full body is needed. Archived statuses are *frozen, not dead* — resurrect by extracting, editing status notes, and writing the entry back to `state="live"`.

### `archive implemented`

Flip ADRs with archivable status (`Implemented`, `Deprecated`, `Superseded`, or `Cancelled`) from `state="live"` to `state="archived"` in the central `adrs-index.json` and bundle their materialized bodies under `archive/archived-adrs-NNN-MMM.zip`. Live statuses (`Proposed`, `Accepted`, `Future`) stay as `state="live"` rows.

**Default behavior is gap-gated** (safe). For every candidate `Implemented` ADR, run gap analysis first; archive only those with zero gaps. `Deprecated`, `Superseded`, and `Cancelled` ADRs always archive (no implementation exists to gap-check). Use `--force` to skip the gap check and restore the old bulk behavior.

**Steps**:
1. Resolve candidates from `get_adr_dir()/adrs-index.json` — entries where `state == "live"` AND `status ∈ {Implemented, Deprecated, Superseded, Cancelled}`. Scope to one ADR when `--adr ADR-NNN` is passed.
2. **Gap-check phase** (skipped when `--force`):
   - Partition candidates by status.
   - For each `Implemented` candidate, run the same gap analysis as `/project adr gaps ADR-NNN`: read the ADR body, scan its Decision / Acceptance Criteria / Impact Manifest, and verify each requirement against the codebase (MCP tool registration, function existence, file presence, test coverage, wiring).
   - Count gaps per ADR. **Zero gaps of any severity → eligible to archive.** Any gap (Critical/High/Medium/Low) → blocked, leave live.
   - `Deprecated`/`Superseded`/`Cancelled` candidates bypass the gap check — they archive directly.
3. **Dry run** (`--dry-run`): print a table with columns `ADR | Status | Gap Count | Decision (archive/block)` and stop. Do not modify any files.
4. **Apply** (no `--dry-run`):
   - Gap-gated path (default): for each archive-eligible ADR, call the script per-ADR so the gating stays at the command layer:
     ```bash
     python .github/scripts/adr_archive.py archive-implemented --adr ADR-NNN
     ```
   - Bypass path (`--force` was passed to `/project adr archive implemented`): the agent skips the gap-check step entirely and calls the script in bulk:
     ```bash
     python .github/scripts/adr_archive.py archive-implemented
     # or scoped:
     python .github/scripts/adr_archive.py archive-implemented --adr ADR-NNN
     ```
   `--force` is a command-level flag interpreted by the slash command; the underlying `adr_archive.py` script has no `--force` argument and behaves identically in both paths.
5. Regenerate ADR and RAG indexes:
   ```bash
   python .github/scripts/generate_adr_index.py
   python src/lib/index/unified_indexer.py --category adrs
   ```
6. Regenerate agent instructions:
   ```bash
   PYTHONPATH=project-brain/capabilities python3 -m skills.ai.scripts.sync_agents sync agents all
   ```
7. **Report**:
   - **Archived**: list ADRs that moved (`ADR-NNN — title`).
   - **Blocked by gaps**: list `Implemented` ADRs left live, with their top gap (highest severity + one-line evidence). The user can then fix the gap (code or ADR) or rerun with `--force` if intentional.

The central `adrs-index.json` preserves all ADR numbers (live + archived), so `/project adr new` must continue to use the highest known ADR number.

**Rule**: any gap of any severity blocks archival in the default flow. There is no severity threshold flag — if a gap is real but acceptable, fix the ADR text (e.g. mark the requirement as descoped in a status note) so the gap stops reporting, or use `--force`. This keeps the archived corpus free of implementation drift.

### `extract ADR-NNN`

Extract one archived ADR body to runtime temp for inspection:

```bash
python .github/scripts/adr_archive.py extract ADR-NNN
```

Do not extract the full archive unless explicitly needed. Runtime extracts are temporary working copies, not canonical ADR files.

---

## /project adr write

Generate a well-structured ADR from a superpowers spec/plan. If no matching spec exists, create the missing brainstorming spec first; do not fall back to a self-contained ADR.

### Usage

```bash
/project adr write "I want to build [describe your feature]"
```

### What This Does

1. Finds the matching superpowers spec and optional implementation plan
2. If no matching spec exists, creates `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` first
3. Writes an ADR that points at the spec/plan instead of replacing them
4. Auto-generates a **swarm implementation prompt** at the end of the ADR
5. Prints the prompt path separately so you can paste it into a new session

### Phase 0: Locate Or Create Spec + Plan, Write Index ADR

`/project adr write` is intended to run in the **same session** as `/superpowers:brainstorming` and `/superpowers:writing-plans` — once those have produced the spec + plan, immediately write the index ADR that points at them. Don't defer to a later session; the ADR is short and gives you a stable reference for `/project adr implement` later.

1. **Scan both paths**:
   - `docs/superpowers/specs/*-design.md` (output of brainstorming, just produced)
   - `docs/superpowers/plans/*.md` (output of writing-plans, just produced)

   Match candidates by recency (created within the last 7 days) OR by topic keywords from the user's description.

2. **If a spec or plan is found**:
   - Read both files (briefly — for title + decision summary only).
   - **Skip Phase 1** — brainstorming already explored the codebase.
   - **In Phase 2**: write a *thin index ADR* (per `TEMPLATE.md`) — title + one-line decision summary + frontmatter pointers `spec_file:` and `plan_file:` set to the original date-prefixed basenames (e.g. `2026-05-10-wiki-signal-priority-design.md`).
   - **Do NOT rename** the spec or plan files. They keep their date-prefixed names; the ADR points at them.
   - **Do NOT delete** the spec or plan after writing the ADR. They are canonical content; the ADR is just an index.
   - The spec + plan travel into the archive zip alongside the ADR when the ADR's status flips to Implemented/Deprecated/Superseded/Cancelled.

3. **If no matching spec is found**:
   - **Do not write a self-contained ADR.**
   - Create a missing brainstorming design spec at `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`.
   - Populate it from the user's request, the current conversation, related ADRs, and code/doc context gathered in Phase 1.
   - Include at minimum: Goal, Context, Decision, Architecture, Components, Data Flow, Error Handling, Testing/Verification, Alternatives, Open Questions, and ADR Handoff.
   - Run a spec self-review for placeholders, contradictions, scope drift, and ambiguous requirements.
   - If there is enough context to make the decision unambiguous, continue to Phase 2 and write the ADR with `spec_file:` set to the new spec basename.
   - If the missing spec exposes unresolved scope or product questions, stop after writing the spec, report the path, and ask the user to review before rerunning `/project adr write`.

4. **If a plan is missing but a spec exists**:
   - Continue writing the ADR with `plan_file: null`.
   - In the ADR status notes and chat output, say that `/superpowers:writing-plans` is still required before `/project adr implement`.

> **Why is the ADR thin?** The ADR is the index/management layer: status, lifecycle, archive bundle membership. The spec + plan are canonical content. Keeping them as separate files means `/project adr implement` can drive execution from the plan directly, and the same plan stays usable for `/superpowers:subagent-driven-development` outside the ADR flow.

### Phase 1: Gather Context

> **Skip this phase only if Phase 0 found and absorbed an existing brainstorming design doc. If Phase 0 must create a missing spec, gather this context before writing the spec.**

Before writing the ADR:

1. **Check existing ADRs** — `ls $(python3 -c "from src.config.paths import get_adr_dir; print(get_adr_dir())")` to find the next available number
2. **Scan related code** — identify files, modules, and patterns affected by the decision
3. **Check for related ADRs** — grep for keywords in existing ADRs to cross-reference

### Phase 2: Write the ADR

Generate the ADR with ALL of these sections. Do not skip any.

> **If Phase 0 found or created a design doc**: Context and Decision sections are pre-populated from brainstorming output. Focus on Consequences, Alternatives, Implementation Order, and Impact Manifest. Set `spec_file:` to the spec basename. Set `plan_file:` to the plan basename when present, otherwise `null`.

**Required sections**:
1. **Title and Metadata** — ADR number, status (Proposed), date, deciders, related ADRs
2. **Context** — Why this decision, what problem, current pain points, constraints
3. **Decision** — What we're building, broken into subsections per component/phase with file paths and action lists
4. **Consequences** — Positive, Negative, Neutral
5. **Implementation Order** — Dependency tree as phases with steps
6. **Alternatives Considered** — At least 2 alternatives with reasons for rejection
7. **References** — Links to related ADRs, docs, external resources
8. **Impact Manifest** (conditional) — Include when ADR involves path renames, API changes, pattern deprecation, or file structure changes. YAML block with `paths_renamed`, `apis_changed`, `patterns_deprecated`, `files_affected`.

### Phase 3: Generate Implementation Prompt (MANDATORY)

After writing all ADR sections, generate a swarm implementation prompt:

1. Extract phases from Implementation Order
2. Map steps to agent roles (developer, devops, architect, security, validator)
3. Identify parallel vs sequential dependencies
4. Select model tiers per step (low=haiku, medium=sonnet, high=opus)
5. Generate prompt using the Team Orchestration template with TeamCreate, TaskCreate, Task spawning

### Phase 4: Output

- **In the ADR file**: Append as `## Implementation Prompt` section
- **In the chat**: Show design overview first (Context, What Changes, What Improves, Phases), then offer the implementation prompt path. Do NOT print the full prompt in chat.

### Phase 5: Self-Review

Instruct the user to paste a review prompt into a new session for second-pass review.

---

## /project adr implement

Execute an ADR (or a standalone superpowers plan file) by driving its plan through the active implementation worktree and the superpowers subagent-driven flow, with native team primitives where the plan exposes parallel-safe clusters. **There is exactly one workflow** — no Native Mode, no Orchestrator Mode, no fallback orchestrator. Every implementing client (Claude Code, Codex, Gemini, etc.) is assumed to have the superpowers skill installed.

### Usage

```bash
/project adr implement ADR-722                                              # resolve plan via ADR.frontmatter.plan_file
/project adr implement 2026-05-10-setup-completeness-widget.md              # plan-file basename (looked up under docs/superpowers/plans/)
/project adr implement docs/superpowers/plans/2026-05-10-setup-completeness-widget.md  # explicit path
```

### Argument resolution

The single positional argument is **either** an ADR identifier (`ADR-NNN`) **or** a superpowers plan file (basename or path). Resolve as follows:

1. **`ADR-NNN`** — read the ADR file at `get_adr_dir()/ADR-NNN-*.md`. Require `plan_file:` in its frontmatter. Resolve the plan to `docs/superpowers/plans/<plan_file>`. The ADR also gives the slug for the worktree name.
2. **Plan basename** (e.g. `2026-05-10-foo.md`) — resolve to `docs/superpowers/plans/<basename>`. Worktree slug derived from the basename minus the date prefix. There is no governing ADR; the run is plan-only.
3. **Plan path** (contains `/`) — use directly. Same slug rule as case 2.

If the argument doesn't match any of these, return usage text — never silently default.

If the resolved plan file does not exist, abort with a clear error and a pointer to `/superpowers:writing-plans` to produce one.

### Workflow (single canonical sequence)

#### Phase 1 — Worktree selection (MANDATORY)

First identify the checkout that invoked `/project adr implement`:

```bash
git rev-parse --show-toplevel
git branch --show-current
```

If the current checkout is already a linked Augur worktree (for example it has `.augur-worktree.yaml`, or `git worktree list --porcelain` shows it is not the main checkout), **reuse the current worktree**. Do not create an additional `adr-*` worktree and do not switch branches underneath the active session. All subsequent steps execute inside this current worktree, even if its branch name is a session branch such as `wt-YYYYMMDD-HHMMSS`; report the branch name in the run summary.

Only create a new implementation worktree when invoked from the main checkout:

- Worktree name: `adr-{number}-{slug}` for ADR runs, `plan-{slug}` for plan-only runs.
- Commit any uncommitted ADR/plan changes on `main` before branching, so the new worktree starts clean.
- Use **`superpowers:using-git-worktrees`** to create the worktree on a fresh branch from `main`.
- All subsequent steps execute inside the new worktree. Never modify `main` directly during `/project adr implement`.

If the command is invoked from a non-main checkout that is not a registered Augur worktree, abort with a clear message instead of guessing whether to branch, switch, or reuse it.

If `superpowers:using-git-worktrees` is unavailable, fall back to a regular feature branch with the same naming scheme. Document the fallback in the run summary.

#### Phase 2 — Drive the plan via subagent-driven-development

Invoke **`superpowers:subagent-driven-development`** against the resolved plan file. This is the canonical execution loop:

- One fresh subagent per plan task.
- Two-stage review between tasks (the skill enforces this).
- Each task's TDD steps from the plan are executed verbatim — failing test first, then implementation, then commit.
- Use `superpowers:systematic-debugging` for any failing test that doesn't pass on the first implementation attempt.

This phase replaces the older "single-agent sequential execution" path entirely.

#### Phase 3 — Parallelize independent task clusters via native Team primitives

When the plan calls out independent task clusters (no shared files, no ordering deps), use the native Team primitives **inside the subagent-driven flow**, not as a replacement for it:

1. **Identify clusters** — scan the plan for tasks under the same checkpoint that touch disjoint files. Common patterns:
   - Independent prerequisite touches (e.g. `C1.x` slots that each modify a single file).
   - Per-module probes / leaf components (e.g. one task per phase probe; one task per UI leaf component).
2. **Spawn a Team** named after the run (`adr-NNN-impl` or `plan-{slug}-impl`).
3. **Create tasks** in the team for each cluster member; mark them PARALLEL where independent and PIPELINE where one feeds another.
4. **Spawn teammate agents** with `isolation: worktree` per task. Each teammate runs the same TDD discipline as `subagent-driven-development` for its single task and reports back.
5. **Stay sequential** for tasks that share files (aggregators, root components, mounts, cleanup) — do NOT force parallelism where it costs correctness.

Parallelism is an optimization, not a requirement. Plans with no independent clusters run fully sequentially under the subagent-driven loop. Plans with strong fan-out (probes, leaf components) save real wall time.

#### Phase 4 — Validation gates (MANDATORY)

Before declaring done, run **every** Completion Gate (below). Surface the result honestly:

- Run `/auto-test-pytest`, `/auto-test-dashboard`, `/auto-lint` — never invoke raw test runners (rule 29).
- For any UI-touching change, perform real-browser verification via Chrome MCP or screenshot tool — HTTP 200 from `curl` is **not** sufficient (rule 28).
- For ADRs with an Impact Manifest, scan for every stale reference. Zero must remain (rule 23).
- Use `superpowers:verification-before-completion` to keep the claims honest before marking anything green.

#### Phase 5 — Status flip + handoff

When (and only when) every Completion Gate passes:

1. Flip the ADR status to `Implemented` via `/project adr set <number> Implemented` (skip if plan-only run).
2. Run the post-write hook (regenerate ADR index + RAG pointer + agent instructions) per the [Post-Write Hook](#post-write-hook-index-and-doc-sync) section.
3. Hand off to `superpowers:finishing-a-development-branch` to merge / open PR / clean up the worktree per the user's chosen integration path.

### Completion Gates (ALL must pass before declaring done)

1. **Library Code** — All modules/classes written, no orphan code.
2. **Integration Wiring** — New code called from existing entry points, configs updated.
3. **Migration & Data** — Existing data migrated, source-of-truth populated.
4. **Tests Match Plan** — Every test case in the plan validated.
5. **Existing Tests Green** — No regressions.
6. **UI & Browser Validation** — Dashboard renders to interactive state in a real browser (rule 28).
7. **Impact Validation** — If the ADR has an Impact Manifest, zero stale references remain.
8. **Decentralization Check** — No new centralized config; skill-owned data lives in the skill's directory (rule 2).
9. **Wiring Verification** — Zero callers of deprecated functions; new functions have production callers.
10. **Agent Instruction Freshness** — New patterns documented in topic files; superseded guidance removed.
11. **Value Validation** — Run the implemented capability against **real data** (the real vault/documents/index, not only tmp-path test fixtures) and show concrete output that demonstrates the user-facing value the ADR promised — real extracted records, a real query answered, the actual artifact produced. Tests passing, a green build, a dry-run count, or a stats command returning zeros is **not** value validation (rule 34). If the real-data run produces weak, empty, or noisy output, that is a finding to fix or report — never downgrade the claim to "works mechanically".

---

## /project adr test

Test an ADR implementation against its acceptance criteria before merge.

### Usage

```bash
/project adr test                              # Auto-detect ADR from worktree/branch
/project adr test ADR-101                      # Test specific ADR
/project adr test ADR-101 --quick              # Skip browser validation
/project adr test ADR-101 --coverage           # Generate coverage report
/project adr test ADR-101 --approve            # Auto-approve test plan (CI mode)
/project adr test ADR-101 --report <path>      # Save report to file
```

### Phases

1. **Context Detection** — Find worktree, ADR file, extract test criteria
2. **Analyze Changes** — Categorize changed files (library, UI, MCP, API, config, data, docs), identify risk areas
3. **Generate Test Plan** — Map changes to tests, assign to agents, estimate duration
4. **User Approval** — Display plan, wait for confirmation
5. **Execute Tests** — Run directly via Bash (not delegated to agents):
   - Unit tests (pytest, npm test)
   - TypeScript build and typecheck
   - Wiring verification: deprecated symbol scan + new function reachability (MANDATORY)
   - Browser validation via Chrome MCP (MANDATORY for UI changes)
   - Value validation: run the capability against real data and show concrete user-facing output (MANDATORY — rule 34; mechanical pass is not value)
   - ADR compliance check against gates
6. **Report** — Pass/fail summary with recommendations
7. **Handle Pre-Existing Issues** — Classify by severity, fix critical/high, add TODO markers for medium/low

---

## /project adr plan

Scan `docs/superpowers/specs/` and `docs/superpowers/plans/` for orphaned design documents without matching ADRs, generate ADRs, and delete the absorbed artifacts.

### Usage

```
/project adr plan                → scan + generate ADRs for orphans + delete absorbed artifacts
/project adr plan --dry-run      → list orphans without generating or deleting anything
```

### How It Works

1. **Discover Orphans** — Cross-reference `docs/superpowers/specs/*-design.md` and `docs/superpowers/plans/*.md` against the central ADR index (`project-brain/decisions/adrs/adrs-index.json`). Specs/plans whose topic keywords don't match any existing ADR (live or archived) are orphans.
2. **Report Orphans** — List each orphaned spec/plan pair with its topic. Stop here if `--dry-run`.
3. **Generate ADRs** — For each orphan: find next ADR number, read spec + plan, extract context/decisions/consequences/alternatives, determine status (Implemented if evidence of completion, else Accepted or Proposed), write ADR with the absorbed content.
4. **Delete absorbed artifacts** — Once the ADR is committed, delete the spec and plan that fed it. Log each deletion. The ADR is now the canonical record.
5. **Summary** — List generated ADRs with paths and status; list deleted source files.

### Rules

- The spec + plan are working drafts. Once absorbed into an ADR, they're transient and get deleted — the ADR is canonical and gets archived under the normal policy (ADR-608).
- Specs/plans whose ADR is already archived also get deleted (the archived ADR carries the content).
- ADRs that exist but never got fed by a spec/plan are unaffected.
- Idempotent — running twice produces no new ADRs if all plans already matched

---

## /project adr harden

Audit a skill or dashboard hub, ask gap-filling questions, guide data import, and generate a hardening ADR.

### Usage

```
/project adr harden career                          # Skill-level: assess quality, fill gaps
/project adr harden http://localhost:3000/career    # Hub-level: dashboard audit → hardening ADR
```

If the argument contains `http` or `localhost`, use **Hub Mode**. Otherwise, use **Skill Mode**.

### Skill Mode — Interactive Gap Analysis

1. **Worktree Setup** — Create worktree before any changes
2. **Discover Skill** — Find skill directory, read key files (SKILL.md, augur.yaml, data, MCP, dashboard)
3. **Assess Quality (6 Dimensions)** — Score 0-100 each:
   - Problem Alignment (25%) — Clear problem statement, actions map to problems
   - Action Coverage (20%) — Actions wired to real handlers, not just YAML stubs
   - Data Support (20%) — augur/data/ has real populated files
   - UI Access (15%) — Pages render real data, not mockup
   - Capability Completeness (10%) — Promised features actually implemented
   - User Journey Fit (10%) — At least one complete end-to-end flow
4. **Ask Gap-Filling Questions** — Based on lowest dimensions, ask targeted questions about data sources, intended workflows, page content, skill purpose, and priorities
5. **Apply Fixes** — Import data, wire actions, fix pages, update SKILL.md
6. **Re-Score and Report** — Show before/after comparison

### Hub Mode — Dashboard Audit

1. **Worktree Setup** — Create worktree
2. **Run Audit Engine** — `dashboard_hardening_audit.py --url {URL}`
3. **Present Results & Ask Questions** — Show 10-dimension score table, collect user decisions (wow effect, scope, skip dimensions)
4. **Generate Hardening ADR** — `generate_hardening_adr.py --audit <report>`
5. **Output** — Print ADR path and implementation prompt
6. **Self-Review** — Suggest second-pass review in new session

### 10 Hub Dimensions

| # | Dimension | Weight |
|---|-----------|--------|
| 1 | UI Compliance | 12% |
| 2 | Page Coverage | 10% |
| 3 | API Completeness | 12% |
| 4 | MCP Tool Wiring | 10% |
| 5 | Performance | 10% |
| 6 | User Value | 15% |
| 7 | Workflows | 8% |
| 8 | Cross-Hub Connectivity | 5% |
| 9 | Action Buttons | 8% |
| 10 | Wow Effect | 10% |

## Additional resources
- [evals/rank.json](evals/rank.json)
