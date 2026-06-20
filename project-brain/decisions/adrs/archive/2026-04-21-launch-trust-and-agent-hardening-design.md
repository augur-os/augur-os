---
title: Launch Trust And Agent Hardening Design
date: 2026-04-21
status: draft-approved
scope: Public trust surfaces, install path clarity, demo evidence, agent instruction shrink, config decentralization, YAML page gates, and worktree safety
---

# Launch Trust And Agent Hardening Design

## Summary

Augur has several credibility and operating-discipline gaps that should be fixed one by one instead of as a single broad refactor. The public surfaces need to match what a fresh clone actually exposes, while agent operating rules should move from prompt text into enforceable gates wherever the invariant can be checked by code.

The work should be implemented as seven independent, verified slices:

1. Skill-count honesty.
2. Install friction and zero-dashboard path clarity.
3. Demo surface.
4. Global agent instruction shrink.
5. Decentralization and dashboard config truth.
6. YAML page compile/runtime gates.
7. Worktree operational guards.

Each slice should have its own acceptance checks and focused commit before the next slice starts.

## Goals

- Remove unsupported public claims such as `200+ portable skills` until a tracked inventory proves them.
- Make the install story honest about what works now and what remains planned.
- Add or wire a real demo surface without using placeholder proof.
- Halve the practical global prompt burden by moving workflow-specific details to owning docs, skills, or code gates.
- Resolve the contradiction between the decentralization rule and remaining central dashboard config files.
- Convert YAML page safety rules into mount/page-health validation where possible.
- Add branch/worktree safety checks that fail closed instead of relying on agent memory.

## Non-Goals

- Releasing all staged skills to live solely to satisfy marketing copy.
- Building a full Homebrew, Winget, or binary distribution in this plan unless that work is selected as a later install slice.
- Creating a fake demo GIF or referencing a missing asset from public docs.
- Deleting central config files before their consumers and governing ADR history are understood.
- Hand-editing generated agent files such as `AGENTS.md`, `CODEX.md`, or `CLAUDE.md`.
- Killing AI client processes as part of worktree cleanup.

## Recommended Approach

Use serial ROI checkpoints.

This approach keeps each correction reviewable and prevents public copy, instruction generation, dashboard validation, and git workflow safety from colliding. It also makes failure states clear: if slice 3 fails because no real demo asset exists, slices 4-7 can still proceed without pretending the demo shipped.

Alternative approaches were considered:

- Trust first, gates second: faster external credibility improvement, but leaves recurring prompt-rule violations in place longer.
- Gates first, marketing last: stronger engineering posture first, but public trust gaps remain visible.
- One full mega-branch: fewer commits, but too much unrelated risk in one diff.

## Architecture

The implementation should be organized around four components.

### 1. Public Trust Surfaces

Owned surfaces:

- `README.md`
- `packages/create-augur/`
- website working copy under `get_documents_dir()/venture-augur/website-working/`
- demo docs/assets under `docs/demo/`
- tests that scan public copy for unsupported claims

Public claims should be computed or test-backed. If the repo exposes 21 top-level live MVP skills and 30 staged skills, copy may say that. It must not say `200+ live` or `200+ portable skills` unless a tracked inventory proves it.

### 2. Instruction Source Split

The source of truth for generated agent instructions remains `docs/agent-topics/agent-rules.md`.

Workflow-specific instructions should move into their owning topic docs or skills:

- Dashboard verification and wiring audit details belong in `docs/agent-topics/DASHBOARD.md` or dashboard health tools.
- YAML page migration rules belong with page migration/build validation.
- Worktree cleanup and `/dev-merge` details belong in `docs/agent-topics/WORKFLOWS.md`, `dev-merge`, and worktree scripts.
- Skill schema and decentralization details belong in `docs/agent-topics/SKILLS.md` and validation scripts.

Generated `AGENTS.md`, `CODEX.md`, `CLAUDE.md`, and client surfaces should be regenerated after source changes.

### 3. Enforcement Gates

Prompt-only rules should become gates when mechanically checkable:

- YAML page MCP data sources must not be mutation/search tools or metadata-only status tools.
- YAML page generation should reject known interaction regressions when replacing richer TSX pages.
- Central dashboard config debt should be detected and classified.
- Generated instruction drift should fail checks.
- Main-checkout branch drift should be detected before agent work continues.

Gates should explain the failing surface and the owner path. They should not hide issues by returning empty data, weakening assertions, or moving the problem into fallback code.

### 4. Operational Workflow Hardening

Worktree and merge cleanup should reuse the existing worktree and `/dev-merge` machinery:

- repair Codex thread state before deleting a worktree
- detect live `codex`, `claude`, `gemini`, or Cowork ownership before deletion
- defer deletion when active ownership is found
- block or fail closed when the main checkout is on a non-main branch
- report exact branch, cwd, PID, and cleanup blockers

The work should improve the workflow users and agents actually run, not add an unused side script.

## Data Flow

Every slice follows the same loop:

1. Inventory current state from source files.
2. Decide whether the fix is public copy correction, code gate, or workflow relocation.
3. Patch the owning source, not generated output directly.
4. Regenerate derived surfaces when source docs or dashboard mounts change.
5. Verify with focused tests and the real workflow check where applicable.
6. Commit the slice before moving on.

For skill counts, the inventory should derive from `skills/*/SKILL.md` and `staging/*/skills/*/SKILL.md`. Public surfaces should depend on that inventory directly or be tested against it.

For instruction shrink, the source doc should shrink first. Generated agent files should only change through the sync generator.

For YAML page gates, validation should run where YAML wrappers or mounted pages are generated, and page-health loops can provide additional runtime diagnostics.

## Error Handling

- If a public count cannot be proven, public copy must choose a conservative truthful phrasing.
- If a zero-dashboard path is not implemented, docs may describe it as planned but not as available.
- If a demo asset is missing, public docs must not reference it as shipped.
- If a central config file has no clear migration owner, classify it as debt and document the exception instead of deleting it.
- If a YAML page tool needs required args or returns only `{skill, status, version}` style metadata, it cannot be used as a passive data source.
- If a TSX page contains interaction patterns the YAML renderer cannot represent, conversion must stop with a diagnostic.
- If worktree safety cannot prove no active AI/client ownership, cleanup must defer and report the blocker.

## Slice Breakdown

### Slice 1: Skill-Count Honesty

Problem:

Public copy claims or implies a larger ready-to-use skill surface than the public tree proves.

Design:

- Add a small inventory helper or test fixture that counts live and staged skills.
- Update README and website copy to distinguish live MVP skills from staged release payloads.
- Remove unsupported `200+ portable skills` claims from public launch surfaces.
- Add regression tests for unsupported count claims and stale numbers.

Acceptance:

- Public copy does not claim more live skills than the repo exposes.
- Tests fail if `200+` returns without a matching tracked inventory.
- The README and website use compatible wording.

### Slice 2: Install Friction

Problem:

The current README leads with clone plus multiple dependency managers, while `create-augur` exists but is not the lead public path. The desired zero-dashboard MCP/skills-only path is not clearly separated from full dashboard setup.

Design:

- Make the simplest currently working path the README lead.
- Clarify what `create-augur` does and when manual clone remains useful.
- Add explicit copy for full system setup versus planned or implemented MCP/skills-only setup.
- Avoid overclaiming Homebrew, Winget, binary installers, or zero-dashboard mode unless implemented in the slice.

Acceptance:

- README and `packages/create-augur` copy agree on the supported current setup.
- Planned install channels are clearly marked as planned.
- A user can tell whether dashboard dependencies are required for the path they choose.

### Slice 3: Demo Surface

Problem:

Public surfaces do not show a concrete `/ask` or ingest-to-answer workflow. A demo README exists, but the root README does not point to a real demo asset.

Design:

- Prefer a real short asset showing ingesting a document, asking `/ask`, and receiving an answer grounded in local knowledge.
- If the asset is not created during the slice, add a tracked launch blocker and keep public README references out.
- Update `docs/demo/README.md` only as the source recording workflow, not as proof that a GIF exists.

Acceptance:

- README references a demo only when the asset exists.
- Missing demo work is tracked honestly.
- Demo copy shows the actual product workflow rather than architecture-only description.

### Slice 4: Global Instruction Shrink

Problem:

The global generated agent instructions contain many workflow-specific incident rules. Every session pays token cost for details that should live in tools, gates, topic docs, or skills.

Design:

- Audit each global rule into one of four destinations:
  - keep global principle
  - move to topic doc
  - move to skill/workflow doc
  - enforce with code gate
- Merge overlapping principles such as UX priority, no workaround fixes, and truthful compounding.
- Preserve critical safety rules that truly apply every session.
- Regenerate generated agent files through the sync pipeline.

Acceptance:

- Global rule count and generated instruction size shrink materially.
- Generated files are in sync.
- Moved details remain discoverable in the owning topic docs or skills.
- No generated file is hand-edited.

### Slice 5: Decentralization And Config Truth

Problem:

The global decentralization rule says central dashboard config files are technical debt, while the tree still contains central config files. That teaches agents that rules are aspirational.

Design:

- Classify each remaining `config/dashboard/*.yaml` file:
  - legitimate central system config
  - generated config
  - migration debt with a clear skill/frontmatter owner
- Migrate debt only when the owner and consumer path are clear.
- Document legitimate exceptions in the global rule or architecture docs.
- Add an audit test so new central dashboard config requires classification.

Acceptance:

- The rule text matches the current tree.
- Known central files are either migrated or documented exceptions.
- New unclassified central dashboard YAML fails validation.

### Slice 6: YAML Page Gates

Problem:

YAML page migrations have caused broken or empty pages, so two global prompt rules now describe checks that should be automated.

Design:

- Extend page scanner or mount validation to inspect YAML `mcp_tool` references.
- Reject passive data blocks backed by mutation/search/argument-required tools.
- Reject metadata-only tool responses as data sources when a local or test probe is available.
- Add conversion diagnostics for TSX pages with `useMcpMutation`, too many `useState` calls, modals/toasts, or multiple local imports.
- Keep browser verification mandatory for dashboard behavior, but reduce global prompt detail by moving specifics to the dashboard topic doc and tools.

Acceptance:

- Tests cover metadata-only MCP responses, mutation/search misuse, and interactive TSX conversion blockers.
- The build or health check produces actionable diagnostics.
- The global rule can be shortened because the gate owns the invariant.

### Slice 7: Worktree Operational Guards

Problem:

Rules about main checkout branch drift and not killing AI clients reflect recurring operational pain. They need root-cause gates in the workflows that create, merge, and remove worktrees.

Design:

- Add a reusable main-checkout branch guard that detects the primary checkout and refuses non-main work there.
- Wire the guard into relevant launcher/preflight/merge entrypoints rather than relying only on prompt instructions.
- Harden cleanup order so thread repair and active-process ownership checks happen before deletion.
- Keep AI/client processes alive; report conflicts instead of terminating them.

Acceptance:

- Script-level tests or dry runs show unsafe main-checkout branch drift fails closed.
- Active AI/client ownership blocks worktree deletion with PID/cwd/branch reporting.
- No cleanup path deletes an active session-owned worktree.

## Verification Strategy

Use focused checks per slice:

- Skill counts and public claims: pytest or grep-backed tests over README, website working copy, and docs.
- Install copy: tests for `create-augur` help/next-step output and README wording.
- Demo: file-existence check when README references a demo asset.
- Instruction shrink: `sync_agents` check or equivalent generated-surface verification.
- Config truth: unit test over `config/dashboard/*.yaml` classification.
- YAML page gates: mount/page-health tests and dashboard script tests.
- Worktree guards: unit tests for guard logic and dry-run script verification.

Before final handoff, run a hardcoded path audit for worktree-specific paths and verify `git status --short --branch`.

## Commit Strategy

Create one focused commit per slice after verification passes. Do not batch unrelated slices into one large commit. If a slice is blocked, report the blocker and continue only with slices that do not depend on it.

## Open Decisions

The implementation plan should decide these while preserving the design constraints:

- Whether skill-count inventory should be a Python helper, generated Markdown, or pure tests.
- Whether zero-dashboard MCP/skills-only setup is implemented now or documented as planned.
- Whether demo creation is done manually from the existing dashboard, from a deterministic HTML replay, or deferred as a launch blocker.
- Which central dashboard config files can be migrated immediately versus classified as legitimate exceptions.

## Done Condition

The program is complete when all seven slices have focused verification, generated files are in sync, public copy is honest, instruction burden is reduced, central config policy matches the tree, YAML page regressions are guarded by code, and worktree cleanup fails closed around active sessions and main-checkout branch drift.
