---
description: Scan command execution logs and evolve SKILL.md files with learned improvements
visibility: auto
---

# /auto-command-evolution

Analyzes command execution logs in external state under
`~/Library/Application Support/Augur/state/command-evolution/` and applies
safe ADR-102 improvements to command `SKILL.md` files.

## What it does

- **Scan**: Reads most recent execution logs per command and finds:
  - failed phases (adds timeout hints)
  - captured learnings (adds hints)
- **Fix**: Uses ADR-102 helpers to update the command skill definition, then
  commits scoped changes per file.

## Usage

Runs automatically in the `command-evolution` loop at `tier: 0`
(`trigger: post-execution`). Can also be invoked manually via `/routines`.

## Protocol

Implements the `OpsCommand` scan-fix protocol.
Supports dry-run via `OpsContext(dry_run=True)`.

## Implementation

`skills/ai/scripts/ops/command_evolution.py`
