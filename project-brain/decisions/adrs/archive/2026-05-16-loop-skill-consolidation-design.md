---
date: 2026-05-16
status: Draft
adr: ADR-756
deciders:
  - gsannikov
related:
  - ADR-601
  - ADR-727
  - ADR-755
---

# Loop-Skill Consolidation — Design

> Design spec for **ADR-756**. Companion to `docs/adrs/ADR-756-loop-skill-consolidation.md`.

## Goal

Consolidate the 11 historical `loop-*` skills into 5 concern-aligned `routine-*` skills. Each auto-command (and its supporting Python module + frontmatter declaration) moves to exactly one new skill. The runner is not touched; loop categories (`testing`, `hardening`, ...) are not renamed; only skill *ownership* changes.

## Current state (audited)

```
shared-vault/skills/
├── loop-test         (11 auto-commands)
├── loop-wiring       (9 auto-commands)
├── loop-ops          (7 auto-commands)
├── loop-docs         (6 auto-commands)
├── loop-repo         (5 auto-commands)
├── loop-hub-coverage (5 auto-commands)
├── loop-quality      (4 auto-commands)
├── loop-observability (3 auto-commands)
├── loop-memory       (2 auto-commands)
├── loop-security     (1 auto-command)
└── loop-hygiene      (0 auto-commands — empty leftover)
```

## Target state

```
shared-vault/skills/
├── routine-codebase   (~24 auto-commands: from loop-test + loop-quality + loop-wiring)
├── routine-platform   (~13 auto-commands: from loop-ops + loop-observability + git-related from loop-repo)
├── routine-vault      (~8 auto-commands: from loop-memory + vault-related from loop-repo + doc-freshness from loop-docs)
├── routine-coverage   (~7 auto-commands: from loop-hub-coverage + skill-usage from loop-docs)
└── routine-security   (1 auto-command: from loop-security)
```

(Exact per-command splits resolved during Task 0 audit; the plan starts with a per-auto-command classification before any moves.)

## Migration mechanism

For each auto-command:

1. `git mv shared-vault/skills/<old-skill>/commands/<auto-name>.md shared-vault/skills/<new-skill>/commands/`
2. `git mv shared-vault/skills/<old-skill>/scripts/<ops-module>.py shared-vault/skills/<new-skill>/scripts/`
3. Update the destination SKILL.md's `x-augur-commands:` block to include the new entry (with the same `callable:` relative path)
4. Remove the entry from the source SKILL.md's `x-augur-commands:` block
5. Update any `import` paths in the moved Python file if it imported from sibling modules in the old skill (resolved via grep)

For each new skill:

1. Create `shared-vault/skills/<new-skill>/SKILL.md` with proper frontmatter (name, hub, type, tags, concern statement)
2. Create `shared-vault/skills/<new-skill>/scripts/__init__.py` marker
3. Create `shared-vault/skills/<new-skill>/commands/` directory
4. Move auto-commands in per above

For each old skill (after all its auto-commands have moved out):

1. Confirm empty (no remaining `auto-*.md`, no remaining `scripts/*.py` besides `__init__.py`)
2. `git rm -r shared-vault/skills/<old-skill>/`

## Cross-references to update

Audited during planning — every reference in docs / configs / scripts that names a `loop-*` skill path:

- `config/system/adaptive_loops.yaml` — per-skill paths if any (check `discover` blocks)
- `docs/architecture-daemon.md` — explicit references to `loop-test`, `loop-quality`, etc.
- `docs/architecture-sdlc.md` — references to specific auto-commands by skill path
- `shared-vault/skills/daemon/scripts/adaptive/discovery.py` — if it hardcodes any skill prefix filter
- Any test fixture that pointed at a `loop-*` path

The plan's Task 0 (audit) produces a complete grep manifest before any moves. Migration tasks consume the manifest.

## Risks

- **Hidden cross-skill imports.** Some `scripts/*_ops.py` files might `from shared-vault.skills.loop-other...` import sibling-skill helpers. Mitigation: Task 0 grep audit; any cross-skill imports get refactored to common module before the move (likely under `shared-vault/skills/daemon/scripts/` or a new `shared-vault/skills/routine-common/`).
- **sync_agents regeneration drift.** Each migration tweaks SKILL.md frontmatter; sync_agents must re-run after each commit to keep client-side artifacts coherent. Mitigation: regen + verify in every migration task.
- **Trust state references by skill path.** Trust ledger persists per-category state — if anything keys on skill-path it breaks. Mitigation: Task 0 verifies trust state is keyed by `loop.category` (e.g. `testing.auto-test-build`), NOT by skill path. (Verified during ADR write: it is.)

## Phasing

Phase 1: Audit (Task 0) — produce the full migration manifest. No file changes. Output: a per-auto-command mapping table (current location → destination skill) + cross-reference grep results.

Phase 2: Create 5 new skill scaffolds in parallel (5 teammates).

Phase 3: Migrate auto-commands per the audit manifest — one teammate per *source* skill (so 11 teammates can run in parallel without git-mv collisions). Within each source skill teammate, sequential migration of each auto-command.

Phase 4: Delete the now-empty `loop-*` skill directories. One commit per deletion.

Phase 5: Cross-reference updates (docs, configs). Sync_agents regen. Full test suite + auto-loop registry verification.

Phase 6: ADR status flip.
