"""Unit tests for the read/list/find skill-discovery implementations.

Covers ``skills_read``: listing skills, loading a skill overview, finding a
skill by query (real trigger scoring), and the structural health report.
Dependencies are injected as callables/mocks per the impl signatures; any
filesystem use is confined to ``tmp_path``.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.mcp.augur_core.tools.core import skills_read
from src.mcp.augur_core.tools.core.models import (
    FindSkillInput,
    GetSkillInput,
    ListSkillsInput,
    ResponseFormat,
)
from src.mcp.augur_core.tools.core.skills_read import (
    find_skill_impl,
    get_skill_health_impl,
    get_skill_impl,
    list_skills_impl,
)


def _skill_record(name: str, description: str = "", triggers=()):
    return SimpleNamespace(
        name=name,
        display_name=name,
        description=description or f"{name} description",
        triggers=tuple(triggers),
        capabilities=(),
        token_estimate=100,
        has_modules=False,
        has_scripts=False,
        has_references=False,
        hub="dev",
        layer=None,
        master=None,
        plugin=None,
        source="augur",
        ownership="augur",
        upstream={},
        skill_type="domain",
        tags=(),
        origin="augur",
        author="bundled",
        visibility=None,
        category=None,
        group=None,
        release=None,
        requires_platform=None,
    )


@pytest.mark.asyncio
async def test_list_skills_json_lists_all(monkeypatch, tmp_path):
    """JSON format returns every unique skill with a count."""
    monkeypatch.setattr(skills_read, "_get_skills_dir", lambda: tmp_path)
    cache = MagicMock()
    cache.get.return_value = None
    metrics = MagicMock()
    records = [_skill_record("ask"), _skill_record("keep")]

    result = await list_skills_impl(
        ListSkillsInput(format=ResponseFormat.JSON), cache, metrics, lambda **kw: records
    )
    data = json.loads(result)
    assert data["count"] == 2
    assert {s["name"] for s in data["skills"]} == {"ask", "keep"}
    cache.set.assert_called_once()


@pytest.mark.asyncio
async def test_list_skills_dedupes_by_id(monkeypatch, tmp_path):
    """Duplicate skill ids collapse to one (first wins)."""
    monkeypatch.setattr(skills_read, "_get_skills_dir", lambda: tmp_path)
    cache = MagicMock()
    cache.get.return_value = None
    records = [_skill_record("ask"), _skill_record("ask")]

    result = await list_skills_impl(
        ListSkillsInput(format=ResponseFormat.JSON), cache, MagicMock(), lambda **kw: records
    )
    assert json.loads(result)["count"] == 1


@pytest.mark.asyncio
async def test_list_skills_returns_cached_value(monkeypatch, tmp_path):
    """A cache hit short-circuits and returns the stored payload verbatim."""
    monkeypatch.setattr(skills_read, "_get_skills_dir", lambda: tmp_path)
    cache = MagicMock()
    cache.get.return_value = "CACHED"
    registry = MagicMock()

    result = await list_skills_impl(
        ListSkillsInput(format=ResponseFormat.JSON), cache, MagicMock(), registry
    )
    assert result == "CACHED"
    registry.assert_not_called()


@pytest.mark.asyncio
async def test_list_skills_markdown_format(monkeypatch, tmp_path):
    """Markdown format renders a header and a section per skill."""
    monkeypatch.setattr(skills_read, "_get_skills_dir", lambda: tmp_path)
    cache = MagicMock()
    cache.get.return_value = None

    result = await list_skills_impl(
        ListSkillsInput(format=ResponseFormat.MARKDOWN),
        cache,
        MagicMock(),
        lambda **kw: [_skill_record("ask", triggers=("ask question",))],
    )
    assert "# Available Augur Skills" in result
    assert "## ask" in result
    assert "ask question" in result


@pytest.mark.asyncio
async def test_get_skill_reads_skill_md(tmp_path):
    """The SKILL.md content is returned for a resolvable skill."""
    skill_path = tmp_path / "ask"
    skill_path.mkdir()
    (skill_path / "SKILL.md").write_text("# Ask Skill\nUse me.", encoding="utf-8")
    entry = SimpleNamespace(name="ask", path=skill_path)

    result = await get_skill_impl(
        GetSkillInput(skill_name="ask"), lambda n: entry, lambda: ["ask"], MagicMock()
    )
    assert "# Ask Skill" in result


@pytest.mark.asyncio
async def test_get_skill_include_modules_appends_sections(tmp_path):
    """include_modules appends Modules and References sections."""
    skill_path = tmp_path / "ask"
    skill_path.mkdir()
    (skill_path / "SKILL.md").write_text("# Ask", encoding="utf-8")
    entry = SimpleNamespace(name="ask", path=skill_path)

    result = await get_skill_impl(
        GetSkillInput(skill_name="ask", include_modules=True),
        lambda n: entry,
        lambda: ["ask"],
        MagicMock(),
    )
    assert "## Available Modules" in result
    assert "## Available References" in result


@pytest.mark.asyncio
async def test_get_skill_not_found_lists_available():
    """An unresolvable skill yields an error naming the available ids."""
    result = await get_skill_impl(
        GetSkillInput(skill_name="nope"),
        lambda n: None,
        lambda: ["ask", "keep"],
        MagicMock(),
    )
    assert "not found" in result
    assert "ask" in result and "keep" in result


@pytest.mark.asyncio
async def test_find_skill_scores_and_ranks(monkeypatch, tmp_path):
    """find_skill returns matches scored by the real trigger scorer."""
    monkeypatch.setattr(skills_read, "_get_skills_dir", lambda: tmp_path)
    cache = MagicMock()
    cache.get.return_value = None
    records = [
        _skill_record("interview-prep", "prep for interviews", ("prepare for interview",)),
        _skill_record("unrelated", "something else", ("totally different",)),
    ]

    result = await find_skill_impl(
        FindSkillInput(query="prepare for interview", top_k=5),
        cache,
        MagicMock(),
        lambda **kw: records,
    )
    data = json.loads(result)
    assert data["query"] == "prepare for interview"
    assert data["matches"], "expected at least one scored match"
    assert data["matches"][0]["skill"] == "interview-prep"
    assert data["matches"][0]["score"] > 0


@pytest.mark.asyncio
async def test_find_skill_respects_top_k(monkeypatch, tmp_path):
    """top_k truncates the ranked match list."""
    monkeypatch.setattr(skills_read, "_get_skills_dir", lambda: tmp_path)
    cache = MagicMock()
    cache.get.return_value = None
    records = [
        _skill_record("a", "alpha", ("alpha task",)),
        _skill_record("b", "alpha", ("alpha task",)),
        _skill_record("c", "alpha", ("alpha task",)),
    ]

    result = await find_skill_impl(
        FindSkillInput(query="alpha task", top_k=1), cache, MagicMock(), lambda **kw: records
    )
    assert len(json.loads(result)["matches"]) <= 1


@pytest.mark.asyncio
async def test_get_skill_health_healthy(tmp_path):
    """SKILL.md plus a scripts dir reports a healthy, available status."""
    skill_path = tmp_path / "ask"
    skill_path.mkdir()
    (skill_path / "SKILL.md").write_text("# Ask", encoding="utf-8")
    (skill_path / "scripts").mkdir()
    entry = SimpleNamespace(name="ask", path=skill_path)

    data = json.loads(await get_skill_health_impl("ask", lambda n: entry))
    assert data["status"] == "healthy"
    assert data["uptime"] == "available"
    assert data["structure"]["has_skill_md"] is True
    assert data["structure"]["has_scripts"] is True


@pytest.mark.asyncio
async def test_get_skill_health_degraded_when_only_skill_md(tmp_path):
    """SKILL.md without scripts/commands is degraded but available."""
    skill_path = tmp_path / "ask"
    skill_path.mkdir()
    (skill_path / "SKILL.md").write_text("# Ask", encoding="utf-8")
    entry = SimpleNamespace(name="ask", path=skill_path)

    data = json.loads(await get_skill_health_impl("ask", lambda n: entry))
    assert data["status"] == "degraded"


@pytest.mark.asyncio
async def test_get_skill_health_unknown_when_unresolved():
    """An unresolvable skill reports unknown with resolved=False."""
    data = json.loads(await get_skill_health_impl("nope", lambda n: None))
    assert data["status"] == "unknown"
    assert data["structure"]["resolved"] is False
