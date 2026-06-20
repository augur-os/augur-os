---
status: Implemented
date: 2026-03-17
deciders:
  - Gur Sannikov
related:
  - ADR-430
hub: dev
tags:
  - plugins
  - cleanup
  - migration
  - guardrails
superseded_by: null
---

# ADR-431: Plugin Distribution — Cleanup & Guardrails

> Sub-ADR of ADR-430. Phase 0 + Phase 0.5. Safe, reversible, no functional changes.

## Context

ADR-430 defines the full plugin distribution migration. This sub-ADR covers the prerequisite cleanup: normalizing 131 skill directories to a canonical structure, moving 7.3M of docs to vault, removing duplicates/garbage, and installing guardrails to prevent regression.

## Decision

Execute Phase 0 (cleanup, 8 steps) and Phase 0.5 (guardrails, 3 steps) from ADR-430.

## Implementation Prompt

**Team name**: `adr-431-cleanup`

### Gate 0: Pre-flight
Verify starting state: `.claude/skills/` has 131+ skill directories. `docs/decisions/` has 283 ADRs. No uncommitted changes on main.

### Batch A: Parallel cleanup (all independent)
**Strategy**: PARALLEL via team agents

| Agent | Task | Files |
|-------|------|-------|
| `garbage` | Delete all `.DS_Store` (26), `__pycache__/` dirs. Add to `.gitignore`. | `.gitignore`, `.claude/skills/` |
| `generated` | Delete auto-generated: `augur/README.md`, `augur/api/tsconfig.json`, `augur/dashboard/tsconfig.json` from all 131 skills. Add to `.gitignore`. | `.claude/skills/*/augur/` |
| `user-data` | Move user artifacts to vault: career reports (xlsx/html), apple voice memos (m4a), finance docx. `git rm --cached`. Add gitignore patterns. | `.claude/skills/{career,apple,finance}/assets/` |
| `prompts` | Delete `augur/data/prompts/` everywhere (stale). Delete empty `augur/data/`. Merge `assets/prompts/` into `assets/seed-data/prompts/` (keep richer version). Delete `assets/prompts/`. Update code refs. | `.claude/skills/*/augur/data/`, `.claude/skills/*/assets/prompts/` |
| `seeds` | Rename `assets/seed-data/` → `assets/seeds/` across all skills. Update all code references (grep `seed-data`). | `.claude/skills/*/assets/seed-data/` |
| `docs` | Move to vault: (1) `docs/decisions/*.md` → `~/Vault/Augur/dev/adrs/`. (2) `docs/plans/` → `~/Vault/Augur/dev/plans/`. (3) `docs/superpowers/specs/` → `~/Vault/Augur/dev/specs/`. (4) `docs/superpowers/plans/` → `~/Vault/Augur/dev/impl-plans/`. (5) Delete dead: `docs/archive/`, `docs/content/`, `docs/memory/`, `docs/exec-plans/`. (6) Update `src/lib/adr_utils.py` ADR_DIR to vault. (7) Update `generate_adr_index.py` to scan vault. (8) Update CLAUDE.md. | `docs/`, `src/lib/adr_utils.py`, `.github/scripts/generate_adr_index.py`, `CLAUDE.md` |
| `adr-plan` | Update `/adr plan` subcommand: after converting spec to ADR, move source from `docs/superpowers/specs/` to `~/Vault/Augur/dev/specs/`. | `.claude/skills/dev-adr/SKILL.md` |
| `metadata` | Delete: `.config` (131 skills), `augur/version.yaml` (~50), per-skill `requirements.txt` (~5). Fix finance `data_dir: .` → `finance`. Report non-standard `.config` values. | `.claude/skills/*/.config`, `.claude/skills/*/augur/version.yaml` |

### Gate 1: Cleanup verification
All agents must complete. Then verify:
- `find .claude/skills -name .DS_Store | wc -l` = 0
- `find .claude/skills -name __pycache__ -type d | wc -l` = 0
- `find .claude/skills -name 'augur.yaml' -path '*/augur/augur.yaml' | wc -l` = unchanged (Phase 1 deletes these)
- `find .claude/skills -name .config | wc -l` = 0
- `find .claude/skills -path '*/augur/data' -type d | wc -l` = 0
- `find .claude/skills -path '*/assets/prompts' -type d | wc -l` = 0
- `find .claude/skills -path '*/assets/seed-data' -type d | wc -l` = 0
- `ls docs/decisions/ | wc -l` = 0 (moved to vault)
- `ls ~/Vault/Augur/dev/adrs/ | wc -l` = 283+
- `/adr query 430` returns ADR from vault
- `npm run build` passes
- `pytest` passes

### Batch B: Guardrails (all independent)
**Strategy**: PARALLEL via team agents

| Agent | Task | Files |
|-------|------|-------|
| `precommit` | Create `.github/scripts/validate_skill_structure.py` with all banned pattern checks (no .config, no augur.yaml after Phase 1, no augur/data/, no assets/prompts/, no user media, SKILL.md required). Add to `.pre-commit-config.yaml`. Test: attempt to commit a `.config` file → blocked. | `.github/scripts/validate_skill_structure.py`, `.pre-commit-config.yaml` |
| `plugin-hook` | Create `hooks/check-skill-structure` script for PostToolUse on Write/Edit. Warns when writing to deprecated paths. Test: write to `augur/data/x.md` → warning in transcript. | `hooks/check-skill-structure` |
| `adaptive` | Create `auto-skill-structure` adaptive command. SKILL.md + scanner script. Scans for all banned patterns + structure violations. Test: create banned file, run scan → found. | `.claude/skills/auto-skill-structure/` |

### Gate 2: Final verification
- `echo "test" > .claude/skills/test-skill/.config && git add . && git commit -m "test"` → blocked by pre-commit
- Clean up test file
- `auto-skill-structure` reports zero violations
- All changes committed cleanly

### Completion Criteria
- [ ] Zero garbage files in `.claude/skills/`
- [ ] Zero duplicate prompt locations
- [ ] All `assets/seed-data/` renamed to `assets/seeds/`
- [ ] Zero per-skill metadata files (.config, version.yaml, requirements.txt)
- [ ] No user data in git
- [ ] 283 ADRs in vault, `/adr query` works
- [ ] `/adr plan` moves superpowers specs to vault
- [ ] Pre-commit hook blocks banned patterns
- [ ] Plugin PostToolUse hook warns on deprecated paths
- [ ] `auto-skill-structure` scan finds zero violations
- [ ] ADR-431 status → Implemented
