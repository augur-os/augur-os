# Multi-Brain Project Brain Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the v1 project-brain foundation: one three-type brain model, root `BRAIN.yaml`, cwd-based project attachment, and idempotent `aug init` for repos that already have or need `project-brain/`.

**Architecture:** Keep this as a foundation slice, not the physical `shared-vault/` migration. The implementation adds a focused manifest/skeleton module, an active-context resolver, and an init/attach flow that updates the local registry and triggers existing client projection sync. Existing path helpers continue to serve old locations until the migration plan replaces them.

**Tech Stack:** Python 3.11+, dataclasses, PyYAML, argparse, existing Augur CLI, existing `sync_agents`, existing `src.config.paths` runtime/log/cache helpers.

**Implementation status:** Implemented before ADR-769 was formalized. The task
checkboxes below are the original execution plan, not the current status ledger.
ADR-769 records the implemented phase and points back to this plan as the
canonical implementation handoff.

---

## Scope

This plan implements the first executable slice from the design:

- Remove the retired `work` brain type from the registry model.
- Treat `shared-vault` as legacy Augur project content, not as a team brain.
- Add root-level `BRAIN.yaml` support for brain roots.
- Add `project-brain/` discovery from any cwd.
- Add an active context resolver with `active_brain` and `attached_project`.
- Add idempotent `aug init` behavior for fresh and cloned repos.
- Trigger generated AI-client projections for all supported clients detected/enabled by the existing sync layer.
- Tighten `/ask` policy so retention is explicit by default.

This plan does not move `shared-vault/` content into `project-brain/`; that is a separate migration plan after the foundation exists and is verified.

## File Map

- Create `src/lib/brain_manifest.py`
  - Owns `BRAIN.yaml` read/write, skeleton creation, project-brain discovery, and manifest validation.
- Create `src/lib/brain_context.py`
  - Owns cwd/override resolution into `ActiveBrainContext`.
- Create `src/lib/brain_init.py`
  - Owns idempotent project-brain create/attach and sync invocation.
- Modify `src/lib/brain_registry_models.py`
  - Remove `BrainType.WORK`; keep `personal`, `team`, `project`.
- Modify `src/lib/brain_registry_io.py`
  - Continue round-tripping only supported brain types.
- Modify `src/lib/brain_registry_bootstrap.py`
  - Stop auto-creating `team-augur` from `shared-vault`.
  - Register `project-augur` only when `project-brain/BRAIN.yaml` exists.
- Modify `src/lib/brain_mount.py`
  - Replace `.augur/BRAIN.yaml` mount behavior with root `BRAIN.yaml` writes.
- Modify `src/config/paths.py`
  - Add project-brain path helpers and active-context helper entrypoints.
- Modify `src/cli.py`
  - Register built-in `aug init` before MCP tool dispatch.
- Modify `shared-vault/skills/augur-core/commands/ask.md`
  - Change default future policy to no retention unless explicit.
- Test `tests/unit/test_brain_registry_models.py`
- Test `tests/unit/test_brain_registry_io.py`
- Test `tests/unit/test_brain_registry_bootstrap.py`
- Test `tests/unit/test_brain_manifest.py`
- Test `tests/unit/test_brain_context.py`
- Test `tests/unit/test_brain_init.py`
- Test `tests/config/test_brain_paths.py`
- Test `tests/cli/test_cli_subcommands.py`

## Follow-Up Plans Required

- Physical migration: `shared-vault/skills -> project-brain/capabilities/skills`, ADRs, specs, wiki, notes, inbox, generated inventories.
- AI-client projection source migration: generated files should eventually read from `project-brain/instructions/` and `project-brain/capabilities/`.
- UI discovery: known brains, discovered project brains, projection/index status.
- Memory review product: client-native memory as input/review source without copying raw content into runtime.

### Task 1: Remove The Retired `work` Brain Type

**Files:**
- Modify: `src/lib/brain_registry_models.py`
- Modify: `tests/unit/test_brain_registry_io.py`
- Modify: any failing test references found by `rg "BrainType\\.WORK|type: work|work-" tests src`

- [ ] **Step 1: Write/update the failing regression test**

In `tests/unit/test_brain_registry_io.py`, replace `test_propagation_policy_roundtrips` with this project-brain version:

```python
def test_propagation_policy_roundtrips(tmp_path: Path):
    brain = Brain(
        id="project-firmware",
        type=BrainType.PROJECT,
        data_root=Path("/Users/x/Projects/firmware/project-brain"),
        git=GitConfig(
            arrangement=GitArrangement.BUNDLED,
            host_repo=Path("/Users/x/Projects/firmware"),
        ),
        propagation=PropagationPolicy(
            allow_from=("personal",),
            allow_to=("personal",),
        ),
    )
    original = BrainRegistry(version=1, brains={"project-firmware": brain})
    target = tmp_path / "brains.yaml"
    save_registry(original, target)
    loaded = load_registry(target)
    assert loaded.get("project-firmware").type is BrainType.PROJECT
    assert loaded.get("project-firmware").propagation == PropagationPolicy(
        allow_from=("personal",), allow_to=("personal",)
    )
```

- [ ] **Step 2: Run the focused regression and confirm it fails before implementation**

Run through the repo test loop:

```text
/auto-test-pytest tests/unit/test_brain_registry_io.py -q
```

Expected before implementation: failure or import/reference failure if `BrainType.WORK` is still expected elsewhere.

- [ ] **Step 3: Remove `WORK` from the enum**

In `src/lib/brain_registry_models.py`, change `BrainType` to:

```python
class BrainType(str, Enum):
    PERSONAL = "personal"
    TEAM = "team"
    PROJECT = "project"
```

- [ ] **Step 4: Search and remove remaining work-brain references**

Run:

```text
rg "BrainType\\.WORK|type: work|work-" src tests docs
```

Expected after edits: no source/test references that model `work` as a current brain type. Historical ADR text may remain only if it is explicitly historical.

- [ ] **Step 5: Run focused tests**

Run:

```text
/auto-test-pytest tests/unit/test_brain_registry_models.py tests/unit/test_brain_registry_io.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add src/lib/brain_registry_models.py tests/unit/test_brain_registry_io.py
git commit -m "refactor: remove work brain type"
```

### Task 2: Add Root `BRAIN.yaml` Manifest And Skeleton Support

**Files:**
- Create: `src/lib/brain_manifest.py`
- Create: `tests/unit/test_brain_manifest.py`

- [ ] **Step 1: Write tests for manifest read/write, skeleton creation, and upward discovery**

Create `tests/unit/test_brain_manifest.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from src.lib.brain_manifest import (
    BRAIN_MANIFEST_NAME,
    PROJECT_BRAIN_DIRNAME,
    BrainManifest,
    ensure_brain_skeleton,
    find_project_brain_root,
    read_brain_manifest,
    write_brain_manifest,
)
from src.lib.brain_registry_models import BrainType


def test_write_and_read_brain_manifest(tmp_path: Path):
    root = tmp_path / "project-brain"
    manifest = BrainManifest(
        schema_version=1,
        id="project-demo",
        type=BrainType.PROJECT,
        root=str(root),
        attached_project=str(tmp_path),
    )

    write_brain_manifest(root, manifest)

    loaded = read_brain_manifest(root / BRAIN_MANIFEST_NAME)
    assert loaded == manifest


def test_ensure_brain_skeleton_creates_expected_dirs(tmp_path: Path):
    root = tmp_path / PROJECT_BRAIN_DIRNAME
    ensure_brain_skeleton(root)

    for rel in (
        "profile",
        "instructions/topics",
        "capabilities/skills",
        "capabilities/agents",
        "knowledge/memory/entries",
        "knowledge/notes",
        "knowledge/sources",
        "knowledge/wiki",
        "decisions/adrs",
        "specs",
        "plans",
        "workflows",
        "policies",
        "activity/daily",
        "reports",
        "inbox",
        "archive",
    ):
        assert (root / rel).is_dir(), rel


def test_find_project_brain_root_walks_up_from_nested_dir(tmp_path: Path):
    project = tmp_path / "repo"
    nested = project / "src" / "firmware"
    nested.mkdir(parents=True)
    brain = project / PROJECT_BRAIN_DIRNAME
    ensure_brain_skeleton(brain)
    write_brain_manifest(
        brain,
        BrainManifest(
            schema_version=1,
            id="project-repo",
            type=BrainType.PROJECT,
            root=str(brain),
            attached_project=str(project),
        ),
    )

    assert find_project_brain_root(nested) == brain


def test_read_brain_manifest_rejects_unknown_type(tmp_path: Path):
    manifest = tmp_path / BRAIN_MANIFEST_NAME
    manifest.write_text(
        "schema_version: 1\nid: x\ntype: work\nroot: /tmp/x\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid brain type"):
        read_brain_manifest(manifest)
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```text
/auto-test-pytest tests/unit/test_brain_manifest.py -q
```

Expected before implementation: import failure for `src.lib.brain_manifest`.

- [ ] **Step 3: Implement `src/lib/brain_manifest.py`**

Create `src/lib/brain_manifest.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from src.lib.brain_registry_models import Brain, BrainType

BRAIN_MANIFEST_NAME = "BRAIN.yaml"
PROJECT_BRAIN_DIRNAME = "project-brain"
BRAIN_SCHEMA_VERSION = 1

_SKELETON_DIRS = (
    "profile",
    "instructions/topics",
    "capabilities/skills",
    "capabilities/agents",
    "knowledge/memory/entries",
    "knowledge/notes",
    "knowledge/sources",
    "knowledge/wiki",
    "decisions/adrs",
    "specs",
    "plans",
    "workflows",
    "policies",
    "activity/daily",
    "reports",
    "inbox",
    "archive",
)


@dataclass(frozen=True)
class BrainManifest:
    schema_version: int
    id: str
    type: BrainType
    root: str
    attached_project: str | None = None
    description: str | None = None

    @classmethod
    def from_brain(
        cls,
        brain: Brain,
        *,
        attached_project: Path | None = None,
    ) -> "BrainManifest":
        return cls(
            schema_version=BRAIN_SCHEMA_VERSION,
            id=brain.id,
            type=brain.type,
            root=str(brain.data_root),
            attached_project=str(attached_project) if attached_project else None,
            description=brain.description,
        )

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "BrainManifest":
        try:
            brain_type = BrainType(raw["type"])
        except ValueError as exc:
            raise ValueError(f"invalid brain type: {raw.get('type')}") from exc
        version = raw.get("schema_version")
        if version != BRAIN_SCHEMA_VERSION:
            raise ValueError(f"unsupported BRAIN.yaml schema_version: {version}")
        return cls(
            schema_version=version,
            id=str(raw["id"]),
            type=brain_type,
            root=str(raw["root"]),
            attached_project=raw.get("attached_project"),
            description=raw.get("description"),
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "schema_version": self.schema_version,
            "id": self.id,
            "type": self.type.value,
            "root": self.root,
        }
        if self.attached_project is not None:
            data["attached_project"] = self.attached_project
        if self.description is not None:
            data["description"] = self.description
        return data


def ensure_brain_skeleton(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for rel in _SKELETON_DIRS:
        (root / rel).mkdir(parents=True, exist_ok=True)


def write_brain_manifest(root: Path, manifest: BrainManifest) -> Path:
    ensure_brain_skeleton(root)
    path = root / BRAIN_MANIFEST_NAME
    path.write_text(
        yaml.safe_dump(manifest.to_dict(), sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    return path


def read_brain_manifest(path: Path) -> BrainManifest:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"invalid BRAIN.yaml content: {path}")
    return BrainManifest.from_dict(raw)


def project_brain_root_for(project_root: Path) -> Path:
    return project_root.resolve() / PROJECT_BRAIN_DIRNAME


def find_project_brain_root(start: Path) -> Path | None:
    current = start.resolve()
    for candidate in (current, *current.parents):
        brain_root = candidate / PROJECT_BRAIN_DIRNAME
        if (brain_root / BRAIN_MANIFEST_NAME).is_file():
            return brain_root
    return None
```

- [ ] **Step 4: Run focused tests**

Run:

```text
/auto-test-pytest tests/unit/test_brain_manifest.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/lib/brain_manifest.py tests/unit/test_brain_manifest.py
git commit -m "feat: add brain root manifest support"
```

### Task 3: Replace `.augur/BRAIN.yaml` Mounts With Root `BRAIN.yaml`

**Files:**
- Modify: `src/lib/brain_mount.py`
- Test: create or update `tests/unit/test_brain_mount.py` if it exists; otherwise add it.

- [ ] **Step 1: Write the root-manifest mount tests**

Create `tests/unit/test_brain_mount.py`:

```python
from __future__ import annotations

from pathlib import Path

import yaml

from src.lib.brain_mount import ensure_mount, mount_dir_for_brain
from src.lib.brain_registry_models import Brain, BrainType, GitArrangement, GitConfig


def test_mount_dir_for_brain_is_brain_root(tmp_path: Path):
    brain = Brain(
        id="project-demo",
        type=BrainType.PROJECT,
        data_root=tmp_path / "project-brain",
        git=GitConfig(arrangement=GitArrangement.BUNDLED, host_repo=tmp_path),
    )

    assert mount_dir_for_brain(brain) == tmp_path / "project-brain"


def test_ensure_mount_writes_root_brain_yaml(tmp_path: Path):
    brain = Brain(
        id="project-demo",
        type=BrainType.PROJECT,
        data_root=tmp_path / "project-brain",
        git=GitConfig(arrangement=GitArrangement.BUNDLED, host_repo=tmp_path),
        description="Demo project brain",
    )

    root = ensure_mount(brain)

    manifest = root / "BRAIN.yaml"
    assert manifest.is_file()
    assert not (root / ".augur" / "BRAIN.yaml").exists()
    data = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    assert data["id"] == "project-demo"
    assert data["type"] == "project"
    assert data["schema_version"] == 1
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```text
/auto-test-pytest tests/unit/test_brain_mount.py -q
```

Expected before implementation: failure because current mount path is `<brain>/.augur`.

- [ ] **Step 3: Update `src/lib/brain_mount.py`**

Replace `_MOUNT_SUBDIR = ".augur"` behavior with root-manifest behavior. Keep the public function names to minimize callers touched in this task:

```python
from src.lib.brain_manifest import BrainManifest, write_brain_manifest


def mount_dir_for_brain(brain: Brain) -> Path:
    """Return the brain root that owns BRAIN.yaml."""
    return Path(brain.data_root)


def ensure_mount(brain: Brain) -> Path:
    """Create or refresh the brain root BRAIN.yaml."""
    root = mount_dir_for_brain(brain)
    attached_project = Path(brain.git.host_repo) if brain.git.host_repo else None
    write_brain_manifest(
        root,
        BrainManifest.from_brain(brain, attached_project=attached_project),
    )
    return root
```

Remove `_MOUNT_SUBDIR`, `_BRAIN_MANIFEST`, `_manifest_body`, `_registry_fingerprint`, `_exclude_mount_from_git_status`, `_git_stdout`, and `_append_git_exclude_pattern` if they become unused.

- [ ] **Step 4: Run focused tests**

Run:

```text
/auto-test-pytest tests/unit/test_brain_mount.py tests/unit/test_brain_manifest.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/lib/brain_mount.py tests/unit/test_brain_mount.py
git commit -m "refactor: write brain manifests at brain root"
```

### Task 4: Bootstrap Project Brain Instead Of `team-augur`

**Files:**
- Modify: `src/lib/brain_registry_bootstrap.py`
- Modify: `tests/unit/test_brain_registry_bootstrap.py`

- [ ] **Step 1: Replace bootstrap tests**

In `tests/unit/test_brain_registry_bootstrap.py`, replace `test_bootstrap_produces_personal_and_team_augur` with:

```python
def test_bootstrap_produces_personal_and_project_augur_when_project_brain_exists(tmp_path: Path):
    project_root = _write_vault_yaml(
        tmp_path, "~/Projects/Au-vault", "https://github.com/x/au-vault.git"
    )
    brain_root = project_root / "project-brain"
    brain_root.mkdir()
    (brain_root / "BRAIN.yaml").write_text(
        "schema_version: 1\n"
        "id: project-augur\n"
        "type: project\n"
        f"root: {brain_root}\n"
        f"attached_project: {project_root}\n",
        encoding="utf-8",
    )
    (project_root / "shared-vault").mkdir()

    registry = build_default_registry(project_root=project_root)

    assert registry.version == 1
    assert sorted(registry.ids()) == ["personal", "project-augur"]

    personal = registry.get("personal")
    assert personal is not None
    assert personal.type is BrainType.PERSONAL

    project = registry.get("project-augur")
    assert project is not None
    assert project.type is BrainType.PROJECT
    assert project.data_root == brain_root.resolve()
    assert project.git.arrangement is GitArrangement.BUNDLED
    assert project.git.host_repo == project_root.resolve()
    assert project.write_policy == "free"
    assert project.auto_activate_cwd_under == (project_root.resolve(),)
```

Replace `test_bootstrap_omits_team_when_shared_vault_missing` with:

```python
def test_bootstrap_does_not_create_team_from_shared_vault(tmp_path: Path):
    project_root = _write_vault_yaml(
        tmp_path, "~/Projects/Au-vault", "https://example.com/x.git"
    )
    (project_root / "shared-vault").mkdir()

    registry = build_default_registry(project_root=project_root)

    assert registry.ids() == ["personal"]
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```text
/auto-test-pytest tests/unit/test_brain_registry_bootstrap.py -q
```

Expected before implementation: failure because current bootstrap creates `team-augur`.

- [ ] **Step 3: Update bootstrap logic**

In `src/lib/brain_registry_bootstrap.py`:

1. Import manifest helpers:

```python
from src.lib.brain_manifest import (
    BRAIN_MANIFEST_NAME,
    PROJECT_BRAIN_DIRNAME,
    read_brain_manifest,
)
```

2. Replace the shared-vault/team block inside `build_default_registry()` with:

```python
    project = _project_from_project_brain(project_root)
    if project is not None:
        brains[project.id] = project
```

3. Add:

```python
def _project_from_project_brain(project_root: Path) -> Brain | None:
    brain_root = (project_root / PROJECT_BRAIN_DIRNAME).resolve()
    manifest_path = brain_root / BRAIN_MANIFEST_NAME
    if not manifest_path.is_file():
        return None
    manifest = read_brain_manifest(manifest_path)
    if manifest.type is not BrainType.PROJECT:
        raise ValueError(f"project brain manifest must have type=project: {manifest_path}")
    return Brain(
        id=manifest.id,
        type=BrainType.PROJECT,
        data_root=brain_root,
        git=GitConfig(
            arrangement=GitArrangement.BUNDLED,
            host_repo=project_root.resolve(),
        ),
        write_policy="free",
        description=manifest.description or "Project brain",
        auto_activate_cwd_under=(project_root.resolve(),),
    )
```

4. Remove `_shared_vault_root()` if unused.

- [ ] **Step 4: Run focused tests**

Run:

```text
/auto-test-pytest tests/unit/test_brain_registry_bootstrap.py tests/unit/test_brain_registry_io.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/lib/brain_registry_bootstrap.py tests/unit/test_brain_registry_bootstrap.py
git commit -m "feat: bootstrap project brains from project-brain"
```

### Task 5: Add Active Brain Context Resolution

**Files:**
- Create: `src/lib/brain_context.py`
- Create: `tests/unit/test_brain_context.py`

- [ ] **Step 1: Write context resolver tests**

Create `tests/unit/test_brain_context.py`:

```python
from __future__ import annotations

from pathlib import Path

from src.lib.brain_context import resolve_active_context
from src.lib.brain_manifest import BrainManifest, ensure_brain_skeleton, write_brain_manifest
from src.lib.brain_registry_io import save_registry
from src.lib.brain_registry_models import (
    Brain,
    BrainRegistry,
    BrainType,
    GitArrangement,
    GitConfig,
)


def _personal(path: Path) -> Brain:
    return Brain(
        id="personal",
        type=BrainType.PERSONAL,
        data_root=path,
        git=GitConfig(arrangement=GitArrangement.UNTRACKED),
    )


def test_resolve_active_context_uses_nearest_project_brain(tmp_path: Path):
    project = tmp_path / "repo"
    nested = project / "src" / "module"
    nested.mkdir(parents=True)
    brain_root = project / "project-brain"
    ensure_brain_skeleton(brain_root)
    write_brain_manifest(
        brain_root,
        BrainManifest(
            schema_version=1,
            id="project-repo",
            type=BrainType.PROJECT,
            root=str(brain_root),
            attached_project=str(project),
        ),
    )
    registry_path = tmp_path / "brains.yaml"
    save_registry(
        BrainRegistry(
            version=1,
            brains={
                "personal": _personal(tmp_path / "personal"),
                "project-repo": Brain(
                    id="project-repo",
                    type=BrainType.PROJECT,
                    data_root=brain_root,
                    git=GitConfig(arrangement=GitArrangement.BUNDLED, host_repo=project),
                    auto_activate_cwd_under=(project,),
                ),
            },
        ),
        registry_path,
    )

    ctx = resolve_active_context(cwd=nested, registry_path=registry_path)

    assert ctx.active_brain.id == "project-repo"
    assert ctx.active_brain.type is BrainType.PROJECT
    assert ctx.attached_project == project.resolve()
    assert ctx.source == "nearest-project-brain"


def test_resolve_active_context_falls_back_to_personal(tmp_path: Path):
    registry_path = tmp_path / "brains.yaml"
    save_registry(
        BrainRegistry(version=1, brains={"personal": _personal(tmp_path / "personal")}),
        registry_path,
    )

    ctx = resolve_active_context(cwd=tmp_path / "outside", registry_path=registry_path)

    assert ctx.active_brain.id == "personal"
    assert ctx.attached_project is None
    assert ctx.source == "default-personal"


def test_resolve_active_context_honors_explicit_brain(tmp_path: Path):
    registry_path = tmp_path / "brains.yaml"
    team = Brain(
        id="team-core",
        type=BrainType.TEAM,
        data_root=tmp_path / "team",
        git=GitConfig(arrangement=GitArrangement.UNTRACKED),
    )
    save_registry(
        BrainRegistry(version=1, brains={"personal": _personal(tmp_path / "personal"), "team-core": team}),
        registry_path,
    )

    ctx = resolve_active_context(
        cwd=tmp_path,
        registry_path=registry_path,
        explicit_brain="team-core",
    )

    assert ctx.active_brain.id == "team-core"
    assert ctx.attached_project is None
    assert ctx.source == "explicit-brain"
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```text
/auto-test-pytest tests/unit/test_brain_context.py -q
```

Expected before implementation: import failure for `src.lib.brain_context`.

- [ ] **Step 3: Implement `src/lib/brain_context.py`**

Create `src/lib/brain_context.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.lib.brain_manifest import find_project_brain_root, read_brain_manifest
from src.lib.brain_registry_io import load_registry
from src.lib.brain_registry_models import Brain, BrainType, GitArrangement, GitConfig


@dataclass(frozen=True)
class ActiveBrainContext:
    active_brain: Brain
    attached_project: Path | None
    source: str

    def to_header_dict(self) -> dict[str, object]:
        return {
            "active_brain": {
                "id": self.active_brain.id,
                "type": self.active_brain.type.value,
                "root": str(self.active_brain.data_root),
            },
            "attached_project": (
                {
                    "root": str(self.attached_project),
                    "has_adrs": (self.attached_project / "project-brain" / "decisions" / "adrs").is_dir(),
                    "has_runtime": True,
                }
                if self.attached_project is not None
                else None
            ),
            "generated_projection": True,
        }


def resolve_active_context(
    *,
    cwd: Path | None = None,
    registry_path: Path | None = None,
    explicit_brain: str | None = None,
    explicit_project: Path | None = None,
) -> ActiveBrainContext:
    start = (explicit_project or cwd or Path.cwd()).resolve()
    registry = load_registry(registry_path) if registry_path and registry_path.is_file() else None

    if explicit_brain:
        if registry is None:
            raise KeyError(f"brain not registered: {explicit_brain}")
        brain = registry.get(explicit_brain)
        if brain is None:
            raise KeyError(f"brain not registered: {explicit_brain}")
        attached = _attached_project_for(brain, start)
        return ActiveBrainContext(active_brain=brain, attached_project=attached, source="explicit-brain")

    project_brain_root = find_project_brain_root(start)
    if project_brain_root is not None:
        manifest = read_brain_manifest(project_brain_root / "BRAIN.yaml")
        project_root = Path(manifest.attached_project).resolve() if manifest.attached_project else project_brain_root.parent.resolve()
        registered = registry.get(manifest.id) if registry is not None else None
        brain = registered or Brain(
            id=manifest.id,
            type=BrainType.PROJECT,
            data_root=project_brain_root,
            git=GitConfig(arrangement=GitArrangement.BUNDLED, host_repo=project_root),
            auto_activate_cwd_under=(project_root,),
            description=manifest.description,
        )
        return ActiveBrainContext(active_brain=brain, attached_project=project_root, source="nearest-project-brain")

    if registry is not None:
        for brain in registry.brains.values():
            for root in brain.auto_activate_cwd_under:
                try:
                    start.relative_to(Path(root).resolve())
                except ValueError:
                    continue
                return ActiveBrainContext(
                    active_brain=brain,
                    attached_project=Path(root).resolve() if brain.type is BrainType.PROJECT else None,
                    source="registered-project",
                )
        personal = registry.get("personal")
        if personal is not None:
            return ActiveBrainContext(active_brain=personal, attached_project=None, source="default-personal")

    raise KeyError("no active brain could be resolved")


def _attached_project_for(brain: Brain, cwd: Path) -> Path | None:
    if brain.type is not BrainType.PROJECT:
        return None
    if brain.git.host_repo is not None:
        return Path(brain.git.host_repo).resolve()
    if brain.auto_activate_cwd_under:
        return Path(brain.auto_activate_cwd_under[0]).resolve()
    return cwd.resolve()
```

- [ ] **Step 4: Run focused tests**

Run:

```text
/auto-test-pytest tests/unit/test_brain_context.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/lib/brain_context.py tests/unit/test_brain_context.py
git commit -m "feat: resolve active brain context"
```

### Task 6: Add Idempotent Project-Brain Init/Attach

**Files:**
- Create: `src/lib/brain_init.py`
- Create: `tests/unit/test_brain_init.py`

- [ ] **Step 1: Write init tests**

Create `tests/unit/test_brain_init.py`:

```python
from __future__ import annotations

from pathlib import Path

from src.lib.brain_init import init_project_brain
from src.lib.brain_registry_io import load_registry, save_registry
from src.lib.brain_registry_models import (
    Brain,
    BrainRegistry,
    BrainType,
    GitArrangement,
    GitConfig,
)


def test_init_project_brain_creates_manifest_skeleton_and_registry(tmp_path: Path):
    project = tmp_path / "repo"
    project.mkdir()
    registry_path = tmp_path / "brains.yaml"
    personal = Brain(
        id="personal",
        type=BrainType.PERSONAL,
        data_root=tmp_path / "personal",
        git=GitConfig(arrangement=GitArrangement.UNTRACKED),
    )
    save_registry(BrainRegistry(version=1, brains={"personal": personal}), registry_path)

    result = init_project_brain(
        project_root=project,
        registry_path=registry_path,
        run_sync=False,
    )

    assert result.created is True
    assert result.brain_id == "project-repo"
    assert (project / "project-brain" / "BRAIN.yaml").is_file()
    assert (project / "project-brain" / "capabilities" / "skills").is_dir()
    registry = load_registry(registry_path)
    assert registry.get("project-repo").type is BrainType.PROJECT


def test_init_project_brain_attaches_existing_manifest_without_recreating(tmp_path: Path):
    project = tmp_path / "firmware"
    brain = project / "project-brain"
    brain.mkdir(parents=True)
    (brain / "BRAIN.yaml").write_text(
        "schema_version: 1\n"
        "id: project-firmware\n"
        "type: project\n"
        f"root: {brain}\n"
        f"attached_project: {project}\n",
        encoding="utf-8",
    )
    registry_path = tmp_path / "brains.yaml"
    save_registry(BrainRegistry(version=1, brains={}), registry_path)

    result = init_project_brain(
        project_root=project,
        registry_path=registry_path,
        run_sync=False,
    )

    assert result.created is False
    assert result.brain_id == "project-firmware"
    registry = load_registry(registry_path)
    assert registry.get("project-firmware").data_root == brain.resolve()
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```text
/auto-test-pytest tests/unit/test_brain_init.py -q
```

Expected before implementation: import failure for `src.lib.brain_init`.

- [ ] **Step 3: Implement `src/lib/brain_init.py`**

Create `src/lib/brain_init.py`:

```python
from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from src.config.paths import get_brain_registry_path
from src.lib.brain_manifest import (
    BRAIN_MANIFEST_NAME,
    BrainManifest,
    ensure_brain_skeleton,
    project_brain_root_for,
    read_brain_manifest,
    write_brain_manifest,
)
from src.lib.brain_registry import clear_cache
from src.lib.brain_registry_io import load_registry, save_registry
from src.lib.brain_registry_models import (
    Brain,
    BrainRegistry,
    BrainType,
    GitArrangement,
    GitConfig,
)


@dataclass(frozen=True)
class ProjectBrainInitResult:
    brain_id: str
    brain_root: Path
    project_root: Path
    created: bool
    sync_returncode: int | None


def init_project_brain(
    *,
    project_root: Path,
    registry_path: Path | None = None,
    run_sync: bool = True,
) -> ProjectBrainInitResult:
    project = project_root.resolve()
    registry_file = registry_path or get_brain_registry_path()
    brain_root = project_brain_root_for(project)
    manifest_path = brain_root / BRAIN_MANIFEST_NAME
    created = not manifest_path.exists()

    if created:
        ensure_brain_skeleton(brain_root)
        manifest = BrainManifest(
            schema_version=1,
            id=f"project-{_slug(project.name)}",
            type=BrainType.PROJECT,
            root=str(brain_root),
            attached_project=str(project),
            description=f"{project.name} project brain",
        )
        write_brain_manifest(brain_root, manifest)
    else:
        manifest = read_brain_manifest(manifest_path)
        if manifest.type is not BrainType.PROJECT:
            raise ValueError(f"{manifest_path} must declare type=project")

    registry = _load_or_empty_registry(registry_file)
    project_brain = Brain(
        id=manifest.id,
        type=BrainType.PROJECT,
        data_root=brain_root,
        git=GitConfig(arrangement=GitArrangement.BUNDLED, host_repo=project),
        description=manifest.description,
        auto_activate_cwd_under=(project,),
    )
    brains = dict(registry.brains)
    brains[project_brain.id] = project_brain
    save_registry(BrainRegistry(version=registry.version, brains=brains), registry_file)
    clear_cache()

    sync_returncode = _sync_client_projections(project) if run_sync else None
    return ProjectBrainInitResult(
        brain_id=project_brain.id,
        brain_root=brain_root,
        project_root=project,
        created=created,
        sync_returncode=sync_returncode,
    )


def _load_or_empty_registry(path: Path) -> BrainRegistry:
    if path.is_file():
        return load_registry(path)
    return BrainRegistry(version=1, brains={})


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "project"


def _sync_client_projections(project_root: Path) -> int:
    env = os.environ.copy()
    shared_vault = project_root / "shared-vault"
    pythonpath = [str(project_root)]
    if shared_vault.is_dir():
        pythonpath.insert(0, str(shared_vault))
    existing = env.get("PYTHONPATH")
    if existing:
        pythonpath.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath)
    env["AUGUR_SYNC_PROJECT_ROOT"] = str(project_root)
    result = subprocess.run(
        [sys.executable, "-m", "skills.ai.scripts.sync_agents", "sync", "all"],
        cwd=project_root,
        env=env,
        check=False,
        text=True,
    )
    return result.returncode
```

- [ ] **Step 4: Run focused tests**

Run:

```text
/auto-test-pytest tests/unit/test_brain_init.py tests/unit/test_brain_manifest.py tests/unit/test_brain_context.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/lib/brain_init.py tests/unit/test_brain_init.py
git commit -m "feat: initialize project brains"
```

### Task 7: Wire `aug init` Into The CLI

**Files:**
- Modify: `src/cli.py`
- Modify: `tests/cli/test_cli_subcommands.py`

- [ ] **Step 1: Add CLI registration tests**

Append to `tests/cli/test_cli_subcommands.py`:

```python
    def test_cli_registers_builtin_init_subcommand(self):
        cli_source = (PROJECT_ROOT / "src" / "cli.py").read_text()
        assert "_register_builtin_subcommands" in cli_source
        assert "init_project_brain" in cli_source
        assert 'add_parser("init"' in cli_source
```

- [ ] **Step 2: Run test and confirm failure**

Run:

```text
/auto-test-pytest tests/cli/test_cli_subcommands.py -q
```

Expected before implementation: new source assertion fails.

- [ ] **Step 3: Add built-in init subcommand**

In `src/cli.py`, add these functions near the parser setup helpers:

```python
def _register_builtin_subcommands(subparsers: argparse._SubParsersAction) -> None:
    init = subparsers.add_parser("init", help="Create or attach a project brain in this folder")
    init.add_argument(
        "--project",
        default=".",
        help="Project root to initialize or attach (default: current directory)",
    )
    init.add_argument(
        "--no-sync",
        action="store_true",
        help="Skip generated AI-client projection sync.",
    )
    init.set_defaults(func=_handle_init)


def _handle_init(args: argparse.Namespace, remaining: list[str] | None = None) -> int:
    from src.lib.brain_init import init_project_brain

    result = init_project_brain(
        project_root=Path(args.project),
        run_sync=not args.no_sync,
    )
    action = "created" if result.created else "attached"
    print(f"Project brain {action}: {result.brain_id}")
    print(f"Brain root: {result.brain_root}")
    print(f"Attached project: {result.project_root}")
    if result.sync_returncode is not None:
        print(f"Projection sync exit code: {result.sync_returncode}")
    return 0 if result.sync_returncode in (None, 0) else int(result.sync_returncode)
```

Then call it before plugin discovery:

```python
    subparsers = parser.add_subparsers(dest="subcommand")
    _register_builtin_subcommands(subparsers)
```

- [ ] **Step 4: Run focused CLI tests**

Run:

```text
/auto-test-pytest tests/cli/test_cli_subcommands.py tests/unit/test_brain_init.py -q
```

Expected: pass.

- [ ] **Step 5: Run a real no-sync init smoke in a temp project**

Run through the CLI in a temp directory, not the repo root:

```text
tmp="$(mktemp -d)"
mkdir -p "$tmp/firmware"
AUGUR_STATE_DIR="$tmp/state" uv run aug init --project "$tmp/firmware" --no-sync
test -f "$tmp/firmware/project-brain/BRAIN.yaml"
test -f "$tmp/state/brains.yaml"
```

Expected: command prints `Project brain created: project-firmware`, and both test commands succeed.

- [ ] **Step 6: Commit**

```bash
git add src/cli.py tests/cli/test_cli_subcommands.py
git commit -m "feat: add project brain init command"
```

### Task 8: Add Path Helper Entry Points For Project Brain And Active Context

**Files:**
- Modify: `src/config/paths.py`
- Modify: `tests/config/test_brain_paths.py`

- [ ] **Step 1: Add path helper tests**

Append to `tests/config/test_brain_paths.py`:

```python
def test_get_project_brain_dir_returns_repo_project_brain(tmp_path: Path):
    from src.config.paths import get_project_brain_dir

    assert get_project_brain_dir(tmp_path) == tmp_path.resolve() / "project-brain"


def test_get_active_brain_context_uses_registry_and_cwd(isolated_state_dir: Path, tmp_path: Path):
    from src.config.paths import get_active_brain_context

    personal = Brain(
        id="personal",
        type=BrainType.PERSONAL,
        data_root=Path("/tmp/test-personal"),
        git=GitConfig(arrangement=GitArrangement.UNTRACKED),
    )
    save_registry(
        BrainRegistry(version=1, brains={"personal": personal}),
        isolated_state_dir / "brains.yaml",
    )
    clear_cache()

    ctx = get_active_brain_context(cwd=tmp_path)

    assert ctx.active_brain.id == "personal"
    assert ctx.attached_project is None
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```text
/auto-test-pytest tests/config/test_brain_paths.py -q
```

Expected before implementation: import failure for new helpers.

- [ ] **Step 3: Add helpers to `src/config/paths.py`**

Near existing brain helpers, add:

```python
def get_project_brain_dir(project_root: Path | None = None) -> Path:
    """Return the tracked project-brain root for a project."""
    from src.lib.brain_manifest import project_brain_root_for

    root = project_root.resolve() if project_root is not None else get_project_root().resolve()
    return project_brain_root_for(root)


def get_active_brain_context(
    *,
    cwd: Path | None = None,
    brain_id: str | None = None,
    project: Path | None = None,
):
    """Resolve active brain and attached project for the current invocation."""
    from src.lib.brain_context import resolve_active_context

    return resolve_active_context(
        cwd=cwd,
        explicit_brain=brain_id,
        explicit_project=project,
        registry_path=get_brain_registry_path(),
    )
```

- [ ] **Step 4: Run focused tests**

Run:

```text
/auto-test-pytest tests/config/test_brain_paths.py tests/unit/test_brain_context.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/config/paths.py tests/config/test_brain_paths.py
git commit -m "feat: expose active brain path helpers"
```

### Task 9: Tighten `/ask` Retention Policy

**Files:**
- Modify: `shared-vault/skills/augur-core/commands/ask.md`
- Add or modify: `shared-vault/skills/augur-core/augur/tests/test_ask_retention.py`

- [ ] **Step 1: Add command-policy regression**

Append to `shared-vault/skills/augur-core/augur/tests/test_ask_retention.py`:

```python
from pathlib import Path


def test_ask_command_does_not_retain_by_default():
    command = Path("shared-vault/skills/augur-core/commands/ask.md").read_text(encoding="utf-8")
    assert "/ask" in command
    assert "does not retain by default" in command
    assert "/ask --retain" in command
    assert "remember this" in command
```

- [ ] **Step 2: Run test and confirm failure**

Run:

```text
/auto-test-pytest shared-vault/skills/augur-core/augur/tests/test_ask_retention.py -q
```

Expected before doc edit: assertion failure for the new exact phrase.

- [ ] **Step 3: Update `/ask` command policy**

In `shared-vault/skills/augur-core/commands/ask.md`, replace the retention defaults in the workflow with this text:

```markdown
5. Identify the result as one or more of:
   - `decision`
   - `preference`
   - `insight`
   - `inferred-pattern`
   - `contradiction`
   - `open-question`
   - `ephemeral`
6. `/ask` does not retain by default.
   - If the user did not pass `--retain` and did not explicitly say
     "remember this", "save this to memory", "promote this", or equivalent,
     answer only and skip persistence.
   - `--private` and `--no-retain` also skip persistence.
7. If retention is explicit, call `ask-retain` with:
   - the final `question`
   - the final `answer`
   - any `explicit_signals`
   - any `inferred_signals`
   - the active `retain_mode`
   - `surface_footer: false`
   - optional explicit `kinds` when the conversation clearly warrants them
```

Also add under flags:

```markdown
- `remember this ...` / `save this to memory ...` — explicit retention intent
```

- [ ] **Step 4: Run focused test**

Run:

```text
/auto-test-pytest shared-vault/skills/augur-core/augur/tests/test_ask_retention.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/augur-core/commands/ask.md shared-vault/skills/augur-core/augur/tests/test_ask_retention.py
git commit -m "docs: make ask retention explicit"
```

### Task 10: Foundation Integration Verification

**Files:**
- No new source files.
- May update tests only if integration exposes a real gap.

- [ ] **Step 1: Run focused foundation test suite**

Run:

```text
/auto-test-pytest tests/unit/test_brain_registry_models.py tests/unit/test_brain_registry_io.py tests/unit/test_brain_manifest.py tests/unit/test_brain_mount.py tests/unit/test_brain_registry_bootstrap.py tests/unit/test_brain_context.py tests/unit/test_brain_init.py tests/config/test_brain_paths.py tests/cli/test_cli_subcommands.py shared-vault/skills/augur-core/augur/tests/test_ask_retention.py -q
```

Expected: pass.

- [ ] **Step 2: Run real temp-project init proof**

Run:

```text
tmp="$(mktemp -d)"
mkdir -p "$tmp/firmware"
AUGUR_STATE_DIR="$tmp/state" uv run aug init --project "$tmp/firmware" --no-sync
cat "$tmp/firmware/project-brain/BRAIN.yaml"
cat "$tmp/state/brains.yaml"
```

Expected concrete output:

```text
Project brain created: project-firmware
Brain root: <tmp>/firmware/project-brain
Attached project: <tmp>/firmware
```

`BRAIN.yaml` must contain `type: project`, and `brains.yaml` must include `project-firmware`.

- [ ] **Step 3: Run existing sync check without writing projections**

Run:

```text
/auto-test-pytest tests/sync_agents/test_skill_sync.py tests/integration/test_sync_agents.py -q
```

Expected: pass. If this fails because sync still assumes `.augur/BRAIN.yaml`, fix the caller to use root `BRAIN.yaml` and add a targeted regression before continuing.

- [ ] **Step 4: Run repository quality loop**

Run:

```text
/auto-test-pytest
```

Expected: pass, or report exact unrelated failures separately if the repo already has known failing tests.

- [ ] **Step 5: Commit final integration fixes if any**

If Step 1-4 required extra edits:

```bash
git add <changed-files>
git commit -m "test: verify project brain foundation"
```

If no extra edits were required, do not create an empty commit.

## Plan Self-Review

- Spec coverage in this foundation slice:
  - Three brain types: Task 1.
  - Root `BRAIN.yaml`: Tasks 2 and 3.
  - Project brain attachment/init: Tasks 4, 5, 6, 7, 8.
  - All detected client projection sync: Task 6 calls existing `sync_agents sync all`; Task 10 guards sync regressions.
  - `/ask` no default retention: Task 9.
  - Runtime/log/cache outside brain: preserved by not adding runtime content stores in this slice.
- Deferred by design:
  - Physical `shared-vault` migration.
  - Dashboard/UI discovery.
  - Full client projection canonical source migration.
  - Memory review UX.
