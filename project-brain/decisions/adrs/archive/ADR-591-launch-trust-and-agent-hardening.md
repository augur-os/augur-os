---
status: Implemented
date: 2026-04-21
deciders:
  - Gur Sannikov
related: []
hub: null
tags: []
superseded_by: null
---

# ADR-591: Launch Trust and Agent Hardening

## Context

Augur has several credibility and operating-discipline gaps that should be fixed one by one instead of as a single broad refactor. The public surfaces need to match what a fresh clone actually exposes (e.g., unsupported `200+ portable skills` claims), the install story should be honest about what works versus what is planned, and a real demo surface should exist before being referenced publicly.

In parallel, agent operating rules have grown into a long prompt-time list. Workflow-specific incident details (dashboard verification, YAML page migration, worktree cleanup, skill schema) should move from prompt text into owning topic docs or enforceable code gates wherever the invariant can be checked mechanically. Generated agent surfaces (`AGENTS.md`, `CODEX.md`, `CLAUDE.md`, `.gemini/GEMINI.md`) must only change through their `sync_agents` source generator.

YAML page migrations have caused broken or empty dashboard pages, and worktree/main-checkout drift is a recurring operational pain. Both should become fail-closed gates rather than relying on agent memory.

## Decision

Implement the work as seven independent, verified slices with a focused commit after each:

1. Skill-count honesty — computed inventory helper (`src/lib/launch_inventory.py`), tests, and corrected README/website copy.
2. Install friction clarity — README leads with `create-augur`; clear distinction between current full setup and planned MCP/skills-only path.
3. Demo surface — README references demo asset only when it exists; `docs/demo/README.md` truthfully marks GIF status.
4. Global instruction shrink — move workflow-specific details to `DASHBOARD.md`, `WORKFLOWS.md`, and `SKILLS.md`; regenerate client surfaces via `sync_agents`.
5. Decentralization and config truth — classify central dashboard config in `config/dashboard/README.md`; add classification regression test.
6. YAML page gates — extend page-health scanner to reject mutation tools, search/find tools, and metadata-only responses as passive YAML data sources.
7. Worktree operational guards — reusable `skills/platform-admin/scripts/worktree_guard.py` wired into `scripts/worktree_preflight.py` to fail closed on main-checkout branch drift.

## Consequences

### Positive
- Public claims become test-backed instead of aspirational.
- Generated client surfaces stay consistent because edits flow through their owning sources.
- Prompt-only rules become mechanical gates that fire for every agent (not just Claude).
- Worktree cleanup and main-checkout safety stop relying on prompt memory.
- Per-slice commits keep failure states isolated.

### Negative
- Seven slices increases coordination cost versus a single mega-PR.
- Some YAML page diagnostics may produce false positives during transition until owners adjust block types.

### Neutral
- Generated `AGENTS.md`/`CODEX.md`/`CLAUDE.md` regenerate after agent-rules edits; reviewers must accept generated diff alongside source diff.

## Alternatives Considered

### Alternative 1: Trust first, gates second
Faster external credibility improvement but leaves recurring prompt-rule violations in place longer.

### Alternative 2: Gates first, marketing last
Stronger engineering posture first, but public trust gaps remain visible during the gate work.

### Alternative 3: One full mega-branch
Fewer commits but too much unrelated risk in one diff; failure in one slice would block the others.

## References
- Plan: docs/superpowers/plans/2026-04-21-launch-trust-and-agent-hardening.md
- Spec: docs/superpowers/specs/2026-04-21-launch-trust-and-agent-hardening-design.md
