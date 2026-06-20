from __future__ import annotations

from pathlib import Path


def test_keep_routes_existing_local_file_before_cloud(tmp_path: Path) -> None:
    from skills.ingest.scripts import keep_engine

    report = tmp_path / "report.pdf"
    report.write_text("pdf bytes", encoding="utf-8")

    route = keep_engine.plan_keep_route(str(report), cwd=tmp_path)

    assert route.kind == "file"
    assert route.route == "local-file"
    assert route.path == report
    assert route.warnings == []
    assert route.requires_confirmation is False


def test_keep_routes_relative_local_file_from_cwd(tmp_path: Path) -> None:
    from skills.ingest.scripts import keep_engine

    notes = tmp_path / "notes.md"
    notes.write_text("body", encoding="utf-8")

    route = keep_engine.plan_keep_route("notes.md", cwd=tmp_path)

    assert route.kind == "file"
    assert route.route == "local-file"
    assert route.path == notes


def test_keep_rejects_cloud_route_without_explicit_intent() -> None:
    from skills.ingest.scripts import keep_engine

    route = keep_engine.plan_keep_route("save the report through google drive")

    assert route.kind == "thought"
    assert route.route == "thought"
    assert "cloud-route-not-selected" in route.warnings


def test_keep_save_flag_routes_generated_artifact(tmp_path: Path) -> None:
    from skills.ingest.scripts import keep_engine

    artifact = tmp_path / "output.html"
    artifact.write_text("<h1>Demo</h1>", encoding="utf-8")

    route = keep_engine.plan_keep_route("--save output.html", cwd=tmp_path)

    assert route.kind == "artifact"
    assert route.route == "generated-artifact"
    assert route.path == artifact


def test_keep_save_flag_skips_explicit_destination_options(tmp_path: Path) -> None:
    from skills.ingest.scripts import keep_engine

    report = tmp_path / "report.md"
    report.write_text("# Report", encoding="utf-8")

    route = keep_engine.plan_keep_route("--save --to project-augur report.md", cwd=tmp_path)

    assert route.kind == "artifact"
    assert route.route == "generated-artifact"
    assert route.path == report
    assert route.warnings == []
    assert route.requires_confirmation is False


def test_keep_save_flag_ignores_natural_language_destination(tmp_path: Path) -> None:
    from skills.ingest.scripts import keep_engine

    banner = tmp_path / "banner.png"
    banner.write_text("png", encoding="utf-8")

    route = keep_engine.plan_keep_route("--save banner.png to venture", cwd=tmp_path)

    assert route.kind == "artifact"
    assert route.route == "generated-artifact"
    assert route.path == banner


def test_keep_artifact_mode_skips_trailing_hub_option(tmp_path: Path) -> None:
    from skills.ingest.scripts import keep_engine

    output = tmp_path / "output.html"
    output.write_text("<h1>Demo</h1>", encoding="utf-8")

    route = keep_engine.plan_keep_route("artifact output.html --hub dev", cwd=tmp_path)

    assert route.kind == "artifact"
    assert route.route == "generated-artifact"
    assert route.path == output


def test_keep_routes_existing_folder_from_cwd(tmp_path: Path) -> None:
    from skills.ingest.scripts import keep_engine

    folder = tmp_path / "notes"
    folder.mkdir()

    route = keep_engine.plan_keep_route("notes", cwd=tmp_path)

    assert route.kind == "folder"
    assert route.route == "local-folder"
    assert route.path == folder


def test_keep_empty_argument_routes_to_interactive_picker() -> None:
    from skills.ingest.scripts import keep_engine

    route = keep_engine.plan_keep_route("  ")

    assert route.kind == "interactive"
    assert route.route == "interactive-picker"
    assert route.requires_confirmation is True


def test_keep_routes_local_file_with_spaces_in_path(tmp_path: Path) -> None:
    """A file path containing spaces (Claude Desktop / macOS) routes to local-file.

    Claude Desktop and macOS paths routinely contain spaces ("Mobile Documents",
    "Claude Desktop Capture"). The route planner must treat the whole argument as a
    single path and choose the local-file route quickly — not shlex-split it into
    tokens and fall through to "thought" (or wander toward a cloud destination).
    """
    from skills.ingest.scripts import keep_engine

    spaced = tmp_path / "Claude Desktop Capture.md"
    spaced.write_text("dragged in from Claude Desktop", encoding="utf-8")

    route = keep_engine.plan_keep_route(str(spaced), cwd=tmp_path)

    assert route.kind == "file"
    assert route.route == "local-file"
    assert route.path == spaced
    assert route.warnings == []
    assert route.requires_confirmation is False


def test_keep_routes_local_folder_with_spaces_in_path(tmp_path: Path) -> None:
    from skills.ingest.scripts import keep_engine

    folder = tmp_path / "My Project Notes"
    folder.mkdir()

    route = keep_engine.plan_keep_route(str(folder), cwd=tmp_path)

    assert route.kind == "folder"
    assert route.route == "local-folder"
    assert route.path == folder


def test_keep_routes_shell_quoted_path_with_spaces(tmp_path: Path) -> None:
    """A shell-quoted single path with spaces must still route to local-file.

    Users paste quoted paths (e.g. `/keep "~/My Notes/Q3 Report.md"`). The whole-arg
    path check misses these (literal quotes), so the shlex single-token fallback must
    recover them rather than dropping to "thought".
    """
    from skills.ingest.scripts import keep_engine

    report = tmp_path / "Q3 Report.md"
    report.write_text("body", encoding="utf-8")

    route = keep_engine.plan_keep_route(f'"{report}"', cwd=tmp_path)

    assert route.kind == "file"
    assert route.route == "local-file"
    assert route.path == report


def test_keep_url_and_thought_routes_are_deterministic() -> None:
    from skills.ingest.scripts import keep_engine

    url = keep_engine.plan_keep_route("https://example.com/article")
    thought = keep_engine.plan_keep_route("Remember that the demo needs real data.")

    assert url.kind == "url"
    assert url.route == "url-capture"
    assert thought.kind == "thought"
    assert thought.route == "thought"
