---
status: Implemented
date: '2026-02-12'
deciders:
- User
related:
- ADR-086 (Hub Data Bridge)
hub: null
tags:
- import
- finance
- hub
- documents
- finance
superseded_by: null
---

# ADR-090: Import Finance Hub from ~/Documents/Finance

## Context

Importing external data from `~/Documents/Finance` into Augur. A finance hub
already exists at `plugins/finance/skills/finance/` with 10 tabs (Overview, Accounts,
Transactions, Budget, Portfolio, Crypto, Real Estate, Goals, Retirement, Taxes).

The source folder contains **~133 files** across **8 directories**:

| Directory | Files | Types | Description |
|-----------|-------|-------|-------------|
| Calculators | 4 | .xlsx | Spreadsheet tools (Balance-Sheet, Real-Estate, AI-Risk, Research) |
| Real-estate | ~60 | .pdf, .docx, .xlsx | Property documents across 5 properties |
| Keep | 14 | .pdf, .xlsx | Important documents (tax reports, mortgage, BTC wallet, donations) |
| Union-Bank | 8 | .pdf | Bank documents (loans, trading fees, LLC docs) |
| Insurance | 5 | .pdf | Policies, annual reports |
| notion | 6 | .md | Notion export (RSU, options, stock strategies, income generation) |
| Strategies | 1 | .docx | Zero-Cost Collar guide for AVGO |
| Backup | 1 | .gsheet | Google Sheet backup (ignore) |

User requested a **full restructure** of the existing finance hub with **separate tabs
per document category**.

Two additional requirements:

1. **Notion migration**: The `notion/` folder content must be fully migrated into Augur
   (copied to plugin data, rendered natively in dashboard). Original folder deleted after
   verification.
2. **Live Balance Sheet**: A Python script reads `Balance-Sheet.xlsx` via openpyxl and
   serves live financial metrics (net worth, assets, loans, cash) to the dashboard via
   an API route. A "Refresh" button on the overview triggers re-extraction.

## Decision

### Approach: Enhance Existing Hub

Rather than creating a new plugin, restructure the existing `plugins/finance/skills/finance/`
hub by adding 3 new tabs, 1 new tab group, and connecting `~/Documents/Finance` via
the bridge API. Existing tabs remain functional.

### Hub Configuration

| Field | Value |
|-------|-------|
| Hub ID | `finance` |
| Title | Finance |
| Bundle | `apps` |
| Icon | DollarSign |
| Plugin path | `plugins/finance/skills/finance/` |

### Tab Structure (13 tabs, 5 groups)

| Group | Tab ID | Label | Status | Source |
|-------|--------|-------|--------|--------|
| overview | overview | Dashboard | MODIFY | Add ExternalDataCards from Balance-Sheet.xlsx |
| tracking | accounts | Accounts | KEEP | Existing |
| tracking | transactions | Transactions | KEEP | Existing |
| tracking | budget | Budget | KEEP | Existing |
| investing | portfolio | Portfolio | KEEP | Existing |
| investing | realestate | Real Estate | MODIFY | Add property document browser |
| investing | crypto | Crypto | KEEP | Existing |
| planning | **calculators** | **Calculators** | **NEW** | Excel files from Calculators/ |
| planning | taxes | Taxes | KEEP | Existing |
| planning | retirement | Retirement | KEEP | Existing |
| planning | goals | Goals | KEEP | Existing |
| documents | **documents** | **Documents** | **NEW** | Folder browser: Keep/, Union-Bank/, Insurance/ |
| knowledge | **knowledge** | **Knowledge** | **NEW** | Notion markdown + Strategies/ |

### New Tab Group

```yaml
- id: documents
  label: Documents
- id: knowledge
  label: Knowledge
```

### Calculators Tab (NEW)

Shows the 4 Excel spreadsheets from `Calculators/` with descriptions and open-in-app
actions:

| File | Description | Action |
|------|-------------|--------|
| Balance-Sheet.xlsx | Personal balance sheet | Open in Excel |
| Real-Estate.xlsx | Real estate investment calculator | Open in Excel |
| AI-Risk.xlsx | AI risk assessment model | Open in Excel |
| Research.xlsx | Investment research workbook | Open in Excel |

### Documents Tab (NEW)

Folder browser showing 3 document categories with file lists and open/analyze actions:

| Category | Files | Description |
|----------|-------|-------------|
| Keep | 14 | Tax reports, mortgage docs, BTC wallet backup, donations |
| Union-Bank | 8 | Bank documents, loans, trading fees |
| Insurance | 5 | Insurance policies, annual reports |

### Knowledge Tab (NEW) — Migrated Notion Content

The Notion markdown files are **fully migrated** into Augur's plugin data directory
at `plugins/finance/skills/finance/augur/knowledge/`. The Knowledge tab renders them
natively as formatted articles — no external file dependency.

**Migration steps**:
1. Copy `~/Documents/Finance/notion/Finance/*.md` to `plugins/finance/skills/finance/augur/knowledge/`
2. Rename files to clean slugs (strip Notion UUIDs): `what-is-rsu.md`, `intel-ldo.md`, etc.
3. Copy `~/Documents/Finance/Strategies/Zero-Cost-Collar-Guide-AVGO.docx` to data/knowledge/
4. Verify all content renders in the Knowledge tab
5. **Delete** `~/Documents/Finance/notion/` folder after verification

| Article | Migrated File |
|---------|---------------|
| What Is RSU and Why is it important | `data/knowledge/what-is-rsu.md` |
| INTEL LDO | `data/knowledge/intel-ldo.md` |
| Options vs. Shorts | `data/knowledge/options-vs-shorts.md` |
| Generate Ongoing Income from Stock Holdings | `data/knowledge/generate-income-from-stocks.md` |
| Stock Strategy | `data/knowledge/stock-strategy.md` |
| Zero-Cost Collar Guide (AVGO) | `data/knowledge/zero-cost-collar-avgo.docx` |

### Real Estate Tab (MODIFY)

Add a "Property Documents" section below existing portfolio view. Groups documents
by property:

| Property | Files | Location |
|----------|-------|----------|
| Pri Megadim (Nachalat Yitzhak 9) | ~25 | Real-estate/פרי מגדים/ |
| Emek Bracha 42 | ~15 | Real-estate/עמק ברכה42/ |
| Kiryat Ono | 2 | Real-estate/קרית אונו/ |
| Brooklyn | 3 | Real-estate/Brooklyn/ |
| Insurance (property) | 4 | Real-estate/ביטוחים/ |

### Live Balance Sheet Extraction

A Python script reads `Balance-Sheet.xlsx` via openpyxl and returns live financial
metrics as JSON. The dashboard calls this via an API route, and a "Refresh" button
triggers re-extraction.

**Script**: `plugins/finance/skills/finance/scripts/read_balance_sheet.py`

Reads from sheet "BS" in `~/Documents/Finance/Calculators/Balance-Sheet.xlsx`:

| Cell | Label | Example Value |
|------|-------|---------------|
| C17 | Total Assets | 11,922K ILS |
| E17 | Total Loans | 472K ILS |
| D22 | Net Worth | 11,449K ILS |
| D21 | Net Worth + Pension | 14,228K ILS |
| D23 | Net Worth USD | $4,622K |
| F22 | USD Exchange Rate | 3.078 |
| K10 | Monthly Income | 38.7K ILS |
| F5 | Cash Available | 3,513K ILS |

**Output format** (JSON):
```json
{
  "total_assets": 11922000,
  "total_loans": 472000,
  "net_worth": 11449000,
  "net_worth_with_pension": 14228000,
  "net_worth_usd": 4622000,
  "usd_exchange_rate": 3.078,
  "monthly_income": 38700,
  "cash_available": 3513000,
  "extracted_at": "2026-02-12T15:30:00Z"
}
```

**API Route**: `plugins/finance/skills/finance/augur/api/balance-sheet/route.ts`

- `GET /api/finance/balance-sheet` — runs the Python script, returns JSON metrics
- Called by the overview page on load and on "Refresh" button click

**Dependencies**: `openpyxl` — added to `plugins/finance/skills/finance/requirements.txt`

### Overview Page (MODIFY)

Add a `BalanceSheetMetrics` component that fetches from `/api/finance/balance-sheet`
and displays live financial metrics as stat cards (Net Worth, Total Assets, Total
Loans, Cash Available, Monthly Income, Net Worth USD). Include a "Refresh" button
that re-triggers extraction. Add `FileActions` component in sidebar for quick access
to calculators and key documents.

### External Data Connection

```yaml
version: 1
hub: finance
connections:
  - id: finance-folder
    source_type: folder
    source_path: ~/Documents/Finance
    connected_at: 2026-02-12T00:00:00Z
    integrations:
      # Calculators - open in native app
      - id: balance-sheet
        file: Calculators/Balance-Sheet.xlsx
        mode: open-external
        action:
          label: Open Balance Sheet
          icon: FileSpreadsheet
      - id: real-estate-calc
        file: Calculators/Real-Estate.xlsx
        mode: open-external
        action:
          label: Open Real Estate Calculator
          icon: FileSpreadsheet
      - id: ai-risk
        file: Calculators/AI-Risk.xlsx
        mode: open-external
        action:
          label: Open AI Risk Model
          icon: FileSpreadsheet
      - id: research
        file: Calculators/Research.xlsx
        mode: open-external
        action:
          label: Open Research Workbook
          icon: FileSpreadsheet
      # Real estate documents - folder browse
      - id: realestate-docs
        files: "Real-estate/**/*"
        mode: open-external
        action:
          label: Browse Property Documents
          icon: FolderOpen
      # Keep - important documents
      - id: keep-docs
        files: "Keep/*"
        mode: open-external
        action:
          label: Browse Important Documents
          icon: FolderOpen
      # Union Bank
      - id: union-bank-docs
        files: "Union-Bank/*"
        mode: open-external
        action:
          label: Browse Bank Documents
          icon: FolderOpen
      # Insurance
      - id: insurance-docs
        files: "Insurance/*"
        mode: open-external
        action:
          label: Browse Insurance Documents
          icon: FolderOpen
      # Balance sheet - live extraction
      - id: balance-sheet-live
        file: Calculators/Balance-Sheet.xlsx
        mode: summary
        extract:
          script: scripts/read_balance_sheet.py
          cells: [C17, E17, D22, D21, D23, F22, K10, F5]
        action:
          label: Refresh Balance Sheet
          icon: RefreshCw
    ignored:
      - file: Backup/BS-Backup-31-11-2025.gsheet
        reason: Google Sheet backup, not directly openable
```

### Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `plugins/finance/skills/finance/augur.yaml` | MODIFY | Add calculators, documents, knowledge tabs + tab groups |
| `plugins/finance/skills/finance/augur/page.tsx` | MODIFY | Add BalanceSheetMetrics + FileActions to overview |
| `plugins/finance/skills/finance/augur/realestate/page.tsx` | MODIFY | Add property documents section |
| `plugins/finance/skills/finance/augur/calculators/page.tsx` | CREATE | Excel spreadsheet browser with open actions |
| `plugins/finance/skills/finance/augur/documents/page.tsx` | CREATE | Folder browser for Keep/, Union-Bank/, Insurance/ |
| `plugins/finance/skills/finance/augur/knowledge/page.tsx` | CREATE | Rendered migrated Notion articles + strategy content |
| `plugins/finance/skills/finance/augur/api/balance-sheet/route.ts` | CREATE | API route that runs Python script, returns JSON metrics |
| `plugins/finance/skills/finance/scripts/read_balance_sheet.py` | CREATE | openpyxl script extracting key cells from Balance-Sheet.xlsx |
| `plugins/finance/skills/finance/requirements.txt` | CREATE | Plugin dependency: openpyxl |
| `plugins/finance/skills/finance/augur/connections.yaml` | CREATE | External data source connection config |
| `plugins/finance/skills/finance/augur/knowledge/*.md` | CREATE | Migrated Notion articles (6 files) |

## Consequences

### Positive

- External financial data from `~/Documents/Finance` accessible in dashboard
- Property documents organized by property in the Real Estate tab
- Investment knowledge fully migrated into Augur — no external dependency on Notion folder
- Excel calculators one click away from the dashboard
- Live balance sheet metrics (net worth, assets, loans, cash) on overview with refresh
- `~/Documents/Finance/notion/` folder cleaned up after migration
- Follows existing bridge patterns (ADR-086) and plugin dependency pattern (ADR-018)

### Negative

- 3 new tab pages + 1 API route + 1 Python script added to codebase
- External folder path hardcoded in connections.yaml (not portable across machines)
- Hebrew filenames may cause display issues in some contexts
- openpyxl dependency added to finance plugin (requires `pip install`)
- Deleting `~/Documents/Finance/notion/` is irreversible (verify migration first)

### Neutral

- Existing 10 tabs remain unchanged and functional
- No database or external service dependencies

## Alternatives Considered

### Alternative 1: Create Separate Hub

Create a new "Finance Documents" hub separate from the existing finance hub.
Rejected because it fragments the financial data across two hubs.

### Alternative 2: Replace Existing Hub Entirely

Delete all existing tabs and rebuild from scratch around the document structure.
Rejected because existing tabs (Accounts, Transactions, Budget, etc.) serve
different purposes than document browsing and should be preserved.

### Alternative 3: Symlink-Based Integration

Symlink external files into the plugin data directory. Rejected because it breaks
the data separation principle (code vs data) and complicates backups.

## References

- ADR-086: Hub Data Bridge
- `/import` skill: `plugins/ai/skills/ai_bridge/augur/skills/import/SKILL.md`
- ExternalDataCards: `src/dashboard/components/bridge/ExternalDataCards.tsx`
- FileActions: `src/dashboard/components/bridge/FileActions.tsx`
- Existing finance hub: `plugins/finance/skills/finance/`

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.
> Auto-generated by `/import`. Edit if needed before running.

You are implementing **ADR-090: Import Finance Hub from ~/Documents/Finance**.

Read the full ADR: `docs/decisions/ADR-090-import-finance.md`

### Phase 1: Notion Migration + Configuration
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | low | Migrate Notion content: copy 5 .md files from `~/Documents/Finance/notion/Finance/` to `plugins/finance/skills/finance/augur/knowledge/`, rename to clean slugs (strip Notion UUIDs). Copy `Strategies/Zero-Cost-Collar-Guide-AVGO.docx` to same dir. Verify all 6 files present. | `plugins/finance/skills/finance/augur/knowledge/` |
| 1.2 | developer | medium | Update dashboard.yaml: add `documents` and `knowledge` tab groups, add `calculators`, `documents`, `knowledge` tabs with correct hrefs, icons, groups | `plugins/finance/skills/finance/augur.yaml` |
| 1.3 | developer | low | Create connections.yaml with all file integrations from the ADR Decision section | `plugins/finance/skills/finance/augur/connections.yaml` |
| 1.4 | developer | low | Create `requirements.txt` with `openpyxl>=3.1.0` | `plugins/finance/skills/finance/requirements.txt` |

### Phase 2: Balance Sheet Script + API
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Create `read_balance_sheet.py`: reads `~/Documents/Finance/Calculators/Balance-Sheet.xlsx` sheet "BS" via openpyxl. Extracts cells C17, E17, D22, D21, D23, F22, K10, F5. Outputs JSON to stdout. Handle missing file/cells gracefully. | `plugins/finance/skills/finance/scripts/read_balance_sheet.py` |
| 2.2 | frontend | medium | Create API route `GET /api/finance/balance-sheet`: spawns `read_balance_sheet.py`, returns JSON. Cache result for 5 minutes, refresh on explicit request param. | `plugins/finance/skills/finance/augur/api/balance-sheet/route.ts` |

### Phase 3: New Tab Pages
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | frontend | medium | Create Calculators tab: show 4 Excel files as cards with descriptions and "Open in Excel" buttons using FileActions pattern. Match existing finance page styling (glass-panel, page-header, etc.) | `plugins/finance/skills/finance/augur/calculators/page.tsx` |
| 3.2 | frontend | medium | Create Documents tab: folder browser with 3 categories (Keep, Union-Bank, Insurance). Each category is a collapsible section showing file names with open buttons. Use DashboardWidget pattern. | `plugins/finance/skills/finance/augur/documents/page.tsx` |
| 3.3 | frontend | medium | Create Knowledge tab: read migrated .md files from `data/knowledge/`, render as formatted articles with summaries. Include Zero-Cost Collar strategy (.docx as download link). Use GlassCard pattern. | `plugins/finance/skills/finance/augur/knowledge/page.tsx` |

### Phase 4: Modify Existing Pages
**Strategy**: PARALLEL

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | frontend | medium | Modify overview page: add `BalanceSheetMetrics` component that fetches `/api/finance/balance-sheet` and displays 6 stat cards (Net Worth, Total Assets, Total Loans, Cash Available, Monthly Income, Net Worth USD). Add "Refresh" button. Add `<FileActions hubId="finance" />` in sidebar. | `plugins/finance/skills/finance/augur/page.tsx` |
| 4.2 | frontend | medium | Modify Real Estate page: add "Property Documents" section below existing portfolio view. Group files by property (Pri Megadim, Emek Bracha, Kiryat Ono, Brooklyn, Insurance). Each property is a collapsible section with file open buttons. | `plugins/finance/skills/finance/augur/realestate/page.tsx` |

### Phase 5: Integration
**Strategy**: PIPELINE

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 5.1 | devops | low | Mount plugin pages via `npm run mount-plugins` in `src/dashboard/` | `src/dashboard/` |
| 5.2 | devops | low | Run `npm run build` in `src/dashboard/` to verify build passes | `src/dashboard/` |

### Phase 6: Verification + Cleanup
**Strategy**: PIPELINE

| Step | Agent | Tier | Task |
|------|-------|------|------|
| V.1 | validator | low | Run `npm run build` in `src/dashboard/` — must pass with zero errors |
| V.2 | validator | low | Verify new tabs render: `localhost:3000/finance/calculators`, `/documents`, `/knowledge` |
| V.3 | validator | low | Verify BalanceSheetMetrics renders on overview with live numbers |
| V.4 | validator | low | Verify Knowledge tab renders all 6 migrated articles |
| V.5 | validator | low | After all verification passes, delete `~/Documents/Finance/notion/` folder |

### Completion Criteria

- [ ] dashboard.yaml has 13 tabs across 5 groups
- [ ] connections.yaml has file integrations for ~/Documents/Finance
- [ ] 6 Notion/strategy files migrated to `data/knowledge/`
- [ ] `read_balance_sheet.py` extracts live metrics from Balance-Sheet.xlsx
- [ ] API route `/api/finance/balance-sheet` returns JSON metrics
- [ ] 3 new tab pages created (calculators, documents, knowledge)
- [ ] Overview page shows live Balance Sheet metrics with Refresh button
- [ ] Real Estate page shows property document browser
- [ ] Knowledge tab renders migrated Notion articles natively
- [ ] `npm run build` passes
- [ ] `~/Documents/Finance/notion/` deleted after verification
- [ ] ADR status updated to Accepted
