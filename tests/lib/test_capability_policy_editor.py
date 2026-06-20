from pathlib import Path
from typing import cast

import pytest
import yaml

from src.lib.capabilities.exposure_policy import (
    CapabilityRecord,
    CapabilityType,
    ClassificationStatus,
    Management,
    OwnerKind,
)
from src.lib.capabilities.policy_editor import (
    CapabilityPolicyError,
    apply_capability_policy_draft,
    draft_capability_policy,
    policy_content_hash,
)


def _record(
    capability_id: str,
    *,
    capability_type: str = "skill",
    owner_kind: str = "augur",
    management: str = "generated",
    scope: str = "project",
    primary_surface: str | None = None,
    preferred_client: str = "codex",
    export_to: tuple[str, ...] = ("codex",),
    classification_status: str = "approved",
    current_exposure: tuple[str, ...] = (),
) -> CapabilityRecord:
    return CapabilityRecord(
        id=capability_id,
        type=cast(CapabilityType, capability_type),
        owner_kind=cast(OwnerKind, owner_kind),
        management=cast(Management, management),
        scope=scope,  # type: ignore[arg-type]
        primary_surface=primary_surface or capability_type,
        preferred_client=preferred_client,
        export_to=export_to,
        classification_status=cast(ClassificationStatus, classification_status),
        source_paths=("project-brain/capabilities/skills/example/SKILL.md",),
        current_exposure=current_exposure,
        drift=(),
        metadata={},
    )


def test_draft_keep_only_in_client_returns_diff_and_impact_for_geo_audit(
    tmp_path: Path,
) -> None:
    policy_path = tmp_path / "capability_exposure.yaml"
    records = [
        _record(
            "skill:geo-audit",
            owner_kind="external",
            management="unmanaged",
            scope="global",
            current_exposure=("claude", "codex"),
        )
    ]

    draft = draft_capability_policy(
        records,
        policy_path=policy_path,
        action="keep_only_in_client",
        capability_ids=["skill:geo-audit"],
        params={"target_client": "claude"},
    )

    assert draft["base_hash"] == policy_content_hash("version: 1\ncapabilities: {}\n")
    assert draft["entries"]["skill:geo-audit"] == {
        "owner_kind": "external",
        "management": "unmanaged",
        "scope": "global",
        "primary_surface": "skill",
        "preferred_client": "claude",
        "export_to": ["claude"],
        "classification_status": "approved",
    }
    assert "-    - codex" in draft["diff"]
    assert draft["impact"]["removed_from"] == {"skill:geo-audit": ["codex"]}
    assert draft["impact"]["added_to"] == {}
    assert draft["impact"]["gemini_delta"] == 0
    assert draft["impact"]["opencode_delta"] == 0


def test_draft_move_to_cli_only_for_augur_generated_mcp_tool_sets_cli_fields(
    tmp_path: Path,
) -> None:
    records = [
        _record(
            "mcp-tool:dashboard-cache-clear",
            capability_type="mcp-tool",
            current_exposure=("gemini",),
        )
    ]

    draft = draft_capability_policy(
        records,
        policy_path=tmp_path / "capability_exposure.yaml",
        action="move_to_cli_only",
        capability_ids=["mcp-tool:dashboard-cache-clear"],
    )

    assert draft["entries"]["mcp-tool:dashboard-cache-clear"] == {
        "owner_kind": "augur",
        "management": "generated",
        "scope": "project",
        "primary_surface": "cli",
        "preferred_client": "shell",
        "export_to": ["cli", "agents-md", "browse"],
        "classification_status": "approved",
    }
    assert draft["impact"]["removed_from"] == {"mcp-tool:dashboard-cache-clear": ["gemini"]}
    assert draft["impact"]["added_to"] == {"mcp-tool:dashboard-cache-clear": ["agents-md", "browse", "cli"]}
    assert draft["impact"]["gemini_delta"] == -1


def test_draft_approve_current_exposure_for_external_cli_sets_shell_policy(
    tmp_path: Path,
) -> None:
    records = [
        _record(
            "cli:gh",
            capability_type="cli",
            owner_kind="external",
            management="unmanaged",
            scope="global",
            preferred_client="none",
            export_to=(),
            classification_status="unclassified",
            current_exposure=("browse", "shell"),
        )
    ]

    draft = draft_capability_policy(
        records,
        policy_path=tmp_path / "capability_exposure.yaml",
        action="approve_current_exposure",
        capability_ids=["cli:gh"],
    )

    assert draft["entries"]["cli:gh"] == {
        "owner_kind": "external",
        "management": "unmanaged",
        "scope": "global",
        "primary_surface": "cli",
        "preferred_client": "shell",
        "export_to": ["browse", "shell"],
        "classification_status": "approved",
    }
    assert draft["impact"]["removed_from"] == {}
    assert draft["impact"]["added_to"] == {}


def test_move_to_cli_only_rejects_unmanaged_external_skill(tmp_path: Path) -> None:
    records = [
        _record(
            "skill:geo-audit",
            owner_kind="external",
            management="unmanaged",
            current_exposure=("gemini",),
        )
    ]

    with pytest.raises(CapabilityPolicyError, match="move_to_cli_only"):
        draft_capability_policy(
            records,
            policy_path=tmp_path / "capability_exposure.yaml",
            action="move_to_cli_only",
            capability_ids=["skill:geo-audit"],
        )


def test_block_from_clients_preserves_preferred_client(tmp_path: Path) -> None:
    records = [
        _record(
            "skill:geo-audit",
            preferred_client="claude",
            export_to=("claude", "codex"),
            current_exposure=("claude", "codex"),
        )
    ]

    draft = draft_capability_policy(
        records,
        policy_path=tmp_path / "capability_exposure.yaml",
        action="block_from_clients",
        capability_ids=["skill:geo-audit"],
        params={"clients": ["claude"]},
    )

    assert draft["entries"]["skill:geo-audit"]["preferred_client"] == "claude"
    assert draft["entries"]["skill:geo-audit"]["export_to"] == ["codex"]
    assert draft["impact"]["removed_from"] == {"skill:geo-audit": ["claude"]}


def test_apply_writes_policy_when_base_hash_matches(tmp_path: Path) -> None:
    policy_path = tmp_path / "capability_exposure.yaml"
    records = [
        _record("skill:geo-audit", current_exposure=("claude", "codex")),
    ]
    draft = draft_capability_policy(
        records,
        policy_path=policy_path,
        action="keep_only_in_client",
        capability_ids=["skill:geo-audit"],
        params={"target_client": "claude"},
    )

    result = apply_capability_policy_draft(policy_path=policy_path, draft=draft)

    written_text = policy_path.read_text(encoding="utf-8")
    assert result == {
        "ok": True,
        "policy_hash": policy_content_hash(written_text),
        "applied_capabilities": ["skill:geo-audit"],
    }
    assert yaml.safe_load(policy_path.read_text(encoding="utf-8")) == {
        "capabilities": draft["entries"],
        "version": 1,
    }


def test_apply_rejects_stale_draft_after_policy_file_changes(tmp_path: Path) -> None:
    policy_path = tmp_path / "capability_exposure.yaml"
    records = [_record("skill:geo-audit", current_exposure=("claude", "codex"))]
    draft = draft_capability_policy(
        records,
        policy_path=policy_path,
        action="keep_only_in_client",
        capability_ids=["skill:geo-audit"],
        params={"target_client": "claude"},
    )
    policy_path.write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "capabilities": {
                    "skill:other": {
                        "classification_status": "approved",
                        "export_to": ["codex"],
                    }
                },
            },
            sort_keys=True,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(CapabilityPolicyError, match="stale draft:"):
        apply_capability_policy_draft(policy_path=policy_path, draft=draft)


def test_apply_rejects_tampered_draft_entries_and_leaves_policy_unchanged(
    tmp_path: Path,
) -> None:
    policy_path = tmp_path / "capability_exposure.yaml"
    records = [_record("skill:geo-audit", current_exposure=("claude", "codex"))]
    draft = draft_capability_policy(
        records,
        policy_path=policy_path,
        action="keep_only_in_client",
        capability_ids=["skill:geo-audit"],
        params={"target_client": "claude"},
    )
    initial_text = policy_path.read_text(encoding="utf-8") if policy_path.exists() else ""
    draft["entries"]["skill:geo-audit"]["export_to"] = ["gemini"]

    with pytest.raises(CapabilityPolicyError, match="draft fingerprint mismatch"):
        apply_capability_policy_draft(policy_path=policy_path, draft=draft)

    if initial_text:
        assert policy_path.read_text(encoding="utf-8") == initial_text
    else:
        assert not policy_path.exists()


def test_apply_rejects_entries_that_do_not_match_draft_capability_ids(
    tmp_path: Path,
) -> None:
    policy_path = tmp_path / "capability_exposure.yaml"
    records = [_record("skill:geo-audit", current_exposure=("claude", "codex"))]
    draft = draft_capability_policy(
        records,
        policy_path=policy_path,
        action="keep_only_in_client",
        capability_ids=["skill:geo-audit"],
        params={"target_client": "claude"},
    )
    draft["entries"]["skill:other"] = draft["entries"].pop("skill:geo-audit")

    with pytest.raises(CapabilityPolicyError, match="draft entries must match"):
        apply_capability_policy_draft(policy_path=policy_path, draft=draft)

    assert not policy_path.exists()


def test_apply_rejects_malformed_entry_and_leaves_policy_unchanged(
    tmp_path: Path,
) -> None:
    policy_path = tmp_path / "capability_exposure.yaml"
    initial_text = yaml.safe_dump(
        {"version": 1, "capabilities": {}},
        sort_keys=True,
        allow_unicode=False,
    )
    policy_path.write_text(initial_text, encoding="utf-8")

    with pytest.raises(CapabilityPolicyError, match="draft entry must be a mapping"):
        apply_capability_policy_draft(
            policy_path=policy_path,
            draft={
                "base_hash": policy_content_hash(initial_text),
                "action": "keep_only_in_client",
                "capability_ids": ["skill:bad"],
                "entries": {"skill:bad": "not-a-mapping"},
            },
        )

    assert policy_path.read_text(encoding="utf-8") == initial_text


def test_apply_rejects_empty_entries(tmp_path: Path) -> None:
    policy_path = tmp_path / "capability_exposure.yaml"
    initial_text = "version: 1\ncapabilities: {}\n"

    with pytest.raises(CapabilityPolicyError, match="draft entries cannot be empty"):
        apply_capability_policy_draft(
            policy_path=policy_path,
            draft={
                "base_hash": policy_content_hash(initial_text),
                "action": "keep_only_in_client",
                "capability_ids": ["skill:bad"],
                "entries": {},
            },
        )


def test_compute_impact_preview_command_lists_existing_client_files(tmp_path):
    """ADR-734 C6.5: preview reports the command files that would be removed."""
    from src.lib.capabilities.policy_editor import compute_impact_preview

    for client in (".claude", ".codex", ".gemini"):
        cmd_dir = tmp_path / client / "commands"
        cmd_dir.mkdir(parents=True)
        (cmd_dir / "doomed.md").write_text("x", encoding="utf-8")

    preview = compute_impact_preview(
        project_root=tmp_path,
        capability_id="command:doomed",
        action="move_to_cli_only",
    )

    assert preview["would_remove"] == [
        ".claude/commands/doomed.md",
        ".codex/commands/doomed.md",
        ".gemini/commands/doomed.md",
    ]


def test_compute_impact_preview_skill_lists_existing_client_dirs(tmp_path):
    from src.lib.capabilities.policy_editor import compute_impact_preview

    skill_dir = tmp_path / ".gemini" / "skills" / "victim"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("x", encoding="utf-8")

    preview = compute_impact_preview(
        project_root=tmp_path,
        capability_id="skill:victim",
        action="block_from_gemini",
    )

    assert preview["would_remove"] == [".gemini/skills/victim"]


def test_compute_impact_preview_quiet_for_non_destructive_actions(tmp_path):
    from src.lib.capabilities.policy_editor import compute_impact_preview

    (tmp_path / ".claude" / "skills" / "foo").mkdir(parents=True)
    preview = compute_impact_preview(
        project_root=tmp_path,
        capability_id="skill:foo",
        action="approve_multi_client",
    )

    assert preview["would_remove"] == []


def test_compute_impact_preview_handles_unknown_capability_type(tmp_path):
    from src.lib.capabilities.policy_editor import compute_impact_preview

    preview = compute_impact_preview(
        project_root=tmp_path,
        capability_id="malformed",
        action="move_to_cli_only",
    )

    assert preview["would_remove"] == []
