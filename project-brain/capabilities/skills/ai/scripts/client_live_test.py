#!/usr/bin/env python3
"""
CLI Agent Live Test (ADR-092).

Graduated end-to-end testing of CLI agents: binary, auth, MCP, round-trip.

Usage:
    python3 project-brain/capabilities/skills/ai/scripts/client_live_test.py --agent kimi
    python3 project-brain/capabilities/skills/ai/scripts/client_live_test.py --all
    python3 project-brain/capabilities/skills/ai/scripts/client_live_test.py --all --quick
    python3 project-brain/capabilities/skills/ai/scripts/client_live_test.py --agent kimi --json
    python3 project-brain/capabilities/skills/ai/scripts/client_live_test.py --agent kimi --verbose --level 3
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

# Resolve project root
SCRIPT_DIR = Path(__file__).resolve().parent
AI_BRIDGE_ROOT = SCRIPT_DIR.parent

from bootstrap_paths import ensure_project_paths  # noqa: E402

PROJECT_ROOT = ensure_project_paths(__file__)

# Add ai skill to path for adapter imports
if str(AI_BRIDGE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_BRIDGE_ROOT))

from src.config.paths import get_runtime_dir  # noqa: E402

RUNTIME_DIR = get_runtime_dir()
DIAGNOSTICS_DIR = RUNTIME_DIR / "diagnostics"


def get_cli_adapters():
    """Get all CLI agent adapters from the registry."""
    from adapters.registry import get_registry
    from adapters.cli_agent_base import CliAgentAdapter

    registry = get_registry()
    adapters = {}
    for adapter in registry.get_all():
        if isinstance(adapter, CliAgentAdapter):
            adapters[adapter.ide_name] = adapter
    return adapters


def resolve_agent_name(name: str, adapters: dict) -> str | None:
    """Resolve user-friendly agent name to adapter key.

    Supports: 'kimi', 'kimi_cli', 'claude', 'claude_code', etc.
    """
    # Direct match
    if name in adapters:
        return name

    # Try with _cli suffix
    if f"{name}_cli" in adapters:
        return f"{name}_cli"

    # Try with _code suffix (for claude -> claude_code)
    if f"{name}_code" in adapters:
        return f"{name}_code"

    # Try matching cli_command
    for key, adapter in adapters.items():
        if adapter.cli_command == name:
            return key

    return None


def format_result_table(result: dict, verbose: bool = False) -> str:
    """Format a single agent's test result as a readable table."""
    lines = []
    agent = result.get("agent", "unknown")
    cli = result.get("cli_command", "unknown")
    overall = result.get("overall", "unknown")
    duration = result.get("duration_ms", 0)

    lines.append(f"Agent: {agent} ({cli})")
    lines.append("-" * 60)

    for level_key, level_data in result.get("levels", {}).items():
        passed = level_data.get("pass")
        skipped = level_data.get("skipped", False)
        elapsed = level_data.get("duration_ms", 0)
        details = level_data.get("details", {})

        if skipped:
            status = "SKIP"
        elif passed is True:
            status = "PASS"
        elif passed is False:
            status = "FAIL"
        else:
            status = "N/A "

        # Build detail string
        detail_parts = []
        if "version" in details and details["version"]:
            detail_parts.append(details["version"])
        if "binary_path" in details and details["binary_path"]:
            detail_parts.append(f"at {details['binary_path']}")
        if "tool_count" in details and details["tool_count"] is not None:
            detail_parts.append(f"{details['tool_count']} tools")
        if "error" in details:
            detail_parts.append(details["error"])
        if "reason" in details:
            detail_parts.append(details["reason"])
        if "output_preview" in details and verbose:
            detail_parts.append(f'response: {details["output_preview"][:80]}')
        elif "stdout_length" in details and not detail_parts:
            detail_parts.append(f'{details["stdout_length"]} chars')

        detail_str = "  ".join(detail_parts)
        padded_key = f"[{level_key}]".ljust(22)
        lines.append(f"  Level {padded_key} {status}  ({elapsed}ms)  {detail_str}")

    lines.append("=" * 60)
    overall_upper = overall.upper()
    lines.append(f"RESULT: {overall_upper} ({duration}ms)")
    lines.append("")

    return "\n".join(lines)


def save_results(results: list[dict]) -> Path | None:
    """Save results to the runtime diagnostics directory."""
    try:
        DIAGNOSTICS_DIR.mkdir(parents=True, exist_ok=True)

        today = datetime.now().strftime("%Y-%m-%d")
        output_file = DIAGNOSTICS_DIR / f"client-test-{today}.json"

        payload = {
            "timestamp": datetime.now().isoformat(),
            "agent_count": len(results),
            "results": results,
        }

        output_file.write_text(json.dumps(payload, indent=2))

        # Update latest symlink
        latest = DIAGNOSTICS_DIR / "client-test-latest.json"
        if latest.is_symlink() or latest.exists():
            latest.unlink()
        latest.symlink_to(output_file.name)

        # Cleanup old files (keep 30 days)
        cutoff = time.time() - (30 * 86400)
        for f in DIAGNOSTICS_DIR.glob("client-test-*.json"):
            if f.name == "client-test-latest.json":
                continue
            if f.stat().st_mtime < cutoff:
                f.unlink()

        return output_file
    except Exception as e:
        print(f"Warning: Failed to save results: {e}", file=sys.stderr)
        return None


def emit_heal_event(agent_name: str, level_failed: str, error: str) -> None:
    """Emit a self-heal event on test failure."""
    try:
        events_file = RUNTIME_DIR / "self_heal_events.jsonl"
        if not events_file.parent.exists():
            return

        event = {
            "timestamp": datetime.now().isoformat(),
            "category": "agent_health",
            "severity": "high" if "0_binary" in level_failed else "medium",
            "source": "client_live_test",
            "message": f"CLI agent {agent_name} failed at {level_failed}: {error}",
            "metadata": {
                "agent": agent_name,
                "failed_level": level_failed,
                "error": error,
            },
        }

        with open(events_file, "a") as f:
            f.write(json.dumps(event) + "\n")
    except Exception:
        pass  # Best-effort


def main():
    parser = argparse.ArgumentParser(description="CLI Agent Live Test (ADR-092)")
    parser.add_argument("--agent", type=str, help="Agent to test (e.g., kimi, claude, opencode)")
    parser.add_argument("--all", action="store_true", help="Test all installed CLI agents")
    parser.add_argument("--level", type=int, default=4, help="Max test level (0-4, default 4)")
    parser.add_argument("--quick", action="store_true", help="Quick mode: levels 0-2 only (no LLM calls)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--verbose", action="store_true", help="Show full agent output")
    parser.add_argument("--report", action="store_true", help="Run all and generate report")
    args = parser.parse_args()

    if args.quick:
        args.level = min(args.level, 2)

    if args.report:
        args.all = True

    if not args.agent and not args.all:
        parser.error("Specify --agent <name> or --all")

    adapters = get_cli_adapters()

    if not adapters:
        print("Error: No CLI adapters found in registry.", file=sys.stderr)
        sys.exit(1)

    # Determine which agents to test
    targets = {}
    if args.all:
        targets = adapters
    else:
        resolved = resolve_agent_name(args.agent, adapters)
        if not resolved:
            available = ", ".join(sorted(adapters.keys()))
            print(f"Error: Unknown agent '{args.agent}'. Available: {available}", file=sys.stderr)
            sys.exit(1)
        targets = {resolved: adapters[resolved]}

    # Run tests
    results = []
    if not args.json:
        print("CLI Agent Live Test")
        print("=" * 60)

    for name, adapter in sorted(targets.items()):
        # Check if installed first
        detection = adapter.detect()
        if not detection.get("installed"):
            result = {
                "agent": name,
                "cli_command": adapter.cli_command,
                "timestamp": datetime.now().isoformat(),
                "overall": "skip",
                "duration_ms": 0,
                "levels": {},
                "skip_reason": f"{adapter.cli_command} not installed",
            }
            results.append(result)
            if not args.json:
                print(f"Agent: {name} ({adapter.cli_command})")
                print("  SKIPPED — not installed")
                print()
            continue

        result = adapter.live_test(level=args.level)
        results.append(result)

        if not args.json:
            print(format_result_table(result, verbose=args.verbose))

        # Emit heal event on failure
        if result.get("overall") == "fail":
            for level_key, level_data in result.get("levels", {}).items():
                if level_data.get("pass") is False and not level_data.get("skipped"):
                    error = level_data.get("details", {}).get("error", "unknown")
                    emit_heal_event(name, level_key, error)
                    break

    # Output
    if args.json:
        output = {
            "timestamp": datetime.now().isoformat(),
            "agent_count": len(results),
            "level": args.level,
            "quick_mode": args.quick,
            "results": results,
        }
        print(json.dumps(output, indent=2))
    else:
        # Summary
        passed = sum(1 for r in results if r.get("overall") == "pass")
        failed = sum(1 for r in results if r.get("overall") == "fail")
        partial = sum(1 for r in results if r.get("overall") == "partial")
        skipped = sum(1 for r in results if r.get("overall") == "skip")
        total = len(results)
        print(f"Summary: {passed} passed, {failed} failed, {partial} partial, {skipped} skipped / {total} total")

    # Save results
    saved = save_results(results)
    if saved and not args.json:
        print(f"Results saved to: {saved}")

    # Exit code
    if any(r.get("overall") == "fail" for r in results):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
