"""Tests for ownership filter in list-skills MCP tool."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_skills():
    """Create skill records with different ownership values.

    Use SimpleNamespace, NOT MagicMock — list_skills_impl uses `getattr(skill, "X",
    None)` for many optional fields, and MagicMock's __getattr__ auto-creates child
    mocks for every attribute access (which then JSON-serialization rejects). With
    SimpleNamespace, getattr(..., default) actually returns the default for fields
    we don't set.
    """
    records = []
    for name, ownership, origin, upstream in [
        ("ask", "augur", "augur", {}),
        ("ui-tool", "external", "claude-local", {}),
        ("shared", "adopted", "augur", {"repo": "owner/shared"}),
    ]:
        records.append(
            SimpleNamespace(
                name=name,
                display_name=name,
                description=f"{name} description",
                triggers=(),
                capabilities=(),
                token_estimate=100,
                has_modules=False,
                has_scripts=False,
                has_references=False,
                hub="dev",
                layer=None,
                master=None,
                plugin=None,
                source=origin,
                ownership=ownership,
                upstream=upstream,
                skill_type="domain",
                tags=(),
                origin=origin,
                author="bundled",
                # Remaining optional fields the impl probes via getattr(skill, X, None):
                visibility=None,
                category=None,
                group=None,
                release=None,
                requires_platform=None,
            )
        )
    return records


@pytest.mark.asyncio
async def test_list_skills_no_filter(mock_skills):
    """Without ownership filter, all skills returned."""
    from src.mcp.augur_core.tools.core.models import ListSkillsInput, ResponseFormat
    from src.mcp.augur_core.tools.core.skills import list_skills_impl

    params = ListSkillsInput(format=ResponseFormat.JSON)
    cache = MagicMock()
    cache.get.return_value = None
    metrics = MagicMock()

    result = await list_skills_impl(params, cache, metrics, lambda **kw: mock_skills)
    data = json.loads(result)
    assert data["count"] == 3


@pytest.mark.asyncio
async def test_list_skills_filter_augur(mock_skills):
    """Filter ownership=augur returns only managed Augur skills."""
    from src.mcp.augur_core.tools.core.models import ListSkillsInput, ResponseFormat
    from src.mcp.augur_core.tools.core.skills import list_skills_impl

    params = ListSkillsInput(format=ResponseFormat.JSON, ownership="augur")
    cache = MagicMock()
    cache.get.return_value = None
    metrics = MagicMock()

    result = await list_skills_impl(params, cache, metrics, lambda **kw: mock_skills)
    data = json.loads(result)
    assert data["count"] == 1
    assert data["skills"][0]["name"] == "ask"
    assert data["skills"][0]["ownership"] == "augur"


@pytest.mark.asyncio
async def test_list_skills_filter_external(mock_skills):
    """Filter ownership=external returns only external skills."""
    from src.mcp.augur_core.tools.core.models import ListSkillsInput, ResponseFormat
    from src.mcp.augur_core.tools.core.skills import list_skills_impl

    params = ListSkillsInput(format=ResponseFormat.JSON, ownership="external")
    cache = MagicMock()
    cache.get.return_value = None
    metrics = MagicMock()

    result = await list_skills_impl(params, cache, metrics, lambda **kw: mock_skills)
    data = json.loads(result)
    assert data["count"] == 1
    assert data["skills"][0]["name"] == "ui-tool"
    assert data["skills"][0]["origin"] == "claude-local"
    assert data["skills"][0]["upstream"] == {}


@pytest.mark.asyncio
async def test_list_skills_filter_adopted(mock_skills):
    """Filter ownership=adopted returns adopted skills with upstream metadata."""
    from src.mcp.augur_core.tools.core.models import ListSkillsInput, ResponseFormat
    from src.mcp.augur_core.tools.core.skills import list_skills_impl

    params = ListSkillsInput(format=ResponseFormat.JSON, ownership="adopted")
    cache = MagicMock()
    cache.get.return_value = None
    metrics = MagicMock()

    result = await list_skills_impl(params, cache, metrics, lambda **kw: mock_skills)
    data = json.loads(result)
    assert data["count"] == 1
    assert data["skills"][0]["name"] == "shared"
    assert data["skills"][0]["ownership"] == "adopted"
    assert data["skills"][0]["upstream"] == {"repo": "owner/shared"}


@pytest.mark.asyncio
async def test_list_skills_emits_ownership_and_upstream(mock_skills):
    """The JSON payload includes ownership, upstream, and origin."""
    from src.mcp.augur_core.tools.core.models import ListSkillsInput, ResponseFormat
    from src.mcp.augur_core.tools.core.skills import list_skills_impl

    params = ListSkillsInput(format=ResponseFormat.JSON)
    cache = MagicMock()
    cache.get.return_value = None
    metrics = MagicMock()

    result = await list_skills_impl(params, cache, metrics, lambda **kw: mock_skills)
    data = json.loads(result)

    shared = next(skill for skill in data["skills"] if skill["name"] == "shared")
    assert shared["ownership"] == "adopted"
    assert shared["upstream"] == {"repo": "owner/shared"}
    assert shared["origin"] == "augur"


@pytest.mark.asyncio
async def test_list_skills_cache_key_uses_ownership(mock_skills):
    """Cache keys should be partitioned by ownership filter, not source."""
    from src.mcp.augur_core.tools.core.models import ListSkillsInput, ResponseFormat
    from src.mcp.augur_core.tools.core.skills import list_skills_impl

    params = ListSkillsInput(format=ResponseFormat.JSON, ownership="external")
    cache = MagicMock()
    cache.get.return_value = None
    metrics = MagicMock()

    await list_skills_impl(params, cache, metrics, lambda **kw: mock_skills)

    assert cache.get.call_args[0][0] == "list_skills:ResponseFormat.JSON:external"
