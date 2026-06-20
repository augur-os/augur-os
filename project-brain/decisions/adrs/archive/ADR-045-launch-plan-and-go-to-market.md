---
status: Superseded
date: '2026-02-06'
deciders:
- Augur Team
related:
- ADR-042 (Help Button — In-Context Support & Monetization Channel)
hub: null
tags:
- launch
- plan
- market
- strategy
superseded_by: ADR-537
---

# ADR-045: Launch Plan & Go-To-Market Strategy

**Updated**: 2026-02-11 (incorporated GTM research findings)
**Supersedes**: ADR-044 (Server-Side Monetization — Revenue Stream Implementation)

## Context

ADR-044 defined a 4-tier monetization model (AI Operator, AI Builder, AI Expert, Enterprise) with 6+ revenue streams, certification programs, partner pages, and a $19/mo community. After critical review, this model was found to be over-engineered for a pre-launch open-source product with zero users:

- **4 tiers for 0 customers** — premature segmentation
- **Certification without ecosystem** — no market demand for Augur credentials
- **Partners page with no partners** — aspirational pages damage credibility
- **$19/mo community** — paid communities are hard to retain without critical mass
- **Course bundled with cert** — over-complicated a simple value prop
- **Enterprise redirect to guriqo.com** — breaks Augur brand experience

Augur is an open-core product. The business model combines open-source distribution for trust and ecosystem growth with paid product offerings and services revenue — similar to early-stage GitLab, Sentry, or pre-license-change Hashicorp. The revenue model must be simple enough to execute as a single founder.

### GTM Research Findings (2026-02-11)

Deep market research identified 7 gaps in the original plan. This update incorporates all findings:

1. **No licensing layer** — everything treated as uniformly "open" with no open vs commercial distinction
2. **Zero product revenue** — only services (sessions, course, consulting), no recurring product revenue stream
3. **No segment focus** — implicitly targets everyone; no priority stack for resource allocation
4. **No hero plugin** — all plugins treated equally; no lead product to anchor launch narrative
5. **Weak onboarding** — `git clone` is fine for devs, insufficient for knowledge workers
6. **No competitive positioning** — tactical plan without narrative differentiation vs competitors
7. **No investment strategy** — no documented stance on bootstrap vs raise

## Decision

### Open-Core Licensing Model

Augur uses a layered licensing model that maximizes trust and distribution via open source while protecting commercial revenue:

| Layer | License | Contents |
|-------|---------|----------|
| **Open Core** | Elastic License 2.0 | Runtime, MCP gateway, plugin system, data formats, CLI tooling, dashboard shell, basic plugins |
| **Commercial** | Proprietary | Premium plugin packs, cloud backup/sync, team features, managed hosting |

#### What is Always Open

- `src/` — Core framework (runtime, config, path resolution, MCP server)
- `plugins/` — Plugin system, skill interfaces, basic plugin implementations
- `src/dashboard/` — Dashboard UI shell and component library
- `docs/` — All documentation, ADRs, guides
- Data formats — YAML/Markdown schemas, SKILL.md contracts, chain definitions

#### What is Commercial (Current or Planned)

| Commercial Offering | Type | Timeline |
|---------------------|------|----------|
| Career Pro Pack | Premium plugin features | Launch (v0.1.0) |
| Cloud Backup & Sync | Recurring SaaS | v0.2.0 (Month 2-3) |
| Domain Plugin Packs (Finance, Health) | Premium bundles | v0.3.0 (Month 4-6) |
| Team & Multi-user Features | Enterprise tier | v0.4.0 (Month 6+) |

#### Trademark Policy

"Augur" name and logo cannot be used by forks for commercial offerings. Forks must rebrand. This protects brand value independent of code.

#### Why Elastic License 2.0 (Not AGPL or MIT)

- **vs MIT/Apache**: Too permissive — allows hosted clones without contribution back
- **vs AGPL**: Forces all modifications to be src/lib, which deters some enterprise adopters
- **vs Elastic 2.0**: Source-available, allows self-hosting and modification, prevents offering as competing managed service. Already in place. Proven model (Elasticsearch, Kibana).

### Target Customer Segments (Priority Stack)

Not all segments can be served equally by a solo founder. Explicit priority for the next 12 months:

#### Primary Beachheads (Months 1-6)

| Segment | Profile | What They Value | GTM Tactic |
|---------|---------|-----------------|------------|
| **Type 4: AI Builders** | No-code/low-code builders who want to ship AI apps for others | Structured substrate for workflows, model agnosticism, plugin packaging | Deep docs, example gallery, "Build a career plugin in a weekend" content, early builder program |
| **Type 2: Knowledge Workers** | Privacy-minded professionals who understand AI value but distrust Big Tech silos | Local-first data sovereignty, opinionated starter kits, "just works" install | Starter packs, course as onboarding funnel, "replace Notion with files you own" narrative |

**Why these two first:**
- AI builders create plugins that serve all other segments (ecosystem flywheel)
- Knowledge workers are early adopters who tolerate setup complexity and give high-signal feedback
- Both segments have strong organic distribution channels (dev communities, privacy forums)

#### Secondary (Months 3-9, Opportunistic)

| Segment | Profile | What They Value | GTM Tactic |
|---------|---------|-----------------|------------|
| **Type 1: Simple Users** | ChatGPT/Claude power users who want more | Out-of-box plugins replacing SaaS (career, health, finance) | 1-click recipes, low-friction install, freemium with upsell to pro packs |
| **Type 3: SMBs** | Small businesses drowning in expensive SaaS | Fast, cheap replacement for Notion+Asana+Helpdesk stack | Consulting/solution delivery on top of Augur, 1-3 case studies, charge real money |

#### Deprioritized (Months 6+, Inbound Only)

| Segment | Profile | Approach |
|---------|---------|----------|
| **Type 5: Enterprise** | Orgs looking to 10x their people bottom-up | Do NOT chase. If inbound comes, frame as paid pilot/consulting ($20-100k). Contact form on augur.run captures demand signal. |

### Launch Day Offerings (4 Revenue Streams)

| Offering | Price | Payment | Revenue Type | Status at Launch |
|----------|-------|---------|--------------|------------------|
| 1:1 Sessions with Gur | $149/hr | Cal.com → Stripe | Services (time-for-money) | Live, bookable |
| "Build Your Personal AI OS" Course | $39 pre-sale (→ $79 at release) | Stripe Payment Link | Education (one-time) | Pre-sale, delivers 4-6 weeks post-launch |
| Career Pro Pack | $49 one-time | Stripe Payment Link → license key | Product (one-time) | Live at launch |
| Enterprise / Custom AI Consulting | Custom | Contact form on augur.run | Services (project-based) | Contact form → email |

**Post-launch additions (Month 2-3):**

| Offering | Price | Revenue Type | Timeline |
|----------|-------|--------------|----------|
| Cloud Backup & Sync | $7/mo | Product (recurring!) | v0.2.0 |
| Domain Plugin Packs (Finance, Health) | $29-99 one-time | Product (one-time) | v0.3.0 |

#### Career Pro Pack: Free vs Paid Split

| Feature | Free (Open Core) | Career Pro ($49) |
|---------|-------------------|------------------|
| Job tracker (YAML storage) | Yes | Yes |
| Basic CV tailoring (Markdown) | Yes | Yes |
| Company research via web search | Yes | Yes |
| Status tracking (Applied → Interview → Offer) | Yes | Yes |
| ATS-aware CV optimization | — | Yes |
| Interview prep question generation | — | Yes |
| Salary negotiation scripts | — | Yes |
| Network relationship tracker | — | Yes |
| Multi-format export (PDF, DOCX) | — | Yes |

#### Payment Infrastructure (Minimal for Launch)

- Stripe account + payment links (no custom checkout)
- License key system: buy → email key → enter in `config.yaml` → unlock features
- Key validation on startup (simple HTTP call or local hash check)
- No user accounts, no login, no subscription management (use Stripe billing portal for recurring when backup launches)

### Hero Plugin Strategy: Career OS

Career is the launch hero. All launch marketing leads with Career because:

1. **Universal need** — all 5 customer types need career management
2. **Replaces paid SaaS** — Huntr ($40/mo), Teal ($29/mo), JobScan ($20/mo) = concrete value proposition
3. **Most complete plugin** — job tracking, CV tailoring, interview prep, scoring already functional
4. **Demonstrates the full stack** — AI + local data + MCP + dashboard working together
5. **Clear free-to-paid upgrade path** — basic tracking free, pro features paid

**How this affects launch assets:**
- Demo video: 60% Career OS, 40% platform overview
- README hero section: Career OS screenshot/GIF
- LinkedIn warmup: career/job-search pain point narratives
- HN post: "Show HN: I replaced $90/mo of career SaaS with a local AI OS"
- Landing page: Career OS as the "try this first" CTA

Other plugins (health, home-automation, linkedin-writer) are "also included" but Career is the lead story.

### Installer & Onboarding Path

**Test criterion**: Can a non-technical friend install Augur and use Career plugin without your help in under 10 minutes?

#### Single-Command Installer (Mac/Linux)

```bash
curl -fsSL https://augur.run/install.sh | bash
```

The installer script:
1. Checks prerequisites (Python 3.11+, Node 18+, git)
2. Clones repo to `~/.augur/` (or user-specified path)
3. Creates `data/` directory with starter config
4. Auto-detects installed IDEs (VS Code, Cursor, Windsurf, Claude Code)
5. Configures MCP server for detected IDEs
6. Enables starter plugins (Career basic, Eisenhower, file-organizer)
7. Launches dashboard on `localhost:3000`
8. Prints "Next steps" with 3 actions to try

#### First-Run Experience

After install, user sees:
1. Dashboard loads with Career plugin active
2. Guided "Add your first job" flow (3 fields: company, role, URL)
3. "Tailor your resume" action with sample job description
4. Result: tailored resume in `data/career/` as Markdown file they can open

#### Fallback: Manual Install

For users who don't trust `curl | bash`:
```bash
git clone https://github.com/augur-ai/augur.git
cd augur && ./setup.sh
```

### Competitive Positioning Narrative

#### Category Definition

Augur is not "just" a second brain, not "just" an agent framework, and not "just" an AI IDE extension. Category: **Personal AI operating system / cognitive infrastructure**.

Core job: Be the persistent, local, model-agnostic layer that stores all personal/work knowledge in plain text you own, exposes it to any LLM and interface, and enforces human-in-the-loop safety.

#### Market 2x2: Where Augur Sits

```
                    Human-Centric (you architect the system)
                              |
                    Obsidian   |   AUGUR
                    Logseq     |   (full Life OS + AI-native)
                              |
    Cloud-centric ────────────┼──────────── Local-first
                              |
                    Notion AI  |   Clawdbot
                    Mem.ai     |   (self-hosted but "always-on landlord")
                    Copilot    |
                    Gemini     |
                              |
                    Automation-First (we optimize you)
```

Augur owns the **top-right quadrant**: local-first AND human-centric. No dominant brand currently occupies this position.

#### Positioning One-Liners (Use in Marketing)

**Against Big Tech assistants (Apple Intelligence, Gemini, Copilot):**
> "They optimize you in their cloud. Augur lets you design your own optimization, on your machine."

**Against PKM SaaS (Notion AI, Mem.ai):**
> "They store your notes in proprietary blobs. Augur turns your life into a human-readable, AI-ready knowledge base you fully own."

**Against Clawdbot (self-hosted assistant):**
> "Always-on agents building a model of you. Augur is an OS where you define every skill and gate — no dark patterns, no silent rewiring."

**Against agent frameworks & IDEs (AutoGPT, CrewAI, Cursor, Windsurf, Antigravity):**
> "They are how you execute work. Augur is where your long-term memory, preferences, and life workflows live."

**Universal positioning statement:**
> "Augur is the local-first AI operating system for your life. Not a chatbot, not another notes app — a personal AI stack you deploy for yourself. Your data lives in plain text on your machine. Any model, any tool — Claude, GPT, Ollama, Cursor, Windsurf — connects through one MCP gateway. Skills are small, composable units that run with explicit approval, so you stay the architect of your system instead of becoming the product of someone else's."

#### Key Narrative Angles by Distribution Channel

| Channel | Primary Angle | Emotional Hook |
|---------|---------------|----------------|
| Hacker News | Architecture + local-first + Unix philosophy | "I replaced $90/mo of SaaS with grep-able YAML files" |
| r/selfhosted | Data sovereignty + self-hosting | "Your AI memory that survives any vendor shutdown" |
| r/LocalLLaMA | Model agnosticism + MCP gateway | "One substrate for Claude, GPT, Ollama — switch anytime" |
| r/artificial | Human agency vs automation | "Do you want an AI landlord or a house you designed?" |
| r/commandline | CLI experience + composability | "Unix philosophy for the AI age: small skills, pipes as chains" |
| LinkedIn | Career transformation + AI adoption | "How I built my own career OS that replaced 3 paid tools" |
| Product Hunt | Visual showcase + value prop | "Personal AI OS — replace Notion + career tools, own your data" |

### Investment & Bootstrap Strategy

**Decision: Bootstrap first.** Do not seek investment before product-market fit.

#### Rationale

- Services revenue (sessions, course, consulting) funds product development
- Early-stage infra funding without traction pushes toward hyper-growth expectations and premature product surface expansion
- Open-core model is compatible with later funding — investors are more comfortable when OSS is already structured and monetized
- Solo founder freedom > investor timeline pressure at this stage

#### Raise Triggers (When to Reconsider)

Consider investment conversations only if ALL of these are true:
- 500+ GitHub stars (community signal)
- 20-50 paying users across product offerings
- $3-10k MRR from mix of premium features + course + consulting
- Clear, repeatable pull from a segment (especially enterprise/SMB)
- Capital needed primarily to hire (dev, docs, community) and de-risk burnout

#### Revenue Sustainability Plan

| Phase | Timeline | Revenue Target | Sources |
|-------|----------|----------------|---------|
| Survival | Months 1-3 | $1-3k/mo | Sessions + course pre-sales + Career Pro |
| Stability | Months 3-6 | $3-8k/mo | + Cloud backup recurring + more plugin packs |
| Scale decision | Month 6+ | $8-15k/mo | + Enterprise pilots + consider raise |

Continue Guriqo consulting separately if income gap exists. Augur revenue is growth capital, not survival income, until Month 6.

### Kill List

| Removed | Rationale |
|---------|-----------|
| certification.html | No ecosystem demand. Certifications need employer/client pull. |
| partners.html | No partners. Empty page = credibility damage. |
| AI Operator tier | Non-technical users don't adopt open-source CLI tools. |
| AI Expert tier | Certification bundle premature. Sessions + course cover the need. |
| $19/mo community | Need volume over revenue. Community must be free at launch. |
| guriqo.com redirect for enterprise | Breaks Augur brand. Enterprise inquiry stays on augur.run. |

### Pages on augur.run at Launch

| Page | Purpose | Status |
|------|---------|--------|
| index.html | Landing page with hero video (Career OS lead), plugin showcase, 3 CTAs | Update existing V14 |
| sessions.html | Book 1:1 with Gur ($149/hr) via Cal.com | Rename/rework expert.html |
| course.html | Pre-sale landing for "Build Your Personal AI OS" ($39) | Rework existing |
| enterprise.html | Contact form for org consulting | New (replaces guriqo redirect) |
| support.html | Support system | Keep as-is |
| terms.html | Legal terms | Keep as-is |

### Course: "Build Your Personal AI OS"

Six modules covering the most accessible, course-worthy plugins:

| Module | Plugin(s) | AI Concept Taught |
|--------|-----------|-------------------|
| 1. Install & First Plugin | file-organizer, eisenhower | AI task delegation, structured data |
| 2. Apple Integration | apple | Local AI + native OS integration |
| 3. Home Automation | home-automation | IoT + AI orchestration |
| 4. Health + Lifestyle | health, lifestyle | Personal data modeling |
| 5. LinkedIn Writer | linkedin-writer | AI content generation workflows |
| 6. Build Your Own Plugin | mcp-app-factory | Plugin architecture, MCP basics |

Launch model: **pre-sale at $39** (launch price), full price $79 after delivery. Course ships 4-6 weeks post-launch. Money-back guarantee if course doesn't ship on time. Email capture for non-buyers.

Plugins NOT course-worthy at launch: infrastructure plugins (router, executor, daemon, renderer, swarm, plugins), developer tooling (developer, devops, architect, security — too internal), skeleton plugins (enterprise, finance, wearables, scraper — incomplete).

### Session Pricing Rationale

$149/hr, not $99. The people willing to pay for 1:1 with the creator of an open-source tool will pay $149. The ones who won't pay $149 also won't pay $99 — it's not the price sensitivity boundary. Fewer sessions at higher rate = same revenue, more time for product work.

### Enterprise on augur.run (Not Guriqo)

Enterprise inquiry form lives on augur.run/enterprise.html. Does NOT redirect to guriqo.com. Guriqo is credited as "Powered by Guriqo" in footer for credibility. Rationale: sending potential enterprise customers to a different domain breaks the Augur brand experience and creates confusion about what they're buying.

## Launch Distribution Strategy

### Pre-Launch: T-14 Days (LinkedIn)

3 warmup posts on personal LinkedIn:
1. **The Problem Post** — "Why I'm not 10x yet" — Three Cracks narrative, no product mention
2. **The Journey Post** — "I quit relying on one AI vendor" — personal story, mention open-sourcing soon
3. **The Teaser Post** — 30-second screen recording of Augur Career OS in action, waitlist CTA

### Launch Day: Coordinated Blitz

**Morning (8 AM IST):**
- GitHub repo goes public, tagged v0.1.0
- augur.run updated with all launch pages
- LinkedIn launch post (strongest piece, GitHub star CTA)

**Mid-morning:**
- Hacker News "Show HN: I replaced $90/mo of career SaaS with a local AI OS" (link to repo, minimal text)
- Respond to EVERY HN comment for first 6 hours

**Afternoon:**
- Reddit posts tailored per subreddit:
  - r/selfhosted — local-first, data ownership angle
  - r/LocalLLaMA — multi-model, provider-agnostic angle
  - r/artificial — broader AI future framing
  - r/commandline — CLI experience

**Optional (T+1 to T+7):**
- Product Hunt launch (better with polished demo video, can delay)

### Post-Launch Content: T+1 to T+7

- Day 2: Technical deep-dive (plugin architecture) on LinkedIn
- Day 3-4: Plugin spotlight posts (Career OS deep-dive, home-automation)
- Day 5: "48 hours after launch" transparency post
- Day 7: Course announcement + pre-sale link

## Critical Assets Required

### 1. README.md (Most Important Document)

Structure:
1. One-liner + badge row (stars, license, version)
2. 30-second demo GIF/video (Career OS as hero)
3. "What is Augur?" — 3 sentences max
4. Quick install — `curl | bash`, works in under 2 minutes
5. Plugin catalog — table with one-line descriptions
6. Architecture diagram
7. "Why Augur?" — Three Cracks condensed to 3 bullets
8. Contributing link
9. License
10. Links (website, course, sessions, community)

### 2. "Augur in 90 Seconds" Demo Video

- 0-10s: Terminal, one install command (`curl | bash`)
- 10-20s: Dashboard loads, Career plugin visible
- 20-35s: Add a job, see it tracked in YAML
- 35-50s: Tailor resume with AI (show MCP query → result)
- 50-65s: Show data files (cat the YAML — "this is YOUR data")
- 65-80s: Quick montage of other plugins (health, home-automation)
- 80-90s: End card with GitHub URL + "Star us" CTA

No voiceover. Text overlays + terminal action. Career OS is 60% of the video.

### 3. Installer Script (`install.sh`)

Single-command installer for Mac/Linux that:
- Checks prerequisites, clones, configures, enables starter plugins
- Prints clear "what to do next" instructions
- See "Installer & Onboarding Path" section above for full spec

### 4. Sessions Page Social Proof

- Short video: Gur explaining what a session covers
- 2-3 testimonials from existing consulting clients
- Clear "what you'll walk away with" list

## Pre-Launch Checklist

### Week 1: Foundation
- [x] Genericize client plugins (client-terminal-automation, client-smb-design, client-ai-consulting)
- [x] Run security audit on public codebase
- [x] Remove hardcoded paths, personal data references
- [x] Write README.md
- [x] Create CONTRIBUTING.md
- [x] Set up GitHub Actions (lint + test)
- [x] Choose and add LICENSE file (Elastic 2.0)
- [x] Validate: user data loads from data/ at runtime, plugins functional
- [ ] Define open-core licensing matrix (which dirs are open vs commercial)
- [ ] Design Career Pro free/paid feature split
- [ ] Create install.sh single-command installer
- [ ] Create CODE_OF_CONDUCT.md

### Week 2: Content & Pages
- [ ] Record "Augur in 90 Seconds" demo video (Career OS hero)
- [ ] Update index.html with launch messaging + competitive positioning
- [ ] Rename expert.html → sessions.html, simplify
- [ ] Rework course.html for pre-sale model
- [ ] Create enterprise.html on augur.run
- [ ] Delete certification.html and partners.html
- [ ] Set up Stripe payment link for course pre-sale ($39)
- [ ] Set up Stripe payment link for Career Pro Pack ($49)
- [ ] Implement license key system (buy → email key → config.yaml → unlock)
- [ ] Verify Cal.com → Stripe booking flow ($149/hr)

### Week 3: Distribution Prep
- [ ] Write all LinkedIn posts (warmup + launch + follow-ups) using positioning one-liners
- [ ] Draft Show HN post (multiple title variants, Career OS lead)
- [ ] Draft Reddit posts per subreddit (see channel-specific angles table)
- [ ] Prepare Product Hunt page (optional)
- [ ] Set up Discord or GitHub Discussions
- [ ] Collect 2-3 client testimonials for sessions page
- [ ] Create early builder program invite (private channel for Type 4 AI builders)

### Week 4: Polish & Launch
- [ ] Tag v0.1.0 on GitHub
- [ ] Final test: clean-machine install via `install.sh` following README
- [ ] Final test: Career Pro purchase → license key → feature unlock
- [ ] Final test: Cal.com booking flow end-to-end
- [ ] Final test: Stripe pre-sale flow end-to-end
- [ ] Publish pre-launch LinkedIn posts
- [ ] **Launch day: execute coordinated blitz**

## Revenue Projections

### Month 1 (Launch Month)

| Source | Optimistic | Realistic | Conservative |
|--------|-----------|-----------|-------------|
| Sessions ($149/hr) | 10 × $149 = $1,490 | 4 × $149 = $596 | 1 × $149 = $149 |
| Course pre-sale ($39) | 50 × $39 = $1,950 | 15 × $39 = $585 | 5 × $39 = $195 |
| Career Pro Pack ($49) | 30 × $49 = $1,470 | 10 × $49 = $490 | 3 × $49 = $147 |
| Enterprise | $0 (pipeline) | $0 | $0 |
| **Total** | **$4,910** | **$1,671** | **$491** |

### Month 3 (Post-Course Delivery + Backup Launch)

| Source | Optimistic | Realistic | Conservative |
|--------|-----------|-----------|-------------|
| Sessions | 15 × $149 = $2,235 | 8 × $149 = $1,192 | 3 × $149 = $447 |
| Course ($79) | 30 × $79 = $2,370 | 10 × $79 = $790 | 3 × $79 = $237 |
| Career Pro Pack ($49) | 50 × $49 = $2,450 | 20 × $49 = $980 | 8 × $49 = $392 |
| Cloud Backup ($7/mo) | 40 × $7 = $280 | 15 × $7 = $105 | 5 × $7 = $35 |
| Enterprise | $5,000 | $0 | $0 |
| **Total** | **$12,335** | **$3,067** | **$1,111** |

### Month 6+ Expansion (If Traction: 500+ Stars)

- Domain plugin packs: Finance OS ($49), Health OS ($29)
- Deep-dive mini-courses ($29 each) per plugin
- Plugin Developer course ($99) — ecosystem play
- Augur Cloud / hosted version — real recurring revenue ($15-25/mo)
- Plugin marketplace with revenue share
- Consider investment if hitting $8-15k MRR with clear enterprise pull

Month 1 realistic revenue (~$1,700) is not livable income. Value of launch month = users, stars, feedback, email list. Continue Guriqo consulting separately if income is needed. Target: self-sustaining from Augur alone by Month 6.

## Consequences

### Positive
- 4 revenue streams vs original 3 — adds product revenue from day zero
- Career Pro as hero creates concrete, replaceable-SaaS value proposition
- Open-core model maximizes distribution while protecting commercial upside
- Explicit segment focus prevents solo-founder resource dilution
- Competitive positioning gives every piece of content a narrative anchor
- Bootstrap-first preserves founder autonomy and product direction
- Installer script dramatically lowers barrier for non-dev segments
- Free community maximizes adoption at the stage where volume matters most

### Negative
- Career Pro requires implementing license key system before launch (extra Week 1-2 work)
- Installer script must be maintained across OS versions and edge cases
- Open-core boundary decisions will be contentious with purist OSS users
- Segment focus means deliberately ignoring enterprise inbound until Month 6
- Course delivery deadline creates a hard commitment 4-6 weeks post-launch
- $149 sessions consume founder time that could go to product development
- Launch success is heavily dependent on HN/Reddit/LinkedIn distribution, which is high-variance

### Risks
- HN launch flops (mitigate: README quality, Career hero demo, installer that works)
- Career Pro has zero buyers (mitigate: free tier still valuable, validates pricing)
- Course pre-sale < 5 buyers (mitigate: still build it — it's the right content regardless)
- Zero session bookings month 1 (mitigate: $149 lost opportunity cost is low)
- Enterprise page generates zero inbound (expected — enterprise is a 6-month play)
- License key system gets cracked (mitigate: honor system is fine at this scale; trust > DRM)
- OSS purists complain about Elastic License (mitigate: clear messaging about why, point to data sovereignty)

## Notes

- ADR-042 help button system remains valid — support.html stays as-is
- ADR-044 is fully superseded — the 4-tier model, certification, partners, and paid community are all removed
- This ADR covers go-to-market strategy, not technical architecture — complements but does not replace technical ADRs
- Revenue projections are intentionally conservative to set realistic founder expectations
- GTM research (2026-02-11) validated the core strategy and added 7 concrete improvements
- Competitive positioning narrative should be reviewed quarterly as market evolves
