---
description: Sweep stale-version artifacts in a folder under Au-docs into per-folder .archive/ via the agent-in-session as classifier.
visibility: core
x-augur-export-command: false
---

> **Retired primary surface:** `/sweep-stores` is no longer exported to primary
> AI clients. Use `/sweep` instead.

# /sweep-stores

Sweep stale-version artifacts in a folder under Au-docs into per-folder `.archive/` directories that AI scanners ignore. You (the agent in this session) classify; the user approves; the MCP tools execute atomically.

## Usage

```bash
/sweep-stores <path>                  # dry-run (default)
/sweep-stores <path> --apply          # destructive
/sweep-stores <path> --paths-only     # emit only the paths that would be archived; no reasoning text
```

For terminal `/sweep-stores`, `<path>` is a folder under `Au-docs/` (absolute or relative). Browse Sources, Notes, and Pages use typed selection MCP tools instead of this path argument.

## What it does (read this carefully before acting)

1. Call MCP tool `hygiene-scan <path>` to get the recursive file listing, root lifecycle config, per-folder lifecycle configs (including `known_groups[]`), per-folder milestone pins, and never-touch skips.
2. **Apply cached known-group decisions per containing folder** before classification:
   - `highest_version` archives all but the highest matching version.
   - `explicit` archives every listed member except `canonical`.
   - `not_a_group` marks all listed members as no-touch for this sweep.
3. **Classify remaining files by folder** using the tiered rubric at `references/sweep-rubric.md`:
   - Tier 1: autonomous proposal.
   - Tier 2: collect into the question batch.
   - Tier 3: inspect text content first (200 lines per file, 10 files per sweep), then collect into the question batch.
4. **Ask the user if the question batch is non-empty**:
   - Use one `AskUserQuestion` call with up to 4 questions.
   - Defer overflow groups and tell the user to re-run after answering the current batch.
   - Build `lifecycle_updates[]` from answered Tier 2/3 decisions.
5. **Present** the structured proposal. Include cached-derived moves, Tier 1 moves, answered Tier 2/3 moves, refusals, and new decisions to cache. Do NOT call `hygiene-apply` yet.
6. **Wait for explicit user approval.** Acceptable forms: "apply", "apply only group X", "skip group Y", "tag file Z as milestone first then apply".
7. On approval, call MCP tool `hygiene-apply` with:
   - `root="docs"`
   - `moves=[{from: relative_path, reason: "...", artifact_group: "..."}]`
   - `lifecycle_updates=[{folder: "...", known_group: {...}}]` when Tier 2/3 questions were answered
   - `dry_run=false` if and only if the user passed `--apply`; otherwise `dry_run=true`.
8. **Report the result** including per-move refusals and per-update results (`written`, `would_succeed`, `refused` with refusal category).

## Rubric (full text)

See `references/sweep-rubric.md`. Key rules:

- `hygiene-scan` is recursive. A passed folder means all descendant folders and files under that folder are analyzed.
- An artifact group is files in the same containing folder sharing a base name + version marker, OR files in the same containing folder matching a `pattern_hints` glob.
- Cached `known_groups[]` entries are applied per folder before tier classification.
- Different formats of the same logical version are NOT in the same group unless the user has explicitly cached that decision.
- Tier 2 and Tier 3 ambiguities must be asked via a batched `AskUserQuestion`; do not guess.
- Files in `.augur-lifecycle.yaml` `deploy_root: true` folders → REPORT, never propose moves.
- Files in `milestone_pins` / `folder_milestone_pins` → REPORT, never propose moves.
- Files in `never_touch_skipped` → already excluded by `hygiene-scan`; do not include them in moves.

## Browse-triggered sweep

Browse first creates a typed selection with MCP tool `hygiene-create-selection` for `docs`, `source-cards`, `vault-notes`, `pages-artifacts`, or `pages-live` targets.

The agent scans that selection with `hygiene-scan-selection`, classifies with the ADR-736 rubric, asks Tier 2/Tier 3 questions, and applies approved moves with `hygiene-apply-selection`.

Browse-triggered sweep is apply-oriented: clicking `Sweep visible` is destructive intent, but ambiguity still requires questions before applying.

Final output must include manual recovery instructions:

- Docs recovery uses `.archive/_manifest.jsonl`.
- Git-managed `source-cards`, `vault-notes`, and `pages-live` recover through git history or `git mv` from the archive path.

## Interactive Q&A protocol

When the rubric assigns a group to Tier 2 or Tier 3, emit one `AskUserQuestion` call carrying all questions for this sweep, capped at 4. Each question has:

- **Subject line:** candidate filenames and the signal that triggered the tier.
- **Options (single-select):**
  - Tier 2: `Same group, keep <newest>` / `Same group, keep <alternative>` / `Not a group, keep both/all`.
  - Tier 3: `<hypothesis option>` / `Same group, keep <alternative>` / `Not a group, keep both/all`.

The answer drives both move additions and a `lifecycle_updates[]` entry for `hygiene-apply`. Do not inspect content for files outside Tier 3. Do not inspect more than 10 files per sweep.

## Required output format

Before any `hygiene-apply` call, show the user:

```
## Sweep proposal — <scanned_path>

### Group: <folder>/<artifact_group>  (<N> stale + 1 current)
- Keep: <current-relative-path>
- Archive:
  - <stale-relative-path>  reason: superseded by <current-relative-path>
  - ...

### Refused / skipped
- <relative-path>  category: <deploy_root | milestone_pinned | never_touch>

### From cached known_groups
- Group <name> (strategy=<strategy>): N moves derived from cache.

### New decisions to cache
- known_groups[].name=<name>, strategy=<strategy>

Total: <N> moves, <total-bytes> archived.
Run with --apply to execute.
```

## Refusal handling

If `hygiene-apply` returns per-move refusals (`status: "refused"`), the user MUST be told which files and why. Do not bury refusals.

## Safety

- Dry-run is the default. `--apply` is required for any destructive action.
- One move's refusal does not abort other moves; report each.
- Lifecycle update refusal does not abort moves; report `lifecycle_collision`, `lifecycle_malformed`, `outside_store`, `folder_missing`, or `malformed_update`.
- After `--apply` succeeds, remind the user to verify in a fresh AI client session that archived files are no longer surfaced.

## Spec

[docs/superpowers/specs/2026-05-11-routine-vault-design.md](../../../../docs/superpowers/specs/2026-05-11-routine-vault-design.md)
