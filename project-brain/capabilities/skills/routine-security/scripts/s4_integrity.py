"""S4: Integrity and trust checks for skill manifests and contents."""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import yaml

_ASQ_SCRIPTS = Path(__file__).resolve().parents[2] / "auto-skill-quality" / "scripts"
if str(_ASQ_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_ASQ_SCRIPTS))
from standard_skill_contract import is_standard_core  # noqa: E402

# x-augur-hub removed: ADR-802 deleted the field and the hub concept entirely.
REQUIRED_FRONTMATTER_FIELDS = {
    "name",
    "x-augur-type",
    "description",
}


def _compute_tree_hash(skill_dir: Path) -> str:
    """Compute a deterministic SHA-256 hash of all files in the skill."""
    hasher = hashlib.sha256()
    for file_path in sorted(skill_dir.rglob("*")):
        if not file_path.is_file():
            continue
        if ".git" in file_path.parts:
            continue
        rel = str(file_path.relative_to(skill_dir))
        hasher.update(rel.encode("utf-8"))
        try:
            hasher.update(file_path.read_bytes())
        except Exception:
            pass
    return hasher.hexdigest()[:16]


def scan_skill(skill_dir: Path, is_augur_managed: bool = True) -> list[dict]:
    """Scan a skill directory for integrity issues.

    Args:
        skill_dir: Path to the skill directory.
        is_augur_managed: If True, enforce Augur-specific frontmatter requirements.
            External skills (tier>=1) should pass False to avoid false positives.
    """
    findings = []
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        findings.append({
            "stage": "S4",
            "category_name": "missing-manifest",
            "severity": "critical",
            "file": "SKILL.md",
            "line": 0,
            "message": "SKILL.md manifest is missing",
            "pattern": "SKILL.md existence",
        })
        return findings

    # Parse frontmatter
    try:
        content = skill_md.read_text(encoding="utf-8")
        if content.startswith("---"):
            end = content.index("---", 3)
            fm = yaml.safe_load(content[3:end])
        else:
            fm = {}
    except Exception as e:
        findings.append({
            "stage": "S4",
            "category_name": "invalid-frontmatter",
            "severity": "high",
            "file": "SKILL.md",
            "line": 0,
            "message": f"Invalid YAML frontmatter: {e}",
            "pattern": "YAML parse",
        })
        return findings

    if not isinstance(fm, dict):
        fm = {}

    # Only enforce Augur-specific frontmatter on managed skills — but NOT on
    # portable ADR-040 standard cores, which omit Augur frontmatter by design.
    if is_augur_managed and not is_standard_core(skill_dir):
        # Check required fields
        missing = REQUIRED_FRONTMATTER_FIELDS - set(fm.keys())
        if missing:
            findings.append({
                "stage": "S4",
                "category_name": "incomplete-manifest",
                "severity": "medium",
                "file": "SKILL.md",
                "line": 0,
                "message": f"Missing required frontmatter fields: {', '.join(missing)}",
                "pattern": "required fields",
            })

        # Check x-augur-license
        if not fm.get("x-augur-license"):
            findings.append({
                "stage": "S4",
                "category_name": "missing-license",
                "severity": "low",
                "file": "SKILL.md",
                "line": 0,
                "message": "No x-augur-license declared",
                "pattern": "license",
            })

    # Compute tree hash
    tree_hash = _compute_tree_hash(skill_dir)
    findings.append({
        "stage": "S4",
        "category_name": "tree-hash",
        "severity": "info",
        "file": "SKILL.md",
        "line": 0,
        "message": f"Tree SHA: {tree_hash}",
        "pattern": "integrity",
        "tree_hash": tree_hash,
    })

    return findings
