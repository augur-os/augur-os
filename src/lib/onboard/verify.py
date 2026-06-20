from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from src.lib.onboard.result import OnboardContext, StepResult


@dataclass
class VerifyProbes:
    """Injectable probes so verify logic is unit-testable. The real probes
    (HTTP to the dashboard, MCP handshake, a seed query) are wired by the driver
    / M4's CI harness."""

    dashboard_interactive: Callable[[OnboardContext], bool]
    mcp_connected: Callable[[OnboardContext], bool]
    sample_query: Callable[[OnboardContext], str]


def verify(ctx: OnboardContext, probes: VerifyProbes) -> StepResult:
    """Assert the system is actually working: dashboard interactive, MCP
    connected, and a real query returns non-empty content (rules 28, 34)."""
    if not probes.dashboard_interactive(ctx):
        return StepResult.fail("verify: dashboard did not load to interactive state")
    if not probes.mcp_connected(ctx):
        return StepResult.fail("verify: MCP servers did not connect")
    answer = (probes.sample_query(ctx) or "").strip()
    if not answer:
        return StepResult.fail("verify: sample query returned no content")
    return StepResult.ok(
        "Verified: dashboard interactive, MCP connected, query answered", {"answer_chars": len(answer)}
    )
