from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from src.plugins.skill_discovery import invalidate_discovery_cache


def _load_discovery_module():
    module_path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "adaptive"
        / "discovery.py"
    )
    spec = importlib.util.spec_from_file_location("adaptive_discovery_test", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_discover_auto_commands_reads_skill_md_callables(tmp_path, monkeypatch):
    module = _load_discovery_module()
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.chdir(tmp_path)
    invalidate_discovery_cache()

    skill_root = tmp_path / "project-brain" / "capabilities" / "skills" / "demo-loop"
    scripts_dir = skill_root / "scripts" / "ops"
    scripts_dir.mkdir(parents=True, exist_ok=True)

    (skill_root / "SKILL.md").write_text(
        """
---
name: demo-loop
description: Demo loop
x-augur-hub: command
x-augur-commands:
  - id: auto-demo-loop
    protocol: scan-fix
    callable: scripts/ops/demo_loop.py
    loop:
      name: observability
      tier: 2
---
# demo-loop
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (scripts_dir / "demo_loop.py").write_text(
        """
name = "auto-demo-loop"

def scan(ctx):
    return None

def fix(ctx, issues):
    return None
""".strip()
        + "\n",
        encoding="utf-8",
    )

    registry = module.discover_auto_commands(tmp_path)

    assert "auto-demo-loop" in registry
    assert registry["auto-demo-loop"].plugin_root == skill_root
