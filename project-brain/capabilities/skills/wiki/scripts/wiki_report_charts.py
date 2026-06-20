"""Render report charts as PNG images.

Three charts: knowledge radar, knowledge graph, hub distribution.
All use matplotlib with a dark theme matching the report style.
"""
from __future__ import annotations

import math
import struct
import sys
import zlib
from pathlib import Path

try:
    import matplotlib
    matplotlib.use("Agg")  # non-interactive backend
    import matplotlib.pyplot as plt
except ImportError:
    matplotlib = None
    plt = None

try:
    import numpy as np
except ImportError:
    np = None
else:
    # Some environments expose a namespace-only `numpy` package without the
    # actual runtime API. Treat that the same as "not installed" so chart
    # generation falls back cleanly and does not poison later imports.
    if not hasattr(np, "linspace") or not hasattr(np, "isscalar"):
        sys.modules.pop("numpy", None)
        np = None

try:
    from .wiki_report import ReportData
except ImportError:
    from wiki_report import ReportData

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


def _write_placeholder_png(path: Path, *, width: int = 640, height: int = 360) -> Path:
    """Write a simple valid PNG when optional chart deps are unavailable."""
    path.parent.mkdir(parents=True, exist_ok=True)

    def _chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack("!I", len(data))
            + tag
            + data
            + struct.pack("!I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    rows = bytearray()
    for y in range(height):
        rows.append(0)  # filter byte
        for x in range(width):
            r = (x * 255) // max(1, width - 1)
            g = (y * 255) // max(1, height - 1)
            b = ((x + y) * 255) // max(1, width + height - 2)
            rows.extend((r, g, b))

    png = bytearray(b"\x89PNG\r\n\x1a\n")
    png.extend(_chunk(b"IHDR", struct.pack("!IIBBBBB", width, height, 8, 2, 0, 0, 0)))
    png.extend(_chunk(b"IDAT", zlib.compress(bytes(rows), level=6)))
    png.extend(_chunk(b"IEND", b""))
    path.write_bytes(bytes(png))
    return path


def render_radar_chart(data: ReportData, *, output_dir: Path) -> Path:
    """Render a knowledge radar/spider chart showing depth per domain."""
    output_dir.mkdir(parents=True, exist_ok=True)
    hubs = data.hubs
    path = output_dir / "radar.png"

    if plt is None or np is None:
        return _write_placeholder_png(path)

    if not hubs:
        fig, ax = plt.subplots(figsize=(6, 6), facecolor=_BG)
        try:
            ax.set_facecolor(_BG)
            ax.text(0.5, 0.5, "No data", ha="center", va="center", color=_MUTED, fontsize=14)
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.axis("off")
            fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=_BG)
        finally:
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
    try:
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

        fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=_BG)
    finally:
        plt.close(fig)
    return path


def render_knowledge_graph(data: ReportData, *, output_dir: Path) -> Path:
    """Render a force-directed knowledge graph from wikilink connections."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "graph.png"

    if plt is None:
        return _write_placeholder_png(path)

    try:
        import networkx as nx
    except ImportError:
        fig, ax = plt.subplots(figsize=(8, 5), facecolor=_BG)
        try:
            ax.set_facecolor(_BG)
            ax.text(0.5, 0.5, "networkx not installed", ha="center", va="center", color=_MUTED, fontsize=14)
            ax.axis("off")
            fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=_BG)
        finally:
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
        try:
            ax.set_facecolor(_BG)
            ax.text(0.5, 0.5, "No pages", ha="center", va="center", color=_MUTED)
            ax.axis("off")
            fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=_BG)
        finally:
            plt.close(fig)
        return path

    fig, ax = plt.subplots(figsize=(10, 6), facecolor=_BG)
    try:
        ax.set_facecolor(_BG)
        ax.axis("off")

        pos = nx.spring_layout(G, k=2.5, iterations=50, seed=42)
        node_colors = [hub_color_map.get(G.nodes[n].get("hub", ""), _MUTED) for n in G.nodes]
        node_sizes = [G.nodes[n].get("size", 300) for n in G.nodes]

        nx.draw_networkx_edges(G, pos, ax=ax, edge_color="#334155", alpha=0.6, arrows=False, width=1)
        nx.draw_networkx_nodes(G, pos, ax=ax, node_color=node_colors, node_size=node_sizes, alpha=0.9)

        labels = {n: G.nodes[n].get("title", n.split("/")[-1])[:12] for n in G.nodes}
        nx.draw_networkx_labels(G, pos, labels, ax=ax, font_size=7, font_color=_TEXT, font_weight="bold")

        fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=_BG)
    finally:
        plt.close(fig)
    return path


def render_hub_distribution(data: ReportData, *, output_dir: Path) -> Path:
    """Render a horizontal stacked bar showing source distribution by hub."""
    output_dir.mkdir(parents=True, exist_ok=True)
    hubs = data.hubs
    path = output_dir / "distribution.png"

    if plt is None:
        return _write_placeholder_png(path)

    if not hubs:
        fig, ax = plt.subplots(figsize=(8, 1.5), facecolor=_BG)
        try:
            ax.set_facecolor(_BG)
            ax.text(0.5, 0.5, "No data", ha="center", va="center", color=_MUTED)
            ax.axis("off")
            fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=_BG)
        finally:
            plt.close(fig)
        return path

    sorted_hubs = sorted(hubs.items(), key=lambda x: x[1]["source_count"], reverse=True)

    fig, ax = plt.subplots(figsize=(10, 1.8), facecolor=_BG)
    try:
        ax.set_facecolor(_BG)

        left = 0
        for i, (hub_name, hub_data) in enumerate(sorted_hubs):
            width = hub_data["source_count"]
            color = _hub_color(i)
            ax.barh(0, width, left=left, height=0.6, color=color, edgecolor=_BG, linewidth=1)
            if width > 30:
                ax.text(left + width / 2, 0, f"{hub_name.title()}\n{width}",
                        ha="center", va="center", color="white", fontsize=8, fontweight="bold")
            left += width

        ax.set_xlim(0, left)
        ax.set_ylim(-0.5, 0.5)
        ax.axis("off")

        fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=_BG)
    finally:
        plt.close(fig)
    return path
