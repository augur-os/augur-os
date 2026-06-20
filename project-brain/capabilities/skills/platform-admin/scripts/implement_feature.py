"""
Implement Feature Workflow - DevOps Agent

Reads a task file, loads codebase context, modifies code, and runs tests.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from subprocess import CompletedProcess, run as subprocess_run  # nosec B404
from typing import Any

# Add project root to path for imports
from bootstrap_paths import ensure_project_paths  # noqa: E402

PROJECT_ROOT = ensure_project_paths(__file__)

from src.config.paths import get_project_root

logger = logging.getLogger(__name__)


def _resolve_command(command: list[str]) -> list[str]:
    """Resolve command executable to absolute path when available."""
    if not command:
        return command
    resolved = shutil.which(command[0])
    if resolved:
        return [resolved, *command[1:]]
    return command


def _run_command(command: list[str], cwd: Path, **kwargs: Any) -> CompletedProcess[str]:
    """Run subprocess command with resolved executable path."""
    return subprocess_run(_resolve_command(command), cwd=str(cwd), **kwargs)  # nosec B603


# Import feature_machine utilities from parent directory
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))
try:
    from feature_machine import (
        _read_task,
        _resolve_task_path,
        _run,
        _run_shell,
        _extract_section,
        _extract_test_commands,
        _write_task,
        _utc_now,
        _load_config,
        _resolve_user_data_base,
    )
except ImportError:
    # Fallback implementations
    import yaml
    from datetime import datetime, timezone

    def _read_task(path: Path) -> tuple[dict, str]:
        content = path.read_text(encoding="utf-8")
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                frontmatter = yaml.safe_load(parts[1]) or {}
                body = parts[2].lstrip("\n")
                return frontmatter, body
        return {}, content

    def _resolve_task_path(task_path: str | None, task_id: str | None) -> tuple[Path | None, dict | None]:
        if task_path:
            return Path(task_path), None
        if not task_id:
            return None, {"error": "Missing task path or id"}
        # Simplified - would need full implementation
        return None, {"error": "Task resolution not fully implemented"}

    def _run(cmd: list[str], cwd: Path) -> tuple[int, str, str]:
        proc = _run_command(cmd, cwd, capture_output=True, text=True)
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()

    def _run_shell(command: str, cwd: Path) -> tuple[int, str, str]:
        proc = subprocess_run(command, cwd=str(cwd), capture_output=True, text=True, shell=True)  # nosec B602
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()

    def _extract_section(body: str, header: str) -> str:
        lines = body.splitlines()
        start = None
        for idx, line in enumerate(lines):
            if line.strip() == f"## {header}":
                start = idx + 1
                break
        if start is None:
            return ""
        end = len(lines)
        for idx in range(start, len(lines)):
            if lines[idx].startswith("## "):
                end = idx
                break
        return "\n".join(lines[start:end]).strip()

    def _extract_test_commands(body: str) -> list[str]:
        import re

        commands = []
        for match in re.findall(r"`([^`]+)`", body):
            candidate = match.strip()
            if any(candidate.startswith(prefix) for prefix in ("pytest", "uv ", "npm ", "python ")):
                commands.append(candidate)
        return list(dict.fromkeys(commands))

    def _write_task(path: Path, frontmatter: dict, body: str) -> None:
        yaml_block = yaml.safe_dump(frontmatter, sort_keys=False).strip()
        content = f"---\n{yaml_block}\n---\n\n{body.lstrip()}"
        path.write_text(content, encoding="utf-8")

    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _load_config():
        class Config:
            test_commands = []

        return Config()

    def _resolve_user_data_base() -> Path:
        env = os.environ.get("AUGUR_ROOT")
        if env:
            return Path(env).expanduser().resolve()
        return get_project_root()


def _project_root() -> Path:
    return PROJECT_ROOT


def _git_repo_root() -> Path:
    return _project_root()


def _extract_file_paths(text: str) -> list[str]:
    """Extract file paths mentioned in task text."""
    import re

    # Patterns for file paths
    patterns = [
        r'`([^`]+\.(py|md|yaml|yml|ts|tsx|js|jsx))`',  # Code blocks
        r'([a-zA-Z0-9_/-]+\.(py|md|yaml|yml|ts|tsx|js|jsx))',  # Plain file names
        r'plugins/[^\s]+',  # Package paths
        r'src/[^\s]+',  # Src paths
    ]

    files = set()
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            if isinstance(match, tuple):
                file_path = match[0] if match[0] else match
            else:
                file_path = match
            # Normalize path
            if file_path.startswith('plugins/') or file_path.startswith('src/'):
                files.add(file_path)

    return sorted(files)


def _grep_search(pattern: str, workspace: Path) -> list[str]:
    """Search for pattern in codebase."""
    try:
        # Use ripgrep if available, otherwise grep
        cmd = ["rg", "-l", pattern, str(workspace)]
        code, out, err = _run(cmd, workspace)
        if code == 0 and out:
            return [line.strip() for line in out.splitlines() if line.strip()]
    except Exception as exc:
        logger.debug("ripgrep search failed for pattern %r: %s", pattern, exc)

    # Fallback to grep
    try:
        cmd = ["grep", "-rl", pattern, str(workspace)]
        code, out, err = _run(cmd, workspace)
        if code == 0 and out:
            return [line.strip() for line in out.splitlines() if line.strip()]
    except Exception as exc:
        logger.debug("grep fallback failed for pattern %r: %s", pattern, exc)

    return []


def _view_file(file_path: str, workspace: Path) -> str:
    """Read file content."""
    full_path = workspace / file_path if not Path(file_path).is_absolute() else Path(file_path)
    if full_path.exists():
        return full_path.read_text(encoding="utf-8")
    return ""


def _load_codebase_context(task_body: str, workspace: Path) -> dict[str, Any]:
    """Load relevant codebase context for the task."""
    context = {
        "files": [],
        "grep_results": {},
        "dependencies": [],
    }

    # Extract file paths from task
    mentioned_files = _extract_file_paths(task_body)
    for file_path in mentioned_files:
        content = _view_file(file_path, workspace)
        if content:
            context["files"].append(
                {
                    "path": file_path,
                    "content": content[:5000],  # Limit size
                }
            )

    # Search for key terms
    key_terms = _extract_key_terms(task_body)
    for term in key_terms[:5]:  # Limit to 5 searches
        matches = _grep_search(term, workspace)
        if matches:
            context["grep_results"][term] = matches[:10]  # Limit results

    return context


def _extract_key_terms(text: str) -> list[str]:
    """Extract key technical terms from task text."""
    import re

    # Look for function names, class names, technical terms
    patterns = [
        r'\b([A-Z][a-zA-Z0-9]+)\b',  # Class names
        r'def\s+([a-z_][a-zA-Z0-9_]+)',  # Function names
        r'([a-z_][a-zA-Z0-9_]+)\s*\(',  # Function calls
    ]

    terms = set()
    for pattern in patterns:
        matches = re.findall(pattern, text)
        terms.update(matches)

    return sorted(terms)[:10]  # Return top 10


def implement_feature(params: dict) -> str:
    """
    Implement a feature from a task file.

    Args:
        params: Dictionary with:
            - task_id: Task identifier
            - task_path: Optional direct path to task file
            - plan: Optional plan text to create an ad-hoc task
            - user_request: Optional original user request for context
            - dry_run: If True, don't modify files

    Returns:
        JSON string with result
    """
    task_id = params.get("task_id")
    task_path = params.get("task_path")
    plan = params.get("plan")
    dry_run = params.get("dry_run", False)

    user_request = params.get("user_request")
    if not user_request:
        context = params.get("context")
        if context:
            try:
                parsed = json.loads(context)
                user_request = parsed.get("user_request")
            except Exception:
                user_request = None

    if not task_id and not task_path and plan:
        return json.dumps({"error": "Plan-to-backlog task creation has been removed (ADR-261). Provide a task_id or task_path instead."}, indent=2)

    # Resolve task path
    path, error = _resolve_task_path(task_path, task_id)
    if error:
        return json.dumps(error, indent=2)

    if not path or not path.exists():
        return json.dumps({"error": f"Task not found: {path}"}, indent=2)

    # Read task
    frontmatter, body = _read_task(path)
    workspace_str = frontmatter.get("workspace", str(_project_root()))
    workspace = Path(workspace_str).expanduser().resolve()

    # Extract requirements
    requirements = _extract_section(body, "Requirements") or _extract_section(body, "## Requirements")
    acceptance_criteria = _extract_section(body, "Acceptance Criteria") or _extract_section(
        body, "## Acceptance Criteria"
    )

    if not requirements and not acceptance_criteria:
        return json.dumps(
            {
                "error": "Task missing requirements or acceptance criteria",
                "task_path": str(path),
            },
            indent=2,
        )

    # Load codebase context
    context = _load_codebase_context(body, workspace)

    # Extract test commands
    config = _load_config()
    test_commands = _extract_test_commands(body) or config.test_commands

    result = {
        "task_id": frontmatter.get("id") or path.stem,
        "task_path": str(path),
        "workspace": str(workspace),
        "requirements_found": bool(requirements),
        "acceptance_criteria_found": bool(acceptance_criteria),
        "context": {
            "files_loaded": len(context["files"]),
            "grep_searches": len(context["grep_results"]),
        },
        "test_commands": test_commands,
        "dry_run": dry_run,
        "message": "Feature implementation workflow ready. Code modifications should be made by the agent using the context provided.",
    }

    if dry_run:
        result["message"] = "DRY RUN: No files modified"

    return json.dumps(result, indent=2)


def main(params: dict = {}) -> str:
    """Main entry point for MCP tool."""
    return implement_feature(params)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Implement a feature from a task file")
    parser.add_argument("--task_id", type=str, help="Task identifier")
    parser.add_argument("--task_path", type=str, help="Path to task file")
    parser.add_argument("--plan", type=str, help="Plan text for ad-hoc tasks")
    parser.add_argument("--user_request", type=str, help="Original user request")
    parser.add_argument("--context", type=str, help="Optional JSON context")
    parser.add_argument("--dry_run", action="store_true", help="Do not modify files")
    args, unknown = parser.parse_known_args()

    params = {k: v for k, v in vars(args).items() if v not in (None, False)}
    for arg in unknown:
        if "=" in arg:
            key, value = arg.split("=", 1)
            params[key.lstrip("-")] = value

    sys.stdout.write(f"{main(params)}\n")
