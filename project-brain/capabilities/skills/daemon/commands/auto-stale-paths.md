---
description: Detect ADR-270 folder/path drift across active code and workflow surfaces
visibility: auto
---

# auto-stale-paths

ADR-270 enforcement scan for active code, workflows, and operational docs. Daemon-managed in the `hardening` loop.

## Scan

Autonomously scans active repository surfaces for:

1. Literal repo-local runtime path references
2. Legacy augur data holdouts
3. Legacy augur MCP fallbacks
4. Placeholder ADR-270 structure markers like generated migration README stubs

The scanner skips archival docs and generated/runtime folders to keep findings actionable.

## Fix

Autonomous findings are **report-only**. The command writes a structured ADR-270 drift report to external state reports under `~/Library/Application Support/Augur/state/adaptive/reports/` for review and follow-up.

If stale path issues are fed in externally with an explicit non-report fix strategy, the existing headless Claude fixer remains available for targeted remediation.
