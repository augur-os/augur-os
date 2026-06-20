---
title: sweep-stores — interactive LLM-driven classification with tiered Q&A and cached decisions
date: 2026-05-12
status: Draft
authors:
  - gsannikov
related_adrs:
  - ADR-571   # vault frontmatter conventions
related_specs:
  - 2026-05-11-loop-hygiene-design.md
scope: enhancement to the loop-hygiene skill committed in the 2026-05-11 spec
---

# Enhanced `/sweep-stores`: tiered classification, interactive Q&A, persistent group decisions

## 1. Problem

The MVP `/sweep-stores` (spec `2026-05-11-loop-hygiene-design.md`) catches one shape of stale artifact: files sharing a base name plus a numeric version marker (e.g., `guriqo-com-V10015.zip` … `V10032.zip`). It cannot detect:

1. **Renamed iterations** — same role, different filename. `augur-intel-form-answers.md` (Mar 20) replaced by `final-form-answers.md` (Mar 30). No shared version marker; current rubric treats them as unrelated.
2. **Variant suffixes** — shared base with role-qualifier suffix. `linkedin-banner-personal.png` vs `linkedin-banner-personal-augur.png`. Rubric refuses to group; both kept, even when one is genuinely dead.
3. **Mixed version schemes** — same logical artifact, two version conventions in sequence. `guriqo-com-v33-1.zip` … `v45-1.zip` then renamed to `V1.zip` … `V10032.zip`. Rubric forces an ambiguity flag; user has to disambiguate manually each sweep.
4. **Format siblings where one is abandoned** — `augur-vision-1.pdf` + `augur-vision-1.pptx`. Rubric says both are canonical. Sometimes one format has been dead for months.
5. **Conceptual supersession** — files with no name overlap that share a role. `pricing-draft.md` replaced by `new-pricing-strategy.md`. Pattern matching cannot see this.

Result observed in today's sweep of `Au-docs/venture-augur/`: 12 subfolders scanned, 47 moves proposed (all in `websites/`), and several real staleness cases left in place because the rubric had no signal for them. The user has to disambiguate each one verbally every sweep.

## 2. Goal

Extend `/sweep-stores` so that:
- The agent uses a tiered confidence rubric to decide between autonomous proposal, interactive Q&A, and content inspection.
- Ambiguities surface as focused, batched questions via `AskUserQuestion`.
- User decisions persist in `.augur-lifecycle.yaml` so subsequent sweeps don't re-ask the same questions.
- The system stays vendor-neutral (agent-as-classifier; no LLM SDK in the skill).

Non-goals are listed in §9.

## 3. Decision summary

Three additive changes to the existing loop-hygiene skill:

1. **Rubric replacement.** `references/sweep-rubric.md` switches from a flat rule list to a **three-tier confidence rubric** with explicit signal definitions for each tier.
2. **Persistence schema.** `.augur-lifecycle.yaml` gains a `known_groups[]` section that caches the user's group/canonical decisions.
3. **Workflow flow.** `commands/sweep-stores.md` gains a known-group-matching step (before classification) and a batched-question step (after Tier 2/3 classification, before proposal).

Two minor MCP contract extensions:
- `hygiene-scan` output includes `known_groups` inside `lifecycle_config`.
- `hygiene-apply` accepts an optional `lifecycle_updates[]` list and writes it to the per-folder YAML atomically before performing moves.

No new MCP tools. No daemon wiring. No dashboard surface. No vendor LLM config.

**Why this shape:** every reasoning step stays agent-side per rule 19 (agents own judgment, MCP tools own atomic operations). The MCP tools gain a single deterministic write path for the cache; everything else is rubric work the agent already does.

## 4. Tier rubric (the core policy)

The agent classifies every candidate fuzzy group into one of three tiers based on deterministic signals. Tier determines whether the agent proposes, asks, or first inspects content.

### Tier 1 — High confidence (propose autonomously, no question)

**Signal:** files share a base name + a version-marker token matching `[Vv]\d+(-\d+)?`.

**Example:** `guriqo-com-V10015.zip` … `guriqo-com-V10032.zip`.

**Action:** propose archive of all-but-highest. Behavior identical to today's rubric.

### Tier 2 — Medium confidence (one batched question per fuzzy group)

**Signal triggers (any of):**
- **(a) Mixed version schemes** — shared base + DIFFERENT version-marker conventions across files.
- **(b) Variant suffixes** — shared base + role-qualifier suffix differs (`-personal` vs `-personal-augur`).
- **(c) Renamed iterations** — names differ but share at least one role token (substring ≥ 6 chars, tokenized on `-`/`_`/`.`, ignoring version markers and common suffixes like `final`/`draft`) AND mtimes are chronologically ordered (older first).

**Action:** ONE single-select question per group via `AskUserQuestion`. Options:
- "Same group, keep `<newest by mtime>`"
- "Same group, keep `<alternative>`" (only when a non-trivial alternative exists)
- "Not a group, keep both/all"

**Caching:** on user `--apply`, the answer becomes a `known_groups[]` entry.

### Tier 3 — Low confidence (content inspection, then question)

**Signal triggers (any of):**
- **(d) Format-sibling pair where one is abandoned** — same base + different extension AND mtime gap > 60 days AND only one was modified in the last 30 days. The recently-touched file is the implied canonical; the question presents it as such.
- **(e) Conceptual supersession** — no name overlap but role keywords match across files (e.g., both contain `pricing` and one references the other's deprecation).

**Action:**
1. Agent reads file content via Read tool (text files only, ≤ 200 lines each, ≤ 10 files per sweep).
2. Agent forms a hypothesis: "X appears to supersede Y because `<evidence>`."
3. `AskUserQuestion` presents the hypothesis as the first option, plus 2 alternatives.

**Caching:** same as Tier 2.

### Always-skip cases

- Different formats at the same logical version with mtimes within 7 days (`augur-vision-1.pdf` + `.pptx` written together) → both canonical, no proposal, no question.
- Milestone-pinned files → existing refusal, never proposed.
- Never-touch list → existing refusal, never proposed.

### Question budget

- Hard cap: **4 questions per sweep** (the `AskUserQuestion` tool's maximum).
- Batched: a single `AskUserQuestion` call carries all open questions. User answers in one pass.
- If more than 4 groups need asking, the agent surfaces the first 4 (in folder-order, then alphabetical) and reports the rest as "deferred — re-run after answering current batch."

### Content inspection budget

- Text-like files (`.md`, `.txt`, `.html`, `.yaml`, `.yml`, `.json`, `.rst`, `.csv`, `.sh`): first 200 lines via Read tool. Agent extracts frontmatter, first H1, DRAFT/TODO/DEPRECATED markers, explicit `Replaces:` / `Supersedes:` / `Obsoletes:` lines.
- Document binaries (`.pptx`, `.docx`, `.pdf`): do NOT parse. Use sibling `.meta.yaml` file if present, otherwise report name + size + mtime only.
- Images (`.png`, `.jpg`, `.jpeg`, `.svg`, `.webp`): name + size + mtime only (no EXIF, no perceptual hashing in v1).
- Video / archive (`.mp4`, `.mov`, `.zip`, `.tar`, `.gz`): name + size + mtime only.
- Hard cap: 10 files inspected per sweep. If a Tier 3 group has more than 10 candidates, agent skips the group and tells the user to pick canonical via milestone-pin or direct YAML edit.

## 5. Persistence schema — `.augur-lifecycle.yaml` extension

Existing fields (`enabled`, `pattern_hints`, `keep_latest`, `deploy_root`, `notes`) are unchanged. One new top-level key: `known_groups`.

```yaml
# venture-augur/websites/.augur-lifecycle.yaml
enabled: true
pattern_hints:
  - "guriqo-com-V*.zip"
  - "augur-run-V*.zip"
deploy_root: false

known_groups:
  - name: guriqo-com-build
    canonical_strategy: highest_version
    pattern: "guriqo-com-*.zip"
    decided_at: 2026-05-12T14:30:00Z
    decided_by: gsannikov
    note: "Confirmed v33-1..v45-1 are stale older scheme."

  - name: form-answers
    canonical_strategy: explicit
    members:
      - augur-intel-form-answers.md
      - final-form-answers.md
    canonical: final-form-answers.md
    decided_at: 2026-05-12T14:31:00Z
    decided_by: gsannikov
    note: "Rename iteration; final supersedes intel-form-answers."

  - name: linkedin-banner-personal
    canonical_strategy: not_a_group
    members:
      - linkedin-banner-personal.png
      - linkedin-banner-personal-augur.png
    decided_at: 2026-05-12T14:32:00Z
    decided_by: gsannikov
    note: "Different roles, both canonical."
```

### `canonical_strategy` values

| Strategy | When used | Sweep behavior |
|---|---|---|
| `highest_version` | Clean version-numbered groups | Apply Tier 1 rubric inside the group's pattern; no question. |
| `explicit` | Named members + named canonical | Archive every member except `canonical`; no question. |
| `not_a_group` | User said "keep both" / "keep all" | Never propose moves for any member of this group; no question. |

### Required fields per entry

- `name` (string, unique within folder): group identifier; used to refuse name-collision on `lifecycle_updates`.
- `canonical_strategy` (enum): one of `highest_version`, `explicit`, `not_a_group`.
- `decided_at` (ISO8601 UTC): set by `hygiene-apply` at write time.
- `decided_by` (string): from `$USER` at write time.

### Optional fields (strategy-dependent)

- `pattern` (glob): required for `highest_version` (defines membership).
- `members` (list of filenames): required for `explicit` and `not_a_group`.
- `canonical` (filename): required for `explicit`.
- `note` (string): free-form, hand-editable.

### Validation rules

- A `highest_version` entry without `pattern` is malformed → scanner returns a warning, agent treats folder as if entry is absent.
- An `explicit` entry without `canonical` OR without `members` is malformed → same warning behavior.
- A `not_a_group` entry without `members` is malformed → same.
- Two entries with the same `name` is a write collision → `hygiene-apply` refuses the new entry, returns refusal in result.
- `decided_by` ≠ current `$USER` is not an error — multi-user editing is allowed; the field is informational.

### Invalidation / escape hatch

- User hand-edits `.augur-lifecycle.yaml` to remove an entry → next sweep re-asks.
- User hand-edits a `members` list or `canonical` → next sweep uses the new values.
- `decided_at` is informational; no automatic expiration in v1.

## 6. Workflow flow

```
1. /sweep-stores <path> [--apply] invoked.

2. hygiene-scan returns:
     - files[]
     - lifecycle_config (with known_groups)
     - milestone_pins
     - never_touch_skipped

3. KNOWN-GROUP MATCHING (new step):
     for each known_group in lifecycle_config.known_groups:
       resolve members:
         strategy == highest_version → glob match files[] against pattern
         strategy == explicit         → match files[] against members[]
         strategy == not_a_group      → match files[] against members[]
       apply cached strategy:
         not_a_group  → mark all matched files as "no-touch this sweep"
         explicit     → archive all matched members except canonical
         highest_version → run Tier 1 rubric within matched members

4. TIER CLASSIFICATION on remaining unmatched files:
     For each candidate group:
       evaluate signals → assign Tier 1 / 2 / 3 / always-skip
     Collect Tier 1 → autonomous_moves[]
     Collect Tier 2 → question_batch[]
     Collect Tier 3 → invoke content inspection → question_batch[]

5. INTERACTIVE Q&A (if question_batch not empty):
     Cap at 4 questions; defer rest.
     Single AskUserQuestion call with up to 4 questions.
     Each question carries:
       - candidate filenames + brief evidence line
       - options: "Same group, keep <X>" | "Same group, keep <Y>" | "Not a group, keep all"
     Build user_answered_moves[] + lifecycle_updates[] from answers.

6. BUILD PROPOSAL:
     moves = known_group_derived_moves + autonomous_moves + user_answered_moves
     refusals = deploy_root + milestone-pinned + never-touch
     Present structured proposal (same format as today).

7. WAIT FOR APPROVAL:
     Accepted forms: "apply", "skip", "apply only group X", "tag Y as milestone first".

8. ON APPROVAL + --apply:
     hygiene-apply(
       root="docs",
       moves=[...],
       lifecycle_updates=[...],   # NEW optional field
       dry_run=false
     )
     Tool writes YAML first, then performs moves.

9. REPORT RESULT:
     - per-move success/failure
     - new known_groups entries cached
     - any refusals
     - reminder: verify in fresh AI client session
```

## 7. MCP tool contract changes

### 7.1 `hygiene-scan` — additive output

```diff
  "lifecycle_config": {
    "pattern_hints": [...],
    "deploy_root": false,
-   "enabled": true
+   "enabled": true,
+   "known_groups": [
+     {
+       "name": "guriqo-com-build",
+       "canonical_strategy": "highest_version",
+       "pattern": "guriqo-com-*.zip",
+       "members": null,
+       "canonical": null,
+       "decided_at": "...",
+       "decided_by": "...",
+       "note": "..."
+     }
+   ]
  }
```

- Field is always present (empty array if no entries).
- Missing-or-malformed entries return a warning in `lifecycle_config` and are dropped from the array.

### 7.2 `hygiene-apply` — additive input

```diff
  {
    "root": "docs",
    "moves": [...],
+   "lifecycle_updates": [
+     {
+       "folder": "venture-augur/websites",
+       "known_group": { ... }
+     }
+   ],
    "dry_run": false
  }
```

### Write semantics

1. **Validate first** — for each `lifecycle_updates[].known_group`:
   - Required-field check per §5.
   - Name-collision check against existing entries in the target folder's YAML.
   - On any validation failure, that update is `refused` with category `lifecycle_collision` or `lifecycle_malformed`. Other updates and all moves proceed.
2. **Write YAML before moves** — for each non-refused update:
   - Parse existing `.augur-lifecycle.yaml` (or create scaffold if missing).
   - Append entry to `known_groups[]`.
   - Write to `.augur-lifecycle.yaml.tmp`, then `os.rename()` to final path (atomic).
3. **Then perform moves** — same logic as today.
4. **YAML writes are NOT rolled back if a move later fails** — cached decision is independent of physical archival. The user can re-run the sweep; the cache will already say "this group is known," and the agent will re-propose the same moves without re-asking.
5. **Dry-run** — `dry_run=true` validates YAML updates the same way (collision check, malformed check) but writes nothing. Returns `would_succeed` / `would_refuse` per update, same shape as moves.

### Why YAML-write-before-moves

If we wrote YAML after moves, a partial-move failure (some files moved, manifest written, then process killed) would leave the cache un-updated. Next sweep would re-ask. By writing the YAML first (atomic, independent), the cache is durable as soon as the user approves — and re-runs converge to the same proposal without redundant questions.

## 8. Testing strategy

| Layer | Tests |
|---|---|
| Unit (`test_hygiene_scan.py`) | `known_groups` parsing: valid / missing / malformed. Pattern resolution against file list. Warning emission on malformed entries. |
| Unit (`test_hygiene_apply.py`) | `lifecycle_updates` write: append-to-existing, create-new YAML, name-collision refusal, malformed refusal, atomic temp-rename, write-before-moves ordering, dry-run validates without writing. |
| Fixture (`fixture_renamed_iteration/`) | Two files with role-token overlap; rubric instructs agent to ask. |
| Fixture (`fixture_variant_suffix/`) | Shared base + qualifier suffix; agent must ask. |
| Fixture (`fixture_mixed_version_scheme/`) | `guriqo-com-v33-1.zip` + `guriqo-com-V10032.zip`; agent must ask. |
| Fixture (`fixture_conceptual_supersession/`) | Two `.md` files, one with `Replaces: <other>` in frontmatter; agent inspects content, surfaces hypothesis. |
| Fixture (`fixture_cached_known_group/`) | Folder has pre-existing `known_groups` entry; scan returns it; rubric instructs agent to skip Tier 2 question for matching files. |
| Fixture (`fixture_lifecycle_malformed/`) | YAML with bad `known_groups` entry; scan returns warning; agent treats folder as having no cache. |
| E2E (`test_hygiene_e2e.py`) | Sweep #1 on fresh fixture: question batch surfaces. Mock user answers. Apply → assert moves AND YAML update. Sweep #2 on now-cached folder: assert no question batch, same moves proposed. |
| Manual | `/sweep-stores Au-docs/venture-augur` after this enhancement ships; confirm Tier 2 questions surface for `IntelSubmit/`, `images/`, `videos/` cases flagged in the 2026-05-12 sweep. |

**No LLM-quality eval** — same stance as the v2 MVP. The rubric is reviewed manually; deterministic plumbing (scan, apply, YAML round-trip, name-collision) is what gets tested.

## 9. Out of scope (this enhancement)

- Image perceptual hashing (`imagehash`). Defer until image-variant detection becomes a hot loop.
- PDF / `.docx` / `.pptx` text extraction. Cost too high, parser fragility too high for v1. Use sibling `.meta.yaml` files for any deck/doc context.
- Auto-loop integration. Phase 5 of the 2026-05-11 spec still owns this.
- Au-vault scope. Phase 3 of the 2026-05-11 spec still owns this.
- Cross-folder `known_groups` (a global lookup table). Each entry is scoped to its source folder; no global registry.
- Multi-canonical groups (e.g., "keep top 3 versions"). `canonical_strategy` is single-canonical or not-a-group only in v1.
- Cooldown on re-ask (e.g., "don't re-ask within 7 days"). Cached entries are the cooldown mechanism.
- Undo command for cached decisions. Hand-edit the YAML is the escape hatch.
- A `/forget-group <name>` slash command. Same escape hatch.
- A dashboard surface for browsing `known_groups`. Phase 6 of the 2026-05-11 spec still owns this.

## 10. Backward compatibility

- Folders with no `.augur-lifecycle.yaml` → behavior identical to today.
- Folders with the old schema (no `known_groups` key) → treated as `known_groups: []`.
- Existing `/sweep-stores` invocations (no cache, no Tier 2/3 ambiguities) → behavior identical to today plus the new question layer.
- Existing `hygiene-apply` callers that omit `lifecycle_updates` → behavior identical (the field is optional).

## 11. ADR governance

This enhancement is **not** an ADR-level architectural change. It extends an existing skill within the trajectory the 2026-05-11 spec explicitly anticipated (richer agent-side reasoning). The design doc itself is the canonical reference.

If during implementation we hit a contract decision that becomes load-bearing for other skills (e.g., `known_groups` schema gets read by `vault-search` or by a Phase 5 auto-loop), we cut an ADR at that point.

## 12. Open questions

None at spec-write time. Questions surfacing during plan-writing will be answered in plan PRs.

## 13. References

- `2026-05-11-loop-hygiene-design.md` — base design this enhancement extends.
- `CLAUDE.md` rules 1, 5, 11, 14, 19.
- `shared-vault/skills/loop-hygiene/references/sweep-rubric.md` — current rubric.
- `shared-vault/skills/loop-hygiene/commands/sweep-stores.md` — current workflow.
- `shared-vault/skills/loop-hygiene/augur/data/lifecycle_schema.yaml` — schema definition file.
- Memory: `feedback_design_only_no_shortcuts.md`, `feedback_vendor_neutral_design.md`, `feedback_cross_agent_enforcement.md`.
