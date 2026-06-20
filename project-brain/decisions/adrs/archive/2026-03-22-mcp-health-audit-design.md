# MCP Health Audit — Design Spec

## Problem

Most dashboard pages show empty data because:
1. **Wiring mismatches** — proxy route `toolName` values don't match actual `@mcp.tool(name=...)` registrations in Python
2. **Broken tools** — registered MCP tools fail at runtime (import errors, missing data dirs, bad code)

The proxy's `fallback` config masks these failures — pages render empty data instead of errors, so the user sees nothing rather than an actionable error.

Existing auto-loops (`auto-api-wiring`, `auto-test-mcp-commands`, `auto-block-wiring`) cover parts of this but:
- Don't auto-fix anything
- Are stagnating (streak 3+)
- Don't produce a unified picture

## Solution

A new auto-command `auto-mcp-health-audit` with 4 sequential phases, usable both as a one-time sweep and as a permanent autoloop.

## Architecture

```
.claude/skills/auto-mcp-health-audit/
├── SKILL.md
├── scripts/
│   └── mcp_health_audit.py       # main script
└── augur/
    └── tests/
        └── test_mcp_health_audit.py
```

```
Phase 1 (d>=0)      Phase 2 (d>=1)       Phase 3 (d>=2)      Phase 4 (always)
Static Wiring   ──▶  Runtime Probe   ──▶  Auto-Fix       ──▶  Report
Audit                                     (safe cases)
```

**Inputs:**
- `apps/dashboard/app/api/[...proxy]/_routes-{a,b,c}.ts` — ~474 toolName references across all HTTP methods (329 static + 38 dynamic route paths, many with multiple methods)
- `src/mcp/augur_mcp/**/*.py` — core/infrastructure/domain tool registrations
- `.claude/skills/*/scripts/mcp/**/*.py` — client-native plugin tools (includes sub-modules like `_gmail.py`, `tools_memory_core.py`, etc.)
- Live MCP server via `http://localhost:3000/api/mcp/tool` (Phase 2 only)

**Outputs:**
- Runtime report via `ops_protocol.write_report()` to `get_runtime_dir() / "reports"` — ephemeral scan results
- ops_protocol findings for autoloop integration (`make_issue()`, `FixResult`, `evolution_gap()`)
- Uncommitted file changes for auto-fixes (user reviews before commit)

## Phase 1: Static Wiring Audit

Runs without the MCP server. Pure file parsing.

### Step 1a: Extract route toolNames
- Parse `_routes-{a,b,c}.ts` files
- Regex: extract every `toolName: "..."` value
- Result: `dict[toolName, list[route_path]]`

### Step 1b: Extract MCP registrations
- Scan `src/mcp/augur_mcp/**/*.py` for core/infrastructure/domain tools
- Scan `.claude/skills/*/scripts/mcp/**/*.py` for client-native plugin tools (includes sub-modules like `_gmail.py`, `tools_memory_core.py`, `_loops.py`, etc.)
- Two-stage regex (matches multi-line decorators per `auto-api-wiring` pattern):
  1. Extract decorator blocks: `re.finditer(r"@mcp\.tool\([^)]*\)", content, re.DOTALL)`
  2. Extract name from each block: `re.search(r'name\s*=\s*"\'["\']', block)`
- Result: `dict[tool_name, python_file_path]`

### Step 1c: Cross-reference

| Finding | Meaning | Severity |
|---------|---------|----------|
| toolName in routes but NOT in registrations | Wiring mismatch — page will always fail | critical |
| toolName in registrations but NOT in routes | Orphan tool — no dashboard consumer | info |
| toolName in routes AND registrations | Wired — candidate for Phase 2 | ok |

### Step 1d: Fuzzy match for mismatches
- For each critical mismatch, compute edit distance against all registered tools
- If close match exists (distance <= 2), flag as "likely typo" with suggested fix

## Phase 2: Runtime Probe

Requires a running MCP server and dashboard dev server.

### Invocation method
- For each wired tool from Phase 1, POST `{ "tool": "<toolName>", "args": {} }` to `http://localhost:3000/api/mcp/tool`
- Timeout: 10s per tool

### Response classification

| HTTP Status | Response Body | Classification |
|-------------|--------------|----------------|
| 200, no `_fallback` | Valid data | **healthy** |
| 200, `_fallback: true` | Fallback fired | **fallback-masked** |
| 200, `error` field | App-level error | **app-error** |
| 500 | Error JSON | **runtime-error** |
| Timeout | — | **timeout** |

### Error fingerprinting
- `ImportError` / `ModuleNotFoundError` → missing dependency or bad import path
- `FileNotFoundError` → missing data dir or file
- `TypeError: missing required argument` → tool needs args (mark `needs-args`, not broken)
- `KeyError` / `AttributeError` → logic bug
- Connection refused → MCP server down (abort remaining probes)

Tools that fail only because they require specific args are marked `needs-args` and excluded from the fix list.

## Phase 3: Auto-Fix

Only runs at difficulty >= 2. Applies safe, predictable fixes. Never touches logic.

| Error Pattern | Auto-Fix Action | Reversible? |
|---------------|----------------|-------------|
| Route `toolName` typo (edit distance <= 2) | Patch `_routes-{a,b,c}.ts` with correct name | Yes (git) |
| `FileNotFoundError` on a data dir path | `mkdir -p` the missing directory | Yes (rmdir) |
| `ModuleNotFoundError` for missing `scripts/mcp/__init__.py` | Scaffold empty `__init__.py` with `register_tools` stub | Yes (git) |
| Syntax error in `scripts/mcp/__init__.py` | Report only | N/A |
| `ImportError` for known path patterns | Report only | N/A |
| Logic bugs (`KeyError`, `AttributeError`) | Report only | N/A |

### Safety rules
- Never modify Python tool logic — only scaffolding and directory creation
- Never modify route configs beyond toolName string replacement
- All file changes are uncommitted — report shows what changed for user review
- If a fix would affect more than 3 files, abort that fix and report instead

## Phase 4: Report

### Output file: `get_runtime_dir() / "reports" / "mcp-health-report.md"`

```markdown
---
generated: <timestamp>
phase1_routes: <N>
phase1_registered: <N>
phase1_mismatches: <N>
phase2_healthy: <N>
phase2_fallback_masked: <N>
phase2_errors: <N>
phase3_auto_fixed: <N>
phase3_needs_human: <N>
---

## Critical: Wiring Mismatches
| Route Path | toolName in Route | Closest Registration | Distance | Auto-Fixed? |

## Runtime Failures
| Tool Name | Error Type | Error Message | File | Auto-Fixed? |

## Fallback-Masked
| Route Path | toolName | Fallback Data | Reason |

## Healthy
<collapsed summary>

## Orphan Tools
<informational>
```

### ops_protocol integration
- Emits `make_issue()` for each wiring mismatch or runtime failure
- Returns `FixResult` with `changes` and `fix_type="code-fix"` for each applied fix
- Uses `classify_fix()` for git-aware fix safety (ADR-443 — prevents re-creating recently deleted files)
- Emits `evolution_gap()` when all checks pass at max difficulty
- Implements full `OpsCommand` protocol: module-level `DIFFICULTY_SPEC`, `name`, `scan()`, `fix()` functions

## Autoloop Integration

Tier association goes in `SKILL.md` `x-augur-loop` frontmatter (per CLAUDE.md rule 2 — decentralized), not in the centralized `adaptive_loops.yaml` config.

| Difficulty | Phases | Runtime | Use Case |
|------------|--------|---------|----------|
| 0 | Static wiring only | ~5s | Quick CI check |
| 1 | Static + runtime probe | ~30-60s | Nightly validation |
| 2 | Static + runtime + auto-fix | ~60-90s | Weekly deep sweep |
| 3 | d2 + validate `transformResponse` field names match MCP tool output keys | ~2min | Monthly deep validation |
| 4 | d3 + invoke `needs-args` tools with scaffolded minimal args | ~3min | On-demand exhaustive audit |

### Evolution behavior (CLAUDE.md rule 8)
When all tools are healthy at d2, report `evolution_gap()` identifying:
- Tools marked `needs-args` that were skipped
- Routes with complex `transformResponse` that could silently corrupt data
- New tools added since last run

## Relationship to existing scanners

| Scanner | Overlap | Distinction |
|---------|---------|-------------|
| `auto-api-wiring` | Phase 1 static cross-ref is similar | This scanner targets `_routes-{a,b,c}.ts` proxy configs specifically; `auto-api-wiring` targets individual `route.ts` files. Consider importing `_collect_route_tool_names` and `_collect_mcp_registrations` from `auto-api-wiring` to avoid drift. |
| `auto-test-mcp-commands` | Phase 2 runtime probe overlaps | This scanner classifies failures by error type and auto-fixes; `auto-test-mcp-commands` only reports pass/fail. |
| `auto-mcp-hygiene` | Tool naming/registration audit | **Retired.** Stub skill deleted; real implementation lives in `skills/daemon/scripts/ops/mcp_hygiene.py`. |

## Non-goals
- Not testing full functional correctness of tools — Phase 2 tests reachability, not business logic
- Not auto-fixing Python logic bugs — only scaffolding and wiring
