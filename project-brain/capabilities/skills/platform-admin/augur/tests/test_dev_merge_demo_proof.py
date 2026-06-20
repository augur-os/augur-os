"""Tests for dev-merge optional demo proof gates."""
from __future__ import annotations

import builtins
import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest


def _find_project_root(start: Path) -> Path:
    for parent in start.parents:
        if (parent / "docs" / "agent-topics").is_dir() and (
            parent / "project-brain" / "capabilities" / "skills"
        ).is_dir():
            return parent
    raise RuntimeError(f"Unable to locate Augur project root from {start}")


PROJECT_ROOT = _find_project_root(Path(__file__).resolve())
SCRIPT_PATH = (
    PROJECT_ROOT
    / "project-brain"
    / "capabilities"
    / "skills"
    / "platform-admin"
    / "scripts"
    / "dev_merge_demo_proof.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("dev_merge_demo_proof", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_skill_manifest(repo_root: Path, *skill_paths: str) -> None:
    manifest_path = repo_root / "docs" / "generated" / "skill-manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            {
                "version": "test",
                "skills": [
                    {"name": Path(path).name, "path": path}
                    for path in skill_paths
                ],
            }
        ),
        encoding="utf-8",
    )


def _write_capability_policy(repo_root: Path, *skill_names: str) -> None:
    policy_path = repo_root / "config" / "system" / "capability_exposure.yaml"
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    policy_path.write_text(
        "capabilities:\n"
        + "".join(
            f"  skill:{skill_name}:\n"
            "    export_to:\n"
            "      - agents-md\n"
            f"    primary_skill: {skill_name}\n"
            for skill_name in skill_names
        ),
        encoding="utf-8",
    )


def _write_mcp_primary_skill_policy(repo_root: Path, skill_name: str) -> None:
    policy_path = repo_root / "config" / "system" / "capability_exposure.yaml"
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    policy_path.write_text(
        "capabilities:\n"
        f"  mcp-tool:{skill_name}-demo:\n"
        "    export_to:\n"
        "      - agents-md\n"
        f"    primary_skill: {skill_name}\n",
        encoding="utf-8",
    )


def test_split_demo_proof_flags_accepts_short_and_readable_aliases() -> None:
    module = _load_module()

    options, remaining = module.split_demo_proof_flags(
        ["full", "--com", "--skillify", "--target", "main"]
    )

    assert options.compound_wiki is True
    assert options.skillify is True
    assert remaining == ["full", "--target", "main"]


def test_split_demo_proof_flags_accepts_typo_alias() -> None:
    module = _load_module()

    options, remaining = module.split_demo_proof_flags(
        ["full", "--compound-wiki", "--skilify"]
    )

    assert options.compound_wiki is True
    assert options.skillify is True
    assert remaining == ["full"]


def test_split_demo_proof_flags_defaults_to_no_requested_proofs() -> None:
    module = _load_module()

    options, remaining = module.split_demo_proof_flags(["full", "--purge"])

    assert options.compound_wiki is False
    assert options.skillify is False
    assert remaining == ["full", "--purge"]


def test_proof_summary_ok_is_false_when_blocked() -> None:
    module = _load_module()

    summary = module.ProofSummary(
        title="Wiki compounding summary",
        status="blocked",
        blockers=["no durable wiki files changed"],
    )

    assert summary.ok is False


def test_proof_summary_ok_is_true_for_changed_created_updated_and_verified_noop() -> None:
    module = _load_module()

    statuses = ["changed", "created", "updated", "reviewed", "verified-noop"]

    assert [
        module.ProofSummary(title="summary", status=status).ok for status in statuses
    ] == [True, True, True, True, True]


def test_demo_proof_result_ok_is_false_for_empty_result() -> None:
    module = _load_module()

    result = module.DemoProofResult()

    assert result.ok is False
    assert result.blockers == []


def test_demo_proof_result_ok_is_true_for_one_passing_summary_without_requested_flags() -> None:
    module = _load_module()

    result = module.DemoProofResult(
        wiki=module.ProofSummary(title="Wiki compounding summary", status="changed")
    )

    assert result.ok is True
    assert result.blockers == []


def test_demo_proof_result_ok_is_false_for_one_blocked_summary() -> None:
    module = _load_module()

    result = module.DemoProofResult(
        skillify=module.ProofSummary(
            title="Skillify summary",
            status="blocked",
            blockers=["no skill source changed"],
        )
    )

    assert result.ok is False
    assert result.blockers == ["no skill source changed"]


def test_demo_proof_result_ok_is_false_when_requested_summary_is_missing() -> None:
    module = _load_module()

    result = module.DemoProofResult(
        wiki=module.ProofSummary(title="Wiki compounding summary", status="changed"),
        requested=module.DemoProofOptions(compound_wiki=True, skillify=True),
    )

    assert result.ok is False
    assert result.blockers == [
        "skillify proof was requested but no skillify summary was produced"
    ]


def test_demo_proof_result_blockers_aggregate_summary_and_missing_requested_proofs() -> None:
    module = _load_module()

    result = module.DemoProofResult(
        skillify=module.ProofSummary(
            title="Skillify summary",
            status="blocked",
            blockers=["skill source changed only in generated output"],
        ),
        requested=module.DemoProofOptions(compound_wiki=True, skillify=True),
    )

    assert result.ok is False
    assert result.blockers == [
        "wiki proof was requested but no wiki summary was produced",
        "skill source changed only in generated output",
    ]


def test_validate_compound_review_proposal_accepts_evidence_backed_proposal() -> None:
    module = _load_module()

    proposal = module.CompoundReviewProposal(
        status="proposed",
        durable_lesson="Client skill projection is a contract boundary.",
        evidence=[
            "Codex skipped 10 projected skills because frontmatter was missing.",
            "Parser-facing tests now cover YAML-safe command skill metadata.",
        ],
        target_type="existing_skill",
        target_artifact="project-brain/capabilities/skills/ai/references/client-projection.md",
        next_action="Strengthen client projection guidance with a parser-gate rule.",
        confidence="high",
        why_not=[
            "No new skill is needed because sync_agents owns client projections.",
            "No ADR is needed because the architecture contract already exists.",
        ],
    )

    result = module.validate_compound_review_proposal(proposal)

    assert result.ok is True
    assert result.blockers == []


def test_validate_compound_review_proposal_blocks_generic_target() -> None:
    module = _load_module()

    proposal = module.CompoundReviewProposal(
        status="proposed",
        durable_lesson="Improve skills.",
        evidence=[
            "Tests passed.",
            "The command ran.",
        ],
        target_type="existing_skill",
        target_artifact="",
        next_action="Improve docs.",
        confidence="high",
        why_not=[],
    )

    result = module.validate_compound_review_proposal(proposal)

    assert result.ok is False
    assert "target_artifact is required for proposed review" in result.blockers
    assert "durable_lesson must be specific" in result.blockers
    assert "evidence item is too generic: Tests passed." in result.blockers
    assert "evidence item is too generic: The command ran." in result.blockers


def test_validate_compound_review_proposal_blocks_generic_passing_command_evidence() -> None:
    module = _load_module()

    proposal = module.CompoundReviewProposal(
        status="proposed",
        durable_lesson="Client skill projection requires artifact-backed review.",
        evidence=[
            "All tests passed.",
            "The command completed successfully.",
        ],
        target_type="existing_skill",
        target_artifact="project-brain/capabilities/skills/ai/references/client-projection.md",
        next_action="Strengthen client projection guidance with artifact-backed evidence.",
        confidence="medium",
        why_not=["Existing ai skill owns the client projection contract."],
    )

    result = module.validate_compound_review_proposal(proposal)

    assert result.ok is False
    assert "evidence item is too generic: All tests passed." in result.blockers
    assert (
        "evidence item is too generic: The command completed successfully."
        in result.blockers
    )


def test_validate_compound_review_proposal_blocks_lone_domain_marker_evidence() -> None:
    module = _load_module()

    proposal = module.CompoundReviewProposal(
        status="proposed",
        durable_lesson="Client skill projection requires artifact-backed review.",
        evidence=["wiki", "skill"],
        target_type="existing_skill",
        target_artifact="project-brain/capabilities/skills/ai/references/client-projection.md",
        next_action="Strengthen client projection guidance with artifact-backed evidence.",
        confidence="medium",
        why_not=["Existing ai skill owns the client projection contract."],
    )

    result = module.validate_compound_review_proposal(proposal)

    assert result.ok is False
    assert "evidence item is too generic: wiki" in result.blockers
    assert "evidence item is too generic: skill" in result.blockers


def test_validate_compound_review_proposal_requires_two_evidence_items_for_low_confidence() -> None:
    module = _load_module()

    proposal = module.CompoundReviewProposal(
        status="proposed",
        durable_lesson="Client projection failures need parser-facing evidence.",
        evidence=[
            "Codex skipped projected skills because YAML frontmatter was missing.",
        ],
        target_type="existing_skill",
        target_artifact="project-brain/capabilities/skills/ai/SKILL.md",
        next_action="Add parser-facing projection guidance to the existing skill.",
        confidence="low",
        why_not=["Existing ai skill owns the client projection contract."],
    )

    result = module.validate_compound_review_proposal(proposal)

    assert result.ok is False
    assert "non-blocked review requires at least two evidence items" in result.blockers


def test_validate_compound_review_proposal_blocks_no_durable_change_target_artifact() -> None:
    module = _load_module()

    proposal = module.CompoundReviewProposal(
        status="no_durable_change",
        durable_lesson="The review found no durable knowledge change to retain.",
        evidence=[
            "Codex review found the existing skill guidance already covers this path.",
            "Parser-facing test output matched the current YAML frontmatter contract.",
        ],
        target_type="none",
        target_artifact="project-brain/capabilities/skills/ai/SKILL.md",
        next_action="",
        confidence="medium",
        why_not=[],
    )

    result = module.validate_compound_review_proposal(proposal)

    assert result.ok is False
    assert "no_durable_change must not set target_artifact" in result.blockers


def test_validate_compound_review_proposal_requires_specific_why_not_for_proposed() -> None:
    module = _load_module()

    proposal = module.CompoundReviewProposal(
        status="proposed",
        durable_lesson="Client skill projection is a contract boundary.",
        evidence=[
            "Codex skipped 10 projected skills because frontmatter was missing.",
            "Parser-facing tests now cover YAML-safe command skill metadata.",
        ],
        target_type="existing_skill",
        target_artifact="project-brain/capabilities/skills/ai/references/client-projection.md",
        next_action="Strengthen client projection guidance with a parser-gate rule.",
        confidence="medium",
        why_not=["", "Improve docs."],
    )

    result = module.validate_compound_review_proposal(proposal)

    assert result.ok is False
    assert "proposed review requires at least one specific why_not reason" in result.blockers
    assert "why_not reason is too generic: " in result.blockers
    assert "why_not reason is too generic: Improve docs." in result.blockers


def test_build_skillify_proof_reports_new_skill_artifacts(tmp_path: Path) -> None:
    module = _load_module()
    _write_capability_policy(tmp_path, "wiki-demo")

    summary = module.build_skillify_proof(
        repo_changes=[
            module.ChangedPath(
                status="A", path="project-brain/capabilities/skills/wiki-demo/SKILL.md"
            ),
            module.ChangedPath(
                status="A",
                path="project-brain/capabilities/skills/wiki-demo/commands/wiki-demo.md",
            ),
            module.ChangedPath(
                status="A",
                path="project-brain/capabilities/skills/wiki-demo/augur/tests/test_demo.py",
            ),
            module.ChangedPath(status="M", path="config/system/capability_exposure.yaml"),
        ],
        repo_root=tmp_path,
    )

    assert summary.status == "created"
    assert summary.skill_path == "project-brain/capabilities/skills/wiki-demo"
    assert summary.incident_gap == (
        "wiki-demo skill created with durable behavior: SKILL.md, command docs"
    )
    assert "SKILL.md" in summary.what_changed
    assert "command docs" in summary.what_changed
    assert "tests" in summary.what_changed
    assert any("canonical skill artifact(s)" in item for item in summary.evidence)
    assert "capability policy touched" in summary.evidence
    assert "capability policy entry present: wiki-demo" in summary.evidence
    assert "same-skill quality test artifact(s) changed: 1" in summary.evidence
    assert summary.ok is True


def test_build_skillify_proof_routes_new_skill_through_manifest(tmp_path: Path) -> None:
    module = _load_module()
    _write_skill_manifest(tmp_path, "project-brain/capabilities/skills/wiki-demo")

    summary = module.build_skillify_proof(
        repo_changes=[
            module.ChangedPath(
                status="A", path="project-brain/capabilities/skills/wiki-demo/SKILL.md"
            ),
            module.ChangedPath(
                status="A",
                path="project-brain/capabilities/skills/wiki-demo/scripts/demo.py",
            ),
            module.ChangedPath(
                status="A",
                path="project-brain/capabilities/skills/wiki-demo/augur/tests/test_demo.py",
            ),
            module.ChangedPath(status="M", path="docs/generated/skill-manifest.json"),
        ],
        repo_root=tmp_path,
    )

    assert summary.status == "created"
    assert "manifest entry present: wiki-demo" in summary.evidence
    assert summary.ok is True


def test_build_skillify_proof_reports_updated_existing_skill() -> None:
    module = _load_module()

    summary = module.build_skillify_proof(
        repo_changes=[
            module.ChangedPath(
                status="M",
                path="project-brain/capabilities/skills/platform-admin/scripts/dev_merge_demo_proof.py",
            ),
            module.ChangedPath(
                status="M",
                path="project-brain/capabilities/skills/platform-admin/augur/tests/test_dev_merge_demo_proof.py",
            ),
        ],
        repo_root=PROJECT_ROOT,
    )

    assert summary.status == "updated"
    assert summary.skill_path == "project-brain/capabilities/skills/platform-admin"
    assert summary.incident_gap == (
        "platform-admin durable skill behavior changed: scripts"
    )
    assert "scripts" in summary.what_changed
    assert "tests" in summary.what_changed
    assert "manifest entry present: platform-admin" in summary.evidence
    assert "same-skill quality test artifact(s) changed: 1" in summary.evidence
    assert summary.ok is True


def test_build_skillify_proof_reports_mcp_script_wrappers() -> None:
    module = _load_module()

    summary = module.build_skillify_proof(
        repo_changes=[
            module.ChangedPath(
                status="M",
                path="project-brain/capabilities/skills/platform-admin/scripts/mcp/tool.py",
            ),
            module.ChangedPath(
                status="M",
                path="project-brain/capabilities/skills/platform-admin/augur/tests/test_tool.py",
            ),
        ],
        repo_root=PROJECT_ROOT,
    )

    assert "MCP wrappers" in summary.what_changed
    assert "scripts" not in summary.what_changed
    assert summary.ok is True


def test_build_skillify_proof_reports_passed_quality_verification() -> None:
    module = _load_module()
    root = "project-brain/capabilities/skills/platform-admin"

    summary = module.build_skillify_proof(
        repo_changes=[
            module.ChangedPath(
                status="M",
                path=f"{root}/scripts/dev_merge_demo_proof.py",
            ),
            module.ChangedPath(
                status="M",
                path=f"{root}/augur/tests/test_dev_merge_demo_proof.py",
            ),
        ],
        repo_root=PROJECT_ROOT,
        quality_verifications={
            root: module.QualityVerification(
                ok=True,
                evidence="quality verification passed: platform-admin: 530 passed",
            )
        },
    )

    assert summary.status == "updated"
    assert "quality verification passed: platform-admin: 530 passed" in summary.evidence
    assert summary.ok is True


def test_build_skillify_proof_blocks_failed_quality_verification() -> None:
    module = _load_module()
    root = "project-brain/capabilities/skills/platform-admin"

    summary = module.build_skillify_proof(
        repo_changes=[
            module.ChangedPath(
                status="M",
                path=f"{root}/scripts/dev_merge_demo_proof.py",
            ),
            module.ChangedPath(
                status="M",
                path=f"{root}/augur/tests/test_dev_merge_demo_proof.py",
            ),
        ],
        repo_root=PROJECT_ROOT,
        quality_verifications={
            root: module.QualityVerification(
                ok=False,
                evidence="quality verification failed: platform-admin: 1 failed",
                blocker="platform-admin quality verification failed",
            )
        },
    )

    assert summary.status == "blocked"
    assert "quality verification failed: platform-admin: 1 failed" in summary.evidence
    assert "platform-admin quality verification failed" in summary.blockers
    assert summary.ok is False


def test_pytest_summary_prefers_stdout_result_over_cleanup_warning() -> None:
    module = _load_module()

    summary = module._pytest_summary(
        stdout=".....\n530 passed in 4.69s\n",
        stderr=(
            "PytestWarning: error removing "
            "/tmp/pytest-of-user/garbage/test_force_remove\n"
        ),
    )

    assert summary == "530 passed in 4.69s"


def test_build_skillify_proof_blocks_generated_only_exports() -> None:
    module = _load_module()

    summary = module.build_skillify_proof(
        repo_changes=[
            module.ChangedPath(status="M", path=".claude/skills/wiki-demo/SKILL.md"),
            module.ChangedPath(status="M", path=".gemini/skills/wiki-demo/SKILL.md"),
        ]
    )

    assert summary.status == "blocked"
    assert "only generated client skill exports changed" in summary.blockers
    assert summary.ok is False


def test_build_skillify_proof_blocks_generated_exports_mixed_with_docs() -> None:
    module = _load_module()

    summary = module.build_skillify_proof(
        repo_changes=[
            module.ChangedPath(status="M", path=".claude/skills/wiki-demo/SKILL.md"),
            module.ChangedPath(status="M", path="docs/superpowers/specs/demo.md"),
        ]
    )

    assert summary.status == "blocked"
    assert summary.items_changed == [".claude/skills/wiki-demo/SKILL.md"]
    assert "only generated client skill exports changed" in summary.blockers
    assert summary.ok is False


def test_build_skillify_proof_verified_noop_when_merge_set_is_empty() -> None:
    module = _load_module()

    summary = module.build_skillify_proof(repo_changes=[])

    assert summary.status == "verified-noop"
    assert "no repo changes detected in the merge set" in summary.evidence
    assert summary.ok is True


def test_build_skillify_proof_blocks_when_no_skill_artifact_changed() -> None:
    module = _load_module()

    summary = module.build_skillify_proof(
        repo_changes=[module.ChangedPath(status="M", path="docs/superpowers/specs/demo.md")]
    )

    assert summary.status == "blocked"
    assert "no canonical skill source changed in the merge set" in summary.blockers
    assert summary.ok is False


def test_build_skillify_proof_blocks_unrouted_skill_code_without_quality_proof() -> None:
    module = _load_module()

    summary = module.build_skillify_proof(
        repo_changes=[
            module.ChangedPath(
                status="M",
                path="project-brain/capabilities/skills/unrouted-demo/scripts/demo.py",
            ),
        ],
        repo_root=PROJECT_ROOT,
    )

    assert summary.status == "blocked"
    assert "unrouted-demo has no routing proof" in summary.blockers
    assert "unrouted-demo code-bearing changes need tests or quality proof" in summary.blockers
    assert summary.ok is False


def test_build_skillify_proof_blocks_deletion_only_skill_changes() -> None:
    module = _load_module()

    summary = module.build_skillify_proof(
        repo_changes=[
            module.ChangedPath(
                status="D",
                path="project-brain/capabilities/skills/platform-admin/SKILL.md",
            ),
        ],
        repo_root=PROJECT_ROOT,
    )

    assert summary.status == "blocked"
    assert "platform-admin has only deletion/removal changes" in summary.blockers
    assert summary.ok is False


def test_build_skillify_proof_blocks_top_level_skills_files() -> None:
    module = _load_module()

    summary = module.build_skillify_proof(
        repo_changes=[
            module.ChangedPath(
                status="M",
                path="project-brain/capabilities/skills/README.md",
            ),
        ]
    )

    assert summary.status == "blocked"
    assert "no canonical skill source changed in the merge set" in summary.blockers
    assert summary.ok is False


def test_build_skillify_proof_reports_multiple_changed_skills() -> None:
    module = _load_module()

    summary = module.build_skillify_proof(
        repo_changes=[
            module.ChangedPath(
                status="M",
                path="project-brain/capabilities/skills/platform-admin/SKILL.md",
            ),
            module.ChangedPath(
                status="M",
                path="project-brain/capabilities/skills/platform-admin/augur/tests/test_demo.py",
            ),
            module.ChangedPath(
                status="M",
                path="project-brain/capabilities/skills/ingest/SKILL.md",
            ),
        ],
        repo_root=PROJECT_ROOT,
    )

    assert summary.status == "updated"
    assert summary.skill_path == (
        "project-brain/capabilities/skills/platform-admin, "
        "project-brain/capabilities/skills/ingest"
    )
    assert summary.incident_gap == (
        "multiple durable skill behaviors changed: "
        "platform-admin changed: SKILL.md; ingest changed: SKILL.md"
    )
    assert summary.items_changed == [
        "project-brain/capabilities/skills/ingest/SKILL.md",
        "project-brain/capabilities/skills/platform-admin/SKILL.md",
        "project-brain/capabilities/skills/platform-admin/augur/tests/test_demo.py",
    ]
    assert "multiple skills changed: platform-admin, ingest" in summary.evidence
    assert summary.ok is True


def test_build_skillify_proof_reports_mixed_skill_status_order_independent(
    tmp_path: Path,
) -> None:
    module = _load_module()
    _write_skill_manifest(
        tmp_path,
        "project-brain/capabilities/skills/platform-admin",
        "project-brain/capabilities/skills/new-demo",
    )

    existing_change = module.ChangedPath(
        status="M",
        path="project-brain/capabilities/skills/platform-admin/SKILL.md",
    )
    new_skill_changes = [
        module.ChangedPath(
            status="A",
            path="project-brain/capabilities/skills/new-demo/SKILL.md",
        ),
        module.ChangedPath(
            status="A",
            path="project-brain/capabilities/skills/new-demo/commands/demo.md",
        ),
    ]

    summaries = [
        module.build_skillify_proof(
            repo_changes=[existing_change, *new_skill_changes],
            repo_root=tmp_path,
        ),
        module.build_skillify_proof(
            repo_changes=[*new_skill_changes, existing_change],
            repo_root=tmp_path,
        ),
    ]

    assert [summary.status for summary in summaries] == ["updated", "updated"]
    assert summaries[0].incident_gap == (
        "multiple durable skill behaviors changed: "
        "platform-admin changed: SKILL.md; new-demo created: SKILL.md, command docs"
    )
    assert summaries[1].incident_gap == (
        "multiple durable skill behaviors changed: "
        "new-demo created: SKILL.md, command docs; platform-admin changed: SKILL.md"
    )


def test_build_skillify_proof_blocks_unrouted_skill_mixed_with_routed_skill() -> None:
    module = _load_module()

    summary = module.build_skillify_proof(
        repo_changes=[
            module.ChangedPath(
                status="A",
                path="project-brain/capabilities/skills/new-demo/SKILL.md",
            ),
            module.ChangedPath(
                status="A",
                path="project-brain/capabilities/skills/new-demo/scripts/demo.py",
            ),
            module.ChangedPath(
                status="M",
                path="project-brain/capabilities/skills/platform-admin/augur/tests/test_demo.py",
            ),
        ],
        repo_root=PROJECT_ROOT,
    )

    assert summary.status == "blocked"
    assert "new-demo has no routing proof" in summary.blockers
    assert "new-demo code-bearing changes need tests or quality proof" in summary.blockers
    assert "manifest entry present: platform-admin" in summary.evidence
    assert summary.ok is False


def test_build_skillify_proof_blocks_new_skill_with_unrelated_policy_touch() -> None:
    module = _load_module()

    summary = module.build_skillify_proof(
        repo_changes=[
            module.ChangedPath(
                status="A",
                path="project-brain/capabilities/skills/new-demo/SKILL.md",
            ),
            module.ChangedPath(
                status="A",
                path="project-brain/capabilities/skills/new-demo/scripts/demo.py",
            ),
            module.ChangedPath(
                status="A",
                path="project-brain/capabilities/skills/new-demo/augur/tests/test_demo.py",
            ),
            module.ChangedPath(status="M", path="config/system/capability_exposure.yaml"),
        ],
        repo_root=PROJECT_ROOT,
    )

    assert summary.status == "blocked"
    assert "capability policy touched" in summary.evidence
    assert "new-demo has no routing proof" in summary.blockers
    assert summary.ok is False


def test_build_skillify_proof_blocks_primary_skill_policy_without_skill_entry(
    tmp_path: Path,
) -> None:
    module = _load_module()
    _write_mcp_primary_skill_policy(tmp_path, "new-demo")

    summary = module.build_skillify_proof(
        repo_changes=[
            module.ChangedPath(
                status="A",
                path="project-brain/capabilities/skills/new-demo/SKILL.md",
            ),
            module.ChangedPath(
                status="A",
                path="project-brain/capabilities/skills/new-demo/scripts/demo.py",
            ),
            module.ChangedPath(
                status="A",
                path="project-brain/capabilities/skills/new-demo/augur/tests/test_demo.py",
            ),
            module.ChangedPath(status="M", path="config/system/capability_exposure.yaml"),
        ],
        repo_root=tmp_path,
    )

    assert summary.status == "blocked"
    assert "capability policy touched" in summary.evidence
    assert "capability policy entry present: new-demo" not in summary.evidence
    assert "new-demo has no routing proof" in summary.blockers
    assert summary.ok is False


def test_build_skillify_proof_blocks_new_skill_with_unrelated_manifest_touch(
    tmp_path: Path,
) -> None:
    module = _load_module()
    _write_skill_manifest(tmp_path, "project-brain/capabilities/skills/platform-admin")

    summary = module.build_skillify_proof(
        repo_changes=[
            module.ChangedPath(
                status="A",
                path="project-brain/capabilities/skills/new-demo/SKILL.md",
            ),
            module.ChangedPath(
                status="A",
                path="project-brain/capabilities/skills/new-demo/scripts/demo.py",
            ),
            module.ChangedPath(
                status="A",
                path="project-brain/capabilities/skills/new-demo/augur/tests/test_demo.py",
            ),
            module.ChangedPath(status="M", path="docs/generated/skill-manifest.json"),
        ],
        repo_root=tmp_path,
    )

    assert summary.status == "blocked"
    assert "skill manifest touched" in summary.evidence
    assert "new-demo has no routing proof" in summary.blockers
    assert summary.ok is False


def test_build_skillify_proof_blocks_deletion_only_skill_mixed_with_valid_skill() -> None:
    module = _load_module()

    summary = module.build_skillify_proof(
        repo_changes=[
            module.ChangedPath(
                status="D",
                path="project-brain/capabilities/skills/new-demo/SKILL.md",
            ),
            module.ChangedPath(
                status="M",
                path="project-brain/capabilities/skills/platform-admin/scripts/dev_merge_demo_proof.py",
            ),
            module.ChangedPath(
                status="M",
                path="project-brain/capabilities/skills/platform-admin/augur/tests/test_demo.py",
            ),
        ],
        repo_root=PROJECT_ROOT,
    )

    assert summary.status == "blocked"
    assert "new-demo has only deletion/removal changes" in summary.blockers
    assert summary.ok is False


def test_build_skillify_proof_blocks_code_without_same_skill_quality_proof() -> None:
    module = _load_module()

    summary = module.build_skillify_proof(
        repo_changes=[
            module.ChangedPath(
                status="M",
                path="project-brain/capabilities/skills/wiki/scripts/wiki_status.py",
            ),
            module.ChangedPath(
                status="M",
                path="project-brain/capabilities/skills/platform-admin/augur/tests/test_demo.py",
            ),
        ],
        repo_root=PROJECT_ROOT,
    )

    assert summary.status == "blocked"
    assert "ingest code-bearing changes need tests or quality proof" in summary.blockers
    assert summary.ok is False


def test_build_wiki_proof_reports_changed_wiki_pages() -> None:
    module = _load_module()

    summary = module.build_wiki_proof(
        status_payload={
            "verdict": "ok",
            "structure": {"pages": 12},
            "compiler": {"current": True},
            "index": {"entries": 12},
        },
        vault_changes=[
            module.ChangedPath(status="M", path="wiki/concepts/agent-memory.md"),
            module.ChangedPath(status="M", path="notes/private-note.md"),
        ],
    )

    assert summary.status == "changed"
    assert summary.items_changed == ["wiki/concepts/agent-memory.md"]
    assert "durable wiki page changed" in summary.what_changed
    assert "wiki-status verdict: ok" in summary.evidence
    assert summary.ok is True


def test_build_wiki_proof_accepts_verified_noop_when_wiki_is_current() -> None:
    module = _load_module()

    summary = module.build_wiki_proof(
        status_payload={
            "verdict": "ok",
            "structure": {"pages": 8},
            "compiler": {"current": True},
            "compounding": {"queries": ["active-projects", "knowledge-gaps"]},
            "index": {"entries": 8},
            "last_extraction_ts": 1780000000.0,
        },
        vault_changes=[],
    )

    assert summary.status == "verified-noop"
    assert summary.items_changed == [
        "compounding query current: active-projects",
        "compounding query current: knowledge-gaps",
    ]
    assert "wiki-status verdict: ok" in summary.evidence
    assert "current evidence timestamp: 2026-05-28T20:26:40Z" in summary.evidence
    assert summary.ok is True


def test_build_wiki_proof_accepts_live_healthy_payload_for_verified_noop() -> None:
    module = _load_module()

    summary = module.build_wiki_proof(
        status_payload={
            "verdict": "healthy",
            "healthy": True,
            "structure": {"pages": 8},
            "compiler": {"current": True},
            "compounding": {"queries": ["q1", "q2"]},
            "index": {"wiki_rag_entries": 8},
            "telemetry": {"last_extraction_ts": 1780000000.0},
        },
        vault_changes=[],
    )

    assert summary.status == "verified-noop"
    assert "wiki index entries: 8" in summary.evidence
    assert "compounding queries: 2" in summary.evidence
    assert "compounding query ids: q1, q2" in summary.evidence
    assert "current evidence timestamp: 2026-05-28T20:26:40Z" in summary.evidence
    assert summary.ok is True


def test_build_wiki_proof_allows_backlog_when_no_durable_wiki_changes() -> None:
    module = _load_module()

    summary = module.build_wiki_proof(
        status_payload={
            "verdict": "structure_ok_compile_backlog",
            "healthy": False,
            "structure": {"pages": 83},
            "compiler": {"current": False},
            "compounding": {
                "queries": [
                    "active-projects",
                    "knowledge-gaps",
                    "profile-human-api",
                    "recent-decisions",
                ]
            },
            "index": {"wiki_rag_entries": 83},
            "generated_at": "2026-05-29T03:34:27.210958+00:00",
        },
        vault_changes=[
            module.ChangedPath(status="M", path="notes/inbox/demo-plan.md"),
        ],
    )

    assert summary.status == "verified-noop"
    assert summary.items_changed == [
        "no durable wiki changes to compound",
        "compounding query present: active-projects",
        "compounding query present: knowledge-gaps",
        "compounding query present: profile-human-api",
        "compounding query present: recent-decisions",
    ]
    assert summary.what_changed == ["no durable wiki changes to compound"]
    assert "wiki-status verdict: structure_ok_compile_backlog" in summary.evidence
    assert "wiki compiler current: False" in summary.evidence
    assert "compounding queries: 4" in summary.evidence
    assert (
        "compounding query ids: active-projects, knowledge-gaps, profile-human-api, recent-decisions"
        in summary.evidence
    )
    assert (
        "current evidence timestamp: 2026-05-29T03:34:27.210958+00:00"
        in summary.evidence
    )
    assert summary.vault_changes == "none"
    assert summary.blockers == []
    assert summary.ok is True


def test_build_wiki_proof_blocks_verified_noop_without_named_pages_or_queries() -> None:
    module = _load_module()

    summary = module.build_wiki_proof(
        status_payload={
            "verdict": "healthy",
            "healthy": True,
            "structure": {"pages": 8},
            "compiler": {"current": True},
            "compounding": {"queries": 3},
            "index": {"wiki_rag_entries": 8},
            "last_extraction_ts": 1780000000.0,
        },
        vault_changes=[],
    )

    assert summary.status == "blocked"
    assert "no named durable wiki page or compounding query evidence found" in summary.blockers
    assert summary.ok is False


def test_build_wiki_proof_blocks_verified_noop_without_freshness_timestamp() -> None:
    module = _load_module()

    summary = module.build_wiki_proof(
        status_payload={
            "verdict": "healthy",
            "healthy": True,
            "structure": {"pages": 8},
            "compiler": {"current": True},
            "compounding": {"queries": ["active-projects"]},
            "index": {"wiki_rag_entries": 8},
        },
        vault_changes=[],
    )

    assert summary.status == "blocked"
    assert "no current evidence timestamp found for wiki verified-noop" in summary.blockers
    assert summary.ok is False


def test_build_wiki_proof_blocks_when_no_real_wiki_evidence_exists() -> None:
    module = _load_module()

    summary = module.build_wiki_proof(
        status_payload={"verdict": "blocked", "structure": {"pages": 0}},
        vault_changes=[],
    )

    assert summary.status == "blocked"
    assert (
        "no named durable wiki page or compounding query evidence found"
        in summary.blockers
    )
    assert summary.ok is False


def test_build_wiki_proof_blocks_on_blocked_verdict_even_when_wiki_changed() -> None:
    module = _load_module()

    summary = module.build_wiki_proof(
        status_payload={
            "verdict": "blocked",
            "structure": {"pages": 12},
            "compiler": {"current": True},
            "index": {"entries": 12},
        },
        vault_changes=[
            module.ChangedPath(status="M", path="wiki/concepts/agent-memory.md"),
        ],
    )

    assert summary.status == "blocked"
    assert "wiki-status verdict: blocked" in summary.evidence
    assert summary.ok is False


def test_build_wiki_proof_blocks_compiler_error_but_preserves_changed_paths() -> None:
    module = _load_module()

    summary = module.build_wiki_proof(
        status_payload={
            "verdict": "compiler_state_error",
            "healthy": False,
            "structure": {"pages": 12},
            "compiler": {"current": True},
            "index": {"wiki_rag_entries": 12},
        },
        vault_changes=[
            module.ChangedPath(status="M", path="wiki/concepts/agent-memory.md"),
        ],
    )

    assert summary.status == "blocked"
    assert summary.items_changed == ["wiki/concepts/agent-memory.md"]
    assert "wiki-status verdict: compiler_state_error" in summary.evidence
    assert summary.ok is False


def test_build_wiki_proof_blocks_compile_backlog_even_when_wiki_changed() -> None:
    module = _load_module()

    summary = module.build_wiki_proof(
        status_payload={
            "verdict": "structure_ok_compile_backlog",
            "healthy": False,
            "structure": {"pages": 12},
            "compiler": {"current": False},
            "index": {"wiki_rag_entries": 12},
        },
        vault_changes=[
            module.ChangedPath(status="M", path="wiki/concepts/agent-memory.md"),
        ],
    )

    assert summary.status == "blocked"
    assert summary.items_changed == ["wiki/concepts/agent-memory.md"]
    assert summary.ok is False


def test_build_wiki_proof_blocks_unknown_non_healthy_verdicts() -> None:
    module = _load_module()

    summary = module.build_wiki_proof(
        status_payload={
            "verdict": "needs_manual_review",
            "healthy": False,
            "structure": {"pages": 12},
            "compiler": {"current": True},
            "index": {"wiki_rag_entries": 12},
        },
        vault_changes=[
            module.ChangedPath(status="M", path="wiki/concepts/agent-memory.md"),
        ],
    )

    assert summary.status == "blocked"
    assert summary.items_changed == ["wiki/concepts/agent-memory.md"]
    assert summary.ok is False


def test_parse_name_status_handles_added_modified_and_renamed_paths() -> None:
    module = _load_module()

    changes = module.parse_name_status(
        "A\tproject-brain/capabilities/skills/new-skill/SKILL.md\n"
        "M\tdocs/agent-topics/WORKFLOWS.md\n"
        "R100\told/wiki/page.md\twiki/page.md\n"
    )

    assert changes == [
        module.ChangedPath(
            status="A", path="project-brain/capabilities/skills/new-skill/SKILL.md"
        ),
        module.ChangedPath(status="M", path="docs/agent-topics/WORKFLOWS.md"),
        module.ChangedPath(status="R100", path="wiki/page.md"),
    ]


def test_parse_porcelain_status_adds_uncommitted_paths() -> None:
    module = _load_module()

    changes = module.parse_porcelain_status(
        " M project-brain/capabilities/skills/platform-admin/SKILL.md\n"
        "?? project-brain/capabilities/skills/platform-admin/scripts/demo.py\n"
    )

    assert changes == [
        module.ChangedPath(
            status="M", path="project-brain/capabilities/skills/platform-admin/SKILL.md"
        ),
        module.ChangedPath(
            status="?",
            path="project-brain/capabilities/skills/platform-admin/scripts/demo.py",
        ),
    ]


def test_parse_porcelain_status_preserves_combined_status_and_non_rename_arrows() -> None:
    module = _load_module()

    changes = module.parse_porcelain_status(
        "R  old/name.md -> docs/new.md\n"
        "C  old/copy.md -> docs/copy.md\n"
        "AM docs/added-modified.md\n"
        "MM docs/both-modified.md\n"
        "MD docs/deleted-in-worktree.md\n"
        " M docs/a -> b.md\n"
        "?? docs/untracked -> still-one-path.md\n"
    )

    assert changes == [
        module.ChangedPath(status="R", path="docs/new.md"),
        module.ChangedPath(status="C", path="docs/copy.md"),
        module.ChangedPath(status="AM", path="docs/added-modified.md"),
        module.ChangedPath(status="MM", path="docs/both-modified.md"),
        module.ChangedPath(status="MD", path="docs/deleted-in-worktree.md"),
        module.ChangedPath(status="M", path="docs/a -> b.md"),
        module.ChangedPath(status="?", path="docs/untracked -> still-one-path.md"),
    ]


def test_collect_git_changes_merges_committed_and_uncommitted_with_dedupe(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    module = _load_module()
    repo_root = tmp_path / "repo"
    calls: list[list[str]] = []

    def fake_run_git(_repo_root: Path, args: list[str]):
        calls.append(args)
        if args == ["merge-base", "HEAD", "origin/main"]:
            return module.subprocess.CompletedProcess(
                args, 0, stdout="abc123\n", stderr=""
            )
        if args == ["diff", "--name-status", "abc123...HEAD"]:
            return module.subprocess.CompletedProcess(
                args,
                0,
                stdout="M\tcommon.md\nA\tcommitted.md\n",
                stderr="",
            )
        if args == ["status", "--porcelain"]:
            return module.subprocess.CompletedProcess(
                args,
                0,
                stdout=" M common.md\n?? untracked.md\n",
                stderr="",
            )
        raise AssertionError(f"Unexpected git args: {args}")

    monkeypatch.setattr(module, "_run_git", fake_run_git)

    changes = module.collect_git_changes(repo_root)

    assert calls == [
        ["merge-base", "HEAD", "origin/main"],
        ["diff", "--name-status", "abc123...HEAD"],
        ["status", "--porcelain"],
    ]
    assert changes == [
        module.ChangedPath(status="M", path="common.md"),
        module.ChangedPath(status="A", path="committed.md"),
        module.ChangedPath(status="?", path="untracked.md"),
    ]


def test_collect_git_changes_raises_on_merge_base_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    module = _load_module()
    repo_root = tmp_path / "repo"

    def fake_run_git(_repo_root: Path, args: list[str]):
        return module.subprocess.CompletedProcess(
            args, 1, stdout="", stderr="fatal: no merge base"
        )

    monkeypatch.setattr(module, "_run_git", fake_run_git)

    with pytest.raises(module.GitInspectionError) as excinfo:
        module.collect_git_changes(repo_root, base_ref="upstream/main")

    message = str(excinfo.value)
    assert "merge-base" in message
    assert str(repo_root) in message
    assert "upstream/main" in message


def test_collect_git_changes_raises_on_status_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    module = _load_module()
    repo_root = tmp_path / "repo"

    def fake_run_git(_repo_root: Path, args: list[str]):
        if args == ["merge-base", "HEAD", "origin/main"]:
            return module.subprocess.CompletedProcess(
                args, 0, stdout="abc123\n", stderr=""
            )
        if args == ["diff", "--name-status", "abc123...HEAD"]:
            return module.subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        if args == ["status", "--porcelain"]:
            return module.subprocess.CompletedProcess(
                args, 128, stdout="", stderr="fatal: not a git repository"
            )
        raise AssertionError(f"Unexpected git args: {args}")

    monkeypatch.setattr(module, "_run_git", fake_run_git)

    with pytest.raises(module.GitInspectionError) as excinfo:
        module.collect_git_changes(repo_root)

    message = str(excinfo.value)
    assert "status --porcelain" in message
    assert str(repo_root) in message
    assert "origin/main" in message


def test_render_demo_proof_prints_requested_summaries_and_pass_result() -> None:
    module = _load_module()

    result = module.DemoProofResult(
        wiki=module.ProofSummary(
            title="Wiki compounding summary",
            status="verified-noop",
            inputs_used=["wiki-status"],
            items_changed=["8 wiki pages current"],
            what_changed=["real wiki state already current"],
            evidence=["wiki-status verdict: ok"],
            vault_changes="none",
        ),
        skillify=module.ProofSummary(
            title="Skillify summary",
            status="updated",
            inputs_used=["git diff"],
            items_changed=["project-brain/capabilities/skills/platform-admin/SKILL.md"],
            what_changed=["SKILL.md"],
            evidence=["1 canonical skill artifact(s) changed"],
            incident_gap="merge set contains durable skill artifacts",
            skill_path="project-brain/capabilities/skills/platform-admin",
        ),
    )

    rendered = module.render_demo_proof(result)

    assert "Demo proof summary before merge" in rendered
    assert "Wiki compounding summary" in rendered
    assert "- Status: verified-noop" in rendered
    assert "Skillify summary" in rendered
    assert "- Skill affected: project-brain/capabilities/skills/platform-admin" in rendered
    assert "Result: proof passed; continuing /dev-merge full" in rendered


def test_render_demo_proof_prints_blocking_reasons() -> None:
    module = _load_module()

    result = module.DemoProofResult(
        skillify=module.ProofSummary(
            title="Skillify summary",
            status="blocked",
            blockers=["no canonical skill source changed in the merge set"],
        )
    )

    rendered = module.render_demo_proof(result)

    assert "Result: blocked before merge" in rendered
    assert "Reason: no canonical skill source changed in the merge set" in rendered


def test_render_demo_proof_prints_compound_review_before_proofs() -> None:
    module = _load_module()

    result = module.DemoProofResult(
        compound_review=module.CompoundReviewResult(
            proposal=module.CompoundReviewProposal(
                status="proposed",
                durable_lesson="Client skill projection is a contract boundary.",
                evidence=[
                    "Codex skipped 10 projected skills because frontmatter was missing.",
                    "Parser-facing tests cover YAML-safe command skill metadata.",
                ],
                target_type="existing_skill",
                target_artifact="project-brain/capabilities/skills/ai/references/client-projection.md",
                next_action="Strengthen client projection guidance with a parser-gate rule.",
                confidence="high",
                why_not=["No new skill is needed because sync_agents owns this path."],
            ),
        ),
        wiki=module.ProofSummary(title="Wiki compounding summary", status="verified-noop"),
        skillify=module.ProofSummary(title="Skillify summary", status="updated"),
    )

    rendered = module.render_demo_proof(result)

    assert rendered.index("Compound review") < rendered.index("Wiki compounding summary")
    assert "Durable lesson: Client skill projection is a contract boundary." in rendered
    assert "Target artifact: project-brain/capabilities/skills/ai/references/client-projection.md" in rendered
    assert "Result: proof passed; continuing /dev-merge full" in rendered


def test_result_payload_includes_compound_review_validation() -> None:
    module = _load_module()

    result = module.DemoProofResult(
        compound_review=module.CompoundReviewResult(
            proposal=module.CompoundReviewProposal(
                status="blocked",
                durable_lesson="Improve skills.",
                evidence=["Tests passed.", "The command ran."],
                target_type="existing_skill",
                target_artifact="",
                next_action="Improve docs.",
                confidence="high",
            ),
            validation=module.CompoundReviewValidation(
                ok=False,
                blockers=["target_artifact is required for proposed review"],
            ),
        ),
        requested=module.DemoProofOptions(compound_wiki=True),
        wiki=module.ProofSummary(title="Wiki compounding summary", status="verified-noop"),
    )

    payload = module._result_payload(result)

    assert payload["compound_review"]["validation"]["ok"] is False
    assert payload["compound_review"]["validation"]["blockers"] == [
        "target_artifact is required for proposed review"
    ]


def test_render_compound_review_missing_proposal_reports_blocked_status() -> None:
    module = _load_module()

    result = module.CompoundReviewResult()

    rendered = module.render_compound_review(result)

    assert "- Status: blocked" in rendered
    assert "compound review proposal was not supplied by the native agent" in rendered


def test_demo_proof_result_ignores_compound_review_blockers_when_review_is_ok() -> None:
    module = _load_module()

    result = module.DemoProofResult(
        compound_review=module.CompoundReviewResult(
            proposal=module.CompoundReviewProposal(
                status="proposed",
                durable_lesson="Client skill projection is a contract boundary.",
                evidence=[
                    "Codex skipped 10 projected skills because frontmatter was missing.",
                    "Parser-facing tests cover YAML-safe command skill metadata.",
                ],
                target_type="existing_skill",
                target_artifact="project-brain/capabilities/skills/ai/references/client-projection.md",
                next_action="Strengthen client projection guidance with a parser-gate rule.",
                confidence="high",
                why_not=["No new skill is needed because sync_agents owns this path."],
            ),
            validation=module.CompoundReviewValidation(
                ok=True,
                blockers=["stale validation blocker should not affect ok review"],
            ),
        ),
        wiki=module.ProofSummary(title="Wiki compounding summary", status="verified-noop"),
    )

    assert result.blockers == []


def test_blocked_compound_review_blocks_demo_proof_even_with_valid_validation() -> None:
    module = _load_module()

    compound_review = module.CompoundReviewResult(
        proposal=module.CompoundReviewProposal(
            status="blocked",
            durable_lesson="Client skill projection needs native-agent evidence before changing parser contracts.",
            evidence=[
                "Codex transcript shows the native agent did not supply a proposal artifact.",
                "dev_merge_demo_proof.py recorded the compound review preflight as blocked.",
            ],
            target_type="existing_skill",
            target_artifact="project-brain/capabilities/skills/ai/references/client-projection.md",
            next_action="Rerun compound review with a native-agent proposal artifact before merge.",
            confidence="high",
            why_not=["The review is blocked by missing native-agent proposal output."],
        ),
        validation=module.CompoundReviewValidation(ok=True),
    )
    result = module.DemoProofResult(
        compound_review=compound_review,
        wiki=module.ProofSummary(title="Wiki compounding summary", status="verified-noop"),
        skillify=module.ProofSummary(title="Skillify summary", status="updated"),
    )

    rendered = module.render_demo_proof(result)

    assert compound_review.ok is False
    assert result.ok is False
    assert "Result: blocked before merge" in rendered
    assert result.blockers == ["compound review proposal status is blocked"]
    assert "Reason: compound review proposal status is blocked" in rendered


def test_write_demo_proof_artifact_writes_json_to_runtime_dir(tmp_path: Path) -> None:
    module = _load_module()

    result = module.DemoProofResult(
        skillify=module.ProofSummary(title="Skillify summary", status="updated")
    )
    result.repo_root = str(PROJECT_ROOT)
    result.vault_root = "/tmp/vault"
    result.base_ref = "origin/main"

    artifact = module.write_demo_proof_artifact(result, runtime_dir=tmp_path)

    assert artifact.parent == tmp_path / "dev-merge" / "demo-proof"
    assert artifact.read_text(encoding="utf-8").startswith("{\n")
    assert result.artifact_path == str(artifact)
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["blockers"] == []
    assert payload["created_at"]
    assert payload["repo_root"] == str(PROJECT_ROOT)
    assert payload["vault_root"] == "/tmp/vault"
    assert payload["base_ref"] == "origin/main"


def test_build_compound_review_evidence_names_repo_wiki_and_skill_signals() -> None:
    module = _load_module()

    evidence = module.build_compound_review_evidence(
        repo_root=PROJECT_ROOT,
        vault_root=Path("/tmp/demo-vault"),
        base_ref="origin/main",
        repo_changes=[
            module.ChangedPath(
                status="M",
                path="project-brain/capabilities/skills/platform-admin/scripts/dev_merge_demo_proof.py",
            ),
            module.ChangedPath(
                status="M",
                path="project-brain/capabilities/skills/platform-admin/augur/tests/test_dev_merge_demo_proof.py",
            ),
        ],
        wiki_summary=module.ProofSummary(
            title="Wiki compounding summary",
            status="verified-noop",
            evidence=[
                "wiki-status verdict: structure_ok_compile_backlog",
                "compounding query ids: active-projects, knowledge-gaps",
            ],
        ),
        skillify_summary=module.ProofSummary(
            title="Skillify summary",
            status="updated",
            evidence=[
                "2 canonical skill artifact(s) changed",
                "quality verification passed: platform-admin: 42 passed",
            ],
            incident_gap="platform-admin durable skill behavior changed: scripts, tests",
            skill_path="project-brain/capabilities/skills/platform-admin",
        ),
    )

    assert evidence.repo_root == str(PROJECT_ROOT)
    assert evidence.vault_root == "/tmp/demo-vault"
    assert evidence.base_ref == "origin/main"
    assert (
        "project-brain/capabilities/skills/platform-admin"
        in evidence.skill_roots_changed
    )
    assert "wiki-status verdict: structure_ok_compile_backlog" in evidence.wiki_evidence
    assert "2 canonical skill artifact(s) changed" in evidence.skillify_evidence
    assert evidence.missing_optional_sources == []


def test_write_compound_review_evidence_artifact_writes_runtime_json(
    tmp_path: Path,
) -> None:
    module = _load_module()

    evidence = module.CompoundReviewEvidence(
        repo_root=str(PROJECT_ROOT),
        vault_root="/tmp/demo-vault",
        base_ref="origin/main",
        repo_changes=[
            "M project-brain/capabilities/skills/platform-admin/scripts/dev_merge_demo_proof.py",
        ],
        skill_roots_changed=["project-brain/capabilities/skills/platform-admin"],
        wiki_evidence=["compounding query ids: active-projects"],
        skillify_evidence=["quality verification passed: platform-admin: 42 passed"],
    )

    artifact = module.write_compound_review_evidence_artifact(evidence, tmp_path)

    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert artifact.parent == tmp_path / "dev-merge" / "compound-review"
    assert payload["repo_root"] == str(PROJECT_ROOT)
    assert payload["skill_roots_changed"] == [
        "project-brain/capabilities/skills/platform-admin"
    ]


def test_build_compound_review_evidence_records_missing_transcript(
    tmp_path: Path,
) -> None:
    module = _load_module()
    transcript_path = tmp_path / "missing-transcript.txt"

    evidence = module.build_compound_review_evidence(
        repo_root=PROJECT_ROOT,
        vault_root=Path("/tmp/demo-vault"),
        base_ref="origin/main",
        repo_changes=[],
        transcript_path=transcript_path,
    )

    assert evidence.transcript_snippets == []
    assert evidence.missing_optional_sources == [
        f"transcript not found: {transcript_path}"
    ]


def test_build_compound_review_evidence_keeps_last_twelve_transcript_lines(
    tmp_path: Path,
) -> None:
    module = _load_module()
    transcript_path = tmp_path / "transcript.txt"
    transcript_path.write_text(
        "\n".join(f"  line {index}  " for index in range(15)) + "\n\n",
        encoding="utf-8",
    )

    evidence = module.build_compound_review_evidence(
        repo_root=PROJECT_ROOT,
        vault_root=Path("/tmp/demo-vault"),
        base_ref="origin/main",
        repo_changes=[],
        transcript_path=transcript_path,
    )

    assert evidence.transcript_snippets == [f"line {index}" for index in range(3, 15)]
    assert evidence.missing_optional_sources == []


def test_build_compound_review_evidence_records_invalid_transcript_encoding(
    tmp_path: Path,
) -> None:
    module = _load_module()
    transcript_path = tmp_path / "transcript.txt"
    transcript_path.write_bytes(b"\xff\xfe\xfa")

    evidence = module.build_compound_review_evidence(
        repo_root=PROJECT_ROOT,
        vault_root=Path("/tmp/demo-vault"),
        base_ref="origin/main",
        repo_changes=[],
        transcript_path=transcript_path,
    )

    assert evidence.transcript_snippets == []
    assert len(evidence.missing_optional_sources) == 1
    assert str(transcript_path) in evidence.missing_optional_sources[0]
    assert "transcript unreadable:" in evidence.missing_optional_sources[0]


def test_attach_compound_review_blocks_repo_inspection_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    repo_root = tmp_path / "repo"
    vault_root = tmp_path / "vault"
    runtime_dir = tmp_path / "runtime"
    repo_root.mkdir()
    vault_root.mkdir()
    runtime_dir.mkdir()
    proposal_path = tmp_path / "proposal.json"
    proposal_path.write_text(
        json.dumps(
            {
                "status": "proposed",
                "durable_lesson": "Client skill projection is a contract boundary.",
                "evidence": [
                    "Codex skipped 10 projected skills because frontmatter was missing.",
                    "Parser-facing tests cover YAML-safe command skill metadata.",
                ],
                "target_type": "existing_skill",
                "target_artifact": "project-brain/capabilities/skills/ai/references/client-projection.md",
                "next_action": "Strengthen client projection guidance with a parser-gate rule.",
                "confidence": "high",
                "why_not": [
                    "No new skill is needed because sync_agents owns this path."
                ],
            }
        ),
        encoding="utf-8",
    )

    def fail_collect_git_changes(root: Path, base_ref: str):
        assert root == repo_root
        assert base_ref == "main"
        raise module.GitInspectionError("fatal: missing merge base")

    monkeypatch.setattr(module, "collect_git_changes", fail_collect_git_changes)

    result = module.DemoProofResult(
        wiki=module.ProofSummary(title="Wiki compounding summary", status="verified-noop"),
        skillify=module.ProofSummary(title="Skillify summary", status="updated"),
    )

    module.attach_compound_review(
        result=result,
        repo_root=repo_root,
        vault_root=vault_root,
        base_ref="main",
        runtime_dir=runtime_dir,
        proposal_json=proposal_path,
    )

    assert result.compound_review is not None
    assert result.compound_review.ok is False
    assert (
        "compound review repo changes could not be inspected: fatal: missing merge base"
        in result.compound_review.blockers
    )
    evidence_payload = json.loads(
        Path(result.compound_review.evidence_artifact_path).read_text(encoding="utf-8")
    )
    assert (
        "compound review repo changes could not be inspected: fatal: missing merge base"
        in evidence_payload["missing_optional_sources"]
    )


def test_main_bootstraps_before_resolving_default_vault_and_runtime(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    module = _load_module()
    repo_root = tmp_path / "repo"
    configured_vault = tmp_path / "configured-vault"
    configured_runtime = tmp_path / "configured-runtime"
    (repo_root / "docs" / "agent-topics").mkdir(parents=True)
    (repo_root / "project-brain" / "capabilities" / "skills").mkdir(parents=True)
    (repo_root / "src" / "mcp").mkdir(parents=True)
    configured_vault.mkdir()
    configured_runtime.mkdir()
    original_sys_path = list(module.sys.path)

    for path in (
        repo_root,
        repo_root / "src" / "mcp",
        repo_root / "project-brain" / "capabilities",
    ):
        while str(path) in module.sys.path:
            module.sys.path.remove(str(path))

    fake_paths = types.SimpleNamespace(
        get_project_root=lambda: repo_root,
        get_vault_dir=lambda: configured_vault,
        get_runtime_dir=lambda: configured_runtime,
    )
    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "src.config.paths":
            required_paths = {
                str(repo_root),
                str(repo_root / "src" / "mcp"),
                str(repo_root / "project-brain" / "capabilities"),
            }
            if not required_paths.issubset(set(module.sys.path)):
                raise ModuleNotFoundError("repo paths not bootstrapped")
            return fake_paths
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    monkeypatch.chdir(repo_root)
    build_calls: list[tuple[module.DemoProofOptions, Path, Path, str]] = []
    artifact_runtime_dirs: list[Path] = []

    def fake_build_demo_proof(
        options: module.DemoProofOptions,
        repo_root: Path,
        vault_root: Path,
        base_ref: str,
    ) -> module.DemoProofResult:
        build_calls.append((options, repo_root, vault_root, base_ref))
        return module.DemoProofResult(
            requested=options,
            skillify=module.ProofSummary(title="Skillify summary", status="updated"),
        )

    def fake_write_demo_proof_artifact(
        _result: module.DemoProofResult,
        runtime_dir: Path,
    ) -> Path:
        artifact_runtime_dirs.append(runtime_dir)
        return runtime_dir / "demo-proof.json"

    monkeypatch.setattr(module, "build_demo_proof", fake_build_demo_proof)
    monkeypatch.setattr(
        module,
        "write_demo_proof_artifact",
        fake_write_demo_proof_artifact,
    )

    try:
        exit_code = module.main(["--skillify"])
    finally:
        module.sys.path[:] = original_sys_path

    assert exit_code == 0
    assert build_calls == [
        (
            module.DemoProofOptions(skillify=True),
            repo_root,
            configured_vault,
            "origin/main",
        )
    ]
    assert artifact_runtime_dirs == [configured_runtime]


def test_main_rejects_review_proposal_without_compound_review(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_module()
    proposal_path = tmp_path / "proposal.json"
    proposal_path.write_text("{}", encoding="utf-8")

    with pytest.raises(SystemExit) as excinfo:
        module.main(["--com", "--review-proposal-json", str(proposal_path)])

    captured = capsys.readouterr()
    assert excinfo.value.code == 2
    assert (
        "--review-proposal-json/--review-transcript require --compound-review"
        in captured.err
    )


def test_main_renders_compound_review_from_native_agent_proposal(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_module()
    proposal_path = tmp_path / "proposal.json"
    proposal_path.write_text(
        json.dumps(
            {
                "status": "proposed",
                "durable_lesson": "Client skill projection is a contract boundary.",
                "evidence": [
                    "Codex skipped 10 projected skills because frontmatter was missing.",
                    "Parser-facing tests cover YAML-safe command skill metadata.",
                ],
                "target_type": "existing_skill",
                "target_artifact": "project-brain/capabilities/skills/ai/references/client-projection.md",
                "next_action": "Strengthen client projection guidance with a parser-gate rule.",
                "confidence": "high",
                "why_not": [
                    "No new skill is needed because sync_agents owns this path."
                ],
            }
        ),
        encoding="utf-8",
    )

    def fake_build_demo_proof(
        options: module.DemoProofOptions,
        repo_root: Path,
        vault_root: Path,
        base_ref: str,
    ) -> module.DemoProofResult:
        return module.DemoProofResult(
            requested=options,
            repo_root=str(repo_root),
            vault_root=str(vault_root),
            base_ref=base_ref,
            wiki=module.ProofSummary(title="Wiki compounding summary", status="verified-noop"),
            skillify=module.ProofSummary(title="Skillify summary", status="updated"),
        )

    monkeypatch.setattr(module, "build_demo_proof", fake_build_demo_proof)
    monkeypatch.setattr(
        module,
        "write_demo_proof_artifact",
        lambda result, runtime_dir: runtime_dir / "demo-proof.json",
    )

    exit_code = module.main(
        [
            "--com",
            "--skillify",
            "--compound-review",
            "--review-proposal-json",
            str(proposal_path),
            "--runtime-dir",
            str(tmp_path),
            "--repo-root",
            str(PROJECT_ROOT),
            "--vault-root",
            str(tmp_path / "vault"),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Compound review" in output
    assert "Durable lesson: Client skill projection is a contract boundary." in output
    assert "Wiki compounding summary" in output
    assert "Skillify summary" in output


def test_main_blocks_compound_review_when_proposal_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_module()

    monkeypatch.setattr(
        module,
        "build_demo_proof",
        lambda options, repo_root, vault_root, base_ref: module.DemoProofResult(
            requested=options,
            repo_root=str(repo_root),
            vault_root=str(vault_root),
            base_ref=base_ref,
            wiki=module.ProofSummary(title="Wiki compounding summary", status="verified-noop"),
        ),
    )
    monkeypatch.setattr(
        module,
        "write_demo_proof_artifact",
        lambda result, runtime_dir: runtime_dir / "demo-proof.json",
    )

    exit_code = module.main(
        [
            "--com",
            "--compound-review",
            "--runtime-dir",
            str(tmp_path),
            "--repo-root",
            str(PROJECT_ROOT),
            "--vault-root",
            str(tmp_path / "vault"),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 2
    assert "Wiki compounding summary" in output
    assert "Reason: compound review proposal was not supplied by the native agent" in output


def test_main_blocks_compound_review_when_proposal_path_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_module()
    missing_path = tmp_path / "missing-proposal.json"

    monkeypatch.setattr(
        module,
        "build_demo_proof",
        lambda options, repo_root, vault_root, base_ref: module.DemoProofResult(
            requested=options,
            repo_root=str(repo_root),
            vault_root=str(vault_root),
            base_ref=base_ref,
            wiki=module.ProofSummary(title="Wiki compounding summary", status="verified-noop"),
        ),
    )
    monkeypatch.setattr(
        module,
        "write_demo_proof_artifact",
        lambda result, runtime_dir: runtime_dir / "demo-proof.json",
    )

    exit_code = module.main(
        [
            "--com",
            "--compound-review",
            "--review-proposal-json",
            str(missing_path),
            "--runtime-dir",
            str(tmp_path),
            "--repo-root",
            str(PROJECT_ROOT),
            "--vault-root",
            str(tmp_path / "vault"),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 2
    assert "Result: blocked before merge" in output
    assert "compound review proposal could not be loaded:" in output
    assert str(missing_path) in output


def test_main_blocks_compound_review_when_proposal_json_is_malformed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_module()
    proposal_path = tmp_path / "proposal.json"
    proposal_path.write_text("{not valid json", encoding="utf-8")

    monkeypatch.setattr(
        module,
        "build_demo_proof",
        lambda options, repo_root, vault_root, base_ref: module.DemoProofResult(
            requested=options,
            repo_root=str(repo_root),
            vault_root=str(vault_root),
            base_ref=base_ref,
            wiki=module.ProofSummary(title="Wiki compounding summary", status="verified-noop"),
        ),
    )
    monkeypatch.setattr(
        module,
        "write_demo_proof_artifact",
        lambda result, runtime_dir: runtime_dir / "demo-proof.json",
    )

    exit_code = module.main(
        [
            "--com",
            "--compound-review",
            "--review-proposal-json",
            str(proposal_path),
            "--runtime-dir",
            str(tmp_path),
            "--repo-root",
            str(PROJECT_ROOT),
            "--vault-root",
            str(tmp_path / "vault"),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 2
    assert "Result: blocked before merge" in output
    assert "compound review proposal could not be loaded:" in output
    assert str(proposal_path) in output


def test_import_wiki_status_module_adds_repo_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    module = _load_module()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    imported: list[str] = []
    original_sys_path = list(module.sys.path)

    class FakeWikiStatusModule:
        pass

    def fake_import_module(name: str):
        imported.append(name)
        return FakeWikiStatusModule()

    monkeypatch.setattr(
        module,
        "importlib",
        types.SimpleNamespace(import_module=fake_import_module),
        raising=False,
    )

    imported_module = module._import_wiki_status_module(repo_root)

    assert isinstance(imported_module, FakeWikiStatusModule)
    assert imported == ["skills.wiki.scripts.wiki_status"]
    assert str(repo_root / "project-brain" / "capabilities") in module.sys.path
    assert str(repo_root / "src" / "mcp") in module.sys.path
    assert str(repo_root) in module.sys.path
    module.sys.path[:] = original_sys_path


def test_load_wiki_status_uses_in_process_builder_and_requested_vault(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    module = _load_module()
    repo_root = tmp_path / "repo"
    vault_root = tmp_path / "vault"
    repo_root.mkdir()
    (vault_root / "wiki").mkdir(parents=True)
    calls: list[Path] = []

    class FakeWikiStatusModule:
        @staticmethod
        def build_wiki_status(*, wiki_dir: Path):
            calls.append(wiki_dir)
            return {
                "verdict": "healthy",
                "healthy": True,
                "wiki_dir": str(wiki_dir),
                "structure": {"pages": 3},
                "compiler": {"current": True},
                "index": {"entries": 3},
                "compounding": {"queries": []},
            }

        @staticmethod
        def load_compounding_queries(vault_dir: Path):
            return [f"query-from-{vault_dir.name}"]

    monkeypatch.setattr(
        module,
        "_import_wiki_status_module",
        lambda _repo_root: FakeWikiStatusModule,
        raising=False,
    )

    payload = module._load_wiki_status(repo_root, vault_root)

    assert calls == [vault_root / "wiki"]
    assert payload["verdict"] == "healthy"
    assert payload["wiki_dir"] == str(vault_root / "wiki")
    assert payload["compounding"]["queries"] == ["query-from-vault"]


def test_load_wiki_status_returns_blocked_payload_on_import_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    module = _load_module()
    repo_root = tmp_path / "repo"
    vault_root = tmp_path / "vault"
    repo_root.mkdir()
    vault_root.mkdir()

    def fail_import(_repo_root: Path):
        raise RuntimeError("boom import")

    monkeypatch.setattr(
        module,
        "_import_wiki_status_module",
        fail_import,
        raising=False,
    )

    payload = module._load_wiki_status(repo_root, vault_root)

    assert payload["verdict"] == "blocked"
    assert (
        payload["compiler"]["error"]
        == "wiki status import/build failed: boom import"
    )


def test_build_demo_proof_preserves_requested_options_and_blocks_repo_inspection_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    module = _load_module()
    repo_root = tmp_path / "repo"
    vault_root = tmp_path / "vault"
    repo_root.mkdir()
    vault_root.mkdir()
    options = module.DemoProofOptions(compound_wiki=True, skillify=True)

    def fake_collect_git_changes(root: Path, base_ref: str):
        assert base_ref == "main"
        if root == repo_root:
            raise module.GitInspectionError("Git inspection failed during repo status")
        raise AssertionError(f"Unexpected git root: {root}")

    monkeypatch.setattr(module, "collect_git_changes", fake_collect_git_changes)
    monkeypatch.setattr(
        module,
        "_load_wiki_status",
        lambda _repo_root, _vault_root: {
            "verdict": "ok",
            "structure": {"pages": 8},
            "compiler": {"current": True},
            "compounding": {"queries": ["active-projects"]},
            "index": {"entries": 8},
            "last_extraction_ts": 1780000000.0,
        },
    )

    result = module.build_demo_proof(
        options=options,
        repo_root=repo_root,
        vault_root=vault_root,
        base_ref="main",
    )

    assert result.requested == options
    assert result.repo_root == str(repo_root)
    assert result.vault_root == str(vault_root)
    assert result.base_ref == "main"
    assert result.created_at
    assert result.wiki is not None
    assert result.wiki.status == "verified-noop"
    assert result.skillify is not None
    assert result.skillify.status == "blocked"
    assert "Git inspection failed during repo status" in result.skillify.blockers
    assert "Git inspection failed during repo status" in result.skillify.evidence
    assert result.ok is False


def test_build_demo_proof_runs_quality_verification_for_code_bearing_roots(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    root = "project-brain/capabilities/skills/platform-admin"
    seen_roots: list[str] = []

    monkeypatch.setattr(
        module,
        "collect_git_changes",
        lambda _repo_root, base_ref: [
            module.ChangedPath(
                status="M",
                path=f"{root}/scripts/dev_merge_demo_proof.py",
            ),
            module.ChangedPath(
                status="M",
                path=f"{root}/augur/tests/test_dev_merge_demo_proof.py",
            ),
        ],
    )

    def fake_quality(repo_root: Path, roots: list[str]):
        assert repo_root == PROJECT_ROOT
        seen_roots.extend(roots)
        return {
            root: module.QualityVerification(
                ok=True,
                evidence="quality verification passed: platform-admin: 530 passed",
            )
        }

    monkeypatch.setattr(module, "_run_skill_quality_verifications", fake_quality)

    result = module.build_demo_proof(
        options=module.DemoProofOptions(skillify=True),
        repo_root=PROJECT_ROOT,
        vault_root=PROJECT_ROOT,
        base_ref="main",
    )

    assert seen_roots == [root]
    assert result.skillify is not None
    assert "quality verification passed: platform-admin: 530 passed" in result.skillify.evidence
    assert result.skillify.ok is True


def test_build_demo_proof_blocks_vault_git_inspection_failure_for_wiki(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    module = _load_module()
    repo_root = tmp_path / "repo"
    vault_root = tmp_path / "vault"
    repo_root.mkdir()
    vault_root.mkdir()
    (vault_root / ".git").mkdir()
    options = module.DemoProofOptions(compound_wiki=True)

    def fake_collect_git_changes(root: Path, base_ref: str):
        assert base_ref == "main"
        if root == vault_root:
            raise module.GitInspectionError("Git inspection failed during vault diff")
        raise AssertionError(f"Unexpected git root: {root}")

    monkeypatch.setattr(module, "collect_git_changes", fake_collect_git_changes)

    result = module.build_demo_proof(
        options=options,
        repo_root=repo_root,
        vault_root=vault_root,
        base_ref="main",
    )

    assert result.requested == options
    assert result.wiki is not None
    assert result.wiki.status == "blocked"
    assert "Git inspection failed during vault diff" in result.wiki.blockers
    assert "Git inspection failed during vault diff" in result.wiki.evidence
    assert result.ok is False


def test_main_returns_blocked_exit_and_writes_artifact(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    module = _load_module()
    repo_root = tmp_path / "repo"
    vault_root = tmp_path / "vault"
    runtime_dir = tmp_path / "runtime"
    repo_root.mkdir()
    vault_root.mkdir()
    runtime_dir.mkdir()
    calls: list[tuple[module.DemoProofOptions, Path, Path, str]] = []

    def fake_build_demo_proof(
        options: module.DemoProofOptions,
        repo_root: Path,
        vault_root: Path,
        base_ref: str,
    ) -> module.DemoProofResult:
        calls.append((options, repo_root, vault_root, base_ref))
        return module.DemoProofResult(
            requested=options,
            skillify=module.ProofSummary(
                title="Skillify summary",
                status="blocked",
                blockers=["no canonical skill source changed in the merge set"],
            ),
        )

    monkeypatch.setattr(module, "build_demo_proof", fake_build_demo_proof)

    exit_code = module.main(
        [
            "--skillify",
            "--repo-root",
            str(repo_root),
            "--vault-root",
            str(vault_root),
            "--runtime-dir",
            str(runtime_dir),
            "--base-ref",
            "main",
        ]
    )

    captured = capsys.readouterr()
    artifacts = sorted((runtime_dir / "dev-merge" / "demo-proof").glob("*.json"))
    assert exit_code == 2
    assert len(artifacts) == 1
    assert "Result: blocked before merge" in captured.out
    assert "no canonical skill source changed in the merge set" in artifacts[0].read_text(
        encoding="utf-8"
    )
    assert calls == [
        (
            module.DemoProofOptions(skillify=True),
            repo_root,
            vault_root,
            "main",
        )
    ]
