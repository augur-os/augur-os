"""S3: Static code analysis for dangerous patterns in skill scripts."""
from __future__ import annotations

import ast
import re
from pathlib import Path

# Dangerous patterns for shell scripts
_SHELL_DANGEROUS = [
    (re.compile(r"\beval\s+['\"]", re.IGNORECASE), "eval usage", "critical"),
    (re.compile(r"`[^`]+`", re.IGNORECASE), "backtick command substitution", "high"),
    (re.compile(r"\bcurl\s+.*\|\s*(bash|sh|zsh)\b", re.IGNORECASE), "curl pipe to shell", "critical"),
    (re.compile(r"\bwget\s+.*\|\s*(bash|sh|zsh)\b", re.IGNORECASE), "wget pipe to shell", "critical"),
    (re.compile(r"\brm\s+-rf\s+[/~]", re.IGNORECASE), "dangerous rm -rf", "critical"),
]

# Hardcoded http(s):// literal — bandit B310 false-positive suppression
_HARDCODED_URL_RE = re.compile(r"""['"]https?://[^'"]+['"]""")


def _is_test_file(file_path: Path) -> bool:
    """True if file is part of a test suite (path or filename convention)."""
    if "tests" in file_path.parts:
        return True
    name = file_path.name
    if name.startswith("test_") or name.endswith("_test.py"):
        return True
    return False


def _line_has_hardcoded_url(file_path: Path, line_no: int) -> bool:
    """True if the file's line_no contains a hardcoded http(s):// literal."""
    if line_no <= 0:
        return False
    try:
        lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return False
    if line_no > len(lines):
        return False
    return bool(_HARDCODED_URL_RE.search(lines[line_no - 1]))


def _scan_python_with_bandit(file_path: Path) -> list[dict]:
    """Try bandit if available."""
    try:
        import bandit.core.config as bandit_config
        import bandit.core.manager as bandit_manager
    except ImportError:
        return []

    findings = []
    try:
        b_conf = bandit_config.BanditConfig()
        b_mgr = bandit_manager.BanditManager(b_conf, "file", [str(file_path)])
        b_mgr.discover_files([str(file_path)], True)
        b_mgr.run_tests()
        is_test = _is_test_file(file_path)
        for issue in b_mgr.get_issue_list():
            sev = issue.severity.lower()
            # Skip low-confidence / low-severity noise (e.g., B110 try-except-pass)
            if sev not in ("medium", "high", "critical"):
                continue
            # B108: insecure /tmp paths in test fixtures are not exploitable
            if issue.test_id == "B108" and is_test:
                continue
            # B310: hardcoded http(s):// literals are not the urlopen-on-untrusted-input risk
            if issue.test_id == "B310" and _line_has_hardcoded_url(file_path, issue.lineno):
                continue
            findings.append({
                "stage": "S3",
                "category_name": f"bandit-{issue.test_id}",
                "severity": sev,
                "file": str(file_path.name),
                "line": issue.lineno,
                "message": issue.text,
                "pattern": issue.test_id,
            })
    except Exception:
        pass
    return findings


_SUPPRESS_RE = re.compile(r"#\s*(?:nosec(?:\s+B\d+)?|noqa:\s*S\d+)\b", re.IGNORECASE)


def _line_is_suppressed(source_lines: list[str], line_no: int) -> bool:
    """True if the line carries a # nosec or # noqa: S### suppression."""
    if line_no <= 0 or line_no > len(source_lines):
        return False
    return bool(_SUPPRESS_RE.search(source_lines[line_no - 1]))


def _scan_python_native(file_path: Path, skill_dir: Path) -> list[dict]:
    """Native AST-based scan for dangerous Python patterns."""
    findings = []
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (SyntaxError, OSError, UnicodeDecodeError):
        return findings
    source_lines = source.splitlines()

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func_name = ""
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr

            dangerous = {
                "eval": ("eval() call", "critical"),
                "exec": ("exec() call", "critical"),
            }
            if func_name in dangerous:
                desc, sev = dangerous[func_name]
                lineno = getattr(node, "lineno", 0)
                if _line_is_suppressed(source_lines, lineno):
                    continue
                findings.append({
                    "stage": "S3",
                    "category_name": desc,
                    "severity": sev,
                    "file": str(file_path.relative_to(skill_dir)),
                    "line": lineno,
                    "message": desc,
                    "pattern": func_name,
                })

            # Check subprocess.run with shell=True
            if (func_name == "run" and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "subprocess"):
                has_shell_true = False
                shell_kw_lineno = 0
                for kw in node.keywords:
                    if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                        has_shell_true = True
                        shell_kw_lineno = getattr(kw.value, "lineno", getattr(node, "lineno", 0))
                if has_shell_true:
                    call_lineno = getattr(node, "lineno", 0)
                    # Suppression may be on the shell=True line OR on the call line
                    if (_line_is_suppressed(source_lines, shell_kw_lineno)
                            or _line_is_suppressed(source_lines, call_lineno)):
                        continue
                    findings.append({
                        "stage": "S3",
                        "category_name": "subprocess-shell-true",
                        "severity": "medium",
                        "file": str(file_path.relative_to(skill_dir)),
                        "line": call_lineno,
                        "message": "subprocess.run() with shell=True — review for injection risk",
                        "pattern": "subprocess.run(..., shell=True)",
                    })
    return findings


def _scan_shell(file_path: Path, skill_dir: Path) -> list[dict]:
    """Scan shell scripts for dangerous patterns."""
    findings = []
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception:
        return findings
    lines = content.splitlines()
    for pattern, label, severity in _SHELL_DANGEROUS:
        for line_no, line in enumerate(lines, 1):
            if pattern.search(line):
                findings.append({
                    "stage": "S3",
                    "category_name": label,
                    "severity": severity,
                    "file": str(file_path.relative_to(skill_dir)),
                    "line": line_no,
                    "message": f"{label} in shell script",
                    "pattern": pattern.pattern[:80],
                    "snippet": line.strip()[:120],
                })
    return findings


def scan_skill(skill_dir: Path) -> list[dict]:
    """Scan a skill directory for dangerous code patterns."""
    findings = []
    for file_path in skill_dir.rglob("*"):
        if not file_path.is_file() or ".git" in file_path.parts:
            continue
        if file_path.suffix == ".py":
            findings.extend(_scan_python_with_bandit(file_path))
            findings.extend(_scan_python_native(file_path, skill_dir))
        elif file_path.suffix in {".sh", ".bash", ".zsh"}:
            findings.extend(_scan_shell(file_path, skill_dir))
    return findings
