"""Tests for client MCP config dangling-path detection + auto-repair.

Covers the 2026-06-16 incident: the Claude Desktop Filesystem DXT extension
still listed ``~/Projects/Au-docs`` in ``allowed_directories`` after the
documents root moved to ``~/Documents``, so the secure-filesystem server
crash-looped on startup and Augur never noticed.
"""

from __future__ import annotations

import sys
import pytest

import json
import textwrap
from pathlib import Path

from src.lib import mcp_client_config_audit as cca
from src.lib import path_migrations as pm


def _migrations(tmp_path: Path, old: Path, new: Path) -> list[dict[str, str]]:
    cfg = tmp_path / "path_migrations.yaml"
    cfg.write_text(
        textwrap.dedent(f"""
            migrations:
              - old: {old}
                new: {new}
                date: 2026-06-13
                note: test
            """),
        encoding="utf-8",
    )
    return pm.load_migrations(cfg)


# ── extraction ────────────────────────────────────────────────────────────────


def test_extract_dxt_allowed_directories(tmp_path: Path) -> None:
    cfg = tmp_path / "fs.json"
    cfg.write_text(
        json.dumps(
            {
                "isEnabled": True,
                "userConfig": {
                    "allowed_directories": ["/a/docs", "~/Desktop"],
                    "some_token": "not-a-path-xyz",
                },
            }
        ),
        encoding="utf-8",
    )
    src = cca.ConfigSource("claude-desktop-extension", cfg, "json", "dxt-extension", False)
    refs = cca.extract_path_refs(src, cfg.read_text())
    raws = {r.raw for r in refs}
    assert raws == {"/a/docs", "~/Desktop"}  # token excluded


def test_extract_mcp_server_cwd_json(tmp_path: Path) -> None:
    cfg = tmp_path / "c.json"
    cfg.write_text(
        json.dumps({"mcpServers": {"x": {"command": "python", "cwd": "/proj/x"}}}),
        encoding="utf-8",
    )
    src = cca.ConfigSource("gemini", cfg, "json", "mcp-config", False)
    refs = cca.extract_path_refs(src, cfg.read_text())
    assert [(r.location, r.raw) for r in refs] == [("mcpServers.x.cwd", "/proj/x")]


def test_extract_mcp_server_cwd_toml(tmp_path: Path) -> None:
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        textwrap.dedent("""
            [mcp_servers.augur]
            command = "python"
            cwd = "/proj/augur"
            """),
        encoding="utf-8",
    )
    src = cca.ConfigSource("codex", cfg, "toml", "mcp-config", False)
    refs = cca.extract_path_refs(src, cfg.read_text())
    assert [(r.location, r.raw) for r in refs] == [("mcp_servers.augur.cwd", "/proj/augur")]


# ── detection ──────────────────────────────────────────────────────────────────


def test_audit_flags_missing_with_successor(tmp_path: Path) -> None:
    old = tmp_path / "Au-docs"
    new = tmp_path / "Documents"
    new.mkdir()
    migs = _migrations(tmp_path, old, new)

    cfg = tmp_path / "fs.json"
    cfg.write_text(
        json.dumps({"userConfig": {"allowed_directories": [str(old)]}}),
        encoding="utf-8",
    )
    src = cca.ConfigSource("claude-desktop-extension", cfg, "json", "dxt-extension", False)
    findings = cca.audit_source(src, migs)
    assert len(findings) == 1
    assert findings[0].repairable
    assert findings[0].successor == str(new)


def test_audit_skips_existing_path(tmp_path: Path) -> None:
    good = tmp_path / "Documents"
    good.mkdir()
    cfg = tmp_path / "fs.json"
    cfg.write_text(
        json.dumps({"userConfig": {"allowed_directories": [str(good)]}}),
        encoding="utf-8",
    )
    src = cca.ConfigSource("claude-desktop-extension", cfg, "json", "dxt-extension", False)
    assert cca.audit_source(src, []) == []


def test_generated_config_not_repairable(tmp_path: Path) -> None:
    old = tmp_path / "Au-docs"
    new = tmp_path / "Documents"
    new.mkdir()
    migs = _migrations(tmp_path, old, new)
    cfg = tmp_path / ".mcp.json"
    cfg.write_text(json.dumps({"mcpServers": {"augur": {"cwd": str(old)}}}), encoding="utf-8")
    src = cca.ConfigSource("client-mcp", cfg, "json", "mcp-config", generated=True)
    findings = cca.audit_source(src, migs)
    assert len(findings) == 1
    assert not findings[0].repairable  # generated => report, don't hand-edit
    assert "config sync" in findings[0].detail


# ── repair ──────────────────────────────────────────────────────────────────────


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="path-migration successor resolution uses POSIX path semantics; validation pending (ROADMAP)",
)
def test_repair_rewrites_dxt_and_preserves_other_keys(tmp_path: Path) -> None:
    old = tmp_path / "Au-docs"
    new = tmp_path / "Documents"
    new.mkdir()
    migs = _migrations(tmp_path, old, new)

    cfg = tmp_path / "fs.json"
    original = {
        "isEnabled": True,
        "userConfig": {"allowed_directories": [str(old), "/keep/me"]},
    }
    cfg.write_text(json.dumps(original, indent=2), encoding="utf-8")
    src = cca.ConfigSource("claude-desktop-extension", cfg, "json", "dxt-extension", False)

    findings = cca.audit_source(src, migs)
    applied = cca.repair_source(src, findings)

    assert len(applied) == 1
    assert applied[0]["old"] == str(old)
    assert applied[0]["new"] == str(new)
    after = json.loads(cfg.read_text())
    assert after["userConfig"]["allowed_directories"] == [str(new), "/keep/me"]
    assert after["isEnabled"] is True  # untouched


@pytest.mark.skipif(
    sys.platform == "win32", reason="Windows home/~ path semantics differ; validation pending (ROADMAP)"
)
def test_repair_preserves_home_tilde_style(tmp_path: Path, monkeypatch) -> None:
    # HOME-relative raw should be rewritten HOME-relative.
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    old = home / "Projects/Au-docs"
    new = home / "Documents"
    new.mkdir(parents=True)
    migs = _migrations(tmp_path, old, new)

    cfg = tmp_path / "fs.json"
    cfg.write_text(
        json.dumps({"userConfig": {"allowed_directories": ["~/Projects/Au-docs"]}}, indent=2),
        encoding="utf-8",
    )
    src = cca.ConfigSource("claude-desktop-extension", cfg, "json", "dxt-extension", False)
    findings = cca.audit_source(src, migs)
    applied = cca.repair_source(src, findings)
    assert applied and applied[0]["new"] == "~/Documents"
    assert "~/Documents" in cfg.read_text()
