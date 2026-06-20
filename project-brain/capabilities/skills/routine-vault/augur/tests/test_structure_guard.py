"""Tests for the vault structure guard (domains layout, spec 2026-06-12)."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from unittest.mock import patch

from src.lib.brain_layout import brain_layout
from src.lib.ops_protocol import OpsContext, ScanResult

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "structure_guard.py"
_SPEC = importlib.util.spec_from_file_location("structure_guard_under_test", _MODULE_PATH)
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)

scan_structure = mod.scan_structure


def _vault(tmp_path: Path) -> Path:
    (tmp_path / "BRAIN.yaml").write_text("layout: domains\n", encoding="utf-8")
    for d in ("career", "inbox", "wiki", "sources", "profile", "_augur"):
        (tmp_path / d).mkdir()
    return tmp_path


def test_clean_vault_has_no_findings(tmp_path):
    assert scan_structure(_vault(tmp_path)) == []


def test_unknown_legacy_top_dir_flagged(tmp_path):
    v = _vault(tmp_path)
    (v / "knowledge").mkdir()
    findings = scan_structure(v)
    assert any("knowledge" in f and "legacy" in f for f in findings)


def test_test_artifact_pattern_flagged(tmp_path):
    v = _vault(tmp_path)
    (v / "career" / "2026-06-12-adr-999-verification.md").write_text("x", encoding="utf-8")
    assert any("verification" in f for f in scan_structure(v))


def test_machine_dir_contents_not_scanned(tmp_path):
    v = _vault(tmp_path)
    (v / "_augur" / "x-verification.md").write_text("x", encoding="utf-8")
    assert scan_structure(v) == []


def test_legacy_layout_vault_returns_no_findings(tmp_path):
    (tmp_path / "knowledge").mkdir()
    assert scan_structure(tmp_path) == []  # guard only applies to domains layout


def test_unexpected_root_file_flagged(tmp_path):
    v = _vault(tmp_path)
    (v / "random-junk.md").write_text("x", encoding="utf-8")
    assert any("random-junk" in f for f in scan_structure(v))


def test_files_symlink_not_flagged(tmp_path):
    v = _vault(tmp_path)
    docs = tmp_path.parent / "docs"
    (docs / "career").mkdir(parents=True)
    os.symlink(os.path.relpath(docs / "career", v / "career"), v / "career" / "files")
    (docs / "career" / "some-verification.md").write_text("x", encoding="utf-8")
    assert (v / "career" / "files").is_symlink()
    # symlinked docs content is not the vault's problem
    try:
        assert scan_structure(v) == []
    finally:
        brain_layout.cache_clear()


def test_scan_wrapper_missing_vault_dir(tmp_path):
    """scan(ctx) returns clean when the configured vault doesn't exist."""
    with patch.object(mod, "_get_vault", return_value=tmp_path / "nonexistent"):
        result = mod.scan(OpsContext(project_root=tmp_path))
    assert isinstance(result, ScanResult)
    assert result.issues == []
    assert result.severity == "info"
    assert "not found" in result.summary


def test_overlong_name_flagged(tmp_path):
    v = _vault(tmp_path)
    (v / "career" / ("x" * 45 + ".md")).write_text("x", encoding="utf-8")
    assert any("name too long" in f for f in scan_structure(v))


def test_dated_name_outside_event_dirs_flagged(tmp_path):
    v = _vault(tmp_path)
    (v / "career" / "2026-01-01-foo.md").write_text("x", encoding="utf-8")
    assert any("dated name" in f for f in scan_structure(v))


def test_dated_name_in_event_dir_ok(tmp_path):
    v = _vault(tmp_path)
    (v / "venture" / "linkedin").mkdir(parents=True)
    (v / "venture" / "linkedin" / "2026-01-01-post.md").write_text("x", encoding="utf-8")
    assert not any("dated name" in f for f in scan_structure(v))


def test_url_fragment_name_flagged(tmp_path):
    v = _vault(tmp_path)
    (v / "career" / "foo-https-substackcdn-com-image.md").write_text("x", encoding="utf-8")
    assert any("url fragment" in f for f in scan_structure(v))


def test_wiki_names_exempt_from_naming_checks(tmp_path):
    """Wiki names are generator-owned: naming checks skip wiki/, content dirs don't."""
    v = _vault(tmp_path)
    long_name = "how-should-some-very-long-generated-concept-name-be-used.md"
    (v / "wiki" / long_name).write_text("x", encoding="utf-8")
    assert not any("name too long" in f for f in scan_structure(v))
    (v / "career" / long_name).write_text("x", encoding="utf-8")
    assert any("name too long" in f and "career" in f for f in scan_structure(v))
