---
status: Implemented
date: 2026-05-13
deciders:
  - gsannikov
related:
  - ADR-734
  - ADR-742
hub: dev
tags:
  - skills
  - quality
  - audit
  - capabilities
  - mece
superseded_by: null
spec_file: 2026-05-13-check-resolvable-design.md
plan_file: 2026-05-13-check-resolvable.md
---

# ADR-741: Skill Resolvability and MECE Coverage Audit

## Status

Implemented (2026-05-13).

## Context

Augur ships 130+ skills, each declaring intent triggers via the `description:` field, `x-augur-tags:` array, and command surfaces in `config/system/capability_exposure.yaml`. There is currently **no automated audit** that confirms:

1. Every user intent declared by a skill is reachable by at least one command surface (CLI / MCP / dashboard / browse).
2. Two or more skills do not silently claim overlapping intents without explicit ownership.
3. Skills are not orphaned (declared but unreachable through any surface).

`auto-skill-quality` lints individual skills but does not perform global coverage analysis. A reference implementation (gbrain) calls this audit `check-resolvable` — it validates resolver reachability, MECE coverage, and routing gaps.

## Decision

Add a `check-resolvable` audit step inside the existing `auto-skill-quality` auto-loop. Runs nightly, produces a JSON report under `get_runtime_dir()/quality/resolvable-report.json`, and surfaces in the dashboard `dev` browse category.

Concretely:

1. Parser walks every `SKILL.md` under `shared-vault/skills/` and the configured private vault `skills/` root.
2. For each skill, extracts:
   - `description:` (user-intent phrases)
   - `x-augur-tags:` (taxonomy tags)
   - `x-augur-commands:` (declared command surfaces)
   - `x-augur-mcp-tools:` (declared MCP tools)
3. Cross-references against `config/system/capability_exposure.yaml` for actual command/MCP exposure.
4. Detects and reports:
   - **Unrouted intents** — declared trigger phrases with no reachable command surface
   - **Routing collisions** — two or more skills claiming overlapping triggers without explicit ownership in capability_exposure
   - **Orphaned skills** — skill declares no triggers reachable from any surface
   - **Stale capability entries** — capability_exposure entries pointing to skills/tools that no longer exist
5. New MCP tool: `skill-resolvable-report` (returns the latest report).
6. Audit failure is **report-only** in the loop initially; flips to CI-blocking after one stabilization release.

## Non-Goals

- No automated routing fix. Report-only — the user (or active AI client) decides how to resolve collisions.
- No LLM-based intent overlap detection. Deterministic string and tag analysis only.
- No replacement of `auto-skill-quality` — `check-resolvable` is a new step inside it, not a separate loop.
- No enforcement of MECE strictness beyond reporting. The system surfaces gaps; the user decides scope.

## Consequences

- Extends `auto-skill-quality` with a new audit step and a new MCP tool.
- New report path `get_runtime_dir()/quality/resolvable-report.json` (rebuildable, not durable state).
- Dashboard `/dev` browse category gains a "Skill Coverage" card.
- Dependent on `capability_exposure.yaml` being current; surfaces drift as a finding.
- Foundation for ADR-742 evals: the resolvability report is one ground-truth signal for retrieval coverage.

## Related

- ADR-734 (capability surface cleanup)
- ADR-742 (eval harness uses coverage as an axis)
- surface-decision-matrix.md (which surface owns which op)
