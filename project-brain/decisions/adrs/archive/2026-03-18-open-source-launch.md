# Open Source Launch Preparation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prepare the Augur codebase for public open-source launch as `augur-os/augur-os` on GitHub.

**Architecture:** Fresh git history from scrubbed codebase. MIT license. All 132 skills ship publicly with personal data replaced by generic examples. CI workflows migrated from self-hosted to GitHub-hosted runners. System works gracefully with no vault/RAG/daemon present.

**Tech Stack:** Python, TypeScript/Next.js, GitHub Actions, `gh` CLI, Chrome MCP for GitHub org setup.

**Spec:** `docs/superpowers/specs/2026-03-18-open-source-launch-design.md`

---

## Phase 1: Code Changes (Sequential — Complete Before Phase 2)

Phase 1 tasks can run in parallel EXCEPT Task 5 (fresh-install resilience) which must run after Tasks 1-3.

---

### Task 1: Personal Data Scrub

**Files:**
- Modify: All 132 skills in `.claude/skills/*/`
- Rename dirs: `.claude/skills/client-smb-design/` → `.claude/skills/smb-client-template/`
- Rename dirs: `.claude/skills/client-ai-consulting/` → `.claude/skills/consulting-template/`
- Rename dirs: `.claude/skills/danit/` → `.claude/skills/design-content-pipeline/`
- Rename dirs: `.claude/skills/client-hub/` → `.claude/skills/hub-template/` (not in spec — discovered during plan research, needs maintainer approval)
- Rename dirs: `.claude/skills/client-terminal-automation/` → `.claude/skills/terminal-automation-template/` (not in spec — discovered during plan research, needs maintainer approval)
- Rename file: `.claude/skills/content/commands/danit.md` → `.claude/skills/content/commands/design-content-pipeline.md`

**IMPORTANT:** This task produces a scrub report first. Do NOT apply changes until the maintainer approves.

- [ ] **Step 1: Generate PII scan report**

Run automated grep for known personal data patterns across the codebase:

```bash
# Client names
grep -r "Danit\|danit" .claude/skills/ --include="*.md" --include="*.py" --include="*.ts" --include="*.yaml" -l

# Personal paths
grep -r "~" . --exclude-dir=.git --exclude-dir=node_modules -l

# Personal GitHub refs
grep -r "gsannikov" . --exclude-dir=.git --exclude-dir=node_modules -l

# Email addresses (non-example)
grep -rP "[a-zA-Z0-9._%+-]+@(?!example\.com)[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}" .claude/skills/ --include="*.md" --include="*.py" --include="*.yaml" -l

# Client-specific skill names
grep -r "client-smb-design\|client-ai-consulting\|client-hub\|client-terminal-automation" . --exclude-dir=.git --exclude-dir=node_modules -l
```

Save results to a temporary report file. Present to maintainer for approval.

- [ ] **Step 2: Rename skill directories**

```bash
# Rename 5 client-specific skills
mv .claude/skills/client-smb-design .claude/skills/smb-client-template
mv .claude/skills/client-ai-consulting .claude/skills/consulting-template
mv .claude/skills/danit .claude/skills/design-content-pipeline
mv .claude/skills/client-hub .claude/skills/hub-template
mv .claude/skills/client-terminal-automation .claude/skills/terminal-automation-template

# Rename slash command file
mv .claude/skills/content/commands/danit.md .claude/skills/content/commands/design-content-pipeline.md
```

- [ ] **Step 3: Update SKILL.md frontmatter in renamed skills**

For each renamed skill, update the `name` and `description` fields in SKILL.md. Replace client-specific names with generic ones:
- "Danit Design" → "Acme Design Co"
- "Danit Design Office freelance interior design practice" → "Freelance design practice content pipeline template"
- Client-specific descriptions → generic template descriptions

- [ ] **Step 4: Scrub hardcoded data filenames in Python MCP tools**

In `.claude/skills/smb-client-template/scripts/mcp/`: replace `danit-design.yaml` and similar hardcoded client filenames with generic names like `sample-client.yaml`.

- [ ] **Step 5: Scrub personal data across all skills**

Apply the approved scrub report changes:
- Replace personal email addresses with `user@example.com`
- Replace phone numbers with `+1-555-0100`
- Replace `~/` with config-resolved paths or `~`
- Replace career-specific company names and job data with sample data
- Replace financial account details with example data
- Replace health records with sample templates
- Genericize Guriqo consulting processes

- [ ] **Step 6: Update all cross-references to renamed skills**

Search for old skill names across the entire repo and update:

```bash
grep -r "client-smb-design\|client-ai-consulting\|client-hub\|client-terminal-automation" . --exclude-dir=.git --exclude-dir=node_modules -l
```

Update references in: CLAUDE.md, skill registry, any SKILL.md that references these skills, dashboard mounting configs, assembled-hubs.json.

- [ ] **Step 7: Verify build passes after scrub**

```bash
cd apps/dashboard && npm run build
```

Expected: Build succeeds with no errors related to renamed skills.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: scrub personal data and rename client skills for open source launch

Rename 5 client-specific skills to generic templates:
- client-smb-design → smb-client-template
- client-ai-consulting → consulting-template
- danit → design-content-pipeline
- client-hub → hub-template
- client-terminal-automation → terminal-automation-template

Replace all personal data (client names, emails, paths, financial/health data)
with generic sample data."
```

---

### Task 2: License Switch (ELv2 → MIT)

**Files:**
- Modify: `LICENSE`
- Modify: `CONTRIBUTING.md`
- Modify: `pyproject.toml`
- Modify: `src/mcp/pyproject.toml`
- Modify: `.claude/skills/devops/pyproject.toml`
- Modify: `apps/dashboard/package.json`
- Delete: `docs/COMMERCIAL.md`

- [ ] **Step 1: Replace LICENSE file entirely**

Replace the entire content of `LICENSE` with MIT license text:

```
MIT License

Copyright (c) 2026 Augur OS Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 2: Update pyproject.toml license fields**

In `pyproject.toml` (root): change `license = { text = "Elastic-2.0" }` → `license = { text = "MIT" }`

In `src/mcp/pyproject.toml`: same change.

In `.claude/skills/devops/pyproject.toml`: same change.

- [ ] **Step 3: Update package.json license fields**

In `apps/dashboard/package.json`: change `"license": "Elastic-2.0"` → `"license": "MIT"`

Search for any other package.json files with Elastic license:
```bash
grep -r '"Elastic-2.0"' . --include="package.json" --exclude-dir=node_modules -l
```

Update all found.

- [ ] **Step 4: Update CONTRIBUTING.md license terms**

Replace the ELv2 contribution terms section (around lines 28-60) with:

```markdown
## License and Contribution Terms

Augur OS is licensed under the **MIT License**. By contributing to this project, you agree that your contributions will be licensed under the MIT License.
```

- [ ] **Step 5: Delete docs/COMMERCIAL.md**

```bash
rm docs/COMMERCIAL.md
```

- [ ] **Step 6: Grep for any remaining Elastic License references**

```bash
grep -ri "elastic.license\|elastic-2.0\|ELv2\|Elastic License" . --exclude-dir=.git --exclude-dir=node_modules -l
```

Update or remove all hits. Check `dist/plugins/` — these are generated but may contain stale license refs. Regeneration will fix them later but clean up now if feasible.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: switch license from Elastic License 2.0 to MIT

Replace LICENSE file entirely with MIT text.
Update license fields in pyproject.toml, package.json.
Update CONTRIBUTING.md terms.
Delete docs/COMMERCIAL.md."
```

---

### Task 3: Rename References

**Files:**
- Modify: `README.md` (badges, URLs)
- Modify: `CONTRIBUTING.md` (GitHub URLs)
- Modify: `SECURITY.md` (email, URLs)
- Modify: `CHANGELOG.md` (URLs)
- Modify: `scripts/install.sh` (repo URLs, stale paths, post-install message)
- Modify: `.github/FUNDING.yml`
- Modify: `pyproject.toml` (project URLs)
- Modify: `src/mcp/pyproject.toml` (project URLs)

- [ ] **Step 1: Find all GitHub URL references**

```bash
grep -r "augur-ai/augur\|gsannikov/augur\|augur-project/augur\|gsannikov/claude-skills" . --exclude-dir=.git --exclude-dir=node_modules -l
```

- [ ] **Step 2: Update all GitHub URLs to `augur-os/augur-os`**

For each file found in Step 1, replace:
- `augur-ai/augur` → `augur-os/augur-os`
- `gsannikov/augur` → `augur-os/augur-os`
- `augur-project/augur` → `augur-os/augur-os`
- `gsannikov/claude-skills` → `augur-os/augur-os`

- [ ] **Step 3: Full scrub of install.sh**

`scripts/install.sh` needs more than URL updates:
- Lines 6, 21: `gsannikov/augur` URLs → `augur-os/augur-os`
- Line 177: `uv run pytest plugins/ai/memory/tests -q` → update to `.claude/skills/` path
- Lines 331, 344: `plugins/dev/skills/devops/scripts/setup_wizard.py` and `oauth_wizard.py` → `.claude/skills/devops/scripts/`
- Line 354: Same stale pytest path
- Line 357: Post-install message "Data is stored within the monorepo at: ${INSTALL_DIR}/plugins/" → update to reflect `.claude/skills/` and vault structure

- [ ] **Step 4: Update FUNDING.yml**

```yaml
github: [gsannikov]  # Keep personal sponsorship handle OR update to augur-os org
```

Decision: Keep `gsannikov` for now (GitHub Sponsors needs separate setup for org). Add a comment noting this points to the maintainer's personal sponsors page.

- [ ] **Step 5: Update pyproject.toml URLs**

Check both `pyproject.toml` and `src/mcp/pyproject.toml` for `[project.urls]` sections. Update any GitHub URLs to `augur-os/augur-os`.

- [ ] **Step 6: Verify no remaining old references**

```bash
grep -r "augur-ai\|gsannikov" . --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.claude/skills/*/assets --exclude=FUNDING.yml --exclude=sync-upstream.yml | head -30
```

Expected: Zero hits. **Intentional exceptions**: `FUNDING.yml` (maintainer handle), `sync-upstream.yml` (deleted in Task 4 — skip here).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: rename all GitHub references to augur-os/augur-os

Update URLs in README, CONTRIBUTING, SECURITY, CHANGELOG, install.sh,
pyproject.toml, FUNDING.yml. Fix stale plugins/ paths in install.sh."
```

---

### Task 4: CI Workflow Migration

**Files:**
- Modify: `.github/workflows/ci-tests.yml`
- Modify: `.github/workflows/ci-lint.yml`
- Modify: `.github/workflows/ci-security.yml`
- Modify: `.github/workflows/ci-cross-platform.yml`
- Modify: `.github/workflows/cron-nightly.yml`
- Modify: `.github/workflows/claude.yml`
- Modify: `.github/workflows/codex.yml`
- Modify: `.github/workflows/release.yml`
- Modify: `.github/workflows/cd-release.yml`
- Modify: `.github/workflows/export-plugins.yml`
- Delete: `.github/workflows/sync-upstream.yml`
- Modify: `.github/workflows/README.md`

- [ ] **Step 1: Migrate runners from self-hosted to ubuntu-latest**

For each workflow file, find `runs-on: self-hosted` and replace with `runs-on: ubuntu-latest`.

Exception: `ci-cross-platform.yml` should use a matrix: `runs-on: ${{ matrix.os }}` with `strategy.matrix.os: [ubuntu-latest, macos-latest]`.

- [ ] **Step 2: Fix stale plugins/ script paths in all workflows**

Run the full audit:
```bash
grep -rn "plugins/" .github/workflows/ --include="*.yml"
```

For each hit, update `plugins/crew/skills/devops/` → `.claude/skills/devops/`, `plugins/dev/skills/` → `.claude/skills/`, `plugins/ai/skills/` → `.claude/skills/`, etc.

Known fixes:
- `ci-lint.yml:228`: `plugins/crew/skills/devops/scripts/cleanup_paths.py` → `.claude/skills/devops/scripts/cleanup_paths.py`
- `ci-lint.yml:329`: embedded Python glob `plugins/**/*.yaml` → `.claude/skills/**/*.yaml` (currently scans empty dir)
- `ci-tests.yml:72,77`: `plugins/crew/skills/devops/scripts/ci_change_detector.py` → `.claude/skills/devops/scripts/ci_change_detector.py`
- `ci-security.yml:139`: `bandit -r packages/ src/ plugins/` → `bandit -r src/ .claude/skills/` (currently misses all skill Python code)
- `cron-nightly.yml:106`: `plugins/ai/skills/ai_bridge/scripts/sync_agents.py` → `.claude/skills/ai_bridge/scripts/sync_agents.py`
- `cron-nightly.yml:170-171`: `ci_failure_analyzer.py` path → `.claude/skills/devops/scripts/`
- `cron-nightly.yml:263-264`: `dependency_tracker.py` path → `.claude/skills/devops/scripts/`
- `export-plugins.yml:50`: `skill_exporter.py` path → `.claude/skills/mcp-app-factory/scripts/`
- `cd-release.yml:70`: `dependency_tracker.py` path → `.claude/skills/devops/scripts/`
- `cd-release.yml:115`: `plugins/crew/skills/devops/scripts/release.py` → `.claude/skills/devops/scripts/release.py`

- [ ] **Step 3: Handle private data repo dependency in cron-nightly.yml**

`cron-nightly.yml` checks out `gsannikov/augur-data` at **two locations** (line 45 in job 1, line 144 in job 2). Add a guard to **both**:

```yaml
- name: Checkout metrics data
  if: github.repository == 'augur-os/augur-os' && github.actor == 'gsannikov'
  uses: actions/checkout@v4
  with:
    repository: gsannikov/augur-data
    token: ${{ secrets.GH_PAT }}
    path: augur-data
  continue-on-error: true
```

This makes it maintainer-only and non-blocking.

- [ ] **Step 4: Handle claude.yml — per-job decision**

Keep `claude-ask` job (read-only PR help, useful for contributors) — migrate to `ubuntu-latest`.

For `claude-fix`, `codex-review-auto-fix`, `claude-review`, `claude-review-fix`: add guard:

```yaml
if: github.repository == 'augur-os/augur-os' && github.actor == 'gsannikov'
```

This keeps them in the file but they only run for the maintainer.

- [ ] **Step 5: Handle codex.yml — TRIGGER_PAT secret**

Add `continue-on-error: true` to the step using `TRIGGER_PAT`. This makes it graceful when the secret doesn't exist (forks, new contributors).

**Note:** `if: secrets.TRIGGER_PAT != ''` is NOT valid GitHub Actions syntax — `secrets.*` cannot be used in `if:` expressions. Use `continue-on-error: true` only.

- [ ] **Step 6: Delete sync-upstream.yml**

```bash
rm .github/workflows/sync-upstream.yml
```

- [ ] **Step 7: Update .github/workflows/README.md**

Fix stale workflow names (`ci-test.yml` → `ci-tests.yml`, `ci-quality.yml` → `ci-lint.yml`), update all `plugins/` script paths, remove `sync-upstream.yml` entry, note that runners use `ubuntu-latest`.

- [ ] **Step 8: Verify workflows parse correctly**

```bash
# Check YAML validity for all workflow files
for f in .github/workflows/*.yml; do python -c "import yaml; yaml.safe_load(open('$f'))"; echo "$f: OK"; done
```

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat: migrate CI workflows for public GitHub repo

Migrate all runners from self-hosted to ubuntu-latest.
Fix stale plugins/ script paths to .claude/skills/.
Guard private data repo + credential-dependent jobs as maintainer-only.
Delete sync-upstream.yml (fork-only workflow).
Update workflows README."
```

---

### Task 5: Fresh-Install Resilience

**Dependency: Must run after Tasks 1-3 are complete.**

**Files:**
- Modify: `src/config/paths.py` (vault resolution)
- Modify: Any Python/TS file that reads vault/RAG/runtime/daemon paths without null checks

- [ ] **Step 1: Test with absent vault**

```bash
AUGUR_VAULT_DIR=/tmp/nonexistent-vault python -c "from src.config.paths import get_vault_dir; print(get_vault_dir())"
```

Expected: Returns path without crashing. If it crashes, fix `src/config/paths.py` to handle absent vault gracefully.

- [ ] **Step 2: Run full test suite with absent external paths**

```bash
AUGUR_VAULT_DIR=/tmp/nonexistent \
AUGUR_STATE_DIR=/tmp/nonexistent \
AUGUR_LOG_DIR=/tmp/nonexistent \
AUGUR_CACHE_DIR=/tmp/nonexistent \
pytest tests/ -x --timeout=60 2>&1 | head -100
```

Document every failure. Fix each one to return empty/default instead of crashing.

- [ ] **Step 3: Run dashboard build with absent vault**

```bash
cd apps/dashboard && npm run build
```

Expected: Build succeeds. Dashboard should render with "no data" states, not broken pages.

- [ ] **Step 4: Test MCP tools with no vault**

```bash
AUGUR_VAULT_DIR=/tmp/nonexistent python -m augur_mcp 2>&1 | head -20
```

Expected: MCP server starts. Tools that read vault return empty results, not exceptions.

- [ ] **Step 5: Test RAG with no index**

Verify the RAG indexing path creates indexes from scratch when none exist. The onboard flow should build RAG indexes on first run from whatever docs exist in the fresh install.

- [ ] **Step 6: Test daemon health with no config**

Verify daemon health checks report "not configured" status, not errors, when no daemon is running and no config exists.

- [ ] **Step 7: Fix all failures found in Steps 2-6**

For each failure, add graceful handling:
- Missing directory → auto-create or return empty
- Missing file → return default/empty, not exception
- Missing config → report "not configured"

- [ ] **Step 8: Re-run full test suite to verify fixes**

```bash
AUGUR_VAULT_DIR=/tmp/nonexistent \
AUGUR_STATE_DIR=/tmp/nonexistent \
pytest tests/ -x --timeout=60
```

Expected: All tests pass.

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat: add fresh-install resilience for absent vault/RAG/daemon

Ensure system works gracefully when vault, RAG indexes, runtime state,
and daemon config are absent. All paths return empty/default instead of
crashing. Required for open source first-run experience."
```

---

### Task 6: README Rewrite

**Files:**
- Modify: `README.md` (complete rewrite)

- [ ] **Step 1: Write new README**

Complete rewrite with this structure:

1. **Hero** — placeholder for now: `> [Hero tagline TBD — separate brainstorming session]`
2. **Badges** — MIT license, CI status (pointing to `augur-os/augur-os`), skill count
3. **What is this** — 3-4 sentences: local-first personal AI OS, skills-based, works with Claude/Cursor/Obsidian/VS Code
4. **Demo** — placeholder: `> [Screenshot/GIF TBD — MANUAL: record dashboard + CLI in action]`
5. **Quick Start** — 3 paths: `git clone` + pipx, Claude Code plugin, VS Code/Obsidian plugin (per ADR-437/438)
6. **What can I build** — 5-6 concrete examples from skills (knowledge management, career tracking, health, finance, home automation, content creation)
7. **Architecture** — diagram showing `.claude/skills/` as source of truth, multi-client mastering via `x-augur-master`, MCP server, CLI, dashboard
8. **CLI** — `aug` command examples (reuse from current README, they're good)
9. **Contributing** — one paragraph + link to CONTRIBUTING.md
10. **License** — `MIT License. See LICENSE.`
11. **Sponsored by Guriqo** — badge + one sentence

Key: Architecture diagram must reflect that skills live where `x-augur-master` says (`.claude/`, `.cursor/`, `.gemini/`, `.codex/`), not exclusively in `.claude/skills/`.

- [ ] **Step 2: Verify all links in README resolve**

Check that all internal links (`LICENSE`, `CONTRIBUTING.md`, `docs/` files) and badge URLs are correct.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "feat: rewrite README for public open-source audience

Complete rewrite targeting developers and life-hackers.
Updated architecture diagram reflecting multi-client skill mastering.
Hero and demo sections TBD (separate brainstorming + manual recording)."
```

---

### Task 7: Update Community Files

**Files:**
- Modify: `CONTRIBUTING.md`
- Modify: `SECURITY.md`
- Modify: `CHANGELOG.md`
- Modify: `.github/FUNDING.yml`

- [ ] **Step 1: Update CONTRIBUTING.md**

Already partially updated in Task 2 (license terms). Now update:
- All GitHub URLs to `augur-os/augur-os`
- Project structure section to reflect `.claude/skills/` (not `plugins/`)
- Add note about `sync-upstream.yml` being available for fork maintainers to copy
- Keep existing sections: getting started, development setup, creating skills, style guidelines, testing

- [ ] **Step 2: Update SECURITY.md**

- Update email address for vulnerability reports to match new org
- Update version support table
- Update any GitHub URLs

- [ ] **Step 3: Reset CHANGELOG.md**

Replace content with:

```markdown
# Changelog

All notable changes to Augur OS will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-XX-XX

### Initial Public Release

- 132 skills across 13 hubs
- Next.js dashboard at localhost:3000
- MCP server for AI agent integration
- CLI (`aug`) for scriptable access
- Multi-client skill mastering (Claude Code, Cursor, VS Code, Obsidian, Gemini, Codex)
- MIT License
```

Date TBD — filled in at actual launch.

- [ ] **Step 4: Update FUNDING.yml**

Keep `github: [gsannikov]` with a comment:

```yaml
# Maintainer's personal GitHub Sponsors page
# Will be updated to augur-os org sponsors when set up
github: [gsannikov]
```

- [ ] **Step 5: Commit**

```bash
git add CONTRIBUTING.md SECURITY.md CHANGELOG.md .github/FUNDING.yml
git commit -m "feat: update community files for open source launch

Update GitHub URLs, license terms, project structure references.
Reset CHANGELOG for v1.0.0 public release.
Update SECURITY.md contact info."
```

---

### Task 8: Config Templates

**Files:**
- Create: `.claude/settings.json.example`
- Create: `.claude/mcp.json.example`

- [ ] **Step 1: Create settings.json.example**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "_comment": "Copy this file to settings.json and adjust paths for your system",
  "permissions": {
    "allow": [
      "Bash(npm run *)",
      "Bash(python *)",
      "Bash(pytest *)",
      "Bash(git *)"
    ]
  }
}
```

- [ ] **Step 2: Create mcp.json.example**

```json
{
  "_comment": "Copy this file to mcp.json. Replace /path/to/augur with your actual install path.",
  "mcpServers": {
    "augur": {
      "command": "python",
      "args": ["-m", "augur_mcp"],
      "cwd": "/path/to/augur/src/mcp",
      "env": {
        "PYTHONPATH": "/path/to/augur:/path/to/augur/src/mcp"
      }
    }
  }
}
```

- [ ] **Step 3: Commit**

```bash
git add .claude/settings.json.example .claude/mcp.json.example
git commit -m "feat: add Claude Code config templates for new users

Ship .claude/settings.json.example and .claude/mcp.json.example
with sensible defaults and placeholder paths."
```

---

### Task 9: Launch Docs

**Files:**
- Create: `docs/getting-started.md`
- Create: `docs/creating-skills.md`
- Create: `docs/architecture.md`

- [ ] **Step 1: Write getting-started.md**

Three install paths (per ADR-437/438):

1. **Git Clone (recommended for developers)**:
   ```bash
   git clone https://github.com/augur-os/augur-os.git
   cd augur-os
   pipx install -e .
   aug discover
   ```

2. **Claude Code Plugin**: Install from dist/plugins, run `/onboard`

3. **VS Code / Obsidian**: Install platform plugin, click Install button

Include post-install: run dashboard (`npm run dashboard:dev`), explore CLI (`aug --list-tools`), create your first skill.

- [ ] **Step 2: Write creating-skills.md**

How to create a skill:
1. Directory structure (`.claude/skills/my-skill/SKILL.md`)
2. SKILL.md frontmatter format
3. Adding MCP tools (`scripts/mcp/`)
4. Adding dashboard pages (`augur/dashboard/`)
5. Testing your skill
6. Submitting as a PR

Reference existing skills as examples.

- [ ] **Step 3: Write architecture.md**

Public-facing architecture doc:
- Skills as the unit of composition
- Multi-client mastering (`x-augur-master` determines which IDE client owns a skill)
- MCP server as the API layer
- Dashboard as the visual surface
- CLI as the scriptable surface
- Vault as user data (external, private)
- ADR-270 data separation principle

- [ ] **Step 4: Commit**

```bash
git add docs/getting-started.md docs/creating-skills.md docs/architecture.md
git commit -m "docs: add getting-started, creating-skills, and architecture guides

Public-facing documentation for new users and contributors.
Covers installation, skill creation, and system architecture."
```

---

## Phase 1 Checkpoint

**Before proceeding to Phase 2, verify:**

- [ ] `npm run build` passes in `apps/dashboard/`
- [ ] `pytest tests/ -x` passes (or document known failures unrelated to launch changes)
- [ ] `grep -r "gsannikov\|augur-ai\|augur-project\|Danit\|Elastic-2.0" . --exclude-dir=.git --exclude-dir=node_modules --exclude=FUNDING.yml` returns zero hits. **Intentional exceptions**: `FUNDING.yml` (maintainer's GitHub Sponsors handle, kept with comment), your name as maintainer in LICENSE/CONTRIBUTING
- [ ] All CI workflow YAML files parse without errors
- [ ] No personal data in any tracked file (final manual review)

**STOP HERE. Get maintainer sign-off before Phase 2.**

---

## Phase 2: Repo Setup

### Task 10: Create GitHub Org and Repo

**MANUAL action required for Step 1. All other steps automated.**

- [ ] **Step 1: MANUAL — Create GitHub org `augur-os`**

1. Go to https://github.com/organizations/plan
2. Create organization named `augur-os`
3. Set org display name to "Augur OS"
4. Add a brief description: "Local-first personal AI OS"

**Tell the agent when this is done.**

- [ ] **Step 2: Create the repo via gh CLI**

```bash
gh repo create augur-os/augur-os --public --description "Local-first personal AI OS. 132 skills. Any AI agent. Your machine." --license MIT
```

- [ ] **Step 3: Prepare fresh git history**

From the current (fully scrubbed) working directory:

```bash
# Create a clean copy without .git
TEMP_DIR=$(mktemp -d)
rsync -a --exclude='.git' --exclude='node_modules' --exclude='.next' --exclude='__pycache__' --exclude='.claude/settings.json' --exclude='.claude/settings.local.json' --exclude='.claude/mcp.json' --exclude='.claude/worktrees' --exclude='.env' --exclude='.env.*' . "$TEMP_DIR/"

# Initialize fresh repo
cd "$TEMP_DIR"
git init
git add -A
git commit -m "Initial commit: Augur OS v1.0.0

Local-first personal AI OS with 132 skills across 13 hubs.
MIT License.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"

# Push to new repo
git remote add origin git@github.com:augur-os/augur-os.git
git branch -M main
git push -u origin main
```

- [ ] **Step 4: Verify push succeeded**

```bash
gh repo view augur-os/augur-os --json name,description,licenseInfo,isPrivate
```

Expected: public repo, MIT license, correct description.

---

### Task 11: Configure Branch Protection and Discussions

- [ ] **Step 1: Configure branch protection on main**

```bash
gh api repos/augur-os/augur-os/branches/main/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":["lint","test","security"]}' \
  --field enforce_admins=false \
  --field required_pull_request_reviews='{"required_approving_review_count":1}' \
  --field restrictions=null
```

Note: `enforce_admins=false` means the maintainer bypasses all protection rules on direct push. If the maintainer opens a PR (instead of pushing directly), the review requirement will still trigger — this is expected and acceptable.

- [ ] **Step 2: Enable GitHub Discussions**

```bash
gh repo edit augur-os/augur-os --enable-discussions
```

Then create categories via Chrome MCP or `gh api`:
- Announcements (announcement type)
- Q&A (question type)
- Show and Tell (open-ended)
- Ideas (open-ended)

- [ ] **Step 3: Commit PR automation workflows**

Create and push these workflow files to the public repo:

`.github/workflows/auto-label.yml` — labels PRs by size and area
`.github/workflows/auto-assign.yml` — assigns maintainer as reviewer when CI passes
`.github/workflows/stale.yml` — closes inactive PRs after 30 days

```bash
git add .github/workflows/auto-label.yml .github/workflows/auto-assign.yml .github/workflows/stale.yml
git push origin main
```

- [ ] **Step 4: Verify branch protection works**

```bash
gh api repos/augur-os/augur-os/branches/main/protection
```

Expected: Shows required status checks for lint, test, security.

---

## Phase 2 Checkpoint

- [ ] `augur-os/augur-os` repo is public and accessible
- [ ] Branch protection requires PR + CI for non-maintainers
- [ ] GitHub Discussions enabled with 4 categories
- [ ] Auto-label and stale bot workflows committed
- [ ] Fresh initial commit with full scrubbed codebase

**STOP HERE. Get maintainer sign-off before sharing with soft launch group.**

---

## Phase 3: Soft Launch (Manual Process)

### Task 12: Soft Launch Execution

- [ ] **Step 1: Identify 5-10 soft launch users**

MANUAL: Select trusted developers/life-hackers who will provide honest feedback.

- [ ] **Step 2: Share repo URL**

Send `https://github.com/augur-os/augur-os` with a request to:
1. Clone and follow `docs/getting-started.md`
2. Report any friction, confusion, or errors
3. Note what's missing or unclear

- [ ] **Step 3: Collect and triage feedback (2-3 weeks)**

Create GitHub Issues for each piece of feedback. Label with `soft-launch-feedback`.

- [ ] **Step 4: Fix critical issues**

Address showstoppers before public announcement.

---

## Phase 4: Announcement (Manual Process)

### Task 13: Public Announcement

- [ ] **Step 1: Finalize hero/positioning**

Separate brainstorming session, informed by soft launch feedback. Rooted in 5 pillars: Trust, Freedom, Pace, Complexity, Future Proof.

Update README hero section.

- [ ] **Step 2: Record demo GIF/screenshot**

MANUAL: Record dashboard and CLI in action for README.

- [ ] **Step 3: LinkedIn post**

Use `linkedin-writer` skill to draft and publish announcement.

- [ ] **Step 4: Create first GitHub Discussion (Announcement)**

Post a "Welcome to Augur OS" announcement with:
- What this project is
- How to get started
- Where to ask questions
- What contributions are welcome

- [ ] **Step 5: (Later) Hacker News Show HN**

When there's initial traction and a few community contributions to point to.
