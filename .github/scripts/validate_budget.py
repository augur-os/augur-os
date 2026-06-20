import argparse
import json
import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.config.paths import get_runtime_dir  # noqa: E402
from src.logging import get_entity_logger  # noqa: E402

logger = get_entity_logger("budget_validator")


def validate_budget(max_daily_cost: float):
    """Validate that daily usage is within budget."""
    stats_file = get_runtime_dir() / "stats/usage_summary.json"

    if not stats_file.exists():
        logger.warning(f"Stats file not found at {stats_file}. Skipping validation.")
        return

    try:
        with open(stats_file, "r") as f:
            stats = json.load(f)

        daily_cost = stats.get("total_cost", 0.0)

        logger.info(f"Daily Cost: ${daily_cost:.4f} (Max: ${max_daily_cost:.2f})")

        if daily_cost > max_daily_cost:
            logger.error(f"🚨 BUDGET EXCEEDED: ${daily_cost:.4f} > ${max_daily_cost:.2f}")
            # In a real scenario, this exit code would fail the CI job
            sys.exit(1)

        logger.info("✅ Budget validation passed.")

    except Exception as e:
        logger.error(f"Validation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate LLM Budget")
    parser.add_argument("--max-daily-cost", type=float, default=5.0, help="Maximum allowed daily cost in USD")
    args = parser.parse_args()

    validate_budget(args.max_daily_cost)
