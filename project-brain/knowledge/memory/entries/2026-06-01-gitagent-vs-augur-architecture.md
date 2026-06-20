---
title: gitagent vs Augur — same bet, different layers
brain_scope: project
type: insight
status: active
owner: team
date: 2026-06-01
source: https://github.com/open-gitagent/gitagent
tags:
  - architecture
  - agent-framework
  - git-native
  - projection
  - comparison
---

# gitagent vs Augur — same bet, different layers

**gitagent** (open-gitagent/gitagent) is a git-native AI agent framework: the
agent's identity, rules, memory, tools, and skills all live as
version-controlled files inside a git repo ("your agent lives inside a git
repo"). Captured 2026-06-01 via `/keep`.

## Convergence — the shared foundational bet
Both gitagent and Augur are built on the same conviction: an agent's
identity/rules/memory/tools/skills should be **version-controlled files, not
opaque runtime state**, local-first, file-first (no database). Augur's
project-brain (`IDENTITY.md`, `SOUL.md`, `AGENTS.md`, skills-as-folders, ADRs,
memory entries) is the same idea. Strip Augur to one repo and you have gitagent.
gitagent validates Augur's foundational premise.

## Where Augur deliberately goes further — three layers gitagent lacks
1. **Source vs. projection** (Augur's signature move). In gitagent the files
   *are* the agent — one repo, read directly. Augur splits brain-authored
   **source** from **generated client projections**: `.claude/`, `.codex/`,
   `.gemini/`, Copilot files are auto-generated from one source via
   `sync_agents`. One brain → many clients, deterministically. Generated
   surfaces are inspectable but explicitly *not canonical*. Single-surface vs.
   one-source-many-surfaces.
2. **An orchestration harness on top of the files.** gitagent is agent-as-repo;
   Augur adds routines, the daemon, MCP tools as atomic ops, adaptive loops, and
   the routines/goal-loop system (ADR-793 inline-session invoker bridge = how the
   client drives autonomous work over the file-source; rule 19 = agents own
   judgment, MCP tools own atomic ops). Substrate vs. substrate + engine.
3. **A brain *stack*, not a brain.** gitagent = one repo = one agent. Augur
   layers brains — global (`augur-core`), personal, per-project — with precedence
   and routing.

## Where gitagent is arguably cleaner
"The repo *is* the agent" is more universal/portable — any git-native tool reads
it with zero projection machinery. Augur's projection + brain-stack is more
powerful but carries real complexity (generators, precedence rules, the harness).
gitagent = elegant minimal substrate; Augur = substrate + projection + harness.

## Takeaway
Augur's differentiation is **everything stacked above the shared file-first
substrate**: one-source-many-clients projection + the autonomous-execution
harness. This is a near-exact external echo of Augur's own `SOUL.md`:
*"brain-owned source, client-native reasoning, and inspectable generated
projections."*
