---
status: Implemented
date: '2026-02-26'
deciders:
- Project team
related:
- ADR-047 (chat-first UI)
- ADR-104 (operation mode terminal)
- ADR-130 (action dispatch modes)
- ADR-162 (action type consolidation)
hub: null
tags:
- demo
- mode
- command
superseded_by: null
---

# ADR-168: Demo Mode Command

## Context

When demoing Augur to others — investors, collaborators, or new users — the system presents as a developer tool: verbose logs, dev-mode commands visible, extended thinking pauses, permission prompts interrupting flow, and default Opus speeds that feel slow during live walkthroughs.

There is no single command to switch the system into a "presentation-ready" state. Currently a demo requires manually:
1. Toggling `/fast` in each Claude Code session
2. Switching dashboard to operation mode
3. Hoping no permission prompt interrupts the flow
4. Avoiding dev-only commands that confuse the audience

A `/demo` command should atomically switch Augur into a polished, fast, audience-friendly state — and switch back when done.

## Decision

### 1. `/demo` Slash Command

Create a new workflow at `plugins/ai/skills/ai_bridge/augur/data/agent-workflows/demo.md` with visibility `core`.

**Usage:**
```bash
/demo          # Enter demo mode (or toggle)
/demo on       # Explicitly enable
/demo off      # Explicitly disable
/demo status   # Show current demo state
```

### 2. Phase 1 — Fast Mode Configuration (MVP)

The `/demo` command writes Claude Code settings to enable fast mode across all instances.

**Settings applied to `~/.claude/settings.json`** (global, affects all instances):

```json
{
  "preferFastMode": true
}
```

**Settings applied to `.claude/settings.local.json`** (project-level, gitignored):

```json
{
  "MAX_THINKING_TOKENS": 8000,
  "DISABLE_NONESSENTIAL_MODEL_CALLS": "1",
  "showTurnDuration": false,
  "spinnerTipsEnabled": false
}
```

**Backup/restore**: Before writing, the script saves the original settings to `runtime/demo/settings-backup-global.json` and `runtime/demo/settings-backup-local.json`. `/demo off` restores from backup and deletes the backup files.

**State tracking**: `runtime/demo/state.json` records:
```json
{
  "active": true,
  "activated_at": "2026-02-26T10:00:00Z",
  "components": ["fast_mode"]
}
```

### 3. Phase 2 — Demo Experience Enhancements

Beyond fast mode, demo mode should apply these additional changes:

| Change | Mechanism | Why |
|--------|-----------|-----|
| **Dashboard → operation mode** | Call `/api/settings/mode` POST with `operation` | Hides dev controls, simplifies UI labels |
| **Curated suggested actions** | Write `runtime/demo/suggested_overrides.json` read by SuggestedActions component | Show impressive capabilities (e.g., /ask, calendar, inbox) instead of dev tools |
| **Hide dev commands** | Filter workflows with `mode: dev` from `/commands` output when demo state is active | Audience doesn't need `/dev-debug`, `/ops-kill`, `/test-nightly` |
| **Suppress permission prompts** | Ensure `skipDangerousModePermissionPrompt: true` in global settings | No "Allow this action?" interruptions during demo |
| **Simplified status line** | Override status line to show only project name + context % (no token counts, no branch) | Cleaner terminal chrome |
| **Auto-compact earlier** | Set `CLAUDE_CODE_AUTOCOMPACT_PCT_OVERRIDE: 60` | Prevent context warnings during demo |

### 4. Phase 3 — Demo Playbooks

Predefined demo scenarios designed to cover all 5 Augur principles across different audiences.

#### The 5 Principles (every demo set must cover all)

| # | Principle | Core Idea | Audience Reads As |
|---|-----------|-----------|-------------------|
| 1 | **Trust** | English is the programming language. You see everything. | "I understand what it's doing" |
| 2 | **Freedom** | Any LLM provider. Any AI bridge. | "I'm not locked in" |
| 3 | **Pace** | Grows with you. You set the speed. | "I can start small" |
| 4 | **Complexity** | Start simple. Add capabilities when ready. | "It scales with me" |
| 5 | **Future Proof** | Your data is the product. | "My knowledge survives vendor changes" |

#### Playbook Schema

```yaml
# plugins/ai/skills/ai_bridge/augur/data/demo/playbooks/{name}.yaml
name: string
audience: investor | technical | new-user | partner
duration_minutes: number
principles_covered: [trust, freedom, pace, complexity, future_proof]
prerequisites:
  - dashboard_running: true
  - skills_enabled: [career, apple, venture-augur]
demos:
  - id: string
    title: string
    rank: number         # 1=highest impact
    category: string     # see categories below
    principles: []       # which of the 5 this demo proves
    readiness: green | yellow | red  # works today / needs polish / needs building
    duration_seconds: number
    steps:
      - action: string   # command, navigation, or UI action
        type: cli | dashboard | browser  # where it happens
        pause: boolean    # wait for audience reaction
        narration: string # what to say to audience
```

#### Demo Categories

| Category | What It Proves |
|----------|---------------|
| **Ecosystem** | Plugin architecture, skill discovery, install/remove |
| **Cross-Tool** | Same brain across IDEs, CLIs, and tools |
| **Orchestration** | Parallel workflows, multi-agent coordination |
| **Knowledge** | RAG, memory, /ask, knowledge editing |
| **Integration** | Local + remote MCP, Apple + Google + web |
| **Automation** | Self-heal, daemon, background intelligence |
| **Domain** | Real business value (venture, career, content, finance) |

---

#### Demo Dashboard Page — Skill Gate Visualizer

A new page under the venture dashboard at `/professional/demo` that visually presents the full lifecycle and quality gates of an Augur skill. This is both a demo asset (shows engineering rigor to investors) and a functional tool (audits real skills).

**Location**: `plugins/professional/skills/venture-augur/augur/dashboard/demo/page.tsx`
**Route**: `/professional/demo`

##### What the page shows

The page visualizes 4 gate systems as a unified pipeline — a skill flows left-to-right through all stages:

```
[Creation] → [Quality] → [Implementation] → [Production]
 5 Stages    6 Scores    10 Gates           Lifecycle
```

##### Section 1: Factory Pipeline (5 Stages)

Visual: Horizontal stepper with checkmarks per completed stage.

| Stage | Name | What It Does | Visual State |
|-------|------|-------------|-------------|
| 1 | **Baseline** | Generate/import skill, conform to Layer 1 (SKILL.md) | Green check / Gray circle |
| 2 | **Hardening** | Validate Layer 1, add base structure (dashboard.yaml scaffold) | Green check / Gray circle |
| 3 | **Data** | Populate `augur/data/`, schemas, sample files, index YAML | Green check / Gray circle |
| 4 | **MCP** | Register tools in MCP gateway, export tool definitions | Green check / Gray circle |
| 5 | **UI** | Create React dashboard components, routing, layout | Green check / Gray circle |

**Data source**: Read skill directory structure and check for stage artifacts.
**Interactive**: Select any skill from a dropdown → stages light up based on which artifacts exist.

##### Section 2: Quality Score (6 Dimensions)

Visual: Radar chart (hexagonal) with 6 axes + overall tier badge.

| Dimension | Weight | What It Measures |
|-----------|--------|-----------------|
| Problem Alignment | 25% | Does the skill solve stated problems? |
| Action Coverage | 20% | Do actions address user needs? |
| Data Support | 20% | Do data structures support workflows? |
| UI Access | 15% | Does UI provide appropriate access? |
| Capability Completeness | 10% | Are all capabilities implemented? |
| User Journey Fit | 10% | Does it fit typical user journeys? |

**Tier badges**: Excellent (85+, green), Good (70-84, blue), Needs Work (50-69, yellow), Poor (<50, red)
**Data source**: MCP tool `audit-plugin` or call scoring module directly.

##### Section 3: Implementation Gates (10 Gates)

Visual: Vertical checklist with expand/collapse per gate. Each gate shows pass/fail/untested.

| Gate | Name | Focus |
|------|------|-------|
| 1 | Library Code | All new modules/classes written, no orphan code |
| 2 | Integration Wiring | New code called from MCP, API, CLI, dashboard |
| 3 | Migration & Data | Backward compatibility, data migrated |
| 4 | UI Verification | Components render, no console errors |
| 5 | Tests Match ADR | Every test case has passing test |
| 6 | Existing Tests Green | No regressions, `npm run build` passes |
| 7 | Impact Validation | Zero stale references for renamed paths |
| 8 | Decentralization | No new centralized config, all data in plugin |
| 9 | Wiring Verification | Zero deprecated callers, every dispatch path traced |
| 10 | Agent Instruction Freshness | Patterns documented, memory synced |

**Data source**: For the demo, show a pre-computed audit of a selected skill (e.g., career, apple, or venture-augur itself). In production, this could run gates live via MCP tools.

##### Section 4: Lifecycle State Machine

Visual: State diagram (horizontal flow with arrows).

```
NEW → CONFIGURED → ENABLED ↔ DISABLED
 ↓                              ↓
IGNORED                     ARCHIVED
```

**Show for selected skill**: Current state (from `.config` file), transition history, dependencies resolved/unresolved.

##### Section 5: Skill Profile Detection

Visual: Three cards (Minimal / Standard / Full) with the detected profile highlighted.

| Profile | Trigger | Required |
|---------|---------|----------|
| **Minimal** | Agent-only, no UI | SKILL.md + scripts/ or mcp/ |
| **Standard** | Dashboard UI, no API | + dashboard.yaml + dashboard/*.tsx |
| **Full** | Complex app with API | + api/health/route.ts + mcp tools |

**Auto-detected** from directory structure. Highlight the active profile for the selected skill.

##### Page Layout

```
┌─────────────────────────────────────────────────────┐
│ Demo — Skill Gate Visualizer          [Select Skill ▾] │
├─────────────────────────────────────────────────────┤
│                                                       │
│ ┌─ Factory Pipeline ─────────────────────────────────┐ │
│ │  ● Baseline → ● Hardening → ● Data → ● MCP → ● UI │ │
│ └────────────────────────────────────────────────────┘ │
│                                                       │
│ ┌─ Quality Score ──────────┐ ┌─ Profile ────────────┐ │
│ │     ╱ Problem ╲          │ │ [Minimal] [Standard] │ │
│ │   Action   Data          │ │ [  ★ Full  ]         │ │
│ │     ╲ UI  Caps ╱         │ │                      │ │
│ │      Journey             │ │ Overall: 82/95       │ │
│ │   Tier: ● Good (82)     │ │ Tier: Good           │ │
│ └──────────────────────────┘ └──────────────────────┘ │
│                                                       │
│ ┌─ Implementation Gates ─────────────────────────────┐ │
│ │ ✅ Gate 1: Library Code                            │ │
│ │ ✅ Gate 2: Integration Wiring                      │ │
│ │ ✅ Gate 3: Migration & Data                        │ │
│ │ ✅ Gate 4: UI Verification                         │ │
│ │ ✅ Gate 5: Tests Match ADR                         │ │
│ │ ✅ Gate 6: Existing Tests Green                    │ │
│ │ ⬜ Gate 7: Impact Validation (N/A — no renames)    │ │
│ │ ✅ Gate 8: Decentralization Check                  │ │
│ │ ✅ Gate 9: Wiring Verification                     │ │
│ │ ✅ Gate 10: Agent Instruction Freshness            │ │
│ │                                          9/10 ✅   │ │
│ └────────────────────────────────────────────────────┘ │
│                                                       │
│ ┌─ Lifecycle ────────────────────────────────────────┐ │
│ │ NEW → CONFIGURED → [★ ENABLED] ↔ DISABLED         │ │
│ │ Dependencies: knowledge ✅  ai_bridge ✅           │ │
│ └────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

##### Registration in augur.yaml

Add to `plugins/professional/skills/venture-augur/augur.yaml`:

```yaml
# In contributions.pages:
- id: demo
  title: Demo
  icon: Sparkles

# In tabs:
- id: demo
  label: Demo
  icon: Sparkles
  group: core
  href: /professional/demo
```

Then run `npm run mount-plugins` to mount the page.

##### Demo flow using this page

This page is itself a demo asset — Demo 19 in the catalog:

---

#### Demo Catalog

##### Demo 19: Skill Gate Visualizer (NEW — for all audiences)
**Category**: Ecosystem
**Rank**: 2 (for Intel/investor — proves engineering rigor visually)
**Principles**: Trust, Complexity, Pace
**Readiness**: RED — page needs building. Factory stages and audit scoring exist as backend tools; page is new UI.
**Duration**: ~90s

| Step | Type | Action | Narration |
|------|------|--------|-----------|
| 1 | dashboard | Navigate to `/professional/demo` — show the gate visualizer | "This is how Augur ensures quality. Every skill passes through gates." |
| 2 | dashboard | Select "career" skill from dropdown — factory pipeline lights up all 5 green | "Career skill: passed all 5 factory stages — baseline, hardening, data, MCP, UI." |
| 3 | dashboard | Show quality radar chart — 82/95 score, "Good" tier | "Scored across 6 dimensions. Problem alignment 23/25. Action coverage 18/20." |
| 4 | dashboard | Show implementation gates — 9/10 green | "10 implementation gates. Library code, integration wiring, UI verification, decentralization — all passed." |
| 5 | dashboard | Expand Gate 8 (Decentralization) — show what it checks | "Gate 8 verifies no centralized config was created. All data inside the plugin." |
| 6 | dashboard | Show profile detection: Full profile highlighted | "Auto-detected as 'Full' profile — has dashboard, API routes, and MCP tools." |
| 7 | dashboard | Show lifecycle state: ENABLED, dependencies resolved | "Currently enabled. Dependencies on knowledge and ai_bridge both resolved." |
| 8 | dashboard | Switch to "organizer" skill — show 3/5 stages, yellow score, missing gates | "Organizer is earlier in the pipeline. 3 stages done, no MCP tools yet." |
| 9 | dashboard | "Every one of our 35 skills goes through this. This is how a one-person team maintains enterprise quality." | |

**What proves Trust**: Every quality dimension, gate, and state visible. Nothing hidden.
**What proves Complexity**: 5 stages + 6 scoring dimensions + 10 gates + lifecycle = comprehensive maturity model.
**What proves Pace**: Skills at different maturity levels coexist. Add capabilities when ready.

**Intel talking points:**
- "35 skills, each with 10 quality gates. That's 350 checkpoints maintained by one person."
- "The radar chart runs locally — no cloud dependency for quality assessment."
- "This is the kind of dashboard that justifies an always-on AI PC — continuous quality monitoring."

---

##### Demo 1: Skill Pull-In from External IDE
**Category**: Ecosystem
**Rank**: 3 (high wow-factor but depends on partially-built import flow)
**Principles**: Pace, Freedom, Complexity
**Readiness**: YELLOW — Install UI exists, source registry defined, but external skill import flow not connected. Needs: skill import endpoint + "pull in" action wiring.
**Duration**: ~90s

| Step | Type | Action | Narration |
|------|------|--------|-----------|
| 1 | browser | Open Codex, install a community skill (e.g. a code-review skill) | "I found this skill in Codex's marketplace" |
| 2 | dashboard | Navigate to `/ai/install` — show the skill appearing in Augur's discovery feed | "Augur detected it — it watches all your IDE environments" |
| 3 | dashboard | Click "Pull In" on the discovered skill | "One click to adopt it into your system" |
| 4 | dashboard | Navigate to the new skill's auto-generated page | "It created a page, wired MCP tools, and registered actions — zero config" |
| 5 | cli | Run `/focus {new-skill}` to show context narrowing | "Now I can work with it from any tool" |

**What proves Pace**: You add skills when ready, not all at once.
**What proves Freedom**: Skill came from Codex, now works everywhere.
**What proves Complexity**: One click did page creation + MCP wiring + action registration.

---

##### Demo 2: Cross-Tool Focus
**Category**: Cross-Tool
**Rank**: 1 (strongest differentiator — no competitor does this)
**Principles**: Freedom, Trust
**Readiness**: GREEN — /focus works today across IDEs, FocusPayload format is canonical.
**Duration**: ~60s

| Step | Type | Action | Narration |
|------|------|--------|-----------|
| 1 | dashboard | Open career page, show job pipeline | "I'm working on my job search" |
| 2 | cli | In Claude Code: `/focus career` | "Focus narrows my context to career tools" |
| 3 | cli | In Antigravity: `/focus` — show same career context | "Same brain, different tool — identical context" |
| 4 | cli | In Codex: `/focus` — show same career context | "Three different IDEs, one unified focus" |
| 5 | cli | Ask "what am I working on?" in any tool — same answer | "My second brain remembers, regardless of which tool asks" |

**What proves Freedom**: Three IDEs, identical context.
**What proves Trust**: You can inspect the FocusPayload — it's plain JSON.

---

##### Demo 3: Parallel Workflow Execution
**Category**: Orchestration
**Rank**: 2 (visually impressive — multiple things happening at once)
**Principles**: Pace, Complexity, Trust
**Readiness**: YELLOW — Post list works, but inline refine/translate action buttons need wiring. Needs: action dispatch from post cards.
**Duration**: ~75s

| Step | Type | Action | Narration |
|------|------|--------|-----------|
| 1 | dashboard | Navigate to `/career/content/posts` — show 4-5 draft posts | "Here are my content drafts" |
| 2 | dashboard | Click "Refine" on post 1 | "Refine this one for clarity" |
| 3 | dashboard | Click "Translate to Hebrew" on post 2 | "Translate this one" |
| 4 | dashboard | Click "Generate Image" on post 3 | "And create a visual for this one" |
| 5 | dashboard | Show all 3 running in parallel (status indicators) | "Three different AI tasks, running simultaneously" |
| 6 | dashboard | Results arrive — show updated posts | "Each finished independently — no waiting in line" |

**What proves Pace**: User controls what runs and when.
**What proves Complexity**: Simple clicks trigger complex multi-step AI workflows.
**What proves Trust**: Each action's progress is visible.

---

##### Demo 4: RAG Knowledge Search
**Category**: Knowledge
**Rank**: 5 (solid but not as visually dramatic)
**Principles**: Future Proof, Trust
**Readiness**: GREEN — search-skill-knowledge MCP tool fully implemented with iterative search.
**Duration**: ~45s

| Step | Type | Action | Narration |
|------|------|--------|-----------|
| 1 | cli | Search: "pitch deck for Series A" | "I need my investor materials" |
| 2 | cli | Show results from venture skill data — slides, financials, market analysis | "It found files across 3 different skills" |
| 3 | cli | Search: "what did we decide about local-first?" | "Now a conceptual search" |
| 4 | cli | Show ADR-006 and related memory entries | "165 architecture decisions, all searchable" |

**What proves Future Proof**: Your knowledge is indexed and survives tool changes.
**What proves Trust**: Sources are cited — you see exactly where answers come from.

---

##### Demo 5: /ask + Living Memory
**Category**: Knowledge
**Rank**: 4 (showcases the "second brain" identity)
**Principles**: Future Proof, Trust, Complexity
**Readiness**: GREEN — /ask workflow fully implemented with unified-search across all sources.
**Duration**: ~60s

| Step | Type | Action | Narration |
|------|------|--------|-----------|
| 1 | cli | `/ask What is special about Augur?` | "Let me ask my second brain" |
| 2 | cli | Show sourced answer citing README, ADRs, memory | "It synthesized from 165 ADRs, 35 skills, and curated memory" |
| 3 | cli | `/ask How many plugins does Augur have?` | "A factual question this time" |
| 4 | cli | Show precise count with skill registry source | "Exact answer, not hallucination — grounded in real data" |
| 5 | cli | `/learn` — record something from this session | "And now I'm teaching it something new" |
| 6 | cli | `/ask` the thing you just taught — show it's learned | "Immediate recall. My knowledge grows every session" |

**What proves Future Proof**: Knowledge persists across sessions, models, tools.
**What proves Trust**: Every answer shows its sources.
**What proves Complexity**: Simple /ask scales from basic lookup to cross-source synthesis.

---

##### Demo 6: One-Man Company — Venture Dashboard
**Category**: Domain
**Rank**: 6 (impressive breadth, but audience must care about business context)
**Principles**: Complexity, Future Proof, Pace
**Readiness**: YELLOW — Dashboard pages exist with 33 action buttons. Backend action execution not verified for all. Needs: verify top 5 actions actually work end-to-end.
**Duration**: ~90s

| Step | Type | Action | Narration |
|------|------|--------|-----------|
| 1 | dashboard | Navigate to `/venture` — show full business dashboard | "This is my entire business operations center" |
| 2 | dashboard | Click through tabs: Strategy, Market, GTM, Revenue, Finance | "8 business domains, all in one place" |
| 3 | dashboard | Click "Weekly Digest" action | "One click for my weekly business summary" |
| 4 | dashboard | Show Financials tab — runway calculator, P&L | "Real financial tracking, not spreadsheets" |
| 5 | dashboard | Click "Investor Update" — show generated report | "Investor-ready reports from my own data" |

**What proves Complexity**: 33 business actions from a single dashboard.
**What proves Future Proof**: All business data lives in your system, not SaaS tools.
**What proves Pace**: Start with overview, drill into any domain when ready.

---

##### Demo 7: Local Deep Integration — File Organizer
**Category**: Integration
**Rank**: 7 (strong local-first proof, but needs backend implementation)
**Principles**: Trust, Future Proof
**Readiness**: RED — UI shell only. No MCP tools, no file analysis/movement logic. Needs: full backend implementation.
**Duration**: ~75s

| Step | Type | Action | Narration |
|------|------|--------|-----------|
| 1 | dashboard | Navigate to `/productivity/organizer` | "My desktop is chaos — let's fix it" |
| 2 | dashboard | Click "Scan Desktop" — show file analysis results | "It analyzed 47 files — receipts, screenshots, PDFs, downloads" |
| 3 | dashboard | Show proposed renames and destinations | "AI suggested names and folders based on content" |
| 4 | dashboard | Approve batch — files move on local machine | "Everything reorganized — on MY machine, not uploaded anywhere" |
| 5 | dashboard | Show before/after file tree | "Local-first means your files never leave your computer" |

**What proves Trust**: You see every proposed rename/move before it happens.
**What proves Future Proof**: Your file organization is YOUR data, not a cloud service.

---

##### Demo 8: Cross-Workflow Integration — Career Pipeline
**Category**: Integration
**Rank**: 8 (most ambitious, highest integration complexity)
**Principles**: Complexity, Freedom, Future Proof
**Readiness**: RED — Framework in place, but Apple Notes ingestion, Gmail scanning, Bright Data LinkedIn scraping, and ranking pipeline all need implementation. Needs: 4 integration endpoints + orchestration flow.
**Duration**: ~120s

| Step | Type | Action | Narration |
|------|------|--------|-----------|
| 1 | dashboard | Navigate to `/career` — show pipeline overview | "My job search command center" |
| 2 | dashboard | Click "Pull Opportunities" | "Let's gather jobs from everywhere" |
| 3 | dashboard | Show Apple Notes scan — 2 saved jobs found | "Found 2 jobs I saved in Apple Notes last week" |
| 4 | dashboard | Show Gmail scan — 1 recruiter email found | "A recruiter email I hadn't processed" |
| 5 | browser | Show LinkedIn scraping via Bright Data MCP — 3 jobs parsed | "And 3 fresh listings from LinkedIn, parsed live" |
| 6 | dashboard | Show all 6 jobs in processing table | "6 opportunities from 3 sources, unified" |
| 7 | dashboard | Show AI ranking against user preferences | "Ranked against MY preferences — not an algorithm's" |

**What proves Complexity**: 3 data sources, 2 MCPs (local + remote), one unified pipeline.
**What proves Freedom**: Local MCP for Apple/Gmail, remote MCP for LinkedIn — both protocols.
**What proves Future Proof**: Job data captured in YOUR system, not locked in LinkedIn.

---

##### Demo 9: Plugin Architecture — Install/Remove
**Category**: Ecosystem
**Rank**: 9 (important for technical audience, less exciting visually)
**Principles**: Pace, Complexity
**Readiness**: GREEN — Plugin enable/disable via .config YAML works today (ADR-230).
**Duration**: ~45s

| Step | Type | Action | Narration |
|------|------|--------|-----------|
| 1 | dashboard | Navigate to admin plugins page — show all skills | "35+ skills, each self-contained" |
| 2 | dashboard | Disable a skill (e.g., wearables) — show it grays out | "Don't need wearables? Turn it off" |
| 3 | dashboard | Show its pages/tools disappear from navigation | "Gone from nav, gone from MCP, gone from search" |
| 4 | dashboard | Re-enable — show it comes back | "Back in one click — all state preserved" |
| 5 | cli | `/commands` — show commands filtered by active plugins | "Even CLI commands reflect your active skills" |

**What proves Pace**: Add or remove capabilities at your own speed.
**What proves Complexity**: One toggle cascades through UI, MCP, search, and CLI.

---

##### Demo 10: Knowledge Editing — IDE-Native
**Category**: Knowledge
**Rank**: 10 (niche but proves Trust deeply)
**Principles**: Trust, Freedom, Future Proof
**Readiness**: GREEN — Monaco editor with RTL support, /files pages, git integration all work.
**Duration**: ~60s

| Step | Type | Action | Narration |
|------|------|--------|-----------|
| 1 | dashboard | Navigate to `/files` — open a knowledge file (star-questions.md) | "My curated interview questions" |
| 2 | dashboard | Edit directly in the Monaco editor | "Full IDE-grade editing right in the dashboard" |
| 3 | dashboard | Show RTL support — switch to Hebrew content | "Even right-to-left languages work natively" |
| 4 | cli | In a different chat session: `/ask what are my star questions?` | "Another session instantly sees my edits" |
| 5 | cli | Show the answer includes the just-edited content | "No sync delay. My knowledge is live." |

**What proves Trust**: You edit your own knowledge files — plain markdown.
**What proves Freedom**: Edit in dashboard, query from CLI, any tool reads the same data.
**What proves Future Proof**: Markdown files outlive any tool.

---

#### NEW — Demos to Add

##### Demo 11: Self-Healing System (NEW)
**Category**: Automation
**Rank**: 2 (tied — visually dramatic, unique capability)
**Principles**: Trust, Complexity, Pace
**Readiness**: GREEN — Scanner, classifier, LLM repair all implemented. 13 log paths monitored.
**Duration**: ~90s

| Step | Type | Action | Narration |
|------|------|--------|-----------|
| 1 | dashboard | Navigate to `/observe/daemon` — show jobs and health | "My system runs 24/7 background jobs" |
| 2 | cli | Seed an error: introduce a typo in a config file | "Let me break something on purpose" |
| 3 | dashboard | Show self-heal scanner detecting the error | "Within seconds — detected, classified, severity assigned" |
| 4 | dashboard | Show LLM auto-fix kicking in (Haiku classifies, Sonnet fixes) | "AI is debugging and fixing it — no human intervention" |
| 5 | dashboard | Show fix applied, error resolved | "Fixed. Tested. Deployed. I didn't touch it." |
| 6 | cli | `/ops-inspect health` — show clean status | "The system heals itself while I sleep" |

**What proves Trust**: Every step visible — detection, classification, fix, verification.
**What proves Complexity**: Simple monitoring escalates to LLM-powered repair.
**What proves Pace**: Start with monitoring, add self-heal when you're ready to trust it.

**Why add**: Self-healing is Augur's most unique capability. No personal tool does this. It's the single most impressive thing to show an investor ("it fixes its own bugs").

---

##### Demo 12: Agent Swarm — Multi-Agent Coordination (NEW)
**Category**: Orchestration
**Rank**: 4 (tied — shows depth of AI integration)
**Principles**: Complexity, Trust, Freedom
**Readiness**: GREEN — Agent Teams framework live, used in multiple ADR implementations.
**Duration**: ~90s

| Step | Type | Action | Narration |
|------|------|--------|-----------|
| 1 | cli | `/orch-swarm` — show available presets | "Pre-built team formations for complex tasks" |
| 2 | cli | Launch a 3-agent team: developer + frontend + validator | "Three specialized agents, one task" |
| 3 | cli | Show agents claiming tasks, communicating via SendMessage | "They coordinate — developer codes, frontend styles, validator checks" |
| 4 | cli | Show parallel execution — all three working simultaneously | "All running at once, not sequentially" |
| 5 | cli | Show final result — committed code, tests passing | "A team of AI agents just shipped a feature" |

**What proves Complexity**: From single commands to coordinated agent teams.
**What proves Trust**: Every agent message and decision is visible.
**What proves Freedom**: Agents use whatever model fits — Haiku for checks, Sonnet for code, Opus for architecture.

**Why add**: Agent swarms are Augur's deepest AI capability. Shows it's not just a wrapper.

---

##### Demo 13: Cowork Export — Distribute Your Brain (NEW)
**Category**: Cross-Tool
**Rank**: 11 (niche but proves Freedom deeply)
**Principles**: Freedom, Future Proof
**Readiness**: GREEN — Full export pipeline works (ADR-135).
**Duration**: ~45s

| Step | Type | Action | Narration |
|------|------|--------|-----------|
| 1 | cli | `/dev-cowork-export` — run export | "Packaging my system for Claude Desktop" |
| 2 | cli | Show exported plugin structure — skills, commands, agents | "My knowledge, commands, and agents — all portable" |
| 3 | browser | Open Claude Desktop — show Augur skills available | "Now my second brain works in Claude Desktop too" |
| 4 | cli | Show MCP server serving tools to external clients | "Any MCP-compatible tool can connect" |

**What proves Freedom**: Export to any MCP-compatible platform.
**What proves Future Proof**: Your brain isn't trapped in one tool.

**Why add**: Directly proves Freedom principle — your system travels with you.

---

##### Demo 14: ADR-Driven Development (NEW)
**Category**: Knowledge
**Rank**: 12 (technical audience only, but proves Trust like nothing else)
**Principles**: Trust, Future Proof
**Readiness**: GREEN — 165 ADRs, /write-adr, /implement-adr all working.
**Duration**: ~75s

| Step | Type | Action | Narration |
|------|------|--------|-----------|
| 1 | cli | `/adr list --status implemented` — show 132 implemented decisions | "Every architectural decision recorded and searchable" |
| 2 | cli | `/ask Why did we choose local-first?` — show ADR-006 cited | "Ask WHY, get the actual decision record" |
| 3 | cli | `/write-adr "add dark mode to dashboard"` — show ADR generated | "Describe what you want — it writes the architecture" |
| 4 | cli | Show the generated implementation prompt at the bottom | "And it writes the execution plan — ready for agents" |
| 5 | cli | "This is decision #166. Every one is searchable, cross-referenced, and machine-executable." | |

**What proves Trust**: Every decision documented, every reason accessible.
**What proves Future Proof**: 165 decisions survive any team change, model change, or rewrite.

**Why add**: ADR-driven development is Augur's most distinctive methodology. For technical audiences, this is the credibility demo.

---

##### Demo 15: Dev Mode vs Operation Mode (NEW — Technical Audience)
**Category**: Ecosystem
**Rank**: 3 (tied — dramatically visual, proves architectural depth)
**Principles**: Trust, Pace, Complexity
**Readiness**: GREEN — Toggle works today via `Cmd+Shift+D`, all UI differences are live.
**Duration**: ~90s

| Step | Type | Action | Narration |
|------|------|--------|-----------|
| 1 | dashboard | Start in Operation mode — show clean dashboard with "Assistant" label, welcome overlay, suggested actions | "This is what a user sees. Clean, simple, no dev noise." |
| 2 | dashboard | Open chat — show auto-started CLI, "Message..." placeholder, Assets browser | "The assistant starts automatically. No setup needed." |
| 3 | dashboard | Show that floating action bar is completely hidden | "No dev tools, no data browser, no CLI selector — just actions" |
| 4 | dashboard | Press `Cmd+Shift+D` — toggle to Development mode | "Now watch — one shortcut to become the builder" |
| 5 | dashboard | Show the floating action bar appearing: Actions, Data Context, Dev Tools, Airplane Mode | "Full floating toolbar. Every MCP tool, every data source, every control." |
| 6 | dashboard | Show CLI selector dropdown — Claude, Cursor, Codex, Windsurf, Copilot, Kimi, Gemini | "Seven different AI bridges, switchable with ⌘1-⌘7" |
| 7 | dashboard | Show Chat/Terminal toggle, PID badge, pathname display, Deep Focus button | "Terminal view, process monitoring, focus control — all unlocked" |
| 8 | dashboard | Open Dev Tools menu — Sync Agents, Clear Cache, Skill Nav toggle | "Builder tools: sync agent rules across all IDEs, clear cache, toggle skill navigation" |
| 9 | dashboard | Show MCP tools list (full in dev) vs Actions list (curated in operation) | "Dev mode shows 358 MCP tools. Operation mode shows 5 relevant actions." |
| 10 | dashboard | Press `Cmd+Shift+D` again — back to Operation mode. Everything collapses. | "One toggle. Same system, two personas. User sees simplicity. Builder sees everything." |

**What proves Trust**: Dev mode hides nothing — every tool, every process, every data source is visible. You choose how much to see.
**What proves Pace**: Start as a user (operation mode). Grow into a builder (dev mode) when you're ready.
**What proves Complexity**: Operation mode is 5 actions. Dev mode is 358 tools. Same system, progressive disclosure.

**Why add for technical audience**: Engineers immediately ask "what's under the hood?" This demo answers that in 90 seconds. The visual contrast between the clean user experience and the full builder toolkit is the most concise proof that Augur scales from simple to powerful. It also shows the ModeToggle architecture — a Zustand store driving conditional rendering across 15+ components — which is a clean engineering pattern to discuss.

**Technical talking points during this demo:**
- Mode state persists in localStorage, survives refresh
- CLI auto-start in operation mode uses `autoContext: true` + `verbosity: 'quiet'`
- MCP tool filtering is server-side: `/api/mcp/tools/list?mode=operation` returns only page-relevant tools
- The floating action bar is a single conditional: `if (mode === 'operation') return null`
- Seven IDE adapters share one brain via canonical FocusPayload format

---

#### Principle Coverage Matrix

| Demo | Trust | Freedom | Pace | Complexity | Future Proof | Rank |
|------|:-----:|:-------:|:----:|:----------:|:------------:|:----:|
| 2: Cross-Tool Focus | **X** | **X** | | | | 1 |
| 16: Local OS Symphony (INTEL) | **X** | | | **X** | **X** | 1* |
| 11: Self-Healing (NEW) | **X** | | **X** | **X** | | 2 |
| 3: Parallel Workflows | **X** | | **X** | **X** | | 2 |
| 17: AI PC Advantage (INTEL) | | **X** | **X** | | **X** | 2* |
| 19: Skill Gate Visualizer (NEW) | **X** | | **X** | **X** | | 2 |
| 15: Dev vs Operation Mode (NEW) | **X** | | **X** | **X** | | 3 |
| 18: Always-On Daemon (INTEL) | **X** | | | **X** | **X** | 3* |
| 1: Skill Pull-In | | **X** | **X** | **X** | | 3 |
| 5: /ask + Memory | **X** | | | **X** | **X** | 4 |
| 12: Agent Swarm (NEW) | **X** | **X** | | **X** | | 4 |
| 4: RAG Search | **X** | | | | **X** | 5 |
| 6: Venture Dashboard | | | **X** | **X** | **X** | 6 |
| 7: File Organizer | **X** | | | | **X** | 7 |
| 8: Career Pipeline | | **X** | | **X** | **X** | 8 |
| 9: Plugin Install/Remove | | | **X** | **X** | | 9 |
| 10: Knowledge Editing | **X** | **X** | | | **X** | 10 |
| 13: Cowork Export (NEW) | | **X** | | | **X** | 11 |
| 14: ADR Development (NEW) | **X** | | | | **X** | 12 |

*\* Rank with asterisk = rank within Intel playbook specifically*

**Coverage per principle:**
- **Trust**: 13/19 demos (strongest coverage)
- **Complexity**: 12/19 demos
- **Future Proof**: 11/19 demos (boosted by Intel demos)
- **Freedom**: 6/19 demos (adequate)
- **Pace**: 8/19 demos

All 5 principles covered by at least 6 demos. No principle has zero coverage.

---

#### Readiness Summary

| Status | Count | Demos |
|--------|-------|-------|
| GREEN (works today) | 12 | #2 Focus, #4 RAG, #5 /ask, #9 Plugins, #10 Knowledge, #11 Self-Heal, #12 Swarm, #13 Cowork, #14 ADR, #15 Dev vs Ops, #16 Local OS Symphony, #18 Always-On Daemon |
| YELLOW (needs polish) | 4 | #1 Skill Pull-In, #3 Parallel Workflows, #6 Venture, #17 AI PC Advantage |
| RED (needs building) | 3 | #7 Organizer, #8 Career Pipeline, #19 Skill Gate Visualizer |

---

#### Recommendations

**Demos to prioritize for first investor demo** (top 5 by rank, all GREEN):
1. Demo 2: Cross-Tool Focus (60s) — unique differentiator
2. Demo 11: Self-Healing (90s) — most impressive to investors
3. Demo 5: /ask + Memory (60s) — "second brain" identity proof
4. Demo 12: Agent Swarm (90s) — depth of AI integration
5. Demo 4: RAG Search (45s) — knowledge retrieval credibility

Total: ~345s (~6 minutes). All GREEN readiness. Covers all 5 principles.

**Demos to cut or merge**:
- Demo 9 (Plugin Install/Remove) is mild — merge into Demo 1 (Skill Pull-In) as a "remove" step
- Demo 13 (Cowork Export) is niche — save for technical deep-dives, skip in investor demos
- Demo 14 (ADR Development) is meta — save for engineering audiences only

**Demos that need investment before they're demoable**:
- Demo 7 (Organizer): RED — needs full backend. High impact if built. Consider building specifically for demo.
- Demo 8 (Career Pipeline): RED — needs 4 integration endpoints. Highest complexity. Defer unless career is the primary audience.
- Demo 3 (Parallel Workflows): YELLOW — needs action button wiring on post cards. Medium effort, high visual payoff.

**Capability gaps — not covered by any demo**:
- **Notifications / Channels** (Telegram, macOS alerts) — add a demo: "get notified on your phone when a job matches"
- **Finance tracking** — could add to venture demo or standalone
- **Home automation** — too niche for most audiences, skip
- **Content creation end-to-end** (draft→review→publish→schedule) — Demo 3 partially covers but a full pipeline demo would be stronger

---

#### Intel AI PC — Demos for Local Machine & Hardware Story

Intel is looking for the **killer app for AI PC** — software that NEEDS powerful local hardware, deep OS integration, and on-device AI inference. Augur is that app. The narrative: **"Your laptop becomes your brain."**

**Why Augur is the AI PC killer app:**
1. **18 OS touchpoints** — Apple Notes (osascript), Calendar, Reminders, file watching (FSEvents), LaunchAgent daemons, Finder, clipboard, native notifications, IMAP email, local MCP server, Ollama, process monitoring, screenshots, voice memos, desktop inbox, system cleanup, IDE detection, port management
2. **Always-on daemon** — launchd-managed background service that monitors, classifies, and self-heals 24/7 — the kind of workload that justifies dedicated hardware
3. **Local-first by architecture** (ADR-006) — privacy is foundational, not bolted on. All data stays on-device.
4. **Already has local LLM profile** — Ollama with Llama 3.2 3B (q8_0) configured at `localhost:11434`, ready for NPU acceleration
5. **Cloud-to-local migration path** — self-heal classification (Haiku), task offloading (Kimi), search evaluation — all are small-prompt tasks that can shift to on-device inference

##### Demo 16: Local OS Symphony — "Your Laptop Is Alive"
**Category**: Integration
**Rank**: 1 (for Intel — this IS the pitch)
**Principles**: Trust, Future Proof, Complexity
**Readiness**: GREEN — all integrations work today, just need orchestrated demo flow.
**Duration**: ~120s

| Step | Type | Action | Narration |
|------|------|--------|-----------|
| 1 | dashboard | Navigate to `/home` — show dashboard with live system status | "This is my personal operating system. Running entirely on this laptop." |
| 2 | cli | `osascript` — show Apple Notes integration pulling my latest notes | "It reads my Apple Notes directly — no cloud sync, no API keys, osascript to the OS" |
| 3 | cli | Show calendar — today's events pulled from Apple Calendar | "My calendar, queried locally. Not through Google, not through an API — direct to the OS" |
| 4 | dashboard | Show daemon status — 7 background services running via LaunchAgent | "7 background daemons running 24/7 via macOS launchd. Self-healing, log monitoring, health checks." |
| 5 | cli | Show file watcher detecting a new file on Desktop | "Drop a file on the Desktop — Augur detects it in under 2 seconds via FSEvents" |
| 6 | dashboard | Show the file classified and routed to the right folder | "Classified by content, renamed, moved — all on-device" |
| 7 | cli | Show local MCP server running on localhost:6161 | "MCP server on localhost — any AI tool on this machine can connect. Claude, Cursor, Codex, Copilot." |
| 8 | dashboard | Show macOS notification pop up for a completed task | "Native macOS notifications. Not Electron. Not a web push. Real OS integration." |
| 9 | dashboard | Navigate to `/observe/daemon` — show all processes, PIDs, health status | "Every background process visible. Every PID tracked. Every health check logged." |
| 10 | cli | `lsof -i :3000 -i :6161` — show Augur's local network footprint | "Two ports. Dashboard on 3000, MCP on 6161. Everything local. Nothing leaves this machine." |

**Intel talking points:**
- "18 OS integration points — not a chatbot in a browser, an actual OS-level application"
- "launchd daemons — the kind of always-on workload that needs dedicated hardware"
- "FSEvents file watching — sub-second latency, hardware-optimized on macOS"
- "This is what a 'personal AI OS' looks like — and it gets faster with better hardware"

**What proves Trust**: Every process, PID, and health check is visible.
**What proves Future Proof**: All data local. No vendor dependency. Your laptop IS the server.
**What proves Complexity**: 18 integrations working in concert, invisible to the user until you look.

---

##### Demo 17: AI PC Advantage — Cloud-to-Local Migration
**Category**: Automation
**Rank**: 2 (for Intel — proves hardware investment pays off)
**Principles**: Future Proof, Freedom, Pace
**Readiness**: YELLOW — Ollama profile exists and adapter works. Needs: wiring self-heal classifier to use local model first, timing comparison script.
**Duration**: ~90s

| Step | Type | Action | Narration |
|------|------|--------|-----------|
| 1 | cli | Show `config/system/llm.yaml` — point to the 3 profiles: remote, local, agentic_ide | "Three inference profiles. Remote cloud, local Ollama, and IDE-routed." |
| 2 | cli | Show Ollama running locally with Llama 3.2 3B | "Local model running right now. 3 billion parameters, quantized to fit in 4GB RAM." |
| 3 | cli | Seed an error → show self-heal classifying it with **cloud Haiku** | "Self-heal detected an error. Classified in 1.2 seconds — but that was a round-trip to Anthropic's servers." |
| 4 | cli | Same error → show self-heal classifying with **local Llama on Ollama** | "Same classification, local model. 0.3 seconds. No network. No API key. No cost." |
| 5 | dashboard | Show side-by-side: cloud vs local latency, cost, privacy | "4x faster. Zero cost. Zero data leaving the machine." |
| 6 | cli | Show the offload tier system — low-tier tasks going local | "Every low-complexity task can run locally. Classification, search evaluation, quick lookups." |
| 7 | cli | Show which tasks stay cloud (Opus for architecture, Sonnet for coding) | "Complex reasoning still uses the best cloud models. The right model for the right task." |
| 8 | cli | "Now imagine this with an Intel NPU — not 0.3 seconds, but 30 milliseconds." | |

**Intel talking points:**
- "We already route tasks by complexity tier — haiku/sonnet/opus. Low-tier is the NPU target."
- "Self-heal runs 24/7. Every classification is a tiny inference. 100+ per day. Perfect NPU workload."
- "Ollama already works. The Intel NPU just makes it 10x faster and uses less battery."
- "The architecture is ready — `config/system/llm.yaml` already has the `local` profile."

**What proves Future Proof**: Architecture already separates local vs cloud. Hardware upgrade = instant benefit.
**What proves Freedom**: Choose cloud, local, or hybrid. No lock-in to any provider.
**What proves Pace**: Start with cloud. Add local when hardware supports it. Zero code changes.

---

##### Demo 18: Always-On Personal Daemon — "Your PC Never Sleeps"
**Category**: Automation
**Rank**: 3 (for Intel — justifies always-on hardware)
**Principles**: Trust, Complexity, Future Proof
**Readiness**: GREEN — daemon, all child processes, and dashboard monitoring all work today.
**Duration**: ~90s

| Step | Type | Action | Narration |
|------|------|--------|-----------|
| 1 | dashboard | Navigate to `/observe/daemon` — show 7 running child processes | "7 background agents running right now. Not cloud functions — local processes on this laptop." |
| 2 | dashboard | Show each service: log monitor, continuous executor, nightly maintainer, dashboard monitor, MCP health, runtime scanner, self-healer | "Log scanning. Health checks. Auto-maintenance. Self-repair. All local." |
| 3 | cli | Show the launchd plist — `KeepAlive: true`, auto-restart on crash | "macOS keeps it alive. Crashes? Auto-restart. Laptop reboot? Starts with the OS." |
| 4 | dashboard | Show daemon detecting a stale process (orphan PID) | "It found an orphaned process. PPID=1, reparented to launchd. That's a zombie." |
| 5 | dashboard | Show daemon cleaning it up — kill, verify, log | "Cleaned up. No human intervention. This happens every 5 minutes." |
| 6 | dashboard | Show nightly maintenance — log rotation, cache cleanup, index rebuild | "Every night at 3am: rotate logs, clean caches, rebuild indexes, check expirations." |
| 7 | cli | Show notification service — macOS notification + optional Telegram/Slack | "If something critical happens at 3am, it tells me. Native macOS notification." |
| 8 | dashboard | "This is why you need an AI PC. This daemon runs 24/7. More power = more intelligence, less battery drain." | |

**Intel talking points:**
- "This is a 24/7 workload. It's the reason someone needs a dedicated AI chip."
- "7 child processes doing continuous inference, log analysis, health checks — always on"
- "NPU offloads these micro-inference tasks from the CPU → better battery, better thermals"
- "The daemon already exists. We just need faster local inference to make it smarter."

**What proves Trust**: Every daemon action logged and visible in the dashboard.
**What proves Complexity**: 7 coordinated services — simple individually, powerful together.
**What proves Future Proof**: launchd integration means it survives reboots, OS updates, and hardware changes.

---

##### NPU Acceleration Opportunity Map

For the Intel conversation, this table maps current cloud workloads to local NPU targets:

| Workload | Current | Cloud Cost | Freq/Day | Local Model | NPU Benefit | Priority |
|----------|---------|-----------|----------|-------------|-------------|----------|
| Self-heal classification | Cloud Haiku | ~$0.02/call | 50-200 | Llama 3.2 3B | 4x faster, zero cost | **P0** |
| Task offloading (low-tier) | Cloud Kimi | ~$0.05/task | 20-50 | Llama 3.2 3B | 90% cost savings | **P0** |
| Search eval (iterative) | Cloud Haiku | ~$0.01/eval | 10-30 | Llama 3.2 3B | Instant, private | **P1** |
| Voice transcription | Not impl. | — | 5-10 | Whisper-tiny | 100x CPU speedup | **P1** |
| File content analysis | Not impl. | — | 10-50 | Llama 3.2 3B | Offline capable | **P2** |
| Screenshot OCR/analysis | Not impl. | — | 5-20 | CLIP-tiny | 50x CPU speedup | **P2** |
| Email classification | Cloud Haiku | ~$0.01/email | 20-50 | Llama 3.2 3B | Private, instant | **P2** |

**Estimated daily NPU workload**: 120-400 micro-inferences + 5-10 transcriptions
**Estimated savings**: $3-8/day in API costs → $90-240/month
**Estimated battery improvement**: CPU offload for inference tasks → 15-25% less CPU thermal

---

#### Audience-Specific Playbook Assembly

```yaml
# intel-ai-pc.yaml — 10 minutes, GREEN+YELLOW+RED(19), THE INTEL PITCH
demos: [16, 18, 11, 19, 17, 2]
narrative: "Your laptop becomes your brain — 18 OS integrations, always-on daemon,
  self-healing AI, 10-gate quality system, cloud-to-local migration path.
  This is the killer app for AI PC."
opener: "What if your laptop wasn't just a tool — but an extension of your mind?"
closer: "Every demo you just saw runs on this laptop. With an Intel NPU,
  it runs 10x faster, uses half the battery, and never needs the cloud for routine tasks."
notes: "Demo 19 (Gate Visualizer) is RED — build it before the Intel pitch.
  It's the 'enterprise rigor' proof that technical investors need."

# investor.yaml — 6 minutes, all GREEN
demos: [2, 11, 5, 12, 4]
narrative: "Your second brain that works everywhere, heals itself, and remembers everything"

# technical.yaml — 14 minutes, GREEN+YELLOW
demos: [15, 2, 12, 14, 11, 3, 1, 9]
narrative: "Dev vs Ops toggle, agent swarms, ADR-driven development, cross-IDE context, self-healing infra"

# new-user.yaml — 8 minutes, all GREEN
demos: [5, 4, 10, 2, 9]
narrative: "Ask anything, search everything, edit knowledge, use any tool, add skills when ready"

# partner.yaml — 10 minutes, GREEN+YELLOW
demos: [2, 13, 1, 6, 11, 5]
narrative: "Platform that exports to your tools, discovers your skills, runs your business"
```

### 5. Implementation Script

Create `scripts/demo-mode.sh` called by the workflow:

```bash
#!/bin/bash
# scripts/demo-mode.sh [on|off|status]
# Atomically toggles demo mode settings across all Claude Code instances
```

**Actions for `on`**:
1. Back up current `~/.claude/settings.json` → `runtime/demo/settings-backup-global.json`
2. Back up current `.claude/settings.local.json` → `runtime/demo/settings-backup-local.json`
3. Merge demo settings into `~/.claude/settings.json` (preserving existing keys)
4. Write `.claude/settings.local.json` with demo overrides
5. Write `runtime/demo/state.json` with `active: true`
6. Print confirmation with what changed

**Actions for `off`**:
1. Restore `~/.claude/settings.json` from backup
2. Restore `.claude/settings.local.json` from backup (or delete if no backup)
3. Delete `runtime/demo/state.json`
4. Print confirmation

**Actions for `status`**:
1. Read `runtime/demo/state.json`
2. Print active state, components, and activation time

## Consequences

**Positive**:
- One command to enter polished demo state — no manual toggles
- Reversible — `/demo off` restores exact prior state from backup
- Fast mode reduces visible latency during live demos
- Operation mode hides dev cruft that confuses non-technical audiences
- Extensible — Phase 2/3 components can be added incrementally via `components` array in state

**Negative**:
- Global settings changes affect ALL Claude Code instances (by design for demos, but could surprise if forgotten)
- Must remember to run `/demo off` after demo — stale demo state degrades normal workflow (reduced thinking tokens, hidden dev commands)
- Backup files in `runtime/demo/` could be lost if runtime is cleaned — mitigated by idempotent restore logic

**Neutral**:
- No dashboard code changes in Phase 1 — only settings files and a workflow
- Phase 2 dashboard changes (suggested actions, command filtering) are additive — no existing code modified
- Compatible with existing operation/development mode toggle — demo mode complements, doesn't replace

## Implementation Order

```
Phase 1: Fast Mode MVP
├── Step 1: Create scripts/demo-mode.sh (on/off/status logic)
├── Step 2: Create /demo workflow (agent-workflows/demo.md)
├── Step 3: Register workflow in registry.yaml via sync_agents.py
└── Step 4: Test toggle cycle (on → verify settings → off → verify restore)

Phase 2: Demo Experience (depends on Phase 1)
├── Step 5: Add dashboard mode switch to demo-mode.sh
├── Step 6: Add suggested actions override logic
├── Step 7: Add dev command filtering in /commands workflow
├── Step 8: Add simplified status line override
└── Step 9: Add auto-compact threshold override

Phase 3: Demo Playbooks (depends on Phase 2)
├── Step 10: Design playbook YAML schema (see Phase 3 section for spec)
├── Step 11: Create playbook runner in /demo workflow (/demo play investor)
├── Step 12: Write 14 demo playbook YAML files in plugins/ai/skills/ai_bridge/augur/data/demo/playbooks/
├── Step 13: Create 4 audience presets (investor.yaml, technical.yaml, new-user.yaml, partner.yaml)
└── Step 14: Wire /demo play command to read playbook, print narration, and execute steps

Phase 4: Demo Readiness — Build Missing Backends (depends on Phase 3)
├── Step 15: [RED/P0] Build Skill Gate Visualizer page at /professional/demo (Demo 19)
│   ├── Create plugins/professional/skills/venture-augur/augur/dashboard/demo/page.tsx
│   ├── Add page + tab to augur.yaml
│   ├── 5-stage factory stepper, 6-dimension radar chart, 10-gate checklist, lifecycle state diagram, profile cards
│   ├── Skill selector dropdown reading from assembled-hubs.json or MCP skill-list tool
│   └── Run mount-plugins to wire the page
├── Step 16: [YELLOW] Wire action dispatch buttons on content post cards (Demo 3)
├── Step 17: [YELLOW] Verify top 5 venture dashboard actions work end-to-end (Demo 6)
├── Step 18: [YELLOW] Connect Install skill import flow for external skill pull-in (Demo 1)
├── Step 19: [RED] Implement organizer skill backend — file analysis, rename, move (Demo 7)
└── Step 20: [RED] Implement career pipeline — Apple Notes + Gmail + Bright Data ingestion (Demo 8)
```

## Alternatives Considered

### 1. Dashboard-only demo mode

Add a "Demo Mode" toggle to the dashboard UI that changes visual presentation.

**Rejected**: Doesn't address the core need — CLI agent speed and terminal experience during demos. Dashboard is secondary; most demo value comes from showing Claude Code solving real problems fast.

### 2. Separate Claude Code profile

Create a `~/.claude/profiles/demo.json` that gets loaded via `CLAUDE_CODE_PROFILE=demo`.

**Rejected**: Claude Code doesn't support profile switching natively. Would require a wrapper script and env var manipulation that's fragile across terminal sessions. The settings.json merge approach is simpler and works with Claude Code's built-in settings hierarchy.

### 3. Per-session fast mode only

Just document "run `/fast` at the start of each demo session."

**Rejected**: Doesn't scale — forgets about dashboard mode, permission prompts, dev command visibility, and all the other presentation polish. The whole point is one command for the complete experience.

## References

- [Claude Code Fast Mode](https://code.claude.com/docs/en/fast-mode) — native fast mode documentation
- [Claude Code Settings](https://code.claude.com/docs/en/settings) — settings hierarchy and keys
- ADR-047: Chat-first UI for operation mode
- ADR-104: Terminal-wrapped operation mode (superseded ADR-047)
- ADR-130: Action dispatch modes (fire/oneshot/ide/modal)

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-168: Demo Mode Command**.

Read the full ADR: `docs/decisions/ADR-168-demo-mode-command.md`

### Team Orchestration

Create a team and spawn teammates to execute the plan below:

1. **Create team**: `TeamCreate(team_name="adr-168-demo-mode", description="Implementing ADR-168: Demo Mode Command")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role in the Execution Plan, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-168-demo-mode", name="{role}",
        model="{tier-model}", prompt="You are '{role}' on the adr-168 team.
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

**Team name**: `adr-168-demo-mode`

#### Phase 1: Fast Mode MVP
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | Create demo-mode.sh script with on/off/status subcommands. Reads/writes ~/.claude/settings.json and .claude/settings.local.json. Backs up to runtime/demo/. Uses jq for JSON merging. | `scripts/demo-mode.sh`, `runtime/demo/` |
| 1.2 | developer | medium | Create /demo workflow markdown with usage examples, argument parsing (on/off/status/toggle), and shell dispatch to scripts/demo-mode.sh | `plugins/ai/skills/ai_bridge/augur/data/agent-workflows/demo.md` |
| 1.3 | devops | low | Run sync_agents.py to register the new workflow in registry.yaml and distribute to IDE adapters | `plugins/ai/skills/ai_bridge/augur/data/ide-integration/registry.yaml` |
| 1.4 | validator | low | Test full toggle cycle: run /demo on, verify ~/.claude/settings.json has preferFastMode:true, verify .claude/settings.local.json has demo overrides, run /demo status, run /demo off, verify settings restored to original | All settings files |

#### Phase 2: Demo Experience Enhancements
**Strategy**: PARALLEL (steps 2.1–2.4 are independent)
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Add dashboard mode switch to demo-mode.sh — call curl or write localStorage-equivalent to set operation mode | `scripts/demo-mode.sh` |
| 2.2 | developer | medium | Add suggested actions override — write runtime/demo/suggested_overrides.json with curated demo actions (inbox, /ask, calendar, career pipeline) | `scripts/demo-mode.sh`, `runtime/demo/suggested_overrides.json` |
| 2.3 | developer | low | Add dev command filtering — modify /commands workflow to check runtime/demo/state.json and hide mode:dev workflows when demo active | `plugins/ai/skills/ai_bridge/augur/data/agent-workflows/commands.md` |
| 2.4 | developer | low | Add simplified status line and auto-compact threshold to demo-mode.sh settings merge | `scripts/demo-mode.sh` |

#### Final Phase: Verification
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task |
|------|-------|------|------|
| 3.1 | validator | low | Run all tests, verify no regressions (`pytest tests/src/`, `npm run build`) |
| 3.2 | validator | low | Verify /demo on → /demo status → /demo off full cycle works end-to-end with all Phase 1+2 components |
| 3.3 | devops | low | Run sync_agents.py --all to ensure all IDE adapters have the new command |

### Completion Criteria
- [ ] All phases executed
- [ ] All tests pass (`pytest tests/src/`, `npm run build`)
- [ ] No orphaned files or broken references
- [ ] /demo on → settings verified → /demo off → settings restored cycle passes
- [ ] ADR status updated to "Accepted" or "Implemented"

### How to Run
```
# Option 1: Use /implement-adr (handles team orchestration automatically)
/implement-adr docs/decisions/ADR-168-demo-mode-command.md

# Option 2: Paste this prompt into Claude Code
# The agent will create the team, spawn teammates, and coordinate
```
