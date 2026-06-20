"""Post-execution feedback hook for skill quality.

Called as a PostToolUse hook after skill execution. Collects lightweight
thumbs up/down feedback and suggests full eval runs.

Usage:
    python3 -m skills.auto_skill_quality.scripts.feedback_hook --skill SKILL_NAME
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
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.config.paths import get_project_root, get_project_brain_skills_dir

MAX_ENTRIES = 50
FEEDBACK_COOLDOWN_DAYS = 7


def should_prompt_feedback(skill_name: str, evals_dir: Path) -> bool:
    """Decide whether to prompt user for feedback."""
    if not (evals_dir / "evals.json").exists():
        return True

    feedback_file = evals_dir / "feedback.json"
    if feedback_file.exists():
        try:
            data = json.loads(feedback_file.read_text())
            entries = data.get("entries", [])
            if entries:
                last_ts = entries[-1].get("timestamp", "")
                if last_ts:
                    last_dt = datetime.fromisoformat(last_ts)
                    if last_dt.tzinfo is None:
                        last_dt = last_dt.replace(tzinfo=timezone.utc)
                    if datetime.now(timezone.utc) - last_dt < timedelta(days=FEEDBACK_COOLDOWN_DAYS):
                        return False
        except (json.JSONDecodeError, ValueError, KeyError, TypeError):
            pass

    return random.random() < 0.20


def append_feedback(evals_dir: Path, skill_name: str, result: str, note: str, prompt_summary: str) -> None:
    """Append a feedback entry to evals/feedback.json, capping at MAX_ENTRIES."""
    feedback_file = evals_dir / "feedback.json"

    if feedback_file.exists():
        try:
            data = json.loads(feedback_file.read_text())
        except json.JSONDecodeError:
            data = {"skill_name": skill_name, "entries": []}
    else:
        data = {"skill_name": skill_name, "entries": []}

    data["entries"].append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "result": result,
        "note": note,
        "prompt_summary": prompt_summary,
    })

    if len(data["entries"]) > MAX_ENTRIES:
        data["entries"] = data["entries"][-MAX_ENTRIES:]

    evals_dir.mkdir(exist_ok=True)
    feedback_file.write_text(json.dumps(data, indent=2))


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Skill feedback hook")
    parser.add_argument("--skill", required=True, help="Skill name")
    args = parser.parse_args()

    skill_name = args.skill
    root = get_project_root()
    evals_dir = get_project_brain_skills_dir(root) / skill_name / "evals"

    if not should_prompt_feedback(skill_name, evals_dir):
        return

    print(f"\nDid {skill_name} do what you expected? (y/n)", flush=True)
    print(f"Run /skill-creator eval {skill_name} to benchmark this skill and improve its rank.", flush=True)


if __name__ == "__main__":
    main()
