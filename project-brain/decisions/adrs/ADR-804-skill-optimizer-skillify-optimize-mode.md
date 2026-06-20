---
status: Accepted
date: 2026-06-08
deciders:
  - gsannikov
related: []
hub: null
tags:
  - skills
  - optimization
  - auto-skill-quality
  - skillify
superseded_by: null
spec_file: 2026-06-08-skill-optimizer-design.md
plan_file: 2026-06-08-skill-optimizer.md
---

# ADR-804: Skill Optimizer — `/skillify <skill>` optimize mode

> **ADR-804 is an index file.** The substantive design and implementation steps live in the linked spec + plan. This file carries pointers, status, and a one-line decision summary.

## Decision summary

Add `/skillify <skill>` **optimize mode**: an on-demand, converge-or-stall optimizer that improves one skill's **accuracy and speed/cost together**, validated by **replaying the skill's real runs** — each candidate edit (instructions, config knobs, *or* code) is kept only if the skill's tests pass and a held-out combined accuracy+speed score strictly improves, else `git revert`; runs worktree-isolated with **no auto-merge**.

## Spec (canonical)

- [`docs/superpowers/specs/2026-06-08-skill-optimizer-design.md`](../superpowers/specs/2026-06-08-skill-optimizer-design.md)

## Plan (canonical, drives `/adr implement`)

- [`docs/superpowers/plans/2026-06-08-skill-optimizer.md`](../superpowers/plans/2026-06-08-skill-optimizer.md)

## Status notes

**Accepted (2026-06-08) — engine implemented + tested; primary measurement source BLOCKED on a logging gap.** Built via `superpowers:subagent-driven-development` (8 tasks, **29 tests passing**) on branch `wt-20260607-085147`: the measurement layer (`replay_source` / `profiler` / `judge` / `score` with a held-out split), the converge-or-stall ops (`optimize_baseline` / `optimize_evaluate` with the tests-pass + strict-improvement gate / `optimize_status` / `optimize_report`), the git-wired CLI, the `/skillify` optimize dispatch + inline-session prompt, and capability registration. Approach **A** (native loop on `auto-skill-quality` + the catalog-loop shape).

**Material finding (rule 34):** the chosen measurement source — *replay real runs* — does **not** work on the real `augur_mcp.log` today. That log records 15,517 `Tool invoked: <name>` lines in **plain text with no args or results** (not the JSON-line `{tool, args, result}` records the replay parser needs). So the optimizer cannot replay real invocations; the **curated/seed-eval fallback is the only live measurement path**, and even that requires a skill to have `evals/`. Status stays **Accepted (not Implemented)** because the headline capability is undelivered.

**Follow-up RESOLVED (2026-06-08).** The structured tool-call invocation log shipped: `src/mcp/augur_shared/mcp_sdk.py:_record_invocation` appends an always-on, local, truncated, never-raising `{ts, tool, args, result, duration_ms}` JSON line per MCP tool call to `get_logs_dir()/mcp_invocations.jsonl`, and `replay_source._parse_invocation_log` reads it (preferred over the legacy plain log). Proven end-to-end on real paths: a written record round-trips into a `ReplayCase` with full inputs + prior output (`source="mcp-invocation-log"`); 31 optimizer + 2 mcp-sdk tests pass. So **the optimizer now replays real usage** — the headline capability is unblocked. Operational caveats (not code gaps): live accumulation begins on the next MCP-server reload (the running server holds the pre-edit module), and a first end-to-end *optimize run on a real skill* (replay → propose → converge) is AI-client-driven and still to be exercised. The accuracy judge is the AI client in-session (rule 11); transcript replay for chat-driven skills remains deferred.

## Related

- Owner skill: `auto-skill-quality` (the audit/improve home; `/skillify` is the creation half, this adds the optimize half).
- Reuses ADR-793 (inline-session catalog-loop) and the goal-loop worktree isolation.

## Impact Manifest

> New, additive capability — no path renames, API changes, or pattern deprecations.

```yaml
impact:
  paths_renamed: []
  apis_changed: []
  patterns_deprecated: []
  files_affected: []
```
