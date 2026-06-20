from __future__ import annotations

import os
from pathlib import Path


def test_discover_source_roots_includes_codex_memory_when_present(tmp_path, monkeypatch) -> None:
    from skills.knowledge.scripts.mcp.ask_context_pack import discover_source_roots

    home = tmp_path / "home"
    codex_memory = home / ".codex" / "memories"
    codex_memory.mkdir(parents=True)
    (codex_memory / "MEMORY.md").write_text("fresh codex focus", encoding="utf-8")

    vault = tmp_path / "vault"
    wiki = vault / "wiki"
    memory = vault / "memory"
    runtime = tmp_path / "runtime"
    wiki.mkdir(parents=True)
    memory.mkdir(parents=True)
    runtime.mkdir()

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("CODEX_HOME", raising=False)

    roots = discover_source_roots(
        vault_dir=vault,
        wiki_dir=wiki,
        vault_memory_dir=memory,
        runtime_dir=runtime,
        project_root=tmp_path / "repo",
    )

    families = {root.family for root in roots}
    assert "codex_memory" in families
    assert "augur_wiki" in families
    assert "augur_vault_memory" in families
    assert "augur_runtime_memory" in families


def test_read_bounded_file_uses_head_and_tail_without_shell(tmp_path) -> None:
    from skills.knowledge.scripts.mcp.ask_context_pack import read_bounded_file

    path = tmp_path / "large.md"
    path.write_text("A" * 2000 + "\nMIDDLE\n" + "Z" * 2000, encoding="utf-8")

    result = read_bounded_file(path, max_chars=500)

    assert len(result) <= 500
    assert "A" * 40 in result
    assert "Z" * 40 in result
    assert "MIDDLE" not in result


def test_read_bounded_file_never_reads_entire_file(tmp_path, monkeypatch) -> None:
    from skills.knowledge.scripts.mcp.ask_context_pack import read_bounded_file

    path = tmp_path / "large.md"
    path.write_text("A" * 2000 + "\nMIDDLE\n" + "Z" * 2000, encoding="utf-8")

    def fail_read_text(self, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        raise AssertionError(f"unexpected full-file read for {self}")

    monkeypatch.setattr(Path, "read_text", fail_read_text)

    result = read_bounded_file(path, max_chars=500)

    assert len(result) == 500
    assert "A" * 40 in result
    assert "Z" * 40 in result
    assert "MIDDLE" not in result


def test_read_bounded_file_returns_empty_for_missing_or_binary_file(tmp_path) -> None:
    from skills.knowledge.scripts.mcp.ask_context_pack import read_bounded_file

    missing = tmp_path / "missing.md"
    binary = tmp_path / "binary.bin"
    binary.write_bytes(b"abc\x00def")

    assert read_bounded_file(missing) == ""
    assert read_bounded_file(binary) == ""


def test_discover_source_roots_includes_configured_global_memory_roots(tmp_path, monkeypatch) -> None:
    from skills.knowledge.scripts.mcp.ask_context_pack import discover_source_roots

    global_memory = tmp_path / "global-memory"
    other_global_memory = tmp_path / "other-global-memory"
    global_memory.mkdir()
    other_global_memory.mkdir()
    (global_memory / "MEMORY.md").write_text("global agent focus", encoding="utf-8")
    (other_global_memory / "MEMORY.md").write_text("other global focus", encoding="utf-8")

    vault = tmp_path / "vault"
    wiki = vault / "wiki"
    memory = vault / "memory"
    runtime = tmp_path / "runtime"
    wiki.mkdir(parents=True)
    memory.mkdir(parents=True)
    runtime.mkdir()

    monkeypatch.setenv(
        "AUGUR_ASK_MEMORY_ROOTS",
        f"{global_memory}{os.pathsep}{other_global_memory}",
    )

    roots = discover_source_roots(
        vault_dir=vault,
        wiki_dir=wiki,
        vault_memory_dir=memory,
        runtime_dir=runtime,
        project_root=tmp_path / "repo",
    )

    global_roots = [root for root in roots if root.family == "agent_global_memories"]
    assert [root.root for root in global_roots] == [global_memory, other_global_memory]


def test_iter_summary_files_orders_rollouts_deterministically_on_tied_mtimes(tmp_path, monkeypatch) -> None:
    from skills.knowledge.scripts.mcp.ask_context_pack import SourceRoot, iter_summary_files

    memory_root = tmp_path / "memories"
    rollout_dir = memory_root / "rollout_summaries"
    rollout_dir.mkdir(parents=True)
    first = rollout_dir / "a.md"
    second = rollout_dir / "b.md"
    first.write_text("first", encoding="utf-8")
    second.write_text("second", encoding="utf-8")
    tied_mtime = 1_700_000_000
    for path in (first, second):
        os.utime(path, (tied_mtime, tied_mtime))

    original_iterdir = Path.iterdir

    def reversed_iterdir(self):
        if self == rollout_dir:
            return iter([second, first])
        return original_iterdir(self)

    monkeypatch.setattr(Path, "iterdir", reversed_iterdir)

    root = SourceRoot("codex_memory", memory_root, "Codex memory", True, ())

    assert list(iter_summary_files(root)) == [first, second]


def test_current_focus_ranks_fresh_codex_memory_over_stale_wiki(tmp_path, monkeypatch) -> None:
    from skills.knowledge.scripts.mcp.ask_context_pack import build_context_pack

    home = tmp_path / "home"
    codex_memory = home / ".codex" / "memories"
    codex_memory.mkdir(parents=True)
    (codex_memory / "MEMORY.md").write_text(
        "# Task Group: Fresh Demo\n"
        "scope: Edge AI demo and skill trust work\n"
        "updated_at=2026-05-27T18:49:03+00:00\n",
        encoding="utf-8",
    )

    vault = tmp_path / "vault"
    wiki = vault / "wiki"
    memory = vault / "memory"
    runtime = tmp_path / "runtime"
    wiki.mkdir(parents=True)
    memory.mkdir(parents=True)
    (runtime / "memory").mkdir(parents=True)
    (wiki / "active-projects.md").write_text(
        "---\nupdated: '2026-05-12T21:35:19+00:00'\n---\n"
        "Older stabilization and wiki query work.\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.delenv("AUGUR_ASK_MEMORY_ROOTS", raising=False)

    pack = build_context_pack(
        "what am I working on now?",
        vault_dir=vault,
        wiki_dir=wiki,
        vault_memory_dir=memory,
        runtime_dir=runtime,
        project_root=tmp_path / "repo",
        current_date="2026-05-28",
    )

    assert pack.intent == "current_focus"
    assert pack.candidates[0].family == "codex_memory"
    assert pack.candidates[0].updated_at == "2026-05-27T18:49:03+00:00"
    assert "Codex memory" in " ".join(pack.source_basis)
    assert "2026-05-27" in " ".join(pack.source_basis)
    assert any("stale" in warning for warning in pack.warnings)


def test_troubleshooting_query_with_working_stays_reflective() -> None:
    from skills.knowledge.scripts.mcp.ask_context_pack import classify_query_intent

    assert classify_query_intent("Why is retention not working?") == "reflective"
    assert classify_query_intent("What am I working on now?") == "current_focus"


def test_current_focus_warns_when_client_memory_is_unavailable(tmp_path, monkeypatch) -> None:
    from skills.knowledge.scripts.mcp.ask_context_pack import build_context_pack

    home = tmp_path / "home"
    vault = tmp_path / "vault"
    wiki = vault / "wiki"
    memory = vault / "memory"
    runtime = tmp_path / "runtime"
    wiki.mkdir(parents=True)
    memory.mkdir(parents=True)
    (runtime / "memory").mkdir(parents=True)
    (wiki / "active-projects.md").write_text(
        "---\nupdated: '2026-05-27T00:00:00+00:00'\n---\n"
        "Fresh wiki context about the current focus.\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.delenv("AUGUR_ASK_MEMORY_ROOTS", raising=False)

    pack = build_context_pack(
        "what am I working on now?",
        vault_dir=vault,
        wiki_dir=wiki,
        vault_memory_dir=memory,
        runtime_dir=runtime,
        project_root=tmp_path / "repo",
        current_date="2026-05-28",
    )

    assert pack.intent == "current_focus"
    assert "client-memory-unavailable" in pack.warnings


def test_reflective_low_signal_query_warns_when_metadata_has_no_matches(
    tmp_path,
    monkeypatch,
) -> None:
    from skills.knowledge.scripts.mcp.ask_context_pack import build_context_pack

    home = tmp_path / "home"
    (home / ".codex" / "memories").mkdir(parents=True)
    vault = tmp_path / "vault"
    wiki = vault / "wiki"
    memory = vault / "memory"
    runtime = tmp_path / "runtime"
    wiki.mkdir(parents=True)
    memory.mkdir(parents=True)
    (runtime / "memory").mkdir(parents=True)
    (wiki / "context.md").write_text(
        "---\nupdated: '2026-05-27T00:00:00+00:00'\n---\n"
        "A substantial but unrelated project note.\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AUGUR_ASK_MEMORY_ROOTS", raising=False)

    pack = build_context_pack(
        "what about this?",
        vault_dir=vault,
        wiki_dir=wiki,
        vault_memory_dir=memory,
        runtime_dir=runtime,
        project_root=tmp_path / "repo",
        current_date="2026-05-28",
    )

    assert pack.intent == "reflective"
    assert "generic-query-low-signal" in pack.warnings


def test_reflective_query_allows_wiki_to_rank_above_recent_raw_memory(tmp_path, monkeypatch) -> None:
    from skills.knowledge.scripts.mcp.ask_context_pack import build_context_pack

    home = tmp_path / "home"
    (home / ".codex" / "memories").mkdir(parents=True)
    vault = tmp_path / "vault"
    wiki = vault / "wiki"
    memory = vault / "memory"
    runtime = tmp_path / "runtime"
    wiki.mkdir(parents=True)
    memory.mkdir(parents=True)
    (runtime / "memory").mkdir(parents=True)
    (wiki / "concept.md").write_text(
        "---\nupdated: '2026-05-27T00:00:00+00:00'\n---\n"
        "Deep durable pattern about project selection and focus.\n",
        encoding="utf-8",
    )
    (memory / "MEMORY.md").write_text("Recent but generic focus note.\n", encoding="utf-8")

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AUGUR_ASK_MEMORY_ROOTS", raising=False)

    pack = build_context_pack(
        "what pattern keeps showing up in how I choose projects?",
        vault_dir=vault,
        wiki_dir=wiki,
        vault_memory_dir=memory,
        runtime_dir=runtime,
        project_root=tmp_path / "repo",
        current_date="2026-05-28",
    )

    assert pack.intent == "reflective"
    assert pack.candidates
    assert pack.candidates[0].family == "augur_wiki"
    assert pack.candidates[0].freshness >= 0.8


def test_structured_search_uses_mtime_iso_and_freshness_metadata(tmp_path, monkeypatch) -> None:
    from skills.knowledge.scripts.mcp.ask_context_pack import build_context_pack

    home = tmp_path / "home"
    (home / ".codex" / "memories").mkdir(parents=True)
    vault = tmp_path / "vault"
    wiki = vault / "wiki"
    memory = vault / "memory"
    runtime = tmp_path / "runtime"
    wiki.mkdir(parents=True)
    memory.mkdir(parents=True)
    (runtime / "memory").mkdir(parents=True)
    memory_file = memory / "MEMORY.md"
    memory_file.write_text("Skill trust guardrail status and search notes.\n", encoding="utf-8")
    fresh_mtime = 1_748_466_000
    os.utime(memory_file, (fresh_mtime, fresh_mtime))

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AUGUR_ASK_MEMORY_ROOTS", raising=False)

    pack = build_context_pack(
        "search skill trust",
        vault_dir=vault,
        wiki_dir=wiki,
        vault_memory_dir=memory,
        runtime_dir=runtime,
        project_root=tmp_path / "repo",
        current_date="2026-05-28",
    )

    assert pack.intent == "structured_search"
    assert pack.candidates[0].updated_at == "2025-05-28T21:00:00+00:00"
    assert pack.candidates[0].freshness == 0.1
    assert pack.candidates[0].quality_source()["freshness"] == 0.1


def test_structured_search_ranks_older_exact_match_above_fresh_unrelated_wiki(tmp_path, monkeypatch) -> None:
    from skills.knowledge.scripts.mcp.ask_context_pack import build_context_pack

    home = tmp_path / "home"
    (home / ".codex" / "memories").mkdir(parents=True)
    vault = tmp_path / "vault"
    wiki = vault / "wiki"
    memory = vault / "memory"
    runtime = tmp_path / "runtime"
    wiki.mkdir(parents=True)
    memory.mkdir(parents=True)
    (runtime / "memory").mkdir(parents=True)
    (wiki / "fresh-unrelated.md").write_text(
        "---\nupdated: '2026-05-28T00:00:00+00:00'\n---\n"
        "Recent dashboard polish and unrelated meeting notes.\n",
        encoding="utf-8",
    )
    (memory / "MEMORY.md").write_text(
        "---\nupdated: '2026-04-20T00:00:00+00:00'\n---\n"
        "Skill trust guardrail status and search notes.\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AUGUR_ASK_MEMORY_ROOTS", raising=False)

    pack = build_context_pack(
        "search skill trust",
        vault_dir=vault,
        wiki_dir=wiki,
        vault_memory_dir=memory,
        runtime_dir=runtime,
        project_root=tmp_path / "repo",
        current_date="2026-05-28",
    )

    assert pack.intent == "structured_search"
    assert pack.candidates[0].family == "augur_vault_memory"
    assert pack.candidates[0].match_terms == ("skill", "trust")
    assert pack.candidates[1].family == "augur_wiki"
    assert pack.candidates[1].match_terms == ()


def test_crlf_frontmatter_timestamp_is_parsed_for_windows_files(tmp_path, monkeypatch) -> None:
    from skills.knowledge.scripts.mcp.ask_context_pack import build_context_pack

    home = tmp_path / "home"
    (home / ".codex" / "memories").mkdir(parents=True)
    vault = tmp_path / "vault"
    wiki = vault / "wiki"
    memory = vault / "memory"
    runtime = tmp_path / "runtime"
    wiki.mkdir(parents=True)
    memory.mkdir(parents=True)
    (runtime / "memory").mkdir(parents=True)
    memory_file = memory / "MEMORY.md"
    memory_file.write_text(
        "---\r\nmodified: '2026-05-27T00:00:00+00:00'\r\n---\r\n"
        "Skill trust guardrail status and search notes.\r\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AUGUR_ASK_MEMORY_ROOTS", raising=False)

    pack = build_context_pack(
        "search skill trust",
        vault_dir=vault,
        wiki_dir=wiki,
        vault_memory_dir=memory,
        runtime_dir=runtime,
        project_root=tmp_path / "repo",
        current_date="2026-05-28",
    )

    assert pack.candidates[0].updated_at == "2026-05-27T00:00:00+00:00"
    assert pack.candidates[0].freshness == 1.0


def test_raw_crlf_and_cr_frontmatter_timestamps_parse_without_text_normalization() -> None:
    from skills.knowledge.scripts.mcp.ask_context_pack import _parse_embedded_updated, _parse_frontmatter_updated

    crlf_text = "---\r\nmodified: '2026-05-27T00:00:00+00:00'\r\n---\r\nBody\r\n"
    cr_text = "---\rmodified: '2026-05-26T00:00:00+00:00'\r---\rBody\r"

    assert _parse_frontmatter_updated(crlf_text) == "2026-05-27T00:00:00+00:00"
    assert _parse_frontmatter_updated(cr_text) == "2026-05-26T00:00:00+00:00"
    assert _parse_embedded_updated("modified: 2026-05-25T00:00:00+00:00") == "2026-05-25T00:00:00+00:00"


def test_frontmatter_modified_timestamp_wins_over_creation_date() -> None:
    from skills.knowledge.scripts.mcp.ask_context_pack import _parse_frontmatter_updated

    text = (
        "---\n"
        "date: '2026-04-01T00:00:00+00:00'\n"
        "modified: '2026-05-27T00:00:00+00:00'\n"
        "---\n"
        "Body\n"
    )

    assert _parse_frontmatter_updated(text) == "2026-05-27T00:00:00+00:00"


def test_candidates_expose_lexical_match_terms(tmp_path, monkeypatch) -> None:
    from skills.knowledge.scripts.mcp.ask_context_pack import build_context_pack

    home = tmp_path / "home"
    (home / ".codex" / "memories").mkdir(parents=True)
    vault = tmp_path / "vault"
    wiki = vault / "wiki"
    memory = vault / "memory"
    runtime = tmp_path / "runtime"
    wiki.mkdir(parents=True)
    memory.mkdir(parents=True)
    (runtime / "memory").mkdir(parents=True)
    memory_file = memory / "MEMORY.md"
    memory_file.write_text("Skill trust guardrail status and search notes.\n", encoding="utf-8")

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AUGUR_ASK_MEMORY_ROOTS", raising=False)

    pack = build_context_pack(
        "search skill trust",
        vault_dir=vault,
        wiki_dir=wiki,
        vault_memory_dir=memory,
        runtime_dir=runtime,
        project_root=tmp_path / "repo",
        current_date="2026-05-28",
    )

    assert pack.candidates[0].match_terms == ("skill", "trust")
    quality_source = pack.candidates[0].quality_source()
    assert quality_source["match_terms"] == ["skill", "trust"]


def test_leading_ask_and_structured_command_terms_do_not_count_as_matches(tmp_path, monkeypatch) -> None:
    from skills.knowledge.scripts.mcp.ask_context_pack import build_context_pack

    home = tmp_path / "home"
    (home / ".codex" / "memories").mkdir(parents=True)
    vault = tmp_path / "vault"
    wiki = vault / "wiki"
    memory = vault / "memory"
    runtime = tmp_path / "runtime"
    wiki.mkdir(parents=True)
    memory.mkdir(parents=True)
    (runtime / "memory").mkdir(parents=True)
    memory_file = memory / "MEMORY.md"
    memory_file.write_text("Skill trust guardrail status and search notes.\n", encoding="utf-8")

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AUGUR_ASK_MEMORY_ROOTS", raising=False)

    pack = build_context_pack(
        "ask search skill trust",
        vault_dir=vault,
        wiki_dir=wiki,
        vault_memory_dir=memory,
        runtime_dir=runtime,
        project_root=tmp_path / "repo",
        current_date="2026-05-28",
    )

    assert pack.intent == "structured_search"
    assert pack.candidates[0].match_terms == ("skill", "trust")
    assert pack.candidates[0].quality_source()["match_terms"] == ["skill", "trust"]


def test_repo_candidate_uses_current_date_for_git_window_and_metadata(tmp_path, monkeypatch) -> None:
    from types import SimpleNamespace

    from skills.knowledge.scripts.mcp import ask_context_pack

    project_root = tmp_path / "repo"
    (project_root / ".git").mkdir(parents=True)
    calls: list[list[str]] = []

    def fake_run(args, **kwargs):  # noqa: ANN001, ANN003
        calls.append(args)
        assert kwargs["cwd"] == project_root
        assert kwargs["timeout"] == 2
        return SimpleNamespace(returncode=0, stdout="abc123 live memory roots quality gate\n")

    monkeypatch.setattr(ask_context_pack.subprocess, "run", fake_run)

    first = ask_context_pack._repo_candidate(
        project_root,
        "what am I working on now?",
        intent="current_focus",
        current_date="2026-05-28",
    )
    second = ask_context_pack._repo_candidate(
        project_root,
        "what am I working on now?",
        intent="current_focus",
        current_date="2026-05-28",
    )

    assert calls
    assert "--since=2026-05-26T00:00:00+00:00" in calls[0]
    assert "--since=2 days ago" not in calls[0]
    assert first is not None
    assert second is not None
    assert first.updated_at == "2026-05-28T00:00:00+00:00"
    assert second.updated_at == first.updated_at


def test_same_score_and_freshness_tie_ranks_newer_source_first(tmp_path, monkeypatch) -> None:
    from skills.knowledge.scripts.mcp.ask_context_pack import build_context_pack

    home = tmp_path / "home"
    (home / ".codex" / "memories").mkdir(parents=True)
    vault = tmp_path / "vault"
    wiki = vault / "wiki"
    memory = vault / "memory"
    runtime = tmp_path / "runtime"
    wiki.mkdir(parents=True)
    memory.mkdir(parents=True)
    (runtime / "memory").mkdir(parents=True)
    (wiki / "older.md").write_text(
        "---\nupdated: '2026-05-27T00:00:00+00:00'\n---\n"
        "quality gate for live memory roots\n",
        encoding="utf-8",
    )
    (wiki / "newer.md").write_text(
        "---\nupdated: '2026-05-28T00:00:00+00:00'\n---\n"
        "quality gate for live memory roots\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AUGUR_ASK_MEMORY_ROOTS", raising=False)

    pack = build_context_pack(
        "quality gate",
        vault_dir=vault,
        wiki_dir=wiki,
        vault_memory_dir=memory,
        runtime_dir=runtime,
        project_root=tmp_path / "repo",
        current_date="2026-05-28",
    )

    assert pack.candidates[0].path_label.endswith("newer.md")
    assert pack.candidates[1].path_label.endswith("older.md")


def test_structured_search_ranks_older_exact_match_above_fresh_partial_match(tmp_path, monkeypatch) -> None:
    from skills.knowledge.scripts.mcp.ask_context_pack import build_context_pack

    home = tmp_path / "home"
    (home / ".codex" / "memories").mkdir(parents=True)
    vault = tmp_path / "vault"
    wiki = vault / "wiki"
    memory = vault / "memory"
    runtime = tmp_path / "runtime"
    wiki.mkdir(parents=True)
    memory.mkdir(parents=True)
    (runtime / "memory").mkdir(parents=True)
    (wiki / "fresh-partial.md").write_text(
        "---\nupdated: '2026-05-28T00:00:00+00:00'\n---\n"
        "Recent skill catalog polish.\n",
        encoding="utf-8",
    )
    (memory / "MEMORY.md").write_text(
        "---\nupdated: '2026-04-20T00:00:00+00:00'\n---\n"
        "Skill trust guardrail status and search notes.\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AUGUR_ASK_MEMORY_ROOTS", raising=False)

    pack = build_context_pack(
        "search skill trust",
        vault_dir=vault,
        wiki_dir=wiki,
        vault_memory_dir=memory,
        runtime_dir=runtime,
        project_root=tmp_path / "repo",
        current_date="2026-05-28",
    )

    assert pack.candidates[0].family == "augur_vault_memory"
    assert pack.candidates[0].match_terms == ("skill", "trust")
    assert pack.candidates[1].family == "augur_wiki"
    assert pack.candidates[1].match_terms == ("skill",)


def test_reflective_query_ranks_older_exact_match_above_fresh_partial_match(tmp_path, monkeypatch) -> None:
    from skills.knowledge.scripts.mcp.ask_context_pack import build_context_pack

    home = tmp_path / "home"
    (home / ".codex" / "memories").mkdir(parents=True)
    vault = tmp_path / "vault"
    wiki = vault / "wiki"
    memory = vault / "memory"
    runtime = tmp_path / "runtime"
    wiki.mkdir(parents=True)
    memory.mkdir(parents=True)
    (runtime / "memory").mkdir(parents=True)
    (wiki / "fresh-partial.md").write_text(
        "---\nupdated: '2026-05-28T00:00:00+00:00'\n---\n"
        "Recent skill catalog polish.\n",
        encoding="utf-8",
    )
    (memory / "MEMORY.md").write_text(
        "---\nupdated: '2026-04-20T00:00:00+00:00'\n---\n"
        "Skill trust pattern that keeps recurring.\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AUGUR_ASK_MEMORY_ROOTS", raising=False)

    pack = build_context_pack(
        "skill trust pattern",
        vault_dir=vault,
        wiki_dir=wiki,
        vault_memory_dir=memory,
        runtime_dir=runtime,
        project_root=tmp_path / "repo",
        current_date="2026-05-28",
    )

    assert pack.intent == "reflective"
    assert pack.candidates[0].family == "augur_vault_memory"
    assert pack.candidates[0].match_terms == ("skill", "trust", "pattern")
    assert pack.candidates[1].family == "augur_wiki"
    assert pack.candidates[1].match_terms == ("skill",)


def test_current_focus_warns_when_only_stale_sources_are_available(tmp_path, monkeypatch) -> None:
    from skills.knowledge.scripts.mcp.ask_context_pack import build_context_pack

    home = tmp_path / "home"
    (home / ".codex" / "memories").mkdir(parents=True)
    vault = tmp_path / "vault"
    wiki = vault / "wiki"
    memory = vault / "memory"
    runtime = tmp_path / "runtime"
    wiki.mkdir(parents=True)
    memory.mkdir(parents=True)
    (runtime / "memory").mkdir(parents=True)
    (wiki / "active-projects.md").write_text(
        "---\nupdated: '2026-04-01T00:00:00+00:00'\n---\n"
        "Old focus note about launch planning.\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AUGUR_ASK_MEMORY_ROOTS", raising=False)

    pack = build_context_pack(
        "what is my current focus?",
        vault_dir=vault,
        wiki_dir=wiki,
        vault_memory_dir=memory,
        runtime_dir=runtime,
        project_root=tmp_path / "repo",
        current_date="2026-05-28",
    )

    assert pack.candidates[0].stale is True
    assert "stale-primary-source" in pack.warnings
    assert "no-fresh-sources" in pack.warnings
    assert any("stale" in basis for basis in pack.source_basis)


def test_expanded_search_query_uses_fast_pass_keywords(tmp_path, monkeypatch) -> None:
    from skills.knowledge.scripts.mcp.ask_context_pack import build_context_pack, expanded_search_query

    home = tmp_path / "home"
    codex_memory = home / ".codex" / "memories"
    codex_memory.mkdir(parents=True)
    (codex_memory / "MEMORY.md").write_text(
        "Fresh work: Edge AI demo, transcript readiness, skill trust guardrails.",
        encoding="utf-8",
    )

    vault = tmp_path / "vault"
    wiki = vault / "wiki"
    memory = vault / "memory"
    runtime = tmp_path / "runtime"
    wiki.mkdir(parents=True)
    memory.mkdir(parents=True)
    (runtime / "memory").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AUGUR_ASK_MEMORY_ROOTS", raising=False)

    pack = build_context_pack(
        "what am I working on now?",
        vault_dir=vault,
        wiki_dir=wiki,
        vault_memory_dir=memory,
        runtime_dir=runtime,
        project_root=tmp_path / "repo",
        current_date="2026-05-28",
    )

    expanded = expanded_search_query("what am I working on now?", pack)

    assert "Edge" in expanded
    assert "demo" in expanded
    assert "trust" in expanded


def test_expanded_search_query_skips_metadata_noise() -> None:
    from skills.knowledge.scripts.mcp.ask_context_pack import ContextPack, SourceCandidate, expanded_search_query

    pack = ContextPack(
        intent="current_focus",
        candidates=(
            SourceCandidate(
                family="codex_memory",
                path=None,
                path_label="Codex memory: rollout.md",
                text=(
                    "thread_id 0198 updated_at 2026-05-27T12:00:00+00:00 "
                    "rollout_path /Users/testuser/.codex/sessions/e-c-abf-aee\n"
                    "Fresh focus: Edge demo trust guardrails."
                ),
                updated_at="2026-05-27T12:00:00+00:00",
                freshness=1.0,
                score=2.0,
            ),
        ),
        source_basis=(),
        warnings=(),
    )

    expanded = expanded_search_query("what am I working on now?", pack)

    assert "thread_id" not in expanded
    assert "updated_at" not in expanded
    assert "Users" not in expanded
    assert "testuser" not in expanded
    assert "codex" not in expanded
    assert "sessions" not in expanded
    assert "abf" not in expanded
    assert "Edge" in expanded
    assert "demo" in expanded
    assert "trust" in expanded


def test_expanded_search_query_skips_log_status_artifacts() -> None:
    from skills.knowledge.scripts.mcp.ask_context_pack import ContextPack, SourceCandidate, expanded_search_query

    pack = ContextPack(
        intent="current_focus",
        candidates=(
            SourceCandidate(
                family="codex_memory",
                path=None,
                path_label="Codex memory: rollout.md",
                text=(
                    "event_msg: jsonl branch main Built validated cleanup status\n"
                    "source_basis: report generated passed warnings\n"
                    "Outcome partial Preference signals steps Verified repo\n"
                    "Current focus: privacy demo transcript trust guardrails."
                ),
                updated_at="2026-05-27T12:00:00+00:00",
                freshness=1.0,
                score=2.0,
            ),
        ),
        source_basis=(),
        warnings=(),
    )

    expanded = expanded_search_query("what am I working on now?", pack)

    assert "jsonl" not in expanded
    assert "branch" not in expanded
    assert "main" not in expanded
    assert "Built" not in expanded
    assert "validated" not in expanded
    assert "Outcome" not in expanded
    assert "Verified" not in expanded
    assert "repo" not in expanded
    assert "privacy" in expanded
    assert "demo" in expanded
    assert "trust" in expanded


def test_expanded_search_query_keeps_slash_command_content_terms() -> None:
    from skills.knowledge.scripts.mcp.ask_context_pack import ContextPack, SourceCandidate, expanded_search_query

    pack = ContextPack(
        intent="current_focus",
        candidates=(
            SourceCandidate(
                family="codex_memory",
                path=None,
                path_label="Codex memory: rollout.md",
                text="Current focus: /ask live memory roots quality gate.",
                updated_at="2026-05-27T12:00:00+00:00",
                freshness=1.0,
                score=2.0,
            ),
        ),
        source_basis=(),
        warnings=(),
    )

    expanded = expanded_search_query("what am I working on now?", pack)

    assert "live" in expanded
    assert "memory" in expanded
    assert "roots" in expanded
    assert "quality" in expanded
    assert "gate" in expanded


def test_expanded_search_query_masks_paths_and_urls_without_dropping_content_terms() -> None:
    from skills.knowledge.scripts.mcp.ask_context_pack import ContextPack, SourceCandidate, expanded_search_query

    pack = ContextPack(
        intent="current_focus",
        candidates=(
            SourceCandidate(
                family="codex_memory",
                path=None,
                path_label="Codex memory: rollout.md",
                text=(
                    "Fresh focus: live memory roots quality gate uses "
                    "/Users/testuser/Projects/Augur/project-brain and "
                    "C:\\Users\\guri\\Augur\\logs with https://example.com/path."
                ),
                updated_at="2026-05-27T12:00:00+00:00",
                freshness=1.0,
                score=2.0,
            ),
        ),
        source_basis=(),
        warnings=(),
    )

    expanded = expanded_search_query("what am I working on now?", pack)

    assert "live" in expanded
    assert "memory" in expanded
    assert "roots" in expanded
    assert "quality" in expanded
    assert "gate" in expanded
    assert "Users" not in expanded
    assert "testuser" not in expanded
    assert "Projects" not in expanded
    assert "guri" not in expanded
    assert "example" not in expanded


def test_expanded_search_query_preserves_mixed_metadata_line_content() -> None:
    from skills.knowledge.scripts.mcp.ask_context_pack import ContextPack, SourceCandidate, expanded_search_query

    pack = ContextPack(
        intent="current_focus",
        candidates=(
            SourceCandidate(
                family="codex_memory",
                path=None,
                path_label="Codex memory: rollout.md",
                text=(
                    "updated_at=2026-05-27T12:00:00+00:00 rollout_path "
                    "/Users/testuser/.codex/sessions/current.jsonl "
                    "live memory roots quality gate"
                ),
                updated_at="2026-05-27T12:00:00+00:00",
                freshness=1.0,
                score=2.0,
            ),
        ),
        source_basis=(),
        warnings=(),
    )

    expanded = expanded_search_query("what am I working on now?", pack)

    assert "live" in expanded
    assert "memory" in expanded
    assert "roots" in expanded
    assert "quality" in expanded
    assert "gate" in expanded
    assert "updated" not in expanded
    assert "jsonl" not in expanded
    assert "sessions" not in expanded
    assert "testuser" not in expanded


def test_expanded_search_query_masks_punctuated_paths() -> None:
    from skills.knowledge.scripts.mcp.ask_context_pack import ContextPack, SourceCandidate, expanded_search_query

    pack = ContextPack(
        intent="current_focus",
        candidates=(
            SourceCandidate(
                family="codex_memory",
                path=None,
                path_label="Codex memory: rollout.md",
                text=(
                    "Paths (`/Users/testuser/Projects/Augur/project-brain/capabilities/skills/knowledge`) "
                    "and (\"C:\\Users\\guri\\Augur\\project-brain\\capabilities\\skills\\knowledge\") "
                    "still describe live memory roots quality gate."
                ),
                updated_at="2026-05-27T12:00:00+00:00",
                freshness=1.0,
                score=2.0,
            ),
        ),
        source_basis=(),
        warnings=(),
    )

    expanded = expanded_search_query("what am I working on now?", pack, max_terms=12)

    assert "live" in expanded
    assert "memory" in expanded
    assert "roots" in expanded
    assert "quality" in expanded
    assert "gate" in expanded
    assert "Users" not in expanded
    assert "testuser" not in expanded
    assert "project" not in expanded
    assert "brain" not in expanded
    assert "capabilities" not in expanded
    assert "skills" not in expanded
    assert "knowledge" not in expanded


def test_expanded_search_query_masks_relative_and_space_containing_paths() -> None:
    from skills.knowledge.scripts.mcp.ask_context_pack import ContextPack, SourceCandidate, expanded_search_query

    pack = ContextPack(
        intent="current_focus",
        candidates=(
            SourceCandidate(
                family="codex_memory",
                path=None,
                path_label="Codex memory: rollout.md",
                text=(
                    "Review (`project-brain/capabilities/skills/knowledge/augur/pages/adaptive.json`) "
                    "and '~/Library/Application Support/Augur/state/current focus.json' "
                    "plus (\"C:\\Users\\guri\\Application Support\\Augur\\state\\adaptive.json\") "
                    "still points at live memory roots quality gate."
                ),
                updated_at="2026-05-27T12:00:00+00:00",
                freshness=1.0,
                score=2.0,
            ),
        ),
        source_basis=(),
        warnings=(),
    )

    expanded = expanded_search_query("what am I working on now?", pack, max_terms=12)

    assert "live" in expanded
    assert "memory" in expanded
    assert "roots" in expanded
    assert "quality" in expanded
    assert "gate" in expanded
    assert "project" not in expanded
    assert "brain" not in expanded
    assert "capabilities" not in expanded
    assert "skills" not in expanded
    assert "knowledge" not in expanded
    assert "Support" not in expanded
    assert "state" not in expanded
    assert "adaptive" not in expanded
    assert "json" not in expanded


def test_match_terms_excludes_generic_stopwords() -> None:
    from skills.knowledge.scripts.mcp.ask_context_pack import _match_terms

    query = "top 10 interview questions for an AI champion role"
    text = "This page is for the overview of which questions exist."
    # "for" / "which" are generic; "questions" is content and present.
    assert _match_terms(query, text) == ("questions",)


def test_match_terms_empty_for_generic_only_query() -> None:
    from skills.knowledge.scripts.mcp.ask_context_pack import _match_terms

    # Every term generic -> no matches, ranking falls back to source/freshness.
    assert _match_terms("what about this and that", "what about this and that") == ()


def test_keyword_score_uses_content_term_denominator() -> None:
    from skills.knowledge.scripts.mcp.ask_context_pack import _keyword_score

    query = "interview questions for the role"
    # content terms: interview, questions, role -> 2 of 3 matched
    text = "interview prep and questions bank"
    assert abs(_keyword_score(query, text) - 2 / 3) < 1e-9


def test_wiki_meta_pages_score_below_topical_pages(tmp_path) -> None:
    from skills.knowledge.scripts.mcp.ask_context_pack import SourceRoot, _candidate_for_file

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    body = "career interview preparation questions and salary negotiation stories"
    (wiki / "overview.md").write_text(f"# Wiki Overview\n{body}", encoding="utf-8")
    (wiki / "career-interview.md").write_text(f"# Career\n{body}", encoding="utf-8")
    (wiki / "knowledge-gaps.md").write_text(
        f"---\ntitle: Gaps\n_page_type: query\n---\n{body}", encoding="utf-8"
    )

    root = SourceRoot("augur_wiki", wiki, "Augur wiki", True)
    query = "career interview questions"
    kwargs = {"intent": "reflective", "current_date": "2026-06-12"}
    topical = _candidate_for_file(root, wiki / "career-interview.md", query, **kwargs)
    overview = _candidate_for_file(root, wiki / "overview.md", query, **kwargs)
    query_page = _candidate_for_file(root, wiki / "knowledge-gaps.md", query, **kwargs)

    assert topical.score > overview.score
    assert topical.score > query_page.score
    # The demotion is exactly the source-priority delta (1.2 -> 0.6)
    assert abs((topical.score - overview.score) - 0.6) < 0.2


def test_personal_vault_is_a_scored_source_family(tmp_path) -> None:
    from skills.knowledge.scripts.mcp.ask_context_pack import (
        _source_priority,
        discover_source_roots,
    )

    assert _source_priority("personal_vault", "reflective") == 0.95
    assert _source_priority("personal_vault", "current_focus") == 0.85

    vault = tmp_path / "vault"
    wiki = vault / "wiki"
    memory = vault / "_augur" / "knowledge" / "memory"
    runtime = tmp_path / "runtime"
    for d in (wiki, memory, runtime):
        d.mkdir(parents=True)
    (vault / "MEMORY.md").write_text("curated vault index", encoding="utf-8")

    roots = discover_source_roots(
        vault_dir=vault, wiki_dir=wiki, vault_memory_dir=memory,
        runtime_dir=runtime, project_root=tmp_path / "repo",
    )
    assert "personal_vault" in {root.family for root in roots}


def test_candidate_for_search_hit_maps_families(tmp_path) -> None:
    from skills.knowledge.scripts.mcp.ask_context_pack import candidate_for_search_hit

    vault = tmp_path / "vault"
    wiki = vault / "wiki"
    career = vault / "career"
    for d in (wiki, career):
        d.mkdir(parents=True)
    note = career / "interview-prep.md"
    note.write_text("# Interview prep\nsalary negotiation stories", encoding="utf-8")
    wiki_page = wiki / "career-hub.md"
    wiki_page.write_text("# Career hub\ninterview synthesis", encoding="utf-8")

    kwargs = {"vault_dir": vault, "wiki_dir": wiki,
              "query": "interview salary negotiation", "intent": "reflective",
              "current_date": "2026-06-12"}
    vault_cand = candidate_for_search_hit({"file": str(note)}, **kwargs)
    wiki_cand = candidate_for_search_hit({"file": str(wiki_page)}, **kwargs)
    outside = candidate_for_search_hit({"file": "/etc/hosts"}, **kwargs)

    assert vault_cand.family == "personal_vault"
    assert wiki_cand.family == "augur_wiki"
    assert outside is None


def test_sort_candidates_ranks_matching_vault_note_over_generic_wiki(tmp_path) -> None:
    from skills.knowledge.scripts.mcp.ask_context_pack import (
        SourceRoot, _candidate_for_file, sort_candidates,
    )

    vault = tmp_path / "vault"
    wiki = vault / "wiki"
    career = vault / "career"
    for d in (wiki, career):
        d.mkdir(parents=True)
    note = career / "interview-prep.md"
    note.write_text("interview questions salary negotiation champion", encoding="utf-8")
    overview = wiki / "overview.md"
    overview.write_text("This wiki has 81 pages across hubs.", encoding="utf-8")

    query = "interview questions salary negotiation"
    kwargs = {"intent": "reflective", "current_date": "2026-06-12"}
    cands = [
        _candidate_for_file(SourceRoot("augur_wiki", wiki, "Augur wiki", True), overview, query, **kwargs),
        _candidate_for_file(SourceRoot("personal_vault", vault, "Personal vault", False), note, query, **kwargs),
    ]
    ranked = sort_candidates(cands, "reflective", query)
    assert ranked[0].family == "personal_vault"


def test_candidate_for_search_hit_resolves_rag_document_chunks(tmp_path) -> None:
    """BM25 document-chunk hits (relative paths) become personal_vault candidates."""
    from skills.knowledge.scripts.mcp.ask_context_pack import candidate_for_search_hit

    vault = tmp_path / "vault"
    wiki = vault / "wiki"
    wiki.mkdir(parents=True)
    rag = tmp_path / "rag"
    chunk = rag / "chunks" / "documents" / "career" / "Interview" / "_13.md"
    chunk.parent.mkdir(parents=True)
    chunk.write_text("Q: Tell me about a transformation you led.", encoding="utf-8")

    hit = {
        "file": "chunks/documents/career/Interview/_13.md",
        "source": "50 Common Interview Questions",
    }
    cand = candidate_for_search_hit(
        hit, vault_dir=vault, wiki_dir=wiki, rag_dir=rag,
        query="interview transformation", intent="reflective",
        current_date="2026-06-12",
    )
    assert cand is not None
    assert cand.family == "personal_vault"
    assert cand.path_label == "Personal documents: 50 Common Interview Questions"
    assert "transformation" in cand.text
    # Chunk mtimes are index-build artifacts, not content dates.
    assert cand.updated_at is None
    assert cand.freshness == 0.45
