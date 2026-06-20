"""Adaptive Loop Engine package.

Keep package import side effects minimal so tests can import submodules like
``skills.daemon.scripts.adaptive.loops.base_loop`` without pulling in the full
engine dependency graph.
"""

from __future__ import annotations

from importlib import import_module

__all__ = [
    "AdaptiveLoopEngine",
    "CategoryReport",
    "CycleReport",
    "TrustLedger",
    "CategoryState",
    "LoopState",
    "BaseLoop",
    "HardeningLoop",
    "LoopResult",
]


def __getattr__(name: str):
    if name == "AdaptiveLoopEngine":
        return import_module(".engine", __name__).AdaptiveLoopEngine
    if name in {"CategoryReport", "CycleReport"}:
        module = import_module(".reporting", __name__)
        return getattr(module, name)
    if name in {"TrustLedger", "CategoryState", "LoopState"}:
        module = import_module(".trust_ledger", __name__)
        return getattr(module, name)
    if name in {"BaseLoop", "LoopResult", "HardeningLoop"}:
        module = import_module(".loops", __name__)
        return getattr(module, name)
    raise AttributeError(name)
