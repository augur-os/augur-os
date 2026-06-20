---
name: tiered-skill
description: Fixture skill with multiple tiered routine declarations.
x-augur-routines:
  - id: testing
    execution: tiered
    policy: adaptive
    callable: scripts/testing.py
    loop: testing
    hub: command
    description: Run test/build checks.
  - id: code-quality
    execution: tiered
    policy: adaptive
    callable: scripts/code_quality.py
    loop: code-quality
    hub: dev
---

# tiered-skill
