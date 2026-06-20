"""End-to-end test: copy a fixture into tmp_path, run scan + apply, verify."""
from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path


# Load hygiene_scan via importlib
_SCAN_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "hygiene_scan.py"
_SCAN_SPEC = importlib.util.spec_from_file_location("hygiene_scan_e2e_under_test", _SCAN_MODULE_PATH)
assert _SCAN_SPEC and _SCAN_SPEC.loader
scan_mod = importlib.util.module_from_spec(_SCAN_SPEC)
sys.modules["hygiene_scan_e2e_under_test"] = scan_mod
_SCAN_SPEC.loader.exec_module(scan_mod)

# Load hygiene_apply via importlib
_APPLY_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "hygiene_apply.py"
_APPLY_SPEC = importlib.util.spec_from_file_location("hygiene_apply_e2e_under_test", _APPLY_MODULE_PATH)
assert _APPLY_SPEC and _APPLY_SPEC.loader
apply_mod = importlib.util.module_from_spec(_APPLY_SPEC)
sys.modules["hygiene_apply_e2e_under_test"] = apply_mod
_APPLY_SPEC.loader.exec_module(apply_mod)


FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "evals" / "fixtures"

# Fake binary-named fixture files are generated, not tracked (ADR-814) —
# load build_fixtures.py from the fixtures dir and ensure they exist.
_BUILD_SPEC = importlib.util.spec_from_file_location(
    "routine_vault_build_fixtures", FIXTURE_ROOT / "build_fixtures.py"
)
assert _BUILD_SPEC and _BUILD_SPEC.loader
_build_mod = importlib.util.module_from_spec(_BUILD_SPEC)
_BUILD_SPEC.loader.exec_module(_build_mod)
ensure_fixtures = _build_mod.ensure_fixtures


def _stage_fixture(tmp_path, monkeypatch, fixture_name: str, subdir: str = "websites") -> Path:
    """Copy a fixture into tmp_path/au-docs/<subdir>/, patch get_documents_dir in both modules."""
    ensure_fixtures()  # generate fake binaries on fresh clones (ADR-814)
    docs = tmp_path / "au-docs"
    docs.mkdir()
    src = FIXTURE_ROOT / fixture_name
    dest = docs / subdir
    shutil.copytree(src, dest)
    monkeypatch.setattr(scan_mod, "get_documents_dir", lambda: docs)
    monkeypatch.setattr(apply_mod, "get_documents_dir", lambda: docs)
    return dest


def test_e2e_websites_versioned_scan_then_apply(tmp_path, monkeypatch):
    folder = _stage_fixture(tmp_path, monkeypatch, "fixture_websites_versioned")
    docs = folder.parent

    # Scan
    scan = scan_mod.hygiene_scan(str(folder))
    file_names = [f["name"] for f in scan["files"]]
    # 50 zips + 2 md = 52 files; lifecycle.yaml is never_touch-skipped (.augur-* prefix)
    assert len(file_names) == 52
    assert "guriqo-com-V10032.zip" in file_names
    assert "guriqo-com-V10001.zip" in file_names
    assert "augur-run-V10032.zip" in file_names
    assert "augur-run-V10015.zip" in file_names
    assert scan["lifecycle_config"] is not None
    assert ".augur-lifecycle.yaml" in scan["never_touch_skipped"]

    # Build a move list as the agent would: archive all but the highest V for each group
    stale_guriqo = [f for f in scan["files"] if f["name"].startswith("guriqo-com-V") and f["name"] != "guriqo-com-V10032.zip"]
    stale_augur = [f for f in scan["files"] if f["name"].startswith("augur-run-V") and f["name"] != "augur-run-V10032.zip"]
    moves = [
        {
            "from": f["relative_path"],
            "reason": f"superseded by {'guriqo-com-V10032.zip' if 'guriqo' in f['name'] else 'augur-run-V10032.zip'}",
            "artifact_group": "guriqo-com-build" if "guriqo" in f["name"] else "augur-run-build",
        }
        for f in stale_guriqo + stale_augur
    ]
    # 31 guriqo stale + 17 augur stale = 48 moves
    assert len(moves) == 48

    # Dry-run apply
    dry = apply_mod.hygiene_apply(root="docs", moves=moves, dry_run=True)
    assert all(m["status"] == "would_succeed" for m in dry["moves"])

    # Real apply
    result = apply_mod.hygiene_apply(root="docs", moves=moves, dry_run=False)
    assert all(m["status"] == "succeeded" for m in result["moves"])
    assert result["total_bytes_archived"] > 0

    # Live folder retains only the two currents + the two markdowns + the lifecycle yaml
    live_files = sorted(f.name for f in folder.iterdir() if f.is_file())
    assert live_files == [
        ".augur-lifecycle.yaml",
        "DEPLOYMENT.md",
        "RELEASE.md",
        "augur-run-V10032.zip",
        "guriqo-com-V10032.zip",
    ]
    # Archive has the 48 stale + manifest + .augur-ignore
    archive = folder / ".archive"
    assert (archive / "_manifest.jsonl").exists()
    assert (archive / ".augur-ignore").exists()
    archived_zips = sorted(f.name for f in archive.iterdir() if f.suffix == ".zip")
    assert len(archived_zips) == 48
    # .gitignore at docs root has .archive/
    assert ".archive/" in (docs / ".gitignore").read_text()


def test_e2e_deploy_root_refuses_apply(tmp_path, monkeypatch):
    folder = _stage_fixture(tmp_path, monkeypatch, "fixture_deploy_root", subdir="prod-site")
    scan = scan_mod.hygiene_scan(str(folder))
    # The agent would build moves; we simulate that.
    moves = [
        {"from": f["relative_path"], "reason": "x"} for f in scan["files"] if f["name"].endswith(".zip")
    ]
    assert len(moves) == 2
    result = apply_mod.hygiene_apply(root="docs", moves=moves, dry_run=False)
    for m in result["moves"]:
        assert m["status"] == "refused"
        assert m["refusal_category"] == "deploy_root"
    # Live files untouched
    assert (folder / "site-v1.zip").exists()
    assert (folder / "site-v2.zip").exists()


def test_e2e_milestone_pinned_refuses_apply(tmp_path, monkeypatch):
    _stage_fixture(tmp_path, monkeypatch, "fixture_milestone_pinned", subdir="presentations")
    moves = [
        {"from": "presentations/deck-v1.pptx", "reason": "stale"},
        {"from": "presentations/deck-v2.pptx", "reason": "stale"},
    ]
    result = apply_mod.hygiene_apply(root="docs", moves=moves, dry_run=False)
    # v1 is pinned, v2 is not
    by_from = {m["from"]: m for m in result["moves"]}
    assert by_from["presentations/deck-v1.pptx"]["status"] == "refused"
    assert by_from["presentations/deck-v1.pptx"]["refusal_category"] == "milestone_pinned"
    assert by_from["presentations/deck-v2.pptx"]["status"] == "succeeded"


def test_e2e_cached_known_groups_skip_question_path(tmp_path, monkeypatch):
    docs_root = tmp_path / "docs"
    folder = docs_root / "ws"
    folder.mkdir(parents=True)

    for version in ("V10001", "V10002", "V10003", "V10032"):
        (folder / f"build-{version}.zip").write_bytes(b"x")

    monkeypatch.setattr(scan_mod, "get_documents_dir", lambda: docs_root)
    monkeypatch.setattr(apply_mod, "get_documents_dir", lambda: docs_root)

    scan1 = scan_mod.hygiene_scan(str(folder))
    assert scan1["lifecycle_config"] is None

    moves = [
        {"from": f"ws/build-{version}.zip", "reason": "test", "artifact_group": "build"}
        for version in ("V10001", "V10002", "V10003")
    ]
    lifecycle_updates = [
        {
            "folder": "ws",
            "known_group": {
                "name": "build",
                "canonical_strategy": "highest_version",
                "pattern": "build-*.zip",
                "decided_at": "2026-05-12T14:30:00Z",
                "decided_by": "test",
            },
        }
    ]
    apply1 = apply_mod.hygiene_apply(
        root="docs",
        moves=moves,
        dry_run=False,
        lifecycle_updates=lifecycle_updates,
    )
    assert all(move["status"] == "succeeded" for move in apply1["moves"])
    assert apply1["lifecycle_updates"][0]["status"] == "written"

    scan2 = scan_mod.hygiene_scan(str(folder))
    groups = scan2["lifecycle_config"]["known_groups"]
    assert len(groups) == 1
    assert groups[0]["name"] == "build"
    assert groups[0]["canonical_strategy"] == "highest_version"
    assert groups[0]["pattern"] == "build-*.zip"
