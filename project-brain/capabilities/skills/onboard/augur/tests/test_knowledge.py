"""Behavior tests for setup knowledge probes."""

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
knowledge = importlib.import_module(f"{PKG}.probes.knowledge")


def test_inbox_folders_done_when_documents_inbox_subdir_exists(setup_env) -> None:
    setup_env.add_inbox_folder()

    result = knowledge.inbox_folders()

    assert result.status == "done"


def test_inbox_folders_done_with_enabled_lanes(setup_env, tmp_path) -> None:
    config_dir = tmp_path / "config" / "system"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "inbox.yaml").write_text(
        "default_sources:\n"
        "  - id: claude-chat\n"
        "    enabled: true\n"
        "  - id: disabled-lane\n"
        "    enabled: false\n",
        encoding="utf-8",
    )

    result = knowledge.inbox_folders()

    assert result.status == "done"
    assert "1 inbox lanes" in (result.details or "")


def test_inbox_folders_pending_when_no_lanes_or_folders(setup_env) -> None:
    result = knowledge.inbox_folders()

    assert result.status == "pending"


def test_inbox_folders_pending_when_documents_inbox_empty(setup_env) -> None:
    (setup_env.documents_dir / "inbox").mkdir(parents=True, exist_ok=True)

    result = knowledge.inbox_folders()

    assert result.status == "pending"


def test_source_folders_done_with_vault_sources(setup_env) -> None:
    setup_env.add_source_folder()

    result = knowledge.source_folders()

    assert result.status == "done"


def test_source_folders_done_with_runtime_sources_yaml(setup_env) -> None:
    knowledge_dir = setup_env.runtime_dir / "knowledge"
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    (knowledge_dir / "sources.yaml").write_text("sources: []\n", encoding="utf-8")

    result = knowledge.source_folders()

    assert result.status == "done"


def test_source_folders_pending_when_no_candidates(setup_env) -> None:
    result = knowledge.source_folders()

    assert result.status == "pending"


def test_wiki_pages_5_done_when_threshold_met(setup_env, monkeypatch) -> None:
    wiki_dir = setup_env.vault_dir / "wiki-compiled"
    wiki_dir.mkdir(parents=True, exist_ok=True)
    for idx in range(5):
        (wiki_dir / f"page-{idx}.md").write_text("# Page\n", encoding="utf-8")
    monkeypatch.setattr(knowledge, "get_compiled_wiki_dir", lambda: wiki_dir)

    result = knowledge.wiki_pages_5()

    assert result.status == "done"
    assert "5" in (result.details or "")


def test_wiki_pages_5_pending_when_under_threshold(setup_env, monkeypatch) -> None:
    wiki_dir = setup_env.vault_dir / "wiki-compiled"
    wiki_dir.mkdir(parents=True, exist_ok=True)
    for idx in range(2):
        (wiki_dir / f"page-{idx}.md").write_text("# Page\n", encoding="utf-8")
    monkeypatch.setattr(knowledge, "get_compiled_wiki_dir", lambda: wiki_dir)

    result = knowledge.wiki_pages_5()

    assert result.status == "pending"
    assert "2/5" in (result.details or "")


def test_wiki_queries_pending_when_no_query_config(setup_env) -> None:
    result = knowledge.wiki_queries()

    assert result.status == "pending"
    assert result.details == "no compounding wiki queries"


def test_wiki_queries_done_when_query_pages_exist(setup_env) -> None:
    # B5: query pages live as wiki/queries/*.md. A vault with seeded query pages but
    # no queries.yaml/config.yaml must still be recognized as having queries.
    queries_dir = knowledge.get_wiki_dir() / "queries"
    queries_dir.mkdir(parents=True, exist_ok=True)
    for slug in ("how-should-x-be-used", "how-should-y-be-used"):
        (queries_dir / f"{slug}.md").write_text("# Query\n", encoding="utf-8")

    result = knowledge.wiki_queries()

    assert result.status == "done"
    assert "2" in (result.details or "")
