from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path


RUNNER_PATH = Path(__file__).resolve().parents[2] / "scripts" / "run_wiki_batched_daily.py"


def test_runner_calls_wiki_update_with_defaults(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def fake_run(limit: int = 20, tier: str = "") -> str:
        captured["limit"] = limit
        captured["tier"] = tier
        return json.dumps({"success": True, "status": "no_change"})

    spec = importlib.util.spec_from_file_location("run_wiki_batched_daily_under_test", RUNNER_PATH)
    assert spec and spec.loader
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)

    from skills.wiki.scripts.mcp import wiki_tools

    monkeypatch.setattr(wiki_tools, "_run_wiki_update", fake_run)

    rc = asyncio.run(runner._run())

    assert rc == 0
    assert captured == {"limit": 20, "tier": ""}
