---
id: ADR-510
title: Agent Digest Nightly Autoloop
status: Implemented
date: 2026-03-24
deciders: [Gur Sannikov]
tags: [agents, memory, digest, violations, autoloop]
related: []
---

# ADR-510: Agent Digest Nightly Autoloop

## Context

Agents across platforms (Claude Code, Codex, Gemini, Cursor) start each session without awareness of which project decisions are actively being violated or what recently changed. Violations repeat across sessions because no mechanism propagates enforcement signals into agent context.

## Decision

Build `auto-agent-digest` skill with three signal collectors feeding a layered digest:
- **Git scanner** — Pattern-match commits against `violation-patterns.yaml` anti-patterns
- **Session log parser** — Extract correction phrases from session logs
- **`/flag` command** — Manual directive flagging by the user

Signals append to JSONL journal. Nightly compiler scores directives by violation frequency with recency decay, then writes two token-capped tiers:
- **Hot** (500 tokens, 7-day window) — currently active violations
- **Warm** (500 tokens, 30-day window) — recent but declining violations

`memory_assembler.py` prepends digest into MEMORY.md for distribution to all agent targets.

## Consequences

### Positive
- Every agent starts every session knowing active violations
- Recency decay auto-demotes old issues without manual cleanup
- Token-capped tiers prevent digest from bloating context

### Negative
- Depends on session logs being available (not all platforms emit them)
- Pattern matching may miss novel violation types

## References

- Plan: `docs/superpowers/plans/2026-03-24-agent-digest.md`
- Spec: `docs/superpowers/specs/2026-03-24-agent-digest-design.md`
- Skill: `skills/auto-agent-digest/`
