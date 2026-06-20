---
description: Detect duplicate internal auto-command implementations and collapse safe mirrors into wrappers
context: current
agent: general-purpose
visibility: ops
---

# /auto-duplication

Scan internal scan-fix implementations for duplicate logic and rewrite safe
adaptive mirrors into thin wrappers around the canonical owner.

## Implementation

`project-brain/capabilities/skills/platform-admin/scripts/ops/duplication_ops.py`
