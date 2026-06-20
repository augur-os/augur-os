#!/usr/bin/env python3
"""
Repository Health Audit Script
Checks the repository against open source best practices as defined in modules/repo-health.md.
Includes benchmarking against industry standards (Bronze, Silver, Gold tiers).
"""

import os
import sys
import yaml
import re
from shutil import which
from subprocess import run as subprocess_run  # nosec B404
from pathlib import Path
from datetime import datetime

# Add project root to path to allow imports if needed
from bootstrap_paths import ensure_project_paths  # noqa: E402

project_root = ensure_project_paths(__file__)

TIERS = {
    "Bronze": {
        "description": "Functional foundation",
        "requirements": ["license", "readme_badges", "description", "installation"],
    },
    "Silver": {
        "description": "Contributor ready",
        "requirements": ["contributing", "code_of_conduct", "ci_cd", "tests", "usage_examples", "tags"],
    },
    "Gold": {
        "description": "Community gold standard",
        "requirements": ["security", "funding", "social_preview", "changelog", "semver_tags"],
    },
}


def check_file_exists(path_list):
    """Check if any of the files in the list exist relative to project root."""
    for path in path_list:
        if (project_root / path).exists():
            return True
    return False


def check_content_contains(path, search_term):
    """Check if file exists and contains the search term."""
    full_path = project_root / path
    if not full_path.exists():
        return False
    try:
        content = full_path.read_text(encoding='utf-8')
        return search_term.lower() in content.lower()
    except Exception:
        return False


def check_git_attributes():
    """Check git specific attributes like tags."""
    results = {"tags": False, "semver_tags": False, "latest_tag": None}

    try:
        git_cmd = which("git") or "git"
        # Check for any tags
        tags_proc = subprocess_run(  # nosec B603
            [git_cmd, "tag"],
            cwd=project_root,
            capture_output=True,
            text=True,
        )
        if tags_proc.stdout.strip():
            results["tags"] = True

            # Check for semver tags (v1.0.0 or 1.0.0)
            tags = tags_proc.stdout.strip().split('\n')
            semver_regex = re.compile(r'^v?\d+\.\d+\.\d+')
            semver_tags = [t for t in tags if semver_regex.match(t)]

            if semver_tags:
                results["semver_tags"] = True
                # simple sort (not true semver sort but sufficient for audit check)
                results["latest_tag"] = sorted(semver_tags)[-1]

    except Exception as e:
        sys.stderr.write(f"Warning: git check failed: {e}\n")

    return results


def get_tier_ranking(audit_results):
    """Calculate the current tier and next steps."""
    # Flatten results for easy checking
    all_checks = {}
    for category in ["documentation", "community", "project_health", "discoverability", "release"]:
        if category in audit_results:
            all_checks.update(audit_results[category])

    # Check tiers in order
    for tier_name in ["Bronze", "Silver", "Gold"]:
        gaps = [req for req in TIERS[tier_name]["requirements"] if all_checks.get(req) != "pass"]
        if gaps:
            return tier_name if tier_name == "Bronze" else ("Bronze" if tier_name == "Silver" else "Silver"), [
                {"tier": tier_name, "missing": gaps}
            ]

    return "Gold", []


def _audit_documentation() -> tuple[dict, int]:
    """Audit documentation files. Returns (results, score)."""
    score = 0
    results = {}

    # README with badges
    has_readme = check_file_exists(["README.md"])
    has_badges = check_content_contains("README.md", "shields.io") if has_readme else False
    results["readme_badges"] = "pass" if has_badges else ("plain_readme" if has_readme else "fail")
    score += 5 if has_badges else (2 if has_readme else 0)

    # Installation instructions
    has_install = check_content_contains("README.md", "installation") or check_content_contains(
        "README.md", "getting started"
    )
    results["installation"] = "pass" if has_install else "fail"
    score += 5 if has_install else 0

    # Usage examples
    has_usage = (
        check_content_contains("README.md", "usage")
        or check_content_contains("README.md", "example")
        or check_content_contains("README.md", "```bash")
    )
    results["usage_examples"] = "pass" if has_usage else "fail"
    score += 5 if has_usage else 0

    # API documentation
    has_docs_dir = (project_root / "docs").is_dir() or (project_root / "documentation").is_dir()
    has_api_section = check_content_contains("README.md", "api")
    results["api_docs"] = "pass" if (has_docs_dir or has_api_section) else "warn"
    score += 5 if (has_docs_dir or has_api_section) else 0

    # Architecture diagram
    has_arch_diagram = (
        check_content_contains("README.md", "architecture")
        or check_content_contains("README.md", ".png")
        or check_content_contains("README.md", ".svg")
        or check_content_contains("README.md", "mermaid")
    )
    results["architecture"] = "pass" if has_arch_diagram else "warn"
    score += 5 if has_arch_diagram else 0

    # Contributing guide
    has_contributing = check_file_exists(["CONTRIBUTING.md", "docs/CONTRIBUTING.md", ".github/CONTRIBUTING.md"])
    results["contributing"] = "pass" if has_contributing else "fail"
    score += 5 if has_contributing else 0

    return results, score


def _audit_community() -> tuple[dict, int]:
    """Audit community files. Returns (results, score)."""
    score = 0
    results = {}

    # License
    has_license = check_file_exists(["LICENSE", "LICENSE.txt", "LICENSE.md"])
    results["license"] = "pass" if has_license else "fail"
    score += 5 if has_license else 0

    # Code of Conduct
    has_coc = check_file_exists(["CODE_OF_CONDUCT.md", "docs/CODE_OF_CONDUCT.md", ".github/CODE_OF_CONDUCT.md"])
    results["code_of_conduct"] = "pass" if has_coc else "fail"
    score += 5 if has_coc else 0

    # Security Policy
    has_security = check_file_exists(["SECURITY.md", "docs/SECURITY.md", ".github/SECURITY.md"])
    results["security"] = "pass" if has_security else "fail"
    score += 5 if has_security else 0

    # Funding
    has_funding = check_file_exists(["FUNDING.yml", ".github/FUNDING.yml"])
    results["funding"] = "pass" if has_funding else "warn"
    score += 5 if has_funding else 0

    return results, score


def _audit_project_health() -> tuple[dict, int]:
    """Audit project health. Returns (results, score)."""
    score = 0
    results = {}

    # CI/CD Configured
    has_cicd = (project_root / ".github" / "workflows").is_dir()
    results["ci_cd"] = "pass" if has_cicd else "fail"
    score += 10 if has_cicd else 0

    # Tests Exist
    has_tests = False
    for root, dirs, files in os.walk(project_root):
        if "node_modules" in root or ".git" in root:
            continue
        for file in files:
            if "test" in file.lower() and (file.endswith(".py") or file.endswith(".js") or file.endswith(".ts")):
                has_tests = True
                break
        if has_tests:
            break

    results["tests"] = "pass" if has_tests else "fail"
    score += 10 if has_tests else 0

    # Stale issues (Placeholder)
    results["stale_issues"] = "pass"
    score += 5

    # Live Demo
    has_demo = check_content_contains("README.md", "demo") or check_content_contains("README.md", "live site")
    results["demo"] = "pass" if has_demo else "warn"
    score += 5 if has_demo else 0

    return results, score


def _audit_discoverability() -> tuple[dict, int]:
    """Audit discoverability. Returns (results, score)."""
    score = 0
    results = {}

    # Topics/Tags
    has_keywords = check_content_contains("package.json", "keywords") or check_content_contains(
        "pyproject.toml", "keywords"
    )
    results["topics"] = "pass" if has_keywords else "warn"
    score += 5 if has_keywords else 0

    # Description
    has_readme = check_file_exists(["README.md"])
    has_desc = False
    if has_readme:
        readme_len = len((project_root / "README.md").read_text(encoding='utf-8'))
        has_desc = readme_len > 100
    results["description"] = "pass" if has_desc else "fail"
    score += 5 if has_desc else 0

    # Social Preview
    has_social_img = check_file_exists([".github/social_preview.png", "docs/social_preview.png", "assets/social.png"])
    results["social_preview"] = "pass" if has_social_img else "fail"
    score += 5 if has_social_img else 0

    # Website Link
    has_website = check_content_contains("README.md", "http")
    results["website"] = "pass" if has_website else "warn"
    score += 5 if has_website else 0

    return results, score


def _audit_release(git_stats: dict) -> dict:
    """Audit release management. Returns results dict."""
    results = {}
    results["tags"] = "pass" if git_stats["tags"] else "warn"
    results["semver_tags"] = "pass" if git_stats["semver_tags"] else "warn"

    # Changelog
    has_changelog = check_file_exists(["CHANGELOG.md", "docs/CHANGELOG.md"])
    results["changelog"] = "pass" if has_changelog else "fail"

    return results


def _generate_recommendations(
    docs_results: dict, community_results: dict, discovery_results: dict, release_results: dict
) -> list:
    """Generate recommendations based on audit results."""
    recommendations = []

    checks = [
        (docs_results.get("readme_badges"), "Add status badges (CI, License) to README.md"),
        (docs_results.get("contributing"), "Create CONTRIBUTING.md guide"),
        (community_results.get("license"), "Add LICENSE file (MIT recommended)"),
        (community_results.get("code_of_conduct"), "Create CODE_OF_CONDUCT.md"),
        (community_results.get("security"), "Create SECURITY.md policy"),
        (discovery_results.get("social_preview"), "Add validation social preview image"),
        (release_results.get("semver_tags"), "Create a git tag for your current version (e.g. v0.1.0 or v1.0.0)"),
        (release_results.get("changelog"), "Create CHANGELOG.md to track version history"),
    ]

    for status, recommendation in checks:
        if status != "pass":
            recommendations.append(recommendation)

    return recommendations


def run_audit(dry_run=False):
    """Run the repository health audit."""
    audit_date = datetime.now().strftime("%Y-%m-%d")
    git_stats = check_git_attributes()

    # Run all audits
    docs_results, docs_score = _audit_documentation()
    community_results, community_score = _audit_community()
    health_results, health_score = _audit_project_health()
    discovery_results, discovery_score = _audit_discoverability()
    release_results = _audit_release(git_stats)

    # Total Score
    total_score = docs_score + community_score + health_score + discovery_score

    # Generate Recommendations
    recommendations = _generate_recommendations(docs_results, community_results, discovery_results, release_results)

    # Benchmarking & Gap Analysis
    audit_data_for_ranking = {
        "documentation": docs_results,
        "community": community_results,
        "project_health": health_results,
        "discoverability": discovery_results,
        "release": release_results,
    }

    current_tier, gaps = get_tier_ranking(audit_data_for_ranking)

    # findings count
    fail_count = str(audit_data_for_ranking).count("fail")
    warn_count = str(audit_data_for_ranking).count("warn")

    report_data = {
        "audit_date": audit_date,
        "repository": "augur",
        "score": f"{total_score}/100",
        "tier": current_tier,
        "documentation": docs_results,
        "community": community_results,
        "project_health": health_results,
        "discoverability": discovery_results,
        "release": release_results,
        "benchmarking": {"current_tier": current_tier, "latest_tag": git_stats["latest_tag"], "gap_analysis": gaps},
        "recommendations": recommendations,
        "summary": {
            "findings_count": fail_count + warn_count,
            "critical": 0,
            "high": fail_count,
            "medium": warn_count,
            "low": 0,
        },
    }

    report_path = None
    if not dry_run:
        # Save generated audit output in runtime state, not the user-editable vault.
        from src.config.paths import get_runtime_dir

        data_dir = get_runtime_dir() / "platform-admin"
        data_dir.mkdir(parents=True, exist_ok=True)
        report_path = data_dir / "repo_health.yaml"
        with open(report_path, "w") as f:
            yaml.dump(report_data, f, default_flow_style=False)
        report_data["report_path"] = str(report_path)

    return {
        "success": True,
        "summary": report_data["summary"],
        "report_path": str(report_path) if report_path else None,
        "data": report_data,
    }


if __name__ == "__main__":
    result = run_audit()
    sys.stdout.write(yaml.dump(result["data"], default_flow_style=False))
