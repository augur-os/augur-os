---
status: Implemented
date: '2026-01-26'
deciders:
- Core team
related: []
hub: null
tags:
- platform
- enhancements
superseded_by: null
---

# ADR-021: Platform Enhancements Q1 2026

**Context**: Post-competitive analysis (Clawdbot review)

## Context

Following a deep competitive analysis of Clawdbot and the personal AI market, we identified:

1. **Augur's unique moats**: No API key requirement, GUI dashboard, RAG, Unix philosophy
2. **Critical gaps**: Vertical skills (careers, recipes, virtual-doctor) cannot update data from web sources
3. **Existing capabilities**: Basic email, Apple Notes, and calendar integration already exist

This ADR defines the platform enhancements needed to:
- Unblock vertical skills that depend on web data
- Strengthen existing moats (RAG, dashboard)
- Add lightweight notification capabilities
- Expand the service layer for future skills

## Decision

### Priority Tiers

#### P0 - Critical (Verticals Blocked + Community)

| Enhancement | Description | Rationale |
|-------------|-------------|-----------|
| **Web Scraper Service** | New service skill providing unified web data access | Careers, recipes, virtual-doctor all need web data |
| **Microsoft Playwright MCP** | Local browser automation via official MCP server | Free, local, no API key - perfect for simple scraping |
| **Brightdata/Firecrawl MCP Tools** | MCP tool definitions for cloud scraping services | Fallback for anti-bot sites or high-volume needs |
| **Community Plugin Manager** | GUI to browse, install, remove plugins from community registry | Enables ecosystem growth, lowers barrier to plugin adoption |
| **Community Project Manager** | In-plugin issue tracking with Dev mode (AI Builder) or ticket sync to GitHub | Two paths: power users build with AI, others request features via community |

#### P1 - High Value (Strengthen Moats)

| Enhancement | Description | Rationale |
|-------------|-------------|-----------|
| **RAG Improvements** | Enhanced indexing, better search, relationship extraction | Unique capability vs Clawdbot - make it unmatched |
| **Dashboard UX Polish** | Improve visual workflows, skill UI consistency | GUI is our moat - needs to be excellent |
| **IDE Integrations** | Add Windsurf, Zed, other IDEs | Expand "bring to work" market |
| **Sense Layer (Hue)** | Service layer for home automation data | Platform capability for future skills, differentiates from Clawdbot |
| **Calendar Sync Improvements** | Enhance existing calendar integration, integrate with sense layer | Enable focus modes, meeting automation |

#### P2 - Nice to Have

| Enhancement | Description | Rationale |
|-------------|-------------|-----------|
| **Telegram Notifications** | One-way push notifications only (no chat) | Lightweight notification capability |

#### P3 - Skip/Defer

| Enhancement | Rationale |
|-------------|-----------|
| Two-way messaging (any platform) | Requires API key, contradicts positioning |
| Mobile apps | Expensive, Clawdbot/Kin dominate |
| Voice wake | Not differentiating |
| WhatsApp integration | Requires API key |

### Architecture Decisions

#### 1. Web Scraper Service

**Location**: `plugins/ai/skills/scraper/`

**Design**:
```
┌─────────────────────────────────────────────────────┐
│                  Vertical Skills                     │
│   (careers, recipes, virtual-doctor, business)       │
└─────────────────────┬───────────────────────────────┘
                      │ MCP calls
                      ▼
┌─────────────────────────────────────────────────────┐
│              Web Scraper Service                     │
│  - scrape_url(url) → content                        │
│  - scrape_structured(url, schema) → data            │
│  - search_web(query) → results                      │
└─────────────────────┬───────────────────────────────┘
                      │ API calls
                      ▼
┌─────────────────────────────────────────────────────┐
│         External Providers (via MCP)                 │
│   - Brightdata (scraping)                           │
│   - Firecrawl (structured extraction)               │
│   - Future: Browserless, ScrapingBee               │
└─────────────────────────────────────────────────────┘
```

**Provider Strategy (Tiered)**:
```
┌─────────────────────────────────────────────────────────────┐
│                    Web Scraper Service                       │
│                                                             │
│  Provider Selection Logic:                                  │
│  1. Try Playwright MCP (local, free) first                 │
│  2. If blocked/failed → fallback to Brightdata/Firecrawl   │
│  3. User can force specific provider via config            │
└─────────────────────────────────────────────────────────────┘
```

**Microsoft Playwright MCP** (Primary - Local):
- **Install**: `npx @playwright/mcp@latest`
- **Cost**: Free, runs locally
- **Pros**: No API key, fast, uses accessibility tree (not screenshots)
- **Cons**: Blocked by sophisticated anti-bot sites
- **Best for**: Simple sites, recipes, job boards, documentation

**Brightdata/Firecrawl** (Fallback - Cloud):
- **Cost**: Pay-per-use
- **Pros**: Bypasses anti-bot, handles JavaScript-heavy sites
- **Cons**: Requires API key (backend, not user-facing)
- **Best for**: LinkedIn, protected sites, high-volume scraping

**MCP Tools to Define**:
```yaml
tools:
  - name: scrape_url
    description: Fetch and parse content from a URL
    parameters:
      url: string (required)
      format: enum [html, markdown, text]
      provider: enum [auto, playwright, brightdata, firecrawl] (default: auto)

  - name: scrape_structured
    description: Extract structured data from a URL using a schema
    parameters:
      url: string (required)
      schema: object (JSON schema for extraction)
      provider: enum [auto, playwright, brightdata, firecrawl] (default: auto)

  - name: search_web
    description: Search the web and return results
    parameters:
      query: string (required)
      num_results: integer (default 10)
```

#### 2. Telegram Notifications Service

**Location**: `plugins/observability/skills/daemon/`

**Design**: One-way only (Augur → User), no incoming message handling

**MCP Tools**:
```yaml
tools:
  - name: send_notification
    description: Send a notification to the user
    parameters:
      message: string (required)
      channel: enum [telegram, desktop] (default: desktop)
      priority: enum [low, normal, high]
```

**Use Cases**:
- "Job scrape complete: 12 new matches"
- "Recipe imported from URL"
- "Competitive intel updated"
- "Background task finished"

#### 3. Sense Layer (Hue) Service

**Location**: `plugins/home/skills/home-automation/` <!-- sense skill was removed; ambient functionality folded into home-automation -->

**Design**: Horizontal service layer for ambient/environmental data

**MCP Tools**:
```yaml
tools:
  - name: get_room_state
    description: Get current state of a room (lights, temp, etc.)
    parameters:
      room: string (optional, default: current)

  - name: set_scene
    description: Set a lighting/environment scene
    parameters:
      scene: enum [focus, relax, meeting, away]
      room: string (optional)
```

**Future Extensions**:
- Temperature sensors
- Presence detection
- Focus mode integration with calendar

#### 4. Community Plugin Manager

**Location**: `plugins/admin/skills/updater/`

**Design**:
```
┌─────────────────────────────────────────────────────────────┐
│                    Plugin Manager Dashboard                  │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  Installed  │  │  Available  │  │   Updates   │         │
│  │   Plugins   │  │  (Registry) │  │  Available  │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│                                                             │
│  [Install]  [Remove]  [Update]  [View Details]              │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                  Community Registry (GitHub)                 │
│                                                             │
│  - Plugin metadata (name, description, author, version)     │
│  - Download URLs (git clone or tarball)                     │
│  - Compatibility info (Augur version, dependencies)         │
│  - User ratings/reviews                                     │
└─────────────────────────────────────────────────────────────┘
```

**MCP Tools**:
```yaml
tools:
  - name: list_plugins
    description: List installed or available community plugins
    parameters:
      filter: enum [installed, available, updates] (default: installed)
      category: string (optional)

  - name: install_plugin
    description: Install a plugin from community registry
    parameters:
      plugin_id: string (required)
      version: string (optional, default: latest)

  - name: remove_plugin
    description: Remove an installed plugin
    parameters:
      plugin_id: string (required)
      keep_data: boolean (default: true)

  - name: update_plugin
    description: Update plugin to latest version
    parameters:
      plugin_id: string (required)
```

**Dashboard Features**:
- Browse community plugins by category (apps, services, core)
- Search by name, description, author
- One-click install/remove
- Version management and update notifications
- Plugin details page with README, screenshots, dependencies

#### 5. Community Project Manager

**Location**: Integrated into each plugin's dashboard

**Design**: Two-path contribution model
```
┌─────────────────────────────────────────────────────────────┐
│              Plugin Dashboard - "Contribute" Tab             │
│                                                             │
│  ┌───────────────────────┐  ┌───────────────────────────┐  │
│  │     🔧 Dev Mode       │  │     📋 Request Mode       │  │
│  │   (AI Builder)        │  │   (Community Ticket)      │  │
│  │                       │  │                           │  │
│  │  "I want to build     │  │  "I have an idea but      │  │
│  │   this myself with    │  │   need help from the      │  │
│  │   AI assistance"      │  │   community"              │  │
│  │                       │  │                           │  │
│  │  → Opens IDE in Dev   │  │  → Creates GitHub issue   │  │
│  │    mode with plugin   │  │    with template          │  │
│  │    context loaded     │  │  → Syncs status back      │  │
│  └───────────────────────┘  └───────────────────────────┘  │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Open Issues / Feature Requests          │   │
│  │  #123 Add export to PDF         [In Progress]       │   │
│  │  #119 Support dark mode         [Open]              │   │
│  │  #115 Better error messages     [Closed]            │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

**MCP Tools**:
```yaml
tools:
  - name: create_feature_request
    description: Create a feature request (syncs to GitHub)
    parameters:
      plugin_id: string (required)
      title: string (required)
      description: string (required)
      type: enum [feature, bug, improvement]

  - name: list_issues
    description: List open issues for a plugin
    parameters:
      plugin_id: string (required)
      status: enum [open, closed, all] (default: open)

  - name: enter_dev_mode
    description: Open IDE with plugin context for development
    parameters:
      plugin_id: string (required)
      issue_id: string (optional, to work on specific issue)
```

**Two-Path Philosophy**:
1. **Dev Mode (AI Builder)**: Power users who want to contribute code
   - Loads plugin context into IDE
   - AI assists with implementation
   - Direct PR workflow

2. **Request Mode (Community Ticket)**: Users who want features but can't/won't code
   - Simple form → GitHub issue
   - Bi-directional sync (status updates appear in dashboard)
   - Community or maintainers can pick up

**GitHub Sync**:
- Issues created from dashboard get `augur-request` label
- Status changes in GitHub reflect in dashboard
- Comments sync bidirectionally
- PRs linked to issues show in dashboard

### Integration with Existing Services

| Existing Service | Enhancement |
|------------------|-------------|
| `inbox` (email) | Add web scraper for email-linked content |
| `calendar` | Integrate with sense layer for meeting modes |
| Apple Notes | Already working, no changes |

## Consequences

### Positive

- Vertical skills (careers, recipes, doctor) become fully functional
- RAG improvements strengthen our unique moat
- Dashboard polish differentiates from Clawdbot's basic control-ui
- Telegram notifications provide mobile touchpoint without full app
- Sense layer enables future home automation skills
- No new API key requirements for users (scraping services are backend)
- Community plugin ecosystem enables network effects (more plugins → more users → more contributors)
- Two-path contribution model lowers barrier (non-devs can still participate)
- GitHub sync creates bridge between dashboard users and developer community

### Negative

- Brightdata/Firecrawl have costs (only used as fallback, not primary)
- Sense layer (Hue) requires user to have Hue hardware
- More services to maintain
- Playwright MCP adds Node.js dependency (already have for dashboard)
- Plugin registry needs moderation/curation to maintain quality
- GitHub sync requires GitHub token configuration

### Neutral

- Existing email/calendar/notes integrations unchanged
- No changes to core MCP architecture
- No changes to "no API key" positioning (scraping is backend service)

## Alternatives Considered

### Alternative 1: Cloud-Only Scraping (Brightdata/Firecrawl)

Use only cloud scraping services, no local browser.

**Partially accepted**:
- Cloud services are fallback for blocked sites
- But local Playwright MCP is primary for cost savings and simplicity
- Tiered approach gives best of both worlds

### Alternative 2: Two-Way Telegram Chat

Full bidirectional Telegram integration like Clawdbot.

**Rejected because**:
- Would require API key for LLM responses
- Contradicts "no API key" positioning
- That's Clawdbot's game, not ours
- One-way notifications sufficient for our use case

### Alternative 3: Skip Sense Layer

Don't build Hue/home automation integration.

**Rejected because**:
- Creates platform for future skills
- Differentiates from Clawdbot (they have skills, we have service layer)
- Low effort as P2

## Implementation Plan

### Phase 1: Unblock Verticals + Community Foundation (Weeks 1-4)

1. Integrate Microsoft Playwright MCP (local scraping)
2. Define Brightdata/Firecrawl MCP tools (cloud fallback)
3. Create web-scraper service skill with tiered provider logic
4. Update careers skill to use web-scraper
5. Update recipes skill to use web-scraper
6. Update virtual-doctor skill to use web-scraper
7. Community Plugin Manager (browse, install, remove)
8. Community Project Manager (GitHub sync foundation)

### Phase 2: Strengthen Moats + Service Layers (Weeks 5-8)

1. RAG improvements (indexing, search quality)
2. Dashboard UX polish
3. IDE integrations (Windsurf, Zed)
4. Sense layer foundation + Hue integration
5. Calendar sync improvements + sense layer integration
6. Dev Mode integration (AI Builder for contributors)
7. Plugin registry launch with initial curated plugins

### Phase 3: Notifications + Community Polish (Weeks 9-12)

1. Telegram notifications service (one-way push)
2. Plugin ratings and reviews
3. Bi-directional GitHub issue sync
4. Community contribution metrics dashboard

## Success Metrics

| Metric | Target |
|--------|--------|
| Verticals using web-scraper | 4 (careers, recipes, doctor, business) |
| RAG search quality | Measurable improvement in relevance |
| Dashboard satisfaction | User feedback positive |
| IDE integrations | +2 new IDEs supported |
| Community plugins in registry | 10+ curated plugins |
| Plugin installs | 100+ installs across community |
| GitHub issues via dashboard | 50+ feature requests synced |
| Dev mode sessions | 20+ contributors using AI Builder |

## References

- Strategic Review: `plugins/consulting-expert/strategy/strategic_review_jan2026.md`
- Clawdbot Comparison: `plugins/consulting-expert/strategy/clawdbot_comparison_accurate.md`
- Existing services: `plugins/ai/skills/`
- ADR-005: MCP Execution Gateway
- ADR-008: Plugin System
- Microsoft Playwright MCP: https://github.com/microsoft/playwright-mcp
- Brightdata MCP: https://brightdata.com/blog/ai/web-scraping-with-mcp
