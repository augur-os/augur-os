# Launch Skill Catalog Audit

**Date:** 2026-04-14
**Status:** Draft
**Scope:** Evaluate first-party skills in `skills/` for launch readiness, catalog visibility, consolidation pressure, and cleanup priority.

## Problem

The current `skills/` tree mixes public user-facing skills, internal system surfaces,
setup flows, templates, and overlapping domain entries. That is workable during
development, but it is not good enough for launch.

For launch, the public catalog must be honest:

- a user should only see skills that can deliver clear value
- a fresh-install user should not be exposed to rough or misleading surfaces
- overlap should not make the product feel noisy or unfinished

The goal is not to make the repository perfectly minimal in one pass. The goal is to
present a catalog that matches what actually works.

## Goals

1. Define a launch-focused audit for first-party skills under `skills/`.
2. Optimize for first-session user value rather than structural elegance.
3. Keep public only the skills that are launch-credible.
4. Hide, merge, or rarely delete skills that do not meet the launch bar.
5. Produce a durable decision record that can drive metadata cleanup first and
   structural cleanup second.

## Non-Goals

- Auditing bundled superpowers or helper skills outside `skills/`
- Forcing every weak skill to be deleted before launch
- Replacing human judgment with composite scoring
- Redesigning hub architecture
- Solving every overlap cluster in a single sweep

## Launch Lens

The dominant evaluation lens is:

`Would a new user get meaningful value from this skill in one session?`

The primary launch users are expected to skew toward:

- personal AI power users
- developer/operator users

That lens takes precedence over strategic ambition. A skill can be strategically
important and still fail the launch bar if it does not work cleanly enough for a
fresh-install user.

## Fresh-Install Standard

The default standard is strict:

- a skill should work out of the box on a fresh install
- if the skill needs connectors or platform access, the path from onboarding or
  connect flow to successful use must feel normal and not require manual debugging

Connector-dependent skills may remain public when they satisfy both conditions:

1. the onboarding or connect path is clean enough to count as normal setup
2. the value after connection is high enough to justify public exposure

Skills that fail this standard are not public launch candidates by default.

## Default Action Bias

When a skill does not meet the launch bar, the default bias is:

- `hide internal` if it still has a useful internal or supporting role
- `merge` if a stronger neighboring skill can absorb the value more clearly
- `delete` only in rare cases where the skill is obvious dead weight, redundant,
  or obsolete with no strong internal reason to keep it

This keeps the launch catalog honest without forcing premature destructive cleanup.

## Audit Universe

This audit covers only first-party skills under `skills/`.

It does not audit:

- bundled superpowers
- generated manifest-only helper entries
- external or client-native skills outside the first-party tree

Those can be handled in separate passes if needed.

## Recommended Audit Method

The primary method is a per-skill launch audit.

Alternative methods were considered:

- metadata-first triage
- cluster-first consolidation

Both are useful as helpers, but neither should drive the launch decision on its own.
Metadata and rank files are too structural, and cluster-first work can force mergers
before individual launch viability has been proven.

Recommended sequence:

1. audit each skill individually against the launch rubric
2. use overlap clusters as a second pass where duplication is hurting clarity

## Launch Gate Rubric

Each skill should be evaluated in this order.

### 1. Promise Clarity

Can a new user understand what the skill is for from its name, description, and entry
surface?

### 2. Fresh-Install Viability

Does the core path work on a fresh install without manual debugging?

If the skill depends on connectors, does it become usable through a normal onboarding
or connect flow only?

### 3. Meaningful First-Session Value

Can the user complete one concrete, useful task in the first session?

### 4. Surface Quality

Is there at least one credible entry surface, such as:

- a command
- a dashboard page
- a visible action
- an obvious invocation pattern

### 5. Overlap Pressure

Is the skill meaningfully distinct, or is a stronger neighboring skill already the
better public entry point?

## Decision Precedence

Decision precedence should be explicit.

- Fail `fresh-install viability` or `meaningful first-session value` -> not public
- Pass usability but fail distinctness -> `merge` candidate
- Valuable but setup-heavy, system-heavy, or supporting -> `hide internal`
- Clear, usable, and distinct -> `keep public`
- No credible role -> `delete`

## Decision Set

Every audited skill receives exactly one primary verdict:

- `keep public`
- `hide internal`
- `merge into <survivor>`
- `delete`
- `improve before public`
- `ask-user`

`ask-user` is reserved for genuinely ambiguous cases where ownership, audience, or
surviving direction cannot be decided confidently from the repo state.

## Evidence Model

This audit should avoid fake precision.

Use lightweight evidence only:

- SKILL.md frontmatter and description quality
- visible entry surfaces
- whether the skill requires platform or connectors
- dashboard or command presence
- rank/eval artifacts as supporting hints only
- one short human judgment note explaining the verdict

Existing `rank.json` files are not strong enough to prove launch readiness because
they mostly measure structural quality, not fresh-install user success.

## Audit Record Format

The deliverable should be a launch audit table with one row per skill.

Each row should include:

- `skill`
- `hub`
- `public/internal today`
- `requires connector/platform`
- `first-session job to be done`
- `launch verdict`
- `recommended action`
- `merge target`
- `reason`
- `confidence`

The point of the table is not reporting for its own sake. It is the decision source
for launch cleanup.

## Audit Order

Run the audit in this sequence:

1. `obvious internal/system skills`
2. `obvious user-facing skills`
3. `overlap clusters`
4. `ambiguous cases`

This prevents overlap debates from consuming the audit before the easy calls are made.

## Overlap Clusters To Inspect

The second pass should explicitly inspect these clusters:

- `knowledge / ingest / rag / scraper`
- `apple / google-workspace / attention / lifestyle`
- `onboard / import / skillstore / plugin-pack / observe / updater`
- `finance / health / eisenhower / books / file-manager`
- `venture / content / project-dev / career-ops`

These clusters are review targets only. They do not pre-commit a merge decision.

## Launch Outputs

The audit should produce five grouped outputs:

- `public launch set`
- `internal-but-keep set`
- `merge queue`
- `delete queue`
- `improve-before-public queue`

This makes the launch conversation operational instead of theoretical.

## Cleanup Model

Launch cleanup should happen in two passes.

### Pass 1: Catalog Honesty

Update metadata, visibility, and public exposure so the user-facing catalog only shows
skills that actually pass the launch gate.

This is the minimum launch requirement.

### Pass 2: Structural Cleanup

For skills marked `merge` or rare-case `delete`:

1. choose the surviving skill
2. migrate any real user value, assets, or wiring that must survive
3. update references
4. then remove the weaker shell if safe

This second pass must be explicit and evidence-driven. It should not become a mass
purge.

## Working Rule

For this launch cycle:

- public catalog quality comes first
- repo minimization comes second
- deletion is exceptional, not the default cleanup tool

That ordering matches the launch objective: focus users on what works and stop
advertising what does not.
