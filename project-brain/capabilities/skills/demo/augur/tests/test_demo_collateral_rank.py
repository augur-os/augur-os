from __future__ import annotations

from pathlib import Path

from src.lib.frontmatter_utils import write_vault_frontmatter


def _write_card(path: Path, *, body: str, demo_id: str = "demo_01") -> Path:
    write_vault_frontmatter(
        path,
        {
            "title": "Workflow Example Card",
            "type": "workflow-example-artifact",
            "demo_id": demo_id,
            "tags": ["example", "workflow-example", "artifact"],
        },
        body,
    )
    return path


def test_demo_collateral_rank_rewards_judge_facing_artifact(tmp_path: Path) -> None:
    from skills.demo.scripts.demo_collateral_rank import score_demo_collateral_path

    card = _write_card(
        tmp_path / "demo-01.md",
        demo_id="demo_01_wiki_llm_cross_agent_ask",
        body="""# Workflow Example 01: Cross-Agent Wiki Compounding

## Bottom Line
Augur turns repeated ask answers from different agents into one governed wiki concept that the next agent can reuse.

## Live Proof
- Augur found 4 retained answers about the same wiki-compounding pattern.
- The retained answers point to Wiki Ingest And Compilation Commands.
- Codex and Claude can both use the same governed brain state.

## What To Show
1. Search Browse for: Workflow Example 01 Cross-Agent Wiki Compounding.
2. Point at the retained-answer count.
3. Point at Wiki Ingest And Compilation Commands.

## Investor Takeaway
Augur is a harness that lets native agents compound knowledge into reviewable files and reuse it across sessions.

## Verification Snapshot
- Retained outcomes: 4
- Status: pass
""",
    )

    result = score_demo_collateral_path(card)

    assert result["score"] >= 90
    assert result["status"] == "pass"
    assert result["failures"] == []


def test_demo_collateral_rank_rejects_internal_metadata_dump(tmp_path: Path) -> None:
    from skills.demo.scripts.demo_collateral_rank import score_demo_collateral_path

    card = _write_card(
        tmp_path / "bad.md",
        body="""# Workflow Example 01 Wiki LLM Cross-Agent Ask Proof

## Evidence
- Candidate wiki file: ~/Projects/Au-vault/wiki/concepts/wiki-ingest-and-compilation-commands.md
- Source synthesis: ~/Projects/Augur/project-brain/knowledge/syntheses/example.md
- Retained cluster: what pattern is emerging
""",
    )

    result = score_demo_collateral_path(card)

    assert result["score"] < 90
    assert result["status"] == "fail"
    assert any("implementation leakage" in failure for failure in result["failures"])
