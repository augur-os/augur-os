"""Unit tests for the Context Injector registry loader.

Covers payload validation, single-shot file loading, the cached/retrying
``load_registry`` entry point, and the startup health summary. All file IO
runs against ``tmp_path`` fixtures with monkeypatched candidate paths so the
tests never touch the real runtime ide-integration directory.
"""

from __future__ import annotations

import time as _time
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

import src.mcp.augur_shared.registry_loader as rl

_VALID_REGISTRY = {
    "skills": {
        "ask": {"modes": ["chat", "agent"], "description": "Ask the brain"},
        "keep": {"modes": ["agent"]},
    },
    "chains": {"research": {"steps": ["ask", "keep"]}},
    "workflows": {"daily": {"schedule": "0 9 * * *"}},
    "page_contexts": {"browse": {"skills": ["ask"]}},
}


@pytest.fixture(autouse=True)
def _reset_registry_state(monkeypatch):
    """Clear module-level cache/state and neutralise retry sleeps per test."""
    # Retry path sleeps 0.5s between attempts; make it instant.
    monkeypatch.setattr(_time, "sleep", lambda *a, **k: None)

    def _clear() -> None:
        rl._registry_cache = None
        rl._registry_cache_time = 0
        rl._registry_source_path = None
        rl._registry_last_error = None

    _clear()
    yield
    _clear()


def _write_registry(path: Path, payload) -> Path:
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
    else:
        path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# _validate_registry_payload
# ---------------------------------------------------------------------------


def test_validate_rejects_non_mapping():
    ok, err = rl._validate_registry_payload(["not", "a", "dict"])
    assert ok is False
    assert err == "Registry payload is not a mapping"


def test_validate_rejects_missing_required_section():
    ok, err = rl._validate_registry_payload({"chains": {}})
    assert ok is False
    assert err == "Missing required section 'skills'"


def test_validate_rejects_required_section_wrong_type():
    ok, err = rl._validate_registry_payload({"skills": ["a", "b"]})
    assert ok is False
    assert err == "Section 'skills' must be a mapping"


def test_validate_rejects_optional_section_wrong_type():
    ok, err = rl._validate_registry_payload({"skills": {}, "chains": [1, 2]})
    assert ok is False
    assert err == "Section 'chains' must be a mapping"


def test_validate_allows_missing_optional_sections():
    ok, err = rl._validate_registry_payload({"skills": {"ask": {}}})
    assert ok is True
    assert err == ""


def test_validate_allows_explicit_none_optional_sections():
    # Optional sections present as null must not be treated as wrong-type.
    ok, err = rl._validate_registry_payload(
        {"skills": {"ask": {}}, "chains": None, "workflows": None, "page_contexts": None}
    )
    assert ok is True
    assert err == ""


def test_validate_accepts_full_payload():
    ok, err = rl._validate_registry_payload(_VALID_REGISTRY)
    assert ok is True
    assert err == ""


# ---------------------------------------------------------------------------
# _try_load_registry_once
# ---------------------------------------------------------------------------


def test_try_load_skips_missing_candidate_without_error(tmp_path):
    missing = tmp_path / "nope.yaml"
    result, errors = rl._try_load_registry_once([missing])
    assert result is None
    # A non-existent path is skipped, not recorded as an error.
    assert errors == []


def test_try_load_returns_normalised_dict_and_source(tmp_path):
    path = _write_registry(tmp_path / "registry.yaml", _VALID_REGISTRY)
    result, errors = rl._try_load_registry_once([path])

    assert errors == []
    assert result is not None
    assert result["_source_path"] == path
    assert set(result) == {"skills", "chains", "workflows", "page_contexts", "_source_path"}
    assert result["skills"].keys() == {"ask", "keep"}
    assert result["chains"] == {"research": {"steps": ["ask", "keep"]}}


def test_try_load_defaults_optional_sections_to_empty(tmp_path):
    path = _write_registry(tmp_path / "registry.yaml", {"skills": {"ask": {}}})
    result, errors = rl._try_load_registry_once([path])

    assert errors == []
    assert result is not None
    assert result["skills"] == {"ask": {}}
    assert result["chains"] == {}
    assert result["workflows"] == {}
    assert result["page_contexts"] == {}


def test_try_load_records_parse_failure(tmp_path):
    # Unbalanced flow mapping -> YAML scanner/parser error.
    path = _write_registry(tmp_path / "registry.yaml", "skills: {unterminated")
    result, errors = rl._try_load_registry_once([path])

    assert result is None
    assert len(errors) == 1
    assert "parse failure" in errors[0]
    assert str(path) in errors[0]


def test_try_load_records_validation_failure(tmp_path):
    path = _write_registry(tmp_path / "registry.yaml", {"chains": {}})
    result, errors = rl._try_load_registry_once([path])

    assert result is None
    assert len(errors) == 1
    assert "Missing required section 'skills'" in errors[0]
    assert str(path) in errors[0]


def test_try_load_empty_file_fails_required_section(tmp_path):
    # Empty YAML -> None -> {} -> missing required 'skills'.
    path = _write_registry(tmp_path / "registry.yaml", "")
    result, errors = rl._try_load_registry_once([path])

    assert result is None
    assert "Missing required section 'skills'" in errors[0]


def test_try_load_prefers_first_valid_candidate(tmp_path):
    missing = tmp_path / "missing.yaml"
    good = _write_registry(tmp_path / "good.yaml", _VALID_REGISTRY)
    result, errors = rl._try_load_registry_once([missing, good])

    assert errors == []
    assert result is not None
    assert result["_source_path"] == good


# ---------------------------------------------------------------------------
# _registry_candidate_paths
# ---------------------------------------------------------------------------


def test_candidate_paths_returns_resolved_registry_when_plugins_dir_set(tmp_path, monkeypatch):
    registry_path = tmp_path / "ide" / "registry.yaml"
    registry_path.parent.mkdir(parents=True)
    monkeypatch.setattr(rl, "get_config", lambda: SimpleNamespace(plugins_dir=tmp_path))
    monkeypatch.setattr(rl, "get_ide_registry_path", lambda: registry_path)

    candidates = rl._registry_candidate_paths()

    assert candidates == [registry_path.resolve()]


def test_candidate_paths_empty_when_no_plugins_dir(monkeypatch):
    monkeypatch.setattr(rl, "get_config", lambda: SimpleNamespace(plugins_dir=None))
    assert rl._registry_candidate_paths() == []


# ---------------------------------------------------------------------------
# load_registry
# ---------------------------------------------------------------------------


def test_load_registry_returns_payload_and_sets_state(tmp_path, monkeypatch):
    path = _write_registry(tmp_path / "registry.yaml", _VALID_REGISTRY)
    monkeypatch.setattr(rl, "_registry_candidate_paths", lambda: [path])

    result = rl.load_registry()

    # _source_path is stripped from the public return value.
    assert "_source_path" not in result
    assert result["skills"].keys() == {"ask", "keep"}
    assert rl._registry_source_path == path
    assert rl._registry_last_error is None


def test_load_registry_caches_within_ttl(tmp_path, monkeypatch):
    path = _write_registry(tmp_path / "registry.yaml", _VALID_REGISTRY)
    monkeypatch.setattr(rl, "_registry_candidate_paths", lambda: [path])

    first = rl.load_registry()
    assert first["skills"].keys() == {"ask", "keep"}

    # Mutate the file on disk; cached result must be returned unchanged.
    _write_registry(path, {"skills": {"only": {}}})
    second = rl.load_registry()
    assert second is first
    assert second["skills"].keys() == {"ask", "keep"}


def test_load_registry_refreshes_after_cache_expiry(tmp_path, monkeypatch):
    path = _write_registry(tmp_path / "registry.yaml", _VALID_REGISTRY)
    monkeypatch.setattr(rl, "_registry_candidate_paths", lambda: [path])

    rl.load_registry()
    # Pretend the cache was populated > 60s ago.
    rl._registry_cache_time = _time.time() - 120
    _write_registry(path, {"skills": {"only": {}}})

    refreshed = rl.load_registry()
    assert refreshed["skills"].keys() == {"only"}


def test_load_registry_empty_when_not_found(monkeypatch):
    monkeypatch.setattr(rl, "_registry_candidate_paths", lambda: [])

    result = rl.load_registry()

    assert result == {"skills": {}, "chains": {}, "workflows": {}, "page_contexts": {}}
    assert rl._registry_source_path is None
    assert rl._registry_last_error == "Registry not found. Checked: "


def test_load_registry_empty_on_parse_error(tmp_path, monkeypatch):
    path = _write_registry(tmp_path / "registry.yaml", "skills: {unterminated")
    monkeypatch.setattr(rl, "_registry_candidate_paths", lambda: [path])

    result = rl.load_registry()

    assert result == {"skills": {}, "chains": {}, "workflows": {}, "page_contexts": {}}
    assert rl._registry_source_path is None
    assert rl._registry_last_error is not None
    assert "parse failure" in rl._registry_last_error


def test_load_registry_retries_then_succeeds(tmp_path, monkeypatch):
    """First attempt fails validation, a later attempt succeeds (regen race)."""
    good_path = tmp_path / "registry.yaml"
    calls = {"n": 0}

    def fake_once(candidates):
        calls["n"] += 1
        if calls["n"] == 1:
            return None, ["transient: validation failure"]
        return {
            "skills": {"ask": {}},
            "chains": {},
            "workflows": {},
            "page_contexts": {},
            "_source_path": good_path,
        }, []

    monkeypatch.setattr(rl, "_registry_candidate_paths", lambda: [good_path])
    monkeypatch.setattr(rl, "_try_load_registry_once", fake_once)

    result = rl.load_registry()

    assert calls["n"] == 2  # retried exactly once before success
    assert result["skills"] == {"ask": {}}
    assert "_source_path" not in result
    assert rl._registry_source_path == good_path
    assert rl._registry_last_error is None


def test_load_registry_exhausts_retries_on_persistent_failure(tmp_path, monkeypatch):
    path = _write_registry(tmp_path / "registry.yaml", {"chains": {}})  # missing skills
    monkeypatch.setattr(rl, "_registry_candidate_paths", lambda: [path])

    calls = {"n": 0}
    real_once = rl._try_load_registry_once

    def counting_once(candidates):
        calls["n"] += 1
        return real_once(candidates)

    monkeypatch.setattr(rl, "_try_load_registry_once", counting_once)

    result = rl.load_registry()

    assert calls["n"] == rl._REGISTRY_LOAD_RETRIES + 1  # 3 total attempts
    assert result["skills"] == {}
    assert "Missing required section 'skills'" in rl._registry_last_error


# ---------------------------------------------------------------------------
# get_registry_health
# ---------------------------------------------------------------------------


def test_health_ok_with_skills(tmp_path, monkeypatch):
    path = _write_registry(tmp_path / "registry.yaml", _VALID_REGISTRY)
    monkeypatch.setattr(rl, "_registry_candidate_paths", lambda: [path])

    health = rl.get_registry_health()

    assert health["ok"] is True
    assert health["source"] == str(path)
    assert health["error"] is None
    assert health["counts"] == {"skills": 2, "chains": 1, "workflows": 1, "page_contexts": 1}


def test_health_not_ok_when_registry_missing(monkeypatch):
    monkeypatch.setattr(rl, "_registry_candidate_paths", lambda: [])

    health = rl.get_registry_health()

    assert health["ok"] is False
    assert health["source"] is None
    assert "Registry not found" in health["error"]
    assert health["counts"] == {"skills": 0, "chains": 0, "workflows": 0, "page_contexts": 0}


def test_health_not_ok_when_loaded_but_no_skills(tmp_path, monkeypatch):
    # A structurally-valid file with an empty skills map loads, but is unhealthy.
    path = _write_registry(tmp_path / "registry.yaml", {"skills": {}, "chains": {"c": {}}})
    monkeypatch.setattr(rl, "_registry_candidate_paths", lambda: [path])

    health = rl.get_registry_health()

    assert health["ok"] is False
    assert health["source"] == str(path)
    assert health["error"] == "Registry loaded but contains no skills"
    assert health["counts"]["skills"] == 0
    assert health["counts"]["chains"] == 1
