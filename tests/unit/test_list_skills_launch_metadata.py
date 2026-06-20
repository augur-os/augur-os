"""Tests for launch metadata in list-skills JSON output."""

from __future__ import annotations

import importlib.util
import json
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.lib.generated_artifacts import write_stable_json
from src.lib.frontmatter_utils import write_frontmatter


def _load_generate_skill_manifest_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "generate-skill-manifest.py"
    spec = importlib.util.spec_from_file_location("generate_skill_manifest", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_list_skills_json_emits_launch_metadata():
    """The JSON payload should include launch catalog metadata."""
    from src.mcp.augur_core.tools.core.models import ListSkillsInput, ResponseFormat
    from src.mcp.augur_core.tools.core.skills import list_skills_impl

    skill = SimpleNamespace(
        name="launch-skill",
        display_name="Launch Skill",
        description="Launch skill description",
        triggers=("launch",),
        capabilities=("capability",),
        token_estimate=42,
        has_modules=False,
        has_scripts=False,
        has_references=False,
        hub="dev",
        master=None,
        plugin=None,
        source="augur",
        ownership="adopted",
        upstream={"repo": "owner/launch-skill"},
        skill_type="domain",
        tags=("tag",),
        origin="augur",
        author="bundled",
        visibility="app",
        group="productivity",
        release="r2",
        category="utility",
        requires_platform=True,
    )

    cache = MagicMock()
    cache.get.return_value = None
    metrics = MagicMock()

    params = ListSkillsInput(format=ResponseFormat.JSON)
    result = await list_skills_impl(params, cache, metrics, lambda **kwargs: [skill])

    data = json.loads(result)
    assert data["count"] == 1

    row = data["skills"][0]
    assert row["visibility"] == "app"
    assert row["group"] == "productivity"
    assert row["release"] == "r2"
    assert row["category"] == "utility"
    assert row["requires_platform"] is True
    assert row["source"] == "augur"
    assert row["ownership"] == "adopted"


def test_generate_skill_manifest_builds_stable_payload(tmp_path):
    """The manifest generator should emit stable project_root and launch metadata."""
    module = _load_generate_skill_manifest_module()

    skill = SimpleNamespace(
        name="launch-skill",
        description="Launch skill description",
        path=module.root / "skills" / "launch-skill",
        master="",
        hub="dev",
        visibility="app",
        group="productivity",
        release="r2",
        category="utility",
        requires_platform=True,
        ownership="adopted",
        source="augur",
        loop_config={},
        dependencies={},
        mcp_tools=[],
        dashboard_pages=[],
        commands=[],
        agent=None,
        tier=0,
    )

    manifest = module.build_manifest([skill])
    assert manifest["project_root"] == "."
    assert manifest["skills"][0]["group"] == "productivity"
    assert manifest["skills"][0]["release"] == "r2"
    assert manifest["skills"][0]["category"] == "utility"
    assert manifest["skills"][0]["requires_platform"] is True
    assert manifest["skills"][0]["ownership"] == "adopted"
    assert manifest["skills"][0]["source"] == "augur"

    path = tmp_path / "skill-manifest-test.json"
    assert write_stable_json(path, manifest, volatile_keys=["generated_at"]) is True
    rewritten = dict(manifest)
    rewritten["generated_at"] = "2099-01-01T00:00:00+00:00"
    assert write_stable_json(path, rewritten, volatile_keys=["generated_at"]) is False


def test_generate_skill_manifest_preserves_standard_private_subskill_path():
    module = _load_generate_skill_manifest_module()
    skill = SimpleNamespace(
        name="apple-notes",
        description="Use local Apple Notes.",
        path=Path("/vault/capabilities/skills/apple/apple-notes"),
        master="",
        hub="",
        visibility="",
        group=None,
        release=None,
        category="",
        requires_platform=False,
        ownership="user",
        source="private-vault",
        loop_config={},
        dependencies={},
        mcp_tools=[],
        dashboard_pages=[],
        commands=[],
        agent=None,
        tier=0,
    )

    manifest = module.build_manifest([skill])
    row = manifest["skills"][0]

    assert row["name"] == "apple-notes"
    assert row["path"] == "/vault/capabilities/skills/apple/apple-notes"
    assert row["ownership"] == "user"
    assert row["source"] == "private-vault"
    assert row["requires_platform"] is False


def test_generate_skill_manifest_discovers_repo_owned_skills_only(monkeypatch):
    """The manifest generator must request tier-0 skills only."""
    module = _load_generate_skill_manifest_module()
    seen = {}

    def fake_discover_all_skills(*, tiers):
        seen["tiers"] = tiers
        return []

    monkeypatch.setattr(module, "discover_all_skills", fake_discover_all_skills)

    skills = module.discover_manifest_skills()
    assert skills == []
    assert seen["tiers"] == (0,)


def test_browse_index_preserves_user_ownership_from_skill_entries(tmp_path, monkeypatch):
    from src.mcp.augur_framework.tools.infrastructure.browse import index as browse_index

    category_dir = tmp_path / "rag" / "skills"
    source_path = tmp_path / "vault" / "skills" / "career-ops" / "SKILL.md"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text("---\nname: career-ops\n---\n", encoding="utf-8")
    write_frontmatter(
        category_dir / "career" / "career-ops.md",
        {
            "type": "skill",
            "hub": "career",
            "name": "career-ops",
            "source": "vault",
            "ownership": "user",
            "skill_client": "vault",
            "skill_origin": "canonical",
            "source_root": "vault",
            "source_path": str(source_path),
            "description": "Career workflows managed in the vault.",
        },
        "",
    )

    index_reader = Path("src/lib/index/index_reader.py").resolve()
    monkeypatch.setattr(browse_index, "find_skill_file", lambda *args: index_reader)
    # Isolate to tmp: the real AI-artifact inventory pulls registered project brains
    # (~80 skills) into the skills category outside the monkeypatched RAG dir.
    monkeypatch.setattr(browse_index, "inventory_browse_entries_for_category", lambda category: [])
    monkeypatch.setattr(
        browse_index,
        "_get_skill_enrichment",
        lambda: {
            "career-ops": {
                "ownership": "external",
                "installMethod": "registry",
                "sourceUrl": "https://example.com/career-ops",
            }
        },
    )

    import src.config.paths as paths

    monkeypatch.setattr(paths, "get_rag_category_dir", lambda category: category_dir)

    result = json.loads(browse_index.browse_index_impl("skills"))

    assert result["count"] == 1
    item = result["items"][0]
    assert item["ownership"] == "user"
    assert item["metadata"]["ownership"] == "user"
    assert item["metadata"]["installMethod"] == "registry"
