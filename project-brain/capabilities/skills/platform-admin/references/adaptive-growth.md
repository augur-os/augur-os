# Adaptive Repo Growth (Design)

## Problem
The Augur monorepo evolves quickly: skills change, the dashboard UI changes, and the user-data repo changes. Over time, the UI and skill workflows drift from the current reality of the codebase (missing buttons, stale docs, broken flows). The cost is paid as “UI debt” and “workflow debt”.

## Goal
Create an **Adaptive Repo Growth** feature that, on demand, analyzes recent changes and produces a **backlog markdown file** containing concrete, executable tasks for improving:
- `apps/dashboard/` (GUI improvements)
- `plugins/*` (skill updates)
- docs/tests/release notes

The backlog is designed to be handed off to an agentic IDE (Cursor/Claude Code/Antigravity) and executed incrementally.

## Non-Goals
- Auto-applying code changes (this feature generates a plan/backlog, it does not patch the repo by itself).
- Shipping an opinionated “one true roadmap”. The output is a best-effort suggestion.
- Replacing CI/test enforcement. It should encourage tests, not bypass them.

## Entry Points
### 1) Dashboard (GUI)
Add a button in **Setup & Health**:
- “Generate Growth Backlog”
- Optional inputs: commit range / last-N commits for project + data repo
- Output: backlog path + quick-open button

### 2) Chat / MCP (Skill)
Extend `plugins/setup-manager` MCP server with a new tool:
- `adaptive_growth`
- Same inputs as the GUI
- Returns: summary + backlog path

## Inputs
### Repos
- **Project repo**: the Augur repo root (auto-detected).
- **Data repo**: user data directory (resolved via `src/config/paths.py`). If it is not a git repo, analysis is skipped with a note.

### Commit Selection
Two supported modes (per repo):
1) **Last N commits** (default): `n=20`
2) **Explicit range**: user-provided `from..to` / `from...to` / single commit-ish

## Outputs
### Backlog file
Generated under user data (default):
`plugins/dev/skills/platform-admin/data/setup-manager/adaptive-growth/growth-backlog-YYYYMMDD-HHMMSS.md`

Why user data?
- Generated artifacts are personal and should not be committed by default.
- The dashboard already allowlists opening files under plugin data directories.

### Backlog format (agent-friendly)
- A short “Context” section (ranges, commits, changed files).
- A prioritized task list grouped by area:
  - Dashboard/UI
  - Skill plugins
  - Data/schema migrations
  - Docs/tests/maintenance
- Each task includes:
  - Goal
  - Files/areas likely impacted
  - Acceptance criteria
  - Suggested commands (lint/test/build)

## How It Works (Pipeline)
1) **Collect git context** (per repo)
   - commit list (`git log`)
   - changed files (`git diff --name-status` or per-commit fallback)
   - diff stats (`git diff --stat`)
   - optional small diff snippets (truncated)

2) **Build analysis context**
   - categorize changes by repo area (`apps/dashboard`, `plugins/<skill>`, docs, scripts)
   - include “operational signals” (e.g. missing dependencies, failing tool invocations) when available

3) **Generate suggestions**
   - default: deterministic heuristics (always works)
   - optional: LLM-powered suggestions when configured (OpenAI/Anthropic/CLI provider)
   - LLM output is requested as strict JSON and then rendered to markdown

4) **Write backlog file**
   - create directories as needed
   - write markdown in a stable format
   - return metadata to caller (GUI/MCP)

## Configuration
Environment variables (optional):
- `AUGUR_GROWTH_PROVIDER`: `none` (default) | `llm` | `openai` (legacy) | `command` (legacy)
- `AUGUR_GROWTH_MODEL`: model override (optional)
- `AUGUR_GROWTH_COMMAND`: a CLI command to run an LLM (reads prompt from stdin, writes response to stdout)
- `AUGUR_GROWTH_OUTPUT_DIR`: override backlog output directory

When `AUGUR_GROWTH_PROVIDER=llm`, Setup Manager uses the src/lib LLM profile configuration from your user data repo:
- `data/core/llm.yaml` (preferred) or `data/core/config.yaml` under `llm:`
- Select active profile via `AUGUR_LLM_PROFILE`

## Safety / Privacy
- Never runs arbitrary shell strings; all subprocess calls use argument arrays.
- Only reads git state; does not modify repos.
- Backlog generation writes to a single directory under user-data (or configured output dir).
- LLM prompts should avoid embedding secrets; optionally redact paths/usernames in prompts.

## Future Enhancements
- Use `dependencies.yaml` to compute blast-radius and include dependency-aware suggestions.
- Support “diff since last backlog generation” (delta mode).
- Optionally open a PR-ready branch and create scaffolding PRs (still not auto-merge).
- Auto-generate changelog snippets and release checklist updates.
