# Career-Ops Import & Career Hub Migration

**Date:** 2026-04-06
**Status:** Draft
**Source:** https://github.com/santifer/career-ops

## Summary

Import santifer/career-ops as a standalone Augur skill that owns the `career` hub. Migrate MCP tools and dashboard pages from the existing career skill to read career-ops' data format. Re-hub non-job-search skills to a new `business` hub. Delete superseded skills.

## Decision Record

- **Approach:** Clone + Adapt (clone career-ops, restructure to Augur skill layout, port MCP tools, rewire dashboard pages)
- **Data authority:** Career-ops layout wins — vault reorganizes to match career-ops conventions
- **Dashboard strategy:** Slash commands for workflows + Next.js dashboard pages for visibility
- **Hub split:** Job search → career hub (career-ops), everything else → new business hub

## Skill Structure

```
skills/career-ops/
├── SKILL.md                          # Skill metadata, hub config, MCP tools, pages
├── README.md
├── commands/                         # 14 career-ops modes as Claude Code commands
│   ├── career-ops.md                 # Router (from .claude/skills/career-ops/SKILL.md)
│   ├── _shared.md                    # Shared context (from modes/_shared.md)
│   ├── auto-pipeline.md
│   ├── scan.md
│   ├── pdf.md
│   ├── batch.md
│   ├── tracker.md
│   ├── pipeline.md
│   ├── apply.md
│   ├── contacto.md
│   ├── deep.md
│   ├── oferta.md
│   ├── ofertas.md
│   ├── training.md
│   └── project.md
├── scripts/                          # Node.js tooling (kept as-is from career-ops)
│   ├── generate-pdf.mjs
│   ├── cv-sync-check.mjs
│   ├── verify-pipeline.mjs
│   ├── dedup-tracker.mjs
│   ├── merge-tracker.mjs
│   ├── normalize-statuses.mjs
│   └── mcp/                          # Python MCP tools (ported from career skill)
│       ├── __init__.py
│       ├── tools.py                  # Job pipeline CRUD
│       ├── tools_companies.py        # Company data reads
│       ├── tools_star.py             # STAR stories
│       ├── tools_resume.py           # CV management
│       └── tools_stats.py            # Job counts/stats for dashboard
├── assets/
│   ├── seeds/                        # Seed data templates
│   └── actions/                      # Action prompt templates (migrated from career skill)
├── references/
│   ├── workflow-interview-prep.md
│   └── scoring-system.md
├── templates/                        # CV and portal templates (from career-ops)
│   ├── cv-template.html
│   ├── portals.example.yml
│   └── states.yml
├── config/
│   └── profile.example.yml
├── augur/
│   ├── dashboard/
│   │   ├── pipeline/page.tsx
│   │   ├── companies/page.tsx
│   │   ├── star/page.tsx
│   │   ├── resume/page.tsx
│   │   ├── reports/page.tsx          # NEW — evaluation reports viewer
│   │   └── tsconfig.json
│   ├── pages/
│   └── tests/
└── evals/
```

**Key decisions:**
- Career-ops `modes/` → `commands/` (Augur convention)
- Node.js scripts stay in `scripts/` alongside Python MCP tools in `scripts/mcp/`
- Go TUI dashboard is NOT imported — replaced by Augur Next.js pages
- `fonts/`, `batch/`, `output/`, `jds/`, `reports/`, `data/` are runtime dirs in the vault
- Career-ops' `config/profile.example.yml` and `templates/` become skill assets
- New `reports/` dashboard page for career-ops evaluation reports

## Hub Configuration

### Career hub (owned by career-ops)

```yaml
hub:
  id: career
  owner: true
  title: Career
  nav_order: 20
  subtitle: AI-powered job search command center
  icon: Briefcase
  category: career
  iconBg: bg-cyan-500/20
  iconColor: text-cyan-400
  overview:
    search: true
    layout: masonry
```

### Business hub (new)

```yaml
hub:
  id: business
  owner: true
  title: Business
  nav_order: 25
  subtitle: Content, consulting, enterprise, and growth
  icon: Building2
  category: business
  iconBg: bg-amber-500/20
  iconColor: text-amber-400
```

Skills re-hubbed to business: `venture-augur`, `enterprise`, `consulting-template`, `content`, `linkedin-writer`, `post`, `design-content-pipeline`, `project-dev`, `growth`.

## Vault Data Layout

New vault path: `Au-vault/career-ops/`

```
Au-vault/career-ops/
├── cv.md                              # Master CV
├── article-digest.md                  # Proof points (optional)
├── config/
│   └── profile.yml                    # Candidate profile
├── portals.yml                        # Portal scanner config
├── data/
│   ├── applications.md                # Tracker (career-ops format)
│   ├── pipeline.md                    # Inbox of pending URLs
│   └── scan-history.tsv              # Scanner dedup
├── reports/                           # Evaluation reports
├── output/                            # Generated PDFs
├── interview-prep/
│   └── story-bank.md                 # STAR+R stories
├── companies/                         # Company research profiles
└── notes/
    ├── hard-skills/                   # Migrated from old vault
    └── learning/                      # Migrated from old vault
```

### Migration map

| Old path | New path | Transform |
|---|---|---|
| `career/job-analyzer/jobs/inbox/*.md` | `career-ops/data/applications.md` | Convert individual files → tracker rows |
| `career/job-analyzer/jobs/active/*.md` | `career-ops/data/applications.md` | Same, with status=active |
| `career/job-analyzer/jobs/archive/*.md` | `career-ops/data/applications.md` | Same, with status=archive |
| `career/job-analyzer/jobs/analyzed/*.md` | `career-ops/reports/` | Rename to career-ops report format |
| `career/job-analyzer/companies/` | `career-ops/companies/` | Direct move |
| `career/job-analyzer/profile/` | `career-ops/config/profile.yml` | Merge into career-ops profile format |
| `career/interview-prep/profile/cvs/*.md` | `career-ops/cv.md` + `career-ops/output/` | Primary CV → cv.md, variants → output/ |
| `career/interview-prep/profile/candidate.md` | `career-ops/config/profile.yml` | Merge into profile |
| `career/interview-prep/interviews/star-stories/` | `career-ops/interview-prep/story-bank.md` | Convert YAML files → markdown story bank |
| `career/notes/hard-skills/` | `career-ops/notes/hard-skills/` | Direct move |
| `career/learning/` | `career-ops/notes/learning/` | Direct move |
| `career/reports/` | `career-ops/reports/` | Direct move |

## MCP Tools

### Ported (rewired to new vault layout)

| Tool name | Reads from | Returns |
|---|---|---|
| `get-career-jobs` | `data/applications.md` | Job rows with status, score, date, company |
| `add-career-job` | Writes to `data/applications.md` | Success + new row |
| `update-career-job` | `data/applications.md` | Updated row |
| `delete-career-job` | `data/applications.md` | Success |
| `get-career-companies` | `companies/` | Company profiles list |
| `get-career-job-counts` | `data/applications.md` | Counts by status |
| `list-career-star` | `interview-prep/story-bank.md` | Parsed stories list |
| `list-career-resumes` | `output/` + `cv.md` | CV variants list |

### New

| Tool name | Reads from | Returns |
|---|---|---|
| `get-career-reports` | `reports/` | Evaluation reports list |
| `get-career-report` | `reports/{id}.md` | Single report content |

### Dropped (absorbed by career-ops modes)

- `tailor-resume` → `/career-ops pdf`
- `career-hardening-*` (5 tools) → **Requires user approval** (see below)
- `training-*` (4 tools) → `/career-ops training`
- `career-knowledge`, `career-learning` → notes in vault
- `career-read-cv`, `career-write-cv`, `career-create-cv`, `career-delete-cv` → `list-career-resumes` + `/career-ops pdf`
- `career-read-doc`, `career-write-doc` → generic file ops
- `manage-career-habits` → **Requires user approval** (see below)

## Dashboard Pages

All use `useMcpQuery` for data. No `fs` imports.

| Route | Type | Data source | Description |
|---|---|---|---|
| `/career/pipeline` | Rewired | `get-career-jobs` | Job table with status filters, stage moves, delete, add modal |
| `/career/companies` | Rewired | `get-career-companies` | Company research card grid with search |
| `/career/star` | Rewired | `list-career-star` | STAR+R stories table with category filters |
| `/career/resume` | Rewired | `list-career-resumes` | CV variants list with preview |
| `/career/reports` | New | `get-career-reports` | Evaluation reports list, expandable A-F detail |

**Dropped pages:**
- `/career/hard-skills` — notes in vault, no dedicated page
- `/career/interview` — agent-driven via `/career-ops` modes
- `/career/profile` — `config/profile.yml`, edited via onboarding

## Slash Commands

Router: `/career-ops` with 14 modes.

```
/career-ops              → Discovery menu
/career-ops {JD}         → Auto-pipeline (evaluate + PDF + tracker)
/career-ops scan         → Portal scanner (Playwright)
/career-ops pdf          → ATS CV generation (Puppeteer)
/career-ops batch        → Parallel evaluation
/career-ops tracker      → Status overview
/career-ops pipeline     → Process inbox URLs
/career-ops apply        → Form filling assistant
/career-ops contacto     → LinkedIn outreach
/career-ops deep         → Deep company research
/career-ops oferta       → Single evaluation A-F
/career-ops ofertas      → Compare multiple offers
/career-ops training     → Evaluate course/cert
/career-ops project      → Evaluate portfolio project
```

## Functionality Requiring Approval Before Deletion

| Capability | Old location | Career-ops equivalent | Decision needed |
|---|---|---|---|
| `career-hardening-*` (quiz, reading, report, attachments, collectors) | `skills/career/scripts/` (5 MCP tools + 5 Python scripts) | No direct equivalent. Career-ops `training` mode evaluates courses, not interactive quiz drilling. | **Drop or port?** |
| `manage-career-habits` | `skills/career/scripts/mcp/tools.py` | No equivalent | **Drop or port?** |
| Hard skills dashboard page | `skills/career/augur/dashboard/` | Notes in vault, no page | **Accept loss?** |

## Migration Sequence

| Phase | Action | Risk |
|---|---|---|
| 1 | Clone career-ops, restructure into `skills/career-ops/` | None |
| 2 | Write SKILL.md with hub config, MCP tools, pages | None |
| 3 | Port MCP tools to `scripts/mcp/`, point at new vault layout | Medium |
| 4 | Create `Au-vault/career-ops/`, copy templates | None |
| 5 | Migrate vault data (old → new format). Keep old dir as backup. | **High** |
| 6 | Create dashboard pages in `augur/dashboard/` | Low |
| 7 | Wire hub layout, mount pages | Low |
| 8 | Re-hub business skills (metadata change to `x-augur-hub: business`) | Low |
| 9 | Create business hub config in `venture-augur/SKILL.md` | Low |
| 10 | Browser-verify all dashboard pages show real data | None |
| 11 | Delete old skills (career, coach, interview-coach, auto-career-hub-coverage) — with approval | **High** |
| 12 | Clean up stale references | Low |

## Safety

- Phase 5: Old vault dir `Au-vault/career/` is NOT deleted — stays as backup
- Phase 10: Mandatory browser verification per CLAUDE.md rule 24
- Phase 11: Explicit approval before each skill deletion with capability diff

## Dependencies

- Node.js + npm (already required)
- Playwright: `npx playwright install chromium` (for portal scanning + PDF)
- No Go dependency (TUI dropped)

## User Impact

| Before | After |
|---|---|
| `/career` with basic pipeline | `/career-ops` with 14 specialized modes |
| Dashboard at `/career/pipeline` | Same URL, richer data from evaluation reports |
| STAR stories as individual YAML files | Single `story-bank.md` that grows with evaluations |
| Manual CV editing | `/career-ops pdf` generates ATS-optimized PDFs |
| No portal scanning | `/career-ops scan` with 45+ preconfigured companies |
| No batch evaluation | `/career-ops batch` with parallel workers |
| 13 skills in career hub | 1 skill (career-ops) + 9 skills in business hub |
