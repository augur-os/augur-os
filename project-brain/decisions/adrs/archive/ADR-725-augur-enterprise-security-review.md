---
status: Implemented
date: 2026-05-11
deciders:
  - gsannikov
related: []
hub: null
tags:
  - security
  - enterprise
  - compliance
  - mcp
  - daemon
  - supply-chain
superseded_by: null
spec_file: 2026-05-11-augur-enterprise-security-review-design.md
plan_file: 2026-05-11-augur-enterprise-security-review-phase-0-1.md
---

# ADR-725: Augur Enterprise Security Review

> **ADR-725 is an index file.** The substantive design and implementation steps live in the linked spec + plan. This file carries pointers, status, and a one-line decision summary.

## Decision summary

Conduct a tiered, evidence-driven security review of the Augur runtime to produce reusable enterprise-readiness documentation (under `docs/security/`) so any enterprise customer — starting with an upcoming pilot — can validate Augur for managed-laptop deployment alongside existing AI dev tools.

## Spec (canonical)

- [`docs/superpowers/specs/2026-05-11-augur-enterprise-security-review-design.md`](../superpowers/specs/2026-05-11-augur-enterprise-security-review-design.md)

## Plan (canonical, drives `/adr implement`)

- [`docs/superpowers/plans/2026-05-11-augur-enterprise-security-review-phase-0-1.md`](../superpowers/plans/2026-05-11-augur-enterprise-security-review-phase-0-1.md)

This plan covers Phase 0 (Foundation) + Phase 1 (Tier-1 surfaces: network egress, MCP trust boundary, code execution surface, daemon and persistence, install and supply chain) and arrives at the emergency-pitch-floor checkpoint. Phase 2-5 are deferred to a follow-up plan informed by Phase 1 evidence; a follow-up ADR will index that plan when written.

## Status notes

**Accepted on 2026-05-11.** Spec and plan completed in the same session via `/superpowers:brainstorming` and `/superpowers:writing-plans`. Status flips to `Implemented` after `/adr implement ADR-725` lands the Phase 0+1 work and the emergency-pitch-floor checkpoint verifies clean (per `Task 1.6.3` in the plan).

The review explicitly defers three engineering follow-ups to separate plans (referenced from `threat-model.md` as proposed work, not implemented):

- An `--enterprise` policy mode (skill allowlist, disabled auto-script-execution, report-only autoloops, SIEM-forwardable audit log).
- An admin-configurable egress allowlist and `--airgap` fail-closed mode.
- A `classification.yaml` vault policy file for excluding classified roots from ingestion.

These follow-ups will get their own ADRs when their plans are written. The proposed `--enterprise` policy ADR is drafted as part of Plan Task 1.3.3 (next available ADR number at execution time).

## Related

- None at index time.

## Impact Manifest

No path renames, API changes, or pattern deprecations. The review adds new documentation under `docs/security/` and a private working doc under `docs/superpowers/security-review/`; no existing files are restructured.

```yaml
impact:
  paths_renamed: []
  apis_changed: []
  patterns_deprecated: []
  files_affected:
    - docs/security/README.md
    - docs/security/threat-model.md
    - docs/security/enterprise-readiness-packet.md
    - docs/security/architecture-trust-boundaries.md
    - docs/security/network-egress-proof.md
    - docs/security/enterprise-deployment-guide.md
    - docs/superpowers/security-review/2026-05-augur-runtime-gap-analysis.md
```
