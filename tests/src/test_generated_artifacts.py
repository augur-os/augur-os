"""Tests for src.lib.generated_artifacts stable write helpers."""

import json

import yaml

from src.lib.generated_artifacts import (
    _normalize,
    _semantic_signature,
    write_stable_text,
    write_stable_json,
    write_stable_yaml,
)

# --- _normalize ---


def test_normalize_strips_volatile_keys():
    data = {"name": "foo", "generated_at": "2026-01-01", "version": 1}
    result = _normalize(data, {"generated_at"})
    assert "generated_at" not in result
    assert result == {"name": "foo", "version": 1}


def test_normalize_sorts_dict_keys():
    data = {"z": 1, "a": 2, "m": 3}
    result = _normalize(data, set())
    assert list(result.keys()) == ["a", "m", "z"]


def test_normalize_recurses_into_nested_dicts():
    data = {"outer": {"generated_at": "x", "value": 1}}
    result = _normalize(data, {"generated_at"})
    assert result == {"outer": {"value": 1}}


def test_normalize_recurses_into_lists():
    data = [{"generated_at": "x", "value": 1}, {"generated_at": "y", "value": 2}]
    result = _normalize(data, {"generated_at"})
    assert result == [{"value": 1}, {"value": 2}]


def test_normalize_returns_scalars_unchanged():
    assert _normalize(42, set()) == 42
    assert _normalize("hello", set()) == "hello"
    assert _normalize(None, set()) is None


# --- _semantic_signature ---


def test_semantic_signature_ignores_volatile_keys():
    a = {"name": "foo", "generated_at": "2026-01-01"}
    b = {"name": "foo", "generated_at": "2026-03-07"}
    assert _semantic_signature(a, ["generated_at"]) == _semantic_signature(b, ["generated_at"])


def test_semantic_signature_differs_on_payload_change():
    a = {"name": "foo", "version": 1}
    b = {"name": "foo", "version": 2}
    assert _semantic_signature(a, []) != _semantic_signature(b, [])


def test_semantic_signature_ignores_key_order():
    a = {"b": 2, "a": 1}
    b = {"a": 1, "b": 2}
    assert _semantic_signature(a, []) == _semantic_signature(b, [])


# --- write_stable_json ---


def test_write_stable_json_creates_new_file(tmp_path):
    path = tmp_path / "out.json"
    result = write_stable_json(path, {"key": "value"})
    assert result is True
    assert path.exists()
    assert json.loads(path.read_text()) == {"key": "value"}


def test_write_stable_json_skips_when_semantically_equal(tmp_path):
    path = tmp_path / "out.json"
    payload = {"name": "foo", "generated_at": "old"}
    write_stable_json(path, payload, volatile_keys=["generated_at"])

    new_payload = {"name": "foo", "generated_at": "new"}
    result = write_stable_json(path, new_payload, volatile_keys=["generated_at"])
    assert result is False
    # File content should still have old timestamp
    assert json.loads(path.read_text())["generated_at"] == "old"


def test_write_stable_json_writes_when_payload_differs(tmp_path):
    path = tmp_path / "out.json"
    write_stable_json(path, {"name": "foo", "version": 1})

    result = write_stable_json(path, {"name": "foo", "version": 2})
    assert result is True
    assert json.loads(path.read_text())["version"] == 2


def test_write_stable_json_creates_parent_dirs(tmp_path):
    path = tmp_path / "deep" / "nested" / "out.json"
    result = write_stable_json(path, {"ok": True})
    assert result is True
    assert path.exists()


def test_write_stable_json_overwrites_corrupt_file(tmp_path):
    path = tmp_path / "out.json"
    path.write_text("not valid json {{{", encoding="utf-8")

    result = write_stable_json(path, {"key": "value"})
    assert result is True
    assert json.loads(path.read_text()) == {"key": "value"}


# --- write_stable_yaml ---


def test_write_stable_yaml_creates_new_file(tmp_path):
    path = tmp_path / "out.yaml"
    result = write_stable_yaml(path, {"key": "value"})
    assert result is True
    assert path.exists()
    assert yaml.safe_load(path.read_text()) == {"key": "value"}


def test_write_stable_yaml_skips_when_semantically_equal(tmp_path):
    path = tmp_path / "out.yaml"
    payload = {"name": "bar", "generated_at": "old"}
    write_stable_yaml(path, payload, volatile_keys=["generated_at"])

    new_payload = {"name": "bar", "generated_at": "new"}
    result = write_stable_yaml(path, new_payload, volatile_keys=["generated_at"])
    assert result is False
    assert yaml.safe_load(path.read_text())["generated_at"] == "old"


def test_write_stable_yaml_writes_when_payload_differs(tmp_path):
    path = tmp_path / "out.yaml"
    write_stable_yaml(path, {"name": "bar", "count": 1})

    result = write_stable_yaml(path, {"name": "bar", "count": 5})
    assert result is True
    assert yaml.safe_load(path.read_text())["count"] == 5


def test_write_stable_yaml_creates_parent_dirs(tmp_path):
    path = tmp_path / "a" / "b" / "out.yaml"
    result = write_stable_yaml(path, {"ok": True})
    assert result is True
    assert path.exists()


def test_write_stable_yaml_overwrites_corrupt_file(tmp_path):
    path = tmp_path / "out.yaml"
    path.write_text(": : : [invalid", encoding="utf-8")

    result = write_stable_yaml(path, {"key": "value"})
    assert result is True
    assert yaml.safe_load(path.read_text()) == {"key": "value"}


# --- write_stable_text ---


def test_write_stable_text_skips_when_only_volatile_line_changes(tmp_path):
    path = tmp_path / "out.md"
    original = "# ADR Index\n\n> Auto-generated on 2026-04-23 23:48. Do not hand-edit.\n\nbody\n"
    updated = "# ADR Index\n\n> Auto-generated on 2026-04-24 01:09. Do not hand-edit.\n\nbody\n"
    path.write_text(original, encoding="utf-8")

    result = write_stable_text(path, updated, volatile_line_prefixes=["> Auto-generated on "])

    assert result is False
    assert path.read_text(encoding="utf-8") == original


def test_write_stable_text_writes_when_nonvolatile_content_changes(tmp_path):
    path = tmp_path / "out.md"
    original = "# ADR Index\n\n> Auto-generated on 2026-04-23 23:48. Do not hand-edit.\n\nbody\n"
    updated = "# ADR Index\n\n> Auto-generated on 2026-04-24 01:09. Do not hand-edit.\n\nchanged body\n"
    path.write_text(original, encoding="utf-8")

    result = write_stable_text(path, updated, volatile_line_prefixes=["> Auto-generated on "])

    assert result is True
    assert path.read_text(encoding="utf-8") == updated
