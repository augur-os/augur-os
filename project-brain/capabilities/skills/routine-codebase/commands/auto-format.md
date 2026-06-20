---
description: Run Prettier against the source tree and commit safe formatting repairs
visibility: auto
---

# auto-format

Run Prettier formatting on source files.

## Scan

Runs `prettier --check` against the tracked source tree and reports drift.

## Fix

Runs `prettier --write` and commits the scoped formatting repair when files change.
