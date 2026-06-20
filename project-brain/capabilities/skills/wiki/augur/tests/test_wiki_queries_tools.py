from __future__ import annotations

import asyncio
import json
from pathlib import Path

from src.config.paths import invalidate_project_cache


def _valid_spec(**overrides):
    spec = {
        "title": "Test query",
        "description": "test",
        "prompt_template": "Synthesize from {{sources}}",
        "sources": [{"kind": "memory_md"}],
        "output": "vault/wiki/test.md",
        "page_type": "query",
        "required_sections": ["Result"],
        "refresh_policy": "manual",
    }
    spec.update(overrides)
    return spec


def _set_vault(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUGUR_VAULT", str(tmp_path))
    invalidate_project_cache()


def test_wiki_queries_list_returns_specs_and_status(monkeypatch, tmp_path: Path) -> None:
    from skills.wiki.scripts.wiki_query_registry import write_query
    from skills.wiki.scripts.mcp import wiki_queries_tools

    _set_vault(monkeypatch, tmp_path)
    write_query("test", _valid_spec())
    state_path = tmp_path / "wiki" / ".queries-state.json"
    state_path.write_text(
        json.dumps(
            {
                "test": {
                    "last_run": "2026-05-12T10:00:00+00:00",
                    "last_error": None,
                }
            }
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "wiki" / "test.md"
    output_path.write_text(
        "---\nsource_fingerprint: abc123\n---\n## Result\nBody\n",
        encoding="utf-8",
    )

    payload = json.loads(asyncio.run(wiki_queries_tools.wiki_queries_list_impl()))

    assert payload["success"] is True
    assert payload["count"] == 1
    assert payload["queries"][0]["id"] == "test"
    assert payload["queries"][0]["spec"]["title"] == "Test query"
    assert payload["queries"][0]["status"] == {
        "last_run": "2026-05-12T10:00:00+00:00",
        "last_error": None,
        "output_size": output_path.stat().st_size,
        "source_fingerprint": "abc123",
    }


def test_wiki_queries_read_returns_one_spec(monkeypatch, tmp_path: Path) -> None:
    from skills.wiki.scripts.wiki_query_registry import write_query
    from skills.wiki.scripts.mcp import wiki_queries_tools

    _set_vault(monkeypatch, tmp_path)
    write_query("test", _valid_spec(title="Read me"))

    payload = json.loads(asyncio.run(wiki_queries_tools.wiki_queries_read_impl(id="test")))

    assert payload["success"] is True
    assert payload["id"] == "test"
    assert payload["spec"]["title"] == "Read me"
    assert payload["status"]["last_run"] is None
    assert payload["status"]["last_error"] is None
    assert payload["status"]["output_size"] == 0
    assert payload["status"]["source_fingerprint"] is None


def test_wiki_queries_read_returns_error_for_missing_query(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.wiki.scripts.mcp import wiki_queries_tools

    _set_vault(monkeypatch, tmp_path)

    payload = json.loads(asyncio.run(wiki_queries_tools.wiki_queries_read_impl(id="missing")))

    assert payload["success"] is False
    assert "Query not found: missing" in payload["error"]


def test_register_wiki_queries_tools_exposes_list_and_read() -> None:
    from skills.wiki.scripts.mcp import register_tools

    class FakeMcp:
        def __init__(self) -> None:
            self.tools = {}
            self.annotations = {}

        def tool(self, name, annotations=None):
            def decorator(func):
                self.tools[name] = func
                self.annotations[name] = annotations
                return func

            return decorator

    fake = FakeMcp()
    register_tools(fake, lambda func: func, None)

    assert "wiki-queries-list" in fake.tools
    assert "wiki-queries-read" in fake.tools
    assert "wiki-queries-run" in fake.tools
    assert fake.annotations["wiki-queries-list"]["readOnlyHint"] is True
    assert fake.annotations["wiki-queries-read"]["readOnlyHint"] is True
    assert fake.annotations["wiki-queries-run"]["readOnlyHint"] is False


def test_wiki_queries_write_validates_and_persists(monkeypatch, tmp_path: Path) -> None:
    from skills.wiki.scripts.wiki_query_registry import read_query
    from skills.wiki.scripts.mcp import wiki_queries_tools

    _set_vault(monkeypatch, tmp_path)
    spec = _valid_spec(title="Written")

    payload = json.loads(
        asyncio.run(
            wiki_queries_tools.wiki_queries_write_impl(
                id="written",
                spec_json=json.dumps(spec),
            )
        )
    )

    assert payload["success"] is True
    assert payload["id"] == "written"
    assert payload["path"].endswith("wiki/queries.yaml")
    assert read_query("written")["title"] == "Written"


def test_wiki_queries_seed_defaults_only_adds_missing_queries(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.wiki.scripts.wiki_query_registry import read_query, write_query
    from skills.wiki.scripts.mcp import wiki_queries_tools

    _set_vault(monkeypatch, tmp_path)
    seed_path = tmp_path / "queries-defaults.yaml"
    seed_path.write_text(
        """
version: 1
queries:
  existing:
    title: Seed existing
    description: seed
    prompt_template: Seed from {{sources}}
    sources:
      - kind: memory_md
    output: vault/wiki/existing.md
    page_type: query
    required_sections:
      - Result
    refresh_policy: manual
  new-query:
    title: New default
    description: seed
    prompt_template: Seed from {{sources}}
    sources:
      - kind: memory_md
    output: vault/wiki/new-query.md
    page_type: query
    required_sections:
      - Result
    refresh_policy: manual
""".lstrip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(wiki_queries_tools, "DEFAULT_QUERIES_PATH", seed_path)
    write_query("existing", _valid_spec(title="User edited", output="vault/wiki/existing.md"))

    payload = json.loads(asyncio.run(wiki_queries_tools.wiki_queries_seed_defaults_impl()))

    assert payload["success"] is True
    assert payload["seeded"] == ["new-query"]
    assert payload["skipped"] == ["existing"]
    assert read_query("existing")["title"] == "User edited"
    assert read_query("new-query")["title"] == "New default"


def test_wiki_queries_run_returns_agent_action_required(monkeypatch, tmp_path: Path) -> None:
    from skills.wiki.scripts.wiki_query_runner import RunResult
    from skills.wiki.scripts.mcp import wiki_queries_tools

    _set_vault(monkeypatch, tmp_path)
    monkeypatch.setattr(
        wiki_queries_tools,
        "run_query",
        lambda query_id, synthesis_markdown=None: RunResult(
            success=True,
            query_id=query_id,
            status="agent_action_required",
            message="Agent synthesis required for wiki query 'test'.",
            prompt_path=str(tmp_path / "runtime" / "wiki" / "query-runs" / "test.md"),
            tokens_used=42,
        ),
    )

    payload = json.loads(asyncio.run(wiki_queries_tools.wiki_queries_run_impl(id="test")))

    assert payload["success"] is True
    assert payload["query_id"] == "test"
    assert payload["status"] == "agent_action_required"
    assert payload["prompt_path"].endswith("query-runs/test.md")


def test_wiki_queries_run_passes_agent_markdown_to_runner(monkeypatch, tmp_path: Path) -> None:
    from skills.wiki.scripts.wiki_query_runner import RunResult
    from skills.wiki.scripts.mcp import wiki_queries_tools

    _set_vault(monkeypatch, tmp_path)
    seen = {}

    def fake_run_query(query_id: str, synthesis_markdown: str | None = None) -> RunResult:
        seen["query_id"] = query_id
        seen["synthesis_markdown"] = synthesis_markdown
        return RunResult(
            success=True,
            query_id=query_id,
            status="complete",
            output_path=str(tmp_path / "wiki" / "test.md"),
            tokens_used=42,
            sections_validated=["Result"],
        )

    monkeypatch.setattr(wiki_queries_tools, "run_query", fake_run_query)

    payload = json.loads(
        asyncio.run(
            wiki_queries_tools.wiki_queries_run_impl(
                id="test",
                synthesis_markdown="## Result\nSynthesized by agent\n",
            )
        )
    )

    assert payload["success"] is True
    assert payload["status"] == "complete"
    assert seen == {
        "query_id": "test",
        "synthesis_markdown": "## Result\nSynthesized by agent\n",
    }


def test_wiki_queries_run_returns_missing_query_error(monkeypatch, tmp_path: Path) -> None:
    from skills.wiki.scripts.mcp import wiki_queries_tools

    _set_vault(monkeypatch, tmp_path)

    payload = json.loads(asyncio.run(wiki_queries_tools.wiki_queries_run_impl(id="missing")))

    assert payload["success"] is False
    assert payload["query_id"] == "missing"
    assert payload["error"] == "query not found: missing"


def test_wiki_queries_run_returns_llm_failure(monkeypatch, tmp_path: Path) -> None:
    from skills.wiki.scripts.wiki_query_runner import RunResult
    from skills.wiki.scripts.mcp import wiki_queries_tools

    _set_vault(monkeypatch, tmp_path)
    monkeypatch.setattr(
        wiki_queries_tools,
        "run_query",
        lambda query_id, synthesis_markdown=None: RunResult(
            success=False,
            query_id=query_id,
            error="LLM unavailable",
        ),
    )

    payload = json.loads(asyncio.run(wiki_queries_tools.wiki_queries_run_impl(id="test")))

    assert payload["success"] is False
    assert payload["error"] == "LLM unavailable"


def test_wiki_queries_run_returns_section_validation_failure(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.wiki.scripts.wiki_query_runner import RunResult
    from skills.wiki.scripts.mcp import wiki_queries_tools

    _set_vault(monkeypatch, tmp_path)
    monkeypatch.setattr(
        wiki_queries_tools,
        "run_query",
        lambda query_id, synthesis_markdown=None: RunResult(
            success=False,
            query_id=query_id,
            error="missing required H2 sections: Result",
        ),
    )

    payload = json.loads(asyncio.run(wiki_queries_tools.wiki_queries_run_impl(id="test")))

    assert payload["success"] is False
    assert payload["error"] == "missing required H2 sections: Result"


def test_wiki_queries_run_returns_already_running_error(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.wiki.scripts.wiki_query_runner import RunResult
    from skills.wiki.scripts.mcp import wiki_queries_tools

    _set_vault(monkeypatch, tmp_path)
    monkeypatch.setattr(
        wiki_queries_tools,
        "run_query",
        lambda query_id, synthesis_markdown=None: RunResult(
            success=False,
            query_id=query_id,
            error="query 'test' already running",
        ),
    )

    payload = json.loads(asyncio.run(wiki_queries_tools.wiki_queries_run_impl(id="test")))

    assert payload["success"] is False
    assert payload["error"] == "query 'test' already running"
