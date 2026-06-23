"""Binary asset helpers and skill content matching for file operations.

This module handles:
- Magic byte validation for binary file formats
- MIME type detection
- Asset subfolder suggestions based on file extensions
- Language detection from text content
- Skill profile building and content-to-skill matching
"""

import json
import mimetypes
from pathlib import Path
from typing import Any

from src.mcp.augur_shared.config import get_skill_data_dir
from src.mcp.augur_shared.logging import get_entity_logger

logger = get_entity_logger("mcp.files")

# =============================================================================
# Binary Asset Helpers
# =============================================================================

# Magic byte signatures for common binary formats
_MAGIC_BYTES: dict[str, tuple[bytes, int]] = {
    ".png": (b"\x89PNG", 0),
    ".jpg": (b"\xff\xd8\xff", 0),
    ".jpeg": (b"\xff\xd8\xff", 0),
    ".pdf": (b"%PDF", 0),
    ".zip": (b"PK\x03\x04", 0),
    ".gif": (b"GIF8", 0),
    ".webp": (b"RIFF", 0),  # RIFF header; full check includes WEBP at offset 8
}


def _validate_asset_magic_bytes(data: bytes, extension: str) -> tuple[bool, str]:
    """
    Validate that binary data matches expected magic bytes for the file extension.

    Returns (True, "") if valid or extension not recognized.
    Returns (False, warning_message) if magic bytes don't match.
    This is advisory -- callers should log the warning but not block the write.
    """
    ext = extension.lower()
    if ext not in _MAGIC_BYTES:
        return True, ""

    expected_bytes, offset = _MAGIC_BYTES[ext]
    if len(data) < offset + len(expected_bytes):
        return False, f"File too small for {ext} format (expected at least {offset + len(expected_bytes)} bytes)"

    actual = data[offset : offset + len(expected_bytes)]
    if actual != expected_bytes:
        return False, (
            f"Magic bytes mismatch for {ext}: " f"expected {expected_bytes!r} at offset {offset}, " f"got {actual!r}"
        )

    # Extra check for WEBP: bytes 8-12 should be "WEBP"
    if ext == ".webp" and len(data) >= 12:
        if data[8:12] != b"WEBP":
            return False, f"RIFF header found but not WEBP format (bytes 8-12: {data[8:12]!r})"

    return True, ""


def _guess_mime_type(path: Path) -> str:
    """Guess MIME type from file extension, falling back to application/octet-stream.

    Normalizes platform-specific aliases (Windows' registry reports .zip as
    ``application/x-zip-compressed``) to the canonical IANA type for cross-OS parity.
    """
    mime_type, _ = mimetypes.guess_type(str(path))
    if mime_type == "application/x-zip-compressed":
        mime_type = "application/zip"
    return mime_type or "application/octet-stream"


# Extension -> asset subfolder mapping
_ASSET_SUBFOLDER_MAP: dict[str, str] = {
    # Images
    ".png": "images",
    ".jpg": "images",
    ".jpeg": "images",
    ".gif": "images",
    ".webp": "images",
    ".svg": "images",
    ".ico": "images",
    ".bmp": "images",
    # Documents / Reports
    ".pdf": "reports",
    ".docx": "reports",
    ".doc": "reports",
    ".txt": "reports",
    ".csv": "reports",
    ".xlsx": "reports",
    ".xls": "reports",
    # Presentations
    ".pptx": "presentations",
    ".ppt": "presentations",
    ".key": "presentations",
    # Video
    ".mp4": "videos",
    ".mov": "videos",
    ".avi": "videos",
    ".webm": "videos",
    # Audio
    ".mp3": "audio",
    ".wav": "audio",
    ".m4a": "audio",
    ".ogg": "audio",
    # Archives
    ".zip": "archives",
    ".tar": "archives",
    ".gz": "archives",
    ".rar": "archives",
}


def _suggest_asset_subfolder(filename: str) -> str:
    """Suggest an asset subfolder based on file extension. Returns '' if unknown."""
    ext = Path(filename).suffix.lower()
    return _ASSET_SUBFOLDER_MAP.get(ext, "")


# =============================================================================
# Skill Content Matching
# =============================================================================


def _detect_language(text: str) -> str | None:
    """Detect language from text using Unicode script ranges. Returns ISO code or None."""
    # Count characters in different script ranges
    hebrew_count = sum(1 for c in text if "\u0590" <= c <= "\u05ff")
    arabic_count = sum(1 for c in text if "\u0600" <= c <= "\u06ff")
    cjk_count = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    latin_count = sum(1 for c in text if "A" <= c <= "Z" or "a" <= c <= "z")

    total = hebrew_count + arabic_count + cjk_count + latin_count
    if total == 0:
        return None

    if hebrew_count / total > 0.3:
        return "he"
    if arabic_count / total > 0.3:
        return "ar"
    if cjk_count / total > 0.3:
        return "zh"
    if latin_count / total > 0.3:
        return "en"
    return None


def _build_skill_profiles(project_root: Path) -> list[dict[str, Any]]:
    """Build content profiles for all enabled skills by reading their metadata.

    Reads: SKILL.md frontmatter, brand-profile.json/business-profile.json,
    platform-rules.json language, data directory names, and context file keywords.

    Returns list of skill profile dicts with routing signals.
    """
    from src.config.paths import get_all_client_skill_dirs
    from src.lib.frontmatter_utils import parse_frontmatter
    from src.plugins.skill_ui_state import is_skill_enabled

    profiles: list[dict[str, Any]] = []

    for client_skills_dir in get_all_client_skill_dirs():
        for skill_dir in client_skills_dir.iterdir():
            if not skill_dir.is_dir() or skill_dir.name.startswith("."):
                continue

            if not is_skill_enabled(skill_dir.name):
                continue

            # Hubs were retired (ADR-802); skills no longer declare a bundle.
            bundle = "unknown"

            profile: dict[str, Any] = {
                "skill_name": skill_dir.name,
                "bundle": bundle,
                "keywords": [],
                "languages": [],
                "company_name": None,
                "description": "",
                "domain_dirs": [],
                "has_posts": False,
                "has_assets": False,
            }

            # 1. Read SKILL.md frontmatter for hub/config/triggers.
            skill_md = skill_dir / "SKILL.md"
            if skill_md.exists():
                try:
                    fm, body = parse_frontmatter(skill_md)
                    if isinstance(fm, dict):
                        profile["description"] = fm.get("description", "")
                        profile["keywords"].append(str(fm.get("name", "")))
                        triggers = fm.get("triggers", [])
                        if isinstance(triggers, list):
                            profile["keywords"].extend(
                                trigger.lower() for trigger in triggers if isinstance(trigger, str)
                            )
                        config = fm.get("x-augur-config", {})
                        if isinstance(config, dict):
                            contributions = config.get("contributions", {})
                            if isinstance(contributions, dict):
                                for contrib in contributions.get("actions", []):
                                    if isinstance(contrib, dict):
                                        desc = contrib.get("description", "")
                                        if isinstance(desc, str) and desc:
                                            profile["keywords"].extend(desc.lower().split()[:10])
                    content = body[:2000]
                    for line in content.split("\n"):
                        if line.startswith("**Triggers**:"):
                            triggers = line.split(":", 1)[1]
                            profile["keywords"].extend(t.strip(" `,'\"") for t in triggers.split(","))
                except Exception:
                    pass

            # 2. Read brand-profile.json or business-profile.json
            context_dir = get_skill_data_dir(skill_dir.name) / "context"
            for profile_file in ["brand-profile.json", "business-profile.json"]:
                bp_path = context_dir / profile_file
                if bp_path.exists():
                    try:
                        bp = json.loads(bp_path.read_text())
                        if isinstance(bp, dict):
                            company = bp.get("company_name") or bp.get("company", "")
                            if company:
                                profile["company_name"] = company
                                profile["keywords"].append(company.lower())
                            tagline = bp.get("tagline", "")
                            if tagline:
                                profile["keywords"].extend(tagline.lower().split()[:8])
                            audience = bp.get("target_audience", "")
                            if audience:
                                profile["keywords"].extend(audience.lower().split()[:8])
                            # Offerings / differentiators
                            for key in ["offerings", "differentiators"]:
                                for item in bp.get(key, []):
                                    if isinstance(item, str):
                                        profile["keywords"].extend(item.lower().split()[:5])
                    except Exception:
                        pass

            # 3. Read platform-rules.json for language
            pr_path = context_dir / "platform-rules.json"
            if pr_path.exists():
                try:
                    pr = json.loads(pr_path.read_text())
                    if isinstance(pr, dict):
                        for platform_cfg in pr.values():
                            if isinstance(platform_cfg, dict):
                                lang = platform_cfg.get("language")
                                if lang and lang not in profile["languages"]:
                                    profile["languages"].append(lang)
                except Exception:
                    pass

            # 4. Scan data directory names for domain signals
            data_dir = get_skill_data_dir(skill_dir.name)
            if data_dir.exists():
                for d in data_dir.iterdir():
                    if d.is_dir() and not d.name.startswith("."):
                        profile["domain_dirs"].append(d.name)
                        profile["keywords"].append(d.name)

            # 5. Check for posts directory (content-producing skill)
            posts_dir = data_dir / "posts" if data_dir.exists() else None
            if posts_dir and posts_dir.exists():
                profile["has_posts"] = True

            # 6. Check for assets directory
            assets_dir = skill_dir / "assets"
            if assets_dir.exists():
                profile["has_assets"] = True

            # Deduplicate and clean keywords
            cleaned = []
            seen: set[str] = set()
            for kw in profile["keywords"]:
                kw = kw.strip().lower()
                if kw and len(kw) > 2 and kw not in seen:
                    seen.add(kw)
                    cleaned.append(kw)
            profile["keywords"] = cleaned

            profiles.append(profile)

    return profiles


def _score_skill_match(
    profile: dict[str, Any],
    content_snippet: str,
    content_language: str | None,
    filename: str | None,
) -> float:
    """Score how well a skill profile matches the given content.

    Returns a score from 0.0 to 1.0.
    """
    score = 0.0
    content_lower = content_snippet.lower()
    content_words = set(content_lower.split())

    # 1. Language match (strong signal, +0.3)
    if content_language and profile["languages"]:
        if content_language in profile["languages"]:
            score += 0.3

    # 2. Company name match (very strong, +0.3)
    if profile["company_name"]:
        company_lower = profile["company_name"].lower()
        if company_lower in content_lower:
            score += 0.3

    # 3. Keyword overlap (up to +0.25)
    if profile["keywords"]:
        keyword_hits = sum(1 for kw in profile["keywords"] if kw in content_lower)
        keyword_ratio = min(keyword_hits / max(len(profile["keywords"]), 1), 1.0)
        score += keyword_ratio * 0.25

    # 4. Content-producing skill bonus (+0.1)
    if profile["has_posts"]:
        score += 0.1

    # 5. Domain directory relevance (+0.05 per match)
    for domain in profile["domain_dirs"]:
        if domain.lower() in content_words:
            score += 0.05

    return min(score, 1.0)


def match_content_to_skill_impl(
    content_snippet: str,
    filename: str | None = None,
    content_language: str | None = None,
) -> list[dict[str, Any]]:
    """Match content to the best skill based on metadata profiles.

    Returns ranked list of skill matches with scores.
    """
    from src.config.paths import get_project_root

    project_root = get_project_root()

    # Auto-detect language if not provided
    if not content_language:
        content_language = _detect_language(content_snippet)

    profiles = _build_skill_profiles(project_root)

    # Score each profile
    results: list[dict[str, Any]] = []
    for profile in profiles:
        score = _score_skill_match(profile, content_snippet, content_language, filename)
        if score > 0.05:  # Only include meaningful matches
            results.append(
                {
                    "skill_name": profile["skill_name"],
                    "bundle": profile["bundle"],
                    "score": round(score, 3),
                    "company_name": profile["company_name"],
                    "description": profile["description"],
                    "languages": profile["languages"],
                    "has_posts": profile["has_posts"],
                    "has_assets": profile["has_assets"],
                    "matched_language": content_language in (profile["languages"] or []) if content_language else False,
                }
            )

    # Sort by score descending
    results.sort(key=lambda x: x["score"], reverse=True)

    return results[:5]  # Top 5 matches
