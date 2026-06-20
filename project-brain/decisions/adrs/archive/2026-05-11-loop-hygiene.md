# loop-hygiene Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the MVP-v2 of `loop-hygiene` per `docs/superpowers/specs/2026-05-11-loop-hygiene-design.md`: a new skill at `shared-vault/skills/loop-hygiene/` providing the `/sweep-stores` slash command and two MCP tools (`hygiene-scan` read-only, `hygiene-apply` destructive+atomic) so an agent in any client session can sweep stale-version artifacts out of `Au-docs/` into per-folder `.archive/` directories that are invisible to AI scanners via `.augur-ignore` + `.gitignore`. No `llm.yaml` routing, no auto-loops, no dashboard, no Au-vault scope — those are Phases 2-6, deferred.

**Architecture:** Six checkpoints, 27 tasks. C1 scaffolds the skill and the shared never-touch module. C2 implements `hygiene_scan` (pure read). C3 implements `hygiene_apply` (atomic destructive with rollback). C4 builds golden fixtures and the e2e test. C5 wires the MCP surface and slash command. C6 runs quality gates and the manual verification ritual. Skill logic lives in `shared-vault/skills/loop-hygiene/scripts/`; MCP tool surface lives in `src/mcp/augur_core/tools/core/hygiene.py` (thin wrappers importing skill logic); slash command lives in `shared-vault/skills/loop-hygiene/commands/sweep-stores.md`.

**Tech Stack:** Python 3.11+ (stdlib `os`, `pathlib`, `hashlib`, `json`, `fnmatch`; PyYAML for lifecycle config; pytest + tmp_path for tests). No new runtime deps. No LLM SDK imports anywhere in the skill (the agent in the session IS the classifier). Existing FastMCP integration for tool registration.

**Spec:** `docs/superpowers/specs/2026-05-11-loop-hygiene-design.md`

**Naming distinction (read before starting):** `loop-repo`'s existing `vault-hygiene` artifact concerns **vault structural integrity** (broken refs, malformed frontmatter, vault-health-repairs). This skill `loop-hygiene` concerns **stale-version artifact retention** (move old versions to .archive/). The two are orthogonal and coexist; do not merge them.

---

## Boundary rules (apply to every task)

- **Auto-loops only.** Tests run via `/auto-test-pytest`; lint via `/auto-lint`; never raw `pytest` per CLAUDE.md rule 29.
- **Path helpers.** Resolve `Au-docs` via `src.config.paths.get_documents_dir()`. Never hardcode `/Users/.../Au-docs`. Per CLAUDE.md rule 3.
- **Plugin decentralization.** Skill logic lives under `shared-vault/skills/loop-hygiene/`. MCP surface adds files under `src/mcp/augur_core/tools/core/`. Per CLAUDE.md rule 2.
- **Frontmatter on user-facing files.** `commands/sweep-stores.md` and `SKILL.md` start with YAML frontmatter. Per CLAUDE.md rule 16.
- **Never silently bypass refusals.** Every refusal returns `{ "refusal_category": "...", "reason": "..." }` in the structured response. Per CLAUDE.md rule 5.
- **Commit after every passing task.** Small focused commits per CLAUDE.md rule 10. Commit messages use the pattern `feat(loop-hygiene): <subject>`, `test(loop-hygiene): <subject>`, or `chore(loop-hygiene): <subject>`.
- **Bootstrap module pattern.** Skill scripts use the `_augur_bootstrap_*` block at the top to import from `src.config.paths` etc. — same pattern as `loop-memory/scripts/context_audit.py`. Copy verbatim from there in Task 4.
- **No LLM SDK imports.** Tasks 4-14 may not import `anthropic`, `openai`, `google.generativeai`, or any LLM client. The classifier is the agent in the session, not a scripted call.

---

## C1 — Skill scaffold + never-touch foundations

### Task 1: Create skill directory and SKILL.md

**Files:**
- Create: `shared-vault/skills/loop-hygiene/SKILL.md`
- Create: `shared-vault/skills/loop-hygiene/commands/` (empty dir for now; .gitkeep)
- Create: `shared-vault/skills/loop-hygiene/scripts/__init__.py` (empty)
- Create: `shared-vault/skills/loop-hygiene/scripts/.gitkeep`
- Create: `shared-vault/skills/loop-hygiene/augur/data/` (empty dir; .gitkeep)
- Create: `shared-vault/skills/loop-hygiene/references/` (empty dir; .gitkeep)
- Create: `shared-vault/skills/loop-hygiene/evals/fixtures/` (empty dir; .gitkeep)
- Create: `shared-vault/skills/loop-hygiene/augur/tests/__init__.py` (empty)

- [ ] **Step 1: Create the directory tree and SKILL.md**

Write `shared-vault/skills/loop-hygiene/SKILL.md`:

```yaml
---
name: loop-hygiene
x-augur-type: domain
x-augur-group: augur_autoloops
x-augur-release: mvp
description: 'Store-wide artifact retention. Moves stale-version files (e.g., guriqo-com-V10031.zip when V10032 exists) out of the live tree into per-folder .archive/ directories that AI scanners ignore. Two MCP tools (hygiene-scan, hygiene-apply) plus one slash command (/sweep-stores). Agent in session is the classifier; no llm.yaml routing. MVP scope: Au-docs only.'
x-augur-hub: adaptive
x-augur-tab: hygiene
x-augur-tags:
- hygiene
- retention
- artifacts
- archive
- au-docs
x-augur-data-deps: []
x-augur-dashboard-pages: []
x-augur-data-dir: loop-hygiene
x-augur-commands:
- id: sweep-stores
  type: slash
  visibility: core
  description: Sweep stale-version artifacts in a folder under Au-docs into per-folder .archive/ via the agent-in-session as classifier.
  callable: commands/sweep-stores.md
x-augur-config:
  contributions:
    pages: []
    commands:
    - id: sweep-stores
      type: slash
      visibility: core
      description: Sweep stale-version artifacts in a folder under Au-docs into per-folder .archive/ via the agent-in-session as classifier.
      callable: commands/sweep-stores.md
---

# loop-hygiene

Store-wide artifact retention for Au-docs. Moves stale-version files into per-folder `.archive/` directories that AI scanners ignore.

## Commands

- [commands/sweep-stores.md](commands/sweep-stores.md)

## Scope (MVP)

- `Au-docs/` only. Au-vault is out of scope until Phase 3.
- The slash command `/sweep-stores <path>` is dry-run by default; `--apply` is required for destructive action.
- Agent in the current session classifies; no separate LLM call, no llm.yaml routing.
- Two MCP tools (`hygiene-scan`, `hygiene-apply`) provide the atomic primitives.

## Distinction from loop-repo's vault-hygiene

`loop-repo`'s `vault-hygiene` repairs vault structural integrity (broken refs, malformed frontmatter). This skill (`loop-hygiene`) retires stale-version artifacts. They are orthogonal.

## Spec and ADR

- Spec: [docs/superpowers/specs/2026-05-11-loop-hygiene-design.md](../../../docs/superpowers/specs/2026-05-11-loop-hygiene-design.md)
- ADR: ADR-732 (assigned at `/adr` finalization in Task 27)
```

- [ ] **Step 2: Create empty placeholder files for empty directories**

```bash
mkdir -p shared-vault/skills/loop-hygiene/{commands,scripts,augur/data,references,evals/fixtures,tests}
touch shared-vault/skills/loop-hygiene/commands/.gitkeep
touch shared-vault/skills/loop-hygiene/augur/data/.gitkeep
touch shared-vault/skills/loop-hygiene/references/.gitkeep
touch shared-vault/skills/loop-hygiene/evals/fixtures/.gitkeep
```

Write `shared-vault/skills/loop-hygiene/scripts/__init__.py` and `shared-vault/skills/loop-hygiene/augur/tests/__init__.py` as empty files.

- [ ] **Step 3: Verify the skill is discovered by the skill manifest**

Run: `python -c "from pathlib import Path; assert Path('shared-vault/skills/loop-hygiene/SKILL.md').exists(); print('OK')"`
Expected: `OK`

Run: `python -c "from src.lib.frontmatter_utils import parse_frontmatter; p = open('shared-vault/skills/loop-hygiene/SKILL.md').read(); fm, _ = parse_frontmatter(p); assert fm['name'] == 'loop-hygiene'; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add shared-vault/skills/loop-hygiene/
git commit -m "feat(loop-hygiene): scaffold skill directory and SKILL.md

Empty skill structure following loop-memory pattern. SKILL.md declares
one slash command contribution (sweep-stores), x-augur-hub=adaptive,
group=augur_autoloops, release=mvp. No scripts or commands yet.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Shared never-touch module + tests

**Files:**
- Create: `shared-vault/skills/loop-hygiene/scripts/never_touch.py`
- Create: `shared-vault/skills/loop-hygiene/augur/tests/test_never_touch.py`

The never-touch list is imported by both `hygiene_scan` and `hygiene_apply`. Centralize in one module.

- [ ] **Step 1: Write the failing test**

Write `shared-vault/skills/loop-hygiene/augur/tests/test_never_touch.py`:

```python
"""Tests for the shared never-touch path classifier."""
from pathlib import Path

import pytest

from shared_vault.skills.loop_hygiene.scripts.never_touch import (
    is_never_touch,
    NEVER_TOUCH_DIR_NAMES,
    NEVER_TOUCH_FILE_GLOBS,
    NEVER_TOUCH_PREFIXES,
)


def test_git_dir_is_never_touch():
    assert is_never_touch(Path("venture-augur/.git/config"))


def test_obsidian_dir_is_never_touch():
    assert is_never_touch(Path(".obsidian/app.json"))


def test_pytest_cache_is_never_touch():
    assert is_never_touch(Path("foo/.pytest_cache/v/cache.bin"))


def test_tmp_driveupload_is_never_touch():
    assert is_never_touch(Path(".tmp.driveupload/x"))


def test_node_modules_is_never_touch():
    assert is_never_touch(Path("foo/node_modules/x/index.js"))


def test_venv_is_never_touch():
    assert is_never_touch(Path(".venv/bin/python"))


def test_pycache_is_never_touch():
    assert is_never_touch(Path("foo/__pycache__/x.pyc"))


def test_archive_dir_is_never_touch():
    assert is_never_touch(Path("foo/.archive/bar.zip"))


def test_archive_dir_nested_is_never_touch():
    assert is_never_touch(Path("foo/.archive/2026-05/bar.zip"))


def test_package_lock_is_never_touch():
    assert is_never_touch(Path("foo/package-lock.json"))


def test_pnpm_lock_is_never_touch():
    assert is_never_touch(Path("foo/pnpm-lock.yaml"))


def test_uv_lock_is_never_touch():
    assert is_never_touch(Path("uv.lock"))


def test_augur_docs_marker_is_never_touch():
    assert is_never_touch(Path(".augur-docs"))


def test_augur_vault_marker_is_never_touch():
    assert is_never_touch(Path(".augur-vault"))


def test_augur_ignore_marker_is_never_touch():
    assert is_never_touch(Path("foo/.augur-ignore"))


def test_augur_reserved_marker_is_never_touch():
    assert is_never_touch(Path(".augur-reserved"))


def test_normal_file_is_not_never_touch():
    assert not is_never_touch(Path("venture-augur/websites/guriqo-com-V10032.zip"))


def test_ds_store_is_not_never_touch():
    # DS_Store is a separate concern (cosmetic clutter); never-touch only
    # protects working-state files. Caller may add own ignore handling.
    assert not is_never_touch(Path("foo/.DS_Store"))


def test_constants_are_frozensets():
    assert isinstance(NEVER_TOUCH_DIR_NAMES, frozenset)
    assert isinstance(NEVER_TOUCH_FILE_GLOBS, frozenset)
    assert isinstance(NEVER_TOUCH_PREFIXES, frozenset)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/auto-test-pytest shared-vault/skills/loop-hygiene/augur/tests/test_never_touch.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'shared_vault.skills.loop_hygiene.scripts.never_touch'`

- [ ] **Step 3: Write the minimal implementation**

Write `shared-vault/skills/loop-hygiene/scripts/never_touch.py`:

```python
"""Shared never-touch path classifier used by hygiene_scan and hygiene_apply.

The never-touch list is a hard refusal layer: any path matching is
silently skipped at scan time and refused at apply time with category
`never_touch`. The list is intentionally NOT user-configurable in MVP —
these are paths whose movement would break tooling, git, Python, Node,
or Augur itself.
"""
from __future__ import annotations

import fnmatch
from pathlib import Path


# Directory names. Match if any path component (including final basename) is in this set.
NEVER_TOUCH_DIR_NAMES: frozenset[str] = frozenset({
    ".git",
    ".obsidian",
    ".pytest_cache",
    ".tmp.driveupload",
    "node_modules",
    ".venv",
    "__pycache__",
    ".archive",
})

# File-basename globs. Match if the path's final component matches any of these.
NEVER_TOUCH_FILE_GLOBS: frozenset[str] = frozenset({
    "package-lock.json",
    "pnpm-lock.yaml",
    "uv.lock",
    "yarn.lock",
    "*.lock",
})

# Basename prefixes. Match if the path's final component starts with any of these
# AND the component starts with a dot (to avoid colliding with user filenames).
NEVER_TOUCH_PREFIXES: frozenset[str] = frozenset({
    ".augur-",
})


def is_never_touch(path: Path) -> bool:
    """Return True if `path` matches any never-touch rule.

    `path` may be absolute or relative; only the basename and path
    components are inspected.
    """
    parts = path.parts
    # Directory-name match anywhere in the path
    for part in parts:
        if part in NEVER_TOUCH_DIR_NAMES:
            return True
    # Basename glob match
    basename = path.name
    for glob in NEVER_TOUCH_FILE_GLOBS:
        if fnmatch.fnmatch(basename, glob):
            return True
    # Dot-prefixed marker match
    for prefix in NEVER_TOUCH_PREFIXES:
        if basename.startswith(prefix):
            return True
    return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/auto-test-pytest shared-vault/skills/loop-hygiene/augur/tests/test_never_touch.py`
Expected: PASS — 18 passed

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/loop-hygiene/scripts/never_touch.py shared-vault/skills/loop-hygiene/augur/tests/test_never_touch.py
git commit -m "feat(loop-hygiene): shared never-touch path classifier with tests

Centralizes the never-touch list (.git/, .obsidian/, .pytest_cache/,
.tmp.driveupload/, node_modules/, .venv/, __pycache__/, .archive/,
.augur-* markers, *.lock files) so both hygiene_scan and hygiene_apply
import from one source. 18 unit tests cover every category.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Lifecycle config + milestone JSON readers + tests

**Files:**
- Create: `shared-vault/skills/loop-hygiene/augur/data/lifecycle_schema.yaml`
- Create: `shared-vault/skills/loop-hygiene/scripts/lifecycle_config.py`
- Create: `shared-vault/skills/loop-hygiene/augur/tests/test_lifecycle_config.py`

`hygiene_scan` reads two optional sidecar files from the folder being scanned: `.augur-lifecycle.yaml` (hints to the agent) and `.milestones.json` (paths pinned against archival). Centralize parsing in one module.

- [ ] **Step 1: Write the lifecycle schema documentation**

Write `shared-vault/skills/loop-hygiene/augur/data/lifecycle_schema.yaml`:

```yaml
# .augur-lifecycle.yaml — per-folder hygiene policy hints.
# Place this file at the root of any folder under Au-docs that wants
# to opt in or customize the /sweep-stores behavior.
#
# All fields optional. Absence of this file is not a refusal — the
# folder remains scannable; /sweep-stores just won't have hints.

# enabled (bool, default true): when false, /sweep-stores refuses
# this folder entirely. Use for folders you want to permanently
# carve out from hygiene.
enabled: true

# pattern_hints (list[str], optional): glob patterns the agent reads
# as classification hints (e.g., "guriqo-com-V*.zip"). The agent is
# free to ignore these or to recognize patterns not listed.
pattern_hints:
  - "guriqo-com-V*.zip"
  - "augur-run-V*.zip"

# keep_latest (int, optional): hint to the agent about how many
# versions of each artifact group to keep. Default behavior absent
# this field: keep_latest=1.
keep_latest: 1

# deploy_root (bool, default false): when true, /sweep-stores reports
# the folder's content but never proposes archives — the agent must
# instruct the user to act via filesystem. hygiene-apply refuses any
# move whose source is in a deploy_root folder, as a safety net.
deploy_root: false

# notes (str, optional): free text the agent reads for context.
notes: "Free text the agent can read for context."
```

- [ ] **Step 2: Write the failing test**

Write `shared-vault/skills/loop-hygiene/augur/tests/test_lifecycle_config.py`:

```python
"""Tests for .augur-lifecycle.yaml and .milestones.json readers."""
import json
from pathlib import Path

import pytest

from shared_vault.skills.loop_hygiene.scripts.lifecycle_config import (
    LifecycleConfig,
    MilestonePin,
    read_lifecycle_config,
    read_milestones,
    LifecycleConfigError,
)


def test_read_lifecycle_config_absent_returns_none(tmp_path):
    assert read_lifecycle_config(tmp_path) is None


def test_read_lifecycle_config_minimal(tmp_path):
    (tmp_path / ".augur-lifecycle.yaml").write_text("enabled: true\n")
    cfg = read_lifecycle_config(tmp_path)
    assert cfg is not None
    assert cfg.enabled is True
    assert cfg.pattern_hints == []
    assert cfg.keep_latest is None
    assert cfg.deploy_root is False
    assert cfg.notes is None


def test_read_lifecycle_config_full(tmp_path):
    (tmp_path / ".augur-lifecycle.yaml").write_text(
        "enabled: true\n"
        "pattern_hints:\n  - 'guriqo-com-V*.zip'\n  - 'augur-run-V*.zip'\n"
        "keep_latest: 1\n"
        "deploy_root: true\n"
        "notes: 'prod website builds'\n"
    )
    cfg = read_lifecycle_config(tmp_path)
    assert cfg.enabled is True
    assert cfg.pattern_hints == ["guriqo-com-V*.zip", "augur-run-V*.zip"]
    assert cfg.keep_latest == 1
    assert cfg.deploy_root is True
    assert cfg.notes == "prod website builds"


def test_read_lifecycle_config_malformed_yaml_raises(tmp_path):
    (tmp_path / ".augur-lifecycle.yaml").write_text("enabled: : invalid\n")
    with pytest.raises(LifecycleConfigError, match="parse"):
        read_lifecycle_config(tmp_path)


def test_read_lifecycle_config_wrong_type_raises(tmp_path):
    (tmp_path / ".augur-lifecycle.yaml").write_text("enabled: 'not-a-bool'\n")
    with pytest.raises(LifecycleConfigError, match="enabled"):
        read_lifecycle_config(tmp_path)


def test_read_milestones_absent_returns_empty(tmp_path):
    assert read_milestones(tmp_path) == []


def test_read_milestones_valid(tmp_path):
    payload = {
        "websites/guriqo-com-V10025.zip": {
            "tag": "intel-submission",
            "tagged_at": "2026-04-25T10:00:00Z",
            "note": "sent to Intel",
        }
    }
    (tmp_path / ".milestones.json").write_text(json.dumps(payload))
    pins = read_milestones(tmp_path)
    assert len(pins) == 1
    assert pins[0].relative_path == "websites/guriqo-com-V10025.zip"
    assert pins[0].tag == "intel-submission"
    assert pins[0].tagged_at == "2026-04-25T10:00:00Z"
    assert pins[0].note == "sent to Intel"


def test_read_milestones_malformed_json_raises(tmp_path):
    (tmp_path / ".milestones.json").write_text("{not-json")
    with pytest.raises(LifecycleConfigError, match="parse"):
        read_milestones(tmp_path)


def test_read_milestones_missing_tag_raises(tmp_path):
    payload = {"websites/x.zip": {"tagged_at": "2026-04-25T10:00:00Z"}}
    (tmp_path / ".milestones.json").write_text(json.dumps(payload))
    with pytest.raises(LifecycleConfigError, match="tag"):
        read_milestones(tmp_path)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `/auto-test-pytest shared-vault/skills/loop-hygiene/augur/tests/test_lifecycle_config.py`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Write the minimal implementation**

Write `shared-vault/skills/loop-hygiene/scripts/lifecycle_config.py`:

```python
"""Readers for .augur-lifecycle.yaml and .milestones.json sidecar files."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml


class LifecycleConfigError(ValueError):
    """Raised on malformed lifecycle config or milestones file."""


@dataclass(frozen=True)
class LifecycleConfig:
    enabled: bool = True
    pattern_hints: list[str] = field(default_factory=list)
    keep_latest: int | None = None
    deploy_root: bool = False
    notes: str | None = None


@dataclass(frozen=True)
class MilestonePin:
    relative_path: str
    tag: str
    tagged_at: str | None
    note: str | None


def read_lifecycle_config(folder: Path) -> LifecycleConfig | None:
    """Read .augur-lifecycle.yaml from `folder`, return None if absent."""
    path = folder / ".augur-lifecycle.yaml"
    if not path.is_file():
        return None
    try:
        raw = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as exc:
        raise LifecycleConfigError(f"failed to parse {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise LifecycleConfigError(f"{path}: top-level must be a mapping")

    enabled = raw.get("enabled", True)
    if not isinstance(enabled, bool):
        raise LifecycleConfigError(f"{path}: 'enabled' must be a bool")

    pattern_hints = raw.get("pattern_hints", [])
    if not isinstance(pattern_hints, list) or not all(isinstance(s, str) for s in pattern_hints):
        raise LifecycleConfigError(f"{path}: 'pattern_hints' must be a list of strings")

    keep_latest = raw.get("keep_latest")
    if keep_latest is not None and not isinstance(keep_latest, int):
        raise LifecycleConfigError(f"{path}: 'keep_latest' must be an int")

    deploy_root = raw.get("deploy_root", False)
    if not isinstance(deploy_root, bool):
        raise LifecycleConfigError(f"{path}: 'deploy_root' must be a bool")

    notes = raw.get("notes")
    if notes is not None and not isinstance(notes, str):
        raise LifecycleConfigError(f"{path}: 'notes' must be a string")

    return LifecycleConfig(
        enabled=enabled,
        pattern_hints=list(pattern_hints),
        keep_latest=keep_latest,
        deploy_root=deploy_root,
        notes=notes,
    )


def read_milestones(folder: Path) -> list[MilestonePin]:
    """Read .milestones.json from `folder`, return [] if absent."""
    path = folder / ".milestones.json"
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise LifecycleConfigError(f"failed to parse {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise LifecycleConfigError(f"{path}: top-level must be an object")

    pins: list[MilestonePin] = []
    for rel_path, entry in raw.items():
        if not isinstance(entry, dict):
            raise LifecycleConfigError(f"{path}: entry for {rel_path!r} must be an object")
        tag = entry.get("tag")
        if not isinstance(tag, str) or not tag:
            raise LifecycleConfigError(f"{path}: entry for {rel_path!r} must have a non-empty 'tag'")
        tagged_at = entry.get("tagged_at")
        if tagged_at is not None and not isinstance(tagged_at, str):
            raise LifecycleConfigError(f"{path}: entry for {rel_path!r}: 'tagged_at' must be a string")
        note = entry.get("note")
        if note is not None and not isinstance(note, str):
            raise LifecycleConfigError(f"{path}: entry for {rel_path!r}: 'note' must be a string")
        pins.append(MilestonePin(relative_path=rel_path, tag=tag, tagged_at=tagged_at, note=note))
    return pins
```

- [ ] **Step 5: Run test to verify it passes**

Run: `/auto-test-pytest shared-vault/skills/loop-hygiene/augur/tests/test_lifecycle_config.py`
Expected: PASS — 9 passed

- [ ] **Step 6: Commit**

```bash
git add shared-vault/skills/loop-hygiene/scripts/lifecycle_config.py shared-vault/skills/loop-hygiene/augur/tests/test_lifecycle_config.py shared-vault/skills/loop-hygiene/augur/data/lifecycle_schema.yaml
git commit -m "feat(loop-hygiene): lifecycle config + milestone readers with tests

Reads .augur-lifecycle.yaml (enabled, pattern_hints, keep_latest,
deploy_root, notes) and .milestones.json (path->{tag,tagged_at,note}).
Both files are optional. Malformed YAML/JSON raises LifecycleConfigError
with a path-qualified message. Schema documented in
augur/data/lifecycle_schema.yaml.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## C2 — `hygiene_scan` implementation

### Task 4: Skeleton with bootstrap pattern + Au-docs root resolution + Au-vault refusal

**Files:**
- Create: `shared-vault/skills/loop-hygiene/scripts/hygiene_scan.py`
- Create: `shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_scan.py`

- [ ] **Step 1: Write the failing test**

Write `shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_scan.py`:

```python
"""Tests for hygiene_scan — the read-only scanner."""
from pathlib import Path

import pytest

from shared_vault.skills.loop_hygiene.scripts.hygiene_scan import (
    hygiene_scan,
    HygieneScanError,
)


def test_refuses_path_outside_au_docs(tmp_path, monkeypatch):
    # Configure get_documents_dir to return tmp_path/au-docs
    docs = tmp_path / "au-docs"
    docs.mkdir()
    monkeypatch.setattr(
        "shared_vault.skills.loop_hygiene.scripts.hygiene_scan.get_documents_dir",
        lambda: docs,
    )
    # Au-vault path is outside Au-docs
    vault = tmp_path / "au-vault"
    vault.mkdir()
    (vault / "notes").mkdir()

    with pytest.raises(HygieneScanError, match="outside Au-docs"):
        hygiene_scan(str(vault / "notes"))


def test_refuses_nonexistent_path(tmp_path, monkeypatch):
    docs = tmp_path / "au-docs"
    docs.mkdir()
    monkeypatch.setattr(
        "shared_vault.skills.loop_hygiene.scripts.hygiene_scan.get_documents_dir",
        lambda: docs,
    )
    with pytest.raises(HygieneScanError, match="does not exist"):
        hygiene_scan(str(docs / "missing"))


def test_refuses_path_pointing_to_file_not_dir(tmp_path, monkeypatch):
    docs = tmp_path / "au-docs"
    docs.mkdir()
    monkeypatch.setattr(
        "shared_vault.skills.loop_hygiene.scripts.hygiene_scan.get_documents_dir",
        lambda: docs,
    )
    (docs / "x.zip").write_bytes(b"x")
    with pytest.raises(HygieneScanError, match="not a directory"):
        hygiene_scan(str(docs / "x.zip"))


def test_scan_empty_dir(tmp_path, monkeypatch):
    docs = tmp_path / "au-docs"
    docs.mkdir()
    monkeypatch.setattr(
        "shared_vault.skills.loop_hygiene.scripts.hygiene_scan.get_documents_dir",
        lambda: docs,
    )
    (docs / "empty").mkdir()
    result = hygiene_scan(str(docs / "empty"))
    assert result["root"] == str(docs)
    assert result["scanned_path"] == "empty"
    assert result["files"] == []
    assert result["lifecycle_config"] is None
    assert result["milestone_pins"] == []
    assert result["never_touch_skipped"] == []
    assert result["warnings"] == []


def test_accepts_relative_path_under_au_docs(tmp_path, monkeypatch):
    docs = tmp_path / "au-docs"
    docs.mkdir()
    (docs / "venture-augur" / "websites").mkdir(parents=True)
    monkeypatch.setattr(
        "shared_vault.skills.loop_hygiene.scripts.hygiene_scan.get_documents_dir",
        lambda: docs,
    )
    monkeypatch.chdir(docs)
    result = hygiene_scan("venture-augur/websites")
    assert result["scanned_path"] == "venture-augur/websites"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/auto-test-pytest shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_scan.py`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the minimal implementation**

Write `shared-vault/skills/loop-hygiene/scripts/hygiene_scan.py`:

```python
"""hygiene_scan: read-only scan of a folder under Au-docs.

Returns file listing, optional lifecycle config, milestone pins, and
skipped never-touch paths. No side effects. The classifier (the agent
in the user's session) consumes this output.
"""
from __future__ import annotations


import importlib.util as _augur_importlib_util
import sys as _augur_sys
from pathlib import Path as _AugurPath

_augur_bootstrap_start = _AugurPath(__file__).resolve()
for _augur_bootstrap_parent in (_augur_bootstrap_start.parent, *_augur_bootstrap_start.parents):
    _augur_bootstrap_path = _augur_bootstrap_parent / "daemon" / "scripts" / "bootstrap_paths.py"
    if _augur_bootstrap_path.is_file():
        break
else:
    raise RuntimeError(f"Unable to locate shared skill bootstrap from {_augur_bootstrap_start}")

_augur_bootstrap_spec = _augur_importlib_util.spec_from_file_location(
    "_augur_shared_bootstrap_paths", _augur_bootstrap_path
)
if _augur_bootstrap_spec is None or _augur_bootstrap_spec.loader is None:
    raise RuntimeError(f"Unable to load shared skill bootstrap from {_augur_bootstrap_path}")
_augur_bootstrap_module = _augur_importlib_util.module_from_spec(_augur_bootstrap_spec)
_augur_sys.modules[_augur_bootstrap_spec.name] = _augur_bootstrap_module
_augur_bootstrap_spec.loader.exec_module(_augur_bootstrap_module)
_augur_bootstrap_module.ensure_project_paths(__file__)

from pathlib import Path
from typing import Any

from src.config.paths import get_documents_dir


class HygieneScanError(ValueError):
    """Raised when scan input is invalid (path outside Au-docs, missing, etc.)."""


def hygiene_scan(path: str) -> dict[str, Any]:
    """Scan a folder under Au-docs.

    Args:
        path: absolute or relative path. Relative paths are resolved
        against the current working directory.

    Returns:
        Dict with keys: root, scanned_path, files, lifecycle_config,
        milestone_pins, never_touch_skipped, warnings.

    Raises:
        HygieneScanError: path is outside Au-docs, missing, or not a directory.
    """
    docs_root = get_documents_dir().resolve()
    candidate = Path(path).expanduser().resolve()

    if not candidate.exists():
        raise HygieneScanError(f"path does not exist: {candidate}")
    if not candidate.is_dir():
        raise HygieneScanError(f"path is not a directory: {candidate}")
    try:
        rel = candidate.relative_to(docs_root)
    except ValueError:
        raise HygieneScanError(f"path is outside Au-docs ({docs_root}): {candidate}") from None

    return {
        "root": str(docs_root),
        "scanned_path": str(rel),
        "files": [],
        "lifecycle_config": None,
        "milestone_pins": [],
        "never_touch_skipped": [],
        "warnings": [],
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/auto-test-pytest shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_scan.py`
Expected: PASS — 5 passed

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/loop-hygiene/scripts/hygiene_scan.py shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_scan.py
git commit -m "feat(loop-hygiene): hygiene_scan skeleton with Au-docs root resolution

Resolves path against get_documents_dir(). Refuses paths outside
Au-docs, missing paths, and non-directory paths. Returns empty result
shape with root, scanned_path, files, lifecycle_config, milestone_pins,
never_touch_skipped, warnings. Bootstrap pattern matches
loop-memory/scripts/context_audit.py.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: File walker with never-touch exclusion and symlink refusal

**Files:**
- Modify: `shared-vault/skills/loop-hygiene/scripts/hygiene_scan.py`
- Modify: `shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_scan.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/test_hygiene_scan.py`:

```python
import os


def _setup_docs(tmp_path, monkeypatch):
    docs = tmp_path / "au-docs"
    docs.mkdir()
    monkeypatch.setattr(
        "shared_vault.skills.loop_hygiene.scripts.hygiene_scan.get_documents_dir",
        lambda: docs,
    )
    return docs


def test_lists_regular_files_in_scanned_folder(tmp_path, monkeypatch):
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    (folder / "guriqo-com-V10031.zip").write_bytes(b"x" * 100)
    (folder / "guriqo-com-V10032.zip").write_bytes(b"y" * 200)

    result = hygiene_scan(str(folder))
    names = sorted(f["name"] for f in result["files"])
    assert names == ["guriqo-com-V10031.zip", "guriqo-com-V10032.zip"]
    by_name = {f["name"]: f for f in result["files"]}
    assert by_name["guriqo-com-V10031.zip"]["size_bytes"] == 100
    assert by_name["guriqo-com-V10032.zip"]["size_bytes"] == 200


def test_includes_relative_path_and_mtime_and_hash(tmp_path, monkeypatch):
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "venture-augur" / "websites"
    folder.mkdir(parents=True)
    (folder / "x.zip").write_bytes(b"hello")

    result = hygiene_scan(str(folder))
    f = result["files"][0]
    assert f["relative_path"] == "venture-augur/websites/x.zip"
    assert "mtime_iso" in f and f["mtime_iso"].endswith("Z")
    # sha256 of b"hello" = 2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824
    assert f["content_hash_sha256"] == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    assert f["is_symlink"] is False


def test_skips_never_touch_files(tmp_path, monkeypatch):
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    (folder / "x.zip").write_bytes(b"x")
    (folder / "package-lock.json").write_bytes(b"{}")
    (folder / ".augur-ignore").write_text("*\n")

    result = hygiene_scan(str(folder))
    names = [f["name"] for f in result["files"]]
    assert names == ["x.zip"]
    assert "package-lock.json" in result["never_touch_skipped"]
    assert ".augur-ignore" in result["never_touch_skipped"]


def test_does_not_recurse_into_never_touch_dirs(tmp_path, monkeypatch):
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    (folder / "x.zip").write_bytes(b"x")
    archive = folder / ".archive"
    archive.mkdir()
    (archive / "old.zip").write_bytes(b"old")
    git = folder / ".git"
    git.mkdir()
    (git / "config").write_text("")

    result = hygiene_scan(str(folder))
    names = [f["name"] for f in result["files"]]
    assert names == ["x.zip"]
    # The dirs themselves are listed as skipped (relative to scanned_path)
    assert ".archive" in result["never_touch_skipped"]
    assert ".git" in result["never_touch_skipped"]


def test_refuses_symlink_files(tmp_path, monkeypatch):
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    target = folder / "real.zip"
    target.write_bytes(b"x")
    link = folder / "link.zip"
    os.symlink(target, link)

    result = hygiene_scan(str(folder))
    names = [f["name"] for f in result["files"]]
    assert names == ["real.zip"]  # symlink excluded entirely
    warnings = [w for w in result["warnings"] if "symlink" in w.lower()]
    assert any("link.zip" in w for w in warnings)


def test_does_not_recurse_into_subfolders(tmp_path, monkeypatch):
    """Scan is shallow — only direct children of the scanned path are listed."""
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    (folder / "x.zip").write_bytes(b"x")
    sub = folder / "subfolder"
    sub.mkdir()
    (sub / "y.zip").write_bytes(b"y")

    result = hygiene_scan(str(folder))
    names = [f["name"] for f in result["files"]]
    assert names == ["x.zip"]
    # The subfolder itself is not listed (only files are), and not skipped
    assert "subfolder" not in result["never_touch_skipped"]
```

- [ ] **Step 2: Run test to verify failures**

Run: `/auto-test-pytest shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_scan.py`
Expected: FAIL — the 6 new tests fail; the original 5 still pass.

- [ ] **Step 3: Extend the implementation**

Replace `hygiene_scan` in `shared-vault/skills/loop-hygiene/scripts/hygiene_scan.py` with:

```python
import hashlib
from datetime import datetime, timezone

from .never_touch import is_never_touch


def hygiene_scan(path: str) -> dict[str, Any]:
    """Scan a folder under Au-docs."""
    docs_root = get_documents_dir().resolve()
    candidate = Path(path).expanduser().resolve()

    if not candidate.exists():
        raise HygieneScanError(f"path does not exist: {candidate}")
    if not candidate.is_dir():
        raise HygieneScanError(f"path is not a directory: {candidate}")
    try:
        rel_scanned = candidate.relative_to(docs_root)
    except ValueError:
        raise HygieneScanError(f"path is outside Au-docs ({docs_root}): {candidate}") from None

    files: list[dict[str, Any]] = []
    never_touch_skipped: list[str] = []
    warnings: list[str] = []

    for entry in sorted(candidate.iterdir(), key=lambda p: p.name):
        rel_to_scanned = entry.relative_to(candidate)
        if is_never_touch(rel_to_scanned):
            never_touch_skipped.append(str(rel_to_scanned))
            continue
        if entry.is_symlink():
            warnings.append(f"refused symlink: {entry.name}")
            continue
        if not entry.is_file():
            # Subfolders are not listed in MVP — scan is shallow.
            continue
        # Compute metadata
        stat = entry.stat()
        mtime_iso = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat().replace("+00:00", "Z")
        content_hash = hashlib.sha256(entry.read_bytes()).hexdigest()
        files.append({
            "name": entry.name,
            "relative_path": str(entry.relative_to(docs_root)),
            "size_bytes": stat.st_size,
            "mtime_iso": mtime_iso,
            "content_hash_sha256": content_hash,
            "is_symlink": False,
        })

    return {
        "root": str(docs_root),
        "scanned_path": str(rel_scanned),
        "files": files,
        "lifecycle_config": None,
        "milestone_pins": [],
        "never_touch_skipped": never_touch_skipped,
        "warnings": warnings,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/auto-test-pytest shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_scan.py`
Expected: PASS — 11 passed

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/loop-hygiene/scripts/hygiene_scan.py shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_scan.py
git commit -m "feat(loop-hygiene): file walker with never-touch exclusion + symlink refusal

Shallow scan (no recursion into subfolders). Filters out never-touch
entries via shared never_touch.is_never_touch. Symlinks are refused
with a warning, not followed. Each file entry includes size, mtime
(ISO Z), sha256 content hash, and relative_path to Au-docs root.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Wire lifecycle config and milestone readers into scan

**Files:**
- Modify: `shared-vault/skills/loop-hygiene/scripts/hygiene_scan.py`
- Modify: `shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_scan.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/test_hygiene_scan.py`:

```python
import json


def test_scan_returns_lifecycle_config(tmp_path, monkeypatch):
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    (folder / ".augur-lifecycle.yaml").write_text(
        "enabled: true\n"
        "pattern_hints:\n  - 'guriqo-com-V*.zip'\n"
        "keep_latest: 1\n"
        "deploy_root: false\n"
    )
    (folder / "x.zip").write_bytes(b"x")

    result = hygiene_scan(str(folder))
    assert result["lifecycle_config"] is not None
    assert result["lifecycle_config"]["enabled"] is True
    assert result["lifecycle_config"]["pattern_hints"] == ["guriqo-com-V*.zip"]
    assert result["lifecycle_config"]["keep_latest"] == 1
    assert result["lifecycle_config"]["deploy_root"] is False


def test_scan_returns_milestone_pins(tmp_path, monkeypatch):
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    pins_payload = {
        "websites/guriqo-com-V10025.zip": {
            "tag": "intel-submission",
            "tagged_at": "2026-04-25T10:00:00Z",
            "note": "sent",
        }
    }
    (folder / ".milestones.json").write_text(json.dumps(pins_payload))
    (folder / "x.zip").write_bytes(b"x")

    result = hygiene_scan(str(folder))
    assert len(result["milestone_pins"]) == 1
    pin = result["milestone_pins"][0]
    assert pin["relative_path"] == "websites/guriqo-com-V10025.zip"
    assert pin["tag"] == "intel-submission"


def test_scan_refuses_when_lifecycle_enabled_false(tmp_path, monkeypatch):
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    (folder / ".augur-lifecycle.yaml").write_text("enabled: false\n")

    with pytest.raises(HygieneScanError, match="enabled: false"):
        hygiene_scan(str(folder))


def test_scan_surfaces_malformed_lifecycle_as_warning(tmp_path, monkeypatch):
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    (folder / ".augur-lifecycle.yaml").write_text("enabled: : invalid\n")
    (folder / "x.zip").write_bytes(b"x")

    result = hygiene_scan(str(folder))
    # Scan does not refuse the whole folder; it surfaces the parse error as a warning
    assert result["lifecycle_config"] is None
    assert any("lifecycle" in w.lower() for w in result["warnings"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/auto-test-pytest shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_scan.py::test_scan_returns_lifecycle_config`
Expected: FAIL — `lifecycle_config` is still None.

- [ ] **Step 3: Extend the implementation**

In `scripts/hygiene_scan.py`, add the imports and wire the readers in:

```python
from dataclasses import asdict

from .lifecycle_config import (
    LifecycleConfig,
    LifecycleConfigError,
    MilestonePin,
    read_lifecycle_config,
    read_milestones,
)
```

Inside `hygiene_scan`, after the directory-relative computation and before walking files, add:

```python
    # Read lifecycle config and milestones; both are optional.
    lifecycle_config: dict[str, Any] | None = None
    milestone_pins: list[dict[str, Any]] = []
    try:
        cfg = read_lifecycle_config(candidate)
        if cfg is not None:
            if not cfg.enabled:
                raise HygieneScanError(
                    f"lifecycle enabled: false at {candidate} — refusing scan"
                )
            lifecycle_config = asdict(cfg)
    except LifecycleConfigError as exc:
        warnings.append(f"lifecycle config parse error: {exc}")

    try:
        pins = read_milestones(candidate)
        milestone_pins = [asdict(p) for p in pins]
    except LifecycleConfigError as exc:
        warnings.append(f"milestones parse error: {exc}")
```

(Note: `warnings` must be initialized before this block — move its initialization up if needed.)

Replace the return statement to use `lifecycle_config` and `milestone_pins`:

```python
    return {
        "root": str(docs_root),
        "scanned_path": str(rel_scanned),
        "files": files,
        "lifecycle_config": lifecycle_config,
        "milestone_pins": milestone_pins,
        "never_touch_skipped": never_touch_skipped,
        "warnings": warnings,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/auto-test-pytest shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_scan.py`
Expected: PASS — 15 passed

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/loop-hygiene/scripts/hygiene_scan.py shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_scan.py
git commit -m "feat(loop-hygiene): wire lifecycle config + milestone pins into scan

Scan reads .augur-lifecycle.yaml and .milestones.json from the scanned
folder. enabled: false in the lifecycle config refuses the entire scan.
Malformed config does not refuse the scan — it is surfaced as a
warning so the agent can decide. milestone_pins are returned as dicts
(dataclass-asdict serialized).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## C3 — `hygiene_apply` implementation

### Task 7: Skeleton + input validation + dry-run path

**Files:**
- Create: `shared-vault/skills/loop-hygiene/scripts/hygiene_apply.py`
- Create: `shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_apply.py`

- [ ] **Step 1: Write the failing test**

Write `shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_apply.py`:

```python
"""Tests for hygiene_apply — the atomic destructive primitive."""
from pathlib import Path

import pytest

from shared_vault.skills.loop_hygiene.scripts.hygiene_apply import (
    hygiene_apply,
    HygieneApplyError,
)


def _setup_docs(tmp_path, monkeypatch):
    docs = tmp_path / "au-docs"
    docs.mkdir()
    monkeypatch.setattr(
        "shared_vault.skills.loop_hygiene.scripts.hygiene_apply.get_documents_dir",
        lambda: docs,
    )
    return docs


def test_refuses_unsupported_root(tmp_path, monkeypatch):
    _setup_docs(tmp_path, monkeypatch)
    with pytest.raises(HygieneApplyError, match="root"):
        hygiene_apply(root="vault", moves=[], dry_run=True)


def test_empty_moves_dry_run_returns_empty_result(tmp_path, monkeypatch):
    _setup_docs(tmp_path, monkeypatch)
    result = hygiene_apply(root="docs", moves=[], dry_run=True)
    assert result["dry_run"] is True
    assert result["moves"] == []
    assert result["total_bytes_archived"] == 0
    assert result["paths_written"] == []


def test_dry_run_validates_but_does_not_move(tmp_path, monkeypatch):
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    src = folder / "x.zip"
    src.write_bytes(b"hello")

    result = hygiene_apply(
        root="docs",
        moves=[{
            "from": "websites/x.zip",
            "reason": "test",
            "artifact_group": "test-group",
        }],
        dry_run=True,
    )

    assert result["dry_run"] is True
    assert len(result["moves"]) == 1
    move = result["moves"][0]
    assert move["status"] == "would_succeed"
    assert move["from"] == "websites/x.zip"
    assert move["to"] == "websites/.archive/x.zip"
    # File NOT moved
    assert src.exists()
    assert not (folder / ".archive" / "x.zip").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/auto-test-pytest shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_apply.py`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the minimal implementation**

Write `shared-vault/skills/loop-hygiene/scripts/hygiene_apply.py`:

```python
"""hygiene_apply: atomic destructive primitive that moves stale-version
files into per-folder .archive/ directories.

Dry-run by default through the caller; `dry_run=False` enables actual
moves. Every move is validated independently — refusal of one move
does not abort others. Atomicity is per-file via os.rename.
"""
from __future__ import annotations


import importlib.util as _augur_importlib_util
import sys as _augur_sys
from pathlib import Path as _AugurPath

_augur_bootstrap_start = _AugurPath(__file__).resolve()
for _augur_bootstrap_parent in (_augur_bootstrap_start.parent, *_augur_bootstrap_start.parents):
    _augur_bootstrap_path = _augur_bootstrap_parent / "daemon" / "scripts" / "bootstrap_paths.py"
    if _augur_bootstrap_path.is_file():
        break
else:
    raise RuntimeError(f"Unable to locate shared skill bootstrap from {_augur_bootstrap_start}")

_augur_bootstrap_spec = _augur_importlib_util.spec_from_file_location(
    "_augur_shared_bootstrap_paths", _augur_bootstrap_path
)
if _augur_bootstrap_spec is None or _augur_bootstrap_spec.loader is None:
    raise RuntimeError(f"Unable to load shared skill bootstrap from {_augur_bootstrap_path}")
_augur_bootstrap_module = _augur_importlib_util.module_from_spec(_augur_bootstrap_spec)
_augur_sys.modules[_augur_bootstrap_spec.name] = _augur_bootstrap_module
_augur_bootstrap_spec.loader.exec_module(_augur_bootstrap_module)
_augur_bootstrap_module.ensure_project_paths(__file__)

from pathlib import Path
from typing import Any

from src.config.paths import get_documents_dir

SUPPORTED_ROOTS = {"docs"}


class HygieneApplyError(ValueError):
    """Raised when apply input is structurally invalid (unsupported root, etc.)."""


def hygiene_apply(
    root: str,
    moves: list[dict[str, Any]],
    dry_run: bool,
) -> dict[str, Any]:
    """Apply (or dry-run) a list of archive moves.

    Args:
        root: store identifier. MVP supports only "docs".
        moves: list of {from, reason, artifact_group} dicts. `from` is
            relative to the store root.
        dry_run: when True, validate every move without modifying disk.

    Returns:
        Dict with: dry_run, moves (list of per-move results),
        total_bytes_archived, paths_written.
    """
    if root not in SUPPORTED_ROOTS:
        raise HygieneApplyError(f"unsupported root: {root!r}; MVP supports only {sorted(SUPPORTED_ROOTS)}")

    store_root = get_documents_dir().resolve()
    move_results: list[dict[str, Any]] = []
    total_bytes = 0
    paths_written: list[str] = []

    for move in moves:
        src_rel = move["from"]
        src_abs = (store_root / src_rel).resolve()
        dest_rel = _compute_archive_destination(src_rel)
        result = {
            "from": src_rel,
            "to": dest_rel,
            "reason": move.get("reason", ""),
            "artifact_group": move.get("artifact_group"),
        }
        if dry_run:
            # Minimal validation in this task; expanded in Task 8.
            if not src_abs.is_file():
                result["status"] = "would_refuse"
                result["refusal_category"] = "source_missing"
            else:
                result["status"] = "would_succeed"
                result["size_bytes"] = src_abs.stat().st_size
        else:
            raise HygieneApplyError("real apply not yet implemented; see Task 9")
        move_results.append(result)

    return {
        "dry_run": dry_run,
        "moves": move_results,
        "total_bytes_archived": total_bytes,
        "paths_written": paths_written,
    }


def _compute_archive_destination(src_rel: str) -> str:
    """Given a source relative to the store root, return the archive destination.

    e.g. 'websites/x.zip' -> 'websites/.archive/x.zip'
    """
    p = Path(src_rel)
    return str(p.parent / ".archive" / p.name)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/auto-test-pytest shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_apply.py`
Expected: PASS — 3 passed

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/loop-hygiene/scripts/hygiene_apply.py shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_apply.py
git commit -m "feat(loop-hygiene): hygiene_apply skeleton with dry-run path

Validates root (only 'docs' supported in MVP). Iterates moves and
computes archive destination per the spec rule (<dir-of-source>/.archive/<basename>).
Dry-run reports per-move would_succeed/would_refuse without touching
the filesystem. Real apply not yet implemented — that arrives in Task 9.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: Per-move validation refusal categories

**Files:**
- Modify: `shared-vault/skills/loop-hygiene/scripts/hygiene_apply.py`
- Modify: `shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_apply.py`

Cover refusal categories: never_touch, symlink, milestone_pinned, cross_filesystem, deploy_root, source_missing. Cross-fs and deploy-root are tested with mocks/fixtures.

- [ ] **Step 1: Add failing tests**

Append to `tests/test_hygiene_apply.py`:

```python
import json
import os


def test_refuses_never_touch_source(tmp_path, monkeypatch):
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    (folder / "package-lock.json").write_bytes(b"{}")

    result = hygiene_apply(
        root="docs",
        moves=[{"from": "websites/package-lock.json", "reason": "x"}],
        dry_run=True,
    )
    move = result["moves"][0]
    assert move["status"] == "would_refuse"
    assert move["refusal_category"] == "never_touch"


def test_refuses_symlink_source(tmp_path, monkeypatch):
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    target = folder / "real.zip"
    target.write_bytes(b"x")
    link = folder / "link.zip"
    os.symlink(target, link)

    result = hygiene_apply(
        root="docs",
        moves=[{"from": "websites/link.zip", "reason": "x"}],
        dry_run=True,
    )
    move = result["moves"][0]
    assert move["status"] == "would_refuse"
    assert move["refusal_category"] == "symlink"


def test_refuses_milestone_pinned_source(tmp_path, monkeypatch):
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    (folder / "pinned.zip").write_bytes(b"x")
    pins = {
        "websites/pinned.zip": {
            "tag": "intel-submission",
            "tagged_at": "2026-04-25T10:00:00Z",
        }
    }
    (folder / ".milestones.json").write_text(json.dumps(pins))

    result = hygiene_apply(
        root="docs",
        moves=[{"from": "websites/pinned.zip", "reason": "x"}],
        dry_run=True,
    )
    move = result["moves"][0]
    assert move["status"] == "would_refuse"
    assert move["refusal_category"] == "milestone_pinned"


def test_refuses_deploy_root_source(tmp_path, monkeypatch):
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    (folder / "x.zip").write_bytes(b"x")
    (folder / ".augur-lifecycle.yaml").write_text("deploy_root: true\n")

    result = hygiene_apply(
        root="docs",
        moves=[{"from": "websites/x.zip", "reason": "x"}],
        dry_run=True,
    )
    move = result["moves"][0]
    assert move["status"] == "would_refuse"
    assert move["refusal_category"] == "deploy_root"


def test_refuses_source_outside_store_root(tmp_path, monkeypatch):
    _setup_docs(tmp_path, monkeypatch)
    # Path with .. escape attempt
    result = hygiene_apply(
        root="docs",
        moves=[{"from": "../escape.zip", "reason": "x"}],
        dry_run=True,
    )
    move = result["moves"][0]
    assert move["status"] == "would_refuse"
    assert move["refusal_category"] == "outside_store"


def test_refusal_of_one_move_does_not_abort_others(tmp_path, monkeypatch):
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    (folder / "good.zip").write_bytes(b"x")
    (folder / "package-lock.json").write_bytes(b"{}")

    result = hygiene_apply(
        root="docs",
        moves=[
            {"from": "websites/package-lock.json", "reason": "x"},
            {"from": "websites/good.zip", "reason": "x"},
        ],
        dry_run=True,
    )
    assert result["moves"][0]["status"] == "would_refuse"
    assert result["moves"][1]["status"] == "would_succeed"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/auto-test-pytest shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_apply.py`
Expected: FAIL — six new tests fail.

- [ ] **Step 3: Extend the implementation**

In `scripts/hygiene_apply.py`, add imports:

```python
from .never_touch import is_never_touch
from .lifecycle_config import LifecycleConfigError, read_lifecycle_config, read_milestones
```

Replace the dry-run validation block inside `hygiene_apply` with a unified validation helper:

```python
def _validate_move(
    src_rel: str,
    store_root: Path,
) -> tuple[str | None, Path | None]:
    """Return (refusal_category, src_abs) — refusal_category is None if the move is OK."""
    src_rel_path = Path(src_rel)
    if is_never_touch(src_rel_path):
        return "never_touch", None

    # Outside-store: any move whose resolved absolute path escapes the store root.
    src_abs = (store_root / src_rel).resolve()
    try:
        src_abs.relative_to(store_root)
    except ValueError:
        return "outside_store", None

    if not src_abs.exists():
        return "source_missing", src_abs
    if src_abs.is_symlink():
        return "symlink", src_abs
    if not src_abs.is_file():
        return "source_missing", src_abs

    # Milestone check
    folder = src_abs.parent
    try:
        pins = read_milestones(folder)
    except LifecycleConfigError:
        pins = []
    for pin in pins:
        pin_abs = (store_root / pin.relative_path).resolve()
        if pin_abs == src_abs:
            return "milestone_pinned", src_abs

    # Deploy-root check
    try:
        cfg = read_lifecycle_config(folder)
    except LifecycleConfigError:
        cfg = None
    if cfg is not None and cfg.deploy_root:
        return "deploy_root", src_abs

    return None, src_abs
```

Inside `hygiene_apply`, replace the dry-run validation with a call to `_validate_move`:

```python
    for move in moves:
        src_rel = move["from"]
        dest_rel = _compute_archive_destination(src_rel)
        result = {
            "from": src_rel,
            "to": dest_rel,
            "reason": move.get("reason", ""),
            "artifact_group": move.get("artifact_group"),
        }
        refusal, src_abs = _validate_move(src_rel, store_root)
        if refusal is not None:
            result["status"] = "would_refuse" if dry_run else "refused"
            result["refusal_category"] = refusal
        else:
            assert src_abs is not None
            if dry_run:
                result["status"] = "would_succeed"
                result["size_bytes"] = src_abs.stat().st_size
            else:
                raise HygieneApplyError("real apply not yet implemented; see Task 9")
        move_results.append(result)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/auto-test-pytest shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_apply.py`
Expected: PASS — 9 passed

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/loop-hygiene/scripts/hygiene_apply.py shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_apply.py
git commit -m "feat(loop-hygiene): per-move validation with six refusal categories

never_touch, symlink, milestone_pinned, deploy_root, source_missing,
outside_store. Refusal of one move never aborts the others — each
move has its own per-move result. Validation is shared between
dry-run and real-apply paths.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: Real apply with atomic os.rename + dup-suffix collision

**Files:**
- Modify: `shared-vault/skills/loop-hygiene/scripts/hygiene_apply.py`
- Modify: `shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_apply.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/test_hygiene_apply.py`:

```python
import hashlib


def test_real_apply_moves_file_to_archive(tmp_path, monkeypatch):
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    src = folder / "x.zip"
    src.write_bytes(b"payload")

    result = hygiene_apply(
        root="docs",
        moves=[{"from": "websites/x.zip", "reason": "stale", "artifact_group": "g"}],
        dry_run=False,
    )

    assert result["dry_run"] is False
    move = result["moves"][0]
    assert move["status"] == "succeeded"
    assert not src.exists()
    dest = folder / ".archive" / "x.zip"
    assert dest.exists()
    assert dest.read_bytes() == b"payload"
    assert result["total_bytes_archived"] == len(b"payload")


def test_apply_creates_archive_directory(tmp_path, monkeypatch):
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    (folder / "x.zip").write_bytes(b"x")

    assert not (folder / ".archive").exists()
    hygiene_apply(
        root="docs",
        moves=[{"from": "websites/x.zip", "reason": "stale"}],
        dry_run=False,
    )
    assert (folder / ".archive").is_dir()


def test_destination_collision_appends_dup_suffix(tmp_path, monkeypatch):
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    archive = folder / ".archive"
    archive.mkdir()
    # Pre-existing archive entry with the same basename
    (archive / "x.zip").write_bytes(b"older")
    src = folder / "x.zip"
    src.write_bytes(b"newer-but-second-archived")

    result = hygiene_apply(
        root="docs",
        moves=[{"from": "websites/x.zip", "reason": "stale"}],
        dry_run=False,
    )
    move = result["moves"][0]
    assert move["status"] == "succeeded"
    # Destination should end with .dup-<shorthash>
    assert ".dup-" in move["to"]
    # Original archive entry untouched
    assert (archive / "x.zip").read_bytes() == b"older"
    # Newly-archived entry exists under the dup name
    dup_dest = docs / move["to"]
    assert dup_dest.read_bytes() == b"newer-but-second-archived"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/auto-test-pytest shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_apply.py::test_real_apply_moves_file_to_archive`
Expected: FAIL — `HygieneApplyError: real apply not yet implemented`

- [ ] **Step 3: Extend the implementation**

In `scripts/hygiene_apply.py`, replace the `else: raise HygieneApplyError("real apply not yet implemented...")` branch with a real-apply implementation. Add the helper:

```python
import hashlib
import os


def _resolve_destination(src_abs: Path, dest_abs: Path) -> Path:
    """If dest_abs exists, append .dup-<shorthash-of-src-path> to break the tie.

    Hash uses the source path so re-archiving the same source path always
    collides to the same dup destination (idempotent).
    """
    if not dest_abs.exists():
        return dest_abs
    short_hash = hashlib.sha256(str(src_abs).encode()).hexdigest()[:8]
    return dest_abs.with_name(f"{dest_abs.name}.dup-{short_hash}")
```

Replace the real-apply branch:

```python
            else:
                # Real apply
                dest_abs = (store_root / dest_rel).resolve()
                dest_abs.parent.mkdir(parents=True, exist_ok=True)
                actual_dest = _resolve_destination(src_abs, dest_abs)
                # Refuse cross-filesystem
                if src_abs.stat().st_dev != dest_abs.parent.stat().st_dev:
                    result["status"] = "refused"
                    result["refusal_category"] = "cross_filesystem"
                    move_results.append(result)
                    continue
                size_bytes = src_abs.stat().st_size
                os.rename(src_abs, actual_dest)
                result["status"] = "succeeded"
                result["to"] = str(actual_dest.relative_to(store_root))
                result["size_bytes"] = size_bytes
                total_bytes += size_bytes
                paths_written.append(result["to"])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/auto-test-pytest shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_apply.py`
Expected: PASS — 12 passed

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/loop-hygiene/scripts/hygiene_apply.py shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_apply.py
git commit -m "feat(loop-hygiene): real apply via atomic os.rename + dup-suffix collision

Creates .archive/ on demand. Atomic move via os.rename. On destination
collision, appends .dup-<short-hash-of-source-path> (idempotent per
source path). Cross-filesystem moves refused (st_dev mismatch).
total_bytes_archived and paths_written populated for the result.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 10: Manifest append with rollback-on-failure

**Files:**
- Modify: `shared-vault/skills/loop-hygiene/scripts/hygiene_apply.py`
- Modify: `shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_apply.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/test_hygiene_apply.py`:

```python
def test_manifest_jsonl_entry_written_after_move(tmp_path, monkeypatch):
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    (folder / "x.zip").write_bytes(b"x")

    hygiene_apply(
        root="docs",
        moves=[{"from": "websites/x.zip", "reason": "stale", "artifact_group": "g"}],
        dry_run=False,
    )

    manifest = folder / ".archive" / "_manifest.jsonl"
    assert manifest.exists()
    lines = manifest.read_text().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["from"] == "websites/x.zip"
    assert entry["to"] == "websites/.archive/x.zip"
    assert entry["reason"] == "stale"
    assert entry["artifact_group"] == "g"
    assert "archived_at" in entry
    assert "apply_run_id" in entry


def test_manifest_is_append_only_across_calls(tmp_path, monkeypatch):
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    (folder / "a.zip").write_bytes(b"a")
    (folder / "b.zip").write_bytes(b"b")

    hygiene_apply(
        root="docs",
        moves=[{"from": "websites/a.zip", "reason": "stale"}],
        dry_run=False,
    )
    hygiene_apply(
        root="docs",
        moves=[{"from": "websites/b.zip", "reason": "stale"}],
        dry_run=False,
    )

    manifest = folder / ".archive" / "_manifest.jsonl"
    lines = manifest.read_text().splitlines()
    assert len(lines) == 2
    entries = [json.loads(line) for line in lines]
    assert entries[0]["from"] == "websites/a.zip"
    assert entries[1]["from"] == "websites/b.zip"


def test_manifest_failure_rolls_back_rename(tmp_path, monkeypatch):
    """If manifest write fails, the move is reverted (the file is moved back)."""
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    src = folder / "x.zip"
    src.write_bytes(b"payload")

    # Patch _append_manifest to raise mid-flight
    import shared_vault.skills.loop_hygiene.scripts.hygiene_apply as ha
    original = ha._append_manifest

    def boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(ha, "_append_manifest", boom)

    result = hygiene_apply(
        root="docs",
        moves=[{"from": "websites/x.zip", "reason": "stale"}],
        dry_run=False,
    )

    move = result["moves"][0]
    assert move["status"] == "refused"
    assert move["refusal_category"] == "manifest_write_failed"
    # The source has been restored
    assert src.exists()
    assert src.read_bytes() == b"payload"
    # The destination does not exist
    assert not (folder / ".archive" / "x.zip").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/auto-test-pytest shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_apply.py::test_manifest_jsonl_entry_written_after_move`
Expected: FAIL — manifest is not written.

- [ ] **Step 3: Extend the implementation**

In `scripts/hygiene_apply.py`, add imports and helpers:

```python
import json
import uuid
from datetime import datetime, timezone


def _append_manifest(archive_dir: Path, entry: dict[str, Any]) -> None:
    """Append a single JSON object as one line to _manifest.jsonl."""
    manifest = archive_dir / "_manifest.jsonl"
    line = json.dumps(entry, separators=(",", ":")) + "\n"
    with manifest.open("a", encoding="utf-8") as f:
        f.write(line)
        f.flush()
        os.fsync(f.fileno())
```

In `hygiene_apply`, generate one apply_run_id per call:

```python
    apply_run_id = uuid.uuid4().hex
```

After a successful `os.rename`, wrap the manifest-write in try/except with rollback:

```python
                # Write manifest; on failure, roll back the rename.
                entry = {
                    "archived_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "from": src_rel,
                    "to": result["to"],
                    "reason": result["reason"],
                    "artifact_group": result.get("artifact_group"),
                    "apply_run_id": apply_run_id,
                }
                try:
                    _append_manifest(actual_dest.parent, entry)
                except OSError as exc:
                    # Roll back the rename so disk state matches the failed result.
                    os.rename(actual_dest, src_abs)
                    result["status"] = "refused"
                    result["refusal_category"] = "manifest_write_failed"
                    result["error"] = str(exc)
                    # Undo total_bytes / paths_written accounting
                    total_bytes -= size_bytes
                    paths_written.pop()
                    move_results.append(result)
                    continue
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/auto-test-pytest shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_apply.py`
Expected: PASS — 15 passed

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/loop-hygiene/scripts/hygiene_apply.py shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_apply.py
git commit -m "feat(loop-hygiene): manifest append-only log + rollback on manifest failure

After every successful os.rename, append one JSON line to
.archive/_manifest.jsonl containing archived_at, from, to, reason,
artifact_group, apply_run_id. If the manifest write fails (disk full,
permission), the rename is reverted via os.rename and the move is
reported as refused with category manifest_write_failed. fsync ensures
the manifest line hits disk before we trust the move.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 11: `.augur-ignore` + `.gitignore` propagation

**Files:**
- Modify: `shared-vault/skills/loop-hygiene/scripts/hygiene_apply.py`
- Modify: `shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_apply.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/test_hygiene_apply.py`:

```python
def test_augur_ignore_written_at_archive_root(tmp_path, monkeypatch):
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    (folder / "x.zip").write_bytes(b"x")

    hygiene_apply(
        root="docs",
        moves=[{"from": "websites/x.zip", "reason": "stale"}],
        dry_run=False,
    )

    augur_ignore = folder / ".archive" / ".augur-ignore"
    assert augur_ignore.exists()
    assert augur_ignore.read_text() == "*\n"


def test_augur_ignore_not_overwritten_if_user_modified(tmp_path, monkeypatch):
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    archive = folder / ".archive"
    archive.mkdir()
    (archive / ".augur-ignore").write_text("# custom user content\n*\n")
    (folder / "x.zip").write_bytes(b"x")

    hygiene_apply(
        root="docs",
        moves=[{"from": "websites/x.zip", "reason": "stale"}],
        dry_run=False,
    )

    assert (archive / ".augur-ignore").read_text() == "# custom user content\n*\n"


def test_gitignore_gets_archive_entry_appended(tmp_path, monkeypatch):
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    (folder / "x.zip").write_bytes(b"x")
    (docs / ".gitignore").write_text("node_modules/\n")

    hygiene_apply(
        root="docs",
        moves=[{"from": "websites/x.zip", "reason": "stale"}],
        dry_run=False,
    )

    content = (docs / ".gitignore").read_text()
    assert "node_modules/" in content
    assert ".archive/" in content


def test_gitignore_archive_entry_idempotent(tmp_path, monkeypatch):
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    (folder / "a.zip").write_bytes(b"a")
    (folder / "b.zip").write_bytes(b"b")
    (docs / ".gitignore").write_text(".archive/\n")

    hygiene_apply(root="docs", moves=[{"from": "websites/a.zip", "reason": "x"}], dry_run=False)
    hygiene_apply(root="docs", moves=[{"from": "websites/b.zip", "reason": "x"}], dry_run=False)

    # Still exactly one .archive/ line
    lines = [ln for ln in (docs / ".gitignore").read_text().splitlines() if ln.strip()]
    assert lines.count(".archive/") == 1


def test_gitignore_created_if_absent(tmp_path, monkeypatch):
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    (folder / "x.zip").write_bytes(b"x")

    hygiene_apply(root="docs", moves=[{"from": "websites/x.zip", "reason": "x"}], dry_run=False)

    gi = docs / ".gitignore"
    assert gi.exists()
    assert ".archive/" in gi.read_text()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/auto-test-pytest shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_apply.py::test_augur_ignore_written_at_archive_root`
Expected: FAIL.

- [ ] **Step 3: Extend the implementation**

In `scripts/hygiene_apply.py`, add helpers:

```python
def _ensure_augur_ignore(archive_dir: Path) -> Path | None:
    """Create .augur-ignore at the archive root with default '*\\n' if absent.
    Returns the path if it was newly created; None if it already existed.
    """
    path = archive_dir / ".augur-ignore"
    if path.exists():
        return None
    path.write_text("*\n")
    return path


def _ensure_gitignore_entry(store_root: Path) -> Path | None:
    """Append '.archive/' to <store_root>/.gitignore if not already present.
    Returns the path if it was newly written/appended; None if no change.
    """
    gi = store_root / ".gitignore"
    existing_lines = []
    if gi.exists():
        existing_lines = gi.read_text().splitlines()
        if ".archive/" in [ln.strip() for ln in existing_lines]:
            return None
    new_content = "\n".join(existing_lines + [".archive/"]) + "\n"
    gi.write_text(new_content)
    return gi
```

In `hygiene_apply`, after the move-processing loop, for each unique archive directory that had a successful move, call `_ensure_augur_ignore`; after all moves, call `_ensure_gitignore_entry` once if any move succeeded.

```python
    # Track unique archive dirs that received at least one successful move
    successful_archive_dirs: set[Path] = set()
    # ... inside the success branch of each move:
    #     successful_archive_dirs.add(actual_dest.parent)

    if not dry_run and successful_archive_dirs:
        for archive_dir in successful_archive_dirs:
            written = _ensure_augur_ignore(archive_dir)
            if written is not None:
                paths_written.append(str(written.relative_to(store_root)))
        written = _ensure_gitignore_entry(store_root)
        if written is not None:
            paths_written.append(str(written.relative_to(store_root)))
```

You'll need to thread `successful_archive_dirs.add(actual_dest.parent)` into the success branch of the move-processing loop.

- [ ] **Step 4: Run tests to verify they pass**

Run: `/auto-test-pytest shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_apply.py`
Expected: PASS — 20 passed

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/loop-hygiene/scripts/hygiene_apply.py shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_apply.py
git commit -m "feat(loop-hygiene): write .augur-ignore + append .archive/ to .gitignore

After any successful move, ensure .augur-ignore exists at every
.archive/ root (content '*'). Existing user-modified .augur-ignore is
not overwritten. After any successful apply, ensure the store-root
.gitignore contains the line '.archive/' (creates the file if absent;
idempotent — does not append twice).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## C4 — Golden fixtures + end-to-end test

### Task 12: Build the five golden fixtures

**Files:**
- Create: `shared-vault/skills/loop-hygiene/evals/fixtures/fixture_websites_versioned/` (48 fake zip files matching pattern)
- Create: `shared-vault/skills/loop-hygiene/evals/fixtures/fixture_logos_mixed/`
- Create: `shared-vault/skills/loop-hygiene/evals/fixtures/fixture_format_variants/`
- Create: `shared-vault/skills/loop-hygiene/evals/fixtures/fixture_deploy_root/`
- Create: `shared-vault/skills/loop-hygiene/evals/fixtures/fixture_milestone_pinned/`
- Create: `shared-vault/skills/loop-hygiene/evals/fixtures/README.md`

- [ ] **Step 1: Write the fixtures README**

Write `shared-vault/skills/loop-hygiene/evals/fixtures/README.md`:

```markdown
# loop-hygiene golden fixtures

These directories mirror real-world bloat patterns. Tests in
`tests/test_hygiene_e2e.py` copy them into `tmp_path` and exercise
the full scan + apply pipeline against them.

| Fixture | Shape | Tested behavior |
|---|---|---|
| fixture_websites_versioned/ | 48 fake `.zip` files matching `guriqo-com-V*.zip` and `augur-run-V*.zip` patterns | scan returns all; apply moves N stale, keeps current; `.augur-ignore` written |
| fixture_logos_mixed/ | guriqo-logo.png, guriqo-logo.svg, augur-logo.png, augur-logo.svg | scan returns all four; the agent's job to recognize two artifact groups |
| fixture_format_variants/ | augur-vision-1.pdf, augur-vision-1.pptx (same logical version, different format) | scan returns both; rubric instructs the agent NOT to mark either as stale |
| fixture_deploy_root/ | .augur-lifecycle.yaml with `deploy_root: true` + a few .zip files | scan returns config; apply refuses every move with `deploy_root` |
| fixture_milestone_pinned/ | .milestones.json pinning one .pptx + several other .pptx files | scan returns pins; apply refuses the pinned file |

All fake artifact bytes are minimal (1-100 bytes per file). The
fixtures exist for plumbing tests, not for content tests.
```

- [ ] **Step 2: Build fixture_websites_versioned**

Write a small generator script `shared-vault/skills/loop-hygiene/evals/fixtures/_build_websites.py`:

```python
"""One-time generator: populates fixture_websites_versioned with 48 fake zips."""
from pathlib import Path

ROOT = Path(__file__).parent / "fixture_websites_versioned"
ROOT.mkdir(exist_ok=True)

# guriqo-com-V10001 through V10032 (32 versions)
for v in range(10001, 10033):
    (ROOT / f"guriqo-com-V{v}.zip").write_bytes(f"guriqo-com-{v}".encode())

# augur-run-V10015 through V10032 (16 versions)
for v in range(10015, 10033):
    (ROOT / f"augur-run-V{v}.zip").write_bytes(f"augur-run-{v}".encode())

# A few non-versioned files that should NOT be archived
(ROOT / "DEPLOYMENT.md").write_text("# Deployment\n")
(ROOT / "RELEASE.md").write_text("# Release\n")

# A .augur-lifecycle.yaml hinting at the patterns
(ROOT / ".augur-lifecycle.yaml").write_text(
    "enabled: true\n"
    "pattern_hints:\n"
    "  - 'guriqo-com-V*.zip'\n"
    "  - 'augur-run-V*.zip'\n"
    "keep_latest: 1\n"
)
```

Run: `python shared-vault/skills/loop-hygiene/evals/fixtures/_build_websites.py`
Expected: No output; the fixture directory now contains 48 zips + 2 markdown files + 1 yaml.

- [ ] **Step 3: Build the four smaller fixtures**

Build `fixture_logos_mixed/`:

```bash
mkdir -p shared-vault/skills/loop-hygiene/evals/fixtures/fixture_logos_mixed
cd shared-vault/skills/loop-hygiene/evals/fixtures/fixture_logos_mixed
printf 'guriqo-png' > guriqo-logo.png
printf 'guriqo-svg' > guriqo-logo.svg
printf 'augur-png' > augur-logo.png
printf 'augur-svg' > augur-logo.svg
cd -
```

Build `fixture_format_variants/`:

```bash
mkdir -p shared-vault/skills/loop-hygiene/evals/fixtures/fixture_format_variants
printf 'pdf' > shared-vault/skills/loop-hygiene/evals/fixtures/fixture_format_variants/augur-vision-1.pdf
printf 'pptx' > shared-vault/skills/loop-hygiene/evals/fixtures/fixture_format_variants/augur-vision-1.pptx
```

Build `fixture_deploy_root/`:

```bash
mkdir -p shared-vault/skills/loop-hygiene/evals/fixtures/fixture_deploy_root
printf 'enabled: true\ndeploy_root: true\n' > shared-vault/skills/loop-hygiene/evals/fixtures/fixture_deploy_root/.augur-lifecycle.yaml
printf 'v1' > shared-vault/skills/loop-hygiene/evals/fixtures/fixture_deploy_root/site-v1.zip
printf 'v2' > shared-vault/skills/loop-hygiene/evals/fixtures/fixture_deploy_root/site-v2.zip
```

Build `fixture_milestone_pinned/`:

```bash
mkdir -p shared-vault/skills/loop-hygiene/evals/fixtures/fixture_milestone_pinned
printf 'v1' > shared-vault/skills/loop-hygiene/evals/fixtures/fixture_milestone_pinned/deck-v1.pptx
printf 'v2' > shared-vault/skills/loop-hygiene/evals/fixtures/fixture_milestone_pinned/deck-v2.pptx
printf 'v3' > shared-vault/skills/loop-hygiene/evals/fixtures/fixture_milestone_pinned/deck-v3.pptx
```

Write the milestone JSON manually (avoid heredoc traps):

Create `shared-vault/skills/loop-hygiene/evals/fixtures/fixture_milestone_pinned/.milestones.json`:

```json
{
  "deck-v1.pptx": {
    "tag": "intel-submission",
    "tagged_at": "2026-04-25T10:00:00Z",
    "note": "Sent to Intel"
  }
}
```

- [ ] **Step 4: Verify fixtures exist**

Run: `find shared-vault/skills/loop-hygiene/evals/fixtures -mindepth 2 -maxdepth 2 -type f | wc -l`
Expected: at least `60` (48 zips + 2 md + 1 yaml in websites; 4 in logos; 2 in format; 3 in deploy_root (incl yaml); 4 in milestone (incl json))

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/loop-hygiene/evals/fixtures/
git commit -m "test(loop-hygiene): golden fixtures for e2e tests

Five fixtures mirroring real bloat patterns:
- fixture_websites_versioned/ (48 fake zips + lifecycle hint yaml + 2 md)
- fixture_logos_mixed/ (4 logo files, two artifact groups)
- fixture_format_variants/ (pdf + pptx of same logical version)
- fixture_deploy_root/ (deploy_root: true + 2 zips)
- fixture_milestone_pinned/ (3 decks + 1 pinned via .milestones.json)

README documents the intent of each. Bytes are minimal.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 13: End-to-end test against fixture_websites_versioned

**Files:**
- Create: `shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_e2e.py`

- [ ] **Step 1: Write the failing test**

Write `shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_e2e.py`:

```python
"""End-to-end test: copy a fixture into tmp_path, run scan + apply, verify."""
import shutil
from pathlib import Path

import pytest

from shared_vault.skills.loop_hygiene.scripts.hygiene_apply import hygiene_apply
from shared_vault.skills.loop_hygiene.scripts.hygiene_scan import hygiene_scan

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "evals" / "fixtures"


def _stage_fixture(tmp_path, monkeypatch, fixture_name: str, subdir: str = "websites") -> Path:
    """Copy a fixture into tmp_path/au-docs/<subdir>/, patch get_documents_dir."""
    docs = tmp_path / "au-docs"
    docs.mkdir()
    src = FIXTURE_ROOT / fixture_name
    dest = docs / subdir
    shutil.copytree(src, dest)
    monkeypatch.setattr(
        "shared_vault.skills.loop_hygiene.scripts.hygiene_scan.get_documents_dir",
        lambda: docs,
    )
    monkeypatch.setattr(
        "shared_vault.skills.loop_hygiene.scripts.hygiene_apply.get_documents_dir",
        lambda: docs,
    )
    return dest


def test_e2e_websites_versioned_scan_then_apply(tmp_path, monkeypatch):
    folder = _stage_fixture(tmp_path, monkeypatch, "fixture_websites_versioned")
    docs = folder.parent

    # Scan
    scan = hygiene_scan(str(folder))
    file_names = [f["name"] for f in scan["files"]]
    # 48 zips + 2 md = 50 files; lifecycle.yaml is never_touch-skipped (.augur-* prefix)
    assert len(file_names) == 50
    assert "guriqo-com-V10032.zip" in file_names
    assert "guriqo-com-V10001.zip" in file_names
    assert "augur-run-V10032.zip" in file_names
    assert "augur-run-V10015.zip" in file_names
    assert scan["lifecycle_config"] is not None
    assert ".augur-lifecycle.yaml" in scan["never_touch_skipped"]

    # Build a move list as the agent would: archive all but the highest V for each group
    stale_guriqo = [f for f in scan["files"] if f["name"].startswith("guriqo-com-V") and f["name"] != "guriqo-com-V10032.zip"]
    stale_augur = [f for f in scan["files"] if f["name"].startswith("augur-run-V") and f["name"] != "augur-run-V10032.zip"]
    moves = [
        {
            "from": f["relative_path"],
            "reason": f"superseded by {'guriqo-com-V10032.zip' if 'guriqo' in f['name'] else 'augur-run-V10032.zip'}",
            "artifact_group": "guriqo-com-build" if "guriqo" in f["name"] else "augur-run-build",
        }
        for f in stale_guriqo + stale_augur
    ]
    # 31 guriqo stale + 17 augur stale = 48 moves
    assert len(moves) == 48

    # Dry-run apply
    dry = hygiene_apply(root="docs", moves=moves, dry_run=True)
    assert all(m["status"] == "would_succeed" for m in dry["moves"])

    # Real apply
    result = hygiene_apply(root="docs", moves=moves, dry_run=False)
    assert all(m["status"] == "succeeded" for m in result["moves"])
    assert result["total_bytes_archived"] > 0

    # Live folder retains only the two currents + the two markdowns + the lifecycle yaml
    live_files = sorted(f.name for f in folder.iterdir() if f.is_file())
    assert live_files == [
        ".augur-lifecycle.yaml",
        "DEPLOYMENT.md",
        "RELEASE.md",
        "augur-run-V10032.zip",
        "guriqo-com-V10032.zip",
    ]
    # Archive has the 48 stale + manifest + .augur-ignore
    archive = folder / ".archive"
    assert (archive / "_manifest.jsonl").exists()
    assert (archive / ".augur-ignore").exists()
    archived_zips = sorted(f.name for f in archive.iterdir() if f.suffix == ".zip")
    assert len(archived_zips) == 48
    # .gitignore at docs root has .archive/
    assert ".archive/" in (docs / ".gitignore").read_text()


def test_e2e_deploy_root_refuses_apply(tmp_path, monkeypatch):
    folder = _stage_fixture(tmp_path, monkeypatch, "fixture_deploy_root", subdir="prod-site")
    scan = hygiene_scan(str(folder))
    # The agent would build moves; we simulate that.
    moves = [
        {"from": f["relative_path"], "reason": "x"} for f in scan["files"] if f["name"].endswith(".zip")
    ]
    assert len(moves) == 2
    result = hygiene_apply(root="docs", moves=moves, dry_run=False)
    for m in result["moves"]:
        assert m["status"] == "refused"
        assert m["refusal_category"] == "deploy_root"
    # Live files untouched
    assert (folder / "site-v1.zip").exists()
    assert (folder / "site-v2.zip").exists()


def test_e2e_milestone_pinned_refuses_apply(tmp_path, monkeypatch):
    folder = _stage_fixture(tmp_path, monkeypatch, "fixture_milestone_pinned", subdir="presentations")
    moves = [
        {"from": "presentations/deck-v1.pptx", "reason": "stale"},
        {"from": "presentations/deck-v2.pptx", "reason": "stale"},
    ]
    result = hygiene_apply(root="docs", moves=moves, dry_run=False)
    # v1 is pinned, v2 is not
    by_from = {m["from"]: m for m in result["moves"]}
    assert by_from["presentations/deck-v1.pptx"]["status"] == "refused"
    assert by_from["presentations/deck-v1.pptx"]["refusal_category"] == "milestone_pinned"
    assert by_from["presentations/deck-v2.pptx"]["status"] == "succeeded"
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `/auto-test-pytest shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_e2e.py`
Expected: PASS — 3 passed (all pieces from C1-C3 are already in place).

If any test fails, debug and fix in this task — do not move on. The e2e is the proof that the unit tests' contracts compose.

- [ ] **Step 3: Commit**

```bash
git add shared-vault/skills/loop-hygiene/augur/tests/test_hygiene_e2e.py
git commit -m "test(loop-hygiene): end-to-end test against three golden fixtures

Stages each fixture into tmp_path/au-docs/, runs full scan + apply
pipeline, verifies post-state. Three scenarios:
- fixture_websites_versioned: 48 stale zips archived, currents kept,
  .augur-ignore and .gitignore written
- fixture_deploy_root: every move refused with deploy_root category,
  live files untouched
- fixture_milestone_pinned: pinned file refused, others succeed

This is the proof that unit-test contracts compose under realistic
data shapes.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## C5 — MCP surface + slash command

### Task 14: MCP tool implementation wrappers

**Files:**
- Create: `src/mcp/augur_core/tools/core/hygiene.py`
- Modify: `src/mcp/augur_core/tools/core/__init__.py` (registration)

- [ ] **Step 1: Write the MCP tool impl wrappers**

Write `src/mcp/augur_core/tools/core/hygiene.py`:

```python
"""hygiene-scan and hygiene-apply MCP tool implementations.

Thin wrappers around the skill's scripts. The skill at
shared-vault/skills/loop-hygiene/ owns the logic; this file owns the
MCP-tool surface (FastMCP registration, JSON-serializable response,
async signature for the MCP server).
"""
from __future__ import annotations

import json
from typing import Any

from src.mcp.augur_shared.logging import get_entity_logger

logger = get_entity_logger("mcp")


async def hygiene_scan_impl(path: str) -> str:
    """MCP tool: scan a folder under Au-docs (read-only).

    Returns a JSON string with the structured scan result. The agent
    in the user's session reasons over this output.
    """
    # Lazy import so the MCP server can start without the skill being installed.
    from shared_vault.skills.loop_hygiene.scripts.hygiene_scan import (
        HygieneScanError,
        hygiene_scan,
    )

    try:
        result = hygiene_scan(path)
        return json.dumps({"success": True, **result})
    except HygieneScanError as exc:
        logger.warning("hygiene-scan refused path=%r: %s", path, exc)
        return json.dumps({"success": False, "error": str(exc)})


async def hygiene_apply_impl(
    root: str,
    moves: list[dict[str, Any]],
    dry_run: bool = True,
) -> str:
    """MCP tool: apply (or dry-run) a list of archive moves.

    `dry_run` defaults to True for safety. The slash command must pass
    `dry_run=False` explicitly when `--apply` is in scope.
    """
    from shared_vault.skills.loop_hygiene.scripts.hygiene_apply import (
        HygieneApplyError,
        hygiene_apply,
    )

    try:
        result = hygiene_apply(root=root, moves=moves, dry_run=dry_run)
        return json.dumps({"success": True, **result})
    except HygieneApplyError as exc:
        logger.warning("hygiene-apply refused: %s", exc)
        return json.dumps({"success": False, "error": str(exc)})
```

- [ ] **Step 2: Register the tools**

Open `src/mcp/augur_core/tools/core/__init__.py`. Near the existing tool registrations (search for `register_core_tools` or `@mcp.tool`), add:

```python
from .hygiene import hygiene_apply_impl, hygiene_scan_impl
```

Find the section where other tools are registered with `@mcp.tool(...)` (e.g., `vault_file_read`, `cross_skill`). Add the two new registrations following the same pattern. Example shape (adjust to match the file's existing pattern):

```python
@mcp.tool(
    name="hygiene-scan",
    description="Read-only scan of a folder under Au-docs. Returns files, lifecycle config, milestone pins, never-touch skips. The agent in your session reasons over this output to propose archives.",
    annotations=tool_annotations(read_only=True),
)
async def hygiene_scan(path: str) -> str:
    return await hygiene_scan_impl(path)


@mcp.tool(
    name="hygiene-apply",
    description="Apply (or dry-run) a list of archive moves. dry_run defaults to True. Moves are atomic per file; refusal of one does not abort others. See response 'moves[].status' and 'moves[].refusal_category' for per-move outcomes.",
    annotations=tool_annotations(read_only=False),
)
async def hygiene_apply(root: str, moves: list[dict[str, Any]], dry_run: bool = True) -> str:
    return await hygiene_apply_impl(root=root, moves=moves, dry_run=dry_run)
```

The exact decorator + annotations call must match the surrounding code in `__init__.py`. Inspect 2-3 existing tool registrations and copy their style.

- [ ] **Step 3: Verify the MCP server still imports cleanly**

Run: `python -c "from src.mcp.augur_core.tools.core import register_core_tools; print('OK')"`
Expected: `OK`

If the import fails (typically because `Any` or `list` annotations aren't imported in `__init__.py`), add the necessary `from typing import Any` at the top of the file.

- [ ] **Step 4: Commit**

```bash
git add src/mcp/augur_core/tools/core/hygiene.py src/mcp/augur_core/tools/core/__init__.py
git commit -m "feat(loop-hygiene): register hygiene-scan and hygiene-apply MCP tools

Thin wrappers in src/mcp/augur_core/tools/core/hygiene.py import from
shared-vault/skills/loop-hygiene/scripts/ via lazy import. Tools
returned as JSON strings (matching the existing impl pattern in
vault_ops.py). hygiene-apply dry_run defaults to True. Errors caught
and returned as {success:false, error:str}; never raised across the
MCP boundary.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 15: Slash command + rubric reference

**Files:**
- Create: `shared-vault/skills/loop-hygiene/commands/sweep-stores.md`
- Create: `shared-vault/skills/loop-hygiene/references/sweep-rubric.md`

- [ ] **Step 1: Write the rubric reference**

Write `shared-vault/skills/loop-hygiene/references/sweep-rubric.md`:

```markdown
# /sweep-stores classification rubric

This is the rubric the agent applies to `hygiene-scan` output to decide which files are stale versions and which are current.

## Artifact groups

Two files belong to the same `artifact_group` if and only if:

1. They share the same base name + a version marker that differs (e.g., `guriqo-com-V10031.zip` and `guriqo-com-V10032.zip` → group `guriqo-com-build`), OR
2. They share the same role and the lifecycle config's `pattern_hints` group them via a common glob (e.g., a glob `augur-deck-v*.pptx` matches `augur-deck-v1.pptx` and `augur-deck-v2.pptx`).

Files of the **same logical name + different format** (e.g., `augur-vision-1.pdf` and `augur-vision-1.pptx`) are NOT in the same group. Both are kept — different formats serve different purposes.

## Picking the current member

Within a group:
- The current is the one with the highest version marker (numeric comparison).
- Tiebreaker: latest `mtime_iso`.

## Refusals (the agent must NOT propose these as moves)

- Any file under the never-touch list (`.git/`, `.obsidian/`, `.pytest_cache/`, `.tmp.driveupload/`, `node_modules/`, `.venv/`, `__pycache__/`, `.archive/`, `.augur-*` markers, lockfiles).
- Any file in a folder whose `.augur-lifecycle.yaml` declares `deploy_root: true`. Report the folder but tell the user it requires manual filesystem action.
- Any file appearing in `milestone_pins[].relative_path`. Surface the pin to the user as part of the proposal summary.

## Output format the agent must produce

Before any apply call, the agent must show the user a structured proposal:

```
## Sweep proposal — <scanned_path>

### Group: <artifact_group>  (<N> stale + 1 current)
- Keep: <current-filename>  (size, mtime)
- Archive:
  - <stale-filename>  reason: superseded by <current-filename>
  - ...

### Refused / skipped
- <filename>  category: <deploy_root | milestone_pinned | never_touch>  reason: ...

Total: <N> moves, <total-bytes> archived.
```

The user then approves (e.g., "apply", "apply except group X", "tag Y as milestone first"). The agent calls `hygiene-apply` with `dry_run=False` and the approved moves list.

## Edge cases

- Single member in a group → no proposal; the file is already canonical.
- Group spans subfolders → the agent does NOT recurse; only direct children of the scanned path are classified (consistent with `hygiene-scan`'s shallow walk).
- Ambiguous cases (no clear version marker, unfamiliar naming) → the agent describes the ambiguity and asks the user, rather than guessing.
```

- [ ] **Step 2: Write the slash command**

Write `shared-vault/skills/loop-hygiene/commands/sweep-stores.md`:

```markdown
---
description: Sweep stale-version artifacts in a folder under Au-docs into per-folder .archive/ via the agent-in-session as classifier.
visibility: core
x-augur-export-command: true
---

# /sweep-stores

Sweep stale-version artifacts in a folder under Au-docs into per-folder `.archive/` directories that AI scanners ignore. You (the agent in this session) classify; the user approves; the MCP tools execute atomically.

## Usage

```bash
/sweep-stores <path>                  # dry-run (default)
/sweep-stores <path> --apply          # destructive
/sweep-stores <path> --paths-only     # emit only the paths that would be archived; no reasoning text
```

`<path>` is a folder under `Au-docs/` (absolute or relative). Au-vault paths are refused in MVP.

## What it does (read this carefully before acting)

1. Call MCP tool `hygiene-scan <path>` to get the file listing, optional lifecycle config, milestone pins, and never-touch skips.
2. **Classify** using the rubric at `references/sweep-rubric.md`. Group files into `artifact_group`s, pick the `current` per group, list `stale` files with one-line reasoning.
3. **Present** the proposal to the user as a structured summary (groups, current, stale, refusals). Do NOT call `hygiene-apply` yet.
4. **Wait for explicit user approval.** Acceptable forms: "apply", "apply only group X", "skip group Y", "tag file Z as milestone first then apply".
5. If the user approves, call MCP tool `hygiene-apply` with:
   - `root="docs"`
   - `moves=[{from: relative_path, reason: "...", artifact_group: "..."}]`
   - `dry_run=false` if and only if the user passed `--apply`; otherwise `dry_run=true`.
6. **Report the result** including any per-move refusals (with their `refusal_category`).

## Rubric (full text)

See `references/sweep-rubric.md`. Key rules:

- An artifact group is files sharing a base name + version marker, OR files matching a `pattern_hints` glob.
- Different formats of the same logical version are NOT in the same group.
- Files in `.augur-lifecycle.yaml` `deploy_root: true` folders → REPORT, never propose moves.
- Files in `milestone_pins` → REPORT, never propose moves.
- Files in `never_touch_skipped` → already excluded by `hygiene-scan`; do not include them in moves.

## Required output format

Before any `hygiene-apply` call, show the user:

```
## Sweep proposal — <scanned_path>

### Group: <artifact_group>  (<N> stale + 1 current)
- Keep: <current-filename>
- Archive:
  - <stale-filename>  reason: superseded by <current-filename>
  - ...

### Refused / skipped
- <filename>  category: <deploy_root | milestone_pinned | never_touch>

Total: <N> moves, <total-bytes> archived.
Run with --apply to execute.
```

## Refusal handling

If `hygiene-apply` returns per-move refusals (`status: "refused"`), the user MUST be told which files and why. Do not bury refusals.

## Safety

- Dry-run is the default. `--apply` is required for any destructive action.
- One move's refusal does not abort other moves; report each.
- After `--apply` succeeds, remind the user to verify in a fresh AI client session that archived files are no longer surfaced.

## Spec

[docs/superpowers/specs/2026-05-11-loop-hygiene-design.md](../../../../docs/superpowers/specs/2026-05-11-loop-hygiene-design.md)
```

- [ ] **Step 3: Verify the slash command appears in `/commands`**

Run: `python -c "from pathlib import Path; p = Path('shared-vault/skills/loop-hygiene/commands/sweep-stores.md'); assert p.exists(); print(p.read_text()[:200])"`
Expected: prints the frontmatter and the start of `# /sweep-stores`.

Run: `/commands | head -50` (this triggers a `list-commands` MCP call; if `sweep-stores` appears, registration is complete; if not, the skill manifest needs a resync — run `/dev-sync`).

- [ ] **Step 4: Commit**

```bash
git add shared-vault/skills/loop-hygiene/commands/sweep-stores.md shared-vault/skills/loop-hygiene/references/sweep-rubric.md
git commit -m "feat(loop-hygiene): /sweep-stores slash command + classification rubric

Command is markdown only (no code). Instructs the agent to call
hygiene-scan, classify per the rubric (artifact_group, current,
stale), present the proposal, wait for user approval, then call
hygiene-apply (dry_run defaulting to true; --apply flips it). Rubric
extracted to references/sweep-rubric.md for stability across surfaces.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 16: Capability policy table update

**Files:**
- Modify: `CLAUDE.md` (capability policy table)
- Modify: `config/system/capability_exposure.yaml`

- [ ] **Step 1: Inspect existing capability_exposure.yaml**

Run: `cat config/system/capability_exposure.yaml | head -40`
Note the format and the pattern other tools use.

- [ ] **Step 2: Add the two new tools to capability_exposure.yaml**

Open `config/system/capability_exposure.yaml`. Following the existing pattern (use the same nesting and keys as adjacent entries), add:

```yaml
mcp-tool:hygiene-scan:
  export_to:
    - mcp
  owner: loop-hygiene
  preferred_surface: mcp via dashboard

mcp-tool:hygiene-apply:
  export_to:
    - mcp
  owner: loop-hygiene
  preferred_surface: mcp via dashboard
```

(The exact YAML shape depends on the file's existing schema. Match the file's pattern — if entries use `tool-id: { export_to, owner, preferred_surface }` shape, copy that.)

- [ ] **Step 3: Add the rows to CLAUDE.md capability policy table**

Open `CLAUDE.md`. Find the capability policy table (around line 280-450). Add two rows, maintaining alphabetical order within the table:

```
| `mcp-tool:hygiene-apply` | mcp-tool | mcp via dashboard | loop-hygiene |
| `mcp-tool:hygiene-scan` | mcp-tool | mcp via dashboard | loop-hygiene |
```

Place between `mcp-tool:get-sync-status` and `mcp-tool:inbox-consume-folder` to maintain alphabetical order.

- [ ] **Step 4: Verify capability exposure parses**

Run: `python -c "import yaml; data = yaml.safe_load(open('config/system/capability_exposure.yaml')); assert 'mcp-tool:hygiene-scan' in data; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md config/system/capability_exposure.yaml
git commit -m "chore(loop-hygiene): register hygiene-{scan,apply} in capability policy

Adds both tools to capability_exposure.yaml (export_to: mcp, owner:
loop-hygiene, preferred_surface: mcp via dashboard) and to the
CLAUDE.md capability policy table (alphabetically positioned).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## C6 — Quality gates and manual verification

### Task 17: Full test suite green + lint

**Files:** None new; this is a quality gate.

- [ ] **Step 1: Run all loop-hygiene tests via auto-loop**

Run: `/auto-test-pytest shared-vault/skills/loop-hygiene/augur/tests/`
Expected: all tests in `test_never_touch.py`, `test_lifecycle_config.py`, `test_hygiene_scan.py`, `test_hygiene_apply.py`, `test_hygiene_e2e.py` pass.

- [ ] **Step 2: Run repository-wide pytest to check for regressions**

Run: `/auto-test-pytest`
Expected: existing tests still pass; no regressions.

- [ ] **Step 3: Run lint**

Run: `/auto-lint`
Expected: clean, or auto-fixed.

If `/auto-lint` reports unresolved findings, fix them in this task; do not move on with debt.

- [ ] **Step 4: Verify MCP server starts**

Run: `python -m src.mcp.augur_core --help 2>&1 | head -20`
Expected: prints help, no ImportError or registration error.

- [ ] **Step 5: Commit any lint-fixes**

```bash
git status
# If files were auto-fixed by lint:
git add -A
git commit -m "chore(loop-hygiene): lint fixes from /auto-lint

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

(If no lint fixes were needed, no commit is necessary for this step.)

---

### Task 18: Manual ritual — real /sweep-stores against Au-docs

**Files:** None new; this is a manual verification step.

This is the moment of truth. The user must do this in a fresh AI client session. The agent's job in THAT session is to use the new command. The plan's job here is to write down the script the user follows.

- [ ] **Step 1: Verify dry-run reports something sensible**

In a fresh Claude Code session (or Codex CLI, or Gemini CLI):

```
/sweep-stores Au-docs/venture-augur/websites
```

Expected: the agent calls `hygiene-scan`, reasons over the output, and presents a proposal listing ~48 stale zips grouped under `guriqo-com-build` and `augur-run-build`, keeping the highest-V member of each.

Inspect the proposal for sanity:
- Does it correctly identify the current?
- Did it skip anything in `never_touch_skipped` (e.g., `.augur-lifecycle.yaml`)?
- Did it include any non-versioned file (`DEPLOYMENT.md`, `RELEASE.md`) in the moves? It should NOT — these are not in the groups.

If the agent misclassifies, capture the dialog and file a rubric-tuning ADR in a follow-up. Do not move on with bad rubric.

- [ ] **Step 2: Apply on a backup copy of the folder**

Make a backup first:

```bash
cp -r Au-docs/venture-augur/websites /tmp/websites-backup-$(date +%s)
```

Then in the AI client session:

```
/sweep-stores Au-docs/venture-augur/websites --apply
```

Expected: the agent re-runs scan, re-presents the proposal, waits for explicit "apply" confirmation, then calls `hygiene-apply` with `dry_run=false`. Inspect:
- 48 (or however many minus current) zips moved into `Au-docs/venture-augur/websites/.archive/`
- `.archive/_manifest.jsonl` exists with one line per archived file
- `.archive/.augur-ignore` exists with content `*\n`
- `Au-docs/.gitignore` contains `.archive/`

- [ ] **Step 3: Verify hiding works**

Open a fresh AI client session (kill the current Claude Code session and start a new one). Ask:

```
List the files in Au-docs/venture-augur/websites/
```

Expected: the agent reports `guriqo-com-V10032.zip`, `augur-run-V10032.zip`, `DEPLOYMENT.md`, `RELEASE.md` (the canonical / non-versioned files). The 48 archived files should NOT appear.

If they DO appear, the `.augur-ignore` mechanism is insufficient for the agent's surface. File a Phase 4 ADR; the MVP is not blocking on a perfect hide but THIS ritual is the empirical answer.

- [ ] **Step 4: Document the result**

Append to the spec's Status section (or create a "Verification Log" section) a short note like:

```
## Verification Log

- 2026-05-11 (or current date): /sweep-stores --apply executed against
  Au-docs/venture-augur/websites. 48 files archived. Fresh-session
  visibility check: <archived files invisible | archived files still
  visible to Claude Code via the {tool name} tool>.
```

Then commit:

```bash
git add docs/superpowers/specs/2026-05-11-loop-hygiene-design.md
git commit -m "docs(loop-hygiene): verification log entry for first apply

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 19: ADR finalization via /adr

**Files:**
- Create: `docs/adrs/ADR-732-loop-hygiene.md` (created by `/adr` slash command, not by hand)

- [ ] **Step 1: Run /adr to create the ADR-732 index**

In a Claude Code session:

```
/adr new loop-hygiene --spec docs/superpowers/specs/2026-05-11-loop-hygiene-design.md --plan docs/superpowers/plans/2026-05-11-loop-hygiene.md --status Accepted --hub adaptive --related ADR-571 ADR-731 ADR-491
```

(Adjust the exact `/adr` argument shape to whatever the current `/adr` command expects — inspect a recent ADR like `ADR-731-memory-synthesis-consolidation.md` for the frontmatter shape and follow that.)

Expected: the `/adr` post-write hook runs, generating:
- `docs/adrs/ADR-732-loop-hygiene.md` (the index file with frontmatter and Decision summary)
- The central JSON `docs/generated/adrs-index.json` is updated
- `docs/generated/adr-index.md` is regenerated
- MEMORY.md "Recent Decisions" section is updated

- [ ] **Step 2: Verify the ADR landed in the central index**

Run: `grep "ADR-732" docs/generated/adrs-index.json docs/generated/adr-index.md`
Expected: both files contain `ADR-732` rows.

- [ ] **Step 3: Final commit**

The `/adr` workflow should commit the ADR plus the regenerated index files automatically. Verify:

Run: `git log --oneline -3`
Expected: top commit references ADR-732 in the standard `adr(...)` pattern.

If `/adr` did not commit, commit manually:

```bash
git add docs/adrs/ADR-732-loop-hygiene.md docs/generated/adrs-index.json docs/generated/adr-index.md MEMORY.md
git commit -m "adr(loop-hygiene): ADR-732 — store-wide artifact retention MVP-v2

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 4: Push (optional, when ready)**

If the workflow calls for it:

```bash
git push origin main
```

Otherwise leave for user-directed push later.

---

## Self-Review

After writing all tasks above, the plan is checked against the spec.

**Spec section coverage:**

| Spec section | Plan tasks covering it |
|---|---|
| §3 Decision summary — slash command + 2 MCP tools | Tasks 14 (MCP), 15 (slash command) |
| §3 — agent-as-classifier, no llm.yaml | Boundary rules + Task 15 rubric explicitly forbids LLM SDK imports in skill |
| §3 — Au-docs only, Au-vault refused | Task 4 (root resolution + refusal) |
| §3 — single .augur-ignore exclusion layer | Task 11 |
| §3 — archive inside source folder | Task 7 (`_compute_archive_destination`) |
| §3 — no per-month, no auto-purge | Out-of-scope; not implemented (correctly) |
| §3 — dry-run default | Task 7 (skeleton dry-run path), Task 14 (MCP impl defaults `dry_run=True`), Task 15 (slash command requires `--apply` flag for destructive) |
| §5.1 Skill layout | Task 1 |
| §5.2 Slash command rubric | Task 15 |
| §5.3 hygiene-scan input/output shape | Tasks 4-6 |
| §5.4 hygiene-apply input/output + atomic os.rename + .dup-<hash> + manifest + .augur-ignore + .gitignore | Tasks 7-11 |
| §5.5 .augur-lifecycle.yaml schema | Task 3 |
| §5.6 .milestones.json schema | Task 3 |
| §6 .augur-ignore + .gitignore | Task 11 |
| §6 Manual verification ritual | Task 18 |
| §7 7 refusal categories (never_touch, symlink, milestone_pinned, cross_filesystem, deploy_root, source_missing, collision_unresolvable) | Tasks 8, 9 — note: "destination collision unresolvable" is structurally rare; the dup-suffix in Task 9 resolves it; no separate test for the unresolvable case |
| §7 Atomicity, manifest rollback | Task 10 |
| §7 Dry-run as first-class mode | Tasks 7 and 14 |
| §7 No "best effort", no silent skips, no audit log | Tasks 8 (every refusal in response), N/A audit log (out of scope per spec §9) |
| §8 Unit tests | Tasks 2, 3, 5, 6, 8, 9, 10, 11 |
| §8 Golden fixtures | Task 12 |
| §8 E2E test | Task 13 |
| §8 No LLM eval in MVP | Boundary rules forbid LLM SDK imports |
| §8 Quality gate before merge | Tasks 17, 18 |
| §9 Out of scope items | Confirmed not implemented (auto-loops, dashboard, Au-vault, multi-layer exclusions, verification probes, llm.yaml, milestone-tag command, undo, SQLite, per-month, audit log) |

No gaps detected.

**Placeholder scan:** searched for "TBD", "TODO", "implement later", "add appropriate", "similar to Task N". None found in the plan body. (Note: the `lifecycle_schema.yaml` content in Task 3 is documentation describing the schema, not a placeholder.)

**Type consistency:**
- `is_never_touch(path: Path) -> bool` — used consistently in Tasks 2, 5, 8.
- `LifecycleConfig` dataclass — used in Tasks 3, 6, 8.
- `MilestonePin` dataclass — used in Tasks 3, 6, 8.
- `HygieneScanError` — Tasks 4, 5, 6.
- `HygieneApplyError` — Tasks 7, 8, 9, 10, 11.
- `hygiene_scan(path: str) -> dict[str, Any]` — Tasks 4-6.
- `hygiene_apply(root, moves, dry_run) -> dict[str, Any]` — Tasks 7-11.
- `_compute_archive_destination` — defined in Task 7, unchanged thereafter.
- `_resolve_destination`, `_append_manifest`, `_ensure_augur_ignore`, `_ensure_gitignore_entry` — defined once each, never renamed.

All identifiers stable across tasks.

---

## Execution

Plan complete and saved to `docs/superpowers/plans/2026-05-11-loop-hygiene.md`. Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints.

Which approach?
