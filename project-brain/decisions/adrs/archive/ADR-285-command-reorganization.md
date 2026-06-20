---
status: Implemented
date: '2026-03-08'
deciders:
- Gur Sannikov
related: []
hub: null
tags:
- command
- reorganization
- unify
- dev
- ops
superseded_by: null
---

# ADR-285: Command Reorganization — Unify Dev + Ops, Hide App

## Context

The slash command taxonomy has three user-facing groups (App 3, Dev 4, Ops 7) plus Auto (52). This creates unnecessary cognitive overhead:

- **App commands** (coach, danit, post) are rarely invoked as slash commands — MCP tools are sufficient.
- **Ops and Dev** overlap conceptually — both are developer workflow commands. The distinction adds naming friction (is it `/ops-loops` or `/dev-loops`?).
- **ops-dispatch** is an incomplete stub with missing config — never implemented.
- **ops-inspect** runs autonomously and fits the auto-loop model better than manual invocation.
- **Two commands are missing**: the ADR command (consolidated in ADR-174 but never given visibility frontmatter) and a standalone sync command for `sync_agents.py`.

## Decision

1. **Hide App commands** — Set `x-augur-visibility: hidden` for coach, danit, post. MCP tools remain available.
2. **Hide ops-install** — MCP tool `install-skill` is sufficient.
3. **Delete ops-dispatch** — Remove the incomplete stub entirely.
4. **Unify Dev + Ops into `dev-*`** — Rename 4 ops commands to `dev-*` prefix. The `ops` visibility group ceases to exist.
5. **Promote ops-inspect to auto-inspect** — Move to auto-loop with tier-2 interval trigger.
6. **Add dev-adr** — Add `x-augur-visibility: dev` to existing ADR SKILL.md (at `plugins/dev/skills/devops/commands/adr/`).
7. **Create dev-sync** — New skill wrapping `sync_agents.py --all`.

### Resulting taxonomy

- **Core (5)**: ask, commands, onboard, save, search
- **Dev (10)**: dev-adr, dev-build, dev-debug, dev-import, dev-learn, dev-loops, dev-merge, dev-rollback, dev-sync, dev-test
- **Auto (53)**: All existing 52 + auto-inspect

## Consequences

### Positive

- Single `dev-*` namespace — no ambiguity about where a command lives
- Fewer groups to scan (3 instead of 5)
- Dead code removed (ops-dispatch)
- ops-inspect runs autonomously for periodic health checks
- Two missing commands surfaced (dev-adr, dev-sync)

### Negative

- Breaking change for muscle memory on `/learn`, `/ops-loops`, `/ops-rollback`, `/ops-import`
- No backward-compatibility aliases (per CLAUDE.md rule 12)

### Neutral

- Auto commands unaffected (except +1 auto-inspect)
- Core commands unaffected
- MCP tools for hidden commands remain functional

## Alternatives Considered

### Alternative 1: `aug-*` prefix

Rename all dev + ops commands to `aug-build`, `aug-merge`, etc. Rejected because `dev-*` already exists for 4 commands — renaming everything would be more churn for no benefit.

### Alternative 2: Keep App commands visible

Keep coach/danit/post as slash commands. Rejected because they're rarely invoked via slash command and MCP provides the same functionality.

## References

- ADR-174: Skill & Command Consolidation (consolidated 5 ADR commands into `/adr`)
- ADR-252: Command discovery via `x-augur-visibility` frontmatter
- Design doc: `docs/plans/2026-03-08-command-reorganization-design.md`
- Implementation plan: `docs/plans/2026-03-08-command-reorganization-plan.md`

## Impact Manifest

```yaml
impact:
  paths_renamed:
    - from: "plugins/ai/skills/learn/"
      to: "plugins/ai/skills/dev-learn/"
      scope: "plugins/ai/skills/learn/**"
    - from: "plugins/admin/skills/ops-import/"
      to: "plugins/admin/skills/dev-import/"
      scope: "plugins/admin/skills/ops-import/**"
    - from: "plugins/observability/skills/ops-loops/"
      to: "plugins/observability/skills/dev-loops/"
      scope: "plugins/observability/skills/ops-loops/**"
    - from: "plugins/dev/skills/ops-rollback/"
      to: "plugins/dev/skills/dev-rollback/"
      scope: "plugins/dev/skills/ops-rollback/**"
    - from: "plugins/observability/skills/ops-inspect/"
      to: "plugins/observability/skills/auto-inspect/"
      scope: "plugins/observability/skills/ops-inspect/**"
  patterns_deprecated:
    - grep: "x-augur-visibility: app"
      replacement: "x-augur-visibility: hidden (for app commands)"
    - grep: "x-augur-visibility: ops"
      replacement: "x-augur-visibility: dev (unified group)"
    - grep: "ops-dispatch"
      replacement: "deleted — no replacement"
  files_affected:
    - glob: "plugins/dev/skills/ops-dispatch/**"
```
