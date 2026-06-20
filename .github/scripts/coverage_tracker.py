#!/usr/bin/env python3
"""
Coverage Tracker

Collects coverage data from Jest and pytest, appends to a rolling history file
for dashboard trend visualization.

Usage:
    python3 .github/scripts/coverage_tracker.py [--save] [--json]

Options:
    --save    Append current coverage to history file
    --json    Output as JSON
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def get_project_root() -> Path:
    script_dir = Path(__file__).resolve().parent
    return script_dir.parent.parent


def read_jest_coverage(root: Path) -> dict[str, float] | None:
    """Read Jest coverage summary."""
    coverage_file = root / "data" / "runtime" / "coverage" / "coverage-summary.json"
    if not coverage_file.exists():
        # Also check the dashboard local path
        coverage_file = root / "apps" / "dashboard" / "coverage" / "coverage-summary.json"
    if not coverage_file.exists():
        return None

    try:
        with open(coverage_file) as f:
            data = json.load(f)
        total = data.get("total", {})
        return {
            "statements": total.get("statements", {}).get("pct", 0),
            "branches": total.get("branches", {}).get("pct", 0),
            "functions": total.get("functions", {}).get("pct", 0),
            "lines": total.get("lines", {}).get("pct", 0),
        }
    except (json.JSONDecodeError, KeyError):
        return None


def read_python_coverage(root: Path) -> dict[str, float] | None:
    """Read Python coverage from coverage.json."""
    coverage_file = root / "coverage.json"
    if not coverage_file.exists():
        return None

    try:
        with open(coverage_file) as f:
            data = json.load(f)
        totals = data.get("totals", {})
        return {
            "statements": totals.get("percent_covered", 0),
            "lines": totals.get("percent_covered", 0),
            "missing": totals.get("missing_lines", 0),
            "covered": totals.get("covered_lines", 0),
        }
    except (json.JSONDecodeError, KeyError):
        return None


def count_test_files(root: Path) -> dict[str, int]:
    """Count test files by type."""
    python_tests = 0
    ts_tests = 0

    for pattern, counter_name in [("**/test_*.py", "python"), ("**/*.test.ts", "ts"), ("**/*.test.tsx", "tsx")]:
        for _ in root.glob(pattern):
            if counter_name == "python":
                python_tests += 1
            else:
                ts_tests += 1

    return {"python": python_tests, "typescript": ts_tests, "total": python_tests + ts_tests}


def collect_coverage_snapshot(root: Path) -> dict[str, Any]:
    """Collect current coverage data."""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        "jest": read_jest_coverage(root),
        "python": read_python_coverage(root),
        "test_counts": count_test_files(root),
    }


def load_history(history_file: Path) -> list[dict[str, Any]]:
    """Load coverage history."""
    if not history_file.exists():
        return []
    try:
        with open(history_file) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def save_history(history: list[dict[str, Any]], history_file: Path) -> None:
    """Save coverage history, maintaining 90-day rolling window."""
    # Keep last 90 entries (approximately 90 days of nightly runs)
    history = history[-90:]
    history_file.parent.mkdir(parents=True, exist_ok=True)
    with open(history_file, 'w') as f:
        json.dump(history, f, indent=2)


def calculate_trend(history: list[dict[str, Any]], key_path: list[str]) -> str:
    """Calculate trend from history: up, down, or stable."""
    if len(history) < 2:
        return "stable"

    def get_nested(d: dict, keys: list[str]) -> float | None:
        for k in keys:
            if d is None or not isinstance(d, dict):
                return None
            d = d.get(k)
        return d if isinstance(d, (int, float)) else None

    recent = [get_nested(e, key_path) for e in history[-7:]]
    recent = [v for v in recent if v is not None]
    if len(recent) < 2:
        return "stable"

    avg_first = sum(recent[:len(recent) // 2]) / max(len(recent) // 2, 1)
    avg_second = sum(recent[len(recent) // 2:]) / max(len(recent) - len(recent) // 2, 1)
    diff = avg_second - avg_first

    if diff > 1.0:
        return "up"
    elif diff < -1.0:
        return "down"
    return "stable"


def print_summary(snapshot: dict[str, Any], history: list[dict[str, Any]]) -> None:
    """Print human-readable summary."""
    print("=" * 60)
    print("COVERAGE SUMMARY")
    print(f"Generated: {snapshot['timestamp']}")
    print("=" * 60)

    jest = snapshot.get("jest")
    if jest:
        print("\nJest (TypeScript):")
        print(f"  Statements: {jest['statements']:.1f}%")
        print(f"  Branches:   {jest['branches']:.1f}%")
        print(f"  Functions:  {jest['functions']:.1f}%")
        print(f"  Lines:      {jest['lines']:.1f}%")
    else:
        print("\nJest: No coverage data found")

    python = snapshot.get("python")
    if python:
        print("\nPython:")
        print(f"  Coverage:   {python['statements']:.1f}%")
        print(f"  Covered:    {python.get('covered', 'N/A')} lines")
        print(f"  Missing:    {python.get('missing', 'N/A')} lines")
    else:
        print("\nPython: No coverage data found")

    counts = snapshot.get("test_counts", {})
    print("\nTest Files:")
    print(f"  Python:     {counts.get('python', 0)}")
    print(f"  TypeScript: {counts.get('typescript', 0)}")
    print(f"  Total:      {counts.get('total', 0)}")

    if history:
        jest_trend = calculate_trend(history, ["jest", "lines"])
        python_trend = calculate_trend(history, ["python", "statements"])
        print("\nTrends (7-day):")
        print(f"  Jest:       {jest_trend}")
        print(f"  Python:     {python_trend}")

    print()


def main() -> int:
    root = get_project_root()

    # Use AUGUR_ROOT env var if set (for CI)
    project_root = os.environ.get("AUGUR_ROOT", str(root))
    history_file = Path(project_root) / "runtime" / "metrics" / "coverage_history.json"

    output_json = "--json" in sys.argv
    save = "--save" in sys.argv

    snapshot = collect_coverage_snapshot(root)
    history = load_history(history_file)

    if save:
        history.append(snapshot)
        save_history(history, history_file)

    if output_json:
        output = {
            "current": snapshot,
            "history_count": len(history),
            "trends": {
                "jest_lines": calculate_trend(history, ["jest", "lines"]),
                "python_coverage": calculate_trend(history, ["python", "statements"]),
            },
        }
        print(json.dumps(output, indent=2))
    else:
        print_summary(snapshot, history)
        if save:
            print(f"Coverage saved to: {history_file}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
