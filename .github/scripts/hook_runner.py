#!/usr/bin/env python3
"""
Hook Runner - Execute lifecycle hooks based on hooks.yaml configuration.

Runs hooks for various lifecycle events (pre-commit, post-chain, on-build-error, etc.)

Usage:
    python3 hook_runner.py --list
    python3 hook_runner.py --event pre-commit
    python3 hook_runner.py --event pre-commit --dry-run
    python3 hook_runner.py --event post-chain --chain feature_development
"""

import argparse
import json
import fnmatch
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
import re
import subprocess
import sys
from typing import Optional

try:
    import yaml
except ImportError as _yaml_err:
    # ADR-084: emit event and fail fast — hooks.yaml requires PyYAML
    try:
        _project_root = Path(__file__).resolve().parent.parent.parent
        sys.path.insert(0, str(_project_root))
        from src.logging.self_heal_event import emit_heal_event

        emit_heal_event(
            source="hook_runner",
            category="import_failure",
            severity="high",
            message=f"PyYAML not installed — hook_runner cannot parse hooks.yaml: {_yaml_err}",
        )
    except ImportError:
        pass
    raise ImportError(
        "PyYAML is required for hook_runner.py. Install it: pip install pyyaml"
    ) from _yaml_err


class FailureAction(str, Enum):
    """What to do when a hook fails."""

    WARN = "warn"  # Log warning, continue
    BLOCK = "block"  # Stop execution, return error
    SKIP = "skip"  # Silently skip on failure


@dataclass
class HookResult:
    """Result of executing a single hook."""

    name: str
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    skipped: bool = False
    skip_reason: Optional[str] = None


class HookRunner:
    """Execute lifecycle hooks from hooks.yaml configuration."""

    def __init__(self, hooks_file: Optional[Path] = None):
        self.project_root = self._get_project_root()
        self.hooks_file = hooks_file or self._find_hooks_file()
        self.hooks_config = self._load_hooks()
        self.log_dir = self._get_log_dir()

    def _get_project_root(self) -> Path:
        """Get project root using git or file location."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                check=True,
            )
            return Path(result.stdout.strip())
        except subprocess.CalledProcessError:
            return Path(__file__).parent.parent.parent

    def _find_hooks_file(self) -> Path:
        """Locate hooks.yaml in standard locations."""
        candidates = [
            self.project_root
            / "skills"
            / "ai"
            / "augur"
            / "data"
            / "ide-integration"
            / "hooks"
            / "hooks.yaml",
            self.project_root
            / "plugins"
            / "dev"
            / "skills"
            / "devops"
            / "data"
            / "hooks"
            / "hooks.yaml",
            self.project_root / ".github" / "hooks" / "hooks.yaml",
        ]
        for path in candidates:
            if path.exists():
                return path

        # Return default location (may not exist yet)
        return (
            self.project_root
            / "skills"
            / "ai"
            / "augur"
            / "data"
            / "ide-integration"
            / "hooks"
            / "hooks.yaml"
        )

    def _load_hooks(self) -> dict:
        """Load and parse hooks.yaml."""
        if not self.hooks_file.exists():
            return {"hooks": {}, "settings": {}}

        content = self.hooks_file.read_text()
        if not content.strip():
            return {"hooks": {}, "settings": {}}

        return yaml.safe_load(content) or {"hooks": {}, "settings": {}}

    def _get_log_dir(self) -> Path:
        """Get log directory from settings or default."""
        log_path = str(self.hooks_config.get("settings", {}).get("log_dir", "hooks"))
        if Path(log_path).is_absolute():
            return Path(log_path)

        try:
            sys.path.insert(0, str(self.project_root))
            from src.config.paths import get_state_dir

            state_dir = get_state_dir()
        except Exception:
            state_dir = Path.home() / "Library" / "Application Support" / "Augur" / "state"

        normalized = log_path.removeprefix("state/")
        return state_dir / normalized

    def _get_changed_files(self) -> list[str]:
        """Get list of staged files (for pre-commit conditions)."""
        try:
            result = subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                capture_output=True,
                text=True,
                check=True,
                cwd=str(self.project_root),
            )
            return [f for f in result.stdout.strip().split("\n") if f]
        except subprocess.CalledProcessError:
            return []

    def _evaluate_condition(self, condition: str) -> bool:
        """
        Evaluate hook condition.

        Supported conditions:
        - changed_files('pattern') - True if any staged file matches glob pattern
        """
        if not condition:
            return True

        # Parse changed_files('pattern') condition
        match = re.match(r"changed_files\(['\"]([^'\"]+)['\"]\)", condition)
        if match:
            pattern = match.group(1)
            changed = self._get_changed_files()
            return any(fnmatch.fnmatch(f, pattern) for f in changed)

        # Unknown condition - default to True (run the hook)
        return True

    def run_hook(self, hook: dict, dry_run: bool = False) -> HookResult:
        """Execute a single hook."""
        name = hook["name"]
        command = hook["run"]
        timeout = hook.get("timeout", 120)
        condition = hook.get("condition")

        # Check condition
        if condition and not self._evaluate_condition(condition):
            return HookResult(
                name=name,
                success=True,
                exit_code=0,
                stdout="",
                stderr="",
                duration_ms=0,
                skipped=True,
                skip_reason=f"Condition not met: {condition}",
            )

        if dry_run:
            print(f"    [DRY-RUN] Would run: {command}")
            return HookResult(
                name=name,
                success=True,
                exit_code=0,
                stdout="",
                stderr="",
                duration_ms=0,
                skipped=True,
                skip_reason="Dry run mode",
            )

        start = datetime.now()
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self.project_root),
            )
            duration = int((datetime.now() - start).total_seconds() * 1000)

            return HookResult(
                name=name,
                success=result.returncode == 0,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                duration_ms=duration,
            )

        except subprocess.TimeoutExpired:
            duration = timeout * 1000
            return HookResult(
                name=name,
                success=False,
                exit_code=-1,
                stdout="",
                stderr=f"Timeout after {timeout}s",
                duration_ms=duration,
            )
        except Exception as e:
            return HookResult(
                name=name,
                success=False,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_ms=0,
            )

    def run_event(
        self, event: str, dry_run: bool = False, chain_name: Optional[str] = None
    ) -> tuple[bool, list[HookResult]]:
        """
        Run all hooks for an event.

        Args:
            event: Event type (pre-commit, post-chain, on-build-error, etc.)
            dry_run: If True, show what would run without executing
            chain_name: For post-chain events, filter by chain name

        Returns:
            Tuple of (all_success, list of HookResults)
        """
        hooks = self.hooks_config.get("hooks", {}).get(event, [])

        if not hooks:
            print(f"ℹ️  No hooks configured for event: {event}")
            return True, []

        results = []
        all_success = True

        print(f"\n{'=' * 50}")
        print(f"🪝 Running {event} hooks ({len(hooks)} hook(s))")
        print(f"{'=' * 50}\n")

        for hook in hooks:
            # Filter by chain name for post-chain hooks
            if event == "post-chain" and chain_name:
                allowed_chains = hook.get("chains", ["*"])
                if "*" not in allowed_chains and chain_name not in allowed_chains:
                    continue

            description = hook.get("description", hook["run"][:50])
            print(f"  [{hook['name']}] {description}")

            result = self.run_hook(hook, dry_run)
            results.append(result)

            if result.skipped:
                print(f"    ⏭️  SKIPPED: {result.skip_reason}")
            elif result.success:
                print(f"    ✅ SUCCESS ({result.duration_ms}ms)")
            else:
                on_failure = FailureAction(hook.get("on_failure", "warn"))
                print(f"    ❌ FAILED (exit {result.exit_code})")

                if result.stderr:
                    # Show first 200 chars of error
                    preview = result.stderr[:200].replace("\n", " ")
                    print(f"    📝 {preview}...")

                if on_failure == FailureAction.BLOCK:
                    print("    🛑 BLOCKING - hook configured to block on failure")
                    all_success = False
                elif on_failure == FailureAction.WARN:
                    print("    ⚠️  WARNING - continuing despite failure")
                # SKIP: silently continue

        # Log results
        if not dry_run:
            self._log_results(event, results)

        return all_success, results

    def _log_results(self, event: str, results: list[HookResult]):
        """Log hook execution results to file."""
        self.log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = self.log_dir / f"{event}_{timestamp}.json"

        log_data = {
            "event": event,
            "timestamp": datetime.now().isoformat(),
            "results": [
                {
                    "name": r.name,
                    "success": r.success,
                    "exit_code": r.exit_code,
                    "duration_ms": r.duration_ms,
                    "skipped": r.skipped,
                    "skip_reason": r.skip_reason,
                }
                for r in results
            ],
        }
        log_file.write_text(json.dumps(log_data, indent=2))

    def list_hooks(self):
        """List all configured hooks."""
        hooks = self.hooks_config.get("hooks", {})

        if not hooks:
            print("\n📋 No hooks configured.")
            print(f"   Create hooks at: {self.hooks_file}")
            return

        print(f"\n📋 Configured Hooks (from {self.hooks_file.name}):\n")

        for event, event_hooks in hooks.items():
            print(f"  {event}:")
            for hook in event_hooks:
                on_fail = hook.get("on_failure", "warn")
                timeout = hook.get("timeout", 120)
                print(f"    • {hook['name']} [{on_fail}] (timeout: {timeout}s)")
                if hook.get("description"):
                    print(f"      {hook['description']}")
                print(
                    f"      Run: {hook['run'][:60]}{'...' if len(hook['run']) > 60 else ''}"
                )
            print()


def main():
    parser = argparse.ArgumentParser(
        description="Hook Runner - Execute lifecycle hooks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Events:
  pre-commit      Before git commit
  post-commit     After git commit
  post-chain      After chain execution
  on-build-error  When build fails
  on-test-failure When tests fail

Examples:
  %(prog)s --list
  %(prog)s --event pre-commit
  %(prog)s --event pre-commit --dry-run
  %(prog)s --event post-chain --chain feature_development
        """,
    )

    parser.add_argument("--event", help="Event to trigger (e.g., pre-commit)")
    parser.add_argument("--chain", help="Chain name (for post-chain events)")
    parser.add_argument("--list", action="store_true", help="List all configured hooks")
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview without executing"
    )
    parser.add_argument("--hooks-file", help="Path to hooks.yaml")

    args = parser.parse_args()

    hooks_file = Path(args.hooks_file) if args.hooks_file else None

    try:
        runner = HookRunner(hooks_file)
    except Exception as e:
        print(f"❌ Failed to initialize hook runner: {e}", file=sys.stderr)
        return 1

    if args.list:
        runner.list_hooks()
        return 0

    if not args.event:
        parser.print_help()
        return 0

    success, results = runner.run_event(
        args.event, dry_run=args.dry_run, chain_name=args.chain
    )

    # Print summary
    total = len(results)
    passed = sum(1 for r in results if r.success)
    skipped = sum(1 for r in results if r.skipped)
    failed = total - passed - skipped

    print(f"\n{'=' * 50}")
    print(f"Summary: {passed} passed, {failed} failed, {skipped} skipped")
    print(f"{'=' * 50}\n")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
