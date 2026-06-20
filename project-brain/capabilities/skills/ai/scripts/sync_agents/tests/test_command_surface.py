import sys
from pathlib import Path


scripts_dir = Path(__file__).resolve().parents[2]
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))


def test_inventory_collects_claude_cowork_and_build_command_sources(tmp_path):
    from sync_agents.command_surface import inventory_augur_command_surfaces

    project_root = tmp_path / "repo"
    repo_commands = project_root / ".claude" / "commands"
    repo_commands.mkdir(parents=True)
    (repo_commands / "wiki.md").write_text("---\nname: wiki\n---\n", encoding="utf-8")

    cowork_dir = tmp_path / "cowork_plugins"
    upload_commands = cowork_dir / "marketplaces" / "local-desktop-app-uploads" / "augur" / "commands"
    upload_commands.mkdir(parents=True)
    (upload_commands / "wiki.md").write_text("---\nname: wiki\n---\n", encoding="utf-8")

    cache_commands = cowork_dir / "cache" / "augur-cowork" / "commands"
    cache_commands.mkdir(parents=True)
    (cache_commands / "dev-loops.md").write_text("---\nname: dev-loops\n---\n", encoding="utf-8")

    build_commands = project_root / "build" / "cowork" / "plugins" / "augur" / "commands"
    build_commands.mkdir(parents=True)
    (build_commands / "ask.md").write_text("---\nname: ask\n---\n", encoding="utf-8")

    entries = inventory_augur_command_surfaces(project_root, cowork_plugin_dirs=[cowork_dir])

    assert [(entry.command, entry.source_class) for entry in entries] == [
        ("wiki", "claude-code-project"),
        ("ask", "cowork-build"),
        ("wiki", "cowork-upload"),
    ]


def test_find_duplicate_commands_reports_all_source_paths(tmp_path):
    from sync_agents.command_surface import (
        CommandSurfaceEntry,
        find_duplicate_commands,
    )

    entries = [
        CommandSurfaceEntry("wiki", "claude-code-project", tmp_path / ".claude" / "commands" / "wiki.md"),
        CommandSurfaceEntry("wiki", "cowork-upload", tmp_path / "cowork" / "commands" / "wiki.md"),
        CommandSurfaceEntry("ask", "cowork-upload", tmp_path / "cowork" / "commands" / "ask.md"),
    ]

    duplicates = find_duplicate_commands(entries)

    assert len(duplicates) == 1
    assert duplicates[0].command == "wiki"
    assert duplicates[0].suggested_owner == "claude-code-project"
    assert [source.source_class for source in duplicates[0].sources] == [
        "claude-code-project",
        "cowork-upload",
    ]


def test_find_duplicate_commands_reports_same_source_class_duplicates(tmp_path):
    from sync_agents.command_surface import (
        find_duplicate_commands,
        inventory_augur_command_surfaces,
    )

    project_root = tmp_path / "repo"
    first_cowork_dir = tmp_path / "cowork_a"
    second_cowork_dir = tmp_path / "cowork_b"
    first_upload_commands = (
        first_cowork_dir
        / "marketplaces"
        / "local-desktop-app-uploads"
        / "augur"
        / "commands"
    )
    second_upload_commands = (
        second_cowork_dir
        / "marketplaces"
        / "local-desktop-app-uploads"
        / "augur"
        / "commands"
    )
    first_upload_commands.mkdir(parents=True)
    second_upload_commands.mkdir(parents=True)
    (first_upload_commands / "wiki.md").write_text("---\nname: wiki\n---\n", encoding="utf-8")
    (second_upload_commands / "wiki.md").write_text("---\nname: wiki\n---\n", encoding="utf-8")

    entries = inventory_augur_command_surfaces(
        project_root,
        cowork_plugin_dirs=[first_cowork_dir, second_cowork_dir],
    )
    duplicates = find_duplicate_commands(entries)

    assert len(duplicates) == 1
    assert duplicates[0].command == "wiki"
    assert duplicates[0].suggested_owner == "cowork-upload"
    assert [source.source_class for source in duplicates[0].sources] == [
        "cowork-upload",
        "cowork-upload",
    ]


def test_format_duplicate_report_is_actionable(tmp_path):
    from sync_agents.command_surface import (
        CommandDuplicate,
        CommandSurfaceEntry,
        format_duplicate_report,
    )

    duplicate = CommandDuplicate(
        command="wiki",
        suggested_owner="claude-code-project",
        sources=[
            CommandSurfaceEntry("wiki", "claude-code-project", tmp_path / ".claude" / "commands" / "wiki.md"),
            CommandSurfaceEntry("wiki", "cowork-upload", tmp_path / "cowork" / "commands" / "wiki.md"),
        ],
    )

    report = format_duplicate_report([duplicate])

    assert "DUPLICATE /wiki" in report
    assert "owner: claude-code-project" in report
    assert "cowork-upload" in report
    assert str(tmp_path / "cowork" / "commands" / "wiki.md") in report


def test_format_duplicate_report_returns_no_duplicate_message():
    from sync_agents.command_surface import (
        NO_DUPLICATES_REPORT,
        format_duplicate_report,
    )

    assert format_duplicate_report([]) == NO_DUPLICATES_REPORT
