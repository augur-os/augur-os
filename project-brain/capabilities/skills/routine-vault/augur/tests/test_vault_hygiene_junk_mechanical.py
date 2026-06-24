"""OS/cache junk findings are banded mechanical + carry an auto_command."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
_MOD = _REPO / "project-brain" / "capabilities" / "skills" / "routine-vault" / "scripts" / "vault_hygiene_ops.py"


def _load():
    if str(_MOD.parent) not in sys.path:
        sys.path.insert(0, str(_MOD.parent))
    spec = importlib.util.spec_from_file_location("vault_hygiene_under_test", _MOD)
    m = importlib.util.module_from_spec(spec); sys.modules[spec.name] = m; spec.loader.exec_module(m); return m


def test_os_cache_junk_finding_is_mechanical(tmp_path):
    m = _load()
    vault = tmp_path / "vault"; (vault / "notes").mkdir(parents=True)
    (vault / "notes" / ".DS_Store").write_bytes(b"junk")
    findings = m._scan_os_cache_junk(vault)   # the helper that emits OS/cache junk (rename in Step 3 if needed)
    junk = [f for f in findings if str(f.get("message", "")).startswith("OS/cache junk")]
    assert junk, "should flag the .DS_Store"
    f = junk[0]
    assert f.get("finding_band") == "mechanical"
    assert f.get("auto_command")   # non-empty command id
    assert ".DS_Store" in (f.get("path") or f.get("message"))


def test_junk_under_venv_or_node_modules_is_skipped(tmp_path):
    m = _load()
    vault = tmp_path / "vault"
    for sub in (".venv", "node_modules"):
        d = vault / sub
        d.mkdir(parents=True)
        (d / ".DS_Store").write_bytes(b"junk")
    (vault / ".DS_Store").write_bytes(b"junk")   # a real one at root level
    findings = m._scan_os_cache_junk(vault)
    paths = [str(f.get("path") or f.get("message")) for f in findings]
    assert not any(".venv" in p or "node_modules" in p for p in paths), (
        "must not flag junk under .venv/node_modules"
    )
    assert any(
        (f.get("path") or "").endswith(".DS_Store")
        and ".venv" not in (f.get("path") or "")
        and "node_modules" not in (f.get("path") or "")
        for f in findings
    ), "should still flag the root .DS_Store"
