from __future__ import annotations

import json
import sqlite3

import yaml


def test_browse_index_returns_dynamic_background_routine_rows(monkeypatch) -> None:
    from src.mcp.augur_framework.tools.infrastructure.browse.index import browse_index_impl

    monkeypatch.setattr(
        "src.mcp.augur_framework.tools.infrastructure.browse.background_routines.list_background_routine_items",
        lambda search=None: [
            {
                "id": "insight_scanner",
                "title": "Insight Scanner",
                "description": "Scans dashboard pages with Claude",
                "hub": "system",
                "type": "loops",
                "source_path": "project-brain/capabilities/skills/daemon/scripts/insight_scanner.py",
                "metadata": {
                    "source_kind": "daemon-script",
                    "spawn_kind": "ai-cli-spawn",
                    "status": "enabled",
                    "cadence": "triggered by daemon-service or other",
                },
            }
        ],
    )
    # browse_index merges scheduled executions into the loops
    # category; isolate that source so the count reflects only the routine rows.
    monkeypatch.setattr(
        "src.mcp.augur_framework.tools.infrastructure.browse.scheduled_executions.list_scheduled_execution_items",
        lambda search=None: [],
    )

    payload = json.loads(browse_index_impl("loops"))
    assert payload["count"] == 1
    assert payload["items"][0]["metadata"]["source_kind"] == "daemon-script"
    assert payload["items"][0]["type"] == "loops"


def test_scheduled_execution_detail_returns_not_found_for_unknown_id() -> None:
    from src.mcp.augur_framework.tools.infrastructure.browse.scheduled_executions import get_scheduled_execution_detail_impl

    payload = json.loads(get_scheduled_execution_detail_impl("codex:missing"))
    assert payload["success"] is False
    assert payload["error"] == "Scheduled execution 'codex:missing' not found"


def test_load_codex_schedules_reads_toml_and_runtime_state(tmp_path, monkeypatch) -> None:
    home = tmp_path / "home"
    automation_dir = home / ".codex" / "automations" / "update-agents-md"
    sqlite_dir = home / ".codex" / "sqlite"
    automation_dir.mkdir(parents=True)
    sqlite_dir.mkdir(parents=True)

    (automation_dir / "automation.toml").write_text(
        """name = "Update AGENTS.md"
prompt = "Update AGENTS.md with newly discovered workflows/commands"
model = "gpt-5.4"
rrule = "RRULE:FREQ=WEEKLY;BYDAY=SU;BYHOUR=11;BYMINUTE=0"
cwds = ["/Users/example/Projects/Augur"]
""",
        encoding="utf-8",
    )

    db = sqlite3.connect(sqlite_dir / "codex-dev.db")
    db.execute(
        "create table automations (automation_id text primary key, status text, last_run_at text, next_run_at text)"
    )
    db.execute(
        "insert into automations values (?, ?, ?, ?)",
        (
            "update-agents-md",
            "ACTIVE",
            "2026-04-12T08:00:25.728000+00:00",
            "2026-04-19T08:00:00+00:00",
        ),
    )
    db.commit()
    db.close()

    monkeypatch.setenv("HOME", str(home))

    from src.mcp.augur_framework.tools.infrastructure.browse.scheduled_sources.codex import load_codex_schedules

    rows = load_codex_schedules()
    assert rows[0]["id"] == "codex:update-agents-md"
    assert rows[0]["status"] == "active"
    assert rows[0]["raw_schedule"]["value"].startswith("RRULE:")
    assert rows[0]["last_run_at"] == "2026-04-12T08:00:25.728000+00:00"


def test_load_codex_schedules_skips_malformed_toml(tmp_path, monkeypatch) -> None:
    home = tmp_path / "home"
    valid_dir = home / ".codex" / "automations" / "valid-schedule"
    broken_dir = home / ".codex" / "automations" / "broken-schedule"
    valid_dir.mkdir(parents=True)
    broken_dir.mkdir(parents=True)

    (valid_dir / "automation.toml").write_text(
        'name = "Valid Schedule"\nprompt = "Run valid schedule"\n',
        encoding="utf-8",
    )
    (broken_dir / "automation.toml").write_text(
        'name = "Broken Schedule"\nprompt = [\n',
        encoding="utf-8",
    )

    monkeypatch.setenv("HOME", str(home))

    from src.mcp.augur_framework.tools.infrastructure.browse.scheduled_sources.codex import load_codex_schedules

    rows = load_codex_schedules()
    assert [row["id"] for row in rows] == ["codex:valid-schedule"]


def test_load_codex_schedules_supports_current_runtime_schema(tmp_path, monkeypatch) -> None:
    home = tmp_path / "home"
    automation_dir = home / ".codex" / "automations" / "update-agents-md"
    sqlite_dir = home / ".codex" / "sqlite"
    automation_dir.mkdir(parents=True)
    sqlite_dir.mkdir(parents=True)

    (automation_dir / "automation.toml").write_text(
        """id = "update-agents-md"
name = "Update AGENTS.md"
prompt = "Update AGENTS.md with newly discovered workflows/commands"
status = "ACTIVE"
model = "gpt-5.4"
rrule = "RRULE:FREQ=WEEKLY;BYDAY=SU;BYHOUR=11;BYMINUTE=0"
cwds = ["/Users/example/Projects/Augur"]
""",
        encoding="utf-8",
    )

    db = sqlite3.connect(sqlite_dir / "codex-dev.db")
    db.execute(
        """
        create table automations (
            id text primary key,
            name text,
            prompt text,
            status text,
            next_run_at integer,
            last_run_at integer,
            cwds text,
            rrule text,
            created_at integer,
            updated_at integer,
            model text,
            reasoning_effort text
        )
        """
    )
    db.execute(
        "insert into automations values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "update-agents-md",
            "Update AGENTS.md",
            "Update AGENTS.md with newly discovered workflows/commands",
            "ACTIVE",
            1776585600000,
            1775980825728,
            '["/Users/example/Projects/Augur"]',
            "RRULE:FREQ=WEEKLY;BYDAY=SU;BYHOUR=11;BYMINUTE=0",
            1775944478647,
            1775944478647,
            "gpt-5.4",
            "high",
        ),
    )
    db.commit()
    db.close()

    monkeypatch.setenv("HOME", str(home))

    from src.mcp.augur_framework.tools.infrastructure.browse.scheduled_sources.codex import load_codex_schedules

    rows = load_codex_schedules()
    assert rows[0]["id"] == "codex:update-agents-md"
    assert rows[0]["status"] == "active"
    assert rows[0]["last_run_at"] == "2026-04-12T08:00:25.728000+00:00"
    assert rows[0]["next_run_at"] == "2026-04-19T08:00:00+00:00"


def test_codex_loader_exposes_execution_environment_and_non_local_warning(
    tmp_path, monkeypatch
) -> None:
    home = tmp_path / "home"
    automation_dir = home / ".codex" / "automations" / "non-local"
    automation_dir.mkdir(parents=True)
    (automation_dir / "automation.toml").write_text(
        """version = 1
id = "non-local"
kind = "cron"
name = "Non Local"
prompt = "/dev-loops run testing"
status = "ACTIVE"
rrule = "RRULE:FREQ=DAILY;BYHOUR=3;BYMINUTE=0"
model = "gpt-5.4"
reasoning_effort = "high"
execution_environment = "remote"
cwds = ["/Users/example/Projects/Augur"]
""",
        encoding="utf-8",
    )
    monkeypatch.setattr("pathlib.Path.home", lambda: home)

    from src.mcp.augur_framework.tools.infrastructure.browse.scheduled_sources.codex import load_codex_schedules

    record = load_codex_schedules()[0]
    assert record["execution_environment"] == "remote"
    assert record["warnings"] == [
        "Codex schedule is not local; cutover is blocked until execution_environment = local."
    ]


def test_load_claude_schedules_reads_prompt_body_and_warning(tmp_path, monkeypatch) -> None:
    home = tmp_path / "home"
    support = (
        home
        / "Library"
        / "Application Support"
        / "Claude"
        / "local-agent-mode-sessions"
        / "session-a"
        / "window-a"
    )
    prompt_dir = home / "Documents" / "Claude" / "Scheduled" / "claude-second-brain-report"
    support.mkdir(parents=True)
    prompt_dir.mkdir(parents=True)

    (support / "scheduled-tasks.json").write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "claude-second-brain-report",
                        "enabled": True,
                        "cronExpression": "0 16 * * 5",
                        "model": "claude-opus-4-6",
                        "filePath": "~/Documents/Claude/Scheduled/claude-second-brain-report/SKILL.md",
                        "createdAt": 1775982575820,
                        "userSelectedFolders": ["/Users/example/Projects/Augur"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (prompt_dir / "SKILL.md").write_text(
        "---\nname: claude-second-brain-report\n---\nRun `/wiki report --style demo`.\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("HOME", str(home))

    from src.mcp.augur_framework.tools.infrastructure.browse.scheduled_sources.claude import load_claude_schedules

    rows = load_claude_schedules()
    assert rows[0]["id"] == "claude:claude-second-brain-report"
    assert rows[0]["native_id"] == "claude-second-brain-report"
    assert rows[0]["prompt_body"].startswith("---")
    assert rows[0]["prompt_summary"] == "Run `/wiki report --style demo`."
    assert rows[0]["last_run_at"] is None
    assert rows[0]["next_run_at"] is None
    assert rows[0]["source_path"] == str(prompt_dir / "SKILL.md")
    assert rows[0]["warnings"] == [
        "Claude schedule interpretation is provisional until timezone semantics are verified."
    ]


def test_load_claude_schedules_skips_malformed_json(tmp_path, monkeypatch) -> None:
    home = tmp_path / "home"
    sessions_root = (
        home
        / "Library"
        / "Application Support"
        / "Claude"
        / "local-agent-mode-sessions"
    )
    broken_dir = sessions_root / "session-a" / "window-a"
    valid_dir = sessions_root / "session-b" / "window-b"
    broken_dir.mkdir(parents=True)
    valid_dir.mkdir(parents=True)

    (broken_dir / "scheduled-tasks.json").write_text('{"tasks": [', encoding="utf-8")
    (valid_dir / "scheduled-tasks.json").write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "valid-claude-task",
                        "enabled": True,
                        "cronExpression": "0 16 * * 5",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("HOME", str(home))

    from src.mcp.augur_framework.tools.infrastructure.browse.scheduled_sources.claude import load_claude_schedules

    rows = load_claude_schedules()
    assert [row["id"] for row in rows] == ["claude:valid-claude-task"]


def test_load_claude_schedules_handles_blank_or_missing_filepath(tmp_path, monkeypatch) -> None:
    home = tmp_path / "home"
    support = (
        home
        / "Library"
        / "Application Support"
        / "Claude"
        / "local-agent-mode-sessions"
        / "session-a"
        / "window-a"
    )
    support.mkdir(parents=True)

    (support / "scheduled-tasks.json").write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "blank-filepath-task",
                        "enabled": True,
                        "filePath": "",
                    },
                    {
                        "id": "missing-file-task",
                        "enabled": False,
                        "filePath": "~/Documents/Claude/Scheduled/missing/SKILL.md",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("HOME", str(home))

    from src.mcp.augur_framework.tools.infrastructure.browse.scheduled_sources.claude import load_claude_schedules

    rows = load_claude_schedules()
    assert [row["id"] for row in rows] == [
        "claude:blank-filepath-task",
        "claude:missing-file-task",
    ]
    assert rows[0]["prompt_body"] == ""
    assert rows[0]["source_path"] == ""
    assert rows[0]["prompt_summary"] == ""
    assert "metadata" not in rows[0]
    assert "hub" not in rows[0]
    assert rows[1]["prompt_body"] == ""


def test_load_claude_schedules_skips_non_dict_task_entries(tmp_path, monkeypatch) -> None:
    home = tmp_path / "home"
    support = (
        home
        / "Library"
        / "Application Support"
        / "Claude"
        / "local-agent-mode-sessions"
        / "session-a"
        / "window-a"
    )
    support.mkdir(parents=True)

    (support / "scheduled-tasks.json").write_text(
        json.dumps(
            {
                "tasks": [
                    None,
                    1,
                    {
                        "id": "ok",
                        "enabled": True,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("HOME", str(home))

    from src.mcp.augur_framework.tools.infrastructure.browse.scheduled_sources.claude import load_claude_schedules

    rows = load_claude_schedules()
    assert [row["id"] for row in rows] == ["claude:ok"]


def test_codex_routine_schedule_manifests_contain_split_nightly_jobs() -> None:
    from src.lib.runtime.codex_automations import discover_codex_schedule_seeds

    ids: list[str] = []
    for seed in discover_codex_schedule_seeds():
        payload = yaml.safe_load(seed.read_text(encoding="utf-8")) or {}
        ids.extend(row["id"] for row in payload.get("schedules", []))

    # Codex schedule bindings were intentionally trimmed (commit 36d9da038):
    # routines now owned by Claude /schedule remote (dream, skill-quality) or no
    # longer scheduled (hardening, knowledge-enrichment, page-health,
    # observability, command-evolution, ...) dropped their Codex seed entry. The
    # routines remain declared in their owning skills; only the Codex binding is
    # gone.
    kept_codex_bindings = {
        "codex-dev-loop-testing",
        "codex-dev-loop-code-quality",
        "codex-dev-loop-duplication",
    }
    assert kept_codex_bindings <= set(ids)

    dropped_codex_bindings = {
        "codex-dream-overnight",
        "codex-knowledge-enrichment-nightly",
        "codex-dev-loop-hardening",
        "codex-dev-loop-page-health",
        "codex-command-evolution-drain",
    }
    assert dropped_codex_bindings.isdisjoint(set(ids))
