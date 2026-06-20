"""Agent-digest compiler — OpsCommand entry point for the nightly loop.

Compiles Hot (violated directives) and Warm (recent ADRs) tiers from
event journal data and ADR frontmatter. Pure functions at the top are
testable without project deps; OpsCommand scan/fix at the bottom use
lazy imports for src.config.paths and src.lib.ops_protocol.
"""

from __future__ import annotations


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
import sys
import importlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

# Ensure sibling modules in scripts/ are importable when loaded via importlib
_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)


def _import_sibling(module_name: str):
    if __package__:
        try:
            return importlib.import_module(f".{module_name}", __package__)
        except ImportError:
            pass

    module_path = Path(__file__).resolve().with_name(f"{module_name}.py")
    module_key = f"_augur_agent_digest_{module_name}_{abs(hash(str(module_path)))}"
    existing = sys.modules.get(module_key)
    if existing is not None:
        return existing
    spec = _augur_importlib_util.spec_from_file_location(module_key, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load sibling module {module_name} from {module_path}")
    module = _augur_importlib_util.module_from_spec(spec)
    sys.modules[module_key] = module
    spec.loader.exec_module(module)
    return module


_scoring = _import_sibling("scoring")
TOKEN_BUDGET_HOT = _scoring.TOKEN_BUDGET_HOT
TOKEN_BUDGET_WARM = _scoring.TOKEN_BUDGET_WARM
estimate_tokens = _scoring.estimate_tokens
score_directives = _scoring.score_directives
select_top_directives = _scoring.select_top_directives

name = "auto-agent-digest"

HOT_WINDOW_DAYS = 7
WARM_WINDOW_DAYS = 30


# ---------------------------------------------------------------------------
# Pure functions — no project-specific deps, testable in isolation
# ---------------------------------------------------------------------------


def compile_hot_tier(
    events: list[dict],
    directive_map: dict[str, dict],
    reference_date: datetime | None = None,
) -> list[str]:
    """Compile Hot tier directive lines from events.

    Returns formatted markdown bullet lines ranked by score,
    capped to TOKEN_BUDGET_HOT.
    """
    if not events:
        return ["No active directives — all patterns clean this week."]
    scored = score_directives(events, reference_date=reference_date)
    return select_top_directives(scored, directive_map, budget=TOKEN_BUDGET_HOT)


def compile_warm_tier(
    adr_dir: Path,
    days: int = WARM_WINDOW_DAYS,
    reference_date: datetime | None = None,
) -> list[str]:
    """Compile Warm tier from recent ADRs.

    Reads the central ``adrs-index.json`` (ADR-642), filters by date,
    returns formatted lines within ``TOKEN_BUDGET_WARM``. Falls back to
    legacy on-disk ``ADR-*.md`` scanning if the central index is missing.
    """
    ref = reference_date or datetime.now(timezone.utc)
    cutoff = ref - timedelta(days=days)
    lines: list[str] = []
    used_tokens = 0

    if not adr_dir.exists():
        return lines

    # Primary: central JSON index.
    try:
        from src.lib.adr_utils import load_adrs_index

        records = load_adrs_index(adr_dir)
    except Exception:
        records = []

    if records:
        records_sorted = sorted(records, key=lambda r: str(r.get("adr_number", "")), reverse=True)
        for record in records_sorted:
            date_str = str(record.get("date", "") or "")
            if not date_str:
                continue
            try:
                adr_date = datetime.strptime(date_str[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                continue
            if adr_date < cutoff:
                continue
            adr_num = str(record.get("adr_number", "")).strip() or "ADR-???"
            title = record.get("title") or adr_num
            line = f"- **{adr_num}**: {title} ({date_str})"
            line_tokens = estimate_tokens(line)
            if used_tokens + line_tokens > TOKEN_BUDGET_WARM:
                break
            lines.append(line)
            used_tokens += line_tokens
        return lines

    # Fallback: legacy on-disk ADR-*.md (pre-ADR-642 environments).
    for adr_file in sorted(adr_dir.glob("ADR-*.md"), reverse=True):
        try:
            content = adr_file.read_text()
        except OSError:
            continue
        if not content.startswith("---"):
            continue
        parts = content.split("---", 2)
        if len(parts) < 3:
            continue
        try:
            fm = yaml.safe_load(parts[1])
        except yaml.YAMLError:
            continue
        title = fm.get("title", adr_file.stem)
        if title == adr_file.stem or (title.startswith("ADR-") and "-" in title[4:]):
            body = parts[2] if len(parts) > 2 else ""
            for body_line in body.split("\n"):
                if body_line.startswith("# "):
                    title = body_line[2:].strip()
                    break
        date_str = fm.get("date", "")
        if not date_str:
            continue
        try:
            if isinstance(date_str, str):
                adr_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            else:
                adr_date = datetime.combine(date_str, datetime.min.time()).replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue
        if adr_date < cutoff:
            continue

        stem_parts = adr_file.stem.split("-")
        if len(stem_parts) >= 2:
            adr_num = stem_parts[0] + "-" + stem_parts[1]
        else:
            adr_num = adr_file.stem

        line = f"- **{adr_num}**: {title} ({date_str})"
        line_tokens = estimate_tokens(line)
        if used_tokens + line_tokens > TOKEN_BUDGET_WARM:
            break
        lines.append(line)
        used_tokens += line_tokens

    return lines


def format_hot_section(
    events: list[dict],
    directive_map: dict[str, dict],
    reference_date: datetime | None = None,
) -> str:
    """Format the complete Hot Directives section as markdown."""
    ref = reference_date or datetime.now(timezone.utc)
    lines = compile_hot_tier(events, directive_map, reference_date=ref)
    total_tokens = sum(estimate_tokens(l) for l in lines)
    header = (
        "## Hot Directives (violated in last 7 days)\n"
        f"<!-- auto-generated by auto-agent-digest nightly loop — do not edit manually -->\n"
        f"<!-- last updated: {ref.isoformat()} | signals: {len(events)} events | budget: {total_tokens}/{TOKEN_BUDGET_HOT} tokens -->\n"
    )
    return header + "\n" + "\n".join(lines) + "\n"


def format_warm_section(
    adr_dir: Path,
    reference_date: datetime | None = None,
) -> str:
    """Format the complete Recent Decisions section as markdown."""
    ref = reference_date or datetime.now(timezone.utc)
    lines = compile_warm_tier(adr_dir, reference_date=ref)
    header = (
        "## Recent Decisions (last 30 days)\n"
        f"<!-- auto-generated by auto-agent-digest weekly loop — do not edit manually -->\n"
        f"<!-- last updated: {ref.isoformat()} | ADRs scanned: {len(lines)} -->\n"
    )
    if not lines:
        return header + "\nNo recent ADRs in the last 30 days.\n"
    return header + "\n" + "\n".join(lines) + "\n"


def _write_digest_file(path: Path, content: str) -> None:
    """Write digest section to intermediate file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


# ---------------------------------------------------------------------------
# OpsCommand contract — these use project-specific imports (lazy)
# ---------------------------------------------------------------------------


def _get_paths():
    """Lazy import of project path functions."""
    from src.config.paths import (
        get_adr_dir,
        get_claude_native_memory_dir,
        get_logs_dir,
        get_memory_dir,
        get_runtime_dir,
        get_skills_dir,
        get_vault_dir,
    )
    return (
        get_adr_dir,
        get_claude_native_memory_dir,
        get_logs_dir,
        get_memory_dir,
        get_runtime_dir,
        get_skills_dir,
        get_vault_dir,
    )


def _get_ops_protocol():
    """Lazy import of ops protocol."""
    from src.lib.ops_protocol import (
        FixResult, OpsContext, ScanResult, evolution_gap, make_issue,
    )
    return FixResult, OpsContext, ScanResult, evolution_gap, make_issue


def _skill_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _agent_digest_dir() -> Path:
    return Path(__file__).resolve().parent


def _journal_dir() -> Path:
    _, _, _, _, get_runtime_dir, _, _ = _get_paths()
    d = get_runtime_dir() / "agent-digest"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load_directive_map() -> dict[str, dict]:
    map_path = _agent_digest_dir() / "directive-map.yaml"
    with map_path.open() as f:
        data = yaml.safe_load(f)
    return data.get("directives", {})


def _load_seed_directives() -> list[dict]:
    seed_path = _skill_root() / "assets" / "seeds" / "agent-digest" / "example-auto-agent-digest.yaml"
    if not seed_path.exists():
        return []
    with seed_path.open() as f:
        data = yaml.safe_load(f)
    return data.get("seed_directives", [])


def scan(ctx):
    """Collect violation signals and report stats."""
    collect_git = _import_sibling("collect_git_signals").collect
    collect_session = _import_sibling("collect_session_signals").collect
    journal = _import_sibling("journal")
    append_event = journal.append_event
    read_events = journal.read_events

    FixResult, OpsContext, ScanResult, evolution_gap, make_issue = _get_ops_protocol()
    _, _, get_logs_dir, _, _, _, _ = _get_paths()

    journal_dir = _journal_dir()
    digest_dir = _agent_digest_dir()
    patterns_path = digest_dir / "violation-patterns.yaml"
    directive_map_path = digest_dir / "directive-map.yaml"
    issues = []

    git_events = collect_git(ctx.project_root, patterns_path, state_dir=journal_dir)
    for event in git_events:
        append_event(journal_dir, event)

    logs_dir = get_logs_dir()
    session_events = collect_session(logs_dir, directive_map_path)
    for event in session_events:
        append_event(journal_dir, event)

    total_new = len(git_events) + len(session_events)

    since = datetime.now(timezone.utc) - timedelta(days=HOT_WINDOW_DAYS)
    all_events = read_events(journal_dir, since=since)

    if not all_events and ctx.difficulty >= 1:
        issues.append(
            evolution_gap(
                "No violation events in 7-day window — session log collector may not be capturing corrections. "
                "Next: verify session log paths and correction patterns."
            )
        )

    if ctx.difficulty >= 1:
        directive_map = _load_directive_map()
        scored = score_directives(all_events)
        low_scores = all(v["score"] < 2 for v in scored.values()) if scored else True
        if scored and low_scores:
            issues.append(
                evolution_gap(
                    "All Hot directives score < 2 — directive-map.yaml may need more patterns. "
                    "Next: review recent session logs for uncaptured correction signals."
                )
            )

    # Promotion candidate check (d>=2)
    if ctx.difficulty >= 2 and all_events:
        since_30d = datetime.now(timezone.utc) - timedelta(days=30)
        events_30d = read_events(journal_dir, since=since_30d)
        scored_30d = score_directives(events_30d)
        for directive_id, data in scored_30d.items():
            if data["count"] >= 10:
                issues.append(
                    evolution_gap(
                        f"Directive '{directive_id}' has {data['count']} violations over 30 days — "
                        f"candidate for CLAUDE.md rule promotion. "
                        f"Next: review and add to docs/agent-topics/agent-rules.md if warranted."
                    )
                )

    return ScanResult(
        issues=issues,
        summary=f"Collected {total_new} new events ({len(git_events)} git, {len(session_events)} session). "
                f"Journal has {len(all_events)} events in 7-day window.",
        severity="info" if not issues else "warning",
        items_scanned=total_new,
        run_fix_on_clean=True,
    )


def _find_claude_native_memory_dir(project_root: Path) -> Path | None:
    """Locate the Claude Code project-specific memory directory."""
    _, get_claude_native_memory_dir, _, _, _, _, _ = _get_paths()
    return get_claude_native_memory_dir(project_root)


def fix(ctx, issues):
    """Compile digest sections and write intermediate files.

    Writes to both the runtime memory dir (canonical) and the Claude native
    memory dir (so hot directives are fresh between full assembly runs).
    """
    journal = _import_sibling("journal")
    append_event = journal.append_event
    archive_old = journal.archive_old
    purge_archives = journal.purge_archives
    read_events = journal.read_events

    FixResult, OpsContext, ScanResult, evolution_gap, make_issue = _get_ops_protocol()
    get_adr_dir, _, _, get_memory_dir, _, _, _ = _get_paths()

    if ctx.dry_run:
        return FixResult(success=True, summary="Dry run: would compile digest sections")

    journal_dir = _journal_dir()
    directive_map = _load_directive_map()
    vault_memory_dir = get_memory_dir()
    claude_native_dir = _find_claude_native_memory_dir(ctx.project_root)
    changes = []
    ref = datetime.now(timezone.utc)

    if ctx.difficulty >= 1:
        since = ref - timedelta(days=HOT_WINDOW_DAYS)
        events = read_events(journal_dir, since=since)

        if not events:
            seeds = _load_seed_directives()
            for seed in seeds:
                append_event(journal_dir, {
                    "ts": ref.isoformat(),
                    "source": "seed",
                    "type": "pattern_violation",
                    "rule": seed["directive"],
                })
            events = read_events(journal_dir, since=since)

        hot_section = format_hot_section(events, directive_map, reference_date=ref)
        hot_path = vault_memory_dir / "digest-hot.md"
        _write_digest_file(hot_path, hot_section)
        changes.append(f"Wrote {hot_path}")

        # Also write to Claude native dir so MEMORY.md stays fresh
        if claude_native_dir is not None:
            native_hot = claude_native_dir / "digest-hot.md"
            _write_digest_file(native_hot, hot_section)
            changes.append(f"Wrote {native_hot}")

    if ctx.difficulty >= 2:
        adr_dir = get_adr_dir()
        warm_section = format_warm_section(adr_dir, reference_date=ref)
        warm_path = vault_memory_dir / "digest-warm.md"
        _write_digest_file(warm_path, warm_section)
        changes.append(f"Wrote {warm_path}")

        if claude_native_dir is not None:
            native_warm = claude_native_dir / "digest-warm.md"
            _write_digest_file(native_warm, warm_section)
            changes.append(f"Wrote {native_warm}")

        date_str = ref.strftime("%Y-%m-%d")
        archive_old(journal_dir, date_str=date_str)
        purged = purge_archives(journal_dir, retention_days=30, reference_date=ref)
        if purged:
            changes.append(f"Purged {len(purged)} old archives")

    return FixResult(
        success=True,
        changes=changes,
        summary=f"Compiled {'hot' if ctx.difficulty == 1 else 'hot + warm'} digest. {len(changes)} files written.",
        fix_type="sync",
    )
