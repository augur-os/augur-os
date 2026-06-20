"""Auto-detect installed local CLIs and write integration yamls.

Closes the "Connect first integration" setup probe for any developer
machine by walking a registry of well-known local CLIs, running
shutil.which()/os.path.exists() per entry, and writing one yaml per
detection to <vault>/integrations/<id>.yaml (the path the probe in
project-brain/capabilities/skills/onboard/scripts/setup/probes/personalization.py
already reads).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SHARED_VAULT_ROOT = Path(__file__).resolve().parents[4]
if str(SHARED_VAULT_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_VAULT_ROOT))

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "scan_local_clis.py"


def _load():
    spec = importlib.util.spec_from_file_location("scan_local_clis", SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_registry_is_non_empty_and_well_shaped() -> None:
    mod = _load()
    assert isinstance(mod.REGISTRY, list)
    assert len(mod.REGISTRY) >= 3
    for entry in mod.REGISTRY:
        assert "id" in entry and entry["id"]
        assert "name" in entry and entry["name"]
        assert "type" in entry and entry["type"] == "local-cli"
        # Each entry must declare HOW to detect it
        assert "binary" in entry or "app_path" in entry


def test_detect_returns_only_present_binaries(tmp_path: Path) -> None:
    mod = _load()
    # Inject a fake registry with one always-present + one never-present + one app path
    fake = [
        {"id": "alpha", "name": "Alpha", "type": "local-cli", "binary": "/bin/sh"},  # always exists
        {"id": "missing", "name": "MissingTool", "type": "local-cli", "binary": "/does/not/exist/zzz999"},
        {"id": "tmpapp", "name": "TmpApp", "type": "local-cli", "app_path": str(tmp_path / "TmpApp.app")},
    ]
    # Create the app
    (tmp_path / "TmpApp.app").mkdir()

    detected = mod.detect(registry=fake)
    ids = sorted(d["id"] for d in detected)
    assert ids == ["alpha", "tmpapp"], f"got {ids}"
    # Detected records carry the resolved path
    alpha = next(d for d in detected if d["id"] == "alpha")
    assert alpha["resolved_path"] == "/bin/sh"
    tmpapp = next(d for d in detected if d["id"] == "tmpapp")
    assert tmpapp["resolved_path"] == str(tmp_path / "TmpApp.app")


def test_scan_writes_one_yaml_per_detection(tmp_path: Path) -> None:
    mod = _load()
    out_dir = tmp_path / "integrations"
    fake = [
        {"id": "alpha", "name": "Alpha", "type": "local-cli", "binary": "/bin/sh"},
        {"id": "beta", "name": "BetaCLI", "type": "local-cli", "binary": "/does/not/exist/zzz"},
    ]
    result = mod.scan(target_dir=out_dir, registry=fake)
    assert result["detected_count"] == 1
    assert result["skipped_count"] == 1
    assert sorted(result["written_files"]) == [str(out_dir / "alpha.yaml")]
    # Yaml on disk is real + readable
    import yaml
    data = yaml.safe_load((out_dir / "alpha.yaml").read_text())
    assert data["id"] == "alpha"
    assert data["enabled"] is True
    assert data["type"] == "local-cli"
    assert data["binary"] == "/bin/sh"
    assert "detected_at" in data


def test_scan_is_idempotent_and_preserves_user_edits(tmp_path: Path) -> None:
    """Running scan twice writes the same content; user notes survive."""
    mod = _load()
    out_dir = tmp_path / "integrations"
    out_dir.mkdir()
    fake = [{"id": "alpha", "name": "Alpha", "type": "local-cli", "binary": "/bin/sh"}]

    # Pre-existing user-authored entry with a note
    import yaml
    (out_dir / "alpha.yaml").write_text(
        yaml.safe_dump({
            "id": "alpha", "name": "Alpha", "type": "local-cli",
            "enabled": True, "binary": "/bin/sh",
            "note": "user-added note: keep me!",
        })
    )

    mod.scan(target_dir=out_dir, registry=fake)
    after = yaml.safe_load((out_dir / "alpha.yaml").read_text())
    # User's note is preserved
    assert after.get("note") == "user-added note: keep me!"
    # Auto fields refreshed
    assert after["enabled"] is True
    assert "detected_at" in after


def test_scan_skips_disabled_user_yaml(tmp_path: Path) -> None:
    """User-set enabled: false survives — the scanner does not override intent."""
    mod = _load()
    out_dir = tmp_path / "integrations"
    out_dir.mkdir()
    fake = [{"id": "alpha", "name": "Alpha", "type": "local-cli", "binary": "/bin/sh"}]

    import yaml
    (out_dir / "alpha.yaml").write_text(
        yaml.safe_dump({"id": "alpha", "enabled": False, "binary": "/bin/sh",
                        "note": "I do not want this enabled"})
    )

    mod.scan(target_dir=out_dir, registry=fake)
    after = yaml.safe_load((out_dir / "alpha.yaml").read_text())
    assert after["enabled"] is False
