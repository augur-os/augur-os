from __future__ import annotations

from pathlib import Path

import yaml

from skills.evals.scripts import command_kpi_bootstrap as bootstrap


def test_bootstrap_writes_private_scenarios_under_documents(tmp_path, monkeypatch) -> None:
    docs = tmp_path / "Au-docs"
    vault = tmp_path / "Au-vault"
    repo = tmp_path / "Augur"
    (repo / "docs/references").mkdir(parents=True)
    (repo / "docs/references/command-quality-contract.md").write_text(
        "# Command Quality Contract\n\n"
        "- `/ask`\n"
        "- `/keep`\n"
        "- `/discover`\n"
        "- `/adr`\n"
        "- `/dev`\n"
        "- `/a-loops`\n"
        "- `/sweep`\n",
        encoding="utf-8",
    )
    vault.mkdir()
    (vault / "profile.md").write_text(
        "---\ntitle: Private Profile\n---\nKnown fact: private profile exists.\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(bootstrap, "get_documents_dir", lambda: docs)
    monkeypatch.setattr(bootstrap, "get_vault_dir", lambda: vault)
    monkeypatch.setattr(bootstrap, "get_project_root", lambda: repo)

    result = bootstrap.bootstrap_private_scenarios(run_id="test-run")

    scenario_path = docs / "evals/commands/scenarios/test-run.yaml"
    assert result["scenario_path"] == str(scenario_path)
    assert scenario_path.exists()
    payload = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
    commands = {item["command"] for item in payload["scenarios"]}
    assert len(payload["scenarios"]) >= 19
    assert commands >= {"ask", "keep", "discover", "adr", "dev", "routines", "sweep"}
    assert any(item["private_refs"] for item in payload["scenarios"])


def test_bootstrap_includes_claude_desktop_local_file_scenario(tmp_path, monkeypatch) -> None:
    """The pack must cover the Claude Desktop save-a-file regression.

    Saving/noting a file from Claude Desktop should quickly choose a local/private
    file route and never default to a cloud destination. The scenario uses a real
    scratch file whose path contains a space (Claude Desktop style) and forbids
    every cloud route.
    """
    docs = tmp_path / "Au-docs"
    vault = tmp_path / "Au-vault"
    repo = tmp_path / "Augur"
    (repo / "docs/references").mkdir(parents=True)
    (repo / "docs/references/command-quality-contract.md").write_text("contract", encoding="utf-8")
    vault.mkdir()

    monkeypatch.setattr(bootstrap, "get_documents_dir", lambda: docs)
    monkeypatch.setattr(bootstrap, "get_vault_dir", lambda: vault)
    monkeypatch.setattr(bootstrap, "get_project_root", lambda: repo)

    bootstrap.bootstrap_private_scenarios(run_id="claude-desktop-run")

    scenario_path = docs / "evals/commands/scenarios/claude-desktop-run.yaml"
    payload = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
    assert len(payload["scenarios"]) >= 20

    scenario = next(
        item for item in payload["scenarios"] if item["id"] == "keep-claude-desktop-local-file"
    )
    assert scenario["command"] == "keep"
    assert scenario["client"] == "claude"
    assert scenario["assertions"]["expected_route"] == "local-file"
    forbidden = {route.lower() for route in scenario["assertions"]["forbidden_routes"]}
    assert {"google-drive", "gdrive", "cloud"} <= forbidden
    # The input path mimics a Claude Desktop / macOS path with a space, and the
    # bootstrap must materialize it so the runner scores a real local file.
    assert " " in Path(scenario["input"]).name
    assert Path(scenario["input"]).exists()
    assert scenario["private_refs"] == [scenario["input"]]
    # Route-decision speed bar: "quickly", must not wander through many paths.
    assert scenario["max_duration_ms"] <= 3000


def test_bootstrap_rejects_unsafe_run_id(tmp_path, monkeypatch) -> None:
    docs = tmp_path / "Au-docs"
    repo = tmp_path / "Augur"
    (repo / "docs/references").mkdir(parents=True)
    (repo / "docs/references/command-quality-contract.md").write_text("contract", encoding="utf-8")

    monkeypatch.setattr(bootstrap, "get_documents_dir", lambda: docs)
    monkeypatch.setattr(bootstrap, "get_vault_dir", lambda: tmp_path / "Au-vault")
    monkeypatch.setattr(bootstrap, "get_project_root", lambda: repo)

    try:
        bootstrap.bootstrap_private_scenarios(run_id="../escape")
    except ValueError as exc:
        assert "safe path component" in str(exc)
    else:  # pragma: no cover - explicit failure branch for clearer assertion output
        raise AssertionError("expected unsafe run_id to fail")

    assert not (tmp_path / "escape.yaml").exists()
