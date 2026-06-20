from __future__ import annotations

import pytest

from skills.ingest.scripts.url_ingest import canonicalize_url, slugify_url


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://example.com/a?utm_source=x&id=1", "https://example.com/a?id=1"),
        ("https://example.com/a?fbclid=abc&id=1", "https://example.com/a?id=1"),
        ("https://example.com/a?gclid=abc", "https://example.com/a"),
        ("https://example.com/a?mc_cid=x&mc_eid=y", "https://example.com/a"),
        ("https://example.com/a?ref=twitter&ref_src=feed", "https://example.com/a"),
        ("https://example.com/a?igshid=xx", "https://example.com/a"),
        ("https://example.com/a#section", "https://example.com/a"),
        ("https://example.com/a/", "https://example.com/a"),
        ("https://example.com/", "https://example.com/"),
        ("HTTPS://EXAMPLE.COM/A", "https://example.com/A"),
        ("https://example.com/a?b=2&a=1", "https://example.com/a?a=1&b=2"),
    ],
)
def test_canonicalize_url(raw: str, expected: str) -> None:
    assert canonicalize_url(raw) == expected


def test_canonicalize_url_idempotent() -> None:
    once = canonicalize_url("https://EXAMPLE.com/a/?utm_source=x&id=1#hash")
    twice = canonicalize_url(once)

    assert once == twice == "https://example.com/a?id=1"


def test_slugify_url_basic() -> None:
    assert (
        slugify_url("https://example.com/articles/why-trees-matter")
        == "example-com-articles-why-trees-matter"
    )


def test_slugify_url_root() -> None:
    assert slugify_url("https://example.com/") == "example-com"


def test_slugify_url_truncates_long_paths() -> None:
    long = "https://example.com/" + ("a" * 200)
    slug = slugify_url(long)

    assert len(slug) <= 80
    assert slug.startswith("example-com-")
