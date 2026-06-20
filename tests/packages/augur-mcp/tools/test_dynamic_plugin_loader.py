import asyncio
from pathlib import Path
import sys
from unittest.mock import MagicMock

import pytest


def _write_skill(skill_dir: Path, *, hub: str, mcp_init_body: str) -> None:
    (skill_dir / "scripts" / "mcp").mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {skill_dir.name}\nx-augur-hub: {hub}\n---\n",
        encoding="utf-8",
    )
    (skill_dir / "scripts" / "__init__.py").write_text("", encoding="utf-8")
    (skill_dir / "scripts" / "mcp" / "__init__.py").write_text(
        mcp_init_body,
        encoding="utf-8",
    )


class FakeMCP:
    def __init__(self) -> None:
        self.tools = {}

    def tool(self, name=None, annotations=None):
        def decorator(func):
            self.tools[name or func.__name__] = func
            return func

        return decorator


@pytest.fixture(autouse=True)
def _isolate_scripts_namespace():
    """Restore the global ``scripts`` package after tests that pop it.

    Several tests below remove ``scripts``/``scripts.*`` from ``sys.modules``
    (and reorder ``sys.path``) to exercise the bundle loader as if no global
    ``scripts`` package existed. Without restoration the real repo-root
    ``scripts`` package stays torn down; later tests re-import ``scripts`` and
    resolve it to the empty ``src/scripts`` package, which lacks
    ``configure_mcp`` and breaks unrelated suites (e.g. configure_mcp tests).
    """
    saved_modules = {
        name: module for name, module in sys.modules.items() if name == "scripts" or name.startswith("scripts.")
    }
    saved_path = list(sys.path)
    try:
        yield
    finally:
        for name in [name for name in sys.modules if name == "scripts" or name.startswith("scripts.")]:
            del sys.modules[name]
        sys.modules.update(saved_modules)
        sys.path[:] = saved_path


def test_loader_filters_registered_tools_through_capability_policy(
    tmp_path,
    monkeypatch,
):
    skill = tmp_path / "skills" / "policy-skill"
    _write_skill(
        skill,
        hub="dev",
        mcp_init_body=(
            "def register_tools(mcp, interceptor, metrics):\n"
            "    @mcp.tool(name='allowed-tool')\n"
            "    def allowed_tool():\n"
            "        return 'allowed'\n\n"
            "    @mcp.tool(name='blocked-tool')\n"
            "    def blocked_tool():\n"
            "        return 'blocked'\n"
        ),
    )

    from src.mcp.augur_shared import plugin_tools

    monkeypatch.setattr(
        plugin_tools,
        "_collect_skill_dirs",
        lambda **_kwargs: [("dev/policy-skill", skill)],
    )
    monkeypatch.setattr(plugin_tools, "is_skill_enabled", lambda _: True)
    monkeypatch.setattr(
        plugin_tools,
        "allowed_mcp_runtime_tool_names",
        lambda names, target="mcp": {"allowed-tool"},
        raising=False,
    )

    plugin_tools.reset_plugin_registry()
    mcp = FakeMCP()

    loaded = plugin_tools.register_plugin_tools(mcp, lambda f: f, MagicMock())

    assert loaded == 1
    assert set(mcp.tools) == {"allowed-tool"}


def test_loader_flags_skills_with_mcp_entrypoint_but_no_register_tools(tmp_path, monkeypatch):
    skills_dir = tmp_path / "skills"
    broken_skill = skills_dir / "broken-skill"
    _write_skill(
        broken_skill,
        hub="brain",
        mcp_init_body='"""broken mcp entrypoint with no register_tools"""',
    )

    # ADR-795: the monolith resolves its skill roots through
    # project_tier_skill_source_dirs, so tests for the monolith path patch that.
    monkeypatch.setattr(
        "src.mcp.augur_shared.plugin_tools.project_tier_skill_source_dirs",
        lambda project_root=None: [skills_dir],
    )
    monkeypatch.setattr(
        "src.mcp.augur_shared.plugin_tools.is_skill_enabled",
        lambda _: True,
    )

    from src.mcp.augur_shared.plugin_tools import (
        get_failed_plugins,
        register_plugin_tools,
        reset_plugin_registry,
    )

    reset_plugin_registry()

    loaded = register_plugin_tools(MagicMock(), lambda f: f, MagicMock())

    assert loaded == 0
    failed = get_failed_plugins()
    # Hubs were retired in ADR-802; collected plugin ids no longer carry a
    # bundle prefix and report the placeholder "unknown" instead.
    assert failed == {
        "unknown/broken-skill": "Plugin unknown/broken-skill has an MCP entrypoint but no register_tools()"
    }


def test_monolith_loads_project_tier_skill(tmp_path, monkeypatch):
    """The project-tier monolith registers skills from project-tier roots."""
    repo_skills = tmp_path / "repo" / "skills"
    custom_skill = repo_skills / "project-fixture-skill"
    _write_skill(
        custom_skill,
        hub="dev",
        mcp_init_body=(
            "def register_tools(mcp, interceptor, metrics):\n" "    mcp.loaded_skill = 'project-fixture-skill'\n"
        ),
    )

    from src.mcp.augur_shared import plugin_tools

    monkeypatch.setattr(
        plugin_tools,
        "project_tier_skill_source_dirs",
        lambda project_root=None: [repo_skills],
    )
    monkeypatch.setattr(plugin_tools, "is_skill_enabled", lambda _: True)

    plugin_tools.reset_plugin_registry()
    mcp = MagicMock()

    loaded = plugin_tools.register_plugin_tools(mcp, lambda f: f, MagicMock())

    assert loaded == 1
    assert mcp.loaded_skill == "project-fixture-skill"


def test_monolith_excludes_private_vault_skills(tmp_path, monkeypatch):
    """ADR-795: the project-tier monolith never loads private vault skills,
    even though scope='all' (bundle_server / discovery) still sees them."""
    project_skills = tmp_path / "project-brain" / "capabilities" / "skills"
    vault_skills = tmp_path / "vault" / "capabilities" / "skills"
    _write_skill(
        project_skills / "proj-skill",
        hub="dev",
        mcp_init_body=("def register_tools(mcp, interceptor, metrics):\n" "    mcp.loaded_skill = 'proj-skill'\n"),
    )
    _write_skill(
        vault_skills / "private-skill",
        hub="life",
        mcp_init_body=("def register_tools(mcp, interceptor, metrics):\n" "    mcp.loaded_skill = 'private-skill'\n"),
    )

    from src.config import paths
    from src.mcp.augur_shared import plugin_tools

    # The real project_tier_skill_source_dirs filter drops the vault root.
    monkeypatch.setattr(
        paths,
        "get_managed_skill_source_dirs",
        lambda project_root=None: [project_skills, vault_skills],
    )
    monkeypatch.setattr(
        paths,
        "get_configured_vault_skills_dir",
        lambda project_root=None: vault_skills,
    )
    monkeypatch.setattr(paths, "get_vault_skills_dir", lambda: vault_skills)
    # scope='all' path (bundle_server / discovery) goes through this symbol.
    monkeypatch.setattr(
        plugin_tools,
        "get_managed_skill_source_dirs",
        lambda project_root=None: [project_skills, vault_skills],
    )
    monkeypatch.setattr(plugin_tools, "is_skill_enabled", lambda _: True)

    # scope='all' still sees BOTH the project and the private vault skill.
    all_names = {sd.name for _, sd in plugin_tools._collect_skill_dirs(apply_exclusions=False)}
    assert {"proj-skill", "private-skill"} <= all_names

    # The monolith (scope='project') loads ONLY the project-tier skill.
    plugin_tools.reset_plugin_registry()
    mcp = MagicMock()
    loaded = plugin_tools.register_plugin_tools(mcp, lambda f: f, MagicMock())

    assert loaded == 1
    assert mcp.loaded_skill == "proj-skill"


def test_loader_excludes_draft_and_archive_skill_roots(tmp_path, monkeypatch):
    repo_skills = tmp_path / "repo" / "skills"
    active_skill = repo_skills / "career-ops"
    draft_skill = tmp_path / "repo" / "drafts" / "staging" / "r4" / "skills" / "draft-only"
    archived_skill = tmp_path / "repo" / "archive" / "skills" / "archived-only"
    _write_skill(
        active_skill,
        hub="career",
        mcp_init_body=(
            "def register_tools(mcp, interceptor, metrics):\n" "    mcp.loaded_active_skill = 'career-ops'\n"
        ),
    )
    _write_skill(
        draft_skill,
        hub="career",
        mcp_init_body=(
            "def register_tools(mcp, interceptor, metrics):\n" "    mcp.loaded_draft_skill = 'draft-only'\n"
        ),
    )
    _write_skill(
        archived_skill,
        hub="career",
        mcp_init_body=(
            "def register_tools(mcp, interceptor, metrics):\n" "    mcp.loaded_archived_skill = 'archived-only'\n"
        ),
    )

    from src.mcp.augur_shared import plugin_tools

    # Only the active project root is a source dir; draft/archive roots are not.
    monkeypatch.setattr(
        plugin_tools,
        "project_tier_skill_source_dirs",
        lambda project_root=None: [repo_skills],
    )
    monkeypatch.setattr(plugin_tools, "is_skill_enabled", lambda _: True)

    plugin_tools.reset_plugin_registry()
    mcp = MagicMock()

    loaded = plugin_tools.register_plugin_tools(mcp, lambda f: f, MagicMock())

    assert loaded == 1
    assert mcp.loaded_active_skill == "career-ops"
    assert "loaded_draft_skill" not in mcp.__dict__
    assert "loaded_archived_skill" not in mcp.__dict__


def test_include_vault_env_flag_does_not_reintroduce_vault_into_monolith(tmp_path, monkeypatch):
    """ADR-795 supersedes the legacy AUGUR_MCP_INCLUDE_VAULT_TIER_TOOLS escape
    hatch for vault skills: the monolith is project-tier only, so the flag can
    no longer pull a private vault skill back into the project-tier server."""
    project_skills = tmp_path / "project-brain" / "capabilities" / "skills"
    project_skills.mkdir(parents=True)
    vault_skills = tmp_path / "vault" / "capabilities" / "skills"
    _write_skill(
        vault_skills / "private-skill",
        hub="brain",
        mcp_init_body=("def register_tools(mcp, interceptor, metrics):\n" "    mcp.loaded_skill = 'private-skill'\n"),
    )

    from src.config import paths
    from src.mcp.augur_shared import plugin_tools

    monkeypatch.setattr(
        paths,
        "get_managed_skill_source_dirs",
        lambda project_root=None: [project_skills, vault_skills],
    )
    monkeypatch.setattr(
        paths,
        "get_configured_vault_skills_dir",
        lambda project_root=None: vault_skills,
    )
    monkeypatch.setattr(paths, "get_vault_skills_dir", lambda: vault_skills)
    monkeypatch.setattr(
        plugin_tools,
        "get_managed_skill_source_dirs",
        lambda project_root=None: [project_skills, vault_skills],
    )
    monkeypatch.setattr(plugin_tools, "is_skill_enabled", lambda _: True)
    monkeypatch.setenv("AUGUR_MCP_INCLUDE_VAULT_TIER_TOOLS", "1")

    plugin_tools.reset_plugin_registry()
    mcp = MagicMock()

    loaded = plugin_tools.register_plugin_tools(mcp, lambda f: f, MagicMock())

    assert loaded == 0
    assert "loaded_skill" not in mcp.__dict__


def test_cli_runtime_loads_project_tier_excluded_bundles(tmp_path, monkeypatch):
    """The in-process CLI runtime still reaches project-tier bundles that the
    AI-client monolith excludes (e.g. project-brain `ingest`)."""
    repo_skills = tmp_path / "repo" / "skills"
    ingest_skill = repo_skills / "ingest"
    _write_skill(
        ingest_skill,
        hub="brain",
        mcp_init_body=("def register_tools(mcp, interceptor, metrics):\n" "    mcp.loaded_skill = 'ingest'\n"),
    )

    from src.cli_config import manifest
    from src.cli_config.manifest import Manifest
    from src.mcp.augur_shared import plugin_tools

    monkeypatch.setattr(
        plugin_tools,
        "project_tier_skill_source_dirs",
        lambda project_root=None: [repo_skills],
    )
    monkeypatch.setattr(plugin_tools, "is_skill_enabled", lambda _: True)
    monkeypatch.setattr(
        manifest,
        "load_manifest",
        lambda: Manifest(project_tier=[], vault_tier=[], monolith_exclusions=["ingest"]),
    )

    plugin_tools.reset_plugin_registry()
    mcp = MagicMock()

    loaded = plugin_tools.register_plugin_tools(
        mcp,
        lambda f: f,
        MagicMock(),
        capability_target="cli",
    )

    assert loaded == 1
    assert mcp.loaded_skill == "ingest"


def test_loader_pins_mcp_sdk_before_skill_scripts_can_shadow_it(tmp_path, monkeypatch):
    pytest.importorskip("mcp.types")

    poison_skill = tmp_path / "poison"
    _write_skill(
        poison_skill,
        hub="dev",
        mcp_init_body=(
            "from pathlib import Path\n"
            "import sys\n\n"
            "def register_tools(mcp, interceptor, metrics):\n"
            "    scripts_dir = Path(__file__).resolve().parents[1]\n"
            "    sys.path.insert(0, str(scripts_dir))\n"
        ),
    )

    annotations_skill = tmp_path / "uses-annotations"
    _write_skill(
        annotations_skill,
        hub="dev",
        mcp_init_body=(
            "from src.mcp.augur_shared.annotations import tool_annotations\n\n"
            "def register_tools(mcp, interceptor, metrics):\n"
            "    mcp.annotation_type = type(tool_annotations({\n"
            "        'title': 'Shadow-safe annotations',\n"
            "        'readOnlyHint': True,\n"
            "        'destructiveHint': False,\n"
            "        'idempotentHint': True,\n"
            "        'openWorldHint': False,\n"
            "    })).__name__\n"
        ),
    )

    from src.mcp.augur_shared import plugin_tools

    monkeypatch.setattr(
        plugin_tools,
        "_collect_skill_dirs",
        lambda **_kwargs: [
            ("dev/poison", poison_skill),
            ("dev/uses-annotations", annotations_skill),
        ],
    )
    monkeypatch.setattr(plugin_tools, "is_skill_enabled", lambda _: True)
    monkeypatch.delitem(sys.modules, "src.mcp.augur_shared.annotations", raising=False)
    monkeypatch.delitem(sys.modules, "mcp.types", raising=False)
    monkeypatch.delitem(sys.modules, "mcp", raising=False)

    plugin_tools.reset_plugin_registry()
    mcp = MagicMock()

    loaded = plugin_tools.register_plugin_tools(mcp, lambda f: f, MagicMock())

    assert loaded == 2
    assert plugin_tools.get_failed_plugins() == {}
    assert mcp.annotation_type == "ToolAnnotations"


def test_bundle_loader_reloads_changed_bundle_code_without_path_leak(tmp_path):
    skill = tmp_path / "skills" / "reloadable"
    _write_skill(
        skill,
        hub="dev",
        mcp_init_body=(
            "from ..value import VALUE\n\n" "def register_tools(mcp, interceptor, metrics):\n" "    mcp.value = VALUE\n"
        ),
    )
    (skill / "scripts" / "value.py").write_text("VALUE = 'v1'\n", encoding="utf-8")

    from src.mcp.augur_shared import plugin_tools

    module = plugin_tools._load_bundle_mcp_module(skill)
    mcp = MagicMock()
    plugin_tools._register_bundle_tools(module, skill, mcp, lambda f: f, MagicMock())
    assert mcp.value == "v1"

    (skill / "scripts" / "value.py").write_text("VALUE = 'v2'\n", encoding="utf-8")
    module = plugin_tools._load_bundle_mcp_module(skill)
    mcp = MagicMock()
    plugin_tools._register_bundle_tools(module, skill, mcp, lambda f: f, MagicMock())

    assert mcp.value == "v2"
    assert str(skill.parent.parent.resolve()) not in sys.path
    assert str(skill.resolve()) not in sys.path
    assert str((skill / "scripts").resolve()) not in sys.path


def test_bundle_loader_reloads_absolute_skills_imports_without_path_leak(tmp_path):
    skill = tmp_path / "skills" / "absimport"
    _write_skill(
        skill,
        hub="dev",
        mcp_init_body=(
            "from skills.absimport.scripts.value import VALUE\n\n"
            "def register_tools(mcp, interceptor, metrics):\n"
            "    mcp.value = VALUE\n"
        ),
    )
    (skill / "scripts" / "value.py").write_text("VALUE = 'v1'\n", encoding="utf-8")

    from src.mcp.augur_shared import plugin_tools

    module = plugin_tools._load_bundle_mcp_module(skill)
    mcp = MagicMock()
    plugin_tools._register_bundle_tools(module, skill, mcp, lambda f: f, MagicMock())
    assert mcp.value == "v1"

    (skill / "scripts" / "value.py").write_text("VALUE = 'v2'\n", encoding="utf-8")
    module = plugin_tools._load_bundle_mcp_module(skill)
    mcp = MagicMock()
    plugin_tools._register_bundle_tools(module, skill, mcp, lambda f: f, MagicMock())

    assert mcp.value == "v2"
    assert str(skill.parent.parent.resolve()) not in sys.path
    assert str(skill.resolve()) not in sys.path
    assert str((skill / "scripts").resolve()) not in sys.path


def test_bundle_loader_supports_import_scripts_helper_without_global_scripts(tmp_path):
    skill = tmp_path / "skills" / "script-importer"
    _write_skill(
        skill,
        hub="dev",
        mcp_init_body=(
            "def register_tools(mcp, interceptor, metrics):\n"
            "    def read_value():\n"
            "        import scripts.helper\n"
            "        return scripts.helper.VALUE\n"
            "    mcp.tool(name='read-value')(interceptor(read_value))\n"
        ),
    )
    (skill / "scripts" / "helper.py").write_text("VALUE = 'from-helper'\n", encoding="utf-8")

    from src.mcp.augur_shared import plugin_tools

    for name in list(sys.modules):
        if name == "scripts" or name.startswith("scripts."):
            sys.modules.pop(name)

    module = plugin_tools._load_bundle_mcp_module(skill)
    mcp = FakeMCP()
    plugin_tools._register_bundle_tools(module, skill, mcp, lambda f: f, MagicMock())

    assert asyncio.run(mcp.tools["read-value"]()) == "from-helper"
    assert not any(name == "scripts" or name.startswith("scripts.") for name in sys.modules)
    assert str(skill.parent.parent.resolve()) not in sys.path
    assert str(skill.resolve()) not in sys.path
    assert str((skill / "scripts").resolve()) not in sys.path


def test_tier0_discovery_omits_retired_repo_root_skills(tmp_path):
    project_root = tmp_path / "project"
    legacy_skill = project_root.joinpath("skills", "legacy-runtime")
    shared_skill = project_root / "project-brain" / "capabilities" / "skills" / "shared-runtime"
    _write_skill(
        legacy_skill,
        hub="dev",
        mcp_init_body="def register_tools(mcp, interceptor, metrics):\n    pass\n",
    )
    _write_skill(
        shared_skill,
        hub="dev",
        mcp_init_body="def register_tools(mcp, interceptor, metrics):\n    pass\n",
    )

    from src.plugins.skill_discovery import discover_all_skills, invalidate_discovery_cache

    invalidate_discovery_cache()
    records = discover_all_skills(tiers=(0,), project_root=project_root)
    records_by_name = {record.name: record for record in records}
    assert "legacy-runtime" not in records_by_name
    assert records_by_name["shared-runtime"].origin == "project-brain"
    assert records_by_name["shared-runtime"].source_root == "project-brain"

    legacy_skills_root = project_root.joinpath("skills")
    for path in sorted(legacy_skills_root.rglob("*"), reverse=True):
        if path.is_file():
            path.unlink()
        else:
            path.rmdir()
    legacy_skills_root.rmdir()
    invalidate_discovery_cache()

    records = discover_all_skills(tiers=(0,), project_root=project_root)
    assert "legacy-runtime" not in {record.name for record in records}


def test_bundle_loader_supports_lazy_relative_import_that_imports_scripts(tmp_path):
    skill = tmp_path / "skills" / "lazy-relative"
    _write_skill(
        skill,
        hub="dev",
        mcp_init_body=(
            "def register_tools(mcp, interceptor, metrics):\n"
            "    def read_value():\n"
            "        from ..worker import read\n"
            "        return read()\n"
            "    mcp.tool(name='read-value')(interceptor(read_value))\n"
        ),
    )
    (skill / "scripts" / "helper.py").write_text("VALUE = 'lazy-ok'\n", encoding="utf-8")
    (skill / "scripts" / "worker.py").write_text(
        "import scripts.helper\n\n" "def read():\n" "    return scripts.helper.VALUE\n",
        encoding="utf-8",
    )

    from src.mcp.augur_shared import plugin_tools

    for name in list(sys.modules):
        if name == "scripts" or name.startswith("scripts."):
            sys.modules.pop(name)

    module = plugin_tools._load_bundle_mcp_module(skill)
    mcp = FakeMCP()
    plugin_tools._register_bundle_tools(module, skill, mcp, lambda f: f, MagicMock())

    assert asyncio.run(mcp.tools["read-value"]()) == "lazy-ok"
    assert not any(name == "scripts" or name.startswith("scripts.") for name in sys.modules)
    assert str(skill.parent.parent.resolve()) not in sys.path
    assert str(skill.resolve()) not in sys.path
    assert str((skill / "scripts").resolve()) not in sys.path
