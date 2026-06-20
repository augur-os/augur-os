from __future__ import annotations

import json
from pathlib import Path


def test_reflect_context_appends_ask_history(tmp_path: Path, monkeypatch) -> None:
    from skills.knowledge.scripts.mcp import tools_reflect

    runtime_dir = tmp_path / "runtime"
    monkeypatch.setattr(tools_reflect, "get_runtime_dir", lambda: runtime_dir)

    tools_reflect._append_ask_history("What should I work on?", {"answers": ["a"]})

    history = runtime_dir / "ask-history.jsonl"
    rows = [json.loads(line) for line in history.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["query_hash"]
    assert rows[0]["query_preview"] == "What should I work on?"
    assert rows[0]["result_keys"] == ["answers"]
