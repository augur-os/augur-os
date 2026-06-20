#!/usr/bin/env python3
"""
Proactive Page Insight Scanner for Augur (ADR-078).

Scans dashboard pages for improvement opportunities using LLM analysis.
Pipeline: load_config → check_usage → analyze_pages → score → promote → notify

Usage:
    python3 insight_scanner.py --loop      # Daemon mode (continuous)
    python3 insight_scanner.py --scan      # One-shot scan
    python3 insight_scanner.py --status    # Show insight stats
"""
# TODO_CLEANUP: This file is 830 lines — consider splitting into smaller modules

from __future__ import annotations

import argparse
import json
import re
import subprocess  # nosec B404
import sys
import time
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    fobj = kwargs.get("file", sys.stdout)
    fobj.write(sep.join(str(arg) for arg in args) + str(end))


# ═══════════════════════════════════════════════════════════════════════════════
# PROJECT SETUP
# ═══════════════════════════════════════════════════════════════════════════════

try:
    from bootstrap_paths import ensure_project_paths
except ImportError:
    _SCRIPTS_DIR = Path(__file__).resolve().parent
    if str(_SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS_DIR))
    from bootstrap_paths import ensure_project_paths

PROJECT_ROOT = ensure_project_paths(__file__)

try:
    from src.logging import get_entity_logger
except ImportError:
    import logging as _logging

    def get_entity_logger(name: str) -> _logging.Logger:
        lg = _logging.getLogger(name)
        if not lg.handlers:
            h = _logging.StreamHandler()
            h.setFormatter(_logging.Formatter("%(levelname)s - %(message)s"))
            lg.addHandler(h)
            lg.setLevel(_logging.INFO)
        return lg


from src.config.paths import get_project_port, get_project_root, get_runtime_dir
from runtime_paths import (
    get_insights_archive_dir,
    get_insights_config_path,
    get_insights_path,
)

try:
    from notification_service import NotificationService
except ImportError:
    try:
        _ns_path = str(Path(__file__).resolve().parent)
        if _ns_path not in sys.path:
            sys.path.insert(0, _ns_path)
        from notification_service import NotificationService
    except ImportError:
        NotificationService = None  # type: ignore[assignment,misc]


logger = get_entity_logger("insight_scanner")

EFFECTIVELY_DISABLED_INTERVAL_HOURS = 876000

# ═══════════════════════════════════════════════════════════════════════════════
# PATHS
# ═══════════════════════════════════════════════════════════════════════════════

DATA_DIR = get_project_root()
CONFIG_FILE = get_insights_config_path()
USAGE_FILE = get_runtime_dir() / "daemon" / "usage_stats.yaml"
INSIGHTS_FILE = get_insights_path()
ARCHIVE_DIR = get_insights_archive_dir()
BUNDLES = (
    "admin",
    "ai",
    "career",
    "consulting",
    "dev",
    "enterprise",
    "finance",
    "health",
    "home",
    "lifestyle",
    "observability",
    "orchestration",
    "productivity",
    "professional",
)

VALID_CATEGORIES = frozenset(
    {
        "data_structure",
        "use_case",
        "action_button",
        "organization",
        "workflow",
        "integration",
    }
)


# ═══════════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class Insight:
    """A single page improvement insight."""

    id: str
    page: str
    category: str  # data_structure|use_case|action_button|organization|workflow|integration
    title: str
    description: str
    score: int  # 0-100
    status: str = "candidate"  # candidate|pending|dismissed|accepted|implemented
    created_at: str = ""
    notified_at: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Insight":
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)


# ═══════════════════════════════════════════════════════════════════════════════
# YAML HELPERS
# ═══════════════════════════════════════════════════════════════════════════════


def _safe_yaml_load(path: Path) -> dict:
    """Safely load a YAML file, returning empty dict on any error."""
    import yaml

    if not path.exists():
        return {}
    try:
        content = yaml.safe_load(path.read_text()) or {}
        return content if isinstance(content, dict) else {}
    except Exception as e:
        logger.warning(f"Failed to load {path.name}: {e}")
        return {}


def _safe_yaml_write(path: Path, data: Any) -> None:
    """Safely write data to a YAML file with atomic write pattern."""
    import yaml

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        tmp.write_text(yaml.safe_dump(data, default_flow_style=False, sort_keys=False), encoding="utf-8")
        tmp.replace(path)
    except Exception as e:
        logger.error(f"Failed to write {path.name}: {e}")
        tmp.unlink(missing_ok=True)


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════════════════


def load_config() -> dict:
    """Load insight scanner config with defaults."""
    config = _safe_yaml_load(CONFIG_FILE)
    config.setdefault("enabled", True)
    config.setdefault("schedule", {})
    config["schedule"].setdefault("default_interval_hours", 12)
    config.setdefault("pages", {})
    config["pages"].setdefault("min_views_7d", 3)
    config.setdefault("scoring", {})
    config["scoring"].setdefault("promotion_threshold", 70)
    config["scoring"].setdefault("max_notifications_per_day", 1)
    config["scoring"].setdefault("staleness_days", 30)
    config["scoring"].setdefault("max_insights_per_page", 3)
    config.setdefault("llm", {})
    config["llm"].setdefault("model", "haiku")
    config["llm"].setdefault("max_tokens", 500)
    config["llm"].setdefault("timeout_s", 60)
    return config


# ═══════════════════════════════════════════════════════════════════════════════
# USAGE GATE
# ═══════════════════════════════════════════════════════════════════════════════


def load_usage_stats() -> dict:
    """Load page usage statistics. Returns dict keyed by page pathname."""
    data = _safe_yaml_load(USAGE_FILE)
    return data.get("pages", data) if isinstance(data, dict) else {}


def get_qualifying_pages(usage: dict, config: dict) -> list[dict]:
    """Filter pages that meet the minimum usage threshold.

    Returns list of dicts with keys: page, skill_name, views_7d.
    """
    min_views = config.get("pages", {}).get("min_views_7d", 3)
    qualifying: list[dict] = []

    for page_path, stats in usage.items():
        views = stats.get("views_7d", 0) if isinstance(stats, dict) else 0
        if views >= min_views:
            skill_name = page_path.strip("/").split("/")[0] if page_path.strip("/") else ""
            if skill_name:
                qualifying.append(
                    {
                        "page": page_path,
                        "skill_name": skill_name,
                        "views_7d": views,
                    }
                )

    return qualifying


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE CONTEXT
# ═══════════════════════════════════════════════════════════════════════════════


def _find_dashboard_yaml(skill_name: str) -> Optional[Path]:
    """Find dashboard.yaml for a given skill name across all bundles."""
    for bundle in BUNDLES:
        candidate = PROJECT_ROOT / "plugins" / bundle / "skills" / skill_name / "dashboard.yaml"
        if candidate.exists():
            return candidate
    return None


def _list_data_files(skill_name: str) -> list[str]:
    """List YAML/JSON data files for a skill in the data directory."""
    files: list[str] = []
    for bundle in BUNDLES:
        data_dir = DATA_DIR / "plugins" / bundle / skill_name
        if not data_dir.exists():
            continue
        for ext in ("*.yaml", "*.yml", "*.json"):
            for f in data_dir.glob(ext):
                files.append(f.name)
    return files[:20]  # Cap to avoid bloating the prompt


def gather_page_context(page: str, skill_name: str, views_7d: int = 0) -> str:
    """Build a context string about a page for LLM analysis."""
    import yaml

    tabs_str = "N/A"
    actions_str = "N/A"

    dash_yaml = _find_dashboard_yaml(skill_name)
    if dash_yaml:
        try:
            dash_data = yaml.safe_load(dash_yaml.read_text()) or {}
            tabs = dash_data.get("tabs", [])
            if tabs:
                tabs_str = ", ".join(t.get("label", t.get("id", "?")) for t in tabs if isinstance(t, dict))
            actions = dash_data.get("actions", [])
            if actions:
                actions_str = ", ".join(a.get("label", a.get("id", "?")) for a in actions if isinstance(a, dict))
        except Exception:
            pass

    data_files = _list_data_files(skill_name)
    data_files_str = ", ".join(data_files) if data_files else "none"

    return (
        f"Page: {page}\n"
        f"Skill: {skill_name}\n"
        f"Tabs: {tabs_str}\n"
        f"Actions: {actions_str}\n"
        f"Data files: {data_files_str}\n"
        f"Usage: {views_7d} views this week"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# LLM ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════


ANALYZE_PROMPT = """Analyze this dashboard page and suggest concrete improvements.

{context}

Suggest 1-3 improvements. For each, provide JSON:
[{{
  "title": "Short title",
  "description": "What to do and why",
  "category": "data_structure|use_case|action_button|organization|workflow|integration",
  "score": 0-100 (higher = more valuable)
}}]

Only suggest if score >= 60. If page is already well-designed, return empty array [].
Respond with ONLY the JSON array (no markdown fences, no extra text)."""


def resolve_cli(config: dict) -> Optional[str]:
    """Resolve which CLI binary to use for LLM calls."""
    from src.lib.llm_retry import resolve_cli as _canonical_resolve_cli

    llm_conf = config.get("llm", {})
    cli_name = llm_conf.get("cli", "auto")
    return _canonical_resolve_cli(cli_name)


def call_llm(prompt: str, config: dict, cli_path: Optional[str] = None) -> str:
    """Call LLM for insight analysis. Returns raw response text."""
    if cli_path is None:
        cli_path = resolve_cli(config)

    if not cli_path:
        logger.warning("No LLM CLI available, skipping analysis")
        return ""

    timeout = config.get("llm", {}).get("timeout_s", 60)

    creationflags = 0x08000000 if sys.platform == "win32" else 0
    try:
        result = subprocess.run(  # nosec B603
            [cli_path, "--print", "--max-turns", "1", "-p", prompt],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(PROJECT_ROOT),
            creationflags=creationflags,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        logger.warning(f"LLM CLI returned {result.returncode}: {result.stderr[:200]}")
    except subprocess.TimeoutExpired:
        logger.warning("LLM call timed out")
    except FileNotFoundError:
        logger.warning(f"CLI not found: {cli_path}")
    except Exception as e:
        logger.warning(f"LLM call error: {e}")

    return ""


def _parse_llm_json_array(output: str) -> list[dict]:
    """Extract a JSON array from LLM output."""
    # Try direct parse as array
    try:
        parsed = json.loads(output.strip())
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict) and "insights" in parsed:
            return parsed["insights"]
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code fence
    match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", output, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(1))
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass

    # Try finding any JSON array
    match = re.search(r"\[.*\]", output, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass

    return []


def analyze_page(page: str, context: str, config: dict, cli_path: Optional[str] = None) -> list[Insight]:
    """Call LLM to analyze a page and return Insight objects."""
    prompt = ANALYZE_PROMPT.format(context=context)
    response = call_llm(prompt, config, cli_path)

    if not response:
        return []

    items = _parse_llm_json_array(response)
    if not items:
        logger.info(f"No suggestions for {page}")
        return []

    max_per_page = config.get("scoring", {}).get("max_insights_per_page", 3)
    now = datetime.now().isoformat()
    insights: list[Insight] = []

    for item in items[:max_per_page]:
        if not isinstance(item, dict):
            continue

        title = str(item.get("title", "")).strip()
        description = str(item.get("description", "")).strip()
        category = str(item.get("category", "")).strip().lower()

        if not title or not description:
            continue

        # Validate category
        if category not in VALID_CATEGORIES:
            category = "workflow"

        # Validate score
        try:
            score = int(item.get("score", 50))
        except (ValueError, TypeError):
            score = 50
        score = max(0, min(100, score))

        if score < 60:
            continue

        insights.append(
            Insight(
                id=str(uuid.uuid4())[:8],
                page=page,
                category=category,
                title=title[:200],
                description=description[:500],
                score=score,
                status="candidate",
                created_at=now,
            )
        )

    return insights


# ═══════════════════════════════════════════════════════════════════════════════
# INSIGHT STORAGE
# ═══════════════════════════════════════════════════════════════════════════════


def load_insights() -> list[Insight]:
    """Load existing insights from disk."""
    data = _safe_yaml_load(INSIGHTS_FILE)
    raw_list = data.get("insights", [])
    insights: list[Insight] = []
    for item in raw_list:
        if isinstance(item, dict):
            try:
                insights.append(Insight.from_dict(item))
            except (TypeError, KeyError):
                continue
    return insights


def save_insights(insights: list[Insight]) -> None:
    """Write insights to disk."""
    data = {
        "insights": [i.to_dict() for i in insights],
        "last_updated": datetime.now().isoformat(),
    }
    _safe_yaml_write(INSIGHTS_FILE, data)


def _insight_dedup_key(insight: Insight) -> str:
    """Generate a dedup key from page + title (lowercased)."""
    return f"{insight.page}|{insight.title.lower().strip()}"


def merge_new_insights(existing: list[Insight], new: list[Insight]) -> list[Insight]:
    """Merge new insights into existing list, deduplicating by page+title."""
    seen = {_insight_dedup_key(i) for i in existing}
    merged = list(existing)

    for insight in new:
        key = _insight_dedup_key(insight)
        if key not in seen:
            merged.append(insight)
            seen.add(key)

    return merged


# ═══════════════════════════════════════════════════════════════════════════════
# PROMOTION & CLEANUP
# ═══════════════════════════════════════════════════════════════════════════════


def promote_insights(insights: list[Insight], threshold: int) -> list[Insight]:
    """Promote candidate insights with score >= threshold to pending.

    Returns the list of newly promoted insights.
    """
    promoted: list[Insight] = []

    for insight in insights:
        if insight.status == "candidate" and insight.score >= threshold:
            insight.status = "pending"
            promoted.append(insight)

    return promoted


def cleanup_stale(insights: list[Insight], staleness_days: int) -> list[Insight]:
    """Archive candidate insights older than staleness_days.

    Returns the cleaned list (stale candidates removed).
    """
    if staleness_days <= 0:
        return insights

    cutoff = datetime.now() - timedelta(days=staleness_days)
    kept: list[Insight] = []
    archived: list[Insight] = []

    for insight in insights:
        if insight.status == "candidate" and insight.created_at:
            try:
                created_dt = datetime.fromisoformat(insight.created_at)
                if created_dt < cutoff:
                    archived.append(insight)
                    continue
            except (ValueError, TypeError):
                pass
        kept.append(insight)

    if archived:
        _archive_insights(archived)
        logger.info(f"Archived {len(archived)} stale candidate insights")

    return kept


def _archive_insights(insights: list[Insight]) -> None:
    """Write archived insights to a timestamped file."""
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    archive_file = ARCHIVE_DIR / f"archived_{today}.yaml"

    existing_data = _safe_yaml_load(archive_file)
    existing_list = existing_data.get("archived", [])
    existing_list.extend([i.to_dict() for i in insights])

    _safe_yaml_write(
        archive_file,
        {
            "archived": existing_list,
            "archived_at": datetime.now().isoformat(),
        },
    )


# ═══════════════════════════════════════════════════════════════════════════════
# NOTIFICATIONS
# ═══════════════════════════════════════════════════════════════════════════════


def notify_if_needed(promoted: list[Insight], config: dict, all_insights: list[Insight]) -> None:
    """Send notification for the best promoted insight (max 1/day)."""
    if not promoted:
        return

    max_per_day = config.get("scoring", {}).get("max_notifications_per_day", 1)
    today = datetime.now().strftime("%Y-%m-%d")

    # Count notifications already sent today across all insights
    notified_today = sum(1 for i in all_insights if i.notified_at and i.notified_at.startswith(today))
    if notified_today >= max_per_day:
        return

    # Pick highest-scoring promoted insight
    best = max(promoted, key=lambda i: i.score)

    if NotificationService is not None:
        try:
            ns = NotificationService()
            ns.notify(
                f"Insight for {best.page}: {best.title}",
                category="insights",
                title="Augur Insight",
                open_url=f"http://localhost:{get_project_port()}{best.page}",
            )
            best.notified_at = datetime.now().isoformat()
            logger.info(f"Notified: {best.title} (score={best.score})")
        except Exception as e:
            logger.warning(f"Notification failed: {e}")
    else:
        logger.info(f"[NOTIFY] Insight for {best.page}: {best.title} (score={best.score})")
        best.notified_at = datetime.now().isoformat()


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════


def run_scan(config: dict) -> dict:
    """Orchestrate: load → qualify → analyze → score → promote → notify.

    Returns summary dict.
    """
    summary: dict[str, Any] = {
        "pages_scanned": 0,
        "new_insights": 0,
        "promoted": 0,
        "archived": 0,
        "timestamp": datetime.now().isoformat(),
    }

    if not config.get("enabled", True):
        logger.info("Insight scanner disabled")
        return summary

    # 1. Load existing data
    usage = load_usage_stats()
    existing_insights = load_insights()

    # 2. Get qualifying pages
    pages = get_qualifying_pages(usage, config)
    if not pages:
        logger.info("No qualifying pages found (check usage_stats.yaml)")
        # Still run promotion and cleanup on existing insights
        threshold = config.get("scoring", {}).get("promotion_threshold", 70)
        promoted = promote_insights(existing_insights, threshold)
        if promoted:
            notify_if_needed(promoted, config, existing_insights)
        staleness = config.get("scoring", {}).get("staleness_days", 30)
        existing_insights = cleanup_stale(existing_insights, staleness)
        summary["archived"] = len(existing_insights)
        save_insights(existing_insights)
        return summary

    summary["pages_scanned"] = len(pages)
    logger.info(f"Scanning {len(pages)} qualifying pages")

    # 3. Resolve CLI once
    cli_path = resolve_cli(config)
    if not cli_path:
        logger.warning("No LLM CLI available, skipping analysis")

    # 4. Analyze each page
    all_new: list[Insight] = []
    if cli_path:
        for page_info in pages:
            page = page_info["page"]
            skill = page_info["skill_name"]
            views = page_info["views_7d"]

            try:
                context = gather_page_context(page, skill, views)
                new_insights = analyze_page(page, context, config, cli_path)
                if new_insights:
                    all_new.extend(new_insights)
                    logger.info(f"  {page}: {len(new_insights)} suggestions")
            except Exception as e:
                logger.warning(f"Failed to analyze {page}: {e}")

    # 5. Merge with existing (dedup)
    merged = merge_new_insights(existing_insights, all_new)
    summary["new_insights"] = len(merged) - len(existing_insights)

    # 6. Promote high-scoring candidates
    threshold = config.get("scoring", {}).get("promotion_threshold", 70)
    promoted = promote_insights(merged, threshold)
    summary["promoted"] = len(promoted)

    # 7. Clean stale candidates
    staleness = config.get("scoring", {}).get("staleness_days", 30)
    pre_cleanup = len(merged)
    merged = cleanup_stale(merged, staleness)
    summary["archived"] = pre_cleanup - len(merged)

    # 8. Notify
    notify_if_needed(promoted, config, merged)

    # 9. Save
    save_insights(merged)

    return summary


def _load_service_interval() -> int | None:
    """Read interval_hours from adaptive_loops.yaml services config (ADR-216)."""
    try:
        from src.config.paths import get_config_dir
        cfg_path = get_config_dir() / "system" / "adaptive_loops.yaml"
        if cfg_path.exists():
            data = _safe_yaml_load(cfg_path)
            return data.get("services", {}).get("insight_scanner", {}).get("interval_hours")
    except Exception:
        pass
    return None


def _is_effectively_disabled_interval(interval_hours: int) -> bool:
    return interval_hours >= EFFECTIVELY_DISABLED_INTERVAL_HOURS


def run_loop(config: dict) -> None:
    """Continuous daemon loop."""
    logger.info("Insight Scanner starting")
    last_interval_hours: int | None = None

    while True:
        # ADR-216: hot-reload interval each cycle from service config.
        raw_interval = (
            _load_service_interval()
            or config.get("schedule", {}).get("default_interval_hours", 12)
        )
        try:
            interval_hours = max(1, int(raw_interval))
        except (TypeError, ValueError):
            interval_hours = 12
        interval_s = interval_hours * 3600
        if interval_hours != last_interval_hours:
            logger.info(f"Insight Scanner interval set to {interval_hours}h")
            last_interval_hours = interval_hours

        if _is_effectively_disabled_interval(interval_hours):
            logger.info(f"Insight Scanner disabled by interval {interval_hours}h; sleeping without scan")
            time.sleep(interval_s)
            continue

        try:
            summary = run_scan(config)
            new = summary.get("new_insights", 0)
            promoted = summary.get("promoted", 0)
            if new > 0 or promoted > 0:
                logger.info(f"Scan complete: {new} new insights, {promoted} promoted")
            else:
                logger.info("Scan complete: no new insights")
        except Exception as e:
            logger.error(f"Scan error: {e}")

        time.sleep(interval_s)


# ═══════════════════════════════════════════════════════════════════════════════
# STATUS
# ═══════════════════════════════════════════════════════════════════════════════


def show_status() -> int:
    """Print insight statistics."""
    insights = load_insights()

    if not insights:
        _out("No insights generated yet.")
        return 0

    by_status: dict[str, int] = {}
    by_category: dict[str, int] = {}
    by_page: dict[str, int] = {}

    for insight in insights:
        by_status[insight.status] = by_status.get(insight.status, 0) + 1
        by_category[insight.category] = by_category.get(insight.category, 0) + 1
        by_page[insight.page] = by_page.get(insight.page, 0) + 1

    _out("Insight Scanner Status")
    _out("=" * 40)
    _out(f"  Total insights: {len(insights)}")
    _out()
    _out("  By status:")
    for status, count in sorted(by_status.items()):
        _out(f"    {status}: {count}")
    _out()
    _out("  By category:")
    for cat, count in sorted(by_category.items()):
        _out(f"    {cat}: {count}")
    _out()
    _out("  By page:")
    for page, count in sorted(by_page.items(), key=lambda x: -x[1]):
        _out(f"    {page}: {count}")

    # Show top pending insights
    pending = [i for i in insights if i.status == "pending"]
    if pending:
        _out()
        _out("  Top pending insights:")
        for insight in sorted(pending, key=lambda i: -i.score)[:5]:
            _out(f"    [{insight.score}] {insight.page}: {insight.title}")

    return 0


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Augur Insight Scanner (ADR-078)")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--loop", action="store_true", help="Daemon mode (continuous)")
    group.add_argument("--scan", action="store_true", help="One-shot scan")
    group.add_argument("--status", action="store_true", help="Show insight stats")
    args = parser.parse_args()

    if args.status:
        return show_status()

    if args.loop:
        config = load_config()
        run_loop(config)
        return 0

    # Default: one-shot scan
    config = load_config()
    summary = run_scan(config)

    _out("Insight Scanner -- Scan Complete")
    _out("=" * 40)
    for key, value in summary.items():
        _out(f"  {key}: {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
