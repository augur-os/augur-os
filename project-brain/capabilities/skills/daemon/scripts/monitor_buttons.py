#!/usr/bin/env python3
"""
Monitor Action Buttons
----------------------
Scans all registered action buttons and verifies that 'fast' buttons have valid execution handlers.
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
import sys
from subprocess import CalledProcessError, run as subprocess_run  # nosec B404
from pathlib import Path


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


def _project_root_from_skill_root(skill_root: Path) -> Path:
    """Resolve checkout root from either project-brain or legacy skill roots."""
    if skill_root.parent.name == "skills":
        skills_container = skill_root.parent.parent
        if (
            skills_container.name == "capabilities"
            and skills_container.parent.name == "project-brain"
        ):
            return skills_container.parent.parent
        if skills_container.name == "project-brain":
            return skills_container.parent
        return skills_container
    return skill_root.parent.parent


# Setup paths
try:
    from src.config.paths import get_project_root, get_python_executable, get_skill_root
    PROJECT_ROOT = get_project_root()
    SKILL_ROOT = get_skill_root("daemon")
except ImportError:
    # Fallback for standalone execution outside monorepo
    SKILL_ROOT = Path(__file__).resolve().parent.parent
    PROJECT_ROOT = _project_root_from_skill_root(SKILL_ROOT)
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    from src.config.paths import get_python_executable  # noqa: E402
CLI_SCRIPT = PROJECT_ROOT / "src" / "cli.py"
PYTHON_VAL = str(get_python_executable())


def run_command(args):
    """Run a CLI command and return JSON output."""
    cmd = [PYTHON_VAL, str(CLI_SCRIPT), "--json"] + args
    try:
        result = subprocess_run(  # nosec B603
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout)
    except CalledProcessError as e:
        _out(f"Error running command: {e}")
        _out(f"Stderr: {e.stderr}")
        return None
    except json.JSONDecodeError:
        _out("Failed to parse JSON")
        _out(f"Raw Output: {result.stdout}")
        _out(f"Stderr: {result.stderr}")
        return None


def main():
    _out("🔍 Scanning Action Buttons...")

    # 1. Get all buttons
    buttons_data = run_command(["buttons"])
    if not buttons_data or "buttons" not in buttons_data:
        _out("❌ Failed to fetch buttons")
        sys.exit(1)

    buttons = buttons_data["buttons"]
    _out(f"Found {len(buttons)} total buttons.")

    # 2. Filter for Fast Actions
    # Note: The CLI output might not explicitly say 'flow: fast' unless 'buttons' command returns full metadata.
    # Logic in PageActionButtons.tsx uses button.flow === 'fast'.
    # We should check if the CLI 'buttons' command output includes 'flow'.

    fast_buttons = [b for b in buttons if b.get("flow") == "fast"]
    _out(f"Found {len(fast_buttons)} fast buttons.")

    failed_count = 0
    passed_count = 0

    _out("\nValidating Fast Buttons:")
    _out("-" * 50)

    for btn in fast_buttons:
        action_id = btn.get("name")  # PageActionButtons uses name as actionId
        label = btn.get("label", action_id)

        # Check validity
        check_result = run_command(["run-action", action_id, "--check"])

        if check_result and check_result.get("status") == "valid":
            _out(f"✅ {label} ({action_id}) - {check_result.get('type')}")
            passed_count += 1
        else:
            _out(f"❌ {label} ({action_id}) - INVALID")
            _out(f"   Details: {check_result}")
            failed_count += 1

    _out("-" * 50)
    _out(f"Summary: {passed_count} Passed, {failed_count} Failed")

    if failed_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
