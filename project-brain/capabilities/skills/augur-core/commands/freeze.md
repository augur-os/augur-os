---
description: Restrict write operations to a specific directory for the current session.
visibility: core
---

# /freeze

Restrict write and edit operations to a specific directory for the current session.

## Usage

```bash
/freeze skills/career
/freeze apps/dashboard
/freeze off
```

## Behavior

When a write or edit targets a path outside the frozen directory:

1. stop
2. report that the action is blocked by `/freeze`
3. require explicit user confirmation before proceeding

## Always Allowed

- reads
- searches
- bash execution
- git operations

## Deactivation

Use `/freeze off`, or end the session.
