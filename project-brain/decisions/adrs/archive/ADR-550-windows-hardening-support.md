---
status: Implemented
date: 2026-04-14
deciders:
- Gur Sannikov
related: []
hub: adaptive
tags:
- windows
- hardening
- adaptive-loops
- ci
superseded_by: null
---

# ADR-550: Windows Hardening Support

## Context

Augur's hardening process currently mixes cross-platform checks, platform-sensitive checks, and GitHub CI smoke coverage without a single Windows support contract. Some hardening checks are mostly text and path based and can work on Windows today, while others assume Unix tooling, shell behavior, or process semantics. Because the system does not declare platform support per check, Windows support risks becoming either noisy false failures, fake parity, or duplicated logic between local hardening flows and GitHub Actions.

At the same time, Windows is now a first-class product target. Hardening cannot stay implicitly Unix-shaped if Windows is meant to be a supported runtime. The system needs an explicit contract that says which checks run on Windows, which can auto-fix on Windows, which are report-only, and which are unsupported, while keeping that metadata owned by the checks themselves rather than another central registry.

## Decision

Introduce capability-gated hardening for Windows.

Each hardening check will declare:

- supported platforms
- Windows fix mode
- optional skip reason

Capability metadata will live beside the check implementation, not in a central registry. Shared hardening runners will read that metadata and decide whether to run, skip, or allow fix mode on the current platform.

Key design points:

- `src.lib.ops_protocol` becomes the shared home for platform capability types and resolution helpers
- adaptive discovery and execution paths consume the same capability contract
- local hardening and GitHub CI use the same platform-aware runner logic and differ only by execution mode
- Windows starts with a safe auto-fix subset only; shell-heavy and process-heavy checks remain report-only or unsupported until verified
- when Windows coverage is still narrow, loops must report evolution gaps rather than pretending full green coverage

## Consequences

### Positive

- Windows hardening becomes explicit, honest, and incrementally expandable
- local loops and CI stop drifting into separate platform behaviors
- deterministic Windows-safe checks can auto-fix without enabling risky parity all at once
- unsupported checks produce visible skip reasons instead of noisy failures or false success

### Negative

- every migrated hardening check needs small metadata and test updates
- runner and reporting logic become slightly more complex because platform state is now first-class
- some checks will stay report-only on Windows until verification catches up

### Neutral

- this does not make every hardening check Windows-compatible immediately
- macOS and Linux continue using the same hardening system, now with explicit capability declarations
- GitHub workflow YAML remains the orchestration layer, but platform rules move into Python

## Alternatives Considered

### Alternative 1: Ad Hoc Windows Branching Per Check

Patch each hardening module or workflow individually with `if win32` logic. Rejected because support would drift quickly between local execution, loop execution, and CI, and no one would have a reliable contract for what Windows hardening actually means.

### Alternative 2: Separate Windows Hardening Profile

Create a separate Windows-only hardening flow with a curated subset of checks. Rejected because it would split the meaning of "hardening" into two systems and increase long-term maintenance burden.

### Alternative 3: Report-Only Windows Support

Allow Windows scans to run but forbid all fixes. Rejected because it is too weak for a supported platform; deterministic low-risk checks should be allowed to auto-fix from the start.

## References

- `<repo>/docs/superpowers/specs/2026-04-14-windows-hardening-support-design.md`
- `<repo>/config/system/adaptive_loops.yaml`
- `<repo>/src/lib/ops_protocol.py`
- `<repo>/skills/daemon/scripts/adaptive/discovery.py`
- `<repo>/skills/daemon/scripts/adaptive/engine_entry_runner.py`

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - "ops capability contract for scan-fix modules"
    - "hardening execution/reporting semantics for platform skips and Windows fix gating"
  patterns_deprecated:
    - "implicit platform assumptions inside hardening checks"
    - "workflow YAML as the source of platform gating truth"
  files_affected:
    - "src/lib/ops_protocol.py"
    - "skills/daemon/scripts/adaptive/discovery.py"
    - "skills/daemon/scripts/adaptive/engine_entry_runner.py"
    - "skills/daemon/scripts/ops/*.py"
    - "skills/loop-ops/scripts/*.py"
    - ".github/workflows/ci-cross-platform.yml"
```

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

**Team name**: `adr-550-windows-hardening`

### Phase 1: Capability Foundation
**Strategy**: `PIPELINE`

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | protocol | medium | Add shared platform capability types and helpers for scan-fix modules | `src/lib/ops_protocol.py` |
| 1.2 | engine | medium | Thread capability metadata through discovery and execution so Windows runs/skip/fix decisions are centralized | `skills/daemon/scripts/adaptive/discovery.py`, `skills/daemon/scripts/adaptive/engine_entry_runner.py`, `skills/daemon/scripts/adaptive/reporting.py` |

### Phase 2: Initial Windows Check Coverage
**Strategy**: `PARALLEL`

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | daemon-checks | medium | Annotate daemon-owned hardening checks and add Windows capability tests | `skills/daemon/scripts/ops/stale_paths.py`, `page_mounts.py`, `build_health.py`, `security_scan.py`, tests |
| 2.2 | loop-checks | medium | Annotate loop-ops hardening checks and add report-only/auto-fix tests | `skills/loop-ops/scripts/dependency_audit.py`, `fs_bypass.py`, `plugin_lint.py`, tests |

### Phase 3: CI And Operator Surface
**Strategy**: `PIPELINE`

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | ci | medium | Route Windows CI hardening verification through the shared platform-aware runner | `.github/workflows/ci-cross-platform.yml`, test helpers/scripts as needed |
| 3.2 | docs | low | Document Windows hardening semantics, skip behavior, and verification entrypoints | `.github/workflows/README.md`, `skills/daemon/commands/dev-loops.md` |

### Completion Criteria
- [ ] Windows hardening support uses explicit per-check capability metadata
- [ ] Local hardening and CI share the same platform gating logic
- [ ] Initial Windows-safe checks support deterministic auto-fix
- [ ] Unsupported/report-only checks are explicit in output
- [ ] Verification covers Windows runner semantics and updated checks
