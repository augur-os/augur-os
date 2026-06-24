"""Unit tests for src.lib.capabilities._discovery_helpers.

Exercises the pure/deterministic capability-discovery helpers: id
normalization, source-derived exposure/scope, owner/management mapping,
policy parsing, and record/metadata merging.
"""

from __future__ import annotations

from pathlib import Path

from src.lib.capabilities._discovery_helpers import (
    _client_from_source,
    _declared_cli_names,
    _exposure_from_sources,
    _is_relative_to,
    _is_truthy,
    _management,
    _merge_capability_records,
    _merge_metadata,
    _metadata_values,
    _owner_kind,
    _path_for_source,
    _policy_list,
    _scope_from_sources,
    _unique_items,
    capability_id,
)
from src.lib.capabilities.exposure_policy import CapabilityDiscovery


def test_capability_id_normalizes_and_prefixes():
    assert capability_id("mcp-tool", "Browse Index") == "mcp-tool:browse-index"
    assert capability_id("skill", "  Foo__Bar!! ") == "skill:foo-bar"
    # Non-string input is coerced via str().
    assert capability_id("cli", 123) == "cli:123"


def test_client_from_source_matches_prefix_and_exact():
    assert _client_from_source("claude") == "claude"
    assert _client_from_source("CODEX-runtime") == "codex"
    assert _client_from_source("gemini-cli") == "gemini"
    assert _client_from_source("") == ""
    assert _client_from_source("unknown-tool") == ""


def test_exposure_from_sources_dedupes_and_filters():
    result = _exposure_from_sources(["claude", "claude-code", "codex", "random"])
    # claude appears twice (claude / claude-code) but dedupes; random dropped.
    assert result == ("claude", "codex")


def test_scope_from_sources_global_project_mixed():
    assert _scope_from_sources(["global-augur"]) == "global"
    assert _scope_from_sources(["project-foo"]) == "project"
    assert _scope_from_sources(["local-skill"]) == "project"
    assert _scope_from_sources(["global", "local"]) == "mixed"
    # No recognizable tags defaults to project.
    assert _scope_from_sources(["", "  "]) == "project"


def test_owner_kind_mapping():
    assert _owner_kind("external") == "external"
    assert _owner_kind("USER") == "user"
    assert _owner_kind("adopted") == "adopted"
    assert _owner_kind(None) == "augur"
    assert _owner_kind("anything-else") == "augur"


def test_management_mapping():
    assert _management("external-client") == "unmanaged"
    assert _management("plugin-cache") == "unmanaged"
    assert _management("project-brain") == "generated"
    assert _management(None) == "generated"


def test_policy_list_handles_str_list_and_other():
    assert _policy_list("a, b ,b, c") == ("a", "b", "c")
    assert _policy_list(["x", "x", "y"]) == ("x", "y")
    assert _policy_list(None) == ()
    assert _policy_list(123) == ()


def test_is_truthy():
    assert _is_truthy(True) is True
    assert _is_truthy(False) is False
    assert _is_truthy("yes") is True
    assert _is_truthy("ON") is True
    assert _is_truthy("0") is False
    assert _is_truthy(None) is False


def test_declared_cli_names_from_str_and_dicts():
    assert list(_declared_cli_names("one, two ,")) == ["one", "two"]
    items = [{"name": "alpha"}, {"id": "beta"}, "gamma", {"other": "skip"}]
    assert list(_declared_cli_names(items)) == ["alpha", "beta", "gamma"]
    assert list(_declared_cli_names(42)) == []


def test_is_relative_to(tmp_path: Path):
    child = tmp_path / "a" / "b.py"
    child.parent.mkdir(parents=True)
    child.write_text("x")
    assert _is_relative_to(child, tmp_path) is True
    assert _is_relative_to(tmp_path, child) is False


def test_path_for_source_relative_and_absolute(tmp_path: Path):
    py_file = tmp_path / "pkg" / "mod.py"
    py_file.parent.mkdir(parents=True)
    py_file.write_text("x")
    assert _path_for_source(py_file, tmp_path) == "pkg/mod.py"
    # root None -> absolute string.
    assert _path_for_source(py_file, None) == str(py_file)
    # py_file not under an unrelated root -> falls back to absolute string.
    other = tmp_path / "elsewhere"
    other.mkdir()
    assert _path_for_source(py_file, other) == str(py_file)


def test_unique_items_and_metadata_values():
    assert _unique_items(["a", "b"], ["b", "c", ""]) == ("a", "b", "c")
    assert _metadata_values("x, y ,, z") == ("x", "y", "z")


def test_merge_metadata_primary_surface_skill_and_conflicts():
    existing = {"primary_surface": "browse", "skill": "alpha", "owner": "augur"}
    incoming = {
        "primary_surface": "mcp",  # setdefault -> keeps existing
        "skill": "beta",           # union-merged
        "owner": "user",           # conflict -> union
        "new": "value",            # added
        "empty": "",               # skipped
    }
    merged = _merge_metadata(existing, incoming)
    assert merged["primary_surface"] == "browse"
    assert merged["skill"] == "alpha,beta"
    assert merged["owner"] == "augur,user"
    assert merged["new"] == "value"
    assert "empty" not in merged


def test_merge_capability_records_combines_same_id():
    rec_a = CapabilityDiscovery(
        id="mcp-tool:foo",
        type="mcp-tool",
        source_paths=("a.py",),
        current_exposure=("mcp",),
        metadata={"skill": "alpha"},
    )
    rec_b = CapabilityDiscovery(
        id="mcp-tool:foo",
        type="mcp-tool",
        source_paths=("b.py",),
        current_exposure=("browse",),
        metadata={"skill": "beta"},
    )
    rec_c = CapabilityDiscovery(id="skill:bar", type="skill")
    merged = _merge_capability_records([rec_b, rec_a, rec_c])
    # Sorted by id: mcp-tool:foo before skill:bar.
    assert [m.id for m in merged] == ["mcp-tool:foo", "skill:bar"]
    foo = merged[0]
    assert foo.source_paths == ("b.py", "a.py")
    assert foo.current_exposure == ("browse", "mcp")
    assert foo.metadata["skill"] == "beta,alpha"
