"""Tests for launch skill inventory generation."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from unittest.mock import MagicMock

from src.lib.launch_skill_inventory import build_launch_skill_inventory
from src.plugins.skill_discovery import SkillRecord


def _record(path: Path, **overrides) -> SkillRecord:
    defaults = dict(
        name="apple",
        description="Apple integrations",
        path=path,
        author="bundled",
        hub="life",
        visibility="app",
        loop_config={},
        dependencies={},
        mcp_tools=["apple-notes-list"],
        dashboard_pages=["/life/apple"],
        commands=[],
        config={},
        agent=None,
        skill_type="domain",
        tags=("apple",),
        tier=0,
        origin="augur",
        ownership="augur",
        upstream={},
        source="augur",
        group="productivity",
        release="r2",
        category="",
        requires_platform=True,
    )
    defaults.update(overrides)
    return SkillRecord(**defaults)


def test_build_launch_skill_inventory_includes_rank_and_launch_fields(tmp_path: Path):
    skill_dir = tmp_path / "skills" / "apple"
    (skill_dir / "evals").mkdir(parents=True)
    (skill_dir / "evals" / "rank.json").write_text(
        json.dumps({"tier": "B", "score": 58.5}),
        encoding="utf-8",
    )

    inventory = build_launch_skill_inventory([_record(skill_dir)], project_root=tmp_path)

    assert inventory["count"] == 1
    assert inventory["generated_at"]
    row = inventory["skills"][0]
    assert row["name"] == "apple"
    assert row["path"] == "skills/apple"
    assert row["hub"] == "life"
    assert row["group"] == "productivity"
    assert row["release"] == "r2"
    assert row["visibility"] == "app"
    assert row["category"] == ""
    assert row["requires_platform"] is True
    assert row["ownership"] == "augur"
    assert row["source"] == "augur"
    assert row["quality_tier"] == "B"
    assert row["quality_score"] == 58.5


def test_build_launch_skill_inventory_normalizes_live_vault_paths(
    tmp_path: Path,
    monkeypatch,
):
    repo_root = tmp_path / "repo"
    vault_root = tmp_path / "vault"
    skill_dir = vault_root / "skills" / "career-ops"
    (skill_dir / "evals").mkdir(parents=True)
    (skill_dir / "evals" / "rank.json").write_text(
        json.dumps({"tier": "C", "score": 44.2}),
        encoding="utf-8",
    )
    monkeypatch.setattr("src.lib.launch_skill_inventory.get_vault_dir", lambda: vault_root)

    inventory = build_launch_skill_inventory(
        [
            _record(
                skill_dir,
                name="career-ops",
                ownership="user",
                origin="vault",
                source="vault",
                source_root="vault",
            )
        ],
        project_root=repo_root,
    )

    assert inventory["skills"][0]["path"] == "vault/skills/career-ops"


def test_build_launch_skill_inventory_raises_on_malformed_rank_json(tmp_path: Path):
    skill_dir = tmp_path / "skills" / "apple"
    (skill_dir / "evals").mkdir(parents=True)
    (skill_dir / "evals" / "rank.json").write_text("{not-json}", encoding="utf-8")

    try:
        build_launch_skill_inventory([_record(skill_dir)], project_root=tmp_path)
    except ValueError as exc:
        message = str(exc)
        assert "rank.json" in message
        assert str(skill_dir / "evals" / "rank.json") in message
    else:
        raise AssertionError("Expected ValueError for malformed rank.json")


def test_assemble_manifest_user_owned_skill_metadata_counts_managed_vault_skills(
    tmp_path: Path,
    monkeypatch,
):
    from src.mcp.augur_framework.tools.domain import discovery

    repo_skill = tmp_path / "skills" / "apple"
    repo_skill.mkdir(parents=True)
    (repo_skill / "SKILL.md").write_text(
        "---\n"
        "name: apple\n"
        "x-augur-hub: life\n"
        "x-augur-mcp-tools:\n"
        "  - apple-notes-list\n"
        "---\n"
        "# Apple\n",
        encoding="utf-8",
    )

    vault_skills_dir = tmp_path / "vault" / "skills"
    vault_skill = vault_skills_dir / "career-ops"
    vault_skill.mkdir(parents=True)
    (vault_skill / "SKILL.md").write_text(
        "---\n"
        "name: career-ops\n"
        "x-augur-hub: career\n"
        "x-augur-mcp-tools:\n"
        "  - career-search\n"
        "---\n"
        "# Career Ops\n",
        encoding="utf-8",
    )

    disabled_vault_skill = vault_skills_dir / "hidden-skill"
    disabled_vault_skill.mkdir(parents=True)
    (disabled_vault_skill / "SKILL.md").write_text(
        "---\n"
        "name: hidden-skill\n"
        "x-augur-hub: hidden\n"
        "x-augur-mcp-tools:\n"
        "  - hidden-tool\n"
        "---\n"
        "# Hidden Skill\n",
        encoding="utf-8",
    )
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir(parents=True)
    (runtime_dir / "focus_state.json").write_text(
        json.dumps({"skill": "hidden-skill"}),
        encoding="utf-8",
    )

    monkeypatch.setattr(discovery, "get_project_root", lambda: tmp_path)
    seen: dict[str, tuple[int, ...] | None] = {}

    def fake_discover_all_skills(*, tiers=None):
        seen["tiers"] = tiers
        return [
            _record(repo_skill, name="apple", hub="life"),
            _record(
                vault_skill,
                name="career-ops",
                hub="career",
                ownership="user",
                origin="vault",
                source="vault",
                source_root="vault",
            ),
        ]

    monkeypatch.setattr(discovery, "discover_all_skills", fake_discover_all_skills, raising=False)

    manifest = discovery.assemble_manifest(runtime_dir)

    assert seen["tiers"] == (0,)
    assert manifest["manifest"]["capabilities"]["skills"] == 2
    assert {hub["id"] for hub in manifest["manifest"]["hubs"]} == {"career", "life"}
    assert {tool["name"] for tool in manifest["recommended_tools"]} == {
        "apple-notes-list",
        "career-search",
    }
    assert manifest["focus"]["hub"] is None


def _load_generate_launch_skill_inventory_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "generate-launch-skill-inventory.py"
    spec = importlib.util.spec_from_file_location("generate_launch_skill_inventory", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generate_launch_skill_inventory_requests_tier_zero_discovery_and_writes_payload(monkeypatch):
    module = _load_generate_launch_skill_inventory_module()
    seen = {}

    def fake_discover_all_skills(*, tiers):
        seen["tiers"] = tiers
        return ["record"]

    def fake_build_launch_skill_inventory(records, project_root):
        seen["records"] = records
        seen["project_root"] = project_root
        return {"generated_at": "now", "count": 1, "skills": [{"name": "apple"}]}

    write_mock = MagicMock(return_value=True)

    monkeypatch.setattr(module, "discover_all_skills", fake_discover_all_skills)
    monkeypatch.setattr(module, "build_launch_skill_inventory", fake_build_launch_skill_inventory)
    monkeypatch.setattr(module, "write_stable_json", write_mock)

    module.main()

    assert seen["tiers"] == (0,)
    assert seen["records"] == ["record"]
    assert seen["project_root"] == module.root
    write_mock.assert_called_once()
    args, kwargs = write_mock.call_args
    assert args[0] == module.root / "docs" / "generated" / "launch-skill-inventory.json"
    assert args[1]["count"] == 1
    assert args[1]["skills"] == [{"name": "apple"}]
    assert kwargs == {"volatile_keys": ["generated_at"]}
