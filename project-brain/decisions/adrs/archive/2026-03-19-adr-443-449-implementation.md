# ADR 443-449 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close all gaps across ADRs 443-449 using parallel agent execution.

**Architecture:** 4 phases, dependency-ordered. Each phase dispatches independent agents in parallel.

---

## Phase 1: Independent fixes (all parallel)

### Agent A: ADR-449 gap fix — vault-status health_score
- Add `health_score` field to vault-status MCP tool
- Read last hygiene scan result or compute inline from 7 checks
- File: `src/mcp/augur_mcp/tools/internal/vault_status.py`

### Agent B: ADR-448 — skills.sh naming fix
- Rename `skillstore-sh-*` MCP tools to `skills-sh-*`
- Update all references in skillstore skill
- Files: `.claude/skills/skillstore/scripts/mcp/__init__.py`, cursor rules

### Agent C: ADR-443 — seed generation fix
- Fix `_generate_seeds()` to read `.tsx` page components for data shape inference
- File: `.claude/skills/auto-skill-quality/scripts/skill_quality_ops.py`

### Agent D: ADR-444 — engine LLM dispatch
- Wire adaptive engine to detect `llm_fix()` on loop modules
- Dispatch via `build_headless_cmd()` with safety harness
- Add git snapshot, build verify, revert, budget 3x, turn limit, timeout
- Files: `.claude/skills/daemon/scripts/adaptive/engine_escalation.py`, `adaptive_loop_executor.py`

## Phase 2: Depends on Phase 1

### Agent E: ADR-446 — fix() LLM fallback (depends on 444)
- Wire `fix()` in skill_quality_ops.py to call `llm_fix()` at d3+ when file fixes plateau
- Add `--upgrade N` manual trigger flag
- File: `.claude/skills/auto-skill-quality/scripts/skill_quality_ops.py`

### Agent F: ADR-447 — standalone deep-dive page
- Move SkillGateVisualizer from venture-augur demo to standalone page
- Remove old location, update routes
- Files: venture-augur dashboard components, new standalone route

## Phase 3: Hub restructuring (depends on 447)

### Agent G: ADR-445 — assembly engine
- Build tab assembly layer in hub assembly that composes sections from multiple skills
- Add 12-column CSS grid with grid-span declarations
- Files: `apps/dashboard/lib/plugin-discovery/scanner.ts`, `apps/dashboard/scripts/mount/hub-assembly.ts`

### Agents H-L: ADR-445 — per-hub skill migration (5 agents, 1 per hub)
- Each agent handles ~24 skills for one target hub
- Update `x-augur-tab` frontmatter on each skill's SKILL.md
- Agent H: brain hub (~13 skills)
- Agent I: career hub (~22 skills)
- Agent J: life hub (~37 skills)
- Agent K: studio hub (~16 skills)
- Agent L: command hub (~15 skills)

## Phase 4: Verification

### Agent M: Gap re-scan
- Run `/adr gaps 443-449` — all gaps should be zero

### Agent N: Harden each ADR
- Run gate verification on all 7 ADRs
- Update status to Implemented for all that pass
