---
id: regenerate-memory-report
description: Rebuild the human-readable memory report at docs/memory/report.html
skill: knowledge
tags: []
---

Regenerate the human-readable memory report for Augur.

Requirements:
- Read the canonical memory workspace at `get_memory_dir()`, especially `get_memory_dir()/MEMORY.md`.
- Rewrite `docs/memory/report.html` as a polished static HTML report for the current memory state.
- Keep the output self-contained: inline CSS is fine, but do not add external scripts or move the file.
- Preserve local-first paths and stay within the owning knowledge/memory workflow.
- After writing the file, verify it exists and briefly summarize what changed.
