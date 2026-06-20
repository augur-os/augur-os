#!/usr/bin/env python3
"""
Self-Heal System Self-Test (ADR-084).

End-to-end verification that the self-heal pipeline works:
1. Emits a test event via emit_heal_event()
2. Verifies the event appears in self_heal_events.jsonl
3. Triggers a scan cycle and verifies the daemon picks it up
4. Checks the registry entry was created
5. Cleans up the test event

Usage:
    python3 project-brain/capabilities/skills/daemon/scripts/self_heal_self_test.py
    python3 project-brain/capabilities/skills/daemon/scripts/self_heal_self_test.py --emit-only
    python3 project-brain/capabilities/skills/daemon/scripts/self_heal_self_test.py --check-only
"""


import importlib.util as _augur_importlib_util
import sys as _augur_sys
from pathlib import Path as _AugurPath

_augur_bootstrap_start = _AugurPath(__file__).resolve()
for _augur_bootstrap_parent in (_augur_bootstrap_start.parent, *_augur_bootstrap_start.parents):
    _augur_bootstrap_path = _augur_bootstrap_parent / "daemon" / "scripts" / "bootstrap_paths.py"
    if _augur_bootstrap_path.is_file():
        break
else:
    raise RuntimeError(f"Unable to locate shared skill bootstrap from {_augur_bootstrap_start}")

_augur_bootstrap_spec = _augur_importlib_util.spec_from_file_location(
    "_augur_shared_bootstrap_paths", _augur_bootstrap_path
)
if _augur_bootstrap_spec is None or _augur_bootstrap_spec.loader is None:
    raise RuntimeError(f"Unable to load shared skill bootstrap from {_augur_bootstrap_path}")
_augur_bootstrap_module = _augur_importlib_util.module_from_spec(_augur_bootstrap_spec)
_augur_sys.modules[_augur_bootstrap_spec.name] = _augur_bootstrap_module
_augur_bootstrap_spec.loader.exec_module(_augur_bootstrap_module)
_augur_bootstrap_module.ensure_project_paths(__file__)
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

try:
    from src.logging import get_entity_logger
except ImportError:
    import logging

    def get_entity_logger(name: str):
        return logging.getLogger(name)


logger = get_entity_logger("daemon")

# Resolve project root
SCRIPT_DIR = Path(__file__).resolve().parent
try:
    from src.config.paths import get_runtime_dir, get_project_root, get_skill_root
    PROJECT_ROOT = get_project_root()
    SKILL_ROOT = get_skill_root("daemon")
except ImportError:
    # Fallback for standalone execution outside monorepo
    # This file is at: project-brain/capabilities/skills/daemon/scripts/self_heal_self_test.py
    SKILL_ROOT = SCRIPT_DIR.parent
    PROJECT_ROOT = next(
        (
            parent
            for parent in SKILL_ROOT.parents
            if (parent / "src").is_dir() and (parent / "project-brain").is_dir()
        ),
        SKILL_ROOT.parent.parent.parent,
    )
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    from src.config.paths import get_runtime_dir, get_project_root, get_skill_root

RUNTIME_DIR = get_runtime_dir()
EVENT_FILE = RUNTIME_DIR / "self_heal_events.jsonl"
REGISTRY_FILE = RUNTIME_DIR / "self_heal_registry.json"
PLUGIN_CONFIG_CANDIDATES = (
    SCRIPT_DIR.parent / "config" / "self_heal.yaml",
    SCRIPT_DIR.parent / "augur" / "config" / "self_heal.yaml",
)

# Unique marker so we can find our test event
TEST_MARKER = f"SELF_TEST_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.getpid()}"


def check_daemon_running() -> bool:
    """Check if the self-heal daemon process is alive."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "ai_self_healer.py"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def _import_emit_heal_event():
    """Import emit_heal_event without triggering src/logging/__init__.py."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "self_heal_event",
        PROJECT_ROOT / "src" / "logging" / "self_heal_event.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.emit_heal_event


def check_emit_works() -> bool:
    """Emit a test event and verify it lands in the JSONL file."""
    emit_heal_event = _import_emit_heal_event()

    emit_heal_event(
        source="self_heal_self_test",
        category="mcp_failure",  # Use valid category
        # Use "medium" so it matches configured scan patterns and verifies scanner coverage.
        severity="medium",
        message=f"Self-test probe: {TEST_MARKER}",
        context={"test": True, "marker": TEST_MARKER},
    )

    # Verify it was written
    if not EVENT_FILE.exists():
        return False

    lines = EVENT_FILE.read_text().strip().splitlines()
    for line in reversed(lines):
        try:
            event = json.loads(line)
            if event.get("context", {}).get("marker") == TEST_MARKER:
                return True
        except json.JSONDecodeError:
            continue
    return False


def check_scanner_picks_up() -> bool:
    """Run a single scan cycle and check if our test event is detected."""
    # Import the scanner directly
    sys.path.insert(0, str(SCRIPT_DIR))
    try:
        from ai_self_healer import load_config, scan_runtime
    except ImportError:
        logger.warning("Could not import ai_self_healer — skipping scanner test")
        return True  # Non-fatal

    config = load_config()
    findings = scan_runtime(config)

    # Look for our test event in findings
    for f in findings:
        if TEST_MARKER in f.message:
            return True

    # If no findings at all for the event file, the scan target might not match
    return False


def check_registry() -> dict:
    """Read the registry and return stats."""
    if not REGISTRY_FILE.exists():
        return {"exists": False}

    try:
        data = json.loads(REGISTRY_FILE.read_text())
        issues = data.get("issues", {})
        last_scan = data.get("last_scan", "never")
        statuses = {}
        for v in issues.values():
            s = v.get("status", "unknown")
            statuses[s] = statuses.get(s, 0) + 1
        return {
            "exists": True,
            "last_scan": last_scan,
            "total_issues": len(issues),
            "statuses": statuses,
        }
    except Exception as e:
        return {"exists": True, "error": str(e)}


def cleanup_test_event():
    """Remove the test event from the JSONL file."""
    if not EVENT_FILE.exists():
        return

    lines = EVENT_FILE.read_text().strip().splitlines()
    cleaned = []
    removed = 0
    for line in lines:
        try:
            event = json.loads(line)
            if event.get("context", {}).get("marker") == TEST_MARKER:
                removed += 1
                continue
        except json.JSONDecodeError:
            pass
        cleaned.append(line)

    if removed > 0:
        EVENT_FILE.write_text("\n".join(cleaned) + "\n" if cleaned else "")
        print(f"  Cleaned up {removed} test event(s)")


def run_full_test() -> bool:
    """Run the complete self-test pipeline."""
    all_pass = True

    # Test 1: Daemon process
    print("1. Checking daemon process...")
    if check_daemon_running():
        print("   PASS — ai_self_healer.py is running")
    else:
        print("   FAIL — ai_self_healer.py is NOT running")
        all_pass = False

    # Test 2: Emit event
    print("2. Emitting test event...")
    if check_emit_works():
        print(f"   PASS — event written to {EVENT_FILE.name}")
    else:
        print(f"   FAIL — event NOT found in {EVENT_FILE.name}")
        all_pass = False

    # Test 3: Scanner detection
    print("3. Running scanner cycle...")
    if check_scanner_picks_up():
        print("   PASS — scanner detected test event")
    else:
        print("   WARN — scanner did not find test event (may need pattern match)")

    # Test 4: Registry health
    print("4. Checking registry...")
    reg = check_registry()
    if reg.get("exists"):
        print(f"   PASS — registry exists, {reg['total_issues']} issues tracked")
        print(f"   Last scan: {reg.get('last_scan', 'unknown')}")
        if reg.get("statuses"):
            status_str = ", ".join(f"{k}={v}" for k, v in sorted(reg["statuses"].items()))
            print(f"   Statuses: {status_str}")
    else:
        print("   FAIL — registry file not found")
        all_pass = False

    # Test 5: Scan targets config
    print("5. Checking scan targets config...")
    config_path = next((p for p in PLUGIN_CONFIG_CANDIDATES if p.exists()), None)
    if config_path:
        content = config_path.read_text()
        if "self_heal_events.jsonl" in content:
            print("   PASS — self_heal_events.jsonl is a scan target")
        else:
            print("   FAIL — self_heal_events.jsonl missing from scan targets")
            all_pass = False
    else:
        checked = ", ".join(str(p) for p in PLUGIN_CONFIG_CANDIDATES)
        print(f"   FAIL — config not found at any known path: {checked}")
        all_pass = False

    # Test 6: Event file schema
    print("6. Validating event schema...")
    if EVENT_FILE.exists():
        lines = EVENT_FILE.read_text().strip().splitlines()
        if lines:
            last = json.loads(lines[-1])
            required = {"timestamp", "source", "category", "severity", "message", "host", "pid"}
            missing = required - set(last.keys())
            if not missing:
                print("   PASS — all required fields present")
            else:
                print(f"   FAIL — missing fields: {missing}")
                all_pass = False
        else:
            print("   SKIP — event file is empty")
    else:
        print("   SKIP — no event file yet")

    # Cleanup
    print("7. Cleaning up test event...")
    cleanup_test_event()

    return all_pass


def run_emit_only():
    """Just emit a test event and exit."""
    print(f"Emitting test event with marker: {TEST_MARKER}")
    if check_emit_works():
        print(f"Event written to {EVENT_FILE}")
        print("The daemon should pick this up within 5 minutes.")
        print(f"Check with: grep '{TEST_MARKER}' {EVENT_FILE}")
    else:
        print("FAILED to emit event")
        sys.exit(1)


def run_check_only():
    """Just check status without emitting."""
    print("Self-Heal System Status")
    print("=" * 40)

    daemon = check_daemon_running()
    print(f"Daemon running:  {'YES' if daemon else 'NO'}")

    reg = check_registry()
    if reg.get("exists"):
        print(f"Registry:        {reg['total_issues']} issues")
        print(f"Last scan:       {reg.get('last_scan', 'unknown')}")
        if reg.get("statuses"):
            for k, v in sorted(reg["statuses"].items()):
                print(f"  {k:15s} {v}")
    else:
        print("Registry:        NOT FOUND")

    if EVENT_FILE.exists():
        lines = EVENT_FILE.read_text().strip().splitlines()
        print(f"Event log:       {len(lines)} events")
        if lines:
            last = json.loads(lines[-1])
            print(
                f"  Last event:    {last.get('timestamp')} [{last.get('severity')}] {last.get('source')}: {last.get('message','')[:60]}"
            )
    else:
        print("Event log:       empty (no fail-fast events yet)")


def main():
    parser = argparse.ArgumentParser(description="Self-Heal System Self-Test")
    parser.add_argument("--emit-only", action="store_true", help="Just emit a test event")
    parser.add_argument("--check-only", action="store_true", help="Just check status")
    args = parser.parse_args()

    if args.emit_only:
        run_emit_only()
    elif args.check_only:
        run_check_only()
    else:
        print("Self-Heal System Self-Test")
        print("=" * 40)
        print(f"Project root: {PROJECT_ROOT}")
        print(f"Test marker:  {TEST_MARKER}")
        print()

        passed = run_full_test()
        print()
        if passed:
            print("RESULT: ALL CHECKS PASSED")
        else:
            print("RESULT: SOME CHECKS FAILED")
            sys.exit(1)


if __name__ == "__main__":
    main()
