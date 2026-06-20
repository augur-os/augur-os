"""Routine orchestration helpers."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any


def orchestrate_run(loop_name: str, *args: Any, **kwargs: Any) -> Any:
    """Run a routine loop through the modernized orchestrator."""
    return _impl().orchestrate_run(loop_name, *args, **kwargs)


def scan_only(loop_name: str, *args: Any, **kwargs: Any) -> Any:
    """Scan a routine loop without applying fixes."""
    return _impl().scan_only(loop_name, *args, **kwargs)


def _impl() -> Any:
    try:
        from . import orchestrator

        return orchestrator
    except Exception:
        scripts_dir = Path(__file__).resolve().parents[1]
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))
        module_name = "routine_orchestrator.orchestrator"
        if module_name in sys.modules:
            return sys.modules[module_name]
        spec = importlib.util.spec_from_file_location(
            module_name,
            Path(__file__).with_name("orchestrator.py"),
        )
        if spec is None or spec.loader is None:
            raise ImportError("Cannot load routine_orchestrator.orchestrator")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module
