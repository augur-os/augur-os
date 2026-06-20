"""Tests for job_ledger/config.py -- daemon skill config block."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

LEDGER_DIR = Path(__file__).resolve().parents[2] / "scripts" / "job_ledger"


def _load(module_name: str, file_name: str) -> Any:
    full_name = f"jobledger_{module_name}"
    if full_name in sys.modules:
        module = sys.modules[full_name]
        sys.modules[module_name] = module
        return module
    spec = importlib.util.spec_from_file_location(full_name, LEDGER_DIR / file_name)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_load_job_ledger_config_reads_block(tmp_path: Path, monkeypatch) -> None:
    cfg_module = _load("config", "config.py")
    fake = tmp_path / "config.yaml"
    fake.write_text(
        "contributions: {}\n"
        "job_ledger:\n"
        "  heartbeat_threshold_s: 120\n"
        "  retention_days: 14\n"
        "  resubmit_allowlist: [routine-vault]\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(cfg_module, "_config_path", lambda: fake)
    cfg = cfg_module.load_job_ledger_config()
    assert cfg["heartbeat_threshold_s"] == 120
    assert cfg["retention_days"] == 14
    assert cfg["resubmit_allowlist"] == ["routine-vault"]


def test_load_job_ledger_config_defaults_when_missing(tmp_path: Path, monkeypatch) -> None:
    cfg_module = _load("config", "config.py")
    fake = tmp_path / "config.yaml"
    fake.write_text("contributions: {}\n", encoding="utf-8")
    monkeypatch.setattr(cfg_module, "_config_path", lambda: fake)
    cfg = cfg_module.load_job_ledger_config()
    assert cfg["heartbeat_threshold_s"] == 300
    assert cfg["retention_days"] == 30
    assert cfg["resubmit_allowlist"] == []
