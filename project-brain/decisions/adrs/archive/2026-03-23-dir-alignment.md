# Directory Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce that first-level directories in Au-vault and Au-docs match Augur skill names or appear in a reserved list, with three enforcement layers (paths.py guard, CI check, auto-loop).

**Architecture:** Shared validation module (`src/lib/dir_alignment.py`) reads managed locations from `project.yaml` via `get_project_paths()` and reserved names from `.augur-reserved` dotfiles. Three consumers: paths.py runtime guard, CI script, auto-loop scanner. The auto-loop handles classification and remediation; guard and CI are boolean checks only.

**Tech Stack:** Python 3.11+, stdlib only (`pathlib`, `difflib`, `dataclasses`, `logging`), ops_protocol for auto-loop

**Spec:** `docs/superpowers/specs/2026-03-23-dir-alignment-design.md`
**Companion spec:** `docs/superpowers/specs/2026-03-23-centralized-path-config-design.md`

---

## File Structure

| File | Responsibility |
|------|---------------|
| **Create:** `src/lib/dir_alignment.py` | Shared validation, classification, fuzzy matching |
| **Create:** `tests/src/test_dir_alignment.py` | Unit tests for validation module |
| **Create:** `scripts/check_dir_alignment.py` | CI check script (thin wrapper) |
| **Create:** `skills/auto-dir-alignment/SKILL.md` | Auto-loop skill metadata |
| **Create:** `skills/auto-dir-alignment/scripts/dir_alignment_ops.py` | Scan/fix module |
| **Create:** `skills/auto-dir-alignment/augur/tests/test_dir_alignment_ops.py` | Auto-loop tests |
| **Create:** `~/Projects/Au-vault/.augur-reserved` | Vault reserved names |
| **Create:** `~/Projects/Au-docs/.augur-reserved` | Docs reserved names |
| **Modify:** `src/config/paths.py` | Add guard to `get_skill_vault_dir` + `get_skill_documents_dir`, remove `_RESERVED_VAULT_NAMES` |
| **Modify:** `tests/src/test_paths.py` | Add guard tests |

---

### Task 1: Create `.augur-reserved` files

No code dependencies — can run in parallel with any task.

**Files:**
- Create: `~/Projects/Au-vault/.augur-reserved`
- Create: `~/Projects/Au-docs/.augur-reserved`

- [ ] **Step 1: Create Au-vault reserved file**

```
# Structural directories — not skill-aligned
config
dev
memory
```

Write to `~/Projects/Au-vault/.augur-reserved`

- [ ] **Step 2: Create Au-docs reserved file**

```
# Structural directories — not skill-aligned
dev
```

Write to `~/Projects/Au-docs/.augur-reserved`

- [ ] **Step 3: Verify files**

Run: `cat ~/Projects/Au-vault/.augur-reserved && cat ~/Projects/Au-docs/.augur-reserved`
Expected: Both files print their contents without error.

- [ ] **Step 4: Commit (in respective repos if tracked, or skip if gitignored)**

Check if Au-vault and Au-docs are git repos:
```bash
ls ~/Projects/Au-vault/.git && ls ~/Projects/Au-docs/.git
```
If tracked, commit in each repo. If not, no action needed.

---

### Task 2: Implement `src/lib/dir_alignment.py` — core validation module

`get_project_paths()` already exists in `paths.py` (lines 61-94) — no prerequisite work needed.

**Files:**
- Create: `src/lib/dir_alignment.py`
- Test: `tests/src/test_dir_alignment.py`

- [ ] **Step 1: Write failing tests**

Create `tests/src/test_dir_alignment.py`:

```python
"""Tests for src/lib/dir_alignment.py."""

from pathlib import Path

import pytest


@pytest.fixture()
def skills_dir(tmp_path: Path) -> Path:
    """Create a mock skills/ directory with known skill names."""
    sd = tmp_path / "skills"
    sd.mkdir()
    for name in ["career", "finance", "consulting-template", "auto-lint", "health"]:
        (sd / name).mkdir()
    return sd


@pytest.fixture()
def location_with_reserved(tmp_path: Path) -> Path:
    """Create a managed location with a .augur-reserved file."""
    loc = tmp_path / "vault"
    loc.mkdir()
    reserved = loc / ".augur-reserved"
    reserved.write_text("# Reserved\nconfig\ndev\nmemory\n")
    return loc


# --- get_reserved_names ---

def test_get_reserved_names_parses_file(location_with_reserved: Path):
    from src.lib.dir_alignment import ManagedLocation, get_reserved_names
    ml = ManagedLocation(path=location_with_reserved)
    result = get_reserved_names(ml)
    assert result == {"config", "dev", "memory"}


def test_get_reserved_names_returns_empty_when_missing(tmp_path: Path):
    from src.lib.dir_alignment import ManagedLocation, get_reserved_names
    ml = ManagedLocation(path=tmp_path / "nonexistent")
    result = get_reserved_names(ml)
    assert result == set()


def test_get_reserved_names_ignores_comments_and_blanks(tmp_path: Path):
    loc = tmp_path / "loc"
    loc.mkdir()
    (loc / ".augur-reserved").write_text("# comment\n\nfoo\n  \nbar\n# another\n")
    from src.lib.dir_alignment import ManagedLocation, get_reserved_names
    result = get_reserved_names(ManagedLocation(path=loc))
    assert result == {"foo", "bar"}


# --- get_skill_names ---

def test_get_skill_names_lists_skills_dir(skills_dir: Path, monkeypatch):
    from src.lib import dir_alignment
    monkeypatch.setattr(dir_alignment, "_get_skills_dir", lambda: skills_dir)
    result = dir_alignment.get_skill_names()
    assert "career" in result
    assert "consulting-template" in result
    assert len(result) == 5


# --- validate_dir_name ---

def test_validate_allows_skill_name(skills_dir: Path, location_with_reserved: Path, monkeypatch):
    from src.lib import dir_alignment
    monkeypatch.setattr(dir_alignment, "_get_skills_dir", lambda: skills_dir)
    ml = dir_alignment.ManagedLocation(path=location_with_reserved)
    assert dir_alignment.validate_dir_name(ml, "career") is True


def test_validate_allows_reserved_name(skills_dir: Path, location_with_reserved: Path, monkeypatch):
    from src.lib import dir_alignment
    monkeypatch.setattr(dir_alignment, "_get_skills_dir", lambda: skills_dir)
    ml = dir_alignment.ManagedLocation(path=location_with_reserved)
    assert dir_alignment.validate_dir_name(ml, "config") is True


def test_validate_rejects_unknown_name(skills_dir: Path, location_with_reserved: Path, monkeypatch):
    from src.lib import dir_alignment
    monkeypatch.setattr(dir_alignment, "_get_skills_dir", lambda: skills_dir)
    ml = dir_alignment.ManagedLocation(path=location_with_reserved)
    assert dir_alignment.validate_dir_name(ml, "random-junk") is False


# --- find_closest_skill ---

def test_find_closest_skill_matches_above_threshold(skills_dir: Path, monkeypatch):
    from src.lib import dir_alignment
    monkeypatch.setattr(dir_alignment, "_get_skills_dir", lambda: skills_dir)
    result = dir_alignment.find_closest_skill("consulting")
    assert result is not None
    name, score = result
    assert name == "consulting-template"
    assert score >= 0.85


def test_find_closest_skill_returns_none_below_threshold(skills_dir: Path, monkeypatch):
    from src.lib import dir_alignment
    monkeypatch.setattr(dir_alignment, "_get_skills_dir", lambda: skills_dir)
    result = dir_alignment.find_closest_skill("zzz-nothing-close")
    assert result is None


# --- classify_violation ---

def test_classify_trivial_rename(skills_dir: Path, tmp_path: Path, monkeypatch):
    from src.lib import dir_alignment
    monkeypatch.setattr(dir_alignment, "_get_skills_dir", lambda: skills_dir)
    loc = tmp_path / "docs"
    loc.mkdir()
    (loc / "consulting").mkdir()
    ml = dir_alignment.ManagedLocation(path=loc)
    result = dir_alignment.classify_violation(ml, "consulting")
    assert result == "trivial-rename"


def test_classify_new_skill_candidate(skills_dir: Path, tmp_path: Path, monkeypatch):
    from src.lib import dir_alignment
    monkeypatch.setattr(dir_alignment, "_get_skills_dir", lambda: skills_dir)
    loc = tmp_path / "vault"
    loc.mkdir()
    big_dir = loc / "my-project"
    big_dir.mkdir()
    (big_dir / "file1.md").touch()
    (big_dir / "file2.md").touch()
    (big_dir / "file3.md").touch()
    ml = dir_alignment.ManagedLocation(path=loc)
    result = dir_alignment.classify_violation(ml, "my-project")
    assert result == "new-skill-candidate"


def test_classify_unknown(skills_dir: Path, tmp_path: Path, monkeypatch):
    from src.lib import dir_alignment
    monkeypatch.setattr(dir_alignment, "_get_skills_dir", lambda: skills_dir)
    loc = tmp_path / "vault"
    loc.mkdir()
    small_dir = loc / "random"
    small_dir.mkdir()
    (small_dir / "note.txt").touch()
    ml = dir_alignment.ManagedLocation(path=loc)
    result = dir_alignment.classify_violation(ml, "random")
    assert result == "unknown"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && python -m pytest tests/src/test_dir_alignment.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.lib.dir_alignment'`

- [ ] **Step 3: Implement `src/lib/dir_alignment.py`**

```python
"""Directory alignment validation — enforces first-level dirs match skill names.

Spec: docs/superpowers/specs/2026-03-23-dir-alignment-design.md
"""

from __future__ import annotations

import difflib
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

FUZZY_THRESHOLD = 0.85


def _get_skills_dir() -> Path:
    """Return the skills/ directory. Separate function for testability."""
    from src.config.paths import get_skills_dir
    return get_skills_dir()


@dataclass
class ManagedLocation:
    """An external directory whose first-level subdirs must match skill names."""
    path: Path
    reserved_file: str = ".augur-reserved"


def get_managed_locations() -> list[ManagedLocation]:
    """Read vault + documents paths from project.yaml via get_project_paths()."""
    from src.config.paths import get_project_paths
    project_paths = get_project_paths()
    if not project_paths:
        logger.warning("No paths: block in project.yaml — dir alignment has nothing to scan")
        return []
    locations: list[ManagedLocation] = []
    for key in ("vault", "documents"):
        path = project_paths.get(key)
        if path and path.is_dir():
            locations.append(ManagedLocation(path=path))
    return locations


def get_reserved_names(location: ManagedLocation) -> set[str]:
    """Read .augur-reserved from location root. Return empty set if missing."""
    reserved_path = location.path / location.reserved_file
    if not reserved_path.exists():
        return set()
    names: set[str] = set()
    for line in reserved_path.read_text().splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            names.add(stripped)
    return names


def get_skill_names() -> set[str]:
    """List skills/ directory names. The filesystem is the source of truth."""
    skills_dir = _get_skills_dir()
    if not skills_dir.is_dir():
        return set()
    return {d.name for d in skills_dir.iterdir() if d.is_dir() and not d.name.startswith(".")}


def validate_dir_name(location: ManagedLocation, dir_name: str) -> bool:
    """Return True if dir_name is a skill name or reserved name."""
    reserved = get_reserved_names(location)
    skills = get_skill_names()
    return dir_name in reserved or dir_name in skills


def find_closest_skill(dir_name: str) -> tuple[str, float] | None:
    """Return (skill_name, score) if fuzzy match score >= 0.85, else None."""
    skills = get_skill_names()
    if not skills:
        return None
    best_name = ""
    best_score = 0.0
    for skill in skills:
        score = difflib.SequenceMatcher(None, dir_name, skill).ratio()
        if score > best_score:
            best_score = score
            best_name = skill
    if best_score >= FUZZY_THRESHOLD:
        return (best_name, best_score)
    return None


def classify_violation(location: ManagedLocation, dir_name: str) -> str:
    """Return 'trivial-rename' | 'new-skill-candidate' | 'unknown'."""
    closest = find_closest_skill(dir_name)
    if closest is not None:
        return "trivial-rename"

    dir_path = location.path / dir_name
    if dir_path.is_dir():
        children = list(dir_path.iterdir())
        file_count = sum(1 for c in children if c.is_file())
        subdir_count = sum(1 for c in children if c.is_dir())
        if file_count >= 3 or subdir_count >= 1:
            return "new-skill-candidate"

    return "unknown"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && python -m pytest tests/src/test_dir_alignment.py -v`
Expected: All 11 tests PASS

- [ ] **Step 5: Commit**

```bash
cd ~/Projects/Augur
git add src/lib/dir_alignment.py tests/src/test_dir_alignment.py
git commit -m "feat: add dir_alignment validation module with tests"
```

---

### Task 3: Add paths.py guard and remove `_RESERVED_VAULT_NAMES`

Depends on Task 2 (`dir_alignment.py` must exist).

**Behavioral change:** Old code rejected reserved names (`config`, `dev`, `memory`) with `ValueError`. New code allows them (they're in `.augur-reserved`, so `validate_dir_name` returns `True`). This is intentional — reserved dirs are valid targets, not forbidden. The existing test `test_get_skill_data_dir_reserved_name_raises` must be updated.

**Files:**
- Modify: `src/config/paths.py:359-396` (remove `_RESERVED_VAULT_NAMES`, modify `get_skill_vault_dir` AND `get_skill_documents_dir`)
- Modify: `tests/src/test_paths.py` (update existing reserved-name test, add new tests)

- [ ] **Step 1: Write failing tests**

Add to `tests/src/test_paths.py`:

```python
def test_get_skill_vault_dir_rejects_unknown_name(tmp_path, monkeypatch):
    """get_skill_vault_dir() raises ValueError for names not in skills or .augur-reserved."""
    from src.lib import dir_alignment
    monkeypatch.setattr(dir_alignment, "_get_skills_dir", lambda: tmp_path / "empty_skills")
    (tmp_path / "empty_skills").mkdir()
    monkeypatch.setattr(paths, "_vault_home_dir", lambda: tmp_path / "vault")
    (tmp_path / "vault").mkdir()
    paths.invalidate_project_cache()
    with pytest.raises(ValueError, match="not a recognized skill name"):
        paths.get_skill_vault_dir("nonexistent-skill")


def test_get_skill_vault_dir_allows_reserved_name_via_dotfile(tmp_path, monkeypatch):
    """get_skill_vault_dir() allows names listed in .augur-reserved."""
    from src.lib import dir_alignment
    monkeypatch.setattr(dir_alignment, "_get_skills_dir", lambda: tmp_path / "empty_skills")
    (tmp_path / "empty_skills").mkdir()
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / ".augur-reserved").write_text("config\ndev\nmemory\n")
    monkeypatch.setattr(paths, "_vault_home_dir", lambda: vault)
    paths.invalidate_project_cache()
    result = paths.get_skill_vault_dir("config")
    assert result == vault / "config"


def test_get_skill_documents_dir_rejects_unknown_name(tmp_path, monkeypatch):
    """get_skill_documents_dir() raises ValueError for unknown names."""
    from src.lib import dir_alignment
    monkeypatch.setattr(dir_alignment, "_get_skills_dir", lambda: tmp_path / "empty_skills")
    (tmp_path / "empty_skills").mkdir()
    monkeypatch.setattr(paths, "_documents_home_dir", lambda: tmp_path / "docs")
    (tmp_path / "docs").mkdir()
    paths.invalidate_project_cache()
    with pytest.raises(ValueError, match="not a recognized skill name"):
        paths.get_skill_documents_dir("nonexistent-skill")


def test_get_skill_documents_dir_allows_reserved_name_via_dotfile(tmp_path, monkeypatch):
    """get_skill_documents_dir() allows names listed in .augur-reserved."""
    from src.lib import dir_alignment
    monkeypatch.setattr(dir_alignment, "_get_skills_dir", lambda: tmp_path / "empty_skills")
    (tmp_path / "empty_skills").mkdir()
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / ".augur-reserved").write_text("dev\n")
    monkeypatch.setattr(paths, "_documents_home_dir", lambda: docs)
    paths.invalidate_project_cache()
    result = paths.get_skill_documents_dir("dev")
    assert result == docs / "dev"
```

- [ ] **Step 2: Update existing reserved-name test**

Find `test_get_skill_data_dir_reserved_name_raises` in `tests/src/test_paths.py`. Change it to test the NEW behavior — reserved names are now allowed (return a path), not rejected:

```python
def test_get_skill_data_dir_reserved_name_allowed_via_dotfile(tmp_path, monkeypatch):
    """Reserved names in .augur-reserved are valid, not rejected."""
    from src.lib import dir_alignment
    monkeypatch.setattr(dir_alignment, "_get_skills_dir", lambda: tmp_path / "empty_skills")
    (tmp_path / "empty_skills").mkdir()
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / ".augur-reserved").write_text("config\ndev\nmemory\n")
    monkeypatch.setattr(paths, "_vault_home_dir", lambda: vault)
    paths.invalidate_project_cache()
    result = paths.get_skill_data_dir("config")
    assert result == vault / "config"
```

- [ ] **Step 3: Run tests to verify new ones fail, updated one fails**

Run: `cd ~/Projects/Augur && python -m pytest tests/src/test_paths.py -k "unknown_name or reserved_name_via_dotfile or reserved_name_allowed" -v`
Expected: FAIL — current code still uses `_RESERVED_VAULT_NAMES`

- [ ] **Step 4: Modify `src/config/paths.py`**

Delete `_RESERVED_VAULT_NAMES` (line 359) and rewrite both functions:

```python
# Remove this line:
# _RESERVED_VAULT_NAMES = {"config", "dev", "memory", ".git"}

def get_skill_vault_dir(skill_name: str) -> Path:
    """Resolve a skill's vault directory. Validates against skill names and .augur-reserved."""
    from src.lib.dir_alignment import ManagedLocation, validate_dir_name
    vault = get_vault_dir()
    location = ManagedLocation(path=vault)
    if not validate_dir_name(location, skill_name):
        raise ValueError(
            f"'{skill_name}' is not a recognized skill name. "
            "Add it to .augur-reserved or create a skill first."
        )
    return vault / skill_name

# ... get_documents_dir() stays unchanged ...

def get_skill_documents_dir(skill_name: str) -> Path:
    """Resolve a skill's documents directory. Validates against skill names and .augur-reserved."""
    from src.lib.dir_alignment import ManagedLocation, validate_dir_name
    docs = get_documents_dir()
    location = ManagedLocation(path=docs)
    if not validate_dir_name(location, skill_name):
        raise ValueError(
            f"'{skill_name}' is not a recognized skill name. "
            "Add it to .augur-reserved or create a skill first."
        )
    return docs / skill_name
```

- [ ] **Step 5: Run full paths test suite**

Run: `cd ~/Projects/Augur && python -m pytest tests/src/test_paths.py -v`
Expected: All tests PASS. Watch for any other tests that referenced `_RESERVED_VAULT_NAMES` or expected the old "reserved vault directory" error message — fix those too.

- [ ] **Step 6: Commit**

```bash
cd ~/Projects/Augur
git add src/config/paths.py tests/src/test_paths.py
git commit -m "feat(paths): replace _RESERVED_VAULT_NAMES with .augur-reserved guard in vault and docs"
```

---

### Task 4: Create CI check script

Depends on Task 2 (`dir_alignment.py` must exist). Can run in parallel with Tasks 3, 5, 6.

**Files:**
- Create: `scripts/check_dir_alignment.py`

- [ ] **Step 1: Write the script**

```python
#!/usr/bin/env python3
"""CI check: verify first-level dirs in managed locations match skill names.

Exit 0 if all dirs are valid, exit 1 if any violations found.

Spec: docs/superpowers/specs/2026-03-23-dir-alignment-design.md
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.lib.dir_alignment import get_managed_locations, validate_dir_name


def main() -> int:
    locations = get_managed_locations()
    if not locations:
        print("No managed locations configured in project.yaml")
        return 0

    violations: list[str] = []
    for loc in locations:
        if not loc.path.is_dir():
            continue
        for entry in sorted(loc.path.iterdir()):
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            if not validate_dir_name(loc, entry.name):
                violations.append(f"  {loc.path.name}/{entry.name}")

    if violations:
        print(f"Directory alignment violations ({len(violations)}):")
        for v in violations:
            print(v)
        return 1

    print("All directories aligned with skill names")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Test manually**

Run: `cd ~/Projects/Augur && python scripts/check_dir_alignment.py`
Expected: Lists any current violations (e.g. `Au-docs/consulting`, `Au-docs/professional`, `Au-docs/reports`, `Au-vault/dashboard`) and exits 1, or exits 0 if migration is already done.

- [ ] **Step 3: Commit**

```bash
cd ~/Projects/Augur
git add scripts/check_dir_alignment.py
git commit -m "feat: add CI check script for dir alignment"
```

---

### Task 5: Create auto-dir-alignment skill — SKILL.md

Depends on nothing — metadata only. Can run in parallel with Tasks 3, 4, 6.

**Files:**
- Create: `skills/auto-dir-alignment/SKILL.md`

- [ ] **Step 1: Create skill directory and SKILL.md**

Run: `mkdir -p ~/Projects/Augur/skills/auto-dir-alignment/scripts ~/Projects/Augur/skills/auto-dir-alignment/augur/tests`

Write `skills/auto-dir-alignment/SKILL.md`:

```markdown
---
name: auto-dir-alignment
x-augur-type: autoloop
x-augur-tags: []
description: 'Validate first-level dirs in vault and docs match skill names or .augur-reserved entries'
x-augur-hub: adaptive
x-augur-tab: infrastructure
x-augur-visibility: auto
x-augur-trigger: nightly
x-augur-config:
  commands:
  - id: auto-dir-alignment
    type: workflow
    visibility: auto
    description: Validate first-level dirs in vault and docs match skill names
    callable: scripts/dir_alignment_ops.py
    protocol: scan-fix
    loop:
      name: code-quality
      tier: 2
      trigger: nightly
  contributions: {}
---

# auto-dir-alignment

Enforce that first-level directories in managed external locations (vault, docs) exactly match an Augur skill name or appear in the location's `.augur-reserved` file.

## Difficulty Levels

| Level | Behavior |
|-------|----------|
| d=0 | Report only — list violations with classification |
| d=1 | Auto-fix trivial renames (dir name fuzzy-matches a skill at >= 0.85) |
| d=2 | d=1 + scaffold skill for new-skill-candidate dirs via `/evolve` dispatch |
| d=3 | d=2 + prompt user for unknown items |

## Evolution Gaps

When all dirs pass at max difficulty, reports: "all aligned, but {N} skills have no vault dir yet."
```

- [ ] **Step 2: Commit**

```bash
cd ~/Projects/Augur
git add skills/auto-dir-alignment/SKILL.md
git commit -m "feat: scaffold auto-dir-alignment skill metadata"
```

---

### Task 6: Implement auto-loop scan/fix module

Depends on Task 2 (`dir_alignment.py`) and Task 5 (skill directory exists). Can run in parallel with Tasks 3, 4.

**Files:**
- Create: `skills/auto-dir-alignment/scripts/dir_alignment_ops.py`
- Test: `skills/auto-dir-alignment/augur/tests/test_dir_alignment_ops.py`

- [ ] **Step 1: Write failing tests**

Create `skills/auto-dir-alignment/augur/tests/test_dir_alignment_ops.py`:

```python
"""Tests for auto-dir-alignment scan/fix module."""

import importlib.util
from pathlib import Path

import pytest
from src.lib.ops_protocol import OpsContext, ScanResult, FixResult

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "dir_alignment_ops.py"


@pytest.fixture()
def mod():
    spec = importlib.util.spec_from_file_location("dir_alignment_ops", _MODULE_PATH)
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _ctx(tmp_path: Path, **kw) -> OpsContext:
    return OpsContext(project_root=tmp_path, **kw)


def test_module_name(mod):
    assert mod.name == "auto-dir-alignment"


def test_scan_reports_violations(mod, tmp_path, monkeypatch):
    """d=0 scan finds dirs that don't match skills."""
    from src.lib import dir_alignment

    # Set up skills dir
    skills = tmp_path / "skills"
    skills.mkdir()
    (skills / "career").mkdir()
    (skills / "finance").mkdir()
    monkeypatch.setattr(dir_alignment, "_get_skills_dir", lambda: skills)

    # Set up managed location with one valid and one invalid dir
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "career").mkdir()
    (vault / "bad-name").mkdir()
    (vault / ".augur-reserved").write_text("")

    monkeypatch.setattr(mod, "_get_locations", lambda: [dir_alignment.ManagedLocation(path=vault)])

    result = mod.scan(_ctx(tmp_path, difficulty=0))
    assert isinstance(result, ScanResult)
    assert len(result.issues) == 1
    assert result.issues[0]["dir_name"] == "bad-name"


def test_scan_no_violations(mod, tmp_path, monkeypatch):
    """d=0 scan with all valid dirs returns clean."""
    from src.lib import dir_alignment

    skills = tmp_path / "skills"
    skills.mkdir()
    (skills / "career").mkdir()
    monkeypatch.setattr(dir_alignment, "_get_skills_dir", lambda: skills)

    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "career").mkdir()
    (vault / ".augur-reserved").write_text("")

    monkeypatch.setattr(mod, "_get_locations", lambda: [dir_alignment.ManagedLocation(path=vault)])

    result = mod.scan(_ctx(tmp_path, difficulty=0))
    assert result.issues == []
    assert result.health == "verified"


def test_fix_dry_run(mod, tmp_path):
    """Fix in dry_run mode does not rename anything."""
    issues = [{"category": "dir-alignment", "detail": "bad → good", "kind": "actionable", "classification": "trivial-rename", "dir_name": "bad", "closest_skill": "good", "location": str(tmp_path)}]
    result = mod.fix(_ctx(tmp_path, difficulty=1, dry_run=True), issues)
    assert isinstance(result, FixResult)
    assert result.success
    assert "Dry run" in result.summary
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && python -m pytest skills/auto-dir-alignment/augur/tests/test_dir_alignment_ops.py -v`
Expected: FAIL with `FileNotFoundError` (scan module doesn't exist yet)

- [ ] **Step 3: Implement `dir_alignment_ops.py`**

Create `skills/auto-dir-alignment/scripts/dir_alignment_ops.py`:

```python
"""Auto-loop scan/fix for directory alignment to skill names.

Spec: docs/superpowers/specs/2026-03-23-dir-alignment-design.md
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from src.lib.dir_alignment import (
    ManagedLocation,
    classify_violation,
    find_closest_skill,
    get_managed_locations,
    get_skill_names,
    validate_dir_name,
)
from src.lib.ops_protocol import (
    FixResult,
    OpsContext,
    ScanResult,
    evolution_gap,
    make_issue,
    report_only_fix,
)

name = "auto-dir-alignment"

DIFFICULTY_SPEC = {
    0: "Report — list violations with classification",
    1: "Auto-fix — rename trivial-rename dirs",
    2: "Scaffold — create skills for new-skill-candidate dirs",
    3: "Interactive — prompt user for unknown dirs",
}

logger = logging.getLogger(__name__)


def _get_locations() -> list[ManagedLocation]:
    """Wrapper for testability."""
    return get_managed_locations()


def scan(ctx: OpsContext) -> ScanResult:
    """Scan managed locations for directory alignment violations."""
    locations = _get_locations()
    if not locations:
        return ScanResult(
            issues=[],
            summary="No managed locations configured",
            severity="info",
            health="verified",
        )

    issues: list[dict] = []
    dirs_scanned = 0

    for loc in locations:
        if not loc.path.is_dir():
            continue
        for entry in sorted(loc.path.iterdir()):
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            dirs_scanned += 1
            if not validate_dir_name(loc, entry.name):
                classification = classify_violation(loc, entry.name)
                closest = find_closest_skill(entry.name)
                detail = f"{entry.name} in {loc.path.name}"
                if closest:
                    detail += f" (closest: {closest[0]}, score: {closest[1]:.2f})"

                issues.append(make_issue(
                    category="dir-alignment",
                    detail=detail,
                    path=str(entry),
                    kind="actionable" if classification == "trivial-rename" else "manual",
                    root_cause_type="manual_debt",
                    fixability="auto" if classification == "trivial-rename" else "manual",
                    classification=classification,
                    dir_name=entry.name,
                    closest_skill=closest[0] if closest else None,
                    location=str(loc.path),
                ))

    # Evolution gaps at max difficulty
    if not issues and ctx.difficulty >= max(DIFFICULTY_SPEC.keys()):
        skills = get_skill_names()
        skills_with_vault = set()
        for loc in locations:
            if loc.path.is_dir():
                skills_with_vault.update(
                    d.name for d in loc.path.iterdir()
                    if d.is_dir() and not d.name.startswith(".")
                )
        missing = skills - skills_with_vault
        if missing:
            issues.append(evolution_gap(
                f"All aligned, but {len(missing)} skills have no vault/docs dir yet"
            ))

    severity = "error" if any(i.get("kind") == "actionable" for i in issues) else "info"
    health = "degraded" if issues and any(i.get("kind") != "maintenance" for i in issues) else "verified"

    return ScanResult(
        issues=issues,
        summary=f"Scanned {dirs_scanned} dirs, {len(issues)} violation(s)",
        severity=severity,
        health=health,
        items_scanned=dirs_scanned,
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Fix directory alignment violations based on difficulty level."""
    if ctx.dry_run:
        return FixResult(success=True, summary=f"Dry run: {len(issues)} issue(s) found")

    if not issues:
        return FixResult(success=True, summary="No issues to fix")

    actions: list[dict] = []
    changes: list[str] = []

    for issue in issues:
        classification = issue.get("classification")

        if classification == "trivial-rename" and ctx.difficulty >= 1:
            src_path = Path(issue["path"])
            closest = issue.get("closest_skill")
            if closest and src_path.is_dir():
                dst_path = src_path.parent / closest
                if not dst_path.exists():
                    shutil.move(str(src_path), str(dst_path))
                    actions.append({"renamed": f"{src_path.name} -> {closest}"})
                    changes.append(str(dst_path))

        elif classification == "new-skill-candidate" and ctx.difficulty >= 2:
            actions.append({"suggest_evolve": issue.get("dir_name")})

        elif classification == "unknown" and ctx.difficulty >= 3:
            actions.append({"ask_user": issue.get("dir_name")})

    return FixResult(
        success=True,
        actions=actions,
        changes=changes,
        summary=f"Applied {len(actions)} action(s)" if actions else "No actionable fixes at this difficulty",
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && python -m pytest skills/auto-dir-alignment/augur/tests/test_dir_alignment_ops.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
cd ~/Projects/Augur
git add skills/auto-dir-alignment/scripts/dir_alignment_ops.py skills/auto-dir-alignment/augur/tests/test_dir_alignment_ops.py
git commit -m "feat: implement auto-dir-alignment scan/fix module with tests"
```

---

### Task 7: Migration — rename and triage existing violations

Depends on Task 1 (`.augur-reserved` files exist) and Task 2 (`dir_alignment.py` exists for verification).

**Files:**
- Rename: `~/Projects/Au-docs/consulting` → `~/Projects/Au-docs/consulting-template`
- Triage: `professional`, `reports` (Au-docs), `dashboard` (Au-vault)

- [ ] **Step 1: Rename `consulting` to `consulting-template` in Au-docs**

Run: `mv ~/Projects/Au-docs/consulting ~/Projects/Au-docs/consulting-template`

Verify: `ls -la ~/Projects/Au-docs/ | grep consulting`
Expected: `consulting-template` exists, `consulting` does not

- [ ] **Step 2: Ask user about remaining violations**

Ask the user what to do with:
- `Au-docs/professional` — rename to an existing skill, create new skill, or delete?
- `Au-docs/reports` — rename to an existing skill, create new skill, or delete?
- `Au-vault/dashboard` — rename to an existing skill, create new skill, or delete?

- [ ] **Step 3: Apply user's decisions**

Execute whatever the user decides for each of the three unknown dirs.

- [ ] **Step 4: Verify alignment**

Run: `cd ~/Projects/Augur && python scripts/check_dir_alignment.py`
Expected: Exit 0 — "All directories aligned with skill names"

- [ ] **Step 5: Commit in affected repos**

If Au-docs or Au-vault are git repos, commit the renames and reserved files.

---

### Task 8: Final integration verification

Depends on all previous tasks.

- [ ] **Step 1: Run full test suite for touched files**

Run: `cd ~/Projects/Augur && python -m pytest tests/src/test_paths.py tests/src/test_dir_alignment.py skills/auto-dir-alignment/augur/tests/test_dir_alignment_ops.py -v`
Expected: All tests PASS

- [ ] **Step 2: Run CI check script**

Run: `cd ~/Projects/Augur && python scripts/check_dir_alignment.py`
Expected: Exit 0

- [ ] **Step 3: Verify paths.py guard works end-to-end**

Run: `cd ~/Projects/Augur && python -c "from src.config.paths import get_skill_vault_dir; print(get_skill_vault_dir('career'))"`
Expected: Prints the vault path for career skill

Run: `cd ~/Projects/Augur && python -c "from src.config.paths import get_skill_vault_dir; get_skill_vault_dir('nonexistent-xyz')"`
Expected: `ValueError: 'nonexistent-xyz' is not a recognized skill name`

- [ ] **Step 4: Final commit if needed**

If any fixups were required, commit them.
