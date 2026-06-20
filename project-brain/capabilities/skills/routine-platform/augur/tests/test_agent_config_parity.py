"""Tests for auto-agent-config-parity scanner."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from src.lib.ops_protocol import OpsContext, ScanResult, FixResult

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "agent_config_parity.py"
_SPEC = importlib.util.spec_from_file_location("agent_config_parity_under_test", str(_MODULE_PATH))
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


def _ctx(tmp_path: Path, *, difficulty: int = 0) -> OpsContext:
    return OpsContext(project_root=tmp_path, difficulty=difficulty)


def _write_claude_settings_with_bash_blocker(tmp_path: Path, blocker_body: str) -> None:
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    blocker = tmp_path / "scripts" / "hooks" / "blocker.sh"
    blocker.parent.mkdir(parents=True)
    blocker.write_text(blocker_body, encoding="utf-8")
    settings = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [
                        {"type": "command", "command": "scripts/hooks/blocker.sh"}
                    ],
                }
            ]
        }
    }
    (claude_dir / "settings.json").write_text(json.dumps(settings), encoding="utf-8")


def test_module_metadata() -> None:
    assert mod.name == "auto-agent-config-parity"
    assert isinstance(mod.DIFFICULTY_SPEC, dict)


def test_no_settings_returns_empty(tmp_path: Path) -> None:
    result = mod.scan(_ctx(tmp_path))
    assert isinstance(result, ScanResult)
    assert result.issues == []


def test_flags_claude_only_dev_server_keyword(tmp_path: Path) -> None:
    # Claude blocker mentions `pnpm dev`. No .githooks/ or pre-commit-config
    # references it. Scanner must flag the gap.
    _write_claude_settings_with_bash_blocker(tmp_path, "if grep -q 'pnpm dev'; then deny; fi\n")

    result = mod.scan(_ctx(tmp_path, difficulty=1))

    keywords = {issue.get("gate_keyword") for issue in result.issues}
    assert "pnpm-dev" in keywords, (
        f"pnpm-dev gate keyword should be flagged as Claude-only; got: {result.issues}"
    )
    relevant = next(i for i in result.issues if i.get("gate_keyword") == "pnpm-dev")
    assert relevant.get("claude_only") is True


def test_no_flag_when_cross_agent_layer_carries_keyword(tmp_path: Path) -> None:
    # Same Claude blocker, but .githooks/pre-commit also references the
    # keyword. Scanner must consider parity satisfied.
    _write_claude_settings_with_bash_blocker(tmp_path, "if grep -q 'pnpm dev'; then deny; fi\n")
    githooks = tmp_path / ".githooks"
    githooks.mkdir()
    (githooks / "pre-commit").write_text(
        "# rejects 'pnpm dev' in committed scripts as well\n",
        encoding="utf-8",
    )

    result = mod.scan(_ctx(tmp_path, difficulty=1))

    flagged = [i for i in result.issues if i.get("gate_keyword") == "pnpm-dev"]
    assert flagged == [], (
        "pnpm-dev should not be flagged when a cross-agent layer references the keyword"
    )


def test_partial_parity_when_other_client_carries_keyword(tmp_path: Path) -> None:
    # Claude blocker has the keyword AND so does another client (codex), but
    # no shared cross-agent gate carries it. Scanner flags it but marks
    # claude_only=False with the peers list populated.
    _write_claude_settings_with_bash_blocker(tmp_path, "if grep -q 'pnpm dev'; then deny; fi\n")
    codex_dir = tmp_path / ".codex"
    codex_dir.mkdir()
    (codex_dir / "config.toml").write_text(
        '# guidance: do not run "pnpm dev" manually\n',
        encoding="utf-8",
    )

    result = mod.scan(_ctx(tmp_path, difficulty=1))

    relevant = next(
        (i for i in result.issues if i.get("gate_keyword") == "pnpm-dev"),
        None,
    )
    assert relevant is not None
    assert relevant.get("claude_only") is False
    assert "codex" in relevant.get("peers", [])


def test_fix_dry_run_reports_gaps(tmp_path: Path) -> None:
    _write_claude_settings_with_bash_blocker(tmp_path, "if grep -q 'pnpm dev'; then deny; fi\n")
    issues = [
        {"category": mod.name, "kind": "actionable", "gate_keyword": "pnpm-dev"},
    ]
    result = mod.fix(_ctx(tmp_path, difficulty=0), issues)
    assert isinstance(result, FixResult)
    assert "would write" in result.summary or "report" in result.summary.lower()


def test_evolution_gap_when_no_cross_agent_layer_at_all(tmp_path: Path) -> None:
    # Multiple Claude gate keywords, zero cross-agent layer entries → at d1
    # the scanner must surface an evolution gap recommending lift to a
    # shared layer.
    _write_claude_settings_with_bash_blocker(
        tmp_path,
        "kill 12345\nrm -rf .next\npnpm dev\nnext-server\n",
    )

    result = mod.scan(_ctx(tmp_path, difficulty=1))

    # evolution_gap() sets category="evolution" with kind="maintenance"
    evolution = [i for i in result.issues if i.get("category") == "evolution"]
    assert evolution, (
        "Expected one evolution_gap issue when no cross-agent layer carries any keyword"
    )
