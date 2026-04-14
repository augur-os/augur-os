# Augur OS

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/augur-os/augur-os/actions/workflows/ci-tests.yml/badge.svg)](https://github.com/augur-os/augur-os/actions/workflows/ci-tests.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Node 20+](https://img.shields.io/badge/node-20+-green.svg)](https://nodejs.org/)

[Website](https://augur.run) | [Documentation](https://augur.run/more.html) | [Sessions](https://augur.run/sessions.html) | [Roadmap](ROADMAP.md)

> **Soft launch.** Augur is a local-first AI personal knowledge system that keeps your skills, memory, and automation on your machine.

Augur is currently in soft launch:

- Native macOS support is implemented.
- Native Windows architecture is implemented.
- Windows validation is still pending before we make a firmer public support claim.
- The canonical roadmap lives at [ROADMAP.md](ROADMAP.md).

Plain-text skills you can `cat`, `grep`, and `git diff`. Connect any MCP-compatible client. Keep your knowledge, preferences, and decisions local.

## What is Augur?

Augur is an open-source personal AI OS. It gives your AI clients a shared skill layer, a persistent knowledge base, and a local dashboard.

Think of it as `.bashrc` for your AI: configure with text files, debug with `cat`, version with `git`.

### Key Features

- **200+ composable skills** across the adaptive, brain, career, command, life, and studio hubs.
- **MCP-native** tooling exposed over Model Context Protocol.
- **Local dashboard** for humans and agents.
- **Ingest pipeline** for OCR, document extraction, web scraping, and bookmark import.
- **LLM Wiki** synthesized from ADRs, memory, and sessions.
- **Multi-client** support for Claude Code, Codex, Gemini CLI, Cursor, and Copilot.
- **Autoloops** for self-heal, code health, dependency audit, and memory sync.
- **Airplane mode** for offline operation with Ollama or local models.

## Working Locally

This repository is the source of truth for development and validation. Treat the repo-first workflow as canonical for now, and treat platform-specific installers as validation paths rather than a broad public-ready install story.

```bash
git clone https://github.com/augur-os/augur-os.git
cd augur-os
corepack enable && pnpm install && uv sync
pnpm --filter dashboard dev
```

The dashboard runs at [localhost:3000](http://localhost:3000).

For Windows-specific validation, follow the repo scripts and the current platform notes rather than assuming public release readiness.

## Architecture

```
+-----------------------------------------------------------+
|                    REASONING LAYER                         |
|               (Model-Agnostic Planning)                   |
|      Claude  -  GPT  -  Ollama  -  Local Models           |
+-----------------------------+-----------------------------+
                              |
+-----------------------------v-----------------------------+
|                    EXECUTION LAYER                         |
|              (200+ Skills, Multi-Client)                  |
|                                                           |
|   skills/            Canonical Augur-managed skills       |
|   .cursor/...        Repo-scoped managed exports          |
|   .gemini/...        Repo-scoped managed exports          |
|   .codex/...         Prompt/native export targets         |
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

For a deeper dive, see [docs/architecture-overview.md](docs/architecture-overview.md).

## Repository Structure

```
augur-os/
├── apps/dashboard/     # Next.js dashboard
├── config/             # System configuration
├── docs/               # Documentation and ADRs
├── packages/           # Shared JS packages
├── plugins/            # Platform integrations
├── scripts/            # Bootstrap and support scripts
├── skills/             # 200+ composable skills
├── src/                # Framework (CLI, config, MCP server)
├── tests/              # Repo-level tests
└── .github/            # CI/CD workflows
```

## CLI

```bash
aug discover                         # Full JSON manifest
aug discover --hub career --compact  # Filter by hub
aug <tool-name> [--param value ...]  # Run any tool
aug unified-search --query "health tracking"
aug --list-tools
```

## Built With

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11+, uv |
| MCP server | Python MCP SDK (stdio JSON-RPC) |
| Dashboard | Next.js 15, TypeScript, Tailwind CSS, shadcn/ui |
| Package manager | pnpm (workspaces) |
| Document processing | MarkItDown, ReportLab |
| AI clients | Claude Code, Codex, Gemini CLI, Cursor, Copilot |

## Contributing

Contributions are welcome, but the project should be treated as soft launch work rather than a broadly public-ready release. See [CONTRIBUTING.md](CONTRIBUTING.md) for current workflow notes.

## License

MIT License. See [LICENSE](LICENSE).
