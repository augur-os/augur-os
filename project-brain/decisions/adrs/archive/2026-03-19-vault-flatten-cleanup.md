# Vault Flatten & Cleanup (ADR-454) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Flatten vault from `augur-{bundle}/{skill}/` to `{skill}/` at root, remove ~575 technical duplicate files, and update all code that constructs vault/documents/RAG paths.

**Architecture:** Centralized path functions (`src/config/paths.py` + `src/mcp/augur_mcp/config.py`) are the single point of change for most downstream code. Three files need explicit rewrites (vault hygiene, RAG scanner, MCP regex). A Python migration script handles the data move. Code changes deploy first, then vault migration runs.

**Tech Stack:** Python (paths, MCP, migration script), shell (vault file operations)

**Spec:** `docs/superpowers/specs/2026-03-19-vault-flatten-cleanup-design.md`

---

### Task 1: Update core path functions in `src/config/paths.py`

**Files:**
- Modify: `src/config/paths.py:391-427`
- Test: `tests/src/test_path_config.py`

- [ ] **Step 1: Update `get_skill_vault_dir()` to flat path**

Replace lines 391-397 in `src/config/paths.py`:

```python
# Replace the existing function with:
_RESERVED_VAULT_NAMES = {"config", "dev", "memory", ".git"}

def get_skill_vault_dir(skill_name: str) -> Path:
    if skill_name in _RESERVED_VAULT_NAMES:
        raise ValueError(f"'{skill_name}' is a reserved vault directory, not a skill")
    return get_vault_dir() / skill_name
```

- [ ] **Step 2: Update `get_skill_documents_dir()` to flat path**

Replace lines 404-410:

```python
def get_skill_documents_dir(skill_name: str) -> Path:
    if skill_name in _RESERVED_VAULT_NAMES:
        raise ValueError(f"'{skill_name}' is a reserved vault directory, not a skill")
    return get_documents_dir() / skill_name
```

- [ ] **Step 3: Update `get_skill_rag_dir()` to flat path**

Replace lines 417-423:

```python
def get_skill_rag_dir(skill_name: str) -> Path:
    return get_rag_dir() / skill_name
```

- [ ] **Step 4: Remove `get_bundle_rag_dir()`**

Delete lines 426-427 (`get_bundle_rag_dir` function). Grep for callers and remove/replace them:

```bash
grep -rn "get_bundle_rag_dir" src/ .claude/ --include="*.py" | grep -v __pycache__ | grep -v .venv
```

- [ ] **Step 5: Update tests in `tests/src/test_path_config.py`**

Read the test file, update any assertions that expect `vault/{bundle}/{skill}` to expect `vault/{skill}`. Same for documents and RAG paths.

- [ ] **Step 6: Update tests in `tests/src/test_paths.py`**

Read the file, update `get_skill_data_dir()` assertions to match the new flat vault structure.

- [ ] **Step 7: Run tests**

```bash
cd ~/Projects/Augur && python -m pytest tests/src/test_path_config.py tests/src/test_paths.py -v
```

- [ ] **Step 8: Commit**

```bash
git add src/config/paths.py tests/src/test_path_config.py tests/src/test_paths.py
git commit -m "fix(ADR-454): flatten vault path functions — remove bundle from vault/documents/RAG paths"
```

---

### Task 2: Rewrite MCP config path functions

**Files:**
- Modify: `src/mcp/augur_mcp/config.py:305-423`

- [ ] **Step 1: Rewrite `get_skill_data_dir()` in MCP config**

Replace lines 305-326 in `src/mcp/augur_mcp/config.py`. The function currently iterates bundles to find the skill, then constructs `vault / bundle / skill`. Simplify to:

```python
def get_skill_data_dir(skill: str) -> Path:
    """Get the vault directory for a specific skill."""
    return _get_vault_dir() / skill
```

- [ ] **Step 2: Rewrite `get_skill_documents_dir()` in MCP config**

Replace lines 362-381:

```python
def get_skill_documents_dir(skill: str) -> Path:
    return _get_documents_dir() / skill
```

- [ ] **Step 3: Rewrite `get_skill_rag_dir()` in MCP config**

Replace lines 400-419:

```python
def get_skill_rag_dir(skill: str) -> Path:
    return _get_rag_dir() / skill
```

- [ ] **Step 4: Remove `get_bundle_rag_dir()` from MCP config**

Delete lines 422-423.

- [ ] **Step 5: Run MCP tests**

```bash
cd ~/Projects/Augur && python -m pytest src/mcp/augur_mcp/tests/ -v -k "path or config" 2>/dev/null; echo "exit: $?"
```

- [ ] **Step 6: Commit**

```bash
git add src/mcp/augur_mcp/config.py
git commit -m "fix(ADR-454): rewrite MCP config path functions — flat vault paths"
```

---

### Task 3: Remove vault scanning from action loading

**Files:**
- Modify: `src/mcp/augur_mcp/infrastructure/actions.py:129-145`

- [ ] **Step 1: Remove vault source from `_collect_skill_action_files()`**

Replace lines 129-145. Remove the `get_skill_data_dir` import and vault source. Only scan plugin `assets/`:

```python
def _collect_skill_action_files(skill_dir: Path) -> list[Path]:
    """Collect action files from plugin source only."""
    selected: dict[str, Path] = {}
    base_dir = skill_dir / "assets"
    if base_dir.is_dir():
        for md_file in sorted(base_dir.rglob("actions/*.md")):
            rel = md_file.relative_to(base_dir).as_posix()
            selected[rel] = md_file
    return [selected[key] for key in sorted(selected)]
```

- [ ] **Step 2: Remove unused import of `get_skill_data_dir` if present**

Check if `get_skill_data_dir` is imported and only used in the removed code. If so, remove the import.

- [ ] **Step 3: Run action-related tests**

```bash
cd ~/Projects/Augur && python -m pytest src/mcp/augur_mcp/tests/ -v -k "action" 2>/dev/null; echo "exit: $?"
```

- [ ] **Step 4: Commit**

```bash
git add src/mcp/augur_mcp/infrastructure/actions.py
git commit -m "fix(ADR-454): remove vault scanning from action loading — plugin source only"
```

---

### Task 4: Remove seed copy-to-vault mechanism

**Files:**
- Modify: `.claude/skills/auto-seed-data/scripts/seed_data_ops.py`

- [ ] **Step 1: Read `seed_data_ops.py` fully to understand the copy logic**

Read the file to identify all code that copies seeds to vault and writes `._seeded` markers.

- [ ] **Step 2: Remove vault copy logic from `fix()` function**

The `fix()` function in `seed_data_ops.py` copies seed files from `assets/seeds/` to vault data dir and writes `._seeded` markers. Remove this copy logic entirely. The `scan()` function can still report which skills have seed data in source, but the fix action should be a no-op or just validate seeds exist.

- [ ] **Step 3: Remove `_SEED_MARKER` constant and `._seeded` references**

Remove the `_SEED_MARKER = "_seeded"` constant and all code referencing `._seeded` files.

- [ ] **Step 4: Run auto-seed-data tests**

```bash
cd ~/Projects/Augur && python -m pytest .claude/skills/auto-seed-data/augur/tests/ -v 2>/dev/null; echo "exit: $?"
```

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/auto-seed-data/scripts/seed_data_ops.py
git commit -m "fix(ADR-454): remove seed copy-to-vault mechanism — seeds read from plugin source via fallback"
```

---

### Task 5: Rewrite `auto-vault-hygiene` for flat structure

**Files:**
- Modify: `.claude/skills/auto-vault-hygiene/scripts/vault_hygiene_ops.py`

- [ ] **Step 1: Read the full file**

Read `vault_hygiene_ops.py` to understand all vault structure assumptions.

- [ ] **Step 2: Update `ALLOWED_TOP_DIRS`**

Add any non-skill dirs that now sit at vault root alongside skill dirs.

- [ ] **Step 3: Rewrite orphan detection loop (lines 108-124)**

Replace the nested `plugin_dir / skill_dir` loop with a flat iteration. Each top-level dir in vault is either a reserved dir (`config/`, `dev/`, `memory/`) or a skill dir. Check skill dirs against known skills:

```python
from src.config.paths import get_project_root, get_all_client_skill_dirs, get_all_plugin_dirs

for entry in vault.iterdir():
    if not entry.is_dir() or entry.name.startswith("."):
        continue
    if entry.name in ALLOWED_TOP_DIRS:
        continue
    # entry.name should be a known skill
    skill_name = entry.name
    skill_found = False
    for client_dir in get_all_client_skill_dirs():
        if (client_dir / skill_name).is_dir():
            skill_found = True
            break
    if not skill_found:
        for plugins_dir in get_all_plugin_dirs():
            for bundle_dir in plugins_dir.iterdir():
                if (bundle_dir / "skills" / skill_name).is_dir():
                    skill_found = True
                    break
            if skill_found:
                break
    if not skill_found:
        issues.append({...})
```

- [ ] **Step 4: Remove any remaining `parts[0]` hub extraction from vault paths**

Search the file for `parts[0]` or similar bundle-extraction patterns and remove them.

- [ ] **Step 5: Run vault hygiene tests**

```bash
cd ~/Projects/Augur && python -m pytest .claude/skills/auto-vault-hygiene/augur/tests/ -v 2>/dev/null; echo "exit: $?"
```

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/auto-vault-hygiene/scripts/vault_hygiene_ops.py
git commit -m "fix(ADR-454): rewrite vault hygiene scanner for flat vault structure"
```

---

### Task 6: Fix `parts[0]` hub extraction across 8 skill files

**Files:**
- Modify: `.claude/skills/rag/scripts/_scanners_structural.py`
- Modify: `.claude/skills/rag/scripts/rag_indexer.py`
- Modify: `.claude/skills/rag/scripts/binary_extractor.py`
- Modify: `.claude/skills/rag/scripts/mcp/rag_tools.py`
- Modify: `.claude/skills/knowledge/scripts/mcp/rag_search.py`
- Modify: `.claude/skills/knowledge/scripts/mcp/rag_knowledge.py`
- Modify: `.claude/skills/file-manager/scripts/mcp/__init__.py`
- Modify: `.claude/skills/apple/scripts/sync/source_sync.py`
- Modify: `src/mcp/augur_mcp/infrastructure/browse.py`
- Modify: `src/mcp/augur_mcp/infrastructure/paths.py`

- [ ] **Step 1: Grep for all `parts[0]` patterns in vault/documents path contexts**

```bash
grep -rn "parts\[0\]" .claude/skills/ src/mcp/ --include="*.py" | grep -v __pycache__ | grep -v .venv
```

Also grep for direct `get_vault_dir() /` construction:

```bash
grep -rn "get_vault_dir()" .claude/skills/ src/mcp/ --include="*.py" | grep -v __pycache__ | grep -v .venv | grep -v "def get_vault_dir"
```

- [ ] **Step 2: Fix each file**

For each file that extracts `hub = parts[0]` from a vault-relative path: the first part is now the skill name, not the bundle. Either:
- Remove the hub extraction if not needed
- Use SKILL.md `x-augur-hub` frontmatter to get the hub name instead
- Adjust index to `parts[0]` = skill (was `parts[1]`)

Read each file, understand the context, and fix accordingly. Do NOT guess — read first.

- [ ] **Step 3: Fix RAG infrastructure regex in `src/mcp/augur_mcp/infrastructure/paths.py`**

Read the file, find the `RAG_SKILL_PATH_RE` regex pattern that expects `bundle/skill`, and update it for flat `skill` structure.

- [ ] **Step 4: Remove `get_bundle_rag_dir` calls from `rag_tools.py`**

Replace any `get_bundle_rag_dir(bundle)` calls with direct skill-level RAG dir lookups.

- [ ] **Step 5: Run RAG and knowledge tests**

```bash
cd ~/Projects/Augur && python -m pytest tests/test_paths_rag.py .claude/skills/rag/augur/tests/ .claude/skills/knowledge/augur/tests/ -v 2>/dev/null; echo "exit: $?"
```

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/rag/ .claude/skills/knowledge/ .claude/skills/file-manager/ .claude/skills/apple/ src/mcp/augur_mcp/infrastructure/browse.py src/mcp/augur_mcp/infrastructure/paths.py tests/test_paths_rag.py
git commit -m "fix(ADR-454): remove bundle-based path extraction from RAG, knowledge, and file operations"
```

---

### Task 7: Hardening writer audit

**Files:**
- Search scope: entire codebase

- [ ] **Step 1: Grep for hardening writes to vault**

```bash
grep -rn "hardening" .claude/skills/ src/ --include="*.py" | grep -v __pycache__ | grep -v .venv | grep -v "get_hardening_dir" | grep -i "vault\|data_dir\|write\|save\|mkdir"
```

- [ ] **Step 2: Fix any code writing hardening data to vault paths**

Any code that constructs hardening paths via `get_skill_data_dir()` or `get_skill_vault_dir()` instead of `get_hardening_dir()` is a bug per ADR-416. Fix each instance.

- [ ] **Step 3: Grep for stale bundle path patterns**

```bash
grep -rn "augur-career\|augur-life\|augur-system\|augur-dev\|augur-knowledge\|augur-dashboard\|augur-adaptive" .claude/skills/ src/ --include="*.py" | grep -v __pycache__ | grep -v .venv | grep -v "plugins/" | grep -v "dist/" | grep -i "vault\|data_dir\|document"
```

- [ ] **Step 4: Commit any fixes**

```bash
git add -A && git commit -m "fix(ADR-454): fix hardening writers leaking to vault — redirect to runtime state"
```

---

### Task 8: Remount plugins and rebuild

**Files:**
- No direct edits — build/deploy step

- [ ] **Step 1: Remount plugins to propagate source changes to dist**

```bash
cd ~/Projects/Augur && python src/scripts/mount-plugins.py
```

- [ ] **Step 2: Run full Python test suite**

```bash
cd ~/Projects/Augur && python -m pytest tests/ src/mcp/augur_mcp/tests/ -v --timeout=30 2>&1 | tail -30
```

- [ ] **Step 3: Verify MCP server starts**

```bash
cd ~/Projects/Augur && timeout 10 python -m src.mcp.augur_mcp 2>&1 | head -5; echo "exit: $?"
```

- [ ] **Step 4: Commit mount if needed**

```bash
git add dist/ && git diff --cached --stat && git commit -m "fix(ADR-454): remount plugins to propagate path changes to deployed copies" --allow-empty
```

---

### Task 9: Vault data migration

**Files:**
- Create: `src/scripts/migrate_vault_flatten.py`
- Operates on: `get_vault_dir()/`, `~/Documents/Augur/`, `~/Library/Application Support/Augur/rag/`

- [ ] **Step 1: Backup vault**

```bash
cd get_vault_dir() && git add -A && git commit -m "pre-ADR-454 backup: snapshot before vault flatten migration" --allow-empty
```

- [ ] **Step 2: Write migration script**

Create `src/scripts/migrate_vault_flatten.py` that:

1. **Rescues 25 user-authored prompts** — read from vault, write to plugin source (replacing TODO placeholders). The audit identified these in: career (3), content (9), growth (4), scraper (3), finance (1), health (1), wealth (3), wearables (1).
2. **Deletes technical files** in vault:
   - `find get_vault_dir()/ -name '._seeded' -delete`
   - `find get_vault_dir()/ -name 'example-*' -delete`
   - `find get_vault_dir()/ -path '*/actions/*' -type f -delete` then `rmdir`
   - `find get_vault_dir()/ -path '*/prompts/*' -type f -delete` then `rmdir`
   - `find get_vault_dir()/ -path '*/chains/*' -type f -delete` then `rmdir`
   - `find get_vault_dir()/ -path '*/schemas/*' -type f -delete` then `rmdir`
   - `find get_vault_dir()/ -path '*/_config/*' -type f -delete` then `rmdir`
   - `find get_vault_dir()/ -name '.gitkeep' -delete`
   - `find get_vault_dir()/ -path '*/hardening/*' -type f -delete` then `rmdir`
   - `rm -rf get_vault_dir()/augur-adaptive/`
3. **Flattens vault**: for each `augur-{bundle}/{skill}/`, `mv` contents to `{skill}/` at root
4. **Flattens Documents**: same logic for `~/Documents/Augur/`
5. **Cleans RAG dirs**: delete `~/Library/Application Support/Augur/rag/augur-*/`
6. **Removes empty dirs**: recursive cleanup
7. **Validates**: asserts per spec (depth, no bundle dirs, no technical patterns)

Use Python `shutil.move`, `pathlib`, not shell commands. Include `--dry-run` flag.

- [ ] **Step 3: Run migration with `--dry-run` first**

```bash
cd ~/Projects/Augur && python src/scripts/migrate_vault_flatten.py --dry-run
```

Review output. Verify it would move the right files.

- [ ] **Step 4: Run migration for real**

```bash
cd ~/Projects/Augur && python src/scripts/migrate_vault_flatten.py
```

- [ ] **Step 5: Commit vault changes**

```bash
cd get_vault_dir() && git add -A && git commit -m "ADR-454: flatten vault structure — remove bundle dirs and technical files"
```

- [ ] **Step 6: Commit migration script**

```bash
cd ~/Projects/Augur && git add src/scripts/migrate_vault_flatten.py
git commit -m "fix(ADR-454): add vault flatten migration script"
```

---

### Task 10: RAG re-index and final verification

**Files:**
- No edits — verification step

- [ ] **Step 1: Run full RAG re-index**

```bash
cd ~/Projects/Augur && python .claude/skills/rag/scripts/unified_indexer.py 2>&1 | tail -20
```

- [ ] **Step 2: Verify vault structure**

```bash
# No bundle dirs remain
ls get_vault_dir()/ | grep -c "augur-"
# Expected: 0

# Max depth check
find get_vault_dir()/ -type f ! -path '*/.git/*' | awk -F/ '{print NF}' | sort -rn | head -1
# Expected: <= 8 (absolute path components for get_vault_dir()/{skill}/{entity}/{file})

# No technical files remain
find get_vault_dir()/ -name '._seeded' -o -name '.gitkeep' -o -path '*/chains/*' -o -path '*/schemas/*' | head -5
# Expected: no output

# File count sanity
find get_vault_dir()/ -type f ! -path '*/.git/*' ! -name '.DS_Store' | wc -l
# Expected: ~2,900 (down from 3,714)
```

- [ ] **Step 3: Verify path functions work end-to-end**

```bash
cd ~/Projects/Augur && python -c "
from src.config.paths import get_skill_vault_dir, get_skill_documents_dir, get_skill_rag_dir
print('vault:', get_skill_vault_dir('career'))
print('docs:', get_skill_documents_dir('career'))
print('rag:', get_skill_rag_dir('career'))
# Should be: get_vault_dir()/career, ~/Documents/Augur/career, ~/Library/.../rag/career
"
```

- [ ] **Step 4: Run full test suite**

```bash
cd ~/Projects/Augur && python -m pytest tests/ src/mcp/augur_mcp/tests/ -v --timeout=30 2>&1 | tail -30
```

- [ ] **Step 5: Verify MCP server starts and responds**

```bash
cd ~/Projects/Augur && timeout 10 python -m src.mcp.augur_mcp 2>&1 | head -5
```

---

### Task 11: Gap scan and cleanup

- [ ] **Step 1: Grep for any remaining bundle path construction**

```bash
grep -rn "/ bundle " src/ .claude/ --include="*.py" | grep -v __pycache__ | grep -v .venv | grep -v "plugins/"
grep -rn "get_bundle_rag_dir" src/ .claude/ --include="*.py" | grep -v __pycache__ | grep -v .venv
```

- [ ] **Step 2: Check for `._seeded` or seed copy references**

```bash
grep -rn "_seeded\|_SEED_MARKER\|copy.*seed\|shutil.*seed" src/ .claude/ --include="*.py" | grep -v __pycache__ | grep -v .venv
```

- [ ] **Step 3: Delete `_seed.yaml` manifests from plugin source**

```bash
find dist/plugins/ .claude/skills/ -name '_seed.yaml' -type f
# Delete them all
find dist/plugins/ .claude/skills/ -name '_seed.yaml' -type f -delete
```

- [ ] **Step 4: Fix any remaining issues found in steps 1-3**

- [ ] **Step 5: Final commit**

```bash
git add -A && git commit -m "fix(ADR-454): gap scan cleanup — remove stale bundle refs and seed manifests"
```
