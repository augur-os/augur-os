---
description: Detect dispatch mode mismatches across actions and write a flow optimization report
visibility: auto
---

# auto-flow-optimizer

Analyze action dispatch configurations for mode mismatches.

## Scan

Checks action YAML `dispatch:` fields against description keywords to detect mismatches.

## Fix

Generates `docs/generated/flow-optimizer-report.md` with recommendations. It does not auto-modify dispatch modes.
