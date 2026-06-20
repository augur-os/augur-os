# Documentation Convergence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `augur` the canonical external-facing documentation source by aligning top-level docs and deeper markdown docs to the current soft-launch state, platform status, and roadmap.

**Architecture:** This is a docs-only convergence pass. The implementation should first establish a coherent top-level narrative, then add a canonical roadmap, then align deeper guides/references that make product or platform claims, and finally verify the whole markdown surface for contradiction drift.

**Tech Stack:** Markdown, ripgrep, Git

---

### Task 1: Converge The Top-Level Documentation Surface

**Files:**
- Modify: `README.md`
- Modify: `CONTRIBUTING.md`
- Modify: `SECURITY.md`
- Modify: `CHANGELOG.md`
- Reference: `docs/superpowers/specs/2026-04-14-documentation-convergence-design.md`

- [ ] **Step 1: Rewrite `README.md` as the canonical external narrative**

Update `README.md` so it clearly states:

```md
- Augur is in soft launch
- native macOS support is implemented
- native Windows architecture is implemented
- Windows validation is still pending before a firmer public support claim
- roadmap and release direction exist at top level
```

Remove visible placeholders like:

```md
<!-- TODO: Add dashboard screenshot -->
```

- [ ] **Step 2: Add a current-state section to `README.md`**

Ensure `README.md` contains a short section shaped like:

```md
## Current Status

- Augur is in soft launch.
- Native macOS support is implemented.
- Native Windows architecture is implemented.
- Windows validation is still pending before broader support claims.
```

- [ ] **Step 3: Reframe install/setup guidance to match current reality**

Review install-related sections in `README.md` and keep only guidance that is accurate for the current state.
Any setup text must not overclaim public readiness beyond the stated soft-launch posture.

Use a pass like:

```bash
rg -n "Quick Start|Windows|install|dashboard|MCP|create-augur|localhost:3000" README.md
```

Expected:

```text
Matches remain only where the guidance is intentional, current, and consistent with soft launch
```

- [ ] **Step 4: Align `CONTRIBUTING.md`, `SECURITY.md`, and `CHANGELOG.md` to the same story**

Update each file so the opening reflects the same state:

```md
- soft launch
- current state is real but not overclaimed
- platform story matches README
- no contradictory release/support language
```

In particular:

```md
CONTRIBUTING.md -> no assumption that docs are purely internal
SECURITY.md -> no stale support-matrix wording
CHANGELOG.md -> no framing that implies a broader public release than reality
```

- [ ] **Step 5: Verify top-level wording consistency**

Run:

```bash
rg -n "soft launch|macOS|Windows|validation pending|implemented" README.md CONTRIBUTING.md SECURITY.md CHANGELOG.md
```

Expected:

```text
The same platform and launch-state language appears consistently across the top-level docs
```

- [ ] **Step 6: Commit the top-level convergence**

```bash
git add README.md CONTRIBUTING.md SECURITY.md CHANGELOG.md
git commit -m "docs: converge top-level documentation"
```

### Task 2: Add The Canonical Roadmap To Augur

**Files:**
- Create: `ROADMAP.md`
- Modify: `README.md`

- [ ] **Step 1: Create `ROADMAP.md` with the canonical release state**

Create `ROADMAP.md` with content shaped like:

```md
# Roadmap

## Current Phase

Augur is currently in soft launch.

## Release Direction

- **May 2026 — Target MVP release**
- **June 2026 — Target start of monthly releases**
- **July 2026 — Monthly release target**
- **August 2026 — Monthly release target**

## Platform Status

- Native macOS support is implemented.
- Native Windows architecture is implemented.
- Windows validation is pending before broader support claims.

## Notes

This roadmap is high-level, provisional, and non-contractual during soft launch.
```

- [ ] **Step 2: Link the roadmap from `README.md`**

Add or keep a link like:

```md
See ROADMAP.md for the release timeline.
```

- [ ] **Step 3: Verify roadmap wording matches the top-level docs**

Run:

```bash
rg -n "soft launch|Target MVP release|Target start of monthly releases|Windows|macOS|validation pending|provisional" README.md ROADMAP.md
```

Expected:

```text
README.md and ROADMAP.md share the same current-state and platform story
```

- [ ] **Step 4: Commit the roadmap**

```bash
git add ROADMAP.md README.md
git commit -m "docs: add canonical roadmap"
```

### Task 3: Align Deeper Guides And References That Make External Claims

**Files:**
- Modify: `docs/getting-started.md`
- Modify: `docs/developer-guide.md`
- Modify: `docs/guides/installation-windows.md`
- Modify: `docs/architecture-overview.md`
- Modify: additional `docs/**/*.md` files that make external claims discovered during the sweep

- [ ] **Step 1: Identify the deeper docs that make external-facing claims**

Run:

```bash
rg -n "soft launch|Windows|macOS|install|setup|dashboard|MCP|release|support" docs --glob '*.md'
```

Expected:

```text
A candidate list of deeper docs whose wording should be aligned with current reality
```

- [ ] **Step 2: Update the highest-impact guides first**

Review and align at least these docs if they make external claims:

```text
docs/getting-started.md
docs/developer-guide.md
docs/guides/installation-windows.md
docs/architecture-overview.md
```

Each touched doc should:

```md
- reflect the same platform story
- avoid contradicting soft launch
- avoid stale placeholders or overclaiming setup/support status
```

- [ ] **Step 3: Update additional markdown docs only where they materially contradict the canonical story**

For each additional file, prefer minimal wording edits over broad rewrites.
Focus on:

```md
- platform support contradictions
- stale launch phrasing
- setup claims that exceed reality
- placeholders visible to external readers
```

- [ ] **Step 4: Verify deeper docs no longer contradict the canonical story**

Run:

```bash
rg -n "Windows|macOS|validation pending|soft launch|public release|support" docs --glob '*.md'
```

Expected:

```text
Touched deeper docs now use wording that is compatible with README.md and ROADMAP.md
```

- [ ] **Step 5: Commit the deeper-doc convergence**

```bash
git add docs
git commit -m "docs: align guides with current launch state"
```

### Task 4: Run A Full Markdown Contradiction Sweep

**Files:**
- Verify: `README.md`
- Verify: `ROADMAP.md`
- Verify: `CONTRIBUTING.md`
- Verify: `SECURITY.md`
- Verify: `CHANGELOG.md`
- Verify: `docs/**/*.md`

- [ ] **Step 1: Search for stale placeholders and soft-launch contradictions**

Run:

```bash
rg -n "TODO:|TBD|coming soon|full public release is live|publicly supported today" README.md ROADMAP.md CONTRIBUTING.md SECURITY.md CHANGELOG.md docs --glob '*.md'
```

Expected:

```text
No unresolved placeholder text or obvious contradiction language in the touched documentation surface
```

- [ ] **Step 2: Search for platform wording contradictions**

Run:

```bash
rg -n "Windows|macOS|validation pending|implemented" README.md ROADMAP.md CONTRIBUTING.md SECURITY.md CHANGELOG.md docs --glob '*.md'
```

Expected:

```text
Platform wording is consistent wherever these concepts appear
```

- [ ] **Step 3: Search for install/readiness overclaim**

Run:

```bash
rg -n "install|setup|dashboard|MCP|localhost:3000|create-augur|configure_mcp|install.ps1" README.md ROADMAP.md CONTRIBUTING.md SECURITY.md CHANGELOG.md docs --glob '*.md'
```

Expected:

```text
Any remaining matches are intentional and do not contradict the current soft-launch state
```

- [ ] **Step 4: Manually review the top-level docs together**

Read these files together in order:

```text
README.md
ROADMAP.md
CONTRIBUTING.md
SECURITY.md
CHANGELOG.md
```

Confirm they answer these external-facing questions coherently:

```text
What is Augur now?
What phase is the project in?
What is the platform status?
What is the roadmap?
What should an interested user do next?
```

- [ ] **Step 5: Check git status for docs-only scope**

Run:

```bash
git status --short
```

Expected:

```text
Only markdown/documentation files are modified, plus any pre-existing untracked plan files already present in the worktree
```

- [ ] **Step 6: Commit the contradiction sweep**

```bash
git add README.md ROADMAP.md CONTRIBUTING.md SECURITY.md CHANGELOG.md docs
git commit -m "docs: finalize documentation convergence"
```

## Self-Review

### Spec Coverage

This plan covers the spec directly:

- top-level convergence: Task 1
- roadmap creation: Task 2
- deeper docs convergence: Task 3
- markdown contradiction sweep: Task 4

### Placeholder Scan

The plan contains no unresolved `TBD`, `TODO`, or “implement later” instructions.
Every verification command and file path is explicit.

### Type And Naming Consistency

The plan consistently references:

- `README.md`
- `ROADMAP.md`
- `CONTRIBUTING.md`
- `SECURITY.md`
- `CHANGELOG.md`
- `docs/**/*.md`
- `docs/superpowers/specs/2026-04-14-documentation-convergence-design.md`

The roadmap wording is kept consistent across all tasks: soft launch, target MVP release, monthly release direction, and Windows validation pending.
