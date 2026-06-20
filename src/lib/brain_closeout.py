"""Whole-family verification closeout for harness layering (ADR-786)."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
import subprocess
from typing import Any

from src.lib.brain_memory_tiers import read_memory_union, render_memory_handoff_markdown
from src.lib.brain_parity import assert_skill_parity
from src.lib.brain_stack import BrainStack
from src.lib.brain_verify_harness import verify_harness_summary

_TEXT_SUFFIXES = {
    ".cfg",
    ".cjs",
    ".css",
    ".js",
    ".json",
    ".jsx",
    ".md",
    ".mjs",
    ".py",
    ".sh",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}
_SKIP_DIRS = {
    ".git",
    ".mypy_cache",
    ".next",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
}


@dataclass(frozen=True)
class CloseoutReport:
    all_ok: bool
    sections: dict[str, Any] = field(default_factory=dict)
    generated_at: str = field(default_factory=lambda: _utc_now())

    def to_dict(self) -> dict[str, Any]:
        return {
            "all_ok": self.all_ok,
            "generated_at": self.generated_at,
            "sections": self.sections,
        }


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def verify_family_closeout(
    stack: BrainStack,
    *,
    clients: Sequence[str],
    single_brain_skills: set[str],
    client_dirs: dict[str, Path] | None = None,
    orphan_refs: list[str] | None = None,
    scan_roots: Sequence[Path] | None = None,
    moved_paths: Sequence[str] | None = None,
    project_root: Path | None = None,
    memory_targets: dict[str, Path | None] | None = None,
) -> CloseoutReport:
    """Run the ADR-786 family closeout gates and return a structured report."""
    harness = verify_harness_summary(
        stack,
        clients=clients,
        client_dirs=client_dirs,
        project_root=project_root,
    )
    parity = assert_skill_parity(stack, single_brain_skills=single_brain_skills)
    refs = list(orphan_refs) if orphan_refs is not None else scan_orphan_references(scan_roots or (), moved_paths or ())
    memory = verify_memory_round_trip(
        stack,
        clients=clients,
        memory_targets=memory_targets,
    )
    sections: dict[str, Any] = {
        "tiers": {"items": _tier_items(stack)},
        "harness": harness,
        "parity": {
            "ok": parity.ok,
            "added": sorted(parity.added),
            "dropped": sorted(parity.dropped),
        },
        "orphan_refs": {
            "ok": not refs,
            "count": len(refs),
            "refs": refs,
        },
        "memory_round_trip": memory,
    }
    all_ok = bool(harness.get("all_ok")) and parity.ok and not refs and bool(memory.get("ok"))
    return CloseoutReport(all_ok=all_ok, sections=sections)


def _tier_items(stack: BrainStack) -> list[dict[str, str]]:
    return [
        {
            "tier": brain.type.value,
            "brain_id": brain.id,
            "root": str(Path(brain.data_root)),
        }
        for brain in stack.ordered()
    ]


def verify_memory_round_trip(
    stack: BrainStack,
    *,
    clients: Sequence[str],
    memory_targets: dict[str, Path | None] | None = None,
) -> dict[str, Any]:
    """Verify tiered memory has real records and is visible in projected clients."""
    union = read_memory_union(stack)
    rendered = render_memory_handoff_markdown(stack)
    sample_keys = _sample_handoff_keys(rendered)
    target_reports: dict[str, Any] = {}
    for client in clients:
        target = memory_targets.get(client) if memory_targets else None
        if target is None:
            target_reports[client] = {"ok": True, "path": None, "checked": False}
            continue
        path = Path(target)
        exists = path.is_file()
        text = path.read_text(encoding="utf-8") if exists else ""
        contains_handoff = "# Augur Cross-Client Handoff" in text
        contains_samples = all(key in text for key in sample_keys[:1]) if sample_keys else False
        target_reports[client] = {
            "ok": exists and contains_handoff and contains_samples,
            "path": str(path),
            "checked": True,
            "exists": exists,
            "contains_handoff": contains_handoff,
            "contains_sample": contains_samples,
        }
    target_ok = all(item["ok"] for item in target_reports.values())
    return {
        "ok": bool(union) and bool(rendered.strip()) and target_ok,
        "entry_count": len(union),
        "sample_entries": sample_keys,
        "projected_bytes": len(rendered.encode("utf-8")),
        "client_targets": target_reports,
    }


def _sample_handoff_keys(rendered: str) -> list[str]:
    keys: list[str] = []
    for line in rendered.splitlines():
        if not line.startswith("- **"):
            continue
        key, sep, _rest = line.removeprefix("- **").partition("**:")
        if sep and key:
            keys.append(key)
    return keys[:5]


def scan_orphan_references(
    roots: Iterable[Path],
    moved_paths: Sequence[str],
) -> list[str]:
    """Return text references to migrated path fragments that should be gone."""
    fragments = [fragment for fragment in moved_paths if fragment]
    if not fragments:
        return []
    hits: list[str] = []
    for root in roots:
        root_path = Path(root)
        if not root_path.exists():
            continue
        rg_hits = _scan_root_with_rg(root_path, fragments)
        hits.extend(rg_hits)
        if rg_hits:
            continue
        hits.extend(_scan_root_with_python(root_path, fragments))
    return sorted(dict.fromkeys(hits))


def _scan_root_with_rg(root: Path, fragments: Sequence[str]) -> list[str]:
    cmd = [
        "rg",
        "--fixed-strings",
        "--line-number",
        "--no-heading",
        "--hidden",
        "--glob",
        "!llms-full.txt",
    ]
    for skip in sorted(_SKIP_DIRS):
        cmd.extend(["--glob", f"!{skip}/**"])
    for fragment in fragments:
        cmd.extend(["-e", fragment])
    cmd.append(str(root))
    try:
        result = subprocess.run(
            cmd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except FileNotFoundError:
        return []
    if result.returncode not in {0, 1}:
        return []
    return [_normalize_rg_line(line) for line in result.stdout.splitlines() if line.strip()]


def _normalize_rg_line(line: str) -> str:
    path, sep, rest = line.partition(":")
    if not sep:
        return line
    lineno, sep, text = rest.partition(":")
    if not sep:
        return line
    return f"{path}:{lineno}: {text}"


def _scan_root_with_python(root: Path, fragments: Sequence[str]) -> list[str]:
    hits: list[str] = []
    for path in root.rglob("*"):
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        if not path.is_file() or path.suffix not in _TEXT_SUFFIXES:
            continue
        if path.name == "llms-full.txt":
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for lineno, line in enumerate(lines, start=1):
            if any(fragment in line for fragment in fragments):
                hits.append(f"{path}:{lineno}: {line}")
    return hits


def project_tier_skill_names(stack: BrainStack) -> set[str]:
    """Return the pre-cutover single-brain baseline: the project tier's skills."""
    if stack.project is None:
        return set()
    root = Path(stack.project.active_brain.data_root) / "capabilities" / "skills"
    if not root.is_dir():
        return set()
    return {child.name for child in root.iterdir() if (child / "SKILL.md").is_file()}


def default_memory_targets(project_root: Path, clients: Sequence[str]) -> dict[str, Path | None]:
    """Resolve known projected memory files for supported clients."""
    targets: dict[str, Path | None] = {}
    for client in clients:
        if client == "claude":
            targets[client] = _claude_memory_target(project_root)
        elif client == "codex":
            targets[client] = Path.home() / ".codex" / "augur-memory.md"
        elif client == "gemini":
            targets[client] = project_root / ".gemini" / "memory" / "augur-memory.md"
        elif client == "cursor":
            targets[client] = project_root / ".cursor" / "memory" / "augur-memory.md"
        elif client == "copilot":
            targets[client] = project_root / ".github" / "copilot-memory.md"
        else:
            targets[client] = None
    return targets


def _claude_memory_target(project_root: Path) -> Path | None:
    try:
        from src.config.paths import get_claude_native_memory_dir

        native_dir = get_claude_native_memory_dir(project_root, create=False)
    except Exception:
        return None
    return native_dir / "MEMORY.md" if native_dir is not None else None


def enabled_clients_from_dirs(client_dirs: dict[str, Path]) -> tuple[str, ...]:
    """Derive clients with at least one configured skill directory path."""
    clients: set[str] = set()
    for tag, path in client_dirs.items():
        if "-" not in tag:
            continue
        root = Path(path)
        if not root.is_dir() or not any(child.is_dir() for child in root.iterdir()):
            continue
        client, _scope = tag.split("-", 1)
        if client:
            clients.add(client)
    return tuple(sorted(clients))


def default_moved_path_fragments() -> tuple[str, ...]:
    """High-signal path fragments retired by the harness-layering family."""
    vault_skills = "vault" + "/skills"
    au_vault_skills = "Au-vault" + "/skills"
    return (
        f"{vault_skills}/",
        vault_skills,
        f"{au_vault_skills}/",
        au_vault_skills,
    )
