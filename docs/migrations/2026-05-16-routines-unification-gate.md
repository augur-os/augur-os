# ADR-758 Gate Verification Log

Date: 2026-05-16

Worktree: `<active ADR-758 worktree>`

Branch: `adr-758-routines-unification-20260516`

Base commit: `1089769fa fix(dev-loops): tighten coverage gap reporting`

## Gate Results

| Gate | Requirement | Result | Evidence |
|---|---|---|---|
| 1 | ADR-755 status is `Implemented` | PASS | `docs/adrs/adrs-index.json` reports `ADR-755 Implemented` |
| 2 | ADR-756 status is `Implemented` | PASS | `docs/adrs/adrs-index.json` reports `ADR-756 Implemented` |
| 3 | ADR-757 status is `Implemented` | PASS | `docs/adrs/adrs-index.json` reports `ADR-757 Implemented` |
| 4a | Dream ledger has at least 10 historical runs | PASS | `aug dream status --history-limit 20` returned 10 complete `dream-cycle` jobs |
| 4b | Recent Dream prompt/MCP architectural churn is not above threshold | PASS | `git log --since='1 month ago' --oneline -- shared-vault/skills/dream/commands/ shared-vault/skills/dream/scripts/mcp/ \| wc -l` returned `3` |

## Dream Ledger Evidence

Command:

```bash
PYTHONPATH="$PWD/shared-vault:$PWD:$PWD/src/mcp" uv run python -m src.cli dream status --history-limit 20
```

Latest run:

```text
20260516-164355-384-009-dream-cycle
state: complete
created_at: 2026-05-16T16:43:55.384776+00:00
```

History count: 10 complete dream-cycle jobs.

Job ids:

- `20260516-164354-664-000-dream-cycle`
- `20260516-164354-765-001-dream-cycle`
- `20260516-164354-842-002-dream-cycle`
- `20260516-164354-917-003-dream-cycle`
- `20260516-164354-993-004-dream-cycle`
- `20260516-164355-069-005-dream-cycle`
- `20260516-164355-158-006-dream-cycle`
- `20260516-164355-234-007-dream-cycle`
- `20260516-164355-308-008-dream-cycle`
- `20260516-164355-384-009-dream-cycle`

The 10 runs were generated in this implementation session with:

```bash
PYTHONPATH="$PWD/shared-vault:$PWD:$PWD/src/mcp" uv run python -m src.cli dream run --iterations 10 --cache-gc-dry-run
```

Real data observed during those runs:

- Dream report path: `<documents>/reports/dream/2026-05-16.md`
- Orphan candidates: `active-projects`, `index`, `knowledge-gaps`, `overview`, `profile-human-api`, `recent-decisions`
- Dead citations: none
- Cache GC dry run: `kept=4`, `purged=[]`, `bytes_freed=0`
- Tier recompute: `entities=1044`
- Stale pages: none
- Merge candidates: none

## Dream Surface Churn Check

Command:

```bash
git log --since='1 month ago' --oneline -- shared-vault/skills/dream/commands/ shared-vault/skills/dream/scripts/mcp/
```

Output:

```text
82a9f570f feat(dream): /dream routine prompt - phase orchestration (ADR-744 task 12)
b9c854226 feat(dream): MCP + aug-dream CLI wiring (ADR-744 task 10)
2aa477a76 feat(dream): scaffold dream skill - SKILL.md, config, fixtures (ADR-744 task 1)
```

## Gate Note

The Dream evidence is an accelerated in-session runtime gate, not a multi-day release-cycle soak. The user requested the missing steps now and to start ADR-758, so this log records the exact evidence used rather than presenting it as older sustained production history.
