"""Guards that the public docs describe the real M3 install and stay clean."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INSTALL_DOCS = [
    ROOT / "README.md",
    ROOT / "docs/getting-started.md",
    ROOT / "docs/guides/installation-windows.md",
]
ALL_TOUCHED = INSTALL_DOCS + [
    ROOT / "docs/developer-guide.md",
    ROOT / "docs/user-guide.md",
    ROOT / "CONTRIBUTING.md",
]


def test_install_docs_reference_onboard_run():
    for doc in INSTALL_DOCS:
        assert "aug onboard run" in doc.read_text(encoding="utf-8"), f"{doc} missing aug onboard run"


def test_readme_drops_unverified_npx_path():
    assert "npx create-augur" not in (ROOT / "README.md").read_text(encoding="utf-8")


def test_no_manual_deps_as_primary_path():
    # `corepack && pnpm install && uv sync` may appear ONLY inside a <details> contributor block.
    for doc in INSTALL_DOCS:
        text = doc.read_text(encoding="utf-8")
        for m in re.finditer(r"corepack enable", text):
            before = text[: m.start()]
            # the nearest <details> must be unclosed at this point (i.e. inside it)
            assert before.count("<details") > before.count(
                "</details>"
            ), f"{doc}: manual deps appear outside a <details> contributor block"


def test_touched_docs_have_no_personal_paths():
    for doc in ALL_TOUCHED:
        text = doc.read_text(encoding="utf-8")
        m = re.search(r"/Users/[A-Za-z0-9._-]+/", text)
        assert m is None, f"{doc} has a personal macOS path: {m.group(0) if m else ''}"
