"""Tests that drifted routines emit Adopt/Push BrowseCardActions server-side."""
from __future__ import annotations

import json
from pathlib import Path


def test_drifted_codex_entry_emits_adopt_and_push_actions(tmp_path, monkeypatch) -> None:
    from src.lib.runtime.codex_automations import sync_codex_automations
    from src.mcp.augur_framework.tools.infrastructure.browse.scheduled_executions import (
        list_scheduled_execution_items,
    )

    monkeypatch.setenv("HOME", str(tmp_path))
    skill_root = tmp_path / "project-brain" / "capabilities" / "skills" / "routine-codebase"
    seeds_dir = skill_root / "assets" / "seeds"
    seeds_dir.mkdir(parents=True)
    (seeds_dir / "routine-schedule.yaml").write_text(
        "schedules:\n"
        "  - id: codex-dev-loop-testing\n"
        '    rrule: "RRULE:FREQ=WEEKLY;BYDAY=SU;BYHOUR=3;BYMINUTE=0"\n'
        '    prompt: "/dev-loops run testing"\n'
        '    workspace: "__PROJECT_ROOT__"\n'
        '    model: "gpt-5.4"\n'
        '    reasoning_effort: "high"\n'
        "    runs_in: local\n",
        encoding="utf-8",
    )
    schedules = [
        {
            "id": "codex-dev-loop-testing",
            "title": "Testing",
            "rrule": "RRULE:FREQ=WEEKLY;BYDAY=SU;BYHOUR=3;BYMINUTE=0",
            "prompt": "/dev-loops run testing",
            "workspace": str(tmp_path),
            "model": "gpt-5.4",
            "reasoning_effort": "high",
            "runs_in": "local",
        }
    ]
    sync_codex_automations(schedules, apply=True, prune=False)
    toml_path = tmp_path / ".codex" / "automations" / "codex-dev-loop-testing" / "automation.toml"
    body = toml_path.read_text(encoding="utf-8")
    body = body.replace(
        'rrule = "RRULE:FREQ=WEEKLY;BYDAY=SU;BYHOUR=3;BYMINUTE=0"',
        'rrule = "RRULE:FREQ=WEEKLY;BYDAY=WE;BYHOUR=14;BYMINUTE=30"',
    )
    toml_path.write_text(body, encoding="utf-8")

    items = list_scheduled_execution_items()
    testing = next(
        (it for it in items if it["id"] == "codex:codex-dev-loop-testing"), None
    )
    assert testing is not None, "expected the drifted codex entry"
    actions = testing.get("actions", [])
    labels = {str(a.get("label", "")) for a in actions}
    assert "Adopt surface version" in labels
    assert "Push my version" in labels
    adopt = next(a for a in actions if a["label"] == "Adopt surface version")
    assert adopt["type"] == "mcp-tool"
    assert adopt["target"] == "routine-adopt-cloud"
    assert adopt["args"] == {"routine_id": "codex:codex-dev-loop-testing"}


def test_seed_evolved_entry_arms_push_only_not_adopt(tmp_path, monkeypatch) -> None:
    """seed-evolved means Augur's intent moved on; user's surface still matches
    its old-intent hash. Adopting the surface would REVERT the seed change.
    Only Push (force-sync the new seed over the surface) makes sense."""
    from src.lib.runtime.codex_automations import sync_codex_automations
    from src.mcp.augur_framework.tools.infrastructure.browse.scheduled_executions import (
        list_scheduled_execution_items,
    )

    monkeypatch.setenv("HOME", str(tmp_path))
    skill_root = tmp_path / "project-brain" / "capabilities" / "skills" / "routine-codebase"
    seeds_dir = skill_root / "assets" / "seeds"
    seeds_dir.mkdir(parents=True)
    seed_path = seeds_dir / "routine-schedule.yaml"
    # Initial seed → write TOML embedding initial hash.
    seed_path.write_text(
        "schedules:\n"
        "  - id: codex-dev-loop-testing\n"
        '    rrule: "RRULE:FREQ=WEEKLY;BYDAY=SU;BYHOUR=3;BYMINUTE=0"\n'
        '    prompt: "/dev-loops run testing"\n'
        '    workspace: "__PROJECT_ROOT__"\n'
        '    model: "gpt-5.4"\n'
        '    reasoning_effort: "high"\n'
        "    runs_in: local\n",
        encoding="utf-8",
    )
    initial = [
        {
            "id": "codex-dev-loop-testing",
            "title": "Testing",
            "rrule": "RRULE:FREQ=WEEKLY;BYDAY=SU;BYHOUR=3;BYMINUTE=0",
            "prompt": "/dev-loops run testing",
            "workspace": str(tmp_path),
            "model": "gpt-5.4",
            "reasoning_effort": "high",
            "runs_in": "local",
        }
    ]
    sync_codex_automations(initial, apply=True, prune=False)
    # Now evolve the seed (Augur intent change) — but DON'T re-sync, so the
    # TOML still carries the embedded hash from the initial seed. This is
    # the seed-evolved state: TOML is hash-consistent with itself, but the
    # embedded hash no longer matches the current desired-seed hash.
    seed_path.write_text(
        "schedules:\n"
        "  - id: codex-dev-loop-testing\n"
        '    rrule: "RRULE:FREQ=WEEKLY;BYDAY=MO;BYHOUR=9;BYMINUTE=0"\n'
        '    prompt: "/dev-loops run testing"\n'
        '    workspace: "__PROJECT_ROOT__"\n'
        '    model: "gpt-5.4"\n'
        '    reasoning_effort: "high"\n'
        "    runs_in: local\n",
        encoding="utf-8",
    )

    items = list_scheduled_execution_items()
    testing = next(
        (it for it in items if it["id"] == "codex:codex-dev-loop-testing"), None
    )
    assert testing is not None
    assert testing["metadata"]["drift_status"] == "seed-evolved"
    labels = {str(a.get("label", "")) for a in testing.get("actions", [])}
    assert "Push my version" in labels, "seed-evolved must arm Push"
    assert "Adopt surface version" not in labels, (
        "seed-evolved must NOT arm Adopt — adopting would revert Augur's "
        "intent change back to the surface's stale state"
    )


def test_in_sync_entry_emits_no_conflict_actions(tmp_path, monkeypatch) -> None:
    """An in-sync entry must arm neither Adopt nor Push.

    `_load_desired_seeds` scans the real project root (not tmp_path), so to
    get a true in-sync row we sync a fixture schedule whose id matches a real
    seed file and whose hashable fields match that seed exactly. We use the
    live routine-codebase 'codex-dev-loop-testing' entry as the fixture and
    pass the real workspace (__PROJECT_ROOT__-expanded) so hashes align.
    """
    import yaml
    from src.config.paths import get_project_root
    from src.lib.runtime.codex_automations import sync_codex_automations
    from src.mcp.augur_framework.tools.infrastructure.browse.scheduled_executions import (
        list_scheduled_execution_items,
    )

    monkeypatch.setenv("HOME", str(tmp_path))
    seed_path = (
        get_project_root()
        / "project-brain"
        / "capabilities"
        / "skills"
        / "routine-codebase"
        / "assets"
        / "seeds"
        / "routine-schedule.yaml"
    )
    desired_seeds = yaml.safe_load(seed_path.read_text(encoding="utf-8")) or {}
    desired_entry = next(
        e for e in desired_seeds.get("schedules", [])
        if isinstance(e, dict) and e.get("id") == "codex-dev-loop-testing"
    )
    schedule = {
        "id": str(desired_entry["id"]),
        "title": str(desired_entry.get("title", "Testing")),
        "rrule": str(desired_entry["rrule"]),
        "prompt": str(desired_entry["prompt"]),
        # __PROJECT_ROOT__ in seed expands to project_root in
        # load_codex_schedule_seed; mirror that resolution here.
        "workspace": str(get_project_root()),
        "model": str(desired_entry["model"]),
        "reasoning_effort": str(desired_entry["reasoning_effort"]),
        "runs_in": "local",
    }
    sync_codex_automations([schedule], apply=True, prune=False)

    items = list_scheduled_execution_items()
    entry = next(
        (it for it in items if it["id"] == "codex:codex-dev-loop-testing"), None
    )
    assert entry is not None
    assert entry["metadata"]["drift_status"] == "in-sync"
    actions = entry.get("actions", [])
    labels = {str(a.get("label", "")) for a in actions}
    assert "Adopt surface version" not in labels
    assert "Push my version" not in labels
