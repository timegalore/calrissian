"""Word frequency analysis."""

from __future__ import annotations

from collections import Counter

from calrission.word_filter import (
    display_form,
    merge_display_form,
    normalize_word,
    should_exclude,
    tokenize,
)


def count_words(text: str) -> tuple[Counter[str], dict[str, str]]:
    counts: Counter[str] = Counter()
    display_forms: dict[str, str] = {}

    for word, sentence_start in tokenize(text):
        if should_exclude(word, sentence_start):
            continue
        key = normalize_word(word)
        counts[key] += 1
        if key in display_forms:
            display_forms[key] = merge_display_form(display_forms[key], word)
        else:
            display_forms[key] = display_form(word)

    return counts, display_forms


def top_words(
    counts: Counter[str],
    maxwords: int,
    display_forms: dict[str, str] | None = None,
) -> list[tuple[str, int]]:
    if maxwords < 1:
        raise ValueError("maxwords must be at least 1")

    ranked = counts.most_common(maxwords)
    if not ranked:
        raise ValueError("No words remain after filtering; cannot build a word cloud")

    if display_forms is None:
        return ranked
    return [(display_forms.get(word, word), count) for word, count in ranked]
