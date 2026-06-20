import json
from pathlib import Path
from types import SimpleNamespace

import pytest


class CapturingMCP:
    def __init__(self) -> None:
        self.tools = {}

    def tool(self, *args, **kwargs):
        name = kwargs.get("name")
        if name is None and args and isinstance(args[0], str):
            name = args[0]

        def decorator(func):
            self.tools[name or func.__name__] = func
            return func

        return decorator


def _registered_core_tools() -> CapturingMCP:
    from src.mcp.augur_core.tools.core import register_core_tools

    mcp = CapturingMCP()
    register_core_tools(
        mcp,
        registry_list_skills=lambda *args, **kwargs: [],
        resolve_skill_entry=lambda *args, **kwargs: None,
        available_skill_ids=lambda *args, **kwargs: [],
    )
    return mcp


def _patch_career_discovery(monkeypatch, vault_dir: Path) -> None:
    from src.mcp.augur_shared import config as shared_config
    from src.plugins import skill_discovery

    monkeypatch.setattr(shared_config, "_get_vault_dir", lambda: vault_dir)
    monkeypatch.setattr(
        skill_discovery,
        "discover_all_skills",
        lambda *args, **kwargs: [SimpleNamespace(name="career-ops", hub="career")],
    )


@pytest.mark.asyncio
async def test_registered_hub_recent_wrapper_uses_vault_root(monkeypatch, tmp_path: Path):
    """The MCP wrapper must pass the vault root, not a derived skill parent."""
    _patch_career_discovery(monkeypatch, tmp_path)
    skill_dir = tmp_path / "career" / "data"
    skill_dir.mkdir(parents=True)
    (skill_dir / "applications.md").write_text("---\ntitle: Applications\n---\nPipeline")

    mcp = _registered_core_tools()
    result = json.loads(
        await mcp.tools["list-hub-recent-files"](
            hub_id="career",
            limit=10,
            per_skill_limit=2,
        )
    )

    assert result["count"] == 1
    assert result["files"][0]["path"] == "career/data/applications.md"
    assert result["files"][0]["skill"] == "career-ops"


@pytest.mark.asyncio
async def test_registered_hub_vault_notes_wrapper_uses_vault_root(monkeypatch, tmp_path: Path):
    """The MCP wrapper must keep domain-first roots relative to vault root."""
    _patch_career_discovery(monkeypatch, tmp_path)
    skill_dir = tmp_path / "career"
    skill_dir.mkdir(parents=True)
    (skill_dir / "cv.md").write_text("---\ntitle: CV\n---\nCareer summary")

    mcp = _registered_core_tools()
    result = json.loads(
        await mcp.tools["list-hub-vault-notes"](
            hub_id="career",
            limit=10,
            per_skill_limit=2,
        )
    )

    assert result["count"] == 1
    assert result["notes"][0]["name"] == "cv.md"
    assert result["notes"][0]["skill"] == "career-ops"
