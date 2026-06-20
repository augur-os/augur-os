# ADR-758 Routines Unification Manifest

Date: 2026-05-16

Scope: start ADR-758 by auditing the live routine surface before adding `x-augur-routine` declarations, schedule moves, registry code, or slash-command aliases.

Inputs:

- `docs/adrs/ADR-758-routines-unification.md`
- `docs/superpowers/plans/2026-05-16-routines-unification.md`
- `docs/superpowers/specs/2026-05-16-routines-unification-design.md`
- `docs/migrations/2026-05-16-loop-skill-consolidation-manifest.md`
- Live `SKILL.md` frontmatter under `shared-vault/skills/`
- Current schedule seeds after migration:
  - skill-local `assets/seeds/routine-schedule.yaml` files under each routine owner

## Task 0 Gate

ADR-755, ADR-756, and ADR-757 are `Implemented`. Dream now has 10 ledger-visible complete `dream-cycle` runs and 3 recent prompt/MCP commits, which is within the ADR-758 plan threshold. Full gate evidence is recorded in `docs/migrations/2026-05-16-routines-unification-gate.md`.

## Routine Namespace Finding

ADR-758 specifies a flat routine namespace. The live repo already has loop categories whose commands are contributed by multiple skill roots. Therefore Task 3 must not add the same flat routine id to every contributing skill. A flat id such as `hardening` or `code-quality` needs exactly one declaration owner, while the orchestrator continues to discover individual command contributors through existing `x-augur-commands`.

TODO_BUG(ADR-758): The plan shorthand "dream + 5 routine-* skills" does not cover every active routine contributor. Current scheduled or loop-declared contributors also include `ai`, `daemon`, `platform-admin`, `auto-skill-quality`, `evals`, `ingest`, and private-vault `file-manager`. ADR-758 implementation must either assign declaration owners for those routine ids or explicitly migrate their loop commands into the routine-* skills before registry enforcement.

## Proposed Flat Routine Ids

| Routine id | Execution | Policy | Declaration owner | Legacy loop | Scheduled today | Notes |
|---|---|---|---|---|---|---|
| `dream` | inline-session | oneshot | `dream` | `dream` | yes | Existing prompt at `commands/dream.md`; schedule seed is `assets/seeds/routine-schedule.yaml` |
| `testing` | tiered | adaptive | `routine-codebase` | `testing` | yes | Contributors: `routine-codebase`, `routine-platform` |
| `code-quality` | tiered | adaptive | `routine-codebase` | `code-quality` | yes | Contributors span six skills; declaration owner must aggregate by loop name |
| `hardening` | tiered | adaptive | `routine-platform` | `hardening` | yes | Contributors span six skills; avoid duplicate routine declarations |
| `knowledge-enrichment` | tiered | adaptive | `routine-vault` | `knowledge-enrichment` | yes | Contributors include `ai`, `ingest`, `platform-admin`, and `routine-vault` |
| `skill-standards` | tiered | adaptive | `routine-coverage` | `skill-standards` | yes | Contributors: `daemon`, `routine-coverage` |
| `observability` | tiered | adaptive | `routine-platform` | `observability` | yes | Contributors: `routine-platform`, `routine-vault` |
| `ui-quality` | tiered | adaptive | `routine-codebase` | `ui-quality` | yes | Single active contributor: `routine-codebase` |
| `page-health` | tiered | adaptive | `routine-platform` | `page-health` | yes | Single active contributor: `routine-platform` |
| `self-heal` | tiered | adaptive | `daemon` | `self-heal` | yes | Contributors: `daemon`, `routine-platform` |
| `skill-quality` | tiered | adaptive | `auto-skill-quality` | `skill-quality` | yes | Declared with legacy `x-augur-loop`, not `x-augur-commands` |
| `duplication` | tiered | adaptive | `platform-admin` | `duplication` | yes | Single active contributor: `platform-admin` |
| `auto-agent-digest` | tiered | adaptive | `ai` | `auto-agent-digest` | yes | Single active contributor: `ai` |
| `command-evolution` | tiered | adaptive | `routine-coverage` | `command-evolution` | yes | Contributors: `ai`, `routine-coverage` |
| `evals` | tiered | observability-only | `evals` | `evals` | no | Declared with legacy `x-augur-loop`; not scheduled in current Codex seed |
| `file-organizer` | tiered | adaptive | private-vault `file-manager` | `file-organizer` | yes | Private skill routine; schedule migrates to Au-vault |

Flat namespace check: no collisions if and only if each routine id above has one declaration owner. Multi-owner command contribution must remain below the routine declaration layer.

## Active Loop Contributors

| Routine id / loop | Active command owners | Command count | Representative command ids |
|---|---|---:|---|
| `auto-agent-digest` | `ai` (1) | 1 | `auto-agent-digest` |
| `code-quality` | `daemon` (1), `platform-admin` (11), `routine-codebase` (2), `routine-coverage` (5), `routine-platform` (2), `routine-vault` (1) | 22 | `auto-format`, `auto-lint`, `auto-git-health`, `auto-logs`, `auto-mcp-hygiene` |
| `command-evolution` | `ai` (1), `routine-coverage` (1) | 2 | `auto-command-evolution`, `auto-command-help-coverage` |
| `duplication` | `platform-admin` (1) | 1 | `auto-duplication` |
| `evals` | `evals` (1) | 1 | `evals` |
| `hardening` | `daemon` (4), `platform-admin` (4), `routine-codebase` (1), `routine-platform` (7), `routine-security` (1), `routine-vault` (4) | 21 | `auto-yaml-lint`, `auto-security-audit`, `auto-frontmatter-lint`, `auto-plugin-lint` |
| `knowledge-enrichment` | `ai` (10), `ingest` (1), `platform-admin` (1), `routine-vault` (1) | 13 | `auto-memory-sync`, `auto-docs`, `auto-claude-md-audit`, `run-pending-enrichment` |
| `observability` | `routine-platform` (3), `routine-vault` (1) | 4 | `auto-inspect`, `auto-perf-profile`, `auto-repo-sync`, `auto-context-audit` |
| `page-health` | `routine-platform` (1) | 1 | `auto-page-health` |
| `self-heal` | `daemon` (2), `routine-platform` (1) | 3 | `auto-self-heal`, `auto-heal-validate`, `auto-file-growth` |
| `skill-quality` | `auto-skill-quality` (1) | 1 | `auto-skill-quality` |
| `skill-standards` | `daemon` (2), `routine-coverage` (1) | 3 | `auto-skill-md`, `auto-skill-refs`, `auto-skill-usage` |
| `testing` | `routine-codebase` (12), `routine-platform` (1) | 13 | `auto-test-build`, `auto-test-pytest`, `auto-test-mcp`, `auto-mcp-health-audit` |
| `ui-quality` | `routine-codebase` (1) | 1 | `auto-ui-quality` |

## Current Scheduled Bindings

| Schedule id | Legacy loop | Prompt today | Proposed routine id | Proposed schedule owner | Migration note |
|---|---|---|---|---|---|
| `codex-dev-loop-testing` | `testing` | `/dev-loops run testing` | `testing` | `routine-codebase` | Move from daemon seed to `routine-codebase/assets/seeds/routine-schedule.yaml` |
| `codex-dev-loop-code-quality` | `code-quality` | `/dev-loops run code-quality` | `code-quality` | `routine-codebase` | Prompt changes to `/routines run code-quality` after alias is live |
| `codex-dev-loop-hardening` | `hardening` | `/dev-loops run hardening` | `hardening` | `routine-platform` | Aggregates hardening commands across skills by loop name |
| `codex-knowledge-enrichment-nightly` | `knowledge-enrichment` | `/dev-loops run knowledge-enrichment` | `knowledge-enrichment` | `routine-vault` | Knowledge contributors outside `routine-vault` remain command contributors |
| `codex-dev-loop-skill-standards` | `skill-standards` | `/dev-loops run skill-standards` | `skill-standards` | `routine-coverage` | Includes daemon-owned skill standard commands |
| `codex-dev-loop-skill-quality` | `skill-quality` | `/dev-loops run skill-quality` | `skill-quality` | `auto-skill-quality` | Requires ADR-758 scope expansion beyond 5 routine-* skills |
| `codex-dev-loop-observability` | `observability` | `/dev-loops run observability` | `observability` | `routine-platform` | Includes vault context audit command |
| `codex-dev-loop-duplication` | `duplication` | `/dev-loops run duplication` | `duplication` | `platform-admin` | Requires ADR-758 scope expansion beyond 5 routine-* skills |
| `codex-dev-loop-ui-quality` | `ui-quality` | `/dev-loops run ui-quality` | `ui-quality` | `routine-codebase` | Single owner today |
| `codex-dev-loop-auto-agent-digest` | `auto-agent-digest` | `/dev-loops run auto-agent-digest` | `auto-agent-digest` | `ai` | Requires ADR-758 scope expansion beyond 5 routine-* skills |
| `codex-dev-loop-file-organizer` | `file-organizer` | `/dev-loops run file-organizer` | `file-organizer` | private-vault `file-manager` | Private skill schedule; migrate to Au-vault `skills/file-manager/assets/seeds/routine-schedule.yaml` |
| `codex-dev-loop-page-health` | `page-health` | `/dev-loops run page-health` | `page-health` | `routine-platform` | Single owner today |
| `codex-dev-loop-self-heal-validate` | `self-heal` | `/dev-loops run self-heal --validate` | `self-heal` | `daemon` | Prompt carries extra `--validate`; preserve in schedule args |
| `codex-command-evolution-drain` | `command-evolution` | `/dev-loops run command-evolution --drain` | `command-evolution` | `routine-coverage` | Prompt carries extra `--drain`; preserve in schedule args |
| `codex-knowledge-enrichment-drain` | `knowledge-enrichment` | `/dev-loops run knowledge-enrichment --drain` | `knowledge-enrichment` | `routine-vault` | Prompt carries extra `--drain`; preserve in schedule args |
| `codex-dream-overnight` | `dream` | `/dream` | `dream` | `dream` | Rename seed to `dream/assets/seeds/routine-schedule.yaml`; prompt changes to `/routines run dream` after alias is live |

## Current Command Declarations In Scope

| Skill | Routine ids / loop categories present today | Active command declaration count |
|---|---|---:|
| `dream` | `dream` via prompt and MCP tools | 0 |
| `routine-codebase` | `testing`, `code-quality`, `hardening`, `ui-quality` | 16 |
| `routine-platform` | `testing`, `code-quality`, `hardening`, `observability`, `page-health`, `self-heal` | 15 |
| `routine-vault` | `code-quality`, `hardening`, `knowledge-enrichment`, `observability`; plus unscheduled `sweep-stores` command | 8 |
| `routine-coverage` | `code-quality`, `command-evolution`, `skill-standards` | 7 |
| `routine-security` | `hardening` | 1 |
| `ai` | `knowledge-enrichment`, `command-evolution`, `auto-agent-digest`; plus non-routine commands | 17 |
| `daemon` | `self-heal`, `hardening`, `skill-standards`, `code-quality`; plus `dev-loops` and current `routine` CLI | 12 |
| `platform-admin` | `code-quality`, `hardening`, `knowledge-enrichment`, `duplication`; plus dev commands | 22 |
| `auto-skill-quality` | `skill-quality` via `x-augur-loop` | 1 |
| `evals` | `evals` via `x-augur-loop` | 1 |
| `ingest` | `knowledge-enrichment`; plus `ingest` and `note` | 3 |

## Task 2 Readiness

Task 2 can start after the registry tests encode these constraints:

- Singular `x-augur-routine` and plural `x-augur-routines` both parse.
- Duplicate flat routine ids are errors only for duplicate declaration owners, not for command contributors sharing the same legacy loop.
- The registry walks declaration blocks for routine wrappers and leaves individual `x-augur-commands` discovery to the existing orchestrator.
- Legacy `x-augur-loop` singleton skills (`auto-skill-quality`, `evals`) either gain explicit `x-augur-routine` declarations or are intentionally excluded with a documented status.
- The `file-organizer` schedule is mapped to private-vault `file-manager` before schedule migration.
