# Directory Alignment to Skill Names

**Date:** 2026-03-23
**Status:** Approved
**Scope:** External directory naming enforcement, auto-loop, CI
**Depends on:** `2026-03-23-centralized-path-config-design.md` (project.yaml paths)

## Problem

External directories (`Au-vault`, `Au-docs`) accumulate first-level folders that don't match any skill name — typos (`consulting` instead of `consulting-template`), orphaned folders (`professional`, `reports`), or undocumented structural dirs (`dashboard`). There's no enforcement, so drift is silent and permanent.

## Rule

Every first-level subdirectory in a managed external location must either:
1. Exactly match a skill name from `skills/` (the skill registry), OR
2. Appear in that location's `.augur-reserved` file

## Design

### 1. Managed Locations

Locations are read from `project.yaml` via `get_project_paths()` — not hardcoded. Example (paths vary per user's `project.yaml`):

| Key | Example path | Reserved file |
|-----|--------------|---------------|
| `vault` | `~/Projects/Au-vault` | `.augur-reserved` |
| `documents` | `~/Projects/Au-docs` | `.augur-reserved` |

Defaults (when `project.yaml` has no `paths:` block): `get_vault_dir()` and `~/Documents/Augur`. `get_managed_locations()` logs a warning and returns empty if no paths are configured.

### 2. Reserved Lists

Plain text file `.augur-reserved` at the root of each managed location. One name per line, `#` comments.

**Au-vault:**
```
# Structural directories
config
dev
memory
```

**Au-docs:**
```
# Structural directories
dev
```

### 3. Violation Classification

| Type | Condition | Action |
|------|-----------|--------|
| `trivial-rename` | `difflib.SequenceMatcher` ratio ≥ 0.85 against a skill name | Auto-fix: rename dir |
| `new-skill-candidate` | Dir has ≥ 3 files or ≥ 1 subdirectory, no close match | Report: suggest `/evolve` to create skill |
| `unknown` | Small dir, no close match | Report: ask user |

### 4. Shared Validation Function — `src/lib/dir_alignment.py`

Single module with:

```python
@dataclass
class ManagedLocation:
    path: Path
    reserved_file: str = ".augur-reserved"

def get_managed_locations() -> list[ManagedLocation]:
    """Read vault + documents paths from project.yaml via get_project_paths()."""

def get_reserved_names(location: ManagedLocation) -> set[str]:
    """Read .augur-reserved from location root. Return empty set if missing."""

def get_skill_names() -> set[str]:
    """List skills/ directory names. The filesystem is the source of truth."""

def validate_dir_name(location: ManagedLocation, dir_name: str) -> bool:
    """Return True if dir_name is a skill name or reserved name."""

def classify_violation(location: ManagedLocation, dir_name: str) -> str:
    """Return 'trivial-rename' | 'new-skill-candidate' | 'unknown'."""

def find_closest_skill(dir_name: str) -> tuple[str, float] | None:
    """Return (skill_name, score) if score >= 0.85, else None."""
```

Dependencies: `pathlib`, `difflib`, `dataclasses` (stdlib only). Imports `get_project_paths` from `src.config.paths`.

### 5. Enforcement Layers

**A. paths.py guard** — In functions that create/resolve external dirs (`get_skill_vault_dir`, equivalent docs function), call `validate_dir_name()`. If `False`, raise `ValueError`:
```
"'{name}' is not a recognized skill name. Add it to .augur-reserved or create a skill first."
```

The existing `_RESERVED_VAULT_NAMES` set in `paths.py` is **removed** — `.augur-reserved` becomes the sole source of truth for reserved names. This eliminates the duplicate registry.

**B. CI check** — `scripts/check_dir_alignment.py`: iterate first-level dirs in each managed location, call `validate_dir_name()`, exit non-zero on failure. Runs in nightly CI.

**C. Auto-loop skill** — `skills/auto-dir-alignment/` (see section 6).

### 6. Auto-Loop Skill (`auto-dir-alignment`)

Standard auto-loop pattern skill. Hub: `x-augur-hub: adaptive`.

**Difficulty levels:**

| Level | Behavior |
|-------|----------|
| d=0 | Report only — list violations with classification |
| d=1 | Auto-fix `trivial-rename` (rename dir, git-move if tracked) |
| d=2 | d=1 + scaffold skill for `new-skill-candidate` via `/evolve` dispatch |
| d=3 | d=2 + prompt user for `unknown` items |

**Evolution gaps** (per CLAUDE.md rule #8): When all dirs pass at max difficulty, report: "all aligned, but {N} skills have no vault dir yet" — informational, not a violation.

**Output:** Runtime state dir via `report_only_fix()` from `ops_protocol.py` (consistent with all other auto-loop skills — not `docs/generated/`, which is git-tracked).

### 7. Migration — Existing Violations

**Au-docs:**

| Dir | Classification | Action |
|-----|----------------|--------|
| `apple` | valid skill | keep |
| `career` | valid skill | keep |
| `finance` | valid skill | keep |
| `linkedin-writer` | valid skill | keep |
| `dev` | reserved | add to `.augur-reserved` |
| `consulting` | trivial-rename → `consulting-template` | rename |
| `professional` | unknown | ask user |
| `reports` | unknown | ask user |

**Au-vault:**

| Dir | Classification | Action |
|-----|----------------|--------|
| `config` | reserved | add to `.augur-reserved` |
| `dev` | reserved | add to `.augur-reserved` |
| `memory` | reserved | add to `.augur-reserved` |
| `dashboard` | unknown | ask user |
| All others (45 dirs) | valid skills | keep |

**Sequence:**
0. Add `paths:` block to `project.yaml` (prerequisite — companion spec)
1. Create `.augur-reserved` in both locations
2. Rename `consulting` → `consulting-template` in Au-docs
3. Ask user about `professional`, `reports`, `dashboard`
4. Enable paths.py guard + CI check

Note: Paths in the tables above are this user's specific values from `project.yaml`, not system defaults.

### 8. File Changes Summary

**New files:**

| File | Purpose |
|------|---------|
| `src/lib/dir_alignment.py` | Shared validation, classification, fuzzy matching |
| `skills/auto-dir-alignment/SKILL.md` | Skill metadata, difficulty levels |
| `skills/auto-dir-alignment/scripts/dir_alignment_ops.py` | Auto-loop scanner (scan/fix) |
| `scripts/check_dir_alignment.py` | CI check script |
| `Au-vault/.augur-reserved` | Vault reserved names |
| `Au-docs/.augur-reserved` | Docs reserved names |

**Modified files:**

| File | Change |
|------|--------|
| `src/config/paths.py` | Add guard in vault/docs dir creation functions; remove `_RESERVED_VAULT_NAMES` set |

### 9. Parallel Agent Suitability

**Prerequisite:** `get_project_paths()` from the companion spec must land in `paths.py` before `dir_alignment.py` can be implemented (it imports this function).

All implementation units are independent — no shared mutable state between them:

| Unit | Dependencies | Can parallel? |
|------|-------------|---------------|
| `get_project_paths()` in `paths.py` | Companion spec | Must land first |
| `src/lib/dir_alignment.py` | stdlib + `get_project_paths` | After prerequisite |
| `paths.py` guard | `dir_alignment.py` | After lead |
| `scripts/check_dir_alignment.py` | `dir_alignment.py` | After lead |
| `auto-dir-alignment` skill | `dir_alignment.py` + ops protocol | After lead |
| `.augur-reserved` files | None | Parallel with anything |
| Migration renames | None | Parallel with anything |

**Build sequence:** `get_project_paths()` + `.augur-reserved` files first, then `dir_alignment.py`, then guard + CI + auto-loop in parallel.

### 10. Testing Strategy

- Unit test: `validate_dir_name()` with valid skill, reserved name, and unknown name
- Unit test: `classify_violation()` returns correct type for each category
- Unit test: `find_closest_skill()` fuzzy matching threshold (0.85)
- Unit test: `.augur-reserved` parsing (comments, blank lines, missing file)
- Unit test: `get_managed_locations()` reads from `project.yaml`
- Integration test: paths.py guard rejects unknown dir names
- Integration test: CI script exits non-zero on violations
- Integration test: auto-loop d=0 reports violations, d=1 renames
