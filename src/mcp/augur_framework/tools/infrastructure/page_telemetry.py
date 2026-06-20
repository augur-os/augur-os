"""
Page telemetry service for MCP server.

Native Python implementation of page-telemetry.ts functionality.
"""

import json
from datetime import datetime
from typing import Any

from src.mcp.augur_shared.config import get_runtime_dir
from src.mcp.augur_shared.logging import get_entity_logger
from src.mcp.augur_shared.utils import ljson

logger = get_entity_logger("page_telemetry")

# Metrics directory
METRICS_DIR = get_runtime_dir() / "metrics" / "page-metrics"


def ensure_metrics_dir() -> None:
    """Ensure the metrics directory exists."""
    METRICS_DIR.mkdir(parents=True, exist_ok=True)


def savePageMetric(metric: dict[str, Any]) -> None:
    """
    Save a page load metric.

    Args:
        metric: Dict with path, metric, duration, timestamp
    """
    ensure_metrics_dir()

    # Create a daily file to avoid huge files
    date = datetime.now().strftime("%Y-%m-%d")
    file_path = METRICS_DIR / f"metrics_{date}.json"

    # Append-only write using ljson utility
    ljson.append(file_path, metric)


def getPageMetrics(days_to_look_back: int = 7) -> list[dict[str, Any]]:
    """
    Get aggregated page performance stats.

    Args:
        days_to_look_back: Number of days to aggregate

    Returns:
        List of page performance stats
    """
    ensure_metrics_dir()

    # Aggregation buckets
    stats: dict[str, dict] = {}

    try:
        now = datetime.now()

        for file_path in METRICS_DIR.glob("metrics_*.json"):
            date_str = file_path.stem.replace("metrics_", "")
            try:
                file_date = datetime.strptime(date_str, "%Y-%m-%d")
                diff_days = (now - file_date).days

                if diff_days > days_to_look_back:
                    continue

                # Read metrics using ljson utility
                # LJSON handles both new format (JSONL) and skips malformed lines
                metrics = ljson.read(file_path)

                # Fallback: Check if it's the legacy array format
                # (ljson.read might return empty or parse errors if it expects lines but finds a huge array on one line)
                if not metrics:
                    try:
                        content = file_path.read_text(encoding="utf-8")
                        if content.strip().startswith("["):
                            metrics = json.loads(content)
                    except (ValueError, json.JSONDecodeError):
                        # Mixed content or really broken
                        pass

                if isinstance(metrics, dict):
                    metrics = [metrics]
                elif not isinstance(metrics, list):
                    metrics = []

                normalized_metrics: list[dict[str, Any]] = []
                for entry in metrics:
                    if isinstance(entry, dict):
                        normalized_metrics.append(entry)
                    elif isinstance(entry, list):
                        normalized_metrics.extend([item for item in entry if isinstance(item, dict)])

                for m in normalized_metrics:
                    page_path = m.get("path", "unknown")
                    if page_path not in stats:
                        stats[page_path] = {
                            "loads": [],
                            "cls": [],
                            "time_on_page": [],
                            "errors": 0,
                            "interactions": 0,
                            "visits": 0,
                            "last_measured": "",
                        }

                    current = stats[page_path]
                    metric_type = m.get("metric", "")
                    duration = m.get("duration", 0)
                    timestamp = m.get("timestamp", "")

                    if metric_type == "load":
                        current["loads"].append(duration)
                        current["visits"] += 1
                    elif metric_type == "cls":
                        current["cls"].append(duration)
                    elif metric_type == "time_on_page":
                        current["time_on_page"].append(duration)
                    elif metric_type == "error":
                        current["errors"] += duration
                    elif metric_type == "interaction":
                        current["interactions"] += duration

                    if not current["last_measured"] or timestamp > current["last_measured"]:
                        current["last_measured"] = timestamp

            except (ValueError, json.JSONDecodeError) as e:
                logger.warning(f"Failed to read metrics file {file_path}: {e}")
                continue

        # Calculate stats
        results = []
        for page_path, data in stats.items():
            count = data["visits"] or 1

            # Performance metrics
            avg_load = sum(data["loads"]) / len(data["loads"]) if data["loads"] else 0
            avg_cls = sum(data["cls"]) / len(data["cls"]) if data["cls"] else 0
            sorted_loads = sorted(data["loads"])
            p95_load = sorted_loads[int(len(sorted_loads) * 0.95)] if sorted_loads else 0
            error_rate = data["errors"] / count

            # Usage metrics
            avg_time = sum(data["time_on_page"]) / len(data["time_on_page"]) if data["time_on_page"] else 0

            # Utility metrics
            interaction_rate = data["interactions"] / count

            # Score calculation
            perf_score = 100
            if avg_load > 1.0:
                perf_score -= 20
            if avg_load > 3.0:
                perf_score -= 30
            if avg_cls > 0.1:
                perf_score -= 10
            if avg_cls > 0.25:
                perf_score -= 20
            perf_score -= error_rate * 50
            perf_score = max(0, perf_score)

            usage_score = min(100, (avg_time / 15) * 100)
            utility_score = min(100, max(60, interaction_rate * 80))
            ui_score = 98

            final_score = round((perf_score * 0.3) + (usage_score * 0.2) + (utility_score * 0.3) + (ui_score * 0.2))

            results.append(
                {
                    "path": page_path,
                    "avg_load_time": round(avg_load, 3),
                    "p95_load_time": round(p95_load, 3),
                    "avg_cls": round(avg_cls, 3),
                    "error_rate": round(error_rate, 3),
                    "avg_time_on_page": round(avg_time, 1),
                    "total_visits": data["visits"],
                    "interaction_rate": round(interaction_rate, 2),
                    "score": final_score,
                    "last_measured": data["last_measured"],
                }
            )

        return sorted(results, key=lambda x: x["score"], reverse=True)

    except Exception as e:
        logger.error(f"Failed to get page metrics: {e}")
        return []


__all__ = ["savePageMetric", "getPageMetrics"]
