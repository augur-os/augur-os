import pytest

from src.config.paths import invalidate_project_cache

from skills.wiki.scripts.wiki_query_registry import (
    SOURCE_KINDS,
    QueryRegistryError,
    delete_query,
    list_queries,
    load_registry,
    validate_query_spec,
    write_query,
)


@pytest.fixture(autouse=True)
def _clear_path_cache():
    invalidate_project_cache()
    yield
    invalidate_project_cache()


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


def test_source_kinds_closed_enum():
    assert SOURCE_KINDS == frozenset(
        {
            "memory_md",
            "daily_logs",
            "ask_retention",
            "adr_index",
            "git_recent_commits",
            "inbox",
            "linked_folder",
        }
    )


def test_validate_minimal_valid_query():
    validate_query_spec("test", _valid_spec())


def test_validate_rejects_unknown_source_kind():
    with pytest.raises(QueryRegistryError, match="unknown source kind"):
        validate_query_spec("test", _valid_spec(sources=[{"kind": "INVALID_KIND"}]))


def test_validate_rejects_non_manual_refresh_policy_in_v1():
    with pytest.raises(QueryRegistryError, match="refresh_policy"):
        validate_query_spec("test", _valid_spec(refresh_policy="weekly"))


def test_load_empty_registry(tmp_path, monkeypatch):
    monkeypatch.setenv("AUGUR_VAULT", str(tmp_path))
    registry = load_registry()
    assert registry == {"version": 1, "queries": {}}


def test_write_query_and_reload(tmp_path, monkeypatch):
    monkeypatch.setenv("AUGUR_VAULT", str(tmp_path))
    write_query("test", _valid_spec())
    queries = list_queries()
    assert "test" in queries
    assert queries["test"]["title"] == "Test query"


def test_delete_query_removes_from_yaml(tmp_path, monkeypatch):
    monkeypatch.setenv("AUGUR_VAULT", str(tmp_path))
    write_query("test", _valid_spec(title="Test", description="x", prompt_template="x", output="vault/wiki/t.md"))
    assert "test" in list_queries()
    assert delete_query("test") is True
    assert "test" not in list_queries()


def test_validate_rejects_output_outside_vault_wiki(tmp_path, monkeypatch):
    monkeypatch.setenv("AUGUR_VAULT", str(tmp_path))
    with pytest.raises(QueryRegistryError, match="output path must be under vault/wiki/"):
        validate_query_spec("test", _valid_spec(output="../../etc/passwd"))


def test_validate_rejects_duplicate_output_path(tmp_path, monkeypatch):
    monkeypatch.setenv("AUGUR_VAULT", str(tmp_path))
    spec_a = _valid_spec(title="A", output="vault/wiki/same.md")
    spec_b = _valid_spec(title="B", output="vault/wiki/same.md")
    write_query("a", spec_a)
    with pytest.raises(QueryRegistryError, match="output path already claimed"):
        write_query("b", spec_b)
