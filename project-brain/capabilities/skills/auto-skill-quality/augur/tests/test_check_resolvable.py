"""Tests for check_resolvable (ADR-741 skill-coverage audit).

Imports via ``importlib.util.spec_from_file_location`` per feedback_skill_test_convention.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
MODULE_PATH = SCRIPTS_DIR / "check_resolvable.py"
MODULE_NAME = "auto_skill_quality_check_resolvable"


def _load_module() -> Any:
    if MODULE_NAME in sys.modules:
        return sys.modules[MODULE_NAME]
    spec = importlib.util.spec_from_file_location(MODULE_NAME, MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # Register the module BEFORE executing so dataclass type-resolution can
    # look up `cls.__module__` in sys.modules (Python 3.12 strictness).
    sys.modules[MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def cr() -> Any:
    """Loaded check_resolvable module."""
    return _load_module()


def _write_skill(root: Path, skill_id: str, frontmatter: dict) -> Path:
    skill_dir = root / skill_id
    skill_dir.mkdir(parents=True, exist_ok=True)
    import yaml

    fm_text = yaml.safe_dump(frontmatter, sort_keys=False).strip()
    (skill_dir / "SKILL.md").write_text(
        f"---\n{fm_text}\n---\n\n# {skill_id}\n", encoding="utf-8"
    )
    return skill_dir


def _write_capability_yaml(path: Path, capabilities: dict) -> Path:
    import yaml

    path.write_text(
        yaml.safe_dump({"capabilities": capabilities}, sort_keys=False),
        encoding="utf-8",
    )
    return path


# ---------------------------------------------------------------------------
# 1. Unrouted intent
# ---------------------------------------------------------------------------


def test_unrouted_intent_detected(cr, tmp_path):
    """A declared command with no matching capability entry must surface."""
    skills_root = tmp_path / "skills"
    _write_skill(
        skills_root,
        "alpha",
        {
            "name": "alpha",
            "description": "Alpha skill",
            "x-augur-tags": ["alpha"],
            "x-augur-commands": ["ghost-command"],
            "x-augur-mcp-tools": [],
        },
    )
    cap = _write_capability_yaml(tmp_path / "capability_exposure.yaml", {})

    report = cr.run_audit(skill_roots=[skills_root], capability_yaml=cap, write=False)

    findings = report["findings"]["unrouted_intents"]
    assert any(
        f["skill_id"] == "alpha" and f["intent_phrase"] == "ghost-command"
        for f in findings
    ), findings


# ---------------------------------------------------------------------------
# 2. Routing collision
# ---------------------------------------------------------------------------


def test_routing_collision_detected(cr, tmp_path):
    """Same bigram declared by two skills with no explicit owner must surface."""
    skills_root = tmp_path / "skills"
    _write_skill(
        skills_root,
        "alpha",
        {
            "name": "alpha",
            "description": "Manage cosmic search results",
            "x-augur-tags": ["cosmic"],
            "x-augur-commands": ["alpha-cmd"],
        },
    )
    _write_skill(
        skills_root,
        "beta",
        {
            "name": "beta",
            "description": "Refine cosmic search relevance",
            "x-augur-tags": ["cosmic"],
            "x-augur-commands": ["beta-cmd"],
        },
    )
    cap = _write_capability_yaml(
        tmp_path / "capability_exposure.yaml",
        {
            "command:alpha-cmd": {"owner_kind": "augur", "management": "generated"},
            "command:beta-cmd": {"owner_kind": "augur", "management": "generated"},
        },
    )

    report = cr.run_audit(skill_roots=[skills_root], capability_yaml=cap, write=False)
    findings = report["findings"]["routing_collisions"]
    phrases = {f["phrase"] for f in findings}
    assert "cosmic search" in phrases, findings
    # Shared category tags are intentional grouping, not routing collisions (ADR-796).
    assert "cosmic" not in phrases, findings


# ---------------------------------------------------------------------------
# 3. Orphaned skill
# ---------------------------------------------------------------------------


def test_orphan_detected(cr, tmp_path):
    """A skill with NO declared surfaces and no capability reference is orphaned."""
    skills_root = tmp_path / "skills"
    _write_skill(
        skills_root,
        "lonely",
        {
            "name": "lonely",
            "description": "A skill nobody wired up",
            "x-augur-tags": [],
            "x-augur-commands": [],
            "x-augur-mcp-tools": [],
        },
    )
    cap = _write_capability_yaml(tmp_path / "capability_exposure.yaml", {})

    report = cr.run_audit(skill_roots=[skills_root], capability_yaml=cap, write=False)
    orphans = report["findings"]["orphaned_skills"]
    assert any(o["skill_id"] == "lonely" for o in orphans), orphans


# ---------------------------------------------------------------------------
# 4. Stale capability entry
# ---------------------------------------------------------------------------


def test_stale_capability_detected(cr, tmp_path):
    """A capability_exposure entry that names a primary_skill not in the catalog is stale."""
    skills_root = tmp_path / "skills"
    _write_skill(
        skills_root,
        "alpha",
        {
            "name": "alpha",
            "description": "Alpha skill",
            "x-augur-mcp-tools": ["alpha-tool"],
        },
    )
    cap = _write_capability_yaml(
        tmp_path / "capability_exposure.yaml",
        {
            "mcp-tool:alpha-tool": {
                "owner_kind": "augur",
                "management": "generated",
                "primary_skill": "ghost-skill",
            },
        },
    )

    report = cr.run_audit(skill_roots=[skills_root], capability_yaml=cap, write=False)
    stale = report["findings"]["stale_capability_entries"]
    assert any(s["tool_id"] == "mcp-tool:alpha-tool" for s in stale), stale


# ---------------------------------------------------------------------------
# 5. Clean catalog produces empty findings
# ---------------------------------------------------------------------------


def test_clean_catalog_produces_empty_findings(cr, tmp_path):
    """Audit a single well-wired skill — all four buckets empty."""
    skills_root = tmp_path / "skills"
    _write_skill(
        skills_root,
        "tidy",
        {
            "name": "tidy",
            "description": "Tidy domain capability",
            "x-augur-tags": ["tidy"],
            "x-augur-commands": ["tidy-cmd"],
            "x-augur-mcp-tools": ["tidy-tool"],
        },
    )
    cap = _write_capability_yaml(
        tmp_path / "capability_exposure.yaml",
        {
            "command:tidy-cmd": {
                "owner_kind": "augur",
                "management": "generated",
                "primary_skill": "tidy",
            },
            "mcp-tool:tidy-tool": {
                "owner_kind": "augur",
                "management": "generated",
                "primary_skill": "tidy",
            },
        },
    )

    report = cr.run_audit(skill_roots=[skills_root], capability_yaml=cap, write=False)
    summary = report["summary"]["findings"]
    assert summary["unrouted_intents"] == 0
    assert summary["orphaned_skills"] == 0
    assert summary["stale_capability_entries"] == 0
    # A single-skill catalog produces no bigram collisions (collision = ≥2 skills).
    assert summary["routing_collisions"] == 0


# ---------------------------------------------------------------------------
# 6. Report schema matches the spec §4.2 shape
# ---------------------------------------------------------------------------


def test_report_schema_matches_spec(cr, tmp_path):
    """Produced JSON must match the spec shape — top-level keys, summary keys, finding buckets."""
    skills_root = tmp_path / "skills"
    _write_skill(
        skills_root,
        "alpha",
        {"name": "alpha", "description": "Sample skill", "x-augur-commands": ["a"]},
    )
    cap = _write_capability_yaml(tmp_path / "capability_exposure.yaml", {})

    report = cr.run_audit(skill_roots=[skills_root], capability_yaml=cap, write=False)

    # Top-level keys per spec §4.2.
    for key in ("generated_at", "auditor_version", "summary", "findings"):
        assert key in report, f"missing top-level key {key}"

    # Summary structure.
    summary = report["summary"]
    for key in ("skills_scanned", "surfaces_scanned", "findings"):
        assert key in summary, f"missing summary key {key}"

    findings_summary = summary["findings"]
    for bucket in (
        "unrouted_intents",
        "routing_collisions",
        "orphaned_skills",
        "stale_capability_entries",
    ):
        assert bucket in findings_summary, f"missing findings count bucket {bucket}"
        assert isinstance(findings_summary[bucket], int)

    # Findings structure.
    findings = report["findings"]
    for bucket in (
        "unrouted_intents",
        "routing_collisions",
        "orphaned_skills",
        "stale_capability_entries",
    ):
        assert bucket in findings, f"missing findings bucket {bucket}"
        assert isinstance(findings[bucket], list)


# ---------------------------------------------------------------------------
# Write path uses runtime dir + JSON is valid on disk
# ---------------------------------------------------------------------------


def test_report_write_target(cr, tmp_path):
    """When write=True with an explicit path, the report writes valid JSON there."""
    skills_root = tmp_path / "skills"
    _write_skill(
        skills_root,
        "alpha",
        {"name": "alpha", "description": "alpha", "x-augur-commands": ["a"]},
    )
    cap = _write_capability_yaml(tmp_path / "capability_exposure.yaml", {})
    target = tmp_path / "out" / "resolvable-report.json"

    cr.run_audit(
        skill_roots=[skills_root],
        capability_yaml=cap,
        write=True,
        report_path=target,
    )

    assert target.is_file()
    loaded = json.loads(target.read_text(encoding="utf-8"))
    assert loaded["summary"]["skills_scanned"] == 1


# ---------------------------------------------------------------------------
# 8. Retired aliases (ADR-796)
# ---------------------------------------------------------------------------


def _write_command_body(skill_dir: Path, cmd_id: str, export_command: bool) -> Path:
    cmds = skill_dir / "commands"
    cmds.mkdir(parents=True, exist_ok=True)
    body = cmds / f"{cmd_id}.md"
    body.write_text(
        f"---\nx-augur-export-command: {str(export_command).lower()}\n---\n\n# {cmd_id}\n",
        encoding="utf-8",
    )
    return body


def test_dashboard_page_declaration_is_not_unrouted(cr, tmp_path):
    """Dashboard pages are not modeled in capability_exposure.yaml (it tracks
    commands/mcp-tools/etc.) and have their own mount-verification, so a declared
    page must NOT be reported as an unrouted intent. Regression for ADR-796."""
    root = tmp_path / "skills"
    _write_skill(
        root,
        "knowledge",
        {
            "name": "knowledge",
            "description": "Knowledge base",
            "x-augur-dashboard-pages": ["/workspace/memory", "/workspace/search"],
        },
    )
    cap = _write_capability_yaml(tmp_path / "cap.yaml", {})
    report = cr.run_audit(skill_roots=[root], capability_yaml=cap, write=False)
    assert report["findings"]["unrouted_intents"] == []
    assert report["summary"]["findings"]["unrouted_intents"] == 0


def test_unrouted_still_flags_command_without_surface(cr, tmp_path):
    """Guard the fix doesn't over-correct: a declared COMMAND with no capability
    surface is still an unrouted finding."""
    root = tmp_path / "skills"
    _write_skill(
        root,
        "evals",
        {"name": "evals", "description": "Evals",
         "x-augur-commands": [{"id": "loop-evals", "type": "workflow"}]},
    )
    cap = _write_capability_yaml(tmp_path / "cap.yaml", {})
    report = cr.run_audit(skill_roots=[root], capability_yaml=cap, write=False)
    assert [f["intent_phrase"] for f in report["findings"]["unrouted_intents"]] == ["loop-evals"]


def test_routine_only_skill_is_not_orphan(cr, tmp_path):
    """A skill wired only via a scheduled routine/loop (no command/mcp-tool/page)
    is daemon-invoked, not an orphan (ADR-796)."""
    root = tmp_path / "skills"
    _write_skill(
        root,
        "file-manager-augur",
        {
            "name": "file-manager-augur",
            "description": "File organizer adapter",
            "x-augur-routine": {"id": "file-organizer", "loop": "file-organizer"},
            "x-augur-loop": {"name": "file-organizer", "trigger": "nightly"},
        },
    )
    cap = _write_capability_yaml(tmp_path / "cap.yaml", {})
    report = cr.run_audit(skill_roots=[root], capability_yaml=cap, write=False)
    assert report["findings"]["orphaned_skills"] == []
    assert report["summary"]["findings"]["orphaned_skills"] == 0


def test_skill_with_no_wiring_is_still_orphan(cr, tmp_path):
    """Guard against over-correction: a skill with no surfaces AND no routine is
    still an orphan."""
    root = tmp_path / "skills"
    _write_skill(root, "ghost", {"name": "ghost", "description": "Nothing wired"})
    cap = _write_capability_yaml(tmp_path / "cap.yaml", {})
    report = cr.run_audit(skill_roots=[root], capability_yaml=cap, write=False)
    assert [o["skill_id"] for o in report["findings"]["orphaned_skills"]] == ["ghost"]


def test_shared_category_tag_is_not_a_collision(cr, tmp_path):
    """Shared x-augur-tags are intentional category grouping (e.g. all routine
    skills tagged 'autoloop'), not routing collisions (ADR-796)."""
    root = tmp_path / "skills"
    _write_skill(root, "routine-a",
                 {"name": "routine-a", "description": "Alpha codebase checks",
                  "x-augur-tags": ["autoloop"]})
    _write_skill(root, "routine-b",
                 {"name": "routine-b", "description": "Beta platform validation",
                  "x-augur-tags": ["autoloop"]})
    cap = _write_capability_yaml(tmp_path / "cap.yaml", {})
    report = cr.run_audit(skill_roots=[root], capability_yaml=cap, write=False)
    assert report["findings"]["routing_collisions"] == []


def test_shared_description_phrase_still_collides(cr, tmp_path):
    """Guard against over-correction: genuine description overlap (a shared
    distinctive bigram) is still a routing collision."""
    root = tmp_path / "skills"
    _write_skill(root, "skill-a",
                 {"name": "skill-a", "description": "manage nightly drift sweeps"})
    _write_skill(root, "skill-b",
                 {"name": "skill-b", "description": "detect nightly drift early"})
    cap = _write_capability_yaml(tmp_path / "cap.yaml", {})
    report = cr.run_audit(skill_roots=[root], capability_yaml=cap, write=False)
    phrases = [c["phrase"] for c in report["findings"]["routing_collisions"]]
    assert "nightly drift" in phrases


def test_retired_alias_advertised_is_flagged(cr, tmp_path):
    root = tmp_path / "skills"
    skill_dir = _write_skill(
        root,
        "platform-admin",
        {
            "name": "platform-admin",
            "description": "Dev ops",
            "x-augur-commands": [
                {"id": "dev", "type": "workflow"},
                {"id": "dev-merge", "type": "workflow"},
            ],
        },
    )
    _write_command_body(skill_dir, "dev", export_command=True)
    _write_command_body(skill_dir, "dev-merge", export_command=False)
    cap = _write_capability_yaml(tmp_path / "cap.yaml", {})

    report = cr.run_audit(skill_roots=[root], capability_yaml=cap, write=False)

    retired = report["findings"]["retired_aliases"]
    assert [f["command_id"] for f in retired] == ["dev-merge"]
    assert report["summary"]["findings"]["retired_aliases"] == 1


def test_exported_command_is_not_flagged(cr, tmp_path):
    root = tmp_path / "skills"
    skill_dir = _write_skill(
        root,
        "platform-admin",
        {"name": "platform-admin", "description": "Dev ops",
         "x-augur-commands": [{"id": "dev", "type": "workflow"}]},
    )
    _write_command_body(skill_dir, "dev", export_command=True)
    cap = _write_capability_yaml(tmp_path / "cap.yaml", {})
    report = cr.run_audit(skill_roots=[root], capability_yaml=cap, write=False)
    assert report["findings"]["retired_aliases"] == []
    assert report["summary"]["findings"]["retired_aliases"] == 0


def test_command_without_body_is_not_flagged(cr, tmp_path):
    """A declared command with no commands/<id>.md body file is not a retired alias."""
    root = tmp_path / "skills"
    _write_skill(
        root,
        "platform-admin",
        {"name": "platform-admin", "description": "Dev ops",
         "x-augur-commands": [{"id": "dev", "type": "workflow"}]},
    )
    cap = _write_capability_yaml(tmp_path / "cap.yaml", {})
    report = cr.run_audit(skill_roots=[root], capability_yaml=cap, write=False)
    assert report["findings"]["retired_aliases"] == []
    assert report["summary"]["findings"]["retired_aliases"] == 0


def _write_command_body_full(skill_dir: Path, cmd_id: str, frontmatter: dict) -> Path:
    import yaml
    cmds = skill_dir / "commands"
    cmds.mkdir(parents=True, exist_ok=True)
    body = cmds / f"{cmd_id}.md"
    fm = yaml.safe_dump(frontmatter, sort_keys=False).strip()
    body.write_text(f"---\n{fm}\n---\n\n# {cmd_id}\n", encoding="utf-8")
    return body


def test_tracked_deprecated_command_is_not_flagged(cr, tmp_path):
    root = tmp_path / "skills"
    skill_dir = _write_skill(
        root, "dream",
        {"name": "dream", "description": "overnight synthesis",
         "x-augur-commands": [{"id": "dream", "type": "routine"}]},
    )
    _write_command_body_full(
        skill_dir, "dream",
        {"x-augur-export-command": False,
         "x-augur-deprecated": True,
         "x-augur-deprecated-in-favor-of": "routines"},
    )
    cap = _write_capability_yaml(tmp_path / "cap.yaml", {})
    report = cr.run_audit(skill_roots=[root], capability_yaml=cap, write=False)
    assert report["findings"]["retired_aliases"] == []
    assert report["summary"]["findings"]["retired_aliases"] == 0
