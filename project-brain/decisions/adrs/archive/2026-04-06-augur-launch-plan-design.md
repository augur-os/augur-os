---
title: Augur Launch Plan — Full Design Spec
date: 2026-04-06
status: draft
context: Competitive response to Cabinet (runcabinet.com) launch; Karpathy LLM+KB thesis validation
---

# Augur Launch Plan — Full Design Spec

## Context

On 2026-04-04, Cabinet (runcabinet.com) launched as an open-source LLM knowledge base, riding Andrej Karpathy's viral thread about LLM knowledge bases. Within 48 hours: 497 GitHub stars, 820 npm downloads, 119 Discord members, 200K+ views on X. Cabinet is a 3-day-old Next.js prototype — Claude Code CLI wrapper with a Tiptap editor, 20 agent templates (~1KB each), no tests, no CI, no multi-model support despite "BYOAI" claims.

Augur has been in development for months with 193 skills, 388 ADRs, 2.8K test files, 12 CI workflows, MCP-native architecture, multi-client support, and a self-healing adaptive engine. The category Karpathy described — "AI compiling knowledge bases from raw data" — is exactly what Augur already does.

**This spec covers the full launch plan: messaging, website, product gaps, onboarding, and launch day process.**

## Launch Parameters

| Parameter | Decision |
|-----------|----------|
| Timeline | 2 weeks from 2026-04-06 (launch day: 2026-04-20) |
| Primary audience | Developers + AI practitioners |
| Primary channel | LinkedIn (2K followers), then HN |
| Success metric | Inbound leads (sessions at $249/hr) |
| Monetization | 1:1 sessions ($249/hr). No course. Enterprise page exists separately. |
| Time commitment | Full-time (6-8h/day) |
| Approach | Fix → Polish → Launch (product + website work, then one strong launch post) |

---

## Topic 0: Value Proposition & Messaging

### Core Identity

Augur connects your **notes, personal files, skills, workflows, MCP tools, and your PC** to AI clients. It is an MCP-first solution with textual RAG. The dashboard UI is just another MCP client — same as Claude Code, Cursor, or Gemini. The MCP server is the product.

Users can install any skill they want, create custom hubs in dev mode, and browse everything through the dashboard or any AI client. The vault is separate from the project — you own all your data (notes, skills, plugins, documents, workflows).

### The Karpathy Thesis — Augur Is The Answer

Obsidian and Notion assume **you write your notes**. Their UIs are optimized for manual editing.

Augur assumes **AI writes them — and you curate**. AI clients compile knowledge from conversations, research, and workflows into markdown files. You review them in Obsidian, the dashboard, or any tool you prefer. The knowledge base builds itself.

This is exactly what Karpathy described: AI compiling wikis from raw data. Augur has been doing this for months.

### Key Differentiators (What To Lead With)

1. **MCP-first** — All execution flows through MCP. Any AI client connects to the same identity. The models are interchangeable; your brain is not.
2. **AI creates, you curate** — Flips the note-taking paradigm. Most content is AI-generated markdown, reviewed through Obsidian or any client.
3. **Skills are the product** — 200+ composable, portable skills following the open Agent Skills standard. Not plugins, not templates — self-contained automation units.
4. **Autoloops** — ~80 autonomous loops run nightly on idle hardware. They scan, fix, and evolve the system. Zero API cost. Your system improves while you sleep.
5. **Local-first + airplane mode** — Works on corporate PCs with no internet via Ollama. No API keys, no data leaving the machine.
6. **You own everything** — Notes, skills, plugins, documents, workflows — all local files. Vault is separate from project. Delete Augur, your data stays.
7. **Two modes** — Production (install skills, use daily) and Dev (build skills, create hubs, customize everything).

### Messaging Do-Nots

- Do NOT compare to Cabinet on the website (too small, 3 days old, not a peer)
- Do NOT position as a "note-taking app" — Augur is an integration/automation layer
- Do NOT lead with feature counts without context — "200+ skills across career, finance, health, knowledge, home automation" > "200+ skills"
- Do NOT emphasize the dashboard as the product — it's one client among many

---

## Topic 1: Website Messaging Changes

### Website files location
`~/Projects/Au-docs/venture-augur/website-working/`

### Change 1: Badge
- **Current:** "Open Source · Coming Soon"
- **New:** "Open Source"

### Change 2: Hero subtitle
- **Current:** "One AI identity that connects every model you use. Your memory, skills, and workflows — unified on your machine."
- **New:** "One AI identity that connects every model you use. Your notes, files, skills, and workflows — unified on your machine through MCP."

### Change 3: Remove course CTA
- Remove the $129 course card entirely
- Keep: Free (open source, GitHub link) + Sessions ($249/hr)
- Update free CTA from "Join Waitlist" to "Get Started" with link to GitHub repo

### Change 4: Add comparison table (new section after The Problem)

**Section title:** "How Augur Compares"

| Capability | Notion AI | Obsidian + Plugins | **Augur** |
|-----------|-----------|-------------------|-----------|
| **Data ownership** | Cloud-hosted on Notion servers | Local notes only | All yours locally — notes, skills, plugins, documents, workflows |
| **Knowledge philosophy** | You write, AI assists | You write, plugins extend | AI creates, you curate. Knowledge compounds across every conversation. |
| **AI models** | Notion's built-in AI only | Plugin-dependent, one at a time | Any — Claude, GPT, Ollama, local models |
| **Multi-IDE** | No | No | Claude Code, Cursor, Codex, Gemini, Ollama |
| **Skills / automation** | None | Community plugins (not native) | Core of the product — 200+ skills, ~80 autonomous autoloops |
| **Self-healing ops** | No | No | Autoloops detect, fix, and evolve nightly |
| **RAG / search** | Basic AI search | Plugin-dependent | BM25 + ripgrep hybrid, content-aware chunking |
| **Offline / airplane** | No | Partial (no AI offline) | Full — local LLM, OCR, speech-to-text |
| **Corporate-ready** | Cloud compliance concerns | Local but no automation | Local-first, airplane mode, no API keys |
| **Extensibility** | Limited API | JS plugins | Open skill standard, any language, dev mode |
| **Native OS integration** | None | Community plugins | macOS: Apple Notes, Reminders, Calendar, Shortcuts. Windows/Linux: Google Workspace (Gmail, Calendar, Drive, Docs). CLI everywhere. |
| **UI role** | UI IS the product | UI IS the product | UI is one MCP client among many |

### Change 5: Add "Two Modes" section to homepage

**Section title:** "Meet You Where You Are"

**Production Mode:**
- Install community skill packs
- Fill them with your data
- Get AI-assisted immediately
- Technical Level: Same as using ChatGPT or Claude

**Dev Mode:**
- Build your own skills and hubs
- Customize everything
- Shape the system to your life
- Technical Level: Domain knowledge + AI fluency. No coding required.

### Change 6: Autoloops + self-healing section

**Section title:** "Your System Improves While You Sleep"

> ~80 autonomous loops run nightly on idle hardware — zero API cost. They scan for broken links, stale references, security vulnerabilities, and code quality issues — and fix what they can. Evolution gaps tell you what's still untested. This isn't monitoring — it's a system that gets better without you.

### Change 7: Skill architecture section

**Section title:** "Install Any Skill. Build Your Own."

> Skills follow the open Agent Skills standard — portable across AI clients, not locked to Augur. Your vault stays separate from the project. RAG indexes connect everything. Browse, search, and install from the dashboard or CLI.

### Change 8: Corporate reference (not full section)

> **Works on Corporate PCs** — Local-first, airplane mode, no data leaves the machine. See our enterprise proposition →

### Change 9: "No Cloud. By Design." section

New section — flips the absence of cloud from weakness to strength:

> **There is no Augur Cloud. That's the point.**
>
> Your second brain runs on your machine — not on our servers, not behind our login, not subject to our pricing changes. Local-first isn't a limitation. It's the architecture.
>
> When a cloud vendor changes policy, raises prices, or shuts down, your second brain doesn't notice. It's already home.

### Change 10: Skills build live pages (vs static iframes)

New messaging point — differentiates from static HTML embedding approaches:

> **Augur extends the Agent Skills standard.** Instead of displaying static HTML in an iframe, Augur builds full data-connected dashboard pages overnight — while you sleep. Every skill can ship its own live page, wired to real data through MCP. Your system doesn't just store knowledge — it builds the interface to navigate it.

### Change 11: Dashboard framing

Add caption under dashboard screenshots:
> "The dashboard is one of many ways to interact with Augur. Claude Code, Cursor, Gemini, and the CLI all connect to the same MCP layer. The UI is optional — your skills and data work everywhere."

### Change 12: Karpathy angle (new callout in Problem section)

After the three problem bullets, add:
> Obsidian and Notion assume you write your notes. Augur assumes AI writes them — and you curate. Your AI clients compile knowledge from conversations, research, and workflows into markdown files. You review them in Obsidian, the dashboard, or any tool you prefer. The knowledge base builds itself.

### Change 13: Skill count consistency
Pick one number and use it everywhere: **200+** (website), reconcile README to match.

### Change 14: Add GitHub link
- Add GitHub repo link to navigation bar
- Add GitHub stars badge to hero section
- Replace "Join Waitlist" primary CTA with "View on GitHub" + keep waitlist as secondary

### Change 15: GitHub repo polish (on augur-os/augur-os public repo)

The public repo needs these fixes before launch:
- **Social preview**: Replace stale "Exocortex" image with Augur branding
- **Repo description**: "Local-first personal AI OS. 200+ composable skills. Any model. Plain text. Yours forever."
- **Topics**: mcp, ai-agents, knowledge-management, second-brain, local-first, automation, skills, model-agnostic, ollama, personal-ai, python, nextjs, cli, model-context-protocol
- **CI badge**: Fix broken link (points to non-existent `ci.yml`, should point to `ci-tests.yml`)
- **Full badge row**: License, CI, Python 3.11+, Node 20+, Stars, Last Commit, PRs Welcome
- **Star History chart**: Add at bottom of README
- **pyproject.toml [project.urls]**: Add homepage, repo, docs, issues URLs
- **CODE_OF_CONDUCT.md**: Add Contributor Covenant v2.1
- **.github/ISSUE_TEMPLATE/config.yml**: Add with link to Discussions
- **.github/SECURITY.md**: Copy from root
- **CHANGELOG.md**: Replace placeholder with real v0.1.0 entries
- **GitHub Discussions**: Enable (no Discord needed at launch)
- **Starter issues**: 10+ with "good first issue" and "help wanted" labels

### Change 16: Demo shows AI client onboarding (not just npx)

The primary demo should show installing Augur FROM an AI client — this is the unique differentiator Cabinet cannot match:
1. Open Claude Code
2. Say "Set up Augur as my second brain" — agent runs `/onboard`
3. Skills install, vault connects, dashboard opens

The `npx create-augur` is the fallback install method shown as secondary. The primary narrative is: **your AI installs your AI system**.

---

## Topic 2: Feature-by-Feature Product Assessment

### Features where Augur is already stronger (no action needed)

| Feature | Augur | Cabinet |
|---------|-------|---------|
| RAG/Search | BM25 + ripgrep hybrid with RRF fusion | `string.includes()` linear scan |
| Multi-model | Claude, GPT, Ollama, local | Claude Code CLI only |
| Multi-IDE | Claude Code, Cursor, Codex, Gemini | None (web UI only) |
| Skill system | 200+ skills, open standard, portable | 20 templates (~1KB each) |
| Automation | ~80 autoloops, self-healing, evolution | Cron-triggered `claude -p` |
| Testing/CI | 2.8K test files, 12 workflows | 0 tests, 0 CI |
| Data separation | Vault external, survives deletion | `data/` inside app directory |
| Apple integration | Notes, Reminders, Calendar, Shortcuts | None |
| Life domains | Finance, health, career, home, lifestyle | Work/startup only |
| Architecture | 388 ADRs, three-layer model | Monolithic, volatile |
| Corporate/offline | Full airplane mode, Ollama | Requires internet + Claude |

### Features to evaluate from Cabinet patterns

Priority decisions for launch:

| Cabinet Feature | Current Augur Equivalent | Decision Needed |
|----------------|------------------------|-----------------|
| `npx create-cabinet` (1-command install) | `pipx install -e .` + `pnpm` + `uv` (3 tools) | **P0: Need 1-command install** |
| Onboarding wizard (5 questions) | CLI-driven, multi-step | **P1: Need guided onboarding** |
| Git auto-commit on every save | Git managed but not auto-commit | Evaluate: is this useful? |
| WYSIWYG editor (Tiptap) | Obsidian integration (external) | **Skip: Obsidian is the editor** |
| Embedded HTML apps (iframe) | Dashboard block system | **Skip: blocks are more powerful** |
| Web terminal (xterm.js + PTY) | xterm.js in dashboard | Already have it |
| Agent personas with memory loop | Skills with MCP tools | Different model — skills > personas |
| Inter-agent messaging | MCP tool chaining | Different model — MCP > message passing |
| Demo video on homepage | [Screenshot/GIF TBD] | **P0: Need demo video/GIF** |
| Comparison table on website | None | **P0: Adding (vs Notion AI, Obsidian)** |

---

## Topic 3: Onboarding Plan

### Current state
- Install requires 3 tools: pipx, pnpm, uv
- No guided setup wizard
- Skills discovery via CLI (`aug discover`)
- README mentions `npx create-augur@latest my-mind` in FAQ but it doesn't exist yet

### Target state for launch
1. **1-command install**: `npx create-augur@latest my-brain` or equivalent
   - Scaffolds project directory
   - Installs Python + Node dependencies
   - Connects to first AI client (Claude Code or Cursor)
   - Opens dashboard

2. **First-run experience in dashboard**:
   - Browse page shows all available skills
   - Quick-start cards for common setups (Knowledge Worker, Developer, Team Lead)
   - "Connect your vault" flow
   - "Install your first skill pack" flow

3. **README quick-start**:
   - Single install command above the fold
   - 3-step "what to do after install"
   - Screenshot/GIF of working dashboard

### Onboarding priorities for 2-week launch

| Priority | Item | Effort |
|----------|------|--------|
| P0 | `npx create-augur` scaffolder | 2-3 days |
| P0 | Demo GIF/video for README + website | 1 day |
| P1 | README rewrite (external-user focus) | 0.5 day |
| P1 | Skill count consistency (pick 200+) | 0.5 day |
| P2 | Dashboard first-run cards | 1-2 days |
| P2 | "Connect your vault" guided flow | 1 day |

---

## Topic 4: Launch Day Plan

### Pre-launch checklist (complete by 2026-04-19)

**Product:**
- [ ] `npx create-augur` works end-to-end
- [ ] README rewritten for external users
- [ ] Demo GIF/video recorded and embedded
- [ ] Skill count consistent everywhere (200+)
- [ ] GitHub repo public with clean history
- [ ] LICENSE, CONTRIBUTING.md verified
- [ ] "good first issue" labels on 10+ issues

**Website:**
- [ ] All messaging changes from Topic 1 implemented
- [ ] Badge changed to "Open Source"
- [ ] Course CTA removed
- [ ] Comparison table added (vs Notion AI, Obsidian+plugins)
- [ ] GitHub link in nav
- [ ] Demo video/GIF on homepage
- [ ] Autoloops section added
- [ ] Karpathy angle callout added
- [ ] Dashboard screenshots captioned ("UI is one client among many")
- [ ] Enterprise page linked from corporate reference
- [ ] Waitlist → "Get Started" CTA change

**Community:**
- [ ] GitHub Discussions enabled
- [ ] Discord or community channel created
- [ ] 10+ "good first issue" labels

### Launch day (2026-04-20) — sequence

**Morning:**
1. Push final website changes live
2. Make GitHub repo public (if not already)
3. Verify `npx create-augur` works from clean machine
4. Verify augur.run loads correctly, all links work

**LinkedIn post (primary channel):**

Structure:
- Hook: The Karpathy angle — "Karpathy described the missing layer for LLMs. We've been building it for months."
- Problem: AI tools don't share context. You're the router.
- Flip: Obsidian/Notion assume you write notes. Augur assumes AI writes them.
- What it is: MCP-first personal AI OS. 200+ skills. Any model. Any IDE.
- Key differentiators: autoloops, airplane mode, skill standard, vault separation
- CTA: GitHub link + augur.run + "Book a session if you want to set this up for your team"
- Visual: Demo GIF or screenshot carousel

**HN Show HN post (secondary, same day or next day):**

Title: "Show HN: Augur – MCP-first personal AI OS with 200+ skills (open source)"

Structure:
- What it is (1 paragraph)
- Why we built it (the fragmentation problem)
- How it works (Filesystem → MCP → Any Client)
- What makes it different (AI creates, you curate; autoloops; airplane mode; open skill standard)
- Technical details (Python + TypeScript, BM25 RAG, no vector DB, 388 ADRs)
- Links: GitHub, website, demo

**Reddit (day 2-3, if HN gets traction):**
- r/selfhosted — "self-hosted AI knowledge system with 200+ skills"
- r/LocalLLaMA — "full airplane mode AI OS with Ollama integration"
- r/ObsidianMD — "Augur: an MCP layer that makes Obsidian vaults AI-native"

### Post-launch (week 3+)

- Respond to every GitHub issue within 24 hours
- Write 2-3 LinkedIn follow-up posts showing real use cases
- Monitor HN/Reddit threads, respond to questions
- Track session booking pipeline
- Reach out to people hitting Notion AI / Obsidian plugin limitations

---

## Two-Week Timeline

### Week 1 (Apr 7-13): Product & Website Fix

| Day | Focus | Deliverable |
|-----|-------|-------------|
| Mon-Tue | `npx create-augur` scaffolder | Working 1-command install |
| Wed | Demo GIF/video recording | 60-90s demo showing key flows |
| Thu | README rewrite | External-user-friendly README with demo embedded |
| Fri | Website messaging changes (Changes 1-6) | Updated index.html |
| Sat-Sun | Website messaging changes (Changes 7-12) + comparison table | Complete website refresh |

### Week 2 (Apr 14-19): Polish & Launch Prep

| Day | Focus | Deliverable |
|-----|-------|-------------|
| Mon | Skill count audit + consistency fix | One number everywhere |
| Tue | GitHub repo cleanup — issues, labels, discussions | Community-ready repo |
| Wed | LinkedIn post draft + review | Final copy ready |
| Thu | HN post draft + review | Final copy ready |
| Fri | End-to-end test: install from scratch, walk through onboarding | Verified flow |
| Sat | Final website QA + deploy | Live at augur.run |
| Sun | Launch day (Apr 20) | Posts go live |

---

## Success Metrics (Launch + 2 Weeks = by May 4)

| Metric | Target | Why |
|--------|--------|-----|
| Session inquiries | 5+ | Primary success metric — inbound leads |
| GitHub stars | 200+ | Social proof for ongoing discovery |
| GitHub issues from external users | 10+ | Signal of real usage |
| LinkedIn post impressions | 10K+ | Reach within existing audience |
| `npx create-augur` installs | 50+ | Adoption signal |
| HN front page | Bonus | Not controllable, but attempt |

---

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| `npx create-augur` takes longer than 2 days | Fallback: well-documented 3-step manual install in README |
| Demo video quality isn't great | Ship it anyway — Cabinet's snoring video got 200K views. Substance > polish. |
| HN doesn't hit front page | LinkedIn is primary channel. HN is bonus. |
| No session bookings in first 2 weeks | Follow up with LinkedIn commenters directly. Offer free 15-min intro calls. |
| Cabinet captures "LLM KB" category label | Augur is a different category (AI OS / skill layer). Don't fight for their label. |
| Corporate buyers need more than a landing page | Enterprise page exists. Add case study / architecture diagram for IT review. |
