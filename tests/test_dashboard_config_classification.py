from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_CONFIG = ROOT / "config" / "dashboard"
GENERATED = DASHBOARD_CONFIG / "generated"
README = DASHBOARD_CONFIG / "README.md"
RULES = ROOT / "docs" / "agent-topics" / "agent-rules.md"


def _classified_files() -> set[str]:
    if not README.exists():
        return set()
    text = README.read_text(encoding="utf-8")
    return set(re.findall(r"`([^`]+\.ya?ml)`", text))


def _dashboard_config_files() -> set[str]:
    actual: set[str] = set()
    for path in DASHBOARD_CONFIG.rglob("*"):
        if not path.is_file():
            continue
        if path.is_relative_to(GENERATED):
            continue
        if path.suffix not in {".yaml", ".yml"}:
            continue
        actual.add(path.relative_to(DASHBOARD_CONFIG).as_posix())
    return actual


def test_dashboard_yaml_files_are_classified() -> None:
    actual = _dashboard_config_files()
    classified = _classified_files()

    assert actual <= classified


def test_dashboard_config_readme_marks_debt_and_exceptions() -> None:
    text = README.read_text(encoding="utf-8")

    assert "`cli_parser_profiles.yaml`" in text
    assert "`generated_surfaces.yaml`" in text
    assert "`app_mode.yaml`" not in text
    assert "`mcp_tools.yaml`" not in text
    assert "migration debt" not in text
    assert "legitimate central system config" in text
    assert (
        "Keep central. Update only when external CLI stream protocols or parser behavior changes; do not migrate to skill metadata."
        in text
    )
    assert "Do not add new central dashboard YAML without classifying it here." in text


def test_retired_dashboard_migration_debt_configs_are_absent() -> None:
    assert not (DASHBOARD_CONFIG / "app_mode.yaml").exists()
    assert not (DASHBOARD_CONFIG / "mcp_tools.yaml").exists()


def test_global_decentralization_rule_matches_config_reality() -> None:
    text = RULES.read_text(encoding="utf-8")

    assert "Central dashboard config must be classified in `config/dashboard/README.md`" in text
    assert (
        "Centralized config files (`config/dashboard/*.yaml`) are technical debt, not a pattern to extend." not in text
    )


def test_agent_rules_include_behavioral_baseline() -> None:
    text = RULES.read_text(encoding="utf-8")

    assert "## Behavioral Baseline" in text
    assert "Prefer the smallest sufficient change." in text
    assert "Every changed line should trace to the user request" in text
    assert "verify against real user-facing data" in text
