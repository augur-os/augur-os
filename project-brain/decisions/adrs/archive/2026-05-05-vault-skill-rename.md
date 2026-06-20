# Vault Skill Rename Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the `obsidian` vault-tier skill to `vault` everywhere it appears (vault bundle, MCP server, registry, onboarding, dashboard, 14+ tests), and rename all 7 MCP tools to the `vault-*` prefix. Frees the `obsidian` namespace for the kepano integration that follows in Plan B.

**Architecture:** Mechanical rename across two repos (Augur project + Au-vault user repo). `skill_registry.py` is already dynamic — once the bundle directory moves, registry auto-discovers `vault`. Hardcoded references live in mcp_servers.yaml, the architecture test's `VAULT_SKILL_NAMES`, onboarding platform metadata, and 14 test files. The dashboard route changes from `/brain/obsidian/vault` → `/brain/vault`.

**Tech Stack:** Python 3.11+, pytest, YAML config, MCP server bundles, Augur sync_agents, Next.js dashboard.

**Spec:** `docs/superpowers/specs/2026-05-05-vault-skill-rename-and-kepano-obsidian-integration-design.md`

**Out of scope (Plan B):** Vendoring kepano/obsidian-skills, distributing to clients, slimming the renamed skill body, adding cross-references.

**Environment:** Commands that change directories use `$AUGUR_REPO` for the active Augur worktree path. Export it before starting (e.g., `export AUGUR_REPO=$(pwd)` from the worktree root). The vault repo is always at `~/Projects/Au-vault`.

---

## File Structure

**Modified files (Augur repo):**
- `config/system/mcp_servers.yaml` — server `augur-obsidian` → `augur-vault`, 7 tools renamed, `monolith_exclusions` list
- `tests/architecture/test_no_vault_skill_refs.py` — `VAULT_SKILL_NAMES` list
- `skills/onboard/augur/data/platforms.yaml` — platform key + setup_tool
- `skills/onboard/SKILL.md` — `--connect <platform>` doc
- `skills/onboard/references/mode-connect.md` — `--connect`/`--from` references
- `skills/rag/assets/seeds/quality_baseline.yaml` — quality probe text

**Renamed files (Augur repo):**
- `tests/cli/test_bundle_server_obsidian.py` → `tests/cli/test_bundle_server_vault.py`
- `skills/ai/augur/tests/test_obsidian.py` → `skills/ai/augur/tests/test_vault.py`

**Test fixture updates (Augur repo):**
- `tests/test_onboard_state.py`
- `tests/mcp/test_hub_vault_notes.py`
- `tests/mcp/test_hub_recent.py`
- `tests/mcp/test_shared_config_paths.py`
- `tests/dashboard/visual/brain-runtime-smoke.spec.ts`
- `tests/dashboard/scripts/generate-block-registry.test.ts`
- `tests/dashboard/surfaces/classifySurface.test.ts`
- `tests/dashboard/surfaces/buildSurfaceInventory.test.ts`
- `tests/scripts/test_install_flags.py`
- `tests/scripts/test_platform_plugins.py`
- `tests/packages/augur-mcp/tools/test_dynamic_plugin_loader.py`
- `tests/packages/augur-mcp/infrastructure/test_browse_vault_integrations.py`
- `tests/src/test_paths.py`

**Renamed files (Au-vault repo, separate git):**
- `~/Projects/Au-vault/skills/obsidian/` → `~/Projects/Au-vault/skills/vault/` (entire directory)
- Inside it: `SKILL.md` frontmatter `name: obsidian` → `name: vault`; dashboard tile id/path

**Files that intentionally do NOT change (architecture test allowlist already documents this):**
- `src/mcp/augur_framework/tools/infrastructure/browse/cli.py` — `skill == "obsidian"` is a `.obsidian/` directory probe (the literal directory name on disk), not a skill name. Stays.
- `skills/ai/scripts/markdown_flavors.py` — `plain_to_obsidian`, `obsidian_to_plain` are flavor names, not skill names. Stays.
- `skills/ai/scripts/sync_agents/vault_adapters/obsidian.py` — adapter named after the markdown flavor it handles. Stays.
- `tests/scripts/test_check_obsidian_vault_roots.py` — tests vault-root layout (inbox, notes, sources…), not the skill. Stays.
- `plugins/obsidian/` — TypeScript Obsidian plugin (separate codebase). Stays.

---

## Task 1: Pre-flight audit

**Files:** none yet. Discovery only.

- [ ] **Step 1: Confirm worktree is clean and on the right branch**

```bash
git status
git branch --show-current
```

Expected: `clean`, branch is the active feature/worktree branch (not `main`).

- [ ] **Step 2: Run a comprehensive grep for `obsidian` references in scope**

```bash
cd "$AUGUR_REPO"
grep -rln "obsidian" \
  config/ skills/ src/ tests/ apps/dashboard/ \
  --include="*.py" --include="*.yaml" --include="*.yml" --include="*.json" \
  --include="*.md" --include="*.ts" --include="*.tsx" \
  2>/dev/null \
  | grep -v node_modules | grep -v "/.git/" \
  | grep -v ".gemini/skills" | grep -v ".opencode/skills" \
  > /tmp/obsidian-refs.txt
wc -l /tmp/obsidian-refs.txt
```

Expected: a file list. Save the count for comparison after completion.

- [ ] **Step 3: Run a comprehensive grep for the bundle path**

```bash
grep -rn "Au-vault/skills/obsidian" config/ skills/ src/ tests/ 2>/dev/null \
  | grep -v "/.git/"
```

Expected: at minimum `config/system/mcp_servers.yaml` and `tests/cli/test_bundle_server_obsidian.py` should appear.

- [ ] **Step 4: Confirm Au-vault repo is on a clean state**

```bash
cd ~/Projects/Au-vault
git status
git branch --show-current
cd -
```

Expected: clean working tree. If not, stop and ask the user — uncommitted vault changes need to be committed first to avoid mixing concerns.

- [ ] **Step 5: Snapshot the current architecture test pass state**

```bash
cd "$AUGUR_REPO"
uv run pytest tests/architecture/test_no_vault_skill_refs.py -v
```

Expected: PASS. This is the baseline. Every step that could affect this test must keep it passing or fix it as part of the same task.

---

## Task 2: Rename the Au-vault bundle directory

**Files:**
- Rename: `~/Projects/Au-vault/skills/obsidian/` → `~/Projects/Au-vault/skills/vault/`
- Modify: `~/Projects/Au-vault/skills/vault/SKILL.md`

- [ ] **Step 1: Rename the bundle directory in the vault repo**

```bash
cd ~/Projects/Au-vault
git mv skills/obsidian skills/vault
git status
```

Expected: All files under `skills/obsidian/` show as renamed to `skills/vault/`.

- [ ] **Step 2: Update SKILL.md `name` field**

Edit `~/Projects/Au-vault/skills/vault/SKILL.md`. Change frontmatter line:

```yaml
name: obsidian
```

To:

```yaml
name: vault
```

- [ ] **Step 3: Update SKILL.md dashboard tile id and route**

In the same file, update the `x-augur-config` block. Find:

```yaml
x-augur-config:
  contributions:
    pages:
    - id: obsidian
      title: Obsidian Vault
```

Replace with:

```yaml
x-augur-config:
  contributions:
    pages:
    - id: vault
      title: Vault
```

Also update `x-augur-dashboard-pages`:

```yaml
x-augur-dashboard-pages:
- /brain/obsidian/vault
```

Change to:

```yaml
x-augur-dashboard-pages:
- /brain/vault
```

- [ ] **Step 4: Commit the vault repo changes**

```bash
cd ~/Projects/Au-vault
git add skills/vault
git commit -m "rename(skills): obsidian → vault

Match x-augur-integration-type. Frees the 'obsidian' name for
upstream kepano/obsidian-skills reference content (Plan B).

Refs: docs/superpowers/specs/2026-05-05-vault-skill-rename-and-kepano-obsidian-integration-design.md (in Augur repo)"
cd -
```

Expected: clean commit in vault repo. Don't push yet — coordinated with the Augur repo work.

---

## Task 3: Update the architecture test's VAULT_SKILL_NAMES

**Files:**
- Modify: `tests/architecture/test_no_vault_skill_refs.py`

- [ ] **Step 1: Run the architecture test — expect failure after Task 2**

```bash
cd "$AUGUR_REPO"
uv run pytest tests/architecture/test_no_vault_skill_refs.py -v
```

Expected: FAIL — the test still pins `obsidian` in `VAULT_SKILL_NAMES`, but the registry now sees `vault` as the vault-tier skill (because the bundle moved). The test will report unexpected literal `vault` references in `src/`, OR it will pass if its check is "names that should NOT appear in src/" and `obsidian` no longer appears anywhere except the allowlisted files. **Read the failure carefully** — its semantics are about *forbidden* literals, not *required* ones.

- [ ] **Step 2: Update VAULT_SKILL_NAMES**

In `tests/architecture/test_no_vault_skill_refs.py`, find:

```python
VAULT_SKILL_NAMES = ["apple", "lifestyle", "file-manager", "obsidian", "ingest"]
```

Replace with:

```python
VAULT_SKILL_NAMES = ["apple", "lifestyle", "file-manager", "vault", "ingest"]
```

- [ ] **Step 3: Re-run the architecture test**

```bash
uv run pytest tests/architecture/test_no_vault_skill_refs.py -v
```

Expected: it now flags references to `vault` (and possibly `obsidian` still in remaining tasks' files). This is the goal — drives the rest of the rename. Note any flagged files for upcoming tasks.

- [ ] **Step 4: Commit**

```bash
git add tests/architecture/test_no_vault_skill_refs.py
git commit -m "test(architecture): rename obsidian → vault in VAULT_SKILL_NAMES"
```

---

## Task 4: Update mcp_servers.yaml

**Files:**
- Modify: `config/system/mcp_servers.yaml:75-100`

- [ ] **Step 1: Find the augur-obsidian server definition**

```bash
grep -n "augur-obsidian\|bundle: obsidian\|monolith_exclusions" config/system/mcp_servers.yaml
```

Expected: ~5 lines around 75 and ~1 line near 100 (in `monolith_exclusions`).

- [ ] **Step 2: Update the server block**

In `config/system/mcp_servers.yaml`, find:

```yaml
  - id: augur-obsidian
    description: Obsidian vault integration (notes / metadata / search)
    command: python
    args: [-m, augur_shared.bundle_server, obsidian]
    bundle: obsidian
    bundle_path: ~/Projects/Au-vault/skills/obsidian
```

Replace with:

```yaml
  - id: augur-vault
    description: Augur vault integration (notes / metadata / search)
    command: python
    args: [-m, augur_shared.bundle_server, vault]
    bundle: vault
    bundle_path: ~/Projects/Au-vault/skills/vault
```

- [ ] **Step 3: Update monolith_exclusions**

Find:

```yaml
monolith_exclusions:
  - apple
  - lifestyle
  - file-manager
  - obsidian
  - ingest
```

Replace with:

```yaml
monolith_exclusions:
  - apple
  - lifestyle
  - file-manager
  - vault
  - ingest
```

- [ ] **Step 4: Update tool names if they're declared in this file**

Run:

```bash
grep -n "obsidian-read\|obsidian-write\|obsidian-search\|obsidian-status\|obsidian-health-repairs\|obsidian-scaffold\|obsidian-convert" config/system/mcp_servers.yaml
```

If any matches, replace each `obsidian-*` tool name with `vault-*`. (If no matches, tools are auto-discovered from the bundle and need no edit here — proceed.)

- [ ] **Step 5: Verify yaml is still valid**

```bash
python3 -c "import yaml; yaml.safe_load(open('config/system/mcp_servers.yaml'))" && echo OK
```

Expected: `OK`.

- [ ] **Step 6: Commit**

```bash
git add config/system/mcp_servers.yaml
git commit -m "config(mcp): rename augur-obsidian server → augur-vault"
```

---

## Task 5: Update bundle MCP tool registrations in the vault skill

**Files:**
- Modify: `~/Projects/Au-vault/skills/vault/augur/` (Python tool registration files — exact paths discovered in step below)

- [ ] **Step 1: Locate tool registration code**

```bash
grep -rln "obsidian-read\|obsidian-write\|obsidian-search\|obsidian-status\|obsidian-health-repairs\|obsidian-scaffold\|obsidian-convert" ~/Projects/Au-vault/skills/vault/ 2>/dev/null
```

Expected: at least one Python file under `augur/` defining the tools. Note paths.

- [ ] **Step 2: Rename each tool string in production code**

For each file from Step 1, replace the seven tool names:

| Old | New |
|---|---|
| `obsidian-read` | `vault-read` |
| `obsidian-write` | `vault-write` |
| `obsidian-search` | `vault-search` |
| `obsidian-status` | `vault-status` |
| `obsidian-health-repairs` | `vault-health-repairs` |
| `obsidian-scaffold` | `vault-scaffold` |
| `obsidian-convert` | `vault-convert` |

A safe sed-driven approach (run from the vault dir, after a clean commit so it's revertable):

```bash
cd ~/Projects/Au-vault/skills/vault
for old_new in \
  "obsidian-read:vault-read" \
  "obsidian-write:vault-write" \
  "obsidian-search:vault-search" \
  "obsidian-status:vault-status" \
  "obsidian-health-repairs:vault-health-repairs" \
  "obsidian-scaffold:vault-scaffold" \
  "obsidian-convert:vault-convert"; do
  old="${old_new%%:*}"
  new="${old_new##*:}"
  grep -rl "$old" . | xargs -I {} sed -i.bak "s/${old}/${new}/g" {}
done
find . -name "*.bak" -delete
git diff --stat
cd -
```

Expected: the diff stat shows the rename across the affected files. Inspect with `git diff` to verify only tool-name strings changed.

- [ ] **Step 3: Smoke-test the bundle server**

```bash
cd "$AUGUR_REPO"
PYTHONPATH="$(pwd):$(pwd)/src/mcp" \
  python -m augur_shared.bundle_server vault \
  </dev/null 2>&1 | head -30
```

Expected: server starts, prints tool registry that includes the seven `vault-*` tools (no `obsidian-*` tools). Kill with Ctrl-C if it hangs (server runs until EOF).

- [ ] **Step 4: Commit (vault repo)**

```bash
cd ~/Projects/Au-vault
git add skills/vault
git commit -m "rename(skills/vault): MCP tools obsidian-* → vault-*"
cd -
```

---

## Task 6: Update bundle server test

**Files:**
- Rename: `tests/cli/test_bundle_server_obsidian.py` → `tests/cli/test_bundle_server_vault.py`
- Modify: contents of the renamed file

- [ ] **Step 1: Rename the test file**

```bash
git mv tests/cli/test_bundle_server_obsidian.py tests/cli/test_bundle_server_vault.py
```

- [ ] **Step 2: Update the file's contents**

Edit `tests/cli/test_bundle_server_vault.py`. Replace:

```python
OBSIDIAN_BUNDLE = Path.home() / "Projects" / "Au-vault" / "skills" / "obsidian"


@pytest.mark.skipif(not OBSIDIAN_BUNDLE.exists(), reason="Au-vault obsidian bundle not present")
def test_obsidian_per_bundle_server_starts_and_lists_tools() -> None:
```

With:

```python
VAULT_BUNDLE = Path.home() / "Projects" / "Au-vault" / "skills" / "vault"


@pytest.mark.skipif(not VAULT_BUNDLE.exists(), reason="Au-vault vault bundle not present")
def test_vault_per_bundle_server_starts_and_lists_tools() -> None:
```

Also update the `bundle_server` argv:

```python
[sys.executable, "-m", "augur_shared.bundle_server", "obsidian"],
```

To:

```python
[sys.executable, "-m", "augur_shared.bundle_server", "vault"],
```

If the test asserts on tool names, update the expected list to include the seven `vault-*` tools.

- [ ] **Step 3: Run the test**

```bash
uv run pytest tests/cli/test_bundle_server_vault.py -v
```

Expected: PASS (or `SKIPPED` if the vault bundle dir is unreachable from this checkout — that's acceptable; verify the skip reason names "vault bundle").

- [ ] **Step 4: Commit**

```bash
git add tests/cli/test_bundle_server_vault.py
git commit -m "test(cli): rename test_bundle_server_obsidian → vault"
```

---

## Task 7: Update onboard platform metadata

**Files:**
- Modify: `skills/onboard/augur/data/platforms.yaml`
- Modify: `skills/onboard/SKILL.md`
- Modify: `skills/onboard/references/mode-connect.md`
- Modify: `tests/test_onboard_state.py`

- [ ] **Step 1: Update platforms.yaml**

Edit `skills/onboard/augur/data/platforms.yaml`. Find:

```yaml
  obsidian:
    detection: "obsidian vault configured"
    setup_tool: "obsidian-scaffold"
    getting_started: >
      Augur is installed and your vault is configured. Open Obsidian
      and look for the Augur vault. The dashboard is at localhost:3000.
```

Replace with:

```yaml
  vault:
    detection: "vault configured"
    setup_tool: "vault-scaffold"
    getting_started: >
      Augur is installed and your vault is configured. The dashboard
      is at localhost:3000. To browse the vault in Obsidian, run
      vault-scaffold to add .obsidian/ config.
```

- [ ] **Step 2: Update onboard SKILL.md**

In `skills/onboard/SKILL.md`, find the `--connect <platform>` row that lists `obsidian` and replace `obsidian` with `vault`:

```bash
grep -n "obsidian" skills/onboard/SKILL.md
```

For each match, edit the line. The likely targets are the `--connect <platform>` documentation row and any prose mentioning `obsidian` as a platform name.

- [ ] **Step 3: Update mode-connect.md**

In `skills/onboard/references/mode-connect.md`, replace:
- `--connect obsidian` → `--connect vault` (every occurrence)
- `--from obsidian` → `--from vault` (every occurrence)
- The narrative section "From Obsidian (`--from obsidian`)" — rename to "From vault (`--from vault`)"
- The "obsidian: Run obsidian-scaffold MCP tool to create .obsidian/ config in vault" line → "vault: Run vault-scaffold MCP tool to create .obsidian/ config in vault"

- [ ] **Step 4: Update test_onboard_state.py**

In `tests/test_onboard_state.py`, find:

```python
state = _mod.write_state(install_source="obsidian", configured_clients=["obsidian"])
...
assert data["install_source"] == "obsidian"
assert data["configured_clients"] == ["obsidian"]
```

Replace each `"obsidian"` with `"vault"`.

- [ ] **Step 5: Run onboard tests**

```bash
uv run pytest tests/test_onboard_state.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add skills/onboard/augur/data/platforms.yaml skills/onboard/SKILL.md \
  skills/onboard/references/mode-connect.md tests/test_onboard_state.py
git commit -m "feat(onboard): rename platform obsidian → vault"
```

---

## Task 8: Update remaining test fixtures

**Files:**
- Modify: `tests/scripts/test_install_flags.py`
- Modify: `tests/scripts/test_platform_plugins.py`
- Modify: `tests/mcp/test_hub_vault_notes.py`
- Modify: `tests/mcp/test_hub_recent.py`
- Modify: `tests/mcp/test_shared_config_paths.py`
- Modify: `tests/dashboard/visual/brain-runtime-smoke.spec.ts`
- Modify: `tests/dashboard/scripts/generate-block-registry.test.ts`
- Modify: `tests/dashboard/surfaces/classifySurface.test.ts`
- Modify: `tests/dashboard/surfaces/buildSurfaceInventory.test.ts`
- Modify: `tests/packages/augur-mcp/tools/test_dynamic_plugin_loader.py`
- Modify: `tests/packages/augur-mcp/infrastructure/test_browse_vault_integrations.py`
- Modify: `tests/src/test_paths.py`
- Rename and modify: `skills/ai/augur/tests/test_obsidian.py` → `test_vault.py`

- [ ] **Step 1: Run the affected suites first to capture the baseline**

```bash
uv run pytest \
  tests/scripts/test_install_flags.py \
  tests/scripts/test_platform_plugins.py \
  tests/mcp/test_hub_vault_notes.py \
  tests/mcp/test_hub_recent.py \
  tests/mcp/test_shared_config_paths.py \
  tests/packages/augur-mcp/tools/test_dynamic_plugin_loader.py \
  tests/packages/augur-mcp/infrastructure/test_browse_vault_integrations.py \
  tests/src/test_paths.py \
  -v 2>&1 | tail -30
```

Expected: most should now FAIL with reference to old `obsidian` paths or expectations. **Save the failure list** — that's the precise rename target.

- [ ] **Step 2: For each failing test, replace the obsidian skill name with vault**

The pattern is mechanical: in test fixtures and assertions, `"obsidian"` (referring to the skill or bundle path) → `"vault"`. Note: do NOT replace strings referring to `.obsidian/` directory probes, Obsidian app, or Obsidian-flavored markdown — those literal usages are correct.

For each file, run:

```bash
grep -n "obsidian" <file>
```

Inspect each match. Categorize:
- **Skill/bundle name** → replace with `vault`
- **`.obsidian/` directory probe / Obsidian app / Obsidian flavor** → keep

Apply edits one file at a time, then run that test.

- [ ] **Step 3: Rename and update test_obsidian.py**

```bash
git mv skills/ai/augur/tests/test_obsidian.py skills/ai/augur/tests/test_vault.py
grep -n "obsidian" skills/ai/augur/tests/test_vault.py
```

For each match: same triage — skill/bundle name → `vault`; flavor name → keep.

If the test imports a function `test_obsidian_*` or has a class `TestObsidian`, rename to `test_vault_*` / `TestVault`.

- [ ] **Step 4: Update TypeScript dashboard tests**

For each of:
- `tests/dashboard/visual/brain-runtime-smoke.spec.ts`
- `tests/dashboard/scripts/generate-block-registry.test.ts`
- `tests/dashboard/surfaces/classifySurface.test.ts`
- `tests/dashboard/surfaces/buildSurfaceInventory.test.ts`

Run `grep -n obsidian <file>` and apply the same triage. Dashboard fixtures likely contain skill name strings or route paths (`/brain/obsidian/vault`) that need updating to `/brain/vault`.

- [ ] **Step 5: Run all updated tests**

```bash
uv run pytest \
  tests/scripts/test_install_flags.py \
  tests/scripts/test_platform_plugins.py \
  tests/mcp/test_hub_vault_notes.py \
  tests/mcp/test_hub_recent.py \
  tests/mcp/test_shared_config_paths.py \
  tests/packages/augur-mcp/tools/test_dynamic_plugin_loader.py \
  tests/packages/augur-mcp/infrastructure/test_browse_vault_integrations.py \
  tests/src/test_paths.py \
  skills/ai/augur/tests/test_vault.py \
  -v
```

Expected: all PASS.

```bash
pnpm --filter dashboard test -- \
  tests/dashboard/scripts/generate-block-registry.test.ts \
  tests/dashboard/surfaces/classifySurface.test.ts \
  tests/dashboard/surfaces/buildSurfaceInventory.test.ts
```

Expected: all PASS. (Visual smoke test runs separately in Task 10.)

- [ ] **Step 6: Commit**

```bash
git add tests/ skills/ai/augur/tests/
git commit -m "test: rename obsidian skill references → vault"
```

---

## Task 9: Update RAG quality baseline

**Files:**
- Modify: `skills/rag/assets/seeds/quality_baseline.yaml`

- [ ] **Step 1: Locate the obsidian probe**

```bash
grep -B 1 -A 5 "obsidian vault integration" skills/rag/assets/seeds/quality_baseline.yaml
```

Expected: one entry with query `"obsidian vault integration"` and expected keywords list.

- [ ] **Step 2: Update the probe**

Edit the file. Find:

```yaml
  - query: "obsidian vault integration"
    expected:
      - "obsidian"
```

Replace with:

```yaml
  - query: "augur vault integration"
    expected:
      - "vault"
```

(The probe tests that the RAG layer surfaces vault-related skills for a relevant query. The keyword `vault` matches the renamed skill.)

- [ ] **Step 3: Run the RAG seed test if one exists**

```bash
uv run pytest -k "quality_baseline or rag_seed" -v 2>&1 | tail -20
```

Expected: PASS, or "no tests collected" if no harness covers this directly.

- [ ] **Step 4: Commit**

```bash
git add skills/rag/assets/seeds/quality_baseline.yaml
git commit -m "test(rag): update quality baseline probe obsidian → vault"
```

---

## Task 10: Update dashboard route and verify generated registries

**Files:**
- Verify: `apps/dashboard/app/brain/` (auto-generated; check after Au-vault rename)
- Regenerate: `docs/generated/skill-manifest.json`, `launch-skill-inventory.json`, `skill-release-matrix.json`

- [ ] **Step 1: Sync the renamed skill into the Augur project**

The `.opencode/skills/`, `.gemini/skills/`, and dashboard surfaces are generated from the vault skill bundle. Trigger the regenerate:

```bash
uv run python -m skills.ai.scripts.sync_agents.cli sync agents all
```

Expected: a flurry of generated files appear/move. `git status` should show:
- `.opencode/skills/obsidian/` deleted, `.opencode/skills/vault/` added
- `.gemini/skills/obsidian/` deleted, `.gemini/skills/vault/` added (or just regenerated under new name; this dir is gitignored)
- `apps/dashboard/app/brain/obsidian/` removed, `apps/dashboard/app/brain/vault/` added

- [ ] **Step 2: Regenerate skill registries**

```bash
uv run python .github/scripts/generate_skill_registry.py
```

Expected: updated `docs/generated/skill-registry.md`.

- [ ] **Step 3: Regenerate skill manifest, launch inventory, release matrix**

```bash
uv run python scripts/write_skill_group_release.py
```

(Or whichever script generates these — verify the actual generator name first by `head` on each generated JSON file's leading comment.)

```bash
head -3 docs/generated/skill-manifest.json
head -3 docs/generated/launch-skill-inventory.json
head -3 docs/generated/skill-release-matrix.json
```

Confirm each file references `vault`, not `obsidian`:

```bash
grep -c '"vault"' docs/generated/skill-manifest.json
grep -c '"obsidian"' docs/generated/skill-manifest.json
```

Expected: `"vault"` count > 0; `"obsidian"` count = 0 (or only in entries about Obsidian as a third-party app, not the skill).

- [ ] **Step 4: Run the dashboard build to catch any route or import drift**

```bash
/dev-build
```

(Slash command that wraps the dashboard rebuild safely per project rule 29.)

Expected: build succeeds. The new route `/brain/vault` exists.

- [ ] **Step 5: Visual smoke test**

```bash
pnpm --filter dashboard test:e2e -- tests/dashboard/visual/brain-runtime-smoke.spec.ts
```

Expected: PASS. Confirms the dashboard renders the new route without runtime errors.

- [ ] **Step 6: Commit generated artifacts**

```bash
git add .opencode/skills apps/dashboard/app/brain docs/generated/
git status
```

Verify nothing unexpected (e.g., unrelated changes); then:

```bash
git commit -m "chore: regenerate registries and dashboard surfaces for vault rename"
```

---

## Task 11: Final verification

- [ ] **Step 1: Re-run the architecture test**

```bash
uv run pytest tests/architecture/test_no_vault_skill_refs.py -v
```

Expected: PASS.

- [ ] **Step 2: Run the full Python test suite**

```bash
uv run pytest tests/ -x --tb=short 2>&1 | tail -40
```

Expected: PASS. If anything fails, the failure points to a missed reference. Triage and fix in a follow-up commit (do NOT skip the test or rewrite assertions to match wrong behavior — per project rule 5).

- [ ] **Step 3: Run the dashboard test suite**

```bash
pnpm --filter dashboard test 2>&1 | tail -20
```

Expected: PASS.

- [ ] **Step 4: Final reference grep — no stale `obsidian` skill name**

```bash
grep -rln '"obsidian"\|: obsidian\b\|obsidian-read\|obsidian-write\|obsidian-search\|obsidian-status\|obsidian-health-repairs\|obsidian-scaffold\|obsidian-convert\|augur-obsidian' \
  config/ skills/ src/ tests/ \
  --include="*.py" --include="*.yaml" --include="*.yml" --include="*.json" --include="*.md" \
  --include="*.ts" --include="*.tsx" \
  2>/dev/null \
  | grep -v node_modules | grep -v "/.git/" \
  | grep -v ".gemini/skills" | grep -v ".opencode/skills"
```

Expected: empty, or only matches in:
- `src/mcp/augur_framework/tools/infrastructure/browse/cli.py` (`.obsidian/` directory probe — keep)
- `skills/ai/scripts/markdown_flavors.py` (flavor names — keep)
- `skills/ai/scripts/sync_agents/vault_adapters/obsidian.py` (flavor adapter — keep)
- `tests/scripts/test_check_obsidian_vault_roots.py` (vault root layout — keep)
- `plugins/obsidian/**` (TS plugin — separate codebase)
- `docs/superpowers/specs/2026-05-05-vault-skill-rename-and-kepano-obsidian-integration-design.md` (the spec itself, references the rename)

Anything else is a missed rename — fix and recommit before declaring done.

- [ ] **Step 5: Push both repos**

```bash
cd ~/Projects/Au-vault
git push
cd "$AUGUR_REPO"
git push
```

- [ ] **Step 6: Mark Plan A complete**

```bash
git commit --allow-empty -m "docs(plan): vault skill rename complete

Implements Phase 1 of
docs/superpowers/specs/2026-05-05-vault-skill-rename-and-kepano-obsidian-integration-design.md

Plan B (kepano integration) follows."
```

---

## Self-Review Checklist (run before claiming done)

- [ ] All 14 listed test files updated (12 mandatory, 2 conditional verified).
- [ ] All 7 MCP tools renamed `obsidian-*` → `vault-*` in production code AND in tests.
- [ ] MCP server renamed `augur-obsidian` → `augur-vault` (both `id:` and `monolith_exclusions`).
- [ ] Vault bundle directory renamed in Au-vault repo (committed there).
- [ ] Architecture test (`test_no_vault_skill_refs.py`) passes with `vault` in `VAULT_SKILL_NAMES`.
- [ ] Onboarding `--connect vault` flow works end-to-end.
- [ ] Dashboard route `/brain/vault` renders.
- [ ] No stale `obsidian` skill-name strings in `config/`, `skills/`, `src/`, `tests/` (allowlist excepted).
- [ ] Generated registries refreshed.
- [ ] Both repos pushed.
