"""Guard the primary AI-client command surface."""
from __future__ import annotations

import json
import re
from pathlib import Path

import yaml


CANONICAL_COMMANDS = {"ask", "keep", "discover", "routines", "skillify", "project"}
PRIMARY_CLIENTS = {"claude", "codex", "gemini"}
PROJECT_SUBCOMMANDS = {"adr", "dev", "sweep"}
RETIRED_GENERATED_WRAPPERS = {
    "adr",
    "dev",
    "sweep",
    "dev-build",
    "dev-clean",
    "dev-debug",
    "dev-merge",
    "routine",
    "sweep-stores",
}

RETIRED_ALIASES = {
    "note",
    "save",
    "adr",
    "dev",
    "dev-build",
    "dev-clean",
    "dev-debug",
    "dev-merge",
    "routine",
    "sweep-stores",
    "eval",
    "profile",
    "dream",
    "sweep",
}


def _repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "project.yaml").exists():
            return parent
    raise RuntimeError("Unable to locate repository root containing project.yaml")


def _frontmatter(text: str) -> str:
    if not text.startswith("---\n"):
        return ""
    end = text.find("\n---", 4)
    if end == -1:
        return ""
    return text[4:end]


def _is_exported_command(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    return bool(re.search(r"^x-augur-export-command:\s*true\s*$", _frontmatter(text), re.MULTILINE))


def _generated_manifest_names(manifest_path: Path) -> set[str]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = payload.get("files", [])
    assert isinstance(files, list), f"{manifest_path} files must be a list"

    names = set()
    for entry in files:
        assert isinstance(entry, str), f"{manifest_path} entries must be strings"
        names.add(Path(entry).parts[0].removesuffix(".md"))
    return names


def _generated_command_manifests(root: Path) -> tuple[Path, ...]:
    return (
        root / ".claude" / "commands" / ".augur-generated-commands.json",
        root / ".codex" / "skills" / ".augur-generated-commands.json",
        root / ".antigravity" / "plugins" / ".augur-generated-commands.json",
    )


def _generated_command_roots(root: Path) -> tuple[tuple[Path, str], ...]:
    return (
        (root / ".claude" / "commands", ".md"),
        (root / ".codex" / "skills", ""),
        (root / ".antigravity" / "plugins", ""),
    )


def test_only_canonical_commands_are_exported_to_primary_clients() -> None:
    root = _repo_root()
    exported = {
        path.stem
        for path in (root / "project-brain" / "capabilities" / "skills").glob("*/commands/*.md")
        if _is_exported_command(path)
    }

    assert exported == CANONICAL_COMMANDS


def test_generated_primary_surfaces_do_not_contain_retired_aliases() -> None:
    root = _repo_root()
    generated_names: set[str] = set()

    for manifest_path in _generated_command_manifests(root):
        if not manifest_path.parent.exists():
            continue
        assert manifest_path.exists(), f"missing generated command manifest in existing generated root: {manifest_path}"
        generated_names.update(_generated_manifest_names(manifest_path))

    assert generated_names.isdisjoint(RETIRED_ALIASES)


def test_generated_command_manifests_only_list_canonical_commands() -> None:
    root = _repo_root()

    for manifest_path in _generated_command_manifests(root):
        if not manifest_path.parent.exists():
            continue
        assert manifest_path.exists(), f"missing generated command manifest in existing generated root: {manifest_path}"
        assert _generated_manifest_names(manifest_path) == CANONICAL_COMMANDS


def test_generated_command_roots_do_not_contain_retired_wrappers() -> None:
    root = _repo_root()
    stale_paths = []

    for command_root, suffix in _generated_command_roots(root):
        if not command_root.exists():
            continue
        for retired in RETIRED_GENERATED_WRAPPERS:
            candidate = command_root / f"{retired}{suffix}"
            if candidate.exists():
                stale_paths.append(candidate)

    assert not stale_paths


def test_canonical_commands_export_to_every_primary_client() -> None:
    root = _repo_root()
    policy = yaml.safe_load((root / "config" / "system" / "capability_exposure.yaml").read_text(encoding="utf-8"))
    capabilities = policy["capabilities"]

    for command in CANONICAL_COMMANDS:
        exports = set(capabilities[f"command:{command}"]["export_to"])
        assert PRIMARY_CLIENTS <= exports

    for command in RETIRED_ALIASES - PROJECT_SUBCOMMANDS:
        entry = capabilities.get(f"command:{command}")
        if entry:
            assert set(entry.get("export_to", [])).isdisjoint(PRIMARY_CLIENTS)


def test_project_coupled_commands_are_subcommands_not_primary_exports() -> None:
    root = _repo_root()
    policy = yaml.safe_load((root / "config" / "system" / "capability_exposure.yaml").read_text(encoding="utf-8"))
    capabilities = policy["capabilities"]

    for command in PROJECT_SUBCOMMANDS:
        entry = capabilities[f"command:{command}"]
        assert entry["primary_surface"] == "subcommand"
        assert entry["x-augur-parent"] == "project"
        assert set(entry.get("export_to", [])).isdisjoint(PRIMARY_CLIENTS)
