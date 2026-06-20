# Vault File Audit — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Audit every file in `~/Projects/Au-vault` (1,182 files, 41 directories) across 5 dimensions — connectivity, classification, consolidation, format, leftovers — and execute cleanup autonomously via parallel agents.

**Architecture:** Two-phase approach. Phase 0: single agent builds a connectivity map (which vault dirs are read by MCP tools called from dashboard pages). Phase 1: 8 parallel agents each handle a batch of directories, running a per-file decision tree and committing per directory.

**Tech Stack:** Bash (grep, find), Python (`src/lib/frontmatter_utils`), Git, Agent tool with worktree isolation.

**Spec:** `docs/superpowers/specs/2026-04-03-vault-file-audit-design.md`

---

## Shared Constants

```
VAULT_DIR = ~/Projects/Au-vault
RUNTIME_DIR = ~/Library/Application Support/Augur/state
PROJECT_ROOT = ~/Projects/Augur
REPORT_DIR = /tmp/vault-cleanup
CONNECTIVITY_MAP = /tmp/vault-cleanup/connectivity-map.json
```

---

## Task 0: Setup working directories

**Files:**
- Create: `/tmp/vault-cleanup/` (working dir)
- Create: `/tmp/vault-cleanup/reports/` (agent reports)

- [ ] **Step 1: Create working directories**

```bash
mkdir -p /tmp/vault-cleanup/reports
```

- [ ] **Step 2: Snapshot current vault state**

```bash
find ~/Projects/Au-vault -type f \
  -not -path '*/.git/*' \
  -not -path '*/.obsidian/*' \
  | wc -l > /tmp/vault-cleanup/file-count-before.txt

echo "Files before cleanup: $(cat /tmp/vault-cleanup/file-count-before.txt)"
```

- [ ] **Step 3: Commit** — no commit needed (temp files only)

---

## Task 1: Build Connectivity Map (Phase 0 — single agent)

**Purpose:** Discover which vault directories are "connected" — meaning an MCP tool reads from them AND a dashboard page calls that tool. Output a JSON map used by all Phase 1 agents.

**Files:**
- Read: `scripts/mcp/**/*.py`, `skills/*/scripts/mcp/**/*.py` (MCP tool definitions)
- Read: `apps/dashboard/**/*.tsx`, `apps/dashboard/**/*.ts` (dashboard tool calls)
- Create: `/tmp/vault-cleanup/connectivity-map.json`

- [ ] **Step 1: Find all MCP tool files that reference vault paths**

Search all Python MCP tool files for vault path references:

```bash
grep -rn \
  "get_vault_dir\|vault_dir\|Au-vault\|get_memory_dir\|get_skill_vault_dir\|get_skill_data_dir\|get_documents_dir" \
  --include="*.py" \
  ~/Projects/Augur/scripts/mcp/ \
  ~/Projects/Augur/skills/*/scripts/mcp/ \
  ~/Projects/Augur/skills/*/scripts/*.py \
  2>/dev/null | grep -v __pycache__
```

For each file found, extract the `@mcp.tool(name=...)` decorators:

```bash
grep -n "@mcp.tool" <file>
```

- [ ] **Step 2: Map each tool to the vault subdirectory it reads**

For each vault-touching tool, determine which subdirectory it accesses. Look for patterns:
- `vault_dir / "subdir"` — direct path construction
- `get_memory_dir()` — resolves to `vault/memory/`
- `get_skill_vault_dir(skill)` — resolves to `vault/{skill}/`
- `get_skill_data_dir(skill)` — resolves to `vault/{skill}/` (alias)

Build a mapping: `{ tool_name: [vault_subdirs_it_reads] }`

- [ ] **Step 3: Check which tools are called from dashboard pages**

For each vault-touching tool name, grep the dashboard for references:

```bash
grep -rn '"tool-name-here"' \
  --include="*.tsx" --include="*.ts" \
  ~/Projects/Augur/apps/dashboard/ \
  2>/dev/null | grep -v node_modules | grep -v .next
```

Look for patterns: `useMcpQuery(*, "tool-name"`, `useMcpMutation(*, "tool-name"`, `useMcpPoll(*, "tool-name"`, `toolName: "tool-name"`, `mcpCall("tool-name"`.

- [ ] **Step 4: Write the connectivity map JSON**

Produce `/tmp/vault-cleanup/connectivity-map.json` with this structure:

```json
{
  "directories": {
    "dev/adrs": {
      "tools": ["get-long-term-decisions"],
      "pages": ["apps/dashboard/app/(views)/browse/..."],
      "status": "connected"
    },
    "memory/entries": {
      "tools": ["reflect-context"],
      "pages": ["apps/dashboard/features/components/chat/ContextButton.tsx"],
      "status": "connected"
    },
    "career": {
      "tools": [],
      "pages": [],
      "status": "disconnected"
    }
  },
  "summary": {
    "total_dirs": 41,
    "connected": 0,
    "disconnected": 0
  }
}
```

Rules:
- A directory is `connected` only if at least one tool reads it AND that tool appears in at least one dashboard file.
- Subdirectories inherit parent status unless they have their own tool reference.
- If a tool reads the entire vault (like RAG search), that does NOT make every directory connected — RAG search is a generic index, not a dedicated reader. Only tools that construct specific `vault_dir / "subdir"` paths count.

- [ ] **Step 5: Verify the map**

Print summary: how many dirs connected vs disconnected. Sanity-check that known-connected dirs (like `dev/adrs`, `memory/entries`) show as connected, and known-operational dirs (like `daemon`, `channels`) show as disconnected.

---

## Task 2: Agent A1 — dev/ (476 files)

**Directories:** `dev/adrs/`, `dev/specs/`, `dev/plans/`
**Disposal rules:** Keep all (governance + design history). Format-fix and tag disconnected only.

**Agent prompt (dispatch with worktree isolation):**

> You are cleaning up vault files in `~/Projects/Au-vault/dev/`. Read `/tmp/vault-cleanup/connectivity-map.json` for connectivity status.
>
> For every `.md` file in `dev/adrs/`, `dev/specs/`, `dev/plans/` and any other `dev/` subdirs:
>
> 1. **Read** the file (first 100 lines)
> 2. **Classify**: runtime (has AUTO-GENERATED, seeded by, synced from markers) vs user-authored. Default to user.
> 3. **Connectivity**: look up `dev/{subdir}` in the connectivity map. If disconnected, add `x-status: disconnected` to frontmatter (for non-ADR files — ADRs always keep as-is).
> 4. **Duplicate check**: within each subdirectory, compare files. If two files have >90% identical body lines (strip frontmatter), delete the smaller/older one.
> 5. **Small file check**: files under 100 lines with same-topic siblings (similar filename prefix or frontmatter tags) — consolidate into `{subdir}-consolidated.md`, preserving each entry as a section. Delete originals.
> 6. **Format check (ADR-404)**: must have YAML frontmatter (`---` delimiters). If missing, add minimal frontmatter `{ title: <filename stem>, date: <git log date or today> }`. If broken YAML, fix it.
> 7. **Runtime files**: if classified as runtime, move to `~/Library/Application Support/Augur/state/dev/{relative-path}`. Create parent dirs.
>
> After processing each top-level subdir (`adrs/`, `specs/`, `plans/`, etc.), commit:
> ```
> vault-cleanup(dev/{subdir}): {summary}
> Deleted: N | Consolidated: N | Format-fixed: N | Tagged: N | Moved-to-runtime: N
> ```
>
> Write a report to `/tmp/vault-cleanup/reports/a1-dev.md` as a markdown table:
> | File | Classification | Connectivity | Action | Reason |
>
> Do NOT delete ADR files regardless of any other signal. ADRs are governance docs.

- [ ] **Step 1: Dispatch agent A1 with the prompt above**
- [ ] **Step 2: Verify commits exist in the Au-vault repo after agent completes**

---

## Task 3: Agent A2 — memory/ (208 files)

**Directories:** `memory/daily/`, `memory/entries/`, `memory/system/`
**Disposal rules:** Consolidate small files, delete duplicates only. Never delete unique user content.

**Agent prompt:**

> You are cleaning up vault files in `~/Projects/Au-vault/memory/`. Read `/tmp/vault-cleanup/connectivity-map.json` for connectivity status.
>
> For every file in `memory/daily/`, `memory/entries/`, `memory/system/`:
>
> 1. **Read** the file
> 2. **Classify**: runtime vs user. Daily logs with only auto-generated content → runtime. Entries with user preferences/feedback → user.
> 3. **Connectivity**: look up in map. Connected entries stay. Disconnected entries: consolidate if small, keep if unique.
> 4. **Duplicate check**: compare within each subdirectory. Memory entries are especially prone to duplicates between `entries/` and `system/`. If two files have >90% body overlap, keep the one in `entries/` (user-facing), delete the `system/` copy.
> 5. **Small file consolidation**: daily logs under 100 lines — consolidate by month into `daily/YYYY-MM-consolidated.md`. Each original becomes a `## YYYY-MM-DD` section. Delete originals. Memory entries under 100 lines with similar prefixes (e.g., `preference_*.md`) — consolidate into `entries/preferences-consolidated.md`, etc.
> 6. **Format check**: ensure frontmatter per ADR-404.
> 7. **Runtime**: auto-generated daily summaries with no user edits → move to runtime dir.
>
> Commit per subdirectory. Write report to `/tmp/vault-cleanup/reports/a2-memory.md`.

- [ ] **Step 1: Dispatch agent A2**
- [ ] **Step 2: Verify commits**

---

## Task 4: Agent A3 — career/ (95 files)

**Directories:** `career/career-profile/`, `career/interview-prep/`, `career/job-analyzer/`, `career/learning/`, `career/notes/`, `career/reports/`
**Disposal rules:** All user-curated. Keep everything. Delete duplicates/redundant only. Never delete job or company data.

**Agent prompt:**

> You are cleaning up vault files in `~/Projects/Au-vault/career/`. Read `/tmp/vault-cleanup/connectivity-map.json`.
>
> For every file in all `career/` subdirectories:
>
> 1. **Read** the file
> 2. **Classify**: all career files default to user-authored.
> 3. **Connectivity**: look up in map. Tag disconnected files with `x-status: disconnected` in frontmatter.
> 4. **Duplicate check**: within each subdir, check for near-duplicate content. Career reports and job analyses may have versioned copies — keep the most recent, delete older duplicates only if content is >90% identical.
> 5. **Small file consolidation**: notes under 100 lines on the same topic — consolidate into `{subdir}-consolidated.md`. Keep interview prep and job analyses as individual files regardless of size.
> 6. **Format check**: ensure frontmatter per ADR-404.
> 7. **Runtime**: career files are never runtime. Skip.
>
> IMPORTANT: Never delete job listings, company profiles, interview prep, or learning notes. These are all user-curated. Only delete provably duplicate files.
>
> Commit per subdirectory. Write report to `/tmp/vault-cleanup/reports/a3-career.md`.

- [ ] **Step 1: Dispatch agent A3**
- [ ] **Step 2: Verify commits**

---

## Task 5: Agent A4 — venture-augur/, linkedin-writer/, content/ (84 files)

**Directories:** `venture-augur/**`, `linkedin-writer/**`, `content/**`
**Disposal rules:** All user-authored. Keep everything. Format-fix and tag only.

**Agent prompt:**

> You are cleaning up vault files in `~/Projects/Au-vault/venture-augur/`, `~/Projects/Au-vault/linkedin-writer/`, and `~/Projects/Au-vault/content/`. Read `/tmp/vault-cleanup/connectivity-map.json`.
>
> For every file:
>
> 1. **Read** the file
> 2. **Classify**: all user-authored (business docs, prepared posts, strategies).
> 3. **Connectivity**: look up in map. Tag disconnected with `x-status: disconnected`.
> 4. **Duplicate check**: within each top-level dir. Delete only if >90% body overlap.
> 5. **Small file consolidation**: venture-augur has many subdirs (brand, competition, financials, etc.) — consolidate small files within each subdir into `{subdir}-consolidated.md`. linkedin-writer posts stay individual regardless of size. content/ strategies stay individual.
> 6. **Format check**: ensure frontmatter per ADR-404.
> 7. **Runtime**: none. These are never runtime files.
>
> IMPORTANT: linkedin-writer files are user-prepared posts. Never delete them.
>
> Commit per top-level directory (3 commits). Write report to `/tmp/vault-cleanup/reports/a4-business.md`.

- [ ] **Step 1: Dispatch agent A4**
- [ ] **Step 2: Verify commits**

---

## Task 6: Agent A5 — scraper/, validator/, devops/, advisor/ (88 files)

**Directories:** `scraper/` (32), `validator/` (15), `devops/` (22), `advisor/` (19)
**Disposal rules:** Mixed. Check if matching skill exists in `skills/`. Connected → keep. Disconnected operational data → delete. Disconnected user content → tag.

**Agent prompt:**

> You are cleaning up vault files in `~/Projects/Au-vault/scraper/`, `validator/`, `devops/`, `advisor/`. Read `/tmp/vault-cleanup/connectivity-map.json`.
>
> Pre-check: verify each skill exists by checking `ls ~/Projects/Augur/skills/{name}/`. If skill exists, its data is potentially active. If skill is deleted, all its vault data is orphaned.
>
> For every file:
>
> 1. **Read** the file
> 2. **Classify**: scraper content/ is often auto-fetched HTML-to-markdown → runtime candidate. Validator reviews/checklists may be auto-generated. Devops reports/incidents may be auto-generated. Advisor analytics may be auto-generated. Check for AUTO-GENERATED markers, timestamps-only content, or template boilerplate.
> 3. **Connectivity**: look up in map.
> 4. **Duplicate check**: within each dir.
> 5. **Small file consolidation**: devops reports, validator checklists — consolidate small ones by type.
> 6. **Format check**: ADR-404.
> 7. **Runtime**: auto-generated scraper content, validator test captures, devops deployment logs → move to runtime dir. User-written notes/analyses → keep in vault.
>
> Commit per top-level directory (4 commits). Write report to `/tmp/vault-cleanup/reports/a5-tools.md`.

- [ ] **Step 1: Dispatch agent A5**
- [ ] **Step 2: Verify commits**

---

## Task 7: Agent A6 — apple/, books/, growth/, ai/ (126 files)

**Directories:** `apple/` (27), `books/` (17), `growth/` (29), `ai/` (35)
**Disposal rules:** Mostly user content. Apple sync files may be runtime. AI agent workflow logs may be runtime.

**Agent prompt:**

> You are cleaning up vault files in `~/Projects/Au-vault/apple/`, `books/`, `growth/`, `ai/`. Read `/tmp/vault-cleanup/connectivity-map.json`.
>
> Pre-check: verify each skill exists via `ls ~/Projects/Augur/skills/{name}/`.
>
> For every file:
>
> 1. **Read** the file
> 2. **Classify**: `notes/lifestyle/apple/notes-sync/` files are sync artifacts → runtime. `notes/lifestyle/apple/notes/` and `notes/lifestyle/apple/reminders/` are user data → keep. books/notes/ are user reading notes → keep. `notes/career/growth/` files are user notes → keep. ai/ agent workflow files and cowork logs may be auto-generated → check for markers.
> 3. **Connectivity**: look up in map.
> 4. **Duplicate check**: within each dir.
> 5. **Small file consolidation**: growth notes, ai workflow docs — consolidate small related files.
> 6. **Format check**: ADR-404.
> 7. **Runtime**: apple sync files, ai auto-generated logs → move to runtime. User notes → keep.
>
> Commit per top-level directory (4 commits). Write report to `/tmp/vault-cleanup/reports/a6-personal.md`.

- [ ] **Step 1: Dispatch agent A6**
- [ ] **Step 2: Verify commits**

---

## Task 8: Agent A7 — lifestyle/, health/, finance/, small life dirs (85 files)

**Directories:** `lifestyle/` (32), `health/` (20), `finance/` (11), `home-automation/` (1), `wearables/` (1), `wealth/` (1)
**Disposal rules:** User content. Keep all. Format-fix and tag disconnected.

**Agent prompt:**

> You are cleaning up vault files in `~/Projects/Au-vault/lifestyle/`, `health/`, `finance/`, `home-automation/`, `wearables/`, `wealth/`. Read `/tmp/vault-cleanup/connectivity-map.json`.
>
> Pre-check: verify each skill exists via `ls ~/Projects/Augur/skills/{name}/`.
>
> For every file:
>
> 1. **Read** the file
> 2. **Classify**: all user-authored (personal life, health, finance content). Default to user.
> 3. **Connectivity**: look up in map. Tag disconnected with `x-status: disconnected`.
> 4. **Duplicate check**: within each dir.
> 5. **Small file consolidation**: lifestyle/ideas/ and lifestyle/notes/ — consolidate small files. health/virtual-doctor/ — consolidate small consultation notes. finance/ideas/ and finance/knowledge/ — consolidate. Single-file dirs (home-automation, wearables, wealth) — leave as-is.
> 6. **Format check**: ADR-404.
> 7. **Runtime**: none expected for personal content.
>
> Commit per top-level directory. Write report to `/tmp/vault-cleanup/reports/a7-life.md`.

- [ ] **Step 1: Dispatch agent A7**
- [ ] **Step 2: Verify commits**

---

## Task 9: Agent A8 — remaining small directories (~52 files)

**Directories:** `Augur/` (7), `channels/` (1), `commands/` (1), `config/` (1), `consulting-template/` (2), `dashboard/` (1), `daemon/` (7), `developer/` (2), `document-extractor/` (1), `eisenhower/` (4), `enterprise/` (1), `file-manager/` (1), `google-workspace/` (1), `knowledge/` (8), `metrics/` (1), `remote-access/` (1), `system-cleanup/` (1), `terminal-automation-template/` (1), `updater/` (2), `attention/` (10)
**Disposal rules:** Per-directory rules from design spec. Channels, attention, daemon → delete (operational). Others → check skill existence.

**Agent prompt:**

> You are cleaning up the remaining small directories in `~/Projects/Au-vault/`. Read `/tmp/vault-cleanup/connectivity-map.json`.
>
> **Directories and rules:**
>
> DELETE (operational state — belongs in runtime, not vault):
> - `channels/` — notification channel config, operational
> - `attention/` — pending items and history, operational
> - `daemon/` — inbox, insights, notifications — all operational
>
> CHECK SKILL EXISTS (delete orphaned, keep active):
> - `Augur/`, `commands/`, `config/`, `consulting-template/`, `dashboard/`, `developer/`, `document-extractor/`, `eisenhower/`, `enterprise/`, `file-manager/`, `google-workspace/`, `knowledge/`, `metrics/`, `remote-access/`, `system-cleanup/`, `terminal-automation-template/`, `updater/`, `wearables/` (wait — wearables is in A7)
>
> For each directory, run `ls ~/Projects/Augur/skills/{dirname}/` to check if the skill exists. If skill deleted → delete vault dir. If skill active → run normal 5-dimension audit.
>
> For all files that survive the above filters:
> 1. Read, classify, connectivity check, duplicate check, format check — standard decision tree.
> 2. Small files in dirs with <5 files — leave individual (not enough to consolidate).
> 3. Operational files (attention pending, daemon inbox) → move to runtime before deleting from vault.
>
> Commit per top-level directory. Write report to `/tmp/vault-cleanup/reports/a8-small.md`.

- [ ] **Step 1: Dispatch agent A8**
- [ ] **Step 2: Verify commits**

---

## Task 10: Merge Reports and Summarize

**Files:**
- Read: `/tmp/vault-cleanup/reports/a1-dev.md` through `a8-small.md`
- Create: `docs/generated/vault-cleanup-report.md`

- [ ] **Step 1: Count files after cleanup**

```bash
find ~/Projects/Au-vault -type f \
  -not -path '*/.git/*' \
  -not -path '*/.obsidian/*' \
  | wc -l > /tmp/vault-cleanup/file-count-after.txt
```

- [ ] **Step 2: Merge all agent reports**

Concatenate all `/tmp/vault-cleanup/reports/a*.md` files into a single report:

```bash
cat /tmp/vault-cleanup/reports/a*.md > /tmp/vault-cleanup/merged-report.md
```

- [ ] **Step 3: Write final report**

Create `docs/generated/vault-cleanup-report.md` with:

```markdown
# Vault File Audit Report

**Date:** 2026-04-03
**Files before:** {from file-count-before.txt}
**Files after:** {from file-count-after.txt}
**Net change:** -{difference}

## Summary by Action

| Action | Count |
|--------|-------|
| Kept (no change) | N |
| Format fixed | N |
| Tagged disconnected | N |
| Consolidated | N |
| Moved to runtime | N |
| Deleted (duplicate) | N |
| Deleted (operational) | N |
| Deleted (orphaned skill) | N |

## Per-Directory Reports

{merged agent reports}
```

- [ ] **Step 4: Commit the report**

```bash
cd ~/Projects/Augur
git add docs/generated/vault-cleanup-report.md
git commit -m "docs: vault file audit report — post-cleanup summary"
```

---

## Execution Notes

**Parallelism:** Tasks 2-9 (agents A1-A8) are fully independent and MUST be dispatched in parallel after Task 1 completes. Task 10 depends on all of Tasks 2-9.

**No worktree needed:** Each agent in Tasks 2-9 operates on `~/Projects/Au-vault` (the vault repo), NOT the main Augur project repo. Agents read from the Augur project (MCP tool files, dashboard code) but write only to the vault. Since writes go to a different repo than reads, worktree isolation of the Augur project is unnecessary. However, agents MUST NOT run in parallel on the same vault directory — the batching ensures each directory is owned by exactly one agent.

**Rollback:** Each directory is its own git commit in the vault repo. `git revert <hash>` undoes one directory. The vault has its own git history.

**Error handling:** If an agent encounters a file it cannot classify, it should default to `user` classification and `keep` action — never delete ambiguous files.
