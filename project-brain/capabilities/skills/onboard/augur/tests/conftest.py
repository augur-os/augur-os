from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest


@pytest.fixture
def setup_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    vault = tmp_path / "vault"
    runtime = tmp_path / "runtime"
    cache = tmp_path / "cache"
    logs = tmp_path / "logs"
    documents = tmp_path / "documents"
    for path in (vault, runtime, cache, logs, documents):
        path.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("AUGUR_VAULT", str(vault))
    monkeypatch.setenv("AUGUR_VAULT_DIR", str(vault))
    monkeypatch.setenv("AUGUR_STATE", str(runtime))
    monkeypatch.setenv("AUGUR_STATE_DIR", str(runtime))
    monkeypatch.setenv("AUGUR_RUNTIME_DIR", str(runtime))
    monkeypatch.setenv("AUGUR_CACHE_DIR", str(cache))
    monkeypatch.setenv("AUGUR_LOGS", str(logs))
    monkeypatch.setenv("AUGUR_LOGS_DIR", str(logs))
    monkeypatch.setenv("AUGUR_DOCUMENTS", str(documents))
    monkeypatch.setenv("AUGUR_DOCUMENTS_DIR", str(documents))
    from src.config import paths

    paths.invalidate_project_cache()

    # Keep the index-machine probe hermetic: it reports "done" when the skill
    # inventory has been generated, evidenced by either the build-time
    # docs/generated/skill-manifest.json (gitignored, may be absent in a clean
    # checkout/CI) or the runtime ide-integration/registry.yaml. Provide the
    # runtime registry in the tmp sandbox so the probe resolves deterministically
    # off controlled state instead of the developer's real-repo build artifacts.
    registry = runtime / "ide-integration" / "registry.yaml"
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text("integrations: []\n", encoding="utf-8")

    # Keep the inbox-lane probe hermetic: it reads config/system/inbox.yaml from
    # the project root, which in tests must be the tmp sandbox, not this repo.
    # The aggregator imports probe modules lazily at probe time, so the module
    # must be imported here first — sys.modules.get alone is a silent no-op.
    if "onboard_setup_pkg" in sys.modules:
        knowledge_probes = importlib.import_module("onboard_setup_pkg.probes.knowledge")
        monkeypatch.setattr(knowledge_probes, "get_project_root", lambda: tmp_path)

    class SetupEnv:
        vault_dir = vault
        runtime_dir = runtime
        cache_dir = cache
        logs_dir = logs
        documents_dir = documents

        def add_private_skill(self, name: str = "focus-routine") -> None:
            skill_dir = vault / "skills" / name
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text("---\nname: focus-routine\n---\n", encoding="utf-8")

        def add_prompt(self, name: str = "daily-start.md") -> None:
            prompt_dir = vault / "prompts"
            prompt_dir.mkdir(parents=True, exist_ok=True)
            (prompt_dir / name).write_text("# Daily start\n", encoding="utf-8")

        def add_prompt_note(self, name: str = "daily-start.md") -> None:
            notes_dir = vault / "notes"
            notes_dir.mkdir(parents=True, exist_ok=True)
            (notes_dir / name).write_text(
                "---\nx-augur-note-type: prompt\nx-augur-prompt-triggerable: true\n---\n# Daily start\n",
                encoding="utf-8",
            )

        def add_profile(self) -> None:
            profile_dir = vault / "memory"
            profile_dir.mkdir(parents=True, exist_ok=True)
            (profile_dir / "profile.md").write_text("A" * 300, encoding="utf-8")

        def add_voice_profile(self, language: str = "en") -> None:
            profile_dir = vault / "profile" / language
            profile_dir.mkdir(parents=True, exist_ok=True)
            (profile_dir / "about-me.md").write_text("A" * 300, encoding="utf-8")

        def add_wiki_profile(self) -> None:
            profile_dir = vault / "wiki"
            profile_dir.mkdir(parents=True, exist_ok=True)
            (profile_dir / "profile-human-api.md").write_text("A" * 300, encoding="utf-8")

        def add_ask_history(self) -> None:
            (runtime / "ask-history.jsonl").write_text('{"ts": 1, "query_hash": "abc"}\n', encoding="utf-8")

        def add_wiki_queries(self) -> None:
            wiki_dir = vault / "knowledge" / "wiki"
            wiki_dir.mkdir(parents=True, exist_ok=True)
            (wiki_dir / "queries.yaml").write_text(
                "queries:\n  - setup completeness\n  - onboarding prompts\n",
                encoding="utf-8",
            )

        def add_wiki_query_registry(self) -> None:
            wiki_dir = vault / "knowledge" / "wiki"
            wiki_dir.mkdir(parents=True, exist_ok=True)
            (wiki_dir / "queries.yaml").write_text(
                "version: 1\nqueries:\n  active-projects:\n    title: Active Projects\n",
                encoding="utf-8",
            )

        def add_wiki_pages(self, count: int = 5) -> None:
            wiki_dir = vault / "knowledge" / "wiki"
            wiki_dir.mkdir(parents=True, exist_ok=True)
            for idx in range(count):
                (wiki_dir / f"page-{idx}.md").write_text("# Page\n", encoding="utf-8")

        def add_inbox_folder(self) -> None:
            inbox_dir = documents / "inbox" / "claude"
            inbox_dir.mkdir(parents=True, exist_ok=True)

        def add_source_folder(self) -> None:
            sources_dir = vault / "knowledge" / "sources" / "documents"
            sources_dir.mkdir(parents=True, exist_ok=True)

        def add_active_integration(self) -> None:
            integrations_dir = runtime / "integrations"
            integrations_dir.mkdir(parents=True, exist_ok=True)
            (integrations_dir / "gmail.yaml").write_text("enabled: true\n", encoding="utf-8")

    return SetupEnv()
