---
name: colliding-skill
description: Fixture skill with a colliding routine declaration.
x-augur-loop:
  id: testing
  skill: colliding-skill
  loop_name: testing
  automation:
    trigger: nightly
    runner: auto
    discover: scripts/other_testing.py
  memory:
    trust: adaptive
---

# colliding-skill
