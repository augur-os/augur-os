#!/usr/bin/env python3
"""
Runtime Error/Warning Scanner.

Scans state/log roots for errors and warnings, translates them into
TODO_ markers for systematic resolution via workflows.

Output: state/tech_debt.md

Mode-aware behavior:
- Production: Scan and log silently
- Dev: Scan and notify for each new error type

Usage:
    python3 runtime_marker_scanner.py              # Run once
    python3 runtime_marker_scanner.py --loop       # Continuous scanning (for daemon)
    python3 runtime_marker_scanner.py --summary    # Show summary only
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


# Setup project root
from bootstrap_paths import ensure_project_paths  # noqa: E402

PROJECT_ROOT = ensure_project_paths(__file__)

try:
    from src.logging import get_entity_logger
except ImportError:
    import importlib

    def get_entity_logger(name: str):
        logging = importlib.import_module("logging")
        logger = logging.getLogger(name)
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger


from src.config.paths import get_logs_dir, get_runtime_dir

# Local imports
try:
    from daemon_mode import get_daemon_mode, is_production_mode
except ImportError:

    def get_daemon_mode():
        return os.environ.get("AUGUR_MODE", "production")

    def is_production_mode():
        return get_daemon_mode() == "production"


try:
    from notification_service import notify
except ImportError:

    def notify(message: str, channel: str = "system"):
        _out(f"[NOTIFY] {message}")


logger = get_entity_logger("runtime_marker_scanner")

# Configuration
SCAN_INTERVAL_SECONDS = 300  # 5 minutes
MAX_ERRORS_PER_FILE = 50  # Limit errors to scan per log file
ARCHIVED_LOG_TOKENS = (
    ".pre-",
    ".old",
    ".bak",
    ".archive",
    ".rotated",
)


# ═══════════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class RuntimeError:
    """Represents an error found in state/log roots."""

    dedup_key: str
    severity: str  # "error", "warning"
    category: str  # "integration", "ux", "performance", "data"
    message: str
    file: str
    line: Optional[int] = None
    count: int = 1
    first_seen: str = ""
    last_seen: str = ""
    stack_trace: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    def to_marker(self) -> str:
        """Convert to TODO_BUG marker format."""
        if self.severity == "error":
            return f"# TODO_BUG({self.category}/medium): {self.message} (seen {self.count}x, last: {self.last_seen})"
        else:
            return f"# TODO_IMPROVE({self.category}): {self.message} (seen {self.count}x)"


# ═══════════════════════════════════════════════════════════════════════════════
# ERROR PATTERNS
# ═══════════════════════════════════════════════════════════════════════════════

ERROR_PATTERNS = [
    # JavaScript/TypeScript errors
    (r"(?:Error|TypeError|ReferenceError|SyntaxError):\s*(.+)", "error", "integration"),
    (r"Unhandled\s+(?:Promise\s+)?(?:Rejection|Exception):\s*(.+)", "error", "integration"),
    (r"(?:FATAL|CRITICAL):\s*(.+)", "error", "integration"),
    # React/Next.js errors
    (r"Hydration\s+failed\s+(.+)", "error", "ux"),
    (r"(?:Server|Client)\s+Error:\s*(.+)", "error", "ux"),
    (r"Warning:\s*(.+)", "warning", "ux"),
    # Python errors
    (r"(?:Exception|Error):\s*(.+)", "error", "integration"),
    (r"Traceback\s+\(most\s+recent\s+call\s+last\)", "error", "integration"),
    # Performance warnings
    (r"(?:timeout|timed\s+out).*?(\d+\s*(?:ms|s|seconds))", "warning", "performance"),
    (r"(?:slow|took)\s+(\d+\s*(?:ms|s|seconds))", "warning", "performance"),
    (r"memory\s+(?:warning|exceeded)", "warning", "performance"),
    # Data errors
    (r"(?:JSON|YAML|parse)\s+error:\s*(.+)", "error", "data"),
    (r"(?:validation|schema)\s+(?:error|failed):\s*(.+)", "error", "data"),
    # Generic patterns (lower priority)
    (r"\bERROR\b[:\s]+(.+)", "error", "integration"),
    (r"\bWARN(?:ING)?\b[:\s]+(.+)", "warning", "integration"),
]


def generate_dedup_key(message: str, file: str, category: str) -> str:
    """Generate a unique key for deduplicating errors."""
    # Normalize message (remove numbers, paths, timestamps)
    normalized = re.sub(r'\d+', 'N', message)
    normalized = re.sub(r'/[^\s]+', '/PATH', normalized)
    normalized = re.sub(r'\b\d{4}-\d{2}-\d{2}\b', 'DATE', normalized)

    key_string = f"{category}|{file}|{normalized[:100]}"
    return hashlib.sha256(key_string.encode()).hexdigest()[:12]


# ═══════════════════════════════════════════════════════════════════════════════
# LOG SCANNING
# ═══════════════════════════════════════════════════════════════════════════════

def _is_active_log_file(log_file: Path) -> bool:
    """Return True when a log file represents the current live stream."""
    name = log_file.name
    if not name.endswith(".log"):
        return False
    if any(token in name for token in ARCHIVED_LOG_TOKENS):
        return False
    return True


def get_log_files() -> list[Path]:
    """Get all live log files to scan."""
    logs_dir = get_logs_dir()
    if not logs_dir.exists():
        return []

    files = {
        log_file
        for pattern in ("*.log", "*.stderr.log")
        for log_file in logs_dir.glob(pattern)
        if _is_active_log_file(log_file)
    }

    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)


def collect_log_positions() -> dict[str, int]:
    """Capture current byte offsets for all tracked log files."""
    positions: dict[str, int] = {}
    for log_file in get_log_files():
        try:
            positions[str(log_file)] = log_file.stat().st_size
        except OSError:
            continue
    return positions


def _get_start_offset(log_file: Path, previous_positions: dict[str, int] | None) -> int:
    """Resolve the safe start offset for incremental log scanning."""
    if not previous_positions:
        return 0
    previous = int(previous_positions.get(str(log_file), 0) or 0)
    try:
        current_size = log_file.stat().st_size
    except OSError:
        return 0
    if previous < 0 or previous > current_size:
        return 0
    return previous


def scan_log_file(
    log_file: Path,
    max_errors: int = MAX_ERRORS_PER_FILE,
    start_offset: int = 0,
) -> list[RuntimeError]:
    """
    Scan a single log file for errors and warnings.

    Args:
        log_file: Path to log file
        max_errors: Maximum errors to return per file

    Returns:
        List of RuntimeError objects
    """
    errors = []

    try:
        with log_file.open("rb") as handle:
            handle.seek(max(start_offset, 0))
            content = handle.read().decode(errors="replace")
    except Exception as e:
        logger.warning(f"Failed to read {log_file}: {e}")
        return errors

    lines = content.splitlines()
    file_name = log_file.name
    now = datetime.now().isoformat()

    for line_num, line in enumerate(lines[-1000:], 1):  # Only scan last 1000 lines
        for pattern, severity, category in ERROR_PATTERNS:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                message = match.group(1) if match.lastindex else match.group(0)
                message = message.strip()[:200]  # Truncate

                if not message:
                    continue

                dedup_key = generate_dedup_key(message, file_name, category)

                errors.append(
                    RuntimeError(
                        dedup_key=dedup_key,
                        severity=severity,
                        category=category,
                        message=message,
                        file=file_name,
                        line=line_num,
                        first_seen=now,
                        last_seen=now,
                    )
                )

                if len(errors) >= max_errors:
                    return errors

                break  # Only match first pattern per line

    return errors


def scan_all_logs(previous_positions: dict[str, int] | None = None) -> dict[str, RuntimeError]:
    """
    Scan all log files and deduplicate errors.

    Returns:
        Dict of dedup_key -> RuntimeError
    """
    errors: dict[str, RuntimeError] = {}

    for log_file in get_log_files():
        start_offset = _get_start_offset(log_file, previous_positions)
        file_errors = scan_log_file(log_file, start_offset=start_offset)

        for error in file_errors:
            if error.dedup_key in errors:
                # Update existing
                existing = errors[error.dedup_key]
                existing.count += 1
                existing.last_seen = error.last_seen
            else:
                errors[error.dedup_key] = error

    return errors


# ═══════════════════════════════════════════════════════════════════════════════
# TECH DEBT OUTPUT
# ═══════════════════════════════════════════════════════════════════════════════


def get_tech_debt_file() -> Path:
    """Get the tech debt output file path."""
    return get_runtime_dir() / "tech_debt.md"


def get_state_file() -> Path:
    """Get the scan-state file path."""
    return get_runtime_dir() / "marker_scanner_state.json"


def load_scan_state() -> dict:
    """Load the previous scan state."""
    state_file = get_state_file()
    if not state_file.exists():
        return {}
    try:
        return json.loads(state_file.read_text())
    except Exception as e:
        logger.warning(f"Failed to parse scan state: {e}")
        return {}


def load_existing_markers() -> dict[str, RuntimeError]:
    """Load existing markers from tech_debt.md."""
    tech_debt_file = get_tech_debt_file()
    if not tech_debt_file.exists():
        return {}

    markers = {}

    try:
        content = tech_debt_file.read_text()

        # Parse markers
        # Format: <!-- key:HASH count:N -->
        for match in re.finditer(r'<!-- key:(\w+) count:(\d+) -->', content):
            key = match.group(1)
            count = int(match.group(2))
            markers[key] = RuntimeError(
                dedup_key=key,
                severity="unknown",
                category="unknown",
                message="",
                file="",
                count=count,
            )

    except Exception as e:
        logger.warning(f"Failed to parse existing markers: {e}")

    return markers


def compute_error_fingerprint(errors: dict[str, RuntimeError]) -> str:
    """Hash the current deduplicated issue set."""
    payload = {
        "mode": get_daemon_mode(),
        "keys": sorted(errors.keys()),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _render_tech_debt(errors: dict[str, RuntimeError], new_count: int) -> str:
    """Render the tech-debt markdown content."""
    if not errors:
        return f"""# Runtime Technical Debt
Auto-generated by daemon runtime_marker_scanner. Review with `/auto-tidy`.

Last updated: {datetime.now().strftime("%Y-%m-%d %H:%M")}
Mode: {get_daemon_mode()}
Total issues: 0 (0 new)

No current runtime markers detected.
"""

    # Separate by severity
    error_list = []
    warning_list = []

    for error in errors.values():
        if error.severity == "error":
            error_list.append(error)
        else:
            warning_list.append(error)

    # Sort by count (most frequent first)
    error_list.sort(key=lambda e: -e.count)
    warning_list.sort(key=lambda e: -e.count)

    content = f"""# Runtime Technical Debt
Auto-generated by daemon runtime_marker_scanner. Review with `/auto-tidy`.

Last updated: {datetime.now().strftime("%Y-%m-%d %H:%M")}
Mode: {get_daemon_mode()}
Total issues: {len(errors)} ({new_count} new)

## Errors (fix urgently)

"""
    for error in error_list[:50]:
        content += f"{error.to_marker()}\n"
        content += f"<!-- key:{error.dedup_key} count:{error.count} -->\n"
        content += f"<!-- file:{error.file} -->\n\n"

    content += """
## Warnings (address in maintenance)

"""
    for error in warning_list[:50]:
        content += f"{error.to_marker()}\n"
        content += f"<!-- key:{error.dedup_key} count:{error.count} -->\n"
        content += f"<!-- file:{error.file} -->\n\n"

    return content


def write_tech_debt(errors: dict[str, RuntimeError], previous_keys: set[str] | None = None) -> tuple[int, bool]:
    """
    Write errors as TODO_ markers to tech_debt.md.

    Returns:
        (new issue count, whether file content changed)
    """
    tech_debt_file = get_tech_debt_file()
    tech_debt_file.parent.mkdir(parents=True, exist_ok=True)

    previous = previous_keys if previous_keys is not None else set(load_existing_markers().keys())
    new_count = len(set(errors.keys()) - previous)
    content = _render_tech_debt(errors, new_count)
    existing_content = tech_debt_file.read_text() if tech_debt_file.exists() else None
    if existing_content == content:
        logger.info(f"Runtime marker report unchanged at {tech_debt_file}")
        return new_count, False

    tech_debt_file.write_text(content)
    logger.info(f"Written {len(errors)} markers to {tech_debt_file} ({new_count} new)")

    return new_count, True


def write_scan_state(errors: dict[str, RuntimeError], log_positions: dict[str, int]) -> None:
    """Write scan state for tracking."""
    state_file = get_state_file()
    state_file.parent.mkdir(parents=True, exist_ok=True)

    state = {
        "last_scan": datetime.now().isoformat(),
        "total_errors": len([e for e in errors.values() if e.severity == "error"]),
        "total_warnings": len([e for e in errors.values() if e.severity == "warning"]),
        "mode": get_daemon_mode(),
        "fingerprint": compute_error_fingerprint(errors),
        "issue_keys": sorted(errors.keys()),
        "log_positions": log_positions,
    }

    state_file.write_text(json.dumps(state, indent=2))


# ═══════════════════════════════════════════════════════════════════════════════
# MONITORING LOGIC
# ═══════════════════════════════════════════════════════════════════════════════


def scan_and_update() -> dict:
    """
    Scan logs and update tech_debt.md.

    Returns:
        Summary dict
    """
    previous_state = load_scan_state()
    previous_positions = previous_state.get("log_positions", {}) if isinstance(previous_state, dict) else {}
    errors = scan_all_logs(previous_positions)
    previous_keys = set(previous_state.get("issue_keys", []))
    current_fingerprint = compute_error_fingerprint(errors)
    previous_fingerprint = previous_state.get("fingerprint")
    current_positions = collect_log_positions()

    summary = {
        "total_errors": len([e for e in errors.values() if e.severity == "error"]),
        "total_warnings": len([e for e in errors.values() if e.severity == "warning"]),
        "mode": get_daemon_mode(),
        "timestamp": datetime.now().isoformat(),
        "fingerprint": current_fingerprint,
    }

    if previous_fingerprint != current_fingerprint or not get_tech_debt_file().exists():
        new_count, report_updated = write_tech_debt(errors, previous_keys)
        summary["new_issues"] = new_count
        summary["changed"] = report_updated

        if errors and not is_production_mode() and new_count > 0:
            notify(
                f"Found {new_count} new state/log issues. Check state/tech_debt.md",
                channel="system",
            )
    else:
        summary["new_issues"] = 0
        summary["changed"] = False

    write_scan_state(errors, current_positions)

    return summary


def monitor_loop(interval: int = SCAN_INTERVAL_SECONDS) -> None:
    """Continuous scanning loop."""
    logger.info(f"Starting runtime marker scanner (interval: {interval}s, mode: {get_daemon_mode()})")

    while True:
        try:
            summary = scan_and_update()
            logger.debug(f"Scan complete: {summary['total_errors']} errors, " f"{summary['total_warnings']} warnings")
        except Exception as e:
            logger.error(f"Scan loop error: {e}")

        import time

        time.sleep(interval)


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Runtime Error/Warning Scanner")
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Run continuous scanning loop",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=SCAN_INTERVAL_SECONDS,
        help=f"Scan interval in seconds (default: {SCAN_INTERVAL_SECONDS})",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Show summary only, don't update tech_debt.md",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )
    args = parser.parse_args()

    if args.loop:
        monitor_loop(args.interval)
        return 0

    if args.summary:
        errors = scan_all_logs()
        summary = {
            "total_errors": len([e for e in errors.values() if e.severity == "error"]),
            "total_warnings": len([e for e in errors.values() if e.severity == "warning"]),
            "unique_issues": len(errors),
            "log_files_scanned": len(get_log_files()),
            "mode": get_daemon_mode(),
        }

        if args.json:
            _out(json.dumps(summary, indent=2))
        else:
            _out("Runtime Marker Scanner Summary")
            _out("=" * 40)
            for key, value in summary.items():
                _out(f"{key}: {value}")

        return 0

    summary = scan_and_update()

    if args.json:
        _out(json.dumps(summary, indent=2))
    else:
        _out("Runtime Marker Scanner")
        _out("=" * 40)
        _out(f"Mode: {summary['mode']}")
        _out(f"Errors found: {summary['total_errors']}")
        _out(f"Warnings found: {summary['total_warnings']}")
        _out(f"New issues: {summary.get('new_issues', 0)}")
        _out(f"\nOutput: {get_tech_debt_file()}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
