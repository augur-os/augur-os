"""End-to-end tests for the wiki report agent-step render pipeline."""
from __future__ import annotations

import json
import re
import tempfile
from asyncio import run
from pathlib import Path

import yaml


def _rich_dict() -> dict:
    """A complete, valid rich dict: all required and optional fields."""
    return {
        "title": "What Your AI Knows About You",
        "name": "Test User",
        "date": "May 12, 2026",
        "synthesis": (
            "A 74-page wiki anchored in AI infrastructure with strong career positioning. "
            "422 cross-references across 74 pages, densely connected and quality-gated."
        ),
        "stats": {
            "pages": 74,
            "hubs": 7,
            "sources": 400,
            "words": "34,286",
            "cross_refs": 422,
        },
        "hub_sections": [
            {
                "name": "brain",
                "source_count": 136,
                "summary": "Control plane for advisor analytics, agent-learning compounding, and observability work.",
                "icon": "*",
                "color": "#8b5cf6",
            },
            {
                "name": "career",
                "source_count": 119,
                "summary": "AI-transformation leadership positioning, career strategy, and content operations work.",
                "icon": "^",
                "color": "#10b981",
            },
        ],
        "who_you_are": {
            "what_you_do": "Building Augur, local-first AI infrastructure that personalizes AI clients.",
            "how_you_think": "Decision-first; every architectural move gets an ADR. Loop-driven.",
        },
        "expertise": [
            {"domain": "Cross-Client AI Harness", "level": "Expert", "percentage": 95, "color": "#6366f1"},
            {"domain": "ADR-Driven Architecture", "level": "Expert", "percentage": 92, "color": "#8b5cf6"},
        ],
        "patterns": [
            {"title": "Discipline beats velocity", "description": "100% quality-passing across all pages."},
            {"title": "Cross-ref compounding", "description": "5.7 outgoing links per page, densely connected."},
        ],
        "blind_spots": [
            {"title": "Life hub thin", "description": "Only 8 pages; work dominates.", "severity": "medium"},
            {"title": "General hub catch-all", "description": "2 pages, 877 words.", "severity": "low"},
        ],
        "portfolio": {"profile": "", "logo": "", "cover": "", "hub_images": {}},
    }


def _strip_html(html: str) -> str:
    text = re.sub(r"<style.*?</style>", "", html, flags=re.DOTALL)
    text = re.sub(r"<script.*?</script>", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def test_validator_rejects_empty_dict():
    from skills.wiki.scripts.wiki_report_contract import validate_rich_dict

    result = validate_rich_dict({})

    assert not result.success
    assert "synthesis" in result.missing_required
    assert "hub_sections" in result.missing_required


def test_mcp_generate_tool_returns_agent_step_required_for_invalid_input():
    from skills.wiki.scripts.mcp.wiki_tools import register_wiki_tools

    class FakeMcp:
        def __init__(self):
            self.tools = {}

        def tool(self, name, annotations=None):
            def decorator(func):
                self.tools[name] = func
                return func

            return decorator

    class Metrics:
        def track_tool(self, name, skill):
            return None

    mcp = FakeMcp()
    register_wiki_tools(mcp, lambda func: func, Metrics())

    result = json.loads(run(mcp.tools["wiki-report-generate"](report_json="{}")))

    assert result["success"] is False
    assert result["error"] == "agent_step_required"
    assert "synthesis" in result["missing_required"]
    assert "hub_sections" in result["missing_required"]
    assert result["contract_path"] == "project-brain/capabilities/skills/rag/commands/wiki.md#wiki-report"


def test_full_rich_dict_renders_all_sections():
    from skills.wiki.scripts.mcp.wiki_tools import _generate_report_html

    with tempfile.TemporaryDirectory() as temp_dir:
        result = json.loads(_generate_report_html(_rich_dict(), output_dir=temp_dir))
        assert result["success"], result

        html_path = Path(result["html_path"])
        assert html_path.exists()
        text = _strip_html(html_path.read_text(encoding="utf-8"))

        assert "What Your AI Knows About You" in text
        assert "Test User" in text
        assert "A 74-page wiki anchored" in text
        assert "74" in text
        assert "7" in text
        assert "400" in text
        assert "Building Augur" in text
        assert "Decision-first" in text
        assert "Cross-Client AI Harness" in text
        assert "Expert" in text
        assert "brain" in text
        assert "Control plane for advisor analytics" in text
        assert "career" in text
        assert "AI-transformation leadership" in text
        assert "Discipline beats velocity" in text
        assert "100% quality-passing" in text
        assert "Life hub thin" in text
        assert "medium" not in text
        assert "General hub catch-all" in text


def test_minimal_rich_dict_renders_no_optional_sections():
    from skills.wiki.scripts.mcp.wiki_tools import _generate_report_html

    minimal = {
        "title": "Minimal",
        "name": "X",
        "date": "2026-05-12",
        "synthesis": "Synthesis " + ("x" * 100),
        "stats": {"pages": 1, "hubs": 1, "sources": 1, "words": "1", "cross_refs": 0},
        "hub_sections": [
            {
                "name": "brain",
                "source_count": 1,
                "summary": "Summary " + ("y" * 60),
                "icon": "*",
                "color": "#8b5cf6",
            },
        ],
        "portfolio": {"profile": "", "logo": "", "cover": "", "hub_images": {}},
    }

    with tempfile.TemporaryDirectory() as temp_dir:
        result = json.loads(_generate_report_html(minimal, output_dir=temp_dir))
        assert result["success"], result

        text = _strip_html(Path(result["html_path"]).read_text(encoding="utf-8"))

        assert "Synthesis " in text
        assert "Summary " in text
        assert "Expertise Stack" not in text
        assert "Patterns Your AI Noticed" not in text
        assert "Blind Spots" not in text


def test_sidecar_yaml_written_alongside_html():
    from skills.wiki.scripts.mcp.wiki_tools import _generate_report_html

    with tempfile.TemporaryDirectory() as temp_dir:
        result = json.loads(_generate_report_html(_rich_dict(), output_dir=temp_dir))
        html_path = Path(result["html_path"])
        sidecar_path = Path(result["sidecar_path"])

        assert sidecar_path == html_path.with_suffix("").with_suffix(".meta.yaml")
        assert sidecar_path.exists()
        sidecar = yaml.safe_load(sidecar_path.read_text(encoding="utf-8"))

        assert sidecar["slug"].startswith("second-brain-report-")
        assert sidecar["kind"] == "generated"
        assert sidecar["hub"] == "brain"
        assert sidecar["source"]["type"] == "agent-synthesized"
        assert sidecar["tags"] == ["wiki", "report", "second-brain"]


def test_generate_report_html_passes_pages_and_connections_to_chart_renderer(monkeypatch):
    from skills.wiki.scripts import wiki_report_charts, wiki_report_render
    from skills.wiki.scripts.mcp.wiki_tools import _generate_report_html

    captured = {}

    def fake_chart(name):
        def render(data, *, output_dir):
            captured[name] = {
                "pages": list(data.pages),
                "connections": list(data.connections),
            }
            path = Path(output_dir) / f"{name}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"png")
            return path

        return render

    def fake_pdf(report, *, output_path):
        output_path.write_bytes(b"%PDF-1.4\n")
        return output_path

    monkeypatch.setattr(wiki_report_charts, "render_radar_chart", fake_chart("radar"))
    monkeypatch.setattr(wiki_report_charts, "render_knowledge_graph", fake_chart("graph"))
    monkeypatch.setattr(wiki_report_charts, "render_hub_distribution", fake_chart("distribution"))
    monkeypatch.setattr(wiki_report_render, "render_pdf", fake_pdf)

    report = _rich_dict()
    report["pages"] = [
        {
            "page": "concepts/agent-learning-compounding-pipeline",
            "title": "Agent Learning Compounding Pipeline",
            "hub": "brain",
            "cross_ref_count": 2,
        }
    ]
    report["connections"] = [
        {
            "from": "concepts/agent-learning-compounding-pipeline",
            "to": "concepts/knowledge-automation-command-loops",
        }
    ]

    with tempfile.TemporaryDirectory() as temp_dir:
        result = json.loads(_generate_report_html(report, output_dir=temp_dir))

    assert result["success"], result
    assert captured["graph"]["pages"] == report["pages"]
    assert captured["graph"]["connections"] == report["connections"]
