# Wiki Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `/wiki report` — a command that generates a polished "Second Brain Intelligence Report" as PDF + HTML, with human-style insights, charts, knowledge graph, and portfolio images.

**Architecture:** Three Python modules in `skills/ingest/scripts/`: data aggregation (wiki_report.py), chart generation (wiki_report_charts.py), and rendering (wiki_report_render.py). The agent synthesizes human insights using LLM capability, then calls the MCP tool `wiki-report-generate` which mechanically renders PDF + HTML. A Jinja2 template handles HTML, ReportLab handles PDF.

**Tech Stack:** Python 3.11+, ReportLab (PDF), Jinja2 (HTML), matplotlib + networkx (charts)

**Spec:** `docs/superpowers/specs/2026-04-11-wiki-report-design.md`

---

## File Structure

### Create

| File | Responsibility |
|------|---------------|
| `skills/ingest/scripts/wiki_report.py` | Aggregate wiki data: stats, connections, hub summaries, cross-refs |
| `skills/ingest/scripts/wiki_report_charts.py` | Render knowledge radar, graph, and distribution bar as PNG |
| `skills/ingest/scripts/wiki_report_render.py` | ReportLab PDF + Jinja2 HTML rendering from structured report data |
| `skills/ingest/assets/templates/report.html.j2` | Dark mode demo-style HTML template |
| `skills/ingest/commands/wiki-report.md` | `/wiki report` command definition |
| `skills/ingest/augur/tests/test_wiki_report.py` | Data aggregation tests |
| `skills/ingest/augur/tests/test_wiki_report_charts.py` | Chart generation tests |

### Modify

| File | Change |
|------|--------|
| `skills/ingest/scripts/mcp/wiki_tools.py` | Add `wiki-report-generate` and `wiki-report-data` tools |
| `skills/ingest/SKILL.md` | Add report tools and command |

---

## Task 1: Report Data Aggregator

**Files:**
- Create: `skills/ingest/scripts/wiki_report.py`
- Test: `skills/ingest/augur/tests/test_wiki_report.py`

- [ ] **Step 1: Write the failing test**

Create `skills/ingest/augur/tests/test_wiki_report.py`:

```python
"""Tests for wiki report data aggregation."""
from pathlib import Path

from scripts.wiki_pages import WikiPages
from scripts.wiki_report import ReportData, aggregate_report_data


def _seed_wiki(tmp_path):
    """Create a small wiki for testing."""
    wiki_dir = tmp_path / "wiki"
    runtime_dir = tmp_path / "runtime"
    wp = WikiPages(wiki_dir=wiki_dir, runtime_wiki_dir=runtime_dir / "wiki")

    wp.write(page="dev/architecture", title="Architecture", hub="dev",
             tags=["mcp", "dashboard", "plugin"],
             sources=["adr-001.md", "adr-005.md", "arch.md"],
             body="# Architecture\n\nAugur uses MCP as the execution gateway.\n\n## See Also\n\n- [[dev/skills-system]]\n- [[dev/dashboard]]")
    wp.write(page="dev/skills-system", title="Skills System", hub="dev",
             tags=["skills", "plugin", "discovery"],
             sources=["adr-163.md", "adr-479.md"],
             body="# Skills System\n\nSkills are self-contained packages.\n\n## See Also\n\n- [[dev/architecture]]")
    wp.write(page="dev/dashboard", title="Dashboard", hub="dev",
             tags=["nextjs", "turbopack", "blocks"],
             sources=["adr-490.md"],
             body="# Dashboard\n\nNext.js dashboard with block system.\n\n## See Also\n\n- [[dev/architecture]]")
    wp.write(page="career/job-search", title="Job Search", hub="career",
             tags=["applications", "tracking", "strategy"],
             sources=["applications.md", "pipeline.md"],
             body="# Job Search\n\nActive job search with 6 CV variants.")
    wp.write(page="finance/overview", title="Finance", hub="finance",
             tags=["budget", "rsu", "tax"],
             sources=["goals.md"],
             body="# Finance\n\nRSU and tax planning.")
    return wp, wiki_dir, runtime_dir


def test_aggregate_returns_report_data(tmp_path):
    wp, wiki_dir, runtime_dir = _seed_wiki(tmp_path)
    data = aggregate_report_data(wiki_dir=wiki_dir, runtime_wiki_dir=runtime_dir / "wiki")
    assert isinstance(data, ReportData)


def test_stats(tmp_path):
    wp, wiki_dir, runtime_dir = _seed_wiki(tmp_path)
    data = aggregate_report_data(wiki_dir=wiki_dir, runtime_wiki_dir=runtime_dir / "wiki")
    assert data.stats["total_pages"] == 5
    assert data.stats["total_hubs"] == 3
    assert data.stats["total_sources"] > 0
    assert data.stats["total_words"] > 0
    assert data.stats["total_cross_refs"] > 0


def test_hubs(tmp_path):
    wp, wiki_dir, runtime_dir = _seed_wiki(tmp_path)
    data = aggregate_report_data(wiki_dir=wiki_dir, runtime_wiki_dir=runtime_dir / "wiki")
    assert "dev" in data.hubs
    assert data.hubs["dev"]["page_count"] == 3
    assert data.hubs["dev"]["source_count"] > 0


def test_connections(tmp_path):
    wp, wiki_dir, runtime_dir = _seed_wiki(tmp_path)
    data = aggregate_report_data(wiki_dir=wiki_dir, runtime_wiki_dir=runtime_dir / "wiki")
    assert len(data.connections) > 0
    assert any(c["from"] == "dev/architecture" for c in data.connections)


def test_pages_have_word_counts(tmp_path):
    wp, wiki_dir, runtime_dir = _seed_wiki(tmp_path)
    data = aggregate_report_data(wiki_dir=wiki_dir, runtime_wiki_dir=runtime_dir / "wiki")
    for page in data.pages:
        assert "word_count" in page
        assert page["word_count"] > 0


def test_portfolio_scanning(tmp_path):
    wp, wiki_dir, runtime_dir = _seed_wiki(tmp_path)
    portfolio = tmp_path / "portfolio"
    portfolio.mkdir()
    (portfolio / "profile.jpg").write_bytes(b"\xff\xd8\xff")  # JPEG magic
    (portfolio / "dev-screenshot.png").write_bytes(b"\x89PNG")

    data = aggregate_report_data(
        wiki_dir=wiki_dir, runtime_wiki_dir=runtime_dir / "wiki",
        portfolio_dir=portfolio,
    )
    assert data.portfolio["profile"] is not None
    assert "dev" in data.portfolio["hub_images"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd skills/ingest && PYTHONPATH=. python -m pytest augur/tests/test_wiki_report.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write wiki_report.py**

Create `skills/ingest/scripts/wiki_report.py`:

```python
"""Aggregate wiki data into structured report data.

Reads all wiki pages, computes stats, extracts cross-references,
scans portfolio folder, and builds a ReportData object that the
renderer and agent use.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .wiki_pages import WikiPages

_WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"}


@dataclass
class ReportData:
    """Structured data for report rendering."""
    stats: dict[str, Any] = field(default_factory=dict)
    hubs: dict[str, dict[str, Any]] = field(default_factory=dict)
    pages: list[dict[str, Any]] = field(default_factory=list)
    connections: list[dict[str, str]] = field(default_factory=list)
    portfolio: dict[str, Any] = field(default_factory=dict)


def aggregate_report_data(
    *,
    wiki_dir: Path,
    runtime_wiki_dir: Path,
    portfolio_dir: Path | None = None,
) -> ReportData:
    """Read all wiki pages and build report data."""
    wp = WikiPages(wiki_dir=wiki_dir, runtime_wiki_dir=runtime_wiki_dir)
    all_pages = wp.list_pages()

    pages_data: list[dict[str, Any]] = []
    connections: list[dict[str, str]] = []
    hubs: dict[str, dict[str, Any]] = {}
    total_words = 0
    total_sources = 0
    all_source_names: set[str] = set()

    for page_meta in all_pages:
        page_key = page_meta["page"]
        full = wp.read(page_key)
        if full is None:
            continue

        body = full.get("body", "")
        word_count = len(body.split())
        total_words += word_count
        sources = full.get("sources", [])
        total_sources += len(sources)
        all_source_names.update(sources)
        hub = full.get("hub", "general")

        # Extract wikilinks as connections
        for match in _WIKILINK_RE.finditer(body):
            target = match.group(1).strip()
            connections.append({"from": page_key, "to": target})

        # Aggregate hub stats
        if hub not in hubs:
            hubs[hub] = {"page_count": 0, "source_count": 0, "word_count": 0, "tags": set()}
        hubs[hub]["page_count"] += 1
        hubs[hub]["source_count"] += len(sources)
        hubs[hub]["word_count"] += word_count
        hubs[hub]["tags"].update(full.get("tags", []))

        pages_data.append({
            "page": page_key,
            "title": full.get("title", ""),
            "hub": hub,
            "tags": full.get("tags", []),
            "sources": sources,
            "word_count": word_count,
            "cross_ref_count": len(_WIKILINK_RE.findall(body)),
            "body_preview": body[:300],
        })

    # Convert tag sets to lists for serialization
    for hub_data in hubs.values():
        hub_data["tags"] = sorted(hub_data["tags"])

    # Portfolio scanning
    portfolio = {"profile": None, "logo": None, "cover": None, "hub_images": {}}
    if portfolio_dir and portfolio_dir.is_dir():
        for img in portfolio_dir.iterdir():
            if img.suffix.lower() not in _IMAGE_EXTS:
                continue
            stem = img.stem.lower()
            if stem.startswith("profile"):
                portfolio["profile"] = str(img)
            elif stem.startswith("logo"):
                portfolio["logo"] = str(img)
            elif stem.startswith("cover"):
                portfolio["cover"] = str(img)
            else:
                # Match hub-* pattern
                for hub_name in hubs:
                    if stem.startswith(f"{hub_name}-") or stem.startswith(f"{hub_name}_"):
                        portfolio["hub_images"].setdefault(hub_name, []).append(str(img))
                        break

    return ReportData(
        stats={
            "total_pages": len(pages_data),
            "total_hubs": len(hubs),
            "total_sources": len(all_source_names),
            "total_words": total_words,
            "total_cross_refs": len(connections),
        },
        hubs=hubs,
        pages=pages_data,
        connections=connections,
        portfolio=portfolio,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd skills/ingest && PYTHONPATH=. python -m pytest augur/tests/test_wiki_report.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add skills/ingest/scripts/wiki_report.py skills/ingest/augur/tests/test_wiki_report.py
git commit -m "feat(wiki-report): data aggregator with stats, connections, and portfolio scanning"
```

---

## Task 2: Chart Generators

**Files:**
- Create: `skills/ingest/scripts/wiki_report_charts.py`
- Test: `skills/ingest/augur/tests/test_wiki_report_charts.py`

- [ ] **Step 1: Write the failing test**

Create `skills/ingest/augur/tests/test_wiki_report_charts.py`:

```python
"""Tests for wiki report chart generation."""
from pathlib import Path

from scripts.wiki_report import ReportData
from scripts.wiki_report_charts import render_radar_chart, render_knowledge_graph, render_hub_distribution


def _sample_data() -> ReportData:
    return ReportData(
        stats={"total_pages": 10, "total_hubs": 3, "total_sources": 100, "total_words": 5000, "total_cross_refs": 20},
        hubs={
            "dev": {"page_count": 5, "source_count": 60, "word_count": 3000, "tags": ["mcp", "dashboard"]},
            "career": {"page_count": 3, "source_count": 30, "word_count": 1500, "tags": ["jobs", "cv"]},
            "finance": {"page_count": 2, "source_count": 10, "word_count": 500, "tags": ["budget"]},
        },
        pages=[
            {"page": "dev/arch", "title": "Architecture", "hub": "dev", "tags": ["mcp"], "sources": [], "word_count": 400, "cross_ref_count": 3, "body_preview": ""},
            {"page": "dev/skills", "title": "Skills", "hub": "dev", "tags": ["skills"], "sources": [], "word_count": 300, "cross_ref_count": 2, "body_preview": ""},
            {"page": "career/search", "title": "Job Search", "hub": "career", "tags": ["jobs"], "sources": [], "word_count": 350, "cross_ref_count": 1, "body_preview": ""},
        ],
        connections=[
            {"from": "dev/arch", "to": "dev/skills"},
            {"from": "dev/skills", "to": "dev/arch"},
            {"from": "dev/arch", "to": "career/search"},
        ],
        portfolio={},
    )


def test_render_radar_chart(tmp_path):
    data = _sample_data()
    path = render_radar_chart(data, output_dir=tmp_path)
    assert path.exists()
    assert path.suffix == ".png"
    assert path.stat().st_size > 1000  # not empty


def test_render_knowledge_graph(tmp_path):
    data = _sample_data()
    path = render_knowledge_graph(data, output_dir=tmp_path)
    assert path.exists()
    assert path.suffix == ".png"
    assert path.stat().st_size > 1000


def test_render_hub_distribution(tmp_path):
    data = _sample_data()
    path = render_hub_distribution(data, output_dir=tmp_path)
    assert path.exists()
    assert path.suffix == ".png"
    assert path.stat().st_size > 1000
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd skills/ingest && PYTHONPATH=. python -m pytest augur/tests/test_wiki_report_charts.py -v`
Expected: FAIL

- [ ] **Step 3: Write wiki_report_charts.py**

Create `skills/ingest/scripts/wiki_report_charts.py`:

```python
"""Render report charts as PNG images.

Three charts: knowledge radar, knowledge graph, hub distribution.
All use matplotlib with a dark theme matching the report style.
"""
from __future__ import annotations

import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt
import numpy as np

from .wiki_report import ReportData

# Dark theme colors matching the report
_BG = "#0f172a"
_CARD_BG = "#1e293b"
_TEXT = "#e2e8f0"
_MUTED = "#64748b"
_HUB_COLORS = [
    "#3b82f6", "#ec4899", "#22c55e", "#f59e0b", "#8b5cf6",
    "#06b6d4", "#f43f5e", "#10b981", "#6366f1", "#a855f7",
]


def _hub_color(index: int) -> str:
    return _HUB_COLORS[index % len(_HUB_COLORS)]


def render_radar_chart(data: ReportData, *, output_dir: Path) -> Path:
    """Render a knowledge radar/spider chart showing depth per domain."""
    output_dir.mkdir(parents=True, exist_ok=True)
    hubs = data.hubs
    if not hubs:
        # Empty chart
        fig, ax = plt.subplots(figsize=(6, 6), facecolor=_BG)
        ax.set_facecolor(_BG)
        ax.text(0.5, 0.5, "No data", ha="center", va="center", color=_MUTED, fontsize=14)
        ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
        path = output_dir / "radar.png"
        fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=_BG)
        plt.close(fig)
        return path

    # Sort hubs by source count, take top 8
    sorted_hubs = sorted(hubs.items(), key=lambda x: x[1]["source_count"], reverse=True)[:8]
    labels = [h[0].title() for h in sorted_hubs]
    max_sources = max(h[1]["source_count"] for h in sorted_hubs) or 1
    values = [h[1]["source_count"] / max_sources for h in sorted_hubs]

    N = len(labels)
    angles = np.linspace(0, 2 * math.pi, N, endpoint=False).tolist()
    values_closed = values + [values[0]]
    angles_closed = angles + [angles[0]]

    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True), facecolor=_BG)
    ax.set_facecolor(_BG)

    # Grid
    ax.set_rlabel_position(0)
    ax.set_yticks([0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels([])
    ax.set_xticks(angles)
    ax.set_xticklabels(labels, color=_TEXT, fontsize=10, fontweight="bold")
    ax.spines["polar"].set_color(_MUTED)
    ax.tick_params(colors=_MUTED)
    for spine in ax.spines.values():
        spine.set_color("#334155")
    ax.yaxis.grid(color="#334155", linewidth=0.5)
    ax.xaxis.grid(color="#334155", linewidth=0.5)

    # Data
    ax.plot(angles_closed, values_closed, color="#6366f1", linewidth=2)
    ax.fill(angles_closed, values_closed, color="#6366f1", alpha=0.15)
    for angle, val, color_idx in zip(angles, values, range(N)):
        ax.plot(angle, val, "o", color=_hub_color(color_idx), markersize=8, zorder=5)

    path = output_dir / "radar.png"
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=_BG)
    plt.close(fig)
    return path


def render_knowledge_graph(data: ReportData, *, output_dir: Path) -> Path:
    """Render a force-directed knowledge graph from wikilink connections."""
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        import networkx as nx
    except ImportError:
        # Fallback: simple placeholder
        fig, ax = plt.subplots(figsize=(8, 5), facecolor=_BG)
        ax.set_facecolor(_BG)
        ax.text(0.5, 0.5, "networkx not installed", ha="center", va="center", color=_MUTED, fontsize=14)
        ax.axis("off")
        path = output_dir / "graph.png"
        fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=_BG)
        plt.close(fig)
        return path

    G = nx.DiGraph()

    # Add nodes from pages
    hub_color_map = {}
    for i, hub_name in enumerate(sorted(data.hubs.keys())):
        hub_color_map[hub_name] = _hub_color(i)

    for page in data.pages:
        G.add_node(page["page"], hub=page["hub"], title=page["title"],
                    size=max(page["cross_ref_count"] * 100 + 200, 200))

    # Add edges from connections
    for conn in data.connections:
        if conn["from"] in G and conn["to"] in G:
            G.add_edge(conn["from"], conn["to"])

    if len(G.nodes) == 0:
        fig, ax = plt.subplots(figsize=(8, 5), facecolor=_BG)
        ax.set_facecolor(_BG)
        ax.text(0.5, 0.5, "No pages", ha="center", va="center", color=_MUTED)
        ax.axis("off")
        path = output_dir / "graph.png"
        fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=_BG)
        plt.close(fig)
        return path

    fig, ax = plt.subplots(figsize=(10, 6), facecolor=_BG)
    ax.set_facecolor(_BG)
    ax.axis("off")

    pos = nx.spring_layout(G, k=2.5, iterations=50, seed=42)
    node_colors = [hub_color_map.get(G.nodes[n].get("hub", ""), _MUTED) for n in G.nodes]
    node_sizes = [G.nodes[n].get("size", 300) for n in G.nodes]

    nx.draw_networkx_edges(G, pos, ax=ax, edge_color="#334155", alpha=0.6, arrows=False, width=1)
    nx.draw_networkx_nodes(G, pos, ax=ax, node_color=node_colors, node_size=node_sizes, alpha=0.9)

    labels = {n: G.nodes[n].get("title", n.split("/")[-1])[:12] for n in G.nodes}
    nx.draw_networkx_labels(G, pos, labels, ax=ax, font_size=7, font_color=_TEXT, font_weight="bold")

    path = output_dir / "graph.png"
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=_BG)
    plt.close(fig)
    return path


def render_hub_distribution(data: ReportData, *, output_dir: Path) -> Path:
    """Render a horizontal stacked bar showing source distribution by hub."""
    output_dir.mkdir(parents=True, exist_ok=True)
    hubs = data.hubs
    if not hubs:
        fig, ax = plt.subplots(figsize=(8, 1.5), facecolor=_BG)
        ax.set_facecolor(_BG)
        ax.text(0.5, 0.5, "No data", ha="center", va="center", color=_MUTED)
        ax.axis("off")
        path = output_dir / "distribution.png"
        fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=_BG)
        plt.close(fig)
        return path

    sorted_hubs = sorted(hubs.items(), key=lambda x: x[1]["source_count"], reverse=True)

    fig, ax = plt.subplots(figsize=(10, 1.8), facecolor=_BG)
    ax.set_facecolor(_BG)

    left = 0
    for i, (hub_name, hub_data) in enumerate(sorted_hubs):
        width = hub_data["source_count"]
        color = _hub_color(i)
        bar = ax.barh(0, width, left=left, height=0.6, color=color, edgecolor=_BG, linewidth=1)
        if width > 30:
            ax.text(left + width / 2, 0, f"{hub_name.title()}\n{width}",
                    ha="center", va="center", color="white", fontsize=8, fontweight="bold")
        left += width

    ax.set_xlim(0, left)
    ax.set_ylim(-0.5, 0.5)
    ax.axis("off")

    path = output_dir / "distribution.png"
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=_BG)
    plt.close(fig)
    return path
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd skills/ingest && PYTHONPATH=. python -m pytest augur/tests/test_wiki_report_charts.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add skills/ingest/scripts/wiki_report_charts.py skills/ingest/augur/tests/test_wiki_report_charts.py
git commit -m "feat(wiki-report): chart generators — radar, knowledge graph, hub distribution"
```

---

## Task 3: HTML Template

**Files:**
- Create: `skills/ingest/assets/templates/report.html.j2`

- [ ] **Step 1: Create the Jinja2 HTML template**

Create `skills/ingest/assets/templates/report.html.j2` — a self-contained dark-mode HTML file with inline CSS. The template receives a `report` object with:
- `report.title`, `report.subtitle`, `report.date`
- `report.synthesis` (the AI-written one-paragraph hook)
- `report.stats` (pages, hubs, sources, words, cross_refs)
- `report.who_you_are` (what_you_do, how_you_think paragraphs)
- `report.expertise` (list of {domain, level, percentage})
- `report.hub_sections` (list of {name, color, source_count, summary})
- `report.patterns` (list of {title, description})
- `report.blind_spots` (list of {title, description, severity})
- `report.charts` (radar_path, graph_path, distribution_path as base64 data URIs)
- `report.portfolio` (profile, logo, cover, hub_images)

The template should match the dark-mode demo style from the brainstorming mockup:
- Background: #0f172a
- Cards: #1e293b
- Gradient cover with stat bar
- Hub cards with colored left borders
- Patterns/blind spots in two columns
- Knowledge graph and radar chart embedded as images
- Footer with Augur branding and Karpathy quote

Key CSS: all inline in a `<style>` block. No external dependencies. Images embedded as base64 data URIs so the HTML is fully self-contained.

- [ ] **Step 2: Commit**

```bash
mkdir -p skills/ingest/assets/templates
git add skills/ingest/assets/templates/report.html.j2
git commit -m "feat(wiki-report): dark mode demo HTML template"
```

---

## Task 4: PDF + HTML Renderer

**Files:**
- Create: `skills/ingest/scripts/wiki_report_render.py`

- [ ] **Step 1: Write the renderer**

Create `skills/ingest/scripts/wiki_report_render.py`:

The renderer takes a structured report dict (same shape as the Jinja2 template expects) and produces:
1. **HTML**: Load `report.html.j2`, render with Jinja2, write to output path. Embed chart PNGs as base64 data URIs. Embed portfolio images as base64.
2. **PDF**: Use ReportLab to create a 4-page PDF matching the HTML layout. Embed the same chart PNGs and portfolio images.

Key functions:
```python
def render_html(report: dict, *, output_path: Path, template_dir: Path) -> Path:
    """Render report as self-contained HTML."""

def render_pdf(report: dict, *, output_path: Path) -> Path:
    """Render report as PDF using ReportLab."""

def _image_to_data_uri(path: str | Path) -> str:
    """Convert an image file to a base64 data URI for HTML embedding."""
```

The PDF rendering uses ReportLab's `SimpleDocTemplate` or `BaseDocTemplate` with custom page templates for:
- Cover page (gradient background, centered title, stat bar)
- Content pages (hub sections, patterns/blind spots)

Colors, fonts, and layout should match the dark-mode demo style.

- [ ] **Step 2: Test HTML rendering manually**

```bash
cd skills/ingest && PYTHONPATH=. python3 -c "
from scripts.wiki_report_render import render_html
from pathlib import Path
# Test with minimal report data
report = {
    'title': 'Test Report', 'subtitle': 'Demo', 'date': '2026-04-11',
    'synthesis': 'This is a test synthesis paragraph.',
    'stats': {'pages': 5, 'hubs': 3, 'sources': 100, 'words': 5000, 'cross_refs': 20},
    'who_you_are': {'what_you_do': 'Test work description.', 'how_you_think': 'Test thinking patterns.'},
    'expertise': [{'domain': 'Dev', 'level': 'Expert', 'percentage': 95}],
    'hub_sections': [{'name': 'Dev', 'color': '#3b82f6', 'source_count': 60, 'summary': 'Test summary.'}],
    'patterns': [{'title': 'Test Pattern', 'description': 'A pattern.'}],
    'blind_spots': [{'title': 'Test Gap', 'description': 'A gap.', 'severity': 'warning'}],
    'charts': {'radar': '', 'graph': '', 'distribution': ''},
    'portfolio': {'profile': None, 'logo': None, 'cover': None, 'hub_images': {}},
}
path = render_html(report, output_path=Path('/tmp/test-report.html'),
                   template_dir=Path('assets/templates'))
print(f'HTML: {path} ({path.stat().st_size} bytes)')
"
```

- [ ] **Step 3: Commit**

```bash
git add skills/ingest/scripts/wiki_report_render.py
git commit -m "feat(wiki-report): PDF + HTML renderer with ReportLab and Jinja2"
```

---

## Task 5: MCP Tools + Command

**Files:**
- Modify: `skills/ingest/scripts/mcp/wiki_tools.py`
- Create: `skills/ingest/commands/wiki-report.md`
- Modify: `skills/ingest/SKILL.md`

- [ ] **Step 1: Add report MCP tools to wiki_tools.py**

Add two tools to `register_wiki_tools()`:

**`wiki-report-data`** (read) — calls `aggregate_report_data()` and returns stats, hub summaries, connections, portfolio info as JSON. The agent uses this to understand the wiki before writing insights.

**`wiki-report-generate`** (mutation) — takes a structured report dict (JSON string with all sections, insights, stats, chart paths), calls `render_html()` and `render_pdf()`, returns file paths.

- [ ] **Step 2: Write /wiki report command**

Create `skills/ingest/commands/wiki-report.md`:

```markdown
---
id: wiki-report
description: Generate a Second Brain Intelligence Report as PDF + HTML
skill: ingest
tags: [wiki, report, demo, viral]
---

Generate a polished "Second Brain Intelligence Report" — a shareable PDF + HTML
artifact with human-style insights about what your AI knows about you.

## Usage

```
/wiki report [--style demo] [--hub <hub>] [--output <path>]
```

## Steps

1. Call `wiki-report-data` to get wiki stats, hub summaries, connections, and portfolio info
2. Review the data and write human-style insights:
   - **One-paragraph synthesis** — 2-3 sentences summarizing who this person is based on ALL the data
   - **What You Do** — narrative about their work and projects
   - **How You Think** — decision patterns and values
   - **Expertise Stack** — ranked domains with human labels (Expert/Advanced/Active/Growing)
   - **Hub summaries** — for each hub, a paragraph of actual insight (not page counts)
   - **Patterns** — 3-4 cross-domain patterns the data reveals
   - **Blind Spots** — 2-3 knowledge gaps with specific recommendations
3. Structure the insights into a report JSON matching the template schema
4. Call `wiki-report-generate` with the structured report data
5. Report the output paths to the user

## Quality Guide

- Write like a personal analyst who READ everything, not a dashboard
- Be specific: "6 CV variants tailored for different roles" not "career documents"
- Be insightful: "your engineering and career hubs are tightly connected" not "high cross-references"
- Be honest about gaps: "your financial brain is almost empty" not "limited financial data"
- The one-paragraph synthesis is the viral hook — make it feel like someone who KNOWS this person
```

- [ ] **Step 3: Update SKILL.md**

Add `wiki-report-generate` and `wiki-report-data` to `x-augur-mcp-tools` list.

- [ ] **Step 4: Commit**

```bash
git add skills/ingest/scripts/mcp/wiki_tools.py skills/ingest/commands/wiki-report.md skills/ingest/SKILL.md
git commit -m "feat(wiki-report): MCP tools, command definition, and SKILL.md update"
```

---

## Dependencies Between Tasks

```
Task 1 (Data Aggregator)
  ↓
Task 2 (Charts) ──→ Task 4 (Renderer) ──→ Task 5 (MCP + Command)
Task 3 (Template) ─↗
```

Tasks 1 and 3 can run in parallel.
Task 2 depends on Task 1.
Task 4 depends on Tasks 2 and 3.
Task 5 depends on Task 4.
