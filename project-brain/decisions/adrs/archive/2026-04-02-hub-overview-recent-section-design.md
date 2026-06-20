# Hub Overview — Recent Section

**Date:** 2026-04-02
**Status:** Approved
**Scope:** Enhance hub-level overview pages with a unified "Recent" section showing latest notes and documents across all skills in the hub.

## Problem

Each hub overview (`HubOverviewPage.tsx`) shows Apps, Tools, Notes, and User Blocks — but Notes is scoped to the primary skill only. There's no cross-skill view of recent activity within a hub. Users can't see at a glance what changed recently across all skills belonging to a hub.

## Solution

Add a `RecentSection` component to `HubOverviewPage` that shows the latest notes and documents from all skills in the hub, sorted by modification time, with per-skill capping to prevent one active skill from dominating.

## Design

### Layout

The section slots into the existing render order:

```
Hub Header → Apps → Tools → ★ RecentSection (new) → Notes → User Blocks
```

Existing sections (Apps, Tools, Notes, User Blocks) are unchanged.

### RecentSection Component

**Location:** `apps/dashboard/components/plugin/HubOverviewPage.tsx` (same file as other sections)

**Props:** `{ hubId: string }`

**Behavior:**

| State | Rendering |
|-------|-----------|
| Loading | 3 skeleton rows with pulse animation |
| Empty (no files) | Section hidden entirely |
| Error | Subtle error banner matching Notes section style |
| Data | Flat list of items, max 10, capped at 2 per skill |

**Each item row displays:**

| Field | Source | Style |
|-------|--------|-------|
| Type icon | `note` = purple icon, `doc` = blue icon | 28px rounded square |
| Name | File name (sans extension) | 13px, font-weight 500, truncated |
| Type + skill badge | e.g., "note · coach" | 11px muted text |
| Relative time | `formatTimeAgo(modified)` | 11px muted, right-aligned |

**"View all →"** link in section header routes to `/browse?hub={hubId}`.

**No click action on items in v1.** Future enhancement can open files in vault/editor.

### MCP Tool: `list-hub-recent-files`

**Location:** Python MCP server (new tool registration)

**Input:**
```json
{
  "hub_id": "career",
  "limit": 10,
  "per_skill_limit": 2
}
```

**Output:**
```json
{
  "success": true,
  "files": [
    {
      "name": "Interview prep — Stripe SRE",
      "path": "career/interview-prep-stripe-sre.md",
      "type": "note",
      "skill": "career",
      "modified": "2026-04-02T10:30:00Z",
      "preview": "System design questions, behavioral prep..."
    }
  ],
  "count": 6
}
```

**Logic:**
1. Read `assembled_hubs.json` to get all skills with `x-augur-hub == hub_id`
2. For each skill, scan its vault directory for markdown and document files
3. Sort all files by `modified` descending
4. Cap at `per_skill_limit` (default 2) items per skill
5. Return top `limit` (default 10) items total

**Type classification:**
- Files in vault note directories → `type: "note"`
- Files in vault data/document directories → `type: "doc"`
- Classification based on path convention, not content inspection

### Data Fetching (Frontend)

```typescript
const { data, loading, error } = useMcpQuery<RecentFile[]>(
  ['hub-recent-files', hubId],
  'list-hub-recent-files',
  'user-data',
  {
    args: { hub_id: hubId, limit: 10, per_skill_limit: 2 },
    select: (raw) => {
      const d = unwrap(raw);
      if (d && typeof d === 'object' && 'files' in d) return d.files;
      return Array.isArray(d) ? d : [];
    },
  },
);
```

Uses `user-data` preset (same as Notes section) since vault files are user data with moderate refresh needs.

### Type Definition

```typescript
interface RecentFile {
  name: string;
  path: string;
  type: 'note' | 'doc';
  skill: string;
  modified: string;
  preview?: string;
}
```

## Scope

### In scope
- `RecentSection` component in `HubOverviewPage.tsx`
- `list-hub-recent-files` MCP tool in Python
- Works for all 6 hubs automatically (component is hub-agnostic)
- Skeleton loading, error state, empty-hides behavior

### Out of scope
- Click-to-open file behavior
- Search/filter within Recent section
- Reordering or modifying existing sections
- Changes to sidebar navigation or hub configuration

## Testing

- MCP tool: unit test with mock vault data, verify per-skill capping and sort order
- Component: verify renders items, handles loading/empty/error states
- Integration: browser verification on at least 2 hubs (one with data, one without)
