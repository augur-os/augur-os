---
status: Implemented
date: 2026-02-12 (updated 2026-02-13)
deciders:
- Core team
related:
- ADR-065 (Dashboard Hardening Workflow)
- ADR-040 (Plugin Template Standard)
- ADR-085 (RAG Three-Tier Index)
- ADR-082 (Knowledge Hardening)
- ADR-027 (MCP App Factory)
hub: null
tags:
- hub
- data
- bridge
- standardized
- hub
superseded_by: null
---

# ADR-086: Hub Data Bridge — Standardized Hub Overview & External Data Integration

## Context

### Two Existing Workflows — Neither Covers These Use Cases

| Flow | Purpose | Trigger | Output |
|------|---------|---------|--------|
| **`/harden`** (ADR-065) | Audit an existing hub across 10 dimensions, generate improvement ADR | `/harden http://localhost:3000/career` | Hardening ADR with scored gaps |
| **Factory Pipeline** (ADR-027/040) | Scaffold or refactor a plugin through 5 stages | `workflow-start(mode=refactor)` | Complete plugin structure |

**`/harden`** knows how to evaluate what a dashboard has but never looks outside the codebase.
**Factory** knows how to build plugins from scratch but not from external reference material.

### Two Distinct Use Cases

**Level 1 — Import (Dev Mode):** "I have a Finance workflow built in Notion + Excel + PDFs. I want to run a command that scans that folder, understands my user flows, and creates (or refactors) an Augur dashboard from it."

This is a one-time dev action. The folder IS the spec. Excel sheet structure reveals what tabs the dashboard needs. Notion pages reveal user flows. PDFs reveal document types to support. The output is a new or refactored plugin — code generation, not just config.

**Level 2 — Connect (Operation Mode):** "I already have a Finance dashboard in Augur. I want to click a button and connect it to a folder (or later, a Notion workspace, or Google Drive) to get summary cards, AI analysis buttons, and open-file links."

This is an ongoing operational action. No code generation — just a config file (`connections.yaml`) that src/lib runtime components read. Pluggable sources: folder today, Notion MCP tomorrow, Google Drive later.

### How They Relate

```
Level 1 (/import)                   Level 2 (Connect button)
─────────────────                   ──────────────────────────
Dev runs once                       User runs anytime
Creates/refactors the hub           Enriches an existing hub
Folder = the spec                   Folder = a data source
Generates code                      Writes config only
Factory-like                        Harden-like

        ┌──────────────────────────┐
        │     Shared Layer         │
        ├──────────────────────────┤
        │ File Analyzers           │
        │ Source Adapters          │
        │ Integration Modes        │
        │ ExternalDataCards.tsx     │
        │ FileActions.tsx          │
        │ excel_reader.py          │
        │ Knowledge Tier 3 reg.    │
        └──────────────────────────┘
```

Level 1 calls Level 2 at the end — after generating the dashboard, it auto-connects the source folder so the new hub already has live external data on first load.

## Decision

### Architecture: Two Levels, Shared Core

```
┌─────────────────────────────────────────────────────────┐
│  Level 1: /import ~/Documents/Finance                    │
│  ─────────────────────────────────────                   │
│  1. Scan folder (src/lib)                                 │
│  2. Analyze user flows (NEW — understand what user does) │
│  3. Generate hub structure (factory patterns)            │
│  4. Generate dashboard pages, API routes, actions        │
│  5. Auto-connect folder via Level 2                      │
│  Output: New/refactored plugin + connected source        │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  Level 2: Connect button (dashboard UI)                  │
│  ──────────────────────────────────────                   │
│  1. User clicks Connect → picks source type + path       │
│  2. Scan source (src/lib)                                 │
│  3. Show integration plan → user approves                │
│  4. Write connections.yaml (no code gen)                  │
│  5. Shared components read config at runtime             │
│  Output: connections.yaml + live data on dashboard       │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  Shared Core                                             │
│  ───────────                                             │
│  folder_scanner.py          — file analyzers             │
│  source_adapter.py          — pluggable source interface │
│  integration_planner.py     — mode assignment engine     │
│  excel_reader.py            — read cells, return JSON    │
│  ExternalDataCards.tsx      — stat cards from summaries   │
│  FileActions.tsx            — AI analyze + open buttons   │
│  /api/bridge/summary        — generic bridge API         │
│  /api/bridge/connections     — manage connections         │
│  connections.yaml schema    — per-hub connection config   │
└─────────────────────────────────────────────────────────┘
```

---

### Shared Core Components

#### Component 1: Source Adapter Interface

Pluggable pattern — folder today, Notion/Google Drive tomorrow.

**File**: `plugins/dev/skills/frontend/scripts/source_adapters/base.py`

```python
class SourceAdapter:
    """Base class for external data sources."""
    source_type: str  # "folder", "notion", "gdrive"

    def scan(self) -> ScanManifest:
        """Scan the source and return structured manifest."""
        raise NotImplementedError

    def read_file(self, path: str) -> bytes:
        """Read a specific file from the source."""
        raise NotImplementedError

    def list_files(self) -> list[FileInfo]:
        """List all files in the source."""
        raise NotImplementedError
```

**Adapters**:

| Adapter | Source | File | Available |
|---------|--------|------|-----------|
| `FolderAdapter` | Local filesystem path | `source_adapters/folder.py` | Now |
| `NotionAdapter` | Notion MCP workspace | `source_adapters/notion.py` | Future (when Notion MCP stable) |
| `GDriveAdapter` | Google Drive folder | `source_adapters/gdrive.py` | Future (uses google-workspace skill) |

#### Component 2: File Analyzers

Pluggable per-type analyzers that extract structure from files.

**File**: `plugins/dev/skills/frontend/scripts/file_analyzers/`

| Analyzer | Files | Extracts |
|----------|-------|----------|
| `ExcelAnalyzer` | .xlsx, .xls, .csv | Sheet names, column headers, row counts, totals detection, named ranges |
| `PdfAnalyzer` | .pdf | Page count, text extractable, section headings, tables |
| `NotionAnalyzer` | .md (Notion export) | Page title, headings, database/table structure, linked pages |
| `DirectoryAnalyzer` | folders | File count, dominant type, purpose guess |
| `GenericAnalyzer` | everything else | Name, type, size only |

Each analyzer returns a `FileStructure` dict that the integration planner consumes.

#### Component 3: Integration Modes

Every file/group gets assigned one mode:

| Mode | What Happens | Dashboard Component | Code Gen Required? |
|------|-------------|--------------------|--------------------|
| **summary** | Read specific values (cells, fields), show as stat cards | `ExternalDataCards.tsx` | No — generic `/api/bridge/summary` reads `connections.yaml` |
| **ai-analyze** | Button feeds file content + prompt to AI | `FileActions.tsx` (flow: llm) | No — action defined in `connections.yaml`, rendered by src/lib component |
| **open-external** | Button opens file in native app (Finder, Excel, Preview) | `FileActions.tsx` (system-open) | No — uses `system-open-file` MCP tool |
| **page-candidate** | File maps to a dashboard tab/page (L1 only) | Generated page.tsx | Yes — L1 generates the page |
| **ignore** | No integration | None | No |

Key insight: **L2 (Connect) needs zero code generation**. Modes `summary`, `ai-analyze`, and `open-external` are all handled by src/lib components that read `connections.yaml` at runtime. Only L1's `page-candidate` mode generates code.

#### Component 4: connections.yaml (Per-Hub Config)

Runtime config that src/lib components read. Written by L2 Connect button (or by L1 at the end).

**Location**: `plugins/{bundle}/skills/{skill}/data/connections.yaml`

```yaml
version: 1
hub: finance
connections:
  - id: finance-folder
    source_type: folder
    source_path: ~/Documents/Finance
    connected_at: "2026-02-12T10:00:00Z"

    integrations:
      - id: balance-sheet-totals
        file: balance-sheet-2025.xlsx
        mode: summary
        extractions:
          - id: total_assets
            label: "Total Assets"
            sheet: Summary
            cell: B42
            format: currency
          - id: net_worth
            label: "Net Worth"
            sheet: Summary
            cell: B44
            format: currency
        display:
          type: stat-cards
          tab: overview
          section: external-data

      - id: analyze-statement
        files: "bank-statement-*.pdf"
        mode: ai-analyze
        action:
          label: "Analyze Bank Statement"
          icon: Brain
          flow: llm
          prompt_context: |
            You are analyzing a bank statement for the Finance hub.
            Extract: opening balance, closing balance, total debits, total credits.
            Flag any unusual transactions over $500.

      - id: open-receipts
        file: receipts/
        mode: open-external
        action:
          label: "Open Receipts"
          icon: FolderOpen

      - id: open-balance-sheet
        file: balance-sheet-2025.xlsx
        mode: open-external
        action:
          label: "Open in Excel"
          icon: FileSpreadsheet

    ignored:
      - file: .DS_Store
        reason: "System file"
      - file: old-tax-2020.pdf
        reason: "Dated, low relevance"
```

#### Component 5: Generic Bridge API

One src/lib API that ALL hubs use. No per-hub route generation for L2.

**File**: `src/dashboard/app/api/bridge/summary/route.ts`

```typescript
// GET /api/bridge/summary?hub=finance
// Reads connections.yaml for the given hub, runs extractions, returns values
export async function GET(request: Request) {
  const hub = new URL(request.url).searchParams.get("hub");
  const config = loadConnections(hub); // reads connections.yaml
  const summaries = await extractSummaries(config); // calls excel_reader.py
  return Response.json({ hub, summaries, updated_at: new Date() });
}
```

**Other src/lib routes**:
- `GET /api/bridge/connections?hub=finance` — list connections for a hub
- `POST /api/bridge/connections` — add a new connection (called by Connect button)
- `DELETE /api/bridge/connections` — remove a connection
- `POST /api/bridge/refresh?hub=finance` — re-scan source, update stale values

#### Component 6: Shared Dashboard Components

**`ExternalDataCards.tsx`** — renders stat cards from bridge summary API:
```tsx
// Fetches /api/bridge/summary?hub={hubId}
// Renders GlassCard per extraction with label, value, format
// Shows "Refresh" button + "Last updated" timestamp
// Shows "Open in Excel" link next to values sourced from spreadsheets
```

**`FileActions.tsx`** — renders action buttons from connections.yaml:
```tsx
// Reads integrations with mode: ai-analyze or open-external
// Renders action buttons using design system
// ai-analyze: opens IDE chat with file path + prompt_context
// open-external: calls system-open-file MCP tool
```

Both components are in `src/dashboard/components/bridge/` and usable by any hub via:
```tsx
import { ExternalDataCards } from "@/components/bridge/ExternalDataCards";
import { FileActions } from "@/components/bridge/FileActions";

// In any hub page:
<ExternalDataCards hubId="finance" />
<FileActions hubId="finance" />
```

---

### Level 1: `/import` (Dev Mode)

**Command**: `/import ~/Documents/Finance`
or: `/import ~/Documents/Finance --hub finance` (if hub already exists, refactor it)

**What it does**: Scans the folder, understands the user's workflow, and CREATES or REFACTORS an Augur dashboard hub.

**How it differs from factory**: Factory builds from a blank spec. `/import` reverse-engineers the spec from the user's existing files.

#### Stage 1: Deep Scan + Flow Analysis

Goes beyond file-level analysis — understands what the USER DOES with these files.

```
Scan: ~/Documents/Finance/
├── balance-sheet-2025.xlsx (5 sheets, 200 rows, formulas, monthly cadence)
│   → User tracks assets/liabilities monthly. Key workflow: update → review totals
├── bank-statement-*.pdf (12 files, monthly series)
│   → User reviews monthly. Key workflow: scan for anomalies → categorize spending
├── budget-2025.xlsx (3 sheets: Plan vs Actual vs Variance)
│   → User compares planned vs actual. Key workflow: update actuals → check variance
├── receipts/ (47 files, photos + PDFs)
│   → User stores receipts. Key workflow: file receipt → occasional search
├── tax-2025/ (nested: forms, docs, correspondence)
│   → User gathers tax docs. Key workflow: collect → review → submit
└── investments.csv (portfolio, 30 rows, ticker + shares + value)
    → User tracks portfolio. Key workflow: update values → check performance

Flow Analysis Output:
├── Hub: "Finance" (or refactor existing)
├── Suggested tabs:
│   ├── Overview (totals from balance-sheet, budget variance, portfolio value)
│   ├── Budget (plan vs actual — read from budget-2025.xlsx)
│   ├── Statements (monthly PDFs — AI analyze)
│   ├── Portfolio (investments.csv — simple table)
│   ├── Tax (nested folder — file browser + AI assist)
│   └── Receipts (folder link + search)
├── Key stat cards: Net Worth, Budget Variance, Portfolio Value
├── Key actions: "Analyze Statement", "Update Budget", "Open Balance Sheet"
└── Data strategy per file:
    ├── balance-sheet → summary (read totals) + open-external
    ├── budget → summary (variance) + open-external
    ├── investments.csv → page-candidate (simple enough to render as table)
    ├── bank-statements → ai-analyze + open-external
    ├── receipts/ → open-external
    └── tax-2025/ → open-external + ai-analyze (per doc)
```

This is the AI-heavy step — it requires understanding document intent, not just structure.

#### Stage 2: Hub Blueprint Generation

Produces a complete hub blueprint (what factory's stages 1-4 produce, but reverse-engineered from files).

```yaml
# Generated blueprint: data/runtime/import/finance/blueprint.yaml
hub:
  id: finance
  title: Finance Hub
  category: personal
  mode: operation

tabs:
  - id: overview
    label: Overview
    default: true
    content:
      - type: stat-cards
        source: connections  # reads from connections.yaml at runtime
      - type: file-actions
        source: connections
  - id: budget
    label: Budget
    content:
      - type: summary-table
        source_file: budget-2025.xlsx
        sheet: Variance
        note: "Simple table — 12 rows, 5 columns. Rendered directly."
  - id: portfolio
    label: Portfolio
    content:
      - type: data-table
        source_file: investments.csv
        note: "30 rows, renderable as sortable table"
  - id: statements
    label: Statements
    content:
      - type: file-list
        pattern: "bank-statement-*.pdf"
        actions: [ai-analyze, open-external]
  - id: tax
    label: Tax
    content:
      - type: folder-browser
        source_dir: tax-2025/
        actions: [ai-analyze, open-external]

# What stays external (NOT migrated into dashboard data):
external_only:
  - balance-sheet-2025.xlsx  # Too complex, formulas. Read totals only.
  - bank-statement-*.pdf     # PDFs stay as PDFs. AI analyzes on demand.
  - receipts/                # Image/PDF folder. Just link.

# What gets a proper page (simple enough to render):
rendered:
  - investments.csv          # 30 rows, simple table. Render in dashboard.
  - budget-2025.xlsx:Variance  # 12 rows, simple comparison. Render as table.
```

#### Stage 3: Code Generation

Uses factory patterns to generate the plugin structure. Produces:

| Output | Source Pattern | Description |
|--------|---------------|-------------|
| `SKILL.md` | Factory stage 1 template | Plugin definition with correct metadata |
| `dashboard.yaml` | Factory stage 4 template | Hub config: tabs, actions from blueprint |
| `dashboard/page.tsx` | Factory stage 5 template | Overview page with ExternalDataCards + FileActions |
| `dashboard/tabs/*.tsx` | Factory stage 5 template | Per-tab pages (Budget table, Portfolio table, Statements list, Tax browser) |
| `dashboard/layout.tsx` | Factory stage 5 template | Standard layout |
| `api/data/route.ts` | Factory data-route template | For `rendered` files: reads CSV/Excel into JSON |
| `api/health/route.ts` | Factory health-route template | Standard health endpoint |

For refactoring an existing hub: diff the blueprint against current state, generate only the missing pieces.

#### Stage 4: Auto-Connect (Calls Level 2)

After code generation, automatically run Level 2's connection flow:
1. Write `connections.yaml` with all `summary`, `ai-analyze`, and `open-external` integrations
2. Register files with Knowledge Tier 3 (ADR-085)
3. Verify: `npm run build`, API endpoints respond, summary values load

#### User Interaction

```
$ /import ~/Documents/Finance

Scanning ~/Documents/Finance...
Found 23 files across 3 directories.

┌─────────────────────────────┬──────┬────────────────────┐
│ File                        │ Type │ Suggested Strategy  │
├─────────────────────────────┼──────┼────────────────────┤
│ balance-sheet-2025.xlsx     │ xlsx │ Summary + Open      │
│ budget-2025.xlsx            │ xlsx │ Render table + Open │
│ investments.csv             │ csv  │ Render as table     │
│ bank-statement-*.pdf (12)   │ pdf  │ AI Analyze + Open   │
│ receipts/ (47 files)        │ dir  │ Open folder         │
│ tax-2025/ (8 files)         │ dir  │ AI Analyze + Open   │
└─────────────────────────────┴──────┴────────────────────┘

[Q1] Hub name? → "finance" (creates new) / "finance" (refactors existing)
[Q2] These tabs look right? → Overview, Budget, Portfolio, Statements, Tax, Receipts
[Q3] From balance-sheet, show which totals? → Total Assets, Net Worth, Liabilities

Generating Finance hub...
├── Created plugins/finance/skills/finance/ (6 files)
├── Connected folder via connections.yaml
├── Registered 23 files with Knowledge hub
└── Build passed ✓

Finance hub ready at http://localhost:3000/finance
```

---

### Level 2: Connect Button (Operation Mode)

**Trigger**: Button in hub dashboard header or settings area. Near the magic button or in a "Data Sources" dropdown.

**What it does**: Connects an existing dashboard to an external data source. Zero code generation — writes `connections.yaml` and src/lib components render the data at runtime.

#### UI Flow

```
User is on Finance dashboard
→ Clicks "Connect Source" button (📎 icon in hub header)
→ Modal opens:
    ┌──────────────────────────────────────┐
    │  Connect Data Source                  │
    │                                       │
    │  Source type:                          │
    │  [● Folder] [ Notion ] [ Google Drive]│
    │                                       │
    │  Path: [~/Documents/Finance    ] [📂] │
    │                                       │
    │  [Scan & Preview]                     │
    └──────────────────────────────────────┘

→ After scan:
    ┌──────────────────────────────────────┐
    │  Found 23 files                       │
    │                                       │
    │  ☑ balance-sheet.xlsx → Summary cards │
    │  ☑ bank-statement-*.pdf → AI Analyze  │
    │  ☑ receipts/ → Open folder            │
    │  ☐ old-tax-2020.pdf → Ignore          │
    │                                       │
    │  [Connect]  [Cancel]                  │
    └──────────────────────────────────────┘

→ Writes connections.yaml
→ ExternalDataCards + FileActions appear on dashboard immediately
→ Files registered in Knowledge Tier 3
```

#### Technical Flow

```
1. Connect button click
   → Opens ConnectSourceModal.tsx (src/lib component in src/dashboard/components/bridge/)

2. User selects source type + path
   → POST /api/bridge/scan { hub: "finance", source_type: "folder", path: "~/Documents/Finance" }
   → Backend calls folder_scanner.py → returns scan_manifest.yaml
   → Frontend shows file list with suggested modes

3. User adjusts modes + approves
   → POST /api/bridge/connections { hub: "finance", source: {...}, integrations: [...] }
   → Backend calls integration_planner.py → writes connections.yaml
   → Backend calls POST /api/knowledge/hub-files for each file (Tier 3)

4. Dashboard refreshes
   → ExternalDataCards fetches /api/bridge/summary?hub=finance → shows stat cards
   → FileActions reads connections → shows action buttons
   → No rebuild, no restart — just a page refresh
```

#### Future Source Adapters

| Source | Adapter | How It Works | When |
|--------|---------|-------------|------|
| **Folder** | `FolderAdapter` | Reads local filesystem | Now |
| **Notion** | `NotionAdapter` | Uses Notion MCP to list pages, read databases | When Notion MCP is configured |
| **Google Drive** | `GDriveAdapter` | Uses google-workspace skill to list/read files | When Google OAuth configured |
| **iCloud** | `ICloudAdapter` | Reads `~/Library/Mobile Documents/` paths | Future |

Each adapter implements `scan()`, `read_file()`, `list_files()`. The Connect modal shows only adapters whose prerequisites are met (e.g., Notion only shows if Notion MCP is configured).

---

### Where the Connect Button Lives

**In the Overview page** — the `BridgeConnectButton` lives inside the External Sources section of each hub's overview page, not in the layout header. This keeps the header clean and groups the Connect action with the data it manages.

The button is rendered by the `ConnectedSources` component (or a wrapper) as part of the L3 standardized overview template. When clicked, it opens `ConnectSourceModal`.

**Migration note**: The Connect button was initially wired into all 12 layout headers (`plugins/consulting/skills/{skill}/dashboard/layout.tsx`). During L3 implementation, it must be **removed from all layouts** and moved into the overview page template. See Refactoring Plan Phase 0.

### Reuse Summary

| Component | Source | Reused By L1 | Reused By L2 | What's New |
|-----------|--------|-------------|-------------|-----------|
| Stage runner | Factory `engine.py` | Yes (runs /import stages) | No (L2 is stateless) | Extract to src/lib module |
| Hub audit / crawl | `/harden` audit engine | Yes (understand existing hub) | No | Subset: crawl only, not score |
| Code gen templates | Factory templates | Yes (generate pages/routes) | No | None |
| Folder scanner | New | Yes | Yes | `folder_scanner.py` |
| Source adapters | New | Yes (FolderAdapter) | Yes (all adapters) | `source_adapters/*.py` |
| File analyzers | New | Yes | Yes | `file_analyzers/*.py` |
| Integration planner | New | Yes | Yes | `integration_planner.py` |
| Excel reader | New | Yes | Yes | `excel_reader.py` |
| connections.yaml | New | Yes (writes at end) | Yes (writes) | Config schema |
| ExternalDataCards | New | Yes (generated pages use it) | Yes (renders from config) | Shared React component |
| FileActions | New | Yes (generated pages use it) | Yes (renders from config) | Shared React component |
| Bridge API | New | Yes (API available) | Yes (API available) | `/api/bridge/*` routes |
| ConnectSourceModal | New | No | Yes (UI entry point) | Shared React component |
| Knowledge Tier 3 | ADR-085 | Yes | Yes | Existing hub-files API |

---

### Level 3: Standardized Hub Overview Template

Every apps/ hub overview page follows a **three-section template**. This replaces the current ad-hoc approach where each hub builds its overview from scratch with inconsistent layouts and capabilities.

#### The Template

```
┌──────────────────────────────────────────────────────────┐
│  Hub Header (layout.tsx — no Connect button here)        │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  ┌─ Section 1: Top Widgets ────────────────────────────┐ │
│  │  [Stat Card]  [Stat Card]  [Stat Card]  [Stat Card] │ │
│  │  Hub-specific metrics from plugin data + external    │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌─ Section 2: Plugin Data ────────────────────────────┐ │
│  │  📁 config.yaml           [Open] [Copy] [Chat]      │ │
│  │  📁 transactions.yaml     [Open] [Copy] [Chat]      │ │
│  │  📁 goals.yaml            [Open] [Copy] [Chat]      │ │
│  │  📁 portfolio.yaml        [Open] [Copy] [Chat]      │ │
│  │  Auto-scanned from plugins/{bundle}/skills/{skill}/data/  │
│  └──────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌─ Section 3: External Sources ───────────────────────┐ │
│  │  External Sources                     [📎 Connect]  │ │
│  │  ──────────────────────────────────────────────────  │ │
│  │  📂 ~/Documents/Finance          12 files  [🗑️]     │ │
│  │  📂 Google Drive > Receipts       8 files  [🗑️]     │ │
│  │  📝 Notion > Budget Tracker       3 pages  [🗑️]     │ │
│  │  📱 Apple Notes > Health Log      5 notes  [🗑️]     │ │
│  │                                                      │ │
│  │  ExternalDataCards (stat cards from summaries)        │ │
│  │  FileActions (AI analyze + open buttons)              │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

#### Section 1: Top Widgets

Hub-specific stat cards and metrics. These are the "at a glance" numbers the user cares about most.

| Hub | Widgets |
|-----|---------|
| **Finance** | Net Worth, Monthly Income, Expenses, Savings Rate |
| **Career** | Jobs Inbox, Active Applications, Interviews, Archived |
| **Health** | Symptoms Count, Medications, Consultations, Last Checkup |
| **Lifestyle** | Recipes Count, Meal Plans, Shopping Lists |
| **Eisenhower** | Urgent+Important, Important, Urgent, Neither |

Widgets pull from two sources:
- **Plugin data** — read from YAML/JSON files in the plugin's `data/` folder
- **External summaries** — read from `ExternalDataCards` (bridge summary API)

Both are merged into a single stat card row. The component is `HubOverviewWidgets`.

#### Section 2: Plugin Data Browser

Auto-scans `plugins/{bundle}/skills/{skill}/data/` and displays all files in a clean file browser.

**Actions per file**:

| Action | Icon | Behavior |
|--------|------|----------|
| **Open** | `ExternalLink` | Opens file in system default editor (calls `system-open-file` MCP) |
| **Copy Path** | `Copy` | Copies absolute path to clipboard |
| **Chat** | `MessageSquare` | Sends file path to chat input — user can then ask AI questions about the file content |

**Component**: `PluginDataBrowser`
- Props: `{ skillPath: string }` — e.g. `plugins/finance/skills/finance`
- Scans `{skillPath}/data/` via API endpoint
- Renders file list with name, type icon, size, last modified
- Excludes: `__pycache__`, `.DS_Store`, `*.pyc`, `node_modules`

**API**: `GET /api/bridge/plugin-data?skill={skillPath}`
- Lists files in the plugin's data directory
- Returns: `{ files: [{ name, path, type, size, modified }] }`

**No RAG for plugin data** — these are structured config files (YAML, JSON), not documents. They're already part of the codebase.

#### Section 3: External Sources

Connected external data sources. Built on top of the existing L2 bridge components.

**Source types**:

| Source | Adapter | Status |
|--------|---------|--------|
| Local folders | `FolderAdapter` | Available now |
| Google Drive | `GDriveAdapter` | Future (google-workspace skill) |
| Notion | `NotionAdapter` | Future (Notion MCP) |
| Apple Notes | `AppleNotesAdapter` | Future (apple skill) |
| Excel/CSV files | Via FolderAdapter | Available now |
| PDF documents | Via FolderAdapter | Available now |

**RAG indexing**: When a user connects an external folder, files are automatically registered with the Knowledge hub's three-tier RAG index (ADR-085, Tier 3: External References). This means the user can search and reference these files from the chat/AI context without navigating to the source.

**Components** (already built):
- `ConnectedSources` — lists current connections with disconnect button
- `ExternalDataCards` — stat cards from extracted values
- `FileActions` — AI analyze + open-in-app buttons

#### Disconnect Flow

When the user clicks the delete button (🗑️) on a connected source, a confirmation modal appears:

```
┌────────────────────────────────────────┐
│  Remove Connection                      │
│                                         │
│  ~/Documents/Finance (12 files)         │
│                                         │
│  ○ Disconnect only                      │
│    Keep files on disk, remove from hub  │
│                                         │
│  ○ Disconnect and delete source data    │
│    Remove connection AND delete the     │
│    connections.yaml entries + RAG index  │
│                                         │
│  [Cancel]  [Remove]                     │
└────────────────────────────────────────┘
```

- **Disconnect only**: Removes the connection from `connections.yaml`. Files remain on disk untouched. RAG index entries are cleaned up.
- **Disconnect and delete source data**: Removes connection, cleans RAG index, AND removes any cached/extracted data from the runtime directory. Original source files (user's actual files on disk) are NEVER deleted.

**API**: `DELETE /api/bridge/connections` with `{ hub, connectionId, deleteData: boolean }`

#### Standardized Overview Page Template

All apps/ hub overview pages should follow this structure:

```tsx
// plugins/consulting/skills/{skill}/dashboard/page.tsx
import { HubOverviewWidgets } from '@/components/bridge/HubOverviewWidgets';
import { PluginDataBrowser } from '@/components/bridge/PluginDataBrowser';
import { ExternalSourcesSection } from '@/components/bridge/ExternalSourcesSection';

export default function HubOverviewPage() {
  const hubId = '{hub-id}';
  const skillPath = 'plugins/consulting/skills/{skill}';

  return (
    <div className="space-y-6">
      {/* Section 1: Top Widgets — hub-specific metrics */}
      <HubOverviewWidgets hubId={hubId} />

      {/* Section 2: Plugin Data Browser — auto-scanned from data/ */}
      <PluginDataBrowser skillPath={skillPath} />

      {/* Section 3: External Sources — Connect button + connected data */}
      <ExternalSourcesSection hubId={hubId} />
    </div>
  );
}
```

`ExternalSourcesSection` is a composite component that renders:
- Section header with "External Sources" title and `BridgeConnectButton` on the right
- `ConnectedSources` — list of connections with disconnect buttons
- `ExternalDataCards` — stat cards from summaries
- `FileActions` — AI analyze + open buttons
- Empty state with "Connect a data source" prompt when no connections exist

**Key rules**:
1. Every hub overview MUST have all three sections
2. Top Widgets may be empty (component handles empty state gracefully)
3. Plugin Data Browser always shows something (every skill has a `data/` folder)
4. External Sources shows empty state with "Connect a source" prompt when no connections exist
5. Hub-specific custom content (charts, tables, timelines) goes BELOW the three standard sections

---

### Refactoring Plan: Existing Hub Overviews

#### Current State

| Hub | Current Overview | Issues |
|-----|-----------------|--------|
| **Career** | Server component, reads YAML directly, custom stat cards, custom tool grid, connected hubs section | No plugin data browser, no external sources, stat cards are hardcoded, no bridge integration |
| **Finance** | Client component, fetches from API, 4 metric cards, accounts/transactions lists, balance sheet, goals | Most complex, has custom widgets that should become Top Widgets, no plugin data browser, no bridge |
| **Health** | Client component, fetches from 3 APIs, overview counts, symptoms/medications grids, timeline | Custom layouts for symptoms/meds, no plugin data browser, no bridge |

#### Refactoring Strategy

**Approach**: Finance-first. Build all src/lib components against the Finance hub, iterate on the template until it works well, then roll out to the remaining 11 hubs.

**Key insight**: The Overview template is powerful enough to **replace entire sub-pages** that are just file listings or document browsers. It also **replaces blocks** in remaining pages (like "Related Hubs" sections). After refactoring, hubs should be leaner — fewer tabs, more on the Overview.

##### Phase 0: Shared Components + Move Connect Button

Build all template components and remove `BridgeConnectButton` from layout headers.

| Step | Change |
|------|--------|
| 1 | Remove `BridgeConnectButton` import and usage from all 12 `layout.tsx` files |
| 2 | Revert header `<div>` from `flex items-center justify-between` back to `flex items-center gap-3` |
| 3 | Create `ExternalSourcesSection.tsx` — composite component that renders section header with Connect button, `ConnectedSources`, `ExternalDataCards`, `FileActions` |
| 4 | Create `PluginDataBrowser.tsx` + `GET /api/bridge/plugin-data` API route |
| 5 | Create `HubOverviewWidgets.tsx` — merges custom widgets + bridge summaries |
| 6 | Create `DisconnectModal.tsx` — disconnect-only vs disconnect-and-delete |
| 7 | `BridgeConnectButton.tsx` remains as-is (reused inside `ExternalSourcesSection`) |

**Files modified**: All 12 `plugins/consulting/skills/{skill}/dashboard/layout.tsx`
**Files created**:
- `src/dashboard/components/bridge/ExternalSourcesSection.tsx`
- `src/dashboard/components/bridge/PluginDataBrowser.tsx`
- `src/dashboard/components/bridge/HubOverviewWidgets.tsx`
- `src/dashboard/components/bridge/DisconnectModal.tsx`
- `src/dashboard/app/api/bridge/plugin-data/route.ts`

##### Phase 1: Refactor Finance (Template Pilot)

Finance is the most complex hub (12 sub-pages, 6 tab groups). Refactoring it first proves the template works and reveals any gaps before rolling out to simpler hubs.

**Finance sub-page analysis**:

| Page | Tab Group | Current Content | Verdict |
|------|-----------|----------------|---------|
| **Overview** (page.tsx) | Overview | Key metrics, Accounts summary, Transactions, Goals, Balance Sheet, Related Hubs | **REWRITE** — use template |
| **Accounts** | Tracking | Account list with CRUD | **KEEP** — has its own data model |
| **Transactions** | Tracking | Filterable list with export | **KEEP** — has filtering/export logic |
| **Budget** | Tracking | Category-based plan vs actual | **KEEP** — has calculation logic |
| **Portfolio** | Investing | Holdings, gain/loss, allocation | **KEEP** — has its own API and views |
| **Crypto** | Investing | Filters portfolio by crypto type | **KEEP** — subset view of portfolio |
| **Real Estate** | Investing | Properties with folder paths and doc counts | **DELETE** — PluginDataBrowser + ExternalSourcesSection replaces this |
| **Goals** | Planning | Savings targets with progress | **KEEP** — has progress tracking logic |
| **Retirement** | Planning | Retirement savings progress | **KEEP** — has target calculations |
| **Taxes** | Planning | Transaction analysis for tax | **KEEP** — has analytics logic |
| **Calculators** | Planning | Links to local Excel spreadsheets | **DELETE** — ExternalSourcesSection replaces this (open-external mode) |
| **Documents** | Documents | Categorized file lists | **DELETE** — PluginDataBrowser + ExternalSourcesSection replaces this entirely |
| **Knowledge** | Knowledge | Static list of articles | **DELETE** — PluginDataBrowser replaces this (files in `data/knowledge/`) |

**Pages to DELETE** (4): Real Estate, Calculators, Documents, Knowledge
**Pages to KEEP** (7): Accounts, Transactions, Budget, Portfolio, Crypto, Goals, Retirement, Taxes

**Blocks to DELETE from remaining pages**:
- Related Hubs section (overview page) — redundant with sidebar
- Any "Connected Hubs" or "Related" sections in sub-pages

**Overview page rewrite**:

| Step | Change |
|------|--------|
| 1 | Replace entire `page.tsx` with the three-section template |
| 2 | **Top Widgets**: Net Worth, Total Assets, Cash, Monthly Income, Loans, Net Worth USD (from Balance Sheet API + summary API). Merge existing 4 metric cards + 6 balance sheet cards into one unified `HubOverviewWidgets` row |
| 3 | **Plugin Data Browser**: `skillPath="plugins/finance/skills/finance"` — shows `accounts.yaml`, `budget.yaml`, `goals.yaml`, `portfolio.yaml`, `transactions.yaml`, `knowledge/` folder. User can open, copy path, or take into chat |
| 4 | **External Sources**: `ExternalSourcesSection hubId="finance"` — Connect button, connected folders (e.g. `~/Documents/Finance`), stat cards from Excel extractions, AI analyze + open buttons for PDFs/spreadsheets |
| 5 | Delete the Accounts summary block (user clicks Accounts tab for detail) |
| 6 | Delete the Recent Transactions block (user clicks Transactions tab for detail) |
| 7 | Delete the Goals Progress block (user clicks Goals tab for detail) |
| 8 | Delete the Balance Sheet section (absorbed into Top Widgets via bridge summary) |
| 9 | Delete the Related Hubs component and import |

**Tab group changes** (update `dashboard.yaml`):

| Before | After |
|--------|-------|
| Overview, Tracking (Accounts, Transactions, Budget), Investing (Portfolio, Crypto, Real Estate), Planning (Goals, Retirement, Taxes, Calculators), Documents, Knowledge | Overview, Tracking (Accounts, Transactions, Budget), Investing (Portfolio, Crypto), Planning (Goals, Retirement, Taxes) |

**Files deleted**:
- `plugins/finance/skills/finance/augur/documents/page.tsx`
- `plugins/finance/skills/finance/augur/knowledge/page.tsx`
- `plugins/finance/skills/finance/augur/calculators/page.tsx`
- `plugins/finance/skills/finance/augur/realestate/page.tsx`
- `plugins/finance/skills/finance/augur/components/RelatedHubs.tsx` (if separate file)

**Files modified**:
- `plugins/finance/skills/finance/augur/page.tsx` — full rewrite
- `plugins/finance/skills/finance/augur.yaml` — remove deleted tabs

**Data folder contents** shown in PluginDataBrowser:
```
plugins/finance/skills/finance/augur/
├── accounts.yaml        [Open] [Copy] [Chat]
├── budget.yaml          [Open] [Copy] [Chat]
├── config.yaml          [Open] [Copy] [Chat]
├── connections.yaml     [Open] [Copy] [Chat]
├── goals.yaml           [Open] [Copy] [Chat]
├── portfolio.yaml       [Open] [Copy] [Chat]
├── transactions.yaml    [Open] [Copy] [Chat]
└── knowledge/           [Open] [Copy] [Chat]
    ├── rsu-guide.md
    ├── stock-strategy.md
    └── ...
```

**Verification after Finance pilot**:
- `npm run build` passes
- Navigate to `/finance` — three-section template renders correctly
- Connect button is in External Sources section, NOT in header
- Deleted tabs (Documents, Knowledge, Calculators, Real Estate) are gone from nav
- Remaining tabs (Accounts, Transactions, Budget, Portfolio, etc.) still work
- PluginDataBrowser shows all data files with working actions
- Template patterns documented and ready for rollout

##### Phase 2: Template Refinement

After Finance, review what worked and what didn't. Update the template components based on learnings before rolling out.

Questions to answer:
- Does the three-section layout feel right? Order correct?
- Is PluginDataBrowser showing too much or too little?
- Does the HubOverviewWidgets card grid look good with varying numbers of metrics?
- Is the ExternalSourcesSection empty state clear enough for hubs with no connections?
- Any missing actions? (e.g., "Edit in VS Code" for YAML files)

##### Phase 3: Roll Out to Remaining Hubs

Apply the proven template to the other 11 hubs. For each hub, audit which sub-pages are just file listings or document browsers — those get deleted, their content absorbed by the Overview.

**Priority order**:
1. Career, Health (most used, most sub-pages to audit)
2. Lifestyle, Eisenhower (have existing overview content)
3. Project-Dev, Venture-Augur (active use)
4. Content, Home-Automation (simpler)
5. Client hubs: AI Consulting, SMB Design, Terminal Automation (lowest priority)

**Per-hub checklist**:
- [ ] Audit sub-pages: which are file-listings that the Overview replaces?
- [ ] Delete replaced pages and update `dashboard.yaml` tabs
- [ ] Rewrite `page.tsx` with template (Widgets + PluginDataBrowser + ExternalSourcesSection)
- [ ] Remove "Related Hubs" / "Connected Hubs" blocks from any remaining sub-pages
- [ ] Verify build + navigation

#### Implementation Files

| New Component | Path |
|---------------|------|
| `ExternalSourcesSection` | `src/dashboard/components/bridge/ExternalSourcesSection.tsx` |
| `HubOverviewWidgets` | `src/dashboard/components/bridge/HubOverviewWidgets.tsx` |
| `PluginDataBrowser` | `src/dashboard/components/bridge/PluginDataBrowser.tsx` |
| `DisconnectModal` | `src/dashboard/components/bridge/DisconnectModal.tsx` |
| Plugin data API | `src/dashboard/app/api/bridge/plugin-data/route.ts` |

| Modified (Phase 0 — remove Connect from header) | Source Path |
|--------------------------------------------------|-------------|
| All 12 hub layouts | `plugins/consulting/skills/{skill}/dashboard/layout.tsx` |

| Modified (Phase 1 — Finance pilot) | Source Path |
|-------------------------------------|-------------|
| Finance overview | `plugins/finance/skills/finance/augur/page.tsx` (rewrite) |
| Finance tabs | `plugins/finance/skills/finance/augur.yaml` (remove deleted tabs) |

| Deleted (Phase 1 — absorbed by Overview) | Source Path |
|------------------------------------------|-------------|
| Documents page | `plugins/finance/skills/finance/augur/documents/page.tsx` |
| Knowledge page | `plugins/finance/skills/finance/augur/knowledge/page.tsx` |
| Calculators page | `plugins/finance/skills/finance/augur/calculators/page.tsx` |
| Real Estate page | `plugins/finance/skills/finance/augur/realestate/page.tsx` |
| RelatedHubs component | `plugins/finance/skills/finance/augur/components/RelatedHubs.tsx` |

| Modified (Phase 3 — remaining hubs) | Source Path |
|--------------------------------------|-------------|
| 11 remaining hub overview pages | `plugins/consulting/skills/{skill}/dashboard/page.tsx` |
| Hub tab configs (where pages deleted) | `plugins/consulting/skills/{skill}/dashboard.yaml` |

## Consequences

### Positive

- **Two levels serve two audiences**: Dev imports whole workflows; operation user connects incrementally
- **L2 needs zero code gen**: connections.yaml + src/lib components = live data with no build step
- **Source adapter pattern**: Folder today, Notion/GDrive tomorrow — same UX, different backend
- **L1 calls L2**: Import creates the hub AND connects the source — no separate manual step
- **All files reach Knowledge hub**: Both levels register with Tier 3 (ADR-085)
- **L3 standardizes all hub overviews**: Consistent UX across all 12 apps/ hubs — users always know where to find their data
- **Plugin data browser makes config files accessible**: Users can browse, open, and chat about plugin config without knowing file paths
- **Connect + Disconnect flow is clean**: One-click connect, explicit disconnect choice (keep vs clean)

### Negative

- **L1 requires AI reasoning**: Flow analysis (what does the user DO with these files?) is non-deterministic. May require multiple user confirmations for complex folders
- **Stale data in L2**: If user modifies Excel, dashboard shows old values until refresh. Mitigated by "Refresh" button and optional daemon watcher
- **Source adapters add surface area**: Each new adapter needs testing and error handling for auth/connectivity. Mitigated by releasing folder-only first, adding others incrementally
- **L3 refactoring touches all 12 hub pages**: Risk of breaking existing hub-specific content. Mitigated by incremental approach (add template sections, keep existing content below)

### Neutral

- `/harden` and factory pipeline continue working independently
- Connect button lives in the External Sources section of each overview page — visible, contextual, no config gating
- connections.yaml lives in plugin data dir — gitignored for privacy, backed up by organizer
- Hub-specific custom content (charts, tables, timelines) coexists below the standard three sections

## Implementation Order

```
Phase 1: Shared Core (no L1/L2 dependency)
├── Step 1.1: Source adapter interface + FolderAdapter
├── Step 1.2: File analyzers (Excel, PDF, Notion, Directory, Generic)
├── Step 1.3: Integration planner (mode assignment engine)
├── Step 1.4: Excel reader script (openpyxl CLI)
├── Step 1.5: connections.yaml schema
└── Step 1.6: Generic bridge API routes (/api/bridge/*)

Phase 2: Level 2 — Connect (depends on Phase 1)
├── Step 2.1: ExternalDataCards.tsx src/lib component
├── Step 2.2: FileActions.tsx src/lib component
├── Step 2.3: ConnectSourceModal.tsx src/lib component
├── Step 2.4: Connect button in hub header (bridge.enabled flag)
├── Step 2.5: Wire modal → scan API → plan → write connections.yaml
└── Step 2.6: Register files with Knowledge Tier 3 on connect

Phase 3: Level 1 — /import (depends on Phase 1, uses Phase 2 at end)
├── Step 3.1: Extract stage runner from factory → src/lib module
├── Step 3.2: Flow analyzer (deep scan + user intent inference)
├── Step 3.3: Hub blueprint generator (scan → tabs/pages/actions plan)
├── Step 3.4: Code generator (blueprint → plugin files using factory templates)
├── Step 3.5: Auto-connect (call L2 flow at end to write connections.yaml)
└── Step 3.6: /import skill definition (SKILL.md)

Phase 4: Verification
├── Step 4.1: E2E test L2: Connect Finance hub to sample folder, verify cards render
├── Step 4.2: E2E test L1: /import sample folder, verify hub created + connected
├── Step 4.3: npm run build passes, all tests pass
└── Step 4.4: Update ADR status

Phase 5: Level 3 — Standardized Hub Overview Template
├── Step 5.0: Remove BridgeConnectButton from all 12 layout headers, revert header flex
├── Step 5.1: Create ExternalSourcesSection (composite: Connect button + ConnectedSources + ExternalDataCards + FileActions)
├── Step 5.2: Create PluginDataBrowser component + plugin-data API route
├── Step 5.3: Create HubOverviewWidgets component (merges plugin data + bridge summaries)
├── Step 5.4: Create DisconnectModal component (disconnect-only vs disconnect-and-delete)
├── Step 5.5: Finance pilot — rewrite overview, delete 4 absorbed pages, update tabs
├── Step 5.6: Template review (user checkpoint — iterate before rollout)
├── Step 5.7: Roll out template to remaining 11 hubs (delete absorbed pages per hub)
└── Step 5.8: Verification — all 12 hubs follow template, build passes
```

## Alternatives Considered

### Alternative 1: Single Command for Both Levels

One `/bridge` command that handles both creating hubs and connecting sources.

**Rejected because**: The two operations have fundamentally different outputs (code vs config), different audiences (dev vs operation user), and different triggers (CLI vs UI button). Merging them creates a confusing UX — "does this generate code or just write config?" Keeping them separate makes intent clear.

### Alternative 2: Connect Button Generates Code Per Hub

Each Connect creates custom API routes and components for that specific hub.

**Rejected because**: Code generation requires a build step (`npm run build`), which breaks the "click and see data" UX of L2. By making L2 config-only with src/lib components, the user sees results immediately on page refresh. This also means a single set of bridge components to maintain, not N per hub.

### Alternative 3: Full File Migration (Import Everything as Augur Data)

Parse all external files, store data in Augur's `data/` directory, make dashboard the source of truth.

**Rejected because**: Users explicitly don't want this. A balance sheet with formulas, conditional formatting, and macros should stay in Excel. The bridge reads summaries and provides AI analysis without replacing the originals. "Some data will be read from Excel for summary... and in addition there will be a button to analyze with AI or even just to open it."

## References

- ADR-065 — Dashboard Hardening Workflow (`/harden`)
- [ADR-027](./ADR-027-mcp-app-factory-refactoring.md) — MCP App Factory (factory pipeline)
- [ADR-040](./ADR-040-portable-plugin-template-standard.md) — Plugin Template Standard (profiles, templates)
- [ADR-085](./ADR-085-rag-three-tier-index.md) — RAG Three-Tier Index (Tier 3 external files)
- [ADR-082](./ADR-082-knowledge-hardening.md) — Knowledge Hub Hardening
- `plugins/ai/skills/mcp-app-factory/scripts/workflow/engine.py` — Factory workflow engine
- `plugins/dev/skills/frontend/scripts/dashboard_hardening_audit.py` — Hardening audit engine
- `plugins/ai/skills/mcp-app-factory/plugin-spec.yaml` — Plugin specification

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-086: Hub Data Bridge — Two-Level External Data Integration**.

Read the full ADR: `docs/decisions/ADR-086-hub-data-bridge.md`

### Offload Protocol (ADR-054)

Before dispatching each step, check if it can be offloaded to a cheap CLI:

1. Read offload config: `cat config/system/llm.yaml` → look for `offload:` section
2. If `offload.enabled: true` AND the step's tier is `low`:
   ```bash
   python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py \
     --task "STEP DESCRIPTION" \
     --files "TARGET_FILE_1,TARGET_FILE_2" \
     --context-files "REFERENCE_FILE_FOR_PATTERNS" \
     --work-dir $(pwd)
   ```
3. Review the JSON output — check `success`, `files_changed`, and `diff` fields
4. Record the verdict:
   - Accept: `--record-verdict accept`
   - Fix: `--record-verdict fix`
   - Escalate: `--record-verdict escalate`
5. If `offload.enabled: false` OR tier is `medium`/`high` → do the step yourself as normal

### Team Orchestration

Create a team and spawn teammates to execute the plan below:

1. **Create team**: `TeamCreate(team_name="adr-086-data-bridge", description="Implementing ADR-086: Hub Data Bridge")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role in the Execution Plan, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-086-data-bridge", name="{role}",
        model="{tier-model}", prompt="You are '{role}' on the adr-086-data-bridge team.
        Read your profile: .claude/agents/{role}.md
        Check TaskList for your assigned tasks. After each task: TaskUpdate to complete,
        SendMessage to team lead. If blocked, move to next available task.")
   ```
4. **Profile loading**: Each teammate MUST read `.claude/agents/{name}.md` for iron laws and constraints
5. **Communication**: Teammates use `SendMessage` to report completion, request reviews, and debate
6. **Dependencies**: PARALLEL phases -> spawn all at once. PIPELINE phases -> use task blocking
7. **Review cycle**: After implementation, validator reviews changes and debates with developer via `SendMessage`
8. **Shutdown**: When all phases pass, send `shutdown_request` to all teammates, then `TeamDelete()`

**Model mapping**: `low` -> haiku, `medium` -> sonnet, `high` -> opus

### Execution Plan

**Team name**: `adr-086-data-bridge`

#### Phase 1: Shared Core
**Strategy**: PARALLEL (1.1–1.5 independent; 1.6 depends on 1.3+1.5)
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | Create source adapter interface: base class with `scan()`, `read_file()`, `list_files()` methods. Implement `FolderAdapter` — walks local directory, returns `ScanManifest` with file list + basic metadata (name, type, size, modified). | `plugins/dev/skills/frontend/scripts/source_adapters/base.py`, `plugins/dev/skills/frontend/scripts/source_adapters/folder.py` |
| 1.2 | developer | medium | Create file analyzers: `ExcelAnalyzer` (openpyxl: sheets, columns, row counts, totals detection), `PdfAnalyzer` (page count via `mdls`/`PyPDF2`, text extractable, section headings), `NotionAnalyzer` (markdown heading parse, table detection), `DirectoryAnalyzer` (file count, dominant type), `GenericAnalyzer` (name/type/size). Each returns `FileStructure` dict. Wire into FolderAdapter.scan(). | `plugins/dev/skills/frontend/scripts/file_analyzers/__init__.py`, `plugins/dev/skills/frontend/scripts/file_analyzers/excel.py`, `plugins/dev/skills/frontend/scripts/file_analyzers/pdf.py`, `plugins/dev/skills/frontend/scripts/file_analyzers/notion.py`, `plugins/dev/skills/frontend/scripts/file_analyzers/directory.py`, `plugins/dev/skills/frontend/scripts/file_analyzers/generic.py` |
| 1.3 | developer | medium | Create integration planner: mode assignment engine. Input: `ScanManifest`. Output: `connections.yaml` draft. Rules: Excel with totals → summary + open-external; PDF with text → ai-analyze + open-external; directory → open-external; CSV/simple-xlsx with <100 rows → page-candidate (L1 only); dated/small → ignore. Configurable via user overrides. | `plugins/dev/skills/frontend/scripts/integration_planner.py` |
| 1.4 | developer | medium | Create `excel_reader.py` CLI: `--file path.xlsx --extractions '[{"sheet":"Summary","cell":"B42","label":"Total"}]'`. Returns JSON array `[{"label":"Total","value":125000,"formatted":"$125,000.00"}]`. Uses openpyxl. Graceful fallback if not installed. Also supports `--file path.csv --columns '["Total"]'` for CSV. | `plugins/dev/skills/frontend/scripts/excel_reader.py` |
| 1.5 | developer | low | Create `connections.yaml` JSON Schema: `plugins/dev/skills/frontend/schemas/connections.schema.yaml`. Fields: version, hub, connections[] → {id, source_type, source_path, connected_at, integrations[] → {id, file/files, mode, extractions[], action{}, display{}}, ignored[]}. | `plugins/dev/skills/frontend/schemas/connections.schema.yaml` |
| 1.6 | developer | medium | Create generic bridge API routes in `src/dashboard/app/api/bridge/`: `summary/route.ts` (GET ?hub= → reads connections.yaml, calls excel_reader.py, returns summaries), `connections/route.ts` (GET list / POST add / DELETE remove), `scan/route.ts` (POST {hub, source_type, path} → calls folder_scanner via subprocess, returns manifest), `refresh/route.ts` (POST ?hub= → re-extract all summaries). All use `getProjectRoot()` pattern. | `src/dashboard/app/api/bridge/summary/route.ts`, `src/dashboard/app/api/bridge/connections/route.ts`, `src/dashboard/app/api/bridge/scan/route.ts`, `src/dashboard/app/api/bridge/refresh/route.ts` |

#### Phase 2: Level 2 — Connect Button
**Strategy**: PIPELINE (2.1+2.2 parallel → 2.3 → 2.4+2.5 parallel → 2.6)
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | frontend | medium | Create `ExternalDataCards.tsx` — fetches `/api/bridge/summary?hub={hubId}`, renders GlassCard per extraction (label, formatted value, source file indicator). Shows loading skeleton, error state, empty state ("No connected sources"). Includes "Refresh" button and "Last updated" timestamp. "Open source file" link per card. | `src/dashboard/components/bridge/ExternalDataCards.tsx` |
| 2.2 | frontend | medium | Create `FileActions.tsx` — reads integrations from `/api/bridge/connections?hub={hubId}`, renders action buttons for ai-analyze (flow: llm, passes file path + prompt_context to IDE chat) and open-external (calls `system-open-file` MCP tool). Uses lucide-react icons from connections.yaml. Groups by integration type. | `src/dashboard/components/bridge/FileActions.tsx` |
| 2.3 | frontend | medium | Create `ConnectSourceModal.tsx` — modal with: source type selector (Folder active, Notion/GDrive disabled with "Coming soon"), path input with folder picker hint, "Scan" button that calls `POST /api/bridge/scan`. After scan: shows file table with mode dropdown per file (summary/ai-analyze/open/ignore). "Connect" button writes via `POST /api/bridge/connections`. | `src/dashboard/components/bridge/ConnectSourceModal.tsx` |
| 2.4 | frontend | medium | Add Connect button to hub header: in `src/dashboard/components/layout/HubHeader.tsx` (or equivalent), add a `📎 Connect` button that opens ConnectSourceModal. Only visible when `bridge.enabled: true` in hub's dashboard.yaml. Read flag from generated-registry.ts or dashboard.yaml at runtime. | `src/dashboard/components/layout/HubHeader.tsx` or equivalent hub layout |
| 2.5 | frontend | medium | Add "Connected Sources" section to hub overview pages: shows current connections (source path, file count, last refreshed) with disconnect button. Uses `/api/bridge/connections?hub={hubId}`. This section appears automatically when connections.yaml exists for the hub — no per-hub code needed. | `src/dashboard/components/bridge/ConnectedSources.tsx` |
| 2.6 | developer | low | On connect, register files with Knowledge Tier 3: in the `POST /api/bridge/connections` handler, after writing connections.yaml, loop through non-ignored integrations and call `POST /api/knowledge/hub-files` for each file (hub, path, tags from mode). Reference: ADR-085. | `src/dashboard/app/api/bridge/connections/route.ts` |

#### Phase 3: Level 1 — /import
**Strategy**: PIPELINE (3.1 → 3.2 → 3.3 → 3.4 → 3.5 → 3.6)
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | high | Extract generic stage runner from factory `engine.py` → `src/scripts/workflow_runner.py`. Classes: `Stage` (name, plan, execute, validate, questions), `WorkflowRunner` (stages list, state_dir, run, resume). Refactor factory engine.py to import src/lib runner. Verify: `python3 -m pytest tests/src/ -v`. | `src/scripts/workflow_runner.py`, `plugins/ai/skills/mcp-app-factory/scripts/workflow/engine.py` |
| 3.2 | developer | high | Create flow analyzer: `plugins/dev/skills/frontend/scripts/flow_analyzer.py`. Input: ScanManifest. Output: FlowAnalysis (suggested tabs, stat cards, actions, per-file data strategy). This is the AI-reasoning step — uses heuristics: Excel with multiple sheets → multiple tabs; monthly file series → time-based view; nested directories → folder browser tab; CSV with <100 rows → renderable table. Presents analysis to user for confirmation. | `plugins/dev/skills/frontend/scripts/flow_analyzer.py` |
| 3.3 | developer | medium | Create hub blueprint generator: `plugins/dev/skills/frontend/scripts/blueprint_generator.py`. Input: FlowAnalysis + user answers. Output: `blueprint.yaml` (hub config, tabs, content per tab, external-only files, rendered files). Schema: `plugins/dev/skills/frontend/schemas/blueprint.schema.yaml`. | `plugins/dev/skills/frontend/scripts/blueprint_generator.py`, `plugins/dev/skills/frontend/schemas/blueprint.schema.yaml` |
| 3.4 | developer | medium | Create import code generator: `plugins/dev/skills/frontend/scripts/import_codegen.py`. Input: blueprint.yaml. Output: plugin files (SKILL.md, dashboard.yaml, dashboard/page.tsx, dashboard/tabs/*.tsx, dashboard/layout.tsx, dashboard/loading.tsx, api/health/route.ts, api/data/route.ts for rendered files). Uses factory templates from `plugins/ai/skills/mcp-app-factory/templates/`. Generated pages import ExternalDataCards + FileActions from `@/components/bridge/`. | `plugins/dev/skills/frontend/scripts/import_codegen.py` |
| 3.5 | developer | medium | Create import workflow: `plugins/dev/skills/frontend/scripts/import_workflow.py`. Uses src/lib WorkflowRunner with 4 stages: DeepScan (folder scan + flow analysis), Blueprint (generate + user Q&A), CodeGen (generate plugin files), Connect (call L2's POST /api/bridge/connections to auto-connect). CLI: `--folder <path> [--hub <id>]`. | `plugins/dev/skills/frontend/scripts/import_workflow.py` |
| 3.6 | developer | low | Create `/import` skill definition: `plugins/ai/skills/ai_bridge/augur/skills/import/SKILL.md`. Usage: `/import ~/Documents/Finance` or `/import ~/Documents/Finance --hub finance`. Describe 4 stages, user questions, output. Sync via sync_agents.py. | `plugins/ai/skills/ai_bridge/augur/skills/import/SKILL.md` |

#### Phase 4: Verification
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task |
|------|-------|------|------|
| 4.1 | validator | medium | E2E test L2: create sample folder `tests/fixtures/bridge/` with sample.xlsx (3 sheets, totals row), sample.pdf (3 pages), sample.csv (20 rows), receipts/ (2 files). Connect to a test hub. Verify: connections.yaml written, `/api/bridge/summary` returns values, `/api/bridge/connections` lists files. |
| 4.2 | validator | medium | E2E test L1: run import workflow against `tests/fixtures/bridge/`. Verify: blueprint.yaml produced with correct tabs, plugin files generated, `npm run build` passes, connections.yaml auto-written. |
| 4.3 | validator | low | Full regression: `pytest tests/src/ -v`, `npm run build`, `npm run test`. Verify factory pipeline still works after stage runner extraction. No hardcoded paths (`python3 .github/scripts/audit_paths.py`). |
| 4.4 | validator | low | Update ADR-086 status to "Implemented". |

#### Phase 5: Level 3 — Standardized Hub Overview Template
**Strategy**: PIPELINE (5.0 first → 5.1–5.4 parallel → 5.5 Finance pilot → 5.6 review → 5.7 rollout → 5.8 verify)
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 5.0 | frontend | low | Remove `BridgeConnectButton` from all 12 apps/ hub layout headers. Revert the header `<div>` from `flex items-center justify-between` back to `flex items-center gap-3`. Remove `BridgeConnectButton` import line. The button will live inside `ExternalSourcesSection` on the overview page instead. For content and home-automation layouts (non-standard), remove the BridgeConnectButton wrapper elements entirely. | All 12 `plugins/consulting/skills/{skill}/dashboard/layout.tsx` files |
| 5.1 | frontend | medium | Create `ExternalSourcesSection.tsx` — composite client component that wraps `BridgeConnectButton`, `ConnectedSources`, `ExternalDataCards`, and `FileActions` into a single section. Renders a section header ("External Sources" title with `BridgeConnectButton` on the right). Below: `ConnectedSources` with disconnect buttons, then `ExternalDataCards`, then `FileActions`. When no connections exist, shows empty state: "No external sources connected" with the Connect button prominent. Props: `{ hubId: string }`. | `src/dashboard/components/bridge/ExternalSourcesSection.tsx` |
| 5.2 | frontend | medium | Create `PluginDataBrowser.tsx` — client component that fetches `GET /api/bridge/plugin-data?skill={skillPath}`, renders file list with name, type icon (from extension), size, last modified. Three action buttons per file: **Open** (calls `POST /api/bridge/open-file`), **Copy Path** (clipboard API), **Chat** (dispatches file path to chat input via custom event or callback prop). Handles empty state, loading skeleton, error. Also create the API route `src/dashboard/app/api/bridge/plugin-data/route.ts` that reads the plugin data directory, filters out `__pycache__`, `.DS_Store`, `*.pyc`, `node_modules`, returns file metadata. | `src/dashboard/components/bridge/PluginDataBrowser.tsx`, `src/dashboard/app/api/bridge/plugin-data/route.ts` |
| 5.3 | frontend | medium | Create `HubOverviewWidgets.tsx` — client component with props `{ hubId, customWidgets?: { label: string, value: string\|number, icon?: string, color?: string }[] }`. Renders a responsive grid of stat cards. Merges `customWidgets` (passed by hub page) with bridge summary values (fetched from `/api/bridge/summary?hub={hubId}`). Each card shows label, formatted value, optional trend indicator. If no widgets and no bridge summaries, renders nothing (null). | `src/dashboard/components/bridge/HubOverviewWidgets.tsx` |
| 5.4 | frontend | medium | Create `DisconnectModal.tsx` — modal triggered by delete button in `ConnectedSources`. Two radio options: "Disconnect only" (removes connection from connections.yaml, cleans RAG index, keeps source files) and "Disconnect and delete source data" (also removes cached/extracted data from runtime dir). Calls `DELETE /api/bridge/connections` with `{ hub, connectionId, deleteData: boolean }`. Update `ConnectedSources.tsx` to use `DisconnectModal` instead of direct delete. | `src/dashboard/components/bridge/DisconnectModal.tsx`, `src/dashboard/components/bridge/ConnectedSources.tsx` |
| 5.5 | frontend | medium | **Finance pilot** — full refactor of Finance hub as template proving ground. (a) Rewrite `page.tsx` with three-section template: `HubOverviewWidgets` (Net Worth, Total Assets, Cash, Monthly Income, Loans, Net Worth USD — merged from summary API + balance sheet API), `PluginDataBrowser` (skillPath: finance), `ExternalSourcesSection` (hubId: finance). (b) Delete 4 pages absorbed by Overview: `documents/page.tsx` (file listing → PluginDataBrowser), `knowledge/page.tsx` (article list → PluginDataBrowser shows `data/knowledge/`), `calculators/page.tsx` (Excel links → ExternalSourcesSection open-external), `realestate/page.tsx` (property docs → ExternalSourcesSection). (c) Delete `components/RelatedHubs.tsx`. (d) Update `dashboard.yaml` to remove deleted tabs (Documents, Knowledge, Calculators tab groups; Real Estate from Investing group). (e) Remove Accounts summary, Recent Transactions, Goals Progress, Balance Sheet blocks from overview — user clicks respective tabs for detail. | `plugins/finance/skills/finance/augur/page.tsx` (rewrite), `plugins/finance/skills/finance/augur.yaml` (update tabs), delete: `documents/page.tsx`, `knowledge/page.tsx`, `calculators/page.tsx`, `realestate/page.tsx`, `components/RelatedHubs.tsx` |
| 5.6 | — | — | **Template review** — manual review of the Finance pilot. Verify the template feels right. Iterate on component APIs, layout, and empty states before rolling out. Not an agent step — this is a user checkpoint. | — |
| 5.7 | frontend | medium | **Rollout to remaining 11 hubs** — apply the proven template. For each hub: (a) audit sub-pages — delete any that are just file listings absorbed by Overview, (b) rewrite `page.tsx` with template, (c) remove "Related Hubs" / "Connected Hubs" blocks from sub-pages, (d) update `dashboard.yaml` tabs. Priority: Career + Health first, then Lifestyle + Eisenhower, then Project-Dev + Venture-Augur, then Content + Home-Automation, then client hubs last. | All 11 remaining `plugins/consulting/skills/{skill}/dashboard/page.tsx` + `dashboard.yaml` files |
| 5.8 | validator | low | Verify all 12 hub overviews: `npm run build` passes, `npm run test` passes, each hub renders the three-section template correctly. Connect button appears in External Sources section (not header). Deleted tabs are gone from navigation. Visual check via Chrome MCP on finance (pilot) + 2 other hubs. |

### Completion Criteria

**L1/L2 (Implemented)**:
- [x] Source adapter interface + FolderAdapter working
- [x] File analyzers handle Excel, PDF, Notion MD, directories, generic files
- [x] Integration planner assigns modes and produces connections.yaml
- [x] Excel reader extracts cell values and returns formatted JSON
- [x] Generic bridge API (`/api/bridge/*`) serves summary data from connections.yaml
- [x] ExternalDataCards + FileActions render on any hub
- [x] ConnectSourceModal scans folder and writes connections.yaml (L2)
- [x] Connect button appears on all apps/ hub headers
- [x] Flow analyzer infers tabs/actions from folder structure (L1)
- [x] Import workflow generates plugin files from blueprint (L1)
- [x] L1 auto-connects via L2 at the end
- [x] All files registered in Knowledge Tier 3 (ADR-085)

**L3 Phase 0 — Shared Components (Pending)**:
- [ ] `BridgeConnectButton` removed from all 12 layout headers (moved to overview page)
- [ ] `ExternalSourcesSection` composite component (Connect button + sources + cards + actions)
- [ ] `PluginDataBrowser` component + `/api/bridge/plugin-data` API route
- [ ] `HubOverviewWidgets` component merges custom + bridge widgets
- [ ] `DisconnectModal` with disconnect-only vs disconnect-and-delete

**L3 Phase 1 — Finance Pilot (Pending)**:
- [ ] Finance overview rewritten with three-section template
- [ ] 4 Finance sub-pages deleted (Documents, Knowledge, Calculators, Real Estate)
- [ ] Finance `dashboard.yaml` tabs updated (removed deleted tab groups)
- [ ] Balance Sheet + summary metrics unified into Top Widgets
- [ ] RelatedHubs component deleted
- [ ] Connect button appears in External Sources section, NOT in layout header
- [ ] `npm run build` passes, deleted tabs gone from navigation

**L3 Phase 3 — Rollout (Pending)**:
- [ ] All 12 apps/ hubs follow the standardized overview template
- [ ] Redundant sub-pages deleted per hub (file listings absorbed by Overview)
- [ ] "Related Hubs" / "Connected Hubs" blocks removed from all sub-pages
- [ ] `npm run build` passes, all tests pass

### How to Run
```
# Option 1: Use /implement-adr
/implement-adr docs/decisions/ADR-086-hub-data-bridge.md

# Option 2: Paste this prompt into Claude Code
# The agent will create the team, spawn teammates, and coordinate
```
