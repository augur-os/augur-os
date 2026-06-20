"""Tests for ADR-758 Codex routine automation projection."""
from __future__ import annotations

import importlib.util as _augur_importlib_util
import sys as _augur_sys
import textwrap
import tomllib
from pathlib import Path as _AugurPath
from unittest.mock import patch

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
assert _augur_bootstrap_spec is not None and _augur_bootstrap_spec.loader is not None
_augur_bootstrap_module = _augur_importlib_util.module_from_spec(_augur_bootstrap_spec)
_augur_sys.modules[_augur_bootstrap_spec.name] = _augur_bootstrap_module
_augur_bootstrap_spec.loader.exec_module(_augur_bootstrap_module)
_augur_bootstrap_module.ensure_project_paths(__file__)

scripts_dir = _AugurPath(__file__).resolve().parents[2]
if str(scripts_dir) not in _augur_sys.path:
    _augur_sys.path.insert(0, str(scripts_dir))

from sync_agents.adapters.codex import CodexAdapter


def _write_routine_skill(
    skills_root: _AugurPath,
    name: str,
    *,
    routine_id: str,
    execution: str = "tiered",
    policy: str = "adaptive",
    prompt: str,
) -> _AugurPath:
    skill = skills_root / name
    (skill / "assets" / "seeds").mkdir(parents=True)
    callable_ref = "commands/dream.md" if execution == "inline-session" else "../daemon/scripts/routine_orchestrator/orchestrator.py"
    (skill / "SKILL.md").write_text(
        textwrap.dedent(
            f"""\
            ---
            name: {name}
            x-augur-routine:
              id: {routine_id}
              execution: {execution}
              policy: {policy}
              callable: {callable_ref}
              loop: {routine_id}
            ---
            """
        ),
        encoding="utf-8",
    )
    (skill / "assets" / "seeds" / "routine-schedule.yaml").write_text(
        textwrap.dedent(
            f"""\
            schedules:
              - id: codex-{routine_id}
                title: {routine_id}
                loop: {routine_id}
                source: codex
                rrule: RRULE:FREQ=DAILY;BYHOUR=3;BYMINUTE=0
                prompt: {prompt}
                workspace: __PROJECT_ROOT__
                model: gpt-5.4
                reasoning_effort: high
                runs_in: local
            """
        ),
        encoding="utf-8",
    )
    return skill


def test_sync_routine_automations_emits_all_skill_local_schedules(tmp_path: _AugurPath) -> None:
    project_root = tmp_path / "project"
    skills_root = project_root / "project-brain" / "capabilities" / "skills"
    skills_root.mkdir(parents=True)
    _write_routine_skill(skills_root, "routine-codebase", routine_id="testing", prompt="/dev-loops run testing")
    _write_routine_skill(
        skills_root,
        "dream",
        routine_id="dream",
        execution="inline-session",
        policy="oneshot",
        prompt="/dream",
    )
    config_path = tmp_path / "home" / ".codex" / "config.toml"
    adapter = CodexAdapter()

    with patch("sync_agents.adapters.codex.PROJECT_ROOT", project_root), patch(
        "sync_agents.adapters.codex.CODEX_HOME", config_path.parent
    ), patch.object(adapter, "_routine_registry_roots", return_value=[skills_root]):
        adapter._sync_routine_automations()

    testing = tomllib.loads(
        (tmp_path / "home" / ".codex" / "automations" / "codex-testing" / "automation.toml").read_text(
            encoding="utf-8"
        )
    )
    dream = tomllib.loads(
        (tmp_path / "home" / ".codex" / "automations" / "codex-dream" / "automation.toml").read_text(
            encoding="utf-8"
        )
    )
    assert testing["prompt"] == "/dev-loops run testing"
    assert dream["prompt"] == "/dream"
    assert testing["cwds"] == [str(project_root)]
    assert dream["cwds"] == [str(project_root)]


def test_legacy_dev_loop_method_delegates_to_routine_projection() -> None:
    adapter = CodexAdapter()
    with patch.object(adapter, "_sync_routine_automations") as sync:
        adapter._sync_dev_loop_automations()

    sync.assert_called_once_with(execution_models={"tiered"}, label="dev-loop", prune=False)


def test_legacy_dream_method_delegates_to_routine_projection() -> None:
    adapter = CodexAdapter()
    with patch.object(adapter, "_sync_routine_automations") as sync:
        adapter._sync_dream_automations()

    sync.assert_called_once_with(routine_ids={"dream"}, label="dream", prune=False)
