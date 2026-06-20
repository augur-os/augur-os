"""Render Second Brain Report as self-contained HTML and PDF.

Two public entrypoints:
    render_html(report, *, output_path, template_dir) -> Path
    render_pdf(report,  *, output_path)               -> Path

Both accept the report dict produced by the wiki_report agent step.
Charts and portfolio images are embedded as base64 data URIs so the
output files are fully self-contained (no external asset references).
"""
from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _image_to_data_uri(path: str | Path) -> str:
    """Read image file and return a base64 data URI string.

    Returns an empty string if path is falsy or the file does not exist.
    """
    if not path:
        return ""
    p = Path(path)
    if not p.is_file():
        return ""
    mime, _ = mimetypes.guess_type(str(p))
    if mime is None:
        # Fall back by extension
        ext = p.suffix.lower()
        mime = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".svg": "image/svg+xml",
        }.get(ext, "image/png")
    data = base64.b64encode(p.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def _embed_charts(report: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of report with chart paths replaced by data URIs."""
    import copy
    r = copy.deepcopy(report)

    charts = r.get("charts") or {}
    for key in ("radar", "graph", "distribution"):
        raw = charts.get(key) or ""
        charts[key] = _image_to_data_uri(raw) if raw else ""
    r["charts"] = charts

    portfolio = r.get("portfolio") or {}
    for key in ("profile", "logo", "cover"):
        raw = portfolio.get(key)
        portfolio[key] = _image_to_data_uri(raw) if raw else None
    hub_images = portfolio.get("hub_images") or {}
    portfolio["hub_images"] = {
        hub: [_image_to_data_uri(img) for img in imgs if img]
        for hub, imgs in hub_images.items()
    }
    r["portfolio"] = portfolio

    return r


# ---------------------------------------------------------------------------
# HTML renderer
# ---------------------------------------------------------------------------

def render_html(
    report: dict[str, Any],
    *,
    output_path: Path,
    template_dir: Path,
) -> Path:
    """Render the report to a self-contained HTML file.

    Args:
        report: The report dict (see module docstring for shape).
        output_path: Destination .html file path.
        template_dir: Directory containing report.html.j2.

    Returns:
        The resolved output_path after writing.
    """
    from jinja2 import Environment, FileSystemLoader, select_autoescape

    template_dir = Path(template_dir).resolve()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(["html"]),
        keep_trailing_newline=True,
    )

    template = env.get_template("report.html.j2")

    # Embed all images as data URIs so the HTML is fully self-contained
    embedded = _embed_charts(report)

    html = template.render(report=embedded)
    output_path.write_text(html, encoding="utf-8")
    return output_path.resolve()


# ---------------------------------------------------------------------------
# PDF renderer
# ---------------------------------------------------------------------------

# Color palette matching the dark HTML theme
_BG_RGB      = (0.059, 0.090, 0.165)   # #0f172a
_CARD_RGB    = (0.118, 0.161, 0.231)   # #1e293b
_BORDER_RGB  = (0.200, 0.255, 0.333)   # #334155
_TEXT_RGB    = (0.886, 0.906, 0.941)   # #e2e8f0
_MUTED_RGB   = (0.392, 0.455, 0.545)   # #64748b
_ACCENT1_RGB = (0.388, 0.400, 0.945)   # #6366f1
_ACCENT2_RGB = (0.024, 0.714, 0.831)   # #06b6d4
_GREEN_RGB   = (0.133, 0.773, 0.369)   # #22c55e
_AMBER_RGB   = (0.961, 0.620, 0.043)   # #f59e0b
_RED_RGB     = (0.937, 0.267, 0.267)   # #ef4444
_BLUE_RGB    = (0.231, 0.510, 0.965)   # #3b82f6

_HUB_COLORS_RGB = [
    _BLUE_RGB,
    (0.925, 0.302, 0.608),  # #ec4899
    _GREEN_RGB,
    _AMBER_RGB,
    (0.545, 0.361, 0.965),  # #8b5cf6
    _ACCENT2_RGB,
    (0.957, 0.247, 0.369),  # #f43f5e
    (0.063, 0.690, 0.506),  # #10b981
    _ACCENT1_RGB,
    (0.659, 0.333, 0.965),  # #a855f7
]


def _hub_color_rgb(index: int) -> tuple[float, float, float]:
    return _HUB_COLORS_RGB[index % len(_HUB_COLORS_RGB)]


def _hex_to_rgb(hex_color: str) -> tuple[float, float, float]:
    """Convert #rrggbb to (r, g, b) floats in [0, 1]."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r = int(h[0:2], 16) / 255
    g = int(h[2:4], 16) / 255
    b = int(h[4:6], 16) / 255
    return (r, g, b)


def _embed_image_for_rl(path: str | Path):
    """Return a ReportLab ImageReader for the given path, or None."""
    from reportlab.lib.utils import ImageReader
    import io

    if not path:
        return None
    p = Path(path)
    if not p.is_file():
        return None
    return ImageReader(io.BytesIO(p.read_bytes()))


def _set_bg(canvas_obj, width: float, height: float) -> None:
    """Fill the current page with the dark background color."""
    canvas_obj.setFillColorRGB(*_BG_RGB)
    canvas_obj.rect(0, 0, width, height, fill=1, stroke=0)


def _draw_card(
    canvas_obj,
    x: float, y: float, w: float, h: float,
    fill_rgb: tuple = _CARD_RGB,
    border_rgb: tuple = _BORDER_RGB,
    radius: float = 6,
) -> None:
    canvas_obj.setFillColorRGB(*fill_rgb)
    canvas_obj.setStrokeColorRGB(*border_rgb)
    canvas_obj.roundRect(x, y, w, h, radius, fill=1, stroke=1)


def render_pdf(
    report: dict[str, Any],
    *,
    output_path: Path,
) -> Path:
    """Render the report to a PDF file using ReportLab.

    Layout (4 pages):
        1. Cover     — gradient, profile photo, synthesis, stat bar
        2. Who You Are — narrative cards + expertise bars
        3. Brain Contents — hub cards + radar/distribution charts
        4. Patterns & Blind Spots — pattern/blind-spot cards + graph chart

    Args:
        report: The report dict.
        output_path: Destination .pdf file path.

    Returns:
        The resolved output_path after writing.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas as rl_canvas

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    PAGE_W, PAGE_H = A4  # 595.27 x 841.89 pts
    MARGIN = 42.0

    c = rl_canvas.Canvas(str(output_path), pagesize=A4)

    charts = report.get("charts") or {}
    portfolio = report.get("portfolio") or {}
    stats = report.get("stats") or {}
    who = report.get("who_you_are") or {}
    expertise = report.get("expertise") or []
    hub_sections = report.get("hub_sections") or []
    patterns = report.get("patterns") or []
    blind_spots = report.get("blind_spots") or []

    def page_bg() -> None:
        _set_bg(c, PAGE_W, PAGE_H)

    def text_line(
        x: float, y: float, text: str,
        size: float = 10,
        rgb: tuple = _TEXT_RGB,
        bold: bool = False,
        italic: bool = False,
        max_width: float = 0,
    ) -> None:
        c.setFillColorRGB(*rgb)
        font = "Helvetica-Bold" if bold else ("Helvetica-Oblique" if italic else "Helvetica")
        c.setFont(font, size)
        if max_width and c.stringWidth(text, font, size) > max_width:
            # Simple truncation with ellipsis
            while text and c.stringWidth(text + "…", font, size) > max_width:
                text = text[:-1]
            text = text + "…"
        c.drawString(x, y, text)

    def wrapped_text(
        x: float, y: float, text: str,
        max_width: float,
        size: float = 10,
        rgb: tuple = _TEXT_RGB,
        line_height: float = 14,
        bold: bool = False,
        italic: bool = False,
    ) -> float:
        """Draw wrapped text, return y position after last line."""
        font = "Helvetica-Bold" if bold else ("Helvetica-Oblique" if italic else "Helvetica")
        c.setFillColorRGB(*rgb)
        c.setFont(font, size)
        words = text.split()
        line = ""
        for word in words:
            test = (line + " " + word).strip()
            if c.stringWidth(test, font, size) <= max_width:
                line = test
            else:
                if line:
                    c.drawString(x, y, line)
                    y -= line_height
                line = word
        if line:
            c.drawString(x, y, line)
            y -= line_height
        return y

    def embed_chart_image(
        chart_path: str,
        x: float, y: float, w: float, h: float,
        label: str = "",
    ) -> None:
        """Draw a chart PNG at given position. Draws placeholder if missing."""
        if label:
            text_line(x, y + h + 4, label, size=8, rgb=_MUTED_RGB, bold=True)

        _draw_card(c, x, y, w, h, fill_rgb=_CARD_RGB, border_rgb=_BORDER_RGB)

        img = _embed_image_for_rl(chart_path)
        if img:
            c.drawImage(img, x + 2, y + 2, width=w - 4, height=h - 4,
                        preserveAspectRatio=True, mask="auto")
        else:
            c.setFillColorRGB(*_MUTED_RGB)
            c.setFont("Helvetica", 9)
            c.drawCentredString(x + w / 2, y + h / 2 - 4, "No chart data")

    # ── PAGE 1: COVER ────────────────────────────────────────────────────────
    page_bg()

    # Gradient cover band (simulated with two overlapping rects + alpha blend)
    grad_h = 280.0
    grad_y = PAGE_H - grad_h
    # Base gradient: left accent1, right accent2 – approximate with 20 strips
    strips = 20
    for i in range(strips):
        t = i / strips
        r = _ACCENT1_RGB[0] + t * (_BLUE_RGB[0] - _ACCENT1_RGB[0])
        g = _ACCENT1_RGB[1] + t * (_BLUE_RGB[1] - _ACCENT1_RGB[1])
        b = _ACCENT1_RGB[2] + t * (_ACCENT2_RGB[2] - _ACCENT1_RGB[2])
        c.setFillColorRGB(r, g, b)
        strip_w = PAGE_W / strips
        c.rect(i * strip_w, grad_y, strip_w + 1, grad_h, fill=1, stroke=0)

    # Profile photo or placeholder
    profile_img = _embed_image_for_rl(portfolio.get("profile"))
    photo_x = MARGIN
    photo_y = PAGE_H - MARGIN - 80
    photo_size = 72.0
    if profile_img:
        # Clip to circle via save/restore
        c.saveState()
        p_path = c.beginPath()
        cx = photo_x + photo_size / 2
        cy = photo_y + photo_size / 2
        p_path.circle(cx, cy, photo_size / 2)
        c.clipPath(p_path, stroke=0)
        c.drawImage(profile_img, photo_x, photo_y, width=photo_size, height=photo_size,
                    preserveAspectRatio=True, mask="auto")
        c.restoreState()
    else:
        c.setFillColorRGB(1, 1, 1, 0.15)
        c.circle(photo_x + photo_size / 2, photo_y + photo_size / 2, photo_size / 2, fill=1, stroke=0)
        c.setFillColorRGB(1, 1, 1, 0.7)
        c.setFont("Helvetica-Bold", 28)
        initial = (report.get("name") or "?")[0].upper()
        c.drawCentredString(photo_x + photo_size / 2, photo_y + photo_size / 2 - 10, initial)

    text_x = photo_x + photo_size + 18
    text_w = PAGE_W - text_x - MARGIN

    # Tag pill
    tag_label = "SECOND BRAIN INTELLIGENCE REPORT"
    tag_w = c.stringWidth(tag_label, "Helvetica-Bold", 8) + 20
    c.setFillColorRGB(1, 1, 1, 0.15)
    c.roundRect(text_x, photo_y + photo_size - 18, tag_w, 16, 8, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1, 0.9)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(text_x + 10, photo_y + photo_size - 12, tag_label)

    # Title
    title_y = photo_y + photo_size - 36
    title = report.get("title", "What Your AI Knows About You")
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 22)
    c.drawString(text_x, title_y, title)

    # Name + date
    name_line = f"Prepared for {report.get('name', '')}  ·  {report.get('date', '')}"
    c.setFillColorRGB(1, 1, 1, 0.75)
    c.setFont("Helvetica", 10)
    c.drawString(text_x, title_y - 16, name_line)

    # Synthesis box
    if report.get("synthesis"):
        syn_y = title_y - 32
        syn_h = 70
        _draw_card(c, text_x, syn_y - syn_h, text_w, syn_h,
                   fill_rgb=(1, 1, 1, 0.12), border_rgb=(1, 1, 1, 0.25))
        wrapped_text(
            text_x + 10, syn_y - 14,
            report["synthesis"],
            max_width=text_w - 20,
            size=9,
            rgb=(1, 1, 1, 0.92),
            line_height=13,
            italic=True,
        )

    # Stat bar
    stat_bar_y = grad_y - 56
    stat_keys = [
        ("pages", "WIKI PAGES"),
        ("hubs", "HUBS"),
        ("sources", "SOURCES"),
        ("words", "WORDS"),
        ("cross_refs", "CROSS-REFS"),
    ]
    col_w = PAGE_W / len(stat_keys)
    _draw_card(c, 0, stat_bar_y, PAGE_W, 50, fill_rgb=_CARD_RGB, border_rgb=_BG_RGB, radius=0)
    for i, (key, label) in enumerate(stat_keys):
        sx = i * col_w
        val = str(stats.get(key, 0))
        # Value
        c.setFillColorRGB(*_ACCENT1_RGB)
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(sx + col_w / 2, stat_bar_y + 28, val)
        # Label
        c.setFillColorRGB(*_MUTED_RGB)
        c.setFont("Helvetica-Bold", 7)
        c.drawCentredString(sx + col_w / 2, stat_bar_y + 14, label)
        # Divider
        if i > 0:
            c.setStrokeColorRGB(*_BORDER_RGB)
            c.line(sx, stat_bar_y + 8, sx, stat_bar_y + 44)

    c.showPage()

    # ── PAGE 2: WHO YOU ARE ──────────────────────────────────────────────────
    page_bg()

    sec_y = PAGE_H - MARGIN
    # Section header
    c.setFillColorRGB(*_ACCENT1_RGB, 0.2)
    c.roundRect(MARGIN, sec_y - 28, 28, 28, 6, fill=1, stroke=0)
    c.setFillColorRGB(*_TEXT_RGB)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(MARGIN + 8, sec_y - 17, chr(0x1F464))  # fallback glyph may not render
    c.setFillColorRGB(*_TEXT_RGB)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(MARGIN + 36, sec_y - 10, "Who You Are")
    c.setFillColorRGB(*_MUTED_RGB)
    c.setFont("Helvetica", 9)
    c.drawString(MARGIN + 36, sec_y - 22, "Identity synthesis from your knowledge graph")

    col_x_left = MARGIN
    col_x_right = PAGE_W / 2 + 8
    col_w_half = PAGE_W / 2 - MARGIN - 8

    card_y = sec_y - 50

    # Left: What You Do card
    if who.get("what_you_do"):
        card_h = 90
        _draw_card(c, col_x_left, card_y - card_h, col_w_half, card_h)
        text_line(col_x_left + 12, card_y - 14, "WHAT YOU DO", size=8, rgb=_MUTED_RGB, bold=True)
        wrapped_text(col_x_left + 12, card_y - 28, who["what_you_do"],
                     max_width=col_w_half - 24, size=9, rgb=(0.784, 0.835, 0.882),
                     line_height=13)
        card_y -= card_h + 12

    # Left: How You Think card
    if who.get("how_you_think"):
        card_h = 90
        _draw_card(c, col_x_left, card_y - card_h, col_w_half, card_h)
        text_line(col_x_left + 12, card_y - 14, "HOW YOU THINK", size=8, rgb=_MUTED_RGB, bold=True)
        wrapped_text(col_x_left + 12, card_y - 28, who["how_you_think"],
                     max_width=col_w_half - 24, size=9, rgb=(0.784, 0.835, 0.882),
                     line_height=13)

    # Right: Expertise bars
    exp_y = sec_y - 50
    exp_card_h = min(200, 20 + len(expertise) * 36)
    _draw_card(c, col_x_right, exp_y - exp_card_h, col_w_half, exp_card_h)
    text_line(col_x_right + 12, exp_y - 14, "EXPERTISE STACK", size=8, rgb=_MUTED_RGB, bold=True)
    bar_y = exp_y - 32
    bar_w = col_w_half - 24
    for item in expertise:
        domain = item.get("domain", "")
        level = item.get("level", "")
        pct = max(0, min(100, item.get("percentage", 0)))
        color_hex = item.get("color", "#6366f1")
        bar_rgb = _hex_to_rgb(color_hex)

        text_line(col_x_right + 12, bar_y, domain, size=9, rgb=_TEXT_RGB, bold=True)
        text_line(col_x_right + 12 + bar_w - c.stringWidth(level, "Helvetica", 8),
                  bar_y, level, size=8, rgb=_MUTED_RGB)

        track_y = bar_y - 12
        # Track
        c.setFillColorRGB(*_BORDER_RGB)
        c.roundRect(col_x_right + 12, track_y, bar_w, 6, 3, fill=1, stroke=0)
        # Fill
        fill_w = bar_w * pct / 100
        if fill_w > 0:
            c.setFillColorRGB(*bar_rgb)
            c.roundRect(col_x_right + 12, track_y, fill_w, 6, 3, fill=1, stroke=0)

        bar_y -= 32

    c.showPage()

    # ── PAGE 3: BRAIN CONTENTS ───────────────────────────────────────────────
    page_bg()

    sec_y = PAGE_H - MARGIN
    c.setFillColorRGB(*_TEXT_RGB)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(MARGIN, sec_y - 10, "What Your Brain Contains")
    c.setFillColorRGB(*_MUTED_RGB)
    c.setFont("Helvetica", 9)
    c.drawString(MARGIN, sec_y - 22,
                 f"Knowledge across {stats.get('hubs', 0)} hubs from {stats.get('sources', 0)} sources")

    # Hub cards grid (2 columns)
    hub_y = sec_y - 48
    hub_card_h = 72
    hub_card_w = (PAGE_W - 2 * MARGIN - 12) / 2

    for i, hub in enumerate(hub_sections):
        col = i % 2
        row = i // 2
        hx = MARGIN + col * (hub_card_w + 12)
        hy = hub_y - row * (hub_card_h + 10) - hub_card_h

        _draw_card(c, hx, hy, hub_card_w, hub_card_h)
        # Accent left border
        hub_color_hex = hub.get("color", "#3b82f6")
        hub_rgb = _hex_to_rgb(hub_color_hex)
        c.setFillColorRGB(*hub_rgb)
        c.roundRect(hx, hy, 4, hub_card_h, 2, fill=1, stroke=0)

        # Hub name
        text_line(hx + 14, hy + hub_card_h - 18, hub.get("name", ""),
                  size=11, rgb=_TEXT_RGB, bold=True)
        # Source count
        count_str = f"{hub.get('source_count', 0)} sources"
        c.setFillColorRGB(*_MUTED_RGB)
        c.setFont("Helvetica-Bold", 7)
        c.drawRightString(hx + hub_card_w - 10, hy + hub_card_h - 16, count_str)
        # Summary
        wrapped_text(hx + 14, hy + hub_card_h - 30, hub.get("summary", ""),
                     max_width=hub_card_w - 24, size=8,
                     rgb=(0.580, 0.639, 0.722), line_height=11)

    # Charts: radar + distribution
    hub_rows = (len(hub_sections) + 1) // 2
    chart_area_y = hub_y - hub_rows * (hub_card_h + 10) - 20
    chart_h = min(180, chart_area_y - MARGIN - 20)

    radar_path = charts.get("radar") or ""
    dist_path = charts.get("distribution") or ""

    if chart_h > 60:
        chart_w = (PAGE_W - 2 * MARGIN - 12) / 2
        if radar_path:
            embed_chart_image(radar_path, MARGIN, MARGIN, chart_w, chart_h, "KNOWLEDGE RADAR")
        if dist_path:
            embed_chart_image(dist_path, MARGIN + chart_w + 12, MARGIN, chart_w, chart_h,
                              "HUB DISTRIBUTION")

    c.showPage()

    # ── PAGE 4: PATTERNS & BLIND SPOTS ──────────────────────────────────────
    page_bg()

    sec_y = PAGE_H - MARGIN
    c.setFillColorRGB(*_TEXT_RGB)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(MARGIN, sec_y - 10, "Patterns & Blind Spots")
    c.setFillColorRGB(*_MUTED_RGB)
    c.setFont("Helvetica", 9)
    c.drawString(MARGIN, sec_y - 22, "What your AI noticed — and what's missing")

    col_w_half = (PAGE_W - 2 * MARGIN - 16) / 2
    pat_x = MARGIN
    blind_x = MARGIN + col_w_half + 16
    item_y = sec_y - 48

    # Column titles
    text_line(pat_x, item_y, "Patterns Your AI Noticed", size=11, rgb=_TEXT_RGB, bold=True)
    c.setStrokeColorRGB(*_BORDER_RGB)
    c.line(pat_x, item_y - 4, pat_x + col_w_half, item_y - 4)

    text_line(blind_x, item_y, "Blind Spots & Gaps", size=11, rgb=_TEXT_RGB, bold=True)
    c.line(blind_x, item_y - 4, blind_x + col_w_half, item_y - 4)

    item_y -= 18
    pat_y = item_y
    blind_y = item_y

    for pattern in patterns:
        if pat_y < MARGIN + 80:
            break
        # Estimate height
        desc = pattern.get("description", "")
        lines_est = max(1, len(desc) // 55)
        ph = 28 + lines_est * 12
        _draw_card(c, pat_x, pat_y - ph, col_w_half, ph)
        # Green left accent
        c.setFillColorRGB(*_GREEN_RGB)
        c.roundRect(pat_x, pat_y - ph, 3, ph, 2, fill=1, stroke=0)

        text_line(pat_x + 12, pat_y - 14, pattern.get("title", ""), size=9,
                  rgb=_TEXT_RGB, bold=True, max_width=col_w_half - 20)
        wrapped_text(pat_x + 12, pat_y - 26, desc,
                     max_width=col_w_half - 20, size=8, rgb=(0.580, 0.639, 0.722), line_height=11)
        pat_y -= ph + 8

    for spot in blind_spots:
        if blind_y < MARGIN + 80:
            break
        desc = spot.get("description", "")
        lines_est = max(1, len(desc) // 55)
        sh = 28 + lines_est * 12
        _draw_card(c, blind_x, blind_y - sh, col_w_half, sh)
        severity = spot.get("severity", "medium")
        accent_rgb = {
            "low": _GREEN_RGB,
            "medium": _AMBER_RGB,
            "high": _RED_RGB,
        }.get(severity, _AMBER_RGB)
        c.setFillColorRGB(*accent_rgb)
        c.roundRect(blind_x, blind_y - sh, 3, sh, 2, fill=1, stroke=0)
        # Severity dot
        c.circle(blind_x + 14, blind_y - 14, 4, fill=1, stroke=0)
        text_line(blind_x + 22, blind_y - 10, spot.get("title", ""), size=9,
                  rgb=_TEXT_RGB, bold=True, max_width=col_w_half - 30)
        wrapped_text(blind_x + 12, blind_y - 22, desc,
                     max_width=col_w_half - 20, size=8, rgb=(0.580, 0.639, 0.722), line_height=11)
        blind_y -= sh + 8

    # Knowledge graph chart at bottom
    graph_path = charts.get("graph") or ""
    graph_y = min(pat_y, blind_y) - 20
    graph_h = graph_y - MARGIN - 16
    if graph_path and graph_h > 60:
        embed_chart_image(graph_path, MARGIN, MARGIN, PAGE_W - 2 * MARGIN, graph_h,
                          "KNOWLEDGE GRAPH")

    # Footer
    c.setStrokeColorRGB(0.118, 0.161, 0.231)
    c.line(MARGIN, MARGIN - 2, PAGE_W - MARGIN, MARGIN - 2)
    c.setFillColorRGB(*_MUTED_RGB)
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(MARGIN, MARGIN - 14,
                 "\u201CThe best way to use your second brain is to let it surface what you can't keep in your head.\u201D")
    c.setFillColorRGB(*_ACCENT1_RGB)
    c.setFont("Helvetica-Bold", 9)
    c.drawRightString(PAGE_W - MARGIN, MARGIN - 8, "Augur")
    c.setFillColorRGB(*_MUTED_RGB)
    c.setFont("Helvetica", 7)
    c.drawRightString(PAGE_W - MARGIN, MARGIN - 18, "augur.run")

    c.save()
    return output_path.resolve()
