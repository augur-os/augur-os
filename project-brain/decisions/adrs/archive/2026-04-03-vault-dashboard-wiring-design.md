# Vault Dashboard Wiring — Design Spec

**Date:** 2026-04-03
**Status:** Approved
**Predecessor:** Vault File Audit (2026-04-03, 1,182 → 936 files)

## Context

The vault audit revealed 31 skill directories are only connected to the dashboard through the generic auto-page (`list-skill-vault-notes` returning a flat list of 20 files with 200-char previews). Only 5 directories have dedicated MCP tool wiring.

This design upgrades the auto-page for all skills and adds custom pages for the 5 highest-value skills.

## Scope

1. **Auto-page upgrade** — enhanced `list-skill-vault-notes` + improved `VaultNotesBlock` (benefits all skills)
2. **Career TSX pages** (2) — pipeline tracker + profile hub
3. **Venture-augur TSX page** (1) — content workspace
4. **Growth TSX pages** (2) — learning dashboard + knowledge browser
5. **LinkedIn-writer YAML page** (1) — post-focused layout
6. **Lifestyle YAML page** (1) — idea/recipe/notes layout
7. **Generic vault MCP tools** (2) — `vault-file-read` + `vault-file-write`

Reference: deleted pages from git commit `fd4113260` ("restore clean baseline — revert broken YAML conversions") provide layout and tool patterns.

## 1. Auto-page Upgrade

### MCP Tool: `list-skill-vault-notes` Enhancement

**File:** `src/mcp/augur_mcp/core/skills.py` (existing function, modify)

Changes from current behavior:

| Property | Current | Upgraded |
|----------|---------|----------|
| File limit | 20 | 50 |
| Directory depth | 2 levels | 3 levels |
| Preview length | 200 chars | 500 chars |
| Grouping | Flat list | Grouped by subdirectory |
| Type info | None | Frontmatter `type` field extracted |
| File size | None | Line count included |

New response shape:

```json
{
  "notes": [
    { "name": "file.md", "modified": "...", "preview": "..." }
  ],
  "groups": [
    {
      "directory": "interview-prep",
      "count": 5,
      "files": [
        { "name": "google-prep.md", "type": "interview", "modified": "...", "lines": 85, "preview": "..." }
      ]
    },
    {
      "directory": ".",
      "count": 2,
      "files": [...]
    }
  ],
  "stats": { "total_files": 55, "total_dirs": 6 }
}
```

Backwards compatible: `notes[]` flat array still returned for existing consumers. New `groups[]` and `stats` fields are additive.

### Dashboard Component: `VaultNotesBlock` Enhancement

**File:** `apps/dashboard/components/blocks/types/VaultNotesBlock.tsx` (existing, modify)

New features:
- Collapsible directory sections with file count badges
- File icons based on `type` field (post, config, note, interview, etc.)
- Sort toggle: by date (default) or by directory
- Line count shown as subtle metadata
- Search filters across all groups

New config props:
- `directory_filter: string` — comma-separated list of subdirs to show (for YAML pages)
- `collapsed: boolean` — start collapsed (default false)
- `sort: "modified_desc" | "directory"` — default sort order

## 2. Career TSX Pages

### Page 1: Pipeline Tracker

**Route:** `/career/pipeline`
**File:** `skills/career/augur/dashboard/pipeline.tsx`

Components:
- **Stat bar**: job counts by status (inbox, active, offer, rejected, archive) via `get-career-job-counts` MCP tool
- **Data table**: columns (title, company, status, match score, date added), pill filters for status, search on title + company, row actions (analyze, update status)
- **Action bar**: analyze-job, sync-jobs, calculate-match-scores

MCP tools: `get-career-job-counts` (verify in git, rebuild if missing), `add-career-job` (verify), `list-skill-vault-notes` (enhanced).

Reference: old `skills/career/augur/pages/pipeline.yaml` from commit `fd4113260^`.

### Page 2: Profile Hub

**Route:** `/career/profile`
**File:** `skills/career/augur/dashboard/profile.tsx`

Components:
- **Profile summary card** at top: from career-profile/candidate.md frontmatter (name, target roles, salary)
- **Tab navigation** across vault subdirs: interview-prep, job-analyzer, learning, notes, reports
- Each tab renders files as cards: CVs as titled cards with expand, notes as expandable list, learning grouped by topic

MCP tools: `list-skill-vault-notes` (enhanced, with subdir filtering), `vault-file-read` (new generic tool, for full CV display).

## 3. Venture-augur Content Workspace

**Route:** `/career/venture-augur/content`
**File:** `skills/venture-augur/augur/dashboard/content.tsx`

Components:
- **Sidebar navigation** by vault subdirs: brand, competition, content, financials, gtm, ideas, marketing, notes, outreach, overview, planning, sales, strategy
- **Main area**: selected subdir's files as markdown preview cards (title, 500 chars, last modified). Click to expand full content in reading pane.
- **Quick stats bar**: total docs, last updated, docs per category
- **Search** across all vault content
- **Action buttons**: "New doc" (creates vault file via `vault-file-write`), "Refresh"

MCP tools: `list-skill-vault-notes` (enhanced), `vault-file-read` (new), `vault-file-write` (new).

Reference: old overview.yaml from commit `fd4113260^` for layout patterns.

## 4. Growth TSX Pages

### Page 1: Learning Dashboard

**Route:** `/brain/growth/dashboard`
**File:** `skills/growth/augur/dashboard/dashboard.tsx`

Components:
- **Progress cards**: courses in progress, active habits, knowledge areas — styled cards with color variants per category
- **Guided prompts**: "Growth check-in", "Add habit", "Review knowledge", "Harden skills" — each dispatches IDE action
- **Recent activity feed**: last 10 modified files from growth/ vault, grouped by type
- **Cheat sheets quick-access**: links to reference docs in `notes/career/growth/`

MCP tools: `list-skill-vault-notes` (enhanced), `vault-file-read`, check git for `career-learning`, `career-habits`, `career-knowledge` tools.

Reference: old `skills/growth/augur/dashboard/page.tsx` (293 lines, glass cards pattern) from commit `cb36b5dc1^`.

### Page 2: Knowledge Browser

**Route:** `/brain/growth/knowledge`
**File:** `skills/growth/augur/dashboard/knowledge.tsx`

Components:
- **Topic grouping**: files organized by frontmatter `topic`/`category`, fallback to subdirectory grouping
- **Expandable notes**: click to read full content inline via `vault-file-read`
- **Spaced repetition prompts**: files with `review_date` frontmatter surface "due for review" badge, click dispatches review action to IDE
- **Search + filter**: by topic, date range, review status

MCP tools: `list-skill-vault-notes` (enhanced), `vault-file-read`.

## 5. LinkedIn-writer YAML Page

**Route:** `/career/linkedin-writer`
**File:** `skills/linkedin-writer/augur/pages/overview.yaml`

```yaml
title: LinkedIn Writer
icon: Linkedin
hub: career
route: linkedin-writer
blocks:
  - type: vault-notes
    title: Posts
    config:
      directory_filter: posts
      sort: modified_desc
      limit: 30
  - type: vault-notes
    title: Context & Assets
    config:
      directory_filter: context,assets
      collapsed: true
  - type: action-bar
    mcp_tool: list-skill-actions
    skill_id: linkedin-writer
```

## 6. Lifestyle YAML Page

**Route:** `/life/lifestyle`
**File:** `skills/lifestyle/augur/pages/overview.yaml`

```yaml
title: Lifestyle
icon: Heart
hub: life
route: lifestyle
blocks:
  - type: vault-notes
    title: Ideas
    config:
      directory_filter: ideas
      sort: modified_desc
  - type: vault-notes
    title: Recipes
    config:
      directory_filter: recipe-manager
  - type: vault-notes
    title: Knowledge & Notes
    config:
      directory_filter: knowledge,notes
      collapsed: true
  - type: action-bar
    mcp_tool: list-skill-actions
    skill_id: lifestyle
```

## 7. Generic Vault MCP Tools

**File:** `src/mcp/augur_mcp/core/vault_ops.py` (new)

### vault-file-read

```python
@mcp.tool(name="vault-file-read")
async def vault_file_read(skill: str, path: str) -> str:
    """Read full content of a vault file by relative path."""
    # Resolves: get_skill_data_dir(skill) / path
    # Returns: { success, frontmatter: {}, body: "...", lines: N, modified: "..." }
    # Security: path must be within skill's vault dir (no traversal)
```

### vault-file-write

```python
@mcp.tool(name="vault-file-write")
async def vault_file_write(skill: str, path: str, title: str, body: str, metadata: dict = {}) -> str:
    """Write a vault file with frontmatter. Creates parent dirs."""
    # Uses write_frontmatter() from src/lib/frontmatter_utils
    # Returns: { success, path: "...", created: bool }
    # Security: path within skill vault dir only, no overwrite without explicit flag
```

Registered in core MCP server alongside `list-skill-vault-notes`. Generic, not skill-specific.

## Implementation Order

1. Generic tools first (`vault-file-read`, `vault-file-write`) — foundation for TSX pages
2. Auto-page upgrade (`list-skill-vault-notes` + `VaultNotesBlock`) — benefits all skills immediately
3. YAML pages (linkedin-writer, lifestyle) — quick wins using enhanced block
4. Career TSX pages — verify/rebuild MCP tools from git history, then pages
5. Venture-augur TSX page — uses generic tools
6. Growth TSX pages — verify old tools, reference old TSX page

## Constraints

- All data fetching via `useMcpQuery`/`useMcpMutation` — no fs/spawn (CLAUDE.md rule 11)
- TSX pages in `skills/{skill}/augur/dashboard/` — auto-mounted to dashboard (CLAUDE.md plugin mounting)
- YAML pages in `skills/{skill}/augur/pages/` — scanner generates wrapper TSX (ADR-491)
- Generic tools in `src/mcp/augur_mcp/core/` — not skill-scoped
- Verify old MCP tools from git before referencing — don't assume they still exist
- Enhanced `list-skill-vault-notes` must be backwards compatible (keep `notes[]` flat array)
