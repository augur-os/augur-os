"""Behavior tests for setup personalization probes."""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
SETUP_DIR = PROJECT_ROOT / "project-brain" / "capabilities" / "skills" / "onboard" / "scripts" / "setup"

PKG = "onboard_setup_pkg"


def _ensure_package() -> None:
    if PKG in sys.modules:
        return
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    spec = importlib.util.spec_from_file_location(
        PKG,
        SETUP_DIR / "__init__.py",
        submodule_search_locations=[str(SETUP_DIR)],
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[PKG] = module
    spec.loader.exec_module(module)


_ensure_package()
personalization = importlib.import_module(f"{PKG}.probes.personalization")


def test_private_skill_done_when_present(setup_env) -> None:
    setup_env.add_private_skill()

    result = personalization.private_skill()

    assert result.status == "done"


def test_private_skill_done_when_nested_vault_capability_present(setup_env) -> None:
    skill_dir = setup_env.vault_dir / "capabilities" / "skills" / "public-presence" / "public-presence"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text("---\nname: public-presence\n---\n", encoding="utf-8")

    result = personalization.private_skill()

    assert result.status == "done"


def test_private_skill_pending_when_no_skill_md(setup_env) -> None:
    skills_dir = setup_env.vault_dir / "skills" / "empty"
    skills_dir.mkdir(parents=True, exist_ok=True)

    result = personalization.private_skill()

    assert result.status == "pending"


def test_saved_prompt_done_when_prompt_exists(setup_env) -> None:
    setup_env.add_prompt()

    result = personalization.saved_prompt()

    assert result.status == "done"
    assert "1 saved prompt notes" in (result.details or "")


def test_saved_prompt_done_when_prompt_note_exists(setup_env) -> None:
    setup_env.add_prompt_note()

    result = personalization.saved_prompt()

    assert result.status == "done"
    assert "1 saved prompt notes" in (result.details or "")


def test_saved_prompt_ignores_readme(setup_env) -> None:
    prompts = setup_env.vault_dir / "prompts"
    prompts.mkdir(parents=True, exist_ok=True)
    (prompts / "README.md").write_text("readme", encoding="utf-8")

    result = personalization.saved_prompt()

    assert result.status == "pending"


def test_first_ask_done_when_history_has_content(setup_env) -> None:
    setup_env.add_ask_history()

    result = personalization.first_ask()

    assert result.status == "done"


def test_first_ask_pending_when_history_empty(setup_env) -> None:
    (setup_env.runtime_dir / "ask-history.jsonl").write_text("", encoding="utf-8")

    result = personalization.first_ask()

    assert result.status == "pending"


def test_first_ask_pending_when_history_missing(setup_env) -> None:
    result = personalization.first_ask()

    assert result.status == "pending"


def test_integration_done_when_enabled_yaml_present(setup_env) -> None:
    setup_env.add_active_integration()

    result = personalization.integration()

    assert result.status == "done"


def test_integration_pending_when_yaml_disabled(setup_env) -> None:
    integrations = setup_env.runtime_dir / "integrations"
    integrations.mkdir(parents=True, exist_ok=True)
    (integrations / "gmail.yaml").write_text("enabled: false\n", encoding="utf-8")

    result = personalization.integration()

    assert result.status == "pending"


def test_integration_pending_when_no_integrations(setup_env) -> None:
    result = personalization.integration()

    assert result.status == "pending"
