"""Tests for cloud-plugin staleness detection (P1, 2026-06-11)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from formatters.cloud_staleness import (  # noqa: E402
    build_cloud_zip,
    check_cloud_plugin_staleness,
    find_rpm_plugin_dir,
    find_upload_target,
)


def _make_rpm(base: Path, commands: dict[str, str], plugin_id: str = "plugin_01TEST") -> Path:
    """Build a fake Desktop app-data layout: session/org/rpm/{manifest,plugin}."""
    rpm = base / "session-1" / "org-1" / "rpm"
    plugin_dir = rpm / plugin_id
    (plugin_dir / "commands").mkdir(parents=True)
    for name, content in commands.items():
        (plugin_dir / "commands" / name).write_text(content, encoding="utf-8")
    (rpm / "manifest.json").write_text(
        json.dumps(
            {
                "lastUpdated": 0,
                "plugins": [
                    {
                        "id": plugin_id,
                        "name": "augur",
                        "updatedAt": "2026-06-11T14:06:23Z",
                        "marketplaceId": "marketplace_01TEST",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return plugin_dir


def _make_bundle(base: Path, commands: dict[str, str]) -> Path:
    bundle = base / "build" / "plugins" / "augur"
    (bundle / "commands").mkdir(parents=True)
    for name, content in commands.items():
        (bundle / "commands" / name).write_text(content, encoding="utf-8")
    return bundle


class TestFindRpmPluginDir:
    def test_finds_plugin_dir_and_manifest_entry(self, tmp_path):
        plugin_dir = _make_rpm(tmp_path, {"keep.md": "x"})
        found = find_rpm_plugin_dir(tmp_path)
        assert found is not None
        assert found[0] == plugin_dir
        assert found[1]["updatedAt"] == "2026-06-11T14:06:23Z"

    def test_returns_none_when_no_sessions_base(self, tmp_path):
        assert find_rpm_plugin_dir(tmp_path / "missing") is None

    def test_ignores_corrupt_manifest(self, tmp_path):
        rpm = tmp_path / "s" / "o" / "rpm"
        rpm.mkdir(parents=True)
        (rpm / "manifest.json").write_text("{not json", encoding="utf-8")
        assert find_rpm_plugin_dir(tmp_path) is None


class TestCheckCloudPluginStaleness:
    def test_in_sync_is_not_stale(self, tmp_path):
        cmds = {"ask.md": "ask body", "keep.md": "keep body"}
        _make_rpm(tmp_path, cmds)
        bundle = _make_bundle(tmp_path, cmds)
        report = check_cloud_plugin_staleness(bundle, tmp_path)
        assert report["checked"] is True
        assert report["stale"] is False
        assert report["reasons"] == []
        assert report["cloud_updated_at"] == "2026-06-11T14:06:23Z"

    def test_missing_command_is_stale(self, tmp_path):
        _make_rpm(tmp_path, {"ask.md": "ask body"})
        bundle = _make_bundle(tmp_path, {"ask.md": "ask body", "keep.md": "keep body"})
        report = check_cloud_plugin_staleness(bundle, tmp_path)
        assert report["stale"] is True
        assert any("missing commands: keep.md" in r for r in report["reasons"])

    def test_retired_command_is_stale(self, tmp_path):
        # The exact March-2026 drift: cloud still serving save/search.
        _make_rpm(tmp_path, {"ask.md": "a", "save.md": "s", "search.md": "se"})
        bundle = _make_bundle(tmp_path, {"ask.md": "a"})
        report = check_cloud_plugin_staleness(bundle, tmp_path)
        assert report["stale"] is True
        assert any("retired commands: save.md, search.md" in r for r in report["reasons"])

    def test_content_drift_is_stale(self, tmp_path):
        _make_rpm(tmp_path, {"keep.md": "old policy"})
        bundle = _make_bundle(tmp_path, {"keep.md": "new policy with Session Reconcile"})
        report = check_cloud_plugin_staleness(bundle, tmp_path)
        assert report["stale"] is True
        assert any("content drifted: keep.md" in r for r in report["reasons"])

    def test_no_cloud_copy_is_checked_false_not_stale(self, tmp_path):
        bundle = _make_bundle(tmp_path, {"keep.md": "x"})
        report = check_cloud_plugin_staleness(bundle, tmp_path / "empty")
        assert report["checked"] is False
        assert report["stale"] is False


class TestFindUploadTarget:
    def test_discovers_endpoint_from_rpm_manifest(self, tmp_path):
        _make_rpm(tmp_path, {"keep.md": "x"})
        target = find_upload_target(tmp_path)
        assert target is not None
        assert target["org_id"] == "org-1"
        assert target["marketplace_id"] == "marketplace_01TEST"
        assert target["plugin_id"] == "plugin_01TEST"
        assert target["upload_url"] == (
            "https://claude.ai/api/organizations/org-1/marketplaces/"
            "marketplace_01TEST/plugins/account-upload?overwrite=true"
        )

    def test_returns_none_without_rpm(self, tmp_path):
        assert find_upload_target(tmp_path / "missing") is None


class TestBuildCloudZip:
    def test_zip_has_top_level_folder_and_stable_hash(self, tmp_path):
        import zipfile

        bundle = _make_bundle(tmp_path, {"ask.md": "a", "keep.md": "k"})
        (bundle / ".claude-plugin").mkdir()
        (bundle / ".claude-plugin" / "plugin.json").write_text("{}", encoding="utf-8")

        info1 = build_cloud_zip(bundle, tmp_path / "out1.zip")
        names = zipfile.ZipFile(info1["path"]).namelist()
        # claude.ai's validator requires the top-level plugin folder.
        assert all(n.startswith("augur/") for n in names)
        assert "augur/.claude-plugin/plugin.json" in names
        assert "augur/commands/keep.md" in names
        assert info1["size"] > 0 and len(info1["sha256"]) == 64
