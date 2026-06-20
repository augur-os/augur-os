"""Tests for src.lib.capabilities.baseline (ADR-734 C1)."""

from __future__ import annotations

from pathlib import Path

from src.lib.capabilities import baseline
from src.lib.capabilities.exposure_policy import CapabilityRecord


def test_build_baseline_returns_sorted_record_summaries():
    records = [
        CapabilityRecord(
            id="command:b",
            type="command",
            owner_kind="augur",
            management="generated",
            scope="project",
            classification_status="approved",
            primary_surface="command",
            preferred_client="shell",
            current_exposure=("claude",),
            export_to=("claude",),
            drift=(),
            source_paths=(),
            metadata={},
        ),
        CapabilityRecord(
            id="command:a",
            type="command",
            owner_kind="augur",
            management="generated",
            scope="project",
            classification_status="unclassified",
            primary_surface="command",
            preferred_client="shell",
            current_exposure=("agents-md",),
            export_to=(),
            drift=(),
            source_paths=(),
            metadata={},
        ),
    ]
    snapshot = baseline.build_baseline(records)
    assert [row["id"] for row in snapshot["records"]] == ["command:a", "command:b"]
    assert snapshot["records"][0]["classification_status"] == "unclassified"
    assert snapshot["records"][1]["current_exposure"] == ["claude"]


def test_write_and_read_baseline_round_trip(tmp_path: Path) -> None:
    records = [
        CapabilityRecord(
            id="skill:demo",
            type="skill",
            owner_kind="augur",
            management="generated",
            scope="project",
            classification_status="approved",
            primary_surface="skill",
            preferred_client="claude",
            current_exposure=("claude",),
            export_to=("claude",),
            drift=(),
            source_paths=(),
            metadata={},
        )
    ]
    path = tmp_path / "baseline.json"
    baseline.write_baseline(path, baseline.build_baseline(records))
    loaded = baseline.read_baseline(path)
    assert loaded["records"][0]["id"] == "skill:demo"
    assert loaded["version"] == 1


def test_cli_script_writes_baseline_to_path(tmp_path: Path, monkeypatch) -> None:
    import importlib.util

    from src.config import paths as paths_mod

    monkeypatch.setattr(paths_mod, "get_cache_dir", lambda: tmp_path)
    spec = importlib.util.spec_from_file_location(
        "capability_baseline",
        Path(__file__).resolve().parents[2] / "scripts" / "capability_baseline.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    target = tmp_path / "snap.json"
    rc = module.main(["--out", str(target)])
    assert rc == 0
    assert target.is_file()
    payload = baseline.read_baseline(target)
    assert payload["version"] == 1
    assert isinstance(payload["records"], list)
