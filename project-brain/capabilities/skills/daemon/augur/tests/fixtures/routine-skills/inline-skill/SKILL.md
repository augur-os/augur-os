---
name: inline-skill
description: Fixture skill with a single inline-session routine declaration.
x-augur-loop:
  id: dream
  skill: inline-skill
  loop_name: dream
  automation:
    trigger: nightly
    runner: auto
    discover: commands/dream.md
  memory:
    trust: oneshot
---

# inline-skill
