#!/usr/bin/env python3
"""
Sync backlog items to GitHub Issues.

Targets self-improvement and data-scientist log derived tasks and keeps
GitHub issues aligned with local backlog status.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path
from subprocess import CompletedProcess, run  # nosec B404
from typing import Any

import yaml

# Path: project-brain/capabilities/skills/platform-admin/scripts/sync_backlog_to_github.py
# Go up 4 levels to reach project root
from bootstrap_paths import ensure_project_paths  # noqa: E402

PROJECT_ROOT = ensure_project_paths(__file__)


def _resolve_command(command: list[str]) -> list[str]:
    """Resolve executable path to absolute when available."""
    if not command:
        raise ValueError("Command must not be empty")

    executable = command[0]
    if Path(executable).is_absolute():
        return command

    resolved = shutil.which(executable)
    if not resolved:
        return command

    return [resolved, *command[1:]]


def _run_command(command: list[str], **kwargs: object) -> CompletedProcess:
    """Run subprocess command with resolved executable."""
    return run(_resolve_command(command), **kwargs)  # nosec B603


def _resolve_user_data_base() -> Path:
    env = os.environ.get("AUGUR_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    try:
        from src.config.paths import get_project_root  # type: ignore

        return get_project_root()
    except Exception:
        return get_project_root()


def _load_sync_config(data_dir: Path) -> dict[str, Any]:
    config_path = data_dir / "config" / "bug_sync.yaml"
    if not config_path.exists():
        return {}
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        return raw.get("bug_sync", {}) if isinstance(raw, dict) else {}
    except Exception:
        return {}


def _sync_enabled(cfg: dict[str, Any]) -> bool:
    env = os.environ.get("AUGUR_GITHUB_SYNC")
    if env is not None:
        return env.strip().lower() in {"1", "true", "yes", "on"}
    return bool(cfg.get("enabled"))


def _resolve_repo(cfg: dict[str, Any]) -> str:
    env_repo = os.environ.get("AUGUR_GITHUB_REPO")
    if env_repo:
        return env_repo.strip()
    repo = str(cfg.get("github_repo", "") or "").strip()
    if repo:
        return repo
    return "augur-os/augur-os"


def _parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            frontmatter = yaml.safe_load(parts[1]) or {}
            return frontmatter, parts[2].strip()
    return {}, content


def _extract_title(body: str, fallback: str) -> str:
    match = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return fallback


def _extract_objective(body: str) -> str:
    match = re.search(r"##\s+Objective\s*\n(.*?)(?=\n##|\Z)", body, re.DOTALL | re.IGNORECASE)
    if not match:
        return ""
    return match.group(1).strip()


def _iter_tasks(backlog_dir: Path):
    if not backlog_dir.exists():
        return
    for task_file in backlog_dir.rglob("*.md"):
        if task_file.name == "EPIC.md":
            continue
        content = None
        try:
            content = task_file.read_text(encoding="utf-8")
        except Exception:
            content = None
        if content is None:
            continue
        frontmatter, body = _parse_frontmatter(content)
        yield task_file, frontmatter, body


def _is_closed(frontmatter: dict[str, Any]) -> bool:
    status = str(frontmatter.get("status", "")).lower()
    if status in {"done", "completed", "resolved", "closed"}:
        return True
    execution = frontmatter.get("execution") or {}
    exec_status = str(execution.get("status", "")).lower()
    return exec_status in {"done", "completed", "resolved", "closed"}


def _priority_label(priority: str) -> str | None:
    value = priority.lower()
    if "p0" in value or "critical" in value:
        return "p0"
    if "p1" in value or "high" in value:
        return "p1"
    if "p2" in value or "medium" in value:
        return "p2"
    if "p3" in value or "low" in value:
        return "p3"
    return None


def _type_label(task_type: str) -> str:
    mapping = {
        "feature": "type:feature",
        "refactor": "type:refactor",
        "research": "type:research",
        "bugfix": "type:bugfix",
        "skill-update": "type:skill-update",
    }
    return mapping.get(task_type, "type:unknown")


LABEL_COLORS = {
    "backlog": "1d76db",
    "self-improvement": "6f42c1",
    "data-scientist": "0e8a16",
    "type:feature": "0e8a16",
    "type:refactor": "fbca04",
    "type:research": "c5def5",
    "type:bugfix": "d73a4a",
    "type:skill-update": "5319e7",
    "type:unknown": "9e9e9e",
    "p0": "d73a4a",
    "p1": "e99695",
    "p2": "f9d0c4",
    "p3": "c2e0c6",
}


def _ensure_labels(repo: str, labels: list[str]) -> None:
    for label in labels:
        color = LABEL_COLORS.get(label, "ededed")
        _run_command(
            ["gh", "label", "create", label, "--repo", repo, "--color", color],
            capture_output=True,
            text=True,
        )


def _get_issue_by_id(repo: str, task_id: str) -> dict[str, Any] | None:
    try:
        result = _run_command(
            ["gh", "issue", "list", "--repo", repo, "--search", f'"{task_id}"', "--json", "url,number,state"],
            capture_output=True,
            text=True,
            check=True,
        )
        issues = json.loads(result.stdout)
        if issues:
            return issues[0]
    except Exception:
        return None
    return None


def _create_issue(repo: str, title: str, body: str, labels: list[str]) -> str | None:
    cmd = ["gh", "issue", "create", "--repo", repo, "--title", title, "--body", body]
    for label in labels:
        cmd.extend(["--label", label])
    try:
        result = _run_command(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except Exception:
        return None


def _close_issue(repo: str, number: int, comment: str) -> None:
    _run_command(
        ["gh", "issue", "close", str(number), "--repo", repo, "--comment", comment],
        capture_output=True,
        text=True,
    )


def _write_task(path: Path, frontmatter: dict[str, Any], body: str) -> None:
    yaml_block = yaml.safe_dump(frontmatter, sort_keys=False).strip()
    path.write_text(f"---\n{yaml_block}\n---\n\n{body}\n", encoding="utf-8")


def sync_backlog(
    backlog_dir: Path,
    sources: list[str],
    repo: str,
    auto_close: bool = True,
) -> dict[str, int]:
    created = 0
    linked = 0
    closed = 0

    for path, frontmatter, body in _iter_tasks(backlog_dir):
        source = str(frontmatter.get("source", "")).lower()
        if not any(token in source for token in sources):
            continue

        task_id = str(frontmatter.get("id") or path.stem)
        task_type = str(frontmatter.get("type", "unknown")).lower()
        priority = str(frontmatter.get("priority", "medium"))
        title = str(frontmatter.get("title") or _extract_title(body, task_id))
        objective = _extract_objective(body)
        status = str(frontmatter.get("status", ""))

        source_label = "self-improvement" if "self-improvement" in source else "data-scientist"
        labels = ["backlog", source_label, _type_label(task_type)]
        priority_label = _priority_label(priority)
        if priority_label:
            labels.append(priority_label)

        github_url = frontmatter.get("github_url")
        issue_info = _get_issue_by_id(repo, task_id)

        if not github_url:
            if issue_info:
                frontmatter["github_url"] = issue_info["url"]
                _write_task(path, frontmatter, body)
                linked += 1
            else:
                _ensure_labels(repo, labels)
                issue_title = f"[{task_id}] {task_type.title()}: {title}"
                issue_body = f"""### Objective
{objective or "No objective provided."}

### Metadata
- **ID**: {task_id}
- **Type**: {task_type}
- **Priority**: {priority}
- **Status**: {status}
- **Source**: {frontmatter.get("source", "")}
- **Path**: {path}
- **Created**: {frontmatter.get("created", "")}

---
*Automatically synced from Augur backlog.*
"""
                created_url = _create_issue(repo, issue_title, issue_body, labels)
                if created_url:
                    frontmatter["github_url"] = created_url
                    _write_task(path, frontmatter, body)
                    created += 1

        if auto_close and _is_closed(frontmatter):
            issue_info = issue_info or _get_issue_by_id(repo, task_id)
            if issue_info and issue_info.get("state") == "OPEN":
                _close_issue(repo, issue_info["number"], "Resolved in Augur backlog.")
                closed += 1

    return {"created": created, "linked": linked, "closed": closed}


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync backlog tasks to GitHub Issues.")
    parser.add_argument(
        "--backlog-dir",
        type=Path,
        help="Backlog directory (default: <AUGUR_ROOT>/agent-tasks/backlog)",
    )
    parser.add_argument(
        "--sources",
        default="self-improvement,data-scientist",
        help="Comma-separated source tokens to sync (default: self-improvement,data-scientist)",
    )
    parser.add_argument(
        "--no-close",
        action="store_true",
        help="Do not auto-close GitHub issues when backlog is resolved",
    )

    args = parser.parse_args()

    data_dir = _resolve_user_data_base()
    cfg = _load_sync_config(data_dir)
    if not _sync_enabled(cfg):
        sys.stdout.write("GitHub sync disabled (config/bug_sync.yaml).\n")
        return 0

    repo = _resolve_repo(cfg)
    backlog_dir = args.backlog_dir or (data_dir / "agent-tasks" / "backlog")
    sources = [s.strip().lower() for s in args.sources.split(",") if s.strip()]

    if not shutil.which("gh"):
        sys.stdout.write("GitHub CLI (gh) not found; skipping sync.\n")
        return 1

    stats = sync_backlog(backlog_dir, sources, repo, auto_close=not args.no_close)
    sys.stdout.write(
        f"Synced backlog -> GitHub: created={stats['created']} linked={stats['linked']} closed={stats['closed']}\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
