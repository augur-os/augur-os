# Getting Started with Augur OS

Augur is local-first AI infrastructure for your laptop. Get to know your AI setup, build your local second brain, and talk with your projects. After install, the Harness — your constitution, skills, hooks, subagents, plugins — lands in every supported AI client. Switch from Claude Code to Codex CLI to Gemini CLI without rebuilding anything.

This guide walks through the first install, the first session, and the hardware tiers that gate optional features.

> If you've never seen Augur before, read [what-is-augur.md](./what-is-augur.md) first — it explains what Augur is and isn't in five minutes.

Augur is in soft launch. Native macOS support is implemented. Native Windows architecture is implemented, but Windows validation is still pending before any firmer support claim.

## Hardware tiers (honest expectations)

Augur runs on any laptop. Some features are NPU- or GPU-accelerated; if your hardware doesn't have them, those features stay off and everything else works.

| Tier | What's enabled | Hardware bar |
|---|---|---|
| **T1** | Memory, skills, cloud-reasoning via your AI client | Any laptop |
| **T2** | + Real-time I/O (voice, accelerated OCR) | 40+ TOPS NPU (Copilot+ PC class) |
| **T3** | + Local 24B-class reasoning (airplane mode) | 100+ TOPS GPU (Apple M-series Pro/Max) |

All tiers are optional. Start at T1; add T2 and T3 later if your hardware supports them. The default install assumes T1.

## Fast Launch

Two ways to install — both cross-OS, both end at a working local second brain.

**One prompt (desktop AI chat).** Open `project-brain/capabilities/skills/onboard/install.md`, paste it into Claude, Codex, Gemini, Cursor, or another supported AI client, and choose a folder by answering "Which folder should I initialize?". The agent runs the onboard engine for you and reports a read-only inventory of your existing AI setup. Next action: Ask Augur about this project.

**Requires** `uv` and Node 22+.

**One command (terminal).**

```
git clone https://github.com/augur-os/augur-os.git
cd augur-os
uv run aug onboard run
```

`aug onboard run` checks prerequisites (and prints the exact per-OS install command if `uv` or Node 22+ is missing — it does not install system tooling for you), installs dependencies, builds the dashboard, wires MCP, seeds a local brain, and verifies the system is up at <http://localhost:3000/browse>.

Then point Augur at any project folder to inventory its existing AI artifacts:

```
uv run aug init --project <folder>
```

The first success moment is the read-only AI artifact inventory, not the dashboard or full onboarding.
The first project question is answer-only by default; Augur does not save or retain anything unless you ask.

## Contributor Full Workspace

<details>
<summary>Manual setup (contributors who want direct control of bootstrap)</summary>

```
git clone https://github.com/augur-os/augur-os.git
cd augur-os
corepack enable && pnpm install && uv sync
```

Then `uv run aug dev build` for the dashboard and `uv run aug init --project .` to attach the checkout as a project brain.
</details>

## Configure MCP For Manual Full-Workspace Work

Use the repo-managed config writer instead of hand-editing example files:

```bash
python scripts/configure_mcp.py --list-ides
python scripts/configure_mcp.py --client cursor --auto
```

For Windows-specific setup and validation, see [guides/installation-windows.md](guides/installation-windows.md).

## Your first hour with Augur

After fast launch creates or attaches `project-brain/`, continue with the first-hour milestones. If you are using the full contributor workspace dashboard, the **Setup Completeness Widget** in the sidebar tracks 11 milestones and auto-detects what's done and what's pending. This section walks through each milestone explicitly so you know what to expect.

### Phase 1 — Foundation (connect Augur to your laptop)

**1. Index your machine.** Augur discovers the AI clients you have installed (Claude Code, Codex, Gemini CLI, Cursor, Copilot) and the skills available. Run `/discover` in your AI client or click "Run /discover" in the widget. Augur registers each client adapter and inventories the skill tree.

**2. Create or clone your vault.** The vault is your durable local data root — where your notes, documents, wiki pages, skills, and prompts live on disk. Default location is `~/Vault/Augur/`. Run `/onboard --migrate` in your AI client or click "Set up vault" in the widget. You can also point the vault at an existing git repo if you want versioning.

**3. Build your human profile.** Augur learns your preferences (preferred AI clients, default hub, conventions) from a profile file. Click "Generate profile" in the widget to call the `memory-profile-regenerate` MCP tool. The profile is plain Markdown; you can edit it directly at `~/Vault/Augur/profile/`.

### Phase 2 — Knowledge (connect your data, watch the wiki compound)

**4. Configure inbox folders.** Tell Augur which folders to watch for new documents (e.g., `~/Desktop`, `~/Downloads`). New files there get extracted, indexed, and routed automatically. Open `/brain/inbox` in the dashboard and add a folder.

**5. Add document source folders.** Connect existing knowledge stores — folders of PDFs, notes, exports from Notion or Obsidian. Open `/brain/sources` (or use the browse page Sources category). Each source folder is scanned, summarized into source cards, and indexed for `/ask`.

**6. Set wiki compounding queries.** The wiki compounds nightly: Augur picks queries you've configured, runs them across your indexed content, and writes the answer to a wiki page. Edit `~/Vault/Augur/wiki/queries.yaml` or use the dashboard's wiki settings.

**7. Get to ≥5 compounded wiki pages.** Once you have inbox folders + source folders + queries configured, the wiki starts filling in. The widget flips this milestone green when `wiki list --count` reaches 5. Browse compiled pages at `/browse?category=wiki`.

### Phase 3 — Personalization (make Augur specifically yours)

**8. Create a private skill.** Skills are modular expertise. A private skill lives in the configured personal brain under `capabilities/skills/<your-skill>/SKILL.md` and is yours alone (not synced upstream). Use `/adr write` to scaffold one, or copy an existing skill structure from `project-brain/capabilities/skills/`. See [creating-skills.md](./creating-skills.md).

**9. Save your first prompt.** Reusable prompt templates live in the configured personal brain prompts root. Save a prompt you find yourself reusing — Augur surfaces them in the Prompts browse category and your AI client can pull them by reference.

**10. Ask your first question (`/ask`).** Run `/ask "your question"` in any AI client. Augur queries across your indexed sources, returns an answer with citations, and retains the question/answer for wiki compounding. The widget flips this milestone green after the first successful `/ask`.

**11. Connect your first integration.** Calendar, mail, browser bookmarks — integrations let Augur pull data from services beyond local files. Open `/browse?category=integrations` and pick one.

### After onboarding

The widget shrinks to a compact bar (~60% complete) and then to a tiny chip (100%). If something regresses (vault disconnects, source folders go empty), the chip flips amber and re-asserts itself.

Day-to-day, you live in the **dashboard browse page** (`/browse`) and your **AI client**. The same skills, prompts, constitution, and memory work in every supported client because Augur generated each client's native format from one source — see [architecture-overview.md](./architecture-overview.md) for the Harness model.

## What Next

- Discover tools: `aug discover`
- Search your knowledge: `aug unified-search --query "your topic"`
- Create a skill: See [creating-skills.md](creating-skills.md)
- Explore the architecture: See [architecture-overview.md](architecture-overview.md)
