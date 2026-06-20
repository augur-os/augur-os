from __future__ import annotations

from pathlib import Path

import yaml

from src.lib.index.agent_profiles import (
    DEFAULT_MASTER_CLIENT,
    agent_projection_metadata,
    load_agent_model_mapping,
    resolve_agent_model_tier,
)


def _write_mapping(root: Path, data: dict) -> None:
    mapping_path = root / "config" / "agents" / "model_mapping.yaml"
    mapping_path.parent.mkdir(parents=True, exist_ok=True)
    mapping_path.write_text(yaml.safe_dump(data), encoding="utf-8")


# --- load_agent_model_mapping ------------------------------------------------


def test_load_agent_model_mapping_missing_file_returns_empty(tmp_path):
    result = load_agent_model_mapping(tmp_path)
    assert result == {"tiers": {}, "reverse_lookup": {}}


def test_load_agent_model_mapping_reads_tiers_and_reverse_lookup(tmp_path):
    _write_mapping(
        tmp_path,
        {
            "tiers": {
                "premium": {"clients": {"claude-code": "opus", "gemini": "pro"}},
            },
            "reverse_lookup": {"opus": "premium", "pro": "premium"},
        },
    )

    result = load_agent_model_mapping(tmp_path)

    assert result["tiers"]["premium"]["clients"]["claude-code"] == "opus"
    assert result["reverse_lookup"]["opus"] == "premium"


def test_load_agent_model_mapping_invalid_yaml_returns_empty(tmp_path):
    mapping_path = tmp_path / "config" / "agents" / "model_mapping.yaml"
    mapping_path.parent.mkdir(parents=True, exist_ok=True)
    # Unbalanced/invalid YAML that raises during parse.
    mapping_path.write_text("tiers: [unclosed\n: : :", encoding="utf-8")

    assert load_agent_model_mapping(tmp_path) == {"tiers": {}, "reverse_lookup": {}}


def test_load_agent_model_mapping_non_dict_root_returns_empty(tmp_path):
    mapping_path = tmp_path / "config" / "agents" / "model_mapping.yaml"
    mapping_path.parent.mkdir(parents=True, exist_ok=True)
    mapping_path.write_text("- just\n- a\n- list", encoding="utf-8")

    assert load_agent_model_mapping(tmp_path) == {"tiers": {}, "reverse_lookup": {}}


def test_load_agent_model_mapping_coerces_non_dict_sections(tmp_path):
    _write_mapping(
        tmp_path,
        {"tiers": ["not", "a", "dict"], "reverse_lookup": "nope"},
    )

    result = load_agent_model_mapping(tmp_path)

    assert result == {"tiers": {}, "reverse_lookup": {}}


# --- resolve_agent_model_tier ------------------------------------------------


def test_resolve_agent_model_tier_empty_model_returns_empty():
    assert resolve_agent_model_tier({"tiers": {}, "reverse_lookup": {}}, "claude-code", "") == ""


def test_resolve_agent_model_tier_uses_reverse_lookup_first():
    mapping = {
        "reverse_lookup": {"opus": "premium"},
        "tiers": {"standard": {"clients": {"claude-code": "opus"}}},
    }
    # reverse_lookup wins even though tiers also maps the model.
    assert resolve_agent_model_tier(mapping, "claude-code", "opus") == "premium"


def test_resolve_agent_model_tier_matches_client_in_tier():
    mapping = {
        "reverse_lookup": {},
        "tiers": {
            "premium": {"clients": {"claude-code": "opus", "gemini": "pro"}},
            "fast": {"clients": {"claude-code": "haiku"}},
        },
    }
    assert resolve_agent_model_tier(mapping, "gemini", "pro") == "premium"
    assert resolve_agent_model_tier(mapping, "claude-code", "haiku") == "fast"


def test_resolve_agent_model_tier_client_model_mismatch_falls_back_to_standard():
    mapping = {
        "reverse_lookup": {},
        "tiers": {"premium": {"clients": {"claude-code": "opus"}}},
    }
    # Same model but wrong client -> no match -> default "standard".
    assert resolve_agent_model_tier(mapping, "gemini", "opus") == "standard"


def test_resolve_agent_model_tier_unknown_model_returns_standard():
    mapping = {"reverse_lookup": {}, "tiers": {}}
    assert resolve_agent_model_tier(mapping, "claude-code", "mystery") == "standard"


def test_resolve_agent_model_tier_skips_malformed_tier_entries():
    mapping = {
        "reverse_lookup": {},
        "tiers": {
            "broken": ["not", "a", "dict"],
            "premium": {"clients": {"claude-code": "opus"}},
        },
    }
    assert resolve_agent_model_tier(mapping, "claude-code", "opus") == "premium"


# --- agent_projection_metadata -----------------------------------------------


def test_agent_projection_metadata_defaults_when_no_mapping(tmp_path):
    metadata = agent_projection_metadata(
        tmp_path,
        name="researcher",
        frontmatter={},
    )
    # No mapping file, no frontmatter -> only the default master client.
    assert metadata == {"master_client": DEFAULT_MASTER_CLIENT}


def test_agent_projection_metadata_includes_source_model_and_tier(tmp_path):
    _write_mapping(
        tmp_path,
        {
            "reverse_lookup": {"opus": "premium"},
            "tiers": {"premium": {"clients": {"claude-code": "opus"}}},
        },
    )

    metadata = agent_projection_metadata(
        tmp_path,
        name="researcher",
        frontmatter={"model": "opus"},
    )

    assert metadata["master_client"] == "claude-code"
    assert metadata["source_model"] == "opus"
    assert metadata["source_tier"] == "premium"


def test_agent_projection_metadata_master_client_precedence(tmp_path):
    # x-augur-master takes precedence over master_client.
    metadata = agent_projection_metadata(
        tmp_path,
        name="agent",
        frontmatter={"x-augur-master": "gemini", "master_client": "codex"},
    )
    assert metadata["master_client"] == "gemini"


def test_agent_projection_metadata_master_client_fallback_to_master_client_key(tmp_path):
    metadata = agent_projection_metadata(
        tmp_path,
        name="agent",
        frontmatter={"master_client": "codex"},
    )
    assert metadata["master_client"] == "codex"


def test_agent_projection_metadata_source_model_fallback_to_default_model(tmp_path):
    metadata = agent_projection_metadata(
        tmp_path,
        name="agent",
        frontmatter={"default_model": "sonnet"},
    )
    assert metadata["source_model"] == "sonnet"


def test_agent_projection_metadata_projects_clients_with_paths_and_sync_status(tmp_path):
    _write_mapping(
        tmp_path,
        {
            "reverse_lookup": {"opus": "premium"},
            "tiers": {
                "premium": {
                    "clients": {"claude-code": "opus", "gemini": "gemini-pro"},
                },
            },
        },
    )
    # Create the claude-code profile on disk so it is "synced"; gemini missing.
    profile = tmp_path / ".claude" / "agents" / "researcher.md"
    profile.parent.mkdir(parents=True, exist_ok=True)
    profile.write_text("# researcher", encoding="utf-8")

    metadata = agent_projection_metadata(
        tmp_path,
        name="researcher",
        frontmatter={"model": "opus"},
    )

    # projection_clients lists every client in the resolved tier.
    assert set(metadata["projection_clients"].split(",")) == {"claude-code", "gemini"}

    assert metadata["claude_code_model"] == "opus"
    assert metadata["claude_code_profile_path"] == ".claude/agents/researcher.md"
    assert metadata["claude_code_sync_status"] == "synced"

    assert metadata["gemini_model"] == "gemini-pro"
    assert metadata["gemini_profile_path"] == ".antigravity/agents/researcher.md"
    assert metadata["gemini_sync_status"] == "missing"


def test_agent_projection_metadata_unknown_client_dir_skips_path_keys(tmp_path):
    _write_mapping(
        tmp_path,
        {
            "reverse_lookup": {"x-model": "premium"},
            "tiers": {"premium": {"clients": {"mystery-client": "x-model"}}},
        },
    )

    metadata = agent_projection_metadata(
        tmp_path,
        name="agent",
        frontmatter={"model": "x-model"},
    )

    # Model key is always emitted; path/sync keys only for known client dirs.
    assert metadata["mystery_client_model"] == "x-model"
    assert "mystery_client_profile_path" not in metadata
    assert "mystery_client_sync_status" not in metadata


def test_agent_projection_metadata_metadata_key_normalization(tmp_path):
    # Client names with punctuation/case are normalized into metadata keys.
    _write_mapping(
        tmp_path,
        {
            "reverse_lookup": {"m": "premium"},
            "tiers": {"premium": {"clients": {"Claude.Code-2": "m"}}},
        },
    )

    metadata = agent_projection_metadata(
        tmp_path,
        name="agent",
        frontmatter={"model": "m"},
    )

    assert metadata["claude_code_2_model"] == "m"


def test_agent_projection_metadata_drops_blank_client_or_model_entries(tmp_path):
    _write_mapping(
        tmp_path,
        {
            "reverse_lookup": {"opus": "premium"},
            "tiers": {
                "premium": {
                    "clients": {
                        "claude-code": "opus",
                        "": "ghost",  # blank client dropped
                        "empty-model": "",  # blank model dropped
                    },
                },
            },
        },
    )

    metadata = agent_projection_metadata(
        tmp_path,
        name="agent",
        frontmatter={"model": "opus"},
    )

    assert metadata["projection_clients"] == "claude-code"
    assert "empty_model_model" not in metadata
