# Developer Guide

This guide covers the current development workflow for Augur.

Augur is currently in soft launch, so this guide reflects the current repo state and validation workflow rather than a finished public-release surface.

## Bootstrap

Start from the repo directly:

```bash
git clone https://github.com/augur-os/augur-os.git
cd augur-os
corepack enable
pnpm install
uv sync
```

For local dashboard work:

```bash
pnpm --filter dashboard dev
```

## Repository Structure

The current repo is organized around a cross-platform core plus skill-owned extensions:

```text
augur-os/
├── apps/dashboard/      # Next.js dashboard shell
├── config/              # System configuration
├── docs/                # Canonical documentation
├── packages/            # Shared JS packages
├── plugins/             # Platform and integration adapters
├── scripts/             # Bootstrap and support scripts
├── skills/              # Skill-owned logic, MCP tools, and UI
├── src/                 # Core Python config, MCP, and libraries
└── tests/               # Repo-level tests
```

## Creating A Skill

Create new skills under `skills/{skill-name}/`.

See [creating-skills.md](creating-skills.md) for the canonical skill structure and authoring rules.

At a minimum, keep each skill self-contained:

```text
skills/{skill-name}/
├── SKILL.md
├── references/
├── scripts/
├── assets/
└── augur/
    ├── tests/
    └── dashboard/   # optional
```

If a skill exposes UI, the source of truth lives with the skill and is mounted into the dashboard shell.

## Testing

Use `uv` so tests run with the repo-managed Python environment:

```bash
uv run pytest
uv run pytest tests/
```

When you touch dashboard code, run the dashboard checks too:

```bash
pnpm --filter dashboard lint
pnpm --filter dashboard build
```

## Release Posture

The roadmap and release posture are still soft-launch scoped. Treat release docs, support claims, and platform statements as part of that external story rather than as a fully public product pipeline.

## Best Practices

- Keep `SKILL.md` focused and concise.
- Use `src/config/paths.py` instead of hardcoded data paths.
- Keep user data outside the repo-managed code surface.
- Prefer small, reviewable changes over broad rewrites.
- Update docs when platform support or release posture changes.
