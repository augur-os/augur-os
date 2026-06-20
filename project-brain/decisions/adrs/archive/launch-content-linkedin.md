---
title: LinkedIn Launch Post — Augur Open Source
status: draft
created: 2026-04-06
target: LinkedIn (organic, personal profile ~2K followers)
success_metric: inbound leads for $249/hr sessions
char_limit: 3000
---

# LinkedIn Launch Post — Draft

## Post Copy (~2,800 chars)

Karpathy just described the missing layer between LLMs and your personal knowledge. We've been building it for 18 months.

He's right: the model is not the bottleneck. Your context is.

Every AI tool you use starts from zero. Claude doesn't know what Cursor knows. ChatGPT doesn't know what your terminal knows. You are the integration layer — copying context between tools like a human API gateway.

Obsidian and Notion assume you'll write the notes. That made sense before LLMs. It doesn't anymore. Augur flips the model: AI creates, you curate. Your agents generate structured knowledge as a side effect of doing real work. You decide what stays.

Today we're open-sourcing Augur — a local-first personal AI OS.

It's not another note app. It's an MCP skill layer that sits underneath every AI client you already use. 200+ composable skills. Any model. Any IDE. The dashboard is just one MCP client — same protocol as Claude Code, Cursor, Windsurf, Gemini CLI. Switch clients without losing your brain.

What makes it different:

-- ~80 autonomous autoloops improve your system while you sleep. Zero API cost — they run on local models via Ollama.

-- Full airplane mode. Works on corporate PCs with no internet, no cloud dependency.

-- Skills follow the open Agent Skills standard (agentskills.io). Portable. Not locked to Augur. Take them anywhere.

-- Your vault is separate from the project. Delete Augur, keep everything you built. Your data is yours, period.

-- macOS-native: deep Apple ecosystem integration. Windows/Linux: Google Workspace. CLI works everywhere.

Two modes: Production (install it, use it) and Dev (build on it, extend it, ship your own skills). MIT license.

If you're tired of being the glue between your AI tools, the repo is live:

github.com/augur-os/augur-os
augur.run

If you want help setting this up for your team or building custom skills for your workflow — I do 1:1 sessions: augur.run/sessions

---

## Visual Assets to Prepare

**Option A — Carousel (recommended for engagement, 3-4 slides):**

1. **Dashboard browse view** — screenshot showing the skill grid or hub overview. Demonstrates the breadth of 200+ skills and the polish of the UI.
2. **Architecture diagram** — MCP-first architecture showing Augur as the skill layer underneath Claude Code, Cursor, Gemini CLI, and the dashboard. Reinforces the "not another app, it's a layer" message.
3. **Comparison table** — Augur vs Obsidian vs Notion vs Mem. Columns: local-first, AI-creates, MCP-native, offline mode, open standard skills, vault separation. Augur checks all boxes.
4. **Terminal screenshot** — Claude Code or Codex session using Augur MCP tools. Shows developer credibility.

**Option B — Single image (simpler, lower risk):**

- Dashboard overview page with visible skill cards and hub navigation. Should look polished and information-dense.

**Design notes:**
- Dark theme preferred (developer audience)
- No watermarks or "made with X" badges
- Clean, no-clutter crops — hide any PII or personal vault data
- LinkedIn image ratio: 1200x627 (single) or 1080x1080 (carousel slides)

## Posting Strategy

- **Time:** Tuesday or Wednesday, 8-9 AM EST (peak LinkedIn engagement for tech)
- **First comment:** Pin a comment with the TL;DR and direct link to the GitHub repo
- **Engagement loop:** Reply to every comment within the first 2 hours — LinkedIn algorithm rewards early engagement velocity
- **Cross-post:** Share to relevant LinkedIn groups (AI/ML, developer tools, PKM) after 24 hours
- **Follow-up post (day 3-5):** "Here's what happened when we open-sourced" with metrics (stars, forks, session bookings)
