---
status: Implemented
date: '2026-04-20'
deciders:
- Gur Sannikov
related:
- ADR-404
- ADR-537
- ADR-551
hub: command
tags:
- release
- staging
- skills
- mvp
- porting
superseded_by: null
implemented_date: '2026-04-14'
implementation_commits:
- 167a9732e7
- 7d9d2e273b
- 715eca4550
- bffada22fe
- 46f7826a6d
- 556c0354ab
- 214291954e
- 70c8ebf675
---

# ADR-557: MVP Main And Staged Release Payloads

## Context

ADR-551 introduced `x-augur-group` and `x-augur-release` as the planning model for first-party skills, but release tags alone did not make the repository operationally clear. The live `skills/` tree still mixed MVP skills with future-release skills, and staged release folders existed as workflow concepts before they were real payloads.

The product needed a concrete structure where `main` represents the current shipped MVP surface and future releases are curated as staged payloads that can later be ported deliberately.

## Decision

Make the main checkout's live `skills/` tree MVP-only and move non-MVP skills into staged release payload folders:

```text
staging/r1/
staging/r2/
staging/r3/
staging/r4/
staging/later/
```

Each staged release folder contains `skills/`, `pages/`, and `manifest.md`. The release tag remains in each skill's `SKILL.md`; the file move changes the operational location, not the shipping label.

Add porting payload utilities and operator commands so staged releases can be validated, initialized, and ported into canonical `main` locations later. Staged payloads are not a runnable shadow app and should not carry unrelated infrastructure work.

## Consequences

Positive:

- `main` more accurately represents the current MVP product surface.
- Future releases exist as concrete, reviewable payloads rather than abstract tags scattered through `skills/`.
- Porting work has a manifest-driven entrypoint.
- Release matrix generation can report live and staged skill locations.

Negative:

- Discovery, generated artifacts, and tests must understand both live `skills/` and staged payload roots.
- Some workflows now need to distinguish live skills from future staged skills.

Neutral:

- `x-augur-release` remains the canonical release label.
- Staged payloads are curated files, not a second source-of-truth runtime tree.

## Implementation Evidence

Key implementation files:

- `src/lib/porting_payload.py`
- `src/lib/mvp_staging_migration.py`
- `src/lib/staged_skill_catalog.py`
- `src/lib/skill_release_matrix.py`
- `scripts/manage_porting_payload.py`
- `scripts/migrate_non_mvp_to_staging.py`
- `skills/platform-admin/commands/stage-release.md`
- `skills/platform-admin/commands/port-release.md`
- `skills/platform-admin/commands/release.md`
- `staging/README.md`
- `staging/r1/manifest.md`
- `staging/r2/manifest.md`
- `staging/r3/manifest.md`
- `staging/r4/manifest.md`
- `staging/later/manifest.md`

Representative tests:

- `tests/unit/test_porting_payload.py`
- `tests/scripts/test_manage_porting_payload.py`
- `tests/unit/test_mvp_staging_migration.py`
- `tests/scripts/test_migrate_non_mvp_to_staging.py`
- `tests/unit/test_release_workspace.py`

## Alternatives Considered

### Keep All Skills In `skills/` And Rely On Release Tags

Rejected. Tags are useful metadata, but they do not stop future-release code and pages from living in the current product tree.

### Maintain A Runnable Porting Branch As A Shadow App

Rejected. A shadow app would drift from `main`. Staged payloads should be adapted into current infrastructure when ported.

### Copy Instead Of Move Non-MVP Skills

Rejected. Duplicating skills would create two mutable copies and obscure which one is canonical.

## References

Absorbed transient artifacts:

- `docs/superpowers/specs/2026-04-14-porting-branch-release-staging-design.md`
- `docs/superpowers/plans/2026-04-14-porting-branch-release-staging.md`
- `docs/superpowers/specs/2026-04-14-mvp-main-staging-migration-design.md`
- `docs/superpowers/plans/2026-04-14-mvp-main-staging-migration.md`

## Impact Manifest

```yaml
paths_renamed:
  - skills/<non-mvp-skill>/ -> staging/<release>/skills/<skill>/
apis_changed:
  - src/lib/porting_payload.py: validates staged release payload folders
  - scripts/manage_porting_payload.py: manages staged release payloads
  - scripts/migrate_non_mvp_to_staging.py: migrates non-mvp skills into staging
patterns_deprecated:
  - storing future release skills directly in live skills/ on main
files_affected:
  - src/lib/porting_payload.py
  - src/lib/mvp_staging_migration.py
  - src/lib/staged_skill_catalog.py
  - src/lib/skill_release_matrix.py
  - scripts/manage_porting_payload.py
  - scripts/migrate_non_mvp_to_staging.py
  - skills/platform-admin/commands/stage-release.md
  - skills/platform-admin/commands/port-release.md
  - skills/platform-admin/commands/release.md
  - staging/README.md
  - staging/r1/manifest.md
  - staging/r2/manifest.md
  - staging/r3/manifest.md
  - staging/r4/manifest.md
  - staging/later/manifest.md
```
