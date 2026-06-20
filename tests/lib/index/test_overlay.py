"""Tests for src/lib/index/_overlay.py -- shared/private overlay metadata helpers.

These pure helpers decide promotion state, entry ids, metadata, and the on-disk
output layout for shared (project-brain) vs private (private-vault) overlay
scopes consumed by the RAG index scanners.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

import pytest

from src.lib.index._overlay import (
    is_promotion_packet_relative,
    overlay_entry_id,
    overlay_metadata,
    overlay_root_label,
    promotion_state,
    vault_overlay_output_path,
    wiki_overlay_output_path,
)


# --------------------------------------------------------------------------- #
# overlay_root_label
# --------------------------------------------------------------------------- #
def test_root_label_maps_each_scope_to_its_canonical_root() -> None:
    assert overlay_root_label("shared") == "project-brain"
    assert overlay_root_label("private") == "private-vault"


def test_root_label_ignores_source_root_override() -> None:
    # source_root is accepted for signature symmetry but must not change the label.
    assert overlay_root_label("private", source_root="/some/other/place") == "private-vault"
    assert overlay_root_label("shared", source_root="ignored") == "project-brain"


def test_root_label_rejects_unknown_scope() -> None:
    with pytest.raises(KeyError):
        overlay_root_label("nonexistent")  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# is_promotion_packet_relative
# --------------------------------------------------------------------------- #
def test_promotion_packet_requires_inbox_promotions_prefix_and_depth_3() -> None:
    assert is_promotion_packet_relative(Path("inbox/promotions/packet-1/note.md")) is True
    # exactly 3 parts is the minimum accepted depth
    assert is_promotion_packet_relative(Path("inbox/promotions/note.md")) is True


@pytest.mark.parametrize(
    "rel",
    [
        Path("inbox/promotions"),  # only 2 parts -- below depth threshold
        Path("inbox"),  # single part
        Path("inbox/notes/x.md"),  # wrong second segment
        Path("notes/promotions/x.md"),  # wrong first segment
        Path("promotions/inbox/x.md"),  # right words, wrong order
    ],
)
def test_promotion_packet_rejects_non_matching_layouts(rel: Path) -> None:
    assert is_promotion_packet_relative(rel) is False


# --------------------------------------------------------------------------- #
# promotion_state
# --------------------------------------------------------------------------- #
def test_promotion_state_shared_packet_path_is_packet() -> None:
    assert promotion_state("shared", Path("inbox/promotions/pkt/x.md")) == "packet"


def test_promotion_state_shared_non_packet_is_integrated() -> None:
    assert promotion_state("shared", Path("notes/x.md")) == "integrated"
    # a near-miss packet path (too shallow) falls through to integrated, not packet
    assert promotion_state("shared", Path("inbox/promotions")) == "integrated"


def test_promotion_state_private_is_always_private_even_on_packet_layout() -> None:
    # The packet branch only applies to shared scope; private overrides it.
    assert promotion_state("private", Path("inbox/promotions/pkt/x.md")) == "private"
    assert promotion_state("private", Path("notes/x.md")) == "private"


# --------------------------------------------------------------------------- #
# overlay_metadata
# --------------------------------------------------------------------------- #
def test_metadata_shared_packet_has_all_keys_and_packet_state() -> None:
    meta = overlay_metadata(scope="shared", rel=Path("inbox/promotions/pkt/x.md"))
    assert meta == {
        "vault_scope": "shared",
        "vault_root": "project-brain",
        "promotion_state": "packet",
        "source_root": "project-brain",
    }


def test_metadata_private_defaults_source_root_to_label() -> None:
    meta = overlay_metadata(scope="private", rel=Path("notes/x.md"))
    assert meta == {
        "vault_scope": "private",
        "vault_root": "private-vault",
        "promotion_state": "private",
        "source_root": "private-vault",
    }


def test_metadata_explicit_source_root_feeds_source_root_only_not_vault_root() -> None:
    # vault_root is the canonical label; source_root carries the caller-supplied origin.
    meta = overlay_metadata(scope="shared", rel=Path("notes/x.md"), source_root="/abs/checkout/project-brain")
    assert meta["source_root"] == "/abs/checkout/project-brain"
    assert meta["vault_root"] == "project-brain"
    assert meta["promotion_state"] == "integrated"


def test_metadata_values_are_all_strings() -> None:
    meta = overlay_metadata(scope="shared", rel=Path("inbox/promotions/p/x.md"))
    assert all(isinstance(v, str) for v in meta.values())


# --------------------------------------------------------------------------- #
# overlay_entry_id
# --------------------------------------------------------------------------- #
def test_entry_id_strips_suffix_and_uses_posix_separators() -> None:
    eid = overlay_entry_id("vault", "shared", Path("inbox/promotions/pkt/note.md"))
    assert eid == "vault:shared:inbox/promotions/pkt/note"


def test_entry_id_only_strips_final_suffix() -> None:
    # with_suffix("") removes just the last extension, not all dotted segments.
    eid = overlay_entry_id("wiki", "private", Path("notes/report.final.md"))
    assert eid == "wiki:private:notes/report.final"


def test_entry_id_for_extensionless_path_is_unchanged_stem() -> None:
    assert overlay_entry_id("wiki", "shared", Path("notes/README")) == "wiki:shared:notes/README"


def test_entry_id_distinguishes_scope_and_category() -> None:
    rel = Path("notes/x.md")
    assert overlay_entry_id("vault", "shared", rel) != overlay_entry_id("vault", "private", rel)
    assert overlay_entry_id("vault", "shared", rel) != overlay_entry_id("wiki", "shared", rel)


# --------------------------------------------------------------------------- #
# vault_overlay_output_path
# --------------------------------------------------------------------------- #
def test_vault_output_shared_packet_preserves_rel_without_scope_segment(tmp_path: Path) -> None:
    cat = tmp_path / "vault"
    rel = Path("inbox/promotions/pkt/note.md")
    # Packet paths stay verbatim under the category dir -- no scope folder injected.
    assert vault_overlay_output_path(cat, "shared", rel) == cat / "inbox/promotions/pkt/note.md"


@pytest.mark.parametrize("root", ["inbox", "notes", "sources", "drafts", "_drafts", "archive", "_system"])
def test_vault_output_known_root_inserts_scope_between_root_and_tail(tmp_path: Path, root: str) -> None:
    cat = tmp_path / "vault"
    rel = Path(f"{root}/sub/leaf.md")
    out = vault_overlay_output_path(cat, "private", rel)
    assert out == cat / root / "private" / "sub/leaf.md"


def test_vault_output_known_root_single_segment_uses_filename_as_tail(tmp_path: Path) -> None:
    cat = tmp_path / "vault"
    # rel has only the root part itself (no children); tail falls back to rel.name.
    out = vault_overlay_output_path(cat, "shared", Path("notes"))
    assert out == cat / "notes" / "shared" / "notes"


def test_vault_output_unknown_root_prefixes_scope_at_top(tmp_path: Path) -> None:
    cat = tmp_path / "vault"
    rel = Path("custom/deep/leaf.md")
    out = vault_overlay_output_path(cat, "private", rel)
    assert out == cat / "private" / "custom/deep/leaf.md"


def test_vault_output_private_packet_layout_is_not_special_cased(tmp_path: Path) -> None:
    cat = tmp_path / "vault"
    rel = Path("inbox/promotions/pkt/note.md")
    # Packet shortcut is shared-only; private routes through the known-root branch
    # because "inbox" is a recognized root.
    out = vault_overlay_output_path(cat, "private", rel)
    assert out == cat / "inbox" / "private" / "promotions/pkt/note.md"


# --------------------------------------------------------------------------- #
# wiki_overlay_output_path
# --------------------------------------------------------------------------- #
def test_wiki_output_always_nests_under_scope_segment(tmp_path: Path) -> None:
    cat = tmp_path / "wiki"
    rel = Path("topic/page.md")
    assert wiki_overlay_output_path(cat, "shared", rel) == cat / "shared" / "topic/page.md"
    assert wiki_overlay_output_path(cat, "private", rel) == cat / "private" / "topic/page.md"


def test_wiki_output_does_not_special_case_packet_layout(tmp_path: Path) -> None:
    cat = tmp_path / "wiki"
    rel = Path("inbox/promotions/pkt/note.md")
    # Unlike the vault layout, wiki never treats packet paths specially.
    out = wiki_overlay_output_path(cat, "shared", rel)
    assert out == cat / "shared" / "inbox/promotions/pkt/note.md"


def test_wiki_output_uses_posix_relative_tail_unchanged(tmp_path: Path) -> None:
    cat = tmp_path / "wiki"
    rel = Path("a/b/c.md")
    out = wiki_overlay_output_path(cat, "private", rel)
    # The full original relative path must appear verbatim after the scope segment.
    assert PurePosixPath(*out.parts[-len(rel.parts) :]) == PurePosixPath("a/b/c.md")
