"""Pre-commit validation for protected system config files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys

import yaml

from src.config.schemas.llm_schema import LlmSchemaError, validate_llm_config
from src.config.schemas.settings_schema import SettingsSchemaError, validate_settings_config

PROTECTED_PATHS = {
    Path("config/system/llm.yaml"),
    Path("config/system/settings.yaml"),
}


@dataclass(frozen=True)
class ValidationResult:
    path: str
    success: bool
    error: str | None = None


def _normalize_path(path: str | Path) -> Path:
    return Path(str(path).replace("\\", "/"))


def is_protected_path(path: str | Path) -> bool:
    return _normalize_path(path) in PROTECTED_PATHS


def validate_blob(path: str | Path, content: str) -> ValidationResult:
    normalized = _normalize_path(path)
    try:
        raw = yaml.safe_load(content) or {}
        if normalized == Path("config/system/llm.yaml"):
            validate_llm_config(raw)
        elif normalized == Path("config/system/settings.yaml"):
            validate_settings_config(raw)
    except (yaml.YAMLError, LlmSchemaError, SettingsSchemaError, ValueError) as exc:
        return ValidationResult(str(normalized), False, str(exc))
    return ValidationResult(str(normalized), True)


def _staged_paths() -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git diff --cached failed")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _staged_blob(path: str) -> str:
    result = subprocess.run(
        ["git", "show", f":{path}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"git show :{path} failed")
    return result.stdout


def _content_for_path(path: str) -> str:
    try:
        return _staged_blob(path)
    except RuntimeError:
        return Path(path).read_text(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    paths = argv if argv is not None else sys.argv[1:]
    if not paths:
        paths = _staged_paths()

    protected = [path for path in paths if is_protected_path(path)]
    if not protected:
        print("No protected system config files staged.")
        return 0

    failures: list[ValidationResult] = []
    for path in protected:
        content = _content_for_path(path)
        result = validate_blob(path, content)
        if not result.success:
            failures.append(result)

    if failures:
        print("System config schema validation failed:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure.path}: {failure.error}", file=sys.stderr)
        print(
            "Run scripts/restore_system_config.py --apply, or update the schema before "
            "changing the file shape. Use --no-verify only as a last-resort bypass.",
            file=sys.stderr,
        )
        return 1

    print("System config schema validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
