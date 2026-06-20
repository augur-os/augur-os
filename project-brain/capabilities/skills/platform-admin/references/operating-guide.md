# DevOps Operating Guide

## Core Competencies
- Environment checks and dependency setup
- Repo health and skill discovery
- Adaptive growth backlog generation

## Workflow Summaries

### Environment Check
1. Verify Python, uv, npm, git.
2. Validate environment variables.
3. Report missing tools.

### Dependency Installation
1. Run `uv sync` for Python.
2. Run `npm install` for dashboard.
3. Verify success and versions.

### Adaptive Growth
1. Load `references/adaptive-growth.md`.
2. Collect git context.
3. Generate prioritized backlog.
4. Write to `plugins/dev/skills/platform-admin/data/setup-manager/adaptive-growth/`.

### Skill Refactor Analysis
1. Inspect skill structure.
2. Identify duplication and doc gaps.
3. Create recommendations or tasks.

### Goodnight (Night Shift Prep)
1. Aggregate daily context.
2. Summarize open items.
3. Prepare overnight bundle.

## Requirements
- Python 3.10+
- uv (latest)
- npm 18+
- git 2.0+

## Configuration
- `AUGUR_GROWTH_PROVIDER`
- `AUGUR_GROWTH_MODEL`
- `AUGUR_GROWTH_OUTPUT_DIR`
- `AUGUR_LLM_PROFILE`

## Constraints
- Non-destructive: generate backlogs only.
- Redact sensitive paths in prompts.
- Use safe subprocess patterns.
