"""Local-semantic toy auto-command for ADR-755 orchestrator tests."""
from __future__ import annotations

from src.lib.ops_protocol import FixResult, OpsContext, ScanResult


name = "auto-semantic"


def scan(ctx: OpsContext) -> ScanResult:
    """Return one issue that needs local semantic judgment."""
    issue = {
        "kind": "actionable",
        "severity": "warning",
        "path": "fixtures/toy_loop/auto_semantic.py",
        "detail": "Choose the right summary wording from nearby context.",
        "requires_llm": True,
        "fixability": "llm-assisted",
    }
    return ScanResult(
        issues=[issue],
        summary="1 local-semantic toy issue",
        severity="warning",
        items_scanned=1,
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Report that semantic repair needs an LLM-capable orchestrator."""
    return FixResult(
        success=True,
        actions=[{"kind": "llm-request", "issues": len(issues)}],
        summary="Semantic toy issue requires LLM-assisted repair.",
        fix_type="report",
    )


def llm_fix(ctx: OpsContext, issues: list[dict]) -> dict:
    """Return a deterministic sentinel for semantic orchestration tests."""
    return {
        "kind": "llm-fix-request",
        "loop": "toy-loop",
        "category": name,
        "issue_count": len(issues),
    }
