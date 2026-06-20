import sys
from pathlib import Path

# Add project root
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.config.paths import get_logs_dir  # noqa: E402
from src.lib.ai.usage_tracker import UsageTracker  # noqa: E402
import json  # noqa: E402


def test_schema():
    tracker = UsageTracker()
    print("Tracking request...")
    tracker.track_request(
        provider="test_provider",
        profile="test_profile",
        model="test_model",
        prompt_text="prompt text",
        response_text="response text",
        cost=0.001,
        success=True,
        error=None,
        prompt_tokens=10,
        completion_tokens=20,
    )

    # Read last line
    log_file = get_logs_dir() / "llm_logs.jsonl"
    if log_file.exists():
        with open(log_file, "r") as f:
            lines = f.readlines()
            last_line = lines[-1]
            entry = json.loads(last_line)
            print("Last Log Entry Keys:", list(entry.keys()))
            if "prompt_tokens" in entry:
                print("✅ Schema Verified: Found prompt_tokens")
            else:
                print("❌ Schema Failed: Missing prompt_tokens")


if __name__ == "__main__":
    test_schema()
