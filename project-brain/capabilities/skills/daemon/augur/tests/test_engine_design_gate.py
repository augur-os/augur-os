"""Tests for the adaptive design-gate note writer."""

from __future__ import annotations

from pathlib import Path

import importlib
import sys

import yaml

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def _read_frontmatter(path: Path) -> tuple[dict, str]:
    content = path.read_text(encoding="utf-8")
    assert content.startswith("---\n")
    _, yaml_block, body = content.split("---\n", 2)
    meta = yaml.safe_load(yaml_block) or {}
    return meta, body.lstrip("\n")


def test_write_design_gate_creates_runtime_note_for_narrow_structural_fix(tmp_path: Path, monkeypatch):
    mod = importlib.import_module("skills.daemon.scripts.adaptive.engine_design_gate")
    monkeypatch.setattr(mod, "get_runtime_dir", lambda: tmp_path / "runtime")
    monkeypatch.setattr(mod, "get_adr_dir", lambda: tmp_path / "adrs")

    out = mod.write_design_gate(
        issue={"detail": "Split loop family"},
        loop_name="skill-quality",
        project_root=tmp_path,
        context={"sources": [{"kind": "wiki", "path": "wiki/dev/autoloops.md"}]},
        use_adr=False,
    )

    assert out["written"] is True
    assert out["kind"] == "runtime-note"
    note_path = Path(out["path"])
    assert note_path.suffix == ".md"
    assert note_path.is_file()

    meta, body = _read_frontmatter(note_path)
    assert meta["type"] == "design-gate"
    assert meta["kind"] == "runtime-note"
    assert meta["loop"] == "skill-quality"
    assert meta["context_source_count"] == 1
    assert "Split loop family" in body
    assert "wiki" in body


def test_write_design_gate_uses_adr_for_ownership_change(tmp_path: Path, monkeypatch):
    mod = importlib.import_module("skills.daemon.scripts.adaptive.engine_design_gate")
    monkeypatch.setattr(mod, "get_runtime_dir", lambda: tmp_path / "runtime")
    monkeypatch.setattr(mod, "get_adr_dir", lambda: tmp_path / "adrs")

    out = mod.write_design_gate(
        issue={"detail": "Move ownership from daemon to codex", "ownership_change": True},
        loop_name="observability",
        project_root=tmp_path,
        context={"sources": []},
        use_adr=True,
    )

    assert out["written"] is True
    assert out["kind"] == "adr"
    assert "ADR-" in out["path"]

    note_path = Path(out["path"])
    assert note_path.is_file()
    meta, body = _read_frontmatter(note_path)
    assert meta["type"] == "design-gate"
    assert meta["kind"] == "adr"
    assert meta["ownership_change"] is True
    assert meta["context_source_count"] == 0
    assert "Move ownership from daemon to codex" in body
    assert "Ownership change: yes" in body
