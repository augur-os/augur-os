# Multi-Brain Augur — Stage 1 (Registry & Aliasing) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce a typed brain registry at `~/.augur/brains.yaml`, auto-generated on first read from today's `vault.yaml` + detected `shared-vault/`, plus a `.augur/` mount writer that prepares each registered brain's directory for AI-client scoping. Zero data movement, zero user-visible behavior change.

**Architecture:** Five flat modules in `src/lib/` (models → I/O → bootstrap → top-level accessor → mount writer) plus a small extension to `src/config/paths.py`. Stage 1 is read-mostly: today's `get_vault_dir()` / `get_shared_vault_dir()` keep returning the same paths via the existing code, AND a new `get_brain_dir(brain_id)` reads the same paths through the registry. No call sites change in Stage 1.

**Tech Stack:** Python 3.11+, `uv` for env management, `pytest` via `/auto-test-pytest` per CLAUDE.md rule 19, PyYAML (already a project dep), dataclasses, type hints.

**Spec reference:** `docs/superpowers/specs/2026-05-16-multi-brain-design.md` — §Brain registry, §Migration stage 1.

**Out of scope for Stage 1:** the `--to <brain-id>` flag, generalized propagation, new brain types (`/brain init`), dashboard federation, memory shared-symlink. Those land in Stage 2 and Stage 3.

---

## File Structure (locked before implementation)

**Create:**
- `src/lib/brain_registry_models.py` — typed dataclasses for `Brain`, `BrainRegistry`, `GitConfig`, `PropagationPolicy`, plus `BrainType` / `GitArrangement` enums. Validation logic lives in `__post_init__`.
- `src/lib/brain_registry_io.py` — `load_registry(path)` and `save_registry(registry, path)`. Pure parsing + serialization; no I/O beyond reading/writing the given path.
- `src/lib/brain_registry_bootstrap.py` — `build_default_registry()`. Reads `config/system/vault.yaml` + computes `shared-vault/` path; returns a `BrainRegistry` with `personal` + `team-augur` entries that reproduce today's behavior.
- `src/lib/brain_registry.py` — `get_registry()`. Top-level accessor: reads `~/.augur/brains.yaml` if exists; otherwise runs bootstrap and writes the file. Cached per process.
- `src/lib/brain_mount.py` — `ensure_mount(brain)`. Writes `<brain.data_root>/.augur/BRAIN.yaml` with the brain's identity (id, type, registry-fingerprint). Per-client harness files (CLAUDE.md, AGENTS.md, …) are NOT generated here — Stage 1 mounts are minimal stubs. Per-client generators land in Stage 2.
- `tests/unit/test_brain_registry_models.py`
- `tests/unit/test_brain_registry_io.py`
- `tests/unit/test_brain_registry_bootstrap.py`
- `tests/unit/test_brain_registry.py`
- `tests/unit/test_brain_mount.py`
- `tests/integration/test_brain_registry_stage1.py`

**Modify:**
- `src/config/paths.py` — add `get_augur_state_dir()` (returns `~/.augur/`), `get_brain_registry_path()` (returns `~/.augur/brains.yaml`), `get_brain_dir(brain_id)`, `list_brain_ids()`. Do not modify any existing function.
- `shared-vault/skills/ai/scripts/sync_agents.py` (or whichever file owns the dev-sync mount pass) — after existing sync, call `ensure_mount(brain)` for each registered brain. Located via Task 7's exploration step.
- `tests/config/test_paths.py` (or create if absent) — coverage for the new helpers.

**Why this split:** every file has one responsibility; tests live next to the unit they cover; the bootstrap module is pure (no env reads at import time) so tests can drive it deterministically; `paths.py` only gets thin accessors that delegate to `brain_registry.py`, preserving rule 3 (use path helpers).

---

## Task 1: Brain registry data model

**Files:**
- Create: `src/lib/brain_registry_models.py`
- Test: `tests/unit/test_brain_registry_models.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_brain_registry_models.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from src.lib.brain_registry_models import (
    Brain,
    BrainRegistry,
    BrainType,
    GitArrangement,
    GitConfig,
    PropagationPolicy,
)


def _git_standalone() -> GitConfig:
    return GitConfig(arrangement=GitArrangement.STANDALONE)


def test_brain_minimal_required_fields():
    brain = Brain(
        id="personal",
        type=BrainType.PERSONAL,
        data_root=Path("/Users/x/Brains/personal"),
        git=_git_standalone(),
    )
    assert brain.id == "personal"
    assert brain.type is BrainType.PERSONAL
    assert brain.write_policy == "free"
    assert brain.propagation == PropagationPolicy()
    assert brain.auto_activate_cwd_under == ()


def test_brain_rejects_relative_data_root():
    with pytest.raises(ValueError, match="data_root must be absolute"):
        Brain(
            id="x",
            type=BrainType.PERSONAL,
            data_root=Path("Brains/personal"),
            git=GitConfig(arrangement=GitArrangement.UNTRACKED),
        )


def test_brain_rejects_unknown_write_policy():
    with pytest.raises(ValueError, match="unknown write_policy"):
        Brain(
            id="x",
            type=BrainType.TEAM,
            data_root=Path("/x"),
            git=GitConfig(arrangement=GitArrangement.UNTRACKED),
            write_policy="bogus",
        )


def test_git_config_bundled_requires_host_repo():
    with pytest.raises(ValueError, match="bundled arrangement requires host_repo"):
        GitConfig(arrangement=GitArrangement.BUNDLED)


def test_git_config_standalone_rejects_host_repo():
    with pytest.raises(ValueError, match="standalone arrangement must not set host_repo"):
        GitConfig(arrangement=GitArrangement.STANDALONE, host_repo=Path("/x"))


def test_git_config_host_repo_must_be_absolute():
    with pytest.raises(ValueError, match="host_repo must be an absolute path"):
        GitConfig(arrangement=GitArrangement.BUNDLED, host_repo=Path("relative/path"))


def test_registry_lookup_by_id():
    brain = Brain(
        id="personal",
        type=BrainType.PERSONAL,
        data_root=Path("/x"),
        git=GitConfig(arrangement=GitArrangement.UNTRACKED),
    )
    registry = BrainRegistry(version=1, brains={"personal": brain})
    assert registry.get("personal") is brain
    assert registry.get("missing") is None
    assert registry.ids() == ["personal"]


def test_registry_rejects_id_mismatch():
    brain = Brain(
        id="personal",
        type=BrainType.PERSONAL,
        data_root=Path("/x"),
        git=GitConfig(arrangement=GitArrangement.UNTRACKED),
    )
    with pytest.raises(ValueError, match="registry key 'wrong-id' does not match brain id 'personal'"):
        BrainRegistry(version=1, brains={"wrong-id": brain})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/auto-test-pytest tests/unit/test_brain_registry_models.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.lib.brain_registry_models'`

- [ ] **Step 3: Write the minimal implementation**

Create `src/lib/brain_registry_models.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class BrainType(str, Enum):
    PERSONAL = "personal"
    TEAM = "team"
    WORK = "work"
    PROJECT = "project"


class GitArrangement(str, Enum):
    STANDALONE = "standalone"
    BUNDLED = "bundled"
    UNTRACKED = "untracked"


@dataclass(frozen=True)
class GitConfig:
    arrangement: GitArrangement
    remote: Optional[str] = None
    branch: str = "main"
    auto_commit: bool = True
    auto_push: bool = True
    host_repo: Optional[Path] = None

    def __post_init__(self) -> None:
        if self.arrangement is GitArrangement.BUNDLED and self.host_repo is None:
            raise ValueError("bundled arrangement requires host_repo")
        if self.arrangement is GitArrangement.STANDALONE and self.host_repo is not None:
            raise ValueError("standalone arrangement must not set host_repo")
        if self.host_repo is not None and not self.host_repo.is_absolute():
            raise ValueError("host_repo must be an absolute path")


@dataclass(frozen=True)
class PropagationPolicy:
    allow_from: tuple[str, ...] = ()
    allow_to: tuple[str, ...] = ()


_VALID_WRITE_POLICIES = frozenset({"free", "packets_only"})


@dataclass(frozen=True)
class Brain:
    id: str
    type: BrainType
    data_root: Path
    git: GitConfig
    description: Optional[str] = None
    write_policy: str = "free"
    auto_activate_cwd_under: tuple[Path, ...] = ()
    propagation: PropagationPolicy = field(default_factory=PropagationPolicy)
    skills_allow: Optional[tuple[str, ...]] = None
    skills_deny: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.data_root.is_absolute():
            raise ValueError(f"data_root must be absolute: {self.data_root}")
        if self.write_policy not in _VALID_WRITE_POLICIES:
            raise ValueError(f"unknown write_policy: {self.write_policy}")
        for path in self.auto_activate_cwd_under:
            if not path.is_absolute():
                raise ValueError(f"auto_activate_cwd_under path must be absolute: {path}")


@dataclass(frozen=True)
class BrainRegistry:
    version: int
    brains: dict[str, Brain]

    def __post_init__(self) -> None:
        for key, brain in self.brains.items():
            if key != brain.id:
                raise ValueError(
                    f"registry key '{key}' does not match brain id '{brain.id}'"
                )

    def get(self, brain_id: str) -> Optional[Brain]:
        return self.brains.get(brain_id)

    def ids(self) -> list[str]:
        return list(self.brains.keys())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/auto-test-pytest tests/unit/test_brain_registry_models.py`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add src/lib/brain_registry_models.py tests/unit/test_brain_registry_models.py
git commit -m "$(cat <<'EOF'
feat(brain-registry): data model for Brain, BrainRegistry, GitConfig (ADR-754 stage 1)

Adds frozen dataclasses with __post_init__ validation for the multi-brain
registry. No call sites use these yet; subsequent commits wire I/O,
bootstrap, accessor, and mount writer.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Brain registry YAML I/O

**Files:**
- Create: `src/lib/brain_registry_io.py`
- Test: `tests/unit/test_brain_registry_io.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_brain_registry_io.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from src.lib.brain_registry_io import load_registry, save_registry
from src.lib.brain_registry_models import (
    Brain,
    BrainRegistry,
    BrainType,
    GitArrangement,
    GitConfig,
    PropagationPolicy,
)


def _sample_registry() -> BrainRegistry:
    personal = Brain(
        id="personal",
        type=BrainType.PERSONAL,
        data_root=Path("/Users/x/Projects/Au-vault"),
        git=GitConfig(
            arrangement=GitArrangement.STANDALONE,
            remote="https://github.com/x/au-vault.git",
            branch="main",
            auto_commit=True,
            auto_push=True,
        ),
    )
    team = Brain(
        id="team-augur",
        type=BrainType.TEAM,
        data_root=Path("/Users/x/Projects/Augur/shared-vault"),
        git=GitConfig(
            arrangement=GitArrangement.BUNDLED,
            host_repo=Path("/Users/x/Projects/Augur"),
        ),
        write_policy="packets_only",
    )
    return BrainRegistry(version=1, brains={"personal": personal, "team-augur": team})


def test_roundtrip_preserves_registry(tmp_path: Path):
    target = tmp_path / "brains.yaml"
    original = _sample_registry()
    save_registry(original, target)
    loaded = load_registry(target)
    assert loaded == original


def test_load_missing_file_raises_filenotfound(tmp_path: Path):
    target = tmp_path / "missing.yaml"
    with pytest.raises(FileNotFoundError):
        load_registry(target)


def test_save_creates_parent_directories(tmp_path: Path):
    target = tmp_path / "nested" / "dir" / "brains.yaml"
    save_registry(_sample_registry(), target)
    assert target.is_file()


def test_load_rejects_wrong_version(tmp_path: Path):
    target = tmp_path / "brains.yaml"
    target.write_text("version: 99\nbrains: {}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported registry version: 99"):
        load_registry(target)


def test_load_rejects_unknown_brain_type(tmp_path: Path):
    target = tmp_path / "brains.yaml"
    target.write_text(
        "version: 1\n"
        "brains:\n"
        "  x:\n"
        "    type: bogus\n"
        "    data_root: /tmp/x\n"
        "    git:\n"
        "      arrangement: untracked\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="invalid brain type"):
        load_registry(target)


def test_propagation_policy_roundtrips(tmp_path: Path):
    brain = Brain(
        id="work-intel",
        type=BrainType.WORK,
        data_root=Path("/Users/x/Brains/work-intel"),
        git=GitConfig(arrangement=GitArrangement.UNTRACKED),
        propagation=PropagationPolicy(
            allow_from=("personal",),
            allow_to=("personal",),
        ),
    )
    original = BrainRegistry(version=1, brains={"work-intel": brain})
    target = tmp_path / "brains.yaml"
    save_registry(original, target)
    loaded = load_registry(target)
    assert loaded.get("work-intel").propagation == PropagationPolicy(
        allow_from=("personal",), allow_to=("personal",)
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/auto-test-pytest tests/unit/test_brain_registry_io.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.lib.brain_registry_io'`

- [ ] **Step 3: Write the minimal implementation**

Create `src/lib/brain_registry_io.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.lib.brain_registry_models import (
    Brain,
    BrainRegistry,
    BrainType,
    GitArrangement,
    GitConfig,
    PropagationPolicy,
)

_SUPPORTED_VERSIONS = frozenset({1})


def load_registry(path: Path) -> BrainRegistry:
    if not path.is_file():
        raise FileNotFoundError(f"brain registry not found: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return _registry_from_dict(raw)


def save_registry(registry: BrainRegistry, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = _registry_to_dict(registry)
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )


def _registry_from_dict(raw: dict[str, Any]) -> BrainRegistry:
    version = raw.get("version")
    if version not in _SUPPORTED_VERSIONS:
        raise ValueError(f"unsupported registry version: {version}")
    brains_raw = raw.get("brains") or {}
    brains: dict[str, Brain] = {}
    for brain_id, body in brains_raw.items():
        brains[brain_id] = _brain_from_dict(brain_id, body)
    return BrainRegistry(version=version, brains=brains)


def _brain_from_dict(brain_id: str, body: dict[str, Any]) -> Brain:
    try:
        brain_type = BrainType(body["type"])
    except ValueError as exc:
        raise ValueError(f"invalid brain type for '{brain_id}': {body.get('type')}") from exc

    git = _git_from_dict(body.get("git") or {})
    propagation_raw = body.get("propagation") or {}
    propagation = PropagationPolicy(
        allow_from=tuple(propagation_raw.get("allow_from") or ()),
        allow_to=tuple(propagation_raw.get("allow_to") or ()),
    )
    cwd_under = tuple(Path(p) for p in (body.get("auto_activate_when", {}).get("cwd_under") or ()))
    skills_allow_raw = body.get("skills_allow")
    skills_allow = tuple(skills_allow_raw) if skills_allow_raw is not None else None
    return Brain(
        id=brain_id,
        type=brain_type,
        data_root=Path(body["data_root"]),
        git=git,
        description=body.get("description"),
        write_policy=body.get("write_policy", "free"),
        auto_activate_cwd_under=cwd_under,
        propagation=propagation,
        skills_allow=skills_allow,
        skills_deny=tuple(body.get("skills_deny") or ()),
    )


def _git_from_dict(body: dict[str, Any]) -> GitConfig:
    try:
        arrangement = GitArrangement(body.get("arrangement", "untracked"))
    except ValueError as exc:
        raise ValueError(f"invalid git arrangement: {body.get('arrangement')}") from exc
    host_repo = body.get("host_repo")
    return GitConfig(
        arrangement=arrangement,
        remote=body.get("remote"),
        branch=body.get("branch", "main"),
        auto_commit=bool(body.get("auto_commit", True)),
        auto_push=bool(body.get("auto_push", True)),
        host_repo=Path(host_repo) if host_repo else None,
    )


def _registry_to_dict(registry: BrainRegistry) -> dict[str, Any]:
    return {
        "version": registry.version,
        "brains": {brain_id: _brain_to_dict(brain) for brain_id, brain in registry.brains.items()},
    }


def _brain_to_dict(brain: Brain) -> dict[str, Any]:
    out: dict[str, Any] = {
        "type": brain.type.value,
        "data_root": str(brain.data_root),
        "git": _git_to_dict(brain.git),
        "write_policy": brain.write_policy,
    }
    if brain.description is not None:
        out["description"] = brain.description
    if brain.auto_activate_cwd_under:
        out["auto_activate_when"] = {
            "cwd_under": [str(p) for p in brain.auto_activate_cwd_under]
        }
    if brain.propagation.allow_from or brain.propagation.allow_to:
        out["propagation"] = {
            "allow_from": list(brain.propagation.allow_from),
            "allow_to": list(brain.propagation.allow_to),
        }
    if brain.skills_allow is not None:
        out["skills_allow"] = list(brain.skills_allow)
    if brain.skills_deny:
        out["skills_deny"] = list(brain.skills_deny)
    return out


def _git_to_dict(git: GitConfig) -> dict[str, Any]:
    out: dict[str, Any] = {
        "arrangement": git.arrangement.value,
        "branch": git.branch,
        "auto_commit": git.auto_commit,
        "auto_push": git.auto_push,
    }
    if git.remote is not None:
        out["remote"] = git.remote
    if git.host_repo is not None:
        out["host_repo"] = str(git.host_repo)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/auto-test-pytest tests/unit/test_brain_registry_io.py`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/lib/brain_registry_io.py tests/unit/test_brain_registry_io.py
git commit -m "$(cat <<'EOF'
feat(brain-registry): YAML load/save with schema validation (ADR-754 stage 1)

Roundtrip-stable serialization for the brain registry. Version-gated
(only v1 supported); rejects unknown brain types and git arrangements at
load time so corrupt files surface immediately rather than at first use.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Default registry bootstrap from today's config

**Files:**
- Create: `src/lib/brain_registry_bootstrap.py`
- Test: `tests/unit/test_brain_registry_bootstrap.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_brain_registry_bootstrap.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from src.lib.brain_registry_bootstrap import build_default_registry
from src.lib.brain_registry_models import BrainType, GitArrangement


def _write_vault_yaml(tmp_path: Path, vault_path: str, remote: str) -> Path:
    config_dir = tmp_path / "config" / "system"
    config_dir.mkdir(parents=True)
    (config_dir / "vault.yaml").write_text(
        "vault:\n"
        f"  path: {vault_path}\n"
        "  git:\n"
        "    auto_commit: true\n"
        "    auto_push: true\n"
        "    remote: origin\n"
        "    branch: main\n"
        f"  remote: \"{remote}\"\n",
        encoding="utf-8",
    )
    return tmp_path


def test_bootstrap_produces_personal_and_team_augur(tmp_path: Path):
    project_root = _write_vault_yaml(
        tmp_path, "~/Projects/Au-vault", "https://github.com/x/au-vault.git"
    )
    (project_root / "shared-vault").mkdir()

    registry = build_default_registry(project_root=project_root)

    assert registry.version == 1
    assert sorted(registry.ids()) == ["personal", "team-augur"]

    personal = registry.get("personal")
    assert personal is not None
    assert personal.type is BrainType.PERSONAL
    assert personal.data_root == Path("~/Projects/Au-vault").expanduser()
    assert personal.git.arrangement is GitArrangement.STANDALONE
    assert personal.git.remote == "https://github.com/x/au-vault.git"
    assert personal.git.branch == "main"

    team = registry.get("team-augur")
    assert team is not None
    assert team.type is BrainType.TEAM
    assert team.data_root == (project_root / "shared-vault").resolve()
    assert team.git.arrangement is GitArrangement.BUNDLED
    assert team.git.host_repo == project_root.resolve()
    assert team.write_policy == "packets_only"


def test_bootstrap_omits_team_when_shared_vault_missing(tmp_path: Path):
    project_root = _write_vault_yaml(
        tmp_path, "~/Projects/Au-vault", "https://example.com/x.git"
    )
    # no shared-vault directory created

    registry = build_default_registry(project_root=project_root)

    assert registry.ids() == ["personal"]


def test_bootstrap_raises_when_vault_yaml_missing(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="vault.yaml not found"):
        build_default_registry(project_root=tmp_path)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/auto-test-pytest tests/unit/test_brain_registry_bootstrap.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.lib.brain_registry_bootstrap'`

- [ ] **Step 3: Write the minimal implementation**

Create `src/lib/brain_registry_bootstrap.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.lib.brain_registry_models import (
    Brain,
    BrainRegistry,
    BrainType,
    GitArrangement,
    GitConfig,
)


def build_default_registry(project_root: Path) -> BrainRegistry:
    """Produce a registry that reproduces today's two-vault behavior.

    Reads ``project_root/config/system/vault.yaml`` for the personal brain.
    Detects ``project_root/shared-vault/`` to register team-augur (bundled).
    """
    brains: dict[str, Brain] = {}
    personal = _personal_from_vault_yaml(project_root)
    brains[personal.id] = personal

    shared_root = (project_root / "shared-vault").resolve()
    if shared_root.is_dir():
        team = Brain(
            id="team-augur",
            type=BrainType.TEAM,
            data_root=shared_root,
            git=GitConfig(
                arrangement=GitArrangement.BUNDLED,
                host_repo=project_root.resolve(),
            ),
            write_policy="packets_only",
            description="Augur OSS team brain (bundled with harness repo)",
        )
        brains[team.id] = team

    return BrainRegistry(version=1, brains=brains)


def _personal_from_vault_yaml(project_root: Path) -> Brain:
    vault_yaml = project_root / "config" / "system" / "vault.yaml"
    if not vault_yaml.is_file():
        raise FileNotFoundError(f"vault.yaml not found: {vault_yaml}")
    data: dict[str, Any] = yaml.safe_load(vault_yaml.read_text(encoding="utf-8")) or {}
    vault_block: dict[str, Any] = data.get("vault") or {}

    raw_path = vault_block.get("path")
    if not raw_path:
        raise ValueError(f"vault.yaml missing vault.path: {vault_yaml}")
    data_root = Path(str(raw_path)).expanduser()

    git_block: dict[str, Any] = vault_block.get("git") or {}
    git = GitConfig(
        arrangement=GitArrangement.STANDALONE,
        remote=vault_block.get("remote"),
        branch=str(git_block.get("branch") or "main"),
        auto_commit=bool(git_block.get("auto_commit", True)),
        auto_push=bool(git_block.get("auto_push", True)),
    )
    return Brain(
        id="personal",
        type=BrainType.PERSONAL,
        data_root=data_root,
        git=git,
        description="Personal brain (migrated from vault.yaml)",
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/auto-test-pytest tests/unit/test_brain_registry_bootstrap.py`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/lib/brain_registry_bootstrap.py tests/unit/test_brain_registry_bootstrap.py
git commit -m "$(cat <<'EOF'
feat(brain-registry): bootstrap default registry from vault.yaml + shared-vault (ADR-754 stage 1)

Generates the initial registry from today's two-vault config so first
boot in stage 1 produces personal + team-augur entries that reproduce
existing get_vault_dir / get_shared_vault_dir paths exactly.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Top-level registry accessor with auto-bootstrap

**Files:**
- Create: `src/lib/brain_registry.py`
- Test: `tests/unit/test_brain_registry.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_brain_registry.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from src.lib.brain_registry import clear_cache, get_registry
from src.lib.brain_registry_io import save_registry, load_registry
from src.lib.brain_registry_models import (
    Brain,
    BrainRegistry,
    BrainType,
    GitArrangement,
    GitConfig,
)


def _write_vault_yaml(project_root: Path) -> None:
    config_dir = project_root / "config" / "system"
    config_dir.mkdir(parents=True)
    (config_dir / "vault.yaml").write_text(
        "vault:\n"
        "  path: ~/Projects/Au-vault\n"
        "  git:\n"
        "    auto_commit: true\n"
        "    auto_push: true\n"
        "    remote: origin\n"
        "    branch: main\n"
        "  remote: \"https://example.com/x.git\"\n",
        encoding="utf-8",
    )


@pytest.fixture(autouse=True)
def _reset_cache():
    clear_cache()
    yield
    clear_cache()


def test_get_registry_bootstraps_when_missing(tmp_path: Path):
    registry_path = tmp_path / ".augur" / "brains.yaml"
    _write_vault_yaml(tmp_path)
    (tmp_path / "shared-vault").mkdir()

    registry = get_registry(registry_path=registry_path, project_root=tmp_path)

    assert registry_path.is_file()
    assert sorted(registry.ids()) == ["personal", "team-augur"]


def test_get_registry_reads_existing_file(tmp_path: Path):
    registry_path = tmp_path / ".augur" / "brains.yaml"
    brain = Brain(
        id="custom",
        type=BrainType.WORK,
        data_root=Path("/tmp/work"),
        git=GitConfig(arrangement=GitArrangement.UNTRACKED),
    )
    save_registry(BrainRegistry(version=1, brains={"custom": brain}), registry_path)

    registry = get_registry(registry_path=registry_path, project_root=tmp_path)

    assert registry.ids() == ["custom"]
    # Bootstrap was not triggered (vault.yaml absent and we didn't fail).


def test_get_registry_caches_within_process(tmp_path: Path):
    registry_path = tmp_path / ".augur" / "brains.yaml"
    _write_vault_yaml(tmp_path)
    (tmp_path / "shared-vault").mkdir()

    first = get_registry(registry_path=registry_path, project_root=tmp_path)
    # Mutate the file on disk; cached call should NOT pick it up.
    registry_path.write_text("version: 1\nbrains: {}\n", encoding="utf-8")
    second = get_registry(registry_path=registry_path, project_root=tmp_path)
    assert first is second
    # After clear, we re-read.
    clear_cache()
    third = get_registry(registry_path=registry_path, project_root=tmp_path)
    assert third.ids() == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/auto-test-pytest tests/unit/test_brain_registry.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.lib.brain_registry'`

- [ ] **Step 3: Write the minimal implementation**

Create `src/lib/brain_registry.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Optional

from src.lib.brain_registry_bootstrap import build_default_registry
from src.lib.brain_registry_io import load_registry, save_registry
from src.lib.brain_registry_models import BrainRegistry

_cache: dict[Path, BrainRegistry] = {}


def get_registry(
    *,
    registry_path: Optional[Path] = None,
    project_root: Optional[Path] = None,
) -> BrainRegistry:
    """Return the active brain registry, bootstrapping it on first read."""
    resolved_path = _resolve_registry_path(registry_path)
    cached = _cache.get(resolved_path)
    if cached is not None:
        return cached
    if resolved_path.is_file():
        registry = load_registry(resolved_path)
    else:
        resolved_project_root = _resolve_project_root(project_root)
        registry = build_default_registry(project_root=resolved_project_root)
        save_registry(registry, resolved_path)
    _cache[resolved_path] = registry
    return registry


def clear_cache() -> None:
    """Reset the per-process cache. Test-only; do not use in production code."""
    _cache.clear()


def _resolve_registry_path(explicit: Optional[Path]) -> Path:
    if explicit is not None:
        return explicit
    # Late import to avoid a cycle with src.config.paths during paths' own initialization.
    from src.config.paths import get_brain_registry_path

    return get_brain_registry_path()


def _resolve_project_root(explicit: Optional[Path]) -> Path:
    if explicit is not None:
        return explicit
    from src.config.paths import get_project_root

    return get_project_root()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/auto-test-pytest tests/unit/test_brain_registry.py`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/lib/brain_registry.py tests/unit/test_brain_registry.py
git commit -m "$(cat <<'EOF'
feat(brain-registry): top-level accessor with auto-bootstrap and per-process cache (ADR-754 stage 1)

get_registry() returns the active registry, lazily creating ~/.augur/brains.yaml
from today's vault.yaml on first read. clear_cache() is test-only.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: paths.py helpers for brain access

**Files:**
- Modify: `src/config/paths.py`
- Test: `tests/config/test_paths.py` (modify if exists, else create)

- [ ] **Step 1: Locate the existing paths module helpers**

Run: `grep -n "^def " src/config/paths.py | head -30`
Expected: list of existing helpers (`get_project_root`, `get_vault_dir`, `get_shared_vault_dir`, etc.).

- [ ] **Step 2: Write the failing test**

Create or extend `tests/config/test_paths.py` (if the file exists, append; if not, create with full content below):

```python
from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.config.paths import (
    get_augur_state_dir,
    get_brain_dir,
    get_brain_registry_path,
    list_brain_ids,
)
from src.lib.brain_registry import clear_cache
from src.lib.brain_registry_io import save_registry
from src.lib.brain_registry_models import (
    Brain,
    BrainRegistry,
    BrainType,
    GitArrangement,
    GitConfig,
)


@pytest.fixture
def isolated_state_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("AUGUR_STATE_DIR", str(tmp_path / ".augur"))
    clear_cache()
    yield tmp_path / ".augur"
    clear_cache()


def test_get_augur_state_dir_honors_env(isolated_state_dir: Path):
    assert get_augur_state_dir() == isolated_state_dir


def test_get_brain_registry_path_under_state_dir(isolated_state_dir: Path):
    assert get_brain_registry_path() == isolated_state_dir / "brains.yaml"


def test_get_brain_dir_returns_data_root(isolated_state_dir: Path):
    brain = Brain(
        id="personal",
        type=BrainType.PERSONAL,
        data_root=Path("/tmp/test-personal"),
        git=GitConfig(arrangement=GitArrangement.UNTRACKED),
    )
    save_registry(
        BrainRegistry(version=1, brains={"personal": brain}),
        isolated_state_dir / "brains.yaml",
    )
    clear_cache()

    assert get_brain_dir("personal") == Path("/tmp/test-personal")


def test_get_brain_dir_raises_for_missing(isolated_state_dir: Path):
    save_registry(
        BrainRegistry(version=1, brains={}),
        isolated_state_dir / "brains.yaml",
    )
    clear_cache()

    with pytest.raises(KeyError, match="missing"):
        get_brain_dir("missing")


def test_list_brain_ids_returns_registry_keys(isolated_state_dir: Path):
    brain_a = Brain(
        id="a", type=BrainType.PERSONAL, data_root=Path("/a"),
        git=GitConfig(arrangement=GitArrangement.UNTRACKED),
    )
    brain_b = Brain(
        id="b", type=BrainType.TEAM, data_root=Path("/b"),
        git=GitConfig(arrangement=GitArrangement.UNTRACKED),
    )
    save_registry(
        BrainRegistry(version=1, brains={"a": brain_a, "b": brain_b}),
        isolated_state_dir / "brains.yaml",
    )
    clear_cache()

    assert sorted(list_brain_ids()) == ["a", "b"]
```

- [ ] **Step 3: Run test to verify it fails**

Run: `/auto-test-pytest tests/config/test_paths.py`
Expected: FAIL with `ImportError: cannot import name 'get_brain_dir' from 'src.config.paths'`

- [ ] **Step 4: Add the helpers to paths.py**

Open `src/config/paths.py` and append (do not modify existing functions):

```python
def get_augur_state_dir() -> Path:
    """Return the per-user Augur state directory (`~/.augur/` by default).

    Honors AUGUR_STATE_DIR env override for tests.
    """
    override = _env_path("AUGUR_STATE_DIR")
    if override:
        return override
    return Path.home() / ".augur"


def get_brain_registry_path() -> Path:
    """Return the path to `brains.yaml` inside the Augur state directory."""
    return get_augur_state_dir() / "brains.yaml"


def get_brain_dir(brain_id: str) -> Path:
    """Return the data_root for the given brain id.

    Raises KeyError if the brain is not registered.
    """
    from src.lib.brain_registry import get_registry

    registry = get_registry()
    brain = registry.get(brain_id)
    if brain is None:
        raise KeyError(f"brain not registered: {brain_id}")
    return brain.data_root


def list_brain_ids() -> list[str]:
    """Return all registered brain ids."""
    from src.lib.brain_registry import get_registry

    return get_registry().ids()
```

**Important:** these are appended at the end of `paths.py`. The lazy `from src.lib.brain_registry import get_registry` import inside each function avoids a top-level cycle (the registry module imports `get_brain_registry_path` and `get_project_root` from `paths`).

- [ ] **Step 5: Run test to verify it passes**

Run: `/auto-test-pytest tests/config/test_paths.py`
Expected: 5 passed (plus any pre-existing test_paths tests continue to pass).

- [ ] **Step 6: Sanity check — existing helpers still work**

Run: `/auto-test-pytest tests/unit/test_vault_promotion.py tests/test_vault.py`
Expected: all green; no behavioral regression in `get_vault_dir` / `get_shared_vault_dir`.

- [ ] **Step 7: Commit**

```bash
git add src/config/paths.py tests/config/test_paths.py
git commit -m "$(cat <<'EOF'
feat(paths): add get_brain_dir, list_brain_ids, get_brain_registry_path (ADR-754 stage 1)

Thin accessors that delegate to src.lib.brain_registry. No existing
helpers are modified; get_vault_dir / get_shared_vault_dir still return
the same paths as before. AUGUR_STATE_DIR env honored for test isolation.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Brain mount writer (data layer)

**Files:**
- Create: `src/lib/brain_mount.py`
- Test: `tests/unit/test_brain_mount.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_brain_mount.py`:

```python
from __future__ import annotations

from pathlib import Path

import yaml

from src.lib.brain_mount import ensure_mount, mount_dir_for_brain
from src.lib.brain_registry_models import (
    Brain,
    BrainType,
    GitArrangement,
    GitConfig,
)


def _brain(tmp_path: Path, brain_id: str = "personal", brain_type: BrainType = BrainType.PERSONAL) -> Brain:
    data_root = tmp_path / brain_id
    data_root.mkdir(parents=True, exist_ok=True)
    return Brain(
        id=brain_id,
        type=brain_type,
        data_root=data_root,
        git=GitConfig(arrangement=GitArrangement.UNTRACKED),
    )


def test_ensure_mount_creates_augur_subdir(tmp_path: Path):
    brain = _brain(tmp_path)
    result = ensure_mount(brain)
    assert result == brain.data_root / ".augur"
    assert result.is_dir()


def test_ensure_mount_writes_brain_yaml(tmp_path: Path):
    brain = _brain(tmp_path, "team-augur", BrainType.TEAM)
    mount = ensure_mount(brain)
    brain_yaml = mount / "BRAIN.yaml"
    assert brain_yaml.is_file()
    parsed = yaml.safe_load(brain_yaml.read_text(encoding="utf-8"))
    assert parsed["id"] == "team-augur"
    assert parsed["type"] == "team"
    assert parsed["data_root"] == str(brain.data_root)


def test_ensure_mount_is_idempotent(tmp_path: Path):
    brain = _brain(tmp_path)
    first = ensure_mount(brain)
    (first / "marker.txt").write_text("preserved", encoding="utf-8")
    second = ensure_mount(brain)
    assert first == second
    assert (second / "marker.txt").read_text(encoding="utf-8") == "preserved"


def test_ensure_mount_updates_brain_yaml_when_brain_changes(tmp_path: Path):
    brain = _brain(tmp_path, "personal", BrainType.PERSONAL)
    ensure_mount(brain)
    # Simulate type change (would not happen in practice, but covers refresh).
    rebadged = Brain(
        id=brain.id,
        type=BrainType.WORK,
        data_root=brain.data_root,
        git=brain.git,
    )
    ensure_mount(rebadged)
    parsed = yaml.safe_load((brain.data_root / ".augur" / "BRAIN.yaml").read_text(encoding="utf-8"))
    assert parsed["type"] == "work"


def test_mount_dir_for_brain(tmp_path: Path):
    brain = _brain(tmp_path)
    assert mount_dir_for_brain(brain) == brain.data_root / ".augur"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/auto-test-pytest tests/unit/test_brain_mount.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.lib.brain_mount'`

- [ ] **Step 3: Write the minimal implementation**

Create `src/lib/brain_mount.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.lib.brain_registry_models import Brain

_MOUNT_SUBDIR = ".augur"
_BRAIN_MANIFEST = "BRAIN.yaml"


def mount_dir_for_brain(brain: Brain) -> Path:
    """Return where the brain's .augur/ mount lives."""
    return brain.data_root / _MOUNT_SUBDIR


def ensure_mount(brain: Brain) -> Path:
    """Create or refresh the brain's .augur/ mount.

    Stage 1 mounts contain only BRAIN.yaml (brain identity). Per-client
    harness files (CLAUDE.md, AGENTS.md, GEMINI.md, mcp.json) are generated
    by sync adapters in stage 2.
    """
    mount = mount_dir_for_brain(brain)
    mount.mkdir(parents=True, exist_ok=True)
    manifest = mount / _BRAIN_MANIFEST
    manifest.write_text(
        yaml.safe_dump(_manifest_body(brain), sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    return mount


def _manifest_body(brain: Brain) -> dict[str, Any]:
    return {
        "id": brain.id,
        "type": brain.type.value,
        "data_root": str(brain.data_root),
        "write_policy": brain.write_policy,
        "schema_version": 1,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/auto-test-pytest tests/unit/test_brain_mount.py`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/lib/brain_mount.py tests/unit/test_brain_mount.py
git commit -m "$(cat <<'EOF'
feat(brain-mount): minimal .augur/ mount writer with BRAIN.yaml manifest (ADR-754 stage 1)

ensure_mount() creates each registered brain's .augur/ directory and
writes BRAIN.yaml recording brain identity. Per-client harness files
land in stage 2; stage 1 only establishes the mount directory.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Wire mount generation into the sync flow

**Files:**
- Modify: the existing sync entry point (located in Step 1)
- Test: `tests/integration/test_brain_registry_stage1.py` (added in Task 8)

- [ ] **Step 1: Locate the sync entry point**

Run: `grep -rln "sync_agents\|def sync_all\|client config sync" shared-vault/skills/ai/ src/lib/ 2>/dev/null | head -10`
Then: `grep -n "def " shared-vault/skills/ai/scripts/sync_agents.py 2>/dev/null | head -30`

Identify the top-level orchestrator function the `/dev-sync` command calls (likely a `sync_all` or `run_sync` in `shared-vault/skills/ai/scripts/sync_agents.py`). Note its path and the function name; the next step targets it.

If the exploration reveals a different file owns the orchestration (e.g., a `dev-sync` slash command's Python entry), use that file's path in step 2.

- [ ] **Step 2: Add the brain-mount step at the end of the sync orchestrator**

Edit the located file. Append a new step at the end of the orchestrator (NOT inside any client-specific adapter), exactly:

```python
def _ensure_brain_mounts() -> list[str]:
    """Ensure .augur/ mount exists in every registered brain root."""
    from src.lib.brain_mount import ensure_mount
    from src.lib.brain_registry import get_registry

    registry = get_registry()
    written: list[str] = []
    for brain_id in registry.ids():
        brain = registry.get(brain_id)
        if brain is None:
            continue
        if not brain.data_root.is_dir():
            # Skip silently in stage 1 — the brain root may exist on a different machine.
            continue
        ensure_mount(brain)
        written.append(brain_id)
    return written
```

Then call `_ensure_brain_mounts()` from the orchestrator function discovered in Step 1, right before its existing return / final report. Log the result via the orchestrator's existing logger (do not introduce a new logging style):

```python
brain_ids = _ensure_brain_mounts()
if brain_ids:
    logger.info("Ensured .augur/ mount for brains: %s", ", ".join(brain_ids))
```

(Adapt `logger` to whatever the file already uses.)

- [ ] **Step 3: Add a unit test for `_ensure_brain_mounts` if practical**

If the orchestrator file already has unit tests under `shared-vault/skills/ai/augur/tests/` (per the user's memory `feedback-skill-test-convention`), add a test there using `importlib.util.spec_from_file_location` to import the function. If no test file exists, defer coverage to the integration test in Task 8 — do NOT introduce a new dotted-module test for skill code.

- [ ] **Step 4: Run the existing sync test suite to catch regressions**

Run: `/auto-test-pytest tests/sync_agents/`
Expected: green; the new function is additive at the orchestrator's tail, so no existing tests should fail.

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/ai/scripts/sync_agents.py  # adapt path if different
git commit -m "$(cat <<'EOF'
feat(dev-sync): ensure .augur/ mount for every registered brain (ADR-754 stage 1)

After the existing per-client sync passes complete, iterate the brain
registry and write BRAIN.yaml inside each brain's .augur/ directory.
Idempotent; missing data_roots are skipped silently (other machines).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Integration test — end-to-end Stage 1 verification

**Files:**
- Create: `tests/integration/test_brain_registry_stage1.py`

- [ ] **Step 1: Write the integration test**

Create `tests/integration/test_brain_registry_stage1.py`:

```python
from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from src.config.paths import (
    get_brain_dir,
    get_brain_registry_path,
    get_shared_vault_dir,
    get_vault_dir,
    list_brain_ids,
)
from src.lib.brain_mount import ensure_mount
from src.lib.brain_registry import clear_cache, get_registry


@pytest.fixture
def fake_project_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("AUGUR_STATE_DIR", str(tmp_path / ".augur"))
    # vault.yaml describes a non-existent path; bootstrap shouldn't care because it doesn't access it.
    config_dir = tmp_path / "config" / "system"
    config_dir.mkdir(parents=True)
    (config_dir / "vault.yaml").write_text(
        "vault:\n"
        f"  path: {tmp_path / 'fake-au-vault'}\n"
        "  git:\n"
        "    auto_commit: true\n"
        "    auto_push: true\n"
        "    remote: origin\n"
        "    branch: main\n"
        "  remote: \"https://example.com/fake.git\"\n",
        encoding="utf-8",
    )
    (tmp_path / "fake-au-vault").mkdir()
    (tmp_path / "shared-vault").mkdir()
    monkeypatch.setenv("AUGUR_VAULT", str(tmp_path / "fake-au-vault"))
    monkeypatch.setenv("AUGUR_SHARED_VAULT", str(tmp_path / "shared-vault"))
    monkeypatch.chdir(tmp_path)
    clear_cache()
    yield tmp_path
    clear_cache()


def test_fresh_setup_creates_registry_and_mounts(fake_project_root: Path):
    # On first call, brains.yaml does not exist.
    registry_path = get_brain_registry_path()
    assert not registry_path.is_file()

    registry = get_registry(project_root=fake_project_root)

    # Registry file now exists with both expected brains.
    assert registry_path.is_file()
    assert sorted(registry.ids()) == ["personal", "team-augur"]

    # get_brain_dir resolves to the same paths as the legacy helpers.
    assert get_brain_dir("personal") == get_vault_dir()
    assert get_brain_dir("team-augur") == get_shared_vault_dir()
    assert sorted(list_brain_ids()) == ["personal", "team-augur"]

    # Mounts exist after ensure_mount runs for each.
    for brain_id in registry.ids():
        brain = registry.get(brain_id)
        ensure_mount(brain)
        mount = brain.data_root / ".augur"
        assert mount.is_dir()
        manifest = mount / "BRAIN.yaml"
        assert manifest.is_file()
        parsed = yaml.safe_load(manifest.read_text(encoding="utf-8"))
        assert parsed["id"] == brain_id


def test_subsequent_calls_reuse_registry(fake_project_root: Path):
    first_registry = get_registry(project_root=fake_project_root)
    registry_path = get_brain_registry_path()
    first_mtime = registry_path.stat().st_mtime
    # No bootstrap should re-run.
    clear_cache()  # force re-read but NOT regenerate
    second_registry = get_registry(project_root=fake_project_root)
    assert second_registry.ids() == first_registry.ids()
    assert registry_path.stat().st_mtime == first_mtime
```

- [ ] **Step 2: Run the integration test**

Run: `/auto-test-pytest tests/integration/test_brain_registry_stage1.py`
Expected: 2 passed.

- [ ] **Step 3: Run the full unit + integration suite to catch cross-test regressions**

Run: `/auto-test-pytest tests/unit/test_brain_registry_models.py tests/unit/test_brain_registry_io.py tests/unit/test_brain_registry_bootstrap.py tests/unit/test_brain_registry.py tests/unit/test_brain_mount.py tests/config/test_paths.py tests/integration/test_brain_registry_stage1.py`
Expected: all green.

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_brain_registry_stage1.py
git commit -m "$(cat <<'EOF'
test(brain-registry): end-to-end stage 1 verification (ADR-754 stage 1)

Drives the full path-helper + registry + mount stack from a fresh
fixture: bootstrap creates brains.yaml, get_brain_dir resolves to the
same paths as get_vault_dir / get_shared_vault_dir, and ensure_mount
writes BRAIN.yaml in each brain root.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Honesty pass — manual verification on the real laptop

Per CLAUDE.md rule 34, mechanical green tests are not sufficient. Stage 1 must demonstrate end-to-end value on the user's actual machine: starting fresh creates a real `~/.augur/brains.yaml` whose two entries point at the user's real `Au-vault` and `Augur/shared-vault/` paths.

- [ ] **Step 1: Run the real-data smoke check**

From `~/Projects/Augur` (the harness checkout):

```bash
uv run python -c "
from src.lib.brain_registry import clear_cache, get_registry
from src.config.paths import get_brain_dir, get_vault_dir, get_shared_vault_dir

clear_cache()
registry = get_registry()
print('Brain ids:', registry.ids())
print('personal data_root:', get_brain_dir('personal'))
print('  legacy get_vault_dir:', get_vault_dir())
print('team-augur data_root:', get_brain_dir('team-augur'))
print('  legacy get_shared_vault_dir:', get_shared_vault_dir())
"
```

Expected: prints `['personal', 'team-augur']`, with personal pointing at `~/Projects/Au-vault` (matching `get_vault_dir()`) and team-augur at `~/Projects/Augur/shared-vault` (matching `get_shared_vault_dir()`).

If the paths do not match, the bootstrap module has a bug — fix before proceeding.

- [ ] **Step 2: Verify `~/.augur/brains.yaml` content by inspection**

Run: `cat ~/.augur/brains.yaml`
Expected: a YAML document with `version: 1`, a `personal` entry pointing at `Au-vault` with `arrangement: standalone` and your real remote, and a `team-augur` entry pointing at `shared-vault/` with `arrangement: bundled` and `host_repo: ~/Projects/Augur`.

- [ ] **Step 3: Verify both `.augur/` mounts were written**

Run: `ls -la ~/Projects/Au-vault/.augur/ ~/Projects/Augur/shared-vault/.augur/`
Expected: both directories exist, each contains a `BRAIN.yaml` with the correct id/type.

- [ ] **Step 4: Verify zero behavior change for existing workflows**

Run the standard Augur test suite that exercises today's vault helpers:

`/auto-test-pytest tests/test_vault.py tests/test_promotion.py tests/unit/test_vault_promotion.py`

Expected: all green; no regression in `get_vault_dir`, `get_shared_vault_dir`, or the promotion-packet flow.

- [ ] **Step 5: Report findings**

Write a short closeout in the PR description (or in the worktree's notes if PR-less): brain registry generated successfully, paths match legacy helpers, both `.augur/` mounts exist, no test regressions. Per rule 34, the closeout must name the real input used (your real laptop, real Au-vault path, real shared-vault path) and the concrete value the output delivered (registry file content + mount manifest content quoted).

- [ ] **Step 6: Final commit (if any tweaks were needed)**

If steps 1-4 required code adjustments to land green, commit them with a descriptive message tied to the finding. If everything was green on the first run, skip this step — there's nothing to commit.

---

## Self-review against the spec

**Spec coverage — Stage 1 section:**

| Spec requirement | Plan task |
| --- | --- |
| Introduce `~/.augur/brains.yaml` with personal + team-augur entries auto-generated from vault.yaml + shared-vault detection | Tasks 3 + 4 |
| `vault.yaml` keeps working as the source of truth for personal's data_root/git block, generated into brains.yaml | Task 3 (`_personal_from_vault_yaml`) |
| `paths.py` keeps current API; existing helpers unchanged | Task 5 (append-only, sanity check in Task 5 step 6 + Task 9 step 4) |
| New helper `get_brain_dir(brain_id)` added | Task 5 |
| Generate `.augur/` mounts inside each registered brain root | Tasks 6 + 7 + Task 9 step 3 |
| Today's `cd Augur && claude` workflow unchanged | Task 5 step 6 + Task 9 step 4 |
| Brain registry data model (Brain, GitConfig, PropagationPolicy, BrainRegistry) | Task 1 |
| Brain registry YAML serialization | Task 2 |

**Placeholder scan:** ran on this plan — no TBDs, TODOs, "fill in later", or vague directives. Every code step shows the exact code.

**Type consistency check:** `Brain`, `BrainRegistry`, `BrainType`, `GitArrangement`, `GitConfig`, `PropagationPolicy`, `ensure_mount`, `get_registry`, `clear_cache`, `build_default_registry`, `get_brain_dir`, `list_brain_ids`, `get_brain_registry_path`, `get_augur_state_dir` — all names appear consistently across tasks 1-9. `_personal_from_vault_yaml` and `_ensure_brain_mounts` are intentionally task-local helpers.

**Scope check:** this plan is Stage 1 only. Stage 2 (BrainContext + propagation generalization) and Stage 3 (new brain types + federation UI) are out of scope and would be drafted as separate plans once Stage 1 is shipped and stable.

---

## Notes for the executor

- **Per CLAUDE.md rule 19:** run tests via `/auto-test-pytest`, not raw `pytest`. The plan uses this throughout; if `/auto-test-pytest` does not accept file-path arguments in the active toolchain, consult `/dev-loops` and adapt the invocation while keeping the same test scope.
- **Per CLAUDE.md rule 21:** if a test fails for a reason other than "module not defined" / "name not defined" (i.e. the failure is unexpected), debug it rather than working around it. Bootstrap and YAML I/O have subtle edge cases — read the traceback, do not patch the assertion.
- **Per CLAUDE.md rule 34:** do not declare Stage 1 done until Task 9's real-data smoke check passes on the user's actual laptop with the real `Au-vault` and `Augur/shared-vault/` paths. Mechanical test-suite green is necessary but not sufficient.
- **Per CLAUDE.md rule 10:** commit after each task. Do not batch multiple tasks into one commit.
- **Per CLAUDE.md rule 14:** do not add compatibility shims beyond what this plan defines (the spec governs the `vault.yaml`-as-source-of-truth shim explicitly; that one is ADR-allowed).
- **If Task 7 exploration reveals the sync orchestrator lives somewhere unexpected,** stop and flag rather than guess. The placement of `_ensure_brain_mounts()` matters — it must run after per-client adapters, not before them, otherwise the mount-init order will conflict with stage 2's per-client harness generation.
