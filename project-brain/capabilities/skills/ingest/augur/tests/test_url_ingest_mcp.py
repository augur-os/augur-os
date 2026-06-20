from __future__ import annotations

import json
from inspect import signature
from pathlib import Path

import httpx
import pytest

from src.lib.frontmatter_utils import parse_frontmatter

from src.lib.ingest import note_index_refresh
from skills.ingest.scripts.mcp import url_tools
from skills.ingest.scripts.mcp.url_tools import (
    save_url_source_impl,
    url_extract_impl,
)
from skills.ingest.scripts.url_ingest import fetch_and_extract

FIXTURES = Path(__file__).parent / "fixtures"


def _write_project_registry(tmp_path: Path) -> tuple[Path, Path, Path]:
    from src.lib.brain_manifest import (
        BrainManifest,
        ensure_brain_skeleton,
        write_brain_manifest,
    )
    from src.lib.brain_registry_io import save_registry
    from src.lib.brain_registry_models import (
        Brain,
        BrainRegistry,
        BrainType,
        GitArrangement,
        GitConfig,
    )

    personal = tmp_path / "personal"
    project = tmp_path / "repo"
    brain_root = project / "project-brain"
    ensure_brain_skeleton(brain_root)
    write_brain_manifest(
        brain_root,
        BrainManifest(
            schema_version=1,
            id="project-repo",
            type=BrainType.PROJECT,
            root=str(brain_root),
            attached_project=str(project),
        ),
    )
    registry_path = tmp_path / "brains.yaml"
    save_registry(
        BrainRegistry(
            version=1,
            brains={
                "personal": Brain(
                    id="personal",
                    type=BrainType.PERSONAL,
                    data_root=personal,
                    git=GitConfig(arrangement=GitArrangement.UNTRACKED),
                )
            },
        ),
        registry_path,
    )
    return registry_path, project, brain_root


def _transport_for_simple_article() -> httpx.MockTransport:
    return httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            content=(FIXTURES / "article_simple.html").read_bytes(),
            headers={"content-type": "text/html; charset=utf-8"},
        )
    )


async def _fake_fetch(url: str) -> dict[str, str]:
    return fetch_and_extract(url, _transport=_transport_for_simple_article())


# ---------------------------------------------------------------------------
# url-extract atomic op
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_url_extract_returns_parsed_content() -> None:
    result = json.loads(
        await url_extract_impl(
            url="https://example.com/why-trees-matter?utm_source=newsletter",
            fetcher=_fake_fetch,
        )
    )

    assert result["success"] is True
    assert result["canonical_url"] == "https://example.com/why-trees-matter"
    assert result["title"] == "Why Trees Matter"
    assert "lungs of the planet" in result["body"]
    assert isinstance(result["content_hash"], str)
    assert result["content_hash"].startswith("sha256:")
    assert len(result["content_hash"]) == len("sha256:") + 64


@pytest.mark.asyncio
async def test_url_extract_missing_url_returns_error() -> None:
    result = json.loads(await url_extract_impl(url="", fetcher=_fake_fetch))
    assert result == {"success": False, "error": "url is required"}


@pytest.mark.asyncio
async def test_url_extract_canonicalization_strips_tracking() -> None:
    a = json.loads(
        await url_extract_impl(
            url="https://example.com/a?utm_source=twitter", fetcher=_fake_fetch
        )
    )
    b = json.loads(
        await url_extract_impl(
            url="https://example.com/a?gclid=xyz", fetcher=_fake_fetch
        )
    )
    assert a["canonical_url"] == b["canonical_url"]
    assert a["content_hash"] == b["content_hash"]


# ---------------------------------------------------------------------------
# save-url-source atomic op
# ---------------------------------------------------------------------------


async def _extract(url: str) -> dict:
    return json.loads(await url_extract_impl(url=url, fetcher=_fake_fetch))


@pytest.mark.asyncio
async def test_save_url_source_writes_card(tmp_path: Path) -> None:
    parsed = await _extract(
        "https://example.com/why-trees-matter?utm_source=newsletter"
    )
    result = json.loads(
        await save_url_source_impl(
            url=parsed["canonical_url"],
            title=parsed["title"],
            body=parsed["body"],
            tags='["ecology", "trees"]',
            vault_dir=tmp_path,
        )
    )

    assert result["success"] is True
    assert result["deduplicated"] is False
    card_path = Path(result["path"])
    assert card_path.parent == tmp_path / "knowledge" / "notes"
    frontmatter, body = parse_frontmatter(card_path)
    assert frontmatter["title"] == "Why Trees Matter"
    assert frontmatter["source_type"] == "url"
    assert frontmatter["x-augur-note-type"] == "url"
    assert frontmatter["canonical_url"] == "https://example.com/why-trees-matter"
    assert frontmatter["tags"] == ["ecology", "trees"]
    assert "lungs of the planet" in body


def test_save_url_source_tool_accepts_cli_json_list_tags() -> None:
    class FakeMcp:
        def __init__(self) -> None:
            self.tools = {}

        def tool(self, name, annotations=None):
            def decorator(func):
                self.tools[name] = func
                return func

            return decorator

    fake = FakeMcp()
    url_tools.register_url_tools(fake, lambda func: func, None)

    tags_param = signature(fake.tools["save-url-source"]).parameters["tags"]
    assert "list" in str(tags_param.annotation)


@pytest.mark.asyncio
async def test_save_url_source_routes_to_project_brain_from_cwd(
    monkeypatch,
    tmp_path: Path,
) -> None:
    registry_path, project, brain_root = _write_project_registry(tmp_path)
    parsed = await _extract("https://example.com/why-trees-matter")

    monkeypatch.setattr(
        url_tools,
        "refresh_notes_browse_index",
        lambda *, vault_dir: note_index_refresh.NoteBrowseIndexRefresh(
            success=True,
            count=1,
        ),
    )

    result = json.loads(
        await url_tools.save_url_source_impl(
            url=parsed["canonical_url"],
            title=parsed["title"],
            body=parsed["body"],
            cwd=project / "src",
            registry_path=registry_path,
        )
    )

    assert result["success"] is True
    assert result["brain"] == {
        "id": "project-repo",
        "type": "project",
        "reason": "active-project",
        "mode": "direct",
    }
    assert Path(result["path"]).parent == brain_root / "knowledge" / "notes"


@pytest.mark.asyncio
async def test_save_url_source_refreshes_browse_index_for_new_card(
    monkeypatch, tmp_path: Path
) -> None:
    parsed = await _extract("https://example.com/why-trees-matter")
    calls: list[Path] = []

    def fake_refresh(*, vault_dir: Path) -> note_index_refresh.NoteBrowseIndexRefresh:
        calls.append(vault_dir)
        return note_index_refresh.NoteBrowseIndexRefresh(success=True, count=12)

    monkeypatch.setattr(url_tools, "refresh_notes_browse_index", fake_refresh)

    result = json.loads(
        await url_tools.save_url_source_impl(
            url=parsed["canonical_url"],
            title=parsed["title"],
            body=parsed["body"],
            tags='["ecology"]',
            vault_dir=tmp_path,
        )
    )

    assert result["success"] is True
    assert result["deduplicated"] is False
    assert result["browse_index"] == {"success": True, "count": 12}
    assert calls == [tmp_path]


@pytest.mark.asyncio
async def test_save_url_source_deduped_card_does_not_claim_new_browse_refresh(
    monkeypatch,
    tmp_path: Path,
) -> None:
    parsed = await _extract("https://example.com/why-trees-matter")
    calls: list[Path] = []

    def fake_refresh(*, vault_dir: Path) -> note_index_refresh.NoteBrowseIndexRefresh:
        calls.append(vault_dir)
        return note_index_refresh.NoteBrowseIndexRefresh(success=True, count=12)

    monkeypatch.setattr(url_tools, "refresh_notes_browse_index", fake_refresh)
    args = dict(
        url=parsed["canonical_url"],
        title=parsed["title"],
        body=parsed["body"],
        tags='["ecology"]',
        vault_dir=tmp_path,
    )

    first = json.loads(await url_tools.save_url_source_impl(**args))
    second = json.loads(await url_tools.save_url_source_impl(**args))

    assert first["deduplicated"] is False
    assert first["browse_index"] == {"success": True, "count": 12}
    assert second["deduplicated"] is True
    assert "browse_index" not in second
    assert calls == [tmp_path]


@pytest.mark.asyncio
async def test_save_url_source_deduplicates(tmp_path: Path) -> None:
    parsed = await _extract("https://example.com/why-trees-matter")
    args = dict(
        url=parsed["canonical_url"],
        title=parsed["title"],
        body=parsed["body"],
        tags='["ecology"]',
        vault_dir=tmp_path,
    )

    first = json.loads(await save_url_source_impl(**args))
    second = json.loads(await save_url_source_impl(**args))

    assert second["deduplicated"] is True
    assert second["path"] == first["path"]
    assert second["sha256"] == first["sha256"]
    cards = list((tmp_path / "knowledge" / "notes").glob("*.md"))
    assert len(cards) == 1


@pytest.mark.asyncio
async def test_save_url_source_canonicalizes_url_before_hash(tmp_path: Path) -> None:
    parsed = await _extract("https://example.com/a?utm_source=twitter")

    first = json.loads(
        await save_url_source_impl(
            url="https://example.com/a?utm_source=twitter",
            title=parsed["title"],
            body=parsed["body"],
            vault_dir=tmp_path,
        )
    )
    second = json.loads(
        await save_url_source_impl(
            url="https://example.com/a?gclid=xyz",
            title=parsed["title"],
            body=parsed["body"],
            vault_dir=tmp_path,
        )
    )

    assert first["sha256"] == second["sha256"]
    assert second["deduplicated"] is True


@pytest.mark.asyncio
async def test_save_url_source_invalid_tags_returns_error(tmp_path: Path) -> None:
    result = json.loads(
        await save_url_source_impl(
            url="https://example.com/a",
            title="t",
            body="b",
            tags="not-json",
            vault_dir=tmp_path,
        )
    )
    assert result == {"success": False, "error": "tags must be a JSON list"}


@pytest.mark.asyncio
async def test_save_url_source_requires_url_and_body(tmp_path: Path) -> None:
    missing_url = json.loads(
        await save_url_source_impl(
            url="", title="t", body="b", vault_dir=tmp_path,
        )
    )
    assert missing_url == {"success": False, "error": "url is required"}

    missing_body = json.loads(
        await save_url_source_impl(
            url="https://example.com/a", title="t", body="", vault_dir=tmp_path,
        )
    )
    assert missing_body == {"success": False, "error": "body is required"}


@pytest.mark.asyncio
async def test_save_url_source_falls_back_to_url_when_title_blank(tmp_path: Path) -> None:
    result = json.loads(
        await save_url_source_impl(
            url="https://example.com/a",
            title="   ",
            body="some body",
            vault_dir=tmp_path,
        )
    )
    assert result["success"] is True
    assert result["title"] == "https://example.com/a"


# ---------------------------------------------------------------------------
# Composition test: extract then save (mirrors the dashboard path)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_then_save_round_trip(tmp_path: Path) -> None:
    parsed = json.loads(
        await url_extract_impl(
            url="https://example.com/why-trees-matter?utm_source=newsletter",
            fetcher=_fake_fetch,
        )
    )
    saved = json.loads(
        await save_url_source_impl(
            url=parsed["canonical_url"],
            title=parsed["title"],
            body=parsed["body"],
            tags='["ecology"]',
            vault_dir=tmp_path,
        )
    )

    assert saved["success"] is True
    assert saved["sha256"] == parsed["content_hash"]
    assert saved["canonical_url"] == parsed["canonical_url"]
