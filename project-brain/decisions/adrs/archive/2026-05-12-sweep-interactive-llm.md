# Sweep Interactive LLM — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `/sweep-stores` with tiered confidence classification (Tier 1 autonomous / Tier 2 interactive Q&A / Tier 3 content-inspection-then-Q&A) and persist the user's group decisions in `.augur-lifecycle.yaml` so subsequent sweeps don't re-ask.

**Architecture:** Pure agent-side reasoning enhancement. The agent gains a richer rubric and a question-asking layer; the two MCP tools (`hygiene-scan`, `hygiene-apply`) gain additive schema changes only — `hygiene-scan` returns cached `known_groups`, `hygiene-apply` accepts optional `lifecycle_updates` and writes them to YAML atomically before moves. No new MCP tools. No daemon wiring.

**Tech Stack:** Python 3.11+, `yaml`, `pathlib`, `dataclasses`, pytest. Spec: `docs/superpowers/specs/2026-05-12-sweep-interactive-llm-design.md`.

---

## File Structure

```
shared-vault/skills/loop-hygiene/
├── SKILL.md                                       # MODIFY: version bump, changelog note
├── augur/data/
│   └── lifecycle_schema.yaml                      # MODIFY: add known_groups schema
├── commands/
│   └── sweep-stores.md                            # MODIFY: workflow now references tier rubric + Q&A layer
├── references/
│   └── sweep-rubric.md                            # REWRITE: tier 1/2/3 with explicit signals
├── scripts/
│   ├── lifecycle_config.py                        # MODIFY: parse known_groups[] into dataclass
│   ├── lifecycle_writer.py                        # NEW: atomic .augur-lifecycle.yaml writer
│   ├── known_groups.py                            # NEW: match files against cached groups
│   ├── hygiene_scan.py                            # MODIFY: emit known_groups in lifecycle_config dict
│   └── hygiene_apply.py                           # MODIFY: accept lifecycle_updates, write YAML before moves
├── evals/fixtures/
│   ├── fixture_renamed_iteration/                 # NEW
│   ├── fixture_variant_suffix/                    # NEW
│   ├── fixture_mixed_version_scheme/              # NEW
│   ├── fixture_conceptual_supersession/           # NEW
│   ├── fixture_cached_known_group/                # NEW
│   └── fixture_lifecycle_malformed_groups/        # NEW
└── augur/tests/
    ├── test_lifecycle_config.py                   # EXTEND: known_groups parsing
    ├── test_lifecycle_writer.py                   # NEW
    ├── test_known_groups.py                       # NEW
    ├── test_hygiene_scan.py                       # EXTEND: known_groups round-trip
    ├── test_hygiene_apply.py                      # EXTEND: lifecycle_updates write
    └── test_hygiene_e2e.py                        # EXTEND: cached known_groups skip on sweep #2
```

**Responsibility boundaries:**
- `lifecycle_config.py` — read+parse YAML; raise `LifecycleConfigError` on malformed.
- `lifecycle_writer.py` — write+append `known_groups[]` atomically via temp-rename. Refuses on name collision.
- `known_groups.py` — pure function: given file list + `known_groups[]`, return `(matched_moves, no_touch_files)`.
- `hygiene_scan.py` — wire `known_groups` field through `asdict(LifecycleConfig)`. No new logic.
- `hygiene_apply.py` — call `lifecycle_writer` BEFORE running moves; surface refusals in result.

**Why split `lifecycle_writer.py` from `lifecycle_config.py`:** the existing `lifecycle_config.py` is read-only and well-tested. Mixing write-side atomic-rename logic into the same file would couple two responsibilities (parse vs persist) that have different invariants and test surfaces.

**Why a new `known_groups.py` module:** matching cached entries against a scan result is pure logic with three strategy branches. Keeping it out of `hygiene_apply.py` lets the agent's classifier prototype the matcher against scan output without touching `hygiene_apply`.

---

## Task 1 — Extend `LifecycleConfig` dataclass with `known_groups[]` field

**Files:**
- Modify: `shared-vault/skills/loop-hygiene/scripts/lifecycle_config.py`
- Modify: `shared-vault/skills/loop-hygiene/augur/tests/test_lifecycle_config.py`

- [ ] **Step 1: Write failing test for `known_groups` parsing (highest_version strategy)**

Append to `shared-vault/skills/loop-hygiene/augur/tests/test_lifecycle_config.py`:

```python
def test_read_lifecycle_config_known_groups_highest_version(tmp_path):
    (tmp_path / ".augur-lifecycle.yaml").write_text(
        "enabled: true\n"
        "known_groups:\n"
        "  - name: guriqo-com-build\n"
        "    canonical_strategy: highest_version\n"
        "    pattern: 'guriqo-com-*.zip'\n"
        "    decided_at: '2026-05-12T14:30:00Z'\n"
        "    decided_by: gsannikov\n"
        "    note: 'older scheme stale'\n"
    )
    cfg = mod.read_lifecycle_config(tmp_path)
    assert len(cfg.known_groups) == 1
    g = cfg.known_groups[0]
    assert g.name == "guriqo-com-build"
    assert g.canonical_strategy == "highest_version"
    assert g.pattern == "guriqo-com-*.zip"
    assert g.members is None
    assert g.canonical is None
    assert g.decided_at == "2026-05-12T14:30:00Z"
    assert g.decided_by == "gsannikov"
    assert g.note == "older scheme stale"
```

- [ ] **Step 2: Run test, confirm failure**

Run: `cd ~/Projects/Augur && uv run pytest shared-vault/skills/loop-hygiene/augur/tests/test_lifecycle_config.py::test_read_lifecycle_config_known_groups_highest_version -v`

Expected: FAIL — `AttributeError: 'LifecycleConfig' object has no attribute 'known_groups'`.

- [ ] **Step 3: Add `KnownGroup` dataclass + extend `LifecycleConfig`**

In `shared-vault/skills/loop-hygiene/scripts/lifecycle_config.py`, add after the existing `LifecycleConfig` dataclass:

```python
VALID_CANONICAL_STRATEGIES = frozenset({"highest_version", "explicit", "not_a_group"})


@dataclass(frozen=True)
class KnownGroup:
    name: str
    canonical_strategy: str  # one of VALID_CANONICAL_STRATEGIES
    pattern: str | None = None
    members: tuple[str, ...] | None = None
    canonical: str | None = None
    decided_at: str | None = None
    decided_by: str | None = None
    note: str | None = None
```

Then modify `LifecycleConfig` to add the field:

```python
@dataclass(frozen=True)
class LifecycleConfig:
    enabled: bool = True
    pattern_hints: list[str] = field(default_factory=list)
    keep_latest: int | None = None
    deploy_root: bool = False
    notes: str | None = None
    known_groups: tuple[KnownGroup, ...] = ()
```

- [ ] **Step 4: Parse `known_groups` in `read_lifecycle_config`**

In `read_lifecycle_config`, after the `notes` parsing block and before the `return`, add:

```python
raw_groups = raw.get("known_groups", [])
if not isinstance(raw_groups, list):
    raise LifecycleConfigError(f"{path}: 'known_groups' must be a list")
known_groups: list[KnownGroup] = []
for idx, entry in enumerate(raw_groups):
    if not isinstance(entry, dict):
        raise LifecycleConfigError(f"{path}: known_groups[{idx}] must be a mapping")
    name = entry.get("name")
    if not isinstance(name, str) or not name:
        raise LifecycleConfigError(f"{path}: known_groups[{idx}].name must be a non-empty string")
    strategy = entry.get("canonical_strategy")
    if strategy not in VALID_CANONICAL_STRATEGIES:
        raise LifecycleConfigError(
            f"{path}: known_groups[{idx}].canonical_strategy must be one of "
            f"{sorted(VALID_CANONICAL_STRATEGIES)}; got {strategy!r}"
        )
    pattern = entry.get("pattern")
    if pattern is not None and not isinstance(pattern, str):
        raise LifecycleConfigError(f"{path}: known_groups[{idx}].pattern must be a string")
    members_raw = entry.get("members")
    members: tuple[str, ...] | None = None
    if members_raw is not None:
        if not isinstance(members_raw, list) or not all(isinstance(m, str) for m in members_raw):
            raise LifecycleConfigError(
                f"{path}: known_groups[{idx}].members must be a list of strings"
            )
        members = tuple(members_raw)
    canonical = entry.get("canonical")
    if canonical is not None and not isinstance(canonical, str):
        raise LifecycleConfigError(f"{path}: known_groups[{idx}].canonical must be a string")
    decided_at = entry.get("decided_at")
    if decided_at is not None and not isinstance(decided_at, str):
        raise LifecycleConfigError(f"{path}: known_groups[{idx}].decided_at must be a string")
    decided_by = entry.get("decided_by")
    if decided_by is not None and not isinstance(decided_by, str):
        raise LifecycleConfigError(f"{path}: known_groups[{idx}].decided_by must be a string")
    note = entry.get("note")
    if note is not None and not isinstance(note, str):
        raise LifecycleConfigError(f"{path}: known_groups[{idx}].note must be a string")
    # Strategy-specific required fields
    if strategy == "highest_version" and pattern is None:
        raise LifecycleConfigError(
            f"{path}: known_groups[{idx}] strategy=highest_version requires 'pattern'"
        )
    if strategy in ("explicit", "not_a_group") and members is None:
        raise LifecycleConfigError(
            f"{path}: known_groups[{idx}] strategy={strategy} requires 'members'"
        )
    if strategy == "explicit" and canonical is None:
        raise LifecycleConfigError(
            f"{path}: known_groups[{idx}] strategy=explicit requires 'canonical'"
        )
    known_groups.append(KnownGroup(
        name=name,
        canonical_strategy=strategy,
        pattern=pattern,
        members=members,
        canonical=canonical,
        decided_at=decided_at,
        decided_by=decided_by,
        note=note,
    ))
```

Modify the final `return`:

```python
return LifecycleConfig(
    enabled=enabled,
    pattern_hints=list(pattern_hints),
    keep_latest=keep_latest,
    deploy_root=deploy_root,
    notes=notes,
    known_groups=tuple(known_groups),
)
```

- [ ] **Step 5: Run test, confirm pass**

Run: `cd ~/Projects/Augur && uv run pytest shared-vault/skills/loop-hygiene/augur/tests/test_lifecycle_config.py::test_read_lifecycle_config_known_groups_highest_version -v`

Expected: PASS.

- [ ] **Step 6: Add tests for the other two strategies + malformed cases**

Append to `test_lifecycle_config.py`:

```python
def test_read_lifecycle_config_known_groups_explicit(tmp_path):
    (tmp_path / ".augur-lifecycle.yaml").write_text(
        "known_groups:\n"
        "  - name: form-answers\n"
        "    canonical_strategy: explicit\n"
        "    members: ['augur-intel-form-answers.md', 'final-form-answers.md']\n"
        "    canonical: final-form-answers.md\n"
    )
    cfg = mod.read_lifecycle_config(tmp_path)
    g = cfg.known_groups[0]
    assert g.canonical_strategy == "explicit"
    assert g.members == ("augur-intel-form-answers.md", "final-form-answers.md")
    assert g.canonical == "final-form-answers.md"


def test_read_lifecycle_config_known_groups_not_a_group(tmp_path):
    (tmp_path / ".augur-lifecycle.yaml").write_text(
        "known_groups:\n"
        "  - name: linkedin-banner-personal\n"
        "    canonical_strategy: not_a_group\n"
        "    members: ['linkedin-banner-personal.png', 'linkedin-banner-personal-augur.png']\n"
    )
    cfg = mod.read_lifecycle_config(tmp_path)
    g = cfg.known_groups[0]
    assert g.canonical_strategy == "not_a_group"
    assert g.members == ("linkedin-banner-personal.png", "linkedin-banner-personal-augur.png")
    assert g.canonical is None


def test_read_lifecycle_config_known_groups_invalid_strategy_raises(tmp_path):
    (tmp_path / ".augur-lifecycle.yaml").write_text(
        "known_groups:\n"
        "  - name: x\n"
        "    canonical_strategy: bogus\n"
    )
    with pytest.raises(mod.LifecycleConfigError, match="canonical_strategy"):
        mod.read_lifecycle_config(tmp_path)


def test_read_lifecycle_config_known_groups_missing_pattern_raises(tmp_path):
    (tmp_path / ".augur-lifecycle.yaml").write_text(
        "known_groups:\n"
        "  - name: x\n"
        "    canonical_strategy: highest_version\n"
    )
    with pytest.raises(mod.LifecycleConfigError, match="requires 'pattern'"):
        mod.read_lifecycle_config(tmp_path)


def test_read_lifecycle_config_known_groups_missing_canonical_raises(tmp_path):
    (tmp_path / ".augur-lifecycle.yaml").write_text(
        "known_groups:\n"
        "  - name: x\n"
        "    canonical_strategy: explicit\n"
        "    members: ['a.md']\n"
    )
    with pytest.raises(mod.LifecycleConfigError, match="requires 'canonical'"):
        mod.read_lifecycle_config(tmp_path)


def test_read_lifecycle_config_known_groups_missing_members_raises(tmp_path):
    (tmp_path / ".augur-lifecycle.yaml").write_text(
        "known_groups:\n"
        "  - name: x\n"
        "    canonical_strategy: not_a_group\n"
    )
    with pytest.raises(mod.LifecycleConfigError, match="requires 'members'"):
        mod.read_lifecycle_config(tmp_path)


def test_read_lifecycle_config_known_groups_absent_returns_empty_tuple(tmp_path):
    (tmp_path / ".augur-lifecycle.yaml").write_text("enabled: true\n")
    cfg = mod.read_lifecycle_config(tmp_path)
    assert cfg.known_groups == ()
```

- [ ] **Step 7: Run all parser tests, confirm pass**

Run: `cd ~/Projects/Augur && uv run pytest shared-vault/skills/loop-hygiene/augur/tests/test_lifecycle_config.py -v`

Expected: all PASS (existing 8 + 7 new = 15 tests).

- [ ] **Step 8: Commit**

```bash
git add shared-vault/skills/loop-hygiene/scripts/lifecycle_config.py shared-vault/skills/loop-hygiene/augur/tests/test_lifecycle_config.py
git commit -m "feat(loop-hygiene): parse known_groups[] in .augur-lifecycle.yaml

Adds KnownGroup dataclass and parsing for three canonical_strategy values
(highest_version, explicit, not_a_group) with per-strategy required-field
validation. Backward compatible: absent known_groups defaults to ()."
```

---

## Task 2 — `known_groups.py` matcher module

**Files:**
- Create: `shared-vault/skills/loop-hygiene/scripts/known_groups.py`
- Create: `shared-vault/skills/loop-hygiene/augur/tests/test_known_groups.py`

- [ ] **Step 1: Write failing test for `match_known_groups`**

Create `shared-vault/skills/loop-hygiene/augur/tests/test_known_groups.py`:

```python
"""Tests for known_groups matcher."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
_LC_PATH = _SCRIPTS / "lifecycle_config.py"
_KG_PATH = _SCRIPTS / "known_groups.py"

_lc_spec = importlib.util.spec_from_file_location("lifecycle_config_under_test", _LC_PATH)
assert _lc_spec and _lc_spec.loader
lc = importlib.util.module_from_spec(_lc_spec)
sys.modules["lifecycle_config_under_test"] = lc
_lc_spec.loader.exec_module(lc)

_kg_spec = importlib.util.spec_from_file_location("known_groups_under_test", _KG_PATH)
assert _kg_spec and _kg_spec.loader
kg = importlib.util.module_from_spec(_kg_spec)
sys.modules["known_groups_under_test"] = kg
_kg_spec.loader.exec_module(kg)


def _files(*names):
    return [{"name": n, "relative_path": f"foo/{n}", "size_bytes": 1, "mtime_iso": "2026-01-01T00:00:00Z"} for n in names]


def test_match_known_groups_highest_version_picks_highest(tmp_path):
    files = _files("guriqo-com-V10001.zip", "guriqo-com-V10002.zip", "guriqo-com-V10032.zip")
    group = lc.KnownGroup(
        name="guriqo-com-build",
        canonical_strategy="highest_version",
        pattern="guriqo-com-*.zip",
    )
    result = kg.match_known_groups(files, [group])
    assert result.moves_by_group["guriqo-com-build"] == [
        "foo/guriqo-com-V10001.zip",
        "foo/guriqo-com-V10002.zip",
    ]
    assert result.no_touch == set()
    assert result.unmatched_files == []  # all consumed by the group
```

- [ ] **Step 2: Run, confirm failure**

Run: `cd ~/Projects/Augur && uv run pytest shared-vault/skills/loop-hygiene/augur/tests/test_known_groups.py -v`

Expected: FAIL — `RuntimeError: Unable to load known_groups from ...`.

- [ ] **Step 3: Create `known_groups.py` with the matcher**

Create `shared-vault/skills/loop-hygiene/scripts/known_groups.py`:

```python
"""Match files against cached known_groups entries.

Pure function. No I/O. Given a scan's file list and a tuple of
KnownGroup entries, returns the moves the agent should propose
without asking, plus the set of files marked "do not touch."
"""
from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from typing import Any

# Avoid importing LifecycleConfig at module-init time; the caller passes
# already-parsed KnownGroup objects. This keeps the matcher purely value-typed.


VERSION_TOKEN_RE = re.compile(r"[Vv](\d+)(?:-(\d+))?")


@dataclass(frozen=True)
class MatchResult:
    moves_by_group: dict[str, list[str]] = field(default_factory=dict)
    no_touch: set[str] = field(default_factory=set)
    unmatched_files: list[dict[str, Any]] = field(default_factory=list)


def _version_sort_key(name: str) -> tuple[int, int]:
    """Extract a sortable version tuple from a filename.

    Returns (major, minor). Files without a version marker sort as (-1, -1).
    """
    m = VERSION_TOKEN_RE.search(name)
    if m is None:
        return (-1, -1)
    major = int(m.group(1))
    minor = int(m.group(2)) if m.group(2) is not None else 0
    return (major, minor)


def match_known_groups(
    files: list[dict[str, Any]],
    groups: list[Any],  # list[KnownGroup]
) -> MatchResult:
    """Resolve every group against the file list.

    Args:
        files: scan output's `files` list (dicts with `name`, `relative_path`, etc.).
        groups: list of KnownGroup dataclass instances.

    Returns:
        MatchResult with:
          - moves_by_group: {group.name: [relative_paths to archive]}
          - no_touch: set of relative_paths that strategy=not_a_group claims
          - unmatched_files: file dicts not matched by any group (agent's Tier 1/2/3 input)
    """
    moves_by_group: dict[str, list[str]] = {}
    no_touch: set[str] = set()
    consumed_paths: set[str] = set()

    for g in groups:
        if g.canonical_strategy == "highest_version":
            assert g.pattern is not None
            matched = [f for f in files if fnmatch.fnmatch(f["name"], g.pattern)]
            if not matched:
                continue
            ordered = sorted(matched, key=lambda f: (_version_sort_key(f["name"]), f["mtime_iso"]))
            keep = ordered[-1]
            archive = ordered[:-1]
            moves_by_group[g.name] = [f["relative_path"] for f in archive]
            for f in matched:
                consumed_paths.add(f["relative_path"])

        elif g.canonical_strategy == "explicit":
            assert g.members is not None and g.canonical is not None
            member_set = set(g.members)
            matched = [f for f in files if f["name"] in member_set]
            if not matched:
                continue
            archive = [f for f in matched if f["name"] != g.canonical]
            moves_by_group[g.name] = [f["relative_path"] for f in archive]
            for f in matched:
                consumed_paths.add(f["relative_path"])

        elif g.canonical_strategy == "not_a_group":
            assert g.members is not None
            member_set = set(g.members)
            matched = [f for f in files if f["name"] in member_set]
            if not matched:
                continue
            for f in matched:
                no_touch.add(f["relative_path"])
                consumed_paths.add(f["relative_path"])

    unmatched = [f for f in files if f["relative_path"] not in consumed_paths]
    return MatchResult(
        moves_by_group=moves_by_group,
        no_touch=no_touch,
        unmatched_files=unmatched,
    )
```

- [ ] **Step 4: Run test, confirm pass**

Run: `cd ~/Projects/Augur && uv run pytest shared-vault/skills/loop-hygiene/augur/tests/test_known_groups.py::test_match_known_groups_highest_version_picks_highest -v`

Expected: PASS.

- [ ] **Step 5: Add tests for `explicit`, `not_a_group`, empty match, mixed strategies**

Append to `test_known_groups.py`:

```python
def test_match_known_groups_explicit_keeps_canonical(tmp_path):
    files = _files("augur-intel-form-answers.md", "final-form-answers.md", "unrelated.md")
    group = lc.KnownGroup(
        name="form-answers",
        canonical_strategy="explicit",
        members=("augur-intel-form-answers.md", "final-form-answers.md"),
        canonical="final-form-answers.md",
    )
    result = kg.match_known_groups(files, [group])
    assert result.moves_by_group["form-answers"] == ["foo/augur-intel-form-answers.md"]
    assert result.no_touch == set()
    assert [f["name"] for f in result.unmatched_files] == ["unrelated.md"]


def test_match_known_groups_not_a_group_no_moves(tmp_path):
    files = _files("linkedin-banner-personal.png", "linkedin-banner-personal-augur.png")
    group = lc.KnownGroup(
        name="linkedin-banner-personal",
        canonical_strategy="not_a_group",
        members=("linkedin-banner-personal.png", "linkedin-banner-personal-augur.png"),
    )
    result = kg.match_known_groups(files, [group])
    assert result.moves_by_group == {}
    assert result.no_touch == {"foo/linkedin-banner-personal.png", "foo/linkedin-banner-personal-augur.png"}
    assert result.unmatched_files == []


def test_match_known_groups_no_matches_returns_all_unmatched(tmp_path):
    files = _files("a.md", "b.md")
    group = lc.KnownGroup(
        name="x",
        canonical_strategy="highest_version",
        pattern="nonmatching-*.zip",
    )
    result = kg.match_known_groups(files, [group])
    assert result.moves_by_group == {}
    assert len(result.unmatched_files) == 2


def test_match_known_groups_version_sort_handles_mixed_schemes(tmp_path):
    files = _files(
        "guriqo-com-v33-1.zip",
        "guriqo-com-v45-1.zip",
        "guriqo-com-V10001.zip",
        "guriqo-com-V10032.zip",
    )
    group = lc.KnownGroup(
        name="g",
        canonical_strategy="highest_version",
        pattern="guriqo-com-*.zip",
    )
    result = kg.match_known_groups(files, [group])
    # V10032 has the highest major (10032), so it wins.
    archived = result.moves_by_group["g"]
    assert "foo/guriqo-com-V10032.zip" not in archived
    assert len(archived) == 3
```

- [ ] **Step 6: Run all matcher tests**

Run: `cd ~/Projects/Augur && uv run pytest shared-vault/skills/loop-hygiene/augur/tests/test_known_groups.py -v`

Expected: 4 PASS.

- [ ] **Step 7: Commit**

```bash
git add shared-vault/skills/loop-hygiene/scripts/known_groups.py shared-vault/skills/loop-hygiene/augur/tests/test_known_groups.py
git commit -m "feat(loop-hygiene): add known_groups matcher

Pure function that resolves cached KnownGroup entries against a scan's
file list. Supports highest_version (glob + numeric sort), explicit
(named members, named canonical), and not_a_group (no-touch). Mixed
version schemes (v33-1 vs V10032) sort correctly by numeric major."
```

---

## Task 3 — `lifecycle_writer.py` atomic YAML writer

**Files:**
- Create: `shared-vault/skills/loop-hygiene/scripts/lifecycle_writer.py`
- Create: `shared-vault/skills/loop-hygiene/augur/tests/test_lifecycle_writer.py`

- [ ] **Step 1: Write failing test for new-file creation**

Create `shared-vault/skills/loop-hygiene/augur/tests/test_lifecycle_writer.py`:

```python
"""Tests for atomic .augur-lifecycle.yaml writer."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
_LW_PATH = _SCRIPTS / "lifecycle_writer.py"

_spec = importlib.util.spec_from_file_location("lifecycle_writer_under_test", _LW_PATH)
assert _spec and _spec.loader
lw = importlib.util.module_from_spec(_spec)
sys.modules["lifecycle_writer_under_test"] = lw
_spec.loader.exec_module(lw)


def test_append_known_group_creates_new_yaml(tmp_path):
    entry = {
        "name": "g1",
        "canonical_strategy": "highest_version",
        "pattern": "a-*.zip",
        "decided_at": "2026-05-12T14:30:00Z",
        "decided_by": "gsannikov",
    }
    lw.append_known_group(tmp_path, entry)
    data = yaml.safe_load((tmp_path / ".augur-lifecycle.yaml").read_text())
    assert data["known_groups"][0]["name"] == "g1"
    assert data["known_groups"][0]["canonical_strategy"] == "highest_version"
```

- [ ] **Step 2: Run, confirm failure**

Run: `cd ~/Projects/Augur && uv run pytest shared-vault/skills/loop-hygiene/augur/tests/test_lifecycle_writer.py -v`

Expected: FAIL — file doesn't exist.

- [ ] **Step 3: Create writer module**

Create `shared-vault/skills/loop-hygiene/scripts/lifecycle_writer.py`:

```python
"""Atomic writer for .augur-lifecycle.yaml known_groups[] section.

Writes via temp-file + os.rename for atomicity. Refuses on name collision
within the target folder. Does not validate semantics (caller is expected
to pass a well-formed entry — schema is enforced at read time).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


class LifecycleWriterError(ValueError):
    """Raised on collision or write failure."""


class LifecycleWriterCollision(LifecycleWriterError):
    """Raised when an entry with the same name already exists."""


def append_known_group(folder: Path, entry: dict[str, Any]) -> Path:
    """Append a known_group entry to folder/.augur-lifecycle.yaml atomically.

    Args:
        folder: directory containing (or to contain) .augur-lifecycle.yaml.
        entry: dict with at least 'name' and 'canonical_strategy'.

    Returns:
        The Path of the written .augur-lifecycle.yaml.

    Raises:
        LifecycleWriterCollision: if an entry with the same `name` already exists.
        LifecycleWriterError: on YAML write failure.
    """
    if "name" not in entry or not entry["name"]:
        raise LifecycleWriterError("entry must include non-empty 'name'")

    target = folder / ".augur-lifecycle.yaml"
    if target.exists():
        try:
            existing = yaml.safe_load(target.read_text()) or {}
        except yaml.YAMLError as exc:
            raise LifecycleWriterError(f"existing yaml malformed: {exc}") from exc
        if not isinstance(existing, dict):
            raise LifecycleWriterError(f"existing yaml top-level is not a mapping")
    else:
        existing = {}

    groups = existing.get("known_groups", [])
    if not isinstance(groups, list):
        raise LifecycleWriterError("existing known_groups is not a list")

    for g in groups:
        if isinstance(g, dict) and g.get("name") == entry["name"]:
            raise LifecycleWriterCollision(
                f"known_groups entry with name={entry['name']!r} already exists"
            )

    groups.append(entry)
    existing["known_groups"] = groups

    tmp = target.with_suffix(".yaml.tmp")
    tmp.write_text(yaml.safe_dump(existing, sort_keys=False))
    os.rename(tmp, target)
    return target
```

- [ ] **Step 4: Run test, confirm pass**

Run: `cd ~/Projects/Augur && uv run pytest shared-vault/skills/loop-hygiene/augur/tests/test_lifecycle_writer.py::test_append_known_group_creates_new_yaml -v`

Expected: PASS.

- [ ] **Step 5: Add tests for append-to-existing, collision, atomicity**

Append to `test_lifecycle_writer.py`:

```python
def test_append_known_group_appends_to_existing_yaml(tmp_path):
    (tmp_path / ".augur-lifecycle.yaml").write_text(
        "enabled: true\n"
        "pattern_hints: ['a-*.zip']\n"
        "known_groups:\n"
        "  - name: existing\n"
        "    canonical_strategy: highest_version\n"
        "    pattern: 'x-*.zip'\n"
    )
    entry = {"name": "new", "canonical_strategy": "not_a_group", "members": ["a.png", "b.png"]}
    lw.append_known_group(tmp_path, entry)
    data = yaml.safe_load((tmp_path / ".augur-lifecycle.yaml").read_text())
    assert data["enabled"] is True
    assert data["pattern_hints"] == ["a-*.zip"]
    assert len(data["known_groups"]) == 2
    assert data["known_groups"][1]["name"] == "new"


def test_append_known_group_collision_raises(tmp_path):
    (tmp_path / ".augur-lifecycle.yaml").write_text(
        "known_groups:\n"
        "  - name: dup\n"
        "    canonical_strategy: highest_version\n"
        "    pattern: 'x-*.zip'\n"
    )
    with pytest.raises(lw.LifecycleWriterCollision, match="dup"):
        lw.append_known_group(tmp_path, {"name": "dup", "canonical_strategy": "not_a_group", "members": ["a"]})


def test_append_known_group_missing_name_raises(tmp_path):
    with pytest.raises(lw.LifecycleWriterError, match="name"):
        lw.append_known_group(tmp_path, {"canonical_strategy": "highest_version"})


def test_append_known_group_atomic_no_tempfile_left(tmp_path):
    lw.append_known_group(tmp_path, {"name": "g", "canonical_strategy": "highest_version", "pattern": "x-*"})
    assert not (tmp_path / ".augur-lifecycle.yaml.tmp").exists()
    assert (tmp_path / ".augur-lifecycle.yaml").exists()


def test_append_known_group_malformed_existing_raises(tmp_path):
    (tmp_path / ".augur-lifecycle.yaml").write_text("not: valid: yaml: :")
    with pytest.raises(lw.LifecycleWriterError, match="malformed"):
        lw.append_known_group(tmp_path, {"name": "g", "canonical_strategy": "highest_version", "pattern": "x-*"})
```

- [ ] **Step 6: Run all writer tests**

Run: `cd ~/Projects/Augur && uv run pytest shared-vault/skills/loop-hygiene/augur/tests/test_lifecycle_writer.py -v`

Expected: 5 PASS.

- [ ] **Step 7: Commit**

```bash
git add shared-vault/skills/loop-hygiene/scripts/lifecycle_writer.py shared-vault/skills/loop-hygiene/augur/tests/test_lifecycle_writer.py
git commit -m "feat(loop-hygiene): atomic known_groups[] writer

Adds lifecycle_writer.append_known_group() — atomic temp-rename write
with name-collision refusal. Preserves existing top-level fields.
Refuses malformed existing YAML rather than overwriting silently."
```

---

## Task 4 — Wire `known_groups` through `hygiene-scan` output

**Files:**
- Modify: `shared-vault/skills/loop-hygiene/scripts/hygiene_scan.py:80-152` (the `hygiene_scan` function body)
- Modify: `shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_scan.py`

- [ ] **Step 1: Write failing test**

Append to `shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_scan.py`:

```python
def test_hygiene_scan_returns_known_groups_in_lifecycle_config(tmp_path, monkeypatch):
    docs_root = tmp_path / "docs"
    folder = docs_root / "venture-augur" / "websites"
    folder.mkdir(parents=True)
    (folder / ".augur-lifecycle.yaml").write_text(
        "known_groups:\n"
        "  - name: guriqo-com-build\n"
        "    canonical_strategy: highest_version\n"
        "    pattern: 'guriqo-com-*.zip'\n"
        "    decided_at: '2026-05-12T14:30:00Z'\n"
        "    decided_by: gsannikov\n"
    )
    (folder / "guriqo-com-V10001.zip").write_bytes(b"x")

    monkeypatch.setattr(mod, "get_documents_dir", lambda: docs_root)

    result = mod.hygiene_scan(str(folder))
    assert result["lifecycle_config"]["known_groups"][0]["name"] == "guriqo-com-build"
    assert result["lifecycle_config"]["known_groups"][0]["canonical_strategy"] == "highest_version"
    assert result["lifecycle_config"]["known_groups"][0]["pattern"] == "guriqo-com-*.zip"
```

(Adjust the importlib loader block at the top of `test_hygiene_scan.py` as needed if it doesn't already expose `mod.get_documents_dir`. The existing tests in this file already monkeypatch this attribute — follow that pattern.)

- [ ] **Step 2: Run, confirm failure**

Run: `cd ~/Projects/Augur && uv run pytest shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_scan.py::test_hygiene_scan_returns_known_groups_in_lifecycle_config -v`

Expected: FAIL — `KeyError: 'known_groups'` (current `LifecycleConfig` had no such field; now it does after Task 1, but the `asdict` flow may emit tuples that don't serialize cleanly through JSON).

- [ ] **Step 3: Confirm `asdict()` flow handles the new field**

No new code is needed if Task 1 succeeded — `dataclasses.asdict` recursively converts the `tuple[KnownGroup, ...]` into a list of dicts. Verify by re-running the test.

If the test fails because tuples aren't serializable downstream, modify `hygiene_scan.py` around line 110:

```python
if cfg is not None:
    if not cfg.enabled:
        raise HygieneScanError(
            f"lifecycle enabled: false at {candidate} — refusing scan"
        )
    lifecycle_config = asdict(cfg)
    # Normalize tuples to lists for downstream JSON serialization clarity
    if "known_groups" in lifecycle_config:
        for g in lifecycle_config["known_groups"]:
            if g.get("members") is not None:
                g["members"] = list(g["members"])
```

- [ ] **Step 4: Run test, confirm pass**

Run: `cd ~/Projects/Augur && uv run pytest shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_scan.py::test_hygiene_scan_returns_known_groups_in_lifecycle_config -v`

Expected: PASS.

- [ ] **Step 5: Add test for malformed `known_groups` → warning, not crash**

Append to `test_hygiene_scan.py`:

```python
def test_hygiene_scan_malformed_known_groups_surfaces_warning(tmp_path, monkeypatch):
    docs_root = tmp_path / "docs"
    folder = docs_root / "x"
    folder.mkdir(parents=True)
    (folder / ".augur-lifecycle.yaml").write_text(
        "known_groups:\n"
        "  - name: bad\n"
        "    canonical_strategy: bogus\n"
    )
    (folder / "f.txt").write_bytes(b"x")

    monkeypatch.setattr(mod, "get_documents_dir", lambda: docs_root)

    result = mod.hygiene_scan(str(folder))
    assert result["lifecycle_config"] is None  # parse failed, warning emitted
    assert any("canonical_strategy" in w for w in result["warnings"])
```

- [ ] **Step 6: Run, confirm pass**

Run: `cd ~/Projects/Augur && uv run pytest shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_scan.py -v`

Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add shared-vault/skills/loop-hygiene/scripts/hygiene_scan.py shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_scan.py
git commit -m "feat(loop-hygiene): emit known_groups in hygiene-scan output

lifecycle_config dict now includes known_groups[] with each entry's
strategy, pattern/members/canonical, and decision metadata.
Malformed entries surface as warnings, not crashes."
```

---

## Task 5 — Extend `hygiene_apply` with `lifecycle_updates` parameter

**Files:**
- Modify: `shared-vault/skills/loop-hygiene/scripts/hygiene_apply.py:73-178`
- Modify: `shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_apply.py`

- [ ] **Step 1: Write failing test — YAML written before moves**

Append to `shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_apply.py`:

```python
def test_hygiene_apply_lifecycle_updates_writes_yaml_before_moves(tmp_path, monkeypatch):
    docs_root = tmp_path / "docs"
    folder = docs_root / "ws"
    folder.mkdir(parents=True)
    (folder / "x.zip").write_bytes(b"x")

    monkeypatch.setattr(mod, "get_documents_dir", lambda: docs_root)

    lifecycle_updates = [
        {
            "folder": "ws",
            "known_group": {
                "name": "g1",
                "canonical_strategy": "highest_version",
                "pattern": "x-*.zip",
                "decided_at": "2026-05-12T14:30:00Z",
                "decided_by": "gsannikov",
            },
        }
    ]
    result = mod.hygiene_apply(
        root="docs",
        moves=[{"from": "ws/x.zip", "reason": "test"}],
        dry_run=False,
        lifecycle_updates=lifecycle_updates,
    )
    # YAML was written
    yaml_path = folder / ".augur-lifecycle.yaml"
    assert yaml_path.exists()
    import yaml as _yaml
    data = _yaml.safe_load(yaml_path.read_text())
    assert data["known_groups"][0]["name"] == "g1"
    # Move also succeeded
    assert result["moves"][0]["status"] == "succeeded"
    # lifecycle_updates surfaced in result
    assert len(result["lifecycle_updates"]) == 1
    assert result["lifecycle_updates"][0]["status"] == "written"
```

- [ ] **Step 2: Run, confirm failure**

Run: `cd ~/Projects/Augur && uv run pytest shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_apply.py::test_hygiene_apply_lifecycle_updates_writes_yaml_before_moves -v`

Expected: FAIL — `TypeError: hygiene_apply() got an unexpected keyword argument 'lifecycle_updates'`.

- [ ] **Step 3: Extend `hygiene_apply` signature + add lifecycle-update handling**

In `hygiene_apply.py`, add a sibling loader for `lifecycle_writer` near the existing loaders (after the `_lc_mod` block, around line 55):

```python
_LIFECYCLE_WRITER_PATH = _AugurPath(__file__).resolve().parent / "lifecycle_writer.py"
_lw_spec = _augur_importlib_util.spec_from_file_location("loop_hygiene_apply_lifecycle_writer", _LIFECYCLE_WRITER_PATH)
if _lw_spec is None or _lw_spec.loader is None:
    raise RuntimeError(f"Unable to load lifecycle_writer from {_LIFECYCLE_WRITER_PATH}")
_lw_mod = _augur_importlib_util.module_from_spec(_lw_spec)
_augur_sys.modules["loop_hygiene_apply_lifecycle_writer"] = _lw_mod
_lw_spec.loader.exec_module(_lw_mod)
append_known_group = _lw_mod.append_known_group
LifecycleWriterCollision = _lw_mod.LifecycleWriterCollision
LifecycleWriterError = _lw_mod.LifecycleWriterError
```

Modify the `hygiene_apply` signature and body:

```python
def hygiene_apply(
    root: str,
    moves: list[dict[str, Any]],
    dry_run: bool,
    lifecycle_updates: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Apply (or dry-run) a list of archive moves and optional lifecycle updates.

    Args:
        root: store identifier. MVP supports only "docs".
        moves: list of {from, reason, artifact_group} dicts.
        dry_run: when True, validate every move without modifying disk.
        lifecycle_updates: optional list of {folder, known_group} entries to
            append to the per-folder .augur-lifecycle.yaml. Written BEFORE
            moves so the cache persists even if some moves later fail.

    Returns:
        Dict with: dry_run, moves, total_bytes_archived, paths_written,
        lifecycle_updates (per-update results).
    """
    if root not in SUPPORTED_ROOTS:
        raise HygieneApplyError(
            f"unsupported root: {root!r}; MVP supports only {sorted(SUPPORTED_ROOTS)}"
        )

    store_root = get_documents_dir().resolve()
    lifecycle_results = _process_lifecycle_updates(
        lifecycle_updates or [],
        store_root,
        dry_run,
    )

    # ... rest of existing body unchanged through the return ...

    return {
        "dry_run": dry_run,
        "moves": move_results,
        "total_bytes_archived": total_bytes,
        "paths_written": paths_written,
        "lifecycle_updates": lifecycle_results,
    }
```

Add helper at module bottom:

```python
def _process_lifecycle_updates(
    updates: list[dict[str, Any]],
    store_root: Path,
    dry_run: bool,
) -> list[dict[str, Any]]:
    """Write each update to its folder's .augur-lifecycle.yaml.

    On collision or write failure, returns per-update refusal but does NOT
    abort other updates or moves. Dry-run validates only.
    """
    results: list[dict[str, Any]] = []
    for upd in updates:
        folder_rel = upd.get("folder")
        entry = upd.get("known_group")
        result: dict[str, Any] = {
            "folder": folder_rel,
            "known_group_name": (entry or {}).get("name"),
        }
        if not isinstance(folder_rel, str) or not isinstance(entry, dict):
            result["status"] = "refused"
            result["refusal_category"] = "malformed_update"
            results.append(result)
            continue
        folder_abs = (store_root / folder_rel).resolve()
        try:
            folder_abs.relative_to(store_root)
        except ValueError:
            result["status"] = "refused"
            result["refusal_category"] = "outside_store"
            results.append(result)
            continue
        if not folder_abs.is_dir():
            result["status"] = "refused"
            result["refusal_category"] = "folder_missing"
            results.append(result)
            continue

        if dry_run:
            # Validate collision without writing.
            yaml_path = folder_abs / ".augur-lifecycle.yaml"
            if yaml_path.exists():
                try:
                    existing = yaml.safe_load(yaml_path.read_text()) or {}
                    for g in existing.get("known_groups", []) or []:
                        if isinstance(g, dict) and g.get("name") == entry.get("name"):
                            result["status"] = "would_refuse"
                            result["refusal_category"] = "lifecycle_collision"
                            results.append(result)
                            break
                    else:
                        result["status"] = "would_succeed"
                        results.append(result)
                    continue
                except yaml.YAMLError:
                    result["status"] = "would_refuse"
                    result["refusal_category"] = "lifecycle_malformed"
                    results.append(result)
                    continue
            result["status"] = "would_succeed"
            results.append(result)
            continue

        try:
            append_known_group(folder_abs, entry)
            result["status"] = "written"
        except LifecycleWriterCollision as exc:
            result["status"] = "refused"
            result["refusal_category"] = "lifecycle_collision"
            result["error"] = str(exc)
        except LifecycleWriterError as exc:
            result["status"] = "refused"
            result["refusal_category"] = "lifecycle_malformed"
            result["error"] = str(exc)
        results.append(result)
    return results
```

Also at the top, add `import yaml` to the imports block (after the existing imports around line 60-65).

- [ ] **Step 4: Run test, confirm pass**

Run: `cd ~/Projects/Augur && uv run pytest shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_apply.py::test_hygiene_apply_lifecycle_updates_writes_yaml_before_moves -v`

Expected: PASS.

- [ ] **Step 5: Add tests for dry-run, collision, malformed folder**

Append to `test_hygiene_apply.py`:

```python
def test_hygiene_apply_lifecycle_updates_dry_run_writes_nothing(tmp_path, monkeypatch):
    docs_root = tmp_path / "docs"
    folder = docs_root / "ws"
    folder.mkdir(parents=True)
    (folder / "x.zip").write_bytes(b"x")

    monkeypatch.setattr(mod, "get_documents_dir", lambda: docs_root)
    result = mod.hygiene_apply(
        root="docs",
        moves=[{"from": "ws/x.zip", "reason": "test"}],
        dry_run=True,
        lifecycle_updates=[{"folder": "ws", "known_group": {"name": "g", "canonical_strategy": "highest_version", "pattern": "x-*"}}],
    )
    assert not (folder / ".augur-lifecycle.yaml").exists()
    assert result["lifecycle_updates"][0]["status"] == "would_succeed"


def test_hygiene_apply_lifecycle_updates_collision_refused(tmp_path, monkeypatch):
    docs_root = tmp_path / "docs"
    folder = docs_root / "ws"
    folder.mkdir(parents=True)
    (folder / "x.zip").write_bytes(b"x")
    (folder / ".augur-lifecycle.yaml").write_text(
        "known_groups:\n"
        "  - name: dup\n"
        "    canonical_strategy: highest_version\n"
        "    pattern: 'x-*'\n"
    )

    monkeypatch.setattr(mod, "get_documents_dir", lambda: docs_root)
    result = mod.hygiene_apply(
        root="docs",
        moves=[{"from": "ws/x.zip", "reason": "test"}],
        dry_run=False,
        lifecycle_updates=[{"folder": "ws", "known_group": {"name": "dup", "canonical_strategy": "not_a_group", "members": ["a"]}}],
    )
    assert result["lifecycle_updates"][0]["status"] == "refused"
    assert result["lifecycle_updates"][0]["refusal_category"] == "lifecycle_collision"
    # Move still proceeds
    assert result["moves"][0]["status"] == "succeeded"


def test_hygiene_apply_lifecycle_updates_folder_missing(tmp_path, monkeypatch):
    docs_root = tmp_path / "docs"
    docs_root.mkdir()
    monkeypatch.setattr(mod, "get_documents_dir", lambda: docs_root)
    result = mod.hygiene_apply(
        root="docs",
        moves=[],
        dry_run=False,
        lifecycle_updates=[{"folder": "nonexistent", "known_group": {"name": "g", "canonical_strategy": "highest_version", "pattern": "x"}}],
    )
    assert result["lifecycle_updates"][0]["status"] == "refused"
    assert result["lifecycle_updates"][0]["refusal_category"] == "folder_missing"


def test_hygiene_apply_no_lifecycle_updates_field_omitted(tmp_path, monkeypatch):
    docs_root = tmp_path / "docs"
    docs_root.mkdir()
    monkeypatch.setattr(mod, "get_documents_dir", lambda: docs_root)
    # Calling without lifecycle_updates keyword should work
    result = mod.hygiene_apply(root="docs", moves=[], dry_run=True)
    assert result["lifecycle_updates"] == []
```

- [ ] **Step 6: Run all hygiene_apply tests**

Run: `cd ~/Projects/Augur && uv run pytest shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_apply.py -v`

Expected: all PASS (existing + 4 new).

- [ ] **Step 7: Commit**

```bash
git add shared-vault/skills/loop-hygiene/scripts/hygiene_apply.py shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_apply.py
git commit -m "feat(loop-hygiene): hygiene_apply accepts lifecycle_updates

Optional lifecycle_updates param drives append-known-group writes to
per-folder .augur-lifecycle.yaml. YAML written BEFORE moves so cached
decisions persist even if moves later fail. Per-update refusals
(lifecycle_collision, lifecycle_malformed, outside_store, folder_missing)
surface independently from move refusals."
```

---

## Task 6 — Rewrite `references/sweep-rubric.md` with tier rubric

**Files:**
- Modify: `shared-vault/skills/loop-hygiene/references/sweep-rubric.md`

- [ ] **Step 1: Replace the full rubric with the tiered version**

Overwrite `shared-vault/skills/loop-hygiene/references/sweep-rubric.md` with:

```markdown
# /sweep-stores classification rubric

This is the rubric the agent applies to `hygiene-scan` output to decide which files are stale versions and which are current. It pairs with the slash command at `commands/sweep-stores.md` (the workflow surface).

## Step 0 — Known-group matching (before classification)

Before any tier work, the agent applies cached decisions from the scan output's `lifecycle_config.known_groups[]`:

- For each `KnownGroup` entry:
  - `canonical_strategy: highest_version` → use `pattern` (glob) to collect files; archive all but the highest-version (numeric major.minor sort; mtime tiebreaker). No question.
  - `canonical_strategy: explicit` → use `members[]`; archive every member except `canonical`. No question.
  - `canonical_strategy: not_a_group` → use `members[]`; mark all matched files as "no-touch this sweep." No proposal, no question.
- Files consumed by known-group matching are removed from the candidate pool before tier classification.

## Tier 1 — High confidence (propose autonomously, no question)

**Signal:** files share a base name + a version-marker token matching the regex `[Vv]\d+(-\d+)?`.

**Example:** `guriqo-com-V10015.zip` … `guriqo-com-V10032.zip`.

**Action:** propose archive of all-but-highest. Tiebreaker: latest `mtime_iso`.

## Tier 2 — Medium confidence (one batched question per fuzzy group)

**Signal triggers (any of):**
- **(a) Mixed version schemes** — shared base + DIFFERENT version-marker conventions across files (e.g., `guriqo-com-v33-1.zip` + `guriqo-com-V10032.zip`).
- **(b) Variant suffixes** — shared base + role-qualifier suffix differs (`linkedin-banner-personal.png` vs `linkedin-banner-personal-augur.png`).
- **(c) Renamed iterations** — names differ but share at least one role token (substring ≥ 6 chars, tokenized on `-`/`_`/`.`, ignoring version markers and common suffixes like `final`/`draft`) AND mtimes are chronologically ordered (older first).

**Action:** ONE single-select question per group via `AskUserQuestion`. Options:
- "Same group, keep `<newest by mtime>`"
- "Same group, keep `<alternative>`" (only when a non-trivial alternative exists)
- "Not a group, keep both/all"

The answer becomes a `known_groups[]` entry on `--apply`.

## Tier 3 — Low confidence (content inspection, then question)

**Signal triggers (any of):**
- **(d) Format-sibling pair where one is abandoned** — same base + different extension AND mtime gap > 60 days AND only one was modified in the last 30 days. The recently-touched file is the implied canonical.
- **(e) Conceptual supersession** — no name overlap but role keywords match across files (e.g., both contain `pricing` and one references the other's deprecation in frontmatter or first H1).

**Action:**
1. Agent reads file content via Read tool — text files only (`.md`, `.txt`, `.html`, `.yaml`, `.yml`, `.json`, `.rst`, `.csv`, `.sh`), ≤ 200 lines each. Extract: frontmatter (status/version/supersedes/replaces fields), first H1, `Replaces:` / `Supersedes:` / `Obsoletes:` lines, DRAFT/TODO/DEPRECATED markers.
2. For binaries (`.pptx`, `.docx`, `.pdf`, images, videos, archives), agent reports only `name`, `size_bytes`, `mtime_iso` — no parsing. Use sibling `.meta.yaml` if present.
3. Agent forms a hypothesis: "X appears to supersede Y because `<evidence>`."
4. `AskUserQuestion` presents the hypothesis as the first option, plus 2 alternatives.
5. Hard cap: 10 files inspected per sweep. If a Tier 3 group has more than 10 candidates, agent skips the group and tells the user to use milestone-pin or hand-edit `.augur-lifecycle.yaml`.

## Always-skip cases

- Different formats at the same logical version (`augur-vision-1.pdf` + `augur-vision-1.pptx`, mtimes within 7 days) → both canonical, no proposal, no question.
- Files in `milestone_pins` → already refused by `hygiene-apply`.
- Files in `never_touch_skipped` → already excluded by `hygiene-scan`.
- Files in folders with `deploy_root: true` → reported but never proposed (existing rule).

## Question budget

- **Hard cap: 4 questions per sweep** (the `AskUserQuestion` tool's maximum).
- Batched: a single `AskUserQuestion` call carries all open questions.
- If more than 4 groups need asking, agent surfaces the first 4 (folder-order, then alphabetical) and reports the rest as "deferred — re-run after answering current batch."

## Required output format

Before any `hygiene-apply` call, agent shows the user:

```
## Sweep proposal — <scanned_path>

### Group: <artifact_group>  (<N> stale + 1 current)
- Keep: <current-filename>  (size, mtime)
- Archive:
  - <stale-filename>  reason: superseded by <current-filename>
  - ...

### From cached known_groups (no question asked)
- Group <name> (strategy=<strategy>): N moves derived from cache.

### Refused / skipped
- <filename>  category: <deploy_root | milestone_pinned | never_touch>  reason: ...

### New decisions to cache
- known_groups[].name=<name>, strategy=<strategy>, decided_at=<now>
  (only if Tier 2/3 questions were answered this sweep)

Total: <N> moves, <total-bytes> archived.
```

## Edge cases

- Single member in a group → no proposal; the file is already canonical.
- Group spans subfolders → agent does NOT recurse; shallow walk only (matches `hygiene-scan`).
- Ambiguous case with no clear signal → describe the ambiguity, ask the user, do NOT guess.
- `known_groups` entry references a file no longer present → entry is silently ignored this sweep (cache is additive, not failing).
- User answers "skip" to a question → group is untouched; no `lifecycle_updates` entry written.
```

- [ ] **Step 2: Sanity check the rubric file is well-formed**

Run: `cd ~/Projects/Augur && head -10 shared-vault/skills/loop-hygiene/references/sweep-rubric.md`

Expected: first 10 lines render as the new rubric header.

- [ ] **Step 3: Commit**

```bash
git add shared-vault/skills/loop-hygiene/references/sweep-rubric.md
git commit -m "docs(loop-hygiene): rewrite sweep-rubric with tier 1/2/3 + known_groups

Replaces the flat rule list with three explicit signal-driven tiers and
adds the cached-known-groups matching step. Defines the interactive Q&A
budget (4 questions/sweep, 10 file content inspections/sweep) and the
new output sections (cached decisions, new decisions to cache)."
```

---

## Task 7 — Update `commands/sweep-stores.md` workflow

**Files:**
- Modify: `shared-vault/skills/loop-hygiene/commands/sweep-stores.md`

- [ ] **Step 1: Rewrite the "What it does" and add Q&A protocol**

Read the current file first to preserve invocation forms and frontmatter. Then replace the "What it does" section (steps 1-6) and add a new "Interactive Q&A protocol" section. New section block to insert in the file (replace the current numbered steps):

```markdown
## What it does (read this carefully before acting)

1. Call MCP tool `hygiene-scan <path>` to get the file listing, lifecycle config (now including `known_groups[]`), milestone pins, and never-touch skips.

2. **Apply cached known-group decisions** (step 0 of the rubric):
   - For each entry in `lifecycle_config.known_groups[]`, resolve members and apply the cached strategy. Consumed files are removed from the candidate pool.

3. **Classify remaining files** using the tiered rubric at `references/sweep-rubric.md`:
   - Tier 1 → autonomous proposal.
   - Tier 2 → collect into question batch.
   - Tier 3 → read content via Read tool (text files, ≤ 200 lines, ≤ 10 files per sweep), then collect into question batch.

4. **Ask the user (if question batch is non-empty)**:
   - Single `AskUserQuestion` call with up to 4 questions. More groups means deferred questions ("re-run after answering current batch").
   - Each question is single-select with three options:
     - "Same group, keep `<X>`"
     - "Same group, keep `<Y>`" (alternative)
     - "Not a group, keep both/all"
   - Build `lifecycle_updates[]` from answers.

5. **Present the structured proposal** (cached-derived + Tier 1 + Tier 2/3 answered). Do NOT call `hygiene-apply` yet.

6. **Wait for explicit user approval.** Accepted forms: `apply`, `apply only group X`, `skip group Y`, `tag file Z as milestone first then apply`.

7. **On approval, call `hygiene-apply`** with:
   - `root="docs"`
   - `moves=[{from: relative_path, reason: "...", artifact_group: "..."}]`
   - `lifecycle_updates=[{folder: ..., known_group: {...}}]` (only when Tier 2/3 questions were answered this sweep)
   - `dry_run=false` if and only if the user passed `--apply`; otherwise `dry_run=true`.

8. **Report the result**, including:
   - Per-move refusals (with `refusal_category`).
   - Per-update results: `written` / `would_succeed` / `refused` (with `refusal_category`: `lifecycle_collision`, `lifecycle_malformed`, `outside_store`, `folder_missing`, `malformed_update`).
   - Reminder to verify in a fresh AI client session that archived files are no longer surfaced.
```

Also add a new section after "Rubric (full text)":

```markdown
## Interactive Q&A protocol

When the rubric assigns a group to Tier 2 or Tier 3, the agent emits ONE `AskUserQuestion` call carrying all questions for this sweep (up to 4). Each question has:

- **Subject line:** the candidate filenames and the signal that triggered the tier (one sentence).
- **Options (single-select):**
  - For Tier 2: `Same group, keep <newest>` / `Same group, keep <alternative>` / `Not a group, keep both/all`.
  - For Tier 3: `<hypothesis option>` (e.g., "Y supersedes X (Y has 'Replaces: X' in frontmatter)") / `Same group, keep X instead` / `Not a group, keep both`.

The user's answer drives:
- A move list addition (or no-op for `not_a_group`).
- A `lifecycle_updates[]` entry that hygiene-apply will write to `.augur-lifecycle.yaml`'s `known_groups[]` section.

The agent must NOT call `AskUserQuestion` with more than 4 questions. If more groups need asking, defer the rest and report them in the proposal as "deferred — re-run after current batch."

The agent must NOT inspect content for files outside Tier 3. Tier 3 content inspection has a hard cap of 10 files per sweep; over-limit groups are skipped with a "use milestone-pin or hand-edit lifecycle.yaml" pointer.
```

- [ ] **Step 2: Verify the command file is well-formed**

Run: `cd ~/Projects/Augur && head -30 shared-vault/skills/loop-hygiene/commands/sweep-stores.md`

Expected: shows the updated invocation forms and "What it does" header.

- [ ] **Step 3: Regenerate propagated copies via sync**

Run: `cd ~/Projects/Augur && uv run python skills/ai/scripts/sync_agents.py sync commands all` (or `sync all` per memory entry `feedback_sync_agents_artifact_scope.md`).

Expected: command stubs in all AI-client directories updated.

If `sync_agents.py` path differs, run: `cd ~/Projects/Augur && find . -name "sync_agents.py" -not -path "*/node_modules/*" -not -path "*/.venv/*"` to find it.

- [ ] **Step 4: Commit**

```bash
git add shared-vault/skills/loop-hygiene/commands/sweep-stores.md
# also stage regenerated stubs if sync_agents.py touched them
git add -A
git commit -m "feat(loop-hygiene): /sweep-stores workflow with cached known_groups + Q&A

Adds step 0 (known-group matching from cached entries), step 4
(interactive question batch via AskUserQuestion, max 4 questions/sweep),
and lifecycle_updates handoff to hygiene-apply. Tier 3 content
inspection capped at 10 files per sweep."
```

---

## Task 8 — Update `augur/data/lifecycle_schema.yaml`

**Files:**
- Modify: `shared-vault/skills/loop-hygiene/augur/data/lifecycle_schema.yaml`

- [ ] **Step 1: Read the existing schema**

Run: `cat ~/Projects/Augur/shared-vault/skills/loop-hygiene/augur/data/lifecycle_schema.yaml`

- [ ] **Step 2: Append `known_groups` to the schema**

Append to the existing schema file (JSON Schema or equivalent format — preserve the existing top-level structure). The new fragment:

```yaml
known_groups:
  type: array
  description: "Cached classification decisions from prior /sweep-stores sessions."
  items:
    type: object
    required:
      - name
      - canonical_strategy
    properties:
      name:
        type: string
        minLength: 1
        description: "Unique within folder. Used to refuse collision on appends."
      canonical_strategy:
        type: string
        enum:
          - highest_version
          - explicit
          - not_a_group
      pattern:
        type: string
        description: "Glob; required when canonical_strategy=highest_version."
      members:
        type: array
        items:
          type: string
        description: "Filenames; required when canonical_strategy in (explicit, not_a_group)."
      canonical:
        type: string
        description: "Filename; required when canonical_strategy=explicit."
      decided_at:
        type: string
        description: "ISO8601 UTC timestamp written by hygiene-apply."
      decided_by:
        type: string
        description: "From $USER at write time."
      note:
        type: string
        description: "Free-form, hand-editable."
```

Adapt the indentation / wrapper to match the existing file's format.

- [ ] **Step 3: Commit**

```bash
git add shared-vault/skills/loop-hygiene/augur/data/lifecycle_schema.yaml
git commit -m "docs(loop-hygiene): document known_groups schema in lifecycle_schema.yaml"
```

---

## Task 9 — Create new fixtures

**Files:**
- Create: `shared-vault/skills/loop-hygiene/evals/fixtures/fixture_renamed_iteration/augur-intel-form-answers.md`
- Create: `shared-vault/skills/loop-hygiene/evals/fixtures/fixture_renamed_iteration/final-form-answers.md`
- Create: `shared-vault/skills/loop-hygiene/evals/fixtures/fixture_variant_suffix/linkedin-banner-personal.png`
- Create: `shared-vault/skills/loop-hygiene/evals/fixtures/fixture_variant_suffix/linkedin-banner-personal-augur.png`
- Create: `shared-vault/skills/loop-hygiene/evals/fixtures/fixture_mixed_version_scheme/guriqo-com-v33-1.zip`
- Create: `shared-vault/skills/loop-hygiene/evals/fixtures/fixture_mixed_version_scheme/guriqo-com-v45-1.zip`
- Create: `shared-vault/skills/loop-hygiene/evals/fixtures/fixture_mixed_version_scheme/guriqo-com-V10032.zip`
- Create: `shared-vault/skills/loop-hygiene/evals/fixtures/fixture_conceptual_supersession/pricing-draft.md`
- Create: `shared-vault/skills/loop-hygiene/evals/fixtures/fixture_conceptual_supersession/new-pricing-strategy.md`
- Create: `shared-vault/skills/loop-hygiene/evals/fixtures/fixture_cached_known_group/.augur-lifecycle.yaml`
- Create: `shared-vault/skills/loop-hygiene/evals/fixtures/fixture_cached_known_group/guriqo-com-V10001.zip`
- Create: `shared-vault/skills/loop-hygiene/evals/fixtures/fixture_cached_known_group/guriqo-com-V10032.zip`
- Create: `shared-vault/skills/loop-hygiene/evals/fixtures/fixture_lifecycle_malformed_groups/.augur-lifecycle.yaml`
- Create: `shared-vault/skills/loop-hygiene/evals/fixtures/fixture_lifecycle_malformed_groups/file.zip`

- [ ] **Step 1: Create renamed-iteration fixture**

```bash
mkdir -p ~/Projects/Augur/shared-vault/skills/loop-hygiene/evals/fixtures/fixture_renamed_iteration
```

File contents (use Write tool):

`augur-intel-form-answers.md`:
```markdown
---
status: draft
---
# Intel form answers

Initial Q&A drafted for Intel submission.
```

`final-form-answers.md`:
```markdown
---
status: final
replaces: augur-intel-form-answers.md
---
# Final form answers

Final version for Intel submission.
```

Set mtimes so `final-form-answers.md` is newer:
```bash
touch -t 202602200000 ~/Projects/Augur/shared-vault/skills/loop-hygiene/evals/fixtures/fixture_renamed_iteration/augur-intel-form-answers.md
touch -t 202603300000 ~/Projects/Augur/shared-vault/skills/loop-hygiene/evals/fixtures/fixture_renamed_iteration/final-form-answers.md
```

- [ ] **Step 2: Create variant-suffix fixture**

```bash
mkdir -p ~/Projects/Augur/shared-vault/skills/loop-hygiene/evals/fixtures/fixture_variant_suffix
```

Both files are 1-byte stubs (we only test name/mtime logic):

```bash
printf '\x89PNG' > ~/Projects/Augur/shared-vault/skills/loop-hygiene/evals/fixtures/fixture_variant_suffix/linkedin-banner-personal.png
printf '\x89PNG' > ~/Projects/Augur/shared-vault/skills/loop-hygiene/evals/fixtures/fixture_variant_suffix/linkedin-banner-personal-augur.png
```

- [ ] **Step 3: Create mixed-version-scheme fixture**

```bash
mkdir -p ~/Projects/Augur/shared-vault/skills/loop-hygiene/evals/fixtures/fixture_mixed_version_scheme
for f in guriqo-com-v33-1.zip guriqo-com-v45-1.zip guriqo-com-V10032.zip; do
  printf 'PK' > ~/Projects/Augur/shared-vault/skills/loop-hygiene/evals/fixtures/fixture_mixed_version_scheme/$f
done
touch -t 202603300000 ~/Projects/Augur/shared-vault/skills/loop-hygiene/evals/fixtures/fixture_mixed_version_scheme/guriqo-com-v33-1.zip
touch -t 202604090000 ~/Projects/Augur/shared-vault/skills/loop-hygiene/evals/fixtures/fixture_mixed_version_scheme/guriqo-com-v45-1.zip
touch -t 202604270000 ~/Projects/Augur/shared-vault/skills/loop-hygiene/evals/fixtures/fixture_mixed_version_scheme/guriqo-com-V10032.zip
```

- [ ] **Step 4: Create conceptual-supersession fixture**

```bash
mkdir -p ~/Projects/Augur/shared-vault/skills/loop-hygiene/evals/fixtures/fixture_conceptual_supersession
```

`pricing-draft.md`:
```markdown
---
status: deprecated
superseded_by: new-pricing-strategy.md
---
# Pricing draft (deprecated)

Earlier pricing model. See new-pricing-strategy.md for the live numbers.
```

`new-pricing-strategy.md`:
```markdown
---
status: live
replaces: pricing-draft.md
---
# New pricing strategy

Live numbers. Supersedes the earlier draft.
```

- [ ] **Step 5: Create cached-known-group fixture**

```bash
mkdir -p ~/Projects/Augur/shared-vault/skills/loop-hygiene/evals/fixtures/fixture_cached_known_group
```

`.augur-lifecycle.yaml`:
```yaml
enabled: true
known_groups:
  - name: guriqo-com-build
    canonical_strategy: highest_version
    pattern: 'guriqo-com-*.zip'
    decided_at: '2026-05-12T14:30:00Z'
    decided_by: gsannikov
    note: 'cached from prior sweep'
```

Two zip stubs:
```bash
printf 'PK' > ~/Projects/Augur/shared-vault/skills/loop-hygiene/evals/fixtures/fixture_cached_known_group/guriqo-com-V10001.zip
printf 'PK' > ~/Projects/Augur/shared-vault/skills/loop-hygiene/evals/fixtures/fixture_cached_known_group/guriqo-com-V10032.zip
```

- [ ] **Step 6: Create lifecycle-malformed-groups fixture**

```bash
mkdir -p ~/Projects/Augur/shared-vault/skills/loop-hygiene/evals/fixtures/fixture_lifecycle_malformed_groups
```

`.augur-lifecycle.yaml`:
```yaml
known_groups:
  - name: bad-entry
    canonical_strategy: bogus
```

`file.zip`:
```bash
printf 'PK' > ~/Projects/Augur/shared-vault/skills/loop-hygiene/evals/fixtures/fixture_lifecycle_malformed_groups/file.zip
```

- [ ] **Step 7: Update `evals/fixtures/README.md` with new fixture descriptions**

Append to `shared-vault/skills/loop-hygiene/evals/fixtures/README.md`:

```markdown
## Tier 2/3 fixtures

| Fixture | Triggers | Expected agent action |
|---|---|---|
| `fixture_renamed_iteration/` | Tier 2 (c) | Ask: "Same group, final-form-answers.md supersedes augur-intel-form-answers.md?" |
| `fixture_variant_suffix/` | Tier 2 (b) | Ask: "Same group: linkedin-banner-personal{,-augur}.png?" |
| `fixture_mixed_version_scheme/` | Tier 2 (a) | Ask: "Same group with mixed schemes (v33-1, v45-1, V10032)?" |
| `fixture_conceptual_supersession/` | Tier 3 (e) | Read content → hypothesis ("new-pricing-strategy.md replaces pricing-draft.md per frontmatter") → ask. |
| `fixture_cached_known_group/` | known-group match | NO question; archive V10001 per cached `highest_version` rule. |
| `fixture_lifecycle_malformed_groups/` | malformed cache | scan returns warning; agent treats folder as having no cache. |
```

- [ ] **Step 8: Commit**

```bash
git add shared-vault/skills/loop-hygiene/evals/fixtures/fixture_renamed_iteration \
        shared-vault/skills/loop-hygiene/evals/fixtures/fixture_variant_suffix \
        shared-vault/skills/loop-hygiene/evals/fixtures/fixture_mixed_version_scheme \
        shared-vault/skills/loop-hygiene/evals/fixtures/fixture_conceptual_supersession \
        shared-vault/skills/loop-hygiene/evals/fixtures/fixture_cached_known_group \
        shared-vault/skills/loop-hygiene/evals/fixtures/fixture_lifecycle_malformed_groups \
        shared-vault/skills/loop-hygiene/evals/fixtures/README.md
git commit -m "test(loop-hygiene): fixtures for Tier 2/3 cases + cached known_groups"
```

---

## Task 10 — E2E test: cached-group round-trip

**Files:**
- Modify: `shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_e2e.py`

- [ ] **Step 1: Read the existing E2E test to understand the pattern**

Run: `cat ~/Projects/Augur/shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_e2e.py`

The existing test uses monkeypatch + a temp `docs_root` mirror of `fixture_websites_versioned`. Follow that pattern.

- [ ] **Step 2: Write the cached-group test**

Append to `test_hygiene_e2e.py`:

```python
def test_e2e_cached_known_groups_skip_question_path(tmp_path, monkeypatch):
    """Sweep #1 creates a known_group entry; sweep #2 should apply the same
    moves without re-asking."""
    docs_root = tmp_path / "docs"
    folder = docs_root / "ws"
    folder.mkdir(parents=True)

    # Sweep #1: no cache, four versioned files
    for v in ("V10001", "V10002", "V10003", "V10032"):
        (folder / f"build-{v}.zip").write_bytes(b"x")

    monkeypatch.setattr(scan_mod, "get_documents_dir", lambda: docs_root)
    monkeypatch.setattr(apply_mod, "get_documents_dir", lambda: docs_root)

    # Simulate the agent's first-sweep flow: scan, build moves, ALSO emit a
    # lifecycle_updates entry to cache the decision.
    scan1 = scan_mod.hygiene_scan(str(folder))
    assert scan1["lifecycle_config"] is None  # no cache yet

    moves = [{"from": f"ws/build-{v}.zip", "reason": "test", "artifact_group": "build"}
             for v in ("V10001", "V10002", "V10003")]
    lifecycle_updates = [{
        "folder": "ws",
        "known_group": {
            "name": "build",
            "canonical_strategy": "highest_version",
            "pattern": "build-*.zip",
            "decided_at": "2026-05-12T14:30:00Z",
            "decided_by": "test",
        },
    }]
    apply1 = apply_mod.hygiene_apply(
        root="docs",
        moves=moves,
        dry_run=False,
        lifecycle_updates=lifecycle_updates,
    )
    assert all(m["status"] == "succeeded" for m in apply1["moves"])
    assert apply1["lifecycle_updates"][0]["status"] == "written"

    # Sweep #2: scan should now return the cached known_group
    scan2 = scan_mod.hygiene_scan(str(folder))
    groups = scan2["lifecycle_config"]["known_groups"]
    assert len(groups) == 1
    assert groups[0]["name"] == "build"
    assert groups[0]["canonical_strategy"] == "highest_version"

    # The agent would now run the matcher and skip the Tier 2/3 question path.
    # We don't simulate the agent here, but we verify the cache is loadable
    # and consistent (the matcher itself is tested in test_known_groups.py).
```

You may need to add a sibling loader for `scan_mod` and `apply_mod` at the top of `test_hygiene_e2e.py` if not already present — follow the pattern from `test_hygiene_scan.py`.

- [ ] **Step 3: Run the E2E test**

Run: `cd ~/Projects/Augur && uv run pytest shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_e2e.py::test_e2e_cached_known_groups_skip_question_path -v`

Expected: PASS.

- [ ] **Step 4: Run the full loop-hygiene test suite**

Run: `cd ~/Projects/Augur && uv run pytest shared-vault/skills/loop-hygiene/augur/tests/ -v`

Expected: all PASS. Confirm no regressions in the existing tests.

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_e2e.py
git commit -m "test(loop-hygiene): e2e round-trip — sweep #1 caches, sweep #2 reads

Verifies that hygiene_apply's lifecycle_updates write is visible to the
next hygiene_scan call, so subsequent sweeps can short-circuit the Q&A path."
```

---

## Task 11 — Run the lint/test gate and bump SKILL.md

**Files:**
- Modify: `shared-vault/skills/loop-hygiene/SKILL.md` (version bump in frontmatter)

- [ ] **Step 1: Run the loop-hygiene test suite one more time**

Run: `cd ~/Projects/Augur && uv run pytest shared-vault/skills/loop-hygiene/augur/tests/ -v`

Expected: all green.

- [ ] **Step 2: Run lint on the touched files**

Per CLAUDE.md rule 29: use `/auto-lint` (slash command) not raw lint commands. From the user's session:

Tell the user: "Run `/auto-lint` to verify lint passes on the touched Python files." (The agent cannot invoke slash commands; the user runs this.)

If lint fails, fix issues inline and re-run.

- [ ] **Step 3: Bump the SKILL.md version**

Read the current SKILL.md frontmatter:

Run: `head -20 ~/Projects/Augur/shared-vault/skills/loop-hygiene/SKILL.md`

Bump the version field (e.g., `0.1.0` → `0.2.0`) and add a changelog line if the file has one:

```yaml
# in SKILL.md frontmatter
version: 0.2.0
```

Add a changelog note (if the SKILL.md format supports it; otherwise reference the spec):

```markdown
## Changelog

- 0.2.0 (2026-05-12): tiered classification, interactive Q&A, cached known_groups. Spec: `docs/superpowers/specs/2026-05-12-sweep-interactive-llm-design.md`.
```

- [ ] **Step 4: Commit**

```bash
git add shared-vault/skills/loop-hygiene/SKILL.md
git commit -m "chore(loop-hygiene): bump to 0.2.0 for tiered Q&A enhancement"
```

---

## Task 12 — Manual end-to-end verification

**Files:** none (manual sweep against real data)

- [ ] **Step 1: Tell the user to run a dry-run against a known case**

Pick a real folder under `Au-docs/venture-augur/` that has Tier 2 ambiguities we flagged on 2026-05-12 — e.g., `IntelSubmit/` (for `final-form-answers.md` vs `augur-intel-form-answers.md`) or `images/` (for `linkedin-banner-personal*` variants).

Tell the user:
```
Run /sweep-stores ~/Projects/Au-docs/venture-augur/IntelSubmit
```

Expected: agent surfaces 1–2 questions via `AskUserQuestion`. Dry-run completes; no files moved.

- [ ] **Step 2: User answers the question, then re-runs with `--apply`**

User runs:
```
/sweep-stores ~/Projects/Au-docs/venture-augur/IntelSubmit --apply
```

Expected:
- Moves succeed.
- `.augur-lifecycle.yaml` in that folder gains a `known_groups[]` entry.
- Result includes the `lifecycle_updates[].status == "written"` confirmation.

- [ ] **Step 3: User runs the sweep a third time to confirm cache short-circuit**

User runs:
```
/sweep-stores ~/Projects/Au-docs/venture-augur/IntelSubmit
```

Expected: no `AskUserQuestion` prompt. Proposal section "From cached known_groups" shows the group was applied without re-asking. If there's nothing left to move (already swept), proposal shows "0 moves."

- [ ] **Step 4: Verify the rule 1 / rule 28 sanity**

Per CLAUDE.md rule 28: this enhancement does not touch dashboard UI, so no client-side browser verification is required. Confirm explicitly in the manual report.

- [ ] **Step 5: Final commit (only if SKILL.md or anything else was edited inline during manual verification)**

```bash
git add -A
git status
# only commit if files are staged
```

---

## Self-Review

Walking back through the spec to check coverage:

**Spec §3 (decision summary):**
- Rubric replacement → Task 6 ✓
- Persistence schema → Task 1, 3, 8 ✓
- Workflow flow → Task 7 ✓
- `hygiene-scan` schema extension → Task 4 ✓
- `hygiene-apply` `lifecycle_updates` → Task 5 ✓

**Spec §4 (tier rubric):**
- Tier 1 high-confidence → Task 6 rubric ✓
- Tier 2 medium with 3 signals → Task 6 rubric ✓
- Tier 3 low with 2 signals + content inspection budget → Task 6 rubric ✓
- Always-skip cases → Task 6 rubric ✓
- 4-question batch cap → Task 6 rubric + Task 7 workflow ✓
- 10-file inspection cap → Task 6 rubric ✓

**Spec §5 (persistence schema):**
- 3 canonical_strategy values → Task 1 parser ✓
- Required-field validation per strategy → Task 1 (parser raises) ✓
- Name-collision refusal → Task 3 writer ✓
- Atomicity (temp-rename) → Task 3 writer ✓
- decided_at / decided_by fields → Task 1 + Task 8 schema ✓

**Spec §6 (workflow flow):**
- 9-step flow including known-group matching, Q&A, YAML-before-moves → Task 7 + Task 2 (matcher) + Task 5 (apply) ✓

**Spec §7 (MCP tool contracts):**
- `hygiene-scan` additive output → Task 4 ✓
- `hygiene-apply` additive input + per-update results → Task 5 ✓
- Write-before-moves ordering → Task 5 ✓
- YAML-not-rolled-back-on-move-failure → Task 5 (already documented in helper) ✓

**Spec §8 (testing):**
- All test categories covered → Tasks 1, 2, 3, 4, 5, 10 ✓
- 6 fixtures created → Task 9 ✓
- Manual verification → Task 12 ✓
- No LLM-quality eval (intentional) → not in plan, matches spec ✓

**Spec §9 (out of scope):**
- No image hashing, no PDF/docx parsing, no auto-loop, no Au-vault — none of these appear in tasks ✓

**Placeholder scan:**
- All code blocks contain real code, no TBD/TODO.
- Every test has a concrete assertion.
- Every step has a real command.

**Type consistency:**
- `KnownGroup` field names (`name`, `canonical_strategy`, `pattern`, `members`, `canonical`, `decided_at`, `decided_by`, `note`) appear identically across Task 1 (dataclass), Task 2 (matcher inputs), Task 3 (writer), Task 4 (scan output), Task 5 (apply input), Task 6 (rubric), Task 7 (command), Task 8 (schema). ✓
- Refusal categories (`lifecycle_collision`, `lifecycle_malformed`, `outside_store`, `folder_missing`, `malformed_update`) consistent between Task 5 implementation and Task 7 command documentation. ✓

**Scope check:** the plan touches one skill (`loop-hygiene`), 12 tasks, in a single direction (richer rubric + cache layer). No subsystem decomposition needed.

---

## Execution Handoff

After implementing, the work should ship as a single PR titled "feat(loop-hygiene): tiered classification + interactive Q&A + cached known_groups" referencing the spec.
