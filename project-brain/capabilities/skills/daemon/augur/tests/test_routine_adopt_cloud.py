"""Tests for routine_adopt_cloud_impl."""
from __future__ import annotations

import json
from pathlib import Path


def _seed_skill(tmp_path: Path) -> Path:
    skill_root = tmp_path / "project-brain" / "capabilities" / "skills" / "routine-codebase"
    seeds_dir = skill_root / "assets" / "seeds"
    seeds_dir.mkdir(parents=True)
    seed = seeds_dir / "routine-schedule.yaml"
    seed.write_text(
        "schedules:\n"
        "  - id: codex-dev-loop-testing\n"
        "    title: Testing\n"
        "    loop: testing\n"
        "    source: codex\n"
        '    rrule: "RRULE:FREQ=WEEKLY;BYDAY=SU;BYHOUR=3;BYMINUTE=0"\n'
        '    prompt: "/dev-loops run testing"\n'
        '    workspace: "__PROJECT_ROOT__"\n'
        '    model: "gpt-5.4"\n'
        '    reasoning_effort: "high"\n'
        "    runs_in: local\n",
        encoding="utf-8",
    )
    return seed


def test_adopt_codex_re_embeds_seed_hash_in_toml(tmp_path, monkeypatch) -> None:
    """After adoption, the TOML's augur_seed_hash matches the new seed.

    This verifies the round-trip contract: post-adoption drift check
    returns in-sync, not codex-edited.
    """
    import tomllib
    from src.lib.runtime.codex_automations import (
        compute_seed_hash,
        sync_codex_automations,
        _toml_fields_to_schedule_shape,
    )
    from src.mcp.augur_framework.tools.infrastructure.browse.scheduled_conflict import (
        adopt_cloud_impl,
    )

    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_skill(tmp_path)
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

    adopt_cloud_impl(
        routine_id="codex:codex-dev-loop-testing",
        seed_search_roots=[tmp_path / "project-brain" / "capabilities" / "skills"],
    )

    data = tomllib.loads(toml_path.read_text(encoding="utf-8"))
    embedded_hash = str(data.get("augur_seed_hash", ""))
    file_hash = compute_seed_hash(_toml_fields_to_schedule_shape(data))
    assert embedded_hash == file_hash, (
        "post-adopt drift should be in-sync; embedded hash must match "
        "the hash recomputed from the TOML fields"
    )


def test_adopt_codex_rewrites_seed_to_match_installed_toml(tmp_path, monkeypatch) -> None:
    from src.lib.runtime.codex_automations import sync_codex_automations
    from src.mcp.augur_framework.tools.infrastructure.browse.scheduled_conflict import (
        adopt_cloud_impl,
    )

    monkeypatch.setenv("HOME", str(tmp_path))
    seed = _seed_skill(tmp_path)
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

    result = adopt_cloud_impl(
        routine_id="codex:codex-dev-loop-testing",
        seed_search_roots=[tmp_path / "project-brain" / "capabilities" / "skills"],
    )

    payload = json.loads(result)
    assert payload["success"] is True
    import yaml

    seed_after = yaml.safe_load(seed.read_text(encoding="utf-8"))
    entry = seed_after["schedules"][0]
    assert entry["rrule"] == "RRULE:FREQ=WEEKLY;BYDAY=WE;BYHOUR=14;BYMINUTE=30"


def test_adopt_claude_remote_is_noop_success(tmp_path) -> None:
    from src.mcp.augur_framework.tools.infrastructure.browse.scheduled_conflict import (
        adopt_cloud_impl,
    )

    result = adopt_cloud_impl(
        routine_id="claude-remote:trig_abc",
        seed_search_roots=[tmp_path],
    )
    payload = json.loads(result)
    assert payload["success"] is True
    assert "no-op" in payload["message"].lower() or "no seed" in payload["message"].lower()


def test_adopt_unknown_routine_returns_error(tmp_path) -> None:
    from src.mcp.augur_framework.tools.infrastructure.browse.scheduled_conflict import (
        adopt_cloud_impl,
    )

    result = adopt_cloud_impl(
        routine_id="codex:does-not-exist",
        seed_search_roots=[tmp_path],
    )
    payload = json.loads(result)
    assert payload["success"] is False
    assert "not found" in payload["error"].lower()


def test_adopt_codex_response_includes_refreshed_browse_row(tmp_path, monkeypatch) -> None:
    """ADR-763 P1 follow-up: adopt's response payload must include an `items`
    array with the post-mutation Browse row so dashboard can clear the drift
    badge without re-fetching the whole listing."""
    from src.lib.runtime.codex_automations import sync_codex_automations
    from src.mcp.augur_framework.tools.infrastructure.browse.scheduled_conflict import (
        adopt_cloud_impl,
    )

    monkeypatch.setenv("HOME", str(tmp_path))
    seed = _seed_skill(tmp_path)
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

    result = adopt_cloud_impl(
        routine_id="codex:codex-dev-loop-testing",
        seed_search_roots=[tmp_path / "project-brain" / "capabilities" / "skills"],
    )
    payload = json.loads(result)

    assert payload["success"] is True
    items = payload.get("items", [])
    assert len(items) == 1, "adopt response should carry the refreshed Browse row"
    row = items[0]
    assert row["id"] == "codex:codex-dev-loop-testing"
    # After adopt, the seed was rewritten to match the TOML and the TOML's
    # augur_seed_hash was re-stamped. Drift should now report in-sync from
    # the TOML's perspective (file hash matches embedded hash).
    assert row["metadata"]["drift_status"] in ("in-sync", "seed-evolved"), (
        f"expected in-sync or seed-evolved after adopt, got {row['metadata']['drift_status']}"
    )
