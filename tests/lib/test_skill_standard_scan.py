from __future__ import annotations

from pathlib import Path

from src.lib.skill_standard_scan import Severity, scan_skill_roots


def _write_skill(root: Path, name: str, body: str) -> Path:
    skill_dir = root / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(body, encoding="utf-8")
    return skill_dir


def test_shared_invalid_surface_is_failure(tmp_path: Path) -> None:
    shared = tmp_path / "project-brain" / "capabilities" / "skills"
    private = tmp_path / "vault" / "skills"
    _write_skill(
        shared,
        "audio-ingest",
        "---\n"
        "name: audio-ingest\n"
        "description: Audio.\n"
        "x-augur:\n"
        "  tools:\n"
        "    - name: audio-classify\n"
        "      surface: mcp-tool\n"
        "---\n",
    )

    report = scan_skill_roots(shared_root=shared, private_root=private)

    assert report.fail_count == 1
    assert report.warn_count == 0
    assert report.issues[0].severity is Severity.FAIL
    assert report.issues[0].code == "invalid-tool-surface"


def test_shared_skill_surface_tool_is_failure(tmp_path: Path) -> None:
    shared = tmp_path / "project-brain" / "capabilities" / "skills"
    private = tmp_path / "vault" / "skills"
    _write_skill(
        shared,
        "audio-ingest",
        "---\n"
        "name: audio-ingest\n"
        "description: Audio.\n"
        "x-augur:\n"
        "  tools:\n"
        "    - name: audio-classify\n"
        "      surface: skill\n"
        "---\n",
    )

    report = scan_skill_roots(shared_root=shared, private_root=private)

    assert report.fail_count == 1
    assert report.warn_count == 0
    assert report.issues[0].severity is Severity.FAIL
    assert report.issues[0].code == "invalid-tool-surface"
    assert report.issues[0].suggested_fix == ("Change surface to one of: cli, mcp, mcp via dashboard.")


def test_private_invalid_surface_is_warning(tmp_path: Path) -> None:
    shared = tmp_path / "project-brain" / "capabilities" / "skills"
    private = tmp_path / "vault" / "skills"
    _write_skill(
        private,
        "file-manager",
        "---\n"
        "name: file-manager\n"
        "description: Private files.\n"
        "x-augur:\n"
        "  tools:\n"
        "    - name: get-pending\n"
        "      surface: mcp-tool\n"
        "---\n",
    )

    report = scan_skill_roots(shared_root=shared, private_root=private)

    assert report.fail_count == 0
    assert report.warn_count == 1
    assert report.issues[0].severity is Severity.WARN
    assert report.issues[0].suggested_fix == ("Change surface to one of: cli, mcp, mcp via dashboard.")


def test_banned_shared_root_dir_is_failure(tmp_path: Path) -> None:
    shared = tmp_path / "project-brain" / "capabilities" / "skills"
    private = tmp_path / "vault" / "skills"
    skill_dir = _write_skill(
        shared,
        "knowledge",
        "---\nname: knowledge\ndescription: Knowledge.\n---\n",
    )
    (skill_dir / "docs").mkdir()

    report = scan_skill_roots(shared_root=shared, private_root=private)

    assert report.fail_count == 1
    assert report.issues[0].code == "banned-root-dir"
    assert report.issues[0].suggested_fix == "Move docs/ to references/."


def test_overlapping_roots_scan_once_and_use_normalized_ownership(
    tmp_path: Path,
) -> None:
    skills = tmp_path / "skills"
    _write_skill(
        skills,
        "file-manager",
        "---\n"
        "name: file-manager\n"
        "description: Private files.\n"
        "x-augur:\n"
        "  tools:\n"
        "    - name: get-pending\n"
        "      surface: mcp-tool\n"
        "---\n",
    )

    report = scan_skill_roots(shared_root=skills, private_root=skills)

    assert report.skills_scanned == 1
    assert report.fail_count == 0
    assert report.warn_count == 1
    assert report.issues[0].ownership == "user"
    assert report.issues[0].severity is Severity.WARN
