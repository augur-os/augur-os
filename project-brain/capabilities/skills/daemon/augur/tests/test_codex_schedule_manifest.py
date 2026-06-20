"""Tests for the Codex migration schedule manifest."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import yaml

from skills.daemon.scripts.adaptive.discovery import AutoCommandEntry

WORKSPACE_TOKEN = "__PROJECT_ROOT__"
DAEMON_ROOT = Path(__file__).resolve().parents[2]


def _python_executable() -> str:
    repo_python = DAEMON_ROOT.parents[2] / ".venv" / "bin" / "python3"
    return str(repo_python if repo_python.is_file() else Path(sys.executable))


def _entry(
    name: str, loop: str, trigger: str, scheduler: str = "codex"
) -> AutoCommandEntry:
    return AutoCommandEntry(
        name=name,
        module=SimpleNamespace(name="test-module"),
        loop_name=loop,
        trigger=trigger,
        scheduler=scheduler,
    )


def test_build_codex_schedule_manifest_splits_mixed_families(tmp_path: Path) -> None:
    from skills.daemon.scripts.adaptive.codex_schedule_manifest import (
        build_codex_schedule_manifest,
    )

    registry = {
        "auto-self-heal": _entry("auto-self-heal", "self-heal", "continuous", "daemon"),
        "auto-heal-validate": _entry(
            "auto-heal-validate", "self-heal", "nightly", "daemon"
        ),
        "auto-file-growth": _entry(
            "auto-file-growth", "self-heal", "nightly", "daemon"
        ),
        "auto-command-evolution": _entry(
            "auto-command-evolution",
            "command-evolution",
            "post-execution",
            "daemon",
        ),
        "auto-command-help-coverage": _entry(
            "auto-command-help-coverage",
            "command-evolution",
            "nightly",
            "codex",
        ),
        "auto-memory-consolidation": _entry(
            "auto-memory-consolidation",
            "knowledge-enrichment",
            "nightly",
            "daemon",
        ),
        "auto-claude-md-audit": _entry(
            "auto-claude-md-audit",
            "knowledge-enrichment",
            "weekly",
            "daemon",
        ),
        "sync-agents": _entry(
            "sync-agents",
            "knowledge-enrichment",
            "post-execution",
            "daemon",
        ),
        "auto-testing": _entry("auto-testing", "testing", "nightly", "daemon"),
        "auto-test-dashboard": _entry(
            "auto-test-dashboard", "testing", "nightly", "codex"
        ),
    }

    manifest = build_codex_schedule_manifest(registry, project_root=tmp_path)
    rows = {row["id"]: row for row in manifest}

    assert set(rows) == {
        "codex-dev-loop-testing",
        "codex-dev-loop-self-heal-validate",
        "codex-command-evolution-drain",
        "codex-knowledge-enrichment-nightly",
        "codex-knowledge-enrichment-drain",
    }
    assert all("trigger" not in row for row in manifest)
    assert len({row["id"] for row in manifest}) == len(manifest)

    assert rows["codex-dev-loop-testing"] == {
        "id": "codex-dev-loop-testing",
        "loop": "testing",
        "mode": "nightly",
        "source_commands": ["auto-test-dashboard", "auto-testing"],
        "current_owner": "mixed",
        "target_owner": "codex",
        "client": "codex",
        "runs_in": "local",
        "cadence": "weekly-sunday-03:00",
        "workspace": WORKSPACE_TOKEN,
        "prompt": "/routines run testing",
        "depends_on": [],
        "cutover_state": "not-installed",
        "browse_title": "Testing",
    }
    assert rows["codex-dev-loop-self-heal-validate"] == {
        "id": "codex-dev-loop-self-heal-validate",
        "loop": "self-heal",
        "mode": "nightly",
        "source_commands": ["auto-file-growth", "auto-heal-validate"],
        "current_owner": "daemon",
        "target_owner": "codex",
        "client": "codex",
        "runs_in": "local",
        "cadence": "nightly-03:55",
        "workspace": WORKSPACE_TOKEN,
        "prompt": "/routines run self-heal --validate",
        "depends_on": [],
        "cutover_state": "not-installed",
        "browse_title": "Self Heal Validate",
    }
    assert rows["codex-command-evolution-drain"] == {
        "id": "codex-command-evolution-drain",
        "loop": "command-evolution",
        "mode": "drain",
        "source_commands": ["auto-command-evolution", "auto-command-help-coverage"],
        "current_owner": "mixed",
        "target_owner": "codex",
        "client": "codex",
        "runs_in": "local",
        "cadence": "every-15-minutes",
        "workspace": WORKSPACE_TOKEN,
        "prompt": "/routines run command-evolution --drain",
        "depends_on": [],
        "cutover_state": "not-installed",
        "browse_title": "Command Evolution Drain",
    }
    assert rows["codex-knowledge-enrichment-nightly"] == {
        "id": "codex-knowledge-enrichment-nightly",
        "loop": "knowledge-enrichment",
        "mode": "nightly",
        "source_commands": [
            "auto-claude-md-audit",
            "auto-memory-consolidation",
        ],
        "current_owner": "daemon",
        "target_owner": "codex",
        "client": "codex",
        "runs_in": "local",
        "cadence": "weekly-wednesday-03:00",
        "workspace": WORKSPACE_TOKEN,
        "prompt": "/routines run knowledge-enrichment",
        "depends_on": [],
        "cutover_state": "not-installed",
        "browse_title": "Knowledge Enrichment Nightly",
    }
    assert rows["codex-knowledge-enrichment-drain"] == {
        "id": "codex-knowledge-enrichment-drain",
        "loop": "knowledge-enrichment",
        "mode": "drain",
        "source_commands": [
            "sync-agents",
        ],
        "current_owner": "daemon",
        "target_owner": "codex",
        "client": "codex",
        "runs_in": "local",
        "cadence": "hourly",
        "workspace": WORKSPACE_TOKEN,
        "prompt": "/routines run knowledge-enrichment --drain",
        "depends_on": [],
        "cutover_state": "not-installed",
        "browse_title": "Knowledge Enrichment Drain",
    }
    assert "self-heal-fast" not in rows
    assert "codex-dev-loop-command-evolution" not in rows
    assert "codex-dev-loop-knowledge-enrichment" not in rows
    assert rows["codex-knowledge-enrichment-drain"]["source_commands"] == [
        "sync-agents"
    ]
    assert rows["codex-knowledge-enrichment-nightly"]["source_commands"] == [
        "auto-claude-md-audit",
        "auto-memory-consolidation",
    ]
    assert rows["codex-dev-loop-self-heal-validate"]["source_commands"] == [
        "auto-file-growth",
        "auto-heal-validate",
    ]


def test_manifest_marks_every_codex_unit_local() -> None:
    from skills.daemon.scripts.adaptive.codex_schedule_manifest import (
        build_codex_schedule_manifest,
    )

    manifest = build_codex_schedule_manifest(
        {
            "auto-testing": _entry("auto-testing", "testing", "nightly", "daemon"),
            "auto-test-dashboard": _entry(
                "auto-test-dashboard", "testing", "nightly", "daemon"
            ),
            "auto-file-growth": _entry(
                "auto-file-growth", "self-heal", "nightly", "daemon"
            ),
            "auto-heal-validate": _entry(
                "auto-heal-validate", "self-heal", "nightly", "daemon"
            ),
        },
        project_root=Path("/tmp/project-root"),
    )

    assert manifest[0] == {
        "id": "codex-dev-loop-testing",
        "loop": "testing",
        "mode": "nightly",
        "source_commands": ["auto-test-dashboard", "auto-testing"],
        "current_owner": "daemon",
        "target_owner": "codex",
        "client": "codex",
        "runs_in": "local",
        "cadence": "weekly-sunday-03:00",
        "workspace": WORKSPACE_TOKEN,
        "prompt": "/routines run testing",
        "depends_on": [],
        "cutover_state": "not-installed",
        "browse_title": "Testing",
    }
    assert all(row["workspace"] == WORKSPACE_TOKEN for row in manifest)
    assert all(row["runs_in"] == "local" for row in manifest)
    assert all("trigger" not in row for row in manifest)
    assert len({row["id"] for row in manifest}) == len(manifest)
    assert sum(1 for row in manifest if row["id"] == "codex-dev-loop-testing") == 1
    rows = {row["id"]: row for row in manifest}
    assert rows["codex-dev-loop-self-heal-validate"]["source_commands"] == [
        "auto-file-growth",
        "auto-heal-validate",
    ]


def test_current_owner_uses_single_non_daemon_scheduler(tmp_path: Path) -> None:
    from skills.daemon.scripts.adaptive.codex_schedule_manifest import (
        build_codex_schedule_manifest,
    )

    manifest = build_codex_schedule_manifest(
        {
            "auto-testing": _entry("auto-testing", "testing", "nightly", "codex"),
        },
        project_root=tmp_path,
    )

    assert manifest == [
        {
            "id": "codex-dev-loop-testing",
            "loop": "testing",
            "mode": "nightly",
            "source_commands": ["auto-testing"],
            "current_owner": "codex",
            "target_owner": "codex",
            "client": "codex",
            "runs_in": "local",
            "cadence": "weekly-sunday-03:00",
            "workspace": WORKSPACE_TOKEN,
            "prompt": "/routines run testing",
            "depends_on": [],
            "cutover_state": "not-installed",
            "browse_title": "Testing",
        }
    ]


def test_manifest_uses_detected_schedule_states(tmp_path: Path) -> None:
    from skills.daemon.scripts.adaptive.codex_schedule_manifest import (
        build_codex_schedule_manifest,
    )

    manifest = build_codex_schedule_manifest(
        {
            "auto-testing": _entry("auto-testing", "testing", "nightly", "codex"),
            "auto-file-growth": _entry(
                "auto-file-growth", "self-heal", "nightly", "codex"
            ),
            "auto-heal-validate": _entry(
                "auto-heal-validate", "self-heal", "nightly", "codex"
            ),
        },
        project_root=tmp_path,
        schedule_states={
            "codex-dev-loop-testing": "active",
            "codex-dev-loop-self-heal-validate": "disabled",
        },
    )
    rows = {row["id"]: row for row in manifest}

    assert rows["codex-dev-loop-testing"]["cutover_state"] == "active"
    assert rows["codex-dev-loop-self-heal-validate"]["cutover_state"] == "disabled"


def test_manifest_normalizes_registry_trigger_and_scheduler_metadata(
    tmp_path: Path,
) -> None:
    from skills.daemon.scripts.adaptive.codex_schedule_manifest import (
        build_codex_schedule_manifest,
    )

    manifest = build_codex_schedule_manifest(
        {
            "auto-testing": _entry("auto-testing", "testing", " Nightly ", " Codex "),
        },
        project_root=tmp_path,
    )

    assert manifest[0]["current_owner"] == "codex"
    assert manifest[0]["id"] == "codex-dev-loop-testing"


def test_detect_codex_schedule_states(tmp_path: Path) -> None:
    from skills.daemon.scripts.adaptive.codex_schedule_manifest import (
        detect_codex_schedule_states,
    )

    automations = tmp_path / ".codex" / "automations"
    active_dir = automations / "active-schedule"
    active_dir.mkdir(parents=True)
    (active_dir / "automation.toml").write_text(
        'managed_by = "augur"\nstatus = "active"\n',
        encoding="utf-8",
    )
    disabled_dir = automations / "disabled-schedule"
    disabled_dir.mkdir(parents=True)
    (disabled_dir / "automation.toml").write_text(
        'managed_by = "augur"\nstatus = "DISABLED"\n',
        encoding="utf-8",
    )
    foreign_dir = automations / "foreign-schedule"
    foreign_dir.mkdir(parents=True)
    (foreign_dir / "automation.toml").write_text(
        'managed_by = "other"\nstatus = "ACTIVE"\n',
        encoding="utf-8",
    )
    invalid_dir = automations / "invalid-schedule"
    invalid_dir.mkdir(parents=True)
    (invalid_dir / "automation.toml").write_text(
        'managed_by = "augur"\nstatus = "ACTIVE"\ninvalid = [\n',
        encoding="utf-8",
    )

    assert detect_codex_schedule_states(
        [
            "active-schedule",
            "disabled-schedule",
            "foreign-schedule",
            "invalid-schedule",
            "missing-schedule",
        ],
        home=tmp_path,
    ) == {
        "active-schedule": "active",
        "disabled-schedule": "disabled",
        "foreign-schedule": "not-installed",
        "invalid-schedule": "invalid",
        "missing-schedule": "not-installed",
    }


def test_metadata_only_manifest_defaults_non_continuous_scheduler_to_codex(
    tmp_path: Path,
) -> None:
    from skills.daemon.scripts.adaptive.codex_schedule_manifest import (
        build_codex_schedule_manifest_from_project,
    )

    skill_dir = tmp_path / "project-brain" / "capabilities" / "skills" / "test-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        """---
name: test-skill
x-augur-commands:
  - id: auto-no-scheduler
    protocol: scan-fix
    callable: scripts/ops/missing.py
    loop:
      name: testing
      trigger: nightly
---
""",
        encoding="utf-8",
    )

    manifest = build_codex_schedule_manifest_from_project(tmp_path)

    assert manifest[0]["current_owner"] == "codex"


def test_regular_loop_with_multiple_triggers_raises() -> None:
    from skills.daemon.scripts.adaptive.codex_schedule_manifest import (
        build_codex_schedule_manifest,
    )

    registry = {
        "auto-testing": _entry("auto-testing", "testing", "nightly", "daemon"),
        "auto-testing-drain": _entry(
            "auto-testing-drain", "testing", "post-execution", "daemon"
        ),
    }

    try:
        build_codex_schedule_manifest(registry, project_root=Path("/tmp/project-root"))
    except ValueError as exc:
        message = str(exc)
        assert "regular loops only support nightly triggers" in message
        assert "testing -> nightly, post-execution" in message
    else:
        raise AssertionError(
            "expected build_codex_schedule_manifest to raise ValueError"
        )


def test_regular_loop_with_unsupported_trigger_raises() -> None:
    from skills.daemon.scripts.adaptive.codex_schedule_manifest import (
        build_codex_schedule_manifest,
    )

    registry = {
        "auto-testing": _entry("auto-testing", "testing", "weekly", "daemon"),
    }

    try:
        build_codex_schedule_manifest(registry, project_root=Path("/tmp/project-root"))
    except ValueError as exc:
        message = str(exc)
        assert "regular loops only support nightly triggers" in message
        assert "testing -> weekly" in message
    else:
        raise AssertionError(
            "expected build_codex_schedule_manifest to raise ValueError"
        )


def test_special_family_with_unsupported_trigger_raises() -> None:
    from skills.daemon.scripts.adaptive.codex_schedule_manifest import (
        build_codex_schedule_manifest,
    )

    registry = {
        "auto-command-help-coverage": _entry(
            "auto-command-help-coverage",
            "command-evolution",
            "weekly",
            "daemon",
        ),
    }

    try:
        build_codex_schedule_manifest(registry, project_root=Path("/tmp/project-root"))
    except ValueError as exc:
        message = str(exc)
        assert "command-evolution -> unsupported trigger(s): weekly" in message
        assert "supported: nightly, post-execution" in message
    else:
        raise AssertionError(
            "expected build_codex_schedule_manifest to raise ValueError"
        )


def test_manifest_cli_uses_checkout_root_from_nested_subdir(tmp_path: Path) -> None:
    nested_cwd = DAEMON_ROOT / "scripts"
    automation_dir = tmp_path / ".codex" / "automations" / "codex-dev-loop-testing"
    automation_dir.mkdir(parents=True)
    (automation_dir / "automation.toml").write_text(
        'managed_by = "augur"\nstatus = "ACTIVE"\n',
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            _python_executable(),
            str(DAEMON_ROOT / "scripts" / "adaptive_loop_executor.py"),
            "manifest",
        ],
        cwd=nested_cwd,
        env={**os.environ, "HOME": str(tmp_path)},
        check=True,
        capture_output=True,
        text=True,
    )

    manifest = yaml.safe_load(result.stdout)["schedules"]
    rows = {row["id"]: row for row in manifest}
    assert rows["codex-dev-loop-testing"]["cutover_state"] == "active"
    assert rows["codex-dev-loop-testing"]["workspace"] == WORKSPACE_TOKEN
    assert "/Users/" not in result.stdout
    assert WORKSPACE_TOKEN in result.stdout


def test_metadata_only_manifest_includes_missing_callable_command(
    tmp_path: Path,
) -> None:
    from skills.daemon.scripts.adaptive.codex_schedule_manifest import (
        build_codex_schedule_manifest_from_project,
    )

    skill_dir = tmp_path / "project-brain" / "capabilities" / "skills" / "test-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        """---
name: test-skill
x-augur-commands:
  - id: auto-missing-callable
    protocol: scan-fix
    callable: scripts/ops/missing.py
    loop:
      name: testing
      trigger: nightly
      scheduler: daemon
---
""",
        encoding="utf-8",
    )

    manifest = build_codex_schedule_manifest_from_project(tmp_path)

    assert manifest == [
        {
            "id": "codex-dev-loop-testing",
            "loop": "testing",
            "mode": "nightly",
            "source_commands": ["auto-missing-callable"],
            "current_owner": "daemon",
            "target_owner": "codex",
            "client": "codex",
            "runs_in": "local",
            "cadence": "weekly-sunday-03:00",
            "workspace": WORKSPACE_TOKEN,
            "prompt": "/routines run testing",
            "depends_on": [],
            "cutover_state": "not-installed",
            "browse_title": "Testing",
        }
    ]


def test_metadata_only_manifest_ignores_user_cache_skills(
    tmp_path: Path, monkeypatch
) -> None:
    from skills.daemon.scripts.adaptive.codex_schedule_manifest import (
        build_codex_schedule_manifest_from_project,
    )

    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    local_skill = tmp_path / "project-brain" / "capabilities" / "skills" / "local-skill"
    local_skill.mkdir(parents=True)
    (local_skill / "SKILL.md").write_text(
        """---
name: local-skill
x-augur-commands:
  - id: auto-local
    protocol: scan-fix
    callable: scripts/ops/local.py
    loop:
      name: testing
      trigger: nightly
      scheduler: daemon
---
""",
        encoding="utf-8",
    )

    cache_skill = tmp_path / "home" / ".claude" / "plugins" / "cache" / "cached-skill"
    cache_skill.mkdir(parents=True)
    (cache_skill / "SKILL.md").write_text(
        """---
name: cached-skill
x-augur-commands:
  - id: auto-cached
    protocol: scan-fix
    callable: scripts/ops/cached.py
    loop:
      name: testing
      trigger: nightly
      scheduler: codex
---
""",
        encoding="utf-8",
    )

    manifest = build_codex_schedule_manifest_from_project(tmp_path)
    rows = {row["id"]: row for row in manifest}

    assert rows["codex-dev-loop-testing"]["source_commands"] == ["auto-local"]
    assert "auto-cached" not in rows["codex-dev-loop-testing"]["source_commands"]


def test_metadata_only_manifest_includes_configured_vault_skills_and_excludes_generated_exports(
    tmp_path: Path,
) -> None:
    from skills.daemon.scripts.adaptive.codex_schedule_manifest import (
        build_codex_schedule_manifest_from_project,
    )

    project_root = tmp_path / "repo"
    repo_skills = project_root / "project-brain" / "capabilities" / "skills"
    repo_skills.mkdir(parents=True)
    vault = tmp_path / "vault"
    vault_skill = vault / "capabilities" / "skills" / "vault-skill"
    vault_skill.mkdir(parents=True)
    generated_skill = project_root / ".gemini" / "skills" / "generated-skill"
    generated_skill.mkdir(parents=True)
    (project_root / "project.yaml").write_text(
        f"name: TestAugur\npaths:\n  vault: {vault}\n",
        encoding="utf-8",
    )
    (vault_skill / "SKILL.md").write_text(
        """---
name: vault-skill
x-augur-commands:
  - id: auto-vault-skill
    protocol: scan-fix
    callable: scripts/ops/vault.py
    loop:
      name: testing
      trigger: nightly
---
""",
        encoding="utf-8",
    )
    (generated_skill / "SKILL.md").write_text(
        """---
name: generated-skill
x-augur-commands:
  - id: auto-generated-skill
    protocol: scan-fix
    callable: scripts/ops/generated.py
    loop:
      name: testing
      trigger: nightly
---
""",
        encoding="utf-8",
    )

    manifest = build_codex_schedule_manifest_from_project(project_root)

    rows = {row["id"]: row for row in manifest}
    assert rows["codex-dev-loop-testing"]["source_commands"] == ["auto-vault-skill"]


def test_metadata_only_manifest_raises_on_malformed_frontmatter(tmp_path: Path) -> None:
    from skills.daemon.scripts.adaptive.codex_schedule_manifest import (
        build_codex_schedule_manifest_from_project,
    )

    skill_dir = tmp_path / "project-brain" / "capabilities" / "skills" / "bad-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        """---
name: bad-skill
x-augur-commands:
  - id: auto-bad
    protocol scan-fix
---
""",
        encoding="utf-8",
    )

    try:
        build_codex_schedule_manifest_from_project(tmp_path)
    except ValueError as exc:
        message = str(exc)
        assert "Malformed frontmatter" in message
        assert str(skill_dir / "SKILL.md") in message
    else:
        raise AssertionError("expected malformed frontmatter to raise ValueError")


def test_codex_schedule_manifest_importable_from_repo_root() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    result = subprocess.run(
        [
            _python_executable(),
            "-c",
            "import skills.daemon.scripts.adaptive.codex_schedule_manifest as mod; print(mod.__name__)",
        ],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )

    assert (
        result.stdout.strip()
        == "skills.daemon.scripts.adaptive.codex_schedule_manifest"
    )
