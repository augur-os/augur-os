"""Regression tests for `/dev-merge` workflow contract text."""
from __future__ import annotations

from pathlib import Path


def _find_project_root(start: Path) -> Path:
    for parent in start.parents:
        if (parent / "docs" / "agent-topics").is_dir() and (
            parent / "project-brain" / "capabilities" / "skills"
        ).is_dir():
            return parent
    raise RuntimeError(f"Unable to locate Augur project root from {start}")


PROJECT_ROOT = _find_project_root(Path(__file__).resolve())
DEV_MERGE_DOC = (
    PROJECT_ROOT / "project-brain/capabilities/skills/platform-admin/commands/dev-merge.md"
)
WORKFLOWS_DOC = PROJECT_ROOT / "docs/agent-topics/WORKFLOWS.md"


def _read(relative_path: str) -> str:
    candidate = PROJECT_ROOT / relative_path
    if candidate.exists():
        return candidate.read_text(encoding="utf-8")
    raise FileNotFoundError(relative_path)


def _normalized(text: str) -> str:
    return " ".join(text.split())


def test_dev_merge_command_requires_salvage_before_discard() -> None:
    text = _read("project-brain/capabilities/skills/platform-admin/commands/dev-merge.md")
    assert "classify leftover branch commits into" in text
    assert "already_in_main" in text
    assert "clean_salvage" in text
    assert "stale_or_conflicting" in text
    assert "auto-discard the leftover branch/worktree" in text


def test_dev_merge_command_requires_terminal_cleanup_after_verified_merge() -> None:
    text = _read("project-brain/capabilities/skills/platform-admin/commands/dev-merge.md")
    assert "successful verified merge" in text
    assert "remove the originating worktree" in text
    assert "delete the originating branch" in text
    assert "repair Codex thread state" in text
    assert "live AI/client process" in text
    assert "defer deletion" in text


def test_dev_merge_command_documents_purge_as_technical_leftovers_only() -> None:
    text = _read("project-brain/capabilities/skills/platform-admin/commands/dev-merge.md")
    assert "--purge" in text
    assert "technical leftovers" in text
    assert "no merge-worthy commits remain" in text


def test_dev_merge_command_documents_safe_sync_mode_for_diverged_main() -> None:
    text = _read("project-brain/capabilities/skills/platform-admin/commands/dev-merge.md")
    assert "`sync`" in text
    assert "ahead of or diverged from `origin/main`" in text
    assert "rebase local-only" in text
    assert "no force push" in text
    assert "safe sync" in text


def test_dev_merge_command_documents_purge_refusal_for_meaningful_changes() -> None:
    text = _read("project-brain/capabilities/skills/platform-admin/commands/dev-merge.md")
    assert "skip purge" in text
    assert "meaningful repo changes" in text
    assert "ambiguous" in text


def test_dev_merge_full_covers_configured_vault_repo() -> None:
    text = _read("project-brain/capabilities/skills/platform-admin/commands/dev-merge.md")
    assert "`full` mode includes the configured vault repository" in text
    assert "config/system/vault.yaml" in text
    assert "commit and push vault changes" in text
    assert "verify both remote tips" in text


def test_dev_merge_command_documents_demo_proof_flags() -> None:
    text = _read("project-brain/capabilities/skills/platform-admin/commands/dev-merge.md")
    assert "--com" in text
    assert "--compound-wiki" in text
    assert "--skillify" in text
    assert "--skilify" in text
    assert "pre-merge proof gates" in text
    assert "blocked before merge" in text


def test_dev_merge_command_documents_demo_proof_order() -> None:
    text = _normalized(
        _read("project-brain/capabilities/skills/platform-admin/commands/dev-merge.md")
    )
    assert "Run wiki proof before skillify proof" in text
    assert "continue the normal `/dev-merge full` contract unchanged" in text
    assert "<requested proof flags>" in text


def test_dev_merge_command_documents_demo_proof_default_paths() -> None:
    text = _normalized(
        _read("project-brain/capabilities/skills/platform-admin/commands/dev-merge.md")
    )
    assert "bootstraps Augur path helpers" in text
    assert "configured vault/runtime paths" in text
    assert "normal `/dev-merge full --com --skillify` callers" in text
    assert "do not pass" in text
    assert "`--vault-root`" in text
    assert "`--runtime-dir`" in text


def test_dev_merge_command_documents_demo_proof_wiki_status_blockers() -> None:
    text = _normalized(
        _read("project-brain/capabilities/skills/platform-admin/commands/dev-merge.md")
    )
    assert "wiki-status" in text
    assert "queued compile backlog" in text
    assert "no durable `wiki/` files changed" in text
    assert "verified no-op summary" in text
    assert "normal merge continues" in text
    assert "stale/low-coverage/current-low-coverage" in text
    assert "structure/compiler errors" in text
    assert "demo-readiness failures" in text
    assert "real page/query evidence" in text
    assert "freshness timestamp" in text
    assert "aggregate counts alone" in text
    assert "routing/quality evidence" in text
    assert "`skill:<name>` capability policy" in text
    assert "primary_skill" in text
    assert "auto-test-pytest" in text
    assert "missing/failing quality verification" in text
    assert "deletion-only skill diffs" in text
    assert "exit 2" in text
    assert "non-zero" in text


def test_dev_merge_command_documents_compound_review_preflight() -> None:
    text = DEV_MERGE_DOC.read_text(encoding="utf-8")
    normalized = _normalized(text)

    assert "Compound Review Preflight" in text
    assert "--compound-review" in text
    assert "--review-proposal-json" in text
    assert "native AI client supplies the proposal JSON" in normalized
    assert "does not write wiki, skill, or ADR files" in text
    assert "collects deterministic `--com`/`--skillify` evidence before attaching" in normalized
    assert "final output renders the compound review before the proof summaries" in normalized
    assert "merge remains blocked unless compound review and requested proof gates pass" in normalized
    assert "run after the review" not in normalized


def test_workflows_doc_documents_demo_proof_flags() -> None:
    text = _normalized(_read("docs/agent-topics/WORKFLOWS.md"))
    assert "/dev merge full --com --skillify" in text
    assert "wiki compounding summary" in text
    assert "skillify summary" in text
    assert "before merge/push" in text
    assert "stop before merge/push" in text


def test_workflows_doc_documents_demo_proof_wiki_status_blockers() -> None:
    text = _normalized(_read("docs/agent-topics/WORKFLOWS.md"))
    assert "wiki-status" in text
    assert "queued compile backlog" in text
    assert "no durable `wiki/` files changed" in text
    assert "verified no-op summary" in text
    assert "normal merge continues" in text
    assert "stale/low-coverage/current-low-coverage" in text
    assert "structure/compiler errors" in text
    assert "demo-readiness failures" in text
    assert "real page/query evidence" in text
    assert "freshness timestamp" in text
    assert "aggregate counts alone" in text
    assert "routing/quality evidence" in text
    assert "`skill:<name>` capability policy" in text
    assert "primary_skill" in text
    assert "auto-test-pytest" in text
    assert "missing/failing quality verification" in text
    assert "deletion-only" in text
    assert "exit 2" in text
    assert "non-zero" in text


def test_workflows_doc_documents_compound_review_preflight() -> None:
    text = WORKFLOWS_DOC.read_text(encoding="utf-8")
    normalized = _normalized(text)

    assert "Compound Review Preflight" in text
    assert "collect deterministic evidence" in text
    assert "native AI client supplies the proposal JSON" in text
    assert "proof gates remain deterministic" in text
    assert "does not write wiki, skill, or ADR files" in text
    assert "passing review is not proof durable artifacts changed" in normalized
    assert "missing, malformed, generic, or not evidence-backed" in normalized
    assert "run after the review" not in normalized


def test_workflows_doc_requires_mixed_branch_cleanup() -> None:
    text = _read("docs/agent-topics/WORKFLOWS.md")
    assert "Mixed Leftover Branch Recovery" in text
    assert "must not stop at \"branch still exists\"" in text
    assert "discard the leftover branch/worktree automatically" in text
    assert "live AI/client process" in text


def test_workflows_doc_mentions_purge_for_stalled_leftovers() -> None:
    text = _read("docs/agent-topics/WORKFLOWS.md")
    assert "--purge" in text
    assert "technical leftovers" in text


def test_workflows_help_example_mentions_dev_merge_sync() -> None:
    text = _read("docs/agent-topics/WORKFLOWS.md")
    assert "/dev merge sync" in text
    assert "Safe sync main with origin/main via rebase" in text
    assert "no force push" in text


def test_agent_rules_call_out_no_leftover_dev_merge_salvage() -> None:
    text = _read("docs/agent-topics/agent-rules.md")
    assert "When `/dev merge` finds a leftover branch/worktree" in text
    assert "salvage everything merge-worthy into `main`" in text
    assert "auto-discard the leftover branch/worktree" in text
    assert "repair Codex thread state" in text
    assert "defer deletion" in text


def test_dev_command_documents_eval_wrapper_over_eval_skill() -> None:
    text = _read("project-brain/capabilities/skills/platform-admin/commands/dev.md")
    assert "`eval`" in text
    assert "`/project dev eval run <command>`" in text
    assert "`aug eval command-kpi-run --command <command>`" in text
    assert "`/project dev eval report`" in text
    assert "`aug eval command-kpi-report`" in text
    assert "evals skill remains the engine of record" in text
