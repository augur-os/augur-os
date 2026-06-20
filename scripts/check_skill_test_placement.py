"""Pre-commit + CI guard: prevent staged/vault skill name leakage into central tests/.

Per ADR-762: skill-specific tests belong in project-brain/capabilities/skills/<skill>/augur/tests/.
The central tests/ directory must only contain repo-level tests (src/, scripts/,
apps/dashboard/) plus an explicit allowlist of boundary tests that legitimately
need to know vault-tier skill names.

Exit codes:
  0 — clean (no violations)
  1 — one or more violations (printed with file path + reason + suggested fix)

Usage:
  uv run python scripts/check_skill_test_placement.py [--repo <path>]
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Violation:
    file: Path
    reason: str
    suggestion: str


@dataclass
class ScanResult:
    exit_code: int
    violations: list[Violation]


def _list_vault_skills(repo: Path) -> list[str]:
    shared = repo / "project-brain" / "capabilities" / "skills"
    if not shared.is_dir():
        return []
    return sorted(
        p.name for p in shared.iterdir()
        if p.is_dir() and not p.name.startswith(".") and p.name != "README.md"
    )


def _list_private_skills(repo: Path) -> list[str]:
    """Discover private-vault skill names from any visible vault location.

    Production: ~/Projects/Au-vault/capabilities/skills/  (read from config/system/vault.yaml).
    Test fixtures: <repo>/_fake_private_vault/capabilities/skills/  (simulates without env touch).
    """
    candidates: list[Path] = []
    fake = repo / "_fake_private_vault" / "capabilities" / "skills"
    if fake.is_dir():
        candidates.append(fake)
    real = Path.home() / "Projects" / "Au-vault" / "capabilities" / "skills"
    if real.is_dir():
        candidates.append(real)
    names: set[str] = set()
    for root in candidates:
        for p in root.iterdir():
            if p.is_dir() and not p.name.startswith("."):
                names.add(p.name)
    return sorted(names)


def _list_staged_skills(repo: Path) -> list[str]:
    """Skills marked as staged (r1/r2/r3/r4/later) — NOT in the MVP/public release.

    Reads docs/generated/skill-release-matrix.json. These are the names with
    HIGH upstream-leak risk: their code is intentionally excluded from
    build/codex/, so any test referencing them in central tests/ leaks
    unreleased work into the upstream artifact.
    """
    import json
    matrix_path = repo / "docs" / "generated" / "skill-release-matrix.json"
    if not matrix_path.is_file():
        return []
    try:
        data = json.loads(matrix_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    skills = data.get("skills", [])
    if not isinstance(skills, list):
        return []
    return sorted(
        s.get("name", "") for s in skills
        if isinstance(s, dict) and s.get("release") not in (None, "", "mvp", "unknown")
        and s.get("name")
    )


def _load_allowlist(repo: Path) -> list[str]:
    path = repo / "config" / "system" / "test_placement_allowlist.yaml"
    if not path.is_file():
        return []
    try:
        import yaml  # stdlib via pyyaml dependency
    except ImportError:
        return []
    raw = yaml.safe_load(path.read_text()) or {}
    if not isinstance(raw, dict):
        return []
    entries = raw.get("allowed_central_tests_with_skill_refs", [])
    if not isinstance(entries, list):
        return []
    return [str(e) for e in entries if isinstance(e, str)]


def scan(repo: Path) -> ScanResult:
    """Scan central tests/ for staged/vault skill name leakage."""
    repo = repo.resolve()
    central = repo / "tests"
    if not central.is_dir():
        return ScanResult(exit_code=0, violations=[])

    vault_skills = _list_vault_skills(repo)
    private_skills = _list_private_skills(repo)
    staged_skills = _list_staged_skills(repo)
    all_skills = sorted(set(vault_skills) | set(private_skills))
    allowlist = set(_load_allowlist(repo))

    violations: list[Violation] = []

    # Check 1: every test file under central tests/
    for test_file in sorted(central.rglob("test_*.py")):
        if "__pycache__" in test_file.parts:
            continue
        rel = test_file.relative_to(repo).as_posix()

        # Rule A (STRICT): filename can't include a STAGED skill name.
        # Staged skills are not in MVP/public release, so their names in
        # central tests/ are an active upstream-leak risk. For MVP skills
        # we only check body-imports (Rule B) — filename matches like
        # "test_vault_status" are too over-eager to flag on word alone.
        stem = test_file.stem
        stem_norm = stem.replace("-", "_")
        for skill in staged_skills:
            skill_underscore = skill.replace("-", "_")
            if re.search(rf"(?:^|_){re.escape(skill_underscore)}(?:_|$)", stem_norm):
                if rel not in allowlist:
                    target_root = "project-brain" if skill in vault_skills else "~/Projects/Au-vault"
                    violations.append(Violation(
                        file=test_file,
                        reason=f"filename references STAGED skill {skill!r} (upstream-leak risk)",
                        suggestion=(
                            f"move to {target_root}/skills/{skill}/augur/tests/{test_file.name}, "
                            f"OR rename to drop the skill name, "
                            f"OR add {rel!r} to config/system/test_placement_allowlist.yaml"
                        ),
                    ))
                    break

        # Rule B: file body can't reference a skill's scripts/ tree.
        # This applies to ALL skills (MVP + staged + private) because importing
        # a skill's internals from central tests/ is a convention violation
        # per feedback-skill-test-convention (test belongs in skill's augur/tests/).
        if rel in allowlist:
            continue
        try:
            text = test_file.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for skill in all_skills:
            aliases = sorted({skill, skill.replace("-", "_")})
            path_patterns = [
                rf"project-brain/capabilities/skills/{re.escape(skill)}/scripts(?:/|\b)",
                rf"~/Projects/Au-vault/capabilities/skills/{re.escape(skill)}/scripts(?:/|\b)",
                rf"skills/{re.escape(skill)}/scripts(?:/|\b)",
            ]
            import_patterns = [
                rf"\b(?:from|import)\s+skills\.{re.escape(alias)}\.scripts(?:\.|\b)"
                for alias in aliases
            ]
            dotted_reference_patterns = [
                rf"(?<![A-Za-z0-9_])skills\.{re.escape(alias)}\.scripts(?:\.|\b)"
                for alias in aliases
            ]
            for pat in path_patterns + import_patterns + dotted_reference_patterns:
                if re.search(pat, text):
                    target_root = "project-brain" if skill in vault_skills else "~/Projects/Au-vault"
                    is_staged = skill in staged_skills
                    severity = "STAGED skill (upstream-leak risk)" if is_staged else "skill convention violation"
                    violations.append(Violation(
                        file=test_file,
                        reason=f"references skill/{skill}/scripts/ — {severity}",
                        suggestion=(
                            f"move to {target_root}/skills/{skill}/augur/tests/{test_file.name}, "
                            f"OR add {rel!r} to allowlist"
                        ),
                    ))
                    break
            else:
                continue
            break

    # Check 2: stale allowlist entries
    for entry in sorted(allowlist):
        if not (repo / entry).is_file():
            violations.append(Violation(
                file=repo / "config" / "system" / "test_placement_allowlist.yaml",
                reason=f"stale allowlist entry: {entry!r} does not exist on disk",
                suggestion=f"remove {entry!r} from config/system/test_placement_allowlist.yaml",
            ))

    return ScanResult(exit_code=1 if violations else 0, violations=violations)


def _print_violations(result: ScanResult, repo: Path) -> None:
    if not result.violations:
        return
    print(f"❌ {len(result.violations)} test placement violation(s) found:\n")
    for v in result.violations:
        try:
            rel = v.file.relative_to(repo).as_posix()
        except ValueError:
            rel = str(v.file)
        print(f"  {rel}")
        print(f"    reason: {v.reason}")
        print(f"    fix:    {v.suggestion}")
        print()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=None,
                        help="Repo root (default: discovered via src.config.paths)")
    args = parser.parse_args()

    if args.repo is None:
        # Use the package's helper if importable; otherwise infer from this file.
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
            from src.config.paths import get_project_root
            repo = get_project_root()
        except Exception:
            repo = Path(__file__).resolve().parent.parent
    else:
        repo = args.repo

    result = scan(repo)
    _print_violations(result, repo)
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
