"""list-prompts must also surface user prompts from <vault>/prompts/."""
from __future__ import annotations

import json

import pytest

from src.mcp.augur_framework.tools.infrastructure.browse.skills import list_prompts_impl
import src.config.paths as paths
from skills.ingest.scripts.prompt_cards import write_prompt_card


@pytest.fixture(autouse=True)
def _clear_path_cache():
    yield
    paths.invalidate_project_cache()


@pytest.mark.asyncio
async def test_list_prompts_includes_vault_prompts(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "_vault_home_dir", lambda: tmp_path / "vault")
    (tmp_path / "vault").mkdir()
    paths.invalidate_project_cache()
    write_prompt_card(
        vault_dir=tmp_path / "vault", label="Define a Goal",
        description="Define then act", body="State your {{goal}}.", source_url="",
    )

    result = json.loads(await list_prompts_impl())
    vault_items = [i for i in result["items"] if i.get("source") == "vault"]
    assert any(i["title"] == "Define a Goal" for i in vault_items)
    assert all("path" in i for i in vault_items)
    assert all(i["id"].startswith("vault/prompts/") for i in vault_items)
