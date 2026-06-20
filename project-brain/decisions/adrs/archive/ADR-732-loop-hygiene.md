---
status: Implemented
date: 2026-05-12
deciders:
  - gsannikov
related:
  - ADR-571
  - ADR-731
  - ADR-491
hub: adaptive
tags:
  - hygiene
  - retention
  - artifacts
  - archive
  - au-docs
  - mcp
  - slash-command
superseded_by: null
spec_file: 2026-05-11-loop-hygiene-design.md
plan_file: 2026-05-11-loop-hygiene.md
---

# ADR-732: loop-hygiene — Store-wide Artifact Retention to Stop AI Hallucinations from Stale Versions

> **ADR-732 is an index file.** The substantive design and implementation steps live in the linked spec + plan. This file carries pointers, status, and a one-line decision summary.

## Decision summary

Introduce a new skill `loop-hygiene` at `shared-vault/skills/loop-hygiene/` that ships a `/sweep-stores` slash command plus two MCP tools (`hygiene-scan` read-only, `hygiene-apply` destructive+atomic) so an agent in any AI client session can sweep stale-version artifacts (e.g., 48 `guriqo-com-V*.zip` builds in `Au-docs/venture-augur/websites/`) out of the live tree into per-folder `.archive/` directories that are invisible to AI scanners via `.augur-ignore` + `.gitignore`. The agent in the user's session is the classifier — no `llm.yaml` routing, no LLM SDK imports anywhere in the skill, no API keys. MVP-v2 scope is committed: Au-docs only, single exclusion layer, no auto-loops, no dashboard. Phases 2–6 (per-month archives + 90-day auto-purge, Au-vault scope, multi-layer exclusions + verification probes, nightly auto-loop, unattended classifier via llm.yaml, dashboard tab + milestone CRUD + undo + audit log) are documented but explicitly deferred to follow-up ADRs.

## Spec (canonical)

- [`docs/superpowers/specs/2026-05-11-loop-hygiene-design.md`](../superpowers/specs/2026-05-11-loop-hygiene-design.md)

## Plan (canonical, drives `/adr implement`)

- [`docs/superpowers/plans/2026-05-11-loop-hygiene.md`](../superpowers/plans/2026-05-11-loop-hygiene.md) — 19 tasks across 6 checkpoints (C1 skill scaffold + never-touch + lifecycle readers, C2 `hygiene_scan` walker + lifecycle/milestone wiring, C3 `hygiene_apply` skeleton → 6 refusal categories → atomic os.rename + dup-suffix → manifest + rollback → `.augur-ignore`/`.gitignore` propagation, C4 5 golden fixtures + e2e, C5 MCP surface + slash command + capability policy, C6 quality gates + manual ritual + this ADR). TDD discipline throughout: each task is failing test → minimal implementation → passing test → commit. Boundary rules forbid LLM SDK imports anywhere in the skill (the agent-in-session is the classifier).

## Status notes

Spec + plan + implementation landed 2026-05-11 to 2026-05-12 in the same `/superpowers:brainstorming` → `/superpowers:writing-plans` → `/superpowers:subagent-driven-development` chain. 18 of 19 plan tasks completed via fresh subagent per task with two-stage review between tasks (spec compliance then code quality). The remaining task (T18, manual `/sweep-stores` ritual against real `Au-docs/venture-augur/websites/`) is user-driven by design — it requires a fresh AI client session to exercise the slash-command-as-classifier path and to verify externally that `.augur-ignore` actually hides archived files from a follow-up session's view.

Load-bearing claims:

- **Single exclusion layer is enough for MVP.** `.augur-ignore` at every `.archive/` root + `.archive/` line in store-root `.gitignore`. The MVP makes no claim that hiding is automatic across every AI tool — it claims the most common Augur scanners honor `.augur-ignore`, which the user verifies manually in the T18 ritual. If hiding leaks, Phase 4 (llms.txt + MCP boundary checks + RAG denylist + Obsidian filter + verification probes) becomes the next follow-up ADR.
- **Agent-as-classifier eliminates ~300 LOC** of LLM client scaffolding, vendor abstraction, caching, and cost guardrails. It also aligns with rule 19 (agents own judgment, MCP tools own atomic operations, commands own policy, daemons schedule) and is genuinely vendor-neutral — works in Claude Code, Codex CLI, Gemini CLI, Cursor, etc. without `llm.yaml` config.
- **Two new MCP tools (`hygiene-scan`, `hygiene-apply`)** are registered in `src/mcp/augur_core/tools/core/hygiene.py` and exposed with `export_to: [mcp]` in `config/system/capability_exposure.yaml`. They load the skill scripts via `importlib.util.spec_from_file_location` (hyphenated dirs prevent dotted imports) with `sys.modules` caching for per-server-boot single load.

Distinction from `loop-repo`'s `vault-hygiene` artifact: this skill (`loop-hygiene`) retires stale-version artifacts. `loop-repo`'s `vault-hygiene` repairs vault structural integrity (broken refs, malformed frontmatter). They are orthogonal and coexist.

Memory feedback captured during the run: `feedback_skill_test_convention.md` (skill tests live at `<skill>/augur/tests/` and use inline importlib + `sys.modules` registration; the dotted `from shared_vault.skills.X import Y` form does not resolve because hyphenated dirs are not valid Python module name components) and `feedback_vendor_neutral_design.md` (every AI-using feature must route through `config/system/llm.yaml` profiles; never hardcode a vendor or model name in designs, specs, or code).
