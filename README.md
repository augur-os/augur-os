# Augur OS

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/augur-os/augur-os/actions/workflows/ci-tests.yml/badge.svg)](https://github.com/augur-os/augur-os/actions/workflows/ci-tests.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Node 20+](https://img.shields.io/badge/node-20+-green.svg)](https://nodejs.org/)
[![GitHub stars](https://img.shields.io/github/stars/augur-os/augur-os?style=social)](https://github.com/augur-os/augur-os)
[![GitHub last commit](https://img.shields.io/github/last-commit/augur-os/augur-os)](https://github.com/augur-os/augur-os/commits)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![Sponsored by Guriqo](https://img.shields.io/badge/Sponsored%20by-Guriqo-orange.svg)](https://guriqo.com)

[Website](https://augur.run) | [Documentation](https://augur.run/more.html) | [Sessions](https://augur.run/sessions.html)

> **`.bashrc` for your AI. Composable skills. Local-first. Model-agnostic. Yours forever.**

Clone it. Connect any LLM. Plain-text skills you can `cat`, `grep`, and `git diff`. A personal knowledge system that grows with you.

> **[Screenshot/GIF TBD]**

---

## Quick Start

```bash
npx create-augur@latest my-brain
cd my-brain
pnpm --filter dashboard dev
```

Dashboard opens at [localhost:3000](http://localhost:3000).

**Requirements**: Node.js >= 20, Python >= 3.11

### Alternative Install Methods

<details>
<summary><strong>Git Clone</strong></summary>

```bash
git clone https://github.com/augur-os/augur-os.git
cd augur-os
pipx install -e .
aug discover
```

**Requirements**: Python >= 3.11, [pipx](https://pipx.pypa.io/)

</details>

<details>
<summary><strong>Claude Code Plugin</strong></summary>

```bash
# Add the marketplace
claude plugin marketplace add augur-os/augur-os

# Install the plugin
claude plugin install augur-skills@augur-skills
```

Skills are auto-discovered from `skills/` and namespaced as `augur-skills:<skill-name>`.

</details>

<details>
<summary><strong>Cowork (Claude Desktop)</strong></summary>

```bash
curl -fsSL https://raw.githubusercontent.com/augur-os/augur-os/main/scripts/install.sh | bash -s -- --from cowork
```

Installs the full system, wires the MCP server, and assembles the Cowork plugin. Restart Claude Desktop after install — skills and tools appear automatically.

</details>

<details>
<summary><strong>Install Individual Skills</strong></summary>

```bash
npx skills add augur-os/augur-os --skill reading-list
npx skills add augur-os/augur-os --skill finance -g  # global install
```

</details>

<details>
<summary><strong>Dashboard (from clone)</strong></summary>

```bash
cd augur-os && pnpm install && pnpm --filter dashboard dev
# Open http://localhost:3000
```

</details>

### MCP Server (for AI agents)

Add to your Claude Desktop / Cursor / IDE config:

```json
{
  "mcpServers": {
    "augur": {
      "command": "python",
      "args": ["-m", "augur_mcp"],
      "cwd": "/path/to/augur-os/src/mcp"
    }
  }
}
```

Then any agent can call `discover-augur` to learn what tools are available.

---

## What Can I Build

- **Knowledge management** -- RAG search across your notes, documents, and bookmarks
- **Career tracking** -- job pipeline, coaching, LinkedIn automation
- **Health and wearables** -- Apple Health integration, habit tracking
- **Home automation** -- Hue lights, Sonos speakers, smart home control
- **Finance** -- portfolio tracking, wealth dashboards
- **Content creation** -- social media posting, blog drafts, OCR pipelines

200+ skills across 6 hubs (`adaptive`, `brain`, `career`, `command`, `life`, `studio`). Start with what you need, add more later.

---

## The Unix Philosophy for AI

> **"This is `~/.bashrc` for your AI. Configure with text files. Debug with `cat`. Version with `git`."**

| Unix Principle | Augur Implementation | What It Means |
|----------------|---------------------|---------------|
| **Do one thing well** | Skills are single-purpose | Each skill has one job. Compose them for complex workflows. |
| **Plain text** | YAML + Markdown everywhere | Your data is `cat`-able, `grep`-able, `git diff`-able. |
| **Composable** | Chain skills together | Pipe skill to skill like `grep \| sort \| uniq`. |
| **Human-readable** | English is the code | SKILL.md files are plain English instructions that AI executes. |

---

## Architecture

```
+-----------------------------------------------------------+
|                    REASONING LAYER                         |
|               (Model-Agnostic Planning)                   |
|      Claude  -  GPT  -  Ollama  -  Local Models          |
+-----------------------------+-----------------------------+
                              |
+-----------------------------v-----------------------------+
|                    EXECUTION LAYER                         |
|              (200+ Skills, Multi-Client)                  |
|                                                           |
|   skills/            All skills live here                 |
|   .cursor/skills/    Cursor-specific skill overrides      |
|   .gemini/skills/    Gemini-specific skill overrides      |
|   .codex/skills/     Codex-specific skill overrides       |
+-----------------------------+-----------------------------+
                              |
+-----------------------------v-----------------------------+
|                      OPS LAYER                            |
|          (Daemon, Self-Heal, Nightly Automation)          |
|    38 auto-* skills  -  Adaptive loops  -  Health checks  |
+-----------------------------------------------------------+
                              |
          +-------------------+-------------------+
          |                   |                   |
     CLI (aug)          MCP Server          Dashboard
                                         localhost:3000
```

### Surfaces

| Surface | Purpose |
|---------|---------|
| **CLI** (`aug`) | Agent-native, scriptable, composable |
| **MCP Server** | Tool provider for Claude, Cursor, and other AI agents |
| **Dashboard** | Visual hub at `localhost:3000` for humans |

---

## Repository Structure

```
augur-os/
├── src/                          # Framework code (CLI, config, MCP server)
├── apps/dashboard/               # Next.js dashboard
├── skills/               # Skills mastered for Claude Code
├── .cursor/skills/               # Skills mastered for Cursor
├── .gemini/skills/               # Skills mastered for Gemini
├── config/                       # System configuration
├── docs/                         # Documentation and ADRs
├── scripts/                      # Install and utility scripts
└── dist/                         # Distributable plugin packages
```

All skills live in `skills/`. IDE-specific overrides may appear in `.cursor/skills/`, `.gemini/skills/`, or `.codex/skills/`.

---

## CLI

The `aug` command wraps all MCP tools as a CLI:

```bash
# Discovery -- find tools and capabilities
aug discover                         # Full JSON manifest
aug discover --hub career --compact  # Filter by hub
aug discover --tier public           # Show only public-tier tools
aug discover --format markdown       # Agent-readable output

# Run any tool
aug <tool-name> [--param value ...]
aug get-career-jobs --status active
aug unified-search --query "health tracking"

# List all tools
aug --list-tools
```

### Installation Methods

| Method | Command | When to use |
|--------|---------|-------------|
| **pipx** (recommended) | `pipx install -e .` | Global install, isolated venv |
| **pip editable** | `pip install -e .` | Development, inside a venv |
| **Direct** | `python src/cli.py` | No install needed |

---

## The 5 Pillars

**Trust** -- SKILL.md files are plain English instructions that AI executes. When you ask "why did it do that?" you can `cat` the answer.

**Freedom** -- Use Claude, GPT, Ollama, or local models. Connect via Claude Code, Cursor, VS Code, or the command line.

**Pace** -- Start with one skill. Add more when ready. The system adapts to your rhythm.

**Complexity** -- Day 1: `aug discover`. Month 1: add skills. Year 1: build custom pipelines.

**Future Proof** -- Models will change. Vendors will come and go. Your knowledge, preferences, and decisions stay with you.

---

## Contributing

Augur OS welcomes contributions -- new skills, bug fixes, documentation, and ideas. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=augur-os/augur-os&type=Date)](https://star-history.com/#augur-os/augur-os&Date)

---

## License

MIT License. See [LICENSE](LICENSE).

---

## Sponsored by Guriqo

Augur OS is sponsored by [Guriqo](https://guriqo.com) -- AI consulting for enterprises building intelligent systems.
