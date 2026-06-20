---
description: Detect stale docs and broken internal links across docs/ and SKILL.md files
visibility: ops
---

# auto-doc-freshness

Scan documentation for broken internal links and stale content that hasn't been
updated in 90+ days. Daemon-managed (knowledge-enrichment loop, tier 2).

## Scan

Walks `docs/**/*.md` and `plugins/*/skills/*/SKILL.md` files:
- **d0**: Checks internal markdown links (relative paths) against filesystem
- **d1+**: Extends scan to SKILL.md files across all plugins
- **d2+**: Also flags docs not updated in 90+ days

## Fix

Removes broken links (keeps link text, drops dead reference). Stale docs are
reported for manual review but not auto-modified.
