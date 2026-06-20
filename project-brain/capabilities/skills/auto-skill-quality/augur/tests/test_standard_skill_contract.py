from __future__ import annotations

import importlib
import sys
from pathlib import Path

PROJECT_ROOT = next(
    (
        p
        for p in Path(__file__).resolve().parents
        if (p / "pyproject.toml").exists() and (p / ".git").exists()
    ),
    Path(__file__).resolve().parents[-1],
)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

mod = importlib.import_module("skills.auto-skill-quality.scripts.standard_skill_contract")
classify_standard_skill_contract = mod.classify_standard_skill_contract
scan_standard_skill_contracts = mod.scan_standard_skill_contracts


def test_standard_bundle_is_ready_without_augur_metadata(tmp_path: Path) -> None:
    root = tmp_path / "email"
    (root / "himalaya").mkdir(parents=True)
    (root / "DESCRIPTION.md").write_text("# Email\n\nStandard email bundle.\n", encoding="utf-8")
    (root / "himalaya" / "SKILL.md").write_text("# Himalaya\n\nUse local himalaya CLI.\n", encoding="utf-8")

    result = classify_standard_skill_contract(root)

    assert result.status == "standard-source-ready"
    assert result.issues == ()


def test_standard_bundle_with_augur_metadata_is_mixed(tmp_path: Path) -> None:
    root = tmp_path / "email"
    (root / "himalaya").mkdir(parents=True)
    (root / "DESCRIPTION.md").write_text("# Email\n\nStandard email bundle.\n", encoding="utf-8")
    (root / "himalaya" / "SKILL.md").write_text("---\nx-augur-hub: workspace\n---\n# Himalaya\n", encoding="utf-8")

    result = classify_standard_skill_contract(root)

    assert result.status == "mixed-needs-split"
    assert "x-augur-" in result.issues[0]


def test_migration_matrix_can_name_rejected_augur_projection_paths(tmp_path: Path) -> None:
    root = tmp_path / "apple"
    (root / "apple-notes").mkdir(parents=True)
    (root / "references").mkdir()
    (root / "DESCRIPTION.md").write_text("# Apple\n\nStandard Apple bundle.\n", encoding="utf-8")
    (root / "apple-notes" / "SKILL.md").write_text("# Apple Notes\n", encoding="utf-8")
    (root / "references" / "migration-matrix.md").write_text(
        "| Source | Target | Decision |\n"
        "|---|---|---|\n"
        "| `scripts/mcp/**` | Augur projection | do not copy |\n",
        encoding="utf-8",
    )

    result = classify_standard_skill_contract(root)

    assert result.status == "standard-source-ready"
    assert result.issues == ()


def test_standard_bundle_with_real_mcp_source_is_mixed(tmp_path: Path) -> None:
    root = tmp_path / "apple"
    (root / "apple-notes").mkdir(parents=True)
    (root / "scripts" / "mcp").mkdir(parents=True)
    (root / "DESCRIPTION.md").write_text("# Apple\n\nStandard Apple bundle.\n", encoding="utf-8")
    (root / "apple-notes" / "SKILL.md").write_text("# Apple Notes\n", encoding="utf-8")
    (root / "scripts" / "mcp" / "tools.py").write_text("def register():\n    return None\n", encoding="utf-8")

    result = classify_standard_skill_contract(root)

    assert result.status == "mixed-needs-split"
    assert any("scripts/mcp/" in issue for issue in result.issues)


def test_standard_bundle_with_augur_python_import_is_mixed(tmp_path: Path) -> None:
    root = tmp_path / "email"
    (root / "himalaya").mkdir(parents=True)
    (root / "scripts").mkdir()
    (root / "DESCRIPTION.md").write_text("# Email\n\nStandard email bundle.\n", encoding="utf-8")
    (root / "himalaya" / "SKILL.md").write_text("# Himalaya\n\nUse local CLI.\n", encoding="utf-8")
    (root / "scripts" / "packets.py").write_text(
        "from src.lib.packet import Packet\n\n"
        "def build() -> Packet:\n"
        "    return Packet()\n",
        encoding="utf-8",
    )

    result = classify_standard_skill_contract(root)

    assert result.status == "mixed-needs-split"
    assert any("import coupling" in issue for issue in result.issues)


def test_standard_bundle_scans_nested_scripts_for_augur_imports(tmp_path: Path) -> None:
    root = tmp_path / "email"
    (root / "himalaya").mkdir(parents=True)
    (root / "scripts" / "sync").mkdir(parents=True)
    (root / "DESCRIPTION.md").write_text("# Email\n\nStandard email bundle.\n", encoding="utf-8")
    (root / "himalaya" / "SKILL.md").write_text("# Himalaya\n\nUse local CLI.\n", encoding="utf-8")
    (root / "scripts" / "sync" / "coupled.py").write_text(
        "from src.config.paths import get_project_root\n\n"
        "ROOT = get_project_root()\n",
        encoding="utf-8",
    )

    result = classify_standard_skill_contract(root)

    assert result.status == "mixed-needs-split"
    assert any("scripts/sync/coupled.py" in issue and "import coupling" in issue for issue in result.issues)


def test_standard_bundle_rejects_projected_skills_imports(tmp_path: Path) -> None:
    root = tmp_path / "vault"
    (root / "markdown").mkdir(parents=True)
    (root / "scripts").mkdir()
    (root / "DESCRIPTION.md").write_text("# Vault\n\nStandard vault bundle.\n", encoding="utf-8")
    (root / "markdown" / "SKILL.md").write_text("# Markdown\n\nUse portable markdown tools.\n", encoding="utf-8")
    (root / "scripts" / "coupled.py").write_text(
        "from skills.vault.scripts.markdown_convert import convert\n",
        encoding="utf-8",
    )

    result = classify_standard_skill_contract(root)

    assert result.status == "mixed-needs-split"
    assert any("skills.vault" in issue and "import coupling" in issue for issue in result.issues)


def test_standard_bundle_rejects_external_llm_provider_imports(tmp_path: Path) -> None:
    for name, source in (
        ("openai_module", "import openai\nclient = openai.OpenAI()\n"),
        ("openai_class", "from openai import OpenAI\nclient = OpenAI()\n"),
        ("anthropic_module", "import anthropic\nclient = anthropic.Anthropic()\n"),
        ("gemini_module", "import google.generativeai\n"),
        ("gemini_from_google", "from google import generativeai\n"),
    ):
        root = tmp_path / name
        (root / "himalaya").mkdir(parents=True)
        (root / "scripts").mkdir()
        (root / "DESCRIPTION.md").write_text("# Email\n\nStandard email bundle.\n", encoding="utf-8")
        (root / "himalaya" / "SKILL.md").write_text("# Himalaya\n\nUse local CLI.\n", encoding="utf-8")
        (root / "scripts" / "model.py").write_text(source, encoding="utf-8")

        result = classify_standard_skill_contract(root)

        assert result.status == "mixed-needs-split"
        assert any("external LLM provider import" in issue for issue in result.issues)


def test_standard_bundle_scans_shell_scripts_for_hardcoded_augur_paths(tmp_path: Path) -> None:
    root = tmp_path / "email"
    (root / "himalaya").mkdir(parents=True)
    (root / "scripts").mkdir()
    (root / "DESCRIPTION.md").write_text("# Email\n\nStandard email bundle.\n", encoding="utf-8")
    (root / "himalaya" / "SKILL.md").write_text("# Himalaya\n\nUse local CLI.\n", encoding="utf-8")
    (root / "scripts" / "check.sh").write_text(
        "#!/bin/sh\nAUGUR_ROOT=/Users/testuser/Projects/Augur\n",
        encoding="utf-8",
    )

    result = classify_standard_skill_contract(root)

    assert result.status == "mixed-needs-split"
    assert any("scripts/check.sh" in issue and "hardcoded Augur path" in issue for issue in result.issues)


def test_standard_bundle_scans_swift_scripts_for_hardcoded_augur_paths(tmp_path: Path) -> None:
    root = tmp_path / "apple"
    (root / "apple-notes").mkdir(parents=True)
    (root / "scripts").mkdir()
    (root / "DESCRIPTION.md").write_text("# Apple\n\nStandard Apple bundle.\n", encoding="utf-8")
    (root / "apple-notes" / "SKILL.md").write_text("# Apple Notes\n", encoding="utf-8")
    (root / "scripts" / "apple.swift").write_text(
        'let logPath = "/Users/testuser/Library/Logs/Augur/apple.log"\n',
        encoding="utf-8",
    )

    result = classify_standard_skill_contract(root)

    assert result.status == "mixed-needs-split"
    assert any("scripts/apple.swift" in issue and "hardcoded Augur path" in issue for issue in result.issues)


def test_standard_bundle_scans_tests_for_augur_imports(tmp_path: Path) -> None:
    root = tmp_path / "email"
    (root / "himalaya").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "DESCRIPTION.md").write_text("# Email\n\nStandard email bundle.\n", encoding="utf-8")
    (root / "himalaya" / "SKILL.md").write_text("# Himalaya\n\nUse local CLI.\n", encoding="utf-8")
    (root / "tests" / "test_coupled.py").write_text(
        "from src.config.paths import get_project_root\n\n"
        "def test_root() -> None:\n"
        "    assert get_project_root()\n",
        encoding="utf-8",
    )

    result = classify_standard_skill_contract(root)

    assert result.status == "mixed-needs-split"
    assert any("tests/test_coupled.py" in issue and "import coupling" in issue for issue in result.issues)


def test_standard_bundle_with_hardcoded_project_or_vault_path_is_mixed(tmp_path: Path) -> None:
    for path_text in (
        "/Users/testuser/Projects/Augur",
        "/Users/testuser/Projects/Au-vault",
    ):
        root = tmp_path / path_text.rsplit("/", maxsplit=1)[-1]
        (root / "himalaya").mkdir(parents=True)
        (root / "scripts").mkdir()
        (root / "DESCRIPTION.md").write_text("# Email\n\nStandard email bundle.\n", encoding="utf-8")
        (root / "himalaya" / "SKILL.md").write_text("# Himalaya\n\nUse local CLI.\n", encoding="utf-8")
        (root / "scripts" / "paths.py").write_text(
            f'DEFAULT_ROOT = "{path_text}"\n',
            encoding="utf-8",
        )

        result = classify_standard_skill_contract(root)

        assert result.status == "mixed-needs-split"
        assert any("hardcoded Augur path" in issue for issue in result.issues)


def test_standard_bundle_with_hardcoded_runtime_log_or_cache_path_is_mixed(tmp_path: Path) -> None:
    for name, path_text in (
        ("runtime", "/Users/testuser/Library/Application Support/Augur"),
        ("logs", "/Users/testuser/Library/Logs/Augur"),
        ("cache", "/Users/testuser/Library/Caches/Augur"),
    ):
        root = tmp_path / name
        (root / "himalaya").mkdir(parents=True)
        (root / "DESCRIPTION.md").write_text("# Email\n\nStandard email bundle.\n", encoding="utf-8")
        (root / "himalaya" / "SKILL.md").write_text(
            f"# Himalaya\n\nDo not write into `{path_text}`.\n",
            encoding="utf-8",
        )

        result = classify_standard_skill_contract(root)

        assert result.status == "mixed-needs-split"
        assert any("hardcoded Augur path" in issue for issue in result.issues)


def test_augur_skill_without_standard_bundle_is_platform_skill(tmp_path: Path) -> None:
    root = tmp_path / "ingest"
    root.mkdir()
    (root / "SKILL.md").write_text("---\nx-augur-type: domain\n---\n# Ingest\n", encoding="utf-8")

    result = classify_standard_skill_contract(root)

    assert result.status == "augur-platform-skill"


def test_root_only_portable_skill_needs_projection_adapter(tmp_path: Path) -> None:
    root = tmp_path / "portable"
    root.mkdir()
    (root / "SKILL.md").write_text("# Portable\n\nUse this with any agent.\n", encoding="utf-8")

    result = classify_standard_skill_contract(root)

    assert result.status == "needs-projection-adapter"
    assert result.issues == ("no DESCRIPTION.md plus subskill SKILL.md bundle found",)


def test_scan_realistic_roots_reports_each_skill(tmp_path: Path) -> None:
    skills = tmp_path / "skills"
    (skills / "email" / "himalaya").mkdir(parents=True)
    (skills / "note-taking" / "obsidian").mkdir(parents=True)
    (skills / "email" / "DESCRIPTION.md").write_text("# Email\n\nStandard email.\n", encoding="utf-8")
    (skills / "email" / "himalaya" / "SKILL.md").write_text("# Himalaya\n\nUse CLI.\n", encoding="utf-8")
    (skills / "note-taking" / "DESCRIPTION.md").write_text("# Note Taking\n\nStandard notes.\n", encoding="utf-8")
    (skills / "note-taking" / "obsidian" / "SKILL.md").write_text("# Obsidian\n\nUse local vault.\n", encoding="utf-8")

    report = scan_standard_skill_contracts([skills])

    by_name = {item.name: item for item in report}
    assert set(by_name) == {"email", "note-taking"}
    assert by_name["email"].status == "standard-source-ready"
    assert by_name["note-taking"].status == "standard-source-ready"


def test_books_and_file_manager_standard_fixtures_are_ready(tmp_path: Path) -> None:
    books = tmp_path / "books"
    (books / "reading-library").mkdir(parents=True)
    (books / "reading-list").mkdir()
    (books / "DESCRIPTION.md").write_text("# Books\n\nStandard reading workflows.\n", encoding="utf-8")
    (books / "reading-library" / "SKILL.md").write_text(
        "# Reading Library\n\nUse local book metadata and notes.\n",
        encoding="utf-8",
    )
    (books / "reading-list" / "SKILL.md").write_text(
        "# Reading List\n\nUse local saved article lists.\n",
        encoding="utf-8",
    )
    file_manager = tmp_path / "file-manager"
    (file_manager / "local-file-organization").mkdir(parents=True)
    (file_manager / "DESCRIPTION.md").write_text(
        "# File Manager\n\nStandard file organization workflow.\n",
        encoding="utf-8",
    )
    (file_manager / "local-file-organization" / "SKILL.md").write_text(
        "# Local File Organization\n\nUse local file triage rules.\n",
        encoding="utf-8",
    )

    assert classify_standard_skill_contract(books).status == "standard-source-ready"
    assert classify_standard_skill_contract(file_manager).status == "standard-source-ready"


def test_books_and_file_manager_adapter_fixtures_are_mixed(tmp_path: Path) -> None:
    books = tmp_path / "books"
    (books / "reading-library").mkdir(parents=True)
    (books / "scripts" / "mcp").mkdir(parents=True)
    (books / "DESCRIPTION.md").write_text("# Books\n\nStandard reading workflows.\n", encoding="utf-8")
    (books / "reading-library" / "SKILL.md").write_text("# Reading Library\n", encoding="utf-8")

    file_manager = tmp_path / "file-manager"
    (file_manager / "local-file-organization").mkdir(parents=True)
    (file_manager / "augur").mkdir()
    (file_manager / "DESCRIPTION.md").write_text("# File Manager\n\nStandard files.\n", encoding="utf-8")
    (file_manager / "local-file-organization" / "SKILL.md").write_text(
        "# Local File Organization\n",
        encoding="utf-8",
    )

    books_result = classify_standard_skill_contract(books)
    file_manager_result = classify_standard_skill_contract(file_manager)

    assert books_result.status == "mixed-needs-split"
    assert any("scripts/mcp/" in issue for issue in books_result.issues)
    assert file_manager_result.status == "mixed-needs-split"
    assert any("augur/" in issue for issue in file_manager_result.issues)


def test_full_migration_report_deduplicates_physical_roots(tmp_path: Path) -> None:
    root = tmp_path / "brain" / "capabilities" / "skills"
    (root / "apple" / "apple-notes").mkdir(parents=True)
    (root / "apple" / "DESCRIPTION.md").write_text("# Apple\n\nStandard.\n", encoding="utf-8")
    (root / "apple" / "apple-notes" / "SKILL.md").write_text("# Apple Notes\n", encoding="utf-8")

    report = mod.build_full_migration_report(
        [
            mod.SkillRootRole("global", "augur-core", root),
            mod.SkillRootRole("project", "project-augur", root),
        ]
    )

    assert len(report.physical_roots) == 1
    assert [item.name for item in report.skills] == ["apple"]
    assert report.skills[0].roles == ("global:augur-core", "project:project-augur")


def test_full_migration_report_marks_platform_only_decisions(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    skill = root / "daemon"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nx-augur-type: platform\n---\n# Daemon\n", encoding="utf-8")

    report = mod.build_full_migration_report([mod.SkillRootRole("global", "augur-core", root)])
    item = report.skills[0]

    assert item.name == "daemon"
    assert item.status == "augur-platform-skill"
    assert item.recommended_action == "keep-platform"


def test_full_migration_gate_fails_scoped_mixed_skill(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    books = root / "books"
    (books / "reading-list").mkdir(parents=True)
    (books / "scripts" / "mcp").mkdir(parents=True)
    (books / "DESCRIPTION.md").write_text("# Books\n\nPortable reading.\n", encoding="utf-8")
    (books / "SKILL.md").write_text("---\nx-augur-type: domain\n---\n# Books Adapter\n", encoding="utf-8")
    (books / "reading-list" / "SKILL.md").write_text("# Reading List\n", encoding="utf-8")
    (books / "scripts" / "mcp" / "__init__.py").write_text("from src.config.paths import get_vault_dir\n", encoding="utf-8")
    for name in ("audio-ingest", "document-extractor", "dream", "evals", "file-manager", "graph"):
        skill = root / name
        skill.mkdir(parents=True)
        skill_name = name.replace("-", " ").title()
        (skill / "SKILL.md").write_text(f"---\nx-augur-type: platform\n---\n# {skill_name}\n", encoding="utf-8")

    report = mod.build_full_migration_report([mod.SkillRootRole("user", "personal", root)])
    gate = mod.evaluate_full_migration_gate(report)

    assert gate.ok is False
    assert gate.blocked == ("books",)
    assert "books remains mixed-needs-split" in gate.issues[0]


def test_full_migration_gate_fails_duplicate_scoped_mixed_row(tmp_path: Path) -> None:
    mixed_root = tmp_path / "a-mixed" / "skills"
    accepted_root = tmp_path / "z-accepted" / "skills"
    mixed_books = mixed_root / "books"
    accepted_books = accepted_root / "books"
    (mixed_books / "reading-list").mkdir(parents=True)
    (mixed_books / "scripts" / "mcp").mkdir(parents=True)
    (mixed_books / "DESCRIPTION.md").write_text("# Books\n\nPortable reading.\n", encoding="utf-8")
    (mixed_books / "reading-list" / "SKILL.md").write_text("# Reading List\n", encoding="utf-8")
    (mixed_books / "scripts" / "mcp" / "__init__.py").write_text(
        "from src.config.paths import get_vault_dir\n",
        encoding="utf-8",
    )
    accepted_books.mkdir(parents=True)
    (accepted_books / "SKILL.md").write_text("---\nx-augur-type: platform\n---\n# Books Adapter\n", encoding="utf-8")
    for name in ("audio-ingest", "document-extractor", "dream", "evals", "file-manager", "graph"):
        skill = accepted_root / name
        skill.mkdir(parents=True)
        skill_name = name.replace("-", " ").title()
        (skill / "SKILL.md").write_text(f"---\nx-augur-type: platform\n---\n# {skill_name}\n", encoding="utf-8")

    report = mod.build_full_migration_report(
        [
            mod.SkillRootRole("global", "augur-core", mixed_root),
            mod.SkillRootRole("user", "personal", accepted_root),
        ]
    )
    gate = mod.evaluate_full_migration_gate(report)

    assert gate.ok is False
    assert gate.blocked == ("books",)
    assert any("books remains mixed-needs-split" in issue for issue in gate.issues)
    assert any(mixed_books.as_posix() in issue for issue in gate.issues)


def test_full_migration_gate_passes_when_scoped_names_are_accepted(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    for name in ("audio-ingest", "books", "document-extractor", "dream", "evals", "file-manager", "graph"):
        skill = root / name
        skill.mkdir(parents=True)
        skill_name = name.replace("-", " ").title()
        (skill / "SKILL.md").write_text(f"---\nx-augur-type: platform\n---\n# {skill_name}\n", encoding="utf-8")

    report = mod.build_full_migration_report([mod.SkillRootRole("user", "personal", root)])
    gate = mod.evaluate_full_migration_gate(report)

    assert gate.ok is True
    assert gate.blocked == ()
    assert gate.issues == ()


def test_is_standard_core_detects_bundle_core(tmp_path):
    is_standard_core = mod.is_standard_core

    # A standard bundle: parent has DESCRIPTION.md, core dir has SKILL.md
    bundle = tmp_path / "recurring-reflection"
    core = bundle / "dream-routine"
    core.mkdir(parents=True)
    (bundle / "DESCRIPTION.md").write_text("# Recurring Reflection\n", encoding="utf-8")
    (core / "SKILL.md").write_text("---\nname: dream-routine\n---\n", encoding="utf-8")
    assert is_standard_core(core) is True

    # A flat Augur skill (no parent DESCRIPTION.md) is NOT a core
    flat = tmp_path / "dream"
    flat.mkdir()
    (flat / "SKILL.md").write_text("---\nname: dream\nx-augur-type: skill\n---\n", encoding="utf-8")
    assert is_standard_core(flat) is False

    # The bundle root itself (has DESCRIPTION.md but its own SKILL.md absent) is NOT a core dir
    assert is_standard_core(bundle) is False
