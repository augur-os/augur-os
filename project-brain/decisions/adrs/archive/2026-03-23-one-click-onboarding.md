# One-Click Onboarding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Augur installable from any AI agent via a single copy-paste prompt, with a portable skills pack that gives agents persistent memory.

**Architecture:** A build script assembles portable skills (filtered by `x-augur-portable: true`) into `dist/skills-pack/`. A universal install prompt auto-detects the agent platform and either installs the pack or runs full system install. `SkillDataStore` gets a one-line change to write to seeds dir when no vault is configured.

**Tech Stack:** Python 3.11+ (build script, SkillDataStore), Bash (install.sh migration), GitHub Actions (CI), Markdown (install prompt, skill updates)

**Spec:** `docs/superpowers/specs/2026-03-23-one-click-onboarding-design.md`
**ADR:** `docs/superpowers/specs/2026-03-23-native-file-ops-for-skills-design.md`

---

## File Structure

### New files

| File | Responsibility |
|---|---|
| `scripts/build_skills_pack.py` | Scan skills for `x-augur-portable: true`, copy into `dist/skills-pack/`, strip non-portable dirs, append upgrade footers |
| `tests/test_build_skills_pack.py` | Unit tests for build script — filtering, stripping, footer appending |
| `.github/workflows/build-skills-pack.yml` | CI workflow — build pack on release tags, push to `skills-pack` branch |
| `skills/augur-upgrade/SKILL.md` | Upgrade skill — detects platform, runs full installer |
| `skills/augur-upgrade/assets/seeds/_seed.yaml` | Minimal seed manifest for upgrade skill |
| `dist/skills-pack/install.md` | Universal install prompt (source copy — build script copies this into the output) |

### Modified files

| File | Change |
|---|---|
| `src/mcp/plugin_utils.py:123-131` | `_resolve_data_dir()` — return `assets_seed_dir` when no vault configured |
| `tests/test_plugin_utils.py` (or create) | Test for standalone mode path resolution |
| `skills/reading-list/SKILL.md` | Add `x-augur-portable: true`, `x-augur-upgrade-hook` |
| `skills/books/SKILL.md` | Add `x-augur-portable: true`, `x-augur-upgrade-hook` |
| `skills/career/SKILL.md` | Add `x-augur-portable: true`, `x-augur-upgrade-hook`, add Data Location section |
| `skills/interview-coach/SKILL.md` | Add `x-augur-portable: true`, `x-augur-upgrade-hook`, add Data Location section |
| `skills/content/SKILL.md` | Add `x-augur-portable: true`, `x-augur-upgrade-hook`, add Data Location section |
| `skills/health/SKILL.md` | Add `x-augur-portable: true`, `x-augur-upgrade-hook`, add Data Location section |
| `skills/finance/SKILL.md` | Add `x-augur-portable: true`, `x-augur-upgrade-hook`, add Data Location section |
| `scripts/install.sh` | Add seed-to-vault migration function for upgrades |

---

## Task 1: SkillDataStore Standalone Mode

**Files:**
- Modify: `src/mcp/plugin_utils.py:123-131`
- Test: `tests/test_skill_data_store_standalone.py`

- [ ] **Step 1: Write failing test for standalone path resolution**

```python
# tests/test_skill_data_store_standalone.py
import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Dynamic import to avoid src.config dependency issues
_utils_path = Path(__file__).resolve().parent.parent / "src" / "mcp" / "plugin_utils.py"
_spec = importlib.util.spec_from_file_location("plugin_utils", _utils_path)
_mod = importlib.util.module_from_spec(_spec)

# Mock the config import that will fail in test env
sys.modules["src.config.paths"] = MagicMock()
_spec.loader.exec_module(_mod)

SkillDataStore = _mod.SkillDataStore


def test_resolve_data_dir_falls_back_to_seeds_when_no_vault(tmp_path):
    """When get_skill_data_dir raises (no vault configured), use assets/seeds/."""
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    seeds_dir = skill_dir / "assets" / "seeds"
    seeds_dir.mkdir(parents=True)

    _paths_mock = sys.modules["src.config.paths"]
    _paths_mock.get_skill_data_dir = MagicMock(side_effect=Exception("no vault"))
    store = SkillDataStore(skill_dir)
    assert store.data_dir == seeds_dir


def test_resolve_data_dir_uses_vault_when_available(tmp_path):
    """When vault is configured, use the vault path."""
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    vault_data = tmp_path / "vault" / "my-skill"
    vault_data.mkdir(parents=True)

    _paths_mock = sys.modules["src.config.paths"]
    _paths_mock.get_skill_data_dir = MagicMock(return_value=vault_data)
    store = SkillDataStore(skill_dir)
    assert store.data_dir == vault_data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_skill_data_store_standalone.py -v`
Expected: FAIL — `_resolve_data_dir()` currently falls back to `self.skill_path / "data"`, not `assets/seeds/`

- [ ] **Step 3: Modify `_resolve_data_dir()` to fall back to seeds**

In `src/mcp/plugin_utils.py`, find the `_resolve_data_dir` method (lines 123-131). Change the fallback from `self.skill_path / "data"` to `self.assets_seed_dir`:

```python
def _resolve_data_dir(self) -> Path:
    """Resolve the data directory — vault first, seeds fallback."""
    try:
        from src.config.paths import get_skill_data_dir
        return get_skill_data_dir(self.skill_path.name)
    except Exception:
        # Standalone mode: no vault configured, use seeds as working dir
        return self.assets_seed_dir
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_skill_data_store_standalone.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/mcp/plugin_utils.py tests/test_skill_data_store_standalone.py
git commit -m "feat(data): SkillDataStore falls back to assets/seeds/ when no vault configured"
```

---

## Task 2: Create augur-upgrade Skill

**Files:**
- Create: `skills/augur-upgrade/SKILL.md`
- Create: `skills/augur-upgrade/assets/seeds/_seed.yaml`

- [ ] **Step 1: Create the SKILL.md**

```markdown
---
name: augur-upgrade
description: Upgrade from Augur skills pack to the full Augur system. Use when the user wants the dashboard, knowledge base, integrations, or any feature that requires the full system.
x-augur-type: command
x-augur-visibility: core
x-augur-hub: command
x-augur-tab: system
x-augur-portable: true
---

# /augur-upgrade

Upgrade from the Augur skills pack to the full system.

## Step 1: Check if already installed

```bash
ls ~/Projects/Augur/scripts/install.sh 2>/dev/null || ls ${AUGUR_DIR:-~/Projects/augur}/scripts/install.sh 2>/dev/null
```

If found, tell the user: "Full Augur is already installed. Run `/onboard --status` to check your setup."
Stop here.

## Step 2: Confirm with the user

Show this message:

---

Ready to install the full Augur system. This adds:

- Your skills learn from each other and remember what you care about
- A personal knowledge base that grows with you — searchable across everything you've ever saved
- A visual dashboard for tracking career, finances, reading, health
- Connects to Obsidian, Apple Notes, Google Workspace, and your IDE
- Background agents that organize, improve, and maintain your system while you're away

Setup takes ~3 minutes. Proceed? (y/n)

---

Wait for confirmation. If no, stop.

## Step 3: Detect platform

Determine which AI agent/IDE you are running in:

| Check | Platform |
|-------|----------|
| You are Claude Code or `~/.claude/` exists | claude-code |
| You are Codex or `~/.codex/` exists | codex |
| You are Gemini CLI or `~/.gemini/` exists | gemini |
| `~/.cursor/` or `~/Library/Application Support/Cursor/` exists | cursor |
| `~/.codeium/windsurf/` exists | windsurf |
| `~/.opencode/` exists | opencode |
| `~/Library/Application Support/Cline/` exists | cline |
| You are running inside VS Code | vscode |
| You are running inside Antigravity | antigravity |

If multiple match, prefer the one you are actually running inside.
If none match, ask the user.

## Step 4: Run installer

```bash
curl -fsSL https://raw.githubusercontent.com/augur-os/augur-os/main/scripts/install.sh | bash -s -- --from <PLATFORM>
```

## Step 5: Post-install

Tell the user:

"Augur is installed. Your existing skill data has been preserved. Restart your session to activate MCP tools, then run `/commands` to see everything available."
```

- [ ] **Step 2: Create the seed manifest**

```yaml
# skills/augur-upgrade/assets/seeds/_seed.yaml
data_path: ''
directories: []
files: []
```

- [ ] **Step 3: Verify skill structure**

Run: `ls -la skills/augur-upgrade/` and `ls -la skills/augur-upgrade/assets/seeds/`
Expected: SKILL.md and _seed.yaml in correct locations

- [ ] **Step 4: Commit**

```bash
git add skills/augur-upgrade/
git commit -m "feat(onboard): create augur-upgrade skill for skills-pack-to-full-system upgrade"
```

---

## Task 3: Create books seed manifest

**Files:**
- Create: `skills/books/assets/seeds/_seed.yaml`

The books skill has `assets/seeds/prompts/` but no `_seed.yaml` manifest. The build script and migration both rely on it.

- [ ] **Step 1: Check existing seed structure**

Run: `ls -la skills/books/assets/seeds/`
Expected: `prompts/` directory exists but no `_seed.yaml`

- [ ] **Step 2: Create _seed.yaml**

```yaml
# skills/books/assets/seeds/_seed.yaml
data_path: ''
directories:
  - prompts/
files: []
```

- [ ] **Step 3: Commit**

```bash
git add skills/books/assets/seeds/_seed.yaml
git commit -m "fix(books): add missing _seed.yaml manifest"
```

---

## Task 4: Add Portability Frontmatter to 7 Skills

**Files:**
- Modify: `skills/reading-list/SKILL.md`
- Modify: `skills/books/SKILL.md`
- Modify: `skills/career/SKILL.md`
- Modify: `skills/interview-coach/SKILL.md`
- Modify: `skills/content/SKILL.md`
- Modify: `skills/health/SKILL.md`
- Modify: `skills/finance/SKILL.md`

For each skill, add two frontmatter fields and a Data Location section. The upgrade hook message is specific to each skill.

- [ ] **Step 1: Update reading-list/SKILL.md frontmatter**

Add to YAML frontmatter (after existing `x-augur-*` fields):

```yaml
x-augur-portable: true
x-augur-upgrade-hook: "your reading list connects to your knowledge base and is searchable across everything you've saved"
```

Add Data Location section after the existing description/usage sections:

```markdown
## Data Location

This skill stores data in `assets/seeds/` within this skill folder.
If Augur is fully installed, data may also be at the vault path — prefer that if it exists.
```

- [ ] **Step 2: Update books/SKILL.md frontmatter**

```yaml
x-augur-portable: true
x-augur-upgrade-hook: "your book notes connect to your knowledge base and are searchable across all your saved content"
```

Add the same Data Location section.

- [ ] **Step 3: Update career/SKILL.md frontmatter**

```yaml
x-augur-portable: true
x-augur-upgrade-hook: "your career pipeline connects to interview prep, calendar, Apple Reminders, and your knowledge base"
```

Add Data Location section. Also add a standalone degradation note in the SKILL.md body near any `knowledge` or `ai_bridge` references:

```markdown
> **Note:** Knowledge search and AI bridge features require the full Augur system.
> In standalone mode, this skill tracks your data via local files.
> Run `/augur-upgrade` for the full integrated experience.
```

- [ ] **Step 4: Update interview-coach/SKILL.md frontmatter**

```yaml
x-augur-portable: true
x-augur-upgrade-hook: "interview prep connects to your career pipeline, syncs with your calendar, and searches your knowledge base for relevant experience"
```

Add Data Location section and standalone degradation note (same pattern as career).

- [ ] **Step 5: Update content/SKILL.md frontmatter**

```yaml
x-augur-portable: true
x-augur-upgrade-hook: "your content calendar connects to LinkedIn, channels, and your knowledge base for research-backed writing"
```

Add Data Location section and standalone degradation note.

- [ ] **Step 6: Update health/SKILL.md frontmatter**

```yaml
x-augur-portable: true
x-augur-upgrade-hook: "health tracking connects to Apple Health, wearables, and your knowledge base for medical history search"
```

Add Data Location section and standalone degradation note.

- [ ] **Step 7: Update finance/SKILL.md frontmatter**

```yaml
x-augur-portable: true
x-augur-upgrade-hook: "financial tracking connects to Google Sheets, your knowledge base, and the visual dashboard for portfolio monitoring"
```

Add Data Location section and standalone degradation note.

- [ ] **Step 8: Verify all frontmatter**

Run: `grep -l 'x-augur-portable: true' skills/*/SKILL.md`
Expected: 8 results (7 skills + augur-upgrade)

- [ ] **Step 9: Commit**

```bash
git add skills/reading-list/SKILL.md skills/books/SKILL.md skills/career/SKILL.md skills/interview-coach/SKILL.md skills/content/SKILL.md skills/health/SKILL.md skills/finance/SKILL.md
git commit -m "feat(onboard): add x-augur-portable and upgrade hooks to 7 pack skills"
```

---

## Task 5: Create Universal Install Prompt

**Files:**
- Create: `skills/onboard/install.md`

This is the source file. The build script copies it into `dist/skills-pack/install.md`.

- [ ] **Step 1: Write install.md**

Create `skills/onboard/install.md` with the full universal prompt. Reference the spec section "The Universal Install Prompt" (`docs/superpowers/specs/2026-03-23-one-click-onboarding-design.md` lines 32-103) for the exact content. The prompt must include:

1. Platform detection table (9 platforms)
2. Welcome message with skills-only vs full system choice
3. Skills-only install path with per-platform target directories
4. Full system install path with `curl | bash --from <PLATFORM>`
5. Platform-specific config steps (codex config.toml, opencode config.json)
6. Confirmation messages for both paths

- [ ] **Step 2: Verify the prompt reads correctly as agent instructions**

Read `skills/onboard/install.md` end-to-end. Check:
- Every step is an instruction the agent can execute
- No ambiguity in platform detection
- Shell commands are correct (especially `git clone --branch skills-pack`)
- Target directories match the spec table exactly

- [ ] **Step 3: Commit**

```bash
git add skills/onboard/install.md
git commit -m "feat(onboard): create universal install prompt for all AI agent platforms"
```

---

## Task 6: Build Skills Pack Script

**Files:**
- Create: `scripts/build_skills_pack.py`
- Create: `tests/test_build_skills_pack.py`

- [ ] **Step 1: Write failing tests for the build script**

```python
# tests/test_build_skills_pack.py
import json
import shutil
import textwrap
from pathlib import Path
from unittest.mock import patch

import importlib.util
import sys

_scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
_spec = importlib.util.spec_from_file_location(
    "build_skills_pack", _scripts_dir / "build_skills_pack.py"
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["build_skills_pack"] = _mod
_spec.loader.exec_module(_mod)


def _make_skill(skills_dir: Path, name: str, portable: bool, upgrade_hook: str = "test hook"):
    """Helper to create a minimal skill directory for testing."""
    skill_dir = skills_dir / name
    skill_dir.mkdir(parents=True)
    frontmatter = f"""---
name: {name}
description: Test skill
x-augur-portable: {str(portable).lower()}
x-augur-upgrade-hook: "{upgrade_hook}"
---

# /{name}

Test instructions.
"""
    (skill_dir / "SKILL.md").write_text(frontmatter)
    # Create dirs that should be kept
    (skill_dir / "commands").mkdir()
    (skill_dir / "references").mkdir()
    (skill_dir / "assets" / "seeds").mkdir(parents=True)
    # Create dirs that should be stripped
    (skill_dir / "augur" / "dashboard").mkdir(parents=True)
    (skill_dir / "scripts" / "mcp").mkdir(parents=True)
    return skill_dir


def test_scan_finds_only_portable_skills(tmp_path):
    """Only skills with x-augur-portable: true are included."""
    skills_dir = tmp_path / "skills"
    _make_skill(skills_dir, "portable-skill", portable=True)
    _make_skill(skills_dir, "non-portable-skill", portable=False)

    result = _mod.scan_portable_skills(skills_dir)
    names = [s["name"] for s in result]
    assert "portable-skill" in names
    assert "non-portable-skill" not in names


def test_strip_removes_augur_and_mcp_dirs(tmp_path):
    """augur/ and scripts/mcp/ are removed from the output."""
    skills_dir = tmp_path / "skills"
    skill = _make_skill(skills_dir, "test-skill", portable=True)
    output_dir = tmp_path / "output"

    _mod.copy_and_strip_skill(skill, output_dir / "test-skill")

    assert (output_dir / "test-skill" / "SKILL.md").exists()
    assert (output_dir / "test-skill" / "commands").exists()
    assert (output_dir / "test-skill" / "assets" / "seeds").exists()
    assert not (output_dir / "test-skill" / "augur").exists()
    assert not (output_dir / "test-skill" / "scripts" / "mcp").exists()


def test_upgrade_footer_appended(tmp_path):
    """Build appends the upgrade footer using x-augur-upgrade-hook."""
    skills_dir = tmp_path / "skills"
    _make_skill(skills_dir, "my-skill", portable=True, upgrade_hook="everything connects")
    output_dir = tmp_path / "output"

    _mod.copy_and_strip_skill(skills_dir / "my-skill", output_dir / "my-skill")
    _mod.append_upgrade_footer(output_dir / "my-skill" / "SKILL.md", "everything connects")

    content = (output_dir / "my-skill" / "SKILL.md").read_text()
    assert "https://augur.run" in content
    assert "everything connects" in content
    assert "/augur-upgrade" in content


def test_dependency_fields_stripped(tmp_path):
    """x-augur-dependencies and x-augur-requires-platform are stripped from portable output."""
    skills_dir = tmp_path / "skills"
    skill_dir = skills_dir / "dep-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: dep-skill\ndescription: Test\nx-augur-portable: true\nx-augur-upgrade-hook: \"test\"\nx-augur-requires-platform: true\nx-augur-dependencies:\n  required:\n  - knowledge\n---\n\n# /dep-skill\n")

    output_dir = tmp_path / "output"
    _mod.copy_and_strip_skill(skill_dir, output_dir / "dep-skill")
    _mod.strip_non_portable_frontmatter(output_dir / "dep-skill" / "SKILL.md")

    content = (output_dir / "dep-skill" / "SKILL.md").read_text()
    assert "x-augur-requires-platform" not in content
    assert "x-augur-dependencies" not in content
    assert "knowledge" not in content
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_build_skills_pack.py -v`
Expected: FAIL — module not found or functions not defined

- [ ] **Step 3: Implement build_skills_pack.py**

```python
#!/usr/bin/env python3
"""Build the portable Augur skills pack from skills/ directory.

Scans for skills with x-augur-portable: true, copies them to dist/skills-pack/,
strips non-portable directories, appends upgrade footers, and generates a manifest.

Usage:
    python scripts/build_skills_pack.py [--skills-dir SKILLS_DIR] [--output-dir OUTPUT_DIR]
"""
from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

# Dirs to keep in the portable pack (per agentskills.io spec)
PORTABLE_DIRS = {"commands", "references", "assets", "examples"}
# Dirs to always strip
STRIP_DIRS = {"augur"}
# Subdirs within scripts/ to strip
STRIP_SCRIPT_SUBDIRS = {"mcp"}

UPGRADE_FOOTER_TEMPLATE = """
---
> This skill is part of [Augur](https://augur.run). With the full system,
> {hook}. Run `/augur-upgrade` to install.
"""

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def parse_frontmatter(skill_md: Path) -> dict:
    """Extract YAML frontmatter from a SKILL.md file as a dict."""
    text = skill_md.read_text()
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return {}
    # Simple YAML parsing — handles flat keys and nested blocks
    result = {}
    current_key = None
    for line in match.group(1).splitlines():
        if line.startswith("  "):
            continue  # Skip nested values for simple parsing
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if value:
                # Handle booleans
                if value.lower() == "true":
                    result[key] = True
                elif value.lower() == "false":
                    result[key] = False
                else:
                    result[key] = value.strip("'\"")
            current_key = key
    return result


def scan_portable_skills(skills_dir: Path) -> list[dict]:
    """Find all skills with x-augur-portable: true."""
    portable = []
    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue
        fm = parse_frontmatter(skill_md)
        if fm.get("x-augur-portable") is True:
            portable.append({
                "name": fm.get("name", skill_dir.name),
                "path": skill_dir,
                "upgrade_hook": fm.get("x-augur-upgrade-hook", ""),
            })
    return portable


def copy_and_strip_skill(src: Path, dst: Path) -> None:
    """Copy a skill directory, stripping non-portable content."""
    dst.mkdir(parents=True, exist_ok=True)

    for item in src.iterdir():
        if item.name in STRIP_DIRS:
            continue
        if item.is_dir():
            if item.name == "scripts":
                # Copy scripts/ but strip scripts/mcp/
                scripts_dst = dst / "scripts"
                shutil.copytree(item, scripts_dst, dirs_exist_ok=True)
                for sub in STRIP_SCRIPT_SUBDIRS:
                    strip_path = scripts_dst / sub
                    if strip_path.exists():
                        shutil.rmtree(strip_path)
            else:
                shutil.copytree(item, dst / item.name, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dst / item.name)


def append_upgrade_footer(skill_md: Path, hook: str) -> None:
    """Append the upgrade footer to a SKILL.md file."""
    if not hook:
        return
    content = skill_md.read_text()
    footer = UPGRADE_FOOTER_TEMPLATE.format(hook=hook)
    skill_md.write_text(content.rstrip() + "\n" + footer)


def strip_non_portable_frontmatter(skill_md: Path) -> None:
    """Remove x-augur-dependencies and x-augur-requires-platform from frontmatter."""
    text = skill_md.read_text()
    # Remove x-augur-requires-platform line
    text = re.sub(r"^x-augur-requires-platform:.*\n", "", text, flags=re.MULTILINE)
    # Remove x-augur-dependencies block (key + all indented continuation lines)
    text = re.sub(
        r"^x-augur-dependencies:\n(?:[ \t]+.*\n)*",
        "",
        text,
        flags=re.MULTILINE,
    )
    skill_md.write_text(text)


def generate_manifest(output_dir: Path, skills: list[dict]) -> None:
    """Generate the top-level SKILL.md manifest for the pack."""
    skill_list = "\n".join(f"- **{s['name']}**" for s in skills)
    manifest = f"""---
name: augur-skills
description: >
  Portable skills pack from Augur — your AI-powered second brain.
  Gives your agent persistent memory about your career, reading,
  health, finances, and more. Works in any AI agent, zero setup.
---

# Augur Skills Pack

A curated set of skills that give your AI agent a memory about you.

## Included Skills

{skill_list}

## Install

See `install.md` for setup instructions.

## Upgrade

Run `/augur-upgrade` to install the full Augur system with dashboard,
knowledge base, integrations, and background automation.

Learn more at [augur.run](https://augur.run).
"""
    (output_dir / "SKILL.md").write_text(manifest)


def build(skills_dir: Path, output_dir: Path, install_prompt: Path | None = None) -> None:
    """Build the complete skills pack."""
    # Clean output
    if output_dir.exists():
        shutil.rmtree(output_dir)
    skills_output = output_dir / "skills"
    skills_output.mkdir(parents=True)

    # 1. Scan
    portable = scan_portable_skills(skills_dir)
    print(f"Found {len(portable)} portable skills")

    # 2-3. Copy and strip
    for skill in portable:
        dest = skills_output / skill["name"]
        copy_and_strip_skill(skill["path"], dest)
        strip_non_portable_frontmatter(dest / "SKILL.md")
        append_upgrade_footer(dest / "SKILL.md", skill["upgrade_hook"])
        print(f"  Packed: {skill['name']}")

    # 4. Copy install prompt
    if install_prompt and install_prompt.exists():
        shutil.copy2(install_prompt, output_dir / "install.md")
        print(f"  Copied: install.md")

    # 5. Generate manifest
    generate_manifest(output_dir, portable)
    print(f"  Generated: SKILL.md manifest")

    print(f"\nSkills pack built: {output_dir}")


def main():
    parser = argparse.ArgumentParser(description="Build Augur portable skills pack")
    parser.add_argument(
        "--skills-dir",
        type=Path,
        default=PROJECT_ROOT / "skills",
        help="Path to skills directory",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "dist" / "skills-pack",
        help="Output directory for the pack",
    )
    parser.add_argument(
        "--install-prompt",
        type=Path,
        default=PROJECT_ROOT / "skills" / "onboard" / "install.md",
        help="Path to the universal install prompt",
    )
    args = parser.parse_args()
    build(args.skills_dir, args.output_dir, args.install_prompt)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_build_skills_pack.py -v`
Expected: PASS (all 4 tests)

- [ ] **Step 5: Run the build script to verify output**

Run: `python scripts/build_skills_pack.py --output-dir /tmp/test-skills-pack`
Expected: Output shows portable skills found and packed. Verify:
- `/tmp/test-skills-pack/skills/` contains only portable skills
- No `augur/` or `scripts/mcp/` dirs in any skill
- Each SKILL.md has the upgrade footer
- No `x-augur-dependencies` or `x-augur-requires-platform` in any SKILL.md
- Top-level SKILL.md manifest exists

Run: `grep -r 'x-augur-requires-platform' /tmp/test-skills-pack/` — should return nothing
Run: `grep -r 'x-augur-dependencies' /tmp/test-skills-pack/` — should return nothing
Run: `grep -r 'augur-upgrade' /tmp/test-skills-pack/skills/*/SKILL.md` — should appear in every skill

- [ ] **Step 6: Commit**

```bash
git add scripts/build_skills_pack.py tests/test_build_skills_pack.py
git commit -m "feat(onboard): build script for portable skills pack"
```

---

## Task 7: GitHub Actions Workflow

**Files:**
- Create: `.github/workflows/build-skills-pack.yml`

- [ ] **Step 1: Write the workflow**

```yaml
# .github/workflows/build-skills-pack.yml
name: Build Skills Pack

on:
  push:
    tags: ['v*']
  workflow_dispatch:

permissions:
  contents: write

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Build skills pack
        run: python scripts/build_skills_pack.py

      - name: Push to skills-pack branch
        run: |
          cd dist/skills-pack
          git init
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git checkout -b skills-pack
          git add .
          git commit -m "Skills pack built from ${GITHUB_REF_NAME}"
          git remote add origin https://x-access-token:${{ secrets.GITHUB_TOKEN }}@github.com/${{ github.repository }}.git
          git push --force origin skills-pack

      - name: Upload release artifact
        if: startsWith(github.ref, 'refs/tags/')
        uses: actions/upload-artifact@v4
        with:
          name: augur-skills-pack
          path: dist/skills-pack/
```

- [ ] **Step 2: Verify YAML syntax**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/build-skills-pack.yml'))"`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/build-skills-pack.yml
git commit -m "ci: add GitHub Actions workflow for skills pack build on release"
```

---

## Task 8: Seed-to-Vault Migration in install.sh

**Files:**
- Modify: `scripts/install.sh`

When a user upgrades from skills-only to full system, any data they created in `assets/seeds/` needs to be copied into the vault.

- [ ] **Step 1: Read current install.sh post-install section**

Read `scripts/install.sh` — find the section after clone/install where MCP is configured (around the `--from` flag handling). The migration function should run after dependencies are installed but before getting-started messages.

- [ ] **Step 2: Add migration function**

Add this function near the other helper functions in install.sh:

```bash
# ═══════════════════════════════════════════════════════════════════════════════
# SEED-TO-VAULT MIGRATION (for skills-pack upgrades)
# ═══════════════════════════════════════════════════════════════════════════════

migrate_seeds_to_vault() {
    local vault_dir
    vault_dir=$(python3 -c "from src.config.paths import get_vault_dir; print(get_vault_dir())" 2>/dev/null)

    if [ -z "$vault_dir" ]; then
        print_warning "Could not resolve vault directory — skipping seed migration"
        return
    fi

    local migrated=0
    for skill_dir in "$INSTALL_DIR"/skills/*/; do
        local skill_name
        skill_name=$(basename "$skill_dir")
        local seeds_dir="$skill_dir/assets/seeds"
        local vault_skill_dir="$vault_dir/$skill_name"

        # Skip if no seeds dir
        [ -d "$seeds_dir" ] || continue

        # Skip if seeds only contains the original _seed.yaml and template dirs
        # (no user-created files to migrate)
        local file_count
        file_count=$(find "$seeds_dir" -type f ! -name '_seed.yaml' | wc -l)
        [ "$file_count" -gt 0 ] || continue

        # Copy seeds to vault (don't overwrite existing vault data)
        mkdir -p "$vault_skill_dir"
        cp -rn "$seeds_dir"/* "$vault_skill_dir"/ 2>/dev/null
        migrated=$((migrated + 1))
    done

    if [ "$migrated" -gt 0 ]; then
        print_success "Migrated data from $migrated skill(s) to vault"
    fi
}
```

- [ ] **Step 3: Call the function after install**

Find the section in install.sh where `--from` handling happens (after dependencies are installed). Add:

```bash
# Migrate any standalone skill data to vault
migrate_seeds_to_vault
```

- [ ] **Step 4: Test the migration manually**

Create a test seed file:
```bash
mkdir -p /tmp/test-augur/skills/career/assets/seeds/applications
echo "test application" > /tmp/test-augur/skills/career/assets/seeds/applications/test.md
```

Verify the function would detect it:
```bash
find /tmp/test-augur/skills/career/assets/seeds -type f ! -name '_seed.yaml' | wc -l
```
Expected: 1

- [ ] **Step 5: Commit**

```bash
git add scripts/install.sh
git commit -m "feat(onboard): add seed-to-vault migration for skills-pack upgrades"
```

---

## Task 9: Update onboard SKILL.md

**Files:**
- Modify: `skills/onboard/SKILL.md`

- [ ] **Step 1: Read current onboard SKILL.md**

Read `skills/onboard/SKILL.md` to find the right location for the new content.

- [ ] **Step 2: Add reference to install prompt**

Add a new section after the "New User Prompt" section:

```markdown
## AI Agent Install (Skills Pack)

For users coming from AI agents (Claude Code, Codex, Gemini, Cursor, etc.),
a universal install prompt is available at `skills/onboard/install.md`.

The user copies this prompt and pastes it into their agent session. The agent:
1. Auto-detects the platform
2. Asks: skills-only or full system?
3. Installs accordingly

The skills pack contains portable skills with persistent memory capabilities.
Users can upgrade to the full system anytime via `/augur-upgrade`.

### Upgrade Migration

When a skills-pack user upgrades to the full system, `install.sh` runs
`migrate_seeds_to_vault()` to copy any user-created data from `assets/seeds/`
directories into the vault. No data is lost during upgrade.
```

- [ ] **Step 3: Commit**

```bash
git add skills/onboard/SKILL.md
git commit -m "docs(onboard): add AI agent install prompt reference and upgrade migration docs"
```

---

## Task 10: End-to-End Verification

- [ ] **Step 1: Run the full build**

```bash
python scripts/build_skills_pack.py
```

Verify: `dist/skills-pack/` contains:
- `SKILL.md` (manifest)
- `install.md` (prompt)
- `skills/` with 8 skill directories (7 user-facing + augur-upgrade)

- [ ] **Step 2: Verify pack structure per skill**

For each skill in `dist/skills-pack/skills/`:
```bash
for skill in dist/skills-pack/skills/*/; do
    echo "=== $(basename $skill) ==="
    ls -la "$skill"
    echo "--- Checking for stripped dirs ---"
    [ -d "$skill/augur" ] && echo "FAIL: augur/ exists" || echo "OK: no augur/"
    [ -d "$skill/scripts/mcp" ] && echo "FAIL: scripts/mcp/ exists" || echo "OK: no scripts/mcp/"
    echo "--- Checking for upgrade footer ---"
    grep -q "augur-upgrade" "$skill/SKILL.md" && echo "OK: has footer" || echo "FAIL: missing footer"
    echo ""
done
```

- [ ] **Step 3: Verify no non-portable fields remain**

```bash
grep -r 'x-augur-requires-platform' dist/skills-pack/
grep -r 'x-augur-dependencies' dist/skills-pack/
```

Expected: no matches for either

- [ ] **Step 4: Run all tests**

```bash
python -m pytest tests/test_skill_data_store_standalone.py tests/test_build_skills_pack.py -v
```

Expected: all tests pass

- [ ] **Step 5: Verify dist/ is in .gitignore**

```bash
grep -q '^dist/' .gitignore && echo "OK: dist/ already in .gitignore" || echo "FAIL: add dist/ to .gitignore"
```

Expected: OK (dist/ is already in .gitignore)
