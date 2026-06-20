"""
Log scanner and resource health monitoring for AI Self-Healer.

Handles:
- Incremental log scanning with byte-offset watermarks (ADR-185)
- Dedup key generation and message normalization
- Adaptive target discovery (untracked log files)
- Resource health checks (CPU, memory, cache size)
"""

from __future__ import annotations

import glob as globmod
import hashlib
import json
import os
import re
import subprocess  # nosec B404
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ai_self_healer import ErrorFinding

from self_heal.patterns import MAX_NEW_LINES_PER_FILE, MAX_MESSAGE_LENGTH, WATERMARK_FILENAME


def _get_paths():
    """Lazy import of path constants to avoid circular imports."""
    import ai_self_healer as _healer
    return _healer.RUNTIME_DIR, _healer.LOGS_DIR, _healer.PROJECT_ROOT


def _get_watermark_file() -> Path:
    """Resolve the active watermark file, honoring module-level overrides."""
    import ai_self_healer as _healer

    configured = getattr(_healer, "_WATERMARK_FILE", None)
    if configured:
        return Path(configured)

    runtime_dir, _, _ = _get_paths()
    return runtime_dir / WATERMARK_FILENAME


def _get_logger():
    import ai_self_healer as _healer
    return _healer.logger


# ═══════════════════════════════════════════════════════════════════════════════
# PATH HELPERS
# ═══════════════════════════════════════════════════════════════════════════════


def _resolve_scan_target_path(target_path: str) -> str:
    """Resolve a configured scan target to an absolute glob/path.

    ADR-270 scan targets use `state/...` and `logs/...` labels that map to the
    split runtime state/log roots.
    """
    RUNTIME_DIR, LOGS_DIR, PROJECT_ROOT = _get_paths()
    raw = str(target_path or "").strip()
    if not raw:
        return ""

    normalized = raw.replace("\\", "/")
    if os.path.isabs(raw):
        return raw

    if normalized == "logs" or normalized.startswith("logs/"):
        suffix = normalized[len("logs"):].lstrip("/")
        return str(LOGS_DIR / suffix) if suffix else str(LOGS_DIR)

    if normalized == "state" or normalized.startswith("state/"):
        suffix = normalized[len("state"):].lstrip("/")
        return str(RUNTIME_DIR / suffix) if suffix else str(RUNTIME_DIR)

    return str(PROJECT_ROOT / raw)


def _to_state_label(path_value: str | Path) -> str:
    """Convert an absolute state/log path back to a stable config label."""
    RUNTIME_DIR, LOGS_DIR, PROJECT_ROOT = _get_paths()
    raw = str(path_value or "").strip()
    if not raw:
        return ""

    normalized = raw.replace("\\", "/")
    if not os.path.isabs(raw):
        return normalized

    path_obj = Path(raw)
    try:
        path_obj = path_obj.resolve(strict=False)
    except Exception:
        path_obj = Path(raw)

    for root, label in ((LOGS_DIR, "logs"), (RUNTIME_DIR, "state"), (PROJECT_ROOT, "")):
        try:
            rel = path_obj.relative_to(root.resolve())
            rel_text = rel.as_posix()
            if not label:
                return rel_text or "."
            return f"{label}/{rel_text}" if rel_text else label
        except Exception:
            continue

    return path_obj.as_posix()


# ═══════════════════════════════════════════════════════════════════════════════
# WATERMARKS
# ═══════════════════════════════════════════════════════════════════════════════


def _load_watermarks() -> dict[str, int]:
    """Load byte-offset watermarks from disk."""
    wm_file = _get_watermark_file()
    if wm_file.exists():
        try:
            return json.loads(wm_file.read_text())
        except Exception:
            return {}
    return {}


def _save_watermarks_atomic(wm: dict[str, int]) -> None:
    """Atomic watermark persistence via temp file + rename (ADR-185).

    Uses write-to-temp + rename to prevent corrupt JSON on crash.
    Prunes entries for log files that no longer exist.
    """
    # Prune watermarks for files that no longer exist
    wm = {path: offset for path, offset in wm.items() if os.path.exists(path)}
    wm_file = _get_watermark_file()
    wm_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = wm_file.with_suffix(".tmp")
    tmp.write_text(json.dumps(wm, indent=2))
    tmp.rename(wm_file)  # atomic on POSIX


def _read_new_lines(fpath: str, watermarks: dict[str, int]) -> tuple[list[str], int]:
    """Read only lines added since last scan. Returns (lines, new_offset).

    If the file shrank (log rotation), resets watermark and reads from start.
    """
    try:
        size = os.path.getsize(fpath)
    except OSError:
        return [], 0

    prev_offset = watermarks.get(fpath, 0)

    # File rotated or truncated — reset
    if size < prev_offset:
        prev_offset = 0

    if size == prev_offset:
        return [], size  # No new data

    try:
        with open(fpath, "r", errors="replace") as f:
            f.seek(prev_offset)
            new_content = f.read()
        return new_content.splitlines(), size
    except Exception:
        return [], prev_offset


# ═══════════════════════════════════════════════════════════════════════════════
# MESSAGE EXTRACTION & FILTERING
# ═══════════════════════════════════════════════════════════════════════════════


def _extract_message(raw_line: str) -> str:
    """Extract human-readable message from a log line.

    Structured JSON log lines (from get_entity_logger) contain a "message" field
    buried in JSON. Extract it so notifications and registry entries are readable.
    """
    stripped = raw_line.strip()
    if stripped.startswith("{"):
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, dict) and "message" in parsed:
                entity = parsed.get("entity", "")
                msg = parsed["message"]
                severity = parsed.get("severity", parsed.get("level", ""))
                prefix = f"[{entity}] " if entity else ""
                suffix = f" ({severity})" if severity and severity not in msg else ""
                return f"{prefix}{msg}{suffix}"
        except (json.JSONDecodeError, KeyError):
            pass
    return stripped


_HTTP_ACCESS_LOG_RE = re.compile(
    r"^(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s+/\S+\s+\d{3}\b"
    r"|^\s*(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s+/\S+\s+\d{3}\s+in\s+\d+m?s"
)


_MOCK_CLIENT_PATTERNS = (
    "MagicMock",
    "<Mock ",
    "unittest.mock",
    "mock.MagicMock",
)


def _is_mock_client_line(raw_line: str) -> bool:
    """Check if a log line originates from a mock/test-double client."""
    return any(pat in raw_line for pat in _MOCK_CLIENT_PATTERNS)


def _is_info_level_log(raw_line: str) -> bool:
    """Check if a log line should be skipped by scanners.

    Returns True for:
    - Structured JSON lines at INFO or DEBUG level
    - HTTP access log lines where the URL path may contain 'error' but response is OK
    """
    stripped = raw_line.strip()
    if _HTTP_ACCESS_LOG_RE.match(stripped):
        return True
    if not stripped.startswith("{"):
        return False
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            level = str(parsed.get("level", "")).upper()
            return level in ("INFO", "DEBUG")
    except (json.JSONDecodeError, KeyError):
        pass
    return False


# ═══════════════════════════════════════════════════════════════════════════════
# DEDUP KEY GENERATION
# ═══════════════════════════════════════════════════════════════════════════════


def _generate_dedup_key(message: str, source_file: str) -> str:
    """Generate hash-based dedup key from normalized error + source."""
    normalized_source = _canonical_source_for_dedup(source_file)
    normalized_message = _normalize_message_for_dedup(message)
    key_string = f"{normalized_source}|{normalized_message[:220]}"
    return hashlib.sha256(key_string.encode()).hexdigest()[:12]


def _normalize_message_for_dedup(message: str) -> str:
    """Normalize volatile tokens from log messages for stable dedup."""
    normalized = message
    normalized = re.sub(r"0x[0-9a-fA-F]+", "0xHEX", normalized)
    normalized = re.sub(
        r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b",
        "UUID",
        normalized,
    )
    normalized = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "DATE", normalized)
    normalized = re.sub(r"\d+", "N", normalized)
    normalized = re.sub(r"/[^\s]+", "/PATH", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _canonical_source_for_dedup(source_file: str) -> str:
    """Canonicalize source path so log rotation does not create new issues."""
    source = _to_state_label(source_file)

    if source.startswith("logs/"):
        parts = source.split("/")
        if len(parts) >= 3:
            source = f"logs/{parts[1]}"

    source = re.sub(
        r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b",
        "UUID",
        source,
    )
    source = re.sub(r"0x[0-9a-fA-F]+", "0xHEX", source)
    source = re.sub(r"\d+", "N", source)
    source = re.sub(r"\s+", " ", source).strip()
    return source


# ═══════════════════════════════════════════════════════════════════════════════
# LOG SCANNER
# ═══════════════════════════════════════════════════════════════════════════════


def scan_logs(targets: list[dict]) -> tuple[list, dict[str, int]]:
    """Incremental log scanner with watermark tracking (ADR-185).

    Reads only new lines since last scan (byte-offset watermarks).
    Filters INFO-level logs before pattern matching.
    Caps at MAX_NEW_LINES_PER_FILE per scan cycle.

    Returns (findings, watermarks) — caller is responsible for persisting
    watermarks AFTER findings are safely processed.
    """
    from ai_self_healer import ErrorFinding

    findings: list[ErrorFinding] = []
    now = datetime.now().isoformat()
    watermarks = _load_watermarks()

    for target in targets:
        patterns = target.get("patterns", [])
        if not patterns:
            continue

        combined = re.compile("|".join(re.escape(p) for p in patterns), re.IGNORECASE)
        target_path = target.get("path", "")
        expanded = globmod.glob(_resolve_scan_target_path(target_path), recursive=True)
        if not expanded:
            continue

        for fpath in expanded:
            new_lines, new_offset = _read_new_lines(fpath, watermarks)
            watermarks[fpath] = new_offset

            if not new_lines:
                continue

            for i, line in enumerate(new_lines[-MAX_NEW_LINES_PER_FILE:]):
                if _is_info_level_log(line):
                    continue
                if combined.search(line):
                    message = _extract_message(line)[:MAX_MESSAGE_LENGTH]
                    if not message:
                        continue

                    source = _canonical_source_for_dedup(fpath)
                    key = _generate_dedup_key(message, source)
                    findings.append(
                        ErrorFinding(
                            dedup_key=key,
                            message=message,
                            file=source,
                            line=i,
                            timestamp=now,
                        )
                    )

    return findings, watermarks


def _filter_stale_logs(targets: list[dict], max_age_hours: int) -> list[dict]:
    """Filter scan targets to only include log files modified within max_age_hours."""
    if max_age_hours <= 0:
        return targets

    cutoff = time.time() - (max_age_hours * 3600)
    filtered: list[dict] = []

    for target in targets:
        target_path = target.get("path", "")
        expanded = globmod.glob(_resolve_scan_target_path(target_path), recursive=True)
        fresh_paths = [p for p in expanded if os.path.getmtime(p) >= cutoff]

        if fresh_paths:
            for fpath in fresh_paths:
                filtered.append(
                    {
                        "path": _to_state_label(fpath),
                        "patterns": target.get("patterns", []),
                    }
                )

    return filtered


# Patterns in error messages that indicate self-healer's own output
_SELF_POISON_PATTERNS = re.compile(
    r'"entity":\s*"ai_self_healer"' r"|Pipeline error: transient error" r"|ai_self_healer.*Pipeline error",
    re.IGNORECASE,
)


def _filter_self_poison(findings: list) -> list:
    """Remove findings that are the self-healer's own error output."""
    return [f for f in findings if not _SELF_POISON_PATTERNS.search(f.message)]


def scan_runtime(config: dict) -> list:
    """Scan runtime logs for errors using best available tool."""
    from ai_self_healer import ErrorFinding  # noqa: F811

    targets = list(config.get("scan_targets", []))
    discovered = config.get("discovered_scan_targets", [])
    if discovered:
        targets.extend(discovered)
    if not targets:
        return []

    max_age = config.get("max_log_age_hours", 24)
    if max_age > 0:
        targets = _filter_stale_logs(targets, max_age)
        if not targets:
            return []

    findings, watermarks = scan_logs(targets)

    # Prevent self-poisoning: drop the healer's own error log entries
    findings = _filter_self_poison(findings)

    # Persist watermarks AFTER findings are returned (ADR-185: atomic, post-process)
    _save_watermarks_atomic(watermarks)

    return findings


# ═══════════════════════════════════════════════════════════════════════════════
# ADAPTIVE TARGET DISCOVERY
# ═══════════════════════════════════════════════════════════════════════════════

# Generic error patterns used to probe untracked log files.
_DISCOVERY_PATTERNS = re.compile(
    r"ERROR|FATAL|CRITICAL|Traceback|Exception|panic:"
    r'|"status":\s*"(?:failed|error)"'
    r'|"severity":\s*"(?:critical|high)"',
    re.IGNORECASE,
)

# File extensions worth probing inside state/log roots.
_LOG_EXTENSIONS = {".log", ".err", ".jsonl"}

# Files owned by the self-healer itself — never auto-track.
_DISCOVERY_IGNORE = {
    "self_heal_registry.json",
    "self_heal_watermarks.json",
    "tech_debt.md",
}

# Directories to skip during discovery (self-poisoning risk).
_DISCOVERY_IGNORE_DIRS = {"ai_self_healer"}

# Max file size to probe (skip huge binaries or rotated archives).
_DISCOVERY_MAX_SIZE = 50 * 1024 * 1024  # 50 MB


def _expand_tracked_paths(config: dict) -> set[str]:
    """Expand all scan_target globs to a set of absolute paths already tracked."""
    tracked: set[str] = set()
    for target in config.get("scan_targets", []):
        expanded = globmod.glob(_resolve_scan_target_path(target.get("path", "")), recursive=True)
        tracked.update(os.path.abspath(p) for p in expanded)
    for target in config.get("discovered_scan_targets", []):
        expanded = globmod.glob(_resolve_scan_target_path(target.get("path", "")), recursive=True)
        tracked.update(os.path.abspath(p) for p in expanded)
    return tracked


def _probe_file_for_errors(fpath: str, max_lines: int = 200) -> bool:
    """Quick-check the tail of a file for error patterns. Non-blocking."""
    try:
        with open(fpath, "r", errors="replace") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 65536))
            tail = f.read()
        for line in tail.splitlines()[-max_lines:]:
            stripped = line.strip()
            if _is_info_level_log(stripped):
                continue
            if _is_mock_client_line(stripped):
                continue
            if stripped.startswith("{"):
                try:
                    parsed = json.loads(stripped)
                    if isinstance(parsed, dict):
                        level = str(parsed.get("level", "")).upper()
                        if level in ("INFO", "DEBUG", "WARNING"):
                            continue
                except (json.JSONDecodeError, KeyError):
                    pass
            if _DISCOVERY_PATTERNS.search(line):
                return True
    except Exception:
        pass
    return False


def _infer_patterns_for_file(fpath: str) -> list[str]:
    """Infer appropriate scan patterns based on file extension and content."""
    ext = Path(fpath).suffix
    if ext == ".jsonl":
        return ['"status": "failed"', '"status": "error"', '"severity": "critical"', '"severity": "high"']
    if ext == ".err":
        return ["Traceback", "Error", "Exception", "No such file"]
    return ["ERROR", "FATAL", "CRITICAL", "Traceback", "Exception"]


def discover_untracked_logs(config: dict) -> list[dict]:
    """Scan state/log roots for log files with errors that aren't in any scan_target."""
    RUNTIME_DIR, LOGS_DIR, _ = _get_paths()
    logger = _get_logger()
    tracked = _expand_tracked_paths(config)

    roots_to_scan = [RUNTIME_DIR]
    if LOGS_DIR != RUNTIME_DIR:
        try:
            LOGS_DIR.relative_to(RUNTIME_DIR)
        except ValueError:
            roots_to_scan.append(LOGS_DIR)

    if not any(root.is_dir() for root in roots_to_scan):
        return []

    hits_by_dir: dict[tuple[str, str], list[str]] = {}

    for scan_root in roots_to_scan:
        for root, dirs, files in os.walk(str(scan_root)):
            dirs[:] = [d for d in dirs if d not in _DISCOVERY_IGNORE_DIRS]

            for fname in files:
                if fname in _DISCOVERY_IGNORE:
                    continue
                fpath = os.path.join(root, fname)
                ext = Path(fname).suffix
                if ext not in _LOG_EXTENSIONS and not fname.endswith(".stderr.log"):
                    continue
                try:
                    if os.path.getsize(fpath) > _DISCOVERY_MAX_SIZE:
                        continue
                except OSError:
                    continue
                abs_path = os.path.abspath(fpath)
                if abs_path in tracked:
                    continue
                if not _probe_file_for_errors(fpath):
                    continue

                fpath_p = Path(fpath)
                try:
                    rel = fpath_p.relative_to(LOGS_DIR)
                    parts = rel.parts
                    if len(parts) >= 2:
                        service_dir = str(Path("logs") / parts[0])
                        effective_ext = ".stderr.log" if fname.endswith(".stderr.log") else ext
                        hits_by_dir.setdefault((service_dir, effective_ext), []).append(fpath)
                        continue
                except ValueError:
                    pass
                rel_path = _to_state_label(fpath)
                hits_by_dir.setdefault((rel_path, ""), []).append(fpath)

    new_targets: list[dict] = []
    now = datetime.now().isoformat()

    for (dir_key, ext), file_list in hits_by_dir.items():
        if ext:
            glob_path = f"{dir_key}/**/*{ext}"
        else:
            glob_path = dir_key

        sample_file = file_list[0]
        patterns = _infer_patterns_for_file(sample_file)
        new_targets.append(
            {
                "path": glob_path,
                "patterns": patterns,
                "discovered_at": now,
            }
        )
        logger.info(f"Discovered untracked log pattern: {glob_path} ({len(file_list)} file(s))")

    return new_targets


def persist_discovered_targets(new_targets: list[dict], config: dict) -> int:
    """Append newly discovered targets to state dir (ADR-466: config/state separation)."""
    import yaml
    import ai_self_healer as _healer

    logger = _get_logger()
    state_path = _healer.SCAN_TARGETS_STATE

    if not new_targets:
        return 0

    existing = list(config.get("discovered_scan_targets", []))
    existing_paths = {t.get("path") for t in existing}

    added = 0
    for target in new_targets:
        if target["path"] not in existing_paths:
            existing.append(target)
            existing_paths.add(target["path"])
            added += 1

    if added == 0:
        return 0

    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        yaml.dump(
            {"discovered_scan_targets": existing},
            default_flow_style=False,
            sort_keys=False,
        )
    )
    logger.info(f"Persisted {added} new scan targets to {state_path}")

    config["discovered_scan_targets"] = existing
    return added


# ═══════════════════════════════════════════════════════════════════════════════
# RESOURCE HEALTH MONITORING
# ═══════════════════════════════════════════════════════════════════════════════


def check_resource_health(config: dict) -> list:
    """Check dev server resource usage and Turbopack cache size.

    Returns ErrorFinding objects that feed into the existing dedup->classify->route
    pipeline. Only runs when resource_health.enabled is True in config.
    """
    from ai_self_healer import ErrorFinding

    _, _, PROJECT_ROOT = _get_paths()
    rh = config.get("resource_health", {})
    if not rh.get("enabled", False):
        return []

    findings: list[ErrorFinding] = []
    now = datetime.now().isoformat()

    # 1. Turbopack cache size check
    cache_limit_mb = rh.get("turbopack_cache_limit_mb", 400)
    dashboard_dir = PROJECT_ROOT / "apps" / "dashboard"
    turbo_cache = dashboard_dir / ".next" / "dev" / "cache" / "turbopack"
    if turbo_cache.is_dir():
        try:
            proc = subprocess.run(  # nosec B603,B607
                ["du", "-sk", str(turbo_cache)],
                capture_output=True, text=True, timeout=10,
            )
            if proc.returncode == 0:
                size_kb = int(proc.stdout.split()[0])
                size_mb = size_kb // 1024
                if size_mb > cache_limit_mb:
                    msg = (
                        f"resource:turbopack_cache_bloat -- Turbopack cache is {size_mb}MB "
                        f"(limit: {cache_limit_mb}MB). Clear .next/ or set AUGUR_DEV_HUBS."
                    )
                    key = _generate_dedup_key(msg, "turbopack_cache")
                    findings.append(ErrorFinding(
                        dedup_key=key, message=msg,
                        file="apps/dashboard/.next/dev/cache/turbopack",
                        timestamp=now,
                    ))
        except Exception:
            pass

    # 2. next-server CPU and RSS checks
    cpu_limit = rh.get("next_dev_cpu_limit_pct", 200)
    rss_limit_mb = rh.get("next_dev_rss_limit_mb", 2048)
    try:
        proc = subprocess.run(  # nosec B603,B607
            ["ps", "aux"],
            capture_output=True, text=True, timeout=10,
        )
        if proc.returncode == 0:
            for line in proc.stdout.splitlines():
                if "next-server" not in line and "next dev" not in line:
                    continue
                parts = line.split()
                if len(parts) < 11:
                    continue
                try:
                    cpu_pct = float(parts[2])
                    rss_kb = int(parts[5])
                    rss_mb = rss_kb // 1024
                except (ValueError, IndexError):
                    continue

                if cpu_pct > cpu_limit:
                    msg = (
                        f"resource:next_dev_cpu_thrash -- next-server using {cpu_pct:.0f}% CPU "
                        f"(limit: {cpu_limit}%). Likely V8 GC thrashing. "
                        f"Set AUGUR_DEV_HUBS or increase --max-old-space-size."
                    )
                    key = _generate_dedup_key(msg, "next_dev_cpu")
                    findings.append(ErrorFinding(
                        dedup_key=key, message=msg,
                        file="next-server", timestamp=now,
                    ))

                if rss_mb > rss_limit_mb:
                    msg = (
                        f"resource:next_dev_memory_bloat -- next-server using {rss_mb}MB RSS "
                        f"(limit: {rss_limit_mb}MB). Set AUGUR_DEV_HUBS to reduce page count."
                    )
                    key = _generate_dedup_key(msg, "next_dev_rss")
                    findings.append(ErrorFinding(
                        dedup_key=key, message=msg,
                        file="next-server", timestamp=now,
                    ))
                break  # Only check the first matching process
    except Exception:
        pass

    # 3. Log bloat check & rate of growth check
    log_limit_mb = rh.get("log_limit_mb", 50)
    growth_limit_mb = rh.get("log_growth_limit_mb", 10)
    log_dir = Path.home() / "Library" / "Logs" / "Augur"
    state_dir = Path.home() / "Library" / "Application Support" / "Augur" / "state" / "adaptive"
    last_size_file = state_dir / "last_log_size.txt"

    if log_dir.is_dir():
        try:
            proc = subprocess.run(
                ["du", "-sk", str(log_dir)],
                capture_output=True, text=True, timeout=10,
            )
            if proc.returncode == 0:
                size_kb = int(proc.stdout.split()[0])
                size_mb = size_kb // 1024

                last_size_mb = 0
                if last_size_file.exists():
                    try:
                        last_size_mb = int(last_size_file.read_text().strip())
                    except Exception:
                        pass

                state_dir.mkdir(parents=True, exist_ok=True)
                last_size_file.write_text(str(size_mb))

                growth_mb = size_mb - last_size_mb

                if growth_mb > growth_limit_mb:
                    msg = (
                        f"resource:log_growth_spike -- Logs directory grew by {growth_mb}MB "
                        f"(limit: {growth_limit_mb}MB/cycle). Indicates abnormal looping or logging spam."
                    )
                    key = _generate_dedup_key(msg, "log_growth")
                    findings.append(ErrorFinding(
                        dedup_key=key, message=msg,
                        file=str(log_dir), timestamp=now,
                    ))
                elif size_mb > log_limit_mb:
                    msg = (
                        f"resource:log_bloat -- Logs directory is {size_mb}MB "
                        f"(limit: {log_limit_mb}MB). Requires manual rotation."
                    )
                    key = _generate_dedup_key(msg, "log_bloat")
                    findings.append(ErrorFinding(
                        dedup_key=key, message=msg,
                        file=str(log_dir), timestamp=now,
                    ))
        except Exception:
            pass

    return findings
