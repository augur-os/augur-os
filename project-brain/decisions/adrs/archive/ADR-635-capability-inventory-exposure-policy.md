---
status: Implemented
date: '2026-05-10'
deciders:
- Gur Sannikov
related: []
hub: null
tags: []
superseded_by: null
spec_file: 2026-05-06-capability-inventory-exposure-policy-design.md
plan_file: 2026-05-06-capability-inventory-exposure-policy.md
---

# ADR-635: Capability Inventory Exposure Policy

## Decision summary

Use a hybrid source of truth: scanners discover current state, and `config/system/capability_exposure.yaml` stores intentional exposure decisions. Treat missing policy as `classification_status: unclassified`; unclassified capabilities are visible in Browse and blocked from new Augur-generated...
