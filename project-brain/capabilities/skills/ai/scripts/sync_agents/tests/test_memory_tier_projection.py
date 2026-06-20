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

import sys
from pathlib import Path

scripts_dir = Path(__file__).resolve().parents[2]
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

from src.lib.brain_context import ActiveBrainContext
from src.lib.brain_registry_models import Brain, BrainType, GitArrangement, GitConfig
from src.lib.brain_stack import BrainStack
from sync_agents import constants, vault
from sync_agents.adapters import base as base_adapter
from sync_agents.adapters.base import BaseAdapter


def _brain(
    brain_id: str,
    brain_type: BrainType,
    root: Path,
    *,
    write_policy: str = "free",
    attached_project: Path | None = None,
) -> Brain:
    return Brain(
        id=brain_id,
        type=brain_type,
        data_root=root,
        git=(
            GitConfig(arrangement=GitArrangement.BUNDLED, host_repo=attached_project)
            if brain_type is BrainType.PROJECT and attached_project is not None
            else GitConfig(arrangement=GitArrangement.UNTRACKED)
        ),
        write_policy=write_policy,
        auto_activate_cwd_under=(attached_project,) if attached_project is not None else (),
    )


def _stack(tmp_path: Path) -> BrainStack:
    project_repo = tmp_path / "repo"
    project_brain = project_repo / "project-brain"
    return BrainStack(
        global_brain=_brain(
            "augur-core",
            BrainType.GLOBAL,
            tmp_path / "global",
            write_policy="read_only",
        ),
        user_brain=_brain("personal", BrainType.PERSONAL, tmp_path / "user"),
        project=ActiveBrainContext(
            active_brain=_brain(
                "project-repo",
                BrainType.PROJECT,
                project_brain,
                attached_project=project_repo,
            ),
            attached_project=project_repo,
            source="test",
        ),
    )


def _write_entry(memory_dir: Path, filename: str, *, name: str, description: str) -> None:
    entries_dir = memory_dir / "entries"
    entries_dir.mkdir(parents=True, exist_ok=True)
    (entries_dir / filename).write_text(
        "\n".join(
            [
                "---",
                f"name: {name}",
                f"description: {description}",
                "type: insight",
                "---",
                "",
                description,
            ]
        ),
        encoding="utf-8",
    )


def test_base_adapter_projects_compact_handoff_to_client_memory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    stack = _stack(tmp_path)
    user_memory = tmp_path / "user" / "memory"
    project_memory = tmp_path / "repo" / "project-brain" / "knowledge" / "memory"
    _write_entry(user_memory, "shared.md", name="shared", description="from user")
    _write_entry(project_memory, "shared.md", name="shared", description="from project")

    monkeypatch.setattr(constants, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(base_adapter, "PROJECT_ROOT", tmp_path, raising=False)
    monkeypatch.setattr(base_adapter, "resolve_active_stack", lambda *, cwd=None: stack)

    class CursorLikeAdapter(BaseAdapter):
        adapter_name = "cursor"

    CursorLikeAdapter().sync_memory()

    projected = tmp_path / ".cursor" / "memory" / "augur-memory.md"
    assert projected.is_file()
    text = projected.read_text(encoding="utf-8")
    assert "# Augur Cross-Client Handoff" in text
    assert "Full recall is pull-based" in text
    assert "from project" in text
    assert "from user" not in text
    assert "tier=project" in text


def test_base_adapter_legacy_memory_fallback_stays_compact(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import src.config.paths as paths

    legacy_dir = tmp_path / "legacy-memory"
    legacy_dir.mkdir()
    (legacy_dir / "MEMORY.md").write_text(
        "\n".join(
            [
                "# Augur Memory",
                "",
                "- **one**: first item",
                "- **two**: second item",
                "- **three**: third item",
            ]
        ),
        encoding="utf-8",
    )

    def _fail_resolve_stack(*, cwd=None):
        raise RuntimeError("tier resolver unavailable")

    monkeypatch.setattr(base_adapter, "resolve_active_stack", _fail_resolve_stack)
    monkeypatch.setattr(paths, "get_memory_dir", lambda: legacy_dir)

    content = base_adapter.projected_memory_content(tmp_path)

    assert content is not None
    assert "# Augur Cross-Client Handoff" in content
    assert "legacy Augur memory" in content
    assert "- **one**: first item" in content
    assert "Tiered Memory Union" not in content


def test_memory_review_target_uses_most_specific_writable_tier(
    tmp_path: Path,
    monkeypatch,
) -> None:
    stack = _stack(tmp_path)
    monkeypatch.setattr(vault, "resolve_active_stack", lambda *, cwd=None: stack)

    target = vault._resolve_memory_review_target(tmp_path)

    assert target.brain.id == "project-repo"
    assert target.memory_dir == tmp_path / "repo" / "project-brain" / "knowledge" / "memory"
