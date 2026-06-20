---
status: Implemented
date: 2026-04-14
deciders:
- Gur Sannikov
related:
- ADR-524
- ADR-537
- ADR-541
hub: null
tags:
- skills
- release
- augur-os
- dashboard
- build
superseded_by: null
---

# ADR-551: Skill Group And Release Enablement

## Context

Augur currently mixes several unrelated concerns inside skill metadata and
catalog behavior:

- catalog visibility
- "internal" versus "public" semantics
- launch readiness
- release scope
- repository copying to `augr-os`

That model no longer matches how the product is actually being shipped.

The real workflow is:

1. all first-party skills live together in the private development repo
2. the development repo should stay flat so every skill remains available while
   it is being built
3. each skill still needs a stable classification so the catalog, review
   process, and release planning are understandable
4. `augr-os` release builds should only include the skills enabled for the
   target release stage
5. pages and generated dashboard artifacts for disabled skills must not survive
   into the released build
6. if an enabled skill depends on a disabled skill, the release build must fail
   instead of silently degrading

The current `x-augur-category: augur-internal` pattern is not a good fit for
that workflow. It overloads a browse/catalog decision into a release-planning
mechanism and forces user-facing-but-not-ready skills into the same bucket as
true operator/system surfaces.

## Decision

Augur will standardize skill planning on two explicit frontmatter fields:

- `x-augur-group`
- `x-augur-release`

### 1. Group Tag

Every first-party skill under `skills/` must declare exactly one
`x-augur-group` from this enum:

- `augur_core`
- `augur_autoloops`
- `augur_admin`
- `brain`
- `productivity`
- `business`
- `career`
- `life`
- `websites`
- `templates`
- `dev`
- `other`

The group tag is descriptive only. It classifies what kind of skill something
is, but it does not decide whether that skill ships in a release.

### 2. Release Tag

Every first-party skill under `skills/` must declare exactly one
`x-augur-release` from this enum:

- `mvp`
- `r1`
- `r2`
- `r3`
- `later`

The release tag is the shipping decision axis.

### 3. Cumulative Release Semantics

Release enablement is cumulative:

- target `mvp` enables only skills tagged `mvp`
- target `r1` enables `mvp + r1`
- target `r2` enables `mvp + r1 + r2`
- target `r3` enables `mvp + r1 + r2 + r3`
- `later` is excluded until the skill is explicitly re-tagged

### 4. Development Repo Behavior

The development repo stays flat:

- all first-party skills remain present in the private repo
- catalog hiding is not used as a release-planning proxy
- `x-augur-category` is no longer the planning model

This ADR retires category-based planning. Any surviving `x-augur-category`
reads are transitional compatibility only and must not drive release scope.

### 5. Release Build Behavior

Release output to `augr-os` is computed from the target release tag.

For a release target, the pipeline must:

1. copy or check out the release workspace
2. compute the enabled skill set from cumulative release semantics
3. fail immediately if enabled skills depend on disabled skills
4. remove disabled skills from the release workspace
5. regenerate derived manifests and dashboard artifacts from the reduced skill
   tree
6. verify that dashboard mount/build discovery only sees enabled skills

This means release scope is enforced structurally, not inferred afterward from
UI filtering.

### 6. Dashboard/Page Gating

Dashboard assembly must consume only the enabled skill set in release builds.

If a skill is not enabled for the target release:

- its files do not remain in the release workspace
- its pages are not mounted
- generated wrappers are not emitted
- hub registries and tab registries do not include it
- routes that depend on it do not survive into the release build

If an enabled skill depends on a disabled skill, the build fails. No warning
mode, partial mount, or best-effort stripping is allowed for release output.

### 7. Release Matrix Record

The canonical raw source of truth remains per-skill frontmatter. The durable
release-planning record is:

- this ADR for the model and release contract
- a generated matrix artifact derived from skill frontmatter
- release-specific ADR updates when the staged release plan materially changes

The first implementation pass will add a generated
`docs/generated/skill-release-matrix.json` artifact and update this ADR with a
snapshot summary derived from the tagged skills.

## Current Release Snapshot

Current release motives:

- `mvp` -> core autonomous brain
- `r1` -> personal operating system
- `r2` -> creation and work expansion
- `r3` -> admin, builder, and experimental surfaces
- `later` -> deferred templates and non-priority shells

Current per-tag counts from
`<repo>/docs/generated/skill-release-matrix.json`:

- `mvp`: 20 skills
- `r1`: 9 skills
- `r2`: 8 skills
- `r3`: 10 skills
- `later`: 3 skills

Current cumulative release targets:

- `mvp`: 20 enabled skills
- `r1`: 29 enabled skills
- `r2`: 37 enabled skills
- `r3`: 47 enabled skills

Current tagged release map:

### MVP — Core Autonomous Brain

- `ai`
- `apple`
- `augur-core`
- `auto-skill-quality`
- `daemon`
- `document-extractor`
- `eisenhower`
- `file-manager`
- `google-workspace`
- `knowledge`
- `loop-docs`
- `loop-hub-coverage`
- `loop-memory`
- `loop-observability`
- `loop-ops`
- `loop-quality`
- `loop-repo`
- `loop-test`
- `loop-wiring`
- `rag`

### R1 — Personal Operating System

- `attention`
- `books`
- `channels`
- `finance`
- `health`
- `home-automation`
- `lifestyle`
- `obsidian`
- `onboard`

### R2 — Creation And Work Expansion

- `career-ops`
- `content`
- `import`
- `ingest`
- `scraper`
- `skillstore`
- `venture`
- `websites`

### R3 — Admin, Builder, And Experimental Surfaces

- `advisor`
- `evolve`
- `observe`
- `patterns`
- `platform-admin`
- `plugin-pack`
- `project-dev`
- `system-cleanup`
- `updater`
- `validator`

### Later

- `consulting-template`
- `smb-client-template`
- `terminal-automation-template`

## Consequences

### Positive

- release planning becomes explicit and reviewable per skill
- the private repo no longer needs catalog hiding to simulate release scope
- `augr-os` releases can be built from a dependency-closed skill subset
- dashboard routes and generated artifacts become aligned with the actual
  release target
- the user gets a real staged roadmap: `mvp`, `r1`, `r2`, `r3`, `later`

### Negative

- every first-party skill must be tagged and kept current
- release tooling becomes stricter because dependency closure is now enforced
- some existing generated artifacts and browse assumptions need migration away
  from category-based logic

### Neutral

- skills can still be user-facing, rough, or operator-heavy in the dev repo;
  the difference is when they ship, not whether they exist
- this ADR does not redesign hub ownership or page layout
- this ADR does not require a new public catalog taxonomy beyond `group`

## Alternatives Considered

### Alternative 1: Keep `x-augur-category` And Add Release Tags On Top

Rejected because the old category model is already overloaded. Keeping it as an
active planning concept would preserve the same confusion between catalog
behavior and release scope.

### Alternative 2: Use Only A Release Tag

Rejected because the product still needs a lightweight classification axis.
Without `group`, release planning would say when a skill ships but not what
kind of surface it is.

### Alternative 3: Keep Release Scope Only In A Manual Release Manifest

Rejected because manual manifests drift too easily from skill-owned metadata.
The release matrix must be derived from the skill frontmatter rather than
maintained in a second central registry.

## References

- `<repo>/docs/superpowers/specs/2026-04-14-skill-group-and-release-enablement-design.md`
- `<repo>/src/plugins/skill_discovery.py`
- `<repo>/src/mcp/augur_mcp/core/skills.py`
- `<repo>/scripts/release.sh`
- `<repo>/apps/dashboard/scripts/mount/discovery.ts`
- `<repo>/apps/dashboard/app/(views)/browse/useBrowseState.ts`

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - "skill discovery metadata contract now includes x-augur-group and x-augur-release"
    - "release pipeline now accepts a target release and prunes disabled skills"
    - "dashboard release build only mounts enabled skills"
  patterns_deprecated:
    - "x-augur-category as a release-planning mechanism"
    - "catalog hiding as the source of release truth"
  files_affected:
    - "skills/*/SKILL.md"
    - "src/lib/skill_release.py"
    - "src/plugins/skill_discovery.py"
    - "src/mcp/augur_mcp/core/skills.py"
    - "scripts/generate-skill-manifest.py"
    - "src/lib/launch_skill_inventory.py"
    - "scripts/release.sh"
    - "apps/dashboard/app/(views)/browse/useBrowseState.ts"
    - "apps/dashboard/scripts/mount/discovery.ts"
```

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

**Team name**: `adr-551-skill-release-enablement`

### Phase 1: Metadata Foundation
**Strategy**: `PIPELINE`

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | release-model | medium | Add shared group/release enums, cumulative release helpers, and dependency-closure validation | `src/lib/skill_release.py`, `tests/unit/test_skill_release.py` |
| 1.2 | discovery | medium | Thread group/release through skill discovery, MCP list-skills output, and generated manifests | `src/plugins/skill_discovery.py`, `src/mcp/augur_mcp/interfaces/skill_registry.py`, `src/mcp/augur_mcp/core/skills.py`, `scripts/generate-skill-manifest.py`, `src/lib/launch_skill_inventory.py`, tests |

### Phase 2: Dev Surface And Skill Tagging
**Strategy**: `PARALLEL`

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | browse | medium | Remove category-based browse hiding and carry group/release through browse enrichment and transforms | `src/mcp/augur_mcp/infrastructure/browse/index.py`, `apps/dashboard/lib/browse/transforms.ts`, `apps/dashboard/app/(views)/browse/useBrowseState.ts`, dashboard tests |
| 2.2 | tagging | medium | Tag every first-party skill with group/release, remove category-based planning tags, and generate the release matrix artifact | `skills/*/SKILL.md`, `scripts/write_skill_group_release.py`, `scripts/generate-skill-release-matrix.py`, `docs/generated/skill-release-matrix.json`, tests |

### Phase 3: Release Build Enforcement
**Strategy**: `PIPELINE`

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | release-pipeline | medium | Prune disabled skills in the release workspace and fail on broken dependency closure | `src/lib/release_workspace.py`, `scripts/prepare_release_workspace.py`, `scripts/release.sh`, tests |
| 3.2 | dashboard-build | medium | Verify dashboard assembly consumes only the reduced skill set and does not emit routes for removed skills | `apps/dashboard/scripts/mount/discovery.ts`, `apps/dashboard/scripts/mount/discovery.test.ts`, `docs/generated/README.md` |

### Completion Criteria
- [ ] Every first-party skill declares valid `x-augur-group` and `x-augur-release`
- [ ] Discovery, MCP, and generated manifests expose the new metadata
- [ ] Browse no longer hides skills based on legacy category
- [ ] Release matrix artifact is generated from tagged skills
- [ ] `scripts/release.sh --release-target <target> --dry-run` prunes the repo and fails on disabled dependencies
- [ ] Dashboard discovery from the regenerated manifest only sees enabled skills for the selected release
