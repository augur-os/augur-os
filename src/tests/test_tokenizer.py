"""Tests for src.lib.tokenizer — shared tokenization utility."""

from src.lib.tokenizer import tokenize


def test_lowercase():
    assert tokenize("Hello WORLD") == ["hello", "world"]


def test_removes_stopwords():
    result = tokenize("the quick brown fox")
    assert result == ["quick", "brown", "fox"]


def test_strips_punctuation():
    assert tokenize("hello, world!") == ["hello", "world"]


def test_empty_string():
    assert tokenize("") == []
