# Plugin Distribution Polish — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Polish the plugin distribution story so Augur skills are installable via `claude install`, `npx skills add`, and per-skill zip uploads to claude.ai, and refactor the onboarding SKILL.md into a lean routing file with mode-per-file references.

**Architecture:** Five independent tasks: audit/fix plugin manifests, verify per-skill cherry-picking, add `!command` dynamic detection to onboarding, refactor onboarding SKILL.md into mode-per-file references, and add a per-skill zip release workflow.

**Tech Stack:** YAML/JSON config, GitHub Actions, Markdown (SKILL.md), shell commands

---

### Task 1: Audit and fix plugin manifests for `claude install`

**Files:**
- Modify: `.claude-plugin/plugin.json`
- Modify: `.claude-plugin/marketplace.json`
- Modify: `README.md` (add install command)

The current `plugin.json` has `"skills": "./skills/"` which should work for auto-discovery. But the `marketplace.json` `source` field points to `"./"` which is the repo root — verify this is correct for the marketplace schema. Also add `repository` and `keywords` fields that finance-skills uses for discoverability.

- [ ] **Step 1: Update plugin.json with repository and keywords**

In `.claude-plugin/plugin.json`, add `repository` and `keywords` fields matching the finance-skills pattern:

```json
{
  "name": "augur-skills",
  "description": "Augur personal knowledge and automation skills",
  "version": "1.0.0",
  "author": { "name": "Augur" },
  "homepage": "https://github.com/AugurOS/augur",
  "repository": "https://github.com/AugurOS/augur",
  "license": "MIT",
  "keywords": [
    "knowledge-management",
    "automation",
    "personal-knowledge",
    "second-brain",
    "productivity",
    "dashboard",
    "mcp"
  ],
  "skills": "./skills/"
}
```

- [ ] **Step 2: Update marketplace.json with metadata block**

In `.claude-plugin/marketplace.json`, add a `metadata` block with version info:

```json
{
  "name": "augur-skills",
  "owner": { "name": "Augur" },
  "metadata": {
    "description": "Personal knowledge, automation, and development skills for the Augur second brain system.",
    "version": "1.0.0"
  },
  "plugins": [
    {
      "name": "augur-skills",
      "description": "Personal knowledge, automation, and development skills",
      "version": "1.0.0",
      "source": "./"
    }
  ]
}
```

- [ ] **Step 3: Add install instructions to README.md**

Find the setup/installation section of the root `README.md` and add:

```markdown
### Quick Install (Claude Code Plugin)

```bash
claude install gh:AugurOS/augur
```

Skills are auto-discovered from `skills/` and namespaced as `augur-skills:<skill-name>`.

### Install Individual Skills

```bash
npx skills add AugurOS/augur --skill reading-list
npx skills add AugurOS/augur --skill finance -g  # global install
```
```

- [ ] **Step 4: Test `claude install` end-to-end**

Run `claude install gh:AugurOS/augur` in a test environment. If it fails, inspect the error and fix the manifest fields. Common issues: `skills` path not resolving, missing `repository` field, schema mismatch.

```bash
claude install gh:AugurOS/augur
```

Expected: Plugin installs, skills from `skills/` are discoverable.

- [ ] **Step 5: Commit**

```bash
git add .claude-plugin/plugin.json .claude-plugin/marketplace.json README.md
git commit -m "chore: update plugin manifests for claude install and marketplace discovery"
```

---

### Task 2: Verify per-skill cherry-picking via `npx skills add`

**Files:**
- Modify: Portable skill `README.md` files (8 skills)

The 8 portable skills (`x-augur-portable: true`) should each be independently installable. Each already has `SKILL.md` with frontmatter — verify the structure matches what `npx skills add` expects: a directory with `SKILL.md` at the root containing `name` and `description` in frontmatter.

- [ ] **Step 1: List all portable skills**

```bash
grep -rl "x-augur-portable: true" skills/*/SKILL.md
```

Expected: 8 skills listed. Note each skill directory name.

- [ ] **Step 2: Verify each portable skill has valid frontmatter**

For each portable skill, confirm `SKILL.md` has `name` and `description` in YAML frontmatter. These two fields are required by the Agent Skills standard for `npx skills add` to work.

```bash
for skill_dir in $(grep -rl "x-augur-portable: true" skills/*/SKILL.md | xargs -I{} dirname {}); do
  echo "=== $(basename $skill_dir) ==="
  head -10 "$skill_dir/SKILL.md"
  echo ""
done
```

Expected: Each skill shows `---` delimited frontmatter with `name:` and `description:` fields.

- [ ] **Step 3: Verify each portable skill has a README.md**

```bash
for skill_dir in $(grep -rl "x-augur-portable: true" skills/*/SKILL.md | xargs -I{} dirname {}); do
  if [ ! -f "$skill_dir/README.md" ]; then
    echo "MISSING README: $(basename $skill_dir)"
  fi
done
```

For any missing README, create one following this template:

```markdown
# <Skill Name>

<One-line description from SKILL.md frontmatter>

## Install

```bash
npx skills add AugurOS/augur --skill <skill-name>
```

## Platform

All platforms (Claude Code, Codex, Gemini CLI, GitHub Copilot)

## Reference Files

- `references/<file>.md` — <description>
```

- [ ] **Step 4: Test cherry-pick install for one skill**

```bash
npx skills add AugurOS/augur --skill reading-list
```

Expected: Skill is installed to `~/.claude/skills/reading-list/` with SKILL.md and references/ intact.

- [ ] **Step 5: Commit**

```bash
git add skills/*/README.md
git commit -m "docs: add install instructions to portable skill READMEs"
```

---

### Task 3: Add `!command` dynamic detection to onboarding SKILL.md

**Files:**
- Modify: `skills/onboard/SKILL.md`

Add dynamic environment checks that execute at skill load time, so the agent knows the machine state before asking any questions.

- [ ] **Step 1: Read current SKILL.md frontmatter and first section**

Read `skills/onboard/SKILL.md` lines 1-15 to understand current frontmatter.

- [ ] **Step 2: Add `!command` blocks after the frontmatter**

Insert after line 9 (after the closing `---`) and before `# /onboard`:

````markdown
## Environment (auto-detected)

```
!`(python3 --version 2>&1 && node --version 2>&1 && pnpm --version 2>&1 && uv --version 2>&1) || echo "DEPS_MISSING"`
```

```
!`cat "$HOME/Library/Application Support/Augur/state/onboard-complete.json" 2>/dev/null || echo "NOT_ONBOARDED"`
```

**If all deps present and state JSON shows `configured_clients`**: This is a returning user. Skip Steps 1-3 (clone, hooks, deps). Jump to the relevant mode.

**If `NOT_ONBOARDED`**: This is a fresh install. Run the default mode from Step 1.

**If `DEPS_MISSING`**: Some prerequisites are missing. Flag which ones and guide installation before proceeding.
````

- [ ] **Step 3: Verify the `!command` syntax is correct**

The `!command` pattern uses fenced code blocks with `` !`command` `` syntax. Verify by checking the finance-skills repo pattern. The command must:
- Run fast (< 2s)
- Include fallback output (`|| echo "..."`)
- Not require interactive input

Both commands above meet these criteria.

- [ ] **Step 4: Commit**

```bash
git add skills/onboard/SKILL.md
git commit -m "feat(onboard): add !command dynamic env detection at skill load time"
```

---

### Task 4: Refactor onboarding SKILL.md into mode-per-file references

**Files:**
- Modify: `skills/onboard/SKILL.md` (reduce from ~368 lines to ~100)
- Create: `skills/onboard/references/mode-default.md`
- Create: `skills/onboard/references/mode-migrate.md`
- Create: `skills/onboard/references/mode-connect.md`
- Create: `skills/onboard/references/mode-full.md`
- Create: `skills/onboard/references/mode-status.md`
- Create: `skills/onboard/references/mode-templates.md`

Extract each mode's content into its own reference file. The SKILL.md becomes a lean router.

- [ ] **Step 1: Create `references/mode-default.md`**

Extract lines 240-336 (Quick Start for New Users + Full Onboarding sections) into `skills/onboard/references/mode-default.md`:

```markdown
# Mode: Default — Interactive Setup

## Quick Start for New Users

**Prerequisites:** Python >=3.11, Node.js >=20, Git installed.

### Step 1: Clone Repository

```bash
mkdir -p ~/Projects && cd ~/Projects
git clone https://github.com/augur-os/augur-os.git Augur
cd Augur
```

### Step 2: Configure Git Hooks

```bash
git config core.hooksPath .githooks
```

This activates guards that block binary files, large files (>200KB), and commits to forbidden paths.

### Step 3: Install Dependencies

```bash
# Enable pnpm via corepack (built into Node.js)
corepack enable

# Install Node.js dependencies (uses pnpm global store)
pnpm install

# Install Python dependencies (uses uv global cache)
uv sync
```

### Step 4: Configure IDE (Automatic)

MCP is auto-configured when you start the dashboard. Just run `pnpm --filter dashboard dev` (Step 5).

**Manual setup** (if needed):
```bash
python3 src/scripts/configure_mcp.py --apply
```

### Step 5: Start Dashboard

```bash
pnpm --filter dashboard dev
```

Dashboard runs at **http://localhost:3000**

### Step 6: Verify Setup

1. Open Claude Desktop - Augur MCP should appear in tools
2. Open Dashboard - should load without errors
3. Try: `/load-context` in Claude

## Full Onboarding (Existing Projects)

For adding a new project to an existing Augur installation.

### 1. Gather Project Information

| Field | Description | Example |
|-------|-------------|---------|
| Project name | Short identifier | `my-saas-app` |
| Project type | Category | `webapp`, `api`, `library`, `cli` |
| Repository URL | Git remote | `github.com/user/repo` |
| Tech stack | Primary technologies | `Next.js, Python, PostgreSQL` |

### 2. Initialize Configuration

```bash
python src/scripts/init_project.py --name "PROJECT_NAME" --type "PROJECT_TYPE"
```

### 3. Configure Skills

| Project Type | Recommended Skills |
|--------------|-------------------|
| webapp | frontend, validator, developer |
| api | developer, security, validator |
| library | developer, knowledge, oss-manager |
| data | data-engineer, data-scientist |

### 4. Set Autonomy Level

| Level | Behavior |
|-------|----------|
| 0.0-0.3 | Manual approval for all changes |
| 0.4-0.6 | Auto-execute reads, manual for writes |
| 0.7-0.8 | Auto-execute most, manual for destructive |
| 0.9-1.0 | Full automation |

Update via dashboard Settings > General.

## Post-Onboarding Checklist

- [ ] Repository cloned
- [ ] Git hooks configured (`git config core.hooksPath .githooks`)
- [ ] Dependencies installed (pnpm + uv)
- [ ] IDE integration configured (Claude Desktop/Claude Code CLI/Cursor)
- [ ] Dashboard running at localhost:3000
- [ ] MCP tools visible in IDE (`claude mcp list` for Claude Code CLI)
```

- [ ] **Step 2: Create `references/mode-migrate.md`**

Extract lines 48-78 (Mode: --migrate + Vault Recovery) into `skills/onboard/references/mode-migrate.md`:

```markdown
# Mode: Migrate — Upgrade Existing Installation

Run when upgrading an existing Augur installation to the current structure. Skip clone/install steps.

## Steps

1. **Detect legacy data** — Scan for data in deprecated paths:
   - `plugins/` (pre-ADR-426 skill locations)
   - `.agent/workflows/` (pre-skill workflow files)
   - `config/dashboard/*.yaml` (centralized config, should be decentralized per ADR-163)
   - Old vault paths that don't match `get_vault_dir()` layout

2. **Migrate to vault** — Move user-editable data (memory, actions, skill data) to `get_vault_dir()` following ADR-270 external directory layout. Use `src.config.paths` for path resolution, never hardcode.

3. **Verify plugin structure** — Confirm skills are in `skills/{skill}/` per ADR-426/ADR-430. Flag any skills still in legacy `plugins/` directories.

4. **Verify MCP wiring** — Run `python3 src/scripts/configure_mcp.py --apply` to ensure IDE integration is current.

5. **Run Post-Onboarding Checklist** (in mode-default.md).

## Vault Recovery

During `--migrate` or `--full`, recover the vault if missing:

1. Check if the vault directory (resolved via `get_vault_dir()`) exists (the directory, not just a symlink)
2. If it exists and contains `.git/`, vault is present — skip recovery
3. If missing:
   a. Verify GitHub auth: run `gh auth status` — if it fails, stop and tell the user to run `gh auth login`
   b. Read `config/system/vault.yaml` — parse YAML, extract `vault.remote` (the git URL) and `vault.path` (resolved via `get_vault_dir()`)
   c. If `vault.remote` is empty or the file doesn't exist, stop and tell the user: "No vault remote configured. Run `/onboard --connect vault <repo-url>` first."
   d. Clone: `git clone <vault.remote> <vault.path>` (expand `~` to `$HOME`)
   e. Validate: check that the cloned directory has expected top-level dirs (actions/, memory/, skills/)
   f. If clone fails (private repo, wrong URL), show the git error and suggest: "Check the remote URL in `config/system/vault.yaml` or re-run with `/onboard --connect vault <correct-url>`"

## Connect Vault

`/onboard --connect vault <repo-url>` — wire a git remote for the vault:

1. **Update config**: Read `config/system/vault.yaml`. Set `vault.remote` to `<repo-url>`. Write back with `vault.path` preserved (resolved via `get_vault_dir()` if not set).
2. **Initialize git if needed**: Expand `vault.path` to an absolute path. If the directory doesn't exist, create it with `mkdir -p`.
   - If `<vault.path>/.git` does NOT exist: run `git init` then `git remote add origin <repo-url>`
   - If `<vault.path>/.git` EXISTS: run `git remote set-url origin <repo-url>` (or `git remote add origin <repo-url>` if no origin remote exists)
3. **Verify**: Run `git remote -v` in the vault directory and confirm the origin URL matches `<repo-url>`
4. **Report**: Tell the user the vault remote is configured and they can run `/onboard --migrate` to clone content if the directory is empty
```

- [ ] **Step 3: Create `references/mode-connect.md`**

Extract lines 100-111 into `skills/onboard/references/mode-connect.md`:

```markdown
# Mode: Connect — Add Platform to Existing Installation

Supported platforms: `obsidian`, `vscode`, `cursor`, `claude-code`.

## Steps

1. **Verify Augur is installed** — Check `~/Projects/Augur` or `$AUGUR_DIR` exists.
2. **Configure MCP** — Run `scripts/configure_mcp.py --client <platform>`.
3. **Platform-specific setup**:
   - `obsidian`: Run `obsidian-scaffold` MCP tool to create `.obsidian/` config in vault
   - `vscode`/`cursor`: No additional setup needed (MCP wiring is sufficient)
4. **Update state** — Add platform to `configured_clients` in `~/Library/Application Support/Augur/state/onboard-complete.json`.
5. **Show getting-started message** for the platform.

## Getting-Started Messages

**From Claude Code (`--from claude-code` or default):**
> Augur is installed. Run `/commands` to see available commands, or open `localhost:3000` for the dashboard.

**From Obsidian (`--from obsidian`):**
> Augur is installed and your vault is configured. Open Obsidian and look for the Augur vault at the path configured in `project.yaml` (resolved via `get_vault_dir()`). The dashboard is at localhost:3000.

**From VS Code (`--from vscode`):**
> Augur is installed and MCP is configured. Open the Augur sidebar to check status. The dashboard is at localhost:3000.

**From Cursor (`--from cursor`):**
> Augur is installed and MCP is configured. The dashboard is at localhost:3000.
```

- [ ] **Step 4: Create `references/mode-full.md`**

Extract lines 96-98 into `skills/onboard/references/mode-full.md`:

```markdown
# Mode: Full — Complete Onboarding

Run for a complete setup that also handles migration. Combines all steps from default mode and migrate mode.

## Execution Order

1. **Run all default mode steps** (see `references/mode-default.md`): Clone, hooks, deps, IDE config, dashboard, verify
2. **Run all migrate mode steps** (see `references/mode-migrate.md`): Detect legacy data, migrate to vault, verify plugins, verify MCP
3. **Run Post-Onboarding Checklist** (in `references/mode-default.md`)

Use this when setting up on a machine that may have partial or outdated Augur artifacts.
```

- [ ] **Step 5: Create `references/mode-status.md`**

Extract lines 112-128 into `skills/onboard/references/mode-status.md`:

```markdown
# Mode: Status — Show Installation State

Display the current Augur installation state. Read-only, modifies nothing.

## Steps

1. **Read state file** — Load `~/Library/Application Support/Augur/state/onboard-complete.json`.
2. **Display status table**:

| Field | Source |
|-------|--------|
| Installed | Check if install dir exists |
| Install source | `install_source` from state file |
| Connected platforms | `configured_clients` from state file |
| Vault scaffolded | `vault_scaffolded` from state file |
| Dashboard status | Ping `localhost:3000` |
| MCP status | Ping `localhost:3001/health` |

If no state file exists, show "Augur has not been fully onboarded. Run `/onboard` first."
```

- [ ] **Step 6: Create `references/mode-templates.md`**

Extract lines 130-172 into `skills/onboard/references/mode-templates.md`:

```markdown
# Mode: Templates — Template-Based Onboarding

Instead of showing individual plugins, present a catalog of dashboard templates grouped by hub. The user picks templates, and required plugins are auto-derived and enabled.

## Steps

1. **Discover templates** — Scan `plugins/ui/templates/{hub}/*.yaml` for all available template YAML files. Parse each file to extract `name`, `description`, `hub`, `icon`, and `requires` fields.

2. **Display template catalog** — Group templates by hub:
   ```
   brain:
     - Library — Reading list and knowledge documents browser (requires: reading-list, knowledge)
     - Memory — ... (requires: ...)
   career:
     - Pipeline — ... (requires: ...)
   life:
     - Home — ... (requires: ...)
     - Wellness — ... (requires: ...)
   ```

3. **User selects templates** — Accept template names or IDs (YAML filename without extension).

4. **Auto-derive required plugins** — Collect all entries from each selected template's `requires` array. Deduplicate to produce a flat list of required plugins.

5. **Auto-enable plugins** — For each plugin, locate its skill directory and write a `.config` file with `enabled: true`. Skip missing community skills and note them.

6. **Write active templates** — Write selections to `get_vault_dir()/dashboard/active.yaml`:
   ```yaml
   brain:
     templates:
       - library
       - memory
   career:
     templates:
       - pipeline
   ```
   Merge with existing entries (do not drop previously activated templates).

7. **Confirm** — Display summary of activated templates and auto-enabled plugins.
```

- [ ] **Step 7: Rewrite SKILL.md as lean router**

Replace the entire content of `skills/onboard/SKILL.md` with a lean routing file (~100 lines):

```markdown
---
name: onboard
x-augur-type: command
x-augur-tags: []
description: Setup wizard for fresh installs, migrations, full onboarding, and multi-platform connection. Use --migrate for upgrades, --full for complete setup, --connect to add platforms, --status to check install state.
x-augur-visibility: core
x-augur-hub: command
x-augur-tab: system
---
# /onboard

## Environment (auto-detected)

` ``
!`(python3 --version 2>&1 && node --version 2>&1 && pnpm --version 2>&1 && uv --version 2>&1) || echo "DEPS_MISSING"`
` ``

` ``
!`cat "$HOME/Library/Application Support/Augur/state/onboard-complete.json" 2>/dev/null || echo "NOT_ONBOARDED"`
` ``

**If all deps present and state JSON shows `configured_clients`**: Returning user. Skip install steps, jump to relevant mode.
**If `NOT_ONBOARDED`**: Fresh install. Run default mode.
**If `DEPS_MISSING`**: Flag missing prerequisites before proceeding.

## Usage

- `/onboard` — Interactive step-by-step setup (default)
- `/onboard --migrate` — Migration-focused onboarding for existing installations
- `/onboard --full` — Complete onboarding: fresh install + migration + verification
- `/onboard --connect <platform>` — Add a platform to an existing installation
- `/onboard --templates` — Template-based onboarding: pick dashboard templates, auto-enable required plugins
- `/onboard --status` — Show install state and connected platforms

## Options

| Flag | Description |
|------|-------------|
| `--help` | Show usage and stop |
| `--evolve` | Trigger skill self-improvement |
| `--migrate` | Run migration-focused onboarding |
| `--full` | Run complete onboarding |
| `--connect <platform>` | Add a platform (obsidian, vscode, cursor, claude-code) |
| `--status` | Show install state |
| `--templates` | Template-based onboarding |

## Mode Selection

Parse arguments to determine mode, then read the corresponding reference file:

| Argument | Reference File | What runs |
|----------|---------------|-----------|
| *(none)* | `references/mode-default.md` | Interactive setup: Steps 1-6 + Post-Onboarding Checklist |
| `--migrate` | `references/mode-migrate.md` | Legacy detection, vault migration, plugin/MCP verification |
| `--full` | `references/mode-full.md` | Default steps + migration steps + verification |
| `--connect <platform>` | `references/mode-connect.md` | MCP wiring + platform-specific setup |
| `--status` | `references/mode-status.md` | Read-only state display |
| `--templates` | `references/mode-templates.md` | Template catalog, auto-derive and enable plugins |

**Read the reference file for the selected mode and follow its instructions.**

## `augur init` — Create a New Project

Before onboarding, scaffold a new project:

```bash
python skills/onboard/scripts/augur_init.py <project-name> [--port PORT] [--repo URL]
```

## AI Agent Install (Skills Pack)

For AI agent users, a universal install prompt is at `skills/onboard/install.md`. The agent auto-detects the platform, asks skills-only or full system, and installs accordingly.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `python` not found | Use `python3` on macOS/Linux |
| Claude Desktop doesn't show MCP | Restart Claude Desktop after running configure_mcp.py |
| Dashboard build fails | Run `pnpm install` again, check Node version (20+) |
| Permission denied (Python) | Run `uv sync` instead of pip |

## Additional resources

- install.md
- evals/rank.json
- references/platform-detection.md
```

- [ ] **Step 8: Verify all reference files exist**

```bash
ls -la skills/onboard/references/
```

Expected: `platform-detection.md`, `mode-default.md`, `mode-migrate.md`, `mode-connect.md`, `mode-full.md`, `mode-status.md`, `mode-templates.md`

- [ ] **Step 9: Commit**

```bash
git add skills/onboard/SKILL.md skills/onboard/references/
git commit -m "refactor(onboard): split SKILL.md into mode-per-file references

Reduces SKILL.md from 368 to ~100 lines. Each --mode flag loads only
the relevant reference file, saving tokens on every invocation."
```

---

### Task 5: Add per-skill zip release workflow

**Files:**
- Create: `.github/workflows/release-skills.yml`
- Modify: `.github/workflows/export-plugins.yml` (minor: ensure tarball compat)

- [ ] **Step 1: Create the release workflow**

Create `.github/workflows/release-skills.yml`:

```yaml
name: Release Individual Skills

on:
  push:
    branches: [main]
    paths:
      - 'skills/*/SKILL.md'
  workflow_dispatch:

jobs:
  release-skills:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Zip each skill directory
        run: |
          mkdir -p dist/skills-zips
          for skill_dir in skills/*/; do
            skill_name=$(basename "$skill_dir")
            # Only zip if SKILL.md exists (real skill, not a support dir)
            if [ -f "$skill_dir/SKILL.md" ]; then
              cd "$skill_dir"
              zip -r "../../dist/skills-zips/${skill_name}.zip" . \
                -x "__pycache__/*" "augur/tests/*" ".pytest_cache/*" "*.pyc"
              cd ../..
              echo "Zipped: $skill_name"
            fi
          done
          ls -la dist/skills-zips/

      - name: Create or update release
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          # Delete existing 'skills-latest' release if it exists
          gh release delete skills-latest --yes 2>/dev/null || true
          # Create new release with all zips
          gh release create skills-latest \
            --title "Individual Skills (Latest)" \
            --notes "Individual skill zips for claude.ai upload. Each .zip contains one skill directory ready for Settings > Capabilities > Skills > Upload." \
            --prerelease \
            dist/skills-zips/*.zip
```

- [ ] **Step 2: Verify the workflow YAML is valid**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/release-skills.yml'))"
```

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/release-skills.yml
git commit -m "ci: add per-skill zip release workflow for claude.ai uploads

Zips each skills/*/ directory and publishes as GitHub release artifacts.
Users can download individual .zip files and upload to claude.ai Skills."
```
