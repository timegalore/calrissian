"""Word frequency analysis."""

from __future__ import annotations

from collections import Counter

from calrission.word_filter import normalize_word, should_exclude, tokenize


def count_words(text: str) -> Counter[str]:
    counts: Counter[str] = Counter()

    for word, sentence_start in tokenize(text):
        if should_exclude(word, sentence_start):
            continue
        counts[normalize_word(word)] += 1

    return counts


def top_words(counts: Counter[str], maxwords: int) -> list[tuple[str, int]]:
    if maxwords < 1:
        raise ValueError("maxwords must be at least 1")

    ranked = counts.most_common(maxwords)
    if not ranked:
        raise ValueError("No words remain after filtering; cannot build a word cloud")

    return ranked
