"""Foundation setup probes."""

from __future__ import annotations

import shutil

from src.config.paths import get_compiled_wiki_dir, get_project_root, get_runtime_dir, get_vault_dir

from .helpers import done, has_any_file, pending
from ..types import ProbeResult


def search_engine() -> ProbeResult:
    """ripgrep powers fast full-text search; absence falls back to a slow scan."""
    rg = shutil.which("rg")
    if rg:
        return done(f"ripgrep available ({rg})")
    return pending(
        "ripgrep (rg) not found — install for fast search: "
        "winget install BurntSushi.ripgrep.MSVC"
    )


def index_machine() -> ProbeResult:
    root = get_project_root()
    registry = get_runtime_dir() / "ide-integration" / "registry.yaml"
    manifest = root / "docs" / "generated" / "skill-manifest.json"
    if registry.exists() or manifest.exists():
        return done("skill inventory available")
    return pending("skill inventory has not been generated")


def vault() -> ProbeResult:
    vault_dir = get_vault_dir()
    if not vault_dir.exists():
        return pending(f"vault path missing: {vault_dir}")
    probe = vault_dir / ".setup-write-test"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except OSError as exc:
        return pending(f"vault is not writable: {exc}")
    return done(str(vault_dir))


def human_profile() -> ProbeResult:
    vault_dir = get_vault_dir()
    runtime_dir = get_runtime_dir()
    candidates = [
        get_compiled_wiki_dir() / "profile-human-api.md",
        vault_dir / "memory" / "profile.md",
        vault_dir / "memory" / "HUMAN_API.md",
        vault_dir / "HUMAN_API.md",
        runtime_dir / "memory" / "profile.md",
        runtime_dir / "memory" / "HUMAN_API.md",
    ]
    if has_any_file(path for path in candidates if path.exists() and path.stat().st_size >= 256):
        return done("profile available")
    return pending("no profile with enough content")


def voice_profile() -> ProbeResult:
    vault_dir = get_vault_dir()
    candidates = [
        vault_dir / "profile" / "en" / "about-me.md",
        vault_dir / "profile" / "he" / "about-me.md",
    ]
    if has_any_file(path for path in candidates if path.exists() and path.stat().st_size >= 256):
        return done("voice profile available")
    return pending("no English or Hebrew voice profile with enough content")
