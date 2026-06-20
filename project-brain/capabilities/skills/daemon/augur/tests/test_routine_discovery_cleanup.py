"""Background-routines cleanup: a soft-disabled service (enabled:false or a >=10yr
sentinel interval) surfaces as status='disabled'/'Disabled', and a daemon-script that
is already a daemon-service is not double-listed.
"""
from __future__ import annotations

from pathlib import Path

from skills.daemon.scripts.routine_discovery import (
    DaemonServiceDiscoverer,
    discover_all_routines,
)


def _discover(tmp_path: Path, yaml_text: str):
    cfg = tmp_path / "adaptive_loops.yaml"
    cfg.write_text(yaml_text, encoding="utf-8")
    return DaemonServiceDiscoverer(
        config_path=cfg, logs_base_dir=tmp_path / "logs"
    ).discover()


def test_enabled_false_service_is_disabled(tmp_path: Path) -> None:
    routines = _discover(
        tmp_path,
        "services:\n  insight_scanner:\n    enabled: false\n    interval_hours: 12\n",
    )
    r = next(x for x in routines if x.id == "insight_scanner")
    assert r.status == "disabled"
    assert r.cadence["spec"] == "Disabled"


def test_century_interval_sentinel_is_disabled(tmp_path: Path) -> None:
    routines = _discover(
        tmp_path,
        "services:\n  insight_scanner:\n    interval_hours: 876000\n",
    )
    r = next(x for x in routines if x.id == "insight_scanner")
    assert r.status == "disabled"
    assert r.cadence["spec"] == "Disabled"


def test_normal_interval_stays_enabled(tmp_path: Path) -> None:
    routines = _discover(
        tmp_path,
        "services:\n  continuous_executor:\n    poll_interval_seconds: 300\n",
    )
    r = next(x for x in routines if x.id == "continuous_executor")
    assert r.status == "enabled"
    assert r.cadence["spec"] != "Disabled"


def test_real_system_has_no_service_script_duplicate() -> None:
    """Real-data: no daemon-script shares a source_path with a daemon-service."""
    routines = discover_all_routines()
    service_paths = {
        r.source_path for r in routines if r.source_kind == "daemon-service" and r.source_path
    }
    dupes = [
        r.id for r in routines if r.source_kind == "daemon-script" and r.source_path in service_paths
    ]
    assert dupes == [], f"daemon-script duplicates of services: {dupes}"
