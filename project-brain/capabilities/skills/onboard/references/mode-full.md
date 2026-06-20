# Mode: --full

Complete setup that handles both fresh install and migration. Use this when setting up on a machine that may have partial or outdated Augur artifacts.

## What runs

1. **All default steps (1-6)** — see `references/mode-default.md`
2. **All migration steps** — see `references/mode-migrate.md`
3. **Post-Onboarding Checklist** — see `references/mode-default.md`

Execute default steps first (clone, hooks, deps, IDE config, dashboard, verify), then migration steps (detect legacy data, migrate to vault, verify plugins, verify MCP), then the checklist.
