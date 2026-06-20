---
id: import-skill
description: Discover and import an external plugin package into an Augur bundle
skill: dashboard
tags: []
---

Help the user import an external plugin package.
Steps:
1. Run `scan-importable-plugins` to discover candidate sources.
2. Ask which source path to import and target bundle.
3. Run `import-skill` with dry_run=true first.
4. If clean, run import with dry_run=false and summarize copied/generated files.
5. Suggest follow-up audit (`audit-plugin`) for the imported skill.
