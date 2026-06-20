# Remaining ADR Implementation Gaps

> Context from 2026-03-19 session. Load this file at the start of a new session to continue the work.

## Priority 1: ADR-443 — Auto-Loop Safety (Accepted, ready to implement)

**File:** `get_vault_dir()/dev/adrs/ADR-443-autoloop-safety-git-aware-fixes.md`

**What:** Auto-loops silently revert intentional architectural changes by applying workarounds without checking git history. Example: ADR-430/431 deleted augur.yaml files, auto-loops recreated them as "fixes" for broken blocks.

**Implementation needed:**
1. Add `_check_git_deletion_history(path)` helper to `src/lib/ops_protocol.py`
2. Add `classify_fix(fix_type, target_path)` returning Safe/Structural/Reverting
3. Modify `.claude/skills/daemon/scripts/adaptive/engine_fix_phase.py` to call `classify_fix()` before applying any fix
4. Safe fixes: apply at any difficulty. Structural: report only at d0-1, apply with logging at d2+. Reverting: always block + alert.

**Memory:** See `feedback_autoloop-regression-patterns.md` for full context.

---

## Priority 2: ADR-417 — Upgrade Report-Only Auto-Commands

### 2a. `auto-markers` TODO_CLEANUP application (High)
**File:** `.claude/skills/auto-markers/scripts/markers.py`
**Current:** `fix()` calls `scan_and_update()` which writes a report. `fix_type="report"`.
**Needed:** At difficulty >= 1, apply TODO_CLEANUP cleanups when the marker has clear inline instructions. Set `fix_type="code-fix"` when changes applied.

### 2b. `auto-debt-scan` marker injection + helper extraction (High)
**File:** `.claude/skills/devops/scripts/ops/debt_scan.py`
**Current:** `fix()` writes a markdown debt report. `fix_type="report"`.
**Needed:** At difficulty >= 1, inject `TODO_CLEANUP` markers for 800+ line files. At difficulty >= 2, attempt helper extraction for 1600+ line files. Set `fix_type="code-fix"`.

### 2c. Already done (this session):
- `auto-code-review` eslint --fix -- delegates to auto-lint's `_fix_eslint_auto()`, committed
- `auto-mcp-hygiene` verb rename -- was already implemented

---

## Priority 3: ADR-412 — Adaptive Loop Hotspot System (High)

**File:** `get_vault_dir()/dev/adrs/ADR-412-adaptive-loop-adaptivity.md`

**What's missing:** Phase 3 hotspot-first deepening never built.
- `hot_paths`, `hot_patterns`, `dominant_root_cause` — zero matches in codebase
- Need to persist hotspot data between cycles
- Two-phase execution mostly exists but most categories still single-phase

**Where to implement:**
- `.claude/skills/daemon/scripts/adaptive/cycle_helpers.py` — add hotspot tracking
- `.claude/skills/daemon/scripts/adaptive/snapshot.py` — add hotspot fields to shared snapshot
- `src/lib/ops_protocol.py` — add hotspot fields to issue protocol

---

## Priority 4: ADR-434 — Migration Verification Test Harnesses (Critical but Large)

**File:** `get_vault_dir()/dev/adrs/ADR-434-plugin-migration-verification.md`

**What's missing:** All 7 test categories are entirely unimplemented:
1. `test-fresh` — fresh install simulation (CLI only)
2. `test-full` — fresh install (full stack, all pages render)
3. `test-migrate` — existing user migration preserves personal skills
4. `test-parity` — per-plugin skill parity verification
5. `test-sync` — cross-client sync discovers plugin masters
6. `test-adr` — ADR system works e2e from vault
7. `test-rollback` — plugin uninstall/reinstall restores state

**Recommendation:** Start with `test-adr` (smallest scope, we just fixed the ADR system) and `test-parity` (most valuable for catching regressions).

---

## Completed This Session (for reference)

| What | Commit/Status |
|------|---------------|
| `/skillstore` skill (skills.sh + GitHub search) | 7 MCP tools, 12 tests |
| 293 ADRs restored to vault | `get_vault_dir()/dev/adrs/` |
| 7 lost ADRs reconstructed (436-442) | Marked [RECONSTRUCTED] |
| 46 plans + 29 specs restored | `get_vault_dir()/dev/{plans,specs}/` |
| 7 augur.yaml deleted (ADR-430/431) | `35b4269` |
| Sync engine plugin cache (ADR-430/432) | 3 functions fixed |
| Daemon hardcoded paths (ADR-430/432) | 5 files |
| Path chains fixed (~40 files total) | ADR-432 |
| auto-code-review eslint --fix (ADR-417) | Delegates to auto-lint |
| dist/ cleanup (.DS_Store, __pycache__, tsconfig) | Disk cleanup |
| auto-coverage-check SKILL.md + PostToolUse hook | ADR-417/431 |
| ADR-443 written and accepted | Auto-loop safety |
| **ADR-443 implemented** | `dc74a60` — fix classification gate, 15 tests |
| **ADR-417 auto-markers upgrade** | `349b5b5` — TODO_CLEANUP resolution at d>=1 |
| **ADR-417 auto-debt-scan upgrade** | `349b5b5` — marker injection at d>=1, extraction at d>=2 |
| **ADR-412 Phase 3 hotspots** | `b6d9523` — hot_paths, hot_patterns, dominant_root_cause tracking |

## How to Use This File

```
/ask load docs/superpowers/plans/2026-03-19-remaining-adr-gaps.md
```

Or just paste: "Continue work from docs/superpowers/plans/2026-03-19-remaining-adr-gaps.md — start with Priority 1 (ADR-443)"
