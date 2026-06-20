#!/usr/bin/env python3
"""Generate client-specific stub files from skills/*/SKILL.md.

One-way generator: reads skills/ at project root, writes stubs into
client-specific directories so Claude Code, Gemini, Codex, Cursor, Copilot,
and OpenCode can discover skills natively.

Generated files are marked with AUGUR-GENERATED (HTML comment for flat files,
frontmatter field for subdirectory SKILL.md files). Stale marked stubs whose
source skill no longer exists are cleaned up automatically.

Every run validates both source SKILL.md files and generated output, exiting
non-zero if any issues are found.

Usage:
    python scripts/generate_client_stubs.py [--dry-run]
"""

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config.paths import get_project_root, get_skills_dir as _get_skills_dir
from src.lib.frontmatter_utils import (
    parse_frontmatter,
    write_frontmatter,
)

MARKER = "<!-- AUGUR-GENERATED -->"
MARKER_FIELD = "x-augur-generated"


@dataclass(frozen=True)
class ClientSpec:
    rel_dir: str
    ext: str  # ignored for subdir layout
    subdir: bool  # True: {dir}/{name}/SKILL.md, False: {dir}/{name}{ext}


ALL_CLIENTS: dict[str, ClientSpec] = {
    "claude": ClientSpec(".claude/skills", ".md", subdir=True),
    "gemini": ClientSpec(".gemini/skills", ".md", subdir=True),
    "codex": ClientSpec(".codex/prompts", ".md", subdir=False),
    "cursor": ClientSpec(".cursor/rules", ".mdc", subdir=False),
    "copilot": ClientSpec(".github/instructions", ".instructions.md", subdir=False),
    "opencode": ClientSpec(".opencode/skills", ".md", subdir=True),
}


def is_generated(path: Path) -> bool:
    """Return True if the file contains an AUGUR-GENERATED marker.

    Checks first 500 bytes to handle both flat stubs (HTML comment on line 1)
    and subdir stubs (frontmatter field).
    """
    try:
        with path.open(encoding="utf-8") as f:
            head = f.read(500)
        return MARKER in head or f"{MARKER_FIELD}:" in head
    except OSError:
        return False


# -- Stub builders ----------------------------------------------------------

def _build_flat_stub(name: str, description: str, body: str) -> str:
    parts = [MARKER, "<!-- source: augur -->", "", f"# {name}"]
    if description:
        parts.extend(["", f"> {description}"])
    if body:
        parts.extend(["", body])
    return "\n".join(parts) + "\n"


def _write_subdir_stub(target: Path, name: str, description: str, body: str) -> None:
    """Write a SKILL.md stub with YAML frontmatter via canonical write_frontmatter."""
    meta: dict[str, Any] = {
        "name": name,
        "description": description,
        "source": "augur",
        MARKER_FIELD: True,
    }
    stub_body = MARKER + "\n"
    if body:
        stub_body += "\n" + body
    write_frontmatter(target, meta, stub_body)


# -- Validation -------------------------------------------------------------

def _validate_source(
    skill_name: str, meta: dict[str, Any], path: Path,
) -> list[str]:
    """Validate a single source SKILL.md. Returns error strings."""
    errors: list[str] = []
    if not meta:
        errors.append(f"  {skill_name}: missing or unparseable frontmatter")
        return errors
    if not meta.get("name"):
        errors.append(f"  {skill_name}: missing 'name' in frontmatter")
    if not meta.get("description"):
        errors.append(f"  {skill_name}: missing 'description' in frontmatter")
    return errors


def _validate_subdir_stub(
    meta: dict[str, Any], rel: Path,
) -> list[str]:
    """Validate an in-memory subdir stub's metadata before writing."""
    errors: list[str] = []
    if not meta.get("name"):
        errors.append(f"  {rel}: missing 'name' in frontmatter")
    if not meta.get("description"):
        errors.append(f"  {rel}: missing 'description' in frontmatter")
    if not meta.get(MARKER_FIELD):
        errors.append(f"  {rel}: missing '{MARKER_FIELD}' in frontmatter")
    return errors


def _validate_existing_artifacts(project_root: Path) -> list[str]:
    """Check for stale flat files and orphan dirs in subdir client directories."""
    errors: list[str] = []
    for client, spec in ALL_CLIENTS.items():
        if not spec.subdir:
            continue
        target_dir = project_root / spec.rel_dir
        if not target_dir.exists():
            continue
        for entry in sorted(target_dir.iterdir()):
            rel = entry.relative_to(project_root)
            if entry.is_file() and is_generated(entry):
                errors.append(f"  {rel}: stale flat stub in subdir client '{client}'")
            elif entry.is_dir() and not (entry / "SKILL.md").exists():
                errors.append(f"  {rel}/: orphan directory — no SKILL.md")
    return errors


# -- Core operations --------------------------------------------------------

def generate_and_validate(
    project_root: Path,
    skills_dir: Path,
    dry_run: bool = False,
) -> tuple[int, set[str], list[str]]:
    """Single-pass: validate sources, generate stubs, validate output.

    Returns (stubs_written, canonical_names, errors).
    """
    written = 0
    canonical_names: set[str] = set()
    errors: list[str] = []

    skill_mds = sorted(skills_dir.glob("*/SKILL.md"))
    if not skill_mds:
        print(f"[stubs] No SKILL.md files found in {skills_dir} — nothing to generate.")
        return written, canonical_names, errors

    for skill_md in skill_mds:
        dir_name = skill_md.parent.name
        meta, body = parse_frontmatter(skill_md)

        canonical_name = str(meta.get("name", "")) or dir_name
        description = str(meta.get("description", ""))
        canonical_names.add(canonical_name)

        # Validate source
        errors.extend(_validate_source(dir_name, meta, skill_md))

        flat_content = _build_flat_stub(canonical_name, description, body)
        subdir_meta: dict[str, Any] = {
            "name": canonical_name,
            "description": description,
            "source": "augur",
            MARKER_FIELD: True,
        }

        for client, spec in ALL_CLIENTS.items():
            if spec.subdir:
                target_dir = project_root / spec.rel_dir / canonical_name
                target_file = target_dir / "SKILL.md"
                # Validate in-memory before writing
                rel = target_file.relative_to(project_root)
                errors.extend(_validate_subdir_stub(subdir_meta, rel))
            else:
                target_dir = project_root / spec.rel_dir
                target_file = target_dir / f"{canonical_name}{spec.ext}"

            if dry_run:
                print(f"[dry-run] Would write {target_file}")
                written += 1
                continue

            if spec.subdir:
                _write_subdir_stub(target_file, canonical_name, description, body)
            else:
                target_dir.mkdir(parents=True, exist_ok=True)
                target_file.write_text(flat_content, encoding="utf-8")
            written += 1

    print(f"[stubs] Wrote {written} stub(s) across {len(ALL_CLIENTS)} clients.")
    return written, canonical_names, errors


def cleanup_stale_stubs(
    project_root: Path,
    existing_names: set[str],
    dry_run: bool = False,
) -> list[str]:
    """Delete generated stubs whose source skill no longer exists.

    Only deletes files that contain AUGUR-GENERATED marker. Returns deleted paths.
    """
    deleted: list[str] = []

    for _client, spec in ALL_CLIENTS.items():
        target_dir = project_root / spec.rel_dir
        if not target_dir.exists():
            continue

        if spec.subdir:
            for entry in target_dir.iterdir():
                if entry.is_dir():
                    skill_md = entry / "SKILL.md"
                    if not skill_md.exists() or not is_generated(skill_md):
                        continue
                    if entry.name not in existing_names:
                        if dry_run:
                            print(f"[dry-run] Would delete stale stub dir {entry}")
                        else:
                            skill_md.unlink()
                            try:
                                entry.rmdir()
                            except OSError:
                                pass
                            print(f"[stubs] Deleted stale stub {entry.relative_to(project_root)}/")
                        deleted.append(str(skill_md))
                elif entry.is_file() and is_generated(entry):
                    # Stale flat file from pre-migration
                    if dry_run:
                        print(f"[dry-run] Would delete stale flat stub {entry}")
                    else:
                        entry.unlink()
                        print(f"[stubs] Deleted stale flat stub {entry.relative_to(project_root)}")
                    deleted.append(str(entry))
        else:
            for stub_file in target_dir.iterdir():
                if not stub_file.is_file() or stub_file.suffix != spec.ext:
                    continue
                if not is_generated(stub_file):
                    continue
                if stub_file.stem not in existing_names:
                    if dry_run:
                        print(f"[dry-run] Would delete stale stub {stub_file}")
                    else:
                        stub_file.unlink()
                        print(f"[stubs] Deleted stale stub {stub_file.relative_to(project_root)}")
                    deleted.append(str(stub_file))

    return deleted


def sync_agents(
    project_root: Path,
    dry_run: bool = False,
) -> tuple[int, int]:
    """Sync agent .md files and registry.json from plugins/agents/ to .claude/agents/.

    Returns (generated_count, deleted_count).
    """
    agents_src = project_root / "plugins" / "agents"
    agents_dst = project_root / ".claude" / "agents"

    if not agents_src.exists():
        print(f"[agents] plugins/agents/ directory not found at {agents_src} — skipping sync.")
        return 0, 0

    generated = 0
    deleted = 0
    source_names: set[str] = set()

    for src_file in sorted(agents_src.glob("*.md")):
        source_names.add(src_file.stem)
        content = src_file.read_text(encoding="utf-8")
        dst_file = agents_dst / src_file.name

        if dry_run:
            print(f"[dry-run] Would write {dst_file.relative_to(project_root)}")
        else:
            agents_dst.mkdir(parents=True, exist_ok=True)
            dst_file.write_text(MARKER + "\n" + content, encoding="utf-8")
            print(f"[agents] Wrote {dst_file.relative_to(project_root)}")
        generated += 1

    registry_src = agents_src / "registry.json"
    if registry_src.exists():
        registry_dst = agents_dst / "registry.json"
        if dry_run:
            print(f"[dry-run] Would copy registry.json to {registry_dst.relative_to(project_root)}")
        else:
            agents_dst.mkdir(parents=True, exist_ok=True)
            if registry_dst.exists():
                current_mode = registry_dst.stat().st_mode
                if not (current_mode & 0o200):
                    registry_dst.chmod(current_mode | 0o200)
            registry_dst.write_text(registry_src.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"[agents] Wrote {registry_dst.relative_to(project_root)}")

    if agents_dst.exists():
        for dst_file in sorted(agents_dst.glob("*.md")):
            if not is_generated(dst_file):
                continue
            if dst_file.stem not in source_names:
                if dry_run:
                    print(f"[dry-run] Would delete stale agent stub {dst_file.relative_to(project_root)}")
                else:
                    dst_file.unlink()
                    print(f"[agents] Deleted stale stub {dst_file.relative_to(project_root)}")
                deleted += 1

    return generated, deleted


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate client-specific stub files from skills/*/SKILL.md."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without writing or deleting any files.",
    )
    args = parser.parse_args(argv)

    project_root = get_project_root()
    skills_dir = _get_skills_dir()

    if not skills_dir.exists():
        print(f"[stubs] skills/ directory not found at {skills_dir} — nothing to do.")
        return 0

    mode = "[dry-run] " if args.dry_run else ""

    # Single pass: validate sources + generate + validate output
    written, canonical_names, errors = generate_and_validate(
        project_root, skills_dir, dry_run=args.dry_run,
    )
    deleted = cleanup_stale_stubs(project_root, canonical_names, dry_run=args.dry_run)

    # Check for stale artifacts in subdir client dirs
    if not args.dry_run:
        errors.extend(_validate_existing_artifacts(project_root))

    print(f"[stubs] {mode}Done — {written} stub(s) written, {len(deleted)} stale stub(s) removed.")

    agent_gen, agent_del = sync_agents(project_root, dry_run=args.dry_run)
    print(f"[agents] {mode}Done — {agent_gen} agent(s) synced, {agent_del} stale agent(s) removed.")

    if errors:
        print(f"[validate] {len(errors)} issue(s):")
        for err in errors:
            print(err)
        print("[validate] Failed — fix issues above.")
        return 1

    print("[validate] All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
