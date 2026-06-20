---
status: Implemented
date: '2026-02-19'
deciders:
- Project team
related:
- ADR-086 (hub overview template)
- ADR-105 (hub-driven plugin architecture)
- ADR-109 (filesystem-driven dashboard)
- ADR-122 (plugin lifecycle)
hub: null
tags:
- smb
- design
- office
- content
- pipeline
superseded_by: null
---

# ADR-123: SMB Design Office Content Pipeline — Multi-Platform Social Media Posting

## Context

The SMB Design Office client (`client-smb-design` hub under `plugins/consulting/`) currently has only a bare Overview tab at `/client-smb-design`. The client (Danit Design — [danit-design.com/en](https://danit-design.com/en)) needs a content management pipeline for their personal brand across three platforms: **personal brand website**, **Facebook**, and **Instagram**.

The existing **LinkedIn Writer** skill (`plugins/career/skills/linkedin-writer/`) provides proven infrastructure for content drafting, management, and publishing workflows — markdown files with YAML frontmatter, a PostsList dashboard component, MCP tools for CRUD, API routes, and chain-based generation pipelines. This ADR reuses that architecture while adapting it for a fundamentally different use case:

**Key differences from LinkedIn Writer:**
1. **Multi-platform output** — each draft produces 3 variants (website, Facebook, Instagram) vs. single LinkedIn post
2. **Hebrew translation** — content must be translated to Hebrew with RTL-aware formatting rules
3. **Client brand context** — Danit Design is an AI-powered interior design studio (purple/pink aesthetic, bilingual EN/HE, democratizing professional design) vs. personal tech-founder brand
4. **Pipeline stages** — draft → brand tailoring → Hebrew translation → platform variants vs. brainstorm → draft → refine
5. **Platform constraints** — Instagram captions (2,200 chars, 30 hashtags), Facebook posts (longer form, link previews), website blog (HTML-friendly, SEO) vs. LinkedIn-only

**Current pain point:** The client pastes draft ideas into ad-hoc chats, then manually adapts them for each platform. There's no structured pipeline, no brand consistency enforcement, and no Hebrew translation workflow.

## Decision

### 1. New Tab: Content Pipeline

Add a `content-pipeline` tab to the `client-smb-design` hub.

**Dashboard route:** `/client-smb-design/content-pipeline`
**Source:** `plugins/consulting/skills/client-smb-design/augur/content-pipeline/`

The tab provides:
- **Draft Input Area** — textarea where the client pastes raw ideas/drafts
- **Pipeline Trigger** — button to run the content pipeline (via MCP tool or chain)
- **Posts List** — reuses the PostsList pattern from LinkedIn Writer (search, filter by status/platform, preview, actions)
- **Platform Variant Viewer** — side-by-side or tabbed view of website/Facebook/Instagram variants for each post

**Pipeline statuses:** `draft` → `processing` → `review` → `approved` → `published`

### 2. Content Pipeline Flow

```
Raw Draft (EN)
    ↓
[Stage 1: Brand Tailoring]
    Read brand context (voice-dna.json, brand-profile.json)
    Align tone, vocabulary, style to Danit Design brand
    ↓
Tailored Draft (EN)
    ↓
[Stage 2: Hebrew Translation]
    Translate to Hebrew
    Apply RTL formatting rules (minimize bidi issues)
    ↓
Tailored Draft (HE)
    ↓
[Stage 3: Platform Variants]
    ├── Website variant (blog-style, HTML-safe, SEO keywords, longer form)
    ├── Facebook variant (conversational, link preview friendly, 1-3 paragraphs)
    └── Instagram variant (caption ≤2200 chars, 20-30 hashtags, emoji-friendly)
    ↓
3 Markdown Files (one per platform, status: review)
```

### 3. Data Structure

```
plugins/consulting/skills/client-smb-design/
├── data/
│   ├── posts/                          # Content drafts (markdown + frontmatter)
│   │   └── YYYY-MM-DD-{slug}/
│   │       ├── draft.md                # Original raw draft (EN)
│   │       ├── tailored.md             # Stage 1 output: brand-aligned (EN)
│   │       ├── translated.md           # Stage 2 output: Hebrew translation
│   │       ├── website.md              # Stage 3 output: website variant (HE)
│   │       ├── facebook.md             # Stage 3 output: Facebook variant (HE)
│   │       └── instagram.md            # Stage 3 output: Instagram variant (HE)
│   └── context/
│       ├── voice-dna.json              # Danit Design tone & style
│       ├── brand-profile.json          # Business info, services, differentiators
│       └── platform-rules.json         # Per-platform constraints & formatting
```

**Post frontmatter schema:**
```yaml
---
title: "Post Title"
date: 2026-02-19
status: draft | processing | review | approved | published
platform: website | facebook | instagram
language: he
tags: [interior-design, ai-design, home-renovation]
source_draft: "slug-of-original-draft"
char_count: 1234
published_url: ""
published_at: ""
---
```

**Directory-based grouping:** Each draft is a directory (not a single file) because one idea produces 3+ variants. The `source_draft` frontmatter field links variants to their original draft.

### 4. Brand Context Files

**voice-dna.json** — Danit Design brand voice:
- **Tone:** Professional yet approachable, democratizing design, customer-centric
- **Vocabulary:** Interior design terms made accessible, AI-powered but human-centered
- **Style:** Aspirational, bilingual-aware, concise for social media
- **Avoid:** Overly technical jargon, hard-sell language, English-only idioms that don't translate
- **Hebrew rules:** Minimize mixed bidi text, prefer full-Hebrew sentences, transliterate brand names only when necessary

**brand-profile.json** — Business context:
- Company: Danit Design / Purely Intelligent Design
- Services: AI-powered interior design, space visualizations, tailored design solutions
- Audience: Young professionals, homeowners, budget-conscious design seekers
- Platforms: Website (danit-design.com), Facebook, Instagram, TikTok
- Color palette: Purple (#673de6), Azure (#357df9), Success green (#00b090)
- Tagline: Fast, transparent design process for everyone

**platform-rules.json** — Per-platform constraints:
- **Website:** Long-form blog, HTML formatting allowed, SEO meta description, 500-1500 words
- **Facebook:** 1-3 paragraphs, link preview, call-to-action, conversational tone, up to 63,206 chars
- **Instagram:** Caption ≤ 2,200 chars, 20-30 relevant hashtags, emoji-friendly, visual-first language

### 5. RTL Hebrew Translation Rules

The pipeline enforces these RTL-safe patterns:
1. **No mixed-direction lines** — if a line is Hebrew, keep numbers and short English terms (brand names) minimal
2. **Hashtags at end** — Hebrew hashtags (`#עיצוב_פנים`) placed at caption end to avoid bidi reordering
3. **No English mid-sentence** — transliterate or use Hebrew equivalents; brand name "Danit Design" stays as-is but isolated
4. **Paragraph breaks** — explicit `\n\n` between paragraphs (not HTML) for social media compatibility
5. **Emoji placement** — emojis at line start (LTR-neutral) or end, never mid-sentence where they disrupt RTL flow
6. **URL isolation** — links on their own line, never embedded in Hebrew text

### 6. Dashboard Components

**New files in `plugins/consulting/skills/client-smb-design/augur/content-pipeline/`:**

| File | Purpose |
|------|---------|
| `page.tsx` | Pipeline dashboard — draft input, stats, posts list, settings button |
| `DraftInput.tsx` | Textarea + "Save Draft" / "Save & Run Full Pipeline" buttons |
| `PostsList.tsx` | Adapted from LinkedIn Writer — filters by platform + status, per-stage buttons |
| `PostCard.tsx` | Single post card with stage buttons, variant viewer, edit/delete actions |
| `VariantViewer.tsx` | Tabbed view (Website / Facebook / Instagram) with RTL, copy, approve |
| `PipelineStages.tsx` | The 3-stage button bar with status indicators + "Run Full Pipeline" |
| `SettingsButton.tsx` | Opens brand context files (voice-dna.json, brand-profile.json) in system editor |

**Reused patterns from LinkedIn Writer:**
- Frontmatter parsing (`lib/posts.ts`)
- Status badges (draft=yellow, processing=blue, review=purple, approved=green, published=gray)
- Search + filter + pagination
- **Edit button** — opens `draft.md` in system default editor via API (same pattern as LinkedIn Writer's `/api/posts/open`)
- **Delete button** — confirmation modal with destructive warning, deletes entire post directory
- **Mark Published modal** — paste platform URL to record publication
- API routes for CRUD operations

### 6a. Brand Settings — Pre-filled Questionnaire

A **"Brand Settings"** button at the top of the page opens the brand context files for editing. These files are **pre-filled with guiding questions** so the client can fill in their brand identity without guessing what's needed.

**Settings button behavior:**
- Clicking "Brand Settings" opens a modal with two tabs: **English** and **Hebrew**
- Each tab shows the brand questionnaire as an editable form
- On save, writes back to `data/context/voice-dna.json` and `data/context/brand-profile.json`
- Alternative: "Open in Editor" button opens the JSON file in system editor (like LinkedIn Writer's edit pattern)

**Pre-filled voice-dna.json template with guiding prompts:**
```json
{
  "_instructions": "Fill in your brand voice. These guide how AI writes content for you.",
  "tone": "Describe your brand tone (e.g., professional, friendly, playful, authoritative)",
  "vocabulary": "Key terms and phrases your brand uses (industry jargon, brand-specific words)",
  "style": "How should posts feel? (e.g., short punchy sentences, storytelling, data-driven)",
  "avoid": ["List words or phrases to NEVER use in your content"],
  "hebrew_rules": {
    "transliterate_brand_name": true,
    "preferred_hashtag_language": "hebrew",
    "formal_or_informal": "Describe formality level for Hebrew content"
  }
}
```

**Pre-filled brand-profile.json template:**
```json
{
  "_instructions": "Fill in your business details. These personalize all generated content.",
  "company_name": "Your company/brand name",
  "tagline": "Your brand tagline or slogan",
  "services": ["List your main services or products"],
  "target_audience": "Who are your ideal customers?",
  "differentiators": ["What makes you different from competitors?"],
  "website_url": "https://your-website.com",
  "social_links": {
    "facebook": "https://facebook.com/your-page",
    "instagram": "https://instagram.com/your-handle"
  },
  "color_palette": {
    "primary": "#hex",
    "secondary": "#hex"
  },
  "contact_info": "Email or phone for CTAs"
}
```

**API route:** `posts/settings/route.ts` — GET reads context files, PUT writes updates back.
**MCP tool:** `get-smb-brand-settings` (read-only), `update-smb-brand-settings` (write)

### 7. API Routes

Create under `plugins/consulting/skills/client-smb-design/api/content-pipeline/`:

| Route | Method | Purpose |
|-------|--------|---------|
| `posts/route.ts` | GET | List all post groups with metadata + stage completion status |
| `posts/route.ts` | POST | Create new draft (save raw text to directory) |
| `posts/[slug]/route.ts` | GET | Get a specific post group (draft + intermediates + variants) |
| `posts/[slug]/route.ts` | DELETE | Delete entire post group directory |
| `posts/[slug]/status/route.ts` | PATCH | Update status of all variants in group |
| `posts/[slug]/publish/route.ts` | POST | Mark variant as published with URL |
| `posts/[slug]/open/route.ts` | POST | Open draft.md in system editor (reuses LinkedIn Writer pattern) |
| `posts/[slug]/pipeline/route.ts` | POST | Run pipeline — body: `{ stage: "tailor" \| "translate" \| "split" \| "all" }`. Returns stage output. |
| `settings/route.ts` | GET | Read brand context files (voice-dna.json, brand-profile.json) as JSON |
| `settings/route.ts` | PUT | Update brand context files from form data |
| `settings/open/route.ts` | POST | Open context file in system editor (body: `{ file: "voice-dna" \| "brand-profile" }`) |

### 8. MCP Tools

Register in `plugins/consulting/skills/client-smb-design/mcp/__init__.py`:

| Tool | Read-Only | Purpose |
|------|-----------|---------|
| `get-smb-content-status` | Yes | Get pipeline status, post counts by platform/status |
| `list-smb-content-posts` | Yes | List post groups with optional status/platform filter |
| `get-smb-content-post` | Yes | Get full post group (all variants + intermediates) by slug |
| `create-smb-content-draft` | No | Create new draft from raw text, save to data/posts/ |
| `run-smb-pipeline-stage` | No | Run a single pipeline stage: `tailor`, `translate`, or `split`. Validates precondition (previous stage output exists). |
| `run-smb-content-pipeline` | No | Run all 3 stages sequentially (tailor → translate → split) in one call |
| `update-smb-content-status` | No | Change status of a post group |
| `delete-smb-content-post` | No | Delete an entire post group directory |
| `get-smb-brand-settings` | Yes | Read brand context files (voice-dna.json, brand-profile.json) |
| `update-smb-brand-settings` | No | Update brand context files with new values |

### 9. Chain Definition

Create `plugins/consulting/skills/client-smb-design/chains/content_pipeline.yaml`:

```yaml
name: smb_content_pipeline
description: Transform raw draft into 3 Hebrew platform variants for Danit Design
category: vertical
triggers:
  - smb content pipeline
  - generate danit posts
  - create content variants

button:
  label: Run Content Pipeline
  page: /client-smb-design/content-pipeline

agents:
  - name: brand-tailor
    action: tailor_draft
    description: |
      1. Read brand context (voice-dna.json, brand-profile.json)
      2. Read raw draft from data/posts/{slug}/draft.md
      3. Rewrite in Danit Design voice — professional, approachable, design-focused
      4. Output tailored English draft
    output: tailored_draft

  - name: hebrew-translator
    action: translate_to_hebrew
    description: |
      1. Read tailored English draft
      2. Translate to Hebrew following RTL rules from voice-dna.json
      3. Apply RTL formatting constraints (no mixed bidi, hashtags at end, etc.)
      4. Output Hebrew draft
    output: hebrew_draft
    depends_on: brand-tailor

  - name: variant-generator
    action: generate_variants
    description: |
      1. Read Hebrew draft and platform-rules.json
      2. Generate 3 variants:
         a. Website: blog-style, longer form, SEO keywords
         b. Facebook: conversational, 1-3 paragraphs, CTA
         c. Instagram: ≤2200 chars, 20-30 hashtags, emoji-friendly
      3. Save each to data/posts/{slug}/{platform}.md with frontmatter
      4. Report char counts per variant
    output: variants
    depends_on: hebrew-translator
```

### 10. Tab Registration

Update `dashboard.yaml` to add the new tab:

```yaml
tabs:
- id: overview
  label: Overview
  icon: LayoutDashboard
  default: true
- id: content-pipeline
  label: Content Pipeline
  icon: PenLine
```

### 11. UI Concept — Step-by-Step Pipeline Controls

Each post in the list exposes **granular stage buttons** so the user can run stages independently or all at once. This gives full control over the pipeline while keeping the fast "do everything" path available.

#### Post Card Layout (expanded state)

```
┌─────────────────────────────────────────────────────────────────────┐
│  📝 Draft: "איך AI משנה עיצוב פנים ב-2026"                         │
│  Created: 2026-02-19  │  Status: draft  │  Tags: ai, interior      │
│─────────────────────────────────────────────────────────────────────│
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Raw Draft (EN)                                    [Edit ✏️] │    │
│  │  "AI is transforming interior design. Here's how we use     │    │
│  │   it at Danit Design to make professional spaces            │    │
│  │   accessible to everyone..."                                │    │
│  │                                              1,247 chars    │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  Pipeline Stages:                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐      │
│  │ 1. Tailor 🎨 │→ │ 2. Translate │→ │ 3. Split Platforms 📱│      │
│  │  [Run ▶]     │  │    🔤 [Run ▶]│  │         [Run ▶]      │      │
│  │  ✅ Done     │  │  ⏳ Pending  │  │     ⏳ Pending        │      │
│  └──────────────┘  └──────────────┘  └──────────────────────┘      │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │              [ ⚡ Run Full Pipeline ]                        │    │
│  │         Tailor → Translate → Split (all in one)             │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  Variants:  [Website 🌐]  [Facebook 📘]  [Instagram 📸]           │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  dir="rtl"                                                   │    │
│  │  AI משנה את עולם עיצוב הפנים. כך אנחנו ב-Danit Design       │    │
│  │  הופכים מרחבים מקצועיים לנגישים לכולם...                     │    │
│  │                                                               │    │
│  │                        1,089 chars │ [📋 Copy] [✅ Approve]  │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  Actions:  [Edit ✏️]  [Mark Published 🚀]  [Delete 🗑️]             │
└─────────────────────────────────────────────────────────────────────┘
```

#### Stage Buttons Behavior

| Button | Action | Precondition | Result |
|--------|--------|-------------|--------|
| **1. Tailor** | Calls `run-smb-pipeline-stage` with `stage=tailor` | `draft.md` exists | Creates `tailored.md` (EN, brand-aligned). Stage badge → ✅ |
| **2. Translate** | Calls `run-smb-pipeline-stage` with `stage=translate` | `tailored.md` exists | Creates `translated.md` (HE). Stage badge → ✅ |
| **3. Split Platforms** | Calls `run-smb-pipeline-stage` with `stage=split` | `translated.md` exists | Creates `website.md`, `facebook.md`, `instagram.md`. Stage badge → ✅ |
| **Run Full Pipeline** | Calls `run-smb-content-pipeline` (all 3 stages) | `draft.md` exists | Runs tailor → translate → split sequentially. All badges → ✅ |

#### Stage Status Indicators

Each stage shows one of:
- ⏳ **Pending** — not yet run (gray)
- 🔄 **Processing** — currently running (blue spinner)
- ✅ **Done** — output file exists (green)
- ❌ **Error** — stage failed (red, with retry button)

Stage status is derived from file existence in the post directory:
- `tailored.md` exists → Stage 1 done
- `translated.md` exists → Stage 2 done
- `website.md` + `facebook.md` + `instagram.md` exist → Stage 3 done

#### Variant Tabs (after Stage 3)

When all 3 platform variants exist, the **Variant Viewer** shows tabbed content:
- Each tab renders Hebrew content with `dir="rtl"` and `lang="he"`
- Shows character count and platform-specific limit indicator (e.g., "1,089 / 2,200" for Instagram)
- **Copy** button copies the variant text to clipboard
- **Approve** button sets that variant's status to `approved`

#### Page Header + Settings

```
┌─────────────────────────────────────────────────────────────────┐
│  Content Pipeline                        [⚙️ Brand Settings]   │
│  Draft → Tailor → Translate → Publish                          │
└─────────────────────────────────────────────────────────────────┘
```

The **Brand Settings** button opens a modal/page with pre-filled questionnaire forms for `voice-dna.json` and `brand-profile.json`. Both English and Hebrew guidance. "Open in Editor" fallback button for power users.

#### Draft Input Area

```
┌─────────────────────────────────────────────────────────────────┐
│  Paste your draft idea (English):                               │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                                                         │    │
│  │  [textarea — paste raw content here]                    │    │
│  │                                                         │    │
│  └─────────────────────────────────────────────────────────┘    │
│  0 chars                                                        │
│                                                                 │
│  ┌───────────────────┐  ┌──────────────────────────────────┐   │
│  │  💾 Save Draft    │  │  ⚡ Save & Run Full Pipeline     │   │
│  └───────────────────┘  └──────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

Three key buttons:
- **Save Draft** — creates the post directory + `draft.md`, status=`draft`. User can then run stages individually from the post card.
- **Save & Run Full Pipeline** — creates draft AND immediately runs all 3 stages. For quick "paste and go" workflow.
- **Brand Settings** (in header) — opens brand profile editor with pre-filled questions.

## Consequences

**Positive:**
- Client gets a self-service GUI for content creation across 3 platforms
- Brand consistency enforced by context profiles (voice-dna, brand-profile)
- Hebrew translation with RTL-safe rules reduces manual formatting fixes
- Reuses proven LinkedIn Writer patterns — lower development risk
- MCP tools enable both dashboard and chat-based workflows
- Directory-per-post grouping keeps variants organized

**Negative:**
- Hebrew translation quality depends on LLM capability — may need human review
- RTL formatting rules are heuristic, not guaranteed bidi-safe in all renderers
- Additional maintenance surface (context JSONs need periodic updates as brand evolves)
- Directory-per-post is slightly more complex than flat files (LinkedIn Writer uses flat)

**Neutral:**
- No changes to existing LinkedIn Writer skill — fully independent
- No changes to hub mounting or plugin architecture
- Platform-rules.json can be extended later for TikTok, Twitter/X

## Implementation Order

```
Phase 1: Data Foundation
├── Step 1: Create context JSON files (voice-dna.json, brand-profile.json, platform-rules.json)
│           Pre-fill with guiding questions/placeholders for client to complete
├── Step 2: Create data/posts/ directory structure
└── Step 3: Create lib/posts.ts with directory-based post group handling
            (includes intermediate file detection for stage status)

Phase 2: MCP Tools + Chain (depends on Phase 1)
├── Step 4: Register 10 MCP tools in mcp/__init__.py (including per-stage + settings)
├── Step 5: Create content_pipeline.yaml chain
└── Step 6: Update dashboard.yaml with content-pipeline tab

Phase 3: Dashboard UI (depends on Phase 1)
├── Step 7: Create DraftInput.tsx (save draft + save & run full pipeline)
├── Step 8: Create PipelineStages.tsx (3 individual stage buttons + run all)
├── Step 9: Create PostCard.tsx (expandable card with stages, variants, edit/delete)
├── Step 10: Create PostsList.tsx (list + filter + search + pagination)
├── Step 11: Create VariantViewer.tsx (tabbed RTL viewer with copy/approve)
├── Step 12: Create SettingsButton.tsx (brand settings modal with pre-filled forms)
└── Step 13: Create content-pipeline/page.tsx (assembles all components)

Phase 4: API Routes (depends on Phase 1)
├── Step 14: Create posts list/create routes
├── Step 15: Create posts CRUD routes (get, delete, status, publish, open-in-editor)
├── Step 16: Create pipeline execution route (per-stage + all)
└── Step 17: Create settings routes (read, write, open-in-editor)

Phase 5: Verification (depends on all)
├── Step 18: Run mount-plugins to generate dashboard files
├── Step 19: Verify all 3 pipeline stages work end-to-end
├── Step 20: Run stale path scanner
└── Step 21: Update ADR status to Implemented
```

## Alternatives Considered

### Alternative 1: Extend LinkedIn Writer with multi-platform support

Add Facebook/Instagram/Website as platform targets within the existing LinkedIn Writer skill.

**Rejected because:**
- LinkedIn Writer is career-hub scoped with personal tech-founder branding — mixing in a client's design brand creates context pollution
- The LinkedIn Writer's voice-dna.json and business-profile.json are specific to the Augur owner, not a consulting client
- Multi-tenant content in one skill violates separation of concerns
- Future clients would all crowd into the same skill

### Alternative 2: Create a standalone `content-pipeline` skill in a new hub

Create `plugins/career/skills/content-pipeline/` as a generic multi-platform content tool.

**Rejected because:**
- The pipeline is deeply client-specific (Danit Design brand, Hebrew, specific platforms)
- A generic tool would over-engineer for a single client's needs
- Placing it inside `client-smb-design` keeps all client-specific assets collocated
- Can always extract to a generic skill later if a pattern emerges across clients

### Alternative 3: External tool integration (Buffer, Hootsuite)

Use a third-party social media scheduling tool for multi-platform posting.

**Rejected because:**
- External tools don't have the brand context or LLM pipeline for Hebrew translation
- Adds external dependency and API costs
- Client wants to control the pipeline within the existing Augur dashboard
- Doesn't reuse existing infrastructure

## References

- LinkedIn Writer skill: `plugins/career/skills/linkedin-writer/`
- Client hub: `plugins/consulting/skills/client-smb-design/`
- Client website: https://danit-design.com/en
- ADR-086: Hub overview template standard
- ADR-105: Hub-driven plugin architecture
- ADR-109: Filesystem-driven dashboard

---

## Implementation Prompt

> Paste this into Claude Code to execute this ADR using Agent Teams.

You are implementing **ADR-123: SMB Design Office Content Pipeline — Multi-Platform Social Media Posting**.

Read the full ADR: `docs/decisions/ADR-123-smb-design-content-pipeline.md`

### Team Orchestration

Create a team and spawn teammates to execute the plan below:

1. **Create team**: `TeamCreate(team_name="adr-123-content-pipeline", description="Implementing ADR-123: SMB Design Content Pipeline")`
2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.
3. **Spawn teammates**: For each unique agent role in the Execution Plan, spawn a teammate:
   ```
   Task(subagent_type="general-purpose", team_name="adr-123-content-pipeline", name="{role}",
        model="{tier-model}", prompt="You are '{role}' on the adr-123 team.
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

**Team name**: `adr-123-content-pipeline`

#### Phase 1: Data Foundation
**Strategy**: PARALLEL
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 1.1 | developer | medium | Create voice-dna.json with Danit Design brand voice (professional, approachable, design-focused, Hebrew-aware). Reference the website danit-design.com/en for tone. Include RTL formatting rules. | `plugins/consulting/skills/client-smb-design/augur/context/voice-dna.json` |
| 1.2 | developer | medium | Create brand-profile.json with Danit Design business context (AI interior design, purple palette, bilingual, target audience). Reference the website. | `plugins/consulting/skills/client-smb-design/augur/context/brand-profile.json` |
| 1.3 | developer | medium | Create platform-rules.json with constraints for website (blog, SEO, 500-1500 words), Facebook (conversational, CTA), Instagram (≤2200 chars, hashtags, emoji). | `plugins/consulting/skills/client-smb-design/augur/context/platform-rules.json` |
| 1.4 | developer | medium | Create lib/posts.ts — directory-based post group handling. Reuse patterns from `plugins/career/skills/linkedin-writer/lib/posts.ts` but adapt for directory-per-post (draft.md + website.md + facebook.md + instagram.md). Functions: listPostGroups(), getPostGroup(), createDraft(), updateGroupStatus(), deletePostGroup(), parseFrontmatter(). | `plugins/consulting/skills/client-smb-design/lib/posts.ts` |
| 1.5 | developer | low | Create data/posts/.gitkeep and ensure directory structure exists | `plugins/consulting/skills/client-smb-design/augur/posts/.gitkeep` |

#### Phase 2: MCP Tools + Chain
**Strategy**: PARALLEL (depends on Phase 1)
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 2.1 | developer | medium | Register 10 MCP tools in mcp/__init__.py. Reuse patterns from `plugins/career/skills/linkedin-writer/mcp/__init__.py`. Tools: get-smb-content-status, list-smb-content-posts, get-smb-content-post, create-smb-content-draft, run-smb-pipeline-stage (single stage: tailor/translate/split), run-smb-content-pipeline (all stages), update-smb-content-status, delete-smb-content-post, get-smb-brand-settings, update-smb-brand-settings. Use directory-based post groups with intermediate files (tailored.md, translated.md). | `plugins/consulting/skills/client-smb-design/mcp/__init__.py` |
| 2.2 | developer | medium | Create content_pipeline.yaml chain with 3 stages: brand-tailor → hebrew-translator → variant-generator. Reference context files. | `plugins/consulting/skills/client-smb-design/chains/content_pipeline.yaml` |
| 2.3 | developer | low | Update dashboard.yaml — add content-pipeline tab with icon PenLine, add MCP tool names to tools array | `plugins/consulting/skills/client-smb-design/augur.yaml` |

#### Phase 3: Dashboard UI
**Strategy**: PARALLEL (depends on Phase 1)
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 3.1 | developer | medium | Create DraftInput.tsx — textarea for pasting raw ideas + two buttons: "Save Draft" and "Save & Run Full Pipeline". Include character counter. "Save Draft" calls POST /api/content-pipeline/posts, "Save & Run" calls POST then triggers /api/content-pipeline/posts/[slug]/pipeline with stage="all". | `plugins/consulting/skills/client-smb-design/augur/content-pipeline/DraftInput.tsx` |
| 3.2 | developer | medium | Create PipelineStages.tsx — 3-stage button bar (Tailor / Translate / Split Platforms) + "Run Full Pipeline" button. Each stage button shows status indicator (pending/processing/done/error). Calls POST /api/content-pipeline/posts/[slug]/pipeline with the specific stage. Derive stage status from file existence (tailored.md, translated.md, website.md+facebook.md+instagram.md). | `plugins/consulting/skills/client-smb-design/augur/content-pipeline/PipelineStages.tsx` |
| 3.3 | developer | medium | Create PostCard.tsx — expandable card for a single post group. Shows raw draft preview, PipelineStages component, VariantViewer (when variants exist), and action buttons: Edit (opens draft.md in editor via /api/.../open), Delete (confirmation modal, calls DELETE /api/.../[slug]), Mark Published (modal to paste URL). Adapt patterns from `plugins/career/skills/linkedin-writer/dashboard/PostsList.tsx`. | `plugins/consulting/skills/client-smb-design/augur/content-pipeline/PostCard.tsx` |
| 3.4 | developer | medium | Create PostsList.tsx — list of PostCard components. Adapted from LinkedIn Writer. Add platform filter (all/website/facebook/instagram), status filter (all/draft/processing/review/approved/published), search by title/tags, pagination (10 per page). | `plugins/consulting/skills/client-smb-design/augur/content-pipeline/PostsList.tsx` |
| 3.5 | developer | medium | Create VariantViewer.tsx — tabbed view (Website / Facebook / Instagram) showing the Hebrew content of each variant. Each tab: RTL text rendering (dir="rtl" lang="he"), char count with platform limit indicator (e.g. "1,089 / 2,200"), copy-to-clipboard button, approve button. | `plugins/consulting/skills/client-smb-design/augur/content-pipeline/VariantViewer.tsx` |
| 3.6 | developer | medium | Create SettingsButton.tsx — "Brand Settings" button in page header. Opens modal with two sections: voice-dna.json form and brand-profile.json form. Pre-filled with guiding questions/placeholders in English and Hebrew. Save writes back to context files via PUT /api/content-pipeline/settings. "Open in Editor" fallback button calls POST /api/content-pipeline/settings/open. | `plugins/consulting/skills/client-smb-design/augur/content-pipeline/SettingsButton.tsx` |
| 3.7 | developer | medium | Create content-pipeline/page.tsx — assembles header (with SettingsButton) + DraftInput + stats cards (draft/review/published counts per platform) + PostsList. Stats fetch from GET /api/content-pipeline/posts. Use glass-panel styling consistent with hub theme. | `plugins/consulting/skills/client-smb-design/augur/content-pipeline/page.tsx` |

#### Phase 4: API Routes
**Strategy**: PARALLEL (depends on Phase 1)
**Agents**:

| Step | Agent | Tier | Task | Files |
|------|-------|------|------|-------|
| 4.1 | developer | medium | Create posts list/create route — GET lists post groups with stage completion derived from file existence, POST creates new draft directory + draft.md. Reuse patterns from linkedin-writer API routes. | `plugins/consulting/skills/client-smb-design/api/content-pipeline/posts/route.ts` |
| 4.2 | developer | medium | Create posts CRUD routes — GET single post group (all variants + intermediates), DELETE post group directory, PATCH status update, POST mark published with URL, POST open draft in editor. | `plugins/consulting/skills/client-smb-design/api/content-pipeline/posts/[slug]/route.ts`, `.../[slug]/status/route.ts`, `.../[slug]/publish/route.ts`, `.../[slug]/open/route.ts` |
| 4.3 | developer | medium | Create pipeline execution route — POST with body `{ stage: "tailor" | "translate" | "split" | "all" }`. Validates preconditions (previous stage file exists). Returns stage output content. | `plugins/consulting/skills/client-smb-design/api/content-pipeline/posts/[slug]/pipeline/route.ts` |
| 4.4 | developer | medium | Create settings routes — GET reads voice-dna.json + brand-profile.json as JSON, PUT writes updates back. POST open opens context file in system editor. | `plugins/consulting/skills/client-smb-design/api/content-pipeline/settings/route.ts`, `.../settings/open/route.ts` |

#### Phase 5: Verification
**Strategy**: PIPELINE
**Agents**:

| Step | Agent | Tier | Task |
|------|-------|------|------|
| 5.1 | devops | low | Run mount-plugins to regenerate dashboard files in src/dashboard/app/client-smb-design/content-pipeline/ |
| 5.2 | validator | low | Verify dashboard builds without errors (`npm run build` in src/dashboard/) |
| 5.3 | validator | low | Verify MCP tools register without errors (check mcp/__init__.py imports) |
| 5.4 | architect | low | Verify ADR intent matches implementation — all 3 pipeline stages, 3 platform variants, Hebrew RTL rules, directory-based posts |
| 5.5 | devops | low | Run stale path scanner: `python3 .github/scripts/scan_stale_paths.py --ci` |
| 5.6 | devops | low | Update ADR-123 status to Implemented |

### Completion Criteria
- [ ] All phases executed
- [ ] All tests pass (`pytest tests/src/`, `npm run build`)
- [ ] No orphaned files or broken references
- [ ] Stale path scanner clean
- [ ] Content pipeline creates 3 Hebrew variants from an English draft
- [ ] Dashboard tab accessible at /client-smb-design/content-pipeline
- [ ] ADR status updated to "Implemented"

### How to Run
```
# Option 1: Use /implement-adr (handles team orchestration automatically)
/implement-adr docs/decisions/ADR-123-smb-design-content-pipeline.md

# Option 2: Paste this prompt into Claude Code
# The agent will create the team, spawn teammates, and coordinate
```
