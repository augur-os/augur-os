"""Shared tokenizer for text processing across skills.

Single source of truth for tokenization: lowercase, strip punctuation,
split on whitespace, remove stopwords.
"""

from __future__ import annotations

import string

# Comprehensive stopword set — superset of all skill-specific implementations.
STOPWORDS: frozenset[str] = frozenset(
    [
        # Articles / conjunctions / prepositions
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "from",
        "into",
        "than",
        "then",
        "there",
        "when",
        "where",
        "which",
        "who",
        "what",
        "how",
        "if",
        "so",
        "up",
        "out",
        "about",
        "through",
        "during",
        "without",
        "within",
        "between",
        "after",
        "before",
        "while",
        "although",
        "however",
        "also",
        "because",
        # Auxiliary verbs
        "is",
        "it",
        "as",
        "be",
        "was",
        "were",
        "been",
        "are",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "can",
        # Demonstratives / determiners
        "this",
        "that",
        "these",
        "those",
        # Negation
        "not",
        "no",
        # Pronouns
        "its",
        "our",
        "your",
        "their",
        "my",
        "his",
        "her",
        "we",
        "you",
        "they",
        "he",
        "she",
        "i",
        "me",
        "him",
        "us",
        "them",
        # Quantifiers
        "all",
        "any",
        "each",
        "both",
        "few",
        "more",
        "most",
        "other",
        "some",
        "such",
        "only",
        "own",
        "same",
        "too",
        "very",
        "just",
    ]
)

_PUNCT_TABLE = str.maketrans("", "", string.punctuation)


def tokenize(text: str) -> list[str]:
    """Lowercase, strip punctuation, split on whitespace, remove stopwords.

    Args:
        text: Input text to tokenize.

    Returns:
        List of lowercase tokens with punctuation and stopwords removed.
    """
    text = text.lower().translate(_PUNCT_TABLE)
    return [tok for tok in text.split() if tok and tok not in STOPWORDS]
