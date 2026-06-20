#!/usr/bin/env python3
"""
Night Shift Context Aggregator for Augur.

Aggregates daily context for handoff to next session:
- Recent git activity
- Backlog status
- Skill health
- Session notes
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
import json
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path
from subprocess import CompletedProcess, run as subprocess_run  # nosec B404
from typing import Any

from src.config.paths import get_project_root


def _resolve_command(command: list[str]) -> list[str]:
    if not command:
        return command
    resolved = shutil.which(command[0])
    if resolved:
        return [resolved, *command[1:]]
    return command


def _run_command(command: list[str], **kwargs: object) -> CompletedProcess[str]:
    return subprocess_run(_resolve_command(command), **kwargs)  # nosec B603


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════


def get_repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in [current] + list(current.parents):
        if (parent / ".git").exists():
            return parent
    return Path.cwd()


def get_data_dir() -> Path:
    paths = [
        get_project_root(),
        get_project_root(),
    ]
    for p in paths:
        if p.exists():
            return p
    return paths[0]


def run_git(repo: Path, args: list[str]) -> str:
    try:
        result = _run_command(["git", *args], cwd=str(repo), capture_output=True, text=True, timeout=30)
        return result.stdout.strip()
    except Exception:
        return ""


# ═══════════════════════════════════════════════════════════════════════════════
# CONTEXT COLLECTORS
# ═══════════════════════════════════════════════════════════════════════════════


def collect_git_activity(repo: Path, since_hours: int = 24) -> dict[str, Any]:
    """Collect recent git activity."""
    since = (datetime.now() - timedelta(hours=since_hours)).strftime("%Y-%m-%d")

    # Recent commits
    log = run_git(repo, ["log", f"--since={since}", "--oneline", "--no-color"])
    commits = []
    for line in log.split("\n"):
        if line.strip():
            sha, _, msg = line.partition(" ")
            commits.append({"sha": sha, "message": msg})

    # Changed files
    diff_stat = run_git(repo, ["diff", "--stat", f"HEAD@{{{since_hours} hours ago}}..HEAD"])

    return {
        "commits": commits[:20],
        "commit_count": len(commits),
        "diff_stat": diff_stat[:500] if diff_stat else "",
    }


def collect_backlog_status(data_dir: Path) -> dict[str, Any]:
    """Collect backlog status across agents."""
    status = {}

    for backlog_path in data_dir.rglob("backlog.md"):
        agent = backlog_path.parent.name
        if agent == "backlogs":
            agent = backlog_path.parent.parent.name

        content = backlog_path.read_text(encoding="utf-8")

        done = content.count("- [x]")
        in_progress = content.count("- [/]")
        todo = content.count("- [ ]")

        status[agent] = {
            "done": done,
            "in_progress": in_progress,
            "todo": todo,
            "total": done + in_progress + todo,
        }

    return status


def collect_skill_health(repo_root: Path) -> dict[str, Any]:
    """Quick skill health check."""
    layers = ["factory", "horizontal", "vertical"]
    skills = {"total": 0, "with_version": 0, "layers": {}}

    for layer in layers:
        layer_path = repo_root / "plugins" / layer
        if not layer_path.exists():
            continue

        layer_skills = []
        for skill_dir in layer_path.iterdir():
            if not skill_dir.is_dir():
                continue

            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue

            skills["total"] += 1
            has_version = (skill_dir / "augur" / "version.yaml").exists()
            if has_version:
                skills["with_version"] += 1

            layer_skills.append(skill_dir.name)

        skills["layers"][layer] = layer_skills

    return skills


def collect_session_notes(data_dir: Path) -> list[str]:
    """Collect any session notes from today."""
    notes = []
    today = datetime.now().strftime("%Y-%m-%d")

    notes_dir = data_dir / "notes"
    if notes_dir.exists():
        for note_file in notes_dir.glob(f"*{today}*.md"):
            content = note_file.read_text(encoding="utf-8")
            notes.append({"file": note_file.name, "preview": content[:200]})

    return notes


# ═══════════════════════════════════════════════════════════════════════════════
# REPORT GENERATION
# ═══════════════════════════════════════════════════════════════════════════════


def generate_handoff(context: dict[str, Any]) -> str:
    """Generate Night Shift handoff report."""
    lines = [
        "# 🌙 Night Shift Context",
        "",
        f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
    ]

    # Git Activity
    git = context.get("git", {})
    lines.append("## Recent Activity")
    lines.append(f"- Commits today: {git.get('commit_count', 0)}")
    lines.append("")

    if git.get("commits"):
        lines.append("Recent commits:")
        for c in git["commits"][:10]:
            lines.append(f"- `{c['sha']}` {c['message']}")
        lines.append("")

    # Backlog Status
    backlog = context.get("backlog", {})
    if backlog:
        lines.append("## Backlog Status")
        lines.append("")
        lines.append("| Agent | Done | Todo | Progress |")
        lines.append("|-------|------|------|----------|")
        for agent, stats in backlog.items():
            total = stats.get("total", 1)
            done = stats.get("done", 0)
            pct = int(100 * done / total) if total > 0 else 0
            lines.append(f"| {agent} | {done} | {stats.get('todo', 0)} | {pct}% |")
        lines.append("")

    # Skill Health
    skills = context.get("skills", {})
    lines.append("## Skill Health")
    lines.append(f"- Total: {skills.get('total', 0)}")
    lines.append(f"- With version: {skills.get('with_version', 0)}")
    lines.append("")

    # Continuation hints
    lines.append("## Suggested Next Steps")
    lines.append("")

    for agent, stats in backlog.items():
        if stats.get("todo", 0) > 0:
            lines.append(f"- {agent}: {stats['todo']} items remaining")

    lines.append("")

    return "\n".join(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Night Shift Context Aggregator")
    parser.add_argument("--hours", type=int, default=24, help="Hours to look back")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--save", action="store_true", help="Save to file")
    args = parser.parse_args()

    repo_root = get_repo_root()
    data_dir = get_data_dir()

    _out("🌙 Aggregating Night Shift context...\n")

    context = {
        "generated_at": datetime.now().isoformat(),
        "git": collect_git_activity(repo_root, args.hours),
        "backlog": collect_backlog_status(data_dir),
        "skills": collect_skill_health(repo_root),
        "notes": collect_session_notes(data_dir),
    }

    if args.json:
        _out(json.dumps(context, indent=2))
        return 0

    report = generate_handoff(context)

    if args.save:
        output_dir = data_dir / "plugins" / "dev" / "skills" / "platform-admin" / "data" / "night-shift"
        output_dir.mkdir(parents=True, exist_ok=True)

        filename = f"handoff-{datetime.now().strftime('%Y%m%d-%H%M')}.md"
        output_path = output_dir / filename
        output_path.write_text(report, encoding="utf-8")
        _out(f"Saved to: {output_path}\n")

    _out(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
