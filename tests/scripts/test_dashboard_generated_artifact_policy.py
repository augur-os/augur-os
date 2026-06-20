from __future__ import annotations

import re
import subprocess
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = PROJECT_ROOT / "config" / "dashboard" / "generated_surfaces.yaml"


DASHBOARD_IGNORED_RUNTIME_ARTIFACTS: set[str] = {
    "apps/dashboard/app/adaptive",
    "apps/dashboard/app/brain",
    "apps/dashboard/app/command",
    "apps/dashboard/app/dev",
    "apps/dashboard/features/generated-skill-pages",
    "apps/dashboard/lib/blocks/custom-block-registry.ts",
    "apps/dashboard/lib/blocks/generated-block-registry.ts",
    "apps/dashboard/lib/browse/generated-item-actions.ts",
    "apps/dashboard/lib/tabs/generated-registry.ts",
    "apps/dashboard/lib/tabs/generated-skill-nav.ts",
    "config/dashboard/generated",
}


DASHBOARD_TRACKED_BOOTSTRAP_ARTIFACTS: set[str] = {
    "apps/dashboard/lib/generated-config-modules.d.ts",
}


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _is_git_ignored(path: str) -> bool:
    if _git("check-ignore", "-q", "--", path).returncode == 0:
        return True

    # Directory ignore patterns such as /features/generated-skill-pages/ match
    # generated contents even when the directory does not exist yet.
    probe_child = f"{path.rstrip('/')}/__augur_generated_probe__"
    return _git("check-ignore", "-q", "--", probe_child).returncode == 0


def _tracked(paths: set[str]) -> list[str]:
    result = _git("ls-files", "--", *sorted(paths))
    assert result.returncode == 0, result.stderr
    return sorted(line for line in result.stdout.splitlines() if line.strip())


def _load_policy() -> dict:
    with POLICY_PATH.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def test_dashboard_generated_surface_policy_is_explicit() -> None:
    policy = _load_policy()
    surfaces = policy.get("surfaces")
    assert isinstance(surfaces, list)

    by_path = {surface["path"]: surface for surface in surfaces}
    expected = DASHBOARD_IGNORED_RUNTIME_ARTIFACTS | DASHBOARD_TRACKED_BOOTSTRAP_ARTIFACTS

    assert set(by_path) == expected
    assert {surface["classification"] for surface in surfaces} == {"ignored-runtime", "tracked-bootstrap"}

    local_inputs = [
        path
        for path, surface in by_path.items()
        if surface["classification"] == "tracked-bootstrap" and surface.get("input_scope") != "repo-only"
    ]
    assert not local_inputs, f"Tracked bootstrap surfaces must be repo-only: {local_inputs}"


def test_dashboard_generated_artifacts_are_gitignored() -> None:
    missing = sorted(path for path in DASHBOARD_IGNORED_RUNTIME_ARTIFACTS if not _is_git_ignored(path))

    assert not missing, f"Expected git to ignore dashboard generated artifacts: {missing}"


def test_dashboard_ignored_runtime_artifacts_are_not_tracked() -> None:
    tracked = _tracked(DASHBOARD_IGNORED_RUNTIME_ARTIFACTS)
    assert not tracked, f"Dashboard generated artifacts should not be tracked: {tracked}"


def test_dashboard_tracked_bootstrap_artifacts_are_tracked_and_not_ignored() -> None:
    tracked = set(_tracked(DASHBOARD_TRACKED_BOOTSTRAP_ARTIFACTS))

    assert tracked == DASHBOARD_TRACKED_BOOTSTRAP_ARTIFACTS

    incorrectly_ignored = sorted(path for path in DASHBOARD_TRACKED_BOOTSTRAP_ARTIFACTS if _is_git_ignored(path))
    assert not incorrectly_ignored, (
        "Tracked dashboard bootstrap artifacts should stay visible to Git: " f"{incorrectly_ignored}"
    )


def test_dashboard_has_no_tracked_legacy_skill_page_sources() -> None:
    tracked = _git("ls-files")
    assert tracked.returncode == 0, tracked.stderr

    legacy_pattern = re.compile(r"(^|/)skills/[^/]+/augur/(dashboard/|pages/[^/]+\.ya?ml$)")
    legacy_paths = sorted(
        path for path in tracked.stdout.splitlines() if legacy_pattern.search(path) and (PROJECT_ROOT / path).exists()
    )

    assert not legacy_paths, (
        "Tracked legacy skill-owned dashboard page sources must be staged or " f"migrated: {legacy_paths}"
    )


def test_dashboard_scripts_regenerate_surfaces_before_typecheck() -> None:
    import json

    package_json = json.loads((PROJECT_ROOT / "apps" / "dashboard" / "package.json").read_text(encoding="utf-8"))
    scripts = package_json["scripts"]

    assert (
        scripts["ensure-generated"]
        == "pnpm run build:scripts && pnpm run generate-item-actions && pnpm run rebuild-plugins"
    )
    assert scripts["prebuild"] == "pnpm run ensure-generated"
    assert scripts["pretypecheck"] == "pnpm run ensure-generated"
    assert scripts["dev"] == "node scripts/start-dev.mjs"
    assert scripts["build"] == "node scripts/build.mjs"
    assert scripts["build:safe"] == "node scripts/build-lock.mjs pnpm run build"
