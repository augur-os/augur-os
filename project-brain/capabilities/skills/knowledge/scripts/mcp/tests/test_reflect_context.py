"""Tests for reflect-context MCP tool."""
from __future__ import annotations

from contextlib import contextmanager
import os
import tempfile
from pathlib import Path
from unittest.mock import patch


@contextmanager
def _patch_context_dirs(
    vault: Path,
    memory: Path,
    wiki: Path,
    *,
    vault_memory: Path | None = None,
    project_root: Path | None = None,
    codex_home: Path | None = None,
):
    vault_memory = vault_memory or vault / "memory"
    project_root = project_root or vault.parent / "repo"
    codex_home = codex_home or vault.parent / "codex-home"
    env = {
        "HOME": str(codex_home.parent / "home"),
        "CODEX_HOME": str(codex_home),
        "AUGUR_ASK_MEMORY_ROOTS": "",
    }
    with patch("skills.knowledge.scripts.mcp.tools_reflect.get_vault_dir", return_value=vault), \
         patch("skills.knowledge.scripts.mcp.tools_reflect.get_runtime_dir", return_value=memory.parent), \
         patch("skills.knowledge.scripts.mcp.tools_reflect.get_compiled_wiki_dir", return_value=wiki), \
         patch("skills.knowledge.scripts.mcp.tools_reflect.get_memory_dir", return_value=vault_memory, create=True), \
         patch("skills.knowledge.scripts.mcp.tools_reflect.get_project_root", return_value=project_root, create=True), \
         patch(
             "skills.knowledge.scripts.mcp.tools_reflect.ensure_fresh_index",
             return_value={"stale": False, "synced": False, "warning": None},
             create=True,
         ), \
         patch.dict(os.environ, env, clear=False):
        yield


def test_assemble_reflection_context_returns_valid_shape():
    """reflect-context must return identity, relevant_memories, domain_context, recent_focus."""
    from skills.knowledge.scripts.mcp.tools_reflect import assemble_reflection_context

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mem = tmp_path / "memory"
        mem.mkdir()
        vault = tmp_path / "vault"
        vault.mkdir()
        wiki = vault / "wiki"
        wiki.mkdir()

        with _patch_context_dirs(vault, mem, wiki):
            result = assemble_reflection_context(query="What do I know about leadership?")

    assert isinstance(result, dict)
    assert "identity" in result
    assert "relevant_memories" in result
    assert "domain_context" in result
    assert "recent_focus" in result
    assert isinstance(result["relevant_memories"], list)
    assert isinstance(result["domain_context"], list)


def _make_memory_dir(tmp: Path) -> Path:
    """Create a test memory directory with sample entries and digest."""
    mem = tmp / "memory"
    mem.mkdir()
    entries = mem / "entries"
    entries.mkdir()

    # Preference entry
    (entries / "claude-code_preference_no-emojis.md").write_text(
        "---\nname: no-emojis\ntype: preference\n---\nNo emojis unless explicitly requested.\n"
    )
    # Feedback entry
    (entries / "claude-code_feedback_concise-responses.md").write_text(
        "---\nname: concise-responses\ntype: feedback\n---\nKeep responses concise and direct.\n"
    )
    # Project entry (should NOT be in identity)
    (entries / "claude-code_project_some-project.md").write_text(
        "---\nname: some-project\ntype: project\n---\nSome project details.\n"
    )

    # Digest
    (mem / "digest-hot.md").write_text(
        "## Hot Directives\n- Focus on X this week\n- Avoid Y pattern\n"
    )

    return mem


def test_identity_loads_preferences_and_feedback():
    """Identity section should include preference and feedback entries, not project entries."""
    from skills.knowledge.scripts.mcp.tools_reflect import assemble_reflection_context

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mem = _make_memory_dir(tmp_path)
        vault = tmp_path / "vault"
        vault.mkdir()
        wiki = vault / "wiki"
        wiki.mkdir()

        with _patch_context_dirs(vault, mem, wiki):
            result = assemble_reflection_context(query="test")

    assert "emojis" in result["identity"].lower() or "concise" in result["identity"].lower()
    assert "some project" not in result["identity"].lower()


def test_identity_prioritizes_preferences_over_old_feedback():
    """Small identity budgets should not be consumed by old technical feedback first."""
    from skills.knowledge.scripts.mcp.tools_reflect import assemble_reflection_context

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mem = tmp_path / "memory"
        entries = mem / "entries"
        entries.mkdir(parents=True)
        (entries / "claude-code_feedback_adaptive-engine-daemon.md").write_text(
            "---\nname: adaptive-engine-daemon\ntype: feedback\n---\n"
            "Adaptive engine, daemon, scanner, and trust state internals. " * 20,
            encoding="utf-8",
        )
        (entries / "claude-code_preference_no-emojis.md").write_text(
            "---\nname: no-emojis\ntype: preference\n---\nNo emojis unless explicitly requested.\n",
            encoding="utf-8",
        )
        vault = tmp_path / "vault"
        vault.mkdir()
        wiki = vault / "wiki"
        wiki.mkdir()

        with _patch_context_dirs(vault, mem, wiki):
            result = assemble_reflection_context(query="test", token_budget=240)

    assert "no emojis" in result["identity"].lower()
    assert "adaptive-engine-daemon" not in result["identity"].lower()


def test_recent_focus_loads_digest():
    """Recent focus should come from digest-hot.md."""
    from skills.knowledge.scripts.mcp.tools_reflect import assemble_reflection_context

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mem = _make_memory_dir(tmp_path)
        vault = tmp_path / "vault"
        vault.mkdir()
        wiki = vault / "wiki"
        wiki.mkdir()

        with _patch_context_dirs(vault, mem, wiki):
            result = assemble_reflection_context(query="test")

    assert "Focus on X" in result["recent_focus"] or "Hot Directives" in result["recent_focus"]


def test_strip_technical_metadata():
    """Output must not contain ADR numbers, file paths, or code blocks."""
    from skills.knowledge.scripts.mcp.tools_reflect import _strip_technical_metadata

    raw = """
This is about ADR-163 decentralization.
See /Users/example/Projects/Augur/skills/ask/SKILL.md for details.
Also check skills/knowledge/scripts/mcp/tools_reflect.py and docs/references/design.md.
```python
def example():
    pass
```
The user prefers concise responses.
"""
    result = _strip_technical_metadata(raw)

    assert "ADR-163" not in result
    assert "/Users/" not in result
    assert "skills/" not in result
    assert "docs/" not in result
    assert "def example" not in result
    assert "concise responses" in result


def test_strip_frontmatter():
    """YAML frontmatter should be removed."""
    from skills.knowledge.scripts.mcp.tools_reflect import _strip_technical_metadata

    raw = """---
name: test
type: feedback
created: 2026-03-25
---

The user prefers tables over prose."""

    result = _strip_technical_metadata(raw)

    assert "name: test" not in result
    assert "type: feedback" not in result
    assert "tables over prose" in result


def test_truncate_to_budget():
    """Text should be truncated to fit within token budget."""
    from skills.knowledge.scripts.mcp.tools_reflect import _truncate_to_budget, _estimate_tokens

    long_text = "This is a sentence. " * 500  # ~2500 tokens
    result = _truncate_to_budget(long_text, token_budget=100)

    assert _estimate_tokens(result) <= 120  # Allow small overshoot from sentence boundary
    assert result.endswith(".")  # Should end at sentence boundary


def test_total_output_respects_budget():
    """Total assembled context should not wildly exceed the token budget."""
    from skills.knowledge.scripts.mcp.tools_reflect import assemble_reflection_context, _estimate_tokens

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mem = _make_memory_dir(tmp_path)
        vault = tmp_path / "vault"
        vault.mkdir()
        wiki = vault / "wiki"
        wiki.mkdir()

        with _patch_context_dirs(vault, mem, wiki):
            result = assemble_reflection_context(query="test", token_budget=2000)

    total_text = result["identity"] + result["recent_focus"] + \
        " ".join(result["relevant_memories"]) + " ".join(result["domain_context"])
    total_tokens = _estimate_tokens(total_text)

    # Should not exceed budget by more than 50% (generous margin for baseline content)
    assert total_tokens <= 3000


def test_assemble_reflection_context_tolerates_non_utf8_vault_hits():
    """Vault search should not fail when ripgrep returns non-UTF8 bytes."""
    from skills.knowledge.scripts.mcp.tools_reflect import assemble_reflection_context

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mem = _make_memory_dir(tmp_path)
        vault = tmp_path / "vault"
        vault.mkdir()
        wiki = vault / "wiki"
        wiki.mkdir()
        bad_file = vault / "bad-note.md"
        bad_file.write_bytes(b"bad-note.md:1:Curly quote \x93 still searchable")

        with _patch_context_dirs(vault, mem, wiki):
            result = assemble_reflection_context(query="Curly")

    assert isinstance(result, dict)
    assert result["identity"]


def test_assemble_reflection_context_prefers_wiki_before_raw_domain_hits():
    """Compiled wiki content should appear before raw domain content and not duplicate."""
    from skills.knowledge.scripts.mcp.tools_reflect import assemble_reflection_context

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mem = _make_memory_dir(tmp_path)
        vault = tmp_path / "vault"
        vault.mkdir()

        wiki = vault / "wiki"
        wiki.mkdir()
        (wiki / "compiled-brain.md").write_text(
            "Wiki compounding insight about leadership and calibration."
        )

        raw_domain = vault / "projects" / "alpha"
        raw_domain.mkdir(parents=True)
        (raw_domain / "raw-one.md").write_text("Raw project note one about leadership.")
        (raw_domain / "raw-two.md").write_text("Raw project note two about leadership.")

        with _patch_context_dirs(vault, mem, wiki):
            result = assemble_reflection_context(query="leadership")

    joined_context = "\n".join(result["domain_context"]).lower()
    wiki_text = "wiki compounding insight about leadership and calibration."
    raw_text = "raw project note one about leadership."

    assert result["domain_context"]
    assert result["domain_context"][0].lower().startswith("wiki compounding insight")
    assert joined_context.count(wiki_text) == 1
    assert raw_text in joined_context


def test_low_signal_context_is_filtered():
    """Bare bullets and punctuation-only fragments should be treated as noise."""
    from skills.knowledge.scripts.mcp.tools_reflect import _is_low_signal_context

    assert _is_low_signal_context("-")
    assert _is_low_signal_context("•")
    assert _is_low_signal_context(" - ")
    assert _is_low_signal_context("Metadata-only seed page generated from scanned sources.")
    assert not _is_low_signal_context("This is a meaningful summary sentence.")


def test_extract_hit_context_prefers_full_wiki_page_over_fragment():
    """Compiled wiki hits should use page-level content when the snippet is too thin."""
    from skills.knowledge.scripts.mcp.tools_reflect import _extract_hit_context

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        wiki_page = tmp_path / "wiki-page.md"
        wiki_page.write_text(
            "---\ntitle: Test Wiki Page\n---\n# Test Wiki Page\n\nThis compiled page explains the local-first wiki model clearly.\n",
            encoding="utf-8",
        )

        hit = {"file": str(wiki_page), "content": "-"}
        extracted = _extract_hit_context(hit, prefer_full_page=True)

    assert extracted.startswith("Test Wiki Page") or extracted.startswith("This compiled page")
    assert extracted != "-"


def test_collect_context_from_hits_dedupes_equivalent_content():
    """Equivalent cleaned snippets should only appear once in assembled context."""
    from skills.knowledge.scripts.mcp.tools_reflect import _collect_context_from_hits

    hits = [
        {"file": "/tmp/a.md", "content": "Wiki compounding improves answer quality."},
        {"file": "/tmp/b.md", "content": "Wiki compounding improves answer quality.\n"},
    ]

    collected = _collect_context_from_hits(hits, token_budget=200)

    assert collected == ["Wiki compounding improves answer quality."]


def test_assemble_reflection_context_includes_live_context_source_basis():
    """reflect-context should expose source metadata for /ask source-basis reporting."""
    from skills.knowledge.scripts.mcp.tools_reflect import assemble_reflection_context

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mem = _make_memory_dir(tmp_path)
        vault = tmp_path / "vault"
        wiki = vault / "wiki"
        vault_memory = vault / "memory"
        vault_memory.mkdir(parents=True)
        wiki.mkdir(parents=True)
        (wiki / "active-projects.md").write_text(
            "---\nupdated: '2026-05-12T21:35:19+00:00'\n---\nOlder wiki focus.\n",
            encoding="utf-8",
        )

        with _patch_context_dirs(vault, mem, wiki, vault_memory=vault_memory):
            result = assemble_reflection_context(
                query="what am I working on now?",
                token_budget=2000,
            )

    assert "source_basis" in result
    assert "quality_sources" in result
    assert "context_warnings" in result
    assert result["retrieval_intent"] == "current_focus"
    assert isinstance(result["source_basis"], list)
    assert isinstance(result["quality_sources"], list)
    assert isinstance(result["context_warnings"], list)
    assert result["quality_sources"]
    assert any("updated_at" in source for source in result["quality_sources"])
    assert any("Augur wiki" in basis for basis in result["source_basis"])


def test_live_context_is_added_before_broad_domain_context():
    """Current-focus context should be visible before older broad wiki context."""
    from skills.knowledge.scripts.mcp.tools_reflect import assemble_reflection_context

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mem = _make_memory_dir(tmp_path)
        vault = tmp_path / "vault"
        wiki = vault / "wiki"
        wiki.mkdir(parents=True)
        codex_home = tmp_path / "codex-home"
        codex_memory = codex_home / "memories"
        codex_memory.mkdir(parents=True)
        (codex_memory / "MEMORY.md").write_text(
            "Fresh focus: live memory roots quality gate.",
            encoding="utf-8",
        )
        (wiki / "active-projects.md").write_text(
            "---\nupdated: '2026-05-12T21:35:19+00:00'\n---\nOlder stabilization work.\n",
            encoding="utf-8",
        )

        with _patch_context_dirs(vault, mem, wiki, codex_home=codex_home):
            result = assemble_reflection_context(query="what am I working on now?")

    joined = "\n".join(result["domain_context"])
    assert "Fresh focus: live memory roots quality gate." in joined
    assert "Older stabilization work" in joined
    assert joined.index("Fresh focus: live memory roots quality gate.") < joined.index(
        "Older stabilization work"
    )


def test_repo_context_is_added_to_recent_focus():
    """Current-focus repo evidence should augment recent_focus instead of domain_context."""
    from skills.knowledge.scripts.mcp.ask_context_pack import SourceCandidate
    from skills.knowledge.scripts.mcp.tools_reflect import assemble_reflection_context

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mem = _make_memory_dir(tmp_path)
        vault = tmp_path / "vault"
        wiki = vault / "wiki"
        wiki.mkdir(parents=True)
        project_root = tmp_path / "repo"
        (project_root / ".git").mkdir(parents=True)

        def fake_repo_candidate(project_root_arg, query, *, intent, current_date):  # noqa: ANN001, ANN003
            assert project_root_arg == project_root
            assert intent == "current_focus"
            return SourceCandidate(
                family="repo_evidence",
                path=project_root,
                path_label="Augur repo: recent commits",
                text="abc123 live memory roots quality gate",
                updated_at=f"{current_date}T00:00:00+00:00",
                freshness=1.0,
                score=2.0,
                reasons=("recent-git-log",),
                current_focus_eligible=True,
            )

        with _patch_context_dirs(vault, mem, wiki, project_root=project_root), \
             patch("skills.knowledge.scripts.mcp.ask_context_pack._repo_candidate", fake_repo_candidate):
            result = assemble_reflection_context(query="what am I working on now?")

    assert "live memory roots quality gate" in result["recent_focus"]
    assert "live memory roots quality gate" not in "\n".join(result["domain_context"])


def test_repo_context_survives_long_digest_focus_budget():
    """Repo evidence should remain in recent_focus even when digest-hot fills the budget."""
    from skills.knowledge.scripts.mcp.ask_context_pack import SourceCandidate
    from skills.knowledge.scripts.mcp.tools_reflect import (
        _estimate_tokens,
        assemble_reflection_context,
    )

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mem = _make_memory_dir(tmp_path)
        (mem / "digest-hot.md").write_text(("Digest filler sentence. " * 80).strip(), encoding="utf-8")
        vault = tmp_path / "vault"
        vault.mkdir()
        wiki = vault / "wiki"
        wiki.mkdir()
        project_root = tmp_path / "repo"
        (project_root / ".git").mkdir(parents=True)

        def fake_repo_candidate(project_root_arg, query, *, intent, current_date):  # noqa: ANN001, ANN003
            assert project_root_arg == project_root
            assert intent == "current_focus"
            return SourceCandidate(
                family="repo_evidence",
                path=project_root,
                path_label="Augur repo: recent commits",
                text="abc123 live memory roots quality gate",
                updated_at=f"{current_date}T00:00:00+00:00",
                freshness=1.0,
                score=2.0,
                reasons=("recent-git-log",),
                current_focus_eligible=True,
            )

        token_budget = 130
        focus_budget = min(300, token_budget // 13)
        with _patch_context_dirs(vault, mem, wiki, project_root=project_root), \
             patch("skills.knowledge.scripts.mcp.ask_context_pack._repo_candidate", fake_repo_candidate):
            result = assemble_reflection_context(
                query="what am I working on now?",
                token_budget=token_budget,
            )

    assert "live memory roots quality gate" in result["recent_focus"]
    assert _estimate_tokens(result["recent_focus"]) <= focus_budget


def test_rollout_candidate_is_sanitized_and_bounded_in_visible_context_and_quality_sources():
    """Codex rollout scaffolding should not leak into reflect-visible context or source text."""
    from skills.knowledge.scripts.mcp.ask_context_pack import ContextPack, SourceCandidate
    from skills.knowledge.scripts.mcp.tools_reflect import assemble_reflection_context

    rollout_text = (
        "session_meta: {\"payload\": {\"id\": \"019de286-bc5f\"}}\n"
        "event_msg: branch main status passed\n"
        "response_item: tool call output\n"
        "rollout_path: /Users/example/.codex/sessions/rollout.jsonl\n"
        "updated_at=2026-05-27T12:00:00+00:00\n"
        "Current focus: live memory roots quality gate.\n"
        + ("Detailed user-visible support sentence. " * 80)
    )
    candidate = SourceCandidate(
        family="codex_memory",
        path=None,
        path_label="Codex memory: rollout.md",
        text=rollout_text,
        updated_at="2026-05-27T12:00:00+00:00",
        freshness=1.0,
        score=2.0,
    )
    pack = ContextPack(
        intent="current_focus",
        candidates=(candidate,),
        source_basis=("Codex memory: rollout.md updated 2026-05-27",),
        warnings=(),
    )

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mem = _make_memory_dir(tmp_path)
        vault = tmp_path / "vault"
        vault.mkdir()
        wiki = vault / "wiki"
        wiki.mkdir()

        with _patch_context_dirs(vault, mem, wiki), \
             patch("skills.knowledge.scripts.mcp.tools_reflect.build_context_pack", return_value=pack), \
             patch("skills.knowledge.scripts.mcp.tools_reflect.expanded_search_query", side_effect=lambda query, _pack: query), \
             patch("skills.knowledge.scripts.mcp.tools_reflect.iterative_search", return_value=[]):
            result = assemble_reflection_context(query="what am I working on now?", token_budget=500)

    visible_text = "\n".join(result["domain_context"])
    quality_text = "\n".join(str(source["text"]) for source in result["quality_sources"])
    combined = f"{visible_text}\n{quality_text}"

    assert "live memory roots quality gate" in combined
    assert "session_meta" not in combined
    assert "event_msg" not in combined
    assert "response_item" not in combined
    assert "rollout_path" not in combined
    assert "updated_at" not in combined
    assert "/Users/" not in combined
    assert result["quality_sources"]
    assert len(str(result["quality_sources"][0]["text"])) <= 480


def test_turn_context_cwd_and_branch_scaffolding_do_not_leak_to_visible_sources():
    """Rollout turn/cwd/branch metadata should be stripped from visible support text."""
    from skills.knowledge.scripts.mcp.ask_context_pack import ContextPack, SourceCandidate
    from skills.knowledge.scripts.mcp.tools_reflect import assemble_reflection_context

    candidate = SourceCandidate(
        family="codex_memory",
        path=None,
        path_label="Codex memory: rollout.md",
        text=(
            "turn_context: {\"cwd\": \"/Users/example/Projects/Augur\", "
            "\"branch\": \"codex/ask-live-memory-roots\"}\n"
            "cwd: /Users/example/Projects/Augur/.worktrees/ask-live-memory-roots\n"
            "branch: codex/ask-live-memory-roots\n"
            "git_branch: codex/ask-live-memory-roots\n"
            "Visible live-memory source sentence for source-basis review."
        ),
        updated_at="2026-05-27T12:00:00+00:00",
        freshness=1.0,
        score=2.0,
    )
    pack = ContextPack(
        intent="current_focus",
        candidates=(candidate,),
        source_basis=("Codex memory: rollout.md updated 2026-05-27",),
        warnings=(),
    )

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mem = _make_memory_dir(tmp_path)
        vault = tmp_path / "vault"
        vault.mkdir()
        wiki = vault / "wiki"
        wiki.mkdir()

        with _patch_context_dirs(vault, mem, wiki), \
             patch("skills.knowledge.scripts.mcp.tools_reflect.build_context_pack", return_value=pack), \
             patch("skills.knowledge.scripts.mcp.tools_reflect.expanded_search_query", side_effect=lambda query, _pack: query), \
             patch("skills.knowledge.scripts.mcp.tools_reflect.iterative_search", return_value=[]):
            result = assemble_reflection_context(query="what am I working on now?")

    visible_text = "\n".join(result["domain_context"])
    quality_text = "\n".join(str(source["text"]) for source in result["quality_sources"])
    combined = f"{visible_text}\n{quality_text}"

    assert "Visible live-memory source sentence" in combined
    assert "turn_context" not in combined
    assert "cwd" not in combined
    assert "branch" not in combined
    assert "/Users/" not in combined


def test_live_context_candidate_duplicate_of_relevant_memory_is_not_repeated():
    """Live candidates already present in relevant_memories should not reappear as domain support."""
    from skills.knowledge.scripts.mcp.ask_context_pack import ContextPack, SourceCandidate
    from skills.knowledge.scripts.mcp.tools_reflect import assemble_reflection_context

    duplicate_text = "Shared memory source sentence about live memory root review."
    candidate = SourceCandidate(
        family="vault_memory",
        path=None,
        path_label="Vault memory: shared.md",
        text=duplicate_text,
        updated_at="2026-05-27T12:00:00+00:00",
        freshness=1.0,
        score=2.0,
    )
    pack = ContextPack(
        intent="current_focus",
        candidates=(candidate,),
        source_basis=("Vault memory: shared.md updated 2026-05-27",),
        warnings=(),
    )

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mem = _make_memory_dir(tmp_path)
        vault = tmp_path / "vault"
        vault.mkdir()
        wiki = vault / "wiki"
        wiki.mkdir()
        memory_hit_file = vault / "memory" / "shared.md"
        memory_hit_file.parent.mkdir(parents=True)

        def fake_search(query, source_dirs, priority_dirs, rag_dirs, **kwargs):  # noqa: ANN001
            if vault in priority_dirs:
                return [{"file": str(memory_hit_file), "content": duplicate_text}]
            return []

        with _patch_context_dirs(vault, mem, wiki), \
             patch("skills.knowledge.scripts.mcp.tools_reflect.build_context_pack", return_value=pack), \
             patch("skills.knowledge.scripts.mcp.tools_reflect.expanded_search_query", side_effect=lambda query, _pack: query), \
             patch("skills.knowledge.scripts.mcp.tools_reflect.iterative_search", side_effect=fake_search):
            result = assemble_reflection_context(query="what am I working on now?")

    quality_text = "\n".join(str(source["text"]) for source in result["quality_sources"])

    assert duplicate_text in "\n".join(result["relevant_memories"])
    assert duplicate_text not in "\n".join(result["domain_context"])
    assert duplicate_text not in quality_text


def test_domain_context_respects_budget_after_live_prepend():
    """Live context should keep priority without making domain_context exceed its budget."""
    from skills.knowledge.scripts.mcp.ask_context_pack import ContextPack, SourceCandidate
    from skills.knowledge.scripts.mcp.tools_reflect import _estimate_tokens, assemble_reflection_context

    live_candidate = SourceCandidate(
        family="codex_memory",
        path=None,
        path_label="Codex memory: MEMORY.md",
        text="Live priority context sentence. " * 80,
        updated_at="2026-05-27T12:00:00+00:00",
        freshness=1.0,
        score=2.0,
    )
    pack = ContextPack(
        intent="current_focus",
        candidates=(live_candidate,),
        source_basis=("Codex memory: MEMORY.md updated 2026-05-27",),
        warnings=(),
    )
    broad_hit = {"file": "", "content": "Broad domain context sentence. " * 80}

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mem = _make_memory_dir(tmp_path)
        vault = tmp_path / "vault"
        vault.mkdir()
        wiki = vault / "wiki"
        wiki.mkdir()

        token_budget = 160
        identity_budget = min(500, token_budget // 8)
        focus_budget = min(300, token_budget // 13)
        memory_budget = min(1500, token_budget * 3 // 8)
        domain_budget = token_budget - identity_budget - focus_budget - memory_budget
        with _patch_context_dirs(vault, mem, wiki), \
             patch("skills.knowledge.scripts.mcp.tools_reflect.build_context_pack", return_value=pack), \
             patch("skills.knowledge.scripts.mcp.tools_reflect.expanded_search_query", side_effect=lambda query, _pack: query), \
             patch("skills.knowledge.scripts.mcp.tools_reflect.iterative_search", return_value=[broad_hit]):
            result = assemble_reflection_context(
                query="what am I working on now?",
                token_budget=token_budget,
            )

    joined_domain = " ".join(result["domain_context"])
    returned_visible = " ".join(
        [
            result["identity"],
            result["recent_focus"],
            " ".join(result["relevant_memories"]),
            joined_domain,
            " ".join(str(source["text"]) for source in result["quality_sources"]),
        ]
    )
    assert result["domain_context"][0].startswith("Live priority context")
    assert _estimate_tokens(joined_domain) <= domain_budget
    assert _estimate_tokens(returned_visible) <= token_budget * 2


def test_quality_sources_only_include_visible_live_candidates():
    """Invisible context-pack candidates should not be reported as quality support."""
    from skills.knowledge.scripts.mcp.ask_context_pack import ContextPack, SourceCandidate
    from skills.knowledge.scripts.mcp.tools_reflect import assemble_reflection_context

    candidates = tuple(
        SourceCandidate(
            family="codex_memory",
            path=None,
            path_label=f"Codex memory: visible-{index}.md",
            text=f"Visible candidate {index} drives answer support.",
            updated_at="2026-05-27T12:00:00+00:00",
            freshness=1.0,
            score=2.0,
        )
        for index in range(1, 5)
    )
    pack = ContextPack(
        intent="current_focus",
        candidates=candidates,
        source_basis=tuple(candidate.path_label for candidate in candidates),
        warnings=(),
    )

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mem = _make_memory_dir(tmp_path)
        vault = tmp_path / "vault"
        vault.mkdir()
        wiki = vault / "wiki"
        wiki.mkdir()

        with _patch_context_dirs(vault, mem, wiki), \
             patch("skills.knowledge.scripts.mcp.tools_reflect.build_context_pack", return_value=pack), \
             patch("skills.knowledge.scripts.mcp.tools_reflect.expanded_search_query", side_effect=lambda query, _pack: query), \
             patch("skills.knowledge.scripts.mcp.tools_reflect.iterative_search", return_value=[]):
            result = assemble_reflection_context(query="what am I working on now?")

    quality_labels = [source["path_label"] for source in result["quality_sources"]]
    joined_domain = "\n".join(result["domain_context"])

    assert quality_labels == [
        "Codex memory: visible-1.md",
        "Codex memory: visible-2.md",
        "Codex memory: visible-3.md",
    ]
    assert "Visible candidate 4" not in joined_domain


def test_broad_search_receives_expanded_context_pack_query():
    """Broad wiki/vault search should run with the context-pack-expanded query."""
    from skills.knowledge.scripts.mcp.ask_context_pack import ContextPack
    from skills.knowledge.scripts.mcp.tools_reflect import assemble_reflection_context

    pack = ContextPack(intent="current_focus", candidates=(), source_basis=(), warnings=())
    seen_queries: list[str] = []

    def fake_search(query, source_dirs, priority_dirs, rag_dirs, **kwargs):  # noqa: ANN001
        seen_queries.append(query)
        return []

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mem = _make_memory_dir(tmp_path)
        vault = tmp_path / "vault"
        vault.mkdir()
        wiki = vault / "wiki"
        wiki.mkdir()

        with _patch_context_dirs(vault, mem, wiki), \
             patch("skills.knowledge.scripts.mcp.tools_reflect.build_context_pack", return_value=pack), \
             patch("skills.knowledge.scripts.mcp.tools_reflect.expanded_search_query", return_value="expanded live query"), \
             patch("skills.knowledge.scripts.mcp.tools_reflect.iterative_search", side_effect=fake_search):
            assemble_reflection_context(query="what am I working on now?")

    assert seen_queries
    assert set(seen_queries) == {"expanded live query"}


def test_memory_bucket_uses_memory_dir_not_top_level_name(tmp_path) -> None:
    """Memory hits are detected by get_memory_dir() containment (post-reorg layout)."""
    from skills.knowledge.scripts.mcp.tools_reflect import _split_memory_hits

    vault = tmp_path / "vault"
    memory = vault / "_augur" / "knowledge" / "memory"
    inside = memory / "entries" / "x.md"
    inside.parent.mkdir(parents=True)
    inside.write_text("m", encoding="utf-8")
    outside = vault / "career" / "note.md"
    outside.parent.mkdir(parents=True)
    outside.write_text("n", encoding="utf-8")

    mem, non_mem = _split_memory_hits(
        [{"file": str(inside)}, {"file": str(outside)}], memory_root=memory
    )
    assert [h["file"] for h in mem] == [str(inside)]
    assert [h["file"] for h in non_mem] == [str(outside)]


def test_reflect_ranks_vault_search_hits_into_domain_context(tmp_path) -> None:
    """A topical vault note found by search must beat a generic wiki overview."""
    from unittest.mock import patch

    from skills.knowledge.scripts.mcp.tools_reflect import assemble_reflection_context

    vault = tmp_path / "vault"
    wiki = vault / "wiki"
    career = vault / "career"
    memory = vault / "_augur" / "knowledge" / "memory"
    runtime = tmp_path / "runtime"
    for d in (wiki, career, memory, runtime / "memory"):
        d.mkdir(parents=True)
    (career / "interview-prep.md").write_text(
        "# Interview prep\nSTAR stories for salary negotiation and champion role interviews.",
        encoding="utf-8",
    )
    (wiki / "overview.md").write_text(
        "# Wiki Overview\nThis wiki spans 81 pages across hubs. Use the index for questions.",
        encoding="utf-8",
    )

    with _patch_context_dirs(vault, runtime / "memory", wiki, vault_memory=memory), \
         patch(
             "skills.knowledge.scripts.mcp.tools_reflect.get_rag_dir",
             return_value=tmp_path / "rag",
             create=True,
         ):
        result = assemble_reflection_context(
            "interview questions salary negotiation", token_budget=4000
        )

    joined = "\n".join(str(d) for d in result["domain_context"])
    assert "salary negotiation" in joined
    families = [s.get("source_family") for s in result["quality_sources"]]
    assert "personal_vault" in families
    # The topical vault note must rank above the generic wiki overview.
    if "81 pages" in joined:
        assert joined.find("STAR stories") < joined.find("81 pages")
