from src.lib.brain_classify.links import find_dangling_links


def test_find_dangling_links_reports_cross_brain_targets(tmp_path):
    wiki = tmp_path / "wiki" / "concepts"
    wiki.mkdir(parents=True)
    (wiki / "stays.md").write_text("links to [[present-page]] and [[moved-away-page]]", encoding="utf-8")
    (wiki / "present-page.md").write_text("here", encoding="utf-8")
    # moved-away-page.md intentionally absent (it relocated to the other brain)

    dangling = find_dangling_links(wiki.parent)
    assert ("stays.md", "moved-away-page") in dangling
    assert ("stays.md", "present-page") not in dangling
