from __future__ import annotations

from pathlib import Path


def test_posix_codex_launcher_prefers_overlay_before_cwd() -> None:
    script = Path("scripts/augur-codex-mcp").read_text(encoding="utf-8")

    overlay_index = script.index('"${AUGUR_PROJECT_ROOT:-}"')
    cwd_index = script.index('"$cwd_root"')

    assert overlay_index < cwd_index


def test_posix_codex_launcher_uses_configured_root_before_cwd_without_overlay() -> None:
    script = Path("scripts/augur-codex-mcp").read_text(encoding="utf-8")

    configured_index = script.index('"$configured_root"')
    cwd_index = script.index('"$cwd_root"')

    assert configured_index < cwd_index


def test_windows_codex_launcher_prefers_overlay_before_cwd() -> None:
    script = Path("scripts/augur-codex-mcp.ps1").read_text(encoding="utf-8")
    candidates_start = script.index("$candidates = @(")
    candidates_end = script.index(")", candidates_start)
    candidates = script[candidates_start:candidates_end]

    overlay_index = candidates.index("$env:AUGUR_PROJECT_ROOT")
    cwd_index = candidates.index("$cwdRoot")

    assert overlay_index < cwd_index
