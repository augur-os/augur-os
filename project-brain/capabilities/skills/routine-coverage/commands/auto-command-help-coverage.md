---
description: Validate and repair missing help sections for command-hub slash commands
context: current
agent: general-purpose
visibility: ops
---

# /auto-command-help-coverage

Audit command-hub `SKILL.md` files for missing usage, examples, options, and
mode-selection help sections, then repair the safe gaps.

## Implementation

`skills/routine-coverage/scripts/command_help_coverage_ops.py`
