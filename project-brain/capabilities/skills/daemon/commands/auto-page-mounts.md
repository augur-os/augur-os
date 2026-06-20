---
description: Verify contributions.pages source files exist for all plugins
visibility: ops
---

# auto-page-mounts

Walk every `SKILL.md` `x-augur-config.contributions.pages` entry and verify that the
referenced source file exists on disk. Daemon-managed (hardening loop, tier 0).

## Scan

For each page in `contributions.pages`, checks that `{skill_dir}/{page.file}`
exists. Emits one issue per missing source file.

## Fix

Writes findings to `docs/generated/hardening/hardening-{date}.md` and commits.
