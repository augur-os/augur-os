"""Auto-generated importability test for skill_quality_ops."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

from src.lib.ops_protocol import OpsContext

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

def test_skill_quality_ops_importable():
    """Verify that skill_quality_ops can be imported without errors."""
    mod = importlib.import_module("skills.auto-skill-quality.scripts.skill_quality_ops")
    assert mod is not None


def test_scorer_loader_does_not_shadow_mcp_sdk():
    """The direct script fallback must not make scripts/mcp shadow the MCP SDK."""
    mod = importlib.import_module("skills.auto-skill-quality.scripts.skill_quality_ops")

    scorer = mod._get_scorer()

    from mcp.server.fastmcp import FastMCP

    assert callable(scorer)
    assert FastMCP is not None


def _scored_demo_skill() -> dict:
    return {
        "skills": [
            {
                "name": "demo",
                "tier": "B",
                "score": 60,
                "rubric": "domain-low",
                "dimensions": {
                    "instruction": {
                        "score": 50,
                        "signals": {"desc_words": 3, "body_lines": 4, "sections": 0},
                    },
                    "product": {"score": 100, "signals": {}},
                    "ui": {"score": 100, "signals": {"page_count": 1, "mature_pages": 1}},
                    "wiring": {"score": 100, "signals": {}},
                },
            }
        ]
    }


def _resolvable_report(**counts: int) -> dict:
    default_counts = {
        "unrouted_intents": 0,
        "routing_collisions": 0,
        "orphaned_skills": 0,
        "stale_capability_entries": 0,
        "retired_aliases": 0,
    }
    default_counts.update(counts)
    return {"summary": {"findings": default_counts}}


def test_check_resolvable_clean_report_emits_no_issue(monkeypatch):
    """A clean catalog audit is proof, not a maintenance finding to route."""
    mod = importlib.import_module("skills.auto-skill-quality.scripts.skill_quality_ops")
    check_resolvable = importlib.import_module(
        "skills.auto-skill-quality.scripts.check_resolvable"
    )

    monkeypatch.setattr(check_resolvable, "run_audit", lambda: _resolvable_report())

    assert mod._check_resolvable_issues() == []


def test_check_resolvable_nonzero_report_emits_maintenance_issue(monkeypatch):
    """Real coverage drift still surfaces as a report-only maintenance issue."""
    mod = importlib.import_module("skills.auto-skill-quality.scripts.skill_quality_ops")
    check_resolvable = importlib.import_module(
        "skills.auto-skill-quality.scripts.check_resolvable"
    )

    monkeypatch.setattr(
        check_resolvable,
        "run_audit",
        lambda: _resolvable_report(stale_capability_entries=1),
    )

    issues = mod._check_resolvable_issues()

    assert len(issues) == 1
    assert issues[0]["category"] == "skill-coverage"
    assert issues[0]["kind"] == "maintenance"
    assert "1 stale" in issues[0]["detail"]


def test_scan_writes_rank_sidecar_under_shared_vault(tmp_path, monkeypatch):
    """Skill rank sidecars should be written beside project-brain skill sources."""
    mod = importlib.import_module("skills.auto-skill-quality.scripts.skill_quality_ops")
    skill_dir = tmp_path / "project-brain" / "capabilities" / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: demo\n---\n# Demo\n", encoding="utf-8")

    monkeypatch.setattr(mod, "_get_scorer", lambda: lambda **_kwargs: _scored_demo_skill())
    monkeypatch.setattr(mod, "get_project_root", lambda: tmp_path)

    result = mod.scan(OpsContext(project_root=tmp_path, difficulty=1, config={"max_skills_per_cycle": 1}))

    assert result.issues[0]["path"] == "project-brain/capabilities/skills/demo/SKILL.md"
    assert (skill_dir / "evals" / "rank.json").is_file()


def test_fix_uses_shared_vault_skill_dir(tmp_path, monkeypatch):
    """File-level fixes should operate on project-brain skills, not retired skills/."""
    mod = importlib.import_module("skills.auto-skill-quality.scripts.skill_quality_ops")
    skill_dir = tmp_path / "project-brain" / "capabilities" / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: demo\n---\n# Demo\n", encoding="utf-8")
    seen: dict[str, Path] = {}

    monkeypatch.setattr(mod, "_get_scorer", lambda: lambda **_kwargs: _scored_demo_skill())
    monkeypatch.setattr(mod, "is_blacklisted", lambda _root, _skill_name: False)
    monkeypatch.setattr(mod, "read_skill_context", lambda _skill_name, path: seen.setdefault("skill_dir", path) or {})
    monkeypatch.setattr(mod, "fix_instruction", lambda _skill_name, _path, _signals, _ctx: ["updated docs"])
    monkeypatch.setattr(mod, "git_commit", lambda *_args, **_kwargs: False)

    mod.fix(
        OpsContext(project_root=tmp_path, difficulty=1, config={"build_verify": False}),
        [{"skill_name": "demo", "dimension": "instruction", "signals": {}, "score": 50}],
    )

    assert seen["skill_dir"] == skill_dir
