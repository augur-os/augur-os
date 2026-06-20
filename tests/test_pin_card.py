"""Parity tests for the pin-card resolver.

The resolver must compute the SAME `itemKey` the Browse UI computes
(apps/dashboard/lib/browse/{transforms,pinOrdering}.ts), otherwise a CLI/MCP
pin is a dead orphan that never renders on the card. These tests pin the
itemKey contract for each id-resolution branch so it can't silently drift.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.mcp.augur_framework.tools.infrastructure.pins import (  # noqa: E402
    _resolve_browse_item,
    browse_pin_item_id,
    browse_pin_target,
    pin_card_impl,
    pin_list_impl,
)

# --- id resolution parity (mirrors browseIndexItemId) ----------------------


def test_documents_id_uses_source_path() -> None:
    # Real-world shape: a binary document. explicitId has no ":" so the
    # overlay branch is skipped and source_path wins.
    entry = {
        "id": "augur-deck-ignite-v2",
        "title": "augur-deck-ignite-v2",
        "source_path": "/docs/IntelIgnite/augur-deck-ignite-v2.pptx",
    }
    assert browse_pin_item_id(entry, "documents") == ("/docs/IntelIgnite/augur-deck-ignite-v2.pptx")


def test_vault_overlay_id_wins_over_source_path() -> None:
    # Vault entries carry an overlay identity + a scheme id ("vault:..."),
    # so the scheme id is used, NOT the filesystem source_path.
    entry = {
        "id": "vault:private:notes/thought-foo",
        "title": "thought-foo",
        "source_path": "/Users/me/Au-vault/notes/thought-foo.md",
        "metadata": {"vault_scope": "private"},
    }
    assert browse_pin_item_id(entry, "vault") == "vault:private:notes/thought-foo"


def test_non_source_backed_category_uses_explicit_id() -> None:
    entry = {"id": "some-skill", "title": "Some Skill", "source_path": "/x/y.md"}
    assert browse_pin_item_id(entry, "skills") == "some-skill"


def test_wiki_prefers_explicit_id() -> None:
    entry = {"id": "wiki:shared:README", "source_path": "/x/README.md"}
    assert browse_pin_item_id(entry, "wiki") == "wiki:shared:README"


# --- full pin target parity (mirrors browseItemPinTarget) ------------------


def test_pin_target_shape_matches_dashboard() -> None:
    entry = {
        "id": "augur-deck-ignite-v2",
        "title": "augur-deck-ignite-v2",
        "source_path": "/docs/IntelIgnite/augur-deck-ignite-v2.pptx",
    }
    target = browse_pin_target(entry, "documents")
    # Exact shape parity with the dashboard browseItemPinTarget() — no hub
    # (ADR-802 removed the hub concept; the UI emits none).
    assert target == {
        "category": "documents",
        "itemKey": "documents::/docs/IntelIgnite/augur-deck-ignite-v2.pptx",
        "url": "/docs/IntelIgnite/augur-deck-ignite-v2.pptx",
        "title": "augur-deck-ignite-v2",
        "kind": "browse-card",
    }


def test_pin_target_omits_hub() -> None:
    # ADR-802 regression guard: hub must never reappear in the pin target.
    target = browse_pin_target({"id": "x", "title": "X"}, "pages")
    assert "hub" not in target
    assert target["kind"] == "browse-card"


# --- selector resolution ---------------------------------------------------


def test_resolver_prefers_exact_title_over_substring() -> None:
    items = [
        {"id": "augur-deck-ignite-v2.backup-1", "title": "augur-deck-ignite-v2.backup-1"},
        {"id": "augur-deck-ignite-v2", "title": "augur-deck-ignite-v2"},
    ]
    match, ambiguous = _resolve_browse_item(items, "augur-deck-ignite-v2")
    assert ambiguous == []
    assert match["id"] == "augur-deck-ignite-v2"


def test_resolver_matches_basename() -> None:
    items = [{"id": "doc", "title": "Doc", "source_path": "/a/b/report.pdf"}]
    match, _ = _resolve_browse_item(items, "report")
    assert match is not None and match["id"] == "doc"


def test_resolver_reports_ambiguous() -> None:
    items = [
        {"id": "a", "title": "Alpha note"},
        {"id": "b", "title": "Alpha draft"},
    ]
    match, ambiguous = _resolve_browse_item(items, "alpha")
    assert match is None
    assert len(ambiguous) == 2


# --- end-to-end impl behavior (no real index needed) -----------------------


def test_pin_card_impl_no_match(tmp_path: Path, monkeypatch) -> None:
    import src.mcp.augur_framework.tools.infrastructure.browse.index as idx

    monkeypatch.setattr(idx, "browse_index_impl", lambda *a, **k: '{"items": [], "count": 0}')
    res = pin_card_impl(pins_path=tmp_path / "pins.yaml", category="documents", selector="nope")
    assert res["added"] is False
    assert "error" in res


def test_pin_card_impl_writes_resolved_target(tmp_path: Path, monkeypatch) -> None:
    import json

    import src.mcp.augur_framework.tools.infrastructure.browse.index as idx

    fake = {
        "items": [
            {
                "id": "augur-deck-ignite-v2",
                "title": "augur-deck-ignite-v2",
                "hub": "venture-augur",
                "source_path": "/docs/augur-deck-ignite-v2.pptx",
            }
        ],
        "count": 1,
    }
    monkeypatch.setattr(idx, "browse_index_impl", lambda *a, **k: json.dumps(fake))

    pins_path = tmp_path / "pins.yaml"
    res = pin_card_impl(pins_path=pins_path, category="documents", selector="augur-deck-ignite-v2")
    assert res["added"] is True
    assert res["itemKey"] == "documents::/docs/augur-deck-ignite-v2.pptx"

    pinned = pin_list_impl(pins_path=pins_path)["pins"]
    assert len(pinned) == 1
    assert pinned[0]["itemKey"] == "documents::/docs/augur-deck-ignite-v2.pptx"
    assert pinned[0]["kind"] == "browse-card"
    # The fake index entry carries a stray legacy `hub`; it must not be
    # propagated into the stored pin (ADR-802).
    assert "hub" not in pinned[0]
