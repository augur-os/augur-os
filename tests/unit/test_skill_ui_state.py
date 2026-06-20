from pathlib import Path

from src.plugins.skill_ui_state import (
    acknowledge_skill_in_dashboard,
    get_skill_ui_state_path,
    migrate_legacy_skill_config,
    mark_skill_new_to_dashboard,
    read_disabled_skills,
    read_skill_dashboard_state,
    set_skill_enabled,
)


def test_mark_skill_new_persists_runtime_dashboard_state(tmp_path: Path):
    runtime_dir = tmp_path / "runtime"

    mark_skill_new_to_dashboard("ingest", hub="workspace", runtime_dir=runtime_dir)

    state = read_skill_dashboard_state("ingest", runtime_dir=runtime_dir)
    assert state["is_new_to_dashboard"] is True
    assert state["hub"] == "workspace"
    assert state["first_seen_at"]
    assert get_skill_ui_state_path(runtime_dir).exists()


def test_acknowledge_skill_preserves_first_seen_and_clears_new_flag(tmp_path: Path):
    runtime_dir = tmp_path / "runtime"

    mark_skill_new_to_dashboard("ingest", hub="workspace", runtime_dir=runtime_dir)
    first = read_skill_dashboard_state("ingest", runtime_dir=runtime_dir)

    acknowledge_skill_in_dashboard("ingest", runtime_dir=runtime_dir)

    acknowledged = read_skill_dashboard_state("ingest", runtime_dir=runtime_dir)
    assert acknowledged["is_new_to_dashboard"] is False
    assert acknowledged["first_seen_at"] == first["first_seen_at"]
    assert acknowledged["acknowledged_at"]


def test_set_skill_enabled_tracks_disabled_skills_in_runtime_state(tmp_path: Path):
    runtime_dir = tmp_path / "runtime"

    set_skill_enabled("ingest", False, runtime_dir=runtime_dir)
    assert read_disabled_skills(runtime_dir=runtime_dir) == {"ingest"}

    set_skill_enabled("ingest", True, runtime_dir=runtime_dir)
    assert read_disabled_skills(runtime_dir=runtime_dir) == set()


def test_migrate_legacy_skill_config_moves_new_flag_to_runtime_state(tmp_path: Path):
    runtime_dir = tmp_path / "runtime"
    skill_dir = tmp_path / "skills" / "ingest"
    skill_dir.mkdir(parents=True)
    (skill_dir / ".config").write_text("enabled: true\nstatus: new\n", encoding="utf-8")

    migrated = migrate_legacy_skill_config(
        skill_dir,
        runtime_dir=runtime_dir,
        delete_file=True,
    )

    assert migrated is True
    assert not (skill_dir / ".config").exists()
    assert read_skill_dashboard_state("ingest", runtime_dir=runtime_dir)["is_new_to_dashboard"] is True
