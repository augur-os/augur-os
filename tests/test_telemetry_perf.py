import sys
import os
import json
import shutil
import tempfile
from pathlib import Path
from datetime import datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent  # tests -> project root
sys.path.insert(0, str(PROJECT_ROOT))
# Mock the data directory for testing
TEST_DATA_DIR: Path | None = None
_PREVIOUS_AUGUR_ROOT: str | None = None


def setup():
    # Clean up BEFORE setting env var and importing, to avoid self-locking
    global TEST_DATA_DIR, _PREVIOUS_AUGUR_ROOT

    if TEST_DATA_DIR and TEST_DATA_DIR.exists():
        try:
            shutil.rmtree(TEST_DATA_DIR)
        except Exception as e:
            print(f"Warning: Failed to clean temp dir: {e}")

    TEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="augur-telemetry-"))
    _PREVIOUS_AUGUR_ROOT = os.environ.get("AUGUR_ROOT")

    os.environ["AUGUR_ROOT"] = str(TEST_DATA_DIR)

    # Now import
    global pt, savePageMetric, getPageMetrics

    import src.mcp.augur_framework.tools.infrastructure.page_telemetry as pt

    # Re-initialize METRICS_DIR since it's a global constant in the module
    pt.METRICS_DIR = TEST_DATA_DIR / "runtime" / "metrics" / "page-metrics"
    pt.ensure_metrics_dir()
    savePageMetric = pt.savePageMetric
    getPageMetrics = pt.getPageMetrics


def setup_module():
    setup()


def teardown_module():
    if _PREVIOUS_AUGUR_ROOT:
        os.environ["AUGUR_ROOT"] = _PREVIOUS_AUGUR_ROOT
    else:
        os.environ.pop("AUGUR_ROOT", None)
    if TEST_DATA_DIR and TEST_DATA_DIR.exists():
        shutil.rmtree(TEST_DATA_DIR)


def test_jsonl_write_read():
    print("Testing JSONL write and read...")

    # 1. Save some metrics
    metrics = [
        {"path": "/test", "metric": "load", "duration": 100, "timestamp": "2026-01-01T10:00:00"},
        {"path": "/test", "metric": "load", "duration": 200, "timestamp": "2026-01-01T10:01:00"},
    ]

    for m in metrics:
        savePageMetric(m)

    # 2. Check file content
    date = datetime.now().strftime("%Y-%m-%d")
    file_path = pt.METRICS_DIR / f"metrics_{date}.json"
    content = file_path.read_text()

    lines = content.strip().split('\n')
    assert len(lines) == 2, f"Expected 2 lines, got {len(lines)}"

    assert content.strip().startswith('{') and content.strip().endswith('}'), "File content does not look like JSONL"

    # 3. Read back using getPageMetrics
    # We need to mock datetime.now() or ensure our test data is within lookback
    # The timestamps above are old, so we need to set them to today
    today_iso = datetime.now().isoformat()

    # Clear and rewrite with today's date
    if file_path.exists():
        file_path.unlink()

    savePageMetric({"path": "/today", "metric": "load", "duration": 150, "timestamp": today_iso})

    results = getPageMetrics(days_to_look_back=1)

    assert len(results) > 0, "No results returned from getPageMetrics"

    assert results[0]["path"] == "/today", f"Expected path '/today', got {results[0]['path']}"

    print("✅ JSONL write/read passed")


def test_legacy_compatibility():
    print("\nTesting Legacy (JSON Array) compatibility...")

    date = datetime.now().strftime("%Y-%m-%d")
    file_path = pt.METRICS_DIR / f"metrics_{date}.json"

    # 1. Create a legacy file
    legacy_data = [{"path": "/legacy", "metric": "load", "duration": 300, "timestamp": datetime.now().isoformat()}]
    file_path.write_text(json.dumps(legacy_data))

    # 2. Append new data (should append as JSONL line after the array)
    # Note: The current implementation appends to the file.
    # If the file ends with ']', appending '{...}' makes it invalid JSON array but valid mixed content?
    # Our reader logic:
    # if content.strip().startswith("["): try json.loads
    # if not metrics: try jsonl

    # Wait, if we append to a JSON array file, it becomes:
    # [{"..."}]
    # {"..."}
    # json.loads will fail.
    # Our reader logic handles this:
    # try json.loads -> fail
    # fall through to JSONL parsing
    # JSONL parser iterates lines.
    # Line 1: [{"..."}] -> json.loads -> list -> wait, metrics.append(list)? No.
    # The JSONL parser expects dicts.

    # Let's see the reader logic again:
    # metrics.append(json.loads(line))
    # If line is `[{"..."}]`, json.loads returns a list.
    # Then `for m in metrics:` iterates over that list? No, metrics is a list of dicts.
    # If we append a list to metrics, metrics becomes [list, dict].
    # Then `m.get` will fail on the list.

    # Correction needed in reader logic?
    # Let's test it first.

    savePageMetric({"path": "/new", "metric": "load", "duration": 400, "timestamp": datetime.now().isoformat()})

    # 3. Read back
    results = getPageMetrics(days_to_look_back=1)

    paths = sorted([r["path"] for r in results])
    print(f"Found paths: {paths}")

    assert "/legacy" in paths and "/new" in paths, "Missing paths in legacy compatibility test"
    print("✅ Legacy compatibility passed")


if __name__ == "__main__":
    setup()

    success = True
    try:
        test_jsonl_write_read()
    except AssertionError as exc:
        success = False
        print(f"\n⛔ JSONL write/read failed: {exc}")

    try:
        test_legacy_compatibility()
    except AssertionError as exc:
        success = False
        print(f"\n⛔ Legacy compatibility failed: {exc}")

    # Cleanup (optional, might fail due to logging)
    # if TEST_DATA_DIR.exists():
    #    shutil.rmtree(TEST_DATA_DIR)

    if success:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print("\n⛔ Some tests failed.")
        sys.exit(1)
