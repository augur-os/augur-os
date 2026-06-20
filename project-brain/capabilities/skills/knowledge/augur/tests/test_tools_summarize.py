"""Auto-generated importability test for tools_summarize."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_tools_summarize_importable():
    """Verify that tools_summarize can be imported without errors."""
    import importlib
    mod = importlib.import_module("skills.knowledge.scripts.mcp.tools_summarize")
    assert mod is not None


class _FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, name: str, annotations=None):
        def decorator(fn):
            self.tools[name] = fn
            return fn

        return decorator


class _FakeMetrics:
    def track_tool(self, *_args, **_kwargs):
        return None


def _identity(fn):
    return fn


def test_knowledge_summarize_file_uses_need_based_extraction_policy():
    import importlib

    mod = importlib.import_module("skills.knowledge.scripts.mcp.tools_summarize")
    fake_mcp = _FakeMCP()
    mod.register_summarize_tools(fake_mcp, _identity, _FakeMetrics())

    calls = []

    def fake_extract(path: str, max_tier: int = 0):
        calls.append((path, max_tier))
        return SimpleNamespace(
            success=True,
            markdown="extracted",
            title="doc",
            format="pdf",
            size_bytes=12,
            error=None,
        )

    async def run_tool():
        with patch.object(mod, "extract", fake_extract):
            tool = fake_mcp.tools["knowledge-summarize-file"]
            raw = await tool("/tmp/sample.pdf")
        return json.loads(raw)

    result = asyncio.run(run_tool())

    assert result["success"] is True
    assert calls == [("/tmp/sample.pdf", 1)]
