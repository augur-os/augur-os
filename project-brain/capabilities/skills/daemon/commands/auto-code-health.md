---
description: Scan and fix build errors and API health issues
visibility: auto
---

# auto-code-health

Unified code health monitoring — TypeScript build errors and API route health. Daemon-managed (hardening loop).

## Build Health (Tier 0)

Scan the dashboard TypeScript codebase for build errors and use headless Claude to fix them.

### Scan

Runs `npx tsc --noEmit --pretty false` in `apps/dashboard/`. Groups errors by file and emits one issue per file.

### Fix

For each affected file, invokes the Claude CLI with a focused prompt to make minimal, correct fixes. Verifies with `tsc --noEmit` after each fix and commits on success.

**Constraint**: Never uses `@ts-ignore` or any suppression comments.

---

## API Health (Tier 2)

Process externally-fed API route health findings.

### Scan

No autonomous scanner. Findings are fed externally by dashboard health monitors or manual ops triggers.

### Fix

Writes each finding to `docs/generated/hardening/hardening-{date}.md`. When a source file is identified, prepends a `TODO_BUG` marker to it. Commits all changes.
