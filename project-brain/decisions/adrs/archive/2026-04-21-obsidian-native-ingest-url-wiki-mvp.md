# Obsidian-Native Ingest URL Wiki MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an obvious `/ingest-url` path that saves URL source cards into the vault, routes them by existing Augur hubs and skills, exposes the same flow in the dashboard, and promotes the staged Obsidian skill as the MVP native wiki/vault UX layer.

**Architecture:** Keep MCP tools deterministic and atomic: `ingest-url` validates, extracts, classifies, writes one source card, and returns structured status. Agents own summary refinement and wiki compilation through the existing concept-first compiler; dashboard code only calls MCP and dispatches IDE actions when compilation is requested. Obsidian support is promoted as a self-contained skill, not centralized registry data.

**Tech Stack:** Python 3.11, pytest, FastMCP-style Augur MCP registration, Next.js dashboard TypeScript, `src.lib.frontmatter_utils.write_frontmatter`, Augur skill frontmatter discovery, existing `sync_agents` generated client surfaces.

---

## Source Spec

Implement against `docs/superpowers/specs/2026-04-21-obsidian-native-ingest-url-wiki-mvp-design.md`.

Key decisions from the spec:

- Default URL source card location: `Au-vault/sources/web/`.
- One markdown file per URL, with YAML frontmatter and Obsidian callouts.
- Deterministic classification uses current `skills/*/SKILL.md` metadata, plus the promoted/staged Obsidian skill during transition.
- `ingest-url` is a wrapper over existing ingest/extraction machinery, not a second ingest pipeline.
- Compiled `wiki/concepts/*` and `wiki/queries/*` pages are only written by the concept-first wiki compiler.
- Dashboard must use MCP (`mcpCall` or `useMcpMutation`) and must not call Python scripts or LLM APIs.

## File Structure

Create:

- `skills/ingest/scripts/url_source_card.py` - URL normalization, source-card rendering, deterministic hub/skill classifier, duplicate-safe vault write.
- `skills/ingest/augur/tests/test_url_source_card.py` - unit tests for classifier, card rendering, duplicate names, and frontmatter format.
- `skills/ingest/commands/ingest-url.md` - user-facing command contract for `/ingest-url`.
- `skills/obsidian/` - promoted copy of `staging/r1/skills/obsidian`.

Modify:

- `skills/ingest/scripts/mcp/ingest_tools.py` - register the `ingest-url` MCP tool.
- `skills/ingest/augur/tests/test_ingest_tools.py` - MCP registration and behavior coverage for `ingest-url`.
- `skills/ingest/augur/tests/test_wiki_command_contracts.py` - command/sync contract coverage for `/ingest-url`.
- `skills/ingest/SKILL.md` - add `ingest-url` to exported MCP tools and command docs.
- `skills/ingest/commands/ingest.md` - replace direct wiki write language with concept-first wiki compiler language.
- `skills/ingest/augur/dashboard/IngestModal.tsx` - keep URL tab, add compile preference if needed by parent callback.
- `apps/dashboard/app/(views)/browse/page.tsx` - wire URL submission to `mcpCall("ingest-url", ...)`.
- `docs/agent-topics/agent-rules.md` - add focused wiki execution instructions for URL ingest, source cards, Obsidian-native markdown, and concept-first compilation.
- Generated agent/client surfaces from `python3 -m skills.ai.scripts.sync_agents sync all`.

Do not modify generated dashboard copies unless they are the source file for that page. Dashboard skill-owned components live in `skills/ingest/augur/dashboard/`; generated Browse feature copies may be refreshed by existing sync/build machinery.

## Task 1: URL Source Card Helpers

**Files:**
- Create: `skills/ingest/scripts/url_source_card.py`
- Create: `skills/ingest/augur/tests/test_url_source_card.py`

- [ ] **Step 1: Write failing tests for deterministic classification and source-card output**

Create `skills/ingest/augur/tests/test_url_source_card.py` with:

```python
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from skills.ingest.scripts.url_source_card import (
    classify_url_source,
    normalize_url,
    render_url_source_card,
    write_url_source_card,
)


def _skill(root: Path, name: str, body: str) -> None:
    skill_dir = root / "skills" / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(body, encoding="utf-8")


def test_normalize_url_requires_http_scheme() -> None:
    assert normalize_url("example.com/a") == "https://example.com/a"
    assert normalize_url("https://example.com/a") == "https://example.com/a"

    with pytest.raises(ValueError, match="Unsupported URL scheme"):
        normalize_url("file:///tmp/a.md")


def test_classification_uses_live_skill_frontmatter_and_recent_context(tmp_path: Path) -> None:
    _skill(
        tmp_path,
        "knowledge",
        """---
name: knowledge
description: Search memory, documents, wiki pages, and project knowledge.
x-augur-hub: brain
x-augur-tags:
  - wiki
  - knowledge
x-augur-mcp-tools:
  - search-skill-knowledge
---
# Knowledge
""",
    )
    _skill(
        tmp_path,
        "finance",
        """---
name: finance
description: Personal finance and portfolio analysis.
x-augur-hub: life
x-augur-tags:
  - portfolio
  - brokerage
---
# Finance
""",
    )
    staged_obsidian = tmp_path / "staging" / "r1" / "skills" / "obsidian"
    staged_obsidian.mkdir(parents=True)
    (staged_obsidian / "SKILL.md").write_text(
        """---
name: obsidian
description: Obsidian vault integration with wikilinks, callouts, canvas, and markdown search.
x-augur-hub: brain
x-augur-tags:
  - obsidian
  - vault
  - wikilinks
---
# Obsidian
""",
        encoding="utf-8",
    )

    result = classify_url_source(
        title="Karpathy LLM Wiki in Obsidian",
        url="https://aimaker.substack.com/p/llm-wiki-obsidian-knowledge-base",
        markdown="This article covers LLM wiki workflows, Obsidian callouts, markdown vaults, and wikilinks.",
        project_root=tmp_path,
        recent_context=["ingest", "wiki", "obsidian"],
    )

    assert result.hub == "brain"
    assert result.skill_candidates[:3] == ["obsidian", "knowledge"]
    assert "read-later" in result.intent
    assert "wiki-ux" in result.intent
    assert result.content_kind == "article"
    assert result.confidence >= 0.55
    assert "obsidian" in result.classification_basis["matched_skill_terms"]


def test_render_source_card_writes_obsidian_native_markdown() -> None:
    captured = datetime(2026, 4, 21, 9, 30, tzinfo=timezone.utc)
    classification = classify_url_source(
        title="Example Go To Market Library",
        url="https://example.com/gtm",
        markdown="A library candidate for go to market execution.",
        project_root=Path("/tmp/missing-project-root"),
        recent_context=[],
    )

    metadata, body = render_url_source_card(
        title="Example Go To Market Library",
        url="https://example.com/gtm",
        markdown="Extracted body text.",
        classification=classification,
        captured_at=captured,
        read_status="unread",
        action_status="triage",
        priority="medium",
        wiki_compile="queued",
        summary="Short summary for later reading.",
        suggested_actions=["Evaluate as Augur library candidate"],
    )

    assert metadata["source_type"] == "url"
    assert metadata["domain"] == "example.com"
    assert metadata["captured"] == "2026-04-21T09:30:00+00:00"
    assert metadata["read_status"] == "unread"
    assert metadata["wiki_compile"] == "queued"
    assert "> [!summary]" in body
    assert "> [!routing]" in body
    assert "## Suggested Actions" in body
    assert "- [ ] Evaluate as Augur library candidate" in body
    assert "## Extracted Content" in body
    assert body.endswith("Extracted body text.\n")


def test_write_source_card_creates_unique_frontmatter_file(tmp_path: Path) -> None:
    classification = classify_url_source(
        title="Example Article",
        url="https://example.com/article",
        markdown="Wiki article body.",
        project_root=tmp_path,
        recent_context=["wiki"],
    )

    first = write_url_source_card(
        vault_dir=tmp_path / "vault",
        destination="sources/web",
        title="Example Article",
        url="https://example.com/article",
        markdown="Wiki article body.",
        classification=classification,
        captured_at=datetime(2026, 4, 21, tzinfo=timezone.utc),
    )
    second = write_url_source_card(
        vault_dir=tmp_path / "vault",
        destination="sources/web",
        title="Example Article",
        url="https://example.com/article",
        markdown="Wiki article body.",
        classification=classification,
        captured_at=datetime(2026, 4, 21, tzinfo=timezone.utc),
    )

    assert first.relative_path == "sources/web/2026-04-21-example-article.md"
    assert second.relative_path == "sources/web/2026-04-21-example-article-2.md"

    content = first.absolute_path.read_text(encoding="utf-8")
    assert content.startswith("---\n")
    metadata = yaml.safe_load(content.split("---", 2)[1])
    assert metadata["url"] == "https://example.com/article"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python3 -m pytest skills/ingest/augur/tests/test_url_source_card.py -q
```

Expected: collection fails with `ModuleNotFoundError: No module named 'skills.ingest.scripts.url_source_card'`.

- [ ] **Step 3: Implement URL source-card helper module**

Create `skills/ingest/scripts/url_source_card.py`:

```python
"""URL source-card helpers for the ingest skill.

The functions in this module stay deterministic. Agents may refine summaries
and suggested actions later, but MCP tools can call this safely without an LLM.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlparse, urlunparse

from src.lib.frontmatter_utils import parse_frontmatter, write_frontmatter


INTENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "task": ("todo", "task", "action", "fix", "implement", "ship", "build"),
    "library-candidate": ("library", "package", "sdk", "framework", "api", "dependency"),
    "competitor-research": ("competitor", "alternative", "vs", "comparison", "market map"),
    "go-to-market": ("go to market", "gtm", "pricing", "positioning", "distribution", "sales"),
    "product-research": ("product", "feature", "ux", "workflow", "user experience"),
    "wiki-ux": ("wiki", "obsidian", "wikilink", "callout", "canvas", "bases", "markdown vault"),
    "implementation-reference": ("architecture", "implementation", "code", "mcp", "cli", "pipeline"),
    "personal-knowledge": ("second brain", "knowledge base", "notes", "memory", "vault"),
}

CONTENT_KIND_KEYWORDS: dict[str, tuple[str, ...]] = {
    "library": ("github.com", "library", "package", "sdk", "framework"),
    "competitor": ("competitor", "alternative", "vs", "comparison"),
    "task": ("todo", "task", "action item"),
    "article": ("article", "post", "substack", "blog", "essay"),
}


@dataclass(frozen=True)
class SkillProfile:
    name: str
    hub: str
    description: str
    tags: tuple[str, ...]
    commands: tuple[str, ...]
    mcp_tools: tuple[str, ...]
    path: Path

    @property
    def terms(self) -> tuple[str, ...]:
        values = [self.name, self.description, *self.tags, *self.commands, *self.mcp_tools]
        return tuple(_normalize_phrase(value) for value in values if _normalize_phrase(value))


@dataclass(frozen=True)
class UrlClassification:
    hub: str
    skill_candidates: list[str]
    intent: list[str]
    content_kind: str
    confidence: float
    classification_basis: dict[str, Any]


@dataclass(frozen=True)
class SourceCardWrite:
    absolute_path: Path
    relative_path: str
    metadata: dict[str, Any]


def normalize_url(raw_url: str) -> str:
    candidate = raw_url.strip()
    if not candidate:
        raise ValueError("URL is required")
    if "://" not in candidate:
        candidate = f"https://{candidate}"
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"Unsupported URL scheme: {parsed.scheme}")
    if not parsed.netloc:
        raise ValueError("URL must include a host")
    normalized = parsed._replace(fragment="")
    return urlunparse(normalized)


def canonical_domain(url: str) -> str:
    parsed = urlparse(normalize_url(url))
    return parsed.netloc.lower().removeprefix("www.")


def classify_url_source(
    *,
    title: str,
    url: str,
    markdown: str,
    project_root: Path,
    recent_context: list[str] | tuple[str, ...] | None = None,
) -> UrlClassification:
    normalized_url = normalize_url(url)
    text = _normalize_phrase(" ".join([title, normalized_url, markdown]))
    recent_terms = tuple(_normalize_phrase(item) for item in (recent_context or []) if _normalize_phrase(item))
    profiles = load_skill_profiles(project_root)

    scored: list[tuple[float, SkillProfile, list[str]]] = []
    for profile in profiles:
        matched = _matched_terms(text, profile.terms)
        recent_hits = [term for term in recent_terms if term and term in profile.terms]
        score = float(len(matched))
        if profile.name in recent_terms:
            score += 1.5
        score += 0.5 * len(recent_hits)
        if score > 0:
            scored.append((score, profile, matched + recent_hits))

    scored.sort(key=lambda item: (-item[0], item[1].name))
    skill_candidates = [item[1].name for item in scored[:5]]
    hub = _choose_hub(scored)
    intent = _detect_intents(text)
    content_kind = _detect_content_kind(text)
    max_score = scored[0][0] if scored else 0.0
    confidence = min(0.95, round(0.35 + (max_score * 0.12), 2)) if scored else 0.35

    matched_skill_terms = {
        profile.name: sorted(set(matches))
        for _score, profile, matches in scored[:5]
    }
    matched_hub_terms = sorted(
        {
            term
            for _score, profile, matches in scored[:5]
            if profile.hub == hub
            for term in matches
        }
    )

    return UrlClassification(
        hub=hub,
        skill_candidates=skill_candidates,
        intent=intent,
        content_kind=content_kind,
        confidence=confidence,
        classification_basis={
            "matched_hub_terms": matched_hub_terms,
            "matched_skill_terms": matched_skill_terms,
            "recent_context_boost": list(recent_terms),
        },
    )


def load_skill_profiles(project_root: Path) -> list[SkillProfile]:
    roots = [project_root / "skills"]
    staged_obsidian = project_root / "staging" / "r1" / "skills" / "obsidian"
    profiles: list[SkillProfile] = []

    for root in roots:
        if root.is_dir():
            for skill_md in sorted(root.glob("*/SKILL.md")):
                profile = _profile_from_skill_md(skill_md)
                if profile is not None:
                    profiles.append(profile)

    if staged_obsidian.is_dir() and not any(profile.name == "obsidian" for profile in profiles):
        profile = _profile_from_skill_md(staged_obsidian / "SKILL.md")
        if profile is not None:
            profiles.append(profile)

    return profiles


def render_url_source_card(
    *,
    title: str,
    url: str,
    markdown: str,
    classification: UrlClassification,
    captured_at: datetime | None = None,
    read_status: str = "unread",
    action_status: str = "triage",
    priority: str = "medium",
    wiki_compile: str = "queued",
    summary: str = "Captured for later review.",
    suggested_actions: list[str] | None = None,
) -> tuple[dict[str, Any], str]:
    normalized_url = normalize_url(url)
    captured = captured_at or datetime.now(timezone.utc)
    actions = suggested_actions or ["Review source and decide whether to compile durable concepts"]
    clean_title = title.strip() or canonical_domain(normalized_url)
    extracted = markdown.strip()

    metadata: dict[str, Any] = {
        "title": clean_title,
        "source_type": "url",
        "url": normalized_url,
        "domain": canonical_domain(normalized_url),
        "captured": captured.isoformat(),
        "hub": classification.hub,
        "skill_candidates": classification.skill_candidates,
        "intent": classification.intent,
        "content_kind": classification.content_kind,
        "read_status": read_status,
        "action_status": action_status,
        "priority": priority,
        "wiki_compile": wiki_compile,
        "confidence": classification.confidence,
        "classification_basis": classification.classification_basis,
    }

    body = "\n".join(
        [
            f"# {clean_title}",
            "",
            "> [!summary]",
            f"> {summary.strip()}",
            "",
            "> [!routing]",
            f"> Routed to `{classification.hub}`.",
            f"> Candidate skills: {_format_candidates(classification.skill_candidates)}.",
            "",
            "## Why It Matters",
            "",
            _why_it_matters(classification),
            "",
            "## Suggested Actions",
            "",
            *[f"- [ ] {action}" for action in actions],
            "",
            "## Extracted Content",
            "",
            extracted,
            "",
        ]
    )
    return metadata, body


def write_url_source_card(
    *,
    vault_dir: Path,
    destination: str,
    title: str,
    url: str,
    markdown: str,
    classification: UrlClassification,
    captured_at: datetime | None = None,
    read_status: str = "unread",
    action_status: str = "triage",
    priority: str = "medium",
    wiki_compile: str = "queued",
    summary: str = "Captured for later review.",
    suggested_actions: list[str] | None = None,
) -> SourceCardWrite:
    captured = captured_at or datetime.now(timezone.utc)
    metadata, body = render_url_source_card(
        title=title,
        url=url,
        markdown=markdown,
        classification=classification,
        captured_at=captured,
        read_status=read_status,
        action_status=action_status,
        priority=priority,
        wiki_compile=wiki_compile,
        summary=summary,
        suggested_actions=suggested_actions,
    )
    dest = _safe_destination(destination)
    filename = f"{captured.date().isoformat()}-{_slugify(metadata['title'])}.md"
    target = _unique_path(vault_dir / dest / filename)
    write_frontmatter(target, metadata, body)
    return SourceCardWrite(
        absolute_path=target,
        relative_path=target.relative_to(vault_dir).as_posix(),
        metadata=metadata,
    )


def _profile_from_skill_md(skill_md: Path) -> SkillProfile | None:
    if not skill_md.is_file():
        return None
    metadata, body = parse_frontmatter(skill_md)
    name = str(metadata.get("name") or skill_md.parent.name).strip()
    hub = str(metadata.get("x-augur-hub") or "brain").strip() or "brain"
    description = str(metadata.get("description") or _first_heading(body)).strip()
    tags = _string_tuple(metadata.get("x-augur-tags"))
    mcp_tools = _string_tuple(metadata.get("x-augur-mcp-tools"))
    command_entries = metadata.get("x-augur-commands")
    commands: list[str] = []
    if isinstance(command_entries, list):
        for entry in command_entries:
            if isinstance(entry, dict) and isinstance(entry.get("name"), str):
                commands.append(entry["name"])
            elif isinstance(entry, str):
                commands.append(entry)
    return SkillProfile(
        name=name,
        hub=hub,
        description=description,
        tags=tags,
        commands=tuple(commands),
        mcp_tools=mcp_tools,
        path=skill_md.parent,
    )


def _string_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, list):
        return tuple(str(item).strip() for item in value if str(item).strip())
    if isinstance(value, str) and value.strip():
        return (value.strip(),)
    return ()


def _first_heading(body: str) -> str:
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def _normalize_phrase(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower().replace("-", " ")).strip()


def _matched_terms(text: str, terms: tuple[str, ...]) -> list[str]:
    matches: list[str] = []
    for term in terms:
        if len(term) < 3:
            continue
        if term in text:
            matches.append(term)
    return matches


def _choose_hub(scored: list[tuple[float, SkillProfile, list[str]]]) -> str:
    if not scored:
        return "brain"
    hub_scores: dict[str, float] = {}
    for score, profile, _matches in scored:
        hub_scores[profile.hub] = hub_scores.get(profile.hub, 0.0) + score
    return sorted(hub_scores.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _detect_intents(text: str) -> list[str]:
    intents = ["read-later"]
    for intent, keywords in INTENT_KEYWORDS.items():
        if any(keyword in text for keyword in keywords) and intent not in intents:
            intents.append(intent)
    return intents


def _detect_content_kind(text: str) -> str:
    for kind, keywords in CONTENT_KIND_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return kind
    return "article"


def _format_candidates(candidates: list[str]) -> str:
    if not candidates:
        return "`none`"
    return ", ".join(f"`{candidate}`" for candidate in candidates)


def _why_it_matters(classification: UrlClassification) -> str:
    intents = ", ".join(classification.intent)
    candidates = ", ".join(classification.skill_candidates) if classification.skill_candidates else "no specific skill"
    return (
        f"This source matched `{classification.hub}` with {classification.confidence:.2f} "
        f"confidence. Intents: {intents}. Candidate skills: {candidates}."
    )


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:80] or "url-source"


def _safe_destination(destination: str) -> Path:
    dest = Path(destination.strip() or "sources/web")
    if dest.is_absolute() or ".." in dest.parts:
        raise ValueError("Destination must be a vault-relative path")
    return dest


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    for index in range(2, 1000):
        candidate = path.with_name(f"{stem}-{index}{suffix}")
        if not candidate.exists():
            return candidate
    raise FileExistsError(f"Could not allocate unique source-card path for {path}")
```

- [ ] **Step 4: Run source-card tests**

Run:

```bash
python3 -m pytest skills/ingest/augur/tests/test_url_source_card.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit Task 1**

```bash
git add skills/ingest/scripts/url_source_card.py skills/ingest/augur/tests/test_url_source_card.py
git commit -m "feat(ingest): add deterministic URL source cards"
git push
```

## Task 2: `ingest-url` MCP Tool

**Files:**
- Modify: `skills/ingest/scripts/mcp/ingest_tools.py`
- Modify: `skills/ingest/augur/tests/test_ingest_tools.py`

- [ ] **Step 1: Write failing MCP registration test**

Add this assertion to the existing MCP registration test in `skills/ingest/augur/tests/test_ingest_tools.py`:

```python
def test_ingest_url_tool_is_registered(fake_mcp) -> None:
    registered = {entry["name"] for entry in fake_mcp.tools}
    assert "ingest-url" in registered
```

If the file uses a different fake MCP shape, keep the assertion equivalent: collect registered tool names and require `ingest-url`.

- [ ] **Step 2: Write failing behavior test for URL capture**

Add this test to `skills/ingest/augur/tests/test_ingest_tools.py`:

```python
def test_ingest_url_writes_source_card(monkeypatch, tmp_path, fake_mcp) -> None:
    from skills.ingest.scripts.mcp import ingest_tools

    monkeypatch.setattr(ingest_tools, "get_vault_dir", lambda: tmp_path / "vault")
    monkeypatch.setattr(ingest_tools, "get_project_root", lambda: tmp_path)

    class FakePipeline:
        def _extract(self, source, content_type):
            assert str(source) == "https://example.com/wiki"
            return "# Example Wiki\n\nA markdown vault article about Obsidian wiki UX."

    monkeypatch.setattr(ingest_tools, "_get_pipeline", lambda: FakePipeline())

    result = fake_mcp.call_tool(
        "ingest-url",
        {
            "url": "https://example.com/wiki",
            "title": "Example Wiki",
            "destination": "sources/web",
            "compile": "queue",
            "read_status": "unread",
        },
    )

    assert result["success"] is True
    assert result["source_path"] == "sources/web/2026-" + result["source_path"].split("2026-", 1)[1]
    assert result["domain"] == "example.com"
    assert result["hub"] == "brain"
    assert result["wiki_compile"] == "queued"
    assert (tmp_path / "vault" / result["source_path"]).exists()
```

If the fake MCP helper does not expose `call_tool`, adapt the invocation to the fixture's existing helper. Do not change the behavior assertions.

- [ ] **Step 3: Run MCP tests to verify failure**

Run:

```bash
python3 -m pytest skills/ingest/augur/tests/test_ingest_tools.py -q
```

Expected: failure because `ingest-url` is not registered.

- [ ] **Step 4: Add `ingest-url` registration and implementation**

Modify `skills/ingest/scripts/mcp/ingest_tools.py`:

1. Add imports near the existing ingest imports:

```python
from datetime import datetime, timezone
from pathlib import Path

from skills.ingest.scripts.detector import ContentType
from skills.ingest.scripts.url_source_card import (
    classify_url_source,
    normalize_url,
    write_url_source_card,
)
from src.config.paths import get_project_root, get_vault_dir
```

If `Path`, `datetime`, `ContentType`, `get_project_root`, or `get_vault_dir` are already imported, reuse the existing imports and only add missing names.

2. Register this tool inside `register_ingest_tools(mcp)` after `ingest-process` and before status/history tools:

```python
    @mcp.tool(name="ingest-url", description="Capture a URL as an Obsidian-native markdown source card")
    def ingest_url(
        url: str,
        destination: str = "sources/web",
        compile: str = "queue",
        read_status: str = "unread",
        title: str = "",
    ) -> dict:
        """Capture a URL as one deterministic source card in the vault."""
        metrics.track_tool("ingest_url", skill="ingest")
        try:
            normalized_url = normalize_url(url)
            pipeline = _get_pipeline()
            markdown = pipeline._extract(Path(normalized_url), ContentType.URL)
            clean_title = title.strip() or _title_from_markdown(markdown) or normalized_url
            wiki_compile = "queued" if compile in {"queue", "true", "yes", "1"} else "none"
            classification = classify_url_source(
                title=clean_title,
                url=normalized_url,
                markdown=markdown,
                project_root=get_project_root(),
                recent_context=["ingest", "wiki"],
            )
            saved = write_url_source_card(
                vault_dir=get_vault_dir(),
                destination=destination,
                title=clean_title,
                url=normalized_url,
                markdown=markdown,
                classification=classification,
                captured_at=datetime.now(timezone.utc),
                read_status=read_status,
                wiki_compile=wiki_compile,
            )
            return {
                "success": True,
                "source_path": saved.relative_path,
                "title": saved.metadata["title"],
                "domain": saved.metadata["domain"],
                "hub": saved.metadata["hub"],
                "skill_candidates": saved.metadata["skill_candidates"],
                "intent": saved.metadata["intent"],
                "content_kind": saved.metadata["content_kind"],
                "read_status": saved.metadata["read_status"],
                "action_status": saved.metadata["action_status"],
                "priority": saved.metadata["priority"],
                "wiki_compile": saved.metadata["wiki_compile"],
                "confidence": saved.metadata["confidence"],
                "classification_basis": saved.metadata["classification_basis"],
            }
        except Exception as exc:
            return {"success": False, "error": str(exc), "url": url}
```

3. Add this helper near other private helpers in the same file:

```python
def _title_from_markdown(markdown: str) -> str:
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return ""
```

- [ ] **Step 5: Run MCP tests**

Run:

```bash
python3 -m pytest skills/ingest/augur/tests/test_ingest_tools.py -q
```

Expected: all ingest tool tests pass.

- [ ] **Step 6: Commit Task 2**

```bash
git add skills/ingest/scripts/mcp/ingest_tools.py skills/ingest/augur/tests/test_ingest_tools.py
git commit -m "feat(ingest): expose ingest-url MCP tool"
git push
```

## Task 3: Command Contract and Skill Metadata

**Files:**
- Create: `skills/ingest/commands/ingest-url.md`
- Modify: `skills/ingest/SKILL.md`
- Modify: `skills/ingest/commands/ingest.md`
- Modify: `skills/ingest/augur/tests/test_wiki_command_contracts.py`

- [ ] **Step 1: Add failing command contract test**

Add to `skills/ingest/augur/tests/test_wiki_command_contracts.py`:

```python
def test_ingest_url_command_contract_exists(project_root: Path) -> None:
    command = project_root / "skills" / "ingest" / "commands" / "ingest-url.md"
    assert command.exists()
    text = command.read_text(encoding="utf-8")
    assert "/ingest-url" in text
    assert "ingest-url" in text
    assert "wiki-update" in text
    assert "wiki-apply-concept-batch" in text
    assert "Do not hand-write compiled wiki pages" in text


def test_ingest_skill_exports_ingest_url_tool(project_root: Path) -> None:
    skill_md = project_root / "skills" / "ingest" / "SKILL.md"
    text = skill_md.read_text(encoding="utf-8")
    assert "ingest-url" in text
    assert "commands/ingest-url.md" in text
```

If this test file does not have a `project_root` fixture, add:

```python
@pytest.fixture
def project_root() -> Path:
    return Path(__file__).resolve().parents[4]
```

- [ ] **Step 2: Run command contract tests to verify failure**

Run:

```bash
python3 -m pytest skills/ingest/augur/tests/test_wiki_command_contracts.py -q
```

Expected: failure because `skills/ingest/commands/ingest-url.md` does not exist or skill metadata does not export it.

- [ ] **Step 3: Create `/ingest-url` command doc**

Create `skills/ingest/commands/ingest-url.md`:

```markdown
---
name: ingest-url
description: Capture a URL as an Obsidian-native source card and optionally queue concept-first wiki compilation.
argument-hint: "<url> [--to sources/web] [--compile] [--read-status unread|reading|read]"
allowed-tools:
  - mcp__augur__skill_action
  - mcp__augur__list_mcp_tools
  - mcp__augur__get_cowork_status
---

# /ingest-url

Capture one URL into the Augur vault as a markdown source card.

## Usage

```bash
/ingest-url https://example.com/article
/ingest-url https://example.com/article --to sources/web --compile
/ingest-url https://example.com/article --read-status unread
```

## Execution

1. Parse the URL and flags.
2. Call the `ingest-url` MCP tool with:
   - `url`
   - `destination`, default `sources/web`
   - `compile`, default `queue` when `--compile` is present and `none` otherwise
   - `read_status`, default `unread`
3. Show the saved source path, title, domain, hub, skill candidates, intent, and wiki compile state.
4. If `--compile` is present and the source has durable value, call `wiki-update` to prepare a concept batch.
5. As the agent, read the returned batch, extract durable concepts, call `wiki-apply-concept-batch`, then run `wiki-reindex`, `wiki-lint`, and `wiki-log`.

## Rules

- Do not hand-write compiled wiki pages.
- Preserve URL source-card frontmatter when summarizing or refining the card.
- Use deterministic hub and skill routing from the MCP result as evidence, not as absolute certainty.
- Use Obsidian-native markdown conventions for user-facing source cards: YAML frontmatter, wikilinks when useful, and callouts for summary/routing/action review.
- Dashboard and MCP tools must not call LLM APIs directly; agent sessions own concept extraction and synthesis.
```

- [ ] **Step 4: Update ingest skill frontmatter**

Modify `skills/ingest/SKILL.md` frontmatter:

1. Add `ingest-url` to `x-augur-mcp-tools`.
2. Add an `x-augur-commands` entry:

```yaml
x-augur-commands:
  - name: ingest-url
    path: commands/ingest-url.md
    description: Capture a URL as an Obsidian-native source card and optionally queue concept-first wiki compilation.
```

If `x-augur-commands` already exists, append the entry and keep existing entries.

- [ ] **Step 5: Update existing `/ingest` command wording**

In `skills/ingest/commands/ingest.md`, replace any instruction that says to directly write wiki pages with this exact policy block:

```markdown
## Wiki Update Policy

When ingested content has durable value, queue the concept-first wiki compiler:

1. Call `wiki-update` to prepare a bounded concept extraction batch.
2. As the agent, extract durable concept JSON from the batch.
3. Call `wiki-apply-concept-batch` to update compiler state and compiled pages.
4. Run `wiki-reindex`, `wiki-lint`, and `wiki-log`.

Do not hand-write compiled wiki pages under `wiki/concepts/` or `wiki/queries/`.
```

- [ ] **Step 6: Run command contract tests**

Run:

```bash
python3 -m pytest skills/ingest/augur/tests/test_wiki_command_contracts.py -q
```

Expected: all command contract tests pass.

- [ ] **Step 7: Commit Task 3**

```bash
git add skills/ingest/commands/ingest-url.md skills/ingest/SKILL.md skills/ingest/commands/ingest.md skills/ingest/augur/tests/test_wiki_command_contracts.py
git commit -m "docs(ingest): add ingest-url command contract"
git push
```

## Task 4: Promote Obsidian Skill MVP

**Files:**
- Create: `skills/obsidian/`
- Modify as needed inside: `skills/obsidian/SKILL.md`
- Modify as needed inside: `skills/obsidian/augur/tests/*`

- [ ] **Step 1: Inspect governing folder rules and staged skill state**

Run:

```bash
find staging/r1/skills/obsidian -maxdepth 2 -name README.md -print
find skills -maxdepth 1 -name README.md -print
python3 -m pytest staging/r1/skills/obsidian/augur/tests -q
```

Expected: staged Obsidian tests pass before promotion. If a README exists, follow its local folder rules before copying files.

- [ ] **Step 2: Promote the staged skill without adding centralized registry data**

Run:

```bash
cp -R staging/r1/skills/obsidian skills/obsidian
```

Then inspect `skills/obsidian/SKILL.md` and ensure:

```yaml
x-augur-hub: brain
x-augur-mcp-tools:
  - obsidian-read
  - obsidian-write
  - obsidian-search
  - obsidian-status
  - obsidian-scaffold
  - obsidian-convert
```

Do not add Obsidian skill metadata to centralized dashboard or skill registry files.

- [ ] **Step 3: Run promoted skill tests**

Run:

```bash
python3 -m pytest skills/obsidian/augur/tests -q
```

Expected: all promoted Obsidian tests pass.

- [ ] **Step 4: Verify live MCP tool registration through skill-owned discovery**

Run:

```bash
python3 -m pytest skills/obsidian/augur/tests -q
python3 -m skills.ai.scripts.sync_agents check
```

Expected: Obsidian tests pass. `sync_agents check` may fail before generated surfaces are synced in Task 7; if it fails only because new Obsidian/ingest-url surfaces are stale, continue to Task 7 and resolve there.

- [ ] **Step 5: Commit Task 4**

```bash
git add skills/obsidian
git commit -m "feat(obsidian): promote vault integration MVP skill"
git push
```

## Task 5: Dashboard URL Ingest Affordance

**Files:**
- Modify: `skills/ingest/augur/dashboard/IngestModal.tsx`
- Modify: `apps/dashboard/app/(views)/browse/page.tsx`

- [ ] **Step 1: Add a URL ingest state test or type-level check if the dashboard test harness exists**

Search for existing Browse dashboard tests:

```bash
rg "IngestModal|handleSubmitUrl|browse page" apps/dashboard skills/ingest -g '*test*' -n
```

If a matching test harness exists, add a test asserting URL submit calls `mcpCall("ingest-url", ...)`. If no harness exists, record this as a verification gap in the final implementation summary and rely on browser verification in Step 6.

- [ ] **Step 2: Update URL submit callback shape if compile preference is needed**

If `skills/ingest/augur/dashboard/IngestModal.tsx` still accepts only `onSubmitUrl: (url: string) => void`, keep it for MVP and default compile to `queue` in the page. If adding a compile toggle, change the prop to:

```ts
onSubmitUrl: (url: string, options?: { compile?: boolean }) => void;
```

For MVP, the minimal code path is to leave the modal unchanged and update the parent callback only.

- [ ] **Step 3: Wire Browse URL submit to MCP**

Modify `apps/dashboard/app/(views)/browse/page.tsx` so `handleSubmitUrl` calls `ingest-url`:

```ts
  const handleSubmitUrl = useCallback((url: string) => {
    const jobId = crypto.randomUUID().slice(0, 8);
    setIngestQueue((q) => [
      { jobId, name: url, status: "pending" as const, stage: "extracting" },
      ...q,
    ]);

    import("@/lib/mcp/client").then(({ mcpCall }) =>
      mcpCall("ingest-url", {
        url,
        destination: "sources/web",
        compile: "queue",
        read_status: "unread",
      })
        .then((result) => {
          const data = result as {
            success?: boolean;
            error?: string;
            source_path?: string;
            hub?: string;
            skill_candidates?: string[];
          };
          setIngestQueue((q) =>
            q.map((item) =>
              item.jobId === jobId
                ? data.success
                  ? {
                      ...item,
                      status: "completed" as const,
                      stage: "saved",
                      destination: data.source_path || "sources/web",
                    }
                  : {
                      ...item,
                      status: "failed" as const,
                      error: data.error || "URL ingest failed",
                    }
                : item,
            ),
          );
        })
        .catch((error) => {
          setIngestQueue((q) =>
            q.map((item) =>
              item.jobId === jobId
                ? { ...item, status: "failed" as const, error: error instanceof Error ? error.message : "URL ingest failed" }
                : item,
            ),
          );
        }),
    );
  }, []);
```

If the dashboard MCP client wraps tool output inside `{ success, data }`, unwrap it in this callback using the existing local pattern in the same file. Do not introduce Python script calls, `fs`, `spawn`, `execFile`, or LLM API calls.

- [ ] **Step 4: Run focused TypeScript/lint check**

Run the repo's dashboard lint command through the existing build/lint workflow if available. Use:

```bash
pnpm --filter dashboard lint
```

Expected: lint passes. If this repo requires `/auto-lint` instead, run the canonical command and report the exact command used.

- [ ] **Step 5: Request dashboard lifecycle gate before browser verification**

Run:

```bash
python3 skills/daemon/scripts/dashboard_lifecycle.py request-action --actor ingest-url-mvp --action verify-dashboard --reason "verify ingest-url dashboard affordance"
```

Expected: JSON with `"decision": "granted"`. If denied, inspect lifecycle state:

```bash
python3 skills/daemon/scripts/dashboard_lifecycle.py state
```

Do not run `npm run dev`, `npm run build`, direct cleanup, or process kills outside the lifecycle gate.

- [ ] **Step 6: Browser-verify URL ingest on the correct checkout**

Before opening the browser, identify the dashboard process cwd and branch for the port being used. Then use Chrome or Playwright to verify:

1. The Browse ingest modal opens.
2. The URL tab accepts a URL.
3. Submitting a URL creates a pending queue item.
4. The queue item completes with a saved `sources/web/...md` destination.
5. The source card exists in `get_vault_dir()/sources/web/`.

If Chrome automation is unavailable, ask the user to check the exact page and record that browser verification is blocked by missing browser automation.

- [ ] **Step 7: Commit Task 5**

```bash
git add skills/ingest/augur/dashboard/IngestModal.tsx 'apps/dashboard/app/(views)/browse/page.tsx'
git commit -m "feat(dashboard): wire URL ingest to MCP"
git push
```

## Task 6: Agent Instructions and Generated Surfaces

**Files:**
- Modify: `docs/agent-topics/agent-rules.md`
- Generated: `AGENTS.md`, `CODEX.md`, `.codex/skills/*`, `.gemini/skills/*`, `.claude/*`, and other sync-managed surfaces if changed by `sync_agents`

- [ ] **Step 1: Update source agent rules**

In `docs/agent-topics/agent-rules.md`, update the Wiki Compounding section with this policy:

```markdown
### URL Ingest and LLM Wiki Execution

- Use `/ingest-url` for durable URL capture instead of ad hoc notes.
- URL captures are saved as vault source cards, normally under `sources/web/`, with YAML frontmatter and Obsidian-native callouts.
- Preserve source-card metadata when summarizing, tagging, or compiling captures.
- Deterministic routing must use current Augur hubs and skill metadata; agent judgment may refine summaries and actions, but should not erase routing evidence.
- Do not hand-write compiled wiki pages under `wiki/concepts/` or `wiki/queries/`; use `wiki-update` and `wiki-apply-concept-batch`.
- Use Obsidian-native markdown conventions for user-facing vault and wiki files: frontmatter, wikilinks where helpful, callouts for summary/routing/action review, and checkbox actions for follow-up work.
```

- [ ] **Step 2: Sync generated agent surfaces**

Run:

```bash
python3 -m skills.ai.scripts.sync_agents sync all
python3 -m skills.ai.scripts.sync_agents check
```

Expected: final check passes. If generated `.gemini/skills` files changed, keep them tracked because Gemini skill discovery requires them to stay git-visible.

- [ ] **Step 3: Verify no generated frontmatter regression**

Run:

```bash
python3 -m pytest skills/ai/augur/tests -q
```

If this full test set is too broad or fails for unrelated known issues, run the narrower generated-frontmatter test module that owns `write_generated_file()` and report the exact result.

- [ ] **Step 4: Commit Task 6**

```bash
git add docs/agent-topics/agent-rules.md AGENTS.md CODEX.md .codex .gemini .claude
git commit -m "docs(agents): focus execution on ingest-url wiki flow"
git push
```

If some generated directories do not exist or are not changed, omit them from `git add`.

## Task 7: End-to-End URL Capture and Wiki Readiness Verification

**Files:**
- External vault: `get_vault_dir()/sources/web/*.md`
- Runtime/generated wiki maintenance state

- [ ] **Step 1: Run focused Python tests**

Run:

```bash
python3 -m pytest \
  skills/ingest/augur/tests/test_url_source_card.py \
  skills/ingest/augur/tests/test_ingest_tools.py \
  skills/ingest/augur/tests/test_wiki_command_contracts.py \
  skills/obsidian/augur/tests \
  -q
```

Expected: all focused tests pass.

- [ ] **Step 2: Run sync check**

Run:

```bash
python3 -m skills.ai.scripts.sync_agents check
```

Expected: check passes with no stale generated client surfaces.

- [ ] **Step 3: Exercise the MCP tool with a stable URL**

Use the existing MCP tool runner or a direct Python test harness from `skills/ingest/augur/tests/test_ingest_tools.py` to call:

```json
{
  "url": "https://aimaker.substack.com/p/llm-wiki-obsidian-knowledge-base-andrej-karphaty",
  "destination": "sources/web",
  "compile": "queue",
  "read_status": "unread"
}
```

Expected:

- `success: true`
- `source_path` starts with `sources/web/`
- `hub` is `brain`
- `skill_candidates` includes `obsidian`, `ingest`, or `knowledge`
- source markdown exists in the vault and starts with YAML frontmatter

If network extraction is blocked or the article blocks automated fetches, use `https://example.com/` for the tool smoke test and keep the Substack article as a manual/browser capture target.

- [ ] **Step 4: Reindex relevant knowledge surfaces**

Run:

```bash
python3 skills/rag/scripts/unified_indexer.py --category wiki
python3 skills/rag/scripts/unified_indexer.py --category documents
```

Expected: indexer completes without tracebacks.

- [ ] **Step 5: Run wiki D4 scan**

Run the existing wiki maintenance scan used in the previous D4 fix:

```bash
python3 - <<'PY'
from skills.wiki.scripts.mcp import wiki_maintenance_ops

class Ctx:
    pass

result = wiki_maintenance_ops.scan(Ctx(), difficulty=4)
print(result)
PY
```

Expected: no D4 defect for weak corroboration. A maintenance/evolution gap is acceptable and should be reported separately from defects.

- [ ] **Step 6: Commit any verification-driven fixes**

If verification required small fixes, commit them:

```bash
git status --short
git add <verified-files>
git commit -m "fix: harden ingest-url wiki verification"
git push
```

If no files changed, do not create an empty commit.

## Task 8: Final Review and Handoff

**Files:**
- All changed files from Tasks 1-7

- [ ] **Step 1: Inspect changed files**

Run:

```bash
git status --short
git log --oneline --decorate -8
git diff --stat origin/main...HEAD
```

Expected: only intentional ingest, Obsidian, dashboard, docs, and generated agent-surface files are changed.

- [ ] **Step 2: Check for worktree-local path leakage**

Run:

```bash
rg "/Users/.*/augur-wt-|augur-wt-[0-9-]+" \
  skills docs apps AGENTS.md CODEX.md .codex .gemini .claude
```

Expected: no matches. If matches appear in generated or docs files, replace them with path resolution functions, relative paths, or neutral examples.

- [ ] **Step 3: Run final focused gate**

Run:

```bash
python3 -m pytest \
  skills/ingest/augur/tests/test_url_source_card.py \
  skills/ingest/augur/tests/test_ingest_tools.py \
  skills/ingest/augur/tests/test_wiki_command_contracts.py \
  skills/obsidian/augur/tests \
  -q
python3 -m skills.ai.scripts.sync_agents check
```

Expected: tests and sync check pass.

- [ ] **Step 4: Push final branch state**

Run:

```bash
git push
git status --short --branch
```

Expected: branch is clean and aligned with `origin/wt-20260420-205555`.

- [ ] **Step 5: Report exact outcome**

Final implementation summary should include:

- Saved plan path.
- Commits created.
- Whether `ingest-url` works from MCP and dashboard.
- Whether Obsidian skill was promoted and tests passed.
- Whether generated agent surfaces are synced.
- Browser verification result.
- D4 scan result.
- Any residual risk, especially if browser or network verification was blocked.

## Self-Review

Spec coverage:

- URL capture command and MCP path: Tasks 2 and 3.
- One source card per URL under `sources/web/`: Tasks 1 and 7.
- Summary/status/routing/action metadata: Task 1.
- Deterministic hub and skill classification: Task 1.
- Obsidian MVP promotion: Task 4.
- Dashboard affordance using MCP: Task 5.
- Agent instruction focus on wiki execution: Task 6.
- Concept-first wiki compiler boundary: Tasks 3 and 6.
- Verification with tests, sync, browser, and D4 scan: Tasks 5 and 7.

Placeholder scan:

- No task relies on deferred design decisions for the MVP.
- Where repository fixture shapes may differ, the required behavior assertion is stated explicitly and must remain unchanged.

Type consistency:

- The helper returns `UrlClassification` and `SourceCardWrite`.
- The MCP output keys match the spec: `source_path`, `title`, `domain`, `hub`, `skill_candidates`, `intent`, and `wiki_compile`.
- The dashboard callback consumes the same MCP output keys.
