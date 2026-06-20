
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
import os
import sys
import json
import re
import shutil
from subprocess import CalledProcessError, CompletedProcess, run as subprocess_run  # nosec B404


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


def run_gh_command(args):
    """Run a gh CLI command."""
    try:
        cmd = ["gh"] + args
        result = _run_command(cmd, capture_output=True, text=True, check=True)
        return result.stdout
    except CalledProcessError as e:
        _out(f"Error running gh command: {e}", file=sys.stderr)
        _out(f"Stderr: {e.stderr}", file=sys.stderr)
        return None


def run_git_command(args):
    """Run a git command."""
    try:
        cmd = ["git"] + args
        _run_command(cmd, check=True, capture_output=True)
        return True
    except CalledProcessError as e:
        _out(f"Error running git command: {e}", file=sys.stderr)
        return False


def get_job_logs(run_id):
    """Fetch logs for a failed run."""
    _out(f"Fetching logs for run {run_id}...", file=sys.stderr)
    jobs_json = run_gh_command(["run", "view", run_id, "--json", "jobs"])
    if not jobs_json:
        return []

    jobs = json.loads(jobs_json).get("jobs", [])
    failed_jobs = [j for j in jobs if j["conclusion"] == "failure"]

    logs = []
    for job in failed_jobs:
        job_id = str(job["databaseId"])
        _out(f"Fetching log for failed job {job['name']} ({job_id})...", file=sys.stderr)
        job_log = run_gh_command(["run", "view", run_id, "--job", job_id, "--log"])
        if job_log:
            logs.append({"name": job["name"], "log": job_log})

    return logs


def parse_traceback(log_content):
    """
    Find the likely file causing the crash.
    Look for 'File "path/to/file.py", line N'
    Return list of (file_path, line_number, error_message)
    """
    # Regex for Python tracebacks: File "/path", line 123, in module
    # We want the LAST file in the traceback that belongs to our repo (not site-plugins)

    # Simple regex to capture file paths and line numbers
    pattern = re.compile(r'File "([^"]+)", line (\d+), in')

    lines = log_content.splitlines()
    candidates = []

    for i, line in enumerate(lines):
        match = pattern.search(line)
        if match:
            fpath = match.group(1)
            lineno = match.group(2)
            # Filter out non-repo files
            if "site-plugins" not in fpath and "/usr/lib" not in fpath:
                # heuristic: prefer paths starting with plugins/ or src/lib/
                if fpath.startswith("/") and os.getcwd() in fpath:
                    fpath = os.path.relpath(fpath, os.getcwd())

                candidates.append((fpath, int(lineno), i))

    if candidates:
        # Take the last candidate as it's likely the point of failure in our code
        last_candidate = candidates[-1]
        fpath, lineno, line_idx = last_candidate

        # Extract the error message (usually a few lines down)
        # Look for the next non-indented line after the traceback
        error_msg = "Unknown Error"
        for j in range(line_idx + 1, len(lines)):
            if not lines[j].strip().startswith("File") and not lines[j].startswith(" "):
                error_msg = lines[j].strip()
                break

        return fpath, lineno, error_msg

    return None, None, None


def generate_fix_with_llm(file_path, line_number, error_message, file_content):
    """
    Stub for calling an LLM to generate a fix.
    In production, this would use `anthropic` or `openai` client.
    """
    _out(f"🤖 AGENT: Generating fix for {file_path}:{line_number} - {error_message}", file=sys.stderr)

    # Prompt construction concept

    # TODO: Integration point
    # if os.getenv("ANTHROPIC_API_KEY"):
    #      response = client.messages.create(...)
    #      return extract_code(response)

    return None


def apply_fix_and_push(run_id, file_path, new_content):
    """Checkout branch, write file, commit, and push."""
    # 1. Checkout the branch associated with the run (this might require fetching ref)
    # For now, simplistic approach: assume we are in a workflow with checkout

    branch_name = f"fix/auto-remediation-{run_id}"

    _out(f"Creating branch {branch_name}...", file=sys.stderr)
    if not run_git_command(["checkout", "-b", branch_name]):
        return False

    _out(f"Applying fix to {file_path}...", file=sys.stderr)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    _out("Committing changes...", file=sys.stderr)
    run_git_command(["config", "user.name", "Augur Agent"])
    run_git_command(["config", "user.email", "agent@augur.ai"])

    if not run_git_command(["add", file_path]):
        return False
    if not run_git_command(["commit", "-m", f"fix: auto-remediation for run {run_id}"]):
        return False

    _out("Pushing changes...", file=sys.stderr)
    # Using GITHUB_TOKEN for push
    # git push origin HEAD:branch_name
    if not run_git_command(["push", "origin", f"HEAD:{branch_name}"]):
        return False

    # Create PR
    run_gh_command(
        ["pr", "create", "--title", f"Fix: Auto-remediation for #{run_id}", "--body", "Automated fix by CI Agent."]
    )

    return True


def create_backlog_item(run_id, job_name, fpath, lineno, err, content):
    """Create a bug report in augur/bugs."""
    # Use src/lib config for paths if possible, or env var
    from src.config.paths import get_runtime_dir

    bugs_dir = get_runtime_dir() / "bugs"
    bugs_dir.mkdir(parents=True, exist_ok=True)

    safe_job_name = re.sub(r'[^a-zA-Z0-9]', '_', job_name)
    filename = f"bug_{run_id}_{safe_job_name}.md"
    filepath = bugs_dir / filename

    # The prompt requested by the user
    agent_prompt = f"""
# 🐞 Bug Report: {job_name} failure in {fpath}

## Context
- **Run ID**: {run_id}
- **File**: `{fpath}`
- **Line**: {lineno}
- **Error**: `{err}`

## Code Context
```python
{content}
```

## Agent Instructions
You are an expert Python engineer.
1. Analyze the error above line by line.
2. Verify the issue in the code context.
3. Apply a fix to the file `{fpath}`.
4. **Do not stop until you have fixed the bug.**
5. Once fixed, delete this file (`{filepath}`).
    """

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(agent_prompt)

    _out(f"Created backlog item: {filepath}", file=sys.stderr)
    return filepath


def main():
    if len(sys.argv) < 2:
        _out("Usage: python ci_failure_analyzer.py <run_id> [--backlog]", file=sys.stderr)
        sys.exit(1)

    run_id = sys.argv[1]
    backlog_mode = "--backlog" in sys.argv

    logs = get_job_logs(run_id)
    if not logs:
        _out("No logs found.")
        sys.exit(0)

    report_lines = ["# 🕵️ Agentic CI Analysis"]

    for item in logs:
        job_name = item["name"]
        log = item["log"]
        fpath, lineno, err = parse_traceback(log)

        if fpath and os.path.exists(fpath):
            report_lines.append(
                f"## Issue Detected in {job_name}\n- **File**: `{fpath}`\n- **Line**: {lineno}\n- **Error**: `{err}`"
            )

            # Read file content
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()

            if backlog_mode:
                bug_file = create_backlog_item(run_id, job_name, fpath, lineno, err, content)
                report_lines.append(f"\n📝 **Backlog Item Created**: `{bug_file}`")
            else:
                # Try to fix (Stub)
                fixed_code = generate_fix_with_llm(fpath, lineno, err, content)

                if fixed_code:
                    if apply_fix_and_push(run_id, fpath, fixed_code):
                        report_lines.append("\n✅ **Auto-fix PR created!**")
                    else:
                        report_lines.append("\n❌ **Auto-fix failed to push.**")
                else:
                    report_lines.append("\n⚠️ **LLM Auto-fix not configured/enabled.**")

        else:
            report_lines.append(
                f"## Raw Log Analysis ({job_name})\nCould not pinpoint file. Snippet:\n```\n{log[-500:]}\n```"
            )

    _out("\n".join(report_lines))


if __name__ == "__main__":
    main()
