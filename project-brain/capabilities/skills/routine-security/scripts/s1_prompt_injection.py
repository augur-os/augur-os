"""S1: Prompt injection detection for skill instruction files."""
from __future__ import annotations

import json
import re
from pathlib import Path

PATTERNS_PATH = Path(__file__).parent.parent / "references" / "injection-patterns.json"


def _load_patterns() -> list[dict]:
    if not PATTERNS_PATH.exists():
        return []
    data = json.loads(PATTERNS_PATH.read_text(encoding="utf-8"))
    return data.get("categories", [])


def _is_pattern_reference_file(file_path: Path) -> bool:
    """True if the file is the scanner's own pattern definition.

    The patterns file naturally contains the strings the scanner is looking for;
    matching it produces self-flagging false positives.
    """
    if file_path.name == "injection-patterns.json":
        return True
    try:
        return file_path.resolve() == PATTERNS_PATH.resolve()
    except OSError:
        return False


def scan_skill(skill_dir: Path) -> list[dict]:
    """Scan a skill directory for prompt injection patterns."""
    findings = []
    categories = _load_patterns()
    if not categories:
        return findings

    # Files to scan
    scan_extensions = {".md", ".txt", ".yaml", ".yml", ".json"}
    for file_path in skill_dir.rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in scan_extensions:
            continue
        if ".git" in file_path.parts:
            continue
        if _is_pattern_reference_file(file_path):
            continue

        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception:
            continue

        lines = content.splitlines()
        for cat in categories:
            for pattern_str in cat.get("patterns", []):
                try:
                    pattern = re.compile(pattern_str, re.IGNORECASE)
                except re.error:
                    continue
                for line_no, line in enumerate(lines, 1):
                    if pattern.search(line):
                        findings.append({
                            "stage": "S1",
                            "category_id": cat["id"],
                            "category_name": cat["name"],
                            "severity": cat["severity"],
                            "file": str(file_path.relative_to(skill_dir)),
                            "line": line_no,
                            "message": f"{cat['name']}: matched pattern '{pattern_str}'",
                            "pattern": pattern_str,
                            "snippet": line.strip()[:120],
                        })
    return findings
