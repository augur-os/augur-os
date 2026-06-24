---
name: tiered-skill
description: Fixture skill with multiple tiered routine declarations.
x-augur-loops:
- id: testing
  skill: tiered-skill
  loop_name: testing
  automation:
    trigger: nightly
    runner: auto
    discover: scripts/testing.py
  memory:
    trust: adaptive
- id: code-quality
  skill: tiered-skill
  loop_name: code-quality
  automation:
    trigger: nightly
    runner: auto
    discover: scripts/code_quality.py
  memory:
    trust: adaptive
---

# tiered-skill
