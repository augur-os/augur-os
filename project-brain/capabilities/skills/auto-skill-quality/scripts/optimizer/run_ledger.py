"""Persist an OptimizeRun (baseline + per-round results) as JSON."""
import json
from pathlib import Path


def save_run(run_dir, run):
    Path(run_dir).mkdir(parents=True, exist_ok=True)
    path = Path(run_dir) / f"{run['run_id']}.json"
    path.write_text(json.dumps(run, indent=2), encoding="utf-8")
    return path


def load_run(run_dir, run_id):
    path = Path(run_dir) / f"{run_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"no optimize run {run_id}")
    return json.loads(path.read_text(encoding="utf-8"))
