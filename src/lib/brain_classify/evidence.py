"""Deterministic brain-evidence extraction (spec 2026-06-13).

Decides which brain a knowledge file is ABOUT by tallying references to each
brain's artifacts (wiki [[links]] + path-like tokens). Zero LLM calls. Shared by
the one-time classifier, the wiki/memory write-time routers, and crossbrain_lint.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# Order matters: PERSONAL is checked first so 'project-brain/.../skills/<private>'
# never wins on the bare 'skills' token. Patterns are matched against link
# targets and path-like tokens, case-insensitively.
PERSONAL_PATTERNS = (
    r"au-vault\b",
    r"au-docs\b",
    r"projects/au-vault",
    r"private-vault skill",
    r"\bcareer/",
    r"\bhealth/",
    r"\bfinance/",
    r"\bventure/",
    r"\blifestyle/",
    r"\bbooks/",
    r"\bprofile/",
    r"\bresume",
    r"\brecipe",
    r"canonical-facts",
    r"\binterview\b",
    r"resume-no-founder",
    r"canonical-resumes",
)
PROJECT_PATTERNS = (
    r"project-brain/",
    r"\bsrc/",
    r"\bapps/",
    r"\bconfig/",
    r"\.github/",
    r"\bscripts/",
    r"augur_core",
    r"augur_framework",
    r"\bdashboard\b",
    r"\bmcp\b",
    r"\bdaemon\b",
    r"\badr-\d",
    r"\.claude/",
)

_LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
# Path-ish tokens: at least one slash, no whitespace, optionally backtick-wrapped.
_PATH_RE = re.compile(r"`?([A-Za-z0-9_.~][A-Za-z0-9_./~-]*/[A-Za-z0-9_./~-]*)`?")


@dataclass(frozen=True)
class BrainEvidence:
    project_refs: int
    personal_refs: int
    subject_brain: str  # "project" | "personal" | "ambiguous"
    signals: tuple[str, ...] = field(default_factory=tuple)


def _classify_token(token: str) -> str | None:
    low = token.lower()
    for pat in PERSONAL_PATTERNS:
        if re.search(pat, low):
            return "personal"
    for pat in PROJECT_PATTERNS:
        if re.search(pat, low):
            return "project"
    return None


def _strip_frontmatter(text: str) -> str:
    """Drop a leading --- YAML frontmatter block.

    Frontmatter holds provenance (`_sources`/`_mentions` citation lists) that
    reflects where a page was compiled FROM, not what it is ABOUT. Brain subject
    must come from the body, so a project page that cites vault sources is not
    misclassified as personal.
    """
    norm = text.replace("\r\n", "\n")
    if not norm.startswith("---\n"):
        return text
    end = norm.find("\n---", 4)
    if end == -1:
        return text
    return norm[end + 4 :]


# Citation-scheme link/token prefixes are provenance, not subject.
_CITATION_SCHEMES = ("vault:", "adr:", "url:", "source-card:", "action:", "page:", "http")


def extract_brain_evidence(path: Path) -> BrainEvidence:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        text = ""
    body = _strip_frontmatter(text)
    link_tokens = [m.group(1) for m in _LINK_RE.finditer(body)]
    # Remove [[...]] spans so _PATH_RE doesn't re-count paths nested inside a
    # citation link (e.g. [[vault:/Users/.../Au-vault/...]]).
    body_no_links = _LINK_RE.sub(" ", body)
    raw_tokens: list[str] = link_tokens + [m.group(1) for m in _PATH_RE.finditer(body_no_links)]
    tokens = [t for t in raw_tokens if not t.lower().lstrip("`'\"").startswith(_CITATION_SCHEMES)]

    project = personal = 0
    signals: list[str] = []
    seen: set[str] = set()
    for tok in tokens:
        verdict = _classify_token(tok)
        if verdict is None:
            continue
        if verdict == "project":
            project += 1
        else:
            personal += 1
        if tok not in seen:
            seen.add(tok)
            signals.append(f"{verdict}: {tok}")

    if project == 0 and personal == 0:
        subject = "ambiguous"
    elif project >= personal * 2 and project > personal:
        subject = "project"
    elif personal >= project * 2 and personal > project:
        subject = "personal"
    elif project > personal:
        subject = "project"
    elif personal > project:
        subject = "personal"
    else:
        subject = "ambiguous"

    return BrainEvidence(
        project_refs=project,
        personal_refs=personal,
        subject_brain=subject,
        signals=tuple(signals),
    )
