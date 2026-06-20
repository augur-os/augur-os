"""Sidecar I/O for HTML artifacts — shared by the artifacts MCP tool and the browse indexer.

Pure helpers only: no MCP imports allowed here (the indexer CLI loads this in isolation).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Sidecar:
    slug: str
    title: str
    kind: str
    hub: str
    source: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    created_at: str = ""
    promoted_at: str = ""
    notes: str = ""


def write_sidecar(path: Path, sidecar: Sidecar) -> None:
    """Write a sidecar YAML file with frontmatter fences."""
    path.parent.mkdir(parents=True, exist_ok=True)
    yaml_body = yaml.safe_dump(
        asdict(sidecar),
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    ).rstrip("\n")
    path.write_text(f"---\n{yaml_body}\n---\n", encoding="utf-8")


def read_sidecar(path: Path) -> Sidecar:
    """Read a sidecar YAML file, accepting fenced or plain YAML."""
    text = path.read_text(encoding="utf-8")
    body = _sidecar_yaml_body(text)
    data = yaml.safe_load(body) or {}
    if not isinstance(data, dict):
        data = {}
    known = set(Sidecar.__dataclass_fields__)
    return Sidecar(**{k: v for k, v in data.items() if k in known})


def _sidecar_yaml_body(text: str) -> str:
    if not text.startswith("---"):
        return text
    end = text.find("\n---", 4)
    if end == -1:
        return text
    return text[4:end]


def sidecar_path_for_html(html_path: Path) -> Path:
    """Return the .meta.yaml sidecar path for an .html artifact path."""
    return html_path.with_suffix("").with_suffix(".meta.yaml")


def iter_artifact_files(docs_dir: Path) -> Iterator[tuple[Path, Path]]:
    """Yield (html_path, sidecar_path) for every sidecar-backed HTML artifact under docs_dir."""
    for html_path in sorted(docs_dir.rglob("*.html")):
        sidecar_path = sidecar_path_for_html(html_path)
        if sidecar_path.exists():
            yield html_path, sidecar_path
