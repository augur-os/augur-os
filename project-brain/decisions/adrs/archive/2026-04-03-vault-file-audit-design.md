# Vault File Audit — Parallel Agent Cleanup

**Date:** 2026-04-03
**Status:** Approved
**Predecessor:** ADR-514 (Vault Cleanup — Phased Reduction from 3,371 to 1,600 Files)

## Context

ADR-514 reduced the vault from 3,371 to ~1,182 content files. This second pass is a deeper 5-dimension audit of every surviving file, executed by parallel agents.

**Vault:** `~/Projects/Au-vault` (1,182 files, 43 directories, 87% markdown)

## Goals (priority order)

1. **Connectivity audit** — is each file actually fetched by an MCP tool that a dashboard page calls, or orphaned?
2. **Classification** — runtime/generated vs user-created — determines where files should live
3. **Small file consolidation** — merge files <100 lines into unified list files to reduce friction
4. **Format correctness** — frontmatter structure per ADR-404
5. **Delete leftovers** — anything that survived ADR-514 but shouldn't have

## Design

### Phase 0: Connectivity Map (single agent)

One agent builds a JSON map of which vault directories are "live":

1. Grep all `@mcp.tool(name=...)` in `scripts/mcp/` and `skills/*/scripts/` for vault path references (`get_vault_dir()`, `vault_dir`, literal `Au-vault`)
2. For each vault-touching tool, extract: tool name, vault subdirectory it reads, read-only vs read-write
3. Grep `apps/dashboard/` for `useMcpQuery`/`useMcpMutation`/`useMcpPoll` calls referencing each tool
4. Output JSON map:

```json
{
  "attention": { "tools": ["get-attention-items"], "pages": ["adaptive/attention"], "status": "connected" },
  "career/interviews": { "tools": [], "pages": [], "status": "disconnected" }
}
```

Any directory not referenced by any tool = `disconnected`.

### Directory-Specific Disposal Rules

For disconnected files, each directory type gets a default action:

| Directory Pattern | Disconnected Action | Rationale |
|---|---|---|
| `dev/adrs/` | **Keep** | Governance docs |
| `dev/specs/`, `dev/plans/` | **Keep** | Design history |
| `dev/*` (other) | **Tag** `x-status: disconnected` | Mixed, needs manual review |
| `memory/entries/`, `memory/system/` | **Consolidate** small, **delete** duplicates only | No unique content loss |
| `career/jobs/`, `career/companies/` | **Keep**, **delete** duplicates/redundant only | User-curated data |
| `career/interviews/`, `career/prep/` | **Keep** | User-written |
| `venture-augur/` | **Keep** | Business docs |
| `linkedin-writer/` | **Keep** | User-prepared posts |
| `channels/`, `attention/`, `daemon/` | **Delete** | Operational state, belongs in runtime |
| Skill data dirs (matches active skill) | **Keep** | Skill exists |
| Skill data dirs (no matching skill) | **Delete** | Orphaned skill data |
| Everything else | **Tag** `x-status: disconnected` | Safe default |

**Principle:** When in doubt, a vault file is user data. Only delete when content is clearly operational/runtime state, or provably duplicate/redundant. Career data and linkedin posts are always user-curated regardless of connectivity.

### Phase 1: Parallel Agents (8 agents)

| Agent | Directories | ~Files | Rationale |
|---|---|---|---|
| **A1** | `dev/adrs/`, `dev/specs/`, `dev/plans/` | ~300 | Largest dir, all reference docs — same keep logic |
| **A2** | `dev/*` (remaining subdirs) | ~176 | Rest of dev — tag-disconnected logic |
| **A3** | `memory/` | ~208 | Self-contained, consolidation-heavy |
| **A4** | `career/` | ~95 | User data, duplicate detection needed |
| **A5** | `venture-augur/`, `linkedin-writer/`, `content/` | ~90 | User-authored business/social content |
| **A6** | `channels/`, `attention/`, `daemon/` | ~80 | Operational dirs — mostly delete/move-to-runtime |
| **A7** | `finance/`, `health/`, `lifestyle/`, `home-automation/` | ~60 | Life hub skill data dirs |
| **A8** | All remaining small dirs (~20 dirs) | ~173 | Long tail, most <10 files each |

Each agent runs in a **worktree** for isolation. Commits per top-level directory within its batch.

### Per-File Decision Tree

```
For each file:
│
├─ 1. READ file (first 100 lines + metadata)
│
├─ 2. CLASSIFY source
│   ├─ Has generator marker (AUTO-GENERATED, seeded by, synced from)? → RUNTIME
│   ├─ Has user-authored signals (prose, personal pronouns, opinions)? → USER
│   └─ Ambiguous? → USER (safe default)
│
├─ 3. CHECK connectivity (lookup in Phase 0 map)
│   ├─ Connected → proceed to format check
│   └─ Disconnected → apply directory disposal rule
│       ├─ Rule says KEEP → proceed to format check
│       ├─ Rule says DELETE → delete file
│       ├─ Rule says TAG → add x-status: disconnected to frontmatter
│       └─ Rule says CONSOLIDATE → mark for small-file pass
│
├─ 4. DUPLICATE check (within same directory)
│   ├─ Hash content body (strip frontmatter)
│   ├─ >90% similarity to another file in same dir? → delete the smaller/older one
│   └─ Unique → continue
│
├─ 5. SMALL FILE check (< 100 lines)
│   ├─ Marked for consolidation OR same-topic siblings exist?
│   │   → Append to unified list file ({directory}-consolidated.md)
│   │   → Delete original
│   └─ Standalone small file with unique topic → keep as-is
│
├─ 6. FORMAT check (ADR-404)
│   ├─ Missing YAML frontmatter? → add minimal frontmatter
│   ├─ Pure YAML that should be markdown+frontmatter? → convert
│   ├─ Broken frontmatter (unclosed ---, bad YAML)? → fix
│   └─ Correct? → no-op
│
└─ 7. RUNTIME classification
    ├─ File classified as RUNTIME in step 2?
    │   → Move to get_runtime_dir()/{original-relative-path}
    │   → Log the move
    └─ Not runtime → done
```

Order matters: Classification before connectivity, connectivity before consolidation, format fix last (only fix files we're keeping).

Duplicate detection: Content similarity is body-only (frontmatter stripped). Simple line-count ratio + shared-line percentage. Only compares within same directory.

### Commit Strategy

Each agent commits per top-level directory:

```
vault-cleanup({dir}): {summary}

Deleted: {n} files (runtime: {n}, duplicates: {n}, leftovers: {n})
Moved to runtime: {n} files
Consolidated: {n} small files → {n} list files
Format fixed: {n} files
Tagged disconnected: {n} files
```

### Output

Each agent produces a per-directory report (markdown table):

| File | Classification | Connectivity | Action | Reason |
|---|---|---|---|---|
| `career/jobs/acme.md` | user | disconnected | keep | user-curated career data |
| `attention/pending/old-123.md` | runtime | disconnected | deleted | operational state |

After all agents complete:
- Merge reports into `docs/generated/vault-cleanup-report.md`
- Print summary stats (total files before/after, breakdown by action)
- Each directory is its own commit — `git revert <hash>` undoes one directory without touching others

## Constraints

- Vault path: `~/Projects/Au-vault`
- Runtime path: resolved via `get_runtime_dir()` from `src/config/paths.py`
- Strict connectivity: file must be fetched by a specific MCP tool that a dashboard page calls
- User-authored content defaults to keep. Only delete operational/runtime state or provable duplicates
- Career data and linkedin posts are always user-curated regardless of connectivity
