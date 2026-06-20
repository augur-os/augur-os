---
title: Windows Hardening Support Design
date: 2026-04-14
status: proposed
author: Codex
---

# Windows Hardening Support Design

## Goal

Make Augur's hardening process work on Windows in both local loops and GitHub CI without creating false failures, fake parity, or a second platform-specific hardening system.

The desired end state is:

- Windows participates in hardening as a real supported platform
- local hardening and CI consume the same platform-aware check model
- deterministic Windows-safe checks can auto-fix
- unsupported checks skip explicitly with clear reasons
- Windows coverage can expand incrementally without a one-shot rewrite

## Recommendation

Use `capability-gated hardening` with a `safe auto-fix subset` for Windows.

This is preferable to:

- `ad hoc per-check branching`
  - logic drifts between checks
  - local loops and CI diverge quickly
  - Windows support becomes hard to reason about
- `separate Windows hardening profile`
  - creates two hardening systems
  - increases maintenance cost
  - weakens the meaning of "hardening" across platforms
- `full Windows auto-fix immediately`
  - too risky for shell-heavy and process-heavy checks
  - likely to create noisy churn and platform-specific breakage

## Support Contract

Every hardening check must declare:

- `id`
- `platforms`
- `windows_fix_mode`
- optional `skip_reason`

Supported platform declarations:

- `cross_platform`
- `windows`
- `macos`
- `linux`

Supported Windows fix modes:

- `auto_fix`
- `report_only`
- `unsupported`

This contract applies equally to:

- local hardening loops
- manual hardening commands
- GitHub CI verification

## Ownership Model

The capability contract must live with each hardening check, not in a new central registry.

That means:

- `skills/daemon/scripts/ops/*.py` checks expose their own capability metadata
- `skills/loop-ops` orchestration reads that metadata instead of hardcoding platform assumptions
- CI invokes shared platform-aware entrypoints rather than duplicating Windows support logic in workflow YAML

This matches Augur's decentralization rule: behavior metadata stays near the code that owns the behavior.

## Execution Model

Windows support should flow through one shared hardening runner.

Each check exposes:

- capability metadata
- a `scan` path
- optionally a deterministic `fix` path

The runner decides, per check:

- whether the check applies on the current platform
- whether it runs in `report_only` or `auto_fix` mode
- how the result is classified

Mode behavior:

- `local scan`
  - run supported checks without mutation
- `local harden`
  - run supported checks and allow fixes only where the capability contract permits Windows `auto_fix`
- `ci verify`
  - run supported checks in non-mutating mode and fail on actionable violations, not on explicit unsupported-platform skips

Important boundary:

- CI YAML chooses platform and entrypoint
- Python hardening logic owns platform gating, skip reasons, fix eligibility, and result classification

## Result Taxonomy

The runner should classify outcomes consistently across local loops and CI:

- `ran`
- `report_only`
- `skipped_platform`
- `skipped_unsupported`
- `failed`

This keeps Windows output honest:

- unsupported checks are visible
- report-only checks still surface real findings
- true execution failures still fail
- Windows does not pretend to have parity where it does not

## Windows Fix Policy

Windows should start with a `safe auto-fix subset`, not `report_only` everywhere and not `full auto-fix`.

Good initial Windows `auto_fix` candidates:

- stale path hygiene
- MCP/config normalization
- text-based repo hygiene
- other deterministic content rewrites with low filesystem risk

Initial Windows `report_only` candidates:

- shell-heavy checks
- process-management checks
- checks with Unix tool assumptions
- file operations likely to hit Windows locking or quoting edge cases

Initial Windows `unsupported` candidates:

- macOS-only operational checks with no meaningful Windows equivalent

## Migration Plan

Rollout should happen in four passes.

### 1. Inventory and classify

Audit current hardening checks and assign:

- supported platforms
- Windows fix mode
- owning file or workflow

The first output is a capability map, not behavior changes.

### 2. Make the runner capability-aware

Introduce shared platform and fix gating once, then route both local hardening and CI through that runner.

At this stage:

- unsupported Windows checks skip cleanly
- supported checks run without separate CI logic

### 3. Enable the safe Windows subset

Turn on Windows `auto_fix` only for deterministic checks already known to be low-risk.

### 4. Expand incrementally

Promote individual Windows checks from `report_only` to `auto_fix` only after focused verification exists for that check.

## Migration Order

Implementation should proceed in this order:

1. `skills/daemon/scripts/ops/*` checks that already behave mostly cross-platform
2. `skills/loop-ops` orchestration
3. GitHub CI wiring cleanup
4. platform-sensitive checks that still need Windows-specific handling

This sequence lowers risk because platform behavior is settled in the checks and runner before CI and heavier operational checks are changed.

## Evolution Gaps

Windows support must not make the hardening loop falsely "green."

If all currently supported Windows checks pass but Windows coverage is still narrow, the loop must report an evolution gap describing what is not yet covered and what should be added next.

That preserves the existing rule:

- a permanently green loop with known platform blind spots is not acceptable

## Verification Expectations

Verification must cover both execution surfaces:

- local hardening on Windows
- GitHub CI on Windows

Minimum validation for the first rollout:

- supported checks run consistently in both places
- unsupported Windows checks emit explicit skip reasons
- report-only checks surface findings without mutating
- auto-fix checks mutate only when allowed by the contract
- no duplicate platform logic remains in CI for the migrated checks

## Risks

Main risks:

- hidden Unix assumptions inside existing check implementations
- local and CI behavior drifting if workflow YAML re-encodes platform logic
- over-enabling Windows auto-fix before path, quoting, and file-locking behavior is proven
- introducing a central capability registry that falls out of sync with the real checks

## Success Criteria

Version 1 is successful when:

- Windows can run hardening locally without noisy false failures
- Windows CI verifies the same supported checks through the same platform-aware runner
- unsupported checks are explicit and non-pretend
- a small trusted subset can auto-fix safely on Windows
- new Windows hardening support can be added check-by-check without redesigning the whole system
