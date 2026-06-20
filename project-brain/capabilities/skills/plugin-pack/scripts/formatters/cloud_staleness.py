"""Cloud-plugin staleness detection (P1, 2026-06-11).

Regular Claude Desktop chats load the Augur plugin from a cloud-synced copy
(claude.ai "My Uploads" marketplace, mirrored into rpm/<plugin_id>/ inside the
Desktop app data) — NOT from the locally installed local-desktop-app-uploads
bundle, which only feeds Cowork agent sessions. The cloud copy drifted silently
for three months because nothing compared it against the repo. This module
makes that drift detectable so every sync path can fail loud instead.
"""
from __future__ import annotations

import json
from pathlib import Path

PLUGIN_NAME = "augur"


def default_sessions_base() -> Path:
    return (
        Path.home()
        / "Library"
        / "Application Support"
        / "Claude"
        / "local-agent-mode-sessions"
    )


def find_rpm_plugin_dir(
    sessions_base: Path | None = None,
) -> tuple[Path, dict] | None:
    """Locate the cloud-synced rpm copy of the augur plugin and its manifest entry."""
    base = sessions_base if sessions_base is not None else default_sessions_base()
    if not base.is_dir():
        return None
    for session_dir in sorted(base.iterdir()):
        if not session_dir.is_dir():
            continue
        for org_dir in sorted(session_dir.iterdir()):
            manifest_path = org_dir / "rpm" / "manifest.json"
            if not manifest_path.is_file():
                continue
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            for entry in manifest.get("plugins", []):
                if entry.get("name") == PLUGIN_NAME and entry.get("id"):
                    plugin_dir = org_dir / "rpm" / str(entry["id"])
                    if plugin_dir.is_dir():
                        return plugin_dir, entry
    return None


def find_upload_target(sessions_base: Path | None = None) -> dict | None:
    """Discover the claude.ai upload endpoint for this machine's augur plugin.

    The org id is the rpm parent directory name and the marketplace id comes
    from the manifest entry — both already on disk, so the sync flow needs no
    configuration to know where to push.
    """
    base = sessions_base if sessions_base is not None else default_sessions_base()
    if not base.is_dir():
        return None
    for session_dir in sorted(base.iterdir()):
        if not session_dir.is_dir():
            continue
        for org_dir in sorted(session_dir.iterdir()):
            manifest_path = org_dir / "rpm" / "manifest.json"
            if not manifest_path.is_file():
                continue
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            for entry in manifest.get("plugins", []):
                if entry.get("name") == PLUGIN_NAME and entry.get("marketplaceId"):
                    org_id = org_dir.name
                    marketplace_id = str(entry["marketplaceId"])
                    return {
                        "org_id": org_id,
                        "marketplace_id": marketplace_id,
                        "plugin_id": entry.get("id"),
                        "upload_url": (
                            "https://claude.ai/api/organizations/"
                            f"{org_id}/marketplaces/{marketplace_id}"
                            "/plugins/account-upload?overwrite=true"
                        ),
                    }
    return None


def build_cloud_zip(bundle_plugin_dir: Path, out_path: Path) -> dict:
    """Build the deterministic cloud-upload zip (top-level `augur/` folder).

    claude.ai's validator requires the plugin wrapped in a top-level folder.
    Returns {"path", "size", "sha256"} so the executing agent can verify the
    payload end-to-end after any transfer hop.
    """
    import hashlib
    import zipfile

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(bundle_plugin_dir.rglob("*")):
            if path.is_file():
                arcname = f"{PLUGIN_NAME}/{path.relative_to(bundle_plugin_dir).as_posix()}"
                zf.write(path, arcname)
    data = out_path.read_bytes()
    return {
        "path": str(out_path),
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def _command_files(commands_dir: Path) -> dict[str, str]:
    if not commands_dir.is_dir():
        return {}
    return {
        path.name: path.read_text(encoding="utf-8")
        for path in sorted(commands_dir.glob("*.md"))
    }


def check_cloud_plugin_staleness(
    bundle_plugin_dir: Path,
    sessions_base: Path | None = None,
) -> dict:
    """Compare the assembled bundle's commands/ against the cloud-synced copy.

    The slash-command surface is what regular Desktop chats actually expose, so
    that is what we diff. Returns a report dict:
      checked          False when no cloud-synced augur plugin exists on this
                       machine (not an error — e.g. CI, fresh installs)
      stale            True when the cloud copy's command set or content differs
      reasons          human-readable drift descriptions
      rpm_dir          path of the cloud-synced copy, when found
      cloud_updated_at the cloud copy's upload timestamp, when found
    """
    found = find_rpm_plugin_dir(sessions_base)
    if found is None:
        return {
            "checked": False,
            "stale": False,
            "reasons": ["no cloud-synced augur plugin found on this machine"],
            "rpm_dir": None,
            "cloud_updated_at": None,
        }
    rpm_dir, entry = found
    expected = _command_files(bundle_plugin_dir / "commands")
    actual = _command_files(rpm_dir / "commands")

    reasons: list[str] = []
    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    if missing:
        reasons.append(f"cloud copy missing commands: {', '.join(missing)}")
    if extra:
        reasons.append(f"cloud copy has retired commands: {', '.join(extra)}")
    for name in sorted(set(expected) & set(actual)):
        if expected[name] != actual[name]:
            reasons.append(f"command content drifted: {name}")

    return {
        "checked": True,
        "stale": bool(reasons),
        "reasons": reasons,
        "rpm_dir": str(rpm_dir),
        "cloud_updated_at": entry.get("updatedAt"),
    }
