---
status: Implemented
date: '2026-02-16'
deciders:
- Project owner
related:
- ADR-105 (plugin-driven tool scoping)
- ADR-016 (monorepo structure)
- ADR-018 (plugin self-containment)
hub: null
tags:
- hub
- rebalancing
- user
- journey
- driven
superseded_by: null
---

# ADR-108: Hub Rebalancing — User-Journey-Driven Plugin Grouping

## Context

### Terminology

```
Hub directory (plugins/{hub}/)     → Sidebar NAV SECTION header
  └── Skill (skills/{skill}/)      → Sidebar LINK (one page)
       └── Page with Tabs           → Tab bar within the page
```

A hub with 1 skill = a section with 1 link (e.g., career). A hub with 5 skills = a section with 5 links (e.g., productivity). Hub = nav group.

### Current State

The 13-hub structure has grown organically with significant imbalances:

| Nav Section | Links | Tabs | Problems |
|-------------|-------|------|----------|
| career | 1 | 15 | Monolith — mixes active job search and passive skill development |
| finance | 1 | 9 | Will grow — needs user journey split now before it becomes another monolith |
| health | 2 | 5 | Balanced |
| productivity | 5 | 29 | Grab-bag — Apple integrations, task mgmt, Google integrations, file cleanup, dev metrics are 4+ different user journeys |
| lifestyle | 2 | 14 | Content Studio (professional writing) misplaced next to recipes and movies |
| home | 1 | 7 | Missing from sidebar navigation entirely |
| business | 5 | 23 | Mixes 3 different audiences: client consulting, product venture, enterprise deployment |
| ai | 4 | 21 | Balanced |
| system | 6+ | 22+ | Grab-bag — mixes admin utilities, monitoring, settings, static pages |
| dev | 2 | — | Missing Project Dev which is in productivity |
| services | 1 | 3 | Legacy duplicate of system/daemon |
| custom | 0 | 0 | Empty |

### Design Questions Applied

For each proposed hub, we asked:
1. **What does the user want to accomplish?** — Define a single, clear user journey per hub
2. **What multi-step workflows does this require?** — Group pages that participate in the same workflows
3. **Which tools are needed?** — Align MCP tool scoping (ADR-105) with hub boundaries
4. **What domain knowledge should be embedded?** — Each hub should have a coherent knowledge domain

## Decision

### Complete Rebalancing Map

Every page in the system, current location → proposed location:

| Current Section | Page | Tabs | Proposed Section | Change | User Journey |
|---|---|---|---|---|---|
| | **CAREER** *("I'm looking for a job")* | | | | |
| career | overview, pipeline, companies, scoring, interview, star, resume, profile | 8 | **career** | SPLIT | Find → Score → Interview → Apply |
| | **GROWTH** *("I want to grow my skills")* | | | | |
| career | overview, knowledge, learning, guard, habits, hardening-report, quiz, history | 8 | **growth** (NEW) | SPLIT | Learn → Test → Reinforce → Monitor |
| | **FINANCE** *("Where is my money going?")* | | | | |
| finance | overview, accounts, transactions, budget | 4 | **finance** | SPLIT | Track income/expenses, manage budget |
| | **WEALTH** *("How do I grow & protect my money?")* | | | | |
| finance | overview, portfolio, crypto, goals, retirement, taxes | 6 | **wealth** (NEW) | SPLIT | Invest → Plan retirement → Optimize taxes |
| | **HEALTH** | | | | |
| health | Health Hub (2), Wearables (3) | 5 | **health** | STAY | Track health, device data |
| | **PRODUCTIVITY** *("I want to get things done")* | | | | |
| productivity | Eisenhower Matrix (6), Organizer (4) | 10 | **productivity** | STAY | Prioritize tasks, organize files |
| | **INTEGRATIONS** *("I want to sync external platforms")* | | | | |
| productivity | Apple (7), Google Workspace (5) | 12 | **integrations** (NEW) | MOVE | Access Apple/Google data |
| | **LIFESTYLE** *("I want to enjoy daily life")* | | | | |
| lifestyle | Lifestyle (8) | 8 | **lifestyle** | STAY | Recipes, movies, travel, reading |
| | **CREATIVE** *("I want to write & publish")* | | | | |
| lifestyle | Content Studio (6) | 6 | **creative** (NEW) | MOVE | Blog posts, books, newsletters |
| | **HOME** *("I want to control my home")* | | | | |
| home | Smart Home (7) | 7 | **home** | FIX | Lighting, climate, devices, scenes |
| | **CONSULTING** *("I'm delivering client work")* | | | | |
| business | AI Consulting (4), SMB Design (1), Bossa Nova (5) | 10 | **consulting** (NEW) | SPLIT | Client service delivery |
| | **VENTURE** *("I'm building the Augur product")* | | | | |
| business | Venture (9) | 9 | **venture** (NEW) | SPLIT | Strategy, GTM, sales, investors |
| | **ENTERPRISE** *("I'm deploying Augur to orgs")* | | | | |
| business | Enterprise (4) | 4 | **enterprise** (NEW) | SPLIT | Organizations, teams, deployment |
| | **AI** | | | | |
| ai | Platform (7), Knowledge (6), Install (3), Factory (5) | 21 | **ai** | STAY | AI infrastructure |
| | **ADMIN** *(tertiary — configure/maintain)* | | | | |
| *(static)* | Settings | — | **admin** (NEW) | ABSORB | App configuration |
| system | Cleanup (1), Updates (4), Scraper (4), Renderer (1) | ~10 | **admin** | MOVE | System maintenance |
| | **OBSERVE** *(tertiary — monitor/diagnose)* | | | | |
| system | Observe (9), Services/Daemon (3) | 12 | **observe** (NEW) | MOVE | Monitor system health |
| | **DEV** *(tertiary — developer tools)* | | | | |
| productivity | Project Dev (7) | 7 | **dev** | MOVE | Dev metrics & pipelines |
| *(static)* | Operations, Control | — | **dev** | STAY | DevOps, agent control |
| | **DELETED** | | | | |
| services | daemon (duplicate) | 3 | — | DELETE | Legacy |
| custom | *(empty)* | 0 | — | DELETE | Unused |

### 1. Split Career into Career + Growth

**Career** (active job search — "I'm looking for a job"):

| Tab | Purpose | Workflow Role |
|-----|---------|--------------|
| overview | Dashboard summary | Entry point |
| pipeline | Active job applications | Track → Score → Interview |
| companies | Target companies research | Research → Score |
| scoring | Job fit scoring | Filter → Prioritize |
| interview | Interview projects | Prepare → Practice |
| star | STAR stories for behavioral interviews | Prepare → Practice |
| resume | Resume/CV management | Tailor → Apply |
| profile | Professional profile | Maintain → Apply |

MCP tools: brightdata-scrape, brightdata-search (job discovery workflow)

**Growth** (professional development — "I want to grow my skills"):

| Tab | Purpose | Workflow Role |
|-----|---------|--------------|
| overview | Dashboard summary | Entry point |
| knowledge | Industry knowledge base | Capture → Review |
| learning | Courses and certifications | Discover → Track → Complete |
| guard | Career risk monitoring | Monitor → Alert |
| habits | Professional habits tracker | Define → Track → Review |
| hardening-report | Weekly analysis report | Generate → Review |
| hardening-quiz | Knowledge retention quizzes | Test → Reinforce |
| hardening-history | Quiz and report history | Review → Improve |

MCP tools: knowledge tools (learning and retention workflow)

**Rationale**: Different cadences (daily for active search vs. weekly for growth), different tools (scraping vs. knowledge), different entry points. A job hunter doesn't need habits clutter; a growth user doesn't need pipeline noise.

### 2. Split Finance into Finance + Wealth

**Finance** (money tracking — "Where is my money going?"):

| Tab | Purpose | Workflow Role |
|-----|---------|--------------|
| overview | Spending dashboard | Entry point |
| accounts | Bank accounts and balances | View → Reconcile |
| transactions | Income and expense log | Record → Categorize |
| budget | Budget vs actual spending | Set → Track → Adjust |

MCP tools: finance-summary, finance-accounts, finance-transactions, finance-budget, finance-import

**Wealth** (investing & planning — "How do I grow and protect my money?"):

| Tab | Purpose | Workflow Role |
|-----|---------|--------------|
| overview | Portfolio dashboard | Entry point |
| portfolio | Stock/bond holdings | Buy → Track → Rebalance |
| crypto | Cryptocurrency holdings | Buy → Track |
| goals | Financial goals (house, education) | Set → Track → Achieve |
| retirement | Retirement planning | Project → Optimize |
| taxes | Tax optimization | Analyze → Plan → Execute |

MCP tools: finance-portfolio, finance-goals, brightdata-scrape (market data)

**Rationale**: Daily spending tracking and monthly investment review are fundamentally different user modes. Budget anxiety and portfolio strategy require different mental states. Splitting early avoids a 15-tab monolith as finance features grow.

### 3. Rebalance Productivity → Productivity + Integrations

**Productivity** (task & file management — "I want to get things done"):

| Skill | Tabs | Purpose |
|-------|------|---------|
| Eisenhower Matrix | 6 | Task prioritization by urgency/importance |
| Organizer | 4 | Organize files — health docs, recipe images, finance receipts |

**Rationale**: Organizer stays in productivity because it serves user file workflows (arrange health docs, rename recipe photos, sort finance receipts) — not system admin.

**Integrations** (platform connectors — "I want to sync external platforms"):

| Skill | Tabs | Purpose |
|-------|------|---------|
| Apple | 7 | Notes, reminders, calendar, email, voice memos, screenshots |
| Google Workspace | 5 | Gmail, Calendar, Drive, Docs |

**Rationale**: Both are connector skills that bridge external platforms into Augur. Their user journey is "access my data from platform X" — distinct from productivity workflows. They share a common pattern: OAuth setup, sync configuration, data import.

### 4. Split Lifestyle → Lifestyle + Creative

**Lifestyle** (personal life — "I want to enjoy daily life"):

| Tab | Purpose | Workflow Role |
|-----|---------|--------------|
| overview | Dashboard | Entry point |
| recipes | Recipe collection | Find → Cook → Rate |
| shopping | Shopping lists | Plan → Buy |
| reading | Reading list | Discover → Read → Review |
| movies | Movie/series collection | Discover → Watch → Rate |
| places | Places to visit | Discover → Visit |
| travel | Travel planning | Plan → Book → Experience |
| ideas | Personal ideas notepad | Capture → Develop |

**Creative** (content creation — "I want to write and publish"):

| Tab | Purpose | Workflow Role |
|-----|---------|--------------|
| overview | Dashboard | Entry point |
| posts | Blog posts | Draft → Edit → Publish |
| books | Book projects | Outline → Write → Edit |
| newsletters | Newsletter management | Draft → Send → Track |
| notes | Writing notes | Capture → Organize |
| scripts | Scripts and screenplays | Draft → Revise |

**Rationale**: Writing blog posts, books, and newsletters is a professional/creative discipline with its own workflow (research → draft → edit → publish). It doesn't belong next to tracking recipes and movies. A user in "writing mode" and a user browsing movie recommendations are in completely different mental states.

### 5. Split Business → Consulting + Venture + Enterprise

**Consulting** (client service delivery — "I'm delivering work for clients"):

| Skill | Tabs | Purpose |
|-------|------|---------|
| AI Consulting | 4 | Non-profit AI consultancy: sessions, opportunities, showcase |
| SMB Design | 1 | SMB client design portal |
| Bossa Nova | 5 | Terminal automation client: automations, productization |
| LinkedIn Writer | 0 | LinkedIn content assistance (backend-only, no dashboard) |

**Rationale**: All four are client service engagements with src/lib workflows: client communication, deliverable tracking, session management.

**Venture** (product management — "I'm building the Augur product"):

| Tab | Purpose | Workflow Role |
|-----|---------|--------------|
| overview | Dashboard | Entry point |
| analytics | Product analytics | Measure → Analyze |
| strategy | Strategic planning | Plan → Execute |
| market | Market research | Research → Position |
| gtm | Go-to-market | Plan → Launch |
| sales | Sales pipeline | Prospect → Close |
| financials | Business financials | Track → Forecast |
| investors | Investor relations | Pitch → Update |
| media | Media and PR | Plan → Execute |

**Rationale**: Product venture management is a distinct user journey from client consulting. The user managing investors and GTM strategy is in a completely different mode than the user delivering client AI sessions.

**Enterprise** (Augur deployment — "I'm deploying Augur to organizations"):

| Tab | Purpose | Workflow Role |
|-----|---------|--------------|
| overview | Dashboard | Entry point |
| organizations | Organization management | Create → Configure |
| teams | Team administration | Create → Assign → Manage |
| settings | Enterprise settings | Configure → Deploy |

**Rationale**: Enterprise is a different product surface entirely — it's about deploying Augur to other organizations. The user here is an admin/deployer, not a consultant or product manager.

### 6. Split System → Admin + Observe

**Admin** (system configuration — "I want to configure and maintain my system"):

| Skill | Tabs | Purpose |
|-------|------|---------|
| Settings | — | App configuration (absorbed from standalone page) |
| System Cleanup | 1 | Free disk space, cache cleanup |
| Updater | 4 | Version management, migrations, plugins |
| Scraper | 4 | Web data extraction configuration |
| Renderer | 1 | Shared rendering utilities |
| Channels | 0 | Notification channel configuration (no dashboard) |

**Observe** (system monitoring — "I want to see what's happening"):

| Skill | Tabs | Purpose |
|-------|------|---------|
| Observe | 9 | Health, logs, MCP, agents, memory, sessions, self-heal |
| Daemon | 3 | Background service monitoring, jobs, notifications |
| Metrics | 0 | System metrics collection (no dashboard) |

### 7. Move Project Dev → Dev

**Dev** (developer tools — tertiary, dev-mode):

| Skill/Page | Tabs | Purpose |
|------------|------|---------|
| Project Dev | 7 | Commits, pipelines, codebase, throughput, telemetry, projects |
| Operations | — | DevOps workflow (static page) |
| Control | — | Agent control (static page) |

**Rationale**: Dev metrics, pipelines, and codebase analysis are developer tools — they belong with Operations and Control, not next to Eisenhower task management.

### 8. Fix Home Hub

The home-automation skill exists at `plugins/home/skills/home-automation/` with a `dashboard.yaml` but is **missing from `pluginNavItems`** in the generated registry. Fix: ensure the generate-tabs script picks it up and it appears in the Home sidebar section.

### 9. Remove Legacy

- **`plugins/ai/`**: Legacy duplicate. Daemon already in system → observe. Delete entirely.
- **`plugins/custom/`**: Empty directory. No skills. Delete.

### 10. Updated Navigation Order

```typescript
const HUB_SECTION_ORDER: string[] = [
  // Professional
  'career', 'growth',
  // Personal management
  'finance', 'wealth', 'health',
  // Daily life
  'productivity', 'integrations', 'lifestyle', 'creative', 'home',
  // Business
  'consulting', 'venture', 'enterprise',
  // AI
  'ai',
  // System (tertiary — collapsed by default)
  'admin', 'observe', 'dev',
];
```

Priority tiers:
- `tertiary`: admin, observe, dev (collapsed by default)
- `primary`: all others

## Consequences

### Positive

- **Clearer user journeys**: Each hub maps to one user goal, not a grab-bag
- **Balanced sections**: No section exceeds ~12 tabs; career drops from 15→8, productivity from 29→10
- **Coherent MCP scoping**: Tool scoping (ADR-105) aligns with user intent per hub
- **Future-proofed finance**: Split now at 9 tabs prevents a 15-tab monolith as features grow
- **Audience separation**: Client consulting, product venture, and enterprise deployment are 3 different users
- **Settings has a home**: No more floating standalone page
- **Home visible**: Actually appears in navigation
- **Legacy cleanup**: services and custom directories removed

### Negative

- **Migration effort**: ~100+ files to move/modify across plugins, dashboard, and navigation
- **Hub count increase**: 13 → 17 (but 2 old were dead, so active hubs go from 11 → 17)
- **More sidebar sections**: 17 sections may feel long — mitigated by tertiary collapse for admin/observe/dev
- **Cross-hub data sharing**: Growth needs career data, wealth needs finance data — requires dependency declarations
- **Bookmark breakage**: URLs like `/career/learning`, `/finance/portfolio` need redirects
- **Plugin-mount regeneration**: All auto-generated dashboard copies must be regenerated

### Neutral

- Plugin self-containment (ADR-018) maintained — each skill still owns its files
- No changes to health or AI hubs
- Core hub (executor, router, swarm) unchanged — backend only

## Implementation Order

```
Phase 1: Create new hub directories (PARALLEL)
├── Step 1: Create plugins/career/ with README.md
├── Step 2: Create plugins/finance/ with README.md
├── Step 3: Create plugins/productivity/ with README.md
├── Step 4: Create plugins/career/ with README.md
├── Step 5: Create plugins/consulting/ with README.md
├── Step 6: Create plugins/professional/ with README.md
├── Step 7: Create plugins/enterprise/ with README.md
├── Step 8: Create plugins/admin/ with README.md
└── Step 9: Create plugins/observability/ with README.md

Phase 2: Split career → career + growth (PARALLEL with Phases 3-6)
├── Step 10: Create growth skill (SKILL.md, dashboard.yaml with growth tabs)
├── Step 11: Move dashboard pages (knowledge, learning, guard, habits, hardening)
├── Step 12: Update career dashboard.yaml (trim to job-search tabs only)
└── Step 13: Wire growth data dependencies

Phase 3: Split finance → finance + wealth (PARALLEL with Phase 2)
├── Step 14: Create wealth skill (SKILL.md, dashboard.yaml)
├── Step 15: Move dashboard pages (portfolio, crypto, goals, retirement, taxes)
├── Step 16: Update finance dashboard.yaml (trim to tracking tabs only)
└── Step 17: Split finance MCP tools between finance and wealth dashboard.yaml

Phase 4: Rebalance productivity + lifestyle + business (PARALLEL with Phases 2-3)
├── Step 18: Move Apple + Google Workspace skills to plugins/productivity/skills/
├── Step 19: Move Content Studio skill to plugins/career/skills/
├── Step 20: Move AI Consulting + SMB Design + Bossa Nova to plugins/consulting/skills/
├── Step 21: Move Venture skill to plugins/professional/skills/
├── Step 22: Move Enterprise skill to plugins/enterprise/skills/
├── Step 23: Move Project Dev skill to plugins/dev/skills/
└── Step 24: Delete plugins/consulting/ (all skills moved out)

Phase 5: Redistribute system → admin + observe (PARALLEL with Phases 2-4)
├── Step 25: Move admin skills (cleanup, updater, renderer, scraper, channels)
├── Step 26: Move observe skills (observe, daemon, metrics)
├── Step 27: Create settings skill in admin (wrap standalone page)
└── Step 28: Delete plugins/admin/ (all skills moved out)

Phase 6: Fix home + remove legacy (PARALLEL with Phases 2-5)
├── Step 29: Fix home-automation nav visibility (ensure pluginNavItems generation)
├── Step 30: Delete plugins/ai/ (legacy)
└── Step 31: Delete plugins/custom/ (empty)

Phase 7: Update navigation + config (depends on Phases 2-6)
├── Step 32: Update navigation.ts (HUB_SECTION_ORDER, priorities, static items)
├── Step 33: Update CLAUDE.md hub references (count → 17)
└── Step 34: Regenerate tab registry + plugin-mount symlinks

Phase 8: Verification (depends on Phase 7)
├── Step 35: Run npm run build
├── Step 36: Run pytest tests/src/
├── Step 37: Verify sidebar navigation renders all 17 sections correctly
└── Step 38: Spot-check pages load in each new hub
```

## Alternatives Considered

### Alternative 1: Career 3-way split (Career + Interview + Growth)

Split career into three hubs: active pipeline, interview prep, and growth.

**Rejected because**: Interview prep (interview, star, resume, profile) is tightly coupled with the job search workflow. Separating them creates a 4-tab hub that users would constantly switch between while applying. The 2-way split (search vs. growth) maps to genuinely different user modes.

### Alternative 2: Keep finance as one hub with tab_groups

Use tab_groups (tracking, investing, planning) instead of splitting.

**Rejected because**: Finance will grow significantly — tax automation, bank integrations, investment analysis features are planned. Splitting at 9 tabs is easier than splitting at 20. The two user journeys ("where's my money going" vs. "how do I grow it") have different cadences (daily vs. monthly).

### Alternative 3: Keep business as one hub

Keep all business skills under one "Business" section.

**Rejected because**: Three fundamentally different audiences: (a) consultant delivering client work, (b) founder building a product, (c) admin deploying to enterprises. These users have different goals, different workflows, and will never cross-visit each other's pages during a session.

### Alternative 4: Organizer in admin instead of productivity

Move Organizer to admin hub as a system maintenance tool.

**Rejected because**: Organizer serves user file workflows — arrange health docs in the right place, rename recipe images, sort finance receipts. It's a personal productivity tool, not system administration. The user thinks "organize my stuff" not "maintain the system."

### Alternative 5: Keep system hub, reorganize internally

Use tab_groups or visual separators within one system hub.

**Rejected because**: Tab groups can't span 8 skills. Admin (configure/write) and observe (monitor/read) have opposite mental models. Separate hubs give proper navigation hierarchy and MCP tool scoping.

## References

- ADR-105: Plugin-driven tool scoping (hub boundaries determine MCP tool sets)
- ADR-016: Monorepo structure (hub directories under plugins/)
- ADR-018: Plugin self-containment (skills own their files)
- `src/dashboard/lib/navigation.ts` — Sidebar navigation configuration
- `src/dashboard/lib/tabs/generated-registry.ts` — Auto-generated tab registry
- `plugins/career/skills/career/augur.yaml` — Current career tab definition
- `plugins/finance/skills/finance/augur.yaml` — Current finance tab definition

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-108: Hub Rebalancing — User-Journey-Driven Plugin Grouping**.

Read the full ADR: `docs/decisions/ADR-108-hub-rebalancing.md`

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
   - Accept (diff is correct): `python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py --record-verdict accept`
   - Fix (you patched the output): `python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py --record-verdict fix`
   - Escalate (offload failed, you did it yourself): `python3 plugins/orchestration/skills/executor/scripts/offload_dispatcher.py --record-verdict escalate`
5. If `offload.enabled: false` OR tier is `medium`/`high` → do the step yourself as normal

### Team Orchestration

Create a team and spawn teammates to execute the plan below:

1. **Create team**: `TeamCreate(team_name="adr-108-hub-rebalancing", description="Implementing ADR-108: Hub Rebalancing")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role in the Execution Plan, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-108-hub-rebalancing", name="{role}",
        model="{tier-model}", prompt="You are '{role}' on the adr-108 team.
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

**Team name**: `adr-108-hub-rebalancing`

#### Phase 1: Create Hub Directories
**Strategy**: PARALLEL
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | low | Create `plugins/career/` with `README.md` (follow pattern from `plugins/career/README.md`) | `plugins/career/README.md` |
| 1.2 | developer | low | Create `plugins/finance/` with `README.md` | `plugins/finance/README.md` |
| 1.3 | developer | low | Create `plugins/productivity/` with `README.md` | `plugins/productivity/README.md` |
| 1.4 | developer | low | Create `plugins/career/` with `README.md` | `plugins/career/README.md` |
| 1.5 | developer | low | Create `plugins/consulting/` with `README.md` | `plugins/consulting/README.md` |
| 1.6 | developer | low | Create `plugins/professional/` with `README.md` | `plugins/professional/README.md` |
| 1.7 | developer | low | Create `plugins/enterprise/` with `README.md` | `plugins/enterprise/README.md` |
| 1.8 | developer | low | Create `plugins/admin/` with `README.md` | `plugins/admin/README.md` |
| 1.9 | developer | low | Create `plugins/observability/` with `README.md` | `plugins/observability/README.md` |

#### Phase 2: Split Career Hub
**Strategy**: PIPELINE (2.1-2.2 parallel, then 2.3, then 2.4)
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Create growth skill skeleton: `SKILL.md` and `dashboard.yaml` with tabs (overview, knowledge, learning, guard, habits, hardening-report, hardening-quiz, hardening-history). Hub id `growth`, title "Professional Growth", icon "TrendingUp". Include tab_groups (overview, development, hardening). Move relevant actions (harden-knowledge, update-learning-targets, get-reading-suggestions, add-course) and modals (add-course) from career. | `plugins/career/skills/growth/SKILL.md`, `plugins/career/skills/growth/augur.yaml` |
| 2.2 | developer | medium | Move dashboard page directories from career to growth: `knowledge/`, `learning/`, `guard/`, `habits/`, `hardening/` from `plugins/career/skills/career/augur/` to `plugins/career/skills/growth/augur/`. Update internal imports. | `plugins/career/skills/growth/augur/` |
| 2.3 | developer | medium | Update career `dashboard.yaml`: remove tab_groups (professional, tools, hardening), remove growth tabs, remove growth actions/modals. Update subtitle to "Job search, interviews, resume, and applications". Keep tab_groups (overview, job-search, interview-prep). | `plugins/career/skills/career/augur.yaml` |
| 2.4 | developer | low | Create `plugins/career/skills/growth/data/`. Add dependencies: `required: [knowledge, ai_bridge]`. | `plugins/career/skills/growth/augur.yaml` |

#### Phase 3: Split Finance Hub (PARALLEL with Phase 2)
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | medium | Create wealth skill: `SKILL.md` and `dashboard.yaml` with tabs (overview, portfolio, crypto, goals, retirement, taxes). Hub id `wealth`, title "Wealth & Investing", icon "TrendingUp". Include tab_groups (overview, investing, planning). Move relevant MCP tools (finance-portfolio, finance-goals) and actions (optimize-taxes) from finance. | `plugins/finance/skills/wealth/SKILL.md`, `plugins/finance/skills/wealth/augur.yaml` |
| 3.2 | developer | medium | Move dashboard page directories from finance to wealth: `portfolio/`, `crypto/`, `goals/`, `retirement/`, `taxes/` from `plugins/finance/skills/finance/augur/` to `plugins/finance/skills/wealth/augur/`. Update internal imports. | `plugins/finance/skills/wealth/augur/` |
| 3.3 | developer | medium | Update finance `dashboard.yaml`: remove investing/planning tab_groups, remove wealth tabs, remove wealth actions. Update subtitle to "Track spending, accounts, and budgets". Keep tab_groups (overview, tracking). Keep MCP tools: finance-summary, finance-accounts, finance-transactions, finance-budget, finance-import. | `plugins/finance/skills/finance/augur.yaml` |
| 3.4 | developer | low | Create `plugins/finance/skills/wealth/data/`. Add dependency on finance for src/lib account data. | `plugins/finance/skills/wealth/augur.yaml` |

#### Phase 4: Rebalance Productivity + Lifestyle + Business (PARALLEL with Phases 2-3)
**Strategy**: PARALLEL (all steps independent)
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | developer | low | Move Apple skill: `git mv plugins/productivity/skills/apple plugins/productivity/skills/apple` | `plugins/productivity/skills/apple/` |
| 4.2 | developer | low | Move Google Workspace skill: `git mv plugins/productivity/skills/google-workspace plugins/productivity/skills/google-workspace` | `plugins/productivity/skills/google-workspace/` |
| 4.3 | developer | low | Move Content Studio skill: `git mv plugins/career/skills/content plugins/career/skills/content` | `plugins/career/skills/content/` |
| 4.4 | developer | low | Move AI Consulting: `git mv plugins/consulting/skills/client-ai-consulting plugins/consulting/skills/client-ai-consulting` | `plugins/consulting/skills/client-ai-consulting/` |
| 4.5 | developer | low | Move SMB Design: `git mv plugins/consulting/skills/client-smb-design plugins/consulting/skills/client-smb-design` | `plugins/consulting/skills/client-smb-design/` |
| 4.6 | developer | low | Move Bossa Nova: `git mv plugins/consulting/skills/client-terminal-automation plugins/consulting/skills/client-terminal-automation` | `plugins/consulting/skills/client-terminal-automation/` |
| 4.7 | developer | low | Move Venture: `git mv plugins/professional/skills/venture-augur plugins/professional/skills/venture-augur` | `plugins/professional/skills/venture-augur/` |
| 4.8 | developer | low | Move Enterprise: `git mv plugins/enterprise/skills/enterprise plugins/enterprise/skills/enterprise` | `plugins/enterprise/skills/enterprise/` |
| 4.9 | developer | low | Move Project Dev: `git mv plugins/professional/skills/project-dev plugins/professional/skills/project-dev` | `plugins/professional/skills/project-dev/` |
| 4.10 | developer | low | Delete `plugins/consulting/` (all skills moved out). Verify empty first. Also delete `plugins/career/skills/linkedin-writer/` if still present (no dashboard). | `plugins/consulting/` |

#### Phase 5: Redistribute System → Admin + Observe (PARALLEL with Phases 2-4)
**Strategy**: PARALLEL (5.1-5.3 parallel, then 5.4)
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 5.1 | developer | low | Move admin skills: `git mv plugins/admin/skills/system-cleanup plugins/admin/skills/`, `git mv plugins/admin/skills/updater plugins/admin/skills/`, `git mv plugins/admin/skills/renderer plugins/admin/skills/`, `git mv plugins/ai/skills/scraper plugins/admin/skills/`, `git mv plugins/admin/skills/channels plugins/admin/skills/` | `plugins/admin/skills/` |
| 5.2 | developer | low | Move observe skills: `git mv plugins/observability/skills/observe plugins/observability/skills/`, `git mv plugins/observability/skills/daemon plugins/observability/skills/`, `git mv plugins/observability/skills/metrics plugins/observability/skills/` | `plugins/observability/skills/` |
| 5.3 | developer | medium | Create settings skill in admin: `dashboard.yaml` with hub.id `settings`, nav_label "Settings", icon "Settings". Move `/settings` page component from `src/dashboard/app/settings/` to `plugins/admin/skills/settings/dashboard/`. | `plugins/admin/skills/settings/` |
| 5.4 | developer | low | Delete `plugins/admin/` (all skills moved). Verify empty first. | `plugins/admin/` |

#### Phase 6: Fix Home + Remove Legacy (PARALLEL with Phases 2-5)
**Strategy**: PARALLEL
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 6.1 | developer | medium | Fix home-automation nav visibility: investigate why `home` doesn't appear in `pluginNavItems` in generated-registry.ts. Check `plugins/home/skills/home-automation/dashboard.yaml` for missing fields. Fix generate-tabs script or dashboard.yaml as needed. | `plugins/home/skills/home-automation/dashboard.yaml`, `scripts/generate-tab-registry.ts` |
| 6.2 | developer | low | Delete `plugins/ai/` entirely: `git rm -r plugins/ai/` (legacy duplicate of daemon). | `plugins/ai/` |
| 6.3 | developer | low | Delete `plugins/custom/` entirely: `git rm -r plugins/custom/` (empty hub). | `plugins/custom/` |

#### Phase 7: Update Navigation + Config (depends on Phases 2-6)
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 7.1 | developer | medium | Update `navigation.ts`: (1) Set `HUB_SECTION_ORDER` to `['career', 'growth', 'finance', 'wealth', 'health', 'productivity', 'integrations', 'lifestyle', 'creative', 'home', 'consulting', 'venture', 'enterprise', 'ai', 'admin', 'observe', 'dev']`. (2) Update `getHubPriority`: admin, observe, dev → tertiary. (3) Remove Settings from `STATIC_OPERATIONS_ITEMS`. (4) Update static items merge logic: replace `system` references with `admin`. | `src/dashboard/lib/navigation.ts` |
| 7.2 | developer | medium | Update `CLAUDE.md`: hub count → 17, update hub list, update directory layout description. | `CLAUDE.md` |
| 7.3 | devops | low | Regenerate: `npm run generate-tabs`. Verify `generated-registry.ts` has entries for all new hubs. Verify `.plugin-mount` symlinks in `src/dashboard/app/`. | `src/dashboard/lib/tabs/generated-registry.ts` |

#### Phase 8: Verification
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task |
|------|-------|------|------|
| 8.1 | validator | low | Run `npm run build` — verify dashboard compiles. Check for broken imports referencing old paths. |
| 8.2 | validator | low | Run `pytest tests/src/` — verify Python tests pass. |
| 8.3 | validator | low | Verify sidebar: inspect `generated-registry.ts` for correct hub assignments. Confirm: career 8 tabs, growth 8 tabs, finance 4 tabs, wealth 6 tabs, productivity 2 skills, integrations 2 skills, consulting 4 skills (3 with dashboards), venture 1 skill, enterprise 1 skill, admin 6 skills (5 with dashboards), observe 3 skills, dev 3+ items. |
| 8.4 | architect | low | Review ADR intent vs implementation: verify no tabs lost, all skills accounted for, no orphaned files. Update ADR-108 status to "Accepted". |

### Completion Criteria
- [ ] All 8 phases executed
- [ ] All tests pass (`pytest tests/src/`, `npm run build`)
- [ ] No orphaned files or broken references
- [ ] Career hub: 8 tabs (job search)
- [ ] Growth hub: 8 tabs (professional development)
- [ ] Finance hub: 4 tabs (spending tracking)
- [ ] Wealth hub: 6 tabs (investing & planning)
- [ ] Productivity hub: 2 skills (Eisenhower + Organizer)
- [ ] Integrations hub: 2 skills (Apple + Google)
- [ ] Lifestyle hub: 1 skill (8 tabs)
- [ ] Creative hub: 1 skill (6 tabs)
- [ ] Home hub: visible in sidebar navigation
- [ ] Consulting hub: 4 skills, 3 with dashboards (client work)
- [ ] Venture hub: 1 skill (product management)
- [ ] Enterprise hub: 1 skill (org deployment)
- [ ] Admin hub: 6 skills, 5 with dashboards (system config)
- [ ] Observe hub: 3 skills (monitoring)
- [ ] Dev hub: Project Dev + Operations + Control
- [ ] Legacy hubs (services, custom, business, system) deleted
- [ ] Navigation renders all 17 sections correctly
- [ ] ADR status updated to "Accepted"

### How to Run
```
# Option 1: Use /implement-adr (handles team orchestration automatically)
/implement-adr docs/decisions/ADR-108-hub-rebalancing.md

# Option 2: Paste this prompt into Claude Code
# The agent will create the team, spawn teammates, and coordinate
```
