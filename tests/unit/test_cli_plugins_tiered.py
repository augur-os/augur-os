from __future__ import annotations

import argparse
from pathlib import Path


def _write_cli_skill(root: Path, skill: str, command: str, source: str) -> None:
    mcp_dir = root / skill / "scripts" / "mcp"
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "__init__.py").write_text(
        "\n".join(
            [
                "def register_subcommands(subparsers):",
                f"    parser = subparsers.add_parser({command!r})",
                f"    parser.set_defaults(source={source!r})",
            ]
        ),
        encoding="utf-8",
    )


def test_discover_subcommands_merges_tiers_most_specific_wins(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from src import cli_plugins

    global_skills = tmp_path / "global" / "capabilities" / "skills"
    user_skills = tmp_path / "user" / "capabilities" / "skills"
    _write_cli_skill(global_skills, "global-foo", "foo", "global")
    _write_cli_skill(user_skills, "user-foo", "foo", "user")
    _write_cli_skill(user_skills, "user-bar", "bar", "user")
    monkeypatch.setattr(
        cli_plugins,
        "_subcommand_source_dirs",
        lambda _project_root=None: [global_skills, user_skills],
    )

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")

    contributed = cli_plugins.discover_subcommands(subparsers)

    assert contributed == 2
    assert parser.parse_args(["foo"]).source == "user"
    assert parser.parse_args(["bar"]).source == "user"
