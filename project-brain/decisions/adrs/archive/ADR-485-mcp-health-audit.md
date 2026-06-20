---
status: Implemented
date: 2026-03-23
deciders:
- Gur Sannikov
related:
- 443
- 260
- 163
hub: adaptive
tags:
- mcp
- autoloop
- wiring
- health
- audit
- auto-fix
superseded_by: null
---

# ADR-485: MCP Health Audit

## Context

Most dashboard pages show empty data because of two root causes: (1) wiring mismatches — proxy route `toolName` values don't match actual `@mcp.tool(name=...)` registrations in Python; (2) broken tools — registered MCP tools fail at runtime (import errors, missing data dirs, bad code). The proxy's `fallback` config masks these failures — pages render empty data instead of errors, making the problem invisible to the user.

Three existing auto-loops (`auto-api-wiring`, `auto-test-mcp-commands`, `auto-block-wiring`) cover parts of this but don't auto-fix anything, are stagnating (streak 3+), and produce no unified picture. `auto-mcp-hygiene` exists as a stub with no implementation.

## Decision

A new auto-command `auto-mcp-health-audit` with 4 sequential phases. Operates both as a one-time sweep and as a permanent autoloop with difficulty-gated behavior.

### Architecture

```
Phase 1 (d>=0)      Phase 2 (d>=1)       Phase 3 (d>=2)      Phase 4 (always)
Static Wiring   ──▶  Runtime Probe   ──▶  Auto-Fix       ──▶  Report
Audit                                     (safe cases)
```

Located at `skills/auto-mcp-health-audit/` with `SKILL.md`, `scripts/mcp_health_audit.py`, and tests.

### Phase 1: Static wiring audit (no server required)

Parse all `toolName` values from `apps/dashboard/app/api/[...proxy]/_routes-{a,b,c}.ts`. Scan `src/mcp/augur_mcp/**/*.py` and `skills/*/scripts/mcp/**/*.py` for `@mcp.tool(name=...)` registrations using two-stage regex (multi-line decorator support). Cross-reference to classify: `critical` (toolName in routes but not registered), `info` (registered but no route consumer), `ok` (wired). For each critical mismatch, compute edit distance against all registered tools — flag "likely typo" with suggested fix if distance ≤ 2.

### Phase 2: Runtime probe (requires running dev server)

POST `{ "tool": "<toolName>", "args": {} }` to `http://localhost:3000/api/mcp/tool` for each wired tool (10s timeout). Classify responses: `healthy` (200, no `_fallback`), `fallback-masked` (200, `_fallback: true`), `app-error` (200 with error field), `runtime-error` (500), `timeout`. Fingerprint errors by type: `ImportError`, `FileNotFoundError`, `TypeError: missing required argument` (mark `needs-args`, not broken), `KeyError`/`AttributeError`.

### Phase 3: Auto-fix (d>=2, safe cases only)

| Error | Fix | Reversible |
|-------|-----|------------|
| Route toolName typo (edit distance ≤ 2) | Patch `_routes-{a,b,c}.ts` | Yes (git) |
| `FileNotFoundError` on data dir | `mkdir -p` | Yes (rmdir) |
| Missing `scripts/mcp/__init__.py` | Scaffold empty with `register_tools` stub | Yes (git) |
| Syntax errors, logic bugs | Report only | N/A |

Safety: never modify Python tool logic. Never modify route configs beyond toolName string replacement. All changes uncommitted — user reviews before commit. Abort and report if a fix would touch more than 3 files.

### Phase 4: Report

Writes `get_runtime_dir() / "reports" / "mcp-health-report.md"` with YAML frontmatter counts and markdown tables for: wiring mismatches, runtime failures, fallback-masked tools, healthy tools (collapsed), orphan tools (informational). Emits `make_issue()` per finding, `FixResult` per applied fix, `evolution_gap()` when all checks pass at max difficulty.

### Difficulty schedule

| d | Phases | Runtime | Use case |
|---|--------|---------|----------|
| 0 | Static wiring only | ~5s | Quick CI check |
| 1 | Static + runtime probe | ~30-60s | Nightly validation |
| 2 | Static + runtime + auto-fix | ~60-90s | Weekly deep sweep |
| 3 | d2 + validate `transformResponse` field names | ~2min | Monthly deep validation |
| 4 | d3 + invoke `needs-args` tools with scaffolded args | ~3min | On-demand exhaustive audit |

Tier association in `SKILL.md` `x-augur-loop` frontmatter — not in centralized `adaptive_loops.yaml`.

### Relationship to existing scanners

`auto-api-wiring` targets individual `route.ts` files; this scanner targets `_routes-{a,b,c}.ts` proxy configs. Import `_collect_route_tool_names` and `_collect_mcp_registrations` from `auto-api-wiring` to avoid drift. `auto-test-mcp-commands` only reports pass/fail — this scanner classifies by error type and auto-fixes. `auto-mcp-hygiene` stub should be retired if this scanner subsumes its scope.

## Consequences

### Positive
- Unified picture of wiring health across all ~474 toolName references and all Python registrations
- Auto-fixes safe wiring typos and missing scaffolding without requiring human intervention
- `fallback-masked` classification surfaces the hidden failures that make pages silently empty
- Replaces three stagnating scanners with one that evolves via difficulty gating
- Implements full `OpsCommand` protocol — integrates with existing autoloop infrastructure

### Negative
- Phase 2 requires a running dev server — CI at d0 can run static-only, but full validation needs the dev environment
- Auto-fix is intentionally conservative (≤3 files, no logic changes) — many failures still require human review
- Consolidating overlapping scanners requires coordinated deprecation of `auto-api-wiring` runtime probe portions and `auto-mcp-hygiene` stub

### Neutral
- Reports are ephemeral (runtime dir) — not committed to git, not persisted across restarts
- `needs-args` tools are excluded from fix list at d2 and below; d4 scaffolds minimal args to probe them

## Alternatives Considered

### Extend `auto-api-wiring` instead of new scanner
Rejected: `auto-api-wiring` targets individual `route.ts` files (ADR-260 pattern), not the consolidated proxy config. Modifying it to cover both patterns would conflate two different wiring architectures. A new scanner with clear scope is cleaner.

### Fix wiring manually without a scanner
Rejected: 474 toolName references across 3 route files against dozens of Python files — manual cross-referencing is error-prone and doesn't give ongoing health monitoring.

### Auto-fix Python logic bugs
Rejected explicitly as non-goal. Auto-fixing logic bugs risks introducing new bugs silently. Only scaffolding and string replacements are safe enough to apply without review.

## References

- Source spec: `docs/superpowers/specs/2026-03-22-mcp-health-audit-design.md`
- ADR-443: Git-aware fix safety (`classify_fix()`)
- ADR-260: MCP proxy catch-all routes (`_routes-{a,b,c}.ts` structure)

## Impact Manifest

```yaml
files_added:
  - skills/auto-mcp-health-audit/SKILL.md
  - skills/auto-mcp-health-audit/scripts/mcp_health_audit.py
  - skills/auto-mcp-health-audit/augur/tests/test_mcp_health_audit.py

skills_to_retire:
  - skills/auto-mcp-hygiene/  # stub with no implementation; subsumed

patterns_deprecated:
  - auto-mcp-hygiene stub  # retire once this scanner covers its scope
```
