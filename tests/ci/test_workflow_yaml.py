from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WF = ROOT / ".github/workflows/fresh-env-onboard.yml"


def test_workflow_parses_and_has_tiered_triggers():
    data = yaml.safe_load(WF.read_text())
    on = data[True] if True in data else data["on"]  # PyYAML maps `on:` -> True
    assert "workflow_call" in on
    assert "schedule" in on
    assert "pull_request" in on


def test_job_runs_onboard_then_verify():
    text = WF.read_text()
    assert "aug onboard run --non-interactive" in text
    assert "fresh_env_verify" in text
    # tiered: PR path is linux-only; schedule/call cover all three OSes
    assert "ubuntu-latest" in text and "macos-latest" in text and "windows-latest" in text


RELEASE = ROOT / ".github/workflows/release.yml"


def test_release_gates_on_fresh_env():
    data = yaml.safe_load(RELEASE.read_text())
    jobs = data["jobs"]
    assert "fresh-env-gate" in jobs
    assert jobs["fresh-env-gate"]["uses"] == "./.github/workflows/fresh-env-onboard.yml"
    # release-please only runs once the gate passed
    assert "fresh-env-gate" in jobs["release-please"].get("needs", [])
