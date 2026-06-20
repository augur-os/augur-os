---
description: Scan dependency vulnerabilities and apply conservative audit fixes
visibility: auto
---

# auto-dependency-audit

Run dependency vulnerability scans against the dashboard package surface.

## Scan

Executes `npm audit --json` in `apps/dashboard` and summarizes vulnerable packages.

## Fix

At higher difficulty, applies `npm audit fix` without forcing major upgrades.
