---
title: "Browse Page Lifecycle Ordering and Journey-Group Delimiters"
type: spec
status: draft
created: 2026-05-11
authors:
  - gsannikov
related:
  - ADR-727 — Background Routines Unified Discovery (parallel work on the same Browse surface)
  - apps/dashboard/lib/browse/types.ts
  - apps/dashboard/app/(views)/browse/BrowseToolbar.tsx
governance:
  next_step: ADR (via /adr write) — no separate writing-plans needed (scope too small for multi-task plan)
tags:
  - dashboard
  - browse
  - information-architecture
  - ui
---

# Browse Page Lifecycle Ordering and Journey-Group Delimiters

## 1. Problem

The Browse page exposes 24 categories (12 visible, 12 dev-only) in an order that doesn't match how users actually move through their work. The existing `group: "content" | "system" | "dev"` field does double duty — it gates visibility (dev is hidden by default) AND attempts to group tabs — but the three values don't capture the user's lifecycle journey, and there's no visual delimiter between groups.

Current state:
- 24 tabs in a single horizontal strip with no separators
- The 3-value `group` field is used as both visibility gate and grouping mechanism
- Drafts (`group: content`) and Archive (`group: content`) sit at positions 11-12, separated from the rest of `content` (positions 1-7) by 3 `system` items — visibly out of place
- No indication to the user that, for example, Inbox and Sources are "raw incoming" while Wiki is "compounded knowledge"

User asks per-tab: "what problem is this tab answering for me?" The Browse page doesn't help them see that without clicking into each tab.

## 2. Goals and non-goals

### Goals

1. **Lifecycle ordering** — left-to-right reads as the user's content lifecycle (raw → processed → reusable → operational → archived).
2. **Two-axis schema** — decouple visibility (`group`) from grouping (`journey_group`).
3. **Visible group labels** — small uppercase labels above each group of tabs ("INCOMING", "KNOWLEDGE", etc.) so the journey shape is unmistakable.
4. **Stable ordering within groups** — `journey_order: int` per category, so re-ordering is explicit and code-reviewable.
5. **Same treatment for dev tabs** — when dev mode is toggled on, the dev tab bar uses the same group-label pattern (INTENT, WIRING, ORCHESTRATION, DIAGNOSTICS).

### Non-goals

- Per-user reordering / pinning (deferred to a follow-on if demand surfaces)
- Animated transitions between groups
- Color coding per group (kept neutral; labels carry the meaning)
- Merging the visible and dev tab bars into a single scrollable view (kept separate per the existing toggle pattern)
- Renaming any existing category — only reordering + grouping
- Touching the underlying Browse data model (only the tab bar render)

## 3. Per-tab problem statement + journey group

### Visible tabs (12 native + 1 added by ADR-723 = 13 tabs, 5 journey groups)

| Order | Tab id | Journey group | journey_order | Problem this tab answers |
|---|---|---|---|---|
| 1 | `inbox` | `incoming` | 1 | New stuff arrived — process or trash? |
| 2 | `sources` | `incoming` | 2 | What document folders does Augur know about? |
| 3 | `notes` | `knowledge` | 1 | What did I write down? |
| 4 | `wiki` | `knowledge` | 2 | What does Augur know about a recurring concept? |
| 5 | `pages` ⚡ | `knowledge` | 3 | What HTML artifacts (live dashboard pages, saved deliverables, generated specs) can I open and read? *(added by ADR-723; placement reserved here)* |
| 6 | `skills` | `reuse` | 1 | What modular expertise is available to my agent? |
| 7 | `actions` | `reuse` | 2 | What one-click operations exist? |
| 8 | `prompts` | `reuse` | 3 | What reusable prompts have I saved? |
| 9 | `integrations` | `system` | 1 | What external services is Augur talking to? |
| 10 | `extensions-bundles` | `system` | 2 | What plugin packages are installed? |
| 11 | `background-routines` | `system` | 3 | What runs without me asking + what's burning my budget? |
| 12 | `drafts` | `state` | 1 | What am I in the middle of writing/building? |
| 13 | `archive` | `state` | 2 | Where did the old stuff go? |

⚡ The `pages` tab is **added by ADR-723** (Augur Pages HTML Artifacts), not by this ADR. ADR-728 reserves its placement at `journey_group: knowledge, journey_order: 3`. When ADR-723 implementation adds `pages` to `BROWSE_CATEGORIES`, it picks up this placement. See §11 Coordination with ADR-723 below.

### Dev tabs (12 tabs, 4 journey groups)

| Order | Tab id | Journey group | journey_order | Problem this tab answers |
|---|---|---|---|---|
| 1 | `adrs` | `intent` | 1 | Why was this decision made? |
| 2 | `commands` | `intent` | 2 | What slash commands exist? |
| 3 | `dashboard-surfaces` | `intent` | 3 | What pages does the dashboard have? |
| 4 | `mcp-servers` | `wiring` | 1 | What MCP servers are connected? |
| 5 | `mcp-tools` | `wiring` | 2 | What tools can my agent call? |
| 6 | `api-routes` | `wiring` | 3 | What HTTP routes does the dashboard expose? |
| 7 | `scripts` | `wiring` | 4 | What standalone scripts exist? |
| 8 | `workflow-definitions` | `orchestration` | 1 | What multi-step chains are defined? |
| 9 | `agent-profiles` | `orchestration` | 2 | What agent configurations exist? |
| 10 | `tests` | `diagnostics` | 1 | What's being tested? |
| 11 | `logs` | `diagnostics` | 2 | What just happened? |
| 12 | `system-metadata` | `diagnostics` | 3 | What's the raw state under the hood? |

## 4. Schema changes — two-axis decoupling

`apps/dashboard/lib/browse/types.ts`:

```typescript
export type JourneyGroup =
  | "incoming" | "knowledge" | "reuse" | "system" | "state"      // visible groups
  | "intent"  | "wiring"    | "orchestration" | "diagnostics";    // dev groups

export interface BrowseCategory {
  id: ViewMode;
  label: string;
  singularLabel: string;
  icon: string;
  devOnly?: boolean;
  group: "content" | "system" | "dev";   // EXISTING — visibility gate (unchanged)
  journey_group: JourneyGroup;            // NEW — lifecycle bucket
  journey_order: number;                   // NEW — rank within journey_group (1-indexed)
  viewLayout?: "table" | "card";
}

export const JOURNEY_GROUP_LABELS: Record<JourneyGroup, string> = {
  incoming:      "INCOMING",
  knowledge:     "KNOWLEDGE",
  reuse:         "REUSE",
  system:        "SYSTEM",
  state:         "STATE",
  intent:        "INTENT",
  wiring:        "WIRING",
  orchestration: "ORCHESTRATION",
  diagnostics:   "DIAGNOSTICS",
};

// Order in which journey_groups render left-to-right (visible groups first, then dev groups).
export const JOURNEY_GROUP_ORDER: JourneyGroup[] = [
  "incoming", "knowledge", "reuse", "system", "state",
  "intent", "wiring", "orchestration", "diagnostics",
];
```

The existing `group` field is preserved as-is — it gates visibility (dev categories hidden until toggle). The new `journey_group` + `journey_order` are pure ordering metadata.

## 5. Rendering — tab bar with group labels

The Browse tab bar component (likely `apps/dashboard/app/(views)/browse/BrowseToolbar.tsx`) changes from a flat tab list to a grouped layout:

```tsx
// Pseudocode for the layout (real implementation matches the existing styling system).
const visibleCategories = BROWSE_CATEGORIES.filter(c => !c.devOnly || devModeOn);

// Bucket by journey_group, preserving JOURNEY_GROUP_ORDER
const byGroup = JOURNEY_GROUP_ORDER
  .map(gid => ({
    gid,
    label: JOURNEY_GROUP_LABELS[gid],
    tabs: visibleCategories
      .filter(c => c.journey_group === gid)
      .sort((a, b) => a.journey_order - b.journey_order),
  }))
  .filter(g => g.tabs.length > 0);

return (
  <div className="browse-toolbar">
    {byGroup.map(g => (
      <div key={g.gid} className="journey-group">
        <div className="journey-group-label">{g.label}</div>
        <div className="journey-group-tabs">
          {g.tabs.map(t => <Tab key={t.id} {...t} />)}
        </div>
      </div>
    ))}
  </div>
);
```

CSS:
- `.browse-toolbar` — flex row, wrap on narrow viewports
- `.journey-group` — flex column (label on top, tabs row underneath)
- `.journey-group-label` — small uppercase, muted (e.g. `text-xs uppercase text-muted-foreground tracking-wider`), ~20px tall
- `.journey-group-tabs` — flex row, the existing tab styling

Separation between groups is the gap between adjacent `.journey-group` columns plus the visible label above each.

## 6. Implementation order

Three checkpoints, one PR:

| # | Checkpoint | Verifiable by |
|---|---|---|
| **C1** | Add `JourneyGroup` type + `JOURNEY_GROUP_LABELS` + `JOURNEY_GROUP_ORDER` constants to `types.ts`. Add `journey_group` + `journey_order` to all 24 entries of `BROWSE_CATEGORIES`. | TypeScript compiles; pytest/Vitest if there's a tab schema test |
| **C2** | Update the tab bar rendering component to group + sort by `journey_group` / `journey_order`, render `JOURNEY_GROUP_LABELS` above each group. | Visual snapshot test or browser verify per rule 28 |
| **C3** | Browser verification (rule 28): open `/browse`, confirm five visible group labels render in correct order with correct tabs underneath. Toggle dev mode, confirm four additional groups appear. Confirm no tab is missing or mis-grouped. | Real-browser load |

No separate plan document — the implementation is ~2 files, <100 lines net. The three checkpoints above are sufficient direct guidance.

## 7. Out of scope

| Item | Why deferred |
|---|---|
| Per-user reordering / pinning | YAGNI — defaults are good; revisit if multiple users ask |
| Color coding per group | Labels carry the meaning; adding color risks over-design |
| Animated group transitions | Pure cosmetic; not blocking the IA fix |
| Merging visible + dev tab bars into one scrollable strip | Existing toggle pattern is fine; merging adds clutter |
| Renaming any category | Out of scope — only reordering + grouping |

## 8. Alternatives considered

| Alternative | Why rejected |
|---|---|
| Use existing `group` field for both visibility AND journey-grouping | Single field can't carry two axes cleanly; doing so today is exactly the inconsistency this spec fixes |
| Pure ordering (no labels) | User asked for delimiters AND said they want to see what problem each tab answers — labels make the journey shape unmistakable |
| Tab pills with group-colored borders | Adds visual weight; relies on color memory; harder for users with color-vision differences |
| Vertical divider line (no labels) | Subtler but loses the "what does this group mean" signal |
| Larger gap only (no line, no label) | Easy to miss; the user can't infer the journey shape from spacing alone |

## 9. References

- ADR-727 — Background Routines Unified Discovery (parallel Browse work; same category list touched)
- ADR-723 — Augur Pages HTML Artifacts (parallel Browse work — adds the `pages` ViewMode and the `kind` filter chip)
- CLAUDE.md rule 28 — Browser verification mandatory for UI changes
- `apps/dashboard/lib/browse/types.ts` — current schema
- `apps/dashboard/app/(views)/browse/BrowseToolbar.tsx` — current tab bar component

## 10. Coordination with ADR-727 and ADR-723

Three ADRs touch `apps/dashboard/lib/browse/types.ts` (specifically `BROWSE_CATEGORIES`) and the Browse rendering surface. Coordination matters.

### ADR-727 → ADR-728

ADR-727 (Background Routines Unified Discovery) renames the existing `scheduled-executions` category to `background-routines` (its plan Task 13 makes this edit). ADR-728 reorders + adds `journey_group` + `journey_order` to every category, including the renamed `background-routines`.

**Implementation order:** ship ADR-727 first (it has the full multi-task plan), then ADR-728 (small refinement) absorbs the new `background-routines` id when it adds journey-group fields to all entries.

If both ADRs are implemented in one PR instead: ADR-727's Task 13 (the `BROWSE_CATEGORIES` edit) absorbs ADR-728's schema additions in the same edit. Same end state, smaller diff.

### ADR-723 → ADR-728

ADR-723 (Augur Pages HTML Artifacts) adds a **new** Browse ViewMode `pages` to `BROWSE_CATEGORIES`. The new entry needs a `journey_group` + `journey_order` assignment.

**Reserved placement (decided here, applied by ADR-723 implementation):**

```typescript
{
  id: "pages",
  label: "Pages",
  singularLabel: "Page",
  icon: "FileCode",   // or whatever icon ADR-723's plan chooses
  devOnly: false,
  group: "content",
  journey_group: "knowledge",  // ← reserved by ADR-728
  journey_order: 3,            // ← reserved by ADR-728 (after wiki at order 2)
  viewLayout: "card",          // or whatever ADR-723 chooses
}
```

When ADR-723 implementation lands and adds the `pages` entry to `BROWSE_CATEGORIES`, it MUST use these two reserved values. If ADR-723 ships before ADR-728, ADR-723's implementation should still set these fields (effectively forward-declaring them) so ADR-728's refinement pass is a no-op for `pages`.

**Why `knowledge` and not a new `artifacts` group:** considered both during the brainstorm (spec §8 alternatives). The 1-tab `artifacts` group was the semantic-cleanest option but creates visual asymmetry (every other group has 2-4 tabs). The `knowledge` placement keeps the layout balanced at 3 tabs and treats `pages` as a sibling of Wiki — both are read-mostly artifact surfaces. The `live` kind within `pages` (operational dashboard surfaces like `/brain/inbox`) is slightly awkward in `knowledge` but the alternative cost is greater.

### ADR-722 → ADR-728

ADR-722 (Setup Completeness Widget) adds a sidebar widget, NOT a new Browse category. No coordination needed.

## 11. Governance

This spec is the design record. After approval:

1. `/adr write` adopts it as ADR-728 (thin index).
2. No separate `/superpowers:writing-plans` — scope is too small (~2 files, <100 lines).
3. Implementation either via `/adr implement ADR-728` (which would drive the spec-only, no plan) OR as a tactical commit referencing the ADR.

The brainstorming spec is not the architectural commitment — the ADR is.
