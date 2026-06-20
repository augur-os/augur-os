"""Tests for seed_yaml_editor surgical YAML updates."""
from __future__ import annotations

import yaml


def test_update_existing_entry_changes_named_fields(tmp_path) -> None:
    from src.lib.runtime.seed_yaml_editor import update_seed_entry

    seed = tmp_path / "routine-schedule.yaml"
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

    changed = update_seed_entry(
        seed,
        schedule_id="codex-dev-loop-testing",
        new_fields={"rrule": "RRULE:FREQ=WEEKLY;BYDAY=WE;BYHOUR=14;BYMINUTE=30"},
    )

    assert changed is True
    payload = yaml.safe_load(seed.read_text(encoding="utf-8"))
    entry = payload["schedules"][0]
    assert entry["rrule"] == "RRULE:FREQ=WEEKLY;BYDAY=WE;BYHOUR=14;BYMINUTE=30"
    assert entry["prompt"] == "/dev-loops run testing"
    assert entry["model"] == "gpt-5.4"


def test_update_missing_id_returns_false(tmp_path) -> None:
    from src.lib.runtime.seed_yaml_editor import update_seed_entry

    seed = tmp_path / "routine-schedule.yaml"
    seed.write_text("schedules: []\n", encoding="utf-8")

    changed = update_seed_entry(seed, schedule_id="nope", new_fields={"rrule": "x"})

    assert changed is False
    assert seed.read_text(encoding="utf-8") == "schedules: []\n"


def test_update_preserves_other_entries(tmp_path) -> None:
    from src.lib.runtime.seed_yaml_editor import update_seed_entry

    seed = tmp_path / "routine-schedule.yaml"
    seed.write_text(
        "schedules:\n"
        "  - id: a\n"
        '    rrule: "RRULE:a"\n'
        "  - id: b\n"
        '    rrule: "RRULE:b"\n',
        encoding="utf-8",
    )

    update_seed_entry(seed, schedule_id="a", new_fields={"rrule": "RRULE:a-new"})

    payload = yaml.safe_load(seed.read_text(encoding="utf-8"))
    by_id = {row["id"]: row for row in payload["schedules"]}
    assert by_id["a"]["rrule"] == "RRULE:a-new"
    assert by_id["b"]["rrule"] == "RRULE:b"
