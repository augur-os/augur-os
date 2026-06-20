"""Unit tests for src.plugins.command_listing.

Covers the shared slash-command listing payload builder consumed by the
``list-commands`` MCP tool and ``aug discover --commands``. The module reads
only a handful of attributes off discovered command/skill objects, so tests use
lightweight ``SimpleNamespace`` fakes and tmp_path markdown files rather than
the real on-disk skill layout.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.plugins import command_listing


def _make_cmd(**overrides):
    """Build a fake CommandInfo-like object with the attrs the module reads."""
    base = dict(
        id="x",
        description="desc",
        visibility="core",
        alias=None,
        group=None,
        bundle="project",
        loop=None,
        path=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _make_skill(**overrides):
    base = dict(
        id="s",
        description="skill desc",
        layer="project",
        visibility=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


# --------------------------------------------------------------------------
# _is_truthy_frontmatter
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [True, "true", "True", "TRUE", "yes", "Yes", "on", "1", "  true  ", " yes "],
)
def test_truthy_frontmatter_accepts_truthy(value):
    assert command_listing._is_truthy_frontmatter(value) is True


@pytest.mark.parametrize(
    "value",
    [False, None, "false", "no", "off", "0", "", "  ", "maybe", "2", "enabled"],
)
def test_truthy_frontmatter_rejects_falsy(value):
    assert command_listing._is_truthy_frontmatter(value) is False


def test_truthy_frontmatter_bool_takes_precedence_over_string_coercion():
    # A real bool False must not be coerced via str() (str(False) == "False").
    assert command_listing._is_truthy_frontmatter(False) is False
    assert command_listing._is_truthy_frontmatter(True) is True


# --------------------------------------------------------------------------
# _is_native_slash_export
# --------------------------------------------------------------------------


def _write_md(tmp_path: Path, name: str, frontmatter_lines: list[str]) -> Path:
    fm = "\n".join(frontmatter_lines)
    doc = f"---\n{fm}\n---\nbody text\n"
    p = tmp_path / name
    p.write_text(doc, encoding="utf-8")
    return p


def test_native_export_true_when_flag_truthy(tmp_path):
    p = _write_md(tmp_path, "cmd.md", ["x-augur-export-command: true"])
    assert command_listing._is_native_slash_export(_make_cmd(path=p)) is True


def test_native_export_false_when_flag_missing(tmp_path):
    p = _write_md(tmp_path, "cmd.md", ["description: hello"])
    assert command_listing._is_native_slash_export(_make_cmd(path=p)) is False


def test_native_export_false_when_flag_falsy(tmp_path):
    p = _write_md(tmp_path, "cmd.md", ["x-augur-export-command: false"])
    assert command_listing._is_native_slash_export(_make_cmd(path=p)) is False


def test_native_export_false_when_path_none():
    assert command_listing._is_native_slash_export(_make_cmd(path=None)) is False


def test_native_export_false_when_no_path_attr():
    # getattr fallback: object missing a ``path`` attribute entirely.
    assert command_listing._is_native_slash_export(object()) is False


def test_native_export_false_when_file_missing(tmp_path):
    missing = tmp_path / "nope.md"
    assert command_listing._is_native_slash_export(_make_cmd(path=missing)) is False


def test_native_export_false_for_non_md_suffix(tmp_path):
    p = tmp_path / "cmd.txt"
    p.write_text("---\nx-augur-export-command: true\n---\nbody\n", encoding="utf-8")
    assert command_listing._is_native_slash_export(_make_cmd(path=p)) is False


def test_native_export_false_for_directory(tmp_path):
    d = tmp_path / "cmd.md"
    d.mkdir()
    # A directory named ``*.md`` is not a file -> not exported.
    assert command_listing._is_native_slash_export(_make_cmd(path=d)) is False


def test_native_export_accepts_string_path(tmp_path):
    p = _write_md(tmp_path, "cmd.md", ["x-augur-export-command: yes"])
    # path provided as a string, not a Path object.
    assert command_listing._is_native_slash_export(_make_cmd(path=str(p))) is True


# --------------------------------------------------------------------------
# build_command_entry
# --------------------------------------------------------------------------


def test_build_command_entry_core_fields():
    cmd = _make_cmd(
        id="ask",
        description="Ask the brain",
        visibility="core",
        alias="a",
        group="grp",
        bundle="augur-core",
    )
    entry = command_listing.build_command_entry(cmd)
    assert entry == {
        "id": "ask",
        "description": "Ask the brain",
        "visibility": "core",
        "alias": "a",
        "group": "grp",
        "bundle": "augur-core",
    }
    assert "loop" not in entry


def test_build_command_entry_includes_loop_when_present():
    cmd = _make_cmd(
        id="auto-test",
        loop={"name": "pytest-loop", "tier": "test", "trigger": "manual", "extra": "ignored"},
    )
    entry = command_listing.build_command_entry(cmd)
    assert entry["loop"] == {"name": "pytest-loop", "tier": "test", "trigger": "manual"}
    # Only the three whitelisted loop keys are carried over.
    assert "extra" not in entry["loop"]


def test_build_command_entry_loop_defaults_missing_keys_to_empty():
    cmd = _make_cmd(id="c", loop={"name": "only-name"})
    entry = command_listing.build_command_entry(cmd)
    assert entry["loop"] == {"name": "only-name", "tier": "", "trigger": ""}


def test_build_command_entry_no_loop_key_for_falsy_loop():
    for falsy in (None, {}, 0, ""):
        entry = command_listing.build_command_entry(_make_cmd(loop=falsy))
        assert "loop" not in entry


# --------------------------------------------------------------------------
# render_commands_payload
# --------------------------------------------------------------------------


def _patch_sources(monkeypatch, cmds, skills, *, exported_ids=None):
    """Patch the lazily-imported discover_commands / list_skills / export check.

    ``exported_ids`` controls which command ids count as native slash exports
    so we can drive the grouping logic without touching the filesystem.
    """
    exported = set(exported_ids) if exported_ids is not None else {c.id for c in cmds}
    monkeypatch.setattr(
        "src.plugins.command_discovery.discover_commands",
        lambda *a, **k: cmds,
    )
    monkeypatch.setattr(
        "src.plugins.skill_discovery.list_skills",
        lambda *a, **k: skills,
    )
    monkeypatch.setattr(
        command_listing,
        "_is_native_slash_export",
        lambda cmd: cmd.id in exported,
    )


def test_render_groups_by_visibility_in_declared_order(monkeypatch):
    cmds = [
        _make_cmd(id="d1", visibility="dev"),
        _make_cmd(id="a1", visibility="app"),
        _make_cmd(id="c1", visibility="core"),
    ]
    _patch_sources(monkeypatch, cmds, skills=[])
    payload = command_listing.render_commands_payload()

    sections = payload["slash_commands"]
    # SLASH_GROUP_ORDER => app, core, dev, test, ops.
    assert [s["key"] for s in sections] == ["app", "core", "dev"]
    assert [s["label"] for s in sections] == ["App Commands", "Core Commands", "Dev Commands"]


def test_render_sorts_commands_within_group_by_id(monkeypatch):
    cmds = [
        _make_cmd(id="zeta", visibility="core"),
        _make_cmd(id="alpha", visibility="core"),
        _make_cmd(id="mid", visibility="core"),
    ]
    _patch_sources(monkeypatch, cmds, skills=[])
    payload = command_listing.render_commands_payload()
    core = next(s for s in payload["slash_commands"] if s["key"] == "core")
    assert [c["id"] for c in core["commands"]] == ["alpha", "mid", "zeta"]


def test_render_excludes_non_exported_commands(monkeypatch):
    cmds = [
        _make_cmd(id="visible", visibility="core"),
        _make_cmd(id="hidden", visibility="core"),
    ]
    _patch_sources(monkeypatch, cmds, skills=[], exported_ids={"visible"})
    payload = command_listing.render_commands_payload()
    core = next(s for s in payload["slash_commands"] if s["key"] == "core")
    assert [c["id"] for c in core["commands"]] == ["visible"]
    assert payload["total_slash_commands"] == 1


def test_render_drops_unknown_visibility_group(monkeypatch):
    # A command whose visibility is not in SLASH_GROUP_ORDER (e.g. "auto")
    # never produces a section even though it is "exported".
    cmds = [_make_cmd(id="loopy", visibility="auto")]
    _patch_sources(monkeypatch, cmds, skills=[])
    payload = command_listing.render_commands_payload()
    assert payload["slash_commands"] == []
    assert payload["total_slash_commands"] == 0


def test_render_totals_count_all_exported_commands(monkeypatch):
    cmds = [
        _make_cmd(id="a", visibility="app"),
        _make_cmd(id="b", visibility="core"),
        _make_cmd(id="c", visibility="dev"),
    ]
    _patch_sources(monkeypatch, cmds, skills=[])
    payload = command_listing.render_commands_payload()
    assert payload["total_slash_commands"] == 3
    # Legacy mirror key must stay in sync with total_slash_commands.
    assert payload["total_commands"] == 3


def test_render_skills_excludes_command_ids_and_visible_skills(monkeypatch):
    cmds = [_make_cmd(id="ask", visibility="core")]
    skills = [
        _make_skill(id="ask", visibility=None),  # shadows a command id -> excluded
        _make_skill(id="geo", visibility=None),  # plain non-command skill -> included
        _make_skill(id="hub", visibility="core"),  # has visibility -> excluded from skills list
    ]
    _patch_sources(monkeypatch, cmds, skills=skills, exported_ids={"ask"})
    payload = command_listing.render_commands_payload()

    skill_ids = [s["id"] for s in payload["skills"]]
    assert skill_ids == ["geo"]
    assert payload["non_command_skills"] == 1
    # total/visible skill counts reflect ALL skills returned by list_skills.
    assert payload["total_skills"] == 3
    assert payload["total_visible_skills"] == 3


def test_render_skills_sorted_and_shape(monkeypatch):
    skills = [
        _make_skill(id="zoo", description="z", layer="user"),
        _make_skill(id="ant", description="a", layer="project"),
    ]
    _patch_sources(monkeypatch, cmds=[], skills=skills)
    payload = command_listing.render_commands_payload()
    assert [s["id"] for s in payload["skills"]] == ["ant", "zoo"]
    ant = payload["skills"][0]
    # bundle is mapped from skill.layer.
    assert ant == {"id": "ant", "description": "a", "bundle": "project"}


def test_render_empty_inputs_produce_zeroed_payload(monkeypatch):
    _patch_sources(monkeypatch, cmds=[], skills=[])
    payload = command_listing.render_commands_payload()
    assert payload == {
        "total_commands": 0,
        "total_slash_commands": 0,
        "total_skills": 0,
        "total_visible_skills": 0,
        "non_command_skills": 0,
        "slash_commands": [],
        "skills": [],
    }


def test_render_payload_keys_are_stable(monkeypatch):
    _patch_sources(monkeypatch, cmds=[_make_cmd(id="a", visibility="core")], skills=[])
    payload = command_listing.render_commands_payload()
    assert set(payload) == {
        "total_commands",
        "total_slash_commands",
        "total_skills",
        "total_visible_skills",
        "non_command_skills",
        "slash_commands",
        "skills",
    }
