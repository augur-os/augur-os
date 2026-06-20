import importlib.util
import sys
from pathlib import Path

_SEC_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def _load(mod_name: str):
    spec = importlib.util.spec_from_file_location(mod_name, _SEC_SCRIPTS / f"{mod_name}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = m
    spec.loader.exec_module(m)
    return m


def _make_bundle_core(tmp_path: Path) -> Path:
    bundle = tmp_path / "recurring-reflection"
    core = bundle / "dream-routine"
    core.mkdir(parents=True)
    (bundle / "DESCRIPTION.md").write_text("# Recurring Reflection\n", encoding="utf-8")
    (core / "SKILL.md").write_text(
        "---\nname: dream-routine\ndescription: portable core\n---\n# Dream Routine\n",
        encoding="utf-8",
    )
    return core


def _make_flat_augur_skill(tmp_path: Path) -> Path:
    d = tmp_path / "dream"
    d.mkdir()
    (d / "SKILL.md").write_text("---\nname: dream\n---\n", encoding="utf-8")  # missing x-augur-type/license
    return d


def test_s4_exempts_standard_core_metadata_but_normal_skill_still_flagged(tmp_path):
    s4 = _load("s4_integrity")
    core = _make_bundle_core(tmp_path)
    kinds = {f["category_name"] for f in s4.scan_skill(core, is_augur_managed=True)}
    assert "incomplete-manifest" not in kinds
    assert "missing-license" not in kinds

    flat = _make_flat_augur_skill(tmp_path)
    flat_kinds = {f["category_name"] for f in s4.scan_skill(flat, is_augur_managed=True)}
    assert "incomplete-manifest" in flat_kinds  # normal skill STILL flagged


def test_s4_still_emits_treehash_for_standard_core(tmp_path):
    s4 = _load("s4_integrity")
    core = _make_bundle_core(tmp_path)
    findings = s4.scan_skill(core, is_augur_managed=True)
    kinds = {f["category_name"] for f in findings}
    # Metadata exemptions must suppress these two kinds for standard cores.
    assert "incomplete-manifest" not in kinds
    assert "missing-license" not in kinds
    # s4 always emits a tree-hash record for any scanned skill — the exemption must not skip it.
    assert findings, "s4 must still produce its non-metadata records for a core"
    assert "tree-hash" in kinds, "s4 tree-hash integrity check must still run for standard cores"


def test_s2_still_secret_scans_standard_core(tmp_path):
    s2 = _load("s2_secret_scanning")
    core = _make_bundle_core(tmp_path)
    # Plant a detectable AWS key — the metadata-only exemption must NOT disable secret scanning.
    (core / "leak.md").write_text('api_key = "AKIAIOSFODNN7REALKEY1"\n', encoding="utf-8")
    findings = s2.scan_skill(core)
    kinds = {f["category_name"] for f in findings}
    assert "AWS Access Key ID" in kinds, (
        "s2 must still flag AWS keys in standard-core files; "
        "the metadata exemption must not disable secret scanning"
    )


def test_s5_exempts_standard_core_but_normal_skill_still_flagged(tmp_path):
    s5 = _load("s5_permissions")
    core = _make_bundle_core(tmp_path)
    kinds = {f["category_name"] for f in s5.scan_skill(core, is_augur_managed=True)}
    assert "no-release-tag" not in kinds
    assert "no-commands-declared" not in kinds

    flat = _make_flat_augur_skill(tmp_path)
    flat_kinds = {f["category_name"] for f in s5.scan_skill(flat, is_augur_managed=True)}
    assert "no-release-tag" in flat_kinds  # normal skill STILL flagged
