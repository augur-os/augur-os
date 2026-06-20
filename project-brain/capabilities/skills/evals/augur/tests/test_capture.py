"""Tests for capture.py — observer on/off/consent transitions (ADR-742).

Capture is off by default. The observer must be a no-op unless contributor
mode is on AND consent exists, must never raise into the tool path, and must
read the env var per-call (so the user can toggle mid-session).

Imports via importlib.util.spec_from_file_location per feedback_skill_test_convention.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"


def _load(module_name: str, file_name: str) -> Any:
    full_name = f"evals_{module_name}"
    if full_name in sys.modules:
        return sys.modules[full_name]
    spec = importlib.util.spec_from_file_location(full_name, SCRIPTS_DIR / file_name)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_capture_bootstraps_sibling_records_import_without_preload() -> None:
    """The MCP observer imports capture.py directly, without preloading records.py."""
    previous_records = sys.modules.pop("records", None)
    previous_path = list(sys.path)
    module_name = "evals_capture_standalone"
    sys.modules.pop(module_name, None)
    try:
        spec = importlib.util.spec_from_file_location(
            module_name, SCRIPTS_DIR / "capture.py"
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        assert callable(module.register_capture_observer())
    finally:
        sys.modules.pop(module_name, None)
        sys.modules.pop("records", None)
        if previous_records is not None:
            sys.modules["records"] = previous_records
        sys.path[:] = previous_path


@pytest.fixture()
def records() -> Any:
    return _load("records", "records.py")


@pytest.fixture()
def capture(records: Any) -> Any:
    return _load("capture", "capture.py")


@pytest.fixture()
def evals_tmp(
    records: Any, capture: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """Redirect eval artifact paths to a tmp dir and reset capture process state."""
    root = tmp_path / "evals"
    monkeypatch.setattr(records, "_docs_evals_dir", lambda: root)
    # capture.py caches the consent-banner-shown flag at module scope.
    monkeypatch.setattr(capture, "_CONSENT_BANNER_SHOWN", False, raising=False)
    # Ensure contributor mode starts unset.
    monkeypatch.delenv(capture.CONTRIBUTOR_ENV, raising=False)
    return root


def _search_result(*doc_ids: str) -> str:
    """A retrieval-tool-shaped JSON result string."""
    return json.dumps(
        {
            "success": True,
            "results": [
                {"file": d, "line": "1", "content": "...", "scope": "rag"}
                for d in doc_ids
            ],
        }
    )


# --------------------------------------------------------------------------
# Off-mode is the default
# --------------------------------------------------------------------------


def test_observer_noop_when_env_unset(capture: Any, evals_tmp: Path) -> None:
    """AUGUR_CONTRIBUTOR_MODE unset -> zero file growth."""
    capture.observe_tool_call(
        "unified-search", (), {"query": "test"}, _search_result("doc-a"), 10
    )
    assert not (evals_tmp / "queries").exists()


def test_observer_noop_when_consent_missing(
    capture: Any, evals_tmp: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Contributor mode on but no consent.md -> capture suppressed."""
    monkeypatch.setenv(capture.CONTRIBUTOR_ENV, "1")
    capture.observe_tool_call(
        "unified-search", (), {"query": "test"}, _search_result("doc-a"), 10
    )
    # No query file written.
    qdir = evals_tmp / "queries"
    assert not qdir.exists() or not list(qdir.glob("*.jsonl"))


def test_observer_captures_when_mode_and_consent(
    capture: Any, records: Any, evals_tmp: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Contributor mode on AND consent.md present -> a record is appended."""
    monkeypatch.setenv(capture.CONTRIBUTOR_ENV, "1")
    capture.write_consent()
    capture.observe_tool_call(
        "unified-search",
        (),
        {"query": "typed knowledge graphs", "top_k": 5},
        _search_result("doc-a", "doc-b"),
        42,
    )
    loaded = records.read_query_records()
    assert len(loaded) == 1
    rec = loaded[0]
    assert rec["query"] == "typed knowledge graphs"
    assert rec["tool"] == "unified-search"
    assert [r["id"] for r in rec["returned"]] == ["doc-a", "doc-b"]
    assert rec["returned"][0]["rank"] == 1


def test_observer_noop_for_non_allowlisted_tool(
    capture: Any, evals_tmp: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A tool not on the allowlist is never captured, even with mode + consent."""
    monkeypatch.setenv(capture.CONTRIBUTOR_ENV, "1")
    capture.write_consent()
    capture.observe_tool_call(
        "list-skills", (), {"query": "test"}, _search_result("doc-a"), 10
    )
    qdir = evals_tmp / "queries"
    assert not qdir.exists() or not list(qdir.glob("*.jsonl"))


# --------------------------------------------------------------------------
# Per-call env read — toggle mid-run
# --------------------------------------------------------------------------


def test_env_var_read_per_call(
    capture: Any, records: Any, evals_tmp: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The env var is read per call — toggling mid-run takes effect immediately."""
    capture.write_consent()
    # Mode off: no capture.
    capture.observe_tool_call(
        "unified-search", (), {"query": "q1"}, _search_result("doc-a"), 10
    )
    assert not records.read_query_records()
    # Toggle mode on: next call IS captured.
    monkeypatch.setenv(capture.CONTRIBUTOR_ENV, "1")
    capture.observe_tool_call(
        "unified-search", (), {"query": "q2"}, _search_result("doc-a"), 10
    )
    loaded = records.read_query_records()
    assert len(loaded) == 1
    assert loaded[0]["query"] == "q2"
    # Toggle back off: no further capture.
    monkeypatch.delenv(capture.CONTRIBUTOR_ENV)
    capture.observe_tool_call(
        "unified-search", (), {"query": "q3"}, _search_result("doc-a"), 10
    )
    assert len(records.read_query_records()) == 1


# --------------------------------------------------------------------------
# Never raises into the tool path
# --------------------------------------------------------------------------


def test_observer_never_raises_on_malformed_result(
    capture: Any, evals_tmp: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A malformed tool result must be swallowed, never raised."""
    monkeypatch.setenv(capture.CONTRIBUTOR_ENV, "1")
    capture.write_consent()
    # None, a non-JSON string, a non-dict — none of these may raise.
    capture.observe_tool_call("unified-search", (), {"query": "q"}, None, 10)
    capture.observe_tool_call("unified-search", (), {"query": "q"}, "not json", 10)
    capture.observe_tool_call("unified-search", (), {"query": "q"}, 12345, 10)
    capture.observe_tool_call("unified-search", (), {"query": "q"}, "[1,2,3]", 10)


def test_observer_never_raises_on_missing_query(
    capture: Any, evals_tmp: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No query in args -> nothing to capture, but no raise."""
    monkeypatch.setenv(capture.CONTRIBUTOR_ENV, "1")
    capture.write_consent()
    capture.observe_tool_call("unified-search", (), {}, _search_result("doc-a"), 10)


# --------------------------------------------------------------------------
# Caller tagging via contextvar
# --------------------------------------------------------------------------


def test_caller_tagging_sets_source(
    capture: Any, records: Any, evals_tmp: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """set_caller tags the captured record's `source` field."""
    monkeypatch.setenv(capture.CONTRIBUTOR_ENV, "1")
    capture.write_consent()
    token = capture.set_caller("/ask")
    try:
        capture.observe_tool_call(
            "unified-search", (), {"query": "tagged"}, _search_result("doc-a"), 10
        )
    finally:
        capture.reset_caller(token)
    loaded = records.read_query_records()
    assert len(loaded) == 1
    assert loaded[0]["source"] == "/ask"


def test_caller_defaults_to_direct(
    capture: Any, records: Any, evals_tmp: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unset caller -> source is 'direct'."""
    monkeypatch.setenv(capture.CONTRIBUTOR_ENV, "1")
    capture.write_consent()
    assert capture.active_caller() == "direct"
    capture.observe_tool_call(
        "unified-search", (), {"query": "untagged"}, _search_result("doc-a"), 10
    )
    loaded = records.read_query_records()
    assert loaded[0]["source"] == "direct"


def test_caller_reset_restores_prior(capture: Any) -> None:
    """reset_caller restores the previous caller value (no leakage)."""
    assert capture.active_caller() == "direct"
    token = capture.set_caller("/ask")
    assert capture.active_caller() == "/ask"
    capture.reset_caller(token)
    assert capture.active_caller() == "direct"


# --------------------------------------------------------------------------
# normalize_tool_name — dashed MCP name vs. python function name
# --------------------------------------------------------------------------


def test_normalize_tool_name(capture: Any) -> None:
    assert capture.normalize_tool_name("unified-search") == "unified-search"
    assert capture.normalize_tool_name("unified_search_tool") == "unified-search"
    assert (
        capture.normalize_tool_name("knowledge_project_index_search_tool")
        == "knowledge-project-index-search"
    )


def test_observer_matches_python_function_name(
    capture: Any, records: Any, evals_tmp: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The interceptor passes func.__name__ (e.g. unified_search_tool) — it must match."""
    monkeypatch.setenv(capture.CONTRIBUTOR_ENV, "1")
    capture.write_consent()
    capture.observe_tool_call(
        "unified_search_tool", (), {"query": "fnname"}, _search_result("doc-a"), 10
    )
    loaded = records.read_query_records()
    assert len(loaded) == 1
    assert loaded[0]["tool"] == "unified-search"  # normalized to dashed form


# --------------------------------------------------------------------------
# Consent flow
# --------------------------------------------------------------------------


def test_write_consent_creates_file(capture: Any, evals_tmp: Path) -> None:
    assert not capture.has_consent()
    path = capture.write_consent()
    assert path.is_file()
    assert capture.has_consent()
    text = path.read_text(encoding="utf-8")
    assert "opted_in_at" in text
    assert "What is captured" in text


def test_capture_status_shape(capture: Any, evals_tmp: Path) -> None:
    status = capture.capture_status()
    for key in (
        "enabled",
        "consent",
        "queries_captured_total",
        "queries_today",
        "last_capture_ts",
    ):
        assert key in status
    assert status["enabled"] is False
    assert status["consent"] is False
    assert status["queries_captured_total"] == 0
