"""verify-harness: cross-client correctness gate (ADR-781 section 2a).

Read-only verification that each AI client actually received the effective
capability set the layered stack promises. ``missing = expected - received`` is
the gap the projection pipeline must close. No writes, no client mutation.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from src.lib.brain_effective import compute_effective_skills
from src.lib.brain_layered_projection import resolve_layered_projection
from src.lib.brain_stack import BrainStack


@dataclass(frozen=True)
class ClientHarnessReport:
    client: str
    expected: tuple[str, ...]
    received: tuple[str, ...]
    missing: tuple[str, ...]

    def ok(self) -> bool:
        return not self.missing


def client_received_skills(client: str, *, client_dirs: dict[str, Path]) -> set[str]:
    """Skill names a client has projected across its local and global dirs."""
    names: set[str] = set()
    for tag in (f"{client}-local", f"{client}-global"):
        path = client_dirs.get(tag)
        if path is None or not Path(path).is_dir():
            continue
        names.update(child.name for child in Path(path).iterdir() if child.is_dir())
    return names


def verify_harness_skills(
    stack: BrainStack,
    *,
    clients: Sequence[str] = ("claude", "codex", "gemini"),
    client_dirs: dict[str, Path] | None = None,
    project_root: Path | None = None,
) -> list[ClientHarnessReport]:
    """Diff the effective skill set against what each client received."""
    if client_dirs is None:
        from src.config.paths import get_client_skill_dirs

        client_dirs = get_client_skill_dirs()
    effective = set(compute_effective_skills(resolve_layered_projection(stack, project_root=project_root)).names())
    expected = tuple(sorted(effective))
    reports: list[ClientHarnessReport] = []
    for client in clients:
        received = client_received_skills(client, client_dirs=client_dirs)
        reports.append(
            ClientHarnessReport(
                client=client,
                expected=expected,
                received=tuple(sorted(received)),
                missing=tuple(sorted(effective - received)),
            )
        )
    return reports


def verify_harness_summary(
    stack: BrainStack,
    *,
    clients: Sequence[str] = ("claude", "codex", "gemini"),
    client_dirs: dict[str, Path] | None = None,
    project_root: Path | None = None,
) -> dict:
    """Compact per-client ok/missing summary for the verify-harness gate."""
    reports = verify_harness_skills(
        stack,
        clients=clients,
        client_dirs=client_dirs,
        project_root=project_root,
    )
    summary: dict = {report.client: {"ok": report.ok(), "missing": list(report.missing)} for report in reports}
    summary["all_ok"] = all(report.ok() for report in reports)
    return summary
