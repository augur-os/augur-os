"""Reader for the job_ledger block in the daemon skill config.yaml (ADR-743)."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("job_ledger.config")

_DEFAULTS: dict[str, Any] = {
    "heartbeat_threshold_s": 300,
    "retention_days": 30,
    "resubmit_allowlist": [],
}


def _config_path() -> Path:
    """Path to the daemon skill config.yaml. Monkeypatchable in tests."""
    return Path(__file__).resolve().parents[2] / "config.yaml"


def load_job_ledger_config() -> dict[str, Any]:
    """Return job_ledger config merged over built-in defaults."""
    cfg = dict(_DEFAULTS)
    try:
        data = yaml.safe_load(_config_path().read_text(encoding="utf-8")) or {}
        block = data.get("job_ledger") or {}
        if isinstance(block, dict):
            cfg.update({key: block[key] for key in _DEFAULTS if key in block})
    except Exception as exc:  # noqa: BLE001
        logger.warning("job ledger config unreadable (%s); using defaults", exc)
    return cfg
