# User Guide

This guide is for using Augur day-to-day — operating your personal brain from the dashboard, your AI client, and the shell. It assumes Augur is already installed.

If you haven't installed Augur yet, see [getting-started.md](./getting-started.md). If you want to know what Augur is (and isn't), see [what-is-augur.md](./what-is-augur.md). For architecture, see [architecture-overview.md](./architecture-overview.md).

Augur is local-first. Everything in this guide happens on your laptop, against your vault, through your existing AI client. Nothing leaves your machine unless you explicitly send it somewhere.

Augur is in soft launch. Native macOS support is implemented. Native Windows architecture is implemented, but Windows validation is still pending before a firmer public support claim.

## Your home is the browse page

The dashboard at `http://localhost:3000/browse` is where you operate your second brain day-to-day. Categories group into three:

| Group | Categories you'll use | What's there |
|---|---|---|
| **Content** | Inbox · Notes · Sources · Wiki · Skills · Actions · Prompts · Drafts · Archive | Everything you own and operate on |
| **System** | Integrations · Extensions & Bundles · Scheduled Executions | What's connected and what's scheduled |
| **Dev** | (Hidden by default — toggle in dashboard mode) | ADRs · MCP Tools · Commands · etc. — for contributors |

### Inbox

`/browse?category=inbox` shows documents waiting to be processed. When you drop a file into a watched folder (`~/Desktop`, `~/Downloads`, anywhere you configured), it lands here first. From the dashboard you can:

- **Scan** — preview what's there before consuming
- **Consume** — route the file through extraction, renaming, knowledge routing, RAG indexing, and wiki-update signaling
- **Purge to Trash** — move disposable candidates to the OS trash (with file-list shown before action)

Best path: scan everything, consume the valuable, purge the chaff. Use `/brain/inbox` in the dashboard or call the `inbox-*` MCP tools from your AI client.

### Notes

`/browse?category=notes` shows your written notes. Augur reads any plain-text or Markdown file under your vault's `notes/` directory.

### Sources

`/browse?category=sources` shows the document folders you've connected. Each source folder is scanned, summarized into source cards, and indexed so `/ask` can cite from it. Add sources from `/brain/sources` or via the `knowledge-sources` MCP tool.

### Wiki

`/browse?category=wiki` shows compiled wiki pages. The wiki compounds nightly: Augur runs your configured queries across indexed content and writes the answers as concept-first pages. Click a page to read it; pages link to their source documents.

The wiki is what makes Augur's `/ask` quality compound — each `/ask` retains a signal, and the wiki compiler folds repeated signals into durable pages.

### Skills

`/browse?category=skills` shows the skills available — Augur-shipped (in `project-brain/capabilities/skills/`) and your private skills (in the configured personal brain `capabilities/skills/` root). Each skill has actions, prompts, commands, and (optionally) dashboard pages.

Your AI client matches a skill at runtime and forks it into an isolated subagent — see the Harness model in [architecture-overview.md](./architecture-overview.md). You don't have to load skills manually; they're discoverable by name and by problem statement.

### Actions

`/browse?category=actions` shows one-click operations skills expose. An action has a dispatch mode (`fire` for bash, `oneshot` for a single LLM call, `ide` for multi-step agent work) and shows up as a button in the dashboard.

### Prompts

`/browse?category=prompts` shows reusable prompt templates. Save reusable prompts in the configured personal brain prompts root; Augur surfaces them in the Prompts category and your AI client can pull them by reference.

### Integrations

`/browse?category=integrations` shows connected services (calendar, mail, browser bookmarks, etc.). Augur talks to integrations through MCP tools — no direct API keys in dashboard code. Add or configure integrations from the System group.

## How Augur reaches your AI client

Everything in the browse page is also reachable from your AI client because Augur generates each client's native format from one source. See the **Harness** section of [architecture-overview.md](./architecture-overview.md). In practice:

- Your **constitution** (project rules, conventions, repo map) loads at session start in every supported client.
- Your **skills** are matched by name and problem statement in every client.
- Your **hooks** (cross-agent `.githooks/` + per-client `.claude/settings.json` / `.codex/hooks.json`) fire deterministically.
- Your **subagents** are bounded specialists every client can delegate to.
- Your **plugins** (Plugin-Pack assembler output) install one-shot per client.

Switch from Claude Code to Codex in the same project and the same setup is already there. Augur regenerates the per-client files when sources change.

## Daily workflow

1. New files land in **Inbox** (you drop them or your watched folders capture them).
2. Augur extracts, indexes, and routes via the consume action.
3. The **Wiki** compounds — recurring concepts get their own pages.
4. You ask questions via `/ask` in any AI client; answers cite your own sources.
5. The AI client uses your **Skills**, your **Prompts**, your **Constitution**.

Capture first, process second, store locally, then query later — that's the loop.

## Platform Status

Augur is currently best described as a soft-launch project.

- macOS is the fully implemented native path today.
- Windows has a native architecture in place.
- Windows validation is still pending before the public support story becomes firmer.

If you are evaluating Augur on Windows, follow the current validation docs rather than assuming every macOS workflow is already equally validated there.

## What To Use First

Start with the repo-first workflow and the dashboard.

- Clone the repo and install dependencies from the project root.
- Launch the dashboard locally.
- Use the command and skill docs to discover the workflow you need.
- Keep your own notes, documents, and generated outputs in the repo-managed locations described by the setup docs.

## Good Starting Points

- [Getting Started](getting-started.md)
- [Developer Guide](developer-guide.md)
- [Creating Skills](creating-skills.md)
- [Architecture Overview](architecture-overview.md)
- [Windows Installation Guide](guides/installation-windows.md)

## When A Skill Feels Close But Not Quite Right

Augur is designed around small, composable skills. If a skill does most of what you need, use it as the starting point and adjust the workflow rather than looking for a single monolithic app.

If you are unsure where to begin, use the dashboard or the repo search tools to find the closest skill, then follow its docs.
