from __future__ import annotations

import importlib
import importlib.util
import sys
import types
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
_aggregator = importlib.import_module(f"{PKG}.aggregator")
_derive_widget_state = _aggregator._derive_widget_state
clear_cache = _aggregator.clear_cache
compute_setup_status = _aggregator.compute_setup_status


def test_state_card_below_60pct() -> None:
    assert _derive_widget_state(pct=0, ever_completed=False, has_pending=True) == "card"
    assert _derive_widget_state(pct=59, ever_completed=False, has_pending=True) == "card"


def test_state_bar_60_to_99pct() -> None:
    assert _derive_widget_state(pct=60, ever_completed=False, has_pending=True) == "bar"
    assert _derive_widget_state(pct=99, ever_completed=False, has_pending=True) == "bar"


def test_state_chip_at_100pct() -> None:
    assert _derive_widget_state(pct=100, ever_completed=True, has_pending=False) == "chip"


def test_state_alert_after_completed_setup_regresses() -> None:
    assert _derive_widget_state(pct=90, ever_completed=True, has_pending=True) == "alert"


def test_compute_setup_status_fresh_vault_shows_foundation_basics(setup_env) -> None:
    clear_cache()

    status = compute_setup_status(skip_cache=True)

    assert status.version == 1
    assert status.total == 12
    assert status.completed == 3
    assert status.pct == 25
    assert status.state == "card"
    assert {phase.id for phase in status.phases} == {
        "foundation",
        "knowledge",
        "personalization",
    }


def test_compute_setup_status_marks_skipped_items_out_of_denominator(setup_env) -> None:
    clear_cache()
    preferences = setup_env.runtime_dir / "preferences.yaml"
    preferences.write_text(
        "setup:\n  skipped:\n    - wiki-pages-5\n    - integration\n",
        encoding="utf-8",
    )

    status = compute_setup_status(skip_cache=True)

    assert status.total == 10
    skipped = [item for phase in status.phases for item in phase.items if item.status == "skipped"]
    assert {item.id for item in skipped} == {"wiki-pages-5", "integration"}


def test_compute_setup_status_latches_completed_and_reports_chip(setup_env) -> None:
    clear_cache()
    setup_env.add_voice_profile()
    setup_env.add_inbox_folder()
    setup_env.add_source_folder()
    setup_env.add_wiki_queries()
    setup_env.add_wiki_pages()
    setup_env.add_private_skill()
    setup_env.add_prompt()
    setup_env.add_ask_history()
    setup_env.add_active_integration()

    status = compute_setup_status(skip_cache=True)

    assert status.completed == 12
    assert status.pct == 100
    assert status.state == "chip"
    assert "ever_completed: true" in (setup_env.runtime_dir / "preferences.yaml").read_text(encoding="utf-8")


def test_compute_setup_status_recognizes_english_voice_profile(setup_env) -> None:
    clear_cache()
    setup_env.add_voice_profile("en")

    status = compute_setup_status(skip_cache=True)

    human_profile = next(item for phase in status.phases for item in phase.items if item.id == "human-profile")
    assert human_profile.status == "done"
    assert human_profile.details == "voice profile available"


def test_compute_setup_status_recognizes_hebrew_voice_profile(setup_env) -> None:
    clear_cache()
    setup_env.add_voice_profile("he")

    status = compute_setup_status(skip_cache=True)

    human_profile = next(item for phase in status.phases for item in phase.items if item.id == "human-profile")
    assert human_profile.status == "done"
    assert human_profile.details == "voice profile available"


def test_compute_setup_status_requires_voice_profile_specific_path(setup_env) -> None:
    clear_cache()
    setup_env.add_wiki_profile()

    status = compute_setup_status(skip_cache=True)

    human_profile = next(item for phase in status.phases for item in phase.items if item.id == "human-profile")
    assert human_profile.status == "pending"


def test_compute_setup_status_recognizes_wiki_query_registry_mapping(setup_env) -> None:
    clear_cache()
    setup_env.add_wiki_query_registry()

    status = compute_setup_status(skip_cache=True)

    wiki_queries = next(item for phase in status.phases for item in phase.items if item.id == "wiki-queries")
    assert wiki_queries.status == "done"
    assert wiki_queries.details == "1 queries"


def test_compute_setup_status_recognizes_wiki_queries_when_skills_is_shadowed(
    setup_env,
    monkeypatch,
) -> None:
    clear_cache()
    setup_env.add_wiki_query_registry()
    shadow = types.ModuleType("skills")
    shadow.__path__ = ["/tmp/not-augur-skills"]
    monkeypatch.setitem(sys.modules, "skills", shadow)

    status = compute_setup_status(skip_cache=True)

    wiki_queries = next(item for phase in status.phases for item in phase.items if item.id == "wiki-queries")
    assert wiki_queries.status == "done"
    assert wiki_queries.details == "1 queries"


def test_compute_setup_status_reports_alert_when_latched_setup_regresses(setup_env) -> None:
    clear_cache()
    (setup_env.runtime_dir / "preferences.yaml").write_text(
        "setup:\n  ever_completed: true\n",
        encoding="utf-8",
    )

    status = compute_setup_status(skip_cache=True)

    assert status.state == "alert"
    assert any(item.status == "regressed" for phase in status.phases for item in phase.items)
