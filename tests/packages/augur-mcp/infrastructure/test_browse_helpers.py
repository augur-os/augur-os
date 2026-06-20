"""
Unit tests for browse path-security helpers (infrastructure/browse/_helpers.py).

Targets the two private helpers directly:
- ``_allowed_roots`` — composition of the allow-list (project/vault/documents/
  logs plus every indexed document-source root).
- ``_is_path_allowed`` — containment check, including parent-matching, the
  prefix-collision attack (``/allowed-evil`` must NOT match ``/allowed``),
  ``..`` traversal that escapes a root, and relative-path resolution.

These complement TestIsPathAllowed / TestIndexedDocumentSourceAllowed in
test_browse.py, which only cover the happy path, a single denied path, the root
itself, and the indexed-Desktop inclusion. The composition of _allowed_roots
and the containment edge cases below were previously untested.

Run with: pytest tests/packages/augur-mcp/infrastructure/test_browse_helpers.py -v
"""

from pathlib import Path

import pytest

from src.lib.index.document_sources import DocumentSource
from src.lib.index.document_attachments import DocumentAttachmentConfigError
from src.mcp.augur_framework.tools.infrastructure.browse._helpers import (
    _allowed_roots,
    _is_path_allowed,
)

_HELPERS = "src.mcp.augur_framework.tools.infrastructure.browse._helpers"


@pytest.fixture
def roots(tmp_path: Path, monkeypatch):
    """Isolate the four base roots and the document-source list.

    The Au-docs document source resolves to ``documents`` so its resolved_path
    equals the documents root (mirrors the real default_document_sources first
    entry). An extra ``desktop`` source is appended to exercise the extend()
    branch that pulls in indexed roots beyond the four bases.
    """
    project = tmp_path / "project"
    vault = tmp_path / "vault"
    documents = tmp_path / "documents"
    logs = tmp_path / "logs"
    desktop = tmp_path / "Desktop"
    for d in (project, vault, documents, logs, desktop):
        d.mkdir()

    monkeypatch.setattr(f"{_HELPERS}.get_project_root", lambda: project)
    monkeypatch.setattr(f"{_HELPERS}.get_vault_dir", lambda: vault)
    monkeypatch.setattr(f"{_HELPERS}.get_documents_dir", lambda: documents)
    monkeypatch.setattr(f"{_HELPERS}.get_logs_dir", lambda: logs)
    fixture_sources = [
        DocumentSource("documents", "Au-docs", documents, preserve_legacy_output=True),
        DocumentSource("desktop", "Desktop", desktop),
    ]
    # _allowed_roots prefers configured_document_sources (live machine config)
    # and only falls back to default_document_sources on config errors — patch
    # both so the test is isolated from this machine's real source registry.
    monkeypatch.setattr(
        f"{_HELPERS}.configured_document_sources",
        lambda project_root, documents_dir: fixture_sources,
    )
    monkeypatch.setattr(
        f"{_HELPERS}.default_document_sources",
        lambda documents_dir: fixture_sources,
    )
    return {
        "project": project,
        "vault": vault,
        "documents": documents,
        "logs": logs,
        "desktop": desktop,
    }


# =============================================================================
# _allowed_roots
# =============================================================================


class TestAllowedRoots:
    """Composition of the allow-list returned by _allowed_roots()."""

    def test_includes_four_base_roots(self, roots):
        """Project, vault, documents and logs roots are all present."""
        result = _allowed_roots()
        for key in ("project", "vault", "documents", "logs"):
            assert roots[key] in result

    def test_includes_indexed_document_source_roots(self, roots):
        """Resolved paths of indexed document sources are appended."""
        result = _allowed_roots()
        # The Desktop source root must be present so its files are revealable.
        assert roots["desktop"] in result

    def test_returns_resolved_paths(self, roots):
        """Every returned root is a resolved (absolute) Path."""
        result = _allowed_roots()
        assert result, "expected a non-empty allow-list"
        for root in result:
            assert isinstance(root, Path)
            assert root.is_absolute()

    def test_document_source_resolved_path_used_not_raw(self, monkeypatch, tmp_path):
        """A relative/unresolved source path is normalised via resolved_path.

        DocumentSource.resolved_path expands/resolves the configured path; the
        allow-list must use that, not the raw .path, otherwise containment
        checks (which compare resolved paths) silently fail.
        """
        project = tmp_path / "project"
        vault = tmp_path / "vault"
        documents = tmp_path / "documents"
        logs = tmp_path / "logs"
        nested = tmp_path / "real_source"
        for d in (project, vault, documents, logs, nested):
            d.mkdir()

        monkeypatch.setattr(f"{_HELPERS}.get_project_root", lambda: project)
        monkeypatch.setattr(f"{_HELPERS}.get_vault_dir", lambda: vault)
        monkeypatch.setattr(f"{_HELPERS}.get_documents_dir", lambda: documents)
        monkeypatch.setattr(f"{_HELPERS}.get_logs_dir", lambda: logs)
        # Path with a redundant "." segment — resolved_path collapses it.
        unresolved = nested / "." / ""
        monkeypatch.setattr(
            f"{_HELPERS}.configured_document_sources",
            lambda project_root, documents_dir: [DocumentSource("x", "X", unresolved)],
        )

        result = _allowed_roots()
        assert nested.resolve() in result
        assert all(".." not in str(r) for r in result)

    def test_passes_documents_dir_into_default_sources(self, monkeypatch, tmp_path):
        """default_document_sources is called with the configured documents dir."""
        documents = tmp_path / "documents"
        for d in (tmp_path / "project", tmp_path / "vault", documents, tmp_path / "logs"):
            d.mkdir()
        seen = {}

        def fake_sources(*, documents_dir):
            seen["documents_dir"] = documents_dir
            return []

        monkeypatch.setattr(f"{_HELPERS}.get_project_root", lambda: tmp_path / "project")
        monkeypatch.setattr(f"{_HELPERS}.get_vault_dir", lambda: tmp_path / "vault")
        monkeypatch.setattr(f"{_HELPERS}.get_documents_dir", lambda: documents)
        monkeypatch.setattr(f"{_HELPERS}.get_logs_dir", lambda: tmp_path / "logs")

        def broken_configured(*, project_root, documents_dir):
            raise DocumentAttachmentConfigError("forced fallback")

        monkeypatch.setattr(f"{_HELPERS}.configured_document_sources", broken_configured)
        monkeypatch.setattr(f"{_HELPERS}.default_document_sources", fake_sources)

        _allowed_roots()
        assert seen["documents_dir"] == documents


# =============================================================================
# _is_path_allowed
# =============================================================================


class TestIsPathAllowed:
    """Containment edge cases for _is_path_allowed()."""

    def test_nested_subdirectory_allowed(self, roots):
        """A deeply nested file under an allowed root is accepted."""
        target = roots["project"] / "a" / "b" / "c" / "file.txt"
        assert _is_path_allowed(str(target)) is True

    def test_file_inside_indexed_source_allowed(self, roots):
        """A file inside an indexed document-source root is accepted."""
        assert _is_path_allowed(str(roots["desktop"] / "report.pdf")) is True

    def test_prefix_collision_sibling_rejected(self, roots, tmp_path):
        """A sibling whose name merely prefixes an allowed root is rejected.

        ``/tmp/.../vault-evil`` must NOT be treated as inside ``/tmp/.../vault``.
        String-prefix matching would wrongly allow this; parent-based matching
        must reject it.
        """
        evil = tmp_path / "vault-evil"
        evil.mkdir()
        assert _is_path_allowed(str(evil / "secret.txt")) is False
        # The evil dir itself is also outside every allowed root.
        assert _is_path_allowed(str(evil)) is False

    def test_traversal_escaping_root_rejected(self, roots):
        """A `..` sequence that resolves outside all roots is rejected."""
        escape = roots["project"] / ".." / ".." / ".." / "etc" / "passwd"
        assert _is_path_allowed(str(escape)) is False

    def test_traversal_staying_inside_root_allowed(self, roots):
        """A `..` sequence that resolves back inside an allowed root passes.

        Resolution normalises ``project/sub/../file`` to ``project/file``,
        which is still inside the project root.
        """
        looped = roots["project"] / "sub" / ".." / "file.txt"
        assert _is_path_allowed(str(looped)) is True

    def test_absolute_outside_path_rejected(self, roots):
        """An absolute path outside every root is rejected."""
        assert _is_path_allowed("/etc/shadow") is False

    def test_root_itself_allowed(self, roots):
        """The allowed root directory itself is accepted (resolved == root)."""
        assert _is_path_allowed(str(roots["vault"])) is True

    def test_relative_path_resolved_against_cwd(self, roots, monkeypatch):
        """A relative path is resolved against cwd before the containment check.

        Path('x').resolve() anchors to the current working directory, so when
        cwd is an allowed root the relative path is accepted.
        """
        monkeypatch.chdir(roots["project"])
        assert _is_path_allowed("notes/today.md") is True

    def test_relative_path_outside_root_rejected(self, roots, monkeypatch):
        """A relative path resolving outside every root is rejected."""
        monkeypatch.chdir(roots["project"])
        # Climb above the project root and into a non-allowed sibling.
        assert _is_path_allowed("../some-other-dir/file.txt") is False
