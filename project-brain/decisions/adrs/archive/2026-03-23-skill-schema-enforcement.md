# Skill Schema Enforcement & Agents Migration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce the Agent Skills standard folder schema across 184 skills, migrate violations, move 15 agent files to `plugins/agents/`, and add pre-commit enforcement.

**Architecture:** Extend existing `validate_skill_structure.py` with new schema rules. Script-driven migration for bulk violations (74 `data/` dirs, 72 `augur/seed/` dirs, 7 `docs/` dirs). Agents move to `plugins/agents/` with stub generator sync to `.claude/agents/`.

**Tech Stack:** Python (validation, migration scripts), YAML (pre-commit config), Markdown (CLAUDE.md, agent files)

**Spec:** `docs/superpowers/specs/2026-03-23-skill-schema-enforcement-design.md`

---

## File Structure

### New Files

| File | Responsibility |
|------|---------------|
| `scripts/migrate_skill_dirs.py` | Bulk migration: rename docs→references, move data/, move augur/seed/ |
| `plugins/agents/` directory + 15 `.md` files | Canonical agent definitions (moved from `.claude/agents/`) |
| `plugins/agents/README.md` | Directory rules for agents |

### Modified Files

| File | What Changes |
|------|-------------|
| `.github/scripts/validate_skill_structure.py` (164 lines) | Add ALLOWED_ROOT_DIRS, BANNED_AUGUR_DIRS, dashboard extension checks, supersede `augur/data/` ban |
| `scripts/generate_client_stubs.py` | Add agent sync target (`.claude/agents/`) |
| `CLAUDE.md` (via `docs/agent-topics/agent-rules.md`) | Add skill folder schema rule |
| `skills/evolve/references/pipeline-steps.md` | Update scaffold to match schema |
| `skills/auto-skill-structure/SKILL.md` | Update checks to match new schema |

---

## Task 1: Write Migration Script for Bulk Directory Fixes

**Files:**
- Create: `scripts/migrate_skill_dirs.py`

- [ ] **Step 1: Write migration script**

Script handles three migrations:
1. `docs/` → `references/` (7 skills: apple, career, daemon, dev-loops, google-workspace, lifestyle, venture-augur)
2. `data/` at skill root → classify and handle (74 skills)
3. `augur/seed/` → `assets/seeds/` (72 skills)

```python
#!/usr/bin/env python3
"""Migrate non-standard skill directories to schema-compliant locations.

Usage:
    python scripts/migrate_skill_dirs.py --dry-run
    python scripts/migrate_skill_dirs.py
"""
import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config.paths import get_project_root, get_skills_dir

SKILLS_DIR = get_skills_dir()


def migrate_docs_to_references(dry_run: bool) -> int:
    """Rename docs/ to references/ at skill root."""
    count = 0
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        docs = skill_dir / "docs"
        refs = skill_dir / "references"
        if not docs.is_dir():
            continue
        if refs.is_dir():
            # Merge: move docs/* into references/
            print(f"  MERGE {skill_dir.name}/docs/* → references/")
            if not dry_run:
                for item in docs.iterdir():
                    dest = refs / item.name
                    if dest.exists():
                        print(f"    SKIP {item.name} (already exists in references/)")
                        continue
                    shutil.move(str(item), str(dest))
                docs.rmdir()
        else:
            print(f"  RENAME {skill_dir.name}/docs → references")
            if not dry_run:
                docs.rename(refs)
        count += 1
    return count


def migrate_data_at_root(dry_run: bool) -> int:
    """Handle data/ at skill root. Delete empty, move non-empty to assets/."""
    count = 0
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        data = skill_dir / "data"
        if not data.is_dir():
            continue
        # Check if inside augur/ (skip those)
        if "augur" in data.parts:
            continue
        files = list(data.rglob("*"))
        real_files = [f for f in files if f.is_file() and f.name != ".gitkeep"]
        if not real_files:
            print(f"  DELETE {skill_dir.name}/data (empty)")
            if not dry_run:
                shutil.rmtree(data)
        else:
            dest = skill_dir / "assets"
            print(f"  MOVE {skill_dir.name}/data → assets/ ({len(real_files)} files)")
            if not dry_run:
                dest.mkdir(exist_ok=True)
                for item in data.iterdir():
                    if item.name == ".gitkeep":
                        continue
                    target = dest / item.name
                    shutil.move(str(item), str(target))
                shutil.rmtree(data)
        count += 1
    return count


def migrate_augur_seed(dry_run: bool) -> int:
    """Move augur/seed/ to assets/seeds/."""
    count = 0
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        seed = skill_dir / "augur" / "seed"
        if not seed.is_dir():
            continue
        dest = skill_dir / "assets" / "seeds"
        print(f"  MOVE {skill_dir.name}/augur/seed → assets/seeds/")
        if not dry_run:
            dest.parent.mkdir(exist_ok=True)
            if dest.exists():
                # Merge
                for item in seed.iterdir():
                    target = dest / item.name
                    if not target.exists():
                        shutil.move(str(item), str(target))
                shutil.rmtree(seed)
            else:
                shutil.move(str(seed), str(dest))
        count += 1
    return count


def main():
    parser = argparse.ArgumentParser(description="Migrate skill dirs to schema")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("=== docs/ → references/ ===")
    c1 = migrate_docs_to_references(args.dry_run)
    print(f"  Total: {c1}\n")

    print("=== data/ at root → delete empty / move to assets/ ===")
    c2 = migrate_data_at_root(args.dry_run)
    print(f"  Total: {c2}\n")

    print("=== augur/seed/ → assets/seeds/ ===")
    c3 = migrate_augur_seed(args.dry_run)
    print(f"  Total: {c3}\n")

    print(f"Grand total: {c1 + c2 + c3} migrations")
    if args.dry_run:
        print("(dry-run — no changes made)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run dry-run**

```bash
python scripts/migrate_skill_dirs.py --dry-run
```

Verify counts: ~7 docs, ~74 data, ~72 seed.

- [ ] **Step 3: Execute migration**

```bash
python scripts/migrate_skill_dirs.py
```

- [ ] **Step 4: Handle ai_bridge/lib/ manually**

```bash
ls skills/ai_bridge/lib/
ls skills/ai_bridge/augur/lib/
```

Read the files in `skills/ai_bridge/lib/`. If portable (standalone utility) → move to `scripts/`. If Augur-internal → merge into `augur/lib/`.

- [ ] **Step 5: Delete enterprise .augur-plugin/**

```bash
rm -rf skills/enterprise/.augur-plugin/
```

- [ ] **Step 6: Validate no violations remain**

```bash
echo "docs at root:" && find skills/ -maxdepth 2 -name "docs" -type d | grep -v augur | wc -l
echo "data at root:" && find skills/ -maxdepth 2 -name "data" -type d | grep -v augur | wc -l
echo "augur/seed:" && find skills/ -path "*/augur/seed" -type d | wc -l
echo "lib at root:" && find skills/ -maxdepth 2 -name "lib" -type d | grep -v augur | wc -l
```

All should be 0.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor: migrate skill directories to schema-compliant structure

- docs/ → references/ (7 skills)
- data/ at root → deleted empty, moved non-empty to assets/ (74 skills)
- augur/seed/ → assets/seeds/ (72 skills)
- ai_bridge/lib/ classified and moved
- enterprise/.augur-plugin/ deleted"
```

---

## Task 2: Update Pre-Commit Hook

**Files:**
- Modify: `.github/scripts/validate_skill_structure.py`

- [ ] **Step 1: Read current file**

```bash
wc -l .github/scripts/validate_skill_structure.py
```

- [ ] **Step 2: Add schema enforcement constants and checks**

Add after existing BANNED_PATTERNS:

```python
# Schema enforcement (ADR-479, agentskills.io standard)
ALLOWED_ROOT_DIRS = {
    "commands", "references", "scripts", "assets",
    "examples", "modules", "augur",
}

BANNED_ROOT_DIRS = {
    "docs", "data", "lib",
    ".augur-plugin", "node_modules", "__pycache__",
}

BANNED_AUGUR_DIRS = {
    "seed",  # moved to assets/seeds/
}

DASHBOARD_ALLOWED_EXTENSIONS = {
    ".tsx", ".ts", ".css", ".js", ".jsx",
}

DASHBOARD_EXCEPTIONS = {
    "tsconfig.json",
}
```

Add new check function:

```python
def check_schema_compliance(file_path: str) -> list[str]:
    """Check file path against skill folder schema."""
    violations = []
    parts = Path(file_path).parts
    # Must be skills/{name}/...
    if len(parts) < 3 or parts[0] != "skills":
        return []
    skill_name = parts[1]

    if len(parts) >= 3:
        subdir = parts[2]
        # Check banned root dirs
        if subdir in BANNED_ROOT_DIRS:
            violations.append(
                f"skills/{skill_name}/{subdir}/ is banned at skill root. "
                f"Use references/ (not docs/), augur/data/ (not data/), "
                f"scripts/ or augur/lib/ (not lib/)."
            )

    if len(parts) >= 4 and parts[2] == "augur":
        augur_subdir = parts[3]
        if augur_subdir in BANNED_AUGUR_DIRS:
            violations.append(
                f"skills/{skill_name}/augur/{augur_subdir}/ is banned. "
                f"Use assets/seeds/ instead of augur/seed/."
            )
        # Dashboard extension check
        if augur_subdir == "dashboard" and len(parts) >= 5:
            filename = parts[-1]
            ext = Path(filename).suffix
            if ext and ext not in DASHBOARD_ALLOWED_EXTENSIONS:
                if filename not in DASHBOARD_EXCEPTIONS:
                    violations.append(
                        f"skills/{skill_name}/augur/dashboard/ allows only "
                        f"{', '.join(DASHBOARD_ALLOWED_EXTENSIONS)} files. "
                        f"Found: {filename}"
                    )
    return violations
```

Update `main()` to call the new check alongside existing checks.

**CRITICAL:** Remove or comment out the existing `augur/data/` ban in BANNED_PATTERNS (line ~51) since `augur/data/` is now allowed for runtime config. Add a comment explaining the supersession.

- [ ] **Step 3: Test with a fake violation**

```bash
mkdir -p /tmp/test-skill/docs
echo "test" > /tmp/test-skill/docs/README.md
python .github/scripts/validate_skill_structure.py skills/test-skill/docs/README.md
echo $?  # Should be 1 (blocked)
rm -rf /tmp/test-skill
```

- [ ] **Step 4: Commit**

```bash
git add .github/scripts/validate_skill_structure.py
git commit -m "feat: enforce skill folder schema in pre-commit hook

Add ALLOWED_ROOT_DIRS, BANNED_ROOT_DIRS, BANNED_AUGUR_DIRS.
Check dashboard/ file extensions.
Supersede old augur/data/ ban (now allowed for runtime config).
Extends existing validate_skill_structure.py (ADR-430)."
```

---

## Task 3: Migrate Agents to Project Root

**Files:**
- Create: `agents/` directory + 15 files
- Create: `agents/README.md`
- Modify: `scripts/generate_client_stubs.py`

- [ ] **Step 1: Create agents/ directory and move files**

```bash
mkdir -p agents
cp .claude/agents/*.md agents/
cp .claude/agents/registry.json agents/
```

- [ ] **Step 2: Create agents/README.md**

```markdown
# Agents

Canonical source for Augur subagent definitions.

Per Claude Code convention, agents are `.md` files with YAML frontmatter
defining name, description, tools, model, and system prompt.

## Sync

The stub generator (`scripts/generate_client_stubs.py`) copies these
to `.claude/agents/` with an `<!-- AUGUR-GENERATED -->` marker.
User-created agents in `.claude/agents/` without the marker are preserved.

## See Also

- [Claude Code Subagents](https://code.claude.com/docs/en/sub-agents)
- [Plugin Agents](https://code.claude.com/docs/en/plugins)
```

- [ ] **Step 3: Add agent sync to stub generator**

Read `scripts/generate_client_stubs.py`. Add a new function `sync_agents()`:

```python
AGENTS_SOURCE = project_root / "agents"
AGENTS_TARGET = project_root / ".claude" / "agents"

def sync_agents(dry_run: bool = False) -> tuple[int, int]:
    """Copy agents/ to .claude/agents/ with AUGUR-GENERATED marker."""
    if not AGENTS_SOURCE.exists():
        return 0, 0
    AGENTS_TARGET.mkdir(parents=True, exist_ok=True)

    generated = 0
    for agent_file in sorted(AGENTS_SOURCE.glob("*.md")):
        content = agent_file.read_text(encoding="utf-8")
        marked = f"{MARKER}\n{content}"
        target = AGENTS_TARGET / agent_file.name
        if not dry_run:
            target.write_text(marked, encoding="utf-8")
        generated += 1

    # Also copy registry.json if it exists
    registry = AGENTS_SOURCE / "registry.json"
    if registry.exists():
        target = AGENTS_TARGET / "registry.json"
        if not dry_run:
            content = registry.read_text(encoding="utf-8")
            target.write_text(f"{MARKER}\n{content}", encoding="utf-8")
        generated += 1

    # Cleanup stale agents
    deleted = 0
    source_names = {f.name for f in AGENTS_SOURCE.iterdir()}
    for f in AGENTS_TARGET.iterdir():
        if not is_generated(f):
            continue
        if f.name not in source_names:
            if not dry_run:
                f.unlink()
            deleted += 1

    return generated, deleted
```

Call `sync_agents()` from `main()` after `generate_stubs()` and `cleanup_stale_stubs()`.

- [ ] **Step 4: Run stub generator to sync agents**

```bash
python scripts/generate_client_stubs.py
```

Verify `.claude/agents/` now has `AUGUR-GENERATED` markers:

```bash
head -1 .claude/agents/advisor.md
# Should show: <!-- AUGUR-GENERATED -->
```

- [ ] **Step 5: Commit**

```bash
git add agents/ .claude/agents/ scripts/generate_client_stubs.py
git commit -m "feat: migrate agents to project root with stub sync

Move 15 agent files from .claude/agents/ to agents/ at project root.
Stub generator syncs back to .claude/agents/ with AUGUR-GENERATED marker.
Add agents/README.md per CLAUDE.md rule 6."
```

---

## Task 4: Update CLAUDE.md and Topic Docs

**Files:**
- Modify: `docs/agent-topics/agent-rules.md` (source of truth for CLAUDE.md)

- [ ] **Step 1: Add skill schema rule to agent-rules.md**

Add after existing rule 18 (or as a new numbered rule):

```markdown
19. **Skill folder schema** — Skills follow the [Agent Skills standard](https://agentskills.io/specification). Standard dirs at skill root (`commands/`, `references/`, `scripts/`, `assets/`, `examples/`, `modules/`) are portable across AI clients. Augur-specific content goes in `augur/` (`dashboard/`, `data/`, `tests/`, `lib/`). Banned at root: `docs/` (use `references/`), `data/` (use `augur/data/` or `assets/`), `lib/` (use `scripts/` or `augur/lib/`). Dashboard pages (`augur/dashboard/`) allow only `.tsx/.ts/.css/.js/.jsx`. Seeds belong in `assets/seeds/`, not `augur/seed/`. Pre-commit hook enforces this.
```

- [ ] **Step 2: Update directory layout in agent-rules.md**

Add `agents/` to the directory layout:

```
augur/
├── src/              # CORE — Python config, scripts, Next.js dashboard
├── skills/           # SKILLS — all skills at project root (ADR-479)
├── plugins/          # PLUGINS — platform integrations + subagent definitions
├── config/           # CONFIG — agents, dashboard, system, integrations
└── docs/             # DOCS — decisions/, references/, guides/
```

- [ ] **Step 3: Commit**

```bash
git add docs/agent-topics/agent-rules.md
git commit -m "docs: add skill folder schema rule and agents/ to CLAUDE.md layout"
```

---

## Task 5: Update /evolve and auto-skill-structure

**Files:**
- Modify: `skills/evolve/references/pipeline-steps.md`
- Modify: `skills/auto-skill-structure/SKILL.md`

- [ ] **Step 1: Update /evolve scaffold**

Read `skills/evolve/references/pipeline-steps.md`. In the SCAFFOLD section, ensure:
- No `augur/seed/` is scaffolded (use `assets/seeds/` instead)
- No `docs/` is scaffolded (use `references/` — already correct)
- No `data/` at skill root (use `augur/data/` for native, `assets/` for portable)
- `domain` type scaffold includes `assets/seeds/` not `augur/seed/`

- [ ] **Step 2: Update auto-skill-structure checks**

Read `skills/auto-skill-structure/SKILL.md`. Update to match the new schema:
- Add `BANNED_ROOT_DIRS` check (docs, data, lib at skill root)
- Add `BANNED_AUGUR_DIRS` check (seed inside augur)
- Add dashboard extension check
- Supersede old `augur/data/` ban with clarification
- Add evolution gap for non-standard dirs that exist but aren't banned

- [ ] **Step 3: Commit**

```bash
git add skills/evolve/ skills/auto-skill-structure/
git commit -m "fix: update /evolve scaffold and auto-skill-structure for schema

/evolve: scaffold assets/seeds/ not augur/seed/, no data/ at root.
auto-skill-structure: add banned root/augur dir checks, dashboard
extension validation, supersede augur/data/ ban."
```

---

## Task 6: Validate Everything

- [ ] **Step 1: Run schema validation across all skills**

```bash
find skills/ -type f -path "skills/*" | python .github/scripts/validate_skill_structure.py
```

Should report 0 blocking violations (all violations were migrated in Task 1).

- [ ] **Step 2: Verify agents discoverable**

```bash
ls agents/*.md | wc -l   # Should be 15 (14 agents + README excluded)
head -1 .claude/agents/advisor.md   # Should show AUGUR-GENERATED marker
```

- [ ] **Step 3: Verify no remaining banned dirs**

```bash
echo "docs:" && find skills/ -maxdepth 2 -name "docs" -type d | grep -v augur | wc -l
echo "data:" && find skills/ -maxdepth 2 -name "data" -type d | grep -v augur | wc -l
echo "lib:" && find skills/ -maxdepth 2 -name "lib" -type d | grep -v augur | wc -l
echo "seed:" && find skills/ -path "*/augur/seed" -type d | wc -l
```

All should be 0.

- [ ] **Step 4: Run stub generator to verify agents sync**

```bash
python scripts/generate_client_stubs.py
```

- [ ] **Step 5: Final commit if fixes needed**

```bash
git add -A && git commit -m "fix: resolve validation issues" || echo "Nothing to commit"
```
