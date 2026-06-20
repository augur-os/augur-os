"""
Skill Porter Source Preparation

Handles resolving import sources from files (zip, markdown, directory)
and URLs (zip, raw markdown, git repos including GitHub tree URLs).
"""

from __future__ import annotations

import re
import shutil
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from porter_utils import (
    find_skill_md,
    choose_skill_md,
    run,
    safe_extract_zip,
    safe_mkdir,
)
from porter_markdown import parse_frontmatter


def download_url_to_file(url: str, out_path: Path, max_bytes: int = 200 * 1024 * 1024) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "augur-skill-porter"})
    with urllib.request.urlopen(req, timeout=30) as resp:  # nosec B310
        ctype = resp.headers.get("content-type", "")
        total = 0
        with out_path.open("wb") as f:
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise RuntimeError(f"Download exceeds max size ({max_bytes} bytes)")
                f.write(chunk)
        return ctype


def sniff_url_kind(url: str) -> str:
    # Fast heuristic without downloading everything.
    req = urllib.request.Request(url, headers={"User-Agent": "augur-skill-porter"})
    with urllib.request.urlopen(req, timeout=15) as resp:  # nosec B310
        ctype = (resp.headers.get("content-type") or "").lower()
        head = resp.read(8192)

    if head.startswith(b"PK\x03\x04"):
        return "zip"

    try:
        text = head.decode("utf-8", errors="ignore").lower()
    except Exception:
        text = ""

    if "text/markdown" in ctype or url.lower().endswith(".md"):
        return "markdown"

    # SKILL.md often begins with '---' frontmatter and includes 'name:'.
    if text.lstrip().startswith("---") and "name:" in text:
        return "markdown"

    # HTML pages likely indicate a repo landing page; try git clone.
    if "text/html" in ctype or "<html" in text:
        return "git"

    # Unknown: prefer git for non-obvious file URLs.
    return "git"


@dataclass(frozen=True)
class SourceContext:
    kind: str
    source_label: str
    root: Path
    skill_md: Path
    skill_root: Path


def prepare_source_from_file(file_path: Path) -> tuple[SourceContext, tempfile.TemporaryDirectory[str] | None]:
    if not file_path.exists():
        raise RuntimeError(f"File not found: {file_path}")

    tmp: tempfile.TemporaryDirectory[str] | None = None

    if file_path.is_dir():
        root = file_path
        kind = "dir"
    elif file_path.suffix.lower() == ".zip":
        tmp = tempfile.TemporaryDirectory(prefix="augur-skill-zip-")
        root = Path(tmp.name)
        safe_extract_zip(file_path, root)
        kind = "zip"
    else:
        # Assume it's a markdown file (SKILL.md).
        tmp = tempfile.TemporaryDirectory(prefix="augur-skill-md-")
        root = Path(tmp.name)
        shutil.copy2(file_path, root / "SKILL.md")
        kind = "skill_md"

    skill_md_candidates = find_skill_md(root)
    skill_md = choose_skill_md(skill_md_candidates)
    skill_root = skill_md.parent

    return (
        SourceContext(
            kind=kind,
            source_label=str(file_path),
            root=root,
            skill_md=skill_md,
            skill_root=skill_root,
        ),
        tmp,
    )


def extract_github_repo_info(url: str) -> tuple[str, str, str | None] | None:
    """Extract repo URL, branch, and subdirectory path from GitHub tree URL.

    Returns (repo_url, branch, subdirectory_path) or None if not a GitHub tree URL.
    Example: https://github.com/owner/repo/tree/branch/path/to/skill
    -> (https://github.com/owner/repo.git, branch, path/to/skill)
    """
    github_tree_pattern = re.compile(r"^https://github\.com/([\w\-\.]+)/([\w\-\.]+)/tree/([^/]+)/?(.*)$")
    match = github_tree_pattern.match(url)
    if not match:
        return None

    owner, repo, branch, subpath = match.groups()
    repo_url = f"https://github.com/{owner}/{repo}.git"
    subdirectory = subpath.strip("/") if subpath else None

    return (repo_url, branch, subdirectory)


def prepare_source_from_url(url: str) -> tuple[SourceContext, tempfile.TemporaryDirectory[str]]:
    tmp = tempfile.TemporaryDirectory(prefix="augur-skill-url-")
    root = Path(tmp.name)

    kind = sniff_url_kind(url)
    if kind == "zip":
        zip_path = root / "bundle.zip"
        download_url_to_file(url, zip_path)
        safe_extract_zip(zip_path, root / "extracted")
        root = root / "extracted"
    elif kind == "markdown":
        md_path = root / "SKILL.md"
        download_url_to_file(url, md_path, max_bytes=10 * 1024 * 1024)
    else:
        # Check if this is a GitHub tree URL (needs special handling)
        github_info = extract_github_repo_info(url)
        if github_info:
            repo_url, branch, subdirectory = github_info
            repo_dir = root / "repo"

            # Clone the repo with the specified branch
            result = run(["git", "clone", "--depth", "1", "--branch", branch, repo_url, str(repo_dir)])
            if result.returncode != 0:
                # Try without branch specification (clone default branch)
                result = run(["git", "clone", "--depth", "1", repo_url, str(repo_dir)])
            if result.returncode != 0:
                raise RuntimeError(f"Failed to clone repo: {result.stderr.strip() or result.stdout.strip()}")

            # Navigate to subdirectory if specified
            if subdirectory:
                subdir_path = repo_dir / subdirectory
                if subdir_path.exists() and subdir_path.is_dir():
                    root = subdir_path
                else:
                    # Try to find the subdirectory by searching for the last component
                    last_component = subdirectory.split("/")[-1]
                    for candidate in repo_dir.rglob(last_component):
                        if candidate.is_dir():
                            # Check if this directory contains SKILL.md
                            if (candidate / "SKILL.md").exists():
                                root = candidate
                                break
                    else:
                        # Fallback: search for SKILL.md and use its parent
                        skill_md_found = list(repo_dir.rglob("SKILL.md"))
                        if skill_md_found:
                            root = skill_md_found[0].parent
                        else:
                            root = repo_dir  # Final fallback to repo root
            else:
                root = repo_dir
        else:
            # Regular git URL
            repo_dir = root / "repo"
            result = run(["git", "clone", "--depth", "1", url, str(repo_dir)])
            if result.returncode != 0:
                raise RuntimeError(f"Failed to clone repo: {result.stderr.strip() or result.stdout.strip()}")
            root = repo_dir

    skill_md_candidates = find_skill_md(root)
    skill_md = choose_skill_md(skill_md_candidates)
    skill_root = skill_md.parent

    return (
        SourceContext(
            kind=f"url:{kind}",
            source_label=url,
            root=root,
            skill_md=skill_md,
            skill_root=skill_root,
        ),
        tmp,
    )
