from __future__ import annotations

from pathlib import Path

import src.lib.index._scanners_structural as scanners


def _make_skill(root: Path, bundle: str, name: str) -> Path:
    """Build a discoverable skill dir at root/plugins/<bundle>/skills/<name>."""
    skill_dir = root / "plugins" / bundle / "skills" / name
    (skill_dir / "scripts").mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(f"---\nname: {name}\n---\n", encoding="utf-8")
    return skill_dir


def test_index_scripts_skips_init_py(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "proj"
    rag = tmp_path / "rag"
    skill = _make_skill(root, "dev", "demo")
    (skill / "scripts" / "__init__.py").write_text("", encoding="utf-8")
    (skill / "scripts" / "helper.py").write_text('"""Do a thing."""\n', encoding="utf-8")
    (skill / "scripts" / "run.sh").write_text("#!/bin/sh\n# Run it\n", encoding="utf-8")

    monkeypatch.setattr(scanners, "_discover_skill_dirs", lambda r: [("dev", skill)])

    count = scanners.index_scripts(root, rag)

    names = sorted(p.stem for p in (rag / "scripts").rglob("*.md"))
    assert "helper" in names
    assert "run" in names
    assert "__init__" not in names
    assert count == 2


def test_index_scripts_skips_paths_outside_root(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    rag = tmp_path / "rag"

    in_skill = _make_skill(root, "dev", "inside")
    (in_skill / "scripts" / "keep.py").write_text('"""keep."""\n', encoding="utf-8")

    # External skill OUTSIDE root — simulates a ~/.claude plugin-cache copy.
    ext = tmp_path / "external" / "skills" / "outside"
    (ext / "scripts").mkdir(parents=True)
    (ext / "scripts" / "drop.py").write_text('"""drop."""\n', encoding="utf-8")

    monkeypatch.setattr(scanners, "_discover_skill_dirs", lambda r: [("dev", in_skill), ("unknown", ext)])

    count = scanners.index_scripts(root, rag)

    names = sorted(p.stem for p in (rag / "scripts").rglob("*.md"))
    assert names == ["keep"]
    assert count == 1


def test_index_scripts_keeps_scripts_under_symlinked_root(tmp_path: Path, monkeypatch) -> None:
    real_root = tmp_path / "real_proj"
    skill = _make_skill(real_root, "dev", "linked")
    (skill / "scripts" / "keep.py").write_text('"""keep."""\n', encoding="utf-8")

    # Caller passes a symlinked path to the same project root.
    link_root = tmp_path / "link_proj"
    link_root.symlink_to(real_root, target_is_directory=True)

    monkeypatch.setattr(scanners, "_discover_skill_dirs", lambda r: [("dev", skill)])

    count = scanners.index_scripts(link_root, rag := tmp_path / "rag")
    names = sorted(p.stem for p in (rag / "scripts").rglob("*.md"))
    assert names == ["keep"]
    assert count == 1
