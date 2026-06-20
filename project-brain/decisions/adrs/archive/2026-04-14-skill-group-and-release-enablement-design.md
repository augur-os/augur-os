# Skill Group And Release Enablement

**Date:** 2026-04-14
**Status:** Draft
**Scope:** Replace the current internal/public planning model for first-party
skills with two explicit metadata tags: classification by group and shipping
timing by release.

## Problem

The current skill model mixes several concerns:

- catalog visibility
- internal vs public semantics
- ownership vocabulary
- launch readiness
- release scope

That is not the release workflow Augur actually needs.

The real workflow is:

- all first-party skills live together in the private development repo
- the repo needs a simple way to classify what kind of skill each one is
- each skill needs a clear release target
- release builds for `augr-os` should include only the skills enabled for the
  target release
- pages and generated UI artifacts for disabled skills must not survive into the
  released build

The current `x-augur-category: augur-internal` model is not a good fit for that.
It overloads catalog behavior with release planning, and it blurs the difference
between truly internal system skills and user-facing skills that are simply not
in the next release.

## Goals

1. Replace the current planning model with two explicit skill tags:
   `x-augur-group` and `x-augur-release`.
2. Keep the development repo flat: all first-party skills remain visible there.
3. Make release scope explicit and cumulative across `mvp`, `r1`, `r2`, `r3`.
4. Make release output to `augr-os` structurally enforce the enabled skill set.
5. Fail release builds when an enabled skill depends on a disabled skill.
6. Maintain a durable ADR that records skill enablement by release.

## Non-Goals

- Designing a new public catalog visibility system in this pass
- Deciding whether a skill is "internal" or "external" for planning purposes
- Redesigning hub architecture
- Changing user-facing product taxonomy beyond the new `group` tag
- Solving every skill overlap or consolidation question in the same migration

## Core Model

Each first-party skill under `skills/` must have exactly two planning tags in
`SKILL.md` frontmatter:

- `x-augur-group`
- `x-augur-release`

### 1. Group Tag

`x-augur-group` is a single-choice classification tag chosen from a fixed enum:

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

Rules:

- every skill must have exactly one group value
- the enum is fixed globally
- `other` exists as an escape hatch for rare cases
- the group tag is descriptive, not a release decision by itself

Examples:

- `onboard` -> `augur_core`
- `loop-test` -> `augur_autoloops`
- `daemon` -> `augur_admin`
- `knowledge` -> `brain`
- `apple` -> `productivity`
- `venture` -> `business`

### 2. Release Tag

`x-augur-release` is a single-choice shipping tag chosen from:

- `mvp`
- `r1`
- `r2`
- `r3`
- `later`

Rules:

- every skill must have exactly one release value
- `x-augur-release` is the primary shipping decision tag
- `later` means the skill is intentionally deferred beyond the current staged
  release plan

## Release Semantics

Release enablement is cumulative.

For a target release:

- `mvp` enables only skills tagged `mvp`
- `r1` enables skills tagged `mvp` or `r1`
- `r2` enables skills tagged `mvp`, `r1`, or `r2`
- `r3` enables skills tagged `mvp`, `r1`, `r2`, or `r3`
- `later` is never enabled unless the skill is re-tagged in a future change

This gives Augur a concrete roadmap:

- what to focus on for `mvp`
- what becomes available in `r1`
- what is intentionally deferred to `r2`, `r3`, or `later`

## Release Motives

Each release stage should have a product motive, not just a bucket of skills.

Current working motives:

- `mvp` -> core autonomous brain
- `r1` -> personal operating system
- `r2` -> creation and work expansion
- `r3` -> admin, builder, and experimental surfaces
- `later` -> deferred templates and non-priority shells

These motives are the lens for future retagging. A skill should not move between
releases just to balance counts; it should move only when its purpose fits the
release motive better somewhere else.

## Development Repo Behavior

The development repo remains flat.

Rules:

- all first-party skills remain present in the private repo
- release tagging does not hide skills from the development workspace
- build-time or catalog-time hiding must not be used as a substitute for release
  planning

In other words:

- `x-augur-group` classifies skills
- `x-augur-release` plans shipping
- the private repo keeps the full skill tree

## Release Output Behavior

Release output to `augr-os` is derived from the target release.

For a target release, the pipeline must:

1. copy the repo into a release workspace
2. compute the enabled skill set from cumulative release semantics
3. remove all skills not enabled for that release
4. regenerate derived artifacts from the reduced skill set
5. verify dependency closure
6. fail if enabled skills reference removed skills

This means release scope is enforced structurally rather than implied by
metadata alone.

## Dependency Closure Rules

Dependency closure is strict.

If an enabled skill depends on a disabled skill, the release build must fail.

No silent fallback behavior is allowed:

- no partial page mounting
- no hidden broken routes
- no best-effort stripping of dependent features
- no weak warning-only mode for shipping

The release contract is:

- the enabled skill set must be dependency-closed
- every enabled page and generated artifact must come only from enabled skills

This applies both to explicit skill dependencies and to page-generation
dependencies that assume the presence of another skill.

## Dashboard And Page Gating

Page/build gating must align with release enablement.

If a skill is not enabled for the target release:

- its files are removed from the release workspace
- its dashboard pages are not mounted
- generated wrappers for its pages are not emitted
- tab registries and hub contributions from that skill are not emitted
- routes that depend on that skill do not exist in the released build

This is important because a release should not carry dead routes or zombie page
registries for disabled skills.

The build system should treat enabled skills as the only source of truth when
assembling:

- mounted pages
- generated wrapper pages
- tab registries
- hub assemblies
- release manifests or packs derived from skills

## Release ADR

A durable ADR must capture skill enablement by release.

That ADR should include:

- the allowed release tags
- cumulative enablement semantics
- a matrix of skills by release target
- notable dependency constraints or exceptions
- rationale for important inclusions and exclusions

This ADR is the durable historical record that lets the user return to the
release plan later and understand what was intended for `mvp`, `r1`, `r2`, and
`r3`.

The source of truth for raw tagging remains per-skill frontmatter. The ADR is
the canonical planning record for release enablement as a whole.

## Current Working Release Map

The current tagged release map is:

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

Current per-tag counts:

- `mvp`: 20
- `r1`: 9
- `r2`: 8
- `r3`: 10
- `later`: 3

## Migration Rules

The old planning model should be retired in favor of the new one.

Migration rules:

1. add `x-augur-group` to every first-party skill
2. add `x-augur-release` to every first-party skill
3. stop using `x-augur-category` for release planning
4. stop using internal/public catalog semantics as a proxy for release scope
5. update release/build tooling to derive shipped content from
   `x-augur-release`
6. update generated manifests and planning artifacts to expose `group` and
   `release`

`x-augur-category` may still exist temporarily during migration if some
surviving UI logic still reads it, but it is no longer the canonical planning
model and should be retired from release decisions.

## Validation Requirements

The migration is not complete until the following checks exist and pass:

1. every first-party skill has a valid `x-augur-group`
2. every first-party skill has a valid `x-augur-release`
3. no skill uses an invalid enum value
4. release enablement resolves to the expected cumulative set
5. release builds fail when enabled skills depend on disabled skills
6. disabled skills do not contribute pages or generated UI artifacts to the
   release build

## Recommended Next Step

Write an implementation plan that:

1. introduces the new metadata schema
2. assigns `group` and `release` values across all first-party skills
3. adds the release-enablement ADR
4. updates release/build scripts to prune skills by release target
5. restores or implements page gating from enabled skills only
6. removes old release-planning dependence on `x-augur-category`
