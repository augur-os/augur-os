from __future__ import annotations


def test_classifies_useful_download_internal_and_noisy_links() -> None:
    from skills.ingest.scripts.email_link_classifier import classify_links

    result = classify_links(
        """
        Read https://example.com/research/post.
        Download https://example.com/report.pdf.
        Open http://localhost:3000/brain.
        Ignore https://newsletter.example.com/unsubscribe?id=1.
        """
    )

    categories = {link.url: link.category for link in result.links}
    assert categories["https://example.com/research/post"] == "article_resource"
    assert categories["https://example.com/report.pdf"] == "downloadable_file"
    assert categories["http://localhost:3000/brain"] == "internal_app"
    assert (
        categories["https://newsletter.example.com/unsubscribe?id=1"]
        == "unsupported_or_noisy"
    )
    assert result.article_resource_urls == ["https://example.com/research/post"]


def test_extracts_duplicate_links_once_and_unwraps_redirects() -> None:
    from skills.ingest.scripts.email_link_classifier import classify_links

    result = classify_links(
        "https://mail.example.com/click?url=https://example.com/a https://example.com/a"
    )

    assert [link.url for link in result.links] == ["https://example.com/a"]
