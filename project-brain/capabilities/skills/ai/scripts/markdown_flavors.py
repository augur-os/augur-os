"""Stateless markdown flavor conversion utility (ADR-436).

Converts between plain markdown, Obsidian-flavored, and Logseq-flavored formats.
Adapters call this utility — it's NOT on the adapter base class.
"""
from __future__ import annotations

import re


def plain_to_obsidian(text: str) -> str:
    """Convert plain markdown to Obsidian-flavored markdown.

    Transforms:
    - Standard links [text](path.md) -> [[path|text]] for internal links
    - Keeps external URLs as standard links
    """
    def _replace_internal_link(m: re.Match) -> str:
        label, target = m.group(1), m.group(2)
        if target.startswith(("http://", "https://", "mailto:")):
            return m.group(0)  # Keep external links
        stem = target.removesuffix(".md")
        if label == stem:
            return f"[[{stem}]]"
        return f"[[{stem}|{label}]]"

    return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", _replace_internal_link, text)


def obsidian_to_plain(text: str) -> str:
    """Convert Obsidian-flavored markdown to plain markdown.

    Transforms:
    - [[page|alias]] -> [alias](page.md)
    - [[page]] -> [page](page.md)
    - ![[embed]] -> [embed](embed) (image/file embeds)
    """
    # Handle aliased wiki-links: [[target|alias]]
    text = re.sub(r"\[\[([^|\]]+)\|([^\]]+)\]\]", r"[\2](\1.md)", text)
    # Handle simple wiki-links: [[target]]
    text = re.sub(r"\[\[([^\]]+)\]\]", r"[\1](\1.md)", text)
    # Handle embeds: ![[file]]
    text = re.sub(r"!\[\[([^\]]+)\]\]", r"[\1](\1)", text)
    return text


def plain_to_logseq(text: str) -> str:
    """Convert plain markdown to Logseq-flavored markdown.

    Transforms:
    - Standard links to wiki-links (same as Obsidian)
    - Adds bullet-point outline structure
    """
    # Logseq uses same wiki-link syntax as Obsidian
    text = plain_to_obsidian(text)
    # Logseq uses outline format — add bullets to non-blank, non-heading lines
    lines = text.split("\n")
    result = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("- "):
            result.append(line)
        else:
            result.append(f"- {line}")
    return "\n".join(result)


def logseq_to_plain(text: str) -> str:
    """Convert Logseq-flavored markdown to plain markdown.

    Transforms:
    - Remove leading bullet markers from outline
    - Wiki-links to standard links
    """
    # Remove leading "- " from outline bullets (preserve nested "  - ")
    lines = text.split("\n")
    result = []
    for line in lines:
        if line.startswith("- ") and not line.startswith("- [ ]"):
            result.append(line[2:])
        else:
            result.append(line)
    text = "\n".join(result)
    return obsidian_to_plain(text)


def convert(text: str, from_flavor: str, to_flavor: str) -> str:
    """Convert text between markdown flavors.

    Supported flavors: 'plain', 'obsidian', 'logseq'
    """
    if from_flavor == to_flavor:
        return text

    # Normalize to plain first, then convert to target
    to_plain = {
        "plain": lambda t: t,
        "obsidian": obsidian_to_plain,
        "logseq": logseq_to_plain,
    }
    from_plain = {
        "plain": lambda t: t,
        "obsidian": plain_to_obsidian,
        "logseq": plain_to_logseq,
    }

    if from_flavor not in to_plain:
        raise ValueError(f"Unknown source flavor: {from_flavor}")
    if to_flavor not in from_plain:
        raise ValueError(f"Unknown target flavor: {to_flavor}")

    plain = to_plain[from_flavor](text)
    return from_plain[to_flavor](plain)
