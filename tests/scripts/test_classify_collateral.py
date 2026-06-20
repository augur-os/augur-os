"""Unit tests for src/scripts/classify_collateral.py.

Covers the pure classification/routing logic: file-info building, skill
registry frontmatter parsing, prompt assembly, file routing (live, dry-run,
archive, missing, error), reindex gating, and the route-mode JSON guards.

IO is exercised against tmp_path; external collaborators (path helpers,
collect_root_strays, unified_indexer, subprocess git) are faked/monkeypatched.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.scripts import classify_collateral as cc  # noqa: E402

# ---------------------------------------------------------------------------
# extract_text_preview
# ---------------------------------------------------------------------------


def test_extract_text_preview_truncates_to_max_chars(tmp_path):
    f = tmp_path / "long.txt"
    f.write_text("x" * 1000, encoding="utf-8")
    out = cc.extract_text_preview(f, max_chars=120)
    assert out == "x" * 120


def test_extract_text_preview_returns_full_when_shorter(tmp_path):
    f = tmp_path / "short.txt"
    f.write_text("hello world", encoding="utf-8")
    assert cc.extract_text_preview(f, max_chars=500) == "hello world"


def test_extract_text_preview_handles_read_error(tmp_path):
    missing = tmp_path / "nope.txt"  # does not exist
    out = cc.extract_text_preview(missing)
    assert out.startswith("<read error:")


# ---------------------------------------------------------------------------
# build_file_info
# ---------------------------------------------------------------------------


def test_build_file_info_text_extension_uses_text_preview(tmp_path):
    f = tmp_path / "note.md"
    f.write_text("# Title\nbody content", encoding="utf-8")
    info = cc.build_file_info(f)
    assert info["filename"] == "note.md"
    assert info["extension"] == ".md"
    assert info["size_bytes"] == f.stat().st_size
    assert info["content_preview"] == "# Title\nbody content"


def test_build_file_info_uppercase_extension_normalized_and_text(tmp_path):
    f = tmp_path / "data.JSON"
    f.write_text('{"k": 1}', encoding="utf-8")
    info = cc.build_file_info(f)
    # extension lowercased so it matches TEXT_EXTENSIONS and gets a real preview
    assert info["extension"] == ".json"
    assert info["content_preview"] == '{"k": 1}'


def test_build_file_info_binary_extension_uses_size_placeholder(tmp_path):
    f = tmp_path / "blob.bin"
    payload = b"\x00\x01\x02\x03\x04"
    f.write_bytes(payload)
    info = cc.build_file_info(f)
    assert info["extension"] == ".bin"
    assert info["content_preview"] == f"<binary; size: {len(payload)} bytes>"


def test_build_file_info_docx_delegates_to_docx_extractor(tmp_path, monkeypatch):
    f = tmp_path / "deck.docx"
    f.write_bytes(b"PK\x03\x04fake")
    monkeypatch.setattr(cc, "extract_docx_preview", lambda p, **k: "DOCX-PREVIEW")
    info = cc.build_file_info(f)
    assert info["extension"] == ".docx"
    assert info["content_preview"] == "DOCX-PREVIEW"


def test_build_file_info_pptx_delegates_to_pptx_extractor(tmp_path, monkeypatch):
    f = tmp_path / "slides.pptx"
    f.write_bytes(b"PK\x03\x04fake")
    monkeypatch.setattr(cc, "extract_pptx_preview", lambda p, **k: "PPTX-PREVIEW")
    info = cc.build_file_info(f)
    assert info["extension"] == ".pptx"
    assert info["content_preview"] == "PPTX-PREVIEW"


# ---------------------------------------------------------------------------
# get_skill_registry
# ---------------------------------------------------------------------------


def _make_skills_dir(tmp_path, monkeypatch) -> Path:
    skills_dir = tmp_path / "project-brain" / "capabilities" / "skills"
    skills_dir.mkdir(parents=True)
    monkeypatch.setattr(cc, "get_project_brain_skills_dir", lambda root: skills_dir)
    return skills_dir


def _write_skill(skills_dir: Path, name: str, body: str) -> None:
    d = skills_dir / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(body, encoding="utf-8")


def test_get_skill_registry_missing_dir_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(cc, "get_project_brain_skills_dir", lambda root: tmp_path / "does-not-exist")
    assert cc.get_skill_registry(tmp_path) == []


def test_get_skill_registry_parses_frontmatter_description(tmp_path, monkeypatch):
    skills_dir = _make_skills_dir(tmp_path, monkeypatch)
    # x-augur-hub was removed by ADR-802 — even when legacy frontmatter still
    # carries it, the registry no longer reads it and hub stays 'unknown'.
    _write_skill(
        skills_dir,
        "venture",
        "---\nx-augur-hub: professional\ndescription: Fundraising and venture work\n---\n# Venture\n",
    )
    reg = cc.get_skill_registry(tmp_path)
    assert reg == [{"name": "venture", "hub": "unknown", "description": "Fundraising and venture work"}]


def test_get_skill_registry_falls_back_to_first_content_line(tmp_path, monkeypatch):
    skills_dir = _make_skills_dir(tmp_path, monkeypatch)
    # No frontmatter description -> first non-heading, non-marker line is used.
    _write_skill(
        skills_dir,
        "research",
        "# Research\n\nDeep multi-source research harness for the brain.\n",
    )
    reg = cc.get_skill_registry(tmp_path)
    assert len(reg) == 1
    assert reg[0]["name"] == "research"
    assert reg[0]["description"] == "Deep multi-source research harness for the brain."
    # hub defaults to 'unknown' when not in frontmatter
    assert reg[0]["hub"] == "unknown"


def test_get_skill_registry_skips_dotdirs_and_missing_skill_md(tmp_path, monkeypatch):
    skills_dir = _make_skills_dir(tmp_path, monkeypatch)
    _write_skill(skills_dir, "real", "---\ndescription: A real skill\n---\n")
    # dot-prefixed dir: skipped
    (skills_dir / ".hidden").mkdir()
    (skills_dir / ".hidden" / "SKILL.md").write_text("---\ndescription: hidden\n---\n", encoding="utf-8")
    # dir without SKILL.md: skipped
    (skills_dir / "empty").mkdir()
    # a file (not a dir) at the skills level: skipped
    (skills_dir / "stray.txt").write_text("not a skill", encoding="utf-8")

    reg = cc.get_skill_registry(tmp_path)
    assert [s["name"] for s in reg] == ["real"]


def test_get_skill_registry_synthesizes_default_when_no_frontmatter(tmp_path, monkeypatch):
    skills_dir = _make_skills_dir(tmp_path, monkeypatch)
    # No frontmatter and no usable body line -> the "Skill in {hub} hub" default
    # fires (hub stays 'unknown' since there is no frontmatter to read it from).
    _write_skill(skills_dir, "bare", "# Bare\n")
    reg = cc.get_skill_registry(tmp_path)
    assert reg[0]["hub"] == "unknown"
    assert reg[0]["description"] == "Skill in unknown hub"


def test_get_skill_registry_empty_frontmatter_description_falls_back_to_first_line(tmp_path, monkeypatch):
    skills_dir = _make_skills_dir(tmp_path, monkeypatch)
    # Quirk: the fallback line scan runs over the WHOLE file (frontmatter
    # included). With an empty frontmatter description, the first non-blank,
    # non-heading, non-'---' line is a frontmatter key line, so that becomes the
    # description rather than the synthesized "Skill in {hub} hub" default.
    # (hub stays 'unknown': x-augur-hub was removed by ADR-802.)
    _write_skill(skills_dir, "bare", "---\nx-augur-hub: life\ndescription: ''\n---\n# Bare\n")
    reg = cc.get_skill_registry(tmp_path)
    assert reg[0]["hub"] == "unknown"
    assert reg[0]["description"] == "x-augur-hub: life"


# ---------------------------------------------------------------------------
# build_classification_prompt
# ---------------------------------------------------------------------------


def test_build_classification_prompt_includes_context_skills_and_files():
    stray = [
        {
            "filename": "pitch.docx",
            "extension": ".docx",
            "size_bytes": 2048,
            "content_preview": "Elevator pitch text",
        }
    ]
    git_ctx = {
        "git_log_summary": "abc123 feat: thing",
        "git_diff_stat": "1 file changed",
        "branch_name": "feature/x",
    }
    registry = [{"name": "venture", "hub": "professional", "description": "Venture work"}]

    prompt = cc.build_classification_prompt(stray, git_ctx, registry)

    assert "abc123 feat: thing" in prompt
    assert "Branch: feature/x" in prompt
    assert "venture (hub: professional): Venture work" in prompt
    assert "### pitch.docx" in prompt
    assert "Extension: .docx" in prompt
    assert "Size: 2048 bytes" in prompt
    assert "Elevator pitch text" in prompt
    assert "Return ONLY the JSON object" in prompt


# ---------------------------------------------------------------------------
# route_files
# ---------------------------------------------------------------------------


@pytest.fixture
def routing_env(tmp_path, monkeypatch):
    """Fake skills dir + runtime dir for routing tests."""
    skills_dir = tmp_path / "project-brain" / "capabilities" / "skills"
    skills_dir.mkdir(parents=True)
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    monkeypatch.setattr(cc, "get_project_brain_skills_dir", lambda root: skills_dir)
    monkeypatch.setattr(cc, "get_runtime_dir", lambda: runtime_dir)
    return tmp_path, skills_dir, runtime_dir


def test_route_files_live_moves_to_skill_assets(routing_env):
    project_root, skills_dir, _ = routing_env
    src = project_root / "pitch.docx"
    src.write_text("pitch", encoding="utf-8")

    classification = {"pitch.docx": {"skill": "venture", "hub": "professional", "reason": "venture pitch"}}
    summary = cc.route_files(classification, {"pitch.docx": src}, project_root)

    assert summary["archived"] == []
    assert summary["errors"] == []
    assert len(summary["routed"]) == 1
    entry = summary["routed"][0]
    assert entry["skill"] == "venture"
    assert entry["hub"] == "professional"
    # File physically moved into the skill assets dir.
    dest = skills_dir / "venture" / "assets" / "pitch.docx"
    assert dest.is_file()
    assert not src.exists()


def test_route_files_archive_moves_to_garbage_collector(routing_env):
    project_root, _, runtime_dir = routing_env
    src = project_root / "scratch.txt"
    src.write_text("temp", encoding="utf-8")

    classification = {"scratch.txt": {"skill": "_archive", "hub": "_archive", "reason": "scratch"}}
    summary = cc.route_files(classification, {"scratch.txt": src}, project_root)

    assert summary["routed"] == []
    assert len(summary["archived"]) == 1
    assert not src.exists()
    # Lands under runtime garbage_collector/<timestamp>/
    gc_root = runtime_dir / "garbage_collector"
    moved = list(gc_root.rglob("scratch.txt"))
    assert len(moved) == 1


def test_route_files_skips_missing_source(routing_env):
    project_root, _, _ = routing_env
    classification = {"gone.txt": {"skill": "venture", "hub": "professional", "reason": "x"}}
    # stray_paths has no entry -> treated as already gone, skipped silently.
    summary = cc.route_files(classification, {}, project_root)
    assert summary == {"routed": [], "archived": [], "errors": []}


def test_route_files_dry_run_does_not_move(routing_env):
    project_root, skills_dir, _ = routing_env
    src = project_root / "pitch.docx"
    src.write_text("pitch", encoding="utf-8")

    classification = {"pitch.docx": {"skill": "venture", "hub": "professional", "reason": "r"}}
    summary = cc.route_files(classification, {"pitch.docx": src}, project_root, dry_run=True)

    # Summary records the intended route but the file is untouched.
    assert len(summary["routed"]) == 1
    assert src.exists()
    assert not (skills_dir / "venture" / "assets" / "pitch.docx").exists()


def test_route_files_records_error_on_move_failure(routing_env, monkeypatch):
    project_root, _, _ = routing_env
    src = project_root / "pitch.docx"
    src.write_text("pitch", encoding="utf-8")

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(cc.shutil, "move", boom)
    classification = {"pitch.docx": {"skill": "venture", "hub": "professional", "reason": "r"}}
    summary = cc.route_files(classification, {"pitch.docx": src}, project_root)

    assert summary["routed"] == []
    assert len(summary["errors"]) == 1
    assert summary["errors"][0]["file"] == "pitch.docx"
    assert "disk full" in summary["errors"][0]["error"]


def test_route_files_defaults_to_archive_when_skill_omitted(routing_env):
    project_root, _, runtime_dir = routing_env
    src = project_root / "mystery.txt"
    src.write_text("?", encoding="utf-8")
    # No 'skill' key -> defaults to _archive.
    summary = cc.route_files({"mystery.txt": {"reason": "unknown"}}, {"mystery.txt": src}, project_root)
    assert len(summary["archived"]) == 1
    assert summary["routed"] == []


# ---------------------------------------------------------------------------
# reindex_routed_skills
# ---------------------------------------------------------------------------


def test_reindex_routed_skills_noop_when_nothing_routed(capsys, tmp_path):
    cc.reindex_routed_skills({"routed": [], "archived": [], "errors": []}, tmp_path)
    assert capsys.readouterr().out == ""


def test_reindex_routed_skills_dry_run_lists_unique_skills(capsys, tmp_path):
    summary = {
        "routed": [
            {"skill": "venture", "hub": "professional"},
            {"skill": "venture", "hub": "professional"},  # duplicate collapses
            {"skill": "research", "hub": "brain"},
        ],
        "archived": [],
        "errors": [],
    }
    cc.reindex_routed_skills(summary, tmp_path, dry_run=True)
    out = capsys.readouterr().out
    assert "Would re-index: skills/research" in out
    assert "Would re-index: skills/venture" in out
    # Each unique skill listed once.
    assert out.count("Would re-index") == 2


def test_reindex_routed_skills_dry_run_skips_entries_without_hub(capsys, tmp_path):
    # Entries missing hub/skill contribute no skill dirs -> early return, no output.
    summary = {"routed": [{"skill": "venture"}], "archived": [], "errors": []}
    cc.reindex_routed_skills(summary, tmp_path, dry_run=True)
    assert capsys.readouterr().out == ""


# ---------------------------------------------------------------------------
# mode_route guards + summary
# ---------------------------------------------------------------------------


def test_mode_route_rejects_invalid_json(monkeypatch):
    monkeypatch.setattr(cc, "collect_root_strays", lambda root: [])
    with pytest.raises(SystemExit) as exc:
        cc.mode_route("{not json", Path("/tmp"))
    assert exc.value.code == 1


def test_mode_route_rejects_non_object_json(monkeypatch):
    monkeypatch.setattr(cc, "collect_root_strays", lambda root: [])
    with pytest.raises(SystemExit) as exc:
        cc.mode_route("[1, 2, 3]", Path("/tmp"))
    assert exc.value.code == 1


def test_mode_route_exits_nonzero_when_routing_has_errors(routing_env, monkeypatch, capsys):
    project_root, _, _ = routing_env
    src = project_root / "pitch.docx"
    src.write_text("pitch", encoding="utf-8")

    monkeypatch.setattr(cc, "collect_root_strays", lambda root: [src])

    def boom(*a, **k):
        raise OSError("nope")

    monkeypatch.setattr(cc.shutil, "move", boom)
    monkeypatch.setattr(cc, "reindex_routed_skills", lambda *a, **k: None)

    payload = json.dumps({"pitch.docx": {"skill": "venture", "hub": "professional", "reason": "r"}})
    with pytest.raises(SystemExit) as exc:
        cc.mode_route(payload, project_root)
    assert exc.value.code == 1
    assert "Errors:   1" in capsys.readouterr().out


def test_mode_route_dry_run_reports_routed_summary(routing_env, monkeypatch, capsys):
    project_root, _, _ = routing_env
    src = project_root / "pitch.docx"
    src.write_text("pitch", encoding="utf-8")

    monkeypatch.setattr(cc, "collect_root_strays", lambda root: [src])
    monkeypatch.setattr(cc, "reindex_routed_skills", lambda *a, **k: None)

    payload = json.dumps({"pitch.docx": {"skill": "venture", "hub": "professional", "reason": "pitch"}})
    cc.mode_route(payload, project_root, dry_run=True)  # no SystemExit on success

    out = capsys.readouterr().out
    assert "Routed:   1" in out
    assert "pitch.docx" in out
    assert src.exists()  # dry-run leaves the file in place


# ---------------------------------------------------------------------------
# mode_context
# ---------------------------------------------------------------------------


def test_mode_context_clean_repo_emits_clean_message(monkeypatch, capsys):
    monkeypatch.setattr(cc, "collect_root_strays", lambda root: [])
    cc.mode_context(Path("/tmp"))
    out = json.loads(capsys.readouterr().out)
    assert out["stray_files"] == []
    assert out["message"] == "No stray files found — repo root is clean."


def test_mode_context_emits_prompt_and_registry_for_strays(tmp_path, monkeypatch, capsys):
    stray = tmp_path / "loose.txt"
    stray.write_text("loose content", encoding="utf-8")

    monkeypatch.setattr(cc, "collect_root_strays", lambda root: [stray])
    monkeypatch.setattr(
        cc,
        "get_git_context",
        lambda root: {"git_log_summary": "log", "git_diff_stat": "diff", "branch_name": "main"},
    )
    monkeypatch.setattr(
        cc,
        "get_skill_registry",
        lambda root: [{"name": "venture", "hub": "professional", "description": "d"}],
    )

    cc.mode_context(tmp_path)
    out = json.loads(capsys.readouterr().out)

    assert [f["filename"] for f in out["stray_files"]] == ["loose.txt"]
    assert out["stray_files"][0]["content_preview"] == "loose content"
    assert out["skill_registry"][0]["name"] == "venture"
    assert "loose.txt" in out["prompt"]
    assert "message" not in out  # only present in the clean-repo branch
