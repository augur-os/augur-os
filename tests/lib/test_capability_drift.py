"""Tests for src.lib.capabilities.drift (ADR-734 C2 drift dimensions)."""

from __future__ import annotations

from pathlib import Path

from src.lib.capabilities.drift import (
    DriftFinding,
    Severity,
    detect_agents_md_drift,
    detect_blocked_present,
    detect_client_budget_blowout,
    detect_direct_mcp_exposure,
    detect_draft_leakage,
    detect_duplicate_external_skills,
    detect_unclassified_export,
    detect_unexpected_client,
    detect_invalid_primary_surface,
    run_all_drift_checks,
)
from src.lib.capabilities.exposure_policy import CapabilityRecord


def _record(**overrides) -> CapabilityRecord:
    defaults = dict(
        id="command:demo",
        type="command",
        owner_kind="augur",
        management="generated",
        scope="project",
        classification_status="approved",
        primary_surface="command",
        preferred_client="shell",
        current_exposure=(),
        export_to=(),
        drift=(),
        source_paths=(),
        metadata={},
    )
    defaults.update(overrides)
    return CapabilityRecord(**defaults)


# --- skeleton --------------------------------------------------------------


def test_drift_finding_carries_dimension_and_severity():
    finding = DriftFinding(
        dimension="blocked_present",
        capability_id="mcp-tool:dangerous",
        severity=Severity.FAIL,
        message="blocked capability has generated MCP surface",
        surface="mcp",
    )
    assert finding.dimension == "blocked_present"
    assert finding.severity is Severity.FAIL
    assert finding.is_failure() is True


def test_drift_finding_warn_is_not_failure():
    finding = DriftFinding(
        dimension="duplicate_external_skill",
        capability_id="skill:shared",
        severity=Severity.WARN,
        message="duplicated",
        surface="claude,codex",
    )
    assert finding.is_failure() is False


# --- D1 direct MCP exposure -----------------------------------------------


def test_detect_direct_mcp_exposure_without_policy_flags_fail():
    record = _record(
        id="mcp-tool:rogue",
        type="mcp-tool",
        primary_surface="mcp",
        preferred_client="claude",
        current_exposure=("mcp",),
        export_to=("cli",),
    )
    findings = detect_direct_mcp_exposure([record])
    assert len(findings) == 1
    assert findings[0].dimension == "direct_mcp_exposure"
    assert findings[0].is_failure() is True


def test_detect_direct_mcp_exposure_clean_when_policy_allows_it():
    record = _record(
        id="mcp-tool:ok",
        type="mcp-tool",
        primary_surface="mcp",
        current_exposure=("mcp",),
        export_to=("mcp",),
    )
    assert detect_direct_mcp_exposure([record]) == []


def test_direct_mcp_exposure_warns_for_user_owned_private_tools():
    record = _record(
        id="mcp-tool:get-pending",
        type="mcp-tool",
        owner_kind="user",
        primary_surface="mcp",
        current_exposure=("mcp",),
        export_to=(),
        source_paths=("/Users/example/Au-vault/skills/file-manager/SKILL.md",),
    )

    findings = detect_direct_mcp_exposure([record])

    assert len(findings) == 1
    assert findings[0].severity is Severity.WARN
    assert findings[0].dimension == "direct_mcp_exposure"


# --- D2 unclassified export -----------------------------------------------


def test_detect_unclassified_export_flags_any_generated_surface_when_unclassified():
    record = _record(
        id="command:mystery",
        classification_status="unclassified",
        current_exposure=("claude",),
        export_to=(),
    )
    findings = detect_unclassified_export([record])
    assert [f.dimension for f in findings] == ["unclassified_export"]
    assert findings[0].is_failure() is True


def test_detect_unclassified_export_ignores_non_client_exposures():
    record = _record(
        id="command:cli-only",
        classification_status="unclassified",
        current_exposure=("cli",),
        export_to=(),
    )
    assert detect_unclassified_export([record]) == []


# --- D3 blocked present ---------------------------------------------------


def test_detect_blocked_present_flags_any_augur_generated_surface():
    record = _record(
        id="mcp-tool:legacy",
        type="mcp-tool",
        classification_status="blocked",
        primary_surface="mcp",
        current_exposure=("claude", "browse"),
        export_to=(),
    )
    findings = detect_blocked_present([record])
    surfaces = sorted(f.surface for f in findings)
    assert surfaces == ["browse", "claude"]
    assert all(f.dimension == "blocked_present" and f.is_failure() for f in findings)


# --- D4 unexpected client -------------------------------------------------


def test_detect_unexpected_client_flags_surface_not_in_export_to():
    record = _record(
        id="skill:demo",
        type="skill",
        primary_surface="skill",
        preferred_client="claude",
        current_exposure=("claude", "gemini"),
        export_to=("claude",),
    )
    findings = detect_unexpected_client([record])
    assert len(findings) == 1
    assert findings[0].surface == "gemini"
    assert findings[0].is_failure() is True


def test_detect_unexpected_client_ignores_external_owners():
    record = _record(
        id="skill:external",
        type="skill",
        owner_kind="external",
        current_exposure=("claude", "gemini"),
        export_to=("claude",),
    )
    assert detect_unexpected_client([record]) == []


# --- D5 duplicate external skill ------------------------------------------


def test_detect_duplicate_external_skill_emits_warning_unless_multi_client_approved(
    tmp_path: Path,
):
    for client in (".claude", ".codex"):
        skill_dir = tmp_path / client / "skills" / "shared-tool"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("---\nname: shared-tool\n---\n", encoding="utf-8")

    findings = detect_duplicate_external_skills(tmp_path, multi_client_approved=set())
    assert findings[0].dimension == "duplicate_external_skill"
    assert findings[0].severity.value == "warn"

    suppressed = detect_duplicate_external_skills(tmp_path, multi_client_approved={"shared-tool"})
    assert suppressed == []


# --- D6 draft leakage -----------------------------------------------------


def test_detect_draft_leakage_flags_drafts_appearing_in_generated_client_dir(
    tmp_path: Path,
):
    (tmp_path / ".claude" / "skills" / "future-skill").mkdir(parents=True)
    (tmp_path / ".claude" / "skills" / "future-skill" / "SKILL.md").write_text("x", encoding="utf-8")
    (tmp_path / "project-brain" / "capabilities" / "skills").mkdir(parents=True)
    (tmp_path / "project-brain" / "capabilities" / "skills" / "future-skill.draft.md").write_text("x", encoding="utf-8")

    findings = detect_draft_leakage(tmp_path)
    assert any(f.dimension == "draft_leakage" for f in findings)
    assert findings[0].is_failure() is True


# --- D7 AGENTS.md drift ---------------------------------------------------


def test_detect_agents_md_drift_flags_table_disagreement_with_policy(tmp_path: Path):
    agents_md = tmp_path / "AGENTS.md"
    agents_md.write_text(
        "| Capability | Type | Preferred Surface |\n"
        "|---|---|---|\n"
        "| `mcp-tool:rogue` | mcp-tool | mcp via dashboard |\n",
        encoding="utf-8",
    )
    record = _record(
        id="mcp-tool:rogue",
        type="mcp-tool",
        primary_surface="cli",
        current_exposure=("cli",),
        export_to=("cli",),
    )
    findings = detect_agents_md_drift(agents_md, [record])
    assert findings[0].dimension == "agents_md_drift"
    assert findings[0].is_failure() is True


def test_detect_agents_md_drift_silent_when_missing_file(tmp_path: Path):
    assert detect_agents_md_drift(tmp_path / "AGENTS.md", []) == []


def test_detect_agents_md_drift_accepts_skill_preferred_client_label(tmp_path: Path):
    agents_md = tmp_path / "AGENTS.md"
    agents_md.write_text(
        "| Capability | Type | Preferred Surface |\n" "|---|---|---|\n" "| `skill:dream` | skill | skill via codex |\n",
        encoding="utf-8",
    )
    record = _record(
        id="skill:dream",
        type="skill",
        primary_surface="skill",
        preferred_client="codex",
        current_exposure=("codex",),
        export_to=("codex",),
    )

    assert detect_agents_md_drift(agents_md, [record]) == []


# --- D8 client budget blowout ---------------------------------------------


def test_detect_client_budget_blowout_flags_when_count_exceeds_budget():
    records = [
        _record(
            id=f"mcp-tool:t{i}",
            type="mcp-tool",
            primary_surface="mcp",
            preferred_client="claude",
            current_exposure=("gemini",),
            export_to=("mcp",),
        )
        for i in range(5)
    ]
    budgets = {"gemini": 4, "opencode": 4}
    findings = detect_client_budget_blowout(records, budgets)
    assert findings[0].dimension == "client_budget_blowout"
    assert findings[0].surface == "gemini"
    assert findings[0].is_failure() is True


def test_detect_client_budget_blowout_quiet_when_under_budget():
    records = [
        _record(
            id="mcp-tool:t0",
            type="mcp-tool",
            current_exposure=("gemini",),
        )
    ]
    assert detect_client_budget_blowout(records, {"gemini": 4}) == []


# --- D9 invalid primary surface -------------------------------------------


def test_detect_invalid_primary_surface_fails_for_augur_skills():
    record = _record(
        id="mcp-tool:audio-classify",
        type="mcp-tool",
        owner_kind="augur",
        primary_surface="mcp-tool",
        source_paths=("project-brain/capabilities/skills/audio-ingest/SKILL.md",),
    )

    findings = detect_invalid_primary_surface([record])

    assert len(findings) == 1
    assert findings[0].severity is Severity.FAIL
    assert findings[0].message == "invalid primary_surface 'mcp-tool'"


def test_detect_invalid_primary_surface_warns_for_private_skills():
    record = _record(
        id="mcp-tool:get-pending",
        type="mcp-tool",
        owner_kind="user",
        primary_surface="mcp-tool",
        source_paths=("/Users/example/Au-vault/skills/file-manager/SKILL.md",),
    )

    findings = detect_invalid_primary_surface([record])

    assert len(findings) == 1
    assert findings[0].severity is Severity.WARN


# --- aggregator -----------------------------------------------------------


def test_run_all_drift_checks_aggregates_failures_and_warnings(tmp_path: Path):
    records = [
        _record(
            id="mcp-tool:blocked",
            type="mcp-tool",
            classification_status="blocked",
            primary_surface="mcp",
            current_exposure=("mcp",),
            export_to=(),
        )
    ]
    report = run_all_drift_checks(
        records,
        project_root=tmp_path,
        agents_md_path=tmp_path / "AGENTS.md",
        budgets={"gemini": 50, "opencode": 50},
        multi_client_approved=set(),
    )
    assert report["fail_count"] >= 1
    assert any(f["dimension"] == "blocked_present" for f in report["findings"])
    assert report["warn_count"] == 0


def test_dream_skill_policy_allows_codex_transition_export():
    from src.lib.capabilities.exposure_policy import resolve_capability_records

    record = _record(
        id="skill:dream",
        type="skill",
        owner_kind="augur",
        current_exposure=("codex",),
        primary_surface="skill",
    )
    policy = {
        "capabilities": {
            "skill:dream": {
                "classification_status": "approved",
                "owner_kind": "augur",
                "management": "generated",
                "scope": "project",
                "primary_surface": "skill",
                "preferred_client": "codex",
                "export_to": ["agents-md", "browse", "codex"],
            }
        }
    }

    resolved = resolve_capability_records([record], policy=policy)
    report = run_all_drift_checks(
        resolved,
        project_root=Path("/tmp/no-project"),
        agents_md_path=Path("/tmp/no-project/AGENTS.md"),
        budgets={"gemini": 50, "opencode": 50},
        multi_client_approved=set(),
    )

    assert report["fail_count"] == 0
