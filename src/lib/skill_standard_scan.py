"""Deterministic skill standard scanner."""

from __future__ import annotations

import dataclasses
import enum
from pathlib import Path
from typing import Any

from src.lib.skill_standard import STANDARD_TOOL_SURFACES, normalize_skill_file


class Severity(enum.Enum):
    FAIL = "fail"
    WARN = "warn"


@dataclasses.dataclass(frozen=True)
class SkillStandardIssue:
    code: str
    severity: Severity
    path: Path
    message: str
    suggested_fix: str
    ownership: str
    skill: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity.value,
            "path": str(self.path),
            "message": self.message,
            "suggested_fix": self.suggested_fix,
            "ownership": self.ownership,
            "skill": self.skill,
        }


@dataclasses.dataclass(frozen=True)
class SkillStandardReport:
    skills_scanned: int
    fail_count: int
    warn_count: int
    issues: tuple[SkillStandardIssue, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "skills_scanned": self.skills_scanned,
            "fail_count": self.fail_count,
            "warn_count": self.warn_count,
            "issues": [issue.to_dict() for issue in self.issues],
        }


BANNED_ROOT_DIRS: dict[str, str] = {
    "docs": "Move docs/ to references/.",
    "data": "Move data/ to assets/seeds/ or a vault-first data helper.",
    "lib": "Move lib/ to scripts/ or augur/lib/.",
}


def scan_skill_roots(shared_root: Path, private_root: Path | None) -> SkillStandardReport:
    issues: list[SkillStandardIssue] = []
    skills_scanned = 0

    for root, ownership in _existing_roots(shared_root, private_root):
        for skill_dir in sorted(path for path in root.iterdir() if path.is_dir()):
            if skill_dir.name.startswith("."):
                continue
            skills_scanned += 1
            skill_md = skill_dir / "SKILL.md"
            skill_name = skill_dir.name
            issue_ownership = ownership

            if not skill_md.is_file():
                issues.append(
                    _issue(
                        "missing-skill-md",
                        ownership=ownership,
                        path=skill_md,
                        skill=skill_name,
                        message=f"Skill {skill_name} is missing SKILL.md.",
                        suggested_fix="Add SKILL.md with standard skill metadata.",
                    )
                )
            else:
                normalized = normalize_skill_file(
                    skill_md,
                    shared_root=shared_root,
                    private_root=private_root,
                )
                skill_name = normalized.name or skill_name
                issue_ownership = normalized.ownership
                valid_surfaces = ", ".join(sorted(STANDARD_TOOL_SURFACES))
                for tool in normalized.tools:
                    if tool.surface in STANDARD_TOOL_SURFACES:
                        continue
                    issues.append(
                        _issue(
                            "invalid-tool-surface",
                            ownership=issue_ownership,
                            path=skill_md,
                            skill=skill_name,
                            message=(f"Tool {tool.name} declares non-standard " f"surface {tool.surface!r}."),
                            suggested_fix=(f"Change surface to one of: {valid_surfaces}."),
                        )
                    )

            for dirname, suggested_fix in BANNED_ROOT_DIRS.items():
                banned_path = skill_dir / dirname
                if not banned_path.is_dir():
                    continue
                issues.append(
                    _issue(
                        "banned-root-dir",
                        ownership=issue_ownership,
                        path=banned_path,
                        skill=skill_name,
                        message=(f"Skill {skill_name} has banned root directory " f"{dirname}/."),
                        suggested_fix=suggested_fix,
                    )
                )

    fail_count = sum(1 for issue in issues if issue.severity is Severity.FAIL)
    warn_count = sum(1 for issue in issues if issue.severity is Severity.WARN)
    return SkillStandardReport(
        skills_scanned=skills_scanned,
        fail_count=fail_count,
        warn_count=warn_count,
        issues=tuple(issues),
    )


def _existing_roots(
    shared_root: Path,
    private_root: Path | None,
) -> tuple[tuple[Path, str], ...]:
    roots: list[tuple[Path, str]] = []
    seen: set[Path] = set()
    candidates: list[tuple[Path, str]] = [(shared_root, "augur")]
    if private_root is not None:
        candidates.append((private_root, "user"))

    for root, ownership in candidates:
        if not root.is_dir():
            continue
        resolved = root.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        roots.append((root, ownership))
    return tuple(roots)


def _issue(
    code: str,
    *,
    ownership: str,
    path: Path,
    skill: str,
    message: str,
    suggested_fix: str,
) -> SkillStandardIssue:
    severity = Severity.FAIL if ownership == "augur" else Severity.WARN
    return SkillStandardIssue(
        code=code,
        severity=severity,
        path=path,
        message=message,
        suggested_fix=suggested_fix,
        ownership=ownership,
        skill=skill,
    )
