# /sweep-stores classification rubric

This is the rubric the agent applies to `hygiene-scan` output to decide which files are stale versions and which are current. It pairs with the slash command at `commands/sweep-stores.md`.

## Scope

`hygiene-scan` is recursive. When the user passes a folder, classify all regular files under that folder and its descendants.

Artifact grouping remains folder-scoped. Compare files only with other files sharing the same `folder_relative_path`; do not make one group across sibling or parent/child folders unless a cached decision in that folder explicitly covers those members.

### Typed Browse selections

For `docs` and `pages-artifacts`, use the existing per-folder docs archive behavior.

For `source-cards`, `vault-notes`, and `pages-live`, do not propose moves for untracked or dirty files. Apply refuses them; report refusals as user-visible safety outcomes, not hidden errors.

## Step 0 — Known-group matching

Before any tier work, apply cached decisions from each folder's lifecycle config:

- `canonical_strategy: highest_version` uses `pattern` as a glob, keeps the highest numeric version, and archives the rest without asking.
- `canonical_strategy: explicit` uses `members[]`, keeps `canonical`, and archives the other matched members without asking.
- `canonical_strategy: not_a_group` uses `members[]` and marks every matched file as no-touch for this sweep.

Use `folder_lifecycle_configs[folder_relative_path].known_groups[]` for recursive folders and `lifecycle_config.known_groups[]` only as the backward-compatible root-folder field. Files consumed by known-group matching are removed from that folder's candidate pool before tier classification.

## Tier 1 — High Confidence

**Signal:** files share a base name plus a version-marker token matching `[Vv]\d+(-\d+)?`.

**Example:** `guriqo-com-V10015.zip` through `guriqo-com-V10032.zip`.

**Action:** propose archive of all-but-highest. Tiebreaker: latest `mtime_iso`.

## Tier 2 — Medium Confidence

Ask one batched question per fuzzy group when any signal appears:

- **Mixed version schemes:** shared base with different marker conventions, such as `v33-1` and `V10032`.
- **Variant suffixes:** shared base with role qualifier differences, such as `linkedin-banner-personal.png` and `linkedin-banner-personal-augur.png`.
- **Renamed iterations:** names differ but share at least one role token of six or more characters after tokenizing on `-`, `_`, and `.`, ignoring version markers and common suffixes like `final` or `draft`, with mtimes ordered older first.

Options:

- `Same group, keep <newest by mtime>`
- `Same group, keep <alternative>`
- `Not a group, keep both/all`

The accepted answer becomes a `known_groups[]` entry on `--apply`.

## Tier 3 — Low Confidence

Inspect content first, then ask, when any signal appears:

- **Format sibling where one is abandoned:** same base with different extension, mtime gap greater than 60 days, and only one file modified in the last 30 days.
- **Conceptual supersession:** weak or no name overlap, but role keywords match and one text file references replacement or deprecation.

Content inspection limits:

- Text-like files only: `.md`, `.txt`, `.html`, `.yaml`, `.yml`, `.json`, `.rst`, `.csv`, `.sh`.
- Read no more than 200 lines per file and no more than 10 files per sweep.
- Extract frontmatter, first H1, `Replaces:`, `Supersedes:`, `Obsoletes:`, and `DRAFT` / `TODO` / `DEPRECATED` markers.
- Do not parse binaries. For `.pptx`, `.docx`, `.pdf`, images, videos, and archives, report name, size, and mtime only. Use sibling `.meta.yaml` if present.

Question options present the agent's hypothesis first, then an alternate canonical, then a not-a-group option.

## Always-Skip Cases

- Different formats at the same logical version with mtimes within 7 days are both canonical.
- Files in `milestone_pins` are refused by `hygiene-apply`.
- Files in `folder_milestone_pins` are reported and not proposed.
- Files in `never_touch_skipped` are excluded by `hygiene-scan`.
- Files in folders with `deploy_root: true` in `folder_lifecycle_configs` are reported but never proposed.

## Question Budget

- Hard cap: 4 questions per sweep.
- Use one batched `AskUserQuestion` call for all open questions.
- If more than 4 groups need asking, surface the first 4 by folder order then alphabetical order, and report the rest as deferred.

## Required Output Format

Before any `hygiene-apply` call, show the user:

```markdown
## Sweep proposal — <scanned_path>

### Group: <folder>/<artifact_group> (<N> stale + 1 current)
- Keep: <current-relative-path> (size, mtime)
- Archive:
  - <stale-relative-path> reason: superseded by <current-relative-path>

### From cached known_groups
- Group <name> (strategy=<strategy>): <N> moves derived from cache.

### Refused / skipped
- <relative-path> category: <deploy_root | milestone_pinned | never_touch> reason: ...

### New decisions to cache
- known_groups[].name=<name>, strategy=<strategy>, decided_at=<now>

Total: <N> moves, <total-bytes> archived.
```

## Edge Cases

- Single member in a group means no proposal.
- Group spans subfolders means no group; `hygiene-scan` is recursive but classification is folder-scoped.
- Ambiguous case with no clear signal means ask the user; do not guess.
- A `known_groups` entry referencing a missing file is ignored for that sweep.
- User answers `skip` to a question means the group is untouched and no `lifecycle_updates` entry is written.
