# Multi-Client Skill Structure Refactor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Flatten skill storage from `.claude/skills/` + `plugins/` into a single `skills/` directory at project root, replace the MCP-backed sync engine with a one-way stub generator, and enable multi-client skill discovery with origin tagging.

**Architecture:** One canonical `skills/` directory (writable, Augur-owned) + read-only client cache scans. Stub generator writes outward to Codex/Cursor/Copilot. Dashboard skills browser aggregates all sources with origin/author/tier/hub filters.

**Tech Stack:** Python 3.11+ (discovery, paths, migration, stub generator), TypeScript (mount-plugins rewrite, dashboard skills browser), YAML frontmatter (SKILL.md format)

**Spec:** `docs/superpowers/specs/2026-03-22-multi-client-skill-structure-design.md`

---

## File Structure

### New Files

| File | Responsibility |
|------|---------------|
| `scripts/migrate_skills.py` | One-shot migration: move skills, flatten nested, strip fields |
| `scripts/generate_client_stubs.py` | One-way stub generator with cleanup |
| (added to `src/config/paths.py`) | `get_skills_dir()` + `get_client_cache_dirs()` functions |
| `.claude-plugin/plugin.json` | Claude Code marketplace manifest |
| `.claude-plugin/marketplace.json` | Marketplace listing |
| `.cursor-plugin/plugin.json` | Cursor discovery config |
| `.codex/INSTALL.md` | Codex external install guide |
| `.opencode/INSTALL.md` | OpenCode external install guide |
| `apps/dashboard/app/api/skills/registry/route.ts` | Skills registry API endpoint |

### Modified Files

| File | What Changes |
|------|-------------|
| `src/plugins/skill_discovery.py` (628 lines) | Rewrite to ~150 lines: single-dir scan + client cache scan + TTL cache |
| `src/config/paths.py` (563 lines) | Add `get_skills_dir()`, `get_client_cache_dirs()`. Remove `PLUGIN_BUNDLES`, `get_plugin_bundles()`, `get_plugins_dir()`, `get_skill_bundle()`. Rewrite `get_skill_root()`, `validate_paths()`. |
| `apps/dashboard/scripts/mount/discovery.ts` (903 lines) | Replace multi-dir scanning with single `skills/` scan |
| `apps/dashboard/scripts/mount-plugins.ts` (888 lines) | Remove `CLIENT_SKILL_DIRS`, update to use `skills/` |
| `src/mcp/augur_mcp/adapters/filesystem_registry.py` (164 lines) | Remove tier logic, remove `master`/`sync_enabled` references |
| `CLAUDE.md` | Update directory layout section |

### Deleted Files

| File | Lines |
|------|-------|
| `.claude/skills/ai_bridge/scripts/sync_agents/sync_client_skills.py` | 142 |
| `src/mcp/augur_mcp/core/skill_renderer.py` | 105 |
| `src/mcp/augur_mcp/adapters/skill_detection.py` | 26 |
| `src/mcp/augur_mcp/core/client_formats.py` | 85 |
| `.claude/skills/` directory (moved) | ~200 skills |
| `plugins/` directory | empty |
| `.gemini/skills/` adapted copies | varies |

---

## Task 1: Write Migration Script

**Files:**
- Create: `scripts/migrate_skills.py`
- Test: `scripts/test_migrate_skills.py`

- [ ] **Step 1: Write test for skill counting and dry-run**

```python
# scripts/test_migrate_skills.py
"""Test migration script in dry-run mode."""
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

def test_dry_run_counts_all_skills():
    """Dry-run should report skill count without moving anything."""
    result = subprocess.run(
        [sys.executable, "scripts/migrate_skills.py", "--dry-run"],
        capture_output=True, text=True, cwd=PROJECT_ROOT,
    )
    assert result.returncode == 0, f"Migration dry-run failed: {result.stderr}"
    assert "SKILL.md files found" in result.stdout
    # Verify no files were actually moved
    assert (PROJECT_ROOT / ".claude" / "skills").exists(), "Dry-run should not move files"

def test_dry_run_detects_nested_skills():
    """Dry-run should find nested sub-skills."""
    result = subprocess.run(
        [sys.executable, "scripts/migrate_skills.py", "--dry-run", "--verbose"],
        capture_output=True, text=True, cwd=PROJECT_ROOT,
    )
    assert "nested" in result.stdout.lower() or "sub-skill" in result.stdout.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest scripts/test_migrate_skills.py -v`
Expected: FAIL — `scripts/migrate_skills.py` doesn't exist

- [ ] **Step 3: Write migration script**

```python
# scripts/migrate_skills.py
"""Migrate skills from .claude/skills/ to skills/ at project root.

Usage:
    python scripts/migrate_skills.py --dry-run    # Preview without moving
    python scripts/migrate_skills.py              # Execute migration
    python scripts/migrate_skills.py --verbose    # Verbose output
"""
import argparse
import re
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
SOURCE_DIR = PROJECT_ROOT / ".claude" / "skills"
TARGET_DIR = PROJECT_ROOT / "skills"
FIELDS_TO_REMOVE = {"x-augur-master", "x-augur-sync", "x-augur-origin", "x-augur-plugin"}


def find_all_skill_files(root: Path) -> list[Path]:
    """Recursively find all SKILL.md files under root."""
    return sorted(root.rglob("SKILL.md"))


def infer_parent(skill_path: Path, source_root: Path) -> str | None:
    """If skill is nested inside another skill, return parent skill name."""
    rel = skill_path.relative_to(source_root)
    parts = rel.parts  # e.g. ('devops', 'commands', 'adr', 'SKILL.md')
    if len(parts) <= 2:
        return None  # Top-level skill: ('skillname', 'SKILL.md')
    return parts[0]  # Parent is the first component


def skill_name_from_path(skill_path: Path) -> str:
    """Extract skill name from SKILL.md path (its parent directory name)."""
    return skill_path.parent.name


def strip_frontmatter_fields(content: str, fields: set[str]) -> str:
    """Remove specified YAML frontmatter fields from markdown content."""
    lines = content.split("\n")
    result = []
    in_frontmatter = False
    skip_block = False
    indent_level = 0

    for i, line in enumerate(lines):
        if i == 0 and line.strip() == "---":
            in_frontmatter = True
            result.append(line)
            continue
        if in_frontmatter and line.strip() == "---":
            in_frontmatter = False
            skip_block = False
            result.append(line)
            continue

        if not in_frontmatter:
            result.append(line)
            continue

        # Check if this is a top-level field to remove
        if not line.startswith((" ", "\t")) and ":" in line:
            field_name = line.split(":")[0].strip()
            if field_name in fields:
                skip_block = True
                indent_level = 0
                continue
            else:
                skip_block = False

        # Skip continuation lines of a removed field
        if skip_block and line.startswith((" ", "\t")):
            continue

        skip_block = False
        result.append(line)

    return "\n".join(result)


def add_parent_field(content: str, parent_name: str) -> str:
    """Add x-augur-parent field to frontmatter."""
    lines = content.split("\n")
    for i, line in enumerate(lines):
        if i > 0 and line.strip() == "---":
            lines.insert(i, f"x-augur-parent: {parent_name}")
            break
    return "\n".join(lines)


def migrate(dry_run: bool = False, verbose: bool = False) -> int:
    """Execute migration. Returns 0 on success, 1 on error."""
    if not SOURCE_DIR.exists():
        print(f"ERROR: Source directory not found: {SOURCE_DIR}")
        return 1

    skill_files = find_all_skill_files(SOURCE_DIR)
    print(f"Found {len(skill_files)} SKILL.md files found in {SOURCE_DIR}")

    # Categorize: top-level vs nested
    top_level = []
    nested = []
    for sf in skill_files:
        parent = infer_parent(sf, SOURCE_DIR)
        if parent is None:
            top_level.append((sf, None))
        else:
            nested.append((sf, parent))

    print(f"  Top-level skills: {len(top_level)}")
    print(f"  Nested sub-skills: {len(nested)}")

    if dry_run:
        if verbose:
            for sf, parent in nested:
                name = skill_name_from_path(sf)
                print(f"  nested sub-skill: {name} (parent: {parent})")
        print("\nDry-run complete. No files moved.")
        return 0

    # Create target directory
    TARGET_DIR.mkdir(exist_ok=True)

    moved = 0
    errors = []

    # Move top-level skills (entire skill directory)
    for sf, _ in top_level:
        skill_dir = sf.parent
        name = skill_dir.name
        dest = TARGET_DIR / name
        if dest.exists():
            errors.append(f"CONFLICT: {name} already exists at {dest}")
            continue
        if verbose:
            print(f"  Moving {skill_dir} -> {dest}")
        shutil.move(str(skill_dir), str(dest))
        moved += 1

    # Move nested sub-skills (just the sub-skill directory, flattened)
    for sf, parent in nested:
        skill_dir = sf.parent
        name = skill_dir.name
        dest = TARGET_DIR / name
        if dest.exists():
            errors.append(f"CONFLICT: nested {name} (parent: {parent}) already exists at {dest}")
            continue
        if verbose:
            print(f"  Flattening nested {parent}/{name} -> {dest}")
        shutil.move(str(skill_dir), str(dest))
        # Add x-augur-parent field
        dest_skill_md = dest / "SKILL.md"
        if dest_skill_md.exists():
            content = dest_skill_md.read_text()
            content = add_parent_field(content, parent)
            dest_skill_md.write_text(content)
        moved += 1

    # Strip deprecated frontmatter fields from all migrated SKILL.md files
    stripped = 0
    for skill_md in TARGET_DIR.rglob("SKILL.md"):
        content = skill_md.read_text()
        new_content = strip_frontmatter_fields(content, FIELDS_TO_REMOVE)
        if new_content != content:
            skill_md.write_text(new_content)
            stripped += 1

    # Validate count: pre-count is number of planned destinations (top-level + nested)
    # NOT the raw rglob count (which includes SKILL.md files at arbitrary depths)
    expected_count = len(top_level) + len(nested)
    post_count = len(list(TARGET_DIR.glob("*/SKILL.md")))
    if post_count != expected_count:
        print(f"WARNING: Count mismatch! Expected: {expected_count}, Got: {post_count}")

    # Report
    print(f"\nMigration complete:")
    print(f"  Skills moved: {moved}")
    print(f"  Frontmatter fields stripped: {stripped} files")
    print(f"  Post-migration skill count: {post_count}")

    if errors:
        print(f"\n  ERRORS ({len(errors)}):")
        for e in errors:
            print(f"    {e}")
        return 1

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate skills to skills/ at project root")
    parser.add_argument("--dry-run", action="store_true", help="Preview without moving")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()
    sys.exit(migrate(dry_run=args.dry_run, verbose=args.verbose))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest scripts/test_migrate_skills.py::test_dry_run_counts_all_skills -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/migrate_skills.py scripts/test_migrate_skills.py
git commit -m "feat: add skill migration script with dry-run support"
```

---

## Task 2: Write Stub Generator

**Files:**
- Create: `scripts/generate_client_stubs.py`
- Test: `scripts/test_generate_client_stubs.py`

- [ ] **Step 1: Write test for stub generation**

```python
# scripts/test_generate_client_stubs.py
"""Test stub generator produces correct output."""
import tempfile
from pathlib import Path
from generate_client_stubs import generate_codex_stub, generate_cursor_stub, AUGUR_GENERATED_MARKER

def test_codex_stub_has_marker():
    """Generated Codex stub must contain AUGUR-GENERATED marker."""
    content = generate_codex_stub("test-skill", "Test description", "# Body here")
    assert AUGUR_GENERATED_MARKER in content

def test_cursor_stub_has_marker():
    """Generated Cursor stub must contain AUGUR-GENERATED marker."""
    content = generate_cursor_stub("test-skill", "Test description", "# Body here")
    assert AUGUR_GENERATED_MARKER in content

def test_cleanup_removes_stale_stubs():
    """Cleanup should delete stubs for skills that no longer exist."""
    from generate_client_stubs import cleanup_stale_stubs, AUGUR_GENERATED_MARKER
    with tempfile.TemporaryDirectory() as tmpdir:
        stale_file = Path(tmpdir) / "deleted-skill.md"
        stale_file.write_text(f"{AUGUR_GENERATED_MARKER}\n# Stale")
        user_file = Path(tmpdir) / "user-installed.md"
        user_file.write_text("# Not generated by Augur")

        cleanup_stale_stubs(Path(tmpdir), current_skill_names={"active-skill"}, suffix=".md")

        assert not stale_file.exists(), "Stale stub should be deleted"
        assert user_file.exists(), "User-installed file should NOT be deleted"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest scripts/test_generate_client_stubs.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Write stub generator**

```python
# scripts/generate_client_stubs.py
"""One-way stub generator: skills/ → client-specific stubs.

Usage:
    python scripts/generate_client_stubs.py           # Generate + cleanup
    python scripts/generate_client_stubs.py --dry-run # Preview only
"""
import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
SKILLS_DIR = PROJECT_ROOT / "skills"
AUGUR_GENERATED_MARKER = "<!-- AUGUR-GENERATED -->"

# Target directories (relative to PROJECT_ROOT)
TARGETS = {
    "codex": {"dir": ".codex/prompts", "suffix": ".md"},
    "cursor": {"dir": ".cursor/rules", "suffix": ".mdc"},
    "copilot": {"dir": ".github/copilot", "suffix": ".md"},
}


def read_skill_md(skill_dir: Path) -> tuple[str, str, str] | None:
    """Read SKILL.md, return (name, description, body) or None."""
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return None
    content = skill_md.read_text()
    # Parse frontmatter
    lines = content.split("\n")
    if not lines or lines[0].strip() != "---":
        return None
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        return None

    name = skill_dir.name
    description = ""
    for line in lines[1:end_idx]:
        if line.startswith("description:"):
            description = line.split(":", 1)[1].strip().strip('"').strip("'")
            if description == "|":
                # Multi-line description — take next non-empty line
                for dl in lines[lines.index(line) + 1 : end_idx]:
                    dl = dl.strip()
                    if dl:
                        description = dl
                        break
            break

    body = "\n".join(lines[end_idx + 1 :]).strip()
    return name, description, body


def generate_codex_stub(name: str, description: str, body: str) -> str:
    """Generate a flat Codex prompt stub."""
    return f"""{AUGUR_GENERATED_MARKER}
---
name: {name}
description: {description}
---

{body}
"""


def generate_cursor_stub(name: str, description: str, body: str) -> str:
    """Generate a Cursor .mdc rule stub."""
    return f"""{AUGUR_GENERATED_MARKER}
---
name: {name}
description: {description}
---

{body}
"""


def cleanup_stale_stubs(target_dir: Path, current_skill_names: set[str], suffix: str) -> list[str]:
    """Delete stubs for skills that no longer exist. Returns list of deleted files."""
    deleted = []
    if not target_dir.exists():
        return deleted
    for f in target_dir.iterdir():
        if not f.name.endswith(suffix):
            continue
        # Only delete files with our marker
        try:
            head = f.read_text()[:200]
        except (OSError, UnicodeDecodeError):
            continue
        if AUGUR_GENERATED_MARKER not in head:
            continue
        # Check if source skill still exists
        stub_name = f.stem
        if stub_name not in current_skill_names:
            f.unlink()
            deleted.append(str(f))
    return deleted


def main(dry_run: bool = False) -> int:
    """Generate stubs and clean up stale ones."""
    if not SKILLS_DIR.exists():
        print(f"ERROR: skills/ directory not found at {SKILLS_DIR}")
        return 1

    # Collect skills
    skills = []
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        if not skill_dir.is_dir():
            continue
        parsed = read_skill_md(skill_dir)
        if parsed:
            skills.append(parsed)

    skill_names = {s[0] for s in skills}
    print(f"Found {len(skills)} skills in {SKILLS_DIR}")

    for target_name, target_config in TARGETS.items():
        target_dir = PROJECT_ROOT / target_config["dir"]
        suffix = target_config["suffix"]

        if dry_run:
            print(f"  Would generate {len(skills)} stubs in {target_dir}")
            continue

        target_dir.mkdir(parents=True, exist_ok=True)

        # Generate stubs
        generated = 0
        for name, description, body in skills:
            stub_path = target_dir / f"{name}{suffix}"
            if target_name == "codex":
                content = generate_codex_stub(name, description, body)
            elif target_name == "cursor":
                content = generate_cursor_stub(name, description, body)
            else:
                content = generate_codex_stub(name, description, body)  # Default format
            stub_path.write_text(content)
            generated += 1

        # Cleanup stale stubs
        deleted = cleanup_stale_stubs(target_dir, skill_names, suffix)

        print(f"  {target_name}: generated {generated}, cleaned up {len(deleted)} stale")

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate client stubs from skills/")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    sys.exit(main(dry_run=args.dry_run))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest scripts/test_generate_client_stubs.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/generate_client_stubs.py scripts/test_generate_client_stubs.py
git commit -m "feat: add one-way stub generator with cleanup"
```

---

## Task 3: Add Client Plugin Manifests

**Files:**
- Create: `.claude-plugin/plugin.json`
- Create: `.claude-plugin/marketplace.json`
- Create: `.cursor-plugin/plugin.json`
- Create: `.codex/INSTALL.md`
- Create: `.opencode/INSTALL.md`

- [ ] **Step 1: Create Claude Code plugin manifest**

```json
// .claude-plugin/plugin.json
{
  "name": "augur-skills",
  "description": "Augur personal knowledge and automation skills",
  "version": "1.0.0",
  "author": { "name": "Augur" },
  "homepage": "https://github.com/AugurOS/augur",
  "license": "MIT",
  "skills": "./skills/"
}
```

```json
// .claude-plugin/marketplace.json
{
  "name": "augur-skills",
  "description": "Augur personal knowledge and automation skills library",
  "owner": { "name": "Augur" },
  "plugins": [
    {
      "name": "augur-skills",
      "description": "Personal knowledge, automation, and development skills",
      "version": "1.0.0",
      "source": "./",
      "author": { "name": "Augur" }
    }
  ]
}
```

- [ ] **Step 2: Create Cursor plugin manifest**

```json
// .cursor-plugin/plugin.json
{
  "name": "augur-skills",
  "displayName": "Augur Skills",
  "description": "Augur personal knowledge and automation skills",
  "version": "1.0.0",
  "author": { "name": "Augur" },
  "license": "MIT",
  "skills": "./skills/"
}
```

- [ ] **Step 3: Create Codex and OpenCode install guides**

Create `.codex/INSTALL.md` with git clone + symlink instructions.
Create `.opencode/INSTALL.md` with git clone + symlink instructions.
(Follow MiniMax format — see spec for reference.)

- [ ] **Step 4: Commit**

```bash
git add .claude-plugin/ .cursor-plugin/ .codex/INSTALL.md .opencode/INSTALL.md
git commit -m "feat: add multi-client plugin manifests and install guides"
```

---

## Tasks 4-8: The Atomic Migration Block

> **CRITICAL: Tasks 4-8 MUST be executed as a single atomic unit and committed together (squash into one commit).** The spec requires all references to be fixed atomically — intermediate commits between these tasks leave the system broken (discovery, paths, mount all point at deleted directories). Execute all 5 tasks, then make ONE commit at the end of Task 8.

## Task 4: Execute Migration

**Prerequisites:** Tasks 1-3 complete. This is the big-bang step.

**Files:**
- Run: `scripts/migrate_skills.py`
- Delete: `.claude/skills/`, `plugins/`

- [ ] **Step 1: Run dry-run and record counts**

```bash
python scripts/migrate_skills.py --dry-run --verbose > /tmp/migration-dry-run.log 2>&1
cat /tmp/migration-dry-run.log
```

Record the total SKILL.md count. This is the target for post-migration validation.

- [ ] **Step 2: Execute migration**

```bash
python scripts/migrate_skills.py --verbose 2>&1 | tee /tmp/migration.log
```

Verify output shows: all skills moved, no errors, count matches.

- [ ] **Step 3: Delete source directories**

```bash
rm -rf .claude/skills/
rm -rf plugins/
```

Note: `.claude/` directory itself stays (it has other files like `settings.json`).

- [ ] **Step 4: Validate file count**

```bash
find skills/ -name "SKILL.md" -maxdepth 2 | wc -l
# Must match pre-migration count from step 1
```

- [ ] **Step 5: DO NOT COMMIT YET — continue to Task 5**

(Part of atomic block — commit happens at end of Task 8)

---

## Task 5: Rewrite `src/config/paths.py`

**Files:**
- Modify: `src/config/paths.py`

- [ ] **Step 1: Add `get_skills_dir()` and `get_client_cache_dirs()`**

Add to `src/config/paths.py`:

```python
def get_skills_dir() -> Path:
    """Canonical skills directory at project root."""
    return get_project_root() / "skills"


def get_client_cache_dirs() -> dict[str, Path]:
    """Client cache directories for multi-source skill discovery."""
    home = Path.home()
    return {
        "claude-code": home / ".claude" / "plugins" / "cache",
        "codex": home / ".codex" / "prompts",
        "cursor": home / ".cursor" / "rules",
        "gemini": home / ".gemini" / "skills",
    }
```

- [ ] **Step 2: Rewrite `get_skill_root()` to use `skills/`**

Replace the current implementation that checks `.claude/skills/` then `plugins/{bundle}/skills/` with:

```python
def get_skill_root(skill_name: str) -> Path:
    """Resolve skill directory from skills/ at project root."""
    skills_dir = get_skills_dir()
    skill_path = skills_dir / skill_name
    if skill_path.exists():
        return skill_path
    raise ValueError(f"Skill not found: {skill_name} (looked in {skills_dir})")
```

- [ ] **Step 3: Remove `PLUGIN_BUNDLES`, `get_plugin_bundles()`, `get_plugins_dir()`, `get_skill_bundle()`**

Delete these functions/constants. Then grep for all importers:

```bash
grep -r "PLUGIN_BUNDLES\|get_plugin_bundles\|get_plugins_dir\|get_skill_bundle" --include="*.py" src/ .claude/
```

Fix every importer.

- [ ] **Step 4: Update `validate_paths()` to remove `plugins/` mkdir**

Remove the line that auto-creates the `plugins/` directory. Add `skills/` to validated paths if appropriate.

- [ ] **Step 5: Remove `get_all_client_skill_dirs()`**

This function returns the old multi-dir list. Replace all callers with `get_skills_dir()` or `get_client_cache_dirs()`.

- [ ] **Step 6: Grep for `get_all_client_skill_dirs` specifically**

```bash
grep -rn "get_all_client_skill_dirs" --include="*.py" src/
```

Known callers: `file_assets.py`, `context_injector.py`, `browse.py`, `plugin_tools.py`. Fix each to use `get_skills_dir()` or `get_client_cache_dirs()`.

- [ ] **Step 7: DO NOT COMMIT YET — continue to Task 6**

(Part of atomic block — commit happens at end of Task 8)

---

## Task 6: Rewrite `skill_discovery.py`

**Files:**
- Modify: `src/plugins/skill_discovery.py` (628 lines → ~150 lines)
- Test: run existing tests after rewrite

- [ ] **Step 1: Write the new discovery module**

Replace the entire `_iter_skill_dirs` and `discover_all_skills` implementation with the multi-source scan from the spec. Keep `SkillRecord` dataclass but remove `master` and `sync_enabled` fields. Keep `list_skills()`, `resolve_skill()`, `get_skill_path()` as thin wrappers. Keep TTL cache.

Key changes:
- `discover_all_skills()` scans `get_skills_dir()` + `get_client_cache_dirs()`
- `is_augur_generated(path)` checks for `AUGUR-GENERATED` marker in first 5 lines
- `SkillRecord` gets `origin` field (already exists) and `author` field
- Remove: `_iter_skill_dirs()`, `infer_master()`, tier logic, dedup logic, adapted-copy scanning

- [ ] **Step 2: Grep for all importers of removed fields/functions**

```bash
grep -r "sync_enabled\|\.master\|infer_master\|_iter_skill_dirs" --include="*.py" src/
```

Fix each reference.

- [ ] **Step 3: Run existing tests**

```bash
python -m pytest tests/ -k "skill" -v --timeout=30
```

Fix any failures caused by the rewrite.

- [ ] **Step 4: DO NOT COMMIT YET — continue to Task 7**

(Part of atomic block — commit happens at end of Task 8)

---

## Task 7: Simplify `filesystem_registry.py` and Delete Sync Infrastructure

**Files:**
- Modify: `src/mcp/augur_mcp/adapters/filesystem_registry.py`
- Delete: `src/mcp/augur_mcp/core/skill_renderer.py`
- Delete: `src/mcp/augur_mcp/adapters/skill_detection.py`
- Delete: `src/mcp/augur_mcp/core/client_formats.py`
- Delete: `.claude/skills/ai_bridge/scripts/sync_agents/sync_client_skills.py`

- [ ] **Step 1: Simplify `filesystem_registry.py`**

Remove references to `master`, `sync_enabled`, tier logic, adapted-copy detection. The registry should just call `discover_all_skills()` and return results.

- [ ] **Step 2: Delete sync infrastructure files**

```bash
rm src/mcp/augur_mcp/core/skill_renderer.py
rm src/mcp/augur_mcp/adapters/skill_detection.py
rm src/mcp/augur_mcp/core/client_formats.py
```

- [ ] **Step 3: Grep for imports of deleted modules**

```bash
grep -r "skill_renderer\|skill_detection\|client_formats\|sync_client_skills" --include="*.py" src/ .claude/ scripts/
```

Remove all imports and references.

- [ ] **Step 4: Delete adapted copies**

```bash
rm -rf .gemini/skills/
```

- [ ] **Step 5: Remove AUGUR-ADAPTED-COPY and AUGUR-STUB markers**

```bash
grep -rl "AUGUR-ADAPTED-COPY\|AUGUR-STUB" --include="*.md" .
```

Delete or clean any files found.

- [ ] **Step 6: Delete `augur.yaml` plugin manifests**

```bash
find skills/ -name "augur.yaml" -type f
```

Review each and delete — discovery is from SKILL.md frontmatter only now.

```bash
grep -r "augur\.yaml" --include="*.py" --include="*.ts" src/ apps/ scripts/
```

Remove any code that reads `augur.yaml` manifests.

- [ ] **Step 7: DO NOT COMMIT YET — continue to Task 8**

(Part of atomic block — commit happens at end of Task 8)

---

## Task 8: Rewrite Dashboard Mount System

**Files:**
- Modify: `apps/dashboard/scripts/mount/discovery.ts` (903 lines)
- Modify: `apps/dashboard/scripts/mount-plugins.ts` (888 lines)

- [ ] **Step 1: Read current `discovery.ts` to understand page-copying logic**

Understand what `scanPluginDir`, `scanClientSkillDir`, `scanPluginCacheDir`, `discoverPlugins` do. The page-copying logic must be preserved — only the source paths change.

- [ ] **Step 2: Replace multi-dir scanning with single `skills/` scan**

In `mount-plugins.ts` (line ~86):
- Remove `CLIENT_SKILL_DIRS` constant (it lives here, NOT in `discovery.ts`)
- Update paths to use `skills/` instead of `.claude/skills/`

In `discovery.ts`:
- Remove `scanPluginDir`, `scanClientSkillDir`, `scanPluginCacheDir`
- Add `scanSkillsDir(skillsDir: string, plugins: Map<string, DiscoveredPlugin>)` that scans `skills/*/augur/dashboard/`
- Update `discoverPlugins()` to call only `scanSkillsDir()`

- [ ] **Step 3: Run dashboard build**

```bash
pnpm --filter dashboard build
```

Fix any build errors.

- [ ] **Step 4: COMMIT THE ENTIRE ATOMIC BLOCK (Tasks 4-8)**

This is the single atomic commit for the entire migration:

```bash
git add -A
git commit -m "feat: migrate skills to skills/ and rewrite infrastructure

Atomic migration:
- Move ~200 skills from .claude/skills/ to skills/ at project root
- Flatten nested sub-skills with x-augur-parent field
- Strip deprecated frontmatter fields (x-augur-master, x-augur-sync, etc.)
- Rewrite paths.py: add get_skills_dir(), get_client_cache_dirs()
- Rewrite skill_discovery.py: single-dir + client cache scan (628→~150 lines)
- Delete sync infrastructure: skill_renderer, skill_detection, client_formats
- Simplify filesystem_registry.py
- Rewrite mount system: single skills/ scan replaces 4-dir scanning
- Delete .claude/skills/, plugins/, .gemini/skills/ adapted copies
- Delete augur.yaml plugin manifests
- Remove AUGUR-ADAPTED-COPY/AUGUR-STUB markers"
```

---

## Task 9: Fix Stale Path References

**Files:**
- Modify: Many files across the codebase

- [ ] **Step 1: Grep for `.claude/skills/` references**

```bash
grep -r '\.claude/skills/' --include="*.py" --include="*.ts" --include="*.md" --include="*.yaml" --include="*.json" . | grep -v node_modules | grep -v .git
```

Fix every reference to point to `skills/`.

- [ ] **Step 2: Grep for `plugins/` references (excluding `node_modules`, `.git`, `dist`)**

```bash
grep -r 'plugins/' --include="*.py" --include="*.ts" --include="*.md" . | grep -v node_modules | grep -v .git | grep -v dist | grep -v "npm\|pnpm\|package"
```

Fix or remove every reference.

- [ ] **Step 3: Grep for removed frontmatter field consumers**

```bash
grep -r 'x-augur-master\|x-augur-sync\|x-augur-origin' --include="*.py" --include="*.ts" .
```

Remove all consumers.

- [ ] **Step 4: Update CLAUDE.md**

Update the "Directory Layout" section to show `skills/` instead of `.claude/skills/` and `plugins/`.
Update the "Skills registry" line.
Update any other stale references.

- [ ] **Step 5: Update topic docs**

Read and update:
- `docs/agent-topics/ARCHITECTURE.md`
- `docs/agent-topics/SKILLS.md`
- `docs/agent-topics/WORKFLOWS.md`

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "fix: update all stale path references to skills/ directory

Fix .claude/skills/ → skills/ across Python, TypeScript, and docs.
Remove plugins/ references. Update CLAUDE.md and topic docs."
```

---

## Task 10: Add Dashboard Skills Browser

**Files:**
- Create: `apps/dashboard/app/api/skills/registry/route.ts`
- Create or modify: Dashboard page for skills browser (locate existing skills page first)

- [ ] **Step 1: Add skills registry to the catch-all MCP proxy config**

The dashboard uses a catch-all proxy route at `apps/dashboard/app/api/[...proxy]/route.ts`. Add `list-skills` with `include_external: true` to the proxy route config rather than creating a standalone route. Check the existing proxy config pattern:

```bash
grep -r "list-skills\|callMcpTool\|proxy.*config" --include="*.ts" apps/dashboard/app/api/ apps/dashboard/lib/
```

Follow the existing pattern for adding a new MCP tool to the proxy. The tool should pass `{ include_external: true }` as a static arg so the dashboard always gets the full unified skill list.

- [ ] **Step 2: Update the MCP `list-skills` tool to include origin/author fields**

The `list-skills` MCP tool needs to return the `origin`, `author`, `tier`, and `hub` fields from the new `discover_all_skills()`. Check the existing tool implementation and add these fields to the response.

- [ ] **Step 3: Verify dashboard builds and skills page works**

```bash
pnpm --filter dashboard build
```

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/app/api/skills/
git commit -m "feat: add skills registry API with multi-source discovery

GET /api/skills/registry returns unified skill list from skills/
and client caches with origin/author/tier/hub tagging."
```

---

## Task 11: Run Stub Generator and Validate

**Files:**
- Run: `scripts/generate_client_stubs.py`
- Verify: `.codex/prompts/`, `.cursor/rules/`

- [ ] **Step 1: Run stub generator**

```bash
python scripts/generate_client_stubs.py
```

Verify output shows correct counts.

- [ ] **Step 2: Verify generated stubs have AUGUR-GENERATED marker**

```bash
head -1 .codex/prompts/auto-lint.md
# Should show: <!-- AUGUR-GENERATED -->
```

- [ ] **Step 3: Commit generated stubs**

```bash
git add .codex/prompts/ .cursor/rules/ .github/copilot/
git commit -m "chore: generate client stubs from skills/ directory"
```

---

## Task 12: Full Validation

- [ ] **Step 1: Run dashboard build**

```bash
pnpm --filter dashboard build
```

Must succeed with no errors.

- [ ] **Step 2: Run test suite**

```bash
python -m pytest tests/ -v --timeout=60
pnpm --filter dashboard test
```

- [ ] **Step 3: Verify skill count**

```bash
find skills/ -maxdepth 2 -name "SKILL.md" | wc -l
```

Must match pre-migration count.

- [ ] **Step 4: Grep for any remaining stale paths**

```bash
grep -r '\.claude/skills/\|AUGUR-ADAPTED-COPY\|AUGUR-STUB\|x-augur-master\b\|x-augur-sync\b\|x-augur-origin\b' --include="*.py" --include="*.ts" . | grep -v node_modules | grep -v .git | grep -v dist
```

Must return empty.

- [ ] **Step 5: Verify discovery returns all skills**

```python
python -c "
from src.plugins.skill_discovery import discover_all_skills
skills = discover_all_skills()
augur = [s for s in skills if s.origin == 'augur']
print(f'Augur skills: {len(augur)}')
print(f'Total skills (all sources): {len(skills)}')
"
```

- [ ] **Step 6: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix: resolve validation issues from migration"
```

---

## Task 13: Update `/evolve` Skill and Write ADR

- [ ] **Step 1: Update `/evolve` to create skills in `skills/`**

```bash
grep -rn "\.claude/skills\|claude.*skills" --include="*.md" --include="*.py" skills/evolve/ skills/skill-creator/ 2>/dev/null || grep -rn "\.claude/skills" --include="*.md" --include="*.py" skills/*/
```

Find the scaffold path in the evolve/skill-creator skill and update from `.claude/skills/{name}/` to `skills/{name}/`. Add `x-augur-created-by: user` to the default frontmatter template.

**Verify:**
```bash
grep -rn "skills/" skills/evolve/ skills/skill-creator/ 2>/dev/null | grep -v node_modules
# Should show the new path, not .claude/skills/
```

- [ ] **Step 2: Update `/dev-sync` to invoke `generate_client_stubs.py`**

Find the dev-sync skill's SKILL.md and update it to invoke `scripts/generate_client_stubs.py` instead of the old sync pipeline.

- [ ] **Step 3: Write superseding ADR**

Run `/adr write` to create the canonical ADR. Reference this spec. Mark ADR-426 Phase 3-4, ADR-186, ADR-171 as superseded.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "docs: write ADR for multi-client skill structure refactor

Update /evolve and /dev-sync skills for new skills/ directory.
Supersedes ADR-426 Phase 3-4, ADR-186, ADR-171."
```
