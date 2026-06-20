# Websites Hub — Design Spec

**Date:** 2026-04-05
**Status:** Draft
**Hub:** `websites` (new)
**Sites:** augur.run, guriqo.com, danit-design.com (all Hostinger)

## Problem

Three websites are managed through a mix of CLI scripts, browser logins, and slash commands. There is no unified view of site status, deployment state, or SEO health. Deploying requires running a Python script + SCP manually. SEO audits exist as skills but results aren't persisted or visualized per-site.

## Solution

A new dashboard hub called **Websites** with 4 pages: Overview, Hosting, SEO, and Reports. The hub provides a single pane of glass for all website operations — monitoring, deployment, SEO auditing, and reporting.

## Sites Configuration

| Site | Domain | Deploy Method | Local Source |
|------|--------|--------------|-------------|
| augur.run | augur.run | SCP + unzip via SSH alias `hostinger` | `~/Projects/Au-docs/venture-augur/website-working/` |
| guriqo.com | guriqo.com | SCP + unzip (built from augur working dir) | Same working dir, `enterprise.html` → `index.html` |
| danit-design.com | danit-design.com | Hostinger Website Builder (Zyro) | No local source — monitor only |

SSH config: `~/.ssh/config` alias `hostinger` → `82.29.199.38:65002` user `u215419198`, key `~/.ssh/id_ed25519`.

## Hub Structure

```
websites/
├── Overview    (hub home — all sites at a glance)
├── Hosting     (deploy, versions, SSL, uptime — tabbed per site)
├── SEO         (audit scores, findings, trends — tabbed per site)
└── Reports     (generate PDF reports, download history)
```

## Page 1: Overview

The hub landing page. Shows all 3 sites in a card grid with key metrics.

**Site Cards (3 columns):**
Each card shows:
- Status dot (green/red — HTTP 200 check)
- Domain name
- Current version (augur.run, guriqo.com) or "Builder" (danit-design.com)
- Last SEO score (overall GEO score, color-coded: green ≥75, yellow ≥50, red <50)
- SSL days remaining
- Site-specific metric: waitlist count (augur.run), inquiry count (guriqo.com), status only (danit-design.com)

**Quick Actions Row:**
- Deploy augur.run (most common action — primary button)
- Run SEO Audit (all sites) — dispatches to IDE
- Check Uptime (all sites)
- Generate Report — links to Reports page

**Recent Activity Feed:**
- Last 5 events: deploys, audits, SSL changes
- Stored in a simple JSON log file in vault

**Data sources:**
- `get-websites-status` MCP tool (new) — HTTP checks, SSL expiry for all 3 sites
- `get-websites-overview` MCP tool (new) — versions, last deploy, SEO scores
- `get-websites-activity` MCP tool (new) — recent activity log

## Page 2: Hosting

Tabbed view — one tab per site (augur.run | guriqo.com | danit-design.com).

### augur.run / guriqo.com tabs

**Status Section:**
- HTTP status (200/503/timeout)
- SSL certificate expiry date + days remaining
- Last deploy timestamp
- Current deployed version

**Deploy Section:**
- "Package & Deploy" button — triggers full pipeline:
  1. `website_deploy.py --action package --site {site}`
  2. `scp` zip to server via `hostinger` alias
  3. `ssh hostinger` unzip + chmod + cleanup
  4. Log deploy event
- Deploy is a mutation dispatched to IDE (rule 10 — no direct execution from dashboard)
- Shows deploy progress/result

**Version History:**
- Table: version, date, size
- Source: `ls ~/Projects/Au-docs/venture-augur/websites/*.zip`
- Rollback button per version (redeploys an older zip)

**Server Info:**
- Disk usage for `domains/{domain}/public_html/`
- File listing with sizes

### danit-design.com tab

**Status Section:**
- Same status/SSL monitoring as other tabs
- Last-Modified header from HTTP response

**Links Section:**
- "Open Site" → `https://danit-design.com`
- "Open Hostinger Panel" → `https://hpanel.hostinger.com`
- "Open Website Builder" → Hostinger Zyro editor link

No deploy section — this site is managed through the Hostinger builder.

**Data sources:**
- `get-website-hosting` MCP tool (new) — per-site status, SSL, versions, disk
- `deploy-website` MCP mutation (new) — wraps `website_deploy.py` pipeline
- `list-website-versions` MCP tool (new) — list zip versions

## Page 3: SEO

Tabbed view — one tab per site. Each tab shows full GEO/SEO audit data.

### Audit Scores Section

Radar chart or score cards showing 5 dimensions:
- Technical SEO (crawlability, indexability, performance, security)
- Content Quality (E-E-A-T, depth, readability)
- Schema / Structured Data (JSON-LD coverage, validation)
- AI Visibility (citability, AI crawler access, llms.txt)
- Platform Optimization (Google AI Overviews, ChatGPT, Perplexity readiness)

Each score is 0-100. Overall GEO score is weighted average.

### Platform Readiness Section

5 mini score cards for AI search platform readiness (from `geo-platform-optimizer`):
- Google AI Overviews
- ChatGPT Search
- Perplexity
- Google Gemini
- Bing Copilot

Each card shows a 0-100 readiness score with color coding.

### Brand Authority Card

Brand Authority Score (0-100) from `geo-brand-mentions` showing presence across Wikipedia, LinkedIn, YouTube, Reddit, and other platforms AI models use for entity recognition.

### Run Audit

Button to trigger audit — dispatches to IDE via `useActionRunner`:
- "Full Audit" — runs `/geo-audit {domain}`
- Individual checks: `/geo-technical`, `/geo-content`, `/geo-schema`, `/geo-crawlers`, `/geo-citability`
- "Platform Optimization" — runs `/geo-platform-optimizer {domain}`
- "Brand Mentions" — runs `/geo-brand-mentions {domain}`
- "Generate llms.txt" — runs `/geo-llmstxt {domain}`

Results are saved to vault as frontmatter markdown per ADR-404:
```
vault/websites/{domain}/audits/YYYY-MM-DD-audit.md
```

### Findings Section

Prioritized list of issues from the last audit:
- Priority: Critical / High / Medium / Low
- Category: Technical / Content / Schema / AI
- Description + recommendation
- Filterable by category and priority

### Trends Section

Simple line chart (or sparklines) showing score progression:
- X axis: audit dates
- Y axis: score per dimension
- Source: historical audit files in vault

**Data sources:**
- `get-website-seo` MCP tool (new) — latest audit scores + findings for a domain
- `list-website-audits` MCP tool (new) — historical audit list
- Audit results stored in `vault/websites/{domain}/audits/`

## Page 4: Reports

Generate and download professional PDF reports.

**Generate Report Section:**
- Select site (dropdown)
- Select report type:
  - Full GEO Audit Report (`/geo-report-pdf`)
  - Comparison Report — baseline vs current (`/geo-compare`)
  - Executive Summary (`/geo-report`)
  - Client Proposal (`/geo-proposal`)
  - Brand Authority Report (`/geo-brand-mentions`)
- "Generate" button — dispatches the corresponding command to IDE
- Generated PDFs saved to `vault/websites/{domain}/reports/`

**Report History:**
- Table: report name, date, site, type, size
- Download link per report
- Delete action

**Data sources:**
- `list-website-reports` MCP tool (new) — list generated reports
- Report generation dispatched to IDE via `useActionRunner`

## MCP Tools (New)

All tools registered under a new `websites` MCP module at `skills/websites/scripts/mcp/`.

| Tool | Type | Purpose |
|------|------|---------|
| `get-websites-status` | query | HTTP + SSL check for all 3 sites |
| `get-websites-overview` | query | Versions, last deploy, SEO scores summary |
| `get-websites-activity` | query | Recent activity log (deploys, audits) |
| `get-website-hosting` | query | Per-site hosting details (status, SSL, versions, disk) |
| `list-website-versions` | query | List packaged zip versions |
| `deploy-website` | mutation | Package + SCP + extract pipeline |
| `get-website-seo` | query | Latest audit scores + findings for a domain |
| `list-website-audits` | query | Historical audit list for a domain |
| `list-website-reports` | query | List generated PDF reports |

## Skill Structure

New skill: `skills/websites/`

```
skills/websites/
├── SKILL.md                    # x-augur-hub: websites, type: domain
├── scripts/
│   ├── mcp/
│   │   ├── __init__.py         # Tool registration
│   │   ├── tools_status.py     # Status, overview, activity tools
│   │   ├── tools_hosting.py    # Hosting, versions, deploy tools
│   │   └── tools_seo.py        # SEO, audits, reports tools
│   └── website_deploy.py       # Moved from venture-augur (or imported)
├── augur/
│   └── data/
│       └── sites.yaml          # Site config (domains, deploy methods, paths)
└── assets/
    └── seeds/
        └── sites.yaml          # Seed config for fresh installs
```

## Dashboard Pages

Per rule 27, custom pages go in `apps/dashboard/features/pages/websites/`:

```
apps/dashboard/features/pages/websites/
├── overview/page.tsx
├── hosting/page.tsx
├── seo/page.tsx
└── reports/page.tsx
```

Each page follows the existing pattern:
- `useMcpQuery` for data fetching
- `useMcpMutation` for deploy actions
- `useActionRunner` with `dispatch: 'ide'` for audit/report generation
- shadcn/ui components (Tabs, Card, Button, Badge, Table)
- GlassCard sections matching existing dashboard design

## Data Storage

```
vault/websites/
├── augur.run/
│   ├── audits/                 # SEO audit results (frontmatter .md)
│   └── reports/                # Generated PDF reports
├── guriqo.com/
│   ├── audits/
│   └── reports/
├── danit-design.com/
│   ├── audits/
│   └── reports/
└── activity.json               # Deploy/audit activity log
```

## Hub Registration

The hub is registered via the skill's `SKILL.md` frontmatter:

```yaml
x-augur-hub: websites
x-augur-config:
  hub:
    id: websites
    owner: true
    label: Websites
    icon: Globe
    order: 35
```

This creates the "Websites" entry in the sidebar between Career (30) and Life (40).

## Out of Scope

- Google Analytics integration (requires API key setup — future)
- Automated scheduled audits (use existing `/dev-loops` for now)
- Multi-user access control
- Site creation/deletion from the dashboard
- DNS record management
