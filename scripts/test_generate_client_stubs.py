#!/usr/bin/env python3
"""Tests for generate_client_stubs.py."""

import sys
import textwrap
from pathlib import Path

import pytest

# Allow importing the sibling module without installing it
sys.path.insert(0, str(Path(__file__).resolve().parent))

from generate_client_stubs import (
    CLIENTS,
    MARKER,
    build_stub,
    cleanup_stale_stubs,
    generate_stubs,
    is_generated,
    parse_frontmatter,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_skill(skills_dir: Path, name: str, description: str = "", body: str = "") -> Path:
    """Create a minimal SKILL.md for the given skill name."""
    skill_dir = skills_dir / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    frontmatter = f"---\nname: {name}\ndescription: {description}\n---\n"
    content = frontmatter + (("\n" + body) if body else "")
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(content, encoding="utf-8")
    return skill_md


def fake_project(tmp_path: Path) -> tuple[Path, Path]:
    """Return (project_root, skills_dir) rooted in tmp_path."""
    project_root = tmp_path / "project"
    project_root.mkdir()
    skills_dir = project_root / "project-brain" / "capabilities" / "skills"
    skills_dir.mkdir()
    return project_root, skills_dir


# ---------------------------------------------------------------------------
# parse_frontmatter
# ---------------------------------------------------------------------------


class TestParseFrontmatter:
    def test_extracts_name_and_description(self):
        text = textwrap.dedent("""\
            ---
            name: my-skill
            description: Does something useful
            x-augur-type: domain
            ---
            Body here.
        """)
        fields, body = parse_frontmatter(text)
        assert fields["name"] == "my-skill"
        assert fields["description"] == "Does something useful"
        assert "Body here." in body

    def test_no_frontmatter(self):
        text = "Just a body."
        fields, body = parse_frontmatter(text)
        assert fields == {}
        assert body == "Just a body."

    def test_skips_augur_namespaced_keys(self):
        text = textwrap.dedent("""\
            ---
            name: skill
            x-augur-hub: adaptive
            ---
        """)
        fields, _ = parse_frontmatter(text)
        assert "x-augur-hub" not in fields
        assert fields["name"] == "skill"

    def test_body_excludes_frontmatter(self):
        text = "---\nname: s\n---\nbody line\n"
        _, body = parse_frontmatter(text)
        assert "name:" not in body
        assert "body line" in body


# ---------------------------------------------------------------------------
# build_stub
# ---------------------------------------------------------------------------


class TestBuildStub:
    def test_marker_is_first_line(self):
        stub = build_stub("my-skill", "A description", "")
        first_line = stub.split("\n")[0]
        assert first_line == MARKER

    def test_contains_name_as_heading(self):
        stub = build_stub("my-skill", "A description", "")
        assert "# my-skill" in stub

    def test_contains_description(self):
        stub = build_stub("my-skill", "Useful skill", "")
        assert "Useful skill" in stub

    def test_contains_body(self):
        stub = build_stub("my-skill", "", "## Usage\nDo things.")
        assert "## Usage" in stub

    def test_ends_with_newline(self):
        stub = build_stub("s", "", "")
        assert stub.endswith("\n")


# ---------------------------------------------------------------------------
# is_generated
# ---------------------------------------------------------------------------


class TestIsGenerated:
    def test_marked_file_returns_true(self, tmp_path):
        f = tmp_path / "stub.md"
        f.write_text(f"{MARKER}\nsome content\n")
        assert is_generated(f) is True

    def test_unmarked_file_returns_false(self, tmp_path):
        f = tmp_path / "user.md"
        f.write_text("# My custom file\nno marker here\n")
        assert is_generated(f) is False

    def test_missing_file_returns_false(self, tmp_path):
        assert is_generated(tmp_path / "nonexistent.md") is False


# ---------------------------------------------------------------------------
# generate_stubs
# ---------------------------------------------------------------------------


class TestGenerateStubs:
    def test_creates_stubs_for_all_clients(self, tmp_path):
        project_root, skills_dir = fake_project(tmp_path)
        make_skill(skills_dir, "demo-skill", description="A demo")

        generate_stubs(project_root, skills_dir, dry_run=False)

        for client, (rel_dir, ext) in CLIENTS.items():
            stub = project_root / rel_dir / f"demo-skill{ext}"
            assert stub.exists(), f"Missing stub for client {client}: {stub}"

    def test_generated_stub_starts_with_marker(self, tmp_path):
        project_root, skills_dir = fake_project(tmp_path)
        make_skill(skills_dir, "alpha", description="Alpha skill")

        generate_stubs(project_root, skills_dir, dry_run=False)

        for _client, (rel_dir, ext) in CLIENTS.items():
            stub = project_root / rel_dir / f"alpha{ext}"
            first_line = stub.read_text().split("\n")[0]
            assert first_line == MARKER, f"Marker missing in {stub}"

    def test_stub_contains_description(self, tmp_path):
        project_root, skills_dir = fake_project(tmp_path)
        make_skill(skills_dir, "beta", description="Beta does things")

        generate_stubs(project_root, skills_dir, dry_run=False)

        for _client, (rel_dir, ext) in CLIENTS.items():
            stub = project_root / rel_dir / f"beta{ext}"
            assert "Beta does things" in stub.read_text()

    def test_dry_run_writes_nothing(self, tmp_path):
        project_root, skills_dir = fake_project(tmp_path)
        make_skill(skills_dir, "gamma")

        generate_stubs(project_root, skills_dir, dry_run=True)

        for _client, (rel_dir, ext) in CLIENTS.items():
            stub = project_root / rel_dir / f"gamma{ext}"
            assert not stub.exists(), f"dry-run should not create {stub}"

    def test_empty_skills_dir_produces_no_stubs(self, tmp_path):
        project_root, skills_dir = fake_project(tmp_path)

        written, _ = generate_stubs(project_root, skills_dir, dry_run=False)

        assert written == []

    def test_uses_name_field_not_dir_name(self, tmp_path):
        """If frontmatter name != directory name, stub uses frontmatter name."""
        project_root, skills_dir = fake_project(tmp_path)
        # Directory is "dir-name" but frontmatter name is "canonical-name"
        skill_dir = skills_dir / "dir-name"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: canonical-name\ndescription: test\n---\n"
        )

        generate_stubs(project_root, skills_dir, dry_run=False)

        for _client, (rel_dir, ext) in CLIENTS.items():
            canonical_stub = project_root / rel_dir / f"canonical-name{ext}"
            dir_stub = project_root / rel_dir / f"dir-name{ext}"
            assert canonical_stub.exists()
            assert not dir_stub.exists()


# ---------------------------------------------------------------------------
# cleanup_stale_stubs
# ---------------------------------------------------------------------------


class TestCleanupStaleStubs:
    def _place_stub(
        self,
        project_root: Path,
        client: str,
        skill_name: str,
        *,
        marked: bool = True,
    ) -> Path:
        rel_dir, ext = CLIENTS[client]
        target_dir = project_root / rel_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        stub = target_dir / f"{skill_name}{ext}"
        if marked:
            stub.write_text(f"{MARKER}\n# {skill_name}\n")
        else:
            stub.write_text(f"# {skill_name}\nUser content.\n")
        return stub

    def test_deletes_marked_stub_for_missing_skill(self, tmp_path):
        project_root, skills_dir = fake_project(tmp_path)
        # No skill named "gone-skill" exists
        stale = self._place_stub(project_root, "codex", "gone-skill", marked=True)

        cleanup_stale_stubs(project_root, skills_dir, dry_run=False)

        assert not stale.exists(), "Stale marked stub should be deleted"

    def test_preserves_unmarked_user_file(self, tmp_path):
        project_root, skills_dir = fake_project(tmp_path)
        user_file = self._place_stub(project_root, "codex", "user-prompt", marked=False)

        cleanup_stale_stubs(project_root, skills_dir, dry_run=False)

        assert user_file.exists(), "User-installed (unmarked) file must not be deleted"

    def test_preserves_valid_skill_stub(self, tmp_path):
        project_root, skills_dir = fake_project(tmp_path)
        make_skill(skills_dir, "live-skill", description="Still here")
        stub = self._place_stub(project_root, "codex", "live-skill", marked=True)

        cleanup_stale_stubs(project_root, skills_dir, dry_run=False)

        assert stub.exists(), "Stub for an existing skill must not be deleted"

    def test_dry_run_does_not_delete(self, tmp_path):
        project_root, skills_dir = fake_project(tmp_path)
        stale = self._place_stub(project_root, "cursor", "old-skill", marked=True)

        cleanup_stale_stubs(project_root, skills_dir, dry_run=True)

        assert stale.exists(), "dry-run must not delete anything"

    def test_returns_deleted_paths(self, tmp_path):
        project_root, skills_dir = fake_project(tmp_path)
        stale = self._place_stub(project_root, "copilot", "stale-one", marked=True)

        deleted = cleanup_stale_stubs(project_root, skills_dir, dry_run=False)

        assert str(stale) in deleted

    def test_missing_target_dir_is_safe(self, tmp_path):
        """cleanup_stale_stubs should not crash when a client dir doesn't exist."""
        project_root, skills_dir = fake_project(tmp_path)
        # No client dirs created at all
        deleted = cleanup_stale_stubs(project_root, skills_dir, dry_run=False)
        assert deleted == []

    def test_cleanup_across_all_clients(self, tmp_path):
        """Stale stubs in every client dir are all cleaned up in one run."""
        project_root, skills_dir = fake_project(tmp_path)
        stubs = [
            self._place_stub(project_root, client, "vanished", marked=True)
            for client in CLIENTS
        ]

        cleanup_stale_stubs(project_root, skills_dir, dry_run=False)

        for stub in stubs:
            assert not stub.exists()


# ---------------------------------------------------------------------------
# Integration: generate then cleanup
# ---------------------------------------------------------------------------


class TestIntegration:
    def test_full_round_trip(self, tmp_path):
        """Generate stubs, remove a skill, cleanup removes its stubs."""
        project_root, skills_dir = fake_project(tmp_path)
        make_skill(skills_dir, "keeper", description="Stays")
        make_skill(skills_dir, "leaver", description="Goes away")

        generate_stubs(project_root, skills_dir, dry_run=False)

        # Remove leaver skill
        import shutil

        shutil.rmtree(skills_dir / "leaver")

        cleanup_stale_stubs(project_root, skills_dir, dry_run=False)

        for _client, (rel_dir, ext) in CLIENTS.items():
            assert (project_root / rel_dir / f"keeper{ext}").exists()
            assert not (project_root / rel_dir / f"leaver{ext}").exists()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
