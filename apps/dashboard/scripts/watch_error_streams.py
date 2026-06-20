#!/usr/bin/env python3
"""Actively watch dashboard-related error streams during dev sessions.

This is intended for interactive `/dev-build --watch` usage. It tails the
main server, MCP, lifecycle, and self-heal event logs from EOF and prints only
actionable new events with clear prefixes.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config.paths import get_logs_dir, get_runtime_dir, get_state_dir

TEXT_ALERT_PATTERNS = (
    " error ",
    "error:",
    "warning",
    "timeout",
    "timed out",
    "typeerror",
    "referenceerror",
    "syntaxerror",
    "unhandled",
    "panic",
    "turbopack",
    "unable to acquire lock",
    "port 3000 is in use",
    "port 3001 is in use",
    "failed",
    "exception",
)

LIFECYCLE_ACTIONS = {
    "gate_denied",
    "crash_detected",
    "crash_loop",
    "recovery_failed",
    "gate_bypassed",
}

SELF_HEAL_SEVERITIES = {"critical", "high", "medium"}
DEDUP_WINDOW_SECONDS = 15.0


@dataclass
class WatchedStream:
    label: str
    path: Path
    kind: str
    offset: int = 0
    inode: int | None = None
    initialized: bool = False


def build_streams() -> list[WatchedStream]:
    logs_dir = get_logs_dir()
    runtime_dir = get_runtime_dir()
    state_dir = get_state_dir()
    candidates = [
        WatchedStream("dashboard.stderr", logs_dir / "dashboard.stderr.log", "text"),
        WatchedStream("augur_mcp", logs_dir / "augur_mcp.log", "text"),
        WatchedStream("lifecycle", logs_dir / "dashboard_lifecycle.jsonl", "lifecycle"),
        WatchedStream("client-error", runtime_dir / "self_heal_events.jsonl", "self_heal"),
        WatchedStream("client-error", state_dir / "self_heal_events.jsonl", "self_heal"),
    ]
    streams: list[WatchedStream] = []
    seen_paths: set[Path] = set()
    for stream in candidates:
        if stream.path in seen_paths:
            continue
        seen_paths.add(stream.path)
        streams.append(stream)
    return streams


def should_emit_text_line(line: str) -> bool:
    normalized = f" {line.strip().lower()} "
    return any(pattern in normalized for pattern in TEXT_ALERT_PATTERNS)


def format_text_line(label: str, line: str) -> str | None:
    stripped = line.strip()
    if not stripped or not should_emit_text_line(stripped):
        return None
    return f"[{label}] {stripped}"


def parse_json_line(line: str) -> dict | None:
    try:
        parsed = json.loads(line)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def should_emit_lifecycle_event(event: dict) -> bool:
    target_instance = os.environ.get("AUGUR_INSTANCE_ID") or os.environ.get(
        "NEXT_PUBLIC_AUGUR_INSTANCE_ID"
    )
    event_instance = str(event.get("instance_id", "")).strip()
    if target_instance and event_instance and event_instance != target_instance:
        return False
    action = str(event.get("action", "")).strip()
    reason = str(event.get("reason", "")).lower()
    return action in LIFECYCLE_ACTIONS or "runtime degraded" in reason


def format_lifecycle_event(event: dict) -> str | None:
    if not should_emit_lifecycle_event(event):
        return None
    actor = event.get("actor", "unknown")
    action = event.get("action", "unknown")
    reason = event.get("reason", "")
    prev_state = event.get("prev_state")
    new_state = event.get("new_state")
    state_bits = []
    if prev_state:
        state_bits.append(str(prev_state))
    if new_state:
        state_bits.append(str(new_state))
    state_suffix = f" ({' -> '.join(state_bits)})" if state_bits else ""
    return f"[lifecycle] {actor} {action}{state_suffix}: {reason}"


def should_emit_self_heal_event(event: dict) -> bool:
    severity = str(event.get("severity", "")).lower()
    category = str(event.get("category", "")).lower()
    return severity in SELF_HEAL_SEVERITIES or category == "client-error"


def format_self_heal_event(event: dict) -> str | None:
    if not should_emit_self_heal_event(event):
        return None
    severity = str(event.get("severity", "unknown")).upper()
    source = event.get("source", "unknown")
    category = event.get("category", "unknown")
    message = event.get("message", "")
    context = event.get("context", {})
    details: list[str] = []
    if isinstance(context, dict):
        fingerprint = context.get("fingerprint")
        if fingerprint:
            details.append(f"fingerprint={fingerprint}")
        url = context.get("url")
        if url:
            details.append(f"url={url}")
    suffix = f" [{' '.join(details)}]" if details else ""
    return f"[client-error] {severity} {source}/{category}: {message}{suffix}"


def format_stream_event(stream: WatchedStream, line: str) -> str | None:
    if stream.kind == "text":
        return format_text_line(stream.label, line)
    event = parse_json_line(line)
    if event is None:
        return None
    if stream.kind == "lifecycle":
        return format_lifecycle_event(event)
    if stream.kind == "self_heal":
        return format_self_heal_event(event)
    return None


def iter_new_lines(stream: WatchedStream, start_at_end: bool) -> list[str]:
    if not stream.path.exists():
        return []

    stat = stream.path.stat()
    if not stream.initialized:
        stream.inode = stat.st_ino
        stream.offset = stat.st_size if start_at_end else 0
        stream.initialized = True
        return []

    if stream.inode != stat.st_ino or stat.st_size < stream.offset:
        stream.inode = stat.st_ino
        stream.offset = 0

    if stat.st_size == stream.offset:
        return []

    with stream.path.open("r", encoding="utf-8", errors="replace") as handle:
        handle.seek(stream.offset)
        lines = handle.readlines()
        stream.offset = handle.tell()
    return lines


def dedupe_key(message: str) -> str:
    return message.strip()


def print_message(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def watch_forever(
    *,
    poll_interval: float,
    start_at_end: bool,
    dedupe_window_seconds: float,
) -> None:
    streams = build_streams()
    last_seen: dict[str, float] = {}

    while True:
        now = time.monotonic()
        stale = [key for key, ts in last_seen.items() if now - ts > dedupe_window_seconds]
        for key in stale:
            last_seen.pop(key, None)

        for stream in streams:
            for line in iter_new_lines(stream, start_at_end):
                message = format_stream_event(stream, line)
                if not message:
                    continue
                key = dedupe_key(message)
                previous = last_seen.get(key)
                if previous is not None and now - previous <= dedupe_window_seconds:
                    continue
                last_seen[key] = now
                print_message(message)

        time.sleep(poll_interval)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--poll-interval", type=float, default=0.5)
    parser.add_argument("--dedupe-window-seconds", type=float, default=DEDUP_WINDOW_SECONDS)
    parser.add_argument(
        "--from-start",
        action="store_true",
        help="Read existing file content instead of tailing from EOF.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        watch_forever(
            poll_interval=args.poll_interval,
            start_at_end=not args.from_start,
            dedupe_window_seconds=args.dedupe_window_seconds,
        )
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
