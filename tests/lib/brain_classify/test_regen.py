from src.lib.brain_classify.regen import regenerate_wiki_metadata
from src.lib.frontmatter_utils import parse_frontmatter


def test_regenerate_rebuilds_index_and_overview_with_concept_count(tmp_path):
    wiki = tmp_path / "wiki"
    concepts = wiki / "concepts"
    concepts.mkdir(parents=True)
    (concepts / "a.md").write_text("---\ntitle: A\n---\nbody a", encoding="utf-8")
    (concepts / "b.md").write_text("---\ntitle: B\n---\nbody b", encoding="utf-8")

    regenerate_wiki_metadata(wiki_dir=wiki)

    index = (wiki / "index.md").read_text(encoding="utf-8")
    overview_meta, _ = parse_frontmatter(wiki / "overview.md")
    # both concept pages reflected in the regenerated membership index
    assert "a" in index and "b" in index
    assert int(overview_meta["concept_count"]) == 2
