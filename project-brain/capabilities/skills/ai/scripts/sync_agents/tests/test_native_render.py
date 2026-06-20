from __future__ import annotations

import sys
from pathlib import Path

scripts_dir = Path(__file__).resolve().parents[2]
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

from sync_agents import standard_skill_projection as ssp


def test_render_carries_allowed_tools() -> None:
    out = ssp._render_client_skill("demo", "Use when demoing.", "# Body",
                                   allowed_tools=["Read", "Bash"])
    assert "name: demo" in out
    assert "description: Use when demoing." in out
    assert "allowed-tools:" in out and "Read" in out and "Bash" in out
    assert "# Body" in out


def test_render_omits_allowed_tools_when_absent() -> None:
    out = ssp._render_client_skill("demo", "Use when demoing.", "# Body")
    assert "allowed-tools" not in out


_RAW = (
    "---\n"
    "name: doc-cleanup\n"
    "x-augur-type: command\n"
    "x-augur-group: life\n"
    "description: Use when cleaning export collateral.\n"
    "allowed-tools: [Read, Bash]\n"
    "---\n\n# Doc Cleanup\nBody.\n"
)


def test_native_render_strips_augur_keeps_native() -> None:
    from sync_agents import skill_sync
    out = skill_sync._render_native_skill_md(_RAW, "doc-cleanup")
    assert "name: doc-cleanup" in out
    assert "description: Use when cleaning export collateral." in out
    assert "allowed-tools" in out and "Read" in out and "Bash" in out
    assert "x-augur-type" not in out and "x-augur-group" not in out
    assert "# Doc Cleanup" in out


def test_native_render_falls_back_to_name_when_frontmatter_missing() -> None:
    from sync_agents import skill_sync
    out = skill_sync._render_native_skill_md("# no frontmatter body\n", "fallback-skill")
    assert "name: fallback-skill" in out
    assert "# no frontmatter body" in out
