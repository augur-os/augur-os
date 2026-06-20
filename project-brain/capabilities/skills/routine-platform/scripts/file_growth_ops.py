"""auto-file-growth: Detect runaway file generation in vault and data directories.

Catches the class of bug where a write-loop creates a new file per operation
instead of updating existing ones — e.g., 195K timestamp-named symptom files
from a health skill that should have had 5.

Difficulty levels:
  d0: Quick count — flag dirs with >500 files or >50% timestamp-named files
  d1: Content — sample-based duplicate detection, RAG index size check
  d2: Deep — full duplicate scan across all vault subdirs
  d3: Exhaustive — git-based growth rate analysis
  d4: Evolution gaps
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
import hashlib
import logging
import re
import sys
from pathlib import Path

from src.lib.brain_layout import brain_knowledge_dir
from src.lib.ops_protocol import (
    OpsContext,
    ScanResult,
    FixResult,
    evolution_gap,
    make_issue,
    report_only_fix,
    write_report,
)

name = "auto-file-growth"

DIFFICULTY_SPEC = {
    0: "Surface — count files per dir, flag >500 and timestamp-name patterns",
    1: "Content — sample duplicate detection, RAG index sizes",
    2: "Deep — full duplicate scan across vault",
    3: "Exhaustive — git growth rate analysis",
    4: "Expert — evolution gaps",
}

logger = logging.getLogger(__name__)

# Thresholds — tuned for a personal knowledge system where individual
# directories should rarely exceed 100 files. Anything higher signals
# a generation bug or stale accumulation.
DIR_FILE_THRESHOLD = 100         # Max files in a single directory before alert
RAG_DIR_FILE_THRESHOLD = 1000    # RAG index dirs hold many entries by design;
                                 # corpus-mirroring dirs (e.g. adrs/ is 1:1 with
                                 # 572+ ADRs) legitimately sit in the hundreds
TIMESTAMP_RATIO_THRESHOLD = 0.3  # If >30% of files are timestamp-named, flag it
DUPLICATE_SAMPLE_SIZE = 50       # Files to sample for duplicate detection at d1
RAG_CATEGORY_THRESHOLD = 5000    # RAG index category with >5k entries is suspicious

# RAG index subdirectories that are structural (chunks, indexes) — skip entirely
_RAG_SKIP_PARTS = {"chunks", "cache", "projects"}

# Pattern: filenames that are purely numeric (epoch millis or similar)
_TIMESTAMP_PATTERN = re.compile(r"^\d{10,16}$")


def _is_timestamp_name(stem: str) -> bool:
    """Check if a filename stem looks like a timestamp (10-16 digits)."""
    return bool(_TIMESTAMP_PATTERN.match(stem))


def _get_scan_dirs() -> list[tuple[str, Path]]:
    """Return (label, path) pairs for directories to monitor."""
    from src.config.paths import get_vault_dir, get_rag_dir

    dirs: list[tuple[str, Path]] = []
    try:
        vault = get_vault_dir()
        if vault.is_dir():
            dirs.append(("vault", vault))
    except Exception:
        pass
    try:
        rag = get_rag_dir()
        if rag.is_dir():
            dirs.append(("rag-index", rag))
    except Exception:
        pass
    return dirs


def _scan_directory_sizes(root: Path, label: str) -> list[dict]:
    """Scan for directories with abnormally high file counts."""
    issues = []
    if not root.is_dir():
        return issues

    for subdir in sorted(root.rglob("*")):
        if not subdir.is_dir():
            continue
        # Only check leaf-ish directories (not root itself)
        try:
            rel = subdir.relative_to(root)
        except ValueError:
            continue
        if str(rel) in (".", ".git", "__pycache__"):
            continue
        # Skip .git internals
        if ".git" in rel.parts:
            continue
        # Skip RAG structural subdirs (chunks are expected to be large)
        if label == "rag-index" and _RAG_SKIP_PARTS & set(rel.parts):
            continue

        # Count direct children files (not recursive, to avoid double-counting)
        files = [f for f in subdir.iterdir() if f.is_file()]
        file_count = len(files)

        # RAG index dirs use a higher threshold — they hold many entries by design
        threshold = RAG_DIR_FILE_THRESHOLD if label == "rag-index" else DIR_FILE_THRESHOLD
        if file_count < threshold:
            continue

        # Check for timestamp-named files
        ts_count = sum(1 for f in files if _is_timestamp_name(f.stem))
        ts_ratio = ts_count / file_count if file_count > 0 else 0

        severity = "error" if file_count > 5000 else "warning"
        detail = f"{label}/{rel}: {file_count:,} files"
        if ts_ratio > TIMESTAMP_RATIO_THRESHOLD:
            detail += f" ({ts_count:,} timestamp-named = {ts_ratio:.0%} — likely stamming bug)"

        issues.append(make_issue(
            category="file-growth",
            detail=detail,
            path=str(subdir),
            kind="actionable",
            severity=severity,
            root_cause_type="code_defect" if ts_ratio > TIMESTAMP_RATIO_THRESHOLD else "unknown",
            fixability="manual",
            file_count=file_count,
            timestamp_count=ts_count,
            timestamp_ratio=round(ts_ratio, 2),
        ))

    return issues


def _scan_duplicate_content(root: Path, label: str, sample_size: int = 0) -> list[dict]:
    """Detect directories where many files have identical content."""
    issues = []
    if not root.is_dir():
        return issues

    for subdir in sorted(root.rglob("*")):
        if not subdir.is_dir() or ".git" in subdir.parts:
            continue

        files = [f for f in subdir.iterdir() if f.is_file() and f.suffix == ".md"]
        if len(files) < 10:
            continue

        # Sample or scan all
        check_files = files[:sample_size] if sample_size > 0 else files

        content_hashes: dict[str, list[str]] = {}
        for f in check_files:
            try:
                h = hashlib.md5(f.read_bytes(), usedforsecurity=False).hexdigest()
                content_hashes.setdefault(h, []).append(f.name)
            except Exception:
                continue

        # Find hashes with many duplicates
        for h, names in content_hashes.items():
            if len(names) >= 5:
                try:
                    rel = subdir.relative_to(root)
                except ValueError:
                    rel = subdir
                issues.append(make_issue(
                    category="duplicate-content",
                    detail=(
                        f"{label}/{rel}: {len(names)} files with identical content "
                        f"(sampled {len(check_files)} of {len(files)})"
                    ),
                    path=str(subdir),
                    kind="actionable",
                    severity="warning",
                    root_cause_type="code_defect",
                    fixability="auto",
                    duplicate_count=len(names),
                    total_files=len(files),
                ))
                break  # One issue per directory is enough

    return issues


def _scan_rag_index_sizes(rag_dir: Path) -> list[dict]:
    """Check RAG index categories for abnormally high entry counts."""
    issues = []
    if not rag_dir.is_dir():
        return issues

    for cat_dir in sorted(rag_dir.iterdir()):
        if not cat_dir.is_dir() or cat_dir.name.startswith("_"):
            continue
        if cat_dir.name in ("chunks", "cache", "projects"):
            continue

        count = sum(1 for _ in cat_dir.rglob("*.md"))
        if count > RAG_CATEGORY_THRESHOLD:
            issues.append(make_issue(
                category="rag-index-growth",
                detail=f"RAG category '{cat_dir.name}' has {count:,} entries (threshold: {RAG_CATEGORY_THRESHOLD:,})",
                path=str(cat_dir),
                kind="actionable",
                severity="warning",
                root_cause_type="unknown",
                fixability="manual",
                entry_count=count,
            ))

    return issues


def _default_client_memory_sources(project_root: Path) -> dict[str, Path]:
    skills_dir = Path(__file__).resolve().parents[2]
    ops_dir = skills_dir / "ai" / "scripts" / "ops"
    if str(ops_dir) not in sys.path:
        sys.path.insert(0, str(ops_dir))
    from memory_assembler import resolve_default_client_memory_plan

    plan = resolve_default_client_memory_plan(project_root=project_root)
    return dict(plan["sources"])


def _scan_stale_memory_entries(
    vault: Path,
    *,
    client_sources: dict[str, Path] | None = None,
    project_root: Path | None = None,
) -> list[dict]:
    """Detect assembled memory entries whose source no longer exists."""
    entries_dir = brain_knowledge_dir(vault) / "memory" / "entries"
    if not entries_dir.is_dir():
        # Pre-ADR-771 flat layout (non-migrated vaults).
        entries_dir = vault / "memory" / "entries"
    if not entries_dir.is_dir():
        return []

    if client_sources is None:
        client_sources = _default_client_memory_sources(project_root or Path.cwd())

    ignored_names = {"MEMORY.md", "augur-memory.md", "stale-entries-report.md"}
    source_files_by_client: dict[str, set[str]] = {}
    for client, source_dir in client_sources.items():
        if not source_dir.is_dir():
            continue
        source_files_by_client[client] = {
            f.name for f in source_dir.iterdir()
            if f.is_file() and f.suffix == ".md" and f.name not in ignored_names
        }

    if not source_files_by_client:
        return []

    stale: list[Path] = []
    for f in entries_dir.iterdir():
        if not f.is_file():
            continue
        for client, source_names in source_files_by_client.items():
            prefix = f"{client}_"
            if not f.name.startswith(prefix):
                continue
            source_name = f.name.replace(prefix, "", 1)
            if source_name not in source_names:
                stale.append(f)
            break

    if not stale:
        return []

    return [make_issue(
        category="stale-memory",
        detail=f"memory/entries: {len(stale)} assembled entries with no source",
        path=str(entries_dir),
        kind="maintenance",
        root_cause_type="stale_accumulation",
        fixability="auto",
        stale_count=len(stale),
        stale_files=sorted(f.name for f in stale),
    )]


def _scan_superseded_adrs(vault: Path) -> list[dict]:
    """Detect superseded/deprecated ADRs that should be archived."""
    from src.config.paths import get_adr_dir
    adrs_dir = get_adr_dir()
    if not adrs_dir.is_dir():
        return []

    superseded: list[str] = []

    # ADR-642: read live entries with archivable status from the central index.
    try:
        from src.lib.adr_utils import load_adrs_index

        for record in load_adrs_index(adrs_dir):
            if record.get("state") != "live":
                continue
            status = str(record.get("status", "")).strip()
            if status in ("Superseded", "Deprecated", "Cancelled"):
                superseded.append(str(record.get("adr_number", "")))
    except Exception:
        pass

    # Fallback: legacy on-disk ADR-*.md files.
    for f in sorted(adrs_dir.glob("ADR-*.md")):
        try:
            head = f.read_text(encoding="utf-8")[:500]
        except Exception:
            continue
        for line in head.splitlines():
            if line.startswith("status:"):
                status = line.split(":", 1)[1].strip()
                if status in ("Superseded", "Deprecated", "Cancelled"):
                    superseded.append(f.name)
                break

    if not superseded:
        return []

    return [make_issue(
        category="superseded-adrs",
        detail=f"adrs: {len(superseded)} superseded/deprecated ADRs should be archived",
        path=str(adrs_dir),
        kind="maintenance",
        root_cause_type="stale_accumulation",
        fixability="auto",
        count=len(superseded),
        files=superseded,
    )]


# ── Protocol ──────────────────────────────────────────────────────────


def scan(ctx: OpsContext) -> ScanResult:
    """Scan for runaway file generation patterns."""
    issues: list[dict] = []
    scan_dirs = _get_scan_dirs()
    items_scanned = 0

    # d0: Directory size + timestamp pattern detection
    for label, root in scan_dirs:
        dir_issues = _scan_directory_sizes(root, label)
        issues.extend(dir_issues)
        items_scanned += 1

    # d0: Stale memory entries and superseded ADR accumulation
    for label, root in scan_dirs:
        if label == "vault":
            issues.extend(_scan_stale_memory_entries(root, project_root=ctx.project_root))
            issues.extend(_scan_superseded_adrs(root))

    # d1: Sample-based duplicate detection + RAG index sizes
    if ctx.difficulty >= 1:
        for label, root in scan_dirs:
            dup_issues = _scan_duplicate_content(root, label, sample_size=DUPLICATE_SAMPLE_SIZE)
            issues.extend(dup_issues)

        # Check RAG index sizes
        try:
            from src.config.paths import get_rag_dir
            rag_dir = get_rag_dir()
            rag_issues = _scan_rag_index_sizes(rag_dir)
            issues.extend(rag_issues)
        except Exception:
            pass

    # d2: Full duplicate scan (no sampling)
    if ctx.difficulty >= 2:
        for label, root in scan_dirs:
            full_dup_issues = _scan_duplicate_content(root, label, sample_size=0)
            # Only add issues not already found at d1
            existing_paths = {i["path"] for i in issues}
            for issue in full_dup_issues:
                if issue["path"] not in existing_paths:
                    issues.append(issue)

    # d4: Evolution gaps
    if ctx.difficulty >= 4 and not issues:
        issues.append(evolution_gap(
            "All file growth checks pass — consider adding: growth rate trending "
            "via persisted baselines, cross-session file creation rate monitoring, "
            "and alerting on MCP tool write frequency anomalies",
            category="file-growth",
        ))

    severity = "error" if any(i.get("severity") == "error" for i in issues) else (
        "warning" if issues else "info"
    )
    health = "broken" if severity == "error" else ("degraded" if issues else "verified")

    summary = f"Scanned {len(scan_dirs)} data directories"
    if issues:
        summary += f" — found {len(issues)} growth issue(s)"
    else:
        summary += " — no abnormal growth detected"

    return ScanResult(
        issues=issues,
        summary=summary,
        severity=severity,
        health=health,
        items_scanned=items_scanned,
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Auto-clean duplicate files and timestamp-spam at d1+, report-only at d0.

    Difficulty escalation:
      d0: Report only — write findings without removing anything
      d1+: Auto-remove duplicate-content files (keep oldest, delete rest)
      d2+: Also archive timestamp-spam files (move to _archive/ subdir)
    """
    if ctx.dry_run:
        return FixResult(
            success=True,
            summary=f"Dry run: {len(issues)} growth issue(s) to investigate",
        )

    if ctx.difficulty < 1:
        return report_only_fix(ctx, "file-growth", issues, noun="growth issue")

    actions: list[dict] = []
    changes: list[str] = []
    total_removed = 0

    for issue in issues:
        category = issue.get("category", "")
        target_dir = Path(issue.get("path", ""))

        if not target_dir.is_dir():
            continue

        # --- Duplicate content cleanup (d1+) ---
        if category == "duplicate-content":
            removed = _fix_duplicates(target_dir)
            if removed:
                total_removed += len(removed)
                changes.extend(removed)
                actions.append({
                    "action": "remove-duplicates",
                    "dir": str(target_dir),
                    "removed_count": len(removed),
                })

        # --- Timestamp-spam cleanup (d2+) ---
        elif category == "file-growth" and ctx.difficulty >= 2:
            ts_ratio = issue.get("timestamp_ratio", 0)
            if ts_ratio > TIMESTAMP_RATIO_THRESHOLD:
                archived = _fix_timestamp_spam(target_dir)
                if archived:
                    total_removed += len(archived)
                    changes.extend(archived)
                    actions.append({
                        "action": "archive-timestamp-spam",
                        "dir": str(target_dir),
                        "archived_count": len(archived),
                    })

        # --- Stale memory cleanup (d1+) ---
        elif category == "stale-memory":
            stale_files = issue.get("stale_files", [])
            removed_count = 0
            for fname in stale_files:
                fpath = target_dir / fname
                if fpath.exists():
                    try:
                        fpath.unlink()
                        removed_count += 1
                        logger.info("Removed stale memory entry: %s", fname)
                    except OSError:
                        pass
            if removed_count:
                total_removed += removed_count
                actions.append({
                    "action": "remove-stale-memory",
                    "removed_count": removed_count,
                })

        # --- Archive superseded ADRs (d1+) ---
        elif category == "superseded-adrs":
            archive_dir = target_dir / "_archived"
            archive_dir.mkdir(exist_ok=True)
            archived_files = issue.get("files", [])
            archived_count = 0
            for fname in archived_files:
                src = target_dir / fname
                if src.exists():
                    try:
                        src.rename(archive_dir / fname)
                        archived_count += 1
                        logger.info("Archived superseded ADR: %s", fname)
                    except OSError:
                        pass
            if archived_count:
                total_removed += archived_count
                actions.append({
                    "action": "archive-superseded-adrs",
                    "archived_count": archived_count,
                })

    # Write report for all actions
    if actions or issues:
        report_data = {
            "issues": [_sanitize_issue(i) for i in issues],
            "actions": actions,
            "total_removed": total_removed,
        }
        report_path = write_report(ctx, "file-growth-latest.json", report_data)
        actions.append({"report": str(report_path)})

    if total_removed > 0:
        summary = f"Removed {total_removed} redundant file(s) across {len([a for a in actions if 'action' in a])} director(ies)"
        fix_type = "code-fix"
    else:
        summary = f"Scanned {len(issues)} growth issue(s), no auto-fixable items at d{ctx.difficulty}"
        fix_type = "report"

    return FixResult(
        success=True,
        actions=actions,
        changes=changes,
        summary=summary,
        fix_type=fix_type,
    )


def _sanitize_issue(issue: dict) -> dict:
    """Remove non-serializable fields from issue for JSON report."""
    return {k: v for k, v in issue.items() if isinstance(v, (str, int, float, bool, list, dict, type(None)))}


def _fix_duplicates(target_dir: Path) -> list[str]:
    """Remove duplicate-content .md files, keeping the oldest by mtime."""
    files = [f for f in target_dir.iterdir() if f.is_file() and f.suffix == ".md"]
    if len(files) < 10:
        return []

    # Group by content hash
    content_groups: dict[str, list[Path]] = {}
    for f in files:
        try:
            h = hashlib.md5(f.read_bytes(), usedforsecurity=False).hexdigest()
            content_groups.setdefault(h, []).append(f)
        except Exception:
            continue

    removed: list[str] = []
    for h, group in content_groups.items():
        if len(group) < 5:
            continue
        # Sort by mtime ascending — keep the oldest
        group.sort(key=lambda p: p.stat().st_mtime)
        for dup in group[1:]:
            try:
                dup.unlink()
                removed.append(str(dup))
                logger.info("Removed duplicate: %s", dup)
            except OSError as e:
                logger.warning("Failed to remove %s: %s", dup, e)

    return removed


def _fix_timestamp_spam(target_dir: Path) -> list[str]:
    """Archive timestamp-named files to _archive/ subdir, keeping the 20 most recent."""
    files = [f for f in target_dir.iterdir() if f.is_file()]
    ts_files = [f for f in files if _is_timestamp_name(f.stem)]

    if len(ts_files) < DIR_FILE_THRESHOLD:
        return []

    # Keep the 20 most recent timestamp files, archive the rest
    ts_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    keep = 20
    to_archive = ts_files[keep:]

    if not to_archive:
        return []

    archive_dir = target_dir / "_archive"
    archive_dir.mkdir(exist_ok=True)

    archived: list[str] = []
    for f in to_archive:
        dest = archive_dir / f.name
        try:
            f.rename(dest)
            archived.append(str(f))
            logger.info("Archived timestamp-spam: %s -> %s", f, dest)
        except OSError as e:
            logger.warning("Failed to archive %s: %s", f, e)

    return archived
