---
status: Implemented
date: 2026-04-05
deciders:
  - Gur Sannikov
related:
  - ADR-491
  - ADR-490
hub: websites
tags: [hosting, seo, deploy, monitoring, dashboard]
superseded_by: null
---

# ADR-533: Websites Hub — Unified Website Management Dashboard

## Context

Three websites (augur.run, guriqo.com, danit-design.com) are all hosted on Hostinger but managed through disconnected tools: a Python CLI script for deploys, browser logins for the Hostinger panel, and 15 GEO/SEO skills in `.claude/skills/geo-*` for audits. There is no unified view of site status, deployment state, or SEO health across all sites. Deploying requires running a script + SCP manually. SEO audit results exist as skill outputs but are not persisted or visualized per-site.

Additionally, Anthropic's recent ban on third-party OAuth access (April 2026) made "no API key required" a competitive differentiator for augur.run — the website was updated to emphasize this, increasing the urgency of having a proper deploy pipeline.

## Decision

Create a new dashboard hub called **Websites** with 4 pages and a dedicated skill at `skills/websites/`.

### Hub Structure

```
websites/
├── Overview    (hub home — 3 site cards, quick actions, activity feed)
├── Hosting     (tabbed per site — deploy, versions, SSL, uptime)
├── SEO         (tabbed per site — audit scores, platform readiness, brand authority, findings, trends)
└── Reports     (generate PDF reports, comparison reports, download history)
```

### Skill: `skills/websites/`

- Owns the `websites` hub (`x-augur-config.hub.owner: true`)
- 8 MCP tools for status, hosting, versions, SEO, audits, and reports
- Sites config in `augur/data/sites.yaml` (3 sites, SSH alias, deploy methods)
- Deploy pipeline in `scripts/deploy.py` (package + SCP + extract + chmod)

### MCP Tools

| Tool | Type | Purpose |
|------|------|---------|
| `get-websites-status` | query | HTTP + SSL check for all 3 sites |
| `get-websites-overview` | query | Versions, last deploy, SEO scores summary |
| `get-websites-activity` | query | Recent activity log |
| `get-website-hosting` | query | Per-site hosting details |
| `list-website-versions` | query | List packaged zip versions |
| `get-website-seo` | query | Latest audit scores + findings |
| `list-website-audits` | query | Historical audit list |
| `list-website-reports` | query | List generated PDF reports |

### Site Configurations

| Site | Deploy | Source |
|------|--------|--------|
| augur.run | SCP + unzip via SSH alias `hostinger` | `~/Projects/Au-docs/venture-augur/website-working/` |
| guriqo.com | SCP + unzip (enterprise.html -> index.html) | Same working dir |
| danit-design.com | Hostinger Website Builder (Zyro) | Monitor only — no local source |

### SEO Integration with 15 GEO Skills

The SEO page integrates with all `.claude/skills/geo-*` skills:

- **Score cards**: Technical, Content, Schema, AI Visibility (from geo-audit sub-skills)
- **Platform Readiness**: 5 cards for Google AIO, ChatGPT, Perplexity, Gemini, Copilot (from geo-platform-optimizer)
- **Brand Authority**: Score 0-100 (from geo-brand-mentions)
- **9 audit buttons**: Full Audit, Technical, Content, Schema, Crawlers, Citability, Platform Optimization, Brand Mentions, Generate llms.txt
- **Reports**: Full GEO Report, Comparison, Executive Summary, Client Proposal, Brand Authority Report

All audits dispatch to IDE via `useActionRunner` (rule 10) and save results to `vault/websites/{domain}/audits/`.

### Dashboard Pages

Per rule 27, pages at `apps/dashboard/features/pages/websites/`:
- `overview/page.tsx` — site cards, quick actions, activity feed
- `hosting/page.tsx` — tabbed deploy, versions, SSL, uptime
- `seo/page.tsx` — scores, platform readiness, brand authority, audit buttons, findings, history
- `reports/page.tsx` — report generation and download history

### Data Storage

```
vault/websites/
├── activity.json               # Deploy/audit event log
├── augur.run/audits/            # SEO audit results (frontmatter .md)
├── augur.run/reports/           # Generated PDF reports
├── guriqo.com/audits/
├── guriqo.com/reports/
├── danit-design.com/audits/
└── danit-design.com/reports/
```

### Infrastructure: SSH Key Auth

SSH key authentication configured for passwordless deploys:
- Key: `~/.ssh/id_ed25519`
- Config alias: `hostinger` in `~/.ssh/config`
- Host: `82.29.199.38:65002`, user `u215419198`

## Consequences

### Positive

- One dashboard for all website operations — no more switching between CLI, browser, and terminal
- Deploy pipeline is one-click from the dashboard (dispatched to IDE)
- SEO audit history is persisted and visualized per-site with trend tracking
- File permissions are fixed automatically on deploy (`chmod 644` for files, `755` for dirs)
- Platform readiness scores surface AI search visibility gaps per site
- Reports can be generated for client work (danit-design.com)

### Negative

- SSH commands in MCP tools add latency (10-15s for disk usage, waitlist count)
- danit-design.com has limited management capability (monitor only, no deploy)
- SEO data depends on manually running audits — no automated scheduling yet

### Neutral

- The 15 GEO skills in `.claude/skills/` remain unchanged — the hub consumes their output
- The existing `skills/venture-augur/scripts/website_deploy.py` is not removed; the new `skills/websites/scripts/deploy.py` is a clean reimplementation

## Alternatives Considered

### Alternative 1: Extend venture-augur skill

Add website management pages to the existing venture-augur skill under the Career hub. Rejected because website management is a distinct domain from business development, and cross-hub contribution is not allowed (CLAUDE.md rule 13).

### Alternative 2: YAML config-driven pages only

Use the YAML block system (ADR-491) instead of custom TSX pages. Rejected because the pages need tabs, mutations, conditional rendering (SCP vs builder sites), and action dispatch — interactions the YAML system cannot express (CLAUDE.md rule 25).

## References

- Design spec: `docs/superpowers/specs/2026-04-05-websites-hub-design.md`
- Implementation plan: `docs/superpowers/plans/2026-04-05-websites-hub.md`
- SSH config: `~/.ssh/config` (hostinger alias)
- Deploy script: `skills/venture-augur/scripts/website_deploy.py` (original)
- GEO skills: `.claude/skills/geo-*` (15 skills)

## Implementation Prompt

> Already implemented. See `docs/superpowers/plans/2026-04-05-websites-hub.md` for the 10-task execution plan.

### Completion Criteria
- [x] Skill scaffold created at `skills/websites/`
- [x] 8 MCP tools registered and responding
- [x] 4 dashboard pages created and building
- [x] Hub mounted via `mount-plugins` with 0 orphans
- [x] `pnpm run build` passes
- [x] Vault directory structure created
- [x] SSH key auth working for deploys
- [x] Website permission fix deployed (chmod on unzip)
