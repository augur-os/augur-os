"""Regression tests for ADR-102 SKILL evolution metadata writes."""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


PKG_NAME = "test_adr102_adaptive"
PKG_DIR = Path(__file__).resolve().parents[2] / "scripts" / "adaptive"

if PKG_NAME not in sys.modules:
    pkg = types.ModuleType(PKG_NAME)
    pkg.__path__ = [str(PKG_DIR)]
    pkg.__package__ = PKG_NAME
    sys.modules[PKG_NAME] = pkg

for submodule in ("analyze_execution", "command_rewriter"):
    full_name = f"{PKG_NAME}.{submodule}"
    if full_name in sys.modules:
        continue
    spec = importlib.util.spec_from_file_location(
        full_name,
        PKG_DIR / f"{submodule}.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    spec.loader.exec_module(module)

analyze_execution = sys.modules[f"{PKG_NAME}.analyze_execution"]
command_rewriter = sys.modules[f"{PKG_NAME}.command_rewriter"]


def test_add_evolution_metadata_uses_x_augur_namespace():
    improvement = analyze_execution.Improvement(
        type=analyze_execution.ImprovementType.FIX_ERROR_PATTERN,
        priority=analyze_execution.ImprovementPriority.HIGH,
        auto_apply=analyze_execution.AutoApply.CONDITIONAL,
        description="Repair recurring scanner logic",
    )

    content = """---
name: sample-skill
description: Sample
---

# sample
"""

    updated = command_rewriter._add_evolution_metadata(content, improvement)

    assert "x-augur-evolution:" in updated
    assert "\nevolution:\n" not in updated
