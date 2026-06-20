from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path


WINDOWS_TERMS = ("windows", "powershell", "pwsh")
POSIX_TERMS = ("posix", "macos", "linux", "bash", "zsh")
CROSS_PLATFORM_TERMS = ("cross-platform", "cross platform", "cross-os", "cross os")
BASH_ONLY_PATTERNS = (
    "python3 ",
    "grep ",
    "sed ",
    "awk ",
    "chmod ",
    "source ",
    "export ",
    "cat <<",
    "./scripts/",
)
FENCE_RE = re.compile(r"```(?P<lang>[A-Za-z0-9_-]*)\n(?P<body>.*?)\n```", re.DOTALL)


@dataclass(frozen=True)
class Issue:
    code: str
    message: str
    line: int


def _nearby_context(text: str, offset: int) -> str:
    before = text[:offset].splitlines()
    heading_index = 0
    for index in range(len(before) - 1, -1, -1):
        if before[index].lstrip().startswith("#"):
            heading_index = index
            break
    lines = [line.strip().lower() for line in before[heading_index:] if line.strip()]
    return "\n".join(lines[-6:])


def _line_number(text: str, offset: int) -> int:
    return text[:offset].count("\n") + 1


def lint_text(text: str) -> list[Issue]:
    issues: list[Issue] = []
    for match in FENCE_RE.finditer(text):
        lang = match.group("lang").lower()
        body = match.group("body")
        context = _nearby_context(text, match.start())
        line = _line_number(text, match.start())
        in_windows = any(term in context for term in WINDOWS_TERMS)
        in_posix = any(term in context for term in POSIX_TERMS)
        in_cross_platform = any(term in context for term in CROSS_PLATFORM_TERMS)
        body_has_bash = any(pattern in body for pattern in BASH_ONLY_PATTERNS)

        if in_windows and (lang == "bash" or body_has_bash):
            issues.append(
                Issue(
                    "windows-bash-command",
                    "Windows sections must use PowerShell or provide a Windows-native equivalent.",
                    line,
                )
            )
        elif in_cross_platform and lang == "bash" and not in_posix:
            issues.append(
                Issue(
                    "unlabeled-bash-block",
                    "Bash blocks must be under an explicit POSIX/macOS/Linux heading.",
                    line,
                )
            )
    return issues


def lint_file(path: Path) -> list[Issue]:
    return lint_text(path.read_text(encoding="utf-8"))


def iter_markdown_files(path: Path) -> list[Path]:
    if path.is_dir():
        return sorted(path.rglob("*.md"))
    return [path]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lint docs for unlabeled Bash in cross-platform command guidance.")
    parser.add_argument(
        "paths",
        nargs="*",
        default=["docs/superpowers/plans", "docs/superpowers/specs", "docs/agent-topics"],
    )
    args = parser.parse_args(argv)

    issues: list[tuple[Path, Issue]] = []
    for raw in args.paths:
        for file in iter_markdown_files(Path(raw)):
            for issue in lint_file(file):
                issues.append((file, issue))

    for file, issue in issues:
        print(f"{file}:{issue.line}: {issue.code}: {issue.message}")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
