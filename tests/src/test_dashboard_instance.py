from src.lib.dashboard_instance import (
    DEFAULT_DASHBOARD_PORT,
    DEFAULT_MCP_PORT,
    external_dashboard_cache_dir,
    resolve_dashboard_instance,
)


def test_main_checkout_resolves_to_visible_main(tmp_path, monkeypatch):
    repo = tmp_path / "Augur"
    repo.mkdir()
    runtime = tmp_path / "runtime"
    runtime.mkdir()

    monkeypatch.setattr(
        "src.lib.dashboard_instance.resolve_main_repo",
        lambda project_root, marker: project_root,
    )

    instance = resolve_dashboard_instance(repo, runtime_dir=runtime)

    assert instance.instance_id == "main"
    assert instance.kind == "main"
    assert instance.name == "main"
    assert instance.dashboard_port == DEFAULT_DASHBOARD_PORT
    assert instance.mcp_port == DEFAULT_MCP_PORT
    assert instance.browser_mode == "visible_allowed"
    assert instance.heal_policy == "enabled"
    assert instance.visibility_policy == "visible_allowed"
    assert instance.lifecycle_dir == runtime / "daemon" / "dashboard" / "main"
    assert instance.build_lock_dir == runtime / "locks" / "dashboard" / "main"
    assert instance.browser_artifact_dir == runtime / "browser-verification" / "main"


def test_main_checkout_ignores_stray_registry_port_entry(tmp_path, monkeypatch):
    """A worktree-registry row keyed to the MAIN repo path must not move the
    main instance off the canonical default port.

    Regression for the `aug dev build` false-`ok:false` bug: a `--from-hook`
    auto-register in the main checkout wrote a registry entry for the main path
    with dashboard_port 3002, so resolution returned 3002 while the live server
    ran on the canonical 3000 — the scoped restart then missed the real server
    and the readiness poll checked the wrong port.
    """
    repo = tmp_path / "Augur"
    repo.mkdir()
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "worktree_registry.yaml").write_text(
        "\n".join(
            [
                "worktrees:",
                f"  '{repo.resolve()}':",
                "    name: Augur",
                "    dashboard_port: 3002",
                "    mcp_port: 8082",
                "    branch: main",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "src.lib.dashboard_instance.resolve_main_repo",
        lambda project_root, marker: project_root,
    )

    instance = resolve_dashboard_instance(repo, runtime_dir=runtime)

    assert instance.kind == "main"
    assert instance.dashboard_port == DEFAULT_DASHBOARD_PORT
    assert instance.mcp_port == DEFAULT_MCP_PORT


def test_marker_worktree_resolves_to_validation_instance(tmp_path):
    main_repo = tmp_path / "Augur"
    worktree = tmp_path / "Augur-adr-737"
    runtime = tmp_path / "runtime"
    main_repo.mkdir()
    worktree.mkdir()
    (worktree / ".augur-worktree.yaml").write_text(
        "\n".join(
            [
                "worktree: true",
                "name: adr-737",
                f"main_repo: {main_repo}",
                "dashboard_port: 3004",
                "mcp_port: 8084",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    instance = resolve_dashboard_instance(worktree, runtime_dir=runtime)

    assert instance.instance_id == "worktree:adr-737"
    assert instance.kind == "worktree"
    assert instance.name == "adr-737"
    assert instance.project_root == worktree.resolve()
    assert instance.main_repo == main_repo.resolve()
    assert instance.dashboard_port == 3004
    assert instance.mcp_port == 8084
    assert instance.browser_mode == "headless_only"
    assert instance.heal_policy == "validation_only"
    assert instance.visibility_policy == "no_visible_mutation"
    assert instance.lifecycle_dir == runtime / "daemon" / "dashboard" / "worktrees" / "adr-737"
    assert instance.build_lock_dir == runtime / "locks" / "dashboard" / "worktrees" / "adr-737"
    assert instance.browser_artifact_dir == runtime / "browser-verification" / "worktrees" / "adr-737"


def test_registry_worktree_resolves_ports_name_and_branch_when_marker_lacks_them(
    tmp_path,
):
    main_repo = tmp_path / "Augur"
    worktree = tmp_path / "Augur-adr-737"
    runtime = tmp_path / "runtime"
    main_repo.mkdir()
    worktree.mkdir()
    (runtime / "worktree_registry.yaml").parent.mkdir(parents=True)
    (runtime / "worktree_registry.yaml").write_text(
        "\n".join(
            [
                "worktrees:",
                f"  '{worktree.resolve()}':",
                "    name: adr-737",
                "    dashboard_port: 3005",
                "    mcp_port: 8085",
                "    branch: codex/adr-737",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (worktree / ".augur-worktree.yaml").write_text(
        f"worktree: true\nmain_repo: {main_repo}\n",
        encoding="utf-8",
    )

    instance = resolve_dashboard_instance(worktree, runtime_dir=runtime)

    assert instance.instance_id == "worktree:adr-737"
    assert instance.name == "adr-737"
    assert instance.dashboard_port == 3005
    assert instance.mcp_port == 8085
    assert instance.branch == "codex/adr-737"


def test_interactive_worktree_resolves_to_isolated_visible(tmp_path):
    main_repo = tmp_path / "Augur"
    worktree = tmp_path / "Augur-adr-737"
    runtime = tmp_path / "runtime"
    main_repo.mkdir()
    worktree.mkdir()
    (worktree / ".augur-worktree.yaml").write_text(
        f"worktree: true\nname: adr-737\nmain_repo: {main_repo}\n",
        encoding="utf-8",
    )

    headless = resolve_dashboard_instance(worktree, runtime_dir=runtime, interactive=False)
    interactive = resolve_dashboard_instance(worktree, runtime_dir=runtime, interactive=True)

    assert headless.browser_mode == "headless_only"
    assert interactive.browser_mode == "isolated_visible"
    # Visible-surface gate stays on regardless — main browser must not be touched.
    assert interactive.visibility_policy == "no_visible_mutation"
    assert interactive.heal_policy == "validation_only"


def test_interactive_isolated_checkout_resolves_to_isolated_visible(tmp_path, monkeypatch):
    repo = tmp_path / "Augur-detached"
    main_repo = tmp_path / "Augur"
    runtime = tmp_path / "runtime"
    repo.mkdir()
    main_repo.mkdir()

    monkeypatch.setattr(
        "src.lib.dashboard_instance.resolve_main_repo",
        lambda project_root, marker: main_repo,
    )

    instance = resolve_dashboard_instance(repo, runtime_dir=runtime, interactive=True)

    assert instance.kind == "isolated"
    assert instance.browser_mode == "isolated_visible"
    assert instance.heal_policy == "disabled"
    assert instance.visibility_policy == "no_visible_mutation"


def test_interactive_main_checkout_unchanged_keeps_visible_allowed(tmp_path, monkeypatch):
    repo = tmp_path / "Augur"
    repo.mkdir()
    runtime = tmp_path / "runtime"
    runtime.mkdir()

    monkeypatch.setattr(
        "src.lib.dashboard_instance.resolve_main_repo",
        lambda project_root, marker: project_root,
    )

    instance = resolve_dashboard_instance(repo, runtime_dir=runtime, interactive=True)

    assert instance.kind == "main"
    # Main is already visible; --interactive is a no-op for main.
    assert instance.browser_mode == "visible_allowed"
    assert instance.visibility_policy == "visible_allowed"


def test_unregistered_non_main_checkout_fails_closed_as_isolated(tmp_path, monkeypatch):
    repo = tmp_path / "Augur-detached"
    main_repo = tmp_path / "Augur"
    runtime = tmp_path / "runtime"
    repo.mkdir()
    main_repo.mkdir()

    monkeypatch.setattr(
        "src.lib.dashboard_instance.resolve_main_repo",
        lambda project_root, marker: main_repo,
    )

    instance = resolve_dashboard_instance(repo, runtime_dir=runtime)

    assert instance.kind == "isolated"
    assert instance.instance_id.startswith("isolated:")
    assert instance.dashboard_port == DEFAULT_DASHBOARD_PORT
    assert instance.mcp_port == DEFAULT_MCP_PORT
    assert instance.browser_mode == "headless_only"
    assert instance.heal_policy == "disabled"
    assert instance.visibility_policy == "no_visible_mutation"


def test_external_cache_dir_matches_start_dev_namespace_for_worktree(tmp_path):
    """The cleanup-side cache path must equal the namespace start-dev.sh
    creates: "dashboard-worktree-" + instance id sanitized with the same
    character class (':' becomes '-', so "worktree:NAME" doubles the prefix).
    """
    main_repo = tmp_path / "Augur"
    worktree = tmp_path / "Augur-notes-classification"
    runtime = tmp_path / "runtime"
    cache_root = tmp_path / "cache"
    main_repo.mkdir()
    worktree.mkdir()
    (worktree / ".augur-worktree.yaml").write_text(
        "\n".join(
            [
                "worktree: true",
                "name: notes-classification",
                f"main_repo: {main_repo}",
                "dashboard_port: 3004",
                "mcp_port: 8084",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    instance = resolve_dashboard_instance(worktree, runtime_dir=runtime)
    cache_dir = external_dashboard_cache_dir(instance, cache_root=cache_root)

    assert instance.instance_id == "worktree:notes-classification"
    assert cache_dir == cache_root / "dashboard-worktree-worktree-notes-classification"


def test_external_cache_dir_is_none_for_main(tmp_path, monkeypatch):
    """Main shares the "dashboard" namespace; per-worktree cleanup must never
    resolve a removable cache dir for it.
    """
    repo = tmp_path / "Augur"
    runtime = tmp_path / "runtime"
    repo.mkdir()
    runtime.mkdir()

    monkeypatch.setattr(
        "src.lib.dashboard_instance.resolve_main_repo",
        lambda project_root, marker: project_root,
    )

    instance = resolve_dashboard_instance(repo, runtime_dir=runtime)

    assert external_dashboard_cache_dir(instance, cache_root=tmp_path) is None
