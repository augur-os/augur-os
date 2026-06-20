from __future__ import annotations

from skills.ingest.scripts.url_ingest import compute_content_hash


def test_hash_format() -> None:
    digest = compute_content_hash("https://example.com/a", "body text")

    assert digest.startswith("sha256:")
    assert len(digest) == len("sha256:") + 64


def test_hash_stable_across_runs() -> None:
    first = compute_content_hash("https://example.com/a", "body text")
    second = compute_content_hash("https://example.com/a", "body text")

    assert first == second


def test_hash_changes_on_body_diff() -> None:
    first = compute_content_hash("https://example.com/a", "body text")
    second = compute_content_hash("https://example.com/a", "body text v2")

    assert first != second


def test_hash_changes_on_url_diff() -> None:
    first = compute_content_hash("https://example.com/a", "body text")
    second = compute_content_hash("https://example.com/b", "body text")

    assert first != second


def test_hash_unicode_safe() -> None:
    digest = compute_content_hash("https://example.com/é", "résumé text - emoji 🌳")

    assert digest.startswith("sha256:")
