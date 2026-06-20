---
id: migrate-skill
description: AI-guided migration of an existing skill to the current ADR-128 v3.0
  plugin schema
skill: dashboard
tags: []
---

Help migrate an existing Augur skill to the v3.0 plugin schema (ADR-128).
Steps:
1. Ask which skill to migrate (list available skills if unsure)
2. Analyze the current skill structure against v3.0 requirements
3. Identify: missing augur.yaml fields, incorrect directory layout, stale data paths
4. Generate a migration plan with specific changes
5. Execute the migration with user approval at each step
6. Run audit after migration to verify compliance
Be methodical. Preserve all existing functionality.
