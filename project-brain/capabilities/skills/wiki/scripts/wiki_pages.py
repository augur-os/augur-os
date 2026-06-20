"""Wiki page CRUD operations.

Manages wiki pages in vault/wiki/ with tag manifest in runtime/wiki/.
Pages use YAML frontmatter with title, type, page_type, hub, tags, sources, updated.
"""
from __future__ import annotations

import hashlib
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from src.lib.frontmatter_utils import parse_frontmatter
from src.lib.wiki_utils import WIKILINK_RE

from src.lib.frontmatter_utils import write_vault_frontmatter


_SEE_ALSO_HEADER = "## See Also"
_LINKED_FROM_HEADER = "## Linked From"
_SUMMARY_SECTION_HEADINGS = (
    "Current Thesis",
    "What This Hub Knows",
    "Current Reality",
    "Core Pattern",
)


def _resolve_wiki_brain_id(md_file: Path) -> str | None:
    """Owning brain for a compiled wiki page (ADR-772), best-effort."""
    try:
        from src.lib.brain_path import resolve_brain_id_for_path

        return resolve_brain_id_for_path(md_file)
    except Exception:
        return None


def compute_source_fingerprint(sources: list[str]) -> str:
    """Compute a stable fingerprint for the current state of source files."""
    digest = hashlib.sha256()
    for source in sorted({str(item) for item in sources}):
        digest.update(source.encode("utf-8"))
        digest.update(b"\0")
        path = Path(source)
        if path.exists():
            try:
                data = path.read_bytes()
            except OSError:
                data = b""
            digest.update(hashlib.sha256(data).digest())
        else:
            digest.update(b"MISSING")
        digest.update(b"\0")
    return digest.hexdigest()


class WikiPages:
    """Read, write, list, and search wiki pages."""

    def __init__(
        self,
        *,
        wiki_dir: Path,
        runtime_wiki_dir: Path,
        max_log_entries: int = 30,
    ) -> None:
        self._wiki_dir = Path(wiki_dir)
        self._runtime_dir = Path(runtime_wiki_dir)
        self._max_log = max_log_entries
        self._wiki_dir.mkdir(parents=True, exist_ok=True)
        self._runtime_dir.mkdir(parents=True, exist_ok=True)

    def write(
        self,
        *,
        page: str,
        title: str,
        page_type: str | None = None,
        tags: list[str],
        sources: list[str],
        body: str,
        hub: str,
        article_metadata: dict[str, Any] | None = None,
        refresh_support: bool = True,
    ) -> Path:
        """Write or overwrite a wiki page, then update tags and index."""
        page_path = self._resolve_page_path(page)
        page_path.parent.mkdir(parents=True, exist_ok=True)

        normalized_body = self._strip_managed_sections(body).rstrip()
        stored_page_type = self._existing_page_type(page_path)
        stored_article_metadata = self._existing_article_metadata(page_path)
        effective_page_type = (page_type or "").strip() or stored_page_type or "wiki-page"
        effective_article_metadata = (
            article_metadata if article_metadata is not None else stored_article_metadata
        )
        related_pages = (
            self._find_related_pages(
                page=page,
                title=title,
                hub=hub,
                tags=tags,
                body=normalized_body,
            )
            if refresh_support
            else []
        )
        now = datetime.now(tz=timezone.utc).isoformat()
        metadata: dict[str, Any] = {
            "title": title,
            "type": "wiki-page",
            "page_type": effective_page_type,
            "hub": hub,
            "tags": tags,
            "sources": sources,
            "updated": now,
            "source_fingerprint": compute_source_fingerprint(sources),
        }
        if effective_article_metadata is not None:
            metadata["article_metadata"] = effective_article_metadata

        write_vault_frontmatter(page_path, metadata, self._with_see_also(normalized_body, related_pages))

        if refresh_support:
            self._rebuild_metadata()
            self.refresh_related_sections()
        return page_path

    def delete(self, page: str, *, rebuild_metadata: bool = True) -> bool:
        """Delete a wiki page if it exists."""
        page_path = self._resolve_page_path(page)
        if not page_path.exists():
            return False
        page_path.unlink()
        if rebuild_metadata:
            self._rebuild_metadata()
            self.refresh_related_sections()
        return True

    def refresh_related_sections(self, *, pages: list[str] | None = None) -> list[str]:
        """Recompute managed See Also and Linked From sections for existing pages."""
        target_pages = set(pages or [])
        updated: list[str] = []
        if target_pages:
            self._rebuild_metadata()
        backlinks = self._read_backlinks()
        backlink_pages = backlinks.get("pages", {}) if isinstance(backlinks, dict) else {}
        page_inventory = self.list_pages()

        for item in page_inventory:
            page_key = str(item.get("page") or "").strip()
            if not page_key:
                continue
            if target_pages and page_key not in target_pages:
                continue

            page_path = self._resolve_page_path(page_key)
            meta, body = parse_frontmatter(page_path)
            base_body = self._strip_managed_sections(body)
            related_pages = self._find_related_pages(
                page=page_key,
                title=str(meta.get("title") or page_path.stem),
                hub=str(meta.get("hub") or ""),
                tags=[str(tag) for tag in meta.get("tags", [])],
                body=base_body,
                candidate_pages=page_inventory,
            )
            linked_from_pages = [
                str(page)
                for page in backlink_pages.get(page_key, {}).get("inbound", [])
                if str(page).strip() and str(page) != page_key
            ]
            refreshed_body = self._with_managed_sections(
                base_body.rstrip(),
                related_pages,
                linked_from_pages,
            )
            if refreshed_body == body.strip():
                continue
            write_vault_frontmatter(page_path, meta, refreshed_body)
            updated.append(page_key)

        if updated:
            self._rebuild_metadata()
        return updated

    def read(self, page: str) -> dict[str, Any] | None:
        """Read a wiki page. Returns None if not found."""
        page_path = self._resolve_page_path(page)
        if not page_path.exists():
            return None
        meta, body = parse_frontmatter(page_path)
        is_system_page = self._is_system_page(page_path.relative_to(self._wiki_dir))
        return {
            "title": meta.get("title", page_path.stem),
            "type": meta.get("type", "wiki-page") if is_system_page else "wiki-page",
            "page_type": meta.get("page_type", meta.get("type", "wiki-page")),
            "hub": meta.get("hub", ""),
            "tags": meta.get("tags", []),
            "sources": meta.get("sources", []),
            "updated": meta.get("updated", ""),
            "source_fingerprint": meta.get("source_fingerprint", ""),
            "article_metadata": meta.get("article_metadata", {}),
            "body": body,
        }

    def list_pages(self, *, hub: str | None = None) -> list[dict[str, Any]]:
        """List all wiki pages, optionally filtered by hub."""
        pages = []
        for md_file in sorted(self._wiki_dir.rglob("*.md")):
            rel = md_file.relative_to(self._wiki_dir)
            if self._is_system_page(rel):
                continue
            page_key = str(rel.with_suffix(""))
            if hub and not page_key.startswith(f"{hub}/"):
                continue
            meta, _ = parse_frontmatter(md_file)
            page_record = {
                "page": page_key,
                "title": meta.get("title", md_file.stem),
                "page_type": meta.get("page_type", meta.get("type", "wiki-page")),
                "tags": meta.get("tags", []),
                "hub": meta.get("hub", ""),
                "updated": meta.get("updated", ""),
                "article_metadata": meta.get("article_metadata", {}),
            }
            brain_id = _resolve_wiki_brain_id(md_file)
            if brain_id:
                page_record["brain_id"] = brain_id
            pages.append(page_record)
        return pages

    def read_tags(self) -> dict[str, Any]:
        """Read the tags manifest from runtime."""
        tags_path = self._runtime_dir / "tags.yaml"
        if not tags_path.exists():
            return {"pages": {}}
        return yaml.safe_load(tags_path.read_text(encoding="utf-8")) or {"pages": {}}

    def refresh_metadata(self, *, compile_summary: dict[str, int] | None = None) -> None:
        """Rebuild tags.yaml, index.md, and overview.md without mutating page content."""
        if compile_summary is not None:
            self._write_compile_summary(compile_summary)
        self._rebuild_metadata(compile_summary=compile_summary)

    def refresh_support_pages(self, *, compile_summary: dict[str, int] | None = None) -> None:
        """Refresh generated support pages with optional compile status context."""
        if compile_summary is not None:
            self._write_compile_summary(compile_summary)
        self._rebuild_metadata(compile_summary=compile_summary)

    def log(self, entry: str) -> None:
        """Append a session summary to the rolling log in runtime."""
        log_path = self._runtime_dir / "log.md"
        now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        new_entry = f"## [{now}]\n\n{entry}"

        if log_path.exists():
            text = log_path.read_text(encoding="utf-8")
            entries = re.split(r"(?=^## \[)", text, flags=re.MULTILINE)
            entries = [e.strip() for e in entries if e.strip()]
        else:
            entries = []

        entries.insert(0, new_entry)
        entries = entries[: self._max_log]

        log_path.write_text("\n\n".join(entries) + "\n", encoding="utf-8")

    def search(self, query: str, *, tags: list[str] | None = None) -> list[dict[str, Any]]:
        """Search wiki pages by content using ripgrep, optionally filtered by tags."""
        matches = []
        for path in self._matching_wiki_files(query):
            if not path.exists() or path.name in ("index.md", "overview.md"):
                continue
            rel = path.relative_to(self._wiki_dir)
            page_key = str(rel.with_suffix(""))
            meta, body = parse_frontmatter(path)
            page_tags = meta.get("tags", [])
            if tags and not any(t in page_tags for t in tags):
                continue
            snippet = ""
            for ln in body.splitlines():
                if query.lower() in ln.lower():
                    snippet = ln.strip()[:200]
                    break
            matches.append({
                "page": page_key,
                "title": meta.get("title", path.stem),
                "score": 1.0,
                "snippet": snippet,
            })
        return matches

    def _matching_wiki_files(self, query: str) -> list[Path]:
        """Files containing the query, via ripgrep or a Python fallback.

        ripgrep is absent on some platforms (e.g. Windows without rg); without a
        fallback wiki search silently returns nothing. The Python branch only
        runs when rg is unavailable, mirroring the substring match used below.
        """
        try:
            result = subprocess.run(
                ["rg", "--no-heading", "-l", "-i", query, str(self._wiki_dir)],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return [Path(line) for line in result.stdout.strip().splitlines() if line]
        except (subprocess.TimeoutExpired, FileNotFoundError):
            needle = query.lower()
            hits: list[Path] = []
            for path in sorted(self._wiki_dir.rglob("*.md")):
                try:
                    if needle in path.read_text(encoding="utf-8", errors="ignore").lower():
                        hits.append(path)
                except OSError:
                    continue
            return hits

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _resolve_page_path(self, page: str) -> Path:
        """Convert a page key like 'finance/budgeting' to a full path."""
        if not page.endswith(".md"):
            page = f"{page}.md"
        return self._wiki_dir / page

    @staticmethod
    def _is_system_page(rel: Path) -> bool:
        """Return True for root-level index/overview pages that are auto-generated."""
        return rel.parent == Path(".") and rel.name in ("index.md", "overview.md")

    def _rebuild_metadata(self, *, compile_summary: dict[str, int] | None = None) -> None:
        """Rebuild tags.yaml, index.md, and overview.md in a single rglob pass."""
        if compile_summary is None:
            compile_summary = self._read_compile_summary()
        pages_data: dict[str, Any] = {}
        hubs: dict[str, list[dict[str, str]]] = {}
        page_bodies: dict[str, str] = {}

        for md_file in sorted(self._wiki_dir.rglob("*.md")):
            rel = md_file.relative_to(self._wiki_dir)
            if self._is_system_page(rel):
                continue
            page_key = str(rel.with_suffix(""))
            meta, body = parse_frontmatter(md_file)
            page_bodies[page_key] = body
            title = str(meta.get("title", md_file.stem))
            hub = str(meta.get("hub", rel.parts[0] if len(rel.parts) > 1 else "general"))
            summary = self._page_summary(title=title, body=body)

            # --- tags.yaml data ---
            pages_data[page_key] = {
                "type": meta.get("type", "wiki-page"),
                "hub": hub,
                "tags": meta.get("tags", []),
                "title": title,
                "sources": meta.get("sources", []),
                "page_type": meta.get("page_type", meta.get("type", "wiki-page")),
                "updated": meta.get("updated", ""),
                "article_metadata": meta.get("article_metadata", {}),
                "summary": summary,
            }

            # --- index.md data ---
            hubs.setdefault(hub, []).append({
                "page": page_key,
                "title": title,
                "summary": summary,
            })

        # Write tags.yaml
        tags_path = self._runtime_dir / "tags.yaml"
        tags_path.write_text(
            yaml.dump({"pages": pages_data}, allow_unicode=True, sort_keys=False, default_flow_style=False),
            encoding="utf-8",
        )
        self._write_backlinks(pages_data=pages_data, page_bodies=page_bodies)

        # Write index.md
        lines = [
            "# Wiki Index",
            "",
            "Use this index to find the right compiled page quickly. Start with hub overviews, then drill into linked topic pages.",
            "",
        ]
        for hub_name in sorted(hubs):
            lines.append(f"## {hub_name.replace('-', ' ').title()}")
            lines.append("")
            for entry in hubs[hub_name]:
                if entry["summary"]:
                    lines.append(f"- [[{entry['page']}]] {entry['title']} — {entry['summary']}")
                else:
                    lines.append(f"- [[{entry['page']}]] {entry['title']}")
            lines.append("")

        index_path = self._wiki_dir / "index.md"
        index_meta: dict[str, Any] = {
            "title": "Wiki Index",
            "type": "wiki-index",
            "updated": datetime.now(tz=timezone.utc).isoformat(),
        }
        write_vault_frontmatter(index_path, index_meta, "\n".join(lines))

        overview_lines = self._overview_lines(hubs, compile_summary=compile_summary)
        overview_path = self._wiki_dir / "overview.md"
        overview_meta: dict[str, Any] = {
            "title": "Wiki Overview",
            "type": "wiki-overview",
            "updated": datetime.now(tz=timezone.utc).isoformat(),
        }
        write_vault_frontmatter(overview_path, overview_meta, "\n".join(overview_lines))

    def _write_compile_summary(self, summary: dict[str, int]) -> None:
        compile_summary_path = self._runtime_dir / "compile-summary.yaml"
        compile_summary_path.write_text(
            yaml.dump(summary, allow_unicode=True, sort_keys=False, default_flow_style=False),
            encoding="utf-8",
        )

    def _write_backlinks(
        self,
        *,
        pages_data: dict[str, Any],
        page_bodies: dict[str, str],
    ) -> None:
        """Persist outbound/inbound graph metadata for current wiki pages."""
        existing_pages = set(pages_data)
        outbound: dict[str, set[str]] = {page: set() for page in existing_pages}
        inbound: dict[str, set[str]] = {page: set() for page in existing_pages}
        candidate_pages = [
            {
                "page": candidate_page,
                "title": candidate_meta.get("title", ""),
                "tags": candidate_meta.get("tags", []),
                "hub": candidate_meta.get("hub", ""),
            }
            for candidate_page, candidate_meta in pages_data.items()
        ]

        for page_key, page_meta in pages_data.items():
            body = page_bodies.get(page_key, "")
            outbound_body = self._strip_linked_from(body)
            inferred_body = self._strip_managed_sections(body)
            explicit_targets = {
                target.strip()
                for target in WIKILINK_RE.findall(outbound_body)
                if target.strip() in existing_pages
            }
            inferred_targets = set(
                self._find_related_pages(
                    page=page_key,
                    title=str(page_meta.get("title") or ""),
                    hub=str(page_meta.get("hub") or ""),
                    tags=[str(tag) for tag in page_meta.get("tags", [])],
                    body=inferred_body,
                    candidate_pages=candidate_pages,
                )
            )
            targets = {
                target for target in (explicit_targets | inferred_targets)
                if target in existing_pages and target != page_key
            }
            outbound[page_key].update(targets)
            for target in targets:
                inbound[target].add(page_key)

        backlinks_path = self._runtime_dir / "backlinks.yaml"
        backlinks_path.write_text(
            yaml.dump(
                {
                    "pages": {
                        page_key: {
                            "outbound": sorted(outbound[page_key]),
                            "inbound": sorted(inbound[page_key]),
                        }
                        for page_key in sorted(existing_pages)
                    }
                },
                allow_unicode=True,
                sort_keys=False,
                default_flow_style=False,
            ),
            encoding="utf-8",
        )

    def _read_backlinks(self) -> dict[str, Any]:
        backlinks_path = self._runtime_dir / "backlinks.yaml"
        if not backlinks_path.exists():
            return {"pages": {}}
        data = yaml.safe_load(backlinks_path.read_text(encoding="utf-8")) or {"pages": {}}
        if not isinstance(data, dict):
            return {"pages": {}}
        pages = data.get("pages", {})
        if not isinstance(pages, dict):
            data["pages"] = {}
        return data

    def _read_compile_summary(self) -> dict[str, int] | None:
        compile_summary_path = self._runtime_dir / "compile-summary.yaml"
        if not compile_summary_path.exists():
            return None
        data = yaml.safe_load(compile_summary_path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            return None
        return {
            str(key): int(value)
            for key, value in data.items()
            if isinstance(value, int | float)
        }

    def _existing_page_type(self, page_path: Path) -> str | None:
        """Return the current stored page subtype if the page already exists."""
        if not page_path.exists():
            return None
        meta, _ = parse_frontmatter(page_path)
        page_type = str(meta.get("page_type") or "").strip()
        if page_type:
            return page_type
        legacy_type = str(meta.get("type") or "").strip()
        return legacy_type or None

    def _existing_article_metadata(self, page_path: Path) -> dict[str, Any] | None:
        """Return the current stored article metadata if the page already exists."""
        if not page_path.exists():
            return None
        meta, _ = parse_frontmatter(page_path)
        article_metadata = meta.get("article_metadata")
        if isinstance(article_metadata, dict):
            return article_metadata
        return None

    def _find_related_pages(
        self,
        *,
        page: str,
        title: str,
        hub: str,
        tags: list[str],
        body: str,
        candidate_pages: list[dict[str, Any]] | None = None,
    ) -> list[str]:
        """Find a few relevant pages to cross-link in See Also."""
        current_tags = {tag.strip().lower() for tag in tags if tag.strip()}
        current_tokens = self._tokenize(f"{page} {title} {body}")
        scored: list[tuple[float, str]] = []
        for candidate in candidate_pages if candidate_pages is not None else self.list_pages():
            candidate_page = candidate["page"]
            if candidate_page == page:
                continue
            candidate_tags = {tag.strip().lower() for tag in candidate.get("tags", []) if str(tag).strip()}
            overlap = len(current_tags & candidate_tags)
            candidate_tokens = self._tokenize(f"{candidate_page} {candidate.get('title', '')}")
            token_overlap = len(current_tokens & candidate_tokens)
            score = overlap * 3 + token_overlap
            if candidate.get("hub") == hub:
                score += 2
            if score <= 0:
                continue
            scored.append((float(score), candidate_page))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [page_key for _, page_key in scored[:5]]

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return {
            token
            for token in re.findall(r"[a-z0-9]+", text.lower())
            if len(token) >= 3
        }

    def _with_see_also(self, body: str, related_pages: list[str]) -> str:
        """Replace or append a managed See Also section."""
        return self._with_managed_sections(body, related_pages, [])

    def _with_managed_sections(
        self,
        body: str,
        related_pages: list[str],
        linked_from_pages: list[str],
    ) -> str:
        """Replace or append the managed See Also and Linked From sections."""
        base_body = self._strip_managed_sections(body).strip()
        sections: list[str] = []
        see_also = self._render_see_also(related_pages)
        linked_from = self._render_linked_from(linked_from_pages)
        if see_also:
            sections.append(see_also)
        if linked_from:
            sections.append(linked_from)
        if not sections:
            return base_body
        managed = "\n\n".join(sections)
        if not base_body:
            return managed
        return f"{base_body}\n\n{managed}"

    @staticmethod
    def _render_see_also(related_pages: list[str]) -> str:
        if not related_pages:
            return ""
        lines = [_SEE_ALSO_HEADER, ""]
        lines.extend(f"- [[{page}]]" for page in related_pages)
        return "\n".join(lines)

    @staticmethod
    def _render_linked_from(linked_from_pages: list[str]) -> str:
        if not linked_from_pages:
            return ""
        lines = [_LINKED_FROM_HEADER, ""]
        lines.extend(f"- [[{page}]]" for page in linked_from_pages)
        return "\n".join(lines)

    @staticmethod
    def _strip_see_also(body: str) -> str:
        """Remove the managed trailing See Also section from page content."""
        return WikiPages._strip_managed_sections(body, headers=(_SEE_ALSO_HEADER,))

    @staticmethod
    def _strip_linked_from(body: str) -> str:
        """Remove the managed trailing Linked From section from page content."""
        return WikiPages._strip_managed_sections(body, headers=(_LINKED_FROM_HEADER,))

    @staticmethod
    def _strip_managed_sections(
        body: str,
        headers: tuple[str, ...] = (_SEE_ALSO_HEADER, _LINKED_FROM_HEADER),
    ) -> str:
        """Remove trailing managed cross-link sections from page content."""
        base_body = str(body or "").strip()
        if not base_body:
            return base_body
        headers_pattern = "|".join(re.escape(header) for header in headers)
        return re.sub(
            rf"\n*(?:{headers_pattern})\n.*\Z",
            "",
            base_body,
            flags=re.DOTALL,
        ).rstrip()

    def _page_summary(self, *, title: str, body: str) -> str:
        for heading in _SUMMARY_SECTION_HEADINGS:
            section = self._extract_section(body, heading)
            summary = self._first_meaningful_paragraph(section)
            if summary and not self._looks_like_scope_scaffold(summary) and not self._looks_like_placeholder_summary(summary):
                return self._truncate(summary)
        summary = self._first_meaningful_paragraph(body)
        if summary and not self._looks_like_scope_scaffold(summary) and not self._looks_like_placeholder_summary(summary):
            return self._truncate(summary)
        return ""

    def _overview_lines(
        self,
        hubs: dict[str, list[dict[str, str]]],
        *,
        compile_summary: dict[str, int] | None = None,
    ) -> list[str]:
        page_count = sum(len(entries) for entries in hubs.values())
        hub_count = len(hubs)
        lines = [
            "# Wiki Overview",
            "",
            "This wiki is the compiled knowledge layer between raw sources and query-time answers.",
            "",
            f"It currently spans {page_count} pages across {hub_count} hubs and is meant to be read as maintained synthesis, not as a dump of raw notes.",
            "",
            "## How To Use This Wiki",
            "",
            "- Start with a hub overview to understand what is stable, what shifted recently, and where the open questions still are.",
            "- Use [[index]] when you need a fast map of pages and one-line summaries before drilling deeper.",
            "- Follow wiki links inside pages to move between connected concepts instead of re-reading raw source files from scratch.",
            "",
        ]
        if compile_summary:
            lines.extend(
                [
                    "## Compilation Status",
                    "",
                    f"- {compile_summary.get('pending', 0)} pending",
                    f"- {compile_summary.get('compiled', 0)} compiled",
                    f"- {compile_summary.get('total', 0)} total indexed sources",
                    "",
                ]
            )
        lines.extend(
            [
                "## Strongest Hubs",
                "",
            ]
        )
        for hub_name in sorted(hubs):
            hub_overview = next(
                (entry for entry in hubs[hub_name] if entry["page"] == f"{hub_name}/overview"),
                hubs[hub_name][0] if hubs[hub_name] else None,
            )
            if not hub_overview:
                continue
            summary = hub_overview["summary"] or self._fallback_hub_summary(hub_name, hubs[hub_name])
            if summary:
                lines.append(f"- [[{hub_overview['page']}]] — {summary}")
            else:
                lines.append(f"- [[{hub_overview['page']}]]")
        return lines

    @staticmethod
    def _extract_section(body: str, heading: str) -> str:
        pattern = re.compile(
            rf"^## {re.escape(heading)}\s*$\n(?P<section>.*?)(?=^## |\Z)",
            re.MULTILINE | re.DOTALL,
        )
        match = pattern.search(body)
        if not match:
            return ""
        return match.group("section").strip()

    @staticmethod
    def _first_meaningful_paragraph(body: str) -> str:
        paragraphs: list[str] = []
        current: list[str] = []
        for raw_line in body.splitlines():
            line = raw_line.strip()
            if not line:
                if current:
                    paragraphs.append(" ".join(current).strip())
                    current = []
                continue
            if line.startswith("#") or line.startswith("- ") or line.startswith("* "):
                if current:
                    paragraphs.append(" ".join(current).strip())
                    current = []
                continue
            current.append(line)
        if current:
            paragraphs.append(" ".join(current).strip())
        return paragraphs[0] if paragraphs else ""

    @staticmethod
    def _looks_like_scope_scaffold(text: str) -> bool:
        return "is the compiled overview for the" in text.lower()

    @staticmethod
    def _looks_like_placeholder_summary(text: str) -> bool:
        normalized = " ".join(text.lower().split())
        return (
            normalized.startswith("metadata-only seed page generated from scanned sources")
            or "it should explain how those materials fit together in practice" in normalized
        )

    @staticmethod
    def _truncate(text: str, *, limit: int = 160) -> str:
        normalized = " ".join(text.split())
        if len(normalized) <= limit:
            return normalized
        clipped = normalized[: limit - 1].rsplit(" ", 1)[0].rstrip(",;:-")
        return f"{clipped}…"

    @staticmethod
    def _fallback_hub_summary(hub_name: str, entries: list[dict[str, str]]) -> str:
        page_count = len(entries)
        label = hub_name.replace("-", " ")
        if page_count == 1:
            return f"Entry point into the {label} hub while deeper synthesis catches up."
        return f"Entry point into the {label} hub across {page_count} compiled pages."
