"""Contract tests for the adopted advisor skill.

The advisor port shipped zero scripts by design (judgment procedures +
methodology references only), so these tests guard the adoption contract:
ADR-805 native-first frontmatter, ADR-802 retired-field absence, command
integrity (ADR-813), reference integrity, and the no-machinery guarantee.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

SKILL_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[6]

RETIRED_FIELDS = (
    "x-augur-hub",
    "x-augur-tab",
    "x-augur-group",
    "x-augur-release",
    "x-augur-mcp-tools",
    "x-augur-dashboard-pages",
    "x-augur-config",
    "x-augur-env",
    "x-augur-data-dir",
    "x-augur-requires-platform",
    "x-augur-dependencies",
)


def _load_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path.name} must start with frontmatter at line 1"
    closing = text.index("\n---", 4)
    return yaml.safe_load(text[4:closing])


class TestSkillMd:
    def test_frontmatter_parses_and_names_advisor(self):
        fm = _load_frontmatter(SKILL_DIR / "SKILL.md")
        assert fm["name"] == "advisor"
        assert fm["x-augur-type"] == "skill"
        assert fm["x-augur-license"] == "MIT"

    def test_retired_adr802_fields_absent(self):
        fm = _load_frontmatter(SKILL_DIR / "SKILL.md")
        present = [field for field in RETIRED_FIELDS if field in fm]
        assert present == [], f"retired frontmatter fields present: {present}"

    def test_description_states_unique_ownership(self):
        fm = _load_frontmatter(SKILL_DIR / "SKILL.md")
        desc = fm["description"]
        for marker in ("architecture", "prompt", "drift"):
            assert marker in desc.lower(), f"description missing '{marker}'"

    def test_body_declares_collision_boundaries(self):
        body = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        for owner in ("evals", "auto-skill-quality", "routine-coverage", "knowledge", "skillify"):
            assert owner in body, f"SKILL.md body missing boundary for '{owner}'"

    def test_declared_commands_exist(self):
        fm = _load_frontmatter(SKILL_DIR / "SKILL.md")
        ids = [c["id"] for c in fm["x-augur-commands"]]
        assert sorted(ids) == ["advisor-architecture", "advisor-prompt-optimize"]
        for cid in ids:
            assert (SKILL_DIR / "commands" / f"{cid}.md").is_file()


class TestCommands:
    def test_command_frontmatter_shape(self):
        for cmd in sorted((SKILL_DIR / "commands").glob("*.md")):
            fm = _load_frontmatter(cmd)
            assert fm["name"] == cmd.stem
            assert "Usage:" in fm["description"]
            assert fm["visibility"] == "dev"

    def test_commands_honor_help_stop_contract(self):
        # CLAUDE.md rule 15: --help displays usage and stops execution.
        for cmd in sorted((SKILL_DIR / "commands").glob("*.md")):
            body = cmd.read_text(encoding="utf-8")
            assert "--help" in body and "stop" in body.lower(), cmd.name

    def test_commands_reference_only_existing_files(self):
        pattern = re.compile(r"`(project-brain/[^`]+\.md)`|`(references/[^`]+\.md)`")
        for cmd in sorted((SKILL_DIR / "commands").glob("*.md")):
            for match in pattern.finditer(cmd.read_text(encoding="utf-8")):
                repo_rel, skill_rel = match.groups()
                target = REPO_ROOT / repo_rel if repo_rel else SKILL_DIR / skill_rel
                assert target.is_file(), f"{cmd.name} references missing file: {target}"


class TestReferences:
    PORTED = [
        "codebase-exploration.md",
        "blueprint-template.md",
        "prompt-optimization.md",
        "ab-testing-framework.md",
        "vision-framework.md",
        "alignment-scoring.md",
        "drift-detection.md",
    ]
    EXCLUDED = [
        "workflows.md",
        "analyst-workflow.md",
        "analyst-operating-guide.md",
        "architect-workflow.md",
        "architecture-workflow.md",
        "analytics-patterns.md",
        "integration-patterns.md",
        "pipeline-integration.md",
    ]

    def test_ported_references_exist_and_are_nonempty(self):
        for name in self.PORTED:
            ref = SKILL_DIR / "references" / name
            assert ref.is_file() and ref.stat().st_size > 200, name

    def test_excluded_references_stayed_excluded(self):
        for name in self.EXCLUDED:
            assert not (SKILL_DIR / "references" / name).exists(), name

    def test_skill_md_reference_table_resolves(self):
        body = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        for rel in re.findall(r"`references/([^`]+\.md)`", body):
            assert (SKILL_DIR / "references" / rel).is_file(), rel


class TestNoMachinery:
    def test_no_scripts_or_mcp_modules_shipped(self):
        # The port deliberately shipped zero scripts and zero MCP tools;
        # re-adding machinery requires a fresh security review + tests.
        assert not (SKILL_DIR / "scripts").exists()
        py_files = [
            p
            for p in SKILL_DIR.rglob("*.py")
            if "augur/tests" not in str(p.relative_to(SKILL_DIR)).replace("\\", "/")
        ]
        assert py_files == [], f"unexpected python files: {py_files}"

    def test_capability_exposure_routes_advisor_as_skill(self):
        text = (REPO_ROOT / "config" / "system" / "capability_exposure.yaml").read_text(encoding="utf-8")
        policies = yaml.safe_load(text)
        entry = policies["capabilities"]["skill:advisor"]
        assert entry["primary_surface"] == "skill"
        assert "mcp" not in entry.get("export_to", [])
