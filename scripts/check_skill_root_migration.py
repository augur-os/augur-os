#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROOT_SKILLS = ROOT / "skills"
SHARED_SKILLS = ROOT / "project-brain" / "capabilities" / "skills"

SCAN_GLOBS = [
    "src/**/*.py",
    "src/**/*.sh",
    "src/**/*.bash",
    "src/**/*.zsh",
    "src/**/*.ts",
    "src/**/*.tsx",
    "apps/dashboard/**/*.py",
    "apps/dashboard/**/*.sh",
    "apps/dashboard/**/*.bash",
    "apps/dashboard/**/*.zsh",
    "apps/dashboard/**/*.ts",
    "apps/dashboard/**/*.tsx",
    "scripts/**/*.py",
    "scripts/**/*.sh",
    "scripts/**/*.bash",
    "scripts/**/*.zsh",
    ".github/**/*.py",
    ".github/**/*.sh",
    ".github/**/*.bash",
    ".github/**/*.zsh",
    ".github/**/*.yaml",
    ".github/**/*.yml",
    "config/**/*.yaml",
    "config/**/*.yml",
    "project-brain/capabilities/skills/**/*.py",
]

FORBIDDEN_FINAL_REGEXES = [
    ("repo-root variable", re.compile(r"(?<![\w.])(?:ROOT|PROJECT_ROOT|project_root|repo_root|root)\s*/\s*[\"']skills[\"']")),
    ("repo-root attribute", re.compile(r"\bself\._?project_root\s*/\s*[\"']skills[\"']")),
    ("repo-root helper", re.compile(r"\bget_project_root\(\)\s*/\s*[\"']skills[\"']")),
    ("cwd root helper", re.compile(r"\bPath\.cwd\(\)\s*/\s*[\"']skills[\"']")),
    ("file-parent helper", re.compile(r"\bPath\(__file__\)\.resolve\(\)\.parents\[\d+\]\s*/\s*[\"']skills[\"']")),
    ("repo-root path.join", re.compile(r"\bpath\.join\(\s*(?:repoRoot|root|PROJECT_ROOT|projectRoot)\s*,\s*[\"']skills[\"']")),
    ("root-relative Path", re.compile(r"\bPath\(\s*[\"']skills[\"']\s*\)")),
    ("root-relative glob", re.compile(r"\bglob\(\s*[\"']skills/")),
    ("root-relative shell command", re.compile(r"\bpython(?:3(?:\.\d+)?)?\s+(?:\./)?skills/")),
    ("root-relative shell path", re.compile(r"\$\{?(?:INSTALL_DIR|MAIN_REPO|PROJECT_ROOT|ROOT)\}?\s*/skills\b")),
]

ALLOWED_CLIENT_ROOT_REGEX = re.compile(
    r"(?:[\"']\.(?:gemini|codex|opencode)[\"']|Path\(\s*[\"']\.(?:gemini|codex|opencode)[\"']\s*\))"
    r"\s*/\s*(?:[\"']skills[\"']|Path\(\s*[\"']skills[\"']\s*\))"
)

ALLOWED_FINAL_FILES = {
    "scripts/check_skill_root_migration.py",
    "tests/test_shared_vault_skill_root_migration.py",
}

TEST_SCAN_GLOBS = [
    "tests/**/*.py",
    "project-brain/capabilities/skills/**/tests/**/*.py",
]

ALLOWED_TEST_RESIDUE_FILES = {
    "tests/test_shared_vault_skill_root_migration.py",
    "tests/unit/test_skill_release_matrix.py",
}


def _skill_dirs(path: Path) -> list[str]:
    if not path.is_dir():
        return []
    return sorted(child.name for child in path.iterdir() if child.is_dir() and not child.name.startswith("."))


def inventory() -> int:
    print("root_skill_dirs:")
    for name in _skill_dirs(ROOT_SKILLS):
        print(f"  - {name}")
    print("shared_vault_skill_dirs:")
    for name in _skill_dirs(SHARED_SKILLS):
        print(f"  - {name}")
    return 0


def _iter_scan_files() -> list[Path]:
    files: list[Path] = []
    for pattern in SCAN_GLOBS:
        files.extend(ROOT.glob(pattern))
    return sorted({
        path
        for path in files
        if path.is_file() and "/tests/" not in path.relative_to(ROOT).as_posix()
    })


def _iter_test_scan_files() -> list[Path]:
    files: list[Path] = []
    for pattern in TEST_SCAN_GLOBS:
        files.extend(ROOT.glob(pattern))
    return sorted({path for path in files if path.is_file()})


def _scan_file_for_issues(path: Path, rel: str) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except (OSError, UnicodeError) as exc:
        return [f"{rel}: could not read file: {exc}"]

    issues: list[str] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if ALLOWED_CLIENT_ROOT_REGEX.search(line):
            line = ALLOWED_CLIENT_ROOT_REGEX.sub("", line)
        for label, regex in FORBIDDEN_FINAL_REGEXES:
            if regex.search(line):
                issues.append(f"{rel}:{line_number}: forbidden root-skill {label} {regex.pattern!r}")
    return issues


def final_contract() -> int:
    issues: list[str] = []
    if ROOT_SKILLS.exists():
        issues.append(f"repo-root skills directory still exists: {ROOT_SKILLS.relative_to(ROOT)}")

    for path in _iter_scan_files():
        rel = path.relative_to(ROOT).as_posix()
        if rel in ALLOWED_FINAL_FILES:
            continue
        issues.extend(_scan_file_for_issues(path, rel))

    if issues:
        print("skill root migration contract failed:")
        for issue in issues:
            print(f"  - {issue}")
        return 1

    print("skill root migration contract passed")
    return 0


def test_contract() -> int:
    issues: list[str] = []
    for path in _iter_test_scan_files():
        rel = path.relative_to(ROOT).as_posix()
        if rel in ALLOWED_TEST_RESIDUE_FILES:
            continue
        issues.extend(_scan_file_for_issues(path, rel))

    if issues:
        print("test skill root migration contract failed:")
        for issue in issues:
            print(f"  - {issue}")
        return 1

    print("test skill root migration contract passed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", action="store_true")
    parser.add_argument("--final-contract", action="store_true")
    parser.add_argument("--test-contract", action="store_true")
    args = parser.parse_args()

    if args.inventory:
        return inventory()
    if args.final_contract:
        return final_contract()
    if args.test_contract:
        return test_contract()

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
