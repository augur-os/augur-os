"""Tests for Codex automation.toml sync generation."""
from __future__ import annotations

from pathlib import Path

import pytest


def test_codex_automations_imports_without_dateutil(monkeypatch) -> None:
    import builtins
    import importlib
    import sys

    original_import = builtins.__import__

    def blocked_import(name, *args, **kwargs):
        if name == "dateutil" or name.startswith("dateutil."):
            raise ModuleNotFoundError("No module named 'dateutil'")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked_import)
    sys.modules.pop("src.lib.runtime.codex_automations", None)
    for module_name in list(sys.modules):
        if module_name == "dateutil" or module_name.startswith("dateutil."):
            sys.modules.pop(module_name)

    module = importlib.import_module("src.lib.runtime.codex_automations")

    assert module._compute_next_run_at_ms("RRULE:FREQ=DAILY;BYHOUR=3;BYMINUTE=55") is not None


def test_sync_codex_automations_writes_local_execution_environment(tmp_path, monkeypatch) -> None:
    from src.lib.runtime.codex_automations import sync_codex_automations

    monkeypatch.setenv("HOME", str(tmp_path))
    schedules = [
        {
            "id": "codex-command-evolution-drain",
            "title": "Command Evolution Drain",
            "rrule": "RRULE:FREQ=MINUTELY;INTERVAL=15",
            "prompt": "/routines run command-evolution --drain",
            "workspace": "/Users/example/Projects/Augur",
            "model": "gpt-5.4",
            "reasoning_effort": "high",
            "runs_in": "local",
        }
    ]

    written = sync_codex_automations(schedules, apply=True)
    automation_toml = (
        Path(tmp_path)
        / ".codex"
        / "automations"
        / "codex-command-evolution-drain"
        / "automation.toml"
    )

    assert written == [automation_toml]
    content = automation_toml.read_text(encoding="utf-8")
    assert 'execution_environment = "local"' in content
    assert 'prompt = "/routines run command-evolution --drain"' in content
    assert 'cwds = ["/Users/example/Projects/Augur"]' in content
    assert 'reasoning_effort = "high"' in content
    assert 'model = "gpt-5.4"' in content
    assert "created_at = " in content
    assert "updated_at = " in content

    import sqlite3

    db = sqlite3.connect(tmp_path / ".codex" / "sqlite" / "codex-dev.db")
    row = db.execute(
        "select status, next_run_at, model, reasoning_effort from automations where id = ?",
        ("codex-command-evolution-drain",),
    ).fetchone()
    db.close()

    assert row is not None
    assert row[0] == "ACTIVE"
    assert row[1] is not None
    assert row[2] == "gpt-5.4"
    assert row[3] == "high"


def test_sync_codex_automations_dry_run_does_not_write_files(tmp_path, monkeypatch) -> None:
    from src.lib.runtime.codex_automations import sync_codex_automations

    monkeypatch.setenv("HOME", str(tmp_path))
    schedules = [
        {
            "id": "codex-dev-loop-testing",
            "title": "Testing",
            "rrule": "RRULE:FREQ=WEEKLY;BYDAY=SU;BYHOUR=3;BYMINUTE=0",
            "prompt": "/routines run testing",
            "workspace": "/Users/example/Projects/Augur",
            "model": "gpt-5.4",
            "reasoning_effort": "high",
            "runs_in": "local",
        }
    ]

    written = sync_codex_automations(schedules, apply=False)

    assert written == [
        Path(tmp_path)
        / ".codex"
        / "automations"
        / "codex-dev-loop-testing"
        / "automation.toml"
    ]
    assert not written[0].exists()


def test_sync_codex_automations_removes_stale_augur_managed_entries(tmp_path, monkeypatch) -> None:
    from src.lib.runtime.codex_automations import sync_codex_automations

    monkeypatch.setenv("HOME", str(tmp_path))
    stale_dir = tmp_path / ".codex" / "automations" / "codex-dev-loop-old"
    stale_dir.mkdir(parents=True)
    (stale_dir / "automation.toml").write_text(
        'id = "codex-dev-loop-old"\nmanaged_by = "augur"\n',
        encoding="utf-8",
    )
    unmanaged_dir = tmp_path / ".codex" / "automations" / "update-agents-md"
    unmanaged_dir.mkdir(parents=True)
    (unmanaged_dir / "automation.toml").write_text(
        'id = "update-agents-md"\nmanaged_by = "manual"\n',
        encoding="utf-8",
    )
    import sqlite3

    sqlite_dir = tmp_path / ".codex" / "sqlite"
    sqlite_dir.mkdir(parents=True)
    db = sqlite3.connect(sqlite_dir / "codex-dev.db")
    db.execute(
        """
        create table automations (
            id text primary key,
            name text not null,
            prompt text not null,
            status text not null default 'ACTIVE',
            next_run_at integer,
            last_run_at integer,
            cwds text not null default '[]',
            rrule text not null default 'FREQ=HOURLY;INTERVAL=24;BYMINUTE=0',
            created_at integer not null,
            updated_at integer not null,
            model text,
            reasoning_effort text
        )
        """
    )
    db.execute(
        "insert into automations values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "codex-dev-loop-old",
            "Old",
            "Old prompt",
            "ACTIVE",
            None,
            None,
            "[]",
            "RRULE:FREQ=DAILY;BYHOUR=1;BYMINUTE=0",
            1,
            1,
            "gpt-5.4",
            "high",
        ),
    )
    db.commit()
    db.close()

    sync_codex_automations(
        [
            {
                "id": "codex-dev-loop-testing",
                "title": "Testing",
                "rrule": "RRULE:FREQ=WEEKLY;BYDAY=SU;BYHOUR=3;BYMINUTE=0",
                "prompt": "/routines run testing",
                "workspace": str(tmp_path / "repo"),
                "model": "gpt-5.4",
                "reasoning_effort": "high",
                "runs_in": "local",
            }
        ],
        apply=True,
    )

    assert not stale_dir.exists()
    assert unmanaged_dir.exists()
    db = sqlite3.connect(sqlite_dir / "codex-dev.db")
    stale_row = db.execute(
        "select id from automations where id = ?",
        ("codex-dev-loop-old",),
    ).fetchone()
    db.close()
    assert stale_row is None


def test_load_codex_schedule_seed_rejects_non_mapping_rows(tmp_path) -> None:
    from src.lib.runtime.codex_automations import load_codex_schedule_seed

    seed_path = tmp_path / "seed.yaml"
    seed_path.write_text(
        "schedules:\n"
        "  - id: codex-dev-loop-testing\n"
        "    rrule: RRULE:FREQ=WEEKLY;BYDAY=SU;BYHOUR=3;BYMINUTE=0\n"
        "    prompt: /routines run testing\n"
        "    model: gpt-5.4\n"
        "    reasoning_effort: high\n"
        "    runs_in: local\n"
        "  - not-a-mapping\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="expected mapping"):
        load_codex_schedule_seed(seed_path, project_root=tmp_path / "repo")


def test_load_codex_schedule_seed_resolves_project_root_placeholder(tmp_path) -> None:
    from src.lib.runtime.codex_automations import load_codex_schedule_seed

    project_root = tmp_path / "repo"
    seed_path = tmp_path / "seed.yaml"
    seed_path.write_text(
        "schedules:\n"
        "  - id: codex-dev-loop-testing\n"
        "    rrule: RRULE:FREQ=WEEKLY;BYDAY=SU;BYHOUR=3;BYMINUTE=0\n"
        "    prompt: /routines run testing\n"
        "    workspace: __PROJECT_ROOT__\n"
        "    model: gpt-5.4\n"
        "    reasoning_effort: high\n"
        "    runs_in: local\n",
        encoding="utf-8",
    )

    schedules = load_codex_schedule_seed(seed_path, project_root=project_root)

    assert schedules[0]["workspace"] == str(project_root)
