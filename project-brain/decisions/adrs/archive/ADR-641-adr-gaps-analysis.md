---
status: Cancelled
date: '2026-05-10'
deciders:
- Gur Sannikov
related:
- ADR-606
hub: null
tags: []
superseded_by: null
---

# ADR-641: ADR Gaps Analysis

## Decision summary

Define ADR gap analysis as a scan over Accepted + Proposed ADRs that classifies each ADR by severity (Critical, High, Medium, Low/Trivial) based on the size and risk of unfinished work. Require evidence for every gap claim: the line, file path, or `grep`/`ls` result that proves a stated requirement...

## Status notes

 | Flipped to Accepted 2026-05-10 — concrete pending deliverable confirmed by code-evidence triage. | Cancelled 2026-05-10 — gap analysis was a one-off ad-hoc exercise; no plan to formalize as a /adr command.
