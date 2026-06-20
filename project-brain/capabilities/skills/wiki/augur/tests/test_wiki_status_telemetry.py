from __future__ import annotations

import importlib.util
import json
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "wiki_status.py"
SPEC = importlib.util.spec_from_file_location("wiki_status_under_test", MODULE_PATH)
assert SPEC and SPEC.loader
wiki_status = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(wiki_status)


def test_telemetry_block_present_in_status(tmp_path: Path) -> None:
    runtime_wiki = tmp_path / "wiki"
    runtime_wiki.mkdir()
    (runtime_wiki / "last-extraction.ts").write_text("1700000000.0", encoding="utf-8")
    (runtime_wiki / "telemetry.json").write_text(
        json.dumps(
            {
                "signals_seen_by_tier": {"critical": 3, "high": 7, "medium": 11, "low": 4},
                "tokens_spent_last_run": 3120,
                "dropped_low_noise_count": 12,
            }
        ),
        encoding="utf-8",
    )

    block = wiki_status._telemetry_block(runtime_wiki)

    assert block["last_extraction_ts"] == 1700000000.0
    assert block["signals_seen_by_tier"]["critical"] == 3
    assert block["tokens_spent_last_run"] == 3120
    assert block["dropped_low_noise_count"] == 12


def test_telemetry_block_missing_files(tmp_path: Path) -> None:
    block = wiki_status._telemetry_block(tmp_path / "wiki")

    assert block["last_extraction_ts"] is None
    assert block["signals_seen_by_tier"] == {}
    assert block["tokens_spent_last_run"] is None
    assert block["dropped_low_noise_count"] is None
