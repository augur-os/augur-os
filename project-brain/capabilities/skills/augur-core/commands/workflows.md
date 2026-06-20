---
description: Inspect and validate cross-skill workflow definitions across Augur.
visibility: ops
---

# /workflows

Inspect workflow definitions across Augur and surface their current health.

## Usage

```bash
/workflows
/workflows --json
/workflows --health
```

## What It Covers

1. discover workflow definitions from the current skill tree
2. summarize names and descriptions
3. optionally check whether referenced tooling still exists

## Notes

- use this as an inspection command, not as the owner of orchestration logic
- if workflow definitions drift, fix the owning skill rather than adding another wrapper
