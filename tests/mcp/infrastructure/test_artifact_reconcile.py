"""Tests for session-aware /keep artifact reconcile tools."""

import asyncio
import base64
import json
import os
import time
from dataclasses import dataclass, field

from src.mcp.augur_framework.tools.infrastructure import artifact_reconcile
from src.mcp.augur_framework.tools.infrastructure.artifact_reconcile import (
    artifact_cleanup_impl,
    artifact_locate_impl,
    group_version_families,
    normalize_stem,
)


class TestNormalizeStem:
    def test_strips_download_counter(self):
        assert normalize_stem("augur-pitch (1).pptx") == normalize_stem("augur-pitch.pptx")

    def test_strips_version_and_final_markers(self):
        base = normalize_stem("Q3 deck.pptx")
        assert normalize_stem("Q3 deck v2.pptx") == base
        assert normalize_stem("Q3-deck-final.pptx") == base

    def test_distinct_names_stay_distinct(self):
        assert normalize_stem("augur-pitch.pptx") != normalize_stem("career-cv.pptx")

    def test_year_parenthetical_is_not_a_download_counter(self):
        assert normalize_stem("Report (2024).pdf") != normalize_stem("Report.pdf")

    def test_stacked_markers_strip_to_fixpoint(self):
        assert normalize_stem("deck v2 (1).pptx") == normalize_stem("deck.pptx")


class TestGroupVersionFamilies:
    def test_groups_counter_variants_and_picks_latest_by_mtime(self, tmp_path):
        old = tmp_path / "deck.pptx"
        new = tmp_path / "deck (1).pptx"
        old.write_bytes(b"a")
        new.write_bytes(b"bb")
        past = time.time() - 3600
        os.utime(old, (past, past))

        families = group_version_families([old, new])
        assert len(families) == 1
        family = families[0]
        assert family["latest"] == str(new)
        assert {m["path"] for m in family["members"]} == {str(old), str(new)}

    def test_different_extensions_are_different_families(self, tmp_path):
        a = tmp_path / "deck.pptx"
        b = tmp_path / "deck.pdf"
        a.write_bytes(b"a")
        b.write_bytes(b"b")
        assert len(group_version_families([a, b])) == 2


class TestArtifactLocate:
    def test_finds_hinted_recent_files_and_skips_old_and_unhinted(self, tmp_path):
        hit = tmp_path / "augur pitch v3.pptx"
        unhinted = tmp_path / "tax-return.pdf"
        stale = tmp_path / "augur pitch old.pptx"
        for f in (hit, unhinted, stale):
            f.write_bytes(b"x")
        week_ago = time.time() - 7 * 86400
        os.utime(stale, (week_ago, week_ago))

        result = json.loads(
            artifact_locate_impl(
                name_hints=["augur pitch"],
                extensions=[".pptx", ".pdf"],
                hours_back=48,
                roots=[str(tmp_path)],
            )
        )
        assert result["success"] is True
        paths = {m["path"] for fam in result["families"] for m in fam["members"]}
        assert str(hit) in paths
        assert str(unhinted) not in paths
        assert str(stale) not in paths

    def test_no_hints_returns_all_recent_matching_extensions(self, tmp_path):
        f = tmp_path / "anything.key"
        f.write_bytes(b"x")
        result = json.loads(
            artifact_locate_impl(
                name_hints=[],
                extensions=[".key"],
                hours_back=24,
                roots=[str(tmp_path)],
            )
        )
        assert result["success"] is True
        assert len(result["families"]) == 1

    def test_reports_searched_roots_when_nothing_found(self, tmp_path):
        result = json.loads(
            artifact_locate_impl(
                name_hints=["nonexistent"],
                extensions=[".pptx"],
                hours_back=24,
                roots=[str(tmp_path)],
            )
        )
        assert result["success"] is True
        assert result["families"] == []
        assert result["searched_roots"] == [str(tmp_path)]


class TestArtifactCleanup:
    def test_refuses_paths_outside_allowed_roots(self, tmp_path):
        inside_root = tmp_path / "downloads"
        inside_root.mkdir()
        outside = tmp_path / "elsewhere" / "deck.pptx"
        outside.parent.mkdir()
        outside.write_bytes(b"x")

        result = json.loads(
            artifact_cleanup_impl(
                trash_paths=[str(outside)],
                allowed_roots=[str(inside_root)],
            )
        )
        assert result["success"] is False
        assert str(outside) in result["refused"][0]["path"]
        assert outside.exists(), "refused plan must not touch anything"

    def test_refusal_is_all_or_nothing(self, tmp_path):
        root = tmp_path / "downloads"
        root.mkdir()
        valid = root / "deck (1).pptx"
        valid.write_bytes(b"x")
        invalid = tmp_path / "outside.pptx"
        invalid.write_bytes(b"x")

        result = json.loads(
            artifact_cleanup_impl(
                trash_paths=[str(valid), str(invalid)],
                allowed_roots=[str(root)],
            )
        )
        assert result["success"] is False
        assert valid.exists(), "valid path must survive when plan is refused"

    def test_trashes_approved_paths(self, tmp_path, monkeypatch):
        root = tmp_path / "downloads"
        root.mkdir()
        stale = root / "deck (1).pptx"
        stale.write_bytes(b"x")
        trashed = []
        monkeypatch.setattr(
            "src.mcp.augur_framework.tools.infrastructure.artifact_reconcile._send_to_trash",
            lambda p: trashed.append(str(p)),
        )

        result = json.loads(artifact_cleanup_impl(trash_paths=[str(stale)], allowed_roots=[str(root)]))
        assert result["success"] is True
        assert trashed == [str(stale)]
        assert result["trashed"] == [str(stale)]

    def test_canonical_move_requires_existing_dest_folder(self, tmp_path):
        root = tmp_path / "mirror"
        root.mkdir()
        src = root / "deck v3.pptx"
        src.write_bytes(b"x")
        missing_dest = root / "Decks" / "Augur"  # not created on purpose

        result = json.loads(
            artifact_cleanup_impl(
                trash_paths=[],
                canonical_move={"source": str(src), "dest_folder": str(missing_dest)},
                allowed_roots=[str(root)],
            )
        )
        assert result["success"] is False
        assert "dest_folder" in result["refused"][0]["reason"]
        assert src.exists()

    def test_canonical_move_moves_into_existing_folder(self, tmp_path):
        root = tmp_path / "mirror"
        dest = root / "Decks"
        dest.mkdir(parents=True)
        src = root / "deck v3.pptx"
        src.write_bytes(b"payload")

        result = json.loads(
            artifact_cleanup_impl(
                trash_paths=[],
                canonical_move={"source": str(src), "dest_folder": str(dest)},
                allowed_roots=[str(root)],
            )
        )
        assert result["success"] is True
        assert (dest / "deck v3.pptx").read_bytes() == b"payload"
        assert not src.exists()

    def test_duplicate_trash_paths_dedupe_to_single_receipt(self, tmp_path, monkeypatch):
        root = tmp_path / "downloads"
        root.mkdir()
        stale = root / "deck (1).pptx"
        stale.write_bytes(b"x")
        trashed = []
        monkeypatch.setattr(
            "src.mcp.augur_framework.tools.infrastructure.artifact_reconcile._send_to_trash",
            lambda p: trashed.append(str(p)),
        )

        result = json.loads(
            artifact_cleanup_impl(
                trash_paths=[str(stale), str(stale)],
                allowed_roots=[str(root)],
            )
        )
        assert result["success"] is True
        assert trashed == [str(stale)], "duplicate entries must trash only once"
        assert result["trashed"] == [str(stale)]

    def test_refuses_when_canonical_source_also_in_trash_paths(self, tmp_path):
        root = tmp_path / "mirror"
        dest = root / "Decks"
        dest.mkdir(parents=True)
        src = root / "deck v3.pptx"
        src.write_bytes(b"payload")

        result = json.loads(
            artifact_cleanup_impl(
                trash_paths=[str(src)],
                canonical_move={"source": str(src), "dest_folder": str(dest)},
                allowed_roots=[str(root)],
            )
        )
        assert result["success"] is False
        assert any("also listed in trash_paths" in r["reason"] for r in result["refused"])
        assert src.exists(), "refused plan must not touch anything"
        assert not (dest / src.name).exists()

    def test_canonical_move_refuses_when_dest_file_exists(self, tmp_path):
        root = tmp_path / "mirror"
        dest = root / "Decks"
        dest.mkdir(parents=True)
        src = root / "deck v3.pptx"
        src.write_bytes(b"new payload")
        existing = dest / "deck v3.pptx"
        existing.write_bytes(b"old payload")

        result = json.loads(
            artifact_cleanup_impl(
                trash_paths=[],
                canonical_move={"source": str(src), "dest_folder": str(dest)},
                allowed_roots=[str(root)],
            )
        )
        assert result["success"] is False
        assert result["refused"][0]["reason"] == "dest exists"
        assert src.read_bytes() == b"new payload"
        assert existing.read_bytes() == b"old payload"

    def test_combined_plan_moves_latest_and_trashes_intermediates(self, tmp_path, monkeypatch):
        root = tmp_path / "mirror"
        dest = root / "Decks"
        dest.mkdir(parents=True)
        latest = root / "deck v3.pptx"
        latest.write_bytes(b"payload")
        stale_one = root / "deck v1.pptx"
        stale_two = root / "deck (1).pptx"
        stale_one.write_bytes(b"x")
        stale_two.write_bytes(b"x")
        trashed = []
        monkeypatch.setattr(
            "src.mcp.augur_framework.tools.infrastructure.artifact_reconcile._send_to_trash",
            lambda p: trashed.append(str(p)),
        )

        result = json.loads(
            artifact_cleanup_impl(
                trash_paths=[str(stale_one), str(stale_two)],
                canonical_move={"source": str(latest), "dest_folder": str(dest)},
                allowed_roots=[str(root)],
            )
        )
        assert result["success"] is True
        assert result["moved"] == {
            "from": str(latest),
            "to": str(dest / "deck v3.pptx"),
        }
        assert result["trashed"] == [str(stale_one), str(stale_two)]
        assert result["refused"] == []
        assert (dest / "deck v3.pptx").read_bytes() == b"payload"
        assert not latest.exists()
        assert trashed == [str(stale_one), str(stale_two)]


@dataclass(frozen=True)
class _FakeProposal:
    packet_id: str = "pkt-1"
    target_vault: str = "personal"
    target_domain: str = "docs"
    target_folder: str = "inbox"
    final_filename: str = "deck.pptx"
    route_reason: str = "deterministic"
    version_group: str = ""
    status: str = "ready"
    questions: list = field(default_factory=list)


class _FakeLifecycle:
    def __init__(self):
        self.staged_kwargs = None
        self.consumed_proposal = None

    def install(self, monkeypatch, proposal=None, consume_status="success"):
        proposal = proposal or _FakeProposal()
        fake_packet = object()
        fake_target = object()

        def fake_stage_packet(**kwargs):
            self.staged_kwargs = kwargs
            return fake_packet

        def fake_resolve_target(packet):
            return fake_target

        def fake_propose(packet, target):
            return proposal

        def fake_consume(*, packet, target, proposal):
            self.consumed_proposal = proposal

            class R:
                status = consume_status
                final_paths = ["/au-docs/venture-augur/deck.pptx"]
                sidecar_paths = ["/au-vault/knowledge/sources/deck.md"]
                questions = list(proposal.questions)

            return R()

        monkeypatch.setattr(
            artifact_reconcile,
            "_load_ingest_lifecycle",
            lambda: (fake_stage_packet, fake_resolve_target, fake_propose, fake_consume),
        )


class TestArtifactKeep:
    def test_files_payload_from_source_path(self, tmp_path, monkeypatch):
        lifecycle = _FakeLifecycle()
        lifecycle.install(monkeypatch)
        deck = tmp_path / "augur pitch (3).pptx"
        deck.write_bytes(b"payload")

        result = json.loads(
            artifact_reconcile.artifact_keep_impl(
                source_path=str(deck),
                title="Augur pitch",
                target_folder="venture-augur/decks",
            )
        )
        assert result["success"] is True
        assert lifecycle.staged_kwargs["content"] == b"payload"
        assert lifecycle.staged_kwargs["filename"] == "augur pitch (3).pptx"
        assert lifecycle.consumed_proposal.target_folder == "venture-augur/decks"
        assert result["final_paths"] == ["/au-docs/venture-augur/deck.pptx"]

    def test_files_payload_from_base64_content(self, monkeypatch):
        lifecycle = _FakeLifecycle()
        lifecycle.install(monkeypatch)

        result = json.loads(
            artifact_reconcile.artifact_keep_impl(
                content_base64=base64.b64encode(b"<html>deck</html>").decode(),
                filename="deck.html",
                title="Deck",
                target_folder="venture-augur",
            )
        )
        assert result["success"] is True
        assert lifecycle.staged_kwargs["content"] == b"<html>deck</html>"

    def test_rejects_oversized_base64(self, monkeypatch):
        lifecycle = _FakeLifecycle()
        lifecycle.install(monkeypatch)
        monkeypatch.setattr(artifact_reconcile, "MAX_CONTENT_BYTES", 8)

        result = json.loads(
            artifact_reconcile.artifact_keep_impl(
                content_base64=base64.b64encode(b"way too large").decode(),
                filename="deck.pptx",
                title="Deck",
                target_folder="x",
            )
        )
        assert result["success"] is False
        assert "size" in result["error"].lower()
        assert lifecycle.staged_kwargs is None, "must not stage oversized content"

    def test_passes_through_needs_input(self, tmp_path, monkeypatch):
        lifecycle = _FakeLifecycle()
        lifecycle.install(
            monkeypatch,
            proposal=_FakeProposal(status="needs_input", questions=["which vault?"]),
            consume_status="needs_input",
        )
        deck = tmp_path / "deck.pptx"
        deck.write_bytes(b"x")

        result = json.loads(
            artifact_reconcile.artifact_keep_impl(source_path=str(deck), title="Deck", target_folder="")
        )
        assert result["success"] is False
        assert result["status"] == "needs_input"
        assert result["questions"] == ["which vault?"]

    def test_target_folder_override_skipped_on_non_ready_proposal(self, tmp_path, monkeypatch):
        lifecycle = _FakeLifecycle()
        lifecycle.install(
            monkeypatch,
            proposal=_FakeProposal(status="needs_input", questions=["which vault?"]),
            consume_status="needs_input",
        )
        deck = tmp_path / "deck.pptx"
        deck.write_bytes(b"x")

        result = json.loads(
            artifact_reconcile.artifact_keep_impl(source_path=str(deck), title="Deck", target_folder="x")
        )
        assert result["success"] is False
        assert lifecycle.consumed_proposal.target_folder == "inbox", "override must NOT apply on non-ready proposals"

    def test_rejects_base64_without_filename(self, monkeypatch):
        lifecycle = _FakeLifecycle()
        lifecycle.install(monkeypatch)

        result = json.loads(
            artifact_reconcile.artifact_keep_impl(
                content_base64=base64.b64encode(b"x").decode(),
                title="Deck",
                target_folder="x",
            )
        )
        assert result["success"] is False
        assert "filename" in result["error"]
        assert lifecycle.staged_kwargs is None

    def test_rejects_missing_source_path(self, tmp_path, monkeypatch):
        lifecycle = _FakeLifecycle()
        lifecycle.install(monkeypatch)

        result = json.loads(
            artifact_reconcile.artifact_keep_impl(source_path=str(tmp_path / "nope.pptx"), title="Deck")
        )
        assert result["success"] is False
        assert "not a file" in result["error"]
        assert lifecycle.staged_kwargs is None

    def test_rejects_when_neither_input_given(self, monkeypatch):
        lifecycle = _FakeLifecycle()
        lifecycle.install(monkeypatch)

        result = json.loads(artifact_reconcile.artifact_keep_impl(title="Deck"))
        assert result["success"] is False
        assert "source_path or content_base64" in result["error"]
        assert lifecycle.staged_kwargs is None

    def test_rejects_invalid_base64(self, monkeypatch):
        lifecycle = _FakeLifecycle()
        lifecycle.install(monkeypatch)

        result = json.loads(
            artifact_reconcile.artifact_keep_impl(
                content_base64="data:text/plain;base64," + base64.b64encode(b"deck").decode(),
                filename="deck.txt",
                title="Deck",
                target_folder="x",
            )
        )
        assert result["success"] is False
        assert lifecycle.staged_kwargs is None, "must not stage corrupted content"


class TestRegistration:
    def _register(self):
        registered = []
        captured_fn = {}
        captured_annotations = {}

        class FakeMCP:
            def tool(self, name=None, annotations=None):
                def deco(fn):
                    registered.append(name)
                    captured_fn[name] = fn
                    captured_annotations[name] = annotations
                    return fn

                return deco

        class FakeMetrics:
            def track_tool(self, *a, **k):
                pass

        artifact_reconcile.register_artifact_reconcile_tools(FakeMCP(), lambda fn: fn, FakeMetrics())
        return registered, captured_fn, captured_annotations

    def test_registers_three_tools(self):
        registered, _, _ = self._register()
        assert registered == ["artifact-locate", "artifact-keep", "artifact-cleanup"]

    def test_safety_annotations(self):
        # tool_annotations returns an mcp ToolAnnotations model, not a dict.
        _, _, annotations = self._register()
        assert annotations["artifact-locate"].readOnlyHint is True
        assert annotations["artifact-locate"].destructiveHint is False
        assert annotations["artifact-cleanup"].destructiveHint is True
        assert annotations["artifact-cleanup"].readOnlyHint is False
        assert annotations["artifact-keep"].destructiveHint is False

    def test_locate_wrapper_calls_impl_end_to_end(self, tmp_path):
        _, captured_fn, _ = self._register()
        deck = tmp_path / "deck.pptx"
        deck.write_bytes(b"x")

        result = json.loads(asyncio.run(captured_fn["artifact-locate"](roots=[str(tmp_path)])))
        assert result["success"] is True
        assert result["searched_roots"] == [str(tmp_path)]
        assert len(result["families"]) == 1
