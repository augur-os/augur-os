# Getting Started with Augur OS

Augur is in soft launch. Native macOS support is implemented. Native Windows architecture is implemented, but Windows validation is still pending before any firmer support claim.

## Prerequisites

- Python 3.11+
- Node.js 20+
- `corepack`
- `uv`

## Clone The Repo

The current source-of-truth workflow is repo-first:

```bash
git clone https://github.com/augur-os/augur-os.git
cd augur-os
corepack enable
pnpm install
uv sync
```

## Run The Dashboard

```bash
pnpm --filter dashboard dev
```

The dashboard runs at `http://localhost:3000`.

## Configure MCP

Use the repo-managed config writer instead of hand-editing example files:

```bash
python scripts/configure_mcp.py --list-ides
python scripts/configure_mcp.py --client cursor --auto
```

For Windows-specific setup and validation, see [guides/installation-windows.md](guides/installation-windows.md).

## What Next

- Discover tools: `aug discover`
- Search your knowledge: `aug unified-search --query "your topic"`
- Create a skill: See [creating-skills.md](creating-skills.md)
- Explore the architecture: See [architecture-overview.md](architecture-overview.md)
