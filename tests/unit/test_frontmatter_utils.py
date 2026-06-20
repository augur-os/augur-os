from pathlib import Path
import tempfile
from src.lib.frontmatter_utils import (
    VAULT_SYSTEM_FIELD_MAP,
    get_skill_config_sidecar,
    load_collection,
    load_skill_contract,
    load_skill_frontmatter,
    merge_vault_frontmatter,
    parse_frontmatter,
    write_frontmatter,
    write_vault_frontmatter,
)


def _write_tmp(content: str) -> Path:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8")
    f.write(content)
    f.close()
    return Path(f.name)


class TestParseFrontmatter:
    def test_basic(self):
        path = _write_tmp("---\nstatus: Implemented\ndate: 2026-03-04\n---\n\n# Title\n\nBody text.\n")
        meta, body = parse_frontmatter(path)
        assert meta["status"] == "Implemented"
        assert "# Title" in body
        assert "Body text." in body

    def test_no_frontmatter(self):
        path = _write_tmp("# Just Markdown\n\nNo frontmatter here.\n")
        meta, body = parse_frontmatter(path)
        assert meta == {}
        assert "# Just Markdown" in body

    def test_empty_frontmatter(self):
        path = _write_tmp("---\n---\n\nBody.\n")
        meta, body = parse_frontmatter(path)
        assert meta == {}
        assert "Body." in body

    def test_unicode(self):
        path = _write_tmp("---\ntitle: שלום עולם\n---\n\nContent with émojis 🎉\n")
        meta, body = parse_frontmatter(path)
        assert meta["title"] == "שלום עולם"
        assert "🎉" in body

    def test_multiline_values(self):
        path = _write_tmp("---\ndeciders:\n  - Alice\n  - Bob\n---\n\nBody.\n")
        meta, body = parse_frontmatter(path)
        assert meta["deciders"] == ["Alice", "Bob"]

    def test_merges_sidecar_config_by_default(self, tmp_path):
        skill_md = tmp_path / "SKILL.md"
        sidecar = tmp_path / "config.yaml"
        skill_md.write_text("---\nname: demo\nx-augur-config-file: config.yaml\n---\n\nBody.\n")
        sidecar.write_text("hub:\n  id: life\n")

        meta, body = parse_frontmatter(skill_md)

        assert meta["name"] == "demo"
        assert meta["x-augur-config"]["hub"]["id"] == "life"
        assert body == "\nBody.\n"

    def test_can_read_raw_frontmatter_without_sidecar_config(self, tmp_path):
        skill_md = tmp_path / "SKILL.md"
        sidecar = tmp_path / "config.yaml"
        skill_md.write_text("---\nname: demo\nx-augur-config-file: config.yaml\n---\n\nBody.\n")
        sidecar.write_text("hub:\n  id: life\n")

        meta, body = parse_frontmatter(skill_md, include_sidecar_config=False)

        assert meta == {"name": "demo", "x-augur-config-file": "config.yaml"}
        assert body == "\nBody.\n"


class TestWriteFrontmatter:
    def test_round_trip(self, tmp_path):
        p = tmp_path / "test.md"
        meta = {"status": "Implemented", "date": "2026-03-04", "tags": ["foo", "bar"]}
        body = "# Title\n\nBody text.\n"
        write_frontmatter(p, meta, body)
        meta2, body2 = parse_frontmatter(p)
        assert meta2["status"] == "Implemented"
        assert meta2["tags"] == ["foo", "bar"]
        assert "Body text." in body2

    def test_unicode_round_trip(self, tmp_path):
        p = tmp_path / "unicode.md"
        meta = {"title": "שלום", "tags": ["עברית"]}
        write_frontmatter(p, meta, "Content.\n")
        meta2, body2 = parse_frontmatter(p)
        assert meta2["title"] == "שלום"

    def test_preserves_key_order(self, tmp_path):
        p = tmp_path / "order.md"
        from collections import OrderedDict

        meta = OrderedDict([("status", "Proposed"), ("date", "2026-03-04"), ("hub", "dev")])
        write_frontmatter(p, meta, "Body.\n")
        content = p.read_text()
        lines = content.split("\n")
        # Keys should appear in insertion order
        status_line = next(i for i, line in enumerate(lines) if line.startswith("status:"))
        date_line = next(i for i, line in enumerate(lines) if line.startswith("date:"))
        hub_line = next(i for i, line in enumerate(lines) if line.startswith("hub:"))
        assert status_line < date_line < hub_line

    def test_empty_body(self, tmp_path):
        p = tmp_path / "empty.md"
        write_frontmatter(p, {"status": "Proposed"}, "")
        meta, body = parse_frontmatter(p)
        assert meta["status"] == "Proposed"
        assert body.strip() == ""

    def test_write_vault_frontmatter_preserves_unrelated_user_metadata(self, tmp_path):
        p = tmp_path / "vault.md"
        write_frontmatter(p, {"user_note": "keep", "title": "Old"}, "Old body\n")

        write_vault_frontmatter(p, {"title": "New", "source": "augur"}, "New body\n")

        meta, body = parse_frontmatter(p)
        assert meta["user_note"] == "keep"
        assert meta["title"] == "New"
        assert meta["source"] == "augur"
        assert "New body" in body

    def test_merge_vault_frontmatter_skips_none_values(self):
        merged = merge_vault_frontmatter(
            {"title": "User", "user_note": "keep"},
            {"title": "System", "empty": None},
        )

        assert merged == {"title": "System", "user_note": "keep"}
        assert "empty" not in merged
        assert "source_fingerprint" in VAULT_SYSTEM_FIELD_MAP


class TestLoadCollection:
    def test_loads_directory(self, tmp_path):
        write_frontmatter(tmp_path / "a.md", {"id": "a", "status": "active"}, "Body A.\n")
        write_frontmatter(tmp_path / "b.md", {"id": "b", "status": "done"}, "Body B.\n")
        items = load_collection(tmp_path)
        assert len(items) == 2
        ids = {i["id"] for i in items}
        assert ids == {"a", "b"}

    def test_empty_directory(self, tmp_path):
        items = load_collection(tmp_path)
        assert items == []

    def test_skips_non_md(self, tmp_path):
        write_frontmatter(tmp_path / "good.md", {"id": "good"}, "Body.\n")
        (tmp_path / "skip.yaml").write_text("key: val\n")
        items = load_collection(tmp_path)
        assert len(items) == 1
        assert items[0]["id"] == "good"


class TestSkillLoaders:
    def test_load_skill_frontmatter_merges_sidecar(self, tmp_path):
        skill_md = tmp_path / "demo" / "SKILL.md"
        skill_md.parent.mkdir(parents=True)
        skill_md.write_text(
            "---\nname: demo\nx-augur-hub: workspace\nx-augur-config-file: config.yaml\n---\n\nBody.\n",
        )
        (skill_md.parent / "config.yaml").write_text(
            "contributions:\n  pages:\n    - id: overview\n",
        )

        frontmatter = load_skill_frontmatter(skill_md.parent)

        assert frontmatter["name"] == "demo"
        assert frontmatter["x-augur-config"]["contributions"]["pages"][0]["id"] == "overview"

    def test_get_skill_config_sidecar_returns_declared_path(self, tmp_path):
        skill_md = tmp_path / "demo" / "SKILL.md"
        skill_md.parent.mkdir(parents=True)
        skill_md.write_text(
            "---\nname: demo\nx-augur-config-file: config.yaml\n---\n",
        )

        sidecar = get_skill_config_sidecar(skill_md.parent)

        assert sidecar == skill_md.parent / "config.yaml"

    def test_load_skill_contract_exposes_compatibility_aliases(self, tmp_path):
        skill_md = tmp_path / "demo" / "SKILL.md"
        skill_md.parent.mkdir(parents=True)
        skill_md.write_text(
            """---
name: demo
description: Demo skill
x-augur-mcp-tools:
  - get-demo-status
x-augur-commands:
  - id: auto-demo
    callable: scripts/demo.py
x-augur-config:
  contributions:
    pages:
      - id: overview
---
Body.
""",
        )

        contract = load_skill_contract(skill_md.parent)

        assert contract["name"] == "demo"
        assert contract["mcp"]["tools"] == ["get-demo-status"]
        assert contract["commands"][0]["id"] == "auto-demo"
        assert contract["contributions"]["pages"][0]["id"] == "overview"
