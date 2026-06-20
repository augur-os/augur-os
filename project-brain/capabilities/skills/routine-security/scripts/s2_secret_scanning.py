"""S2: Secret scanning for skill scripts and instruction files."""
from __future__ import annotations

import re
from pathlib import Path

# Custom regex for skill-specific secrets
_CUSTOM_PATTERNS = [
    # Specific high-confidence API key / credential formats only.
    # Avoid generic variable-name heuristics (password=, token=) which
    # produce false positives in config-driven personal automation code.
    ("AWS Access Key ID", re.compile(r"AKIA[0-9A-Z]{16}", re.IGNORECASE), "critical"),
    ("GitHub Token", re.compile(r"gh[pousr]_[A-Za-z0-9_]{36,}", re.IGNORECASE), "critical"),
    ("OpenAI API Key", re.compile(r"sk-[a-zA-Z0-9]{48}", re.IGNORECASE), "critical"),
    ("Anthropic API Key", re.compile(r"sk-ant-[a-zA-Z0-9-]{40,}", re.IGNORECASE), "critical"),
    ("Private Key", re.compile(r"-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"), "critical"),
    ("Connection String", re.compile(r"(postgres|mysql|mongodb|redis)://[^:]+:[^@]+@", re.IGNORECASE), "high"),
]


def _scan_with_detect_secrets(skill_dir: Path) -> list[dict]:
    """Try to use detect-secrets if available."""
    try:
        from detect_secrets.core.secrets_collection import SecretsCollection
    except ImportError:
        return []

    findings = []
    try:
        collection = SecretsCollection()
        for file_path in skill_dir.rglob("*"):
            if not file_path.is_file() or ".git" in file_path.parts:
                continue
            try:
                collection.scan_file(str(file_path))
            except Exception:
                continue
        for secret in collection:
            findings.append({
                "stage": "S2",
                "category_name": "detect-secrets",
                "severity": "high",
                "file": str(Path(secret.filename).relative_to(skill_dir)),
                "line": secret.line_number,
                "message": f"{secret.type}: {secret.secret_hash[:8]}...",
                "pattern": secret.type,
            })
    except Exception:
        pass
    return findings


def scan_skill(skill_dir: Path) -> list[dict]:
    """Scan a skill directory for secrets."""
    findings = []

    # Try detect-secrets first
    ds_findings = _scan_with_detect_secrets(skill_dir)
    findings.extend(ds_findings)

    # Fallback: custom regex
    for file_path in skill_dir.rglob("*"):
        if not file_path.is_file() or ".git" in file_path.parts:
            continue
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception:
            continue
        lines = content.splitlines()
        for label, pattern, severity in _CUSTOM_PATTERNS:
            for line_no, line in enumerate(lines, 1):
                if pattern.search(line):
                    # Skip if detect-secrets already found something on this line
                    if any(f["file"] == str(file_path.relative_to(skill_dir)) and f["line"] == line_no for f in ds_findings):
                        continue
                    findings.append({
                        "stage": "S2",
                        "category_name": label,
                        "severity": severity,
                        "file": str(file_path.relative_to(skill_dir)),
                        "line": line_no,
                        "message": f"{label} detected",
                        "pattern": pattern.pattern[:80],
                        "snippet": line.strip()[:120],
                    })
    return findings
