---
name: auto-self-heal
description: Scan external Augur logs for errors and delegate fixes to ai_self_healer.
visibility: ops
---

# auto-self-heal

Scan external Augur logs for errors and auto-fix them via `ai_self_healer`. Daemon-managed (self-heal loop, tier 0, continuous trigger).

## Usage

```
/auto-self-heal
/auto-self-heal --dry-run    # Scan only, no fixes applied
```

## What This Does

1. Calls `scan()` — delegates to `ai_self_healer.scan_runtime()`, filters out already-resolved registry entries (abandoned, dismissed, fixed, etc.)
2. Maps each finding's severity to an engine category:
   - `critical` → `import-fixes`
   - `high` → `config-fixes`
   - `medium` / `low` → `logic-fixes`
3. Calls `fix()` — delegates to `ai_self_healer.fix_entry()` per issue, running the classify→route→fix pipeline
4. Commits any changed files with `fix(adaptive): self-heal <key>` messages

## Scope

**Handles**: Errors from external Augur logs under `~/Library/Logs/Augur/`, Python import failures, config issues, and logic errors detected in daemon and service logs.

**Does not handle**: TypeScript errors (use `auto-lint`), marker tech debt (use `auto-tidy`), build failures (use `auto-build-health`).

## Adaptive Engine Integration

Registered in `SKILL.md` frontmatter with `protocol: scan-fix` under the `self-heal` loop at tier 0. The engine trust-gates `fix()` — scan results are always collected, but fixes only run when trust score is sufficient.

## Related

- `project-brain/capabilities/skills/daemon/scripts/ai_self_healer.py` — the underlying healer module
- `project-brain/capabilities/skills/daemon/scripts/ops/self_heal.py` — this command's implementation
- `/a-loops` — monitor loop status and trust scores
- `/daemon` — manage the daemon that schedules this command

$ARGUMENTS
