#!/usr/bin/env python3
"""
Visual Regression Testing for Webapp Testing Agent.

Visual regression testing:
- Screenshot comparison
- Diff detection
- Threshold alerts
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


def get_repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in [current] + list(current.parents):
        if (parent / ".git").exists():
            return parent
    return Path.cwd()


def get_screenshots_dir(repo: Path) -> Path:
    screenshots = repo / "tests" / "dashboard" / "visual" / "screenshots"
    screenshots.mkdir(parents=True, exist_ok=True)
    return screenshots


def find_baseline_screenshots(screenshots_dir: Path) -> list[Path]:
    """Find baseline screenshots."""
    baseline_dir = screenshots_dir / "baseline"
    if not baseline_dir.exists():
        return []
    return list(baseline_dir.glob("*.png"))


def find_current_screenshots(screenshots_dir: Path) -> list[Path]:
    """Find current test screenshots."""
    current_dir = screenshots_dir / "current"
    if not current_dir.exists():
        return []
    return list(current_dir.glob("*.png"))


def compare_screenshots(baseline: Path, current: Path) -> dict[str, Any]:
    """Compare two screenshots using pixel-level diff with Pillow."""
    try:
        from PIL import Image, ImageChops
    except ImportError:
        # Fallback to size-based comparison if Pillow not installed
        baseline_size = baseline.stat().st_size if baseline.exists() else 0
        current_size = current.stat().st_size if current.exists() else 0
        size_diff = abs(baseline_size - current_size)
        threshold = baseline_size * 0.01
        return {
            "baseline": baseline.name,
            "baseline_size": baseline_size,
            "current_size": current_size,
            "size_diff": size_diff,
            "passed": size_diff <= threshold,
            "diff_percentage": (size_diff / baseline_size * 100) if baseline_size > 0 else 0,
            "method": "size-based (Pillow not available)",
        }

    baseline_img = Image.open(baseline).convert("RGB")
    current_img = Image.open(current).convert("RGB")

    # Resize current to match baseline if dimensions differ
    if baseline_img.size != current_img.size:
        current_img = current_img.resize(baseline_img.size)

    diff = ImageChops.difference(baseline_img, current_img)
    diff_pixels = sum(1 for px in diff.getdata() if any(c > 10 for c in px))
    total_pixels = baseline_img.size[0] * baseline_img.size[1]
    diff_percentage = (diff_pixels / total_pixels * 100) if total_pixels > 0 else 0

    return {
        "baseline": baseline.name,
        "total_pixels": total_pixels,
        "diff_pixels": diff_pixels,
        "diff_percentage": round(diff_percentage, 3),
        "passed": diff_percentage <= 1.0,  # 1% threshold
        "method": "pixel-diff",
    }


def run_visual_regression(repo: Path) -> dict[str, Any]:
    """Run visual regression tests."""
    screenshots_dir = get_screenshots_dir(repo)
    baselines = find_baseline_screenshots(screenshots_dir)

    results = {
        "timestamp": datetime.now().isoformat(),
        "baselines_found": len(baselines),
        "comparisons": [],
        "passed": 0,
        "failed": 0,
    }

    for baseline in baselines:
        current = screenshots_dir / "current" / baseline.name

        if not current.exists():
            results["comparisons"].append(
                {
                    "name": baseline.name,
                    "status": "missing",
                    "passed": False,
                }
            )
            results["failed"] += 1
            continue

        comparison = compare_screenshots(baseline, current)
        comparison["name"] = baseline.name
        comparison["status"] = "passed" if comparison["passed"] else "failed"
        results["comparisons"].append(comparison)

        if comparison["passed"]:
            results["passed"] += 1
        else:
            results["failed"] += 1

    return results


def generate_report(results: dict[str, Any]) -> str:
    """Generate visual regression report."""
    lines = [
        "# Visual Regression Report",
        "",
        f"**Generated**: {results['timestamp'][:19]}",
        "",
        "## Summary",
        f"- Baselines: {results['baselines_found']}",
        f"- Passed: {results['passed']}",
        f"- Failed: {results['failed']}",
        "",
    ]

    if not results["comparisons"]:
        lines.append("> No baseline screenshots found. Run tests to create baselines.")
        lines.append("")
        lines.append("### Creating Baselines")
        lines.append("")
        lines.append("```bash")
        lines.append("# Run Playwright tests with screenshots")
        lines.append("npx playwright test --update-snapshots")
        lines.append("```")
    else:
        lines.append("## Results")
        lines.append("")
        lines.append("| Screenshot | Status | Diff |")
        lines.append("|------------|--------|------|")

        for comp in results["comparisons"]:
            icon = "✅" if comp.get("passed") else "❌"
            diff = f"{comp.get('diff_percentage', 0):.1f}%" if "diff_percentage" in comp else "-"
            lines.append(f"| {comp['name']} | {icon} {comp['status']} | {diff} |")

    lines.append("")

    return "\n".join(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Visual Regression")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--update", action="store_true", help="Update baselines")
    args = parser.parse_args()

    repo = get_repo_root()

    _out("🖼️ Running visual regression...\n")

    results = run_visual_regression(repo)

    if args.json:
        _out(json.dumps(results, indent=2))
    else:
        _out(generate_report(results))

    return 1 if results["failed"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
