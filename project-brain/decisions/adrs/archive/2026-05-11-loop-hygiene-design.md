---
title: loop-hygiene — store-wide artifact retention to stop AI hallucinations from stale versions
date: 2026-05-11
status: Draft
authors:
  - gsannikov
related_adrs:
  - ADR-571   # vault frontmatter conventions
  - ADR-731   # memory synthesis consolidation
  - ADR-491   # config-driven dashboard pages
mvp_scope: v2 — agent-as-classifier, Au-docs only, single .augur-ignore exclusion layer, no auto-loops, no llm.yaml
---

# loop-hygiene: store-wide artifact retention

## 1. Problem

`Au-docs/` (435 MB, 451 files) and `Au-vault/` (31 MB, 2348 files) accumulate AI-generated artifacts faster than they are pruned. Worst offender: `Au-docs/venture-augur/websites/` holds 48 versioned zip builds of two artifacts (`guriqo-com-V*.zip`, `augur-run-V*.zip`). Similar version sprawl exists in `presentations/`, `logos/`, `videos/`, `video/`.

Three concrete harms:

1. **AI context pollution.** Any AI tool that walks these folders (RAG indexer, browse scanner, MCP search, wiki ingest, vault-search, knowledge-summarize-file) reads stale versions alongside the current one. The model has no signal to pick the latest.
2. **No canonical "current" pointer.** Visually impossible to tell which deck, which logo, which website build is the live one.
3. **Storage bloat.** 60 MB+ of stale videos, 200 MB+ of stale website zips. Growing weekly.

Result: AI hallucinations from stale-version reads (the AI cites a deprecated positioning from an old deck), repeated user effort to disambiguate ("which file is current?"), and disk waste.

## 2. Goal

Build a store-wide artifact retention system that (a) keeps a single canonical "current" copy in the live tree, (b) moves stale versions to an archive that is invisible to all AI tooling, (c) eventually auto-purges archive contents past a retention window — while staying safe-by-default and never destroying user work without an explicit confirmation step.

## 3. Decision summary

Introduce a new skill `loop-hygiene` under `shared-vault/skills/loop-hygiene/`, group `augur_autoloops`, hub `adaptive`. The skill ships with a phased rollout. **Only the MVP-v2 scope is committed in this ADR.** Phases 2–6 are future work, accepted in principle, each gated on observed need.

**MVP-v2 scope (committed):**
- Single slash command `/sweep-stores` invoked inside any AI client session (Claude Code, Codex CLI, Gemini CLI, Cursor, etc.)
- Two MCP tools: `hygiene-scan` (read-only, returns file listing + metadata) and `hygiene-apply` (write, performs atomic moves)
- **The agent in the session is the classifier.** No `llm.yaml` task entry, no LLM SDK imports in the skill, no API keys, no model-routing config. The slash command instructs the agent to reason over `hygiene-scan` output and propose archives in chat; the user approves; the agent calls `hygiene-apply` with the approved list.
- Scope: **`Au-docs/` only** for MVP. Folders opt in via a per-folder `.augur-lifecycle.yaml` file or via explicit path argument. `Au-vault/` is out of scope for MVP.
- Single exclusion layer: `.augur-ignore` file at the archive root, plus appending `.archive/` to the store's `.gitignore`. This is the cheapest, most universally honored mechanism in the existing Augur scanner stack.
- Archive structure: an `.archive/` folder created **inside** each source folder that has files archived out of it (e.g., archived files from `venture-augur/websites/` land in `venture-augur/websites/.archive/`). Recovery is obvious — the archive sits right alongside the live files in the same folder. **No per-month partitioning yet** (defer to Phase 2 when auto-purge ships). **No auto-purge** in MVP — archive grows; user prunes manually via filesystem.
- No auto-loops, no daemon wiring, no dashboard tab, no new MCP tools beyond `hygiene-scan` and `hygiene-apply` in MVP.
- Dry-run is the default (`/sweep-stores <path>` reports without moving). Destructive action requires explicit `--apply`.

**Rationale for the MVP-v2 shape:**
- The agent-as-classifier path eliminates ~300 LOC of classifier scaffolding, vendor abstraction, caching, and cost guardrails that have no payoff until a nightly auto-loop exists.
- It aligns with Augur rule 19: agents own judgment, MCP tools own atomic operations, commands own policy, daemons schedule.
- It is genuinely vendor-neutral — whatever LLM the user's session is running becomes the classifier, no config needed.
- It defers the highest-risk components (destructive automation, multi-layer exclusions, dashboard surface) until the cheap layer is proven.

## 4. Full architectural vision (informative; not all committed)

The MVP is one phase of a longer-arc system. The full vision is documented so future contributors (and future-self) understand where this leads. Each phase past MVP is its own follow-up ADR.

```
                ┌────────────────────────────────────────────────┐
                │  Agent session (Claude Code / Codex / Gemini)  │
                │                                                │
                │  /sweep-stores <path>                          │
                │   │                                            │
                │   ▼                                            │
                │  hygiene-scan ─────────────┐                   │
                │   │                        │ (MCP read)        │
                │   │   ┌──────────────────────────┐             │
                │   │   │  agent reasoning:        │             │
                │   │   │  group artifacts,        │             │
                │   │   │  pick current,           │             │
                │   │   │  list stale + reasoning  │             │
                │   │   └──────────────────────────┘             │
                │   ▼                                            │
                │  user approves in chat                         │
                │   │                                            │
                │   ▼                                            │
                │  hygiene-apply ────────────┐                   │
                │                            │ (MCP write)       │
                └────────────────────────────┼───────────────────┘
                                             │
                                             ▼
                              Au-docs/<folder>/.archive/
                              + .augur-ignore
                              + .gitignore entry
                              + _manifest.jsonl (append-only)
```

**Phased rollout:**

| Phase | Adds | Trigger condition |
|---|---|---|
| **MVP (v2)** | `/sweep-stores`, two MCP tools, agent-as-classifier, Au-docs only, single exclusion layer, no auto-loops | this ADR |
| Phase 2 | Per-month archive partitioning (`.archive/YYYY-MM/`), weekly `archive-purge` auto-loop, 90-day retention with milestone tags | MVP proves hiding works for ≥ 30 days |
| Phase 3 | Au-vault scope (`notes/`, `sources/` only; `drafts/`, `prompts/`, `inbox/`, `memory/`, `wiki/`, `skills/`, `config/`, `archive/`, `dev/` excluded by allowlist semantics) | user opts in |
| Phase 4 | Additional exclusion layers (llms.txt, MCP boundary checks in `vault-search`/`knowledge-*`/`wiki-*`/`unified-search`, RAG denylist, Obsidian `userIgnoreFilters`) + verification probes (revert-on-failure) | observed leaks despite `.augur-ignore` |
| Phase 5 | Nightly `auto-hygiene` auto-loop (scan-only, no apply) + `loop-hygiene` registered with adaptive engine + inbox file for morning review | manual sweeps become a chore |
| Phase 5b | Optional `llm.yaml` task routing for unattended classification (when there is no agent session) | nightly loop needs deeper reasoning than naming patterns |
| Phase 6 | Dashboard tab in adaptive hub (inbox + summary + archive browser) + milestone tagging + undo window + audit log | confidence to remove human-in-loop, or visual review becomes preferable to CLI |

## 5. MVP components (committed)

### 5.1 Skill layout

```
shared-vault/skills/loop-hygiene/
├── SKILL.md                           # x-augur metadata, command + MCP tool contributions
├── commands/
│   └── sweep-stores.md                # slash command: agent-driven sweep workflow
├── scripts/
│   ├── hygiene_scan.py                # backs the hygiene-scan MCP tool
│   └── hygiene_apply.py               # backs the hygiene-apply MCP tool
├── augur/
│   ├── data/
│   │   └── lifecycle_schema.yaml      # JSON schema for .augur-lifecycle.yaml validation
│   └── pages/                         # empty in MVP; reserved for Phase 6
├── references/
│   └── sweep-rubric.md                # the reasoning rubric the slash command embeds for the agent
├── evals/
│   └── fixtures/                      # golden folder trees for testing
└── tests/                             # unit + e2e tests
```

### 5.2 `/sweep-stores` slash command (the policy surface)

The command is a markdown file that instructs the agent. It does not contain code. It carries the **rubric** the agent uses to classify.

**Invocation forms:**
- `/sweep-stores <path>` — dry-run. Scan path, agent reasons, agent shows proposal in chat, no files moved.
- `/sweep-stores <path> --apply` — same flow, but the agent calls `hygiene-apply` with the approved list at the end.
- `/sweep-stores <path> --paths-only` — agent emits only the paths that would be archived, no reasoning text. Useful for piping or quick checks.

**Rubric the command carries (excerpted):**
- An `artifact_group` is files that share a base name + a version marker (e.g., `guriqo-com-V*.zip` → group `guriqo-com-build`), OR files that share a role across formats only if mtimes show a versioning pattern (newer mtime supersedes older). Different formats of the same file at the same logical version (e.g., `augur-vision-1.pdf` + `augur-vision-1.pptx`) are NOT a group — both are kept.
- Within a group, the `current` member is the one with the highest version marker; tiebreaker is latest mtime.
- Files matching the never-touch list (§5.4) are not classified.
- Folders tagged `deploy_root: true` in `.augur-lifecycle.yaml` are reported but never recommended for archive — agent must instruct the user to act via filesystem.
- The agent must show its grouping to the user as a structured summary (table or bullet list per group) before any apply call.

### 5.3 `hygiene-scan` MCP tool (read-only)

**Input:** `{ path: string, follow_symlinks: false }` (symlinks never followed)

**Output:**
```json
{
  "root": "/Users/.../Au-docs",
  "scanned_path": "venture-augur/websites",
  "files": [
    {
      "name": "guriqo-com-V10032.zip",
      "relative_path": "venture-augur/websites/guriqo-com-V10032.zip",
      "size_bytes": 4100000,
      "mtime_iso": "2026-05-09T14:13:00Z",
      "content_hash_sha256": "ab12...",
      "is_symlink": false
    }
  ],
  "lifecycle_config": {
    "pattern_hints": ["guriqo-com-V*.zip", "augur-run-V*.zip"],
    "deploy_root": false,
    "enabled": true
  } | null,
  "milestone_pins": [
    { "relative_path": "venture-augur/websites/guriqo-com-V10025.zip", "tag": "intel-submission", "tagged_at": "..." }
  ],
  "never_touch_skipped": ["...paths skipped at scan time..."],
  "warnings": []
}
```

- Resolves the root via `src.config.paths.get_documents_dir()` (Au-docs). Au-vault paths are refused in MVP.
- Reads `.augur-lifecycle.yaml` from `scanned_path` if present (purely informational hints for the agent; does not gate scan).
- Reads `.milestones.json` from `scanned_path` if present.
- Never recurses into `.archive/`, `.git/`, `.obsidian/`, `.pytest_cache/`, `.tmp.driveupload/`, `node_modules/`, `.venv/`, `__pycache__/`, or any `.augur-*` marker file.
- Read-only. No side effects.

### 5.4 `hygiene-apply` MCP tool (destructive, atomic)

**Input:**
```json
{
  "root": "docs",
  "moves": [
    {
      "from": "venture-augur/websites/guriqo-com-V10031.zip",
      "reason": "superseded by guriqo-com-V10032.zip",
      "artifact_group": "guriqo-com-build"
    }
  ],
  "dry_run": false
}
```

**Behavior:**
1. Resolves `root` (MVP only accepts `"docs"`) → `get_documents_dir()`.
2. For each move, validates: source exists, is not a symlink, is not on the never-touch list, is not milestone-pinned, source and destination on same filesystem (refuses cross-mount). Refusal aborts that one move; other moves continue.
3. Constructs destination path: `<root>/<dir-of-source>/.archive/<basename>`. If destination already exists (same name was archived before), appends `.dup-<short-hash>` suffix.
4. Atomic move via `os.rename()`. If rename fails, that move fails; index/manifest not touched for that file.
5. After successful rename, appends one JSON object per line to `<root>/<dir-of-source>/.archive/_manifest.jsonl`:
   ```json
   {"archived_at":"...","from":"...","to":"...","reason":"...","artifact_group":"...","apply_run_id":"..."}
   ```
6. After all moves in a target folder succeed, ensures `<root>/<dir-of-source>/.archive/.augur-ignore` exists (creates with default content if not) and appends `.archive/` to `<root>/.gitignore` if not already present.
7. Returns a structured result: per-move success/failure, total bytes archived, paths written.

**Atomicity guarantees:**
- `os.rename()` is atomic within a filesystem. Cross-mount renames are refused, not faked.
- Manifest is append-only; a torn write leaves a malformed last line that readers skip with a warning.
- No SQLite in MVP. The manifest is the index. Phase 2 adds the SQLite index for query speed and reporting.

### 5.5 `.augur-lifecycle.yaml` schema (per-folder, optional)

```yaml
# Optional, lives at the root of any folder under Au-docs that wants to opt in or customize
enabled: true                                  # default true if file exists
pattern_hints:                                  # optional; agent uses these as classification hints
  - "guriqo-com-V*.zip"
  - "augur-run-V*.zip"
keep_latest: 1                                  # informational; agent uses
deploy_root: false                              # if true, /sweep-stores reports but never auto-applies
notes: "Free text the agent can read for context."
```

**No-config default:** folders without a `.augur-lifecycle.yaml` are still scannable when `/sweep-stores <path>` is explicitly invoked on them. The file's role is to (a) hint the agent on patterns and (b) flag `deploy_root` protection. Absence of the file is not a refusal.

### 5.6 `.milestones.json` schema (per-folder, optional)

```json
{
  "venture-augur/websites/guriqo-com-V10025.zip": {
    "tag": "intel-submission",
    "tagged_at": "2026-04-25T10:00:00Z",
    "note": "Sent to Intel, reference version"
  }
}
```

`hygiene-apply` refuses any move whose source matches a milestone-pinned path. Editing this file is manual in MVP; Phase 6 adds a `/milestone-tag` slash command.

## 6. AI-visibility hardening (MVP layer)

MVP ships exactly one exclusion mechanism, intentionally:

**Layer 1: `.augur-ignore` + `.gitignore`**
- `.augur-ignore` at every `.archive/` root, content: `*\n` (ignore everything in this directory).
- `.gitignore` at the store root gets one line appended on first archive: `.archive/`.
- These two together cover the existing Augur scanners that already honor `.augur-ignore` (browse, wiki, RAG, knowledge, ingest) and any git-aware tool.

**Out of scope for MVP** (deferred to Phase 4):
- `llms.txt` generation
- Obsidian `userIgnoreFilters` mutation
- MCP-boundary checks inside `vault-search` / `knowledge-*` / `wiki-*` / `unified-search`
- RAG denylist registration
- Three-probe post-archive verification (`vault-search` / `RAG` / `browse-index`)

**MVP verification is manual, by the user:**
After the first `--apply`, the user is expected to:
1. Open a fresh AI client session.
2. Ask the agent something like "list files in `venture-augur/websites/`."
3. Confirm the archived files do not appear.

If they do appear, the user files a bug; we then prioritize Phase 4 in a follow-up ADR. The MVP makes no claim that hiding is automatic or guaranteed — it claims that the most common AI scanners (the ones used by Augur internally) honor `.augur-ignore`, which is verifiable.

## 7. Safety, error handling, refusal rules (MVP)

**Hard refusals — `hygiene-apply` aborts the specific move, never proceeds:**

| Refusal | Trigger | Behavior |
|---|---|---|
| Never-touch hit | Source matches `.git/`, `.obsidian/`, `.pytest_cache/`, `.tmp.driveupload/`, `node_modules/`, `.venv/`, `__pycache__/`, lockfiles, `.augur-*` markers, or `.archive/` itself | Move refused, returned as `skipped` in result |
| Symlink | Source is a symlink | Refused; symlinks are never moved |
| Milestone-pinned | Source matches an entry in the folder's `.milestones.json` | Refused with explanation |
| Cross-filesystem | Source and destination on different mountpoints | Refused; preserves atomicity |
| Deploy-root | Folder's `.augur-lifecycle.yaml` has `deploy_root: true` | The slash command's rubric instructs the agent never to propose moves; if a move still arrives at `hygiene-apply`, it is refused |
| Source missing | Source does not exist at apply time | Refused; race with another writer |
| Destination collision unresolvable | Destination + `.dup-<hash>` also exists | Refused (vanishingly rare) |

**Atomicity:**
- One `os.rename()` per file. No copy+delete fallback across filesystems.
- Manifest append happens after a successful rename. If the manifest write throws, the rename is rolled back (`os.rename()` reverse) and the move is reported as failed.

**Dry-run is the default:**
- `/sweep-stores <path>` without `--apply` shows the proposal but calls `hygiene-apply` with `dry_run: true`, which validates the move list without performing any rename.
- `dry_run: true` returns the same result schema as a real apply, but every move is reported as `would_succeed` / `would_refuse`.

**Concurrency:**
- MVP makes no concurrency guarantee beyond "one user, one session." `hygiene-apply` does not take a lockfile. If the user runs `/sweep-stores --apply` twice in parallel, individual moves are still atomic but the apply runs do not coordinate. Phase 5 adds a lockfile when the auto-loop ships.

**Refusal observability:**
- Every refusal is included in the structured response with `{ reason: "...", refusal_category: "..." }`.
- The slash command's rubric instructs the agent to surface refusals to the user, not bury them.

**What we explicitly do NOT do in MVP:**
- No "best effort" fallback that leaves a partial state (rule 5).
- No silent skips (every skip is in the response).
- No undo command (recovery in MVP = `mv` from the filesystem).
- No audit log file (the per-folder `_manifest.jsonl` is the only record).

## 8. Testing strategy (MVP)

**Unit tests — `tests/test_hygiene_scan.py`, `tests/test_hygiene_apply.py`:**
- Never-touch globs match correctly
- Symlinks refused at scan and apply
- Cross-mount refused at apply (mocked via different temp roots flagged via `os.stat`'s `st_dev`)
- Milestone-pinned paths refused
- `.augur-lifecycle.yaml` parsing: valid, malformed, missing
- `.milestones.json` parsing: valid, malformed, missing
- Manifest is append-only and rollback-safe (simulate manifest-write failure → assert rename is reverted)
- Destination collision: `.dup-<hash>` suffix is applied correctly
- Coverage target: ≥ 90% on `hygiene_scan.py` and `hygiene_apply.py`

**Golden fixtures — `evals/fixtures/`:**

| Fixture | Tests |
|---|---|
| `fixture_websites_versioned/` | 48 zips matching a pattern; scan returns all; apply with explicit move list succeeds; `.augur-ignore` written; `.gitignore` appended |
| `fixture_logos_mixed/` | guriqo-logo.png + guriqo-logo.svg + augur-logo.png + augur-logo.svg; two artifact groups; agent's job, but scan + apply primitives must support the case |
| `fixture_format_variants/` | `augur-vision-1.pdf` + `augur-vision-1.pptx`; different format ≠ stale; rubric test (read the rubric in `references/sweep-rubric.md`, manually verify it instructs correctly) |
| `fixture_deploy_root/` | folder with `.augur-lifecycle.yaml: deploy_root: true`; apply refuses |
| `fixture_milestone_pinned/` | folder with `.milestones.json` entry; apply refuses that file |

**End-to-end test — `tests/test_hygiene_e2e.py`:**
- Spin up a temp directory mirroring `fixture_websites_versioned`
- Call `hygiene-scan`, assert output schema and contents
- Construct a move list (simulating what an agent would produce)
- Call `hygiene-apply` with `dry_run: true`, assert `would_succeed` for all
- Call `hygiene-apply` with `dry_run: false`, assert files moved, manifest written, `.augur-ignore` exists, `.gitignore` updated
- Assert no AI-scanner mock would re-find archived paths under standard `.augur-ignore` behavior (a small integration test against a mock scanner that respects `.augur-ignore`)
- Tear down

**No LLM eval in MVP.** The agent's classification quality is the agent's responsibility, not the skill's; we cannot meaningfully test it without making vendor-specific assumptions. The rubric is reviewed manually by the user during development, and golden fixtures exercise the deterministic plumbing.

**Quality gate before merge:**
- `/auto-test-pytest` green for the new test files
- Manual run of `/sweep-stores Au-docs/venture-augur/websites` (dry-run) in a real session, agent's proposal reviewed by user
- Manual run of `/sweep-stores Au-docs/venture-augur/websites --apply` on a copy of the folder, archived files confirmed invisible to a follow-up agent session (the MVP-verification ritual from §6)

## 9. Out of scope / explicit non-goals (MVP)

- Auto-loops (nightly scan, weekly purge): Phase 5 / Phase 2.
- Dashboard surface: Phase 6.
- Au-vault scope: Phase 3.
- Multi-layer exclusions (llms.txt, MCP boundaries, RAG denylist, Obsidian filters): Phase 4.
- Verification probes / revert-on-failure: Phase 4.
- LLM-driven classification when no agent session exists: Phase 5b.
- Milestone-tag CRUD slash command: Phase 6 (MVP edits `.milestones.json` manually).
- Undo / restore command: Phase 6 (MVP uses filesystem `mv`).
- SQLite index: Phase 2.
- Per-month archive partitioning: Phase 2 (defer until auto-purge ships).
- Auto-purge (90-day retention): Phase 2.
- Audit log under `get_logs_dir()`: Phase 6.
- Capability policy table addition to `CLAUDE.md`: deferred until tools surface in dashboard (Phase 6).

## 10. Open questions

None at spec-write time. The MVP scope is tight; questions that come up during plan-writing will be answered in plan PRs or in follow-up ADRs.

## 11. References

- `CLAUDE.md` rules 1, 5, 11, 12, 13, 14, 19, 27, 28
- `src/config/paths.py` — `get_documents_dir()`
- `shared-vault/skills/loop-memory/SKILL.md` — auto-loop skill template
- `config/system/llm.yaml` — vendor abstraction (NOT used in MVP; referenced for Phase 5b)
- ADR-491 — config-driven dashboard pages (referenced for Phase 6)
- ADR-571 — vault frontmatter conventions
- ADR-731 — memory synthesis consolidation (parallel autoloop architecture)
- Memory: `feedback_vendor_neutral_design.md`, `feedback_design_only_no_shortcuts.md`, `feedback_cross_agent_enforcement.md`, `project_enforcement_layers.md`, `project_loop_engine_quirks.md`
